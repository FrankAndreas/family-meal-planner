from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import ai, auth, models
from .database import get_db
from .timeutil import utcnow

router = APIRouter(tags=["ai"])


@router.get("/ai/status")
def ai_status(user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    settings = ai.Settings.from_env()
    left = max(0, settings.calls_per_hour - len(ai.calls_last_hour(db, user, utcnow()))) if settings.enabled else 0
    return {"enabled": settings.enabled, "calls_left_this_hour": left}


@router.get("/ai/usage")
def ai_usage(_parent: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)):
    """AI calls this month per person, and all calls ever (the costs themselves are in Infomaniak's manager)."""
    now = utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    rows = (
        db.query(models.User.name, func.count(models.AiCall.id))
        .join(models.User, models.User.id == models.AiCall.user_id)
        .filter(models.AiCall.at >= month_start)
        .group_by(models.User.name)
        .order_by(models.User.name)
        .all()
    )
    return {"month": [{"user_name": name, "calls": calls} for name, calls in rows], "total": db.query(models.AiCall).count()}
