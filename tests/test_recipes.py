from helpers import create_recipe, create_user, login, recipe_body


def test_create_and_read(client, admin_headers):
    r = create_recipe(
        client,
        admin_headers,
        tags=["vegi"],
        ingredients=[
            {"group": "Teig", "amount": 250, "unit": "g", "name": "Mehl"},
            {"amount": None, "unit": None, "name": "Salz", "note": "nach Belieben"},
        ],
    )
    got = client.get(f"/api/recipes/{r['id']}", headers=admin_headers).json()
    assert [i["name"] for i in got["ingredients"]] == ["Mehl", "Salz"]
    assert got["ingredients"][0]["group"] == "Teig"
    assert got["ingredients"][1]["note"] == "nach Belieben"
    assert got["created_by_name"] == "Admin" and got["deleted"] is False and got["source_kind"] == "manual"
    assert got["servings"] == 4 and got["servings_unit"] is None and got["steps"] == ["Kochen"]


def test_child_creates_and_edits(client, admin_headers):
    create_user(client, admin_headers, "Lena")
    kid = login(client, "Lena", "5678")
    r = create_recipe(client, kid, "Pancakes")
    assert r["created_by_name"] == "Lena"
    put = client.put(f"/api/recipes/{r['id']}", json=recipe_body("Pancakes mit Sirup"), headers=kid)
    assert put.status_code == 200 and put.json()["title"] == "Pancakes mit Sirup"


def test_unknown_unit(client, admin_headers):
    body = recipe_body(ingredients=[{"amount": 1, "unit": "cups", "name": "Milch"}])
    r = client.post("/api/recipes", json=body, headers=admin_headers)
    assert r.status_code == 422 and "unknown_unit" in r.text


def test_servings_must_be_positive(client, admin_headers):
    for servings in (0, -1, 101):
        r = client.post("/api/recipes", json=recipe_body(servings=servings), headers=admin_headers)
        assert r.status_code == 422, servings


def test_blank_title_refused(client, admin_headers):
    assert client.post("/api/recipes", json=recipe_body("  "), headers=admin_headers).status_code == 422


def test_put_replaces_ingredients(client, admin_headers):
    r = create_recipe(
        client, admin_headers, ingredients=[{"name": "A"}, {"name": "B"}]
    )
    client.put(
        f"/api/recipes/{r['id']}", json=recipe_body(ingredients=[{"name": "C"}]), headers=admin_headers
    )
    got = client.get(f"/api/recipes/{r['id']}", headers=admin_headers).json()
    assert [i["name"] for i in got["ingredients"]] == ["C"]


def test_list_sorted_and_search(client, admin_headers):
    create_recipe(client, admin_headers, "Zürcher Geschnetzeltes", tags=["Fleisch"])
    create_recipe(client, admin_headers, "älplermagronen")
    create_recipe(client, admin_headers, "Risotto", ingredients=[{"amount": 300, "unit": "g", "name": "Arborio-Reis"}])

    def titles(query=""):
        return [r["title"] for r in client.get(f"/api/recipes{query}", headers=admin_headers).json()]

    assert titles() == ["älplermagronen", "Risotto", "Zürcher Geschnetzeltes"]
    assert titles("?q=reis") == ["Risotto"]
    assert titles("?q=fleisch") == ["Zürcher Geschnetzeltes"]
    assert titles("?q=ZÜRCHER") == ["Zürcher Geschnetzeltes"]
    assert titles("?tag=FLEISCH") == ["Zürcher Geschnetzeltes"]


def test_tags_merge_case(client, admin_headers):
    create_recipe(client, admin_headers, "A", tags=["Vegi", " vegi ", ""])
    b = create_recipe(client, admin_headers, "B", tags=["VEGI", "schnell"])
    assert b["tags"] == ["Vegi", "schnell"]
    assert client.get("/api/tags", headers=admin_headers).json() == [
        {"name": "schnell", "count": 1},
        {"name": "Vegi", "count": 2},
    ]


def test_only_parents_delete(client, admin_headers):
    r = create_recipe(client, admin_headers)
    create_user(client, admin_headers, "Lena")
    kid = login(client, "Lena", "5678")
    denied = client.delete(f"/api/recipes/{r['id']}", headers=kid)
    assert denied.status_code == 403 and denied.json()["detail"] == "parents_only"
    assert client.delete(f"/api/recipes/{r['id']}", headers=admin_headers).status_code == 204


def test_deleted_recipe_readable_but_hidden(client, admin_headers):
    r = create_recipe(client, admin_headers, "Weg", tags=["x"])
    client.delete(f"/api/recipes/{r['id']}", headers=admin_headers)
    got = client.get(f"/api/recipes/{r['id']}", headers=admin_headers)
    assert got.status_code == 200 and got.json()["deleted"] is True
    assert client.get("/api/recipes?q=weg", headers=admin_headers).json() == []
    assert client.get("/api/tags", headers=admin_headers).json() == []
    put = client.put(f"/api/recipes/{r['id']}", json=recipe_body("Weg"), headers=admin_headers)
    assert put.status_code == 404


def test_missing_recipe(client, admin_headers):
    r = client.get("/api/recipes/999", headers=admin_headers)
    assert r.status_code == 404 and r.json()["detail"] == "recipe_not_found"


def test_needs_login(client):
    assert client.get("/api/recipes").status_code == 401


def test_units(client, admin_headers):
    assert client.get("/api/units", headers=admin_headers).json()[:3] == ["g", "kg", "ml"]


def test_recipe_survives_creator_deletion(client, admin_headers):
    lena = create_user(client, admin_headers, "Lena")
    r = create_recipe(client, login(client, "Lena", "5678"))
    client.delete(f"/api/users/{lena['id']}", headers=admin_headers)
    assert client.get(f"/api/recipes/{r['id']}", headers=admin_headers).json()["created_by_name"] is None


def test_people_as_yield_unit_means_people(client, admin_headers):
    for word in ("Personen", "personen ", "Pers.", "Portionen", "Portion", "people", "servings", "Person"):
        r = create_recipe(client, admin_headers, servings=2, servings_unit=word)
        assert r["servings_unit"] is None, word


def test_source_url_must_be_web(client, admin_headers):
    r = client.post("/api/recipes", json=recipe_body(source_url="javascript:alert(1)"), headers=admin_headers)
    assert r.status_code == 422
    ok = create_recipe(client, admin_headers, source_url="https://www.swissmilk.ch/de/rezepte/")
    assert ok["source_url"] == "https://www.swissmilk.ch/de/rezepte/"


def test_search_ignores_accents(client, admin_headers):
    create_recipe(client, admin_headers, "Älplermagronen", tags=["Käse"])
    for q in ("alplermagronen", "kase", "ÄLPLER"):
        assert [r["title"] for r in client.get(f"/api/recipes?q={q}", headers=admin_headers).json()] == [
            "Älplermagronen"
        ], q
    assert len(client.get("/api/recipes?tag=kase", headers=admin_headers).json()) == 1
