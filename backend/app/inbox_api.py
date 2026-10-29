"""The recipe inbox: mails from the Cloudflare Email Worker and pasted links, waiting for a parent."""

import hmac
import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from . import auth, config, mail, models, schemas
from .database import get_db
from .errors import api_error

router = APIRouter(tags=["inbox"])
logger = logging.getLogger(__name__)

MAX_BYTES = 25 * 1024 * 1024


def inbox_dir():
    folder = config.data_dir() / "inbox"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def raw_path(item: models.InboxItem):
    return inbox_dir() / f"{item.id}.eml"


def item_out(item: models.InboxItem) -> schemas.InboxItemOut:
    return schemas.InboxItemOut(
        id=item.id,
        kind=item.kind,
        status=item.status,
        user_name=item.user.name if item.user else None,
        from_addr=item.from_addr,
        subject=item.subject,
        url=item.url,
        received_at=item.received_at,
        attachments=item.attachments,
        error=item.error,
        recipe_id=item.recipe_id,
    )


def visible_item(db: Session, item_id: int, user: models.User) -> models.InboxItem:
    """An item the person may see: parents all, children their own."""
    item = db.get(models.InboxItem, item_id)
    if item is None or (user.role != models.UserRole.PARENT and item.user_id != user.id):
        raise api_error(404, "item_not_found")
    return item


@router.post("/inbound")
async def receive_mail(request: Request, db: Session = Depends(get_db)):
    """Called by the Cloudflare Email Worker with the raw mail; protected by a shared secret, not a login."""
    secret = config.env("INBOUND_SECRET")
    if not secret:
        raise api_error(503, "inbound_off")
    if not hmac.compare_digest(request.headers.get("x-inbound-secret", "").encode(), secret.encode()):
        logger.warning("/inbound: wrong or missing secret")
        raise api_error(401, "inbound_wrong_secret")
    length = request.headers.get("content-length", "")
    if length.isdigit() and int(length) > MAX_BYTES:
        raise api_error(413, "inbound_too_big")
    raw = await request.body()
    if len(raw) > MAX_BYTES:
        raise api_error(413, "inbound_too_big")
    summary = mail.summarize(raw)
    sender = (
        db.query(models.UserEmail).filter(models.UserEmail.address == summary.from_addr).first()
        if summary.from_addr
        else None
    )
    if sender is None:
        # Neither the sender nor the content goes into the log
        logger.warning("/inbound: mail from an unregistered address refused")
        raise api_error(403, "inbound_sender_unknown")
    if db.query(models.InboxItem).filter(models.InboxItem.message_id == summary.message_id).first():
        return {"status": "duplicate"}
    item = models.InboxItem(
        kind="mail",
        user_id=sender.user_id,
        from_addr=summary.from_addr,
        subject=summary.subject,
        message_id=summary.message_id,
        attachments=summary.attachments,
        size=len(raw),
    )
    db.add(item)
    db.flush()
    raw_path(item).write_bytes(raw)
    db.commit()
    logger.info("/inbound: mail stored in the inbox")
    return {"status": "stored", "id": item.id}


@router.get("/inbox", response_model=list[schemas.InboxItemOut])
def list_items(user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    query = db.query(models.InboxItem).filter(models.InboxItem.status != "done")
    if user.role != models.UserRole.PARENT:
        query = query.filter(models.InboxItem.user_id == user.id)
    return [item_out(i) for i in query.order_by(models.InboxItem.received_at.desc(), models.InboxItem.id.desc())]


@router.get("/inbox/count")
def count_items(user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    return {"waiting": len(list_items(user, db))}


@router.delete("/inbox/{item_id}", status_code=204)
def discard_item(item_id: int, parent: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)):
    item = visible_item(db, item_id, parent)
    path = raw_path(item)
    db.delete(item)
    db.commit()
    path.unlink(missing_ok=True)


def _email_out(entry: models.UserEmail) -> schemas.EmailOut:
    return schemas.EmailOut(id=entry.id, user_id=entry.user_id, user_name=entry.user.name, address=entry.address)


@router.get("/emails", response_model=list[schemas.EmailOut])
def list_emails(all: bool = False, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    query = db.query(models.UserEmail)
    if not (all and user.role == models.UserRole.PARENT):
        query = query.filter(models.UserEmail.user_id == user.id)
    return [_email_out(e) for e in query.order_by(models.UserEmail.address)]


@router.post("/emails", response_model=schemas.EmailOut, status_code=201)
def add_email(body: schemas.EmailIn, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    owner_id = body.user_id or user.id
    if owner_id != user.id and user.role != models.UserRole.PARENT:
        raise api_error(403, "parents_only")
    if db.get(models.User, owner_id) is None:
        raise api_error(404, "user_not_found")
    if db.query(models.UserEmail).filter(models.UserEmail.address == body.address).first():
        raise api_error(409, "email_taken")
    entry = models.UserEmail(user_id=owner_id, address=body.address)
    db.add(entry)
    db.commit()
    return _email_out(entry)


@router.delete("/emails/{email_id}", status_code=204)
def delete_email(email_id: int, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    entry = db.get(models.UserEmail, email_id)
    if entry is None or (entry.user_id != user.id and user.role != models.UserRole.PARENT):
        raise api_error(404, "email_not_found")
    db.delete(entry)
    db.commit()
