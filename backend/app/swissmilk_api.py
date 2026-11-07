"""Swissmilk recipes for what's at home: searched on request from "Was habe ich?", checked with the same matcher as
the family's own recipes, photos passed through (spec 2026-11-01-swissmilk-search-design). Never the AI."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from . import auth, fetch, models, schemas, swissmilk
from .database import get_db
from .errors import api_error
from .settings_store import get_settings
from .pantry import MAX_MISSING, check, fit, typed_words

router = APIRouter(tags=["swissmilk"])

# The whole search, all recipe pages included; what isn't there by then is left out
BUDGET_SECONDS = 15
# A photo through the backend, at most
PHOTO_SECONDS = 10
# Recipe pages fetched at once
PARALLEL = 4
# One Swissmilk search per person in this time
SEARCH_GAP_SECONDS = 5
# Inbox items that still count as "taken over": waiting for a parent, being read, or a draft to check
OPEN_STATUSES = ("waiting", "processing", "draft")

_last_search: dict[int, float] = {}
_limit_lock = threading.Lock()


def reset_limits() -> None:
    with _limit_lock:
        _last_search.clear()


def _take_turn(user_id: int) -> None:
    now = time.monotonic()
    with _limit_lock:
        if now - _last_search.get(user_id, -SEARCH_GAP_SECONDS) < SEARCH_GAP_SECONDS:
            raise api_error(429, "too_many_searches")
        _last_search[user_id] = now


def _read(url: str, deadline: float) -> dict | None:
    try:
        return swissmilk.recipe(url, deadline)
    except Exception:
        # A page that can't be loaded or read is left out, never an error for the whole search
        return None


def _already(db: Session) -> tuple[dict[str, int], set[str]]:
    """Swissmilk recipe numbers the family has as live recipes, and those waiting in the inbox."""
    recipes: dict[str, int] = {}
    for recipe_id, source in (
        db.query(models.Recipe.id, models.Recipe.source_url)
        .filter(models.Recipe.deleted_at.is_(None), models.Recipe.source_url.isnot(None))
        .all()
    ):
        number = swissmilk.recipe_id(source)
        if number:
            recipes.setdefault(number, recipe_id)
    waiting = {
        number
        for (url,) in db.query(models.InboxItem.url).filter(
            models.InboxItem.kind == "url", models.InboxItem.status.in_(OPEN_STATUSES)
        )
        if url and (number := swissmilk.recipe_id(url))
    }
    return recipes, waiting


@router.get("/use-up/swissmilk", response_model=list[schemas.SwissmilkResult])
def search(
    have: list[str] = Query([], max_length=20),
    mode: Literal["use_up", "cook_now"] = "use_up",
    me: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    typed = typed_words(have)
    if not typed:
        return []
    _take_turn(me.id)
    # One budget for everything: the search page, then the recipe pages; fetches end by it too
    deadline = time.monotonic() + BUDGET_SECONDS
    executor = ThreadPoolExecutor(max_workers=PARALLEL)
    try:
        listing = executor.submit(swissmilk.search, typed, deadline)
        try:
            urls = listing.result(timeout=max(0.0, deadline - time.monotonic()))
        except Exception:
            raise api_error(502, "swissmilk_unreachable")
        futures = {executor.submit(_read, url, deadline): url for url in urls}
        done, _ = wait(futures, timeout=max(0.0, deadline - time.monotonic()))
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    staples = get_settings(db).staples
    recipes, waiting = _already(db)
    hits = []
    for position, url in enumerate(urls):
        future = next((f for f in done if futures[f] == url), None)
        draft = future.result() if future else None
        if not draft:
            continue
        used, missing = check([(i["name"], i["note"]) for i in draft["ingredients"]], typed, staples)
        if not used or (mode == "cook_now" and len(missing) > MAX_MISSING):
            continue
        number = swissmilk.recipe_id(url)
        hits.append(
            (
                (*fit(mode, used, missing), position),
                {
                    "title": draft["title"],
                    "url": url,
                    "photo": f"/api/use-up/swissmilk/photo/{swissmilk.remember_photo(draft['image_url'])}"
                    if draft.get("image_url")
                    else None,
                    "used": used,
                    "missing": missing,
                    "recipe_id": recipes.get(number),
                    "waiting": number in waiting and number not in recipes,
                },
            )
        )
    return [result for _, result in sorted(hits, key=lambda hit: hit[0])]


@router.get("/use-up/swissmilk/photo/{key}")
def photo(key: str, _user: models.User = Depends(auth.get_current_user)):
    """Only photos a search handed out, so this is never a way to fetch anything else."""
    url = swissmilk.photo_for(key)
    if url is None:
        raise api_error(404, "not_found")
    try:
        data = swissmilk.photo(url, time.monotonic() + PHOTO_SECONDS)
    except Exception:
        raise api_error(404, "not_found")
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})
