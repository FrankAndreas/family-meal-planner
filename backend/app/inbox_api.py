"""The recipe inbox: mails from the Cloudflare Email Worker and pasted links, waiting for a parent."""

import hmac
import io
import logging
from urllib.parse import urlsplit

from datetime import timedelta

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from . import auth, config, importer, mail, models, photos, schemas  # noqa: F401  (photos: HEIC opener)
from .database import get_db
from .errors import api_error
from .timeutil import utcnow

router = APIRouter(tags=["inbox"])
logger = logging.getLogger(__name__)

MAX_BYTES = 25 * 1024 * 1024
THUMB_SIDE = 320
# Processing that never finished (e.g. the backend restarted meanwhile) counts as failed after this
STUCK_AFTER = timedelta(minutes=10)


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


def _unstick(db: Session) -> None:
    stuck = db.query(models.InboxItem).filter(
        models.InboxItem.status == "processing", models.InboxItem.processing_since < utcnow() - STUCK_AFTER
    )
    for item in stuck:
        item.status, item.error, item.processing_since = "failed", "ai_failed", None
    db.commit()


def visible_item(db: Session, item_id: int, user: models.User) -> models.InboxItem:
    """An item the person may see: parents all, children their own."""
    _unstick(db)
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
    _unstick(db)
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
    for thumb in (inbox_dir() / "thumbs").glob(f"{item_id}-*.jpg"):
        thumb.unlink(missing_ok=True)


@router.post("/inbox/urls", response_model=schemas.InboxItemOut, status_code=201)
def add_url(body: schemas.UrlIn, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """A link found while browsing. A parent's paste is the release: it is processed right away."""
    parent = user.role == models.UserRole.PARENT
    item = models.InboxItem(
        kind="url",
        status="processing" if parent else "waiting",
        user_id=user.id,
        subject=urlsplit(body.url).hostname or body.url,
        url=body.url,
    )
    if parent:
        item.processing_since = utcnow()
    db.add(item)
    db.commit()
    if parent:
        importer.start(item.id, user.id)
    return item_out(item)


@router.get("/inbox/{item_id}", response_model=schemas.InboxItemDetail)
def read_item(item_id: int, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    item = visible_item(db, item_id, user)
    return schemas.InboxItemDetail(**item_out(item).model_dump(), draft=item.draft, ai_raw=item.ai_raw)


@router.post("/inbox/{item_id}/process", response_model=schemas.InboxItemOut, status_code=202)
def process_item(item_id: int, parent: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)):
    """The release: only now is the mail read, are links fetched and may the AI see it."""
    item = visible_item(db, item_id, parent)
    if item.status in ("processing", "done"):
        raise api_error(409, "item_busy")
    item.status, item.error, item.processing_since = "processing", None, utcnow()
    db.commit()
    importer.start(item.id, parent.id)
    db.refresh(item)
    return item_out(item)


def _image_attachment(item: models.InboxItem, index: int) -> tuple[str, bytes]:
    found = mail.attachment(raw_path(item).read_bytes(), index) if item.kind == "mail" else None
    if found is None or not found[0].startswith("image/"):
        raise api_error(404, "attachment_not_found")
    return found


@router.get("/inbox/{item_id}/attachments/{index}")
def read_attachment(
    item_id: int, index: int, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)
):
    """One image of a mail, decoded because a person opened it (no AI, nothing leaves the NAS)."""
    kind, data = _image_attachment(visible_item(db, item_id, user), index)
    return Response(data, media_type=kind)


@router.get("/inbox/{item_id}/attachments/{index}/thumb")
def read_thumbnail(
    item_id: int, index: int, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)
):
    item = visible_item(db, item_id, user)
    cached = inbox_dir() / "thumbs" / f"{item.id}-{index}.jpg"
    if not cached.is_file():
        _, data = _image_attachment(item, index)
        try:
            with Image.open(io.BytesIO(data)) as source:
                image = ImageOps.exif_transpose(source).convert("RGB")
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            raise api_error(404, "attachment_not_found")
        image.thumbnail((THUMB_SIDE, THUMB_SIDE))
        cached.parent.mkdir(parents=True, exist_ok=True)
        image.save(cached, "JPEG", quality=80)
    return FileResponse(cached, media_type="image/jpeg")


@router.get("/inbox/{item_id}/raw")
def read_raw(item_id: int, parent: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)):
    """The mail as it arrived (part of the original of an imported recipe)."""
    item = visible_item(db, item_id, parent)
    if item.kind != "mail":
        raise api_error(404, "attachment_not_found")
    return FileResponse(raw_path(item), media_type="message/rfc822", filename=f"rezept-{item.id}.eml")


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
