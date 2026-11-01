from helpers import create_user, login

STAPLES = ["Salz", "Pfeffer", "Öl", "Wasser", "Zucker", "Mehl", "Bouillon"]


def test_defaults(client):
    assert client.get("/api/settings", headers=login(client)).json() == {
        "family_size": 4,
        "week_start": 5,
        "staples": STAPLES,
    }


def test_parent_changes_settings(client):
    headers = login(client)
    assert client.patch("/api/settings", json={"week_start": 0}, headers=headers).json() == {
        "family_size": 4,
        "week_start": 0,
        "staples": STAPLES,
    }
    assert client.get("/api/settings", headers=headers).json()["week_start"] == 0


def test_child_reads_but_cannot_change(client):
    create_user(client, login(client), "Lena")
    kid = login(client, "Lena", "5678")
    assert client.get("/api/settings", headers=kid).status_code == 200
    r = client.patch("/api/settings", json={"family_size": 2}, headers=kid)
    assert r.status_code == 403 and r.json()["detail"] == "parents_only"
    r = client.patch("/api/settings", json={"staples": []}, headers=kid)
    assert r.status_code == 403 and r.json()["detail"] == "parents_only"


def test_needs_login(client):
    assert client.get("/api/settings").status_code == 401


def test_ranges(client):
    headers = login(client)
    for body in ({"family_size": 0}, {"family_size": 21}, {"week_start": 7}, {"week_start": -1}):
        assert client.patch("/api/settings", json=body, headers=headers).status_code == 422, body


def test_parent_edits_staples(client):
    headers = login(client)
    empty = client.patch("/api/settings", json={"staples": [" Butter ", "salz", "Salz", ""]}, headers=headers)
    assert empty.status_code == 422
    r = client.patch("/api/settings", json={"staples": [" Butter ", "salz", "Salz"]}, headers=headers)
    assert r.json()["staples"] == ["Butter", "salz"]
    assert client.get("/api/settings", headers=headers).json()["staples"] == ["Butter", "salz"]
