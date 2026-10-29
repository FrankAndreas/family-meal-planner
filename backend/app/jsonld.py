"""The schema.org Recipe most recipe sites (Swissmilk, Fooby, Betty Bossi, blogs) put in their pages, as a draft.
No AI involved."""

import html
import json
import re
from html.parser import HTMLParser

from .ingredient_parse import parse_line
from .schemas import PEOPLE_WORDS

MAX_TAGS = 5


class _Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.blocks: list[str] = []
        self._inside = False

    def handle_starttag(self, tag, attrs):
        self._inside = tag == "script" and dict(attrs).get("type", "").lower() == "application/ld+json"
        if self._inside:
            self.blocks.append("")

    def handle_endtag(self, tag):
        if tag == "script":
            self._inside = False

    def handle_data(self, data):
        if self._inside:
            self.blocks[-1] += data


def _nodes(value):
    """Every dict in a JSON-LD document (lists and @graph included)."""
    if isinstance(value, list):
        for item in value:
            yield from _nodes(item)
    elif isinstance(value, dict):
        yield value
        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in value:
                yield from _nodes(value[key])


def _is_recipe(node: dict) -> bool:
    kind = node.get("@type")
    return kind == "Recipe" or (isinstance(kind, list) and "Recipe" in kind)


def _text(value) -> str:
    """Plain text: entities decoded, tags dropped (sites sometimes put HTML into JSON-LD)."""
    text = " ".join(re.sub(r"<[^>]+>", " ", html.unescape(str(value or ""))).split())
    return re.sub(r" ([.,;:!?])", r"\1", text)


def _minutes(value) -> int | None:
    match = re.fullmatch(r"P(?:\d+D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:\d+S)?", str(value or "").strip())
    if not match or not (match.group(1) or match.group(2)):
        return None
    return int(match.group(1) or 0) * 60 + int(match.group(2) or 0)


def _yield(value) -> tuple[float, str | None]:
    values = value if isinstance(value, list) else [value]
    # The most telling entry: one with a word ("4 Personen", "1 Blech"), else the first
    texts = [_text(v) for v in values if _text(v)]
    texts.sort(key=lambda t: not re.search(r"[^\d\s.,]", t))
    for text in texts:
        match = re.match(r"(\d+(?:[.,]\d+)?)\s*(.*)", text)
        if match:
            amount = float(match.group(1).replace(",", "."))
            unit = match.group(2).strip()[:30] or None
            if unit and unit.casefold().rstrip(".") in PEOPLE_WORDS:
                unit = None
            return (amount if 0 < amount <= 100 else 4), unit
    return 4, None


def _steps(value) -> list[str]:
    if isinstance(value, str):
        return [_text(line) for line in value.splitlines() if _text(line)]
    steps: list[str] = []
    for item in value if isinstance(value, list) else [value]:
        if isinstance(item, str):
            steps.extend(_steps(item))
        elif isinstance(item, dict) and item.get("@type") == "HowToSection":
            name = _text(item.get("name"))
            for step in _steps(item.get("itemListElement") or []):
                steps.append(f"{name}: {step}" if name else step)
        elif isinstance(item, dict):
            text = _text(item.get("text") or item.get("name"))
            if text:
                steps.append(text)
    return steps


def _tags(node: dict) -> list[str]:
    tags: list[str] = []
    for key in ("keywords", "recipeCategory"):
        value = node.get(key)
        items = value if isinstance(value, list) else str(value or "").split(",")
        for tag in (_text(t) for t in items):
            if tag and tag.casefold() not in {t.casefold() for t in tags}:
                tags.append(tag[:40])
    return tags[:MAX_TAGS]


def _image(value) -> str | None:
    if isinstance(value, list):
        return next((url for url in map(_image, value) if url), None)
    if isinstance(value, dict):
        return _image(value.get("url") or value.get("contentUrl"))
    text = str(value or "").strip()
    return text if text.lower().startswith(("http://", "https://")) else None


def recipe_from_html(page: str, page_url: str) -> dict | None:
    parser = _Scripts()
    try:
        parser.feed(page)
    except Exception:
        return None
    for block in parser.blocks:
        try:
            document = json.loads(block)
        except ValueError:
            continue
        node = next((n for n in _nodes(document) if _is_recipe(n)), None)
        if node is None or not _text(node.get("name")):
            continue
        servings, servings_unit = _yield(node.get("recipeYield"))
        prep, cook = _minutes(node.get("prepTime")), _minutes(node.get("cookTime"))
        if prep is None and cook is None:
            cook = _minutes(node.get("totalTime"))
        language = str(node.get("inLanguage") or "")[:2].lower()
        ingredients = [parse_line(_text(line)) for line in node.get("recipeIngredient") or []]
        return {
            "title": _text(node.get("name"))[:200],
            "servings": servings,
            "servings_unit": servings_unit,
            "prep_minutes": prep,
            "cook_minutes": cook,
            "ingredients": [i for i in ingredients if i["name"]][:100],
            "steps": _steps(node.get("recipeInstructions") or [])[:60],
            "tags": _tags(node),
            "notes": "",
            "language": language if language in ("de", "en") else None,
            "source_url": page_url,
            "image_url": _image(node.get("image")),
            "uncertain": [],
        }
    return None
