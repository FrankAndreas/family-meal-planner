import json

import pytest

from app import ai, models
from helpers import create_recipe, create_user, login


@pytest.fixture
def translator(monkeypatch):
    monkeypatch.setenv("INFOMANIAK_AI_TOKEN", "t")
    monkeypatch.setenv("INFOMANIAK_AI_PRODUCT_ID", "p")
    answers = []

    class Translator:
        def complete(self, content):
            data = json.loads(content[0]["text"].split(ai.TRANSLATE_MARKER, 1)[1])
            data = answers.pop(0)(data) if answers else {
                "title": "Pfannkuchen",
                "ingredients": [{"name": "Mehl", "note": "gesiebt"}, {"name": "Milch", "note": ""}],
                "steps": ["Alles verrühren."],
                "notes": "",
            }
            return ai.Answer(json.dumps(data), 77)

    monkeypatch.setattr(ai, "client_for", lambda settings: Translator())
    return answers


def _english(client, headers):
    return create_recipe(
        client,
        headers,
        "Pancakes",
        language="en",
        ingredients=[
            {"amount": 200, "unit": "g", "name": "flour", "note": "sifted"},
            {"amount": 3, "unit": "dl", "name": "milk"},
        ],
        steps=["Mix everything."],
    )


def test_translate_keeps_amounts_and_original(client, admin_headers, translator, db):
    r = _english(client, admin_headers)
    out = client.post(f"/api/recipes/{r['id']}/translate", headers=admin_headers)
    assert out.status_code == 200, out.text
    got = out.json()
    assert got["title"] == "Pfannkuchen" and got["language"] == "de" and got["steps"] == ["Alles verrühren."]
    assert [(i["amount"], i["unit"], i["name"], i["note"]) for i in got["ingredients"]] == [
        (200, "g", "Mehl", "gesiebt"),
        (3, "dl", "Milch", ""),
    ]
    assert got["original"]["title"] == "Pancakes" and got["original"]["language"] == "en"
    assert got["original"]["ingredients"][0] == {"name": "flour", "note": "sifted"}
    call = db.query(models.AiCall).one()
    assert call.purpose == "translate" and call.recipe_id == r["id"] and call.tokens == 77


def test_second_translation_keeps_first_original(client, admin_headers, translator):
    r = _english(client, admin_headers)
    client.post(f"/api/recipes/{r['id']}/translate", headers=admin_headers)
    client.put(f"/api/recipes/{r['id']}", json={**{k: r[k] for k in ("title", "servings", "steps", "tags")}, "ingredients": [
        {"amount": 200, "unit": "g", "name": "flour"}, {"amount": 3, "unit": "dl", "name": "milk"}], "language": "en"}, headers=admin_headers)
    again = client.post(f"/api/recipes/{r['id']}/translate", headers=admin_headers).json()
    assert again["original"]["title"] == "Pancakes"


def test_ingredient_count_must_match(client, admin_headers, translator):
    r = _english(client, admin_headers)
    translator.append(lambda data: {**data, "ingredients": data["ingredients"][:1]})
    response = client.post(f"/api/recipes/{r['id']}/translate", headers=admin_headers)
    assert response.status_code == 502 and response.json()["detail"] == "ai_failed"
    assert client.get(f"/api/recipes/{r['id']}", headers=admin_headers).json()["title"] == "Pancakes"


def test_already_german(client, admin_headers, translator):
    r = create_recipe(client, admin_headers, language="de")
    response = client.post(f"/api/recipes/{r['id']}/translate", headers=admin_headers)
    assert response.status_code == 400 and response.json()["detail"] == "already_german"


def test_parents_only(client, admin_headers, translator):
    r = _english(client, admin_headers)
    create_user(client, admin_headers, "Lena")
    assert client.post(f"/api/recipes/{r['id']}/translate", headers=login(client, "Lena", "5678")).status_code == 403


def test_ai_off(client, admin_headers, monkeypatch):
    r = _english(client, admin_headers)
    response = client.post(f"/api/recipes/{r['id']}/translate", headers=admin_headers)
    assert response.status_code == 503 and response.json()["detail"] == "ai_off"
