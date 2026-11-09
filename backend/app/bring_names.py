"""Ingredient names as Bring! knows them (issue #70). A recipe says "mehligkochende Kartoffeln" or "glatter Peterli";
Bring! sorts and shows an icon only for its own articles ("Kartoffeln", "Petersilie"), everything else lands under
"Eigene Artikel". So the shopping list names the food by its noun, mapped to Bring!'s article where one fits, and the
describing words go to the amount text Bring! shows under the item.

Rules only, no AI: a name that matches nothing stays as the recipe wrote it (without the describing words)."""

import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from .ingredient_parse import UNIT_WORDS
from .pantry import canonical

# Bring!'s de-CH catalog (https://web.getbring.com/locale/articles.de-CH.json, sections left out): article id → the
# name the Swiss app shows. Bring! recognizes an item by its id ("Rote Bete" shows as "Randen").
_ARTICLES_FILE = Path(__file__).with_name("bring_articles.json")

# Names Bring! has no article for that mean one it has, as canonical() reads them → (article name, the unit of an
# amount without one: "1 Knoblauchzehe" is 1 clove, not 1 bulb)
ALIASES: dict[str, tuple[str, str | None]] = {
    "peterli": ("Petersilie", None),
    "knoblauchzeh": ("Knoblauch", "clove"),
    "vollrahm": ("Rahm", None),
    "halbrahm": ("Rahm", None),
    "schlagrahm": ("Rahm", None),
    "eigelb": ("Eier", None),
    "eiweiss": ("Eier", None),
    "eiklar": ("Eier", None),
    "zitronensaft": ("Zitrone", None),
}

# Where the name stops naming the food: "Entrecôtes vom Rind à je ca. 180 g", "Öl zum Braten"
_TAIL = re.compile(r"\s(?:zum|zur|für|fur|aus|nach|mit|von|vom|à|je|ca\.)\s.*$", re.IGNORECASE)
# Lengths aren't units a recipe amount can have; "2 cm Ingwer" is read as 2 and "cm Ingwer"
_LENGTHS = {"cm", "mm"}


@dataclass(frozen=True)
class ShoppingName:
    name: str
    detail: str = ""
    # The unit for an amount the recipe gave none (see ALIASES)
    unit: str | None = None


@cache
def articles() -> dict[str, str]:
    return json.loads(_ARTICLES_FILE.read_text(encoding="utf-8"))


@cache
def _by_canonical() -> dict[str, tuple[str, str]]:
    """canonical() of an article's name (and of its id) → (id, name)."""
    found: dict[str, tuple[str, str]] = {}
    for article_id, name in articles().items():
        for text in (article_id, name):
            found.setdefault(canonical(text), (article_id, name))
    return found


def article_id(name: str) -> str:
    """What Bring! gets as the item: the article's id for a catalog name, else the name itself."""
    found = _by_canonical().get(canonical(name))
    return found[0] if found else name


def _describing(word: str) -> bool:
    return not word[:1].isupper()


def shopping_name(name: str) -> ShoppingName:
    """The name for the shopping list: "mehligkochende Kartoffeln" → Kartoffeln ("mehligkochende"), "glatter Peterli"
    → Petersilie ("glatter"). A name without a capitalized word (not German) stays as it is."""
    text = re.sub(r"\s*\([^)]*\)", "", " ".join(name.split())).strip()
    main, _, after = text.partition(",")
    details: list[str] = []
    tail = _TAIL.search(main)
    if tail:
        details.append(tail.group(0).strip())
        main = main[: tail.start()]
    words = main.split()
    head = next((i for i, word in enumerate(words) if not _describing(word)), None)
    if head is None:
        return ShoppingName(name.strip())
    before = [w for w in words[:head] if w.lower().rstrip(".") not in UNIT_WORDS and w.lower() not in _LENGTHS]
    details = [" ".join(before), *details, after.strip()]
    food = " ".join(words[head:])
    unit = None
    alias = ALIASES.get(canonical(food))
    if alias:
        food, unit = alias
    found = _by_canonical().get(canonical(food))
    if found:
        food = found[1]
    return ShoppingName(food, ", ".join(d for d in details if d), unit)
