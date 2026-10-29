"""Recipes photographed in the app (the back of a pack, a cookbook page): into the inbox like a mail."""

import pytest

from app import importer
from helpers import create_user, login
from mails import png


@pytest.fixture
def started(monkeypatch):
    begun = []
    monkeypatch.setattr(importer, "start", lambda item_id, user_id: begun.append(item_id))
    return begun


def _scan(client, headers, *images):
    files = [("files", (name, data, kind)) for name, data, kind in images]
    return client.post("/api/inbox/scans", files=files, headers=headers)


def _png(name="1.png", size=(1200, 800)):
    return (name, png(size=size), "image/png")


def test_parent_scan_is_read_at_once(client, admin_headers, started):
    response = _scan(client, admin_headers, _png("1.png"), _png("2.png"))
    assert response.status_code == 201, response.text
    item = response.json()
    assert item["kind"] == "scan" and item["status"] == "processing" and item["user_name"] == "Admin"
    assert [a["type"] for a in item["attachments"]] == ["image/png", "image/png"]
    assert started == [item["id"]]
    thumb = client.get(f"/api/inbox/{item['id']}/attachments/1/thumb", headers=admin_headers)
    assert thumb.status_code == 200


def test_child_scan_waits_for_a_parent(client, admin_headers, started):
    create_user(client, admin_headers, "Lena")
    child = login(client, "Lena", "5678")
    item = _scan(client, child, _png()).json()
    assert item["status"] == "waiting" and started == []
    assert [i["id"] for i in client.get("/api/inbox", headers=child).json()] == [item["id"]]


def test_scan_takes_pictures_only(client, admin_headers, started):
    for bad in [("r.pdf", b"%PDF-1", "application/pdf"), ("x.svg", b"<svg/>", "image/svg+xml")]:
        response = _scan(client, admin_headers, _png(), bad)
        assert response.status_code == 400 and response.json()["detail"] == "scan_not_image"
    assert client.get("/api/inbox", headers=admin_headers).json() == []


def test_scan_needs_one_to_ten_pictures(client, admin_headers, started):
    assert _scan(client, admin_headers).status_code == 422
    response = _scan(client, admin_headers, *[_png(f"{n}.png", (20, 20)) for n in range(11)])
    assert response.status_code == 400 and response.json()["detail"] == "scan_too_many"


def test_scan_too_large(client, admin_headers, started, monkeypatch):
    from app import inbox_api

    monkeypatch.setattr(inbox_api, "MAX_BYTES", 1000)
    response = _scan(client, admin_headers, _png())
    assert response.status_code == 413 and response.json()["detail"] == "scan_too_big"


def test_scan_needs_login(client, started):
    assert _scan(client, {}, _png()).status_code == 401
