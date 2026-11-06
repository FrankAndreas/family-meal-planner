"""The shared shopping list and sending it to Bring! (spec 2026-11-06). Parents only.

The list stores only the parents' decisions (ticked meals, choices per line, free items); every read works the lines
out from the plan, so amounts follow changes to the plan. A send carries the version the sender saw and is refused
when the list has changed since, so nothing goes to Bring! that nobody looked at."""

import hashlib
import json
from datetime import timedelta

from fastapi import APIRouter, Depends, Response
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import auth, bring, models, scaling, schemas
from .database import get_db
from .errors import api_error
from .plan_api import entries_in_week
from .settings_store import get_settings
from .shopping import Source, combine, line_key
from .timeutil import utcnow
from .weeks import week_start_of

router = APIRouter(tags=["shopping"])


# --- Bring! login -------------------------------------------------------------------------------------------------


def _login(db: Session) -> models.BringLogin | None:
    return db.get(models.BringLogin, 1)


def _bring_out(login: models.BringLogin | None) -> dict:
    if login is None:
        return {"email": None, "list_uuid": None, "list_name": None}
    return {"email": login.email, "list_uuid": login.list_uuid, "list_name": login.list_name}


def _bring_call(action):
    """Runs a Bring! call; a failure becomes the error the frontend shows."""
    try:
        return action()
    except bring.BringFailed as failed:
        raise api_error(400 if failed.code == "bring_login_failed" else 502, failed.code)


def _lists(login: models.BringLogin) -> list[tuple[str, str]]:
    client = bring.client()
    return _bring_call(lambda: client.lists(client.login(login.email, login.password)))


def _lists_out(lists: list[tuple[str, str]]) -> dict:
    return {"lists": [{"uuid": uuid, "name": name} for uuid, name in lists]}


@router.get("/bring", response_model=schemas.BringOut)
def read_bring(_parent: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)):
    return _bring_out(_login(db))


@router.post("/bring/login", response_model=schemas.BringListsOut)
def bring_login(body: schemas.BringLoginIn, _parent: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)):
    """Checks the login with Bring! before storing it; a new login forgets the chosen list."""
    client = bring.client()
    lists = _bring_call(lambda: client.lists(client.login(body.email, body.password)))
    login = _login(db) or models.BringLogin(id=1)
    login.email, login.password, login.list_uuid, login.list_name = body.email, body.password, None, None
    db.add(login)
    db.commit()
    return _lists_out(lists)


def _login_or_error(db: Session) -> models.BringLogin:
    login = _login(db)
    if login is None:
        raise api_error(400, "bring_not_set_up")
    return login


@router.get("/bring/lists", response_model=schemas.BringListsOut)
def bring_lists(_parent: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)):
    return _lists_out(_lists(_login_or_error(db)))


@router.put("/bring/list", response_model=schemas.BringOut)
def choose_bring_list(body: schemas.BringListIn, _parent: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)):
    login = _login_or_error(db)
    name = dict(_lists(login)).get(body.uuid)
    if name is None:
        raise api_error(400, "bring_unknown_list")
    login.list_uuid, login.list_name = body.uuid, name
    db.commit()
    return _bring_out(login)


@router.delete("/bring", status_code=204)
def bring_logout(_parent: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)):
    login = _login(db)
    if login is not None:
        db.delete(login)
        db.commit()
    return Response(status_code=204)


# --- The list -----------------------------------------------------------------------------------------------------


def _open(db: Session) -> models.ShoppingList | None:
    return db.query(models.ShoppingList).order_by(models.ShoppingList.id).first()


def _open_or_error(db: Session) -> models.ShoppingList:
    shopping = _open(db)
    if shopping is None:
        raise api_error(404, "shopping_none")
    return shopping


def _name(db: Session, user_id: int | None) -> str | None:
    user = db.get(models.User, user_id) if user_id is not None else None
    return user.name if user else None


def _out(db: Session, shopping: models.ShoppingList) -> schemas.ShoppingOut:
    settings = get_settings(db)
    entries = entries_in_week(db, shopping.week_start)
    ticked = {meal.entry_id for meal in shopping.meals}
    sources: list[Source] = []
    meals, notes = [], []
    for entry in entries:
        if entry.recipe is None:
            if entry.note:
                notes.append({"date": entry.date, "slot": entry.slot, "note": entry.note})
            continue
        recipe = entry.recipe
        meals.append(
            {
                "entry_id": entry.id,
                "date": entry.date,
                "slot": entry.slot,
                "title": recipe.title,
                "people": entry.people,
                "ticked": entry.id in ticked,
            }
        )
        if entry.id not in ticked:
            continue
        people = entry.people or settings.family_size
        factor = scaling.factor(recipe.servings, recipe.servings_unit, people, settings.family_size)
        for ingredient in recipe.ingredients:
            sources.append(
                Source(ingredient.name, scaling.scale(ingredient.amount, ingredient.unit, factor), ingredient.unit, recipe.title)
            )
    choices = {choice.key: choice.buy for choice in shopping.choices}
    extras = [{"id": e.id, "name": e.name, "amount": e.amount} for e in shopping.extras]
    lines = [
        {
            "key": line.key,
            "name": line.name,
            "amounts": [{"amount": amount, "unit": unit} for amount, unit in line.amounts],
            "extras": line.extras,
            "meals": line.meals,
            "staple": line.staple,
            "buy": choices.get(line.key, not line.staple),
        }
        for line in combine(sources, [(e["name"], e["amount"]) for e in extras], settings.staples)
    ]
    # What would be sent: a meal planned meanwhile (unticked) or a note changes nothing in it
    content = json.dumps(lines, default=str, sort_keys=True)
    return schemas.ShoppingOut(
        week_start=shopping.week_start,
        week_end=shopping.week_start + timedelta(days=6),
        started_by=_name(db, shopping.created_by),
        changed_by=_name(db, shopping.updated_by),
        changed_at=shopping.updated_at,
        meals=meals,
        notes=notes,
        lines=lines,
        extras=extras,
        version=hashlib.sha256(content.encode()).hexdigest()[:32],
    )


def _changed(db: Session, shopping: models.ShoppingList, me: models.User) -> schemas.ShoppingOut:
    shopping.updated_by, shopping.updated_at = me.id, utcnow()
    db.commit()
    db.refresh(shopping)
    return _out(db, shopping)


@router.get("/shopping", response_model=schemas.ShoppingStateOut)
def read_shopping(_parent: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)):
    shopping = _open(db)
    return {"list": _out(db, shopping) if shopping else None}


@router.post("/shopping", response_model=schemas.ShoppingOut)
def start_shopping(body: schemas.ShoppingStartIn, me: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)):
    """Starts the list for a week with every planned recipe ticked; the open one if it is for that week."""
    if week_start_of(body.week_start, get_settings(db).week_start) != body.week_start:
        raise api_error(400, "shopping_bad_week")
    shopping = _open(db)
    if shopping is not None and shopping.week_start == body.week_start:
        return _out(db, shopping)
    if shopping is not None:
        if not body.replace:
            raise api_error(409, "shopping_other_week")
        db.delete(shopping)
        db.flush()
    shopping = models.ShoppingList(week_start=body.week_start, created_by=me.id, updated_by=me.id)
    shopping.meals = [
        models.ShoppingMeal(entry_id=e.id) for e in entries_in_week(db, body.week_start) if e.recipe_id is not None
    ]
    db.add(shopping)
    try:
        db.commit()
    except IntegrityError:
        # The other parent started one at the same moment (one list at most: `singleton` is unique)
        db.rollback()
        shopping = db.query(models.ShoppingList).one()
        if shopping.week_start != body.week_start:
            raise api_error(409, "shopping_other_week")
        return _out(db, shopping)
    db.refresh(shopping)
    return _out(db, shopping)


@router.delete("/shopping", status_code=204)
def discard_shopping(_parent: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)):
    shopping = _open(db)
    if shopping is not None:
        db.delete(shopping)
        db.commit()
    return Response(status_code=204)


@router.put("/shopping/meals/{entry_id}", response_model=schemas.ShoppingOut)
def tick_meal(
    entry_id: int, body: schemas.ShoppingTickIn, me: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)
):
    shopping = _open_or_error(db)
    if entry_id not in {e.id for e in entries_in_week(db, shopping.week_start) if e.recipe_id is not None}:
        raise api_error(400, "shopping_not_in_week")
    # Written so that the other parent doing the same at the same moment is no conflict
    if body.ticked:
        db.execute(insert(models.ShoppingMeal).values(list_id=shopping.id, entry_id=entry_id).on_conflict_do_nothing())
    else:
        db.query(models.ShoppingMeal).filter_by(list_id=shopping.id, entry_id=entry_id).delete()
    return _changed(db, shopping, me)


def _choose(db: Session, shopping: models.ShoppingList, key: str, buy: bool) -> None:
    """Sets a line's choice; the same choice made by the other parent at the same moment is no conflict."""
    db.execute(
        insert(models.ShoppingChoice)
        .values(list_id=shopping.id, key=key, buy=buy)
        .on_conflict_do_update(index_elements=["list_id", "key"], set_={"buy": buy})
    )


@router.put("/shopping/lines", response_model=schemas.ShoppingOut)
def choose_line(body: schemas.ShoppingChoiceIn, me: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)):
    """buy: False drops the line, True keeps it (also a staple), None goes back to the default."""
    shopping = _open_or_error(db)
    if body.buy is None:
        db.query(models.ShoppingChoice).filter_by(list_id=shopping.id, key=body.key).delete()
    else:
        _choose(db, shopping, body.key, body.buy)
    return _changed(db, shopping, me)


@router.post("/shopping/extras", response_model=schemas.ShoppingOut)
def add_extra(body: schemas.ShoppingExtraIn, me: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)):
    shopping = _open_or_error(db)
    position = max((e.position for e in shopping.extras), default=-1) + 1
    db.add(models.ShoppingExtra(list_id=shopping.id, name=body.name, amount=body.amount, position=position))
    # Asked for by name: bought, even if the line of that name was dropped or is usually at home
    _choose(db, shopping, line_key(body.name), True)
    return _changed(db, shopping, me)


@router.delete("/shopping/extras/{extra_id}", response_model=schemas.ShoppingOut)
def remove_extra(extra_id: int, me: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)):
    shopping = _open_or_error(db)
    extra = db.get(models.ShoppingExtra, extra_id)
    if extra is not None and extra.list_id == shopping.id:
        db.delete(extra)
    return _changed(db, shopping, me)


@router.post("/shopping/send", response_model=schemas.ShoppingSentOut)
def send_shopping(body: schemas.ShoppingSendIn, _parent: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)):
    """Sends the lines to buy, with the amount texts the sender saw, and deletes the list once Bring! has them."""
    shopping = _open_or_error(db)
    login = _login(db)
    if login is None or not login.list_uuid:
        raise api_error(400, "bring_not_set_up")
    current = _out(db, shopping)
    if current.version != body.version:
        raise api_error(409, "shopping_changed")
    items = [(line.name, body.specs.get(line.key, "")) for line in current.lines if line.buy]
    if not items:
        raise api_error(400, "shopping_empty")
    client = bring.client()
    try:
        client.add(client.login(login.email, login.password), login.list_uuid, items)
    except bring.BringFailed as failed:
        raise api_error(502, failed.code)
    # Someone changed the list while Bring! was called: keep it, so that change isn't thrown away unseen
    db.expire_all()
    shopping = _open(db)
    if shopping is not None and _out(db, shopping).version != body.version:
        return {"sent": len(items), "kept": True}
    if shopping is not None:
        db.delete(shopping)
        db.commit()
    return {"sent": len(items), "kept": False}
