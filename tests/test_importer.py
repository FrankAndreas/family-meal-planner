import json
from datetime import timedelta
from pathlib import Path

import pytest

from app import ai, config, fetch, importer, models
from app.timeutil import utcnow
from helpers import create_user, login
from mails import build_mail, png

PAGES = Path(__file__).parent / "pages"
GOOD = {
    "title": "Mail-Risotto",
    "servings": 4,
    "ingredients": [{"amount": 300, "unit": "g", "name": "Reis", "note": ""}],
    "steps": ["Kochen"],
    "uncertain": ["300 g?"],
    "image_index": 1,
}


@pytest.fixture
def world(monkeypatch):
    """Fake web pages, a recording AI, and processing run at once instead of in a thread."""
    monkeypatch.setenv("INFOMANIAK_AI_TOKEN", "t")
    monkeypatch.setenv("INFOMANIAK_AI_PRODUCT_ID", "p")
    monkeypatch.setenv("INBOUND_SECRET", "s")
    pages: dict = {}
    calls: list = []

    def fake_fetch(url, accept=fetch.PAGE_TYPES):
        if url not in pages:
            raise fetch.FetchFailed("http 404")
        kind, body = pages[url]
        if not any(kind.startswith(a) for a in accept):
            raise fetch.FetchFailed("type")
        return fetch.Page(url, kind, body)

    class Recorder:
        def complete(self, content):
            calls.append(content)
            return ai.Answer(json.dumps(GOOD), 99)

    monkeypatch.setattr(importer.fetch, "fetch", fake_fetch)
    monkeypatch.setattr(importer.ai, "client_for", lambda settings: Recorder())
    monkeypatch.setattr(importer, "start", importer.run)
    return pages, calls


def _html(name):
    return ("text/html; charset=utf-8", (PAGES / name).read_bytes())


def _jpeg():
    import io

    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (800, 600), (10, 200, 10)).save(out, "JPEG")
    return out.getvalue()


def _mail(client, headers, **kwargs):
    client.post("/api/emails", json={"address": "papa@example.ch"}, headers=headers)
    response = client.post("/api/inbound", content=build_mail(**kwargs), headers={"X-Inbound-Secret": "s"})
    return response.json()["id"]


def _item(client, headers, item_id):
    return client.get(f"/api/inbox/{item_id}", headers=headers).json()


def test_url_with_jsonld_needs_no_ai(client, admin_headers, world, db):
    pages, calls = world
    pages["https://www.swissmilk.ch/r"] = _html("swissmilk-like.html")
    pages["https://img.example.ch/a.jpg"] = ("image/jpeg", _jpeg())
    item = client.post("/api/inbox/urls", json={"url": "https://www.swissmilk.ch/r"}, headers=admin_headers).json()
    got = _item(client, admin_headers, item["id"])
    assert got["status"] == "draft" and got["draft"]["title"] == "Älplermagronen"
    assert got["draft"]["photo"] and (config.data_dir() / "photos" / got["draft"]["photo"]).is_file()
    assert calls == [] and db.query(models.AiCall).count() == 0


def test_url_without_jsonld_asks_the_ai(client, admin_headers, world, db):
    pages, calls = world
    pages["https://blog.example/x"] = _html("no-recipe.html")
    item = client.post("/api/inbox/urls", json={"url": "https://blog.example/x"}, headers=admin_headers).json()
    got = _item(client, admin_headers, item["id"])
    assert got["status"] == "draft" and got["draft"]["title"] == "Mail-Risotto"
    assert got["draft"]["source_url"] == "https://blog.example/x"
    assert len(calls) == 1 and "Kein Rezept hier." in calls[0][0]["text"]
    assert db.query(models.AiCall).one().tokens == 99


def test_mail_with_link_to_recipe_page(client, admin_headers, world):
    pages, calls = world
    pages["https://www.swissmilk.ch/r"] = _html("swissmilk-like.html")
    item = _mail(client, admin_headers, text="Das hier! https://www.facebook.com/x https://www.swissmilk.ch/r")
    client.post(f"/api/inbox/{item}/process", headers=admin_headers)
    got = _item(client, admin_headers, item)
    assert got["draft"]["title"] == "Älplermagronen" and calls == []


def test_mail_screenshots_go_to_the_ai_in_one_call(client, admin_headers, world):
    _, calls = world
    item = _mail(client, admin_headers, text="Facebook-Rezept", images=[("1.png", png()), ("2.png", png()), ("3.png", png())])
    response = client.post(f"/api/inbox/{item}/process", headers=admin_headers)
    assert response.status_code == 202
    got = _item(client, admin_headers, item)
    assert got["status"] == "draft" and got["draft"]["image_attachment"] == 1
    assert len(calls) == 1 and [p["type"] for p in calls[0]] == ["text", "image_url", "image_url", "image_url"]
    assert json.loads(got["ai_raw"])["title"] == "Mail-Risotto"


def test_nothing_found(client, admin_headers, world, monkeypatch):
    item = _mail(client, admin_headers, text="   ")
    client.post(f"/api/inbox/{item}/process", headers=admin_headers)
    got = _item(client, admin_headers, item)
    assert got["status"] == "failed" and got["error"] == "nothing_found"


def test_ai_limit_reported(client, admin_headers, world, monkeypatch):
    monkeypatch.setenv("AI_CALLS_PER_HOUR", "0")
    item = _mail(client, admin_headers, text="Rezept: Reis kochen")
    client.post(f"/api/inbox/{item}/process", headers=admin_headers)
    assert _item(client, admin_headers, item)["error"] == "ai_off"


def test_busy_and_children(client, admin_headers, world, db, monkeypatch):
    monkeypatch.setattr(importer, "start", lambda item_id, user_id: None)
    item = _mail(client, admin_headers, text="x")
    assert client.post(f"/api/inbox/{item}/process", headers=admin_headers).status_code == 202
    busy = client.post(f"/api/inbox/{item}/process", headers=admin_headers)
    assert busy.status_code == 409 and busy.json()["detail"] == "item_busy"
    create_user(client, admin_headers, "Lena")
    assert client.post(f"/api/inbox/{item}/process", headers=login(client, "Lena", "5678")).status_code == 403


def test_stuck_item_reported_failed(client, admin_headers, world, db, monkeypatch):
    monkeypatch.setattr(importer, "start", lambda item_id, user_id: None)
    item = _mail(client, admin_headers, text="x")
    client.post(f"/api/inbox/{item}/process", headers=admin_headers)
    row = db.get(models.InboxItem, item)
    row.processing_since = utcnow() - timedelta(minutes=11)
    db.commit()
    got = _item(client, admin_headers, item)
    assert got["status"] == "failed" and got["error"] == "ai_failed"
    assert client.post(f"/api/inbox/{item}/process", headers=admin_headers).status_code == 202


def test_save_draft_as_recipe(client, admin_headers, world):
    item = _mail(client, admin_headers, text="Rezept", images=[("1.png", png()), ("2.png", png((1, 2, 3)))])
    client.post(f"/api/inbox/{item}/process", headers=admin_headers)
    draft = _item(client, admin_headers, item)["draft"]
    body = {k: draft[k] for k in ("title", "servings", "servings_unit", "ingredients", "steps", "tags")}
    saved = client.post("/api/recipes", json={**body, "inbox_item_id": item}, headers=admin_headers)
    assert saved.status_code == 201, saved.text
    recipe = saved.json()
    assert recipe["source_kind"] == "mail" and recipe["photo_url"] and recipe["inbox_item_id"] == item
    done = client.get(f"/api/inbox/{item}", headers=admin_headers).json()
    assert done["status"] == "done" and done["recipe_id"] == recipe["id"]
    assert client.get("/api/inbox", headers=admin_headers).json() == []
    again = client.post("/api/recipes", json={**body, "inbox_item_id": item}, headers=admin_headers)
    assert again.status_code == 400 and again.json()["detail"] == "draft_not_ready"


def test_mail_footer_link_does_not_block_the_screenshots(client, admin_headers, world):
    pages, calls = world
    pages["https://aka.ms/getoutlook"] = _html("no-recipe.html")
    item = _mail(client, admin_headers, text="Rezept\n\nGet Outlook https://aka.ms/getoutlook", images=[("1.png", png())])
    client.post(f"/api/inbox/{item}/process", headers=admin_headers)
    got = _item(client, admin_headers, item)
    assert got["status"] == "draft"
    # One call, with the picture, not about Outlook's page
    assert len(calls) == 1 and [p["type"] for p in calls[0]] == ["text", "image_url"]


def test_page_the_ai_cant_read_falls_back_to_the_mail(client, admin_headers, world, monkeypatch):
    pages, calls = world
    pages["https://blog.example/x"] = _html("no-recipe.html")
    answers = [json.dumps({"title": ""}), json.dumps(GOOD)]

    class Picky:
        def complete(self, content):
            calls.append(content)
            return ai.Answer(answers.pop(0), 10)

    monkeypatch.setattr(importer.ai, "client_for", lambda settings: Picky())
    item = _mail(client, admin_headers, text="Reis kochen, siehe https://blog.example/x")
    client.post(f"/api/inbox/{item}/process", headers=admin_headers)
    got = _item(client, admin_headers, item)
    assert got["status"] == "draft" and got["draft"]["title"] == "Mail-Risotto" and len(calls) == 2


def test_broken_link_skipped(client, admin_headers, world):
    pages, calls = world
    pages["https://www.swissmilk.ch/r"] = _html("swissmilk-like.html")
    item = _mail(client, admin_headers, text="http://a..b/ http://x.ch:abc/ http://[::1/ https://www.swissmilk.ch/r")
    client.post(f"/api/inbox/{item}/process", headers=admin_headers)
    assert _item(client, admin_headers, item)["draft"]["title"] == "Älplermagronen"


def test_unreadable_image_doesnt_shift_the_photo(client, admin_headers, world, monkeypatch):
    _, calls = world
    answer = {**GOOD, "image_index": 0}
    monkeypatch.setattr(importer.ai, "client_for", lambda settings: type("C", (), {"complete": lambda self, c: ai.Answer(json.dumps(answer), 1)})())
    item = _mail(client, admin_headers, text="x", images=[("broken.png", b"not a png"), ("food.png", png())])
    client.post(f"/api/inbox/{item}/process", headers=admin_headers)
    # Only food.png reached the AI, so its index 0 is attachment 1
    assert _item(client, admin_headers, item)["draft"]["image_attachment"] == 1


def test_at_most_ten_pictures_per_call(client, admin_headers, world):
    _, calls = world
    item = _mail(client, admin_headers, text="x", images=[(f"{n}.png", png()) for n in range(12)])
    client.post(f"/api/inbox/{item}/process", headers=admin_headers)
    assert len([p for p in calls[0] if p["type"] == "image_url"]) == 10
