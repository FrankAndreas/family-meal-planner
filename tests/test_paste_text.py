"""A recipe's text pasted in (a Facebook post's caption), with the link it came from: the AI reads the text, the
link is only kept as the source."""

import pytest

from app import importer
from helpers import create_user, login

CAPTION = """Craving fudgy brownies without the guilt?
🥣 Ingredients:
• 3 ripe bananas (peeled)
• 1/4 cup natural peanut butter
• 3 tbsp cocoa powder
⏰ Bake: 180°C (350°F) for 18–20 mins.
See https://example.com/other-recipe for more"""
REEL = "https://www.facebook.com/reel/2350975632311568"


@pytest.fixture
def started(monkeypatch):
    begun = []
    monkeypatch.setattr(importer, "start", lambda item_id, user_id: begun.append(item_id))
    return begun


def test_parent_text_is_read_at_once(client, admin_headers, started):
    response = client.post("/api/inbox/texts", json={"text": CAPTION, "url": REEL}, headers=admin_headers)
    assert response.status_code == 201, response.text
    item = response.json()
    assert item["kind"] == "text" and item["status"] == "processing" and item["user_name"] == "Admin"
    assert item["subject"] == "Craving fudgy brownies without the guilt?" and item["url"] == REEL
    assert item["attachments"] == [] and started == [item["id"]]
    detail = client.get(f"/api/inbox/{item['id']}", headers=admin_headers).json()
    assert detail["text"] == CAPTION


def test_child_text_waits_for_a_parent(client, admin_headers, started):
    create_user(client, admin_headers, "Lena")
    child = login(client, "Lena", "5678")
    item = client.post("/api/inbox/texts", json={"text": "  Brownies\n3 Bananen  ", "url": ""}, headers=child).json()
    assert item["status"] == "waiting" and item["url"] is None and started == []
    assert item["subject"] == "Brownies"


@pytest.mark.parametrize(
    "body",
    [{"text": "   "}, {"text": "x" * 20_001}, {"text": "Brownies", "url": "javascript:alert(1)"}, {}],
)
def test_text_is_checked(client, admin_headers, started, body):
    assert client.post("/api/inbox/texts", json=body, headers=admin_headers).status_code == 422
    assert started == []


def test_text_needs_login(client, started):
    assert client.post("/api/inbox/texts", json={"text": "Brownies"}).status_code == 401


def test_subject_is_the_first_line_as_written(client, admin_headers, started):
    long = "🍫 " + "Brownies " * 30
    item = client.post("/api/inbox/texts", json={"text": f"\n\n{long}\nmore"}, headers=admin_headers).json()
    assert item["subject"] == long.strip()[:120]
    tricky = client.post("/api/inbox/texts", json={"text": "=?utf-8?q?Hacked?= real"}, headers=admin_headers).json()
    assert tricky["subject"] == "=?utf-8?q?Hacked?= real"


def test_blank_link_is_no_link(client, admin_headers, started):
    item = client.post("/api/inbox/texts", json={"text": "Brownies", "url": "   "}, headers=admin_headers).json()
    assert item["url"] is None


def test_item_still_opens_without_its_file(client, admin_headers, started):
    from app import inbox_files, models

    item = client.post("/api/inbox/texts", json={"text": "Brownies"}, headers=admin_headers).json()
    inbox_files.raw_path(models.InboxItem(id=item["id"])).unlink()
    response = client.get(f"/api/inbox/{item['id']}", headers=admin_headers)
    assert response.status_code == 200 and response.json()["text"] is None
