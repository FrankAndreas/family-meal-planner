from sqlalchemy.orm import Session

from . import models
from .pantry import DEFAULT_STAPLES


def ensure_settings(db: Session) -> None:
    """A fresh database gets the settings row, with the defaults (on start, see main.start)."""
    if db.get(models.Settings, 1) is None:
        db.add(models.Settings(id=1, family_size=4, week_start=5, staples=list(DEFAULT_STAPLES)))
        db.commit()


def get_settings(db: Session) -> models.Settings:
    """The single settings row (only read: the app creates it on start)."""
    settings = db.get(models.Settings, 1)
    if settings is None:
        raise LookupError("No settings row: the app creates it on start (main.start)")
    return settings
