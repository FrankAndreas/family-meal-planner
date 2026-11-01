from helpers import create_recipe, create_user, login, plan


def _recipe(client, headers, title, *names, notes=None):
    notes = notes or {}
    ingredients = [{"amount": None, "unit": None, "name": n, "note": notes.get(n, "")} for n in names]
    return create_recipe(client, headers, title=title, ingredients=ingredients)


def _search(client, headers, *have, mode=None):
    params = [("have", h) for h in have] + ([("mode", mode)] if mode else [])
    response = client.get("/api/use-up", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_use_up_ranks_by_used_then_missing_then_longest_ago(client, admin_headers, today):
    _recipe(client, admin_headers, "A", "Kartoffeln", "Lauch", "Rahm")
    _recipe(client, admin_headers, "B", "Kartoffeln", "Lauch", "Tomaten", "Rüebli")
    c = _recipe(client, admin_headers, "C", "Kartoffeln", "Lauch")
    _recipe(client, admin_headers, "D", "Kartoffeln", "Lauch")
    _recipe(client, admin_headers, "E", "Hörnli")
    plan(client, admin_headers, "2026-10-01", recipe_id=c["id"])
    found = _search(client, admin_headers, "Kartoffeln", "Lauch", "Tomaten")
    assert [r["title"] for r in found] == ["B", "D", "C", "A"]
    assert found[0]["used"] == ["Kartoffeln", "Lauch", "Tomaten"] and found[0]["missing"] == ["Rüebli"]
    assert found[2]["last_eaten"] == "2026-10-01"


def test_cook_now_allows_two_missing(client, admin_headers, today):
    _recipe(client, admin_headers, "A", "Kartoffeln", "Salz", "Pfeffer", "Olivenöl")
    _recipe(client, admin_headers, "B", "Kartoffeln", "Rahm", "Käse")
    _recipe(client, admin_headers, "C", "Kartoffeln", "Rahm", "Käse", "Speck")
    found = _search(client, admin_headers, "Kartoffeln", mode="cook_now")
    assert [(r["title"], r["missing"]) for r in found] == [("A", []), ("B", ["Rahm", "Käse"])]


def test_optional_never_missing(client, admin_headers, today):
    _recipe(
        client, admin_headers, "A", "Kartoffeln", "Petersilie", "Schnittlauch",
        notes={"Petersilie": "nach Belieben", "Schnittlauch": "optional"},
    )
    assert _search(client, admin_headers, "Kartoffeln")[0]["missing"] == []


def test_staples_follow_the_setting(client, admin_headers, today):
    _recipe(client, admin_headers, "A", "Kartoffeln", "Olivenöl")
    assert _search(client, admin_headers, "Kartoffeln")[0]["missing"] == []
    client.patch("/api/settings", json={"staples": ["Salz"]}, headers=admin_headers)
    assert _search(client, admin_headers, "Kartoffeln")[0]["missing"] == ["Olivenöl"]


def test_typed_basic_counts_as_used(client, admin_headers, today):
    _recipe(client, admin_headers, "R", "Salz", "Wasser")
    for mode in ("use_up", "cook_now"):
        assert _search(client, admin_headers, "Lauch", mode=mode) == []
    found = _search(client, admin_headers, "Salz")
    assert [(r["title"], r["used"], r["missing"]) for r in found] == [("R", ["Salz"], [])]


def test_synonyms_and_repeats_count_once(client, admin_headers, today):
    _recipe(client, admin_headers, "A", "Halbrahm")
    assert _search(client, admin_headers, "Rahm", "Sahne", "Rahm")[0]["used"] == ["Rahm"]


def test_have_limits(client, admin_headers, today):
    _recipe(client, admin_headers, "A", "Lauch")
    assert _search(client, admin_headers, " ") == []
    assert _search(client, admin_headers) == []
    many = client.get("/api/use-up", params=[("have", f"x{n}") for n in range(21)], headers=admin_headers)
    assert many.status_code == 422


def test_deleted_recipes_never_show(client, admin_headers, today):
    r = _recipe(client, admin_headers, "A", "Lauch")
    client.delete(f"/api/recipes/{r['id']}", headers=admin_headers)
    assert _search(client, admin_headers, "Lauch") == []


def test_needs_login(client):
    assert client.get("/api/use-up?have=Lauch").status_code == 401
    assert client.get("/api/ingredient-names?q=la").status_code == 401


def test_child_may_search(client, admin_headers, today):
    _recipe(client, admin_headers, "A", "Lauch")
    create_user(client, admin_headers, "Lena")
    assert [r["title"] for r in _search(client, login(client, "Lena", "5678"), "Lauch")] == ["A"]


def test_ingredient_names(client, admin_headers):
    _recipe(client, admin_headers, "A", "Kartoffeln", "Rahm")
    _recipe(client, admin_headers, "B", "kartoffeln", "Süsskartoffeln")
    names = lambda q: client.get("/api/ingredient-names", params={"q": q}, headers=admin_headers).json()  # noqa: E731
    assert names("kart") == ["Kartoffeln", "Süsskartoffeln"]
    assert names("") == []
