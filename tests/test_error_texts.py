"""Every error code the backend sends has a text in both frontend languages (else people read "Something went
wrong")."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _codes() -> set[str]:
    codes: set[str] = set()
    for source in (ROOT / "backend" / "app").glob("*.py"):
        codes |= set(re.findall(r'api_error\(\s*[\w.]+,\s*"(\w+)"', source.read_text()))
        codes |= set(re.findall(r'ValueError\("(\w+)"\)', source.read_text()))
    return codes


def _locale_errors(name: str) -> set[str]:
    text = (ROOT / "frontend" / "src" / "locales" / f"{name}.ts").read_text()
    block = text[text.index("    errors: {") : text.index("\n    },", text.index("    errors: {"))]
    return set(re.findall(r"^\s+(\w+):", block, re.M))


def test_codes_found():
    assert {"wrong_name_or_pin", "recipe_not_found", "entry_not_found"} <= _codes()


def test_every_code_has_a_text():
    for name in ("de", "en"):
        assert _codes() - _locale_errors(name) == set(), name
