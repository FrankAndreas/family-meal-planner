from pathlib import Path

from app import microdata, swissmilk

PAGES = Path(__file__).parent / "pages"
PAGE = (PAGES / "swissmilk-recipe.html").read_text()
URL = "https://www.swissmilk.ch/de/rezepte-kochideen/rezepte/LM_div_0812_03/kartoffelgratin/"


def test_reads_a_swissmilk_recipe():
    draft = swissmilk.read_recipe(PAGE, URL)
    assert draft["title"] == "Kartoffelgratin"
    assert draft["servings"] == 4 and draft["servings_unit"] is None
    assert (draft["prep_minutes"], draft["cook_minutes"]) == (20, 50)
    assert [i["name"] for i in draft["ingredients"]] == [
        "mehligkochende Kartoffeln", "Milch", "Rahm", "Knoblauchzehen", "Salz", "Pfeffer", "Muskatnuss",
        "Gruyère AOP", "Butterflöckli",
    ]
    assert draft["ingredients"][0]["amount"] == 800 and draft["ingredients"][0]["unit"] == "g"
    assert "nach Belieben" in draft["ingredients"][3]["note"]
    assert len(draft["steps"]) == 6 and draft["steps"][1] == "Kartoffelscheiben in die Form schichten."
    assert draft["image_url"] == "https://api.swissmilk.ch/wp-content/uploads/2019/06/kartoffelgratin-2560x1920.jpg"
    assert "Vegetarisch" in draft["tags"] and draft["source_url"] == URL


def test_page_without_recipe_microdata():
    assert swissmilk.read_recipe("<html><body>Nichts</body></html>", URL) is None


def test_generic_microdata_keeps_all_rows():
    draft = microdata.recipe_from_html(PAGE, URL)
    assert draft["ingredients"][0]["name"].startswith("ofenfeste Form")
    assert draft["title"] == "Kartoffelgratin"
