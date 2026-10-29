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


def test_child_pasted_link_waits(client, admin_headers, monkeypatch):
    from app import importer

    started = []
    monkeypatch.setattr(importer, "start", lambda item_id, user_id: started.append(item_id))
    create_user(client, admin_headers, "Lena")
    kid = login(client, "Lena", "5678")
    response = client.post("/api/inbox/urls", json={"url": "https://www.swissmilk.ch/de/rezepte/x/"}, headers=kid)
    assert response.status_code == 201
    item = response.json()
    assert item["kind"] == "url" and item["status"] == "waiting" and item["subject"] == "www.swissmilk.ch"
    assert started == []


def test_parent_pasted_link_starts_at_once(client, admin_headers, monkeypatch):
    from app import importer

    started = []
    monkeypatch.setattr(importer, "start", lambda item_id, user_id: started.append(item_id))
    item = client.post("/api/inbox/urls", json={"url": "https://fooby.ch/r/1"}, headers=admin_headers).json()
    assert item["status"] == "processing" and started == [item["id"]]


def test_only_web_links(client, admin_headers):
    response = client.post("/api/inbox/urls", json={"url": "javascript:alert(1)"}, headers=admin_headers)
    assert response.status_code == 422 and "not_a_web_link" in response.text


def _image_mail(client, monkeypatch, headers, address="papa@x.ch", user_id=None):
    from mails import build_mail, png

    monkeypatch.setenv("INBOUND_SECRET", "s")
    body = {"address": address, **({"user_id": user_id} if user_id else {})}
    client.post("/api/emails", json=body, headers=headers)
    raw = build_mail(from_addr=address, images=[("a.png", png(size=(1200, 800)))], attachments=[("r.pdf", b"%PDF-1", "application/pdf")])
    return client.post("/api/inbound", content=raw, headers={"X-Inbound-Secret": "s"}).json()["id"]


def test_attachment_and_thumbnail(client, admin_headers, monkeypatch):
    import io

    from PIL import Image

    item = _image_mail(client, monkeypatch, admin_headers)
    full = client.get(f"/api/inbox/{item}/attachments/0", headers=admin_headers)
    assert full.status_code == 200 and full.headers["content-type"] == "image/png"
    thumb = client.get(f"/api/inbox/{item}/attachments/0/thumb", headers=admin_headers)
    image = Image.open(io.BytesIO(thumb.content))
    assert image.format == "JPEG" and max(image.size) <= 320
    pdf = client.get(f"/api/inbox/{item}/attachments/1", headers=admin_headers)
    assert pdf.status_code == 404 and pdf.json()["detail"] == "attachment_not_found"


def test_other_childs_attachment_hidden(client, admin_headers, monkeypatch):
    item = _image_mail(client, monkeypatch, admin_headers)
    create_user(client, admin_headers, "Lena")
    kid = login(client, "Lena", "5678")
    assert client.get(f"/api/inbox/{item}/attachments/0/thumb", headers=kid).status_code == 404


def test_raw_mail_for_parents(client, admin_headers, monkeypatch):
    item = _image_mail(client, monkeypatch, admin_headers)
    raw = client.get(f"/api/inbox/{item}/raw", headers=admin_headers)
    assert raw.status_code == 200 and raw.headers["content-type"].startswith("message/rfc822")
    assert b"Subject: Rezept" in raw.content


def test_parent_link_records_when_processing_began(client, admin_headers, monkeypatch, db):
    from app import importer, models

    monkeypatch.setattr(importer, "start", lambda item_id, user_id: None)
    item = client.post("/api/inbox/urls", json={"url": "https://fooby.ch/r/2"}, headers=admin_headers).json()
    assert db.get(models.InboxItem, item["id"]).processing_since is not None


def test_malformed_pasted_link(client, admin_headers):
    response = client.post("/api/inbox/urls", json={"url": "http://[x"}, headers=admin_headers)
    assert response.status_code == 422 and "not_a_web_link" in response.text


def test_svg_attachment_not_served(client, admin_headers, monkeypatch):
    from mails import build_mail

    monkeypatch.setenv("INBOUND_SECRET", "s")
    client.post("/api/emails", json={"address": "papa@x.ch"}, headers=admin_headers)
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    raw = build_mail(from_addr="papa@x.ch", attachments=[("x.svg", svg, "image/svg+xml")])
    item = client.post("/api/inbound", content=raw, headers={"X-Inbound-Secret": "s"}).json()["id"]
    assert client.get(f"/api/inbox/{item}/attachments/0", headers=admin_headers).status_code == 404
