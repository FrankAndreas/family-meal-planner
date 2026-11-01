"""Does an ingredient someone has at home match an ingredient of a recipe? The way a person would say it: plurals,
compound words and a few regional names count; look-alikes that are a different food don't (spec 2026-11-01:
a false ✓ is worse than a miss)."""

import re

from .text import sort_key

# What's always at home unless parents say otherwise
DEFAULT_STAPLES = ["Salz", "Pfeffer", "Öl", "Wasser", "Zucker", "Mehl", "Bouillon"]

# Base forms (see _base) that name the same thing; the first is the group's key
SYNONYMS: list[tuple[str, ...]] = [
    ("kartoffel", "hardopfel", "erdapfel"),
    ("rahm", "sahn"),
    ("ruebli", "karott", "mohr"),
    ("quark", "topf"),
    ("zucchetti", "zucchini"),
    ("peperon", "paprika"),
    ("nusslisalat", "feldsalat"),
]
_GROUP = {word: group for group in SYNONYMS for word in group}

# Compounds that end in the typed word but are a different food: the start that gives them away
EXCEPTIONS: dict[str, tuple[str, ...]] = {
    "lauch": ("knob", "schnitt", "bar"),
    "kartoffel": ("suss",),
    "zwiebel": ("fruhlings",),
    "milch": ("kokos",),
    "butt": ("erdnuss",),
    "ei": ("br", "salb"),
}

_ENDINGS = ("en", "er", "n", "e", "s")
_LETTERS = re.compile(r"[^\W\d_]+")
# The start of a compound counts only from this length on: "Lauch" finds "Lauchstange", "Ei" not "Eisbergsalat"
_MIN_START = 4
# The rest of a compound before its head: "Halb|rahm" yes, "R|eis" and "Br|ei" no
_MIN_FRONT = 3


def _base(word: str) -> str:
    """Without one plural or inflection ending: "tomaten" and "tomate" → "tomat", "eier" → "ei"."""
    for ending in _ENDINGS:
        if word.endswith(ending) and len(word) - len(ending) >= 2:
            return word[: -len(ending)]
    return word


def _words(name: str) -> list[str]:
    """The words of an ingredient name that can name the food: nothing in brackets, and only the nouns when the
    name has capitalized words ("festkochende Kartoffeln" → Kartoffeln)."""
    found = _LETTERS.findall(re.sub(r"\([^)]*\)", " ", name))
    nouns = [w for w in found if w[0].isupper()]
    return [_base(sort_key(w)) for w in (nouns or found)]


def canonical(word: str) -> str:
    """Equal for plurals and synonyms: counts "Rahm" and "Sahne" once."""
    return " ".join(_GROUP.get(base, (base,))[0] for base in _words(word))


def _matches_word(typed: str, word: str, strict: bool) -> bool:
    if word == typed:
        return True
    front = word[: -len(typed)] if word.endswith(typed) else None
    if front is not None and len(front) >= _MIN_FRONT:
        return not front.endswith(EXCEPTIONS.get(typed, ()))
    return not strict and len(typed) >= _MIN_START and word.startswith(typed)


def matches(typed: str, ingredient: str, *, strict: bool = False) -> bool:
    """Does the typed word match this ingredient name? `strict` (for basics): the whole word or the end of a compound,
    never its start ("Salz" is in "Meersalz", not in "Salzkartoffeln")."""
    # Typed text is read like an ingredient name ("Crème fraîche", "rote Zwiebeln"): each of its words must be there
    typed_words = _words(typed)
    words = _words(ingredient)
    return bool(typed_words) and all(
        any(_matches_word(form, word, strict) for form in _GROUP.get(base, (base,)) for word in words)
        for base in typed_words
    )
