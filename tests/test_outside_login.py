"""From outside (through the Cloudflare tunnel) the Cloudflare Access login counts, passed on to the family hub
(2026-10-30). Invented people."""

import fake_hub
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
