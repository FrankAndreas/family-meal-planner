"""Recipe categories (spec 2026-11-05): a fixed list, which of them fit a slot of the day, and the words on websites
and in tags that name them. The text shown for a key comes from the frontend's locales."""

import re
from collections.abc import Iterable
from typing import Literal

from .text import sort_key

# The order everywhere they're listed; frontend/src/categories.ts mirrors it
CATEGORIES = ("breakfast", "apero", "starter", "soup", "salad", "main", "side", "dessert", "baking", "snack")
Category = Literal["breakfast", "apero", "starter", "soup", "salad", "main", "side", "dessert", "baking", "snack"]

# What comes first in the suggestions when planning that slot
SLOT_FITS: dict[str, frozenset[str]] = {
    "breakfast": frozenset({"breakfast", "baking"}),
    "snack": frozenset({"snack", "baking", "apero"}),
    "lunch": frozenset({"main", "soup", "salad", "starter"}),
    "dinner": frozenset({"main", "soup", "salad", "starter"}),
}
# Usually planned next to a main dish: neither up nor down
NEUTRAL = frozenset({"side", "dessert"})

WORDS: dict[str, tuple[str, ...]] = {
    "breakfast": ("Frühstück", "Zmorge", "Brunch", "Breakfast"),
    "apero": ("Apéro", "Apéros", "Apero", "Aperitif", "Fingerfood", "Appetizer", "Appetizers", "Häppchen"),
    "starter": ("Vorspeise", "Vorspeisen", "Starter", "Starters", "Entrée", "Entrées"),
    "soup": ("Suppe", "Suppen", "Soup", "Soups", "Soupe", "Soupes"),
    "salad": ("Salat", "Salate", "Salad", "Salads", "Salade", "Salades"),
    "main": (
        "Hauptgericht", "Hauptgerichte", "Hauptspeise", "Hauptspeisen", "Hauptgang", "Main course", "Main courses",
        "Main dish", "Main dishes", "Plat principal", "Plats principaux",
    ),
    "side": ("Beilage", "Beilagen", "Side dish", "Side dishes", "Accompagnement", "Accompagnements"),
    "dessert": ("Dessert", "Desserts", "Nachspeise", "Nachspeisen", "Nachtisch", "Süssspeise", "Süssspeisen"),
    "baking": (
        "Gebäck", "Kuchen", "Backen", "Brot", "Brote", "Guetzli", "Torte", "Torten", "Cake", "Cakes", "Baking",
    ),
    "snack": ("Snack", "Snacks", "Zvieri", "Znüni", "Imbiss"),
}

_PATTERNS = {
    category: re.compile("|".join(rf"(?<!\w){re.escape(sort_key(w))}(?!\w)" for w in words))
    for category, words in WORDS.items()
}


def clean(values: Iterable[object]) -> list[str]:
    """Known keys only, each once, in the list's order."""
    given = set(v for v in values if isinstance(v, str))
    return [c for c in CATEGORIES if c in given]


def from_words(values: Iterable[str]) -> tuple[list[str], list[str]]:
    """The categories the values name (whole words, case and accents ignored), and the values that named none, as
    they were. A value is not split further: callers split on commas."""
    found: set[str] = set()
    rest: list[str] = []
    for value in values:
        key = sort_key(value)
        named = {c for c, pattern in _PATTERNS.items() if pattern.search(key)}
        if named:
            found |= named
        else:
            rest.append(value)
    return [c for c in CATEGORIES if c in found], rest


def slot_group(categories: Iterable[str], slot: str) -> int:
    """0: fits the slot; 1: unknown (no categories, or only side dish / dessert); 2: fits another slot."""
    known = set(clean(categories))
    if known & SLOT_FITS[slot]:
        return 0
    if known <= NEUTRAL:
        return 1
    return 2
