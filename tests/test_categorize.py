"""The AI sorts recipes without a category (spec 2026-11-05)."""

import json

import pytest

from app import ai, models
from app.timeutil import utcnow
from helpers import create_recipe, create_user, login


@pytest.fixture
def sorter(monkeypatch):
    """The AI switched on, answering like the fake: "main" for every recipe sent (plus junk to be ignored)."""
    monkeypatch.setenv("INFOMANIAK_AI_TOKEN", "t")
    monkeypatch.setenv("INFOMANIAK_AI_PRODUCT_ID", "p")
    monkeypatch.setenv("AI_FAKE", "1")
    sent: list[list[dict]] = []
    real = ai.categorize

    def recording(client, recipes):
        sent.append(recipes)
        return real(client, recipes)

    monkeypatch.setattr(ai, "categorize", recording)
    return sent


def _post(client, headers, **body):
    return client.post("/api/recipes/categorize", json=body, headers=headers)


def _categories(client, headers, recipe):
    return client.get(f"/api/recipes/{recipe['id']}", headers=headers).json()["categories"]


def test_batch_fills_untried(client, admin_headers, sorter, db):
    a = create_recipe(client, admin_headers, "A", tags=["vegi"])
    b = create_recipe(client, admin_headers, "B", categories=["dessert"])
    c = create_recipe(client, admin_headers, "C")
    assert client.get("/api/recipes/categorize", headers=admin_headers).json() == {"remaining": 2}
    response = _post(client, admin_headers)
    assert response.status_code == 200, response.text
    assert response.json() == {"categorized": 2, "remaining": 0}
    assert [_categories(client, admin_headers, r) for r in (a, b, c)] == [["main"], ["dessert"], ["main"]]
    assert client.get("/api/recipes/categorize", headers=admin_headers).json() == {"remaining": 0}
    assert [(call.purpose, call.user_id is not None) for call in db.query(models.AiCall)] == [("categorize", True)]
    assert [r["title"] for r in sorter[0]] == ["A", "C"]
    assert sorter[0][0]["tags"] == ["vegi"] and sorter[0][0]["ingredients"] == ["Hörnli"]


def test_only_title_tags_and_ingredient_names_sent(client, admin_headers, sorter):
    many = [{"amount": n + 1, "unit": "g", "name": f"Zutat {n}", "note": "geheim"} for n in range(20)]
    create_recipe(client, admin_headers, "A", ingredients=many, steps=["Geheimer Schritt"], notes="Notiz")
    _post(client, admin_headers)
    sent = sorter[0][0]
    assert set(sent) == {"id", "title", "tags", "ingredients"}
    assert sent["ingredients"] == [f"Zutat {n}" for n in range(15)]


def test_batch_size(client, admin_headers, sorter):
    for n in range(30):
        create_recipe(client, admin_headers, f"R{n}")
    assert _post(client, admin_headers).json() == {"categorized": 25, "remaining": 5}
    assert _post(client, admin_headers).json() == {"categorized": 5, "remaining": 0}


def test_unknown_ids_and_keys_ignored(client, admin_headers, monkeypatch):
    monkeypatch.setenv("INFOMANIAK_AI_TOKEN", "t")
    monkeypatch.setenv("INFOMANIAK_AI_PRODUCT_ID", "p")
    other = create_recipe(client, admin_headers, "Schon tot")
    r = create_recipe(client, admin_headers, "A")
    client.delete(f"/api/recipes/{other['id']}", headers=admin_headers)
    answer = {str(r["id"]): ["pizza", "soup"], str(other["id"]): ["main"], "999999": ["main"], "x": "y"}
    monkeypatch.setattr(ai, "client_for", lambda s: type("C", (), {"complete": lambda self, c: ai.Answer(json.dumps(answer), 5)})())
    assert _post(client, admin_headers).json() == {"categorized": 1, "remaining": 0}
    assert _categories(client, admin_headers, r) == ["soup"]
    assert client.get(f"/api/recipes/{other['id']}", headers=admin_headers).json()["categories"] == []


def test_not_sent_again(client, admin_headers, sorter, monkeypatch):
    r = create_recipe(client, admin_headers, "Rätsel")
    # The AI names the recipe, but finds no category for it
    monkeypatch.setattr(ai, "categorize", lambda client, recipes: (sorter.append(recipes) or {r["id"]: []}, 3))
    assert _post(client, admin_headers).json() == {"categorized": 0, "remaining": 0}
    assert _categories(client, admin_headers, r) == []
    assert _post(client, admin_headers).json() == {"categorized": 0, "remaining": 0}
    assert len(sorter) == 1


def test_empty_batch_no_call(client, admin_headers, sorter, db):
    create_recipe(client, admin_headers, "A", categories=["main"])
    assert _post(client, admin_headers).json() == {"categorized": 0, "remaining": 0}
    assert sorter == [] and db.query(models.AiCall).count() == 0


def test_edited_meanwhile_not_overwritten(client, admin_headers, sorter, monkeypatch, db):
    r = create_recipe(client, admin_headers, "A")

    def meanwhile(client_, recipes):
        with type(db)(bind=db.get_bind()) as other:
            other.get(models.Recipe, r["id"]).categories = ["soup"]
            other.commit()
        return {r["id"]: ["main"]}, 3

    monkeypatch.setattr(ai, "categorize", meanwhile)
    assert _post(client, admin_headers).json() == {"categorized": 0, "remaining": 0}
    assert _categories(client, admin_headers, r) == ["soup"]


def test_single_recipe_ignores_tried(client, admin_headers, sorter, db):
    r = create_recipe(client, admin_headers, "A")
    db.get(models.Recipe, r["id"]).ai_categorized_at = utcnow()
    db.commit()
    assert client.get("/api/recipes/categorize", headers=admin_headers).json() == {"remaining": 0}
    assert _post(client, admin_headers, recipe_id=r["id"]).json() == {"categorized": 1, "remaining": 0}
    assert _categories(client, admin_headers, r) == ["main"]
    again = _post(client, admin_headers, recipe_id=r["id"])
    assert again.status_code == 400 and again.json()["detail"] == "already_categorized"


def test_single_recipe_must_exist(client, admin_headers, sorter):
    r = create_recipe(client, admin_headers, "A")
    client.delete(f"/api/recipes/{r['id']}", headers=admin_headers)
    assert _post(client, admin_headers, recipe_id=r["id"]).status_code == 404
    assert _post(client, admin_headers, recipe_id=424242).status_code == 404


def test_failed_answer_marks_nothing(client, admin_headers, sorter, monkeypatch):
    r = create_recipe(client, admin_headers, "A")

    def failing(client_, recipes):
        raise ai.AiFailed("garbage")

    monkeypatch.setattr(ai, "categorize", failing)
    response = _post(client, admin_headers)
    assert response.status_code == 502 and response.json()["detail"] == "categorize_failed"
    assert client.get("/api/recipes/categorize", headers=admin_headers).json() == {"remaining": 1}
    assert _categories(client, admin_headers, r) == []


def test_garbage_answer_fails():
    class Garbage:
        def complete(self, content):
            return ai.Answer("Das sind Hauptgerichte.", 1)

    with pytest.raises(ai.AiFailed):
        ai.categorize(Garbage(), [{"id": 1, "title": "A", "tags": [], "ingredients": []}])


def test_children_refused(client, admin_headers, sorter):
    create_user(client, admin_headers, "Lena")
    kid = login(client, "Lena", "5678")
    assert _post(client, kid).status_code == 403
    assert client.get("/api/recipes/categorize", headers=kid).status_code == 403


def test_ai_off(client, admin_headers):
    create_recipe(client, admin_headers, "A")
    response = _post(client, admin_headers)
    assert response.status_code == 503 and response.json()["detail"] == "ai_off"


def test_hourly_limit(client, admin_headers, sorter, monkeypatch):
    monkeypatch.setenv("AI_CALLS_PER_HOUR", "1")
    for n in range(30):
        create_recipe(client, admin_headers, f"R{n}")
    assert _post(client, admin_headers).status_code == 200
    response = _post(client, admin_headers)
    assert response.status_code == 429 and response.json()["detail"]["code"] == "ai_limit"
    assert client.get("/api/recipes/categorize", headers=admin_headers).json() == {"remaining": 5}


@pytest.mark.parametrize(
    "answer",
    [{"recipes": [{"id": 1, "categories": ["main"]}]}, {"id 1": ["main"]}, {}],
)
def test_answer_naming_no_asked_recipe_fails(client, admin_headers, monkeypatch, answer):
    """An answer that names none of the recipes sent is a failed answer, not "found nothing for all of them"."""
    monkeypatch.setenv("INFOMANIAK_AI_TOKEN", "t")
    monkeypatch.setenv("INFOMANIAK_AI_PRODUCT_ID", "p")
    create_recipe(client, admin_headers, "A")
    create_recipe(client, admin_headers, "B")
    monkeypatch.setattr(ai, "client_for", lambda s: type("C", (), {"complete": lambda self, c: ai.Answer(json.dumps(answer), 5)})())
    response = _post(client, admin_headers)
    assert response.status_code == 502 and response.json()["detail"] == "categorize_failed"
    assert client.get("/api/recipes/categorize", headers=admin_headers).json() == {"remaining": 2}
