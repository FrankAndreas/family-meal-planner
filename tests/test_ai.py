import json
import logging
import urllib.error
from datetime import timedelta

import pytest
from fastapi import HTTPException

from app import ai, models
from app.timeutil import utcnow
from helpers import create_user, login


@pytest.fixture
def ai_on(monkeypatch):
    monkeypatch.setenv("INFOMANIAK_AI_TOKEN", "tok-secret")
    monkeypatch.setenv("INFOMANIAK_AI_PRODUCT_ID", "prod-4711")
    monkeypatch.setenv("AI_CALLS_PER_HOUR", "2")


def _admin(db):
    return db.query(models.User).filter_by(name="Admin").one()


def test_off_without_token(db):
    with pytest.raises(HTTPException) as caught:
        ai.take_call(db, _admin(db), "import")
    assert caught.value.status_code == 503 and caught.value.detail == "ai_off"


def test_hourly_limit(db, ai_on):
    admin = _admin(db)
    ai.take_call(db, admin, "import", item_id=1)
    ai.take_call(db, admin, "translate", recipe_id=2)
    with pytest.raises(HTTPException) as caught:
        ai.take_call(db, admin, "import")
    assert caught.value.status_code == 429
    assert caught.value.detail["code"] == "ai_limit" and 1 <= caught.value.detail["minutes"] <= 60
    assert db.query(models.AiCall).count() == 2


def test_old_calls_dont_count(db, ai_on):
    admin = _admin(db)
    db.add_all([models.AiCall(user_id=admin.id, at=utcnow() - timedelta(hours=2), purpose="import") for _ in range(5)])
    db.commit()
    ai.take_call(db, admin, "import")


def test_zero_turns_it_off(db, ai_on, monkeypatch):
    monkeypatch.setenv("AI_CALLS_PER_HOUR", "0")
    with pytest.raises(HTTPException) as caught:
        ai.take_call(db, _admin(db), "import")
    assert caught.value.detail == "ai_off"


def test_status_and_usage(client, admin_headers, db, ai_on):
    lena = create_user(client, admin_headers, "Lena")
    ai.take_call(db, _admin(db), "import")
    db.add(models.AiCall(user_id=lena["id"], at=utcnow(), purpose="import"))
    db.add(models.AiCall(user_id=lena["id"], at=utcnow() - timedelta(days=40), purpose="import"))
    db.commit()
    assert client.get("/api/ai/status", headers=admin_headers).json() == {"enabled": True, "calls_left_this_hour": 1}
    usage = client.get("/api/ai/usage", headers=admin_headers).json()
    assert usage == {"month": [{"user_name": "Admin", "calls": 1}, {"user_name": "Lena", "calls": 1}], "total": 3}
    assert client.get("/api/ai/usage", headers=login(client, "Lena", "5678")).status_code == 403


GOOD = {
    "title": "Risotto",
    "servings": 4,
    "servings_unit": None,
    "ingredients": [{"amount": 300, "unit": "g", "name": "Reis", "note": ""}],
    "steps": ["Kochen"],
    "tags": ["vegi"],
    "uncertain": ["300 g oder 350 g Reis?"],
    "image_index": 1,
    "language": "de",
}


def test_valid_answer():
    draft = ai.validate_draft(json.dumps(GOOD))
    assert draft["title"] == "Risotto" and draft["uncertain"] == ["300 g oder 350 g Reis?"] and draft["image_index"] == 1


def test_fenced_json_accepted():
    assert ai.validate_draft("Hier:\n```json\n" + json.dumps(GOOD) + "\n```")["title"] == "Risotto"


@pytest.mark.parametrize("answer", ["Ich habe leider kein Rezept gefunden.", '{"title": "Ris', "[]", json.dumps({**GOOD, "title": ""})])
def test_garbage_fails(answer):
    with pytest.raises(ai.AiFailed):
        ai.validate_draft(answer)


def test_unknown_unit_becomes_note():
    answer = {**GOOD, "ingredients": [{"amount": 2, "unit": "cups", "name": "Mehl", "note": "gesiebt"}]}
    assert ai.validate_draft(json.dumps(answer))["ingredients"][0] == {
        "amount": 2,
        "unit": None,
        "name": "Mehl",
        "note": "cups, gesiebt",
    }


def test_sizes_capped_and_values_cleaned():
    answer = {
        **GOOD,
        "servings": -3,
        "ingredients": [{"amount": -1, "unit": "g", "name": f"Zutat {n}"} for n in range(500)],
        "steps": ["<script>alert(1)</script>"] * 80,
        "image_index": "zwei",
    }
    draft = ai.validate_draft(json.dumps(answer))
    assert len(draft["ingredients"]) == 100 and draft["ingredients"][0]["amount"] is None
    assert len(draft["steps"]) == 60 and draft["steps"][0] == "<script>alert(1)</script>"
    assert draft["servings"] == 4 and draft["image_index"] is None


def test_client_error_hides_secrets(monkeypatch, ai_on, caplog):
    def refuse(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, "no", {}, None)

    monkeypatch.setattr(ai.urllib.request, "urlopen", refuse)
    client = ai.InfomaniakClient(ai.Settings.from_env())
    with caplog.at_level(logging.WARNING), pytest.raises(ai.AiFailed):
        client.complete([{"type": "text", "text": "hi"}])
    assert "prod-4711" not in caplog.text and "tok-secret" not in caplog.text


def test_recipe_from_ai_sends_text_and_images():
    seen = {}

    class Recorder:
        def complete(self, content):
            seen["content"] = content
            return ai.Answer(json.dumps(GOOD), 1234)

    from mails import png

    draft, raw, tokens, sent = ai.recipe_from_ai(Recorder(), text="Risotto für 4", images=[png(size=(4000, 3000)), png()])
    kinds = [part["type"] for part in seen["content"]]
    assert kinds == ["text", "image_url", "image_url"] and "Risotto für 4" in seen["content"][0]["text"]
    assert sent == [0, 1] and draft["title"] == "Risotto" and tokens == 1234 and json.loads(raw)["title"] == "Risotto"


def test_strings_where_lists_belong():
    answer = {**GOOD, "tags": "vegi", "steps": "Reis andünsten. Dann Bouillon.", "uncertain": "Menge?", "ingredients": {"x": 1}}
    draft = ai.validate_draft(json.dumps(answer))
    assert draft["tags"] == ["vegi"] and draft["steps"] == ["Reis andünsten. Dann Bouillon."]
    assert draft["uncertain"] == ["Menge?"] and draft["ingredients"] == []
