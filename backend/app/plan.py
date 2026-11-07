"""The week plan's entries, for every part of the app (the plan, the shopping list)."""

from datetime import date, timedelta

from sqlalchemy.orm import Session, selectinload

from . import models

SLOTS = ("breakfast", "snack", "lunch", "dinner")


def entries_between(db: Session, first: date, last: date) -> list[models.PlanEntry]:
    entries = (
        db.query(models.PlanEntry)
        .filter(models.PlanEntry.date >= first, models.PlanEntry.date <= last)
        .options(selectinload(models.PlanEntry.recipe))
        .all()
    )
    entries.sort(key=lambda e: (e.date, SLOTS.index(e.slot), e.position, e.id))
    return entries


def entries_in_week(db: Session, start: date) -> list[models.PlanEntry]:
    """The entries of the week starting on `start`, in plan order."""
    return entries_between(db, start, start + timedelta(days=6))
