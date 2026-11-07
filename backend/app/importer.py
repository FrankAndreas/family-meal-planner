"""Turning an inbox item into a recipe draft, after a parent released it. In order, stopping at the first that works:
1. links (the pasted URL, or links in the mail) → the page's schema.org Recipe, no AI;
2. a fetched page without one → the AI reads the page's text;
3. the mail itself → the AI reads its text and all its pictures in one go.
A pasted text goes straight to 3: its link is only the source, never fetched.
A draft in another language than the family's (DEFAULT_LANGUAGE) is then translated, the original kept with it
(spec 2026-11-04); Swissmilk never, it uses no AI.
Runs in a thread of its own, so the request returns at once and the inbox page polls."""

import logging
import threading
from urllib.parse import urlsplit

from . import ai, config, database, fetch, inbox, jsonld, mail, microdata, models, photos, swissmilk
from .errors import Refused
from .inbox_files import raw_path
from .models import InboxKind

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
        except Refused as error:
            # e.g. ai_off or ai_limit from take_call
            inbox.fail(db, item, error.code)
        except ai.AiFailed:
            inbox.fail(db, item, "ai_failed")
        except Exception:
            logger.exception("Processing inbox item %s failed", item_id)
            inbox.fail(db, item, "ai_failed")


# Said in the draft's "Bitte prüfen" when the translation didn't work: the Translate button can still do it later
NOT_TRANSLATED = {
    "de": "Konnte nicht übersetzt werden – das geht später mit «Auf Deutsch übersetzen» beim Rezept.",
    "en": "Could not be translated – use “Translate into English” on the recipe later.",
}
# ... unless the AI is switched off: then the button can't either
AI_OFF = {
    "de": "Nicht übersetzt: Die KI ist ausgeschaltet.",
    "en": "Not translated: the AI is switched off.",
}


def _translated(db, item: models.InboxItem, user: models.User, draft: dict) -> dict:
    """The draft in the family's language, its text before kept as "original"; as it was if its language is unknown,
    already the family's, or the AI can't (off, its hourly limit, a failed answer)."""
    target = config.default_language()
    if draft.get("language") not in ("de", "en") or draft["language"] == target:
        return draft
    text = {
        "title": draft.get("title") or "",
        "ingredients": [{"name": i.get("name") or "", "note": i.get("note") or ""} for i in draft.get("ingredients", [])],
        "steps": list(draft.get("steps") or []),
        "notes": draft.get("notes") or "",
        "tags": list(draft.get("tags") or []),
    }
    try:
        call = ai.take_call(db, user, "translate", item_id=item.id)
        done, tokens = ai.translate(ai.client_for(ai.Settings.from_env()), text, target)
    except (ai.AiOff, ai.AiLimit, ai.AiFailed) as error:
        off = isinstance(error, ai.AiOff)
        return {**draft, "uncertain": [*draft.get("uncertain", []), (AI_OFF if off else NOT_TRANSLATED)[target]]}
    call.tokens = tokens
    db.commit()
    ingredients = [{**old, **new} for old, new in zip(draft.get("ingredients", []), done["ingredients"])]
    original = {**text, "language": draft["language"]}
    return {**draft, **done, "ingredients": ingredients, "language": target, "original": original}


def _photo(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return photos.store_photo(fetch.fetch(url, accept=IMAGE_TYPES).body)
    except (fetch.FetchFailed, fetch.FetchRefused, photos.PhotoUnreadable):
        return None


def _swissmilk_draft(page: fetch.Page) -> dict | None:
    """A Swissmilk page read without any AI: its recipe microdata, its photo from Swissmilk's photo host."""
    draft = swissmilk.read_recipe(page.text, page.url)
    if not draft:
        return None
    image = draft.pop("image_url", None)
    try:
        draft["photo"] = photos.store_photo(swissmilk.original_photo(image)) if image else None
    except (fetch.FetchFailed, fetch.FetchRefused, photos.PhotoUnreadable):
        draft["photo"] = None
    return draft


def _from_swissmilk(link: str) -> dict | None:
    address = swissmilk.page_url(link)
    if address is None:
        return None
    try:
        return _swissmilk_draft(swissmilk._get(address))
    except (fetch.FetchFailed, fetch.FetchRefused):
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
    if item.kind == InboxKind.URL:
        links = [item.url]
    elif item.kind == InboxKind.TEXT:
        content = mail.content(raw_path(item).read_bytes())
        links = []
    else:
        content = mail.content(raw_path(item).read_bytes())
        links = [link for link in content.links if _followable(link)][:MAX_LINKS]

    page_without_recipe = None
    swissmilk_unreadable = False
    for link in links:
        if swissmilk.is_swissmilk(link):
            # Swissmilk: only its own hosts, only its structured data, never the AI (spec 2026-11-01)
            draft = _from_swissmilk(link)
            if draft:
                inbox.finish(db, item, draft)
                return
            swissmilk_unreadable = True
            continue
        try:
            page = fetch.fetch(link)
        except (fetch.FetchFailed, fetch.FetchRefused):
            continue
        if swissmilk.is_swissmilk(page.url):
            # Reached by a redirect (a newsletter's click tracker): still Swissmilk, still never the AI
            draft = _swissmilk_draft(page)
            if draft:
                inbox.finish(db, item, draft)
                return
            swissmilk_unreadable = True
            continue
        draft = jsonld.recipe_from_html(page.text, page.url) or microdata.recipe_from_html(page.text, page.url)
        if draft:
            draft["photo"] = _photo(draft.pop("image_url", None))
            inbox.finish(db, item, _translated(db, item, user, draft))
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
            inbox.finish(db, item, _translated(db, item, user, draft), raw)
            return

    if content is not None and (content.text.strip() or content.images):
        # A pasted text's subject is only its own first line
        text = content.text if item.kind == InboxKind.TEXT else f"Betreff: {item.subject}\n\n{content.text}"
        draft, raw, sent = _ask_ai(db, item, user, text, [data for _, data in content.images])
        index = draft.pop("image_index", None)
        # The picture the AI named (counted among those it got), else the first it got: as an attachment index,
        # decoded again when saving
        if sent:
            chosen = sent[index] if isinstance(index, int) and 0 <= index < len(sent) else sent[0]
            draft["image_attachment"] = content.images[chosen][0]
        draft["source_url"] = item.url if item.kind == InboxKind.TEXT else (links[0] if links else None)
        inbox.finish(db, item, _translated(db, item, user, draft), raw)
        return

    inbox.fail(db, item, "swissmilk_unreadable" if swissmilk_unreadable else "nothing_found")
