"""Swissmilk (swissmilk.ch): the only code that talks to it. Fixed addresses, structured data only, never the AI
(spec 2026-11-01-swissmilk-search-design)."""

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


def _cached(key: str, make):
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < CACHE_SECONDS:
            return hit[1]
    value = make()
    with _lock:
        _cache[key] = (now, value)
        _cache.move_to_end(key)
        while len(_cache) > CACHE_ENTRIES:
            _cache.popitem(last=False)
    return value


def _get(url: str, accept: tuple[str, ...] = fetch.PAGE_TYPES) -> fetch.Page:
    """The one network call: HTTPS to Swissmilk's page host, or its photo host, and nowhere else (also not by
    redirect)."""
    host = PHOTO_HOST if url.startswith(PHOTO_PREFIX) else PAGE_HOST
    return fetch.fetch(url, accept=accept, allowed_hosts=frozenset({host}))


def is_swissmilk(url: str) -> bool:
    try:
        return (urlsplit(url).hostname or "").lower() == PAGE_HOST
    except ValueError:
        return False


def is_recipe_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme == "https" and parts.hostname == PAGE_HOST and not parts.query and bool(
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


def recipe(url: str) -> dict | None:
    if not is_recipe_url(url):
        raise fetch.FetchRefused(url)
    return _cached(f"recipe:{url}", lambda: read_recipe(_get(url).text, url))


def photo(url: str) -> bytes:
    if not url.startswith(PHOTO_PREFIX) or urlsplit(url).hostname != PHOTO_HOST:
        raise fetch.FetchRefused(url)
    return _cached(f"photo:{url}", lambda: photos.downscale(_get(url, accept=IMAGE_TYPES).body))
