from sqlalchemy.orm import Session

from . import models
from .pantry import DEFAULT_STAPLES


def get_settings(db: Session) -> models.Settings:
    """The single settings row, created with defaults on first use."""
    settings = db.get(models.Settings, 1)
    if settings is None:
        settings = models.Settings(id=1, family_size=4, week_start=5, staples=list(DEFAULT_STAPLES))
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings
