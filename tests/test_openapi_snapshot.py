"""The frontend's types are generated from frontend/openapi.json (frontend/src/apiSchema.ts): that file must be the
backend's API as it is, else the types drift from what the backend sends."""

import json
from pathlib import Path

from app.main import app

SNAPSHOT = Path(__file__).resolve().parents[1] / "frontend" / "openapi.json"


def test_the_frontends_api_snapshot_is_up_to_date():
    assert SNAPSHOT.is_file(), "Run scripts/api-types.sh"
    assert json.loads(SNAPSHOT.read_text()) == app.openapi(), "The API changed: run scripts/api-types.sh"
