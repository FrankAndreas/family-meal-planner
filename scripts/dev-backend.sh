#!/bin/bash
# Start the backend locally on port 8000 (Vite forwards /api there), with its database in backend/data.
set -euo pipefail
cd "$(dirname "$0")/../backend"
# Logins come from a family hub running locally (family-hub: scripts/dev-backend.sh, port 8086)
export HUB_URL="${HUB_URL:-http://localhost:8086}"
exec ../venv/bin/uvicorn app.main:app --reload "$@"
