"""Logging in through the family hub, and the people the hub gives the planner (spec 2026-10-30). Invented people."""

import fake_hub
import pytest
from helpers import ADMIN, bearer, create_recipe, create_user, login, remove_from_hub
from mails import build_mail
from test_inbound import SECRET

from app import database, models


def me(client, headers=None, **kwargs):
    return client.get("/api/me", headers=headers, **kwargs)


def user_row(name):
    with database.SessionLocal() as db:
        return db.query(models.User).filter(models.User.name == name).one()


# Logging in


def test_no_login_401(client):
    response = me(client)
    assert response.status_code == 401 and response.json()["detail"] == "not_logged_in"


def test_unknown_token_401(client):
    assert me(client, bearer("tok-nobody")).status_code == 401


def test_cookie_login_needs_the_header_for_changes(client):
    client.cookies.set("hub_session", fake_hub.token(ADMIN))
    assert me(client).json()["name"] == ADMIN
    body = {"title": "Rösti", "servings": 2, "ingredients": [], "steps": [], "tags": []}
    # Another site could make the browser send the cookie, but not this header
    refused = client.post("/api/recipes", json=body)
    assert refused.status_code == 403 and refused.json()["detail"] == "csrf"
    assert client.post("/api/recipes", json=body, headers={"X-Requested-With": "meals"}).status_code == 201


def test_no_access_403(client, family_hub):
    family_hub.add("Max", "PARENT", access=False)
    response = me(client, bearer(fake_hub.token("Max")))
    assert response.status_code == 403 and response.json()["detail"] == "no_access"


def test_hub_down_503(client, family_hub):
    headers = login(client)
    family_hub.down = True
    from app import hub

    hub.forget()
    response = me(client, headers)
    assert response.status_code == 503 and response.json()["detail"] == "hub_unavailable"


def test_no_login_through_the_tunnel(client):
    # Home only: Cloudflare sets this on everything through its tunnel (only the recipe mails come that way)
    response = me(client, {**bearer(fake_hub.token(ADMIN)), "Cf-Connecting-Ip": "203.0.113.7"})
    assert response.status_code == 401


def test_hub_login_url(client, monkeypatch):
    monkeypatch.setenv("HUB_PUBLIC_URL", "https://home.local.example.ch")
    assert client.get("/api/hub").json() == {"login_url": "https://home.local.example.ch"}


def test_removed_endpoints(client):
    headers = login(client)
    assert client.post("/api/token", json={"name": ADMIN, "pin": "1234"}).status_code in (404, 405)
    assert client.post("/api/users", json={"name": "X", "pin": "1234"}, headers=headers).status_code in (404, 405)
    assert client.post("/api/me/pin", json={"current_pin": "1", "new_pin": "2"}, headers=headers).status_code in (
        404,
        405,
    )
    assert client.patch("/api/me", json={"language": "en"}, headers=headers).status_code in (404, 405)
    assert client.get("/api/users/public").status_code in (404, 405)
    admin_id = me(client, headers).json()["id"]
    assert client.patch(f"/api/users/{admin_id}", json={"name": "Boss"}, headers=headers).status_code in (404, 405)
    assert client.post(f"/api/users/{admin_id}/pin", json={"pin": "9999"}, headers=headers).status_code in (404, 405)


# The people from the hub


def test_existing_row_linked_at_the_switch(client, family_hub):
    before = user_row(ADMIN)
    assert before.hub_id is None
    headers = login(client)
    recipe = create_recipe(client, headers)
    client.put(f"/api/recipes/{recipe['id']}/rating", json={"stars": 4}, headers=headers)
    after = user_row(ADMIN)
    assert (after.id, after.hub_id) == (before.id, family_hub.people[ADMIN].id)


def test_old_rows_linked_by_name_only_at_the_switch(client, family_hub):
    with database.SessionLocal() as db:
        db.add(models.User(name="Beat", name_key="beat", role=models.UserRole.PARENT))
        db.commit()
    login(client)
    # Later, someone new with that name is a new person, not the old row and its stars
    family_hub.add("Beat", "PARENT")
    login(client, "Beat")
    rows = [r for r in database.SessionLocal().query(models.User).all() if r.hub_id == family_hub.people["Beat"].id]
    assert len(rows) == 1 and rows[0].name == "Beat"
    with database.SessionLocal() as db:
        old = db.query(models.User).filter(models.User.hub_id.is_(None)).one()
        assert old.is_active is False


def test_name_link_needs_the_same_role(client, family_hub):
    with database.SessionLocal() as db:
        db.add(models.User(name="Kid", name_key="kid", role=models.UserRole.CHILD))
        db.commit()
    family_hub.add("Kid", "PARENT")
    login(client)
    with database.SessionLocal() as db:
        old = db.query(models.User).filter(models.User.name_key.like("kid%"), models.User.hub_id.is_(None)).one()
        assert old.role == models.UserRole.CHILD


def test_new_person_name_role_language_from_the_hub(client, family_hub):
    family_hub.add("Lena", "CHILD", language="en")
    found = me(client, login(client, "Lena")).json()
    assert (found["name"], found["role"], found["language"]) == ("Lena", "CHILD", "en")


def test_rename_and_role_follow_the_hub(client, family_hub):
    lena = create_user(client, None, "Lena")
    family_hub.rename("Lena", "Lea")
    family_hub.set_role("Lea", "PARENT")
    found = me(client, login(client, "Lea")).json()
    assert (found["id"], found["name"], found["role"]) == (lena["id"], "Lea", "PARENT")


def test_demoted_parent_loses_rights_at_once(client, family_hub):
    create_user(client, None, "Mia", role="PARENT")
    headers = login(client, "Mia")
    assert client.get("/api/users", headers=headers).status_code == 200
    family_hub.set_role("Mia", "CHILD")
    assert client.get("/api/users", headers=headers).status_code == 403


def test_children_dont_list_people(client):
    create_user(client, None, "Lena")
    assert client.get("/api/users", headers=login(client, "Lena")).status_code == 403


# Removed in the hub: hidden with their data, until a parent deletes it


def test_removed_person_hidden_and_back(client, family_hub):
    create_user(client, None, "Lena")
    admin = login(client)
    remove_from_hub("Lena")
    assert "Lena" not in [u["name"] for u in client.get("/api/users", headers=admin).json()]
    assert [u["name"] for u in client.get("/api/users/removed", headers=admin).json()] == ["Lena"]
    family_hub.give_access("Lena")
    assert "Lena" in [u["name"] for u in client.get("/api/users", headers=admin).json()]


def test_stars_of_a_removed_person_keep_counting(client):
    admin = login(client)
    recipe = create_recipe(client, admin)
    create_user(client, None, "Lena")
    client.put(f"/api/recipes/{recipe['id']}/rating", json={"stars": 2}, headers=admin)
    client.put(f"/api/recipes/{recipe['id']}/rating", json={"stars": 4}, headers=login(client, "Lena"))
    remove_from_hub("Lena")
    client.get("/api/users", headers=admin)
    assert client.get(f"/api/recipes/{recipe['id']}", headers=admin).json()["rating_avg"] == 3.0


def test_only_removed_people_are_deleted(client):
    admin = login(client)
    lena = create_user(client, None, "Lena")
    refused = client.delete(f"/api/users/{lena['id']}", headers=admin)
    assert refused.status_code == 409 and refused.json()["detail"] == "still_in_hub"
    remove_from_hub("Lena")
    client.get("/api/users", headers=admin)
    assert client.delete(f"/api/users/{lena['id']}", headers=admin).status_code == 204
    assert client.get("/api/users/removed", headers=admin).json() == []


@pytest.fixture
def inbound(monkeypatch, client):
    monkeypatch.setenv("INBOUND_SECRET", SECRET)
    return lambda raw: client.post(
        "/api/inbound", content=raw, headers={"X-Inbound-Secret": SECRET, "Content-Type": "message/rfc822"}
    )


def test_mail_from_a_removed_persons_address_refused(client, inbound):
    admin = login(client)
    lena = create_user(client, None, "Lena")
    client.post("/api/emails", json={"address": "lena@example.ch", "user_id": lena["id"]}, headers=admin)
    remove_from_hub("Lena")
    client.get("/api/users", headers=admin)
    response = inbound(build_mail(from_addr="lena@example.ch"))
    assert response.status_code == 403 and response.json()["detail"] == "inbound_sender_unknown"


def test_default_language_for_the_no_access_page(client, monkeypatch):
    monkeypatch.setenv("DEFAULT_LANGUAGE", "en")
    assert client.get("/api/config").json()["default_language"] == "en"


def test_the_people_list_asks_the_hub_now(client, family_hub):
    # A parent opening the family list sees the hub's current state, not the one of up to a minute ago
    admin = login(client)
    create_user(client, None, "Lena")
    family_hub.access.discard("Lena")  # changed in the hub, without the app hearing about it
    assert "Lena" not in [u["name"] for u in client.get("/api/users", headers=admin).json()]
    assert [u["name"] for u in client.get("/api/users/removed", headers=admin).json()] == ["Lena"]
