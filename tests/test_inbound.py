import pytest

from app import config, inbox_api
from helpers import create_user
from mails import build_mail, png

SECRET = "test-inbound-secret"


@pytest.fixture
def inbound(monkeypatch, client):
    monkeypatch.setenv("INBOUND_SECRET", SECRET)

    def post(raw, secret=SECRET):
        return client.post("/api/inbound", content=raw, headers={"X-Inbound-Secret": secret, "Content-Type": "message/rfc822"})

    return post


def _register(client, headers, address="Papa@Example.ch", user_id=None):
    body = {"address": address, **({"user_id": user_id} if user_id else {})}
    response = client.post("/api/emails", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_off_without_secret(client):
    response = client.post("/api/inbound", content=build_mail(), headers={"X-Inbound-Secret": "x"})
    assert response.status_code == 503 and response.json()["detail"] == "inbound_off"


def test_wrong_secret(inbound):
    response = inbound(build_mail(), secret="nope")
    assert response.status_code == 401 and response.json()["detail"] == "inbound_wrong_secret"


def test_unknown_sender_refused_and_nothing_stored(inbound, admin_headers, client):
    response = inbound(build_mail(from_addr="stranger@example.com"))
    assert response.status_code == 403 and response.json()["detail"] == "inbound_sender_unknown"
    assert client.get("/api/inbox", headers=admin_headers).json() == []
    assert not (config.data_dir() / "inbox").exists() or not list((config.data_dir() / "inbox").iterdir())


def test_registered_sender_stored(inbound, admin_headers, client):
    _register(client, admin_headers)
    response = inbound(build_mail(images=[("a.png", png())]))
    assert response.status_code == 200 and response.json()["status"] == "stored"
    item_id = response.json()["id"]
    assert (config.data_dir() / "inbox" / f"{item_id}.eml").is_file()
    item = client.get("/api/inbox", headers=admin_headers).json()[0]
    assert item["kind"] == "mail" and item["status"] == "waiting" and item["user_name"] == "Admin"
    assert item["subject"] == "Rezept" and item["attachments"][0]["name"] == "a.png"


def test_duplicate_message_id(inbound, admin_headers, client):
    _register(client, admin_headers)
    raw = build_mail(message_id="<same@x>")
    assert inbound(raw).json()["status"] == "stored"
    assert inbound(raw).json()["status"] == "duplicate"
    assert len(client.get("/api/inbox", headers=admin_headers).json()) == 1


def test_too_big(inbound, admin_headers, client, monkeypatch):
    _register(client, admin_headers)
    monkeypatch.setattr(inbox_api, "MAX_BYTES", 100)
    response = inbound(build_mail())
    assert response.status_code == 413 and response.json()["detail"] == "inbound_too_big"


def test_mail_of_a_child_belongs_to_the_child(inbound, admin_headers, client):
    lena = create_user(client, admin_headers, "Lena")
    _register(client, admin_headers, "lena@example.ch", user_id=lena["id"])
    inbound(build_mail(from_addr="lena@example.ch"))
    assert client.get("/api/inbox", headers=admin_headers).json()[0]["user_name"] == "Lena"
