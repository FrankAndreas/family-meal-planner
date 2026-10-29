from helpers import create_recipe, create_user, login, plan


def test_default_week_is_the_one_of_tomorrow(client, admin_headers, today):
    week = client.get("/api/plan", headers=admin_headers).json()
    assert week["start"] == "2026-10-31" and len(week["days"]) == 7 and week["days"][-1] == "2026-11-06"
    assert week["total_slots"] == 28 and week["planned_slots"] == 0 and week["today"] == "2026-10-30"


def test_any_date_gives_its_week(client, admin_headers, today):
    assert client.get("/api/plan?start=2026-11-03", headers=admin_headers).json()["start"] == "2026-10-31"


def test_plan_recipe_with_family_size(client, admin_headers, today):
    r = create_recipe(client, admin_headers)
    entry = plan(client, admin_headers, "2026-10-31", recipe_id=r["id"])
    assert entry["people"] == 4 and entry["recipe"]["title"] == r["title"] and entry["note"] is None
    assert entry["eaten"] is True and entry["recipe_deleted"] is False
    client.patch("/api/settings", json={"family_size": 5}, headers=admin_headers)
    assert plan(client, admin_headers, "2026-11-01", recipe_id=r["id"])["people"] == 5
    week = client.get("/api/plan?start=2026-10-31", headers=admin_headers).json()
    assert [e["people"] for e in week["entries"]] == [4, 5]


def test_plan_note(client, admin_headers, today):
    entry = plan(client, admin_headers, "2026-10-31", note=" Pizza-Abend ", people=3)
    assert entry["note"] == "Pizza-Abend" and entry["people"] is None and entry["recipe"] is None


def test_recipe_or_note(client, admin_headers, today):
    r = create_recipe(client, admin_headers)
    for body in ({}, {"recipe_id": r["id"], "note": "x"}, {"note": "   "}):
        response = client.post(
            "/api/plan/entries", json={"date": "2026-10-31", "slot": "dinner", **body}, headers=admin_headers
        )
        assert response.status_code == 422 and "recipe_or_note" in response.text, body


def test_slot_order_and_positions(client, admin_headers, today):
    r = create_recipe(client, admin_headers)
    plan(client, admin_headers, "2026-10-31", "dinner", recipe_id=r["id"])
    plan(client, admin_headers, "2026-10-31", "dinner", note="Salat")
    plan(client, admin_headers, "2026-10-31", "breakfast", note="Zopf")
    week = client.get("/api/plan", headers=admin_headers).json()
    assert [(e["slot"], e["position"]) for e in week["entries"]] == [("breakfast", 0), ("dinner", 0), ("dinner", 1)]
    assert week["planned_slots"] == 2


def test_move_entry(client, admin_headers, today):
    first = plan(client, admin_headers, "2026-11-01", "lunch", note="Da")
    moving = plan(client, admin_headers, "2026-10-31", "dinner", note="Weg")
    moved = client.patch(
        f"/api/plan/entries/{moving['id']}", json={"date": "2026-11-01", "slot": "lunch"}, headers=admin_headers
    ).json()
    assert moved["date"] == "2026-11-01" and moved["slot"] == "lunch" and moved["position"] == 1
    assert first["position"] == 0


def test_patch_people_and_note(client, admin_headers, today):
    r = create_recipe(client, admin_headers)
    entry = plan(client, admin_headers, "2026-10-31", recipe_id=r["id"])
    assert client.patch(f"/api/plan/entries/{entry['id']}", json={"people": 2.5}, headers=admin_headers).json()[
        "people"
    ] == 2.5
    note = plan(client, admin_headers, "2026-10-31", note="Resten")
    assert client.patch(f"/api/plan/entries/{note['id']}", json={"note": "Auswärts"}, headers=admin_headers).json()[
        "note"
    ] == "Auswärts"


def test_child_plans_moves_deletes(client, admin_headers, today):
    create_user(client, admin_headers, "Lena")
    kid = login(client, "Lena", "5678")
    entry = plan(client, kid, "2026-10-31", note="Pancakes")
    assert client.patch(f"/api/plan/entries/{entry['id']}", json={"slot": "breakfast"}, headers=kid).status_code == 200
    assert client.delete(f"/api/plan/entries/{entry['id']}", headers=kid).status_code == 204


def test_deleted_recipe(client, admin_headers, today):
    r = create_recipe(client, admin_headers)
    entry = plan(client, admin_headers, "2026-10-31", recipe_id=r["id"])
    client.delete(f"/api/recipes/{r['id']}", headers=admin_headers)
    response = client.post(
        "/api/plan/entries", json={"date": "2026-11-01", "slot": "dinner", "recipe_id": r["id"]}, headers=admin_headers
    )
    assert response.status_code == 400 and response.json()["detail"] == "recipe_deleted"
    listed = client.get("/api/plan", headers=admin_headers).json()["entries"][0]
    assert listed["recipe_deleted"] is True and listed["recipe"]["title"] == r["title"]
    assert client.delete(f"/api/plan/entries/{entry['id']}", headers=admin_headers).status_code == 204


def test_two_devices_add_to_the_same_slot(client, admin_headers, today):
    create_user(client, admin_headers, "Lena")
    kid = login(client, "Lena", "5678")
    plan(client, admin_headers, "2026-10-31", note="Von Papa")
    plan(client, kid, "2026-10-31", note="Von Lena")
    notes = [e["note"] for e in client.get("/api/plan", headers=kid).json()["entries"]]
    assert notes == ["Von Papa", "Von Lena"]


def test_errors(client, admin_headers, today):
    missing = client.patch("/api/plan/entries/999", json={"people": 2}, headers=admin_headers)
    assert missing.status_code == 404 and missing.json()["detail"] == "entry_not_found"
    r = create_recipe(client, admin_headers)
    bad = {"date": "2026-10-31", "slot": "dinner", "recipe_id": r["id"]}
    assert client.post("/api/plan/entries", json={**bad, "people": 0}, headers=admin_headers).status_code == 422
    assert client.post("/api/plan/entries", json={**bad, "slot": "brunch"}, headers=admin_headers).status_code == 422
    unknown = client.post("/api/plan/entries", json={**bad, "recipe_id": 999}, headers=admin_headers)
    assert unknown.status_code == 404 and unknown.json()["detail"] == "recipe_not_found"
