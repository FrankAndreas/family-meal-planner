import io
import time
from pathlib import Path

import pytest
from PIL import Image

from app import ai, fetch, swissmilk, swissmilk_api
from helpers import create_recipe, create_user, login

PAGES = Path(__file__).parent / "pages"
SEARCH = (PAGES / "swissmilk-search.html").read_text()
RECIPE = (PAGES / "swissmilk-recipe.html").read_text()
GRATIN = "https://www.swissmilk.ch/de/rezepte-kochideen/rezepte/LM_div_0812_03/kartoffelgratin/"


def _jpeg() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (4, 4), "blue").save(out, "JPEG")
    return out.getvalue()


@pytest.fixture
def site(monkeypatch):
    """A fake Swissmilk: the saved search page, and the saved Kartoffelgratin for every recipe link."""
    pages = {}
    swissmilk.clear_cache()
    swissmilk_api.reset_limits()

    def get(url, accept=fetch.PAGE_TYPES):
        if url in pages:
            result = pages[url](url) if callable(pages[url]) else pages[url]
            if isinstance(result, Exception):
                raise result
            return fetch.Page(url, "text/html", result.encode())
        if url.startswith(swissmilk.SEARCH):
            return fetch.Page(url, "text/html", SEARCH.encode())
        if url.startswith(swissmilk.PHOTO_PREFIX):
            return fetch.Page(url, "image/jpeg", _jpeg())
        # Each recipe page is the gratin, under its own address
        return fetch.Page(url, "text/html", RECIPE.encode())

    monkeypatch.setattr(swissmilk, "_get", get)
    yield pages
    swissmilk.clear_cache()
    swissmilk_api.reset_limits()


def _search(client, headers, *have, mode="use_up"):
    return client.get("/api/use-up/swissmilk", params=[("have", h) for h in have] + [("mode", mode)], headers=headers)


def test_search_ranks_and_checks(client, admin_headers, site):
    found = _search(client, admin_headers, "Kartoffeln").json()
    gratin = next(r for r in found if r["url"] == GRATIN)
    assert gratin["title"] == "Kartoffelgratin" and gratin["used"] == ["Kartoffeln"]
    assert gratin["missing"] == ["Milch", "Rahm", "Muskatnuss", "Gruyère AOP"]
    assert gratin["photo"].startswith("/api/use-up/swissmilk/photo/")
    assert gratin["recipe_id"] is None and gratin["waiting"] is False
    assert len(found) == 12


def test_cook_now_drops_too_many_missing(client, admin_headers, site):
    assert _search(client, admin_headers, "Kartoffeln", mode="cook_now").json() == []


def test_unreadable_page_is_skipped(client, admin_headers, site):
    site[GRATIN] = "<html></html>"
    found = _search(client, admin_headers, "Kartoffeln").json()
    assert GRATIN not in [r["url"] for r in found] and len(found) == 11


def test_slow_page_within_budget(client, admin_headers, site, monkeypatch):
    monkeypatch.setattr(swissmilk_api, "BUDGET_SECONDS", 1.0)

    def slow(url):
        time.sleep(3)
        return RECIPE

    site[GRATIN] = slow
    started = time.monotonic()
    found = _search(client, admin_headers, "Kartoffeln").json()
    assert time.monotonic() - started < 2.0
    assert GRATIN not in [r["url"] for r in found] and len(found) == 11


def test_search_page_down(client, admin_headers, site):
    site[swissmilk.search_url(["Kartoffeln"])] = fetch.FetchFailed("http 503")
    response = _search(client, admin_headers, "Kartoffeln")
    assert response.status_code == 502 and response.json()["detail"] == "swissmilk_unreachable"


def test_already_there(client, admin_headers, site):
    french = "https://www.swissmilk.ch/fr/recettes-idees/recettes/LM_div_0812_03/gratin/"
    mine = create_recipe(client, admin_headers, source_url=french)
    gratin = lambda: next(r for r in _search(client, admin_headers, "Kartoffeln").json() if r["url"] == GRATIN)  # noqa: E731
    assert gratin()["recipe_id"] == mine["id"]
    client.delete(f"/api/recipes/{mine['id']}", headers=admin_headers)
    swissmilk_api.reset_limits()
    assert gratin()["recipe_id"] is None
    create_user(client, admin_headers, "Lena")
    client.post("/api/inbox/urls", json={"url": GRATIN}, headers=login(client, "Lena", "5678"))
    swissmilk_api.reset_limits()
    assert gratin()["waiting"] is True


def test_photo_only_for_handed_out_keys(client, admin_headers, site):
    gratin = next(r for r in _search(client, admin_headers, "Kartoffeln").json() if r["url"] == GRATIN)
    photo = client.get(gratin["photo"], headers=admin_headers)
    assert photo.status_code == 200 and photo.headers["content-type"] == "image/jpeg"
    assert client.get("/api/use-up/swissmilk/photo/0000000000000000", headers=admin_headers).status_code == 404
    assert client.get(gratin["photo"]).status_code == 401


def test_one_search_per_5_seconds(client, admin_headers, site):
    assert _search(client, admin_headers, "Kartoffeln").status_code == 200
    again = _search(client, admin_headers, "Kartoffeln")
    assert again.status_code == 429 and again.json()["detail"] == "too_many_searches"
    create_user(client, admin_headers, "Lena")
    assert _search(client, login(client, "Lena", "5678"), "Kartoffeln").status_code == 200


def test_no_ai_called(client, admin_headers, site, monkeypatch):
    def no_ai(*args, **kwargs):
        raise AssertionError("the AI must not be asked")

    monkeypatch.setattr(ai, "client_for", no_ai)
    assert _search(client, admin_headers, "Kartoffeln").status_code == 200


def test_nothing_typed_asks_nobody(client, admin_headers, site, monkeypatch):
    monkeypatch.setattr(swissmilk, "_get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no call")))
    assert _search(client, admin_headers, " ").json() == []
