"""The recipe collection, for every part of the app: finding recipes, and their ratings and favourites."""

from sqlalchemy.orm import Session, selectinload

from . import categories, models, stats
from .errors import NotFound
from .text import sort_key


def photo_url(recipe: models.Recipe) -> str | None:
    return f"/api/photos/{recipe.photo}" if recipe.photo else None


def total_minutes(recipe: models.Recipe) -> int | None:
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
            "photo_url": photo_url(recipe),
            "tags": recipe.tags,
            "categories": categories.clean(recipe.categories),
            "servings": recipe.servings,
            "servings_unit": recipe.servings_unit,
            "total_minutes": total_minutes(recipe),
            "rating_avg": round(sum(r.stars for r in ratings) / len(ratings), 2) if ratings else None,
            "rating_count": len(ratings),
            "my_rating": next((r.stars for r in ratings if r.user_id == me.id), None),
            "my_favorite": me.id in favorites,
            "favorite_count": len(favorites),
            "last_eaten": self.eaten[recipe.id][0],
            "times_eaten": self.eaten[recipe.id][1],
        }


def get_recipe(db: Session, recipe_id: int, *, allow_deleted: bool = False) -> models.Recipe:
    recipe = db.get(models.Recipe, recipe_id)
    if recipe is None or (recipe.deleted_at is not None and not allow_deleted):
        raise NotFound("recipe_not_found")
    return recipe


def live_recipes(db: Session) -> list[models.Recipe]:
    return (
        db.query(models.Recipe)
        .filter(models.Recipe.deleted_at.is_(None))
        .options(selectinload(models.Recipe.ingredients))
        .all()
    )


def filter_recipes(recipes: list[models.Recipe], q: str, tag: str, category: str = "") -> list[models.Recipe]:
    """`q` in the title, a tag or an ingredient; `tag` one of the tags (both ignore case and accents); `category` one
    of the categories, or "none" for recipes without any."""
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
    if category == "none":
        recipes = [r for r in recipes if not categories.clean(r.categories)]
    elif category:
        recipes = [r for r in recipes if category in r.categories]
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
