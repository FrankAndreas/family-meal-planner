"""The AI (Infomaniak's OpenAI-compatible service, as in family-budget-dashboard): reading recipes from mails and
pages, translating them. Only parents start it, each call counts against an hourly limit and stays in the usage
log. The answer is untrusted: it becomes a draft a person checks.

The token and product ID come from the environment and never appear in a response or a log line."""

import base64
import io
import json
import logging
import math
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from fastapi import APIRouter, Depends
from PIL import Image, ImageOps
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import auth, config, models, photos  # noqa: F401  (photos: HEIC opener)
from .database import get_db
from .errors import api_error
from .timeutil import utcnow
from .units import UNITS

router = APIRouter(tags=["ai"])
logger = logging.getLogger(__name__)

DEFAULT_MODEL = "google/gemma-4-31B-it"
DEFAULT_CALLS_PER_HOUR = 30
TIMEOUT_SECONDS = 90
ENDPOINT = "/chat/completions"
IMAGE_SIDE = 2000
MAX_INGREDIENTS = 100
MAX_STEPS = 60
MAX_TEXT = 20_000
# Pictures per call: a long Facebook recipe fits in a few screenshots; more only costs
MAX_IMAGES = 10


@dataclass(frozen=True)
class Settings:
    token: str
    product_id: str
    model: str
    calls_per_hour: int

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.product_id and self.calls_per_hour > 0)

    @classmethod
    def from_env(cls) -> "Settings":
        try:
            calls = int(config.env("AI_CALLS_PER_HOUR") or DEFAULT_CALLS_PER_HOUR)
        except ValueError:
            calls = DEFAULT_CALLS_PER_HOUR
        return cls(
            token=config.env("INFOMANIAK_AI_TOKEN"),
            product_id=config.env("INFOMANIAK_AI_PRODUCT_ID"),
            model=config.env("AI_MODEL") or DEFAULT_MODEL,
            calls_per_hour=calls,
        )


@dataclass
class Answer:
    text: str
    tokens: int | None = None


class AiFailed(Exception):
    """No usable answer: the service was down, or answered something that isn't a recipe."""


class AiClient(Protocol):
    def complete(self, content: list[dict]) -> Answer: ...


class InfomaniakClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def complete(self, content: list[dict]) -> Answer:
        base = f"https://api.infomaniak.com/2/ai/{self.settings.product_id}/openai/v1"
        body = {"model": self.settings.model, "temperature": 0, "messages": [{"role": "user", "content": content}]}
        request = urllib.request.Request(
            base + ENDPOINT,
            data=json.dumps(body).encode(),
            method="POST",
            headers={"Authorization": f"Bearer {self.settings.token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                answer = json.load(response)
            tokens = (answer.get("usage") or {}).get("total_tokens")
            return Answer(str(answer["choices"][0]["message"]["content"]), tokens if isinstance(tokens, int) else None)
        except urllib.error.HTTPError as error:
            # Neither the URL (product ID) nor the error body goes into the log
            logger.warning("AI service %s answered HTTP %s", ENDPOINT, error.code)
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            logger.warning("AI service %s not reachable: %s", ENDPOINT, type(error).__name__)
        except (ValueError, KeyError, IndexError, TypeError):
            logger.warning("AI service %s sent an unexpected answer", ENDPOINT)
        raise AiFailed(ENDPOINT)


TRANSLATE_MARKER = "TRANSLATE:"


class FakeClient:
    """Fixed answers for the browser tests (AI_FAKE=1); never used in production."""

    def complete(self, content: list[dict]) -> Answer:
        question = content[0].get("text", "") if content else ""
        if TRANSLATE_MARKER in question:
            data = json.loads(question.split(TRANSLATE_MARKER, 1)[1])
            data["title"] = "DE " + data["title"]
            return Answer(json.dumps(data), 50)
        return Answer(
            json.dumps(
                {
                    "title": "Fake-Risotto",
                    "servings": 4,
                    "servings_unit": None,
                    "prep_minutes": 10,
                    "cook_minutes": 25,
                    "ingredients": [
                        {"amount": 300, "unit": "g", "name": "Risottoreis", "note": ""},
                        {"amount": 1, "unit": "l", "name": "Bouillon", "note": ""},
                    ],
                    "steps": ["Reis andünsten.", "Bouillon nach und nach beigeben."],
                    "tags": ["vegi"],
                    "uncertain": ["1 l oder 1,2 l Bouillon?"],
                    "image_index": 0,
                    "language": "de",
                }
            ),
            321,
        )


def client_for(settings: Settings) -> AiClient:
    if config.env("AI_FAKE") == "1":
        return FakeClient()
    return InfomaniakClient(settings)


def _calls_last_hour(db: Session, user: models.User, now) -> list:
    return (
        db.query(models.AiCall.at)
        .filter(models.AiCall.user_id == user.id, models.AiCall.at > now - timedelta(hours=1))
        .order_by(models.AiCall.at)
        .all()
    )


def take_call(db: Session, user: models.User, purpose: str, item_id: int | None = None, recipe_id: int | None = None):
    """Count one AI call for the person, or refuse: AI off (503), or the last hour's calls used up (429)."""
    settings = Settings.from_env()
    if not settings.enabled:
        raise api_error(503, "ai_off")
    now = utcnow()
    calls = _calls_last_hour(db, user, now)
    if len(calls) >= settings.calls_per_hour:
        minutes = max(1, math.ceil((calls[0].at + timedelta(hours=1) - now).total_seconds() / 60))
        raise api_error(429, "ai_limit", minutes=minutes)
    call = models.AiCall(user_id=user.id, at=now, purpose=purpose, item_id=item_id, recipe_id=recipe_id)
    db.add(call)
    db.commit()
    return call


RECIPE_PROMPT = """Du liest ein Kochrezept aus einer Mail, einem Bildschirmfoto (z. B. Facebook) oder einer Webseite.
Antworte NUR mit einem JSON-Objekt, ohne Text davor oder danach:
{{"title": str, "servings": Zahl, "servings_unit": null oder Wort (z. B. "Blech", "Stück"; null heisst Personen),
 "prep_minutes": Zahl oder null, "cook_minutes": Zahl oder null,
 "ingredients": [{{"amount": Zahl oder null, "unit": eine von {units} oder null, "name": str, "note": str}}],
 "steps": [str], "tags": [str], "uncertain": [str], "image_index": Zahl oder null, "language": "de" oder "en"}}
Regeln:
- Übernimm das Rezept in seiner Sprache, übersetze nichts.
- Der Titel ist der des Rezepts, nicht der Betreff der Mail.
- Unbekannte Mengen: null. Einheiten nur aus der Liste, sonst null und das Wort in "note".
- Schreibe in "uncertain" kurz (auf Deutsch) jede Angabe, die du nicht sicher lesen konntest, z. B. "200 g oder 250 g Mehl?".
- image_index: welches der Bilder (ab 0) das fertige Gericht zeigt, sonst null.
- Wenn kein Rezept darin ist: {{"title": ""}}.

Inhalt:
"""


def _image_part(data: bytes) -> dict | None:
    try:
        with Image.open(io.BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
    except Exception:
        return None
    # As sharp as the service sensibly takes: small text in screenshots must stay readable
    image.thumbnail((IMAGE_SIDE, IMAGE_SIDE))
    out = io.BytesIO()
    image.save(out, "JPEG", quality=90)
    return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()}}


def _json(answer: str):
    text = answer.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise AiFailed("no json")
        try:
            return json.loads(text[start : end + 1])
        except ValueError as error:
            raise AiFailed("no json") from error


def _str(value, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit] if not isinstance(value, (dict, list)) else ""


def _list(value) -> list:
    """What the AI should have sent as a list: a lone string counts as one item, anything else as none."""
    if isinstance(value, list):
        return value
    return [value] if isinstance(value, str) and value.strip() else []


def _number(value, low: float, high: float) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if low < number <= high else None


def validate_draft(answer: str) -> dict:
    data = _json(answer)
    if not isinstance(data, dict) or not _str(data.get("title"), 200):
        raise AiFailed("no recipe")
    ingredients = []
    for item in _list(data.get("ingredients"))[:MAX_INGREDIENTS]:
        if not isinstance(item, dict) or not _str(item.get("name"), 200):
            continue
        unit = item.get("unit")
        note = _str(item.get("note"), 200)
        if unit is not None and unit not in UNITS:
            note = ", ".join(n for n in (_str(unit, 30), note) if n)[:200]
            unit = None
        ingredients.append(
            {"amount": _number(item.get("amount"), 0, 100_000), "unit": unit, "name": _str(item.get("name"), 200), "note": note}
        )
    image_index = data.get("image_index")
    servings_unit = _str(data.get("servings_unit"), 30) or None
    language = data.get("language")
    minutes = {key: _number(data.get(key), -1, 1440) for key in ("prep_minutes", "cook_minutes")}
    return {
        "title": _str(data["title"], 200),
        "servings": _number(data.get("servings"), 0, 100) or 4,
        "servings_unit": servings_unit,
        "prep_minutes": int(minutes["prep_minutes"]) if minutes["prep_minutes"] is not None else None,
        "cook_minutes": int(minutes["cook_minutes"]) if minutes["cook_minutes"] is not None else None,
        "ingredients": ingredients,
        "steps": [s for s in (_str(step, 2000) for step in _list(data.get("steps"))[:MAX_STEPS]) if s],
        "tags": [t for t in (_str(tag, 40) for tag in _list(data.get("tags"))[:5]) if t],
        "notes": _str(data.get("notes"), 2000),
        "uncertain": [u for u in (_str(x, 200) for x in _list(data.get("uncertain"))[:20]) if u],
        "image_index": image_index if isinstance(image_index, int) and not isinstance(image_index, bool) else None,
        "language": language if language in ("de", "en") else None,
    }


def recipe_from_ai(
    client: AiClient, *, text: str, images: list[bytes] = ()
) -> tuple[dict, str, int | None, list[int]]:
    """The draft, the raw answer (kept as part of the original), the tokens the service reported, and which of the
    given images were sent (positions): the AI's image_index counts only those."""
    content = [{"type": "text", "text": RECIPE_PROMPT.format(units=", ".join(UNITS)) + text[:MAX_TEXT]}]
    sent: list[int] = []
    for position, data in enumerate(images):
        part = _image_part(data)
        if part and len(sent) < MAX_IMAGES:
            content.append(part)
            sent.append(position)
    answer = client.complete(content)
    return validate_draft(answer.text), answer.text, answer.tokens, sent


@router.get("/ai/status")
def ai_status(user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    settings = Settings.from_env()
    left = max(0, settings.calls_per_hour - len(_calls_last_hour(db, user, utcnow()))) if settings.enabled else 0
    return {"enabled": settings.enabled, "calls_left_this_hour": left}


@router.get("/ai/usage")
def ai_usage(_parent: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)):
    """AI calls this month per person, and all calls ever (the costs themselves are in Infomaniak's manager)."""
    now = utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    rows = (
        db.query(models.User.name, func.count(models.AiCall.id))
        .join(models.User, models.User.id == models.AiCall.user_id)
        .filter(models.AiCall.at >= month_start)
        .group_by(models.User.name)
        .order_by(models.User.name)
        .all()
    )
    return {"month": [{"user_name": name, "calls": calls} for name, calls in rows], "total": db.query(models.AiCall).count()}


TRANSLATE_PROMPT = """Übersetze dieses Kochrezept ins Deutsche (Schweizer Rechtschreibung: ss statt ß).
Antworte NUR mit demselben JSON, in derselben Form: gleich viele Zutaten in derselben Reihenfolge, gleich viele
Schritte. Übersetze title, name, note, steps und notes; erfinde nichts dazu.
"""


def translate(client: AiClient, text: dict) -> tuple[dict, int | None]:
    """The recipe's text in German: {title, ingredients: [{name, note}], steps, notes}, the same shape as given."""
    answer = client.complete([{"type": "text", "text": TRANSLATE_PROMPT + TRANSLATE_MARKER + json.dumps(text, ensure_ascii=False)}])
    data = _json(answer.text)
    if (
        not isinstance(data, dict)
        or not _str(data.get("title"), 200)
        or not isinstance(data.get("ingredients"), list)
        or len(data["ingredients"]) != len(text["ingredients"])
        or not isinstance(data.get("steps"), list)
        or len(data["steps"]) != len(text["steps"])
    ):
        raise AiFailed("translation doesn't fit the recipe")
    return (
        {
            "title": _str(data["title"], 200),
            "ingredients": [
                {"name": _str(i.get("name"), 200) or old["name"], "note": _str(i.get("note"), 200)}
                if isinstance(i, dict)
                else old
                for i, old in zip(data["ingredients"], text["ingredients"])
            ],
            "steps": [_str(step, 2000) or old for step, old in zip(data["steps"], text["steps"])],
            "notes": str(data.get("notes") or "")[:10_000],
        },
        answer.tokens,
    )
