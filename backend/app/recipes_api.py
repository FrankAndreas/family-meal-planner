import unicodedata

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, selectinload

from . import auth, models, photos, scaling, schemas, stats
from .database import get_db
from .errors import api_error
from .settings_store import get_settings
from .timeutil import utcnow
from .units import UNITS

router = APIRouter(tags=["recipes"])


def sort_key(text: str) -> str:
    """Text without case and accents: sorts "Älplermagronen" next to "Apfelwähe" (not after "Zopf"), and lets a
    search for "alpler" find it."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _photo_url(recipe: models.Recipe) -> str | None:
    return f"/api/photos/{recipe.photo}" if recipe.photo else None


def _total_minutes(recipe: models.Recipe) -> int | None:
    if recipe.prep_minutes is None and recipe.cook_minutes is None:
        return None
    return (recipe.prep_minutes or 0) + (recipe.cook_minutes or 0)


class Votes:
    """Ratings and favourites of many recipes, loaded in two queries (for lists)."""

    def __init__(self, db: Session, recipe_ids: list[int]):
        self.ratings: dict[int, list[models.Rating]] = {rid: [] for rid in recipe_ids}
        self.favorites: dict[int, set[int]] = {rid: set() for rid in recipe_ids}
        self.eaten: dict[int, tuple] = {rid: (None, 0) for rid in recipe_ids}
        if not recipe_ids:
            return
        query = db.query(models.Rating).options(selectinload(models.Rating.user))
        for rating in query.filter(models.Rating.recipe_id.in_(recipe_ids)):
            self.ratings[rating.recipe_id].append(rating)
        for fav in db.query(models.Favorite).filter(models.Favorite.recipe_id.in_(recipe_ids)):
            self.favorites[fav.recipe_id].add(fav.user_id)
        self.eaten = stats.eaten_stats(db, recipe_ids)

    def summary(self, recipe: models.Recipe, me: models.User) -> dict:
        ratings = self.ratings[recipe.id]
        favorites = self.favorites[recipe.id]
        return {
            "id": recipe.id,
            "title": recipe.title,
            "photo_url": _photo_url(recipe),
            "tags": recipe.tags,
            "servings": recipe.servings,
            "servings_unit": recipe.servings_unit,
            "total_minutes": _total_minutes(recipe),
            "rating_avg": round(sum(r.stars for r in ratings) / len(ratings), 2) if ratings else None,
            "rating_count": len(ratings),
            "my_rating": next((r.stars for r in ratings if r.user_id == me.id), None),
            "my_favorite": me.id in favorites,
            "favorite_count": len(favorites),
            "last_eaten": self.eaten[recipe.id][0],
            "times_eaten": self.eaten[recipe.id][1],
        }


def recipe_out(
    db: Session, recipe: models.Recipe, me: models.User, people: float | None = None
) -> schemas.RecipeOut:
    factor = (
        1
        if people is None
        else scaling.factor(recipe.servings, recipe.servings_unit, people, get_settings(db).family_size)
    )
    votes = Votes(db, [recipe.id])
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
        inbox_item_id=db.query(models.InboxItem.id).filter(models.InboxItem.recipe_id == recipe.id).scalar(),
        original=recipe.original,
    )


def get_recipe(db: Session, recipe_id: int, *, allow_deleted: bool = False) -> models.Recipe:
    recipe = db.get(models.Recipe, recipe_id)
    if recipe is None or (recipe.deleted_at is not None and not allow_deleted):
        raise api_error(404, "recipe_not_found")
    return recipe


def live_recipes(db: Session) -> list[models.Recipe]:
    return (
        db.query(models.Recipe)
        .filter(models.Recipe.deleted_at.is_(None))
        .options(selectinload(models.Recipe.ingredients))
        .all()
    )


def filter_recipes(recipes: list[models.Recipe], q: str, tag: str) -> list[models.Recipe]:
    """`q` in the title, a tag or an ingredient; `tag` one of the tags. Both ignore case and accents."""
    if q.strip():
        needle = sort_key(q.strip())
        recipes = [
            r
            for r in recipes
            if needle in sort_key(r.title)
            or any(needle in sort_key(t) for t in r.tags)
            or any(needle in sort_key(i.name) for i in r.ingredients)
        ]
    if tag.strip():
        wanted = sort_key(tag.strip())
        recipes = [r for r in recipes if any(sort_key(t) == wanted for t in r.tags)]
    return recipes


def normalize_tags(db: Session, tags: list[str], except_id: int | None = None) -> list[str]:
    """Tags without blanks and duplicates; a tag the family already uses in another case keeps that spelling
    ("vegi" becomes "Vegi"), so the tag filter lists it once."""
    known: dict[str, str] = {}
    for recipe in live_recipes(db):
        if recipe.id != except_id:
            for tag in recipe.tags:
                known.setdefault(tag.casefold(), tag)
    result: list[str] = []
    for tag in (t.strip() for t in tags):
        key = tag.casefold()
        if tag and key not in {t.casefold() for t in result}:
            result.append(known.get(key, tag))
    return result


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
    favorites: str = Query("", pattern="^(|mine|any)$"),
    me: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    recipes = filter_recipes(live_recipes(db), q, tag)
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
        item = db.get(models.InboxItem, body.inbox_item_id)
        if item is None or (me.role != models.UserRole.PARENT and item.user_id != me.id):
            raise api_error(404, "item_not_found")
        if item.status != "draft":
            raise api_error(400, "draft_not_ready")
    recipe = models.Recipe(created_by=me.id)
    _apply(db, recipe, body)
    if item is not None:
        recipe.source_kind = item.kind
        recipe.photo = _draft_photo(item)
    db.add(recipe)
    db.flush()
    if item is not None:
        item.status, item.recipe_id = "done", recipe.id
    db.commit()
    return recipe_out(db, recipe, me)


def _draft_photo(item: models.InboxItem) -> str | None:
    """The draft's photo: fetched from the recipe page already, or the mail picture the AI chose."""
    draft = item.draft or {}
    if draft.get("photo") and photos.photo_path(draft["photo"]):
        return draft["photo"]
    if item.kind == "mail" and draft.get("image_attachment") is not None:
        from . import mail
        from .inbox_api import raw_path

        found = mail.attachment(raw_path(item).read_bytes(), draft["image_attachment"])
        if found and found[0].startswith("image/"):
            try:
                return photos.store_photo(found[1])
            except HTTPException:
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


@router.delete("/recipes/{recipe_id}/photo", response_model=schemas.RecipeOut)
def remove_photo(recipe_id: int, me: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    recipe = get_recipe(db, recipe_id)
    old, recipe.photo = recipe.photo, None
    db.commit()
    photos.delete_photo(old)
    return recipe_out(db, recipe, me)


# Without login: <img> can't send the token. The names are random, and the app is only reachable at home
@router.get("/photos/{name}")
def read_photo(name: str):
    path = photos.photo_path(name)
    if path is None or not path.is_file():
        raise api_error(404, "photo_not_found")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=31536000, immutable"})
