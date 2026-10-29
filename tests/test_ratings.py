from helpers import create_recipe, create_user, login


def _rate(client, headers, recipe_id, stars):
    return client.put(f"/api/recipes/{recipe_id}/rating", json={"stars": stars}, headers=headers)


def test_rate_and_change(client, admin_headers):
    r = create_recipe(client, admin_headers)
    _rate(client, admin_headers, r["id"], 5)
    got = _rate(client, admin_headers, r["id"], 3).json()
    assert got["my_rating"] == 3 and got["rating_avg"] == 3 and got["rating_count"] == 1


def test_average_and_per_person(client, admin_headers):
    r = create_recipe(client, admin_headers)
    create_user(client, admin_headers, "Lena")
    _rate(client, admin_headers, r["id"], 3)
    got = _rate(client, login(client, "Lena", "5678"), r["id"], 5).json()
    assert got["rating_avg"] == 4.0
    assert [(x["name"], x["stars"]) for x in got["ratings"]] == [("Admin", 3), ("Lena", 5)]
    summary = client.get("/api/recipes", headers=admin_headers).json()[0]
    assert summary["rating_avg"] == 4.0 and summary["my_rating"] == 3


def test_remove_rating(client, admin_headers):
    r = create_recipe(client, admin_headers)
    _rate(client, admin_headers, r["id"], 4)
    got = _rate(client, admin_headers, r["id"], None).json()
    assert got["my_rating"] is None and got["rating_avg"] is None and got["rating_count"] == 0


def test_stars_range(client, admin_headers):
    r = create_recipe(client, admin_headers)
    assert _rate(client, admin_headers, r["id"], 0).status_code == 422
    assert _rate(client, admin_headers, r["id"], 6).status_code == 422


def test_cannot_rate_deleted(client, admin_headers):
    r = create_recipe(client, admin_headers)
    client.delete(f"/api/recipes/{r['id']}", headers=admin_headers)
    assert _rate(client, admin_headers, r["id"], 4).status_code == 404


def test_favorites(client, admin_headers):
    mine = create_recipe(client, admin_headers, "Meins")
    theirs = create_recipe(client, admin_headers, "Lenas")
    create_recipe(client, admin_headers, "Niemand")
    create_user(client, admin_headers, "Lena")
    kid = login(client, "Lena", "5678")
    on = client.put(f"/api/recipes/{mine['id']}/favorite", json={"favorite": True}, headers=admin_headers).json()
    assert on["my_favorite"] is True and on["favorite_count"] == 1
    client.put(f"/api/recipes/{theirs['id']}/favorite", json={"favorite": True}, headers=kid)

    def titles(query):
        return [r["title"] for r in client.get(f"/api/recipes?favorites={query}", headers=admin_headers).json()]

    assert titles("mine") == ["Meins"]
    assert titles("any") == ["Lenas", "Meins"]
    off = client.put(f"/api/recipes/{mine['id']}/favorite", json={"favorite": False}, headers=admin_headers).json()
    assert off["my_favorite"] is False and off["favorite_count"] == 0
    # Twice the same is fine
    client.put(f"/api/recipes/{mine['id']}/favorite", json={"favorite": False}, headers=admin_headers)


def test_deleting_user_removes_their_votes(client, admin_headers):
    r = create_recipe(client, admin_headers)
    lena = create_user(client, admin_headers, "Lena")
    kid = login(client, "Lena", "5678")
    _rate(client, kid, r["id"], 2)
    client.put(f"/api/recipes/{r['id']}/favorite", json={"favorite": True}, headers=kid)
    assert client.delete(f"/api/users/{lena['id']}", headers=admin_headers).status_code == 204
    got = client.get(f"/api/recipes/{r['id']}", headers=admin_headers).json()
    assert got["rating_count"] == 0 and got["favorite_count"] == 0
