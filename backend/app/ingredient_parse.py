"""Ingredient lines as recipe pages write them ("200 g Mehl", "1–2 Zwiebeln, fein gehackt") → amount, unit, name,
note. Units are mapped to units.UNITS; anything else stays in the name."""

import re

# Word (lowercase, without a trailing dot) → unit key, or (unit key, factor)
UNIT_WORDS: dict[str, str | tuple[str, float]] = {
    **dict.fromkeys(["g", "gr", "gramm", "gram", "grams"], "g"),
    "kg": "kg",
    "ml": "ml",
    "cl": ("ml", 10),
    "dl": "dl",
    **dict.fromkeys(["l", "liter", "litre", "liters"], "l"),
    **dict.fromkeys(["tl", "tsp", "teaspoon", "teaspoons"], "tsp"),
    **dict.fromkeys(["el", "tbsp", "tablespoon", "tablespoons"], "tbsp"),
    **dict.fromkeys(["prise", "prisen", "pinch"], "pinch"),
    **dict.fromkeys(["stk", "stück", "piece", "pieces", "pc", "pcs"], "piece"),
    **dict.fromkeys(["zehe", "zehen", "clove", "cloves"], "clove"),
    **dict.fromkeys(["scheibe", "scheiben", "slice", "slices"], "slice"),
    **dict.fromkeys(["bund", "bunch"], "bunch"),
    **dict.fromkeys(["dose", "dosen", "can", "cans"], "can"),
    **dict.fromkeys(["becher", "pot"], "cup"),
    **dict.fromkeys(["pck", "packung", "päckchen", "pack"], "pack"),
    **dict.fromkeys(["handvoll", "handful"], "handful"),
}
VULGAR = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3}
_AMOUNT = r"(?:\d+\s+\d+/\d+|\d+/\d+|\d*[½¼¾⅓⅔]|\d+(?:[.,]\d+)?)"
_LINE = re.compile(rf"^({_AMOUNT})(?:\s*(?:–|-|bis)\s*({_AMOUNT}))?\s*(.*)$")


def _value(text: str) -> float:
    text = text.strip()
    if " " in text:
        whole, fraction = text.split()
        return int(whole) + _value(fraction)
    if "/" in text:
        top, bottom = text.split("/")
        return int(top) / int(bottom)
    if text[-1] in VULGAR:
        return (int(text[:-1]) if text[:-1] else 0) + VULGAR[text[-1]]
    return float(text.replace(",", "."))


def parse_line(line: str) -> dict:
    text = " ".join(line.split())
    notes: list[str] = []
    amount = unit = None
    match = _LINE.match(text)
    if match:
        try:
            amount = _value(match.group(1))
        except (ValueError, ZeroDivisionError):
            amount = None
        if match.group(2):
            # "1–2 Zwiebeln": the lower amount, the range kept as a note
            notes.append(text[: match.start(3)].strip())
        text = match.group(3)
        first, _, rest = text.partition(" ")
        known = UNIT_WORDS.get(first.lower().rstrip("."))
        if known and amount is not None and rest:
            unit, factor = (known, 1) if isinstance(known, str) else known
            amount = round(amount * factor, 4)
            text = rest
    # Parentheses and what follows a comma are notes: "Hörnli (z. B. Barilla)", "Kartoffeln, festkochend"
    for inner in re.findall(r"\(([^)]*)\)", text):
        notes.append(inner.strip())
    text = re.sub(r"\s*\([^)]*\)", "", text)
    name, comma, after = text.partition(",")
    if comma and after.strip():
        notes.append(after.strip())
    if amount is not None and amount == int(amount):
        amount = int(amount)
    return {"amount": amount, "unit": unit, "name": name.strip(), "note": ", ".join(n for n in notes if n)}
