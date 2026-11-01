"""Swissmilk (swissmilk.ch): the only code that talks to it. Fixed addresses, structured data only, never the AI
(spec 2026-11-01-swissmilk-search-design)."""

import hashlib
import re
import threading
import time
from collections import OrderedDict
from urllib.parse import quote_plus, urljoin, urlsplit

from . import fetch, microdata, photos

PAGE_HOST = "www.swissmilk.ch"
PHOTO_HOST = "api.swissmilk.ch"
SEARCH = "https://www.swissmilk.ch/de/suche/?q="
IMAGE_TYPES = ("image/",)
MAX_CANDIDATES = 12
# Search results show small photos: kept small in the cache too
THUMB_SIDE = 320
_RECIPE_PATH = re.compile(r"^/de/rezepte-kochideen/rezepte/[A-Za-z0-9_]+/[a-z0-9-]+/$")
# The recipe number in any language's address: /rezepte/<ID>/, /recettes/<ID>/, /ricette/<ID>/
_RECIPE_ID = re.compile(r"/(?:rezepte|recettes|ricette)/([A-Za-z0-9_]+)/[^/]+/?$")
_LINK = re.compile(r"""href=["']([^"'#]+)["']""")

PHOTO_PREFIX = f"https://{PHOTO_HOST}/wp-content/uploads/"
MAX_INGREDIENTS = 60
MAX_NAME = 200


def _real_ingredient(attrs: dict[str, str]) -> bool:
    """Swissmilk marks ingredient rows with the class "Ingredient"; equipment ("ofenfeste Form ca. 2 l") has none."""
    return "Ingredient" in attrs.get("class", "").split()


def _split_list(ingredient: dict) -> list[dict]:
    """ "Salz, Pfeffer, Muskatnuss" (no amount, every part a noun) is three ingredients, not one with a note."""
    if ingredient["amount"] is not None or not ingredient["note"]:
        return [ingredient]
    parts = [ingredient["name"], *(p.strip() for p in ingredient["note"].split(","))]
    if not all(p and p[0].isupper() for p in parts):
        return [ingredient]
    return [{"amount": None, "unit": None, "name": p, "note": ""} for p in parts]


def read_recipe(page: str, page_url: str) -> dict | None:
    """A recipe draft from a Swissmilk recipe page, or None if it has none."""
    node = microdata.recipe_node(page, keep_ingredient=_real_ingredient)
    if not node:
        return None
    images = node.get("image") or []
    node["recipeIngredient"] = [line.replace("*", "") for line in node.get("recipeIngredient", [])]
    node["image"] = next((i for i in images if i.startswith(PHOTO_PREFIX)), None)
    draft = microdata.draft_from_node(node, page_url)
    if not draft:
        return None
    ingredients = [split for i in draft["ingredients"] for split in _split_list(i)]
    draft["ingredients"] = [{**i, "name": i["name"][:MAX_NAME]} for i in ingredients if i["name"]][:MAX_INGREDIENTS]
    draft["title"] = re.sub(r"\s+", " ", draft["title"])[:MAX_NAME]
    return draft


# Pages and photos for a day: a family's searches repeat, and Swissmilk shouldn't see every one
CACHE_SECONDS = 24 * 3600
CACHE_ENTRIES = 500
_cache: OrderedDict[str, tuple[float, object]] = OrderedDict()
_lock = threading.Lock()


def clear_cache() -> None:
    with _lock:
        _cache.clear()
        _keys.clear()
        _inflight.clear()


# Pages being fetched right now: a second search asking for the same page waits for it instead of fetching again
_inflight: dict[str, threading.Event] = {}


def _fresh(key: str):
    hit = _cache.get(key)
    return hit if hit and time.monotonic() - hit[0] < CACHE_SECONDS else None


def _cached(key: str, make, deadline: float | None = None, keep=lambda value: True):
    """The cached value, else `make()`. Only one fetch per key at a time: others wait for it (until their deadline),
    and if it fails, one of them tries again. `keep` decides whether a value is worth keeping."""
    while True:
        with _lock:
            hit = _fresh(key)
            if hit:
                return hit[1]
            waiting = _inflight.get(key)
            if waiting is None:
                _inflight[key] = done = threading.Event()
        if waiting is None:
            break
        left = None if deadline is None else deadline - time.monotonic()
        if (left is not None and left <= 0) or not waiting.wait(timeout=left):
            raise fetch.FetchFailed("deadline")
        # Done: its value is in the cache now, or it failed and the loop makes one of us the next to try
    try:
        value = make()
        if keep(value):
            with _lock:
                _cache[key] = (time.monotonic(), value)
                _cache.move_to_end(key)
                while len(_cache) > CACHE_ENTRIES:
                    _cache.popitem(last=False)
        return value
    finally:
        with _lock:
            # Only our own: after clear_cache() a newer fetch of this key may be under way
            if _inflight.get(key) is done:
                del _inflight[key]
        done.set()


def _get(url: str, accept: tuple[str, ...] = fetch.PAGE_TYPES, deadline: float | None = None) -> fetch.Page:
    """The one network call: HTTPS to Swissmilk's page host, or its photo host, and nowhere else (also not by
    redirect); ended by `deadline` if given."""
    host = PHOTO_HOST if url.startswith(PHOTO_PREFIX) else PAGE_HOST
    return fetch.fetch(url, accept=accept, allowed_hosts=frozenset({host}), deadline=deadline)


def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def is_swissmilk(url: str) -> bool:
    """Anything on swissmilk.ch, however spelled ("swissmilk.ch", "www.swissmilk.ch.", "api.swissmilk.ch"): such a
    page is read without AI or not at all."""
    host = _host(url)
    return host == "swissmilk.ch" or host.endswith(".swissmilk.ch")


def page_url(url: str) -> str | None:
    """The address on Swissmilk's page host for a link to its pages (https, www, no trailing dot), else None."""
    if _host(url) not in ("swissmilk.ch", PAGE_HOST):
        return None
    parts = urlsplit(url)
    return f"https://{PAGE_HOST}{parts.path or '/'}" + (f"?{parts.query}" if parts.query else "")


def is_recipe_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    # The plain host only: no login details ("x@") and no port in a link handed on to the family
    return parts.scheme == "https" and parts.netloc == PAGE_HOST and not parts.query and bool(
        _RECIPE_PATH.match(parts.path)
    )


def recipe_id(url: str) -> str | None:
    if not is_swissmilk(url):
        return None
    match = _RECIPE_ID.search(urlsplit(url).path)
    return match.group(1) if match else None


def search_url(words: list[str]) -> str:
    return SEARCH + quote_plus(" ".join(words))


def candidates(page: str) -> list[str]:
    """The search page's recipe links, in its order: the first few, each once, only Swissmilk's own."""
    found: list[str] = []
    for href in _LINK.findall(page):
        url = urljoin(f"https://{PAGE_HOST}/", href)
        if is_recipe_url(url) and url not in found:
            found.append(url)
            if len(found) == MAX_CANDIDATES:
                break
    return found


def search(words: list[str], deadline: float | None = None) -> list[str]:
    """Swissmilk's recipe links for these words; the same search within a day asks Swissmilk once."""
    url = search_url(words)
    # Nothing found is not kept: it may be a maintenance page rather than an answer
    return _cached(f"search:{url}", lambda: candidates(_get(url, deadline=deadline).text), deadline, keep=bool)


def recipe(url: str, deadline: float | None = None) -> dict | None:
    if not is_recipe_url(url):
        raise fetch.FetchRefused(url)
    return _cached(f"recipe:{url}", lambda: read_recipe(_get(url, deadline=deadline).text, url), deadline)


def _check_photo(url: str) -> None:
    if not url.startswith(PHOTO_PREFIX) or urlsplit(url).hostname != PHOTO_HOST:
        raise fetch.FetchRefused(url)


def photo(url: str, deadline: float | None = None) -> bytes:
    """A search result's photo, small."""
    _check_photo(url)
    return _cached(
        f"photo:{url}",
        lambda: photos.downscale(_get(url, accept=IMAGE_TYPES, deadline=deadline).body, THUMB_SIDE),
        deadline,
    )


def original_photo(url: str) -> bytes:
    """The photo as Swissmilk has it, for a recipe taken over (stored at full size by photos.store_photo)."""
    _check_photo(url)
    return _get(url, accept=IMAGE_TYPES).body


# Photo keys handed out by searches: apart from the page cache, so many recipe pages never push out the keys of
# results still on screen (only addresses, so many fit)
PHOTO_KEYS = 5000
_keys: OrderedDict[str, tuple[float, str]] = OrderedDict()


def remember_photo(url: str) -> str:
    """A short key for a photo a search handed out; the photo endpoint serves only those."""
    key = hashlib.sha256(url.encode()).hexdigest()[:16]
    with _lock:
        _keys[key] = (time.monotonic(), url)
        _keys.move_to_end(key)
        while len(_keys) > PHOTO_KEYS:
            _keys.popitem(last=False)
    return key


def photo_for(key: str) -> str | None:
    with _lock:
        hit = _keys.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1]
    return None
