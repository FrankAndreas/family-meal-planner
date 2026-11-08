"""The shared shopping list and sending it to Bring! (spec 2026-11-06)."""

from datetime import date, timedelta

import pytest

from app import bring
from helpers import create_recipe, create_user, login, plan

WEEK = date(2026, 10, 31)  # a Saturday: the default first day of the week
HOERNLI = [{"amount": 200, "unit": "g", "name": "Hörnli"}, {"amount": 1, "unit": "tsp", "name": "Salz"}]


@pytest.fixture(autouse=True)
def fake_bring(monkeypatch):
    monkeypatch.setenv("BRING_FAKE", "1")
    bring.FakeBring.sent.clear()
    return bring.FakeBring.sent


@pytest.fixture
def parent2(client, admin_headers):
    create_user(client, admin_headers, "Mama", role="PARENT")
    return login(client, "Mama")


def _get(client, headers):
    response = client.get("/api/shopping", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["list"]


def _start(client, headers, start=WEEK, **body):
    return client.post("/api/shopping", json={"week_start": str(start), **body}, headers=headers)


def _line(shopping, name):
    return next(line for line in shopping["lines"] if line["name"] == name)


def _setup_bring(client, headers):
    assert client.post("/api/bring/login", json={"email": "a@b.ch", "password": "geheim"}, headers=headers).status_code == 200
    assert client.put("/api/bring/list", json={"uuid": "fake-home"}, headers=headers).status_code == 200


def _send(client, headers, shopping, specs=None):
    return client.post(
        "/api/shopping/send", json={"version": shopping["version"], "specs": specs or {}}, headers=headers
    )


@pytest.fixture
def week(client, admin_headers):
    """Älplermagronen for 6 on Saturday (recipe for 4), a note on Sunday."""
    recipe = create_recipe(client, admin_headers, "Älplermagronen", ingredients=HOERNLI)
    entry = plan(client, admin_headers, WEEK, recipe_id=recipe["id"], people=6)
    note = plan(client, admin_headers, WEEK + timedelta(days=1), note="Resten")
    return {"recipe": recipe, "entry": entry, "note": note}


def test_nothing_open(client, admin_headers):
    assert _get(client, admin_headers) is None


def test_start_ticks_recipe_entries_only(client, admin_headers, week):
    response = _start(client, admin_headers)
    assert response.status_code == 200, response.text
    shopping = response.json()
    assert [(m["entry_id"], m["title"], m["ticked"]) for m in shopping["meals"]] == [
        (week["entry"]["id"], "Älplermagronen", True)
    ]
    assert [n["note"] for n in shopping["notes"]] == ["Resten"]
    assert shopping["week_start"] == str(WEEK) and shopping["week_end"] == str(WEEK + timedelta(days=6))


def test_lines_scaled_per_entry(client, admin_headers, week):
    shopping = _start(client, admin_headers).json()
    line = _line(shopping, "Hörnli")
    assert line["amounts"] == [{"amount": 300, "unit": "g"}]
    assert line["meals"] == ["Älplermagronen"] and line["buy"] is True


def test_entry_without_people_uses_family_size(client, admin_headers, today):
    client.patch("/api/settings", json={"family_size": 2}, headers=admin_headers)
    recipe = create_recipe(client, admin_headers, "A", ingredients=HOERNLI)
    plan(client, admin_headers, WEEK, recipe_id=recipe["id"])
    entry_people = _start(client, admin_headers).json()["meals"][0]["people"]
    shopping = _get(client, admin_headers)
    assert _line(shopping, "Hörnli")["amounts"] == [{"amount": 100, "unit": "g"}]
    assert entry_people in (None, 2)


def test_same_recipe_twice_counts_twice(client, admin_headers, week):
    plan(client, admin_headers, WEEK + timedelta(days=2), recipe_id=week["recipe"]["id"], people=4)
    _start(client, admin_headers)
    assert _line(_get(client, admin_headers), "Hörnli")["amounts"] == [{"amount": 500, "unit": "g"}]


def test_later_entry_unticked(client, admin_headers, week):
    _start(client, admin_headers)
    later = plan(client, admin_headers, WEEK + timedelta(days=3), recipe_id=week["recipe"]["id"])
    meals = _get(client, admin_headers)["meals"]
    assert [(m["entry_id"], m["ticked"]) for m in meals] == [(week["entry"]["id"], True), (later["id"], False)]


def test_tick_and_untick(client, admin_headers, week):
    _start(client, admin_headers)
    entry_id = week["entry"]["id"]
    shopping = client.put(f"/api/shopping/meals/{entry_id}", json={"ticked": False}, headers=admin_headers).json()
    assert shopping["meals"][0]["ticked"] is False and shopping["lines"] == []
    shopping = client.put(f"/api/shopping/meals/{entry_id}", json={"ticked": True}, headers=admin_headers).json()
    assert _line(shopping, "Hörnli")["amounts"] == [{"amount": 300, "unit": "g"}]


def test_tick_outside_week_or_note_refused(client, admin_headers, week):
    _start(client, admin_headers)
    other = plan(client, admin_headers, WEEK + timedelta(days=7), recipe_id=week["recipe"]["id"])
    for entry_id in (other["id"], week["note"]["id"], 999999):
        response = client.put(f"/api/shopping/meals/{entry_id}", json={"ticked": True}, headers=admin_headers)
        assert response.status_code == 400 and response.json()["detail"] == "shopping_not_in_week"


def test_deleted_entry_drops_out(client, admin_headers, week):
    _start(client, admin_headers)
    client.delete(f"/api/plan/entries/{week['entry']['id']}", headers=admin_headers)
    shopping = _get(client, admin_headers)
    assert shopping["meals"] == [] and shopping["lines"] == []


def test_entry_moved_out_and_back_is_unticked(client, admin_headers, week):
    _start(client, admin_headers)
    entry_id = week["entry"]["id"]
    client.patch(f"/api/plan/entries/{entry_id}", json={"date": str(WEEK + timedelta(days=7))}, headers=admin_headers)
    assert _get(client, admin_headers)["meals"] == []
    client.patch(f"/api/plan/entries/{entry_id}", json={"date": str(WEEK)}, headers=admin_headers)
    assert [m["ticked"] for m in _get(client, admin_headers)["meals"]] == [False]


def test_entry_moved_within_week_stays_ticked(client, admin_headers, week):
    _start(client, admin_headers)
    entry_id = week["entry"]["id"]
    client.patch(
        f"/api/plan/entries/{entry_id}", json={"date": str(WEEK + timedelta(days=4)), "slot": "lunch"}, headers=admin_headers
    )
    assert [m["ticked"] for m in _get(client, admin_headers)["meals"]] == [True]


def test_recipe_deleted_after_planning_still_counts(client, admin_headers, week):
    _start(client, admin_headers)
    client.delete(f"/api/recipes/{week['recipe']['id']}", headers=admin_headers)
    assert _line(_get(client, admin_headers), "Hörnli")["amounts"] == [{"amount": 300, "unit": "g"}]


def test_staple_starts_dropped(client, admin_headers, week):
    salz = _line(_start(client, admin_headers).json(), "Salz")
    assert salz["staple"] is True and salz["buy"] is False


def test_kept_staple_stays_kept(client, admin_headers, week):
    _start(client, admin_headers)
    key = _line(_get(client, admin_headers), "Salz")["key"]
    shopping = client.put("/api/shopping/lines", json={"key": key, "buy": True}, headers=admin_headers).json()
    assert _line(shopping, "Salz")["buy"] is True
    client.patch("/api/settings", json={"staples": ["Pfeffer"]}, headers=admin_headers)
    assert _line(_get(client, admin_headers), "Salz")["buy"] is True
    client.patch("/api/settings", json={"staples": ["Salz", "Pfeffer"]}, headers=admin_headers)
    assert _line(_get(client, admin_headers), "Salz")["buy"] is True


def test_choice_removed_goes_back_to_default(client, admin_headers, week):
    _start(client, admin_headers)
    key = _line(_get(client, admin_headers), "Salz")["key"]
    client.put("/api/shopping/lines", json={"key": key, "buy": True}, headers=admin_headers)
    shopping = client.put("/api/shopping/lines", json={"key": key, "buy": None}, headers=admin_headers).json()
    assert _line(shopping, "Salz")["buy"] is False


def test_drop_survives_amount_change(client, admin_headers, week):
    _start(client, admin_headers)
    key = _line(_get(client, admin_headers), "Hörnli")["key"]
    client.put("/api/shopping/lines", json={"key": key, "buy": False}, headers=admin_headers)
    client.patch(f"/api/plan/entries/{week['entry']['id']}", json={"people": 8}, headers=admin_headers)
    line = _line(_get(client, admin_headers), "Hörnli")
    assert line["buy"] is False and line["amounts"] == [{"amount": 400, "unit": "g"}]


def test_extra_added_and_removed(client, admin_headers, week):
    _start(client, admin_headers)
    shopping = client.post("/api/shopping/extras", json={"name": " WC-Papier ", "amount": "2 Pack"}, headers=admin_headers).json()
    assert [(e["name"], e["amount"]) for e in shopping["extras"]] == [("WC-Papier", "2 Pack")]
    line = _line(shopping, "WC-Papier")
    assert line["amounts"] == [] and line["extras"] == ["2 Pack"] and line["buy"] is True
    extra_id = shopping["extras"][0]["id"]
    shopping = client.delete(f"/api/shopping/extras/{extra_id}", headers=admin_headers).json()
    assert shopping["extras"] == [] and all(line["name"] != "WC-Papier" for line in shopping["lines"])


@pytest.mark.parametrize("body", [{"name": "", "amount": ""}, {"name": "x" * 101, "amount": ""}, {"name": "A", "amount": "x" * 51}])
def test_extra_validated(client, admin_headers, week, body):
    _start(client, admin_headers)
    assert client.post("/api/shopping/extras", json=body, headers=admin_headers).status_code == 422


def test_extra_merges_with_line(client, admin_headers, week):
    _start(client, admin_headers)
    shopping = client.post("/api/shopping/extras", json={"name": "hörnli", "amount": "1 Pack"}, headers=admin_headers).json()
    line = _line(shopping, "Hörnli")
    assert line["amounts"] == [{"amount": 300, "unit": "g"}] and line["extras"] == ["1 Pack"]
    assert len([x for x in shopping["lines"] if x["key"] == line["key"]]) == 1


def test_other_week_conflict_and_replace(client, admin_headers, week):
    _start(client, admin_headers)
    again = _start(client, admin_headers)
    assert again.status_code == 200 and again.json()["week_start"] == str(WEEK)
    other = _start(client, admin_headers, WEEK + timedelta(days=7))
    assert other.status_code == 409 and other.json()["detail"] == "shopping_other_week"
    assert _get(client, admin_headers)["week_start"] == str(WEEK)
    replaced = _start(client, admin_headers, WEEK + timedelta(days=7), replace=True)
    assert replaced.status_code == 200 and replaced.json()["week_start"] == str(WEEK + timedelta(days=7))


def test_bad_week_start(client, admin_headers):
    response = _start(client, admin_headers, WEEK + timedelta(days=1))
    assert response.status_code == 400 and response.json()["detail"] == "shopping_bad_week"


def test_discard(client, admin_headers, week):
    _start(client, admin_headers)
    assert client.delete("/api/shopping", headers=admin_headers).status_code == 204
    assert _get(client, admin_headers) is None


def test_changes_without_list(client, admin_headers, week):
    for response in (
        client.put(f"/api/shopping/meals/{week['entry']['id']}", json={"ticked": True}, headers=admin_headers),
        client.put("/api/shopping/lines", json={"key": "x", "buy": False}, headers=admin_headers),
        client.post("/api/shopping/extras", json={"name": "A", "amount": ""}, headers=admin_headers),
        client.delete("/api/shopping/extras/1", headers=admin_headers),
        client.post("/api/shopping/send", json={"version": "x", "specs": {}}, headers=admin_headers),
    ):
        assert response.status_code == 404 and response.json()["detail"] == "shopping_none"


def test_shows_who_started_and_changed(client, admin_headers, parent2, week):
    shopping = _start(client, admin_headers).json()
    assert shopping["started_by"] == "Admin" and shopping["changed_by"] == "Admin"
    key = _line(shopping, "Hörnli")["key"]
    shopping = client.put("/api/shopping/lines", json={"key": key, "buy": False}, headers=parent2).json()
    assert shopping["started_by"] == "Admin" and shopping["changed_by"] == "Mama" and shopping["changed_at"]
    assert _line(_get(client, admin_headers), "Hörnli")["buy"] is False


def test_children_refused(client, admin_headers, week):
    create_user(client, admin_headers, "Lena")
    kid = login(client, "Lena")
    for response in (
        client.get("/api/shopping", headers=kid),
        _start(client, kid),
        client.delete("/api/shopping", headers=kid),
        client.put("/api/shopping/meals/1", json={"ticked": True}, headers=kid),
        client.put("/api/shopping/lines", json={"key": "x", "buy": False}, headers=kid),
        client.post("/api/shopping/extras", json={"name": "A", "amount": ""}, headers=kid),
        client.delete("/api/shopping/extras/1", headers=kid),
        client.post("/api/shopping/send", json={"version": "x", "specs": {}}, headers=kid),
        client.get("/api/bring", headers=kid),
        client.post("/api/bring/login", json={"email": "a@b.ch", "password": "p"}, headers=kid),
        client.get("/api/bring/lists", headers=kid),
        client.put("/api/bring/list", json={"uuid": "fake-home"}, headers=kid),
        client.delete("/api/bring", headers=kid),
    ):
        assert response.status_code == 403, response.request.url


def test_bring_login_lists_and_choice(client, admin_headers):
    assert client.get("/api/bring", headers=admin_headers).json() == {"email": None, "list_uuid": None, "list_name": None}
    assert client.get("/api/bring/lists", headers=admin_headers).json()["detail"] == "bring_not_set_up"
    wrong = client.post("/api/bring/login", json={"email": "a@b.ch", "password": "wrong"}, headers=admin_headers)
    assert wrong.status_code == 400 and wrong.json()["detail"] == "bring_login_failed"
    assert client.get("/api/bring", headers=admin_headers).json()["email"] is None
    ok = client.post("/api/bring/login", json={"email": "a@b.ch", "password": "geheim"}, headers=admin_headers)
    assert ok.json() == {"lists": [{"uuid": "fake-home", "name": "Zuhause"}, {"uuid": "fake-office", "name": "Büro"}]}
    unknown = client.put("/api/bring/list", json={"uuid": "nope"}, headers=admin_headers)
    assert unknown.status_code == 400 and unknown.json()["detail"] == "bring_unknown_list"
    chosen = client.put("/api/bring/list", json={"uuid": "fake-home"}, headers=admin_headers).json()
    assert chosen == {"email": "a@b.ch", "list_uuid": "fake-home", "list_name": "Zuhause"}
    shown = client.get("/api/bring", headers=admin_headers)
    assert shown.json() == chosen and "geheim" not in shown.text
    assert client.get("/api/bring/lists", headers=admin_headers).json()["lists"][1]["name"] == "Büro"
    # A new login clears the chosen list
    client.post("/api/bring/login", json={"email": "c@d.ch", "password": "geheim"}, headers=admin_headers)
    assert client.get("/api/bring", headers=admin_headers).json() == {"email": "c@d.ch", "list_uuid": None, "list_name": None}
    assert client.delete("/api/bring", headers=admin_headers).status_code == 204
    assert client.get("/api/bring", headers=admin_headers).json()["email"] is None


def test_send_needs_bring(client, admin_headers, week):
    shopping = _start(client, admin_headers).json()
    response = _send(client, admin_headers, shopping)
    assert response.status_code == 400 and response.json()["detail"] == "bring_not_set_up"
    client.post("/api/bring/login", json={"email": "a@b.ch", "password": "geheim"}, headers=admin_headers)
    response = _send(client, admin_headers, shopping)
    assert response.status_code == 400 and response.json()["detail"] == "bring_not_set_up"


def test_send_sends_ticked_lines_with_specs_and_deletes(client, admin_headers, week, fake_bring):
    _setup_bring(client, admin_headers)
    _start(client, admin_headers)
    shopping = client.post("/api/shopping/extras", json={"name": "WC-Papier", "amount": ""}, headers=admin_headers).json()
    hoernli = _line(shopping, "Hörnli")["key"]
    response = _send(client, admin_headers, shopping, {hoernli: "300 g", _line(shopping, "Salz")["key"]: "1 TL"})
    assert response.status_code == 200, response.text
    assert response.json() == {"sent": 2, "kept": False}
    assert fake_bring == [("fake-home", [("Hörnli", "300 g"), ("WC-Papier", "")])]
    assert _get(client, admin_headers) is None


def _drop_line(client, headers, week):
    key = _line(_get(client, headers), "Hörnli")["key"]
    client.put("/api/shopping/lines", json={"key": key, "buy": False}, headers=headers)


def _more_people(client, headers, week):
    client.patch(f"/api/plan/entries/{week['entry']['id']}", json={"people": 8}, headers=headers)


def _other_parent_unticks(client, headers, week):
    client.put(f"/api/shopping/meals/{week['entry']['id']}", json={"ticked": False}, headers=headers)


def _extra_added(client, headers, week):
    client.post("/api/shopping/extras", json={"name": "Milch", "amount": ""}, headers=headers)


@pytest.mark.parametrize("change", [_drop_line, _more_people, _other_parent_unticks, _extra_added])
def test_send_refused_when_changed(client, admin_headers, week, fake_bring, change):
    _setup_bring(client, admin_headers)
    seen = _start(client, admin_headers).json()
    change(client, admin_headers, week)
    response = _send(client, admin_headers, seen)
    assert response.status_code == 409 and response.json()["detail"] == "shopping_changed"
    assert fake_bring == []
    assert _get(client, admin_headers) is not None


def test_send_failure_keeps_list(client, admin_headers, week, fake_bring):
    _setup_bring(client, admin_headers)
    _start(client, admin_headers)
    shopping = client.post("/api/shopping/extras", json={"name": "FAIL", "amount": ""}, headers=admin_headers).json()
    response = _send(client, admin_headers, shopping)
    assert response.status_code == 502 and response.json()["detail"] == "bring_failed"
    assert _get(client, admin_headers) == shopping
    shopping = client.delete(f"/api/shopping/extras/{shopping['extras'][0]['id']}", headers=admin_headers).json()
    assert _send(client, admin_headers, shopping).status_code == 200
    assert [name for name, _ in fake_bring[-1][1]] == ["Hörnli"]


def _stored(db):
    from app import models

    db.expire_all()
    return db.get(models.BringLogin, 1)


def test_the_password_is_never_stored(client, admin_headers, db):
    """Only Bring!'s session (its tokens) is kept: a copy of the database or a backup gives away no password."""
    _setup_bring(client, admin_headers)
    login = _stored(db)
    assert login.password is None and login.access_token and login.refresh_token and login.uuid == "fake-user"


def test_a_stored_password_becomes_a_session_on_first_use(client, admin_headers, week, db, fake_bring):
    """A login from before: its password logs in once, then only the session is kept."""
    _setup_bring(client, admin_headers)
    login = _stored(db)
    login.password, login.access_token, login.refresh_token, login.expires_at = "geheim", None, None, None
    db.commit()
    assert _send(client, admin_headers, _start(client, admin_headers).json()).status_code == 200
    login = _stored(db)
    assert login.password is None and login.access_token and fake_bring


def test_an_expired_session_is_renewed(client, admin_headers, week, db, fake_bring):
    _setup_bring(client, admin_headers)
    login = _stored(db)
    login.expires_at = 0
    db.commit()
    assert _send(client, admin_headers, _start(client, admin_headers).json()).status_code == 200
    assert _stored(db).access_token == "Bearer fake-renewed" and fake_bring


def test_a_session_bring_ended_early_is_renewed_and_tried_again(client, admin_headers, week, db, fake_bring):
    _setup_bring(client, admin_headers)
    login = _stored(db)
    login.access_token = "Bearer stale"
    db.commit()
    assert _send(client, admin_headers, _start(client, admin_headers).json()).status_code == 200
    assert _stored(db).access_token == "Bearer fake-renewed" and fake_bring


def test_send_after_bring_ended_the_login_keeps_list(client, admin_headers, week, db):
    """Bring! refuses to renew the session (password changed there): log in again in the settings."""
    _setup_bring(client, admin_headers)
    login = _stored(db)
    login.refresh_token, login.expires_at = "revoked", 0
    db.commit()
    shopping = _start(client, admin_headers).json()
    response = _send(client, admin_headers, shopping)
    assert response.status_code == 502 and response.json()["detail"] == "bring_login_expired"
    assert _get(client, admin_headers) is not None


def test_extra_with_name_of_dropped_line_is_bought(client, admin_headers, week, fake_bring):
    """Out of salt: adding "Salz" buys it, although Salz is usually at home (dropped by default)."""
    _setup_bring(client, admin_headers)
    _start(client, admin_headers)
    shopping = client.post("/api/shopping/extras", json={"name": "Salz", "amount": "1 Pack"}, headers=admin_headers).json()
    assert _line(shopping, "Salz")["buy"] is True
    assert _send(client, admin_headers, shopping).status_code == 200
    assert [name for name, _ in fake_bring[0][1]] == ["Hörnli", "Salz"]


def test_change_during_send_keeps_list(client, admin_headers, week, fake_bring, monkeypatch, db):
    """The other parent adds something while Bring! is being called: the list stays, so it isn't lost."""
    from app import models

    _setup_bring(client, admin_headers)
    shopping = _start(client, admin_headers).json()
    real = bring.FakeBring.add

    def meanwhile(self, session, list_uuid, items):
        real(self, session, list_uuid, items)
        with type(db)(bind=db.get_bind()) as other:
            shopping_id = other.query(models.ShoppingList.id).scalar()
            other.add(models.ShoppingExtra(list_id=shopping_id, name="WC-Papier", amount="", position=0))
            other.commit()

    monkeypatch.setattr(bring.FakeBring, "add", meanwhile)
    response = _send(client, admin_headers, shopping)
    assert response.status_code == 200 and response.json() == {"sent": 1, "kept": True}
    kept = _get(client, admin_headers)
    assert kept is not None and _line(kept, "WC-Papier")["buy"] is True


def test_send_without_change_deletes(client, admin_headers, week, fake_bring):
    _setup_bring(client, admin_headers)
    shopping = _start(client, admin_headers).json()
    assert _send(client, admin_headers, shopping).json() == {"sent": 1, "kept": False}


def test_new_unticked_meal_does_not_block_send(client, admin_headers, week, fake_bring):
    """A meal planned meanwhile arrives unticked: it changes nothing that is sent, so the send goes through."""
    _setup_bring(client, admin_headers)
    seen = _start(client, admin_headers).json()
    create_user(client, admin_headers, "Lena")
    plan(client, login(client, "Lena"), WEEK + timedelta(days=2), recipe_id=week["recipe"]["id"])
    response = _send(client, admin_headers, seen)
    assert response.status_code == 200, response.text
    assert [name for name, _ in fake_bring[0][1]] == ["Hörnli"]


def test_empty_send_refused(client, admin_headers, week, fake_bring):
    _setup_bring(client, admin_headers)
    _start(client, admin_headers)
    shopping = client.put(f"/api/shopping/meals/{week['entry']['id']}", json={"ticked": False}, headers=admin_headers).json()
    response = _send(client, admin_headers, shopping)
    assert response.status_code == 400 and response.json()["detail"] == "shopping_empty"
    assert fake_bring == [] and _get(client, admin_headers) is not None


def test_same_tick_twice_before_commit(client, admin_headers, week, db):
    """The other parent's identical tick lands first: writing it again is no conflict."""
    from app import models, shopping_api

    _start(client, admin_headers)
    shopping = db.query(models.ShoppingList).one()
    shopping_api._tick(db, shopping, week["entry"]["id"], True)
    shopping_api._tick(db, shopping, week["entry"]["id"], True)
    db.commit()
    assert db.query(models.ShoppingMeal).count() == 1


def test_same_choice_twice_before_commit(client, admin_headers, week, db):
    from app import models, shopping_api

    _start(client, admin_headers)
    shopping = db.query(models.ShoppingList).one()
    shopping_api._choose(db, shopping, "hornli", False)
    shopping_api._choose(db, shopping, "hornli", True)
    db.commit()
    assert [(c.key, c.buy) for c in db.query(models.ShoppingChoice)] == [("hornli", True)]


def test_two_parents_start_at_once(client, admin_headers, week, monkeypatch, db):
    """Both see no list and both start one: there is still only one."""
    from app import models, shopping_api

    _start(client, admin_headers)
    monkeypatch.setattr(shopping_api, "_open", lambda db: None)
    same = _start(client, admin_headers)
    assert same.status_code == 200, same.text
    other = _start(client, admin_headers, WEEK + timedelta(days=7))
    assert other.status_code == 409 and other.json()["detail"] == "shopping_other_week"
    assert db.query(models.ShoppingList).count() == 1


def test_extras_in_the_order_added(client, admin_headers, week, db):
    from app import models

    _start(client, admin_headers)
    shopping_id = db.query(models.ShoppingList.id).scalar()
    # Inserted in reverse id order, so the rows' own order can't pass for "by id"
    for extra_id, name in ((20, "B"), (10, "A")):
        db.add(models.ShoppingExtra(id=extra_id, list_id=shopping_id, name=name, amount="", position=0))
        db.commit()
    first = _get(client, admin_headers)
    assert [e["name"] for e in first["extras"]] == ["A", "B"]
    assert _get(client, admin_headers)["version"] == first["version"]


def test_bring_login_422_does_not_echo_password(client, admin_headers):
    password = "geheim-" + "x" * 200
    response = client.post("/api/bring/login", json={"email": "a@b.ch", "password": password}, headers=admin_headers)
    assert response.status_code == 422
    assert "geheim" not in response.text


def test_send_to_a_list_that_is_gone(client, admin_headers, week, monkeypatch):
    def gone(self, session, list_uuid, items):
        raise bring.BringFailed("bring_list_gone")

    _setup_bring(client, admin_headers)
    shopping = _start(client, admin_headers).json()
    monkeypatch.setattr(bring.FakeBring, "add", gone)
    response = _send(client, admin_headers, shopping)
    assert response.status_code == 502 and response.json()["detail"] == "bring_list_gone"


def test_start_only_takes_the_one_list_conflict(client, admin_headers, week, monkeypatch, db):
    """Another failure while starting (here: a planned meal deleted meanwhile) is not taken for "a list exists"."""
    from sqlalchemy.exc import IntegrityError

    from app import models, plan, shopping_api

    real = plan.entries_in_week

    def deleted_meanwhile(db_, start):
        entries = real(db_, start)
        with type(db)(bind=db.get_bind()) as other:
            other.delete(other.get(models.PlanEntry, week["entry"]["id"]))
            other.commit()
        return entries

    monkeypatch.setattr(shopping_api, "entries_in_week", deleted_meanwhile)
    with pytest.raises(IntegrityError):
        _start(client, admin_headers)
