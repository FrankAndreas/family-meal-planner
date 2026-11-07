#!/usr/bin/env bash
# The frontend's types from the backend's API: writes frontend/openapi.json (the API as FastAPI describes it) and
# generates frontend/src/apiSchema.ts from it. Run after changing a schema or a route; a backend test and the
# frontend's lint fail while either is out of date.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-venv/bin/python}"
# Importing the app touches no database (main.start runs only when it starts)
# Written to a temporary file first, so a failing import leaves the snapshot as it was
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
"$PYTHON" -c "import json, sys; sys.path.insert(0, 'backend'); from app.main import app; print(json.dumps(app.openapi(), indent=2, ensure_ascii=False))" > "$tmp"
mv "$tmp" frontend/openapi.json
cd frontend && npm run --silent gen-types
