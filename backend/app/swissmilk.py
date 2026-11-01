"""Swissmilk (swissmilk.ch): the only code that talks to it. Fixed addresses, structured data only, never the AI
(spec 2026-11-01-swissmilk-search-design)."""

import re

from . import microdata
from .ingredient_parse import parse_line

PHOTO_PREFIX = "https://api.swissmilk.ch/wp-content/uploads/"
MAX_INGREDIENTS = 60
MAX_NAME = 200


def _real_ingredient(attrs: dict[str, str]) -> bool:
    """Swissmilk marks ingredient rows with the class "Ingredient"; equipment ("ofenfeste Form ca. 2 l") has none."""
    return "Ingredient" in attrs.get("class", "").split()


def _split_list(ingredient: dict) -> list[dict]:
    """ "Salz, Pfeffer, Muskatnuss" (no amount, every part a noun) is three ingredients, not one with a note."""
    if ingredient["amount"] is not None or not ingredient["note"]:
        return [ingredient]
    parts = [ingredient["name"], *(p.strip() for p in ingredient["note"].split(","))]
    if not all(p and p[0].isupper() for p in parts):
        return [ingredient]
    return [{"amount": None, "unit": None, "name": p, "note": ""} for p in parts]


def read_recipe(page: str, page_url: str) -> dict | None:
    """A recipe draft from a Swissmilk recipe page, or None if it has none."""
    node = microdata.recipe_node(page, keep_ingredient=_real_ingredient)
    if not node:
        return None
    images = node.get("image") or []
    node["recipeIngredient"] = [line.replace("*", "") for line in node.get("recipeIngredient", [])]
    node["image"] = next((i for i in images if i.startswith(PHOTO_PREFIX)), None)
    draft = microdata.draft_from_node(node, page_url)
    if not draft:
        return None
    ingredients = [split for i in draft["ingredients"] for split in _split_list(i)]
    draft["ingredients"] = [{**i, "name": i["name"][:MAX_NAME]} for i in ingredients if i["name"]][:MAX_INGREDIENTS]
    draft["title"] = re.sub(r"\s+", " ", draft["title"])[:MAX_NAME]
    return draft
