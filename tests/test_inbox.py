from app import config
from helpers import create_user, login
from mails import build_mail


def _mail_for(client, monkeypatch, headers, address, user_id=None):
    monkeypatch.setenv("INBOUND_SECRET", "s")
    body = {"address": address, **({"user_id": user_id} if user_id else {})}
    client.post("/api/emails", json=body, headers=headers)
    response = client.post("/api/inbound", content=build_mail(from_addr=address), headers={"X-Inbound-Secret": "s"})
    return response.json()["id"]


def test_emails_parent_adds_for_child(client, admin_headers):
    lena = create_user(client, admin_headers, "Lena")
    added = client.post("/api/emails", json={"address": "lena@x.ch", "user_id": lena["id"]}, headers=admin_headers)
    assert added.status_code == 201 and added.json()["user_name"] == "Lena"
    taken = client.post("/api/emails", json={"address": "LENA@x.ch"}, headers=admin_headers)
    assert taken.status_code == 409 and taken.json()["detail"] == "email_taken"
    invalid = client.post("/api/emails", json={"address": "nope"}, headers=admin_headers)
    assert invalid.status_code == 422 and "invalid_email" in invalid.text


def test_emails_child_only_own(client, admin_headers):
    create_user(client, admin_headers, "Lena")
    kid = login(client, "Lena", "5678")
    own = client.post("/api/emails", json={"address": "lena@x.ch"}, headers=kid)
    assert own.status_code == 201
    admin_id = client.get("/api/me", headers=admin_headers).json()["id"]
    other = client.post("/api/emails", json={"address": "a@x.ch", "user_id": admin_id}, headers=kid)
    assert other.status_code == 403
    assert [e["address"] for e in client.get("/api/emails", headers=kid).json()] == ["lena@x.ch"]
    client.post("/api/emails", json={"address": "papa@x.ch"}, headers=admin_headers)
    assert len(client.get("/api/emails?all=1", headers=admin_headers).json()) == 2
    assert client.delete(f"/api/emails/{own.json()['id']}", headers=kid).status_code == 204


def test_child_sees_own_items_only_and_cannot_discard(client, admin_headers, monkeypatch):
    lena = create_user(client, admin_headers, "Lena")
    kid = login(client, "Lena", "5678")
    mine = _mail_for(client, monkeypatch, admin_headers, "lena@x.ch", lena["id"])
    _mail_for(client, monkeypatch, admin_headers, "papa@x.ch")
    assert [i["id"] for i in client.get("/api/inbox", headers=kid).json()] == [mine]
    assert len(client.get("/api/inbox", headers=admin_headers).json()) == 2
    assert client.get("/api/inbox/count", headers=kid).json() == {"waiting": 1}
    assert client.get("/api/inbox/count", headers=admin_headers).json() == {"waiting": 2}
    denied = client.delete(f"/api/inbox/{mine}", headers=kid)
    assert denied.status_code == 403


def test_discard_removes_file(client, admin_headers, monkeypatch):
    item = _mail_for(client, monkeypatch, admin_headers, "papa@x.ch")
    assert client.delete(f"/api/inbox/{item}", headers=admin_headers).status_code == 204
    assert not (config.data_dir() / "inbox" / f"{item}.eml").exists()
    assert client.get("/api/inbox", headers=admin_headers).json() == []
    missing = client.delete(f"/api/inbox/{item}", headers=admin_headers)
    assert missing.status_code == 404 and missing.json()["detail"] == "item_not_found"
