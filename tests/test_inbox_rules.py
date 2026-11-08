"""An inbox item's life in one place (app/inbox.py), who may see what (User), and the inbox's helpers that left the
router: building a scan's or a pasted text's mail, and thumbnails."""

import io
from datetime import timedelta

import pytest
from PIL import Image

from app import inbox, inbox_files, mail, models, photos
from app.errors import NotFound
from app.models import InboxKind, InboxStatus
from app.timeutil import utcnow
from mails import png


def _people(db):
    parent = db.query(models.User).filter_by(name="Admin").one()
    child = models.User(name="Lena", name_key="lena", role=models.UserRole.CHILD)
    db.add(child)
    db.commit()
    return parent, child


def test_parent_and_child(db):
    parent, child = _people(db)
    assert parent.is_parent and not child.is_parent
    assert parent.may_see(child.id) and parent.may_see(None)
    assert child.may_see(child.id) and not child.may_see(parent.id) and not child.may_see(None)


def test_statuses_are_the_stored_words(db):
    assert [s.value for s in InboxStatus] == ["waiting", "processing", "draft", "failed", "done"]
    assert [k.value for k in InboxKind] == ["mail", "url", "scan", "text"]
    assert InboxStatus.DRAFT == "draft"


def test_a_parents_item_is_released_at_once_a_childs_waits(db):
    parent, child = _people(db)
    mine = models.InboxItem(kind=InboxKind.TEXT, subject="x")
    assert inbox.add(db, parent, mine, b"raw mail") is True
    assert mine.status == InboxStatus.PROCESSING and mine.processing_since is not None and mine.user_id == parent.id
    assert inbox_files.raw_path(mine).read_bytes() == b"raw mail"
    theirs = models.InboxItem(kind=InboxKind.URL, subject="y", url="https://example.ch/")
    assert inbox.add(db, child, theirs) is False
    assert theirs.status == InboxStatus.WAITING and theirs.processing_since is None


def test_release_only_what_isnt_busy_or_done(db):
    parent, _ = _people(db)
    item = models.InboxItem(kind=InboxKind.URL, subject="y", url="https://example.ch/", user_id=parent.id)
    db.add(item)
    db.commit()
    for busy in (InboxStatus.PROCESSING, InboxStatus.DONE):
        item.status = busy
        with pytest.raises(inbox.ItemBusy):
            inbox.release(db, item)
    item.status, item.error = InboxStatus.FAILED, "ai_failed"
    inbox.release(db, item)
    assert item.status == InboxStatus.PROCESSING and item.error is None and item.processing_since is not None


def test_processing_ends_in_a_draft_or_failed(db):
    parent, _ = _people(db)
    item = models.InboxItem(kind=InboxKind.URL, subject="y", url="https://example.ch/", user_id=parent.id)
    inbox.add(db, parent, item)
    inbox.fail(db, item, "nothing_found")
    assert (item.status, item.error, item.processing_since) == (InboxStatus.FAILED, "nothing_found", None)
    inbox.release(db, item)
    inbox.finish(db, item, {"title": "Risotto"}, "raw answer")
    assert (item.status, item.error, item.draft, item.ai_raw) == (InboxStatus.DRAFT, None, {"title": "Risotto"}, "raw answer")


def test_only_a_draft_becomes_a_recipe(db):
    parent, _ = _people(db)
    item = models.InboxItem(kind=InboxKind.URL, subject="y", url="https://example.ch/", user_id=parent.id)
    inbox.add(db, parent, item)
    with pytest.raises(inbox.DraftNotReady):
        inbox.check_draft(item)
    inbox.finish(db, item, {"title": "Risotto"})
    inbox.check_draft(item)
    inbox.saved_as(item, 42)
    assert (item.status, item.recipe_id) == (InboxStatus.DONE, 42)


def test_visible_to_its_sender_and_the_parents(db):
    parent, child = _people(db)
    item = models.InboxItem(kind=InboxKind.URL, subject="y", url="https://example.ch/")
    inbox.add(db, parent, item)
    assert inbox.visible(db, item.id, parent) is item
    with pytest.raises(NotFound):
        inbox.visible(db, item.id, child)
    with pytest.raises(NotFound):
        inbox.visible(db, 999, parent)


def test_built_mail_reads_like_a_mail():
    raw = mail.build("Scan 07.11.2026 10:00", "scan.invalid", attachments=[(png(), "image/png", "scan-1.png")])
    summary = mail.summarize(raw)
    assert summary.subject == "Scan 07.11.2026 10:00" and summary.message_id.endswith("@scan.invalid>")
    assert [a["type"] for a in summary.attachments] == ["image/png"]
    text = mail.build("Risotto", "text.invalid", text="Risotto\n300 g Reis")
    assert "300 g Reis" in mail.content(text).text and mail.summarize(text).attachments == []


def test_thumbnail_is_a_small_jpeg():
    thumb = photos.downscale(png(size=(1200, 800)), 320, quality=80)
    with Image.open(io.BytesIO(thumb)) as image:
        assert image.format == "JPEG" and max(image.size) == 320
    with pytest.raises(photos.PhotoUnreadable):
        photos.downscale(b"not a picture", 320)


def _stuck(db, parent):
    item = models.InboxItem(kind=InboxKind.URL, subject="old", url="https://example.ch/", user_id=parent.id)
    inbox.add(db, parent, item)
    item.processing_since = utcnow() - inbox.STUCK_AFTER - timedelta(minutes=1)
    db.commit()
    return item


def test_stuck_shows_as_failed_without_writing(db):
    """Stuck is worked out when read: looking at the inbox writes nothing."""
    parent, _ = _people(db)
    old = _stuck(db, parent)
    new = models.InboxItem(kind=InboxKind.URL, subject="new", url="https://example.ch/", user_id=parent.id)
    inbox.add(db, parent, new)
    assert inbox.shown(old) == (InboxStatus.FAILED, "ai_failed")
    assert inbox.shown(new) == (InboxStatus.PROCESSING, None)
    assert old.status == InboxStatus.PROCESSING and not db.dirty


def test_a_stuck_item_can_be_released_again(db):
    parent, _ = _people(db)
    item = _stuck(db, parent)
    inbox.release(db, item)
    assert item.status == InboxStatus.PROCESSING and item.processing_since > utcnow() - timedelta(minutes=1)


def test_a_stuck_item_no_longer_counts_as_open(db):
    parent, _ = _people(db)
    stuck = _stuck(db, parent)
    waiting = models.InboxItem(kind=InboxKind.URL, subject="w", url="https://example.ch/", user_id=None)
    db.add(waiting)
    db.commit()
    assert {i.id for i in db.query(models.InboxItem).filter(inbox.is_open())} == {waiting.id}
    assert stuck.id not in {i.id for i in db.query(models.InboxItem).filter(inbox.is_open())}


def test_reading_the_inbox_writes_nothing(client, admin_headers, db):
    parent = db.query(models.User).filter_by(name="Admin").one()
    item = _stuck(db, parent)
    shown = client.get("/api/inbox", headers=admin_headers).json()
    assert [(i["status"], i["error"]) for i in shown] == [("failed", "ai_failed")]
    assert client.get("/api/inbox/count", headers=admin_headers).json() == {"waiting": 1}
    assert client.get(f"/api/inbox/{item.id}", headers=admin_headers).json()["status"] == "failed"
    db.expire_all()
    assert db.get(models.InboxItem, item.id).status == InboxStatus.PROCESSING


def test_an_inbox_id_is_never_used_twice(db):
    """The files of an item (its mail, cached thumbnails) are named by its id: a new item must never get the id of one
    discarded before, or it could show that item's files."""
    parent, _ = _people(db)
    first = models.InboxItem(kind=InboxKind.URL, subject="a", url="https://example.ch/")
    inbox.add(db, parent, first)
    gone = first.id
    db.delete(first)
    db.commit()
    second = models.InboxItem(kind=InboxKind.URL, subject="b", url="https://example.ch/")
    inbox.add(db, parent, second)
    assert second.id > gone
