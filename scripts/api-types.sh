#!/usr/bin/env bash
# The frontend's types from the backend's API: writes frontend/openapi.json (the API as FastAPI describes it) and
# generates frontend/src/apiSchema.ts from it. Run after changing a schema or a route; a backend test and the
# frontend's lint fail while either is out of date.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-venv/bin/python}"
# Importing the app touches no database (main.start runs only when it starts)
"$PYTHON" -c "import json, sys; sys.path.insert(0, 'backend'); from app.main import app; print(json.dumps(app.openapi(), indent=2, ensure_ascii=False))" > frontend/openapi.json
cd frontend && npm run --silent gen-types
