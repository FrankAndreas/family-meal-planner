"""Scaling a recipe to the number of people at the table, with amounts rounded the way people measure.

Pure functions: the recipe view uses them now, a shopping list later.
"""

import math

# Things counted, not weighed: half an egg is fine, a third isn't
COUNTED = {None, "piece", "clove", "slice", "bunch", "can", "cup", "pack", "handful"}


def _nearest(value: float, step: float) -> float:
    # Half up (2.25 → 2.5), and rounded again against float noise (0.1 + 0.2)
    return round(math.floor(value / step + 0.5) * step, 4)


def round_amount(amount: float, unit: str | None) -> float:
    if unit in ("g", "ml"):
        step = 1 if amount < 10 else 5 if amount < 100 else 10 if amount < 1000 else 50
        return _nearest(amount, step)
    if unit in ("kg", "l"):
        return _nearest(amount, 0.05 if amount < 1 else 0.1)
    if unit == "dl":
        return max(_nearest(amount, 0.5), 0.5)
    if unit in ("tsp", "tbsp"):
        return max(_nearest(amount, 0.25 if amount < 1 else 0.5), 0.25)
    if unit == "pinch":
        return max(_nearest(amount, 1), 1)
    if unit in COUNTED:
        return max(_nearest(amount, 0.5), 0.5)
    return amount


def factor(servings: float, servings_unit: str | None, people: float, family_size: int) -> float:
    """How much of the recipe `people` need. A yield in other units ("1 Blech") is taken as meant for the family."""
    return people / (servings if servings_unit is None else family_size)


def scale(amount: float | None, unit: str | None, factor: float) -> float | None:
    if amount is None:
        return None
    # At the recipe's own yield, show what was written
    if factor == 1:
        return amount
    return round_amount(amount * factor, unit)
