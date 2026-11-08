import pytest

from app import config, inbox_api
from helpers import ADMIN, confirm_email, create_user, login, remove_from_hub
from mails import build_mail, png

SECRET = "test-inbound-secret"


@pytest.fixture
def inbound(monkeypatch, client):
    monkeypatch.setenv("INBOUND_SECRET", SECRET)

    def post(raw, secret=SECRET):
        return client.post("/api/inbound", content=raw, headers={"X-Inbound-Secret": secret, "Content-Type": "message/rfc822"})

    return post


def _register(client, headers, address="Papa@Example.ch", name=ADMIN):
    """The address the person confirmed in the family hub (the only addresses recipe mails come from)."""
    confirm_email(client, name, address)


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
    create_user(client, admin_headers, "Lena")
    _register(client, admin_headers, "lena@example.ch", name="Lena")
    inbound(build_mail(from_addr="lena@example.ch"))
    assert client.get("/api/inbox", headers=admin_headers).json()[0]["user_name"] == "Lena"


def test_an_address_the_hub_does_not_share_is_refused(inbound, admin_headers, client):
    """Confirmed in the hub, but the planner's tile doesn't share the addresses: the planner knows none."""
    import fake_hub

    _register(client, admin_headers)
    fake_hub.current.share_email = False
    from app import hub, hub_people

    hub.client.forget()
    hub_people.forget()
    login(client)
    response = inbound(build_mail())
    assert response.status_code == 403 and response.json()["detail"] == "inbound_sender_unknown"


def test_an_address_two_people_have_is_refused(inbound, admin_headers, client):
    """Whose would it be? Neither: the hub should know each address once."""
    create_user(client, admin_headers, "Lena")
    _register(client, admin_headers, "family@example.ch")
    _register(client, admin_headers, "family@example.ch", name="Lena")
    response = inbound(build_mail(from_addr="family@example.ch"))
    assert response.status_code == 403 and response.json()["detail"] == "inbound_sender_unknown"


def test_a_person_the_hub_no_longer_lists_sends_nothing(inbound, admin_headers, client):
    create_user(client, admin_headers, "Lena")
    _register(client, admin_headers, "lena@example.ch", name="Lena")
    remove_from_hub("Lena")
    from app import hub, hub_people

    hub.client.forget()
    hub_people.forget()
    login(client)
    response = inbound(build_mail(from_addr="lena@example.ch"))
    assert response.status_code == 403


def test_the_person_and_the_family_see_the_hubs_address(admin_headers, client):
    lena = create_user(client, admin_headers, "Lena")
    _register(client, admin_headers, "Lena@Example.ch", name="Lena")
    assert client.get("/api/me", headers=login(client, "Lena")).json()["email"] == "lena@example.ch"
    people = {u["name"]: u["email"] for u in client.get("/api/users", headers=admin_headers).json()}
    assert people == {"Admin": None, "Lena": "lena@example.ch"} and lena["id"]


def test_addresses_are_no_longer_typed_in(client, admin_headers):
    assert client.post("/api/emails", json={"address": "x@example.ch"}, headers=admin_headers).status_code in (404, 405)


def test_a_person_the_hub_no_longer_lists_keeps_no_address(admin_headers, client):
    """Hidden with their data, but their address isn't the hub's to share any more."""
    create_user(client, admin_headers, "Lena")
    _register(client, admin_headers, "lena@example.ch", name="Lena")
    remove_from_hub("Lena")
    from app import hub, hub_people

    hub.client.forget()
    hub_people.forget()
    login(client)
    removed = client.get("/api/users/removed", headers=admin_headers).json()
    assert [(u["name"], u["email"]) for u in removed] == [("Lena", None)]
