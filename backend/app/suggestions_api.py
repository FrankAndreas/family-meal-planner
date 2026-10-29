"""What to cook next week: the suggestion panel's tabs on the planning screen."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import auth, models, schemas, timeutil
from .database import get_db
from .recipes_api import Votes, filter_recipes, live_recipes, sort_key

router = APIRouter(tags=["suggestions"])

# "Lange her" leaves out what the family didn't like
MIN_AVERAGE_LONG_AGO = 3


def _skipped_not_replanned(db: Session) -> dict[int, date]:
    """Recipes marked not eaten (in the past) and not planned on any later day: when they were skipped."""
    skipped = dict(
        db.query(models.PlanEntry.recipe_id, func.max(models.PlanEntry.date))
        .filter(
            models.PlanEntry.recipe_id.isnot(None),
            models.PlanEntry.eaten.is_(False),
            models.PlanEntry.date < timeutil.today(),
        )
        .group_by(models.PlanEntry.recipe_id)
        .all()
    )
    latest = dict(
        db.query(models.PlanEntry.recipe_id, func.max(models.PlanEntry.date))
        .filter(models.PlanEntry.recipe_id.in_(list(skipped)))
        .group_by(models.PlanEntry.recipe_id)
        .all()
    )
    return {rid: day for rid, day in skipped.items() if latest[rid] <= day}


@router.get("/suggestions", response_model=list[schemas.RecipeSummary])
def suggestions(
    tab: Literal["favorites", "long_ago", "new", "again"],
    q: str = "",
    tag: str = "",
    limit: int = Query(50, ge=1, le=200),
    me: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    recipes = filter_recipes(live_recipes(db), q, tag)
    votes = Votes(db, [r.id for r in recipes])
    summaries = {r.id: votes.summary(r, me) for r in recipes}
    by_title = sorted(recipes, key=lambda r: sort_key(r.title))

    if tab == "favorites":
        chosen = [r for r in by_title if summaries[r.id]["favorite_count"]]
        # Best average first; unrated ones after all rated ones
        chosen.sort(key=lambda r: -(summaries[r.id]["rating_avg"] or 0))
    elif tab == "long_ago":
        chosen = [
            r
            for r in by_title
            if summaries[r.id]["times_eaten"]
            and (summaries[r.id]["rating_avg"] is None or summaries[r.id]["rating_avg"] >= MIN_AVERAGE_LONG_AGO)
        ]
        chosen.sort(key=lambda r: summaries[r.id]["last_eaten"])
    elif tab == "new":
        chosen = [r for r in recipes if not summaries[r.id]["times_eaten"]]
        chosen.sort(key=lambda r: (r.created_at, r.id), reverse=True)
    else:
        skipped = _skipped_not_replanned(db)
        chosen = [r for r in by_title if r.id in skipped]
        chosen.sort(key=lambda r: skipped[r.id], reverse=True)
    return [summaries[r.id] for r in chosen[:limit]]
