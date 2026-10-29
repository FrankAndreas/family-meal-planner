from datetime import date

from helpers import create_recipe, plan


def _summary(client, headers, recipe_id):
    return client.get(f"/api/recipes/{recipe_id}", headers=headers).json()


def test_last_eaten_and_times(client, admin_headers, today):
    r = create_recipe(client, admin_headers)
    plan(client, admin_headers, "2026-10-20", recipe_id=r["id"])
    plan(client, admin_headers, "2026-10-25", recipe_id=r["id"])
    got = _summary(client, admin_headers, r["id"])
    assert got["last_eaten"] == "2026-10-25" and got["times_eaten"] == 2
    listed = client.get("/api/recipes", headers=admin_headers).json()[0]
    assert listed["last_eaten"] == "2026-10-25" and listed["times_eaten"] == 2


def test_today_and_future_not_eaten_yet(client, admin_headers, today):
    r = create_recipe(client, admin_headers)
    plan(client, admin_headers, "2026-10-30", recipe_id=r["id"])
    plan(client, admin_headers, "2026-11-02", recipe_id=r["id"])
    got = _summary(client, admin_headers, r["id"])
    assert got["last_eaten"] is None and got["times_eaten"] == 0


def test_not_eaten_doesnt_count(client, admin_headers, today):
    r = create_recipe(client, admin_headers)
    entry = plan(client, admin_headers, "2026-10-25", recipe_id=r["id"])
    client.patch(f"/api/plan/entries/{entry['id']}", json={"eaten": False}, headers=admin_headers)
    assert _summary(client, admin_headers, r["id"])["times_eaten"] == 0


def test_close_only_when_over(client, admin_headers, today):
    r = create_recipe(client, admin_headers)
    plan(client, admin_headers, "2026-10-25", recipe_id=r["id"])
    today(date(2026, 10, 29))
    early = client.post("/api/plan/close", json={"start": "2026-10-24"}, headers=admin_headers)
    assert early.status_code == 400 and early.json()["detail"] == "week_not_over"
    # On its last day (Friday, the planning session) the week can be closed
    today(date(2026, 10, 30))
    closed = client.post("/api/plan/close", json={"start": "2026-10-27"}, headers=admin_headers)
    assert closed.status_code == 200 and closed.json()["closed"] is True and closed.json()["start"] == "2026-10-24"
    assert client.post("/api/plan/close", json={"start": "2026-10-24"}, headers=admin_headers).status_code == 200


def test_friday_offers_closing_the_week_ending_today(client, admin_headers, today):
    r = create_recipe(client, admin_headers)
    plan(client, admin_headers, "2026-10-26", recipe_id=r["id"])
    # Friday 30.10: the planner opens on 31.10, and the week ending today waits to be closed
    week = client.get("/api/plan", headers=admin_headers).json()
    assert week["start"] == "2026-10-31" and week["previous_needs_closing"] is True


def test_previous_needs_closing(client, admin_headers, today):
    today(date(2026, 10, 31))
    r = create_recipe(client, admin_headers)
    week = lambda: client.get("/api/plan?start=2026-10-31", headers=admin_headers).json()  # noqa: E731
    plan(client, admin_headers, "2026-10-26", note="Nur Notiz")
    assert week()["previous_needs_closing"] is False
    plan(client, admin_headers, "2026-10-25", recipe_id=r["id"])
    assert week()["previous_needs_closing"] is True
    client.post("/api/plan/close", json={"start": "2026-10-24"}, headers=admin_headers)
    assert week()["previous_needs_closing"] is False


def test_changing_week_start_keeps_everything(client, admin_headers, today):
    today(date(2026, 11, 2))
    for day in range(24, 31):
        plan(client, admin_headers, f"2026-10-{day}", note=f"Tag {day}")
    plan(client, admin_headers, "2026-11-01", note="Sonntag")
    client.post("/api/plan/close", json={"start": "2026-10-24"}, headers=admin_headers)
    client.patch("/api/settings", json={"week_start": 0}, headers=admin_headers)
    week = client.get("/api/plan?start=2026-10-26", headers=admin_headers).json()
    assert week["start"] == "2026-10-26"
    assert [e["note"] for e in week["entries"]] == [f"Tag {d}" for d in range(26, 31)] + ["Sonntag"]
    assert week["closed"] is False
    before = client.get("/api/plan?start=2026-10-19", headers=admin_headers).json()
    assert [e["note"] for e in before["entries"]] == ["Tag 24", "Tag 25"]


def test_history(client, admin_headers, today):
    today(date(2026, 11, 2))
    plan(client, admin_headers, "2026-10-10", note="Alt")
    plan(client, admin_headers, "2026-10-25", note="Letzte")
    weeks = client.get("/api/plan/history?before=2026-10-31&weeks=8", headers=admin_headers).json()
    assert [w["start"] for w in weeks] == ["2026-10-24", "2026-10-10"]
    assert [w["start"] for w in client.get("/api/plan/history?before=2026-10-31&weeks=1", headers=admin_headers).json()] == [
        "2026-10-24"
    ]
    default = client.get("/api/plan/history", headers=admin_headers).json()
    assert default[0]["start"] == "2026-10-24"


def test_recipe_history(client, admin_headers, today):
    r = create_recipe(client, admin_headers)
    plan(client, admin_headers, "2026-10-12", recipe_id=r["id"])
    skipped = plan(client, admin_headers, "2026-10-19", recipe_id=r["id"])
    client.patch(f"/api/plan/entries/{skipped['id']}", json={"eaten": False}, headers=admin_headers)
    plan(client, admin_headers, "2026-10-26", recipe_id=r["id"])
    plan(client, admin_headers, "2026-11-02", recipe_id=r["id"])
    assert client.get(f"/api/recipes/{r['id']}/history", headers=admin_headers).json() == ["2026-10-26", "2026-10-12"]
