from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from . import auth, models, schemas, stats, timeutil
from .database import get_db
from .errors import api_error
from .recipes_api import Votes, get_recipe
from .settings_store import get_settings
from .weeks import week_days, week_start_of

router = APIRouter(tags=["plan"])

SLOTS = ("breakfast", "snack", "lunch", "dinner")


def _entries(db: Session, first: date, last: date) -> list[models.PlanEntry]:
    entries = (
        db.query(models.PlanEntry)
        .filter(models.PlanEntry.date >= first, models.PlanEntry.date <= last)
        .options(selectinload(models.PlanEntry.recipe))
        .all()
    )
    entries.sort(key=lambda e: (e.date, SLOTS.index(e.slot), e.position, e.id))
    return entries


def entries_out(db: Session, entries: list[models.PlanEntry], me: models.User) -> list[schemas.EntryOut]:
    votes = Votes(db, sorted({e.recipe_id for e in entries if e.recipe_id is not None}))
    return [
        schemas.EntryOut(
            id=e.id,
            date=e.date,
            slot=e.slot,
            position=e.position,
            recipe=votes.summary(e.recipe, me) if e.recipe else None,
            recipe_deleted=bool(e.recipe and e.recipe.deleted_at),
            note=e.note,
            people=e.people,
            eaten=e.eaten,
        )
        for e in entries
    ]


def _closed(db: Session, first: date, last: date) -> bool:
    """All days inside stored closures: after a change of the first day, a week only partly closed shows open."""
    closures = db.query(models.WeekClosure).filter(models.WeekClosure.start <= last, models.WeekClosure.end >= first)
    covered = {c.start + timedelta(days=n) for c in closures for n in range((c.end - c.start).days + 1)}
    return all(day in covered for day in week_days(first))


def _needs_closing(db: Session, start: date) -> bool:
    first, last = start - timedelta(days=7), start - timedelta(days=1)
    # A week can be closed on its last day: Friday's planning session starts by closing the week ending today
    if last > timeutil.today() or _closed(db, first, last):
        return False
    return (
        db.query(models.PlanEntry.id)
        .filter(models.PlanEntry.date >= first, models.PlanEntry.date <= last, models.PlanEntry.recipe_id.isnot(None))
        .first()
        is not None
    )


def week_out(db: Session, start: date, me: models.User) -> schemas.WeekOut:
    days = week_days(start)
    entries = _entries(db, days[0], days[-1])
    return schemas.WeekOut(
        start=days[0],
        end=days[-1],
        days=days,
        today=timeutil.today(),
        entries=entries_out(db, entries, me),
        closed=_closed(db, days[0], days[-1]),
        previous_needs_closing=_needs_closing(db, days[0]),
        planned_slots=len({(e.date, e.slot) for e in entries}),
        total_slots=len(days) * len(SLOTS),
    )


def _get_entry(db: Session, entry_id: int) -> models.PlanEntry:
    entry = db.get(models.PlanEntry, entry_id)
    if entry is None:
        raise api_error(404, "entry_not_found")
    return entry


def _next_position(db: Session, day: date, slot: str, except_id: int | None = None) -> int:
    query = db.query(func.max(models.PlanEntry.position)).filter(
        models.PlanEntry.date == day, models.PlanEntry.slot == slot
    )
    if except_id is not None:
        query = query.filter(models.PlanEntry.id != except_id)
    highest = query.scalar()
    return 0 if highest is None else highest + 1


def _one_entry(db: Session, entry: models.PlanEntry, me: models.User) -> schemas.EntryOut:
    return entries_out(db, [entry], me)[0]


@router.get("/plan", response_model=schemas.WeekOut)
def read_week(
    start: date | None = None, me: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)
):
    # Without a date: the week of tomorrow, so on the last day of a week the planner opens on the coming one
    day = start or timeutil.today() + timedelta(days=1)
    return week_out(db, week_start_of(day, get_settings(db).week_start), me)


@router.post("/plan/entries", response_model=schemas.EntryOut, status_code=201)
def add_entry(body: schemas.EntryIn, me: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    people = None
    if body.recipe_id is not None:
        recipe = get_recipe(db, body.recipe_id, allow_deleted=True)
        if recipe.deleted_at is not None:
            raise api_error(400, "recipe_deleted")
        people = body.people or get_settings(db).family_size
    entry = models.PlanEntry(
        date=body.date,
        slot=body.slot,
        position=_next_position(db, body.date, body.slot),
        recipe_id=body.recipe_id,
        note=body.note,
        people=people,
        created_by=me.id,
    )
    db.add(entry)
    db.commit()
    return _one_entry(db, entry, me)


@router.patch("/plan/entries/{entry_id}", response_model=schemas.EntryOut)
def update_entry(
    entry_id: int,
    body: schemas.EntryPatch,
    me: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    entry = _get_entry(db, entry_id)
    moved = (body.date is not None and body.date != entry.date) or (body.slot is not None and body.slot != entry.slot)
    if body.date is not None:
        entry.date = body.date
    if body.slot is not None:
        entry.slot = body.slot
    if body.position is not None:
        entry.position = body.position
    elif moved:
        entry.position = _next_position(db, entry.date, entry.slot, except_id=entry.id)
    if body.people is not None and entry.recipe_id is not None:
        entry.people = body.people
    if body.note is not None and entry.recipe_id is None:
        entry.note = body.note
    if body.eaten is not None:
        entry.eaten = body.eaten
    db.commit()
    return _one_entry(db, entry, me)


@router.delete("/plan/entries/{entry_id}", status_code=204)
def delete_entry(entry_id: int, _user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    db.delete(_get_entry(db, entry_id))
    db.commit()


@router.post("/plan/close", response_model=schemas.WeekOut)
def close_week(body: schemas.CloseIn, me: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    start = week_start_of(body.start, get_settings(db).week_start)
    end = start + timedelta(days=6)
    if end > timeutil.today():
        raise api_error(400, "week_not_over")
    if db.get(models.WeekClosure, start) is None:
        db.add(models.WeekClosure(start=start, end=end, closed_by=me.id))
        db.commit()
    return week_out(db, start, me)


@router.get("/plan/history", response_model=list[schemas.WeekOut])
def history(
    before: date | None = None,
    weeks: int = Query(8, ge=1, le=52),
    me: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Past weeks with entries, newest first, all before the week of `before` (default: this week)."""
    week_start = get_settings(db).week_start
    limit = week_start_of(before or timeutil.today(), week_start)
    starts: list[date] = []
    for (day,) in (
        db.query(models.PlanEntry.date).filter(models.PlanEntry.date < limit).distinct().order_by(models.PlanEntry.date.desc())
    ):
        start = week_start_of(day, week_start)
        if start not in starts:
            starts.append(start)
            if len(starts) == weeks:
                break
    return [week_out(db, start, me) for start in starts]


@router.get("/recipes/{recipe_id}/history", response_model=list[date])
def recipe_history(
    recipe_id: int, _user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)
):
    get_recipe(db, recipe_id, allow_deleted=True)
    rows = (
        db.query(models.PlanEntry.date)
        .filter(models.PlanEntry.recipe_id == recipe_id, *stats.eaten_filter())
        .order_by(models.PlanEntry.date.desc())
    )
    return [day for (day,) in rows]
