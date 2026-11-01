import re
from pathlib import Path

import pytest

from app import fetch, microdata, swissmilk

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


SEARCH = (PAGES / "swissmilk-search.html").read_text()
FIRST = "https://www.swissmilk.ch/de/rezepte-kochideen/rezepte/LM_div_0812_03/kartoffelgratin/"
PATTERN = r"^https://www\.swissmilk\.ch/de/rezepte-kochideen/rezepte/[A-Za-z0-9_]+/[a-z0-9-]+/$"


@pytest.fixture(autouse=True)
def fresh_cache():
    swissmilk.clear_cache()
    yield
    swissmilk.clear_cache()


def test_candidates_from_the_search_page():
    page = (
        '<a href="https://evil.example/de/rezepte-kochideen/rezepte/X/y/">x</a><a href="/de/suche/">s</a>' + SEARCH
    )
    found = swissmilk.candidates(page)
    assert len(found) == 12 and found[0] == FIRST
    assert all(re.match(PATTERN, url) for url in found) and len(set(found)) == 12


def test_search_url_encodes_words():
    assert (
        swissmilk.search_url(["Rüebli", "Salz & Pfeffer", "#1"])
        == "https://www.swissmilk.ch/de/suche/?q=R%C3%BCebli+Salz+%26+Pfeffer+%231"
    )


def test_recipe_and_photo_refuse_other_addresses(monkeypatch):
    calls = []
    monkeypatch.setattr(swissmilk, "_get", lambda url, accept=None: calls.append(url))
    with pytest.raises(fetch.FetchRefused):
        swissmilk.recipe("https://www.swissmilk.ch/de/suche/")
    with pytest.raises(fetch.FetchRefused):
        swissmilk.photo("https://res.cloudinary.com/x.jpg")
    assert calls == []


def test_recipe_is_cached(monkeypatch):
    calls = []

    def get(url, accept=None):
        calls.append(url)
        return fetch.Page(url, "text/html", PAGE.encode())

    monkeypatch.setattr(swissmilk, "_get", get)
    assert swissmilk.recipe(FIRST)["title"] == "Kartoffelgratin"
    assert swissmilk.recipe(FIRST)["title"] == "Kartoffelgratin"
    assert calls == [FIRST]


def test_photo_is_downscaled_and_cached(monkeypatch):
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (3000, 2000), "red").save(buffer, "PNG")
    calls = []

    def get(url, accept=None):
        calls.append(url)
        return fetch.Page(url, "image/png", buffer.getvalue())

    monkeypatch.setattr(swissmilk, "_get", get)
    url = swissmilk.PHOTO_PREFIX + "2019/06/x.jpg"
    data = swissmilk.photo(url)
    assert swissmilk.photo(url) == data and calls == [url]
    with Image.open(io.BytesIO(data)) as image:
        assert image.format == "JPEG" and max(image.size) == swissmilk.THUMB_SIDE == 320


def test_recipe_id():
    assert swissmilk.recipe_id(FIRST) == "LM_div_0812_03"
    assert swissmilk.recipe_id("https://www.swissmilk.ch/fr/recettes-idees/recettes/LM_div_0812_03/gratin/?x=1") == "LM_div_0812_03"
    assert swissmilk.recipe_id("https://www.swissmilk.ch/de/suche/") is None
    assert swissmilk.is_swissmilk(FIRST) and not swissmilk.is_swissmilk("https://swissmilk.ch.evil.example/")


def test_original_photo_only_from_swissmilk(monkeypatch):
    monkeypatch.setattr(swissmilk, "_get", lambda url, accept=None: fetch.Page(url, "image/jpeg", b"raw"))
    assert swissmilk.original_photo(swissmilk.PHOTO_PREFIX + "a.jpg") == b"raw"
    with pytest.raises(fetch.FetchRefused):
        swissmilk.original_photo("https://res.cloudinary.com/a.jpg")


def test_photo_keys_outlive_a_full_cache(monkeypatch):
    monkeypatch.setattr(swissmilk, "_get", lambda url, accept=None: fetch.Page(url, "text/html", b"<html></html>"))
    key = swissmilk.remember_photo(swissmilk.PHOTO_PREFIX + "a.jpg")
    for n in range(swissmilk.CACHE_ENTRIES + 50):
        swissmilk.recipe(f"https://www.swissmilk.ch/de/rezepte-kochideen/rezepte/X{n}/y/")
    assert swissmilk.photo_for(key) == swissmilk.PHOTO_PREFIX + "a.jpg"


def test_every_spelling_of_swissmilk():
    for url in ("https://swissmilk.ch/x", "https://www.swissmilk.ch./x", "https://api.swissmilk.ch/x", FIRST):
        assert swissmilk.is_swissmilk(url)
    assert not swissmilk.is_swissmilk("https://notswissmilk.ch/x")
    assert swissmilk.page_url("http://swissmilk.ch./de/a/?b=1") == "https://www.swissmilk.ch/de/a/?b=1"
    assert swissmilk.page_url("https://api.swissmilk.ch/x") is None
