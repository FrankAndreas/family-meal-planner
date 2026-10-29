from pathlib import Path

from app.jsonld import recipe_from_html

PAGES = Path(__file__).parent / "pages"


def _page(name):
    return (PAGES / name).read_text()


def test_graph_recipe():
    draft = recipe_from_html(_page("swissmilk-like.html"), "https://www.swissmilk.ch/de/rezepte/a/")
    assert draft["title"] == "Älplermagronen" and draft["language"] == "de"
    assert draft["servings"] == 4 and draft["servings_unit"] is None
    assert draft["prep_minutes"] == 20 and draft["cook_minutes"] == 65
    assert draft["ingredients"][1] == {"amount": 300, "unit": "g", "name": "Kartoffeln", "note": "festkochend"}
    assert draft["steps"] == ["Sauce: Rahm & Käse aufkochen.", "Alles mischen."]
    assert draft["tags"] == ["Pasta", "Käse", "Kartoffeln", "Hauptgericht"]
    assert draft["image_url"] == "https://img.example.ch/a.jpg"
    assert draft["source_url"] == "https://www.swissmilk.ch/de/rezepte/a/" and draft["uncertain"] == []


def test_plain_recipe_other_yield():
    draft = recipe_from_html(_page("blog-plain.html"), "https://blog.example/w")
    assert draft["servings"] == 1 and draft["servings_unit"] == "Blech"
    assert draft["steps"] == ["Teig auslegen.", "Äpfel darauf."]
    assert draft["ingredients"][0] == {"amount": 1, "unit": None, "name": "Kuchenteig", "note": ""}
    assert draft["language"] is None


def test_no_recipe():
    assert recipe_from_html(_page("no-recipe.html"), "https://x") is None
    assert recipe_from_html("<html>nothing</html>", "https://x") is None
