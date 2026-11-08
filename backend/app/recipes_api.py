from typing import Literal

from fastapi import APIRouter, Depends, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from . import ai, auth, categories, config, fetch, inbox, inbox_files, jsonld, mail, models, photos, scaling, schemas
from .database import get_db
from .http_errors import api_error
from .models import InboxKind
from .recipes import Votes, filter_recipes, get_recipe, live_recipes, normalize_tags
from .settings_store import get_settings
from .text import sort_key
from .timeutil import utcnow
from .units import UNITS

router = APIRouter(tags=["recipes"])


def recipe_out(
    db: Session, recipe: models.Recipe, me: models.User, people: float | None = None
) -> schemas.RecipeOut:
    factor = (
        1
        if people is None
        else scaling.factor(recipe.servings, recipe.servings_unit, people, get_settings(db).family_size)
    )
    votes = Votes(db, [recipe.id])
    item = db.query(models.InboxItem).filter(models.InboxItem.recipe_id == recipe.id).first()
    ratings = sorted(votes.ratings[recipe.id], key=lambda r: r.user.name_key)
    return schemas.RecipeOut(
        **votes.summary(recipe, me),
        prep_minutes=recipe.prep_minutes,
        cook_minutes=recipe.cook_minutes,
        steps=recipe.steps,
        notes=recipe.notes,
        source_kind=recipe.source_kind,
        source_url=recipe.source_url,
        language=recipe.language,
        created_by_name=recipe.creator.name if recipe.creator else None,
        deleted=recipe.deleted_at is not None,
        ingredients=[
            schemas.IngredientOut(
                id=i.id,
                group=i.group,
                amount=i.amount,
                unit=i.unit,
                name=i.name,
                note=i.note,
                scaled_amount=scaling.scale(i.amount, i.unit, factor),
            )
            for i in recipe.ingredients
        ],
        ratings=[schemas.RatingOut(user_id=r.user_id, name=r.user.name, stars=r.stars) for r in ratings],
        people=people,
        factor=factor,
        inbox_item_id=item.id if item else None,
        source_mail=schemas.SourceMail(
            id=item.id, kind=item.kind, user_name=item.user.name if item.user else None, received_at=item.received_at
        )
        if item
        else None,
        original=recipe.original,
        # Not in the family's language (or unknown, from outside): into which a parent can have it translated
        translate_into=_translate_into(recipe),
    )


def _translate_into(recipe: models.Recipe) -> str | None:
    target = config.default_language()
    if recipe.language == target or (recipe.language is None and recipe.source_kind == "manual"):
        return None
    return target


def _apply(db: Session, recipe: models.Recipe, body: schemas.RecipeIn) -> None:
    data = body.model_dump(exclude={"ingredients", "tags", "inbox_item_id"})
    for key, value in data.items():
        setattr(recipe, key, value)
    recipe.tags = normalize_tags(db, body.tags, except_id=recipe.id)
    recipe.ingredients = [
        models.RecipeIngredient(position=n, **ingredient.model_dump()) for n, ingredient in enumerate(body.ingredients)
    ]


@router.get("/recipes", response_model=list[schemas.RecipeSummary])
def list_recipes(
    q: str = "",
    tag: str = "",
    category: str = Query("", pattern=f"^(|none|{'|'.join(categories.CATEGORIES)})$"),
    favorites: str = Query("", pattern="^(|mine|any)$"),
    me: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    recipes = filter_recipes(live_recipes(db), q, tag, category)
    votes = Votes(db, [r.id for r in recipes])
    if favorites == "mine":
        recipes = [r for r in recipes if me.id in votes.favorites[r.id]]
    elif favorites == "any":
        recipes = [r for r in recipes if votes.favorites[r.id]]
    recipes.sort(key=lambda r: sort_key(r.title))
    return [votes.summary(r, me) for r in recipes]


@router.post("/recipes", response_model=schemas.RecipeOut, status_code=201)
def create_recipe(
    body: schemas.RecipeIn, me: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)
):
    item = None
    if body.inbox_item_id is not None:
        item = inbox.visible(db, body.inbox_item_id, me)
        inbox.check_draft(item)
    recipe = models.Recipe(created_by=me.id)
    _apply(db, recipe, body)
    if item is not None:
        recipe.source_kind = item.kind
        recipe.photo = _draft_photo(item)
        recipe.original = _draft_original(item.draft or {}, recipe.ingredients)
    db.add(recipe)
    db.flush()
    if item is not None:
        inbox.saved_as(item, recipe.id)
    db.commit()
    return recipe_out(db, recipe, me)


def _draft_original(draft: dict, saved: list[models.RecipeIngredient]) -> dict | None:
    """Translated while imported: the text before, to show as the original. Its ingredients follow the saved ones
    (the original is shown by position): each saved one takes the original of the draft's ingredient it still is (by
    name), one added or renamed while checking the draft its own text."""
    original = draft.get("original")
    if not isinstance(original, dict) or not isinstance(original.get("ingredients"), list):
        return None
    translated = [str((i or {}).get("name") or "") for i in draft.get("ingredients") or []]
    before = original["ingredients"]
    taken: set[int] = set()
    ingredients = []
    for ingredient in saved:
        match = next((n for n, name in enumerate(translated) if name == ingredient.name and n not in taken), None)
        if match is not None and match < len(before) and isinstance(before[match], dict):
            taken.add(match)
            ingredients.append(before[match])
        else:
            ingredients.append({"name": ingredient.name, "note": ingredient.note})
    return {**original, "ingredients": ingredients}


def _draft_photo(item: models.InboxItem) -> str | None:
    """The draft's photo: fetched from the recipe page already, or the mail picture the AI chose."""
    draft = item.draft or {}
    if draft.get("photo") and photos.photo_path(draft["photo"]):
        return draft["photo"]
    if item.kind in (InboxKind.MAIL, InboxKind.SCAN) and draft.get("image_attachment") is not None:
        found = mail.attachment(inbox_files.raw_path(item).read_bytes(), draft["image_attachment"])
        if found and found[0].startswith("image/"):
            try:
                return photos.store_photo(found[1])
            except photos.PhotoUnreadable:
                return None
    return None


@router.get("/recipes/{recipe_id}", response_model=schemas.RecipeOut)
def read_recipe(
    recipe_id: int,
    people: float | None = Query(None, gt=0, le=100),
    me: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    return recipe_out(db, get_recipe(db, recipe_id, allow_deleted=True), me, people)


@router.put("/recipes/{recipe_id}", response_model=schemas.RecipeOut)
def update_recipe(
    recipe_id: int,
    body: schemas.RecipeIn,
    me: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    recipe = get_recipe(db, recipe_id)
    _apply(db, recipe, body)
    db.commit()
    return recipe_out(db, recipe, me)


@router.delete("/recipes/{recipe_id}", status_code=204)
def delete_recipe(
    recipe_id: int, _parent: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)
):
    get_recipe(db, recipe_id).deleted_at = utcnow()
    db.commit()


@router.get("/tags", response_model=list[schemas.TagCount])
def list_tags(_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    counts: dict[str, int] = {}
    for recipe in live_recipes(db):
        for tag in recipe.tags:
            counts[tag] = counts.get(tag, 0) + 1
    return [{"name": name, "count": count} for name, count in sorted(counts.items(), key=lambda kv: sort_key(kv[0]))]


@router.get("/units")
def list_units(_user: models.User = Depends(auth.get_current_user)):
    return list(UNITS)


@router.put("/recipes/{recipe_id}/rating", response_model=schemas.RecipeOut)
def rate_recipe(
    recipe_id: int,
    body: schemas.RatingIn,
    me: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    recipe = get_recipe(db, recipe_id)
    rating = db.get(models.Rating, (recipe.id, me.id))
    if body.stars is None:
        if rating is not None:
            db.delete(rating)
    elif rating is None:
        db.add(models.Rating(recipe_id=recipe.id, user_id=me.id, stars=body.stars))
    else:
        rating.stars = body.stars
    db.commit()
    return recipe_out(db, recipe, me)


@router.put("/recipes/{recipe_id}/favorite", response_model=schemas.RecipeOut)
def favorite_recipe(
    recipe_id: int,
    body: schemas.FavoriteIn,
    me: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    recipe = get_recipe(db, recipe_id)
    favorite = db.get(models.Favorite, (recipe.id, me.id))
    if body.favorite and favorite is None:
        db.add(models.Favorite(recipe_id=recipe.id, user_id=me.id))
    elif not body.favorite and favorite is not None:
        db.delete(favorite)
    db.commit()
    return recipe_out(db, recipe, me)


@router.post("/recipes/{recipe_id}/photo", response_model=schemas.RecipeOut)
async def upload_photo(
    recipe_id: int,
    file: UploadFile,
    me: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    recipe = get_recipe(db, recipe_id)
    data = await file.read(photos.MAX_BYTES + 1)
    if len(data) > photos.MAX_BYTES:
        raise api_error(413, "photo_too_large")
    old, recipe.photo = recipe.photo, photos.store_photo(data)
    db.commit()
    photos.delete_photo(old)
    return recipe_out(db, recipe, me)


@router.post("/recipes/{recipe_id}/photo-url", response_model=schemas.RecipeOut)
def photo_from_link(
    recipe_id: int,
    body: schemas.UrlIn,
    me: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """A picture's link, or a page's: then the picture it shows when shared. Only public web servers (see fetch)."""
    recipe = get_recipe(db, recipe_id)
    try:
        found = fetch.fetch(body.url, accept=("image/", *fetch.PAGE_TYPES))
        if not found.content_type.startswith("image/"):
            image_url = jsonld.page_image(found.text, found.url)
            if not image_url:
                raise api_error(400, "photo_link_failed")
            found = fetch.fetch(image_url, accept=("image/",))
    except (fetch.FetchFailed, fetch.FetchRefused):
        raise api_error(400, "photo_link_failed")
    old, recipe.photo = recipe.photo, photos.store_photo(found.body)
    db.commit()
    photos.delete_photo(old)
    return recipe_out(db, recipe, me)


@router.delete("/recipes/{recipe_id}/photo", response_model=schemas.RecipeOut)
def remove_photo(recipe_id: int, me: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    recipe = get_recipe(db, recipe_id)
    old, recipe.photo = recipe.photo, None
    db.commit()
    photos.delete_photo(old)
    return recipe_out(db, recipe, me)


# Without login: <img> can't send the token. The names are random (unguessable); from outside Cloudflare Access lets
# only the family through
@router.get("/photos/{name}")
def read_photo(name: str, size: Literal["full", "card"] = "full"):
    """`size=card`: the small version recipe cards show."""
    path = photos.card_path(name) if size == "card" else photos.photo_path(name)
    if path is None or not path.is_file():
        raise api_error(404, "photo_not_found")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=31536000, immutable"})


@router.post("/recipes/{recipe_id}/translate", response_model=schemas.RecipeOut)
def translate_recipe(recipe_id: int, parent: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)):
    """The recipe in the family's language (DEFAULT_LANGUAGE), by the AI; amounts and units stay, the text before is
    kept as the original."""
    recipe = get_recipe(db, recipe_id)
    target = config.default_language()
    if recipe.language == target:
        raise api_error(400, "already_translated")
    text = {
        "title": recipe.title,
        "ingredients": [{"name": i.name, "note": i.note} for i in recipe.ingredients],
        "steps": list(recipe.steps),
        "notes": recipe.notes,
        "tags": list(recipe.tags),
    }
    call = ai.take_call(db, parent, "translate", recipe_id=recipe.id)
    try:
        german, tokens = ai.translate(ai.client_for(ai.Settings.from_env()), text, target)
    except ai.AiFailed:
        raise api_error(502, "ai_failed")
    call.tokens = tokens
    # A second translation (after edits) keeps the very first original
    if recipe.original is None:
        recipe.original = {**text, "language": recipe.language}
    recipe.title, recipe.steps, recipe.notes, recipe.language = german["title"], german["steps"], german["notes"], target
    # In the spelling the family already uses for a tag ("vegi" → "Vegi")
    recipe.tags = normalize_tags(db, german["tags"], except_id=recipe.id)
    for ingredient, new in zip(recipe.ingredients, german["ingredients"]):
        ingredient.name, ingredient.note = new["name"], new["note"]
    db.commit()
    return recipe_out(db, recipe, parent)
