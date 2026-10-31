"""From outside (through the Cloudflare tunnel) the Cloudflare Access login counts, passed on to the family hub
(2026-10-30). Invented people."""

import fake_hub
from app import hub
from helpers import ADMIN, bearer

OUTSIDE = {"Cf-Connecting-Ip": "203.0.113.7"}


def outside(name=ADMIN, **extra):
    return {**OUTSIDE, "Cf-Access-Jwt-Assertion": fake_hub.cloudflare_token(name), **extra}


def test_cloudflare_login_from_outside(client):
    found = client.get("/api/me", headers=outside())
    assert found.status_code == 200 and found.json()["name"] == ADMIN


def test_a_hub_login_counts_for_nothing_outside(client):
    # A hub token or cookie arriving through the tunnel can only be a stolen home login
    assert client.get("/api/me", headers={**OUTSIDE, **bearer(fake_hub.token(ADMIN))}).status_code == 401
    client.cookies.set("hub_session", fake_hub.token(ADMIN))
    assert client.get("/api/me", headers=OUTSIDE).status_code == 401


def test_changes_from_outside_need_the_header(client):
    body = {"title": "Rösti", "servings": 2, "ingredients": [], "steps": [], "tags": []}
    refused = client.post("/api/recipes", json=body, headers=outside())
    assert refused.status_code == 403 and refused.json()["detail"] == "csrf"
    assert client.post("/api/recipes", json=body, headers=outside(**{"X-Requested-With": "meals"})).status_code == 201


def test_unknown_to_the_hub_from_outside(client):
    # Cloudflare let the address in, but the hub knows no one with it (not confirmed there)
    response = client.get("/api/me", headers=outside("Nobody"))
    assert response.status_code == 403 and response.json()["detail"] == "no_access"


def test_logout_from_outside_is_cloudflares(client, monkeypatch):
    monkeypatch.setenv("HUB_PUBLIC_URL", "https://home.local.example.ch")
    assert client.get("/api/hub", headers=OUTSIDE).json()["logout_url"] == "/cdn-cgi/access/logout"
    assert client.get("/api/hub").json()["logout_url"] == "https://home.local.example.ch/logout"


def test_outside_without_cloudflares_login(client):
    assert client.get("/api/me", headers=OUTSIDE).status_code == 401


def test_a_hub_cookie_beside_cloudflares_login_counts_for_nothing(client, family_hub):
    family_hub.add("Mia", "CHILD")
    client.cookies.set("hub_session", fake_hub.token("Mia"))
    assert client.get("/api/me", headers=outside()).json()["name"] == ADMIN
    assert client.get("/api/me", headers=outside(**bearer(fake_hub.token("Mia")))).json()["name"] == ADMIN


def test_a_cloudflare_token_at_home_is_no_login(client):
    # Which login a request carries depends on where it came from, never on the token's text (security review
    # 2026-10-31): at home Cloudflare's token goes to the hub as a hub login, which it is not
    for text in (fake_hub.cloudflare_token(ADMIN), "cf:" + fake_hub.cloudflare_token(ADMIN)):
        assert client.get("/api/me", headers=bearer(text)).status_code == 401
        client.cookies.set("hub_session", text)
        assert client.get("/api/me").status_code == 401
        client.cookies.clear()


def test_the_family_list_from_outside_asks_the_hub_with_cloudflares_login(client, family_hub, monkeypatch):
    family_hub.add("Mia", "CHILD")
    asked = []
    monkeypatch.setattr(hub, "fetch_people", lambda login: asked.append(login) or family_hub.fetch_people(login))
    found = client.get("/api/users", headers=outside(**bearer(fake_hub.token("Mia"))))
    assert found.status_code == 200 and "Mia" in [u["name"] for u in found.json()]
    assert asked and all(a.token == fake_hub.cloudflare_token(ADMIN) and a.outside_ip for a in asked)


def test_someone_unknown_outside_gets_in_once_the_hub_knows_them(client, family_hub):
    # A "not logged in" from outside may be a hub without Cloudflare's keys or a just-confirmed address: not kept
    assert client.get("/api/me", headers=outside("Mia")).status_code == 403
    family_hub.people["Mia"] = hub.HubPerson(id=99, name="Mia", role="CHILD", color=None, language="de")
    family_hub.access.add("Mia")
    assert client.get("/api/me", headers=outside("Mia")).status_code == 200


def test_changes_from_outside_need_the_header_for_uploads_and_deletes_too(client):
    made = client.post(
        "/api/recipes",
        json={"title": "Rösti", "servings": 2, "ingredients": [], "steps": [], "tags": []},
        headers=outside(**{"X-Requested-With": "meals"}),
    ).json()
    upload = client.post(f"/api/recipes/{made['id']}/photo", files={"file": ("a.jpg", b"x", "image/jpeg")}, headers=outside())
    assert upload.status_code == 403 and upload.json()["detail"] == "csrf"
    deleted = client.delete(f"/api/recipes/{made['id']}", headers=outside())
    assert deleted.status_code == 403 and deleted.json()["detail"] == "csrf"


def test_the_hub_gets_the_login_with_the_right_headers(monkeypatch):
    sent = []

    class Answer:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return b'{"valid": false}'

    monkeypatch.setattr(hub.urllib.request, "urlopen", lambda request, timeout: sent.append(request) or Answer())
    hub._get("/api/session", hub.Login("cloudflares-token", outside_ip="203.0.113.7"))
    hub._get("/api/session", hub.Login("hub-token"))
    outside_call, home_call = (dict(r.header_items()) for r in sent)
    # From outside the hub also gets Cf-Connecting-Ip, so it ignores any hub token as well (family-hub "For apps")
    assert outside_call == {"Cf-access-jwt-assertion": "cloudflares-token", "Cf-connecting-ip": "203.0.113.7"}
    assert home_call == {"Authorization": "Bearer hub-token"}
