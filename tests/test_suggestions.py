from helpers import create_recipe, create_user, login, plan


def _rate(client, headers, recipe_id, stars):
    client.put(f"/api/recipes/{recipe_id}/rating", json={"stars": stars}, headers=headers)


def _fav(client, headers, recipe_id):
    client.put(f"/api/recipes/{recipe_id}/favorite", json={"favorite": True}, headers=headers)


def _titles(client, headers, tab, extra=""):
    response = client.get(f"/api/suggestions?tab={tab}{extra}", headers=headers)
    assert response.status_code == 200, response.text
    return [r["title"] for r in response.json()]


def test_favorites_best_rated_first(client, admin_headers, today):
    create_user(client, admin_headers, "Lena")
    kid = login(client, "Lena", "5678")
    good = create_recipe(client, admin_headers, "Gut")
    okay = create_recipe(client, admin_headers, "Okay")
    unrated = create_recipe(client, admin_headers, "Unbewertet")
    create_recipe(client, admin_headers, "Kein Favorit")
    _fav(client, admin_headers, okay["id"])
    _fav(client, kid, good["id"])
    _fav(client, kid, unrated["id"])
    _rate(client, admin_headers, good["id"], 5)
    _rate(client, admin_headers, okay["id"], 3)
    assert _titles(client, admin_headers, "favorites") == ["Gut", "Okay", "Unbewertet"]


def test_long_ago(client, admin_headers, today):
    old = create_recipe(client, admin_headers, "Alt")
    recent = create_recipe(client, admin_headers, "Neulich")
    bad = create_recipe(client, admin_headers, "Schlecht")
    unrated = create_recipe(client, admin_headers, "Unbewertet")
    create_recipe(client, admin_headers, "Nie gegessen")
    plan(client, admin_headers, "2026-08-01", recipe_id=old["id"])
    plan(client, admin_headers, "2026-10-20", recipe_id=recent["id"])
    plan(client, admin_headers, "2026-07-01", recipe_id=bad["id"])
    plan(client, admin_headers, "2026-09-01", recipe_id=unrated["id"])
    _rate(client, admin_headers, bad["id"], 2)
    _rate(client, admin_headers, old["id"], 4)
    assert _titles(client, admin_headers, "long_ago") == ["Alt", "Unbewertet", "Neulich"]


def test_new(client, admin_headers, today):
    first = create_recipe(client, admin_headers, "Erstes")
    create_recipe(client, admin_headers, "Zweites")
    eaten = create_recipe(client, admin_headers, "Gegessen")
    plan(client, admin_headers, "2026-10-20", recipe_id=eaten["id"])
    planned = create_recipe(client, admin_headers, "Erst geplant")
    plan(client, admin_headers, "2026-11-02", recipe_id=planned["id"])
    assert _titles(client, admin_headers, "new") == ["Erst geplant", "Zweites", "Erstes"]
    assert first["id"]


def test_again(client, admin_headers, today):
    skipped = create_recipe(client, admin_headers, "Ausgelassen")
    replanned = create_recipe(client, admin_headers, "Neu geplant")
    create_recipe(client, admin_headers, "Gegessen")
    for recipe in (skipped, replanned):
        entry = plan(client, admin_headers, "2026-10-21", recipe_id=recipe["id"])
        client.patch(f"/api/plan/entries/{entry['id']}", json={"eaten": False}, headers=admin_headers)
    plan(client, admin_headers, "2026-11-03", recipe_id=replanned["id"])
    assert _titles(client, admin_headers, "again") == ["Ausgelassen"]


def test_deleted_never_suggested(client, admin_headers, today):
    gone = create_recipe(client, admin_headers, "Weg")
    _fav(client, admin_headers, gone["id"])
    plan(client, admin_headers, "2026-09-01", recipe_id=gone["id"])
    client.delete(f"/api/recipes/{gone['id']}", headers=admin_headers)
    for tab in ("favorites", "long_ago", "new", "again"):
        assert _titles(client, admin_headers, tab) == [], tab


def test_search_narrows(client, admin_headers, today):
    for title in ("Risotto", "Rösti"):
        _fav(client, admin_headers, create_recipe(client, admin_headers, title)["id"])
    assert _titles(client, admin_headers, "favorites", "&q=risot") == ["Risotto"]
    assert _titles(client, admin_headers, "favorites", "&q=rosti") == ["Rösti"]


def test_summary_has_stats(client, admin_headers, today):
    r = create_recipe(client, admin_headers, "Alt")
    plan(client, admin_headers, "2026-08-01", recipe_id=r["id"])
    got = client.get("/api/suggestions?tab=long_ago", headers=admin_headers).json()[0]
    assert got["last_eaten"] == "2026-08-01" and got["times_eaten"] == 1


def test_unknown_tab(client, admin_headers):
    assert client.get("/api/suggestions?tab=random", headers=admin_headers).status_code == 422
