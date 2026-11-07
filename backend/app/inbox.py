"""An inbox item's life, the moves in one place:
- add: a child's item waits for a parent; a parent's is released at once;
- release (a parent): waiting or failed → processing;
- fail / finish (the importer): processing → failed / draft;
- saved_as (saving the draft as a recipe): draft → done.
Processing that never ended (the backend restarted meanwhile) counts as failed after STUCK_AFTER (unstick)."""

from datetime import timedelta

from sqlalchemy.orm import Session

from . import models
from .errors import NotFound, Refused
from .inbox_files import raw_path
from .models import InboxStatus
from .timeutil import utcnow

STUCK_AFTER = timedelta(minutes=10)
# Still on their way to a recipe: waiting for a parent, being read, or a draft to check
OPEN = (InboxStatus.WAITING, InboxStatus.PROCESSING, InboxStatus.DRAFT)


class ItemBusy(Refused):
    status = 409

    def __init__(self) -> None:
        super().__init__("item_busy")


class DraftNotReady(Refused):
    def __init__(self) -> None:
        super().__init__("draft_not_ready")


def add(db: Session, user: models.User, item: models.InboxItem, raw: bytes | None = None) -> bool:
    """Store a new item from `user`, with its mail (`raw`) if it has one. True if it was released (a parent's): then
    the caller starts the importer."""
    item.user_id = user.id
    item.status = InboxStatus.PROCESSING if user.is_parent else InboxStatus.WAITING
    if user.is_parent:
        item.processing_since = utcnow()
    db.add(item)
    db.flush()
    if raw is not None:
        raw_path(item).write_bytes(raw)
    db.commit()
    return user.is_parent


def release(db: Session, item: models.InboxItem) -> None:
    """A parent's go: only now is it read, are links fetched and may the AI see it."""
    if item.status in (InboxStatus.PROCESSING, InboxStatus.DONE):
        raise ItemBusy()
    item.status, item.error, item.processing_since = InboxStatus.PROCESSING, None, utcnow()
    db.commit()


def fail(db: Session, item: models.InboxItem, code: str) -> None:
    item.status, item.error, item.processing_since = InboxStatus.FAILED, code, None
    db.commit()


def finish(db: Session, item: models.InboxItem, draft: dict, raw: str | None = None) -> None:
    item.status, item.error, item.draft, item.ai_raw, item.processing_since = InboxStatus.DRAFT, None, draft, raw, None
    db.commit()


def check_draft(item: models.InboxItem) -> None:
    """Only a draft can be saved as a recipe."""
    if item.status != InboxStatus.DRAFT:
        raise DraftNotReady()


def saved_as(item: models.InboxItem, recipe_id: int) -> None:
    """The draft became this recipe; committed with it."""
    item.status, item.recipe_id = InboxStatus.DONE, recipe_id


def unstick(db: Session) -> None:
    stuck = db.query(models.InboxItem).filter(
        models.InboxItem.status == InboxStatus.PROCESSING, models.InboxItem.processing_since < utcnow() - STUCK_AFTER
    )
    for item in stuck:
        item.status, item.error, item.processing_since = InboxStatus.FAILED, "ai_failed", None
    db.commit()


def visible(db: Session, item_id: int, user: models.User) -> models.InboxItem:
    """An item the person may see (User.may_see)."""
    item = db.get(models.InboxItem, item_id)
    if item is None or not user.may_see(item.user_id):
        raise NotFound("item_not_found")
    return item
