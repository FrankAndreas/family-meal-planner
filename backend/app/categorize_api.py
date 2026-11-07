"""The AI sorts recipes that have no category yet (spec 2026-11-05): parents only, several recipes per AI call, and
never over categories someone set."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from . import ai, auth, categories, models, schemas
from .database import get_db
from .http_errors import api_error
from .recipes import get_recipe, live_recipes
from .timeutil import utcnow

router = APIRouter(tags=["categories"])

# Recipes per AI call, and the ingredient names sent for each (title, tags and names say enough; steps never go out)
BATCH = 25
MAX_INGREDIENTS = 15


def _untried(db: Session) -> list[models.Recipe]:
    """Live recipes without categories the AI hasn't been asked about yet, oldest first."""
    recipes = [r for r in live_recipes(db) if not categories.clean(r.categories) and r.ai_categorized_at is None]
    return sorted(recipes, key=lambda r: r.id)


def _sent(recipe: models.Recipe) -> dict:
    return {
        "id": recipe.id,
        "title": recipe.title,
        "tags": list(recipe.tags),
        "ingredients": [i.name for i in recipe.ingredients[:MAX_INGREDIENTS]],
    }


@router.get("/recipes/categorize", response_model=schemas.CategorizeLeft)
def categorize_left(_parent: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)):
    return {"remaining": len(_untried(db))}


@router.post("/recipes/categorize", response_model=schemas.CategorizeOut)
def categorize(
    body: schemas.CategorizeIn, parent: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)
):
    """One batch: the recipe asked for, or the next recipes nobody sorted yet."""
    if body.recipe_id is not None:
        recipe = get_recipe(db, body.recipe_id)
        if categories.clean(recipe.categories):
            raise api_error(400, "already_categorized")
        batch = [recipe]
    else:
        batch = _untried(db)[:BATCH]
    if not batch:
        return {"categorized": 0, "remaining": 0}
    call = ai.take_call(db, parent, "categorize", recipe_id=body.recipe_id)
    try:
        found, tokens = ai.categorize(ai.client_for(ai.Settings.from_env()), [_sent(r) for r in batch])
    except ai.AiFailed:
        raise api_error(502, "categorize_failed")
    call.tokens = tokens
    done = 0
    now = utcnow()
    for recipe in batch:
        # Someone may have set categories while the AI was thinking: theirs stay
        db.refresh(recipe)
        recipe.ai_categorized_at = now
        if found.get(recipe.id) and not categories.clean(recipe.categories):
            recipe.categories = found[recipe.id]
            done += 1
    db.commit()
    return {"categorized": done, "remaining": len(_untried(db))}
