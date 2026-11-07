"""The recipe inbox: mails from the Cloudflare Email Worker, pasted links and texts, and scans, waiting for a parent.
An item's life (statuses and the moves between them) is in inbox.py."""

import hmac
import logging
from datetime import datetime
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from . import ai, auth, config, importer, inbox, mail, models, photos, schemas, swissmilk
from .database import get_db
from .http_errors import api_error
from .inbox_files import inbox_dir, raw_path
from .models import InboxKind, InboxStatus

router = APIRouter(tags=["inbox"])
logger = logging.getLogger(__name__)

MAX_BYTES = 25 * 1024 * 1024
THUMB_SIDE = 320
# Pictures only, never SVG: an SVG opened in a tab of its own could run script with the app's login
RASTER_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/heic", "image/heif"}


def item_out(item: models.InboxItem) -> schemas.InboxItemOut:
    status, error = inbox.shown(item)
    return schemas.InboxItemOut(
        id=item.id,
        kind=item.kind,
        status=status,
        user_name=item.user.name if item.user else None,
        from_addr=item.from_addr,
        subject=item.subject,
        url=item.url,
        received_at=item.received_at,
        attachments=item.attachments,
        error=error,
        recipe_id=item.recipe_id,
    )


def _add(db: Session, user: models.User, item: models.InboxItem, raw: bytes | None = None) -> schemas.InboxItemOut:
    """A new item from someone in the family; a parent's is read right away."""
    if inbox.add(db, user, item, raw):
        importer.start(item.id, user.id)
    return item_out(item)


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
        db.query(models.UserEmail)
        .join(models.User)
        # A person the family hub no longer lists sends nothing in (their address stays until their data is deleted)
        .filter(models.UserEmail.address == summary.from_addr, models.User.is_active.is_(True))
        .first()
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
        kind=InboxKind.MAIL,
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


def _unfinished(db: Session, user: models.User) -> list[models.InboxItem]:
    """Not yet a recipe: all for a parent, a child's own for a child; newest first."""
    query = db.query(models.InboxItem).filter(models.InboxItem.status != InboxStatus.DONE)
    if not user.is_parent:
        query = query.filter(models.InboxItem.user_id == user.id)
    return query.order_by(models.InboxItem.received_at.desc(), models.InboxItem.id.desc()).all()


@router.get("/inbox", response_model=list[schemas.InboxItemOut])
def list_items(user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    return [item_out(i) for i in _unfinished(db, user)]


@router.get("/inbox/count")
def count_items(user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    return {"waiting": len(_unfinished(db, user))}


@router.delete("/inbox/{item_id}", status_code=204)
def discard_item(item_id: int, parent: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)):
    item = inbox.visible(db, item_id, parent)
    path = raw_path(item)
    db.delete(item)
    db.commit()
    path.unlink(missing_ok=True)
    for thumb in (inbox_dir() / "thumbs").glob(f"{item_id}-*.jpg"):
        thumb.unlink(missing_ok=True)


@router.post("/inbox/urls", response_model=schemas.InboxItemOut, status_code=201)
def add_url(body: schemas.UrlIn, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """A link found while browsing. A parent's paste is the release: it is processed right away."""
    # A Swissmilk recipe already on its way in (a double tap on "Übernehmen", another language's page): that one
    number = swissmilk.recipe_id(body.url)
    if number:
        for open_item in db.query(models.InboxItem).filter(
            models.InboxItem.kind == InboxKind.URL, inbox.is_open()
        ):
            if swissmilk.recipe_id(open_item.url or "") == number:
                return item_out(open_item)
    return _add(db, user, models.InboxItem(kind=InboxKind.URL, subject=urlsplit(body.url).hostname or body.url, url=body.url))


@router.post("/inbox/scans", response_model=schemas.InboxItemOut, status_code=201)
async def add_scan(
    files: list[UploadFile], user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)
):
    """Photos of one recipe taken in the app (the back of a pack, a cookbook page). Kept as a mail with the photos
    attached, so it is processed and shown like one. A parent's scan is the release: it is read right away."""
    if len(files) > ai.MAX_IMAGES:
        raise api_error(400, "scan_too_many")
    pictures = []
    total = 0
    for number, file in enumerate(files, 1):
        kind = (file.content_type or "").lower()
        if kind not in RASTER_TYPES:
            raise api_error(400, "scan_not_image")
        data = await file.read(MAX_BYTES + 1)
        total += len(data)
        if total > MAX_BYTES:
            raise api_error(413, "scan_too_big")
        pictures.append((data, kind, f"scan-{number}.{kind.split('/')[1]}"))
    raw = mail.build(datetime.now().strftime("Scan %d.%m.%Y %H:%M"), "scan.invalid", attachments=pictures)
    summary = mail.summarize(raw)
    item = models.InboxItem(
        kind=InboxKind.SCAN,
        subject=summary.subject,
        message_id=summary.message_id,
        attachments=summary.attachments,
        size=len(raw),
    )
    return _add(db, user, item, raw)


def _title(text: str) -> str:
    """The pasted text's first line, cut to fit."""
    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return mail.clean(first, 120) or "Text"


@router.post("/inbox/texts", response_model=schemas.InboxItemOut, status_code=201)
def add_text(body: schemas.TextIn, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """A recipe's text pasted in (a Facebook post's caption), with the link it came from. Kept as a mail with only
    that text, so it is processed and shown like one; the link is never fetched (Facebook shows nothing without a
    login), only kept as the source. A parent's paste is the release: it is read right away."""
    raw = mail.build(_title(body.text), "text.invalid", text=body.text)
    item = models.InboxItem(
        kind=InboxKind.TEXT,
        subject=_title(body.text),
        url=body.url,
        message_id=mail.summarize(raw).message_id,
        attachments=[],
        size=len(raw),
    )
    return _add(db, user, item, raw)


@router.get("/inbox/{item_id}", response_model=schemas.InboxItemDetail)
def read_item(item_id: int, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    item = inbox.visible(db, item_id, user)
    text = None
    if item.kind == InboxKind.TEXT:
        # Its file gone (a database restored without the inbox folder): the item and its draft still open
        try:
            text = mail.content(raw_path(item).read_bytes()).text
        except OSError:
            pass
    return schemas.InboxItemDetail(**item_out(item).model_dump(), draft=item.draft, ai_raw=item.ai_raw, text=text)


@router.post("/inbox/{item_id}/process", response_model=schemas.InboxItemOut, status_code=202)
def process_item(item_id: int, parent: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)):
    """The release: only now is the mail read, are links fetched and may the AI see it."""
    item = inbox.visible(db, item_id, parent)
    inbox.release(db, item)
    importer.start(item.id, parent.id)
    db.refresh(item)
    return item_out(item)


def _image_attachment(item: models.InboxItem, index: int) -> tuple[str, bytes]:
    found = mail.attachment(raw_path(item).read_bytes(), index) if item.kind in (InboxKind.MAIL, InboxKind.SCAN) else None
    if found is None or found[0] not in RASTER_TYPES:
        raise api_error(404, "attachment_not_found")
    return found


@router.get("/inbox/{item_id}/attachments/{index}")
def read_attachment(
    item_id: int, index: int, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)
):
    """One image of a mail, decoded because a person opened it (no AI, nothing leaves the NAS)."""
    kind, data = _image_attachment(inbox.visible(db, item_id, user), index)
    return Response(data, media_type=kind)


@router.get("/inbox/{item_id}/attachments/{index}/thumb")
def read_thumbnail(
    item_id: int, index: int, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)
):
    item = inbox.visible(db, item_id, user)
    cached = inbox_dir() / "thumbs" / f"{item.id}-{index}.jpg"
    if not cached.is_file():
        _, data = _image_attachment(item, index)
        try:
            thumb = photos.downscale(data, THUMB_SIDE, quality=80)
        except photos.PhotoUnreadable:
            raise api_error(404, "attachment_not_found")
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(thumb)
    return FileResponse(cached, media_type="image/jpeg")


@router.get("/inbox/{item_id}/raw")
def read_raw(item_id: int, parent: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)):
    """The mail as it arrived (part of the original of an imported recipe)."""
    item = inbox.visible(db, item_id, parent)
    if item.kind != InboxKind.MAIL:
        raise api_error(404, "attachment_not_found")
    return FileResponse(raw_path(item), media_type="message/rfc822", filename=f"rezept-{item.id}.eml")
