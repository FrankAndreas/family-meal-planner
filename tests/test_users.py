from helpers import create_user, login


def test_child_cannot_manage_users(client):
    create_user(client, login(client), "Lena")
    kid = login(client, "Lena", "5678")
    r = client.post("/api/users", json={"name": "X", "pin": "1111", "role": "CHILD"}, headers=kid)
    assert r.status_code == 403 and r.json()["detail"] == "parents_only"
    assert client.get("/api/users", headers=kid).status_code == 403


def test_parent_lists_users(client):
    admin = login(client)
    create_user(client, admin, "Lena")
    assert [u["name"] for u in client.get("/api/users", headers=admin).json()] == ["Admin", "Lena"]


def test_name_taken_ignores_case(client):
    admin = login(client)
    create_user(client, admin, "Lena")
    r = client.post("/api/users", json={"name": "lena", "pin": "1111", "role": "CHILD"}, headers=admin)
    assert r.status_code == 409 and r.json()["detail"] == "name_taken"


def test_rename_to_taken_name(client):
    admin = login(client)
    create_user(client, admin, "Lena")
    mia = create_user(client, admin, "Mia")
    r = client.patch(f"/api/users/{mia['id']}", json={"name": "LENA"}, headers=admin)
    assert r.status_code == 409 and r.json()["detail"] == "name_taken"


def test_rename_changes_case_of_own_name(client):
    admin = login(client)
    mia = create_user(client, admin, "mia")
    assert client.patch(f"/api/users/{mia['id']}", json={"name": "Mia"}, headers=admin).json()["name"] == "Mia"
    login(client, "MIA", "5678")


def test_blank_name_refused(client):
    r = client.post("/api/users", json={"name": "   ", "pin": "1111", "role": "CHILD"}, headers=login(client))
    assert r.status_code == 422


def test_last_parent_cannot_become_child(client):
    admin = login(client)
    me = client.get("/api/me", headers=admin).json()
    r = client.patch(f"/api/users/{me['id']}", json={"role": "CHILD"}, headers=admin)
    assert r.status_code == 400 and r.json()["detail"] == "last_parent"


def test_second_parent_can_be_demoted(client):
    admin = login(client)
    papa = create_user(client, admin, "Papa", role="PARENT")
    r = client.patch(f"/api/users/{papa['id']}", json={"role": "CHILD"}, headers=admin)
    assert r.json()["role"] == "CHILD"


def test_demoted_parent_loses_rights_at_once(client):
    admin = login(client)
    papa = create_user(client, admin, "Papa", role="PARENT")
    papa_headers = login(client, "Papa", "5678")
    client.patch(f"/api/users/{papa['id']}", json={"role": "CHILD"}, headers=admin)
    assert client.get("/api/users", headers=papa_headers).status_code == 403


def test_cannot_delete_self(client):
    admin = login(client)
    me = client.get("/api/me", headers=admin).json()
    r = client.delete(f"/api/users/{me['id']}", headers=admin)
    assert r.status_code == 400 and r.json()["detail"] == "cannot_delete_self"


def test_delete_unknown_user(client):
    r = client.delete("/api/users/99", headers=login(client))
    assert r.status_code == 404 and r.json()["detail"] == "user_not_found"


def test_public_list_has_names_only(client):
    create_user(client, login(client), "Lena")
    assert client.get("/api/users/public").json() == [{"id": 1, "name": "Admin"}, {"id": 2, "name": "Lena"}]


def test_seed_admin_only_on_empty_database(db):
    from app.seed import seed_admin

    assert seed_admin(db) is None
