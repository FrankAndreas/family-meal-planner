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
    ("nusslisalat", "feldsalat"),
]
_GROUP = {word: group for group in SYNONYMS for word in group}

# Compounds that end in the typed word but are a different food: the start that gives them away
EXCEPTIONS: dict[str, tuple[str, ...]] = {
    "lauch": ("knob", "schnitt", "bar"),
    "kartoffel": ("suss",),
    "zwiebel": ("fruhlings", "lauch"),
    "milch": ("kokos", "butter", "mandel", "hafer", "soja"),
    "butt": ("erdnuss",),
    "ei": ("br", "salb", "kl"),
    "nuss": ("muskat",),
    "apfel": ("granat", "erd"),
    "ol": ("karfi",),
}

_ENDINGS = ("en", "er", "n", "e", "s")
# A final "s" after these stays: "Reis", "Mais", "Nuss" are no plurals
_KEEP_S_AFTER = ("i", "s")
_LETTERS = re.compile(r"[^\W\d_]+")
# The start of a compound counts only from this length on: "Lauch" finds "Lauchstange", "Ei" not "Eisbergsalat"
_MIN_START = 4
# The rest of a compound before its head: "Halb|rahm" yes, "R|eis" and "Br|ei" no
_MIN_FRONT = 3


def _base(word: str) -> str:
    """Without one plural or inflection ending: "tomaten" and "tomate" → "tomat", "eier" → "ei", "nusse" → "nuss"."""
    for ending in _ENDINGS:
        if ending == "s" and word[:-1].endswith(_KEEP_S_AFTER):
            continue
        if word.endswith(ending) and len(word) - len(ending) >= 2:
            return word[: -len(ending)]
    return word


# Words that start with a typed word but are a different food: "Butter" isn't "Buttermilch"
NOT_STARTS = {_base(w) for w in ("buttermilch", "zitronengras", "kohlrabi")}
# What makes a describing word of a food word: "mehl|ig", "mehl|igkochend"
_DESCRIBING = ("ig", "lich", "isch")


def _words(name: str, nouns_only: bool = True) -> list[str]:
    """The words of an ingredient name that can name the food: nothing in brackets, and only the nouns when the
    name has capitalized words ("festkochende Kartoffeln" → Kartoffeln)."""
    found = _LETTERS.findall(re.sub(r"\([^)]*\)", " ", name))
    nouns = [w for w in found if w[0].isupper()] if nouns_only else []
    return [_base(sort_key(w)) for w in (nouns or found)]


def _typed_words(text: str) -> list[str]:
    """What someone typed, word by word, whatever the case: the part before a comma ("Lauch, in Ringen" → Lauch)."""
    return _words(text.split(",")[0], nouns_only=False)


def canonical(word: str) -> str:
    """Equal for plurals and synonyms: counts "Rahm" and "Sahne" once."""
    return " ".join(_GROUP.get(base, (base,))[0] for base in _typed_words(word))


def _matches_word(typed: str, word: str, strict: bool) -> bool:
    if word == typed:
        return True
    front = word[: -len(typed)] if word.endswith(typed) else None
    if front is not None and len(front) >= _MIN_FRONT:
        return not front.endswith(EXCEPTIONS.get(typed, ()))
    return (
        not strict
        and len(typed) >= _MIN_START
        and word.startswith(typed)
        and word not in NOT_STARTS
        and not word[len(typed) :].startswith(_DESCRIBING)
    )


def matches(typed: str, ingredient: str, *, strict: bool = False) -> bool:
    """Does the typed word match this ingredient name? `strict` (for basics): the whole word or the end of a compound,
    never its start ("Salz" is in "Meersalz", not in "Salzkartoffeln")."""
    # One typed word looks at the nouns only ("Mehl" isn't in "mehlige Kartoffeln"); several must all be there,
    # whatever the case ("crème fraîche" is in "Crème fraîche", not in "Crème double")
    typed_words = _typed_words(typed)
    words = _words(ingredient, nouns_only=len(typed_words) == 1)
    return bool(typed_words) and all(
        any(_matches_word(form, word, strict) for form in _GROUP.get(base, (base,)) for word in words)
        for base in typed_words
    )


# Where an ingredient name stops naming the food: "Öl zum Braten", "Pfeffer aus der Mühle"
_PURPOSE = re.compile(r"\s(?:zum|zur|für|fur|aus|nach|mit|von|vom|in|im|am|auf)\s.*$", re.IGNORECASE)
_ALTERNATIVES = re.compile(r"\s+oder\s+", re.IGNORECASE)
_TOGETHER = re.compile(r"\s+und\s+|\s*[&/+]\s*", re.IGNORECASE)


def covered(ingredient: str, staples: list[str]) -> bool:
    """Is the ingredient a basic? Read up to a comma (the rest describes it); each thing it names together
    ("Salz und Pfeffer") must be a basic, of alternatives ("Butter oder Öl") one is enough. "Zitronensaft und Salz"
    is no basic: the lemon juice is still to buy."""
    name = re.sub(r"\([^)]*\)", " ", ingredient).split(",")[0]

    def is_basic(part: str) -> bool:
        part = _PURPOSE.sub("", " " + part.strip()).strip()
        return bool(part) and any(matches(staple, part, strict=True) for staple in staples)

    return any(
        all(is_basic(part) for part in _TOGETHER.split(alternative)) for alternative in _ALTERNATIVES.split(name)
    )
