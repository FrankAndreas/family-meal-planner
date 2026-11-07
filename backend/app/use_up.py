"""Was habe ich? How a recipe fits what someone has at home (spec 2026-11-01), for the family's collection and for
Swissmilk's."""

from .pantry import canonical, covered, matches
from .text import sort_key

# Jetzt kochen: recipes missing more than this aren't shown
MAX_MISSING = 2


def _optional(note: str) -> bool:
    note = sort_key(note or "")
    return "belieben" in note or "optional" in note


def check(ingredients: list[tuple[str, str]], typed: list[str], staples: list[str]) -> tuple[list[str], list[str]]:
    """For a recipe's (name, note) ingredients: which typed words it uses, and what is missing (neither typed nor
    a basic nor optional), each thing once."""
    used = [word for word in typed if any(matches(word, name) for name, _ in ingredients)]
    missing: list[str] = []
    for name, note in ingredients:
        if _optional(note) or any(matches(word, name) for word in typed) or covered(name, staples):
            continue
        # The same thing in two groups ("Butter" for dough and topping) is one thing to buy
        if canonical(name) not in {canonical(m) for m in missing}:
            missing.append(name)
    return used, missing


def fit(mode: str, used: list[str], missing: list[str]) -> tuple[int, int]:
    """How well a recipe fits, for sorting: Aufbrauchen by used first, Jetzt kochen by missing first."""
    return (-len(used), len(missing)) if mode == "use_up" else (len(missing), -len(used))


def typed_words(have: list[str]) -> list[str]:
    """The typed words without blanks, one per synonym group (as first typed)."""
    seen: set[str] = set()
    result = []
    for word in (h.strip() for h in have):
        if word and canonical(word) not in seen:
            seen.add(canonical(word))
            result.append(word)
    return result
