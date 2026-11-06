"""The week's ingredients combined into a shopping list (spec 2026-11-06). Pure functions: the API feeds them the
scaled ingredients of the ticked meals and the free items."""

from dataclasses import dataclass, field

from .pantry import covered
from .scaling import round_amount
from .text import sort_key

Part = tuple[float, str | None]

# Units that add up with each other, in their base unit
_MASS = {"g": 1, "kg": 1000}
_VOLUME = {"ml": 1, "dl": 100, "l": 1000}


@dataclass
class Source:
    name: str
    amount: float | None
    unit: str | None
    meal: str


@dataclass
class Line:
    key: str
    name: str
    amounts: list[Part] = field(default_factory=list)
    extras: list[str] = field(default_factory=list)
    meals: list[str] = field(default_factory=list)
    staple: bool = False


def line_key(name: str) -> str:
    return sort_key(name.strip())


def _shown(total: float, kind: str) -> Part:
    """A sum in base units, in the unit people would write it."""
    if kind == "mass":
        unit = "g" if total < 1000 else "kg"
        return round_amount(total / _MASS[unit], unit), unit
    unit = "ml" if total < 100 else "dl" if total < 1000 else "l"
    return round_amount(total / _VOLUME[unit], unit), unit


def add_up(parts: list[Part]) -> list[Part]:
    """Amounts that can be added are added (g with kg, ml with dl and l, the same unit); the rest stay side by side,
    in the order they first appear."""
    totals: dict[str, float] = {}
    order: list[str] = []
    for amount, unit in parts:
        kind = "mass" if unit in _MASS else "volume" if unit in _VOLUME else f"unit:{unit}"
        base = amount * (_MASS.get(unit) or _VOLUME.get(unit) or 1) if unit else amount
        if kind not in totals:
            totals[kind] = 0
            order.append(kind)
        totals[kind] += base
    result: list[Part] = []
    for kind in order:
        if kind in ("mass", "volume"):
            result.append(_shown(totals[kind], kind))
        else:
            unit = kind.removeprefix("unit:")
            unit = None if unit == "None" else unit
            result.append((round_amount(totals[kind], unit), unit))
    return result


def combine(sources: list[Source], extras: list[tuple[str, str]], staples: list[str]) -> list[Line]:
    """One line per ingredient name (case and accents ignored), recipe lines first in the order they appear, then
    the free items that match no recipe line. A free item with a recipe line's name joins that line."""
    lines: dict[str, Line] = {}
    parts: dict[str, list[Part]] = {}
    for source in sources:
        key = line_key(source.name)
        line = lines.get(key)
        if line is None:
            line = lines[key] = Line(key=key, name=source.name.strip())
            parts[key] = []
        if source.amount is not None:
            parts[key].append((source.amount, source.unit))
        if source.meal not in line.meals:
            line.meals.append(source.meal)
    for key, line in lines.items():
        line.amounts = add_up(parts[key])
        line.staple = covered(line.name, staples, kinds=False)
    for name, amount in extras:
        key = line_key(name)
        if key not in lines:
            lines[key] = Line(key=key, name=name.strip())
        lines[key].extras.append(amount)
    return list(lines.values())
