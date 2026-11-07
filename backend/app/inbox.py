"""An inbox item's life, the moves in one place:
- add: a child's item waits for a parent; a parent's is released at once;
- release (a parent): anything not processing or done → processing (the inbox offers it for waiting and failed; a
  draft released again is read anew);
- fail / finish (the importer): → failed / draft, whatever the status meanwhile (not checked);
- saved_as (saving the draft as a recipe): draft → done.
Processing that never ended (the backend restarted meanwhile) is stuck after STUCK_AFTER: worked out when read, so
looking at the inbox writes nothing. A stuck item is shown as failed (shown), no longer counts as open (is_open), and
can be released again."""

from datetime import timedelta

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from . import models
from .errors import NotFound, Refused
from .inbox_files import raw_path
from .models import InboxStatus
from .timeutil import utcnow

STUCK_AFTER = timedelta(minutes=10)


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
    if item.status == InboxStatus.DONE or (item.status == InboxStatus.PROCESSING and not _stuck(item)):
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


def _stuck(item: models.InboxItem) -> bool:
    return (
        item.status == InboxStatus.PROCESSING
        and item.processing_since is not None
        and item.processing_since < utcnow() - STUCK_AFTER
    )


def shown(item: models.InboxItem) -> tuple[str, str | None]:
    """The status and error a person sees: a stuck item as failed."""
    if _stuck(item):
        return InboxStatus.FAILED, "ai_failed"
    return item.status, item.error


def is_open():
    """A filter for items still on their way to a recipe: waiting for a parent, being read (not stuck), or a draft to
    check."""
    item = models.InboxItem
    return or_(
        item.status.in_((InboxStatus.WAITING, InboxStatus.DRAFT)),
        and_(
            item.status == InboxStatus.PROCESSING,
            or_(item.processing_since.is_(None), item.processing_since >= utcnow() - STUCK_AFTER),
        ),
    )


def visible(db: Session, item_id: int, user: models.User) -> models.InboxItem:
    """An item the person may see (User.may_see)."""
    item = db.get(models.InboxItem, item_id)
    if item is None or not user.may_see(item.user_id):
        raise NotFound("item_not_found")
    return item
