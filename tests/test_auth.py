from helpers import ADMIN, ADMIN_PIN, create_user, login


def test_login_and_me(client):
    me = client.get("/api/me", headers=login(client)).json()
    assert me["name"] == ADMIN and me["role"] == "PARENT"
    assert me["language"] == "de" and me["language_chosen"] is False


def test_login_is_case_insensitive(client):
    assert client.post("/api/token", json={"name": " admin ", "pin": ADMIN_PIN}).status_code == 200


def test_wrong_pin(client):
    r = client.post("/api/token", json={"name": ADMIN, "pin": "0000"})
    assert r.status_code == 401 and r.json()["detail"] == "wrong_name_or_pin"


def test_unknown_name(client):
    r = client.post("/api/token", json={"name": "Nobody", "pin": "0000"})
    assert r.status_code == 401 and r.json()["detail"] == "wrong_name_or_pin"


def test_lock_after_five_wrong_pins(client):
    for _ in range(5):
        client.post("/api/token", json={"name": ADMIN, "pin": "0000"})
    r = client.post("/api/token", json={"name": ADMIN, "pin": ADMIN_PIN})
    assert r.status_code == 429 and r.json()["detail"] == {"code": "locked", "minutes": 15}


def test_pin_must_be_four_digits(client):
    headers = login(client)
    for pin in ("12a4", "123", "12345"):
        r = client.post("/api/users", json={"name": "Lena", "pin": pin, "role": "CHILD"}, headers=headers)
        assert r.status_code == 422, pin


def test_no_token(client):
    r = client.get("/api/me")
    assert r.status_code == 401 and r.json()["detail"] == "not_logged_in"


def test_token_dies_with_pin_reset(client):
    admin = login(client)
    lena = create_user(client, admin, "Lena")
    old = login(client, "Lena", "5678")
    assert client.post(f"/api/users/{lena['id']}/pin", json={"pin": "9999"}, headers=admin).status_code == 204
    assert client.get("/api/me", headers=old).status_code == 401
    login(client, "Lena", "9999")


def test_pin_reset_unlocks(client):
    admin = login(client)
    lena = create_user(client, admin, "Lena")
    for _ in range(5):
        client.post("/api/token", json={"name": "Lena", "pin": "0000"})
    client.post(f"/api/users/{lena['id']}/pin", json={"pin": "9999"}, headers=admin)
    login(client, "Lena", "9999")


def test_own_pin_change_keeps_this_device(client):
    headers = login(client)
    r = client.post("/api/me/pin", json={"current_pin": ADMIN_PIN, "new_pin": "4321"}, headers=headers)
    assert r.status_code == 204
    assert client.get("/api/me", headers=headers).status_code == 401
    fresh = {"Authorization": f"Bearer {r.headers['X-New-Token']}"}
    assert client.get("/api/me", headers=fresh).status_code == 200
    login(client, ADMIN, "4321")


def test_own_pin_change_needs_current_pin(client):
    r = client.post("/api/me/pin", json={"current_pin": "0000", "new_pin": "4321"}, headers=login(client))
    assert r.status_code == 400 and r.json()["detail"] == "wrong_current_pin"


def test_token_of_deleted_user(client):
    admin = login(client)
    lena = create_user(client, admin, "Lena")
    token = login(client, "Lena", "5678")
    client.delete(f"/api/users/{lena['id']}", headers=admin)
    create_user(client, admin, "Mia")  # must not inherit Lena's id
    assert client.get("/api/me", headers=token).status_code == 401


def test_language_choice(client):
    headers = login(client)
    me = client.patch("/api/me", json={"language": "en"}, headers=headers).json()
    assert me["language"] == "en" and me["language_chosen"] is True
    me = client.patch("/api/me", json={"language": None}, headers=headers).json()
    assert me["language"] == "de" and me["language_chosen"] is False


def test_unsupported_language_refused(client):
    assert client.patch("/api/me", json={"language": "fr"}, headers=login(client)).status_code == 422


def test_unknown_default_language_falls_back_to_german(client, monkeypatch):
    monkeypatch.setenv("DEFAULT_LANGUAGE", "fr")
    assert client.get("/api/me", headers=login(client)).json()["language"] == "de"


def test_english_default_language(client, monkeypatch):
    monkeypatch.setenv("DEFAULT_LANGUAGE", "en")
    assert client.get("/api/me", headers=login(client)).json()["language"] == "en"


def _fail(client, name=ADMIN, times=5):
    for _ in range(times):
        client.post("/api/token", json={"name": name, "pin": "0000"})


def test_repeated_lockouts_grow(client, db):
    from app import models

    _fail(client)
    user = db.query(models.User).filter_by(name="Admin").one()
    user.locked_until = None  # the first lock ran out
    db.commit()
    _fail(client)
    r = client.post("/api/token", json={"name": ADMIN, "pin": ADMIN_PIN})
    assert r.json()["detail"] == {"code": "locked", "minutes": 30}


def test_lock_never_longer_than_a_day(client, db):
    from app import models

    user = db.query(models.User).filter_by(name="Admin").one()
    user.lockouts = 20
    db.commit()
    _fail(client)
    r = client.post("/api/token", json={"name": ADMIN, "pin": ADMIN_PIN})
    assert r.json()["detail"] == {"code": "locked", "minutes": 24 * 60}


def test_correct_login_forgets_lockouts(client, db):
    from app import models

    user = db.query(models.User).filter_by(name="Admin").one()
    user.lockouts = 3
    db.commit()
    login(client)
    db.refresh(user)
    assert user.lockouts == 0


def test_public_config_has_default_language(client, monkeypatch):
    assert client.get("/api/config").json() == {"default_language": "de"}
    monkeypatch.setenv("DEFAULT_LANGUAGE", "en")
    assert client.get("/api/config").json() == {"default_language": "en"}
