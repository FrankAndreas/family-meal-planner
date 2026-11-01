"""Was habe ich? Recipes from the family's own collection for what's at home (spec 2026-11-01)."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from . import auth, models, schemas
from .database import get_db
from .pantry import canonical, covered, matches
from .recipes_api import Votes, live_recipes
from .settings_store import get_settings
from .text import sort_key

router = APIRouter(tags=["use-up"])

# Jetzt kochen: recipes missing more than this aren't shown
MAX_MISSING = 2
MAX_NAMES = 10


def _optional(ingredient: models.RecipeIngredient) -> bool:
    note = sort_key(ingredient.note or "")
    return "belieben" in note or "optional" in note


def _typed(have: list[str]) -> list[str]:
    """The typed words without blanks, one per synonym group (as first typed)."""
    seen: set[str] = set()
    result = []
    for word in (h.strip() for h in have):
        if word and canonical(word) not in seen:
            seen.add(canonical(word))
            result.append(word)
    return result


@router.get("/use-up", response_model=list[schemas.UseUpOut])
def use_up(
    have: list[str] = Query([], max_length=20),
    mode: Literal["use_up", "cook_now"] = "use_up",
    me: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    typed = _typed(have)
    if not typed:
        return []
    staples = get_settings(db).staples
    hits = []
    for recipe in live_recipes(db):
        used = [word for word in typed if any(matches(word, i.name) for i in recipe.ingredients)]
        if not used:
            continue
        missing: list[str] = []
        for i in recipe.ingredients:
            if _optional(i) or any(matches(word, i.name) for word in typed) or covered(i.name, staples):
                continue
            # The same thing in two groups ("Butter" for dough and topping) is one thing to buy
            if canonical(i.name) not in {canonical(m) for m in missing}:
                missing.append(i.name)
        if mode == "cook_now" and len(missing) > MAX_MISSING:
            continue
        hits.append((recipe, used, missing))

    votes = Votes(db, [recipe.id for recipe, _, _ in hits])
    summaries = {recipe.id: votes.summary(recipe, me) for recipe, _, _ in hits}

    def order(hit):
        recipe, used, missing = hit
        # Never eaten counts as longest ago
        eaten = summaries[recipe.id]["last_eaten"] or date.min
        fit = (-len(used), len(missing)) if mode == "use_up" else (len(missing), -len(used))
        return (*fit, eaten, sort_key(recipe.title))

    return [
        {**summaries[recipe.id], "used": used, "missing": missing} for recipe, used, missing in sorted(hits, key=order)
    ]


@router.get("/ingredient-names", response_model=list[str])
def ingredient_names(
    q: str = "", _user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)
):
    """Ingredient names of the collection containing `q`, those starting with it first: so people type the words the
    recipes use."""
    needle = sort_key(q.strip())
    if not needle:
        return []
    names: dict[str, str] = {}
    for recipe in live_recipes(db):
        for ingredient in recipe.ingredients:
            key = sort_key(ingredient.name.strip())
            if needle in key:
                names.setdefault(key, ingredient.name.strip())
    keys = sorted(names, key=lambda k: (not k.startswith(needle), k))
    return [names[k] for k in keys[:MAX_NAMES]]
