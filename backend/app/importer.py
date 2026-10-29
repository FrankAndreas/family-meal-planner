"""Turning an inbox item into a recipe draft, after a parent released it. In order, stopping at the first that works:
1. links (the pasted URL, or links in the mail) → the page's schema.org Recipe, no AI;
2. a fetched page without one → the AI reads the page's text;
3. the mail itself → the AI reads its text and all its pictures in one go.
Runs in a thread of its own, so the request returns at once and the inbox page polls."""

import logging
import threading
from urllib.parse import urlsplit

from fastapi import HTTPException

from . import ai, database, fetch, jsonld, mail, models, photos

logger = logging.getLogger(__name__)

MAX_LINKS = 3
# Pages that show nothing without a login: following them only costs time
LOGIN_WALLS = ("facebook.com", "fb.com", "fb.watch", "instagram.com", "tiktok.com")
IMAGE_TYPES = ("image/",)


def start(item_id: int, user_id: int) -> None:
    threading.Thread(target=run, args=(item_id, user_id), daemon=True).start()


def run(item_id: int, user_id: int) -> None:
    with database.SessionLocal() as db:
        item = db.get(models.InboxItem, item_id)
        user = db.get(models.User, user_id)
        if item is None or user is None:
            return
        try:
            process(db, item, user)
        except HTTPException as error:
            # ai_off or ai_limit from take_call
            detail = error.detail
            _fail(db, item, detail["code"] if isinstance(detail, dict) else str(detail))
        except ai.AiFailed:
            _fail(db, item, "ai_failed")
        except Exception:
            logger.exception("Processing inbox item %s failed", item_id)
            _fail(db, item, "ai_failed")


def _fail(db, item: models.InboxItem, code: str) -> None:
    item.status, item.error, item.processing_since = "failed", code, None
    db.commit()


def _finish(db, item: models.InboxItem, draft: dict, raw: str | None = None) -> None:
    item.status, item.error, item.draft, item.ai_raw, item.processing_since = "draft", None, draft, raw, None
    db.commit()


def _photo(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return photos.store_photo(fetch.fetch(url, accept=IMAGE_TYPES).body)
    except (fetch.FetchFailed, fetch.FetchRefused, HTTPException):
        return None


def _followable(link: str) -> bool:
    try:
        host = (urlsplit(link).hostname or "").lower()
    except ValueError:
        return False
    return not any(host == wall or host.endswith("." + wall) for wall in LOGIN_WALLS)


def _ask_ai(db, item, user, text: str, images: list[bytes]) -> tuple[dict, str, list[int]]:
    call = ai.take_call(db, user, "import", item_id=item.id)
    draft, raw, tokens, sent = ai.recipe_from_ai(ai.client_for(ai.Settings.from_env()), text=text, images=images)
    call.tokens = tokens
    db.commit()
    return draft, raw, sent


def process(db, item: models.InboxItem, user: models.User) -> None:
    content = None
    if item.kind == "url":
        links = [item.url]
    else:
        from .inbox_api import raw_path

        content = mail.content(raw_path(item).read_bytes())
        links = [link for link in content.links if _followable(link)][:MAX_LINKS]

    page_without_recipe = None
    for link in links:
        try:
            page = fetch.fetch(link)
        except (fetch.FetchFailed, fetch.FetchRefused):
            continue
        draft = jsonld.recipe_from_html(page.text, page.url)
        if draft:
            draft["photo"] = _photo(draft.pop("image_url", None))
            _finish(db, item, draft)
            return
        page_without_recipe = page_without_recipe or page

    # A page without recipe data: the AI reads it, unless the mail brings pictures (screenshots are the recipe;
    # a link in a mail footer isn't). If the AI finds nothing on the page, the mail itself is still tried.
    mail_has_pictures = content is not None and bool(content.images)
    if page_without_recipe is not None and not mail_has_pictures:
        text, _ = mail.html_text(page_without_recipe.text)
        try:
            draft, raw, _ = _ask_ai(db, item, user, text, [])
        except ai.AiFailed:
            if content is None or not content.text.strip():
                raise
        else:
            draft.pop("image_index", None)
            draft["source_url"] = page_without_recipe.url
            _finish(db, item, draft, raw)
            return

    if content is not None and (content.text.strip() or content.images):
        text = f"Betreff: {item.subject}\n\n{content.text}"
        draft, raw, sent = _ask_ai(db, item, user, text, [data for _, data in content.images])
        index = draft.pop("image_index", None)
        # The picture the AI named (counted among those it got), else the first it got: as an attachment index,
        # decoded again when saving
        if sent:
            chosen = sent[index] if isinstance(index, int) and 0 <= index < len(sent) else sent[0]
            draft["image_attachment"] = content.images[chosen][0]
        draft["source_url"] = links[0] if links else None
        _finish(db, item, draft, raw)
        return

    _fail(db, item, "nothing_found")
