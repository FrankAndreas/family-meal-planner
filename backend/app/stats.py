from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models, timeutil


def eaten_filter():
    """Entries that count as eaten: on a day before today, and not marked as skipped. Tonight's dinner hasn't
    happened yet."""
    return models.PlanEntry.eaten.is_(True), models.PlanEntry.date < timeutil.today()


def eaten_stats(db: Session, recipe_ids: list[int]) -> dict[int, tuple[date | None, int]]:
    """When each recipe was last eaten and how often, in one query."""
    stats: dict[int, tuple[date | None, int]] = {rid: (None, 0) for rid in recipe_ids}
    if not recipe_ids:
        return stats
    rows = (
        db.query(models.PlanEntry.recipe_id, func.max(models.PlanEntry.date), func.count())
        .filter(models.PlanEntry.recipe_id.in_(recipe_ids), *eaten_filter())
        .group_by(models.PlanEntry.recipe_id)
    )
    for recipe_id, last, count in rows:
        stats[recipe_id] = (last, count)
    return stats
