from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from . import auth, models, schemas
from .database import get_db
from .settings_store import get_settings

router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=schemas.SettingsOut)
def read_settings(_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    return get_settings(db)


@router.patch("/settings", response_model=schemas.SettingsOut)
def update_settings(
    body: schemas.SettingsPatch, _parent: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)
):
    settings = get_settings(db)
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(settings, key, value)
    db.commit()
    return settings
