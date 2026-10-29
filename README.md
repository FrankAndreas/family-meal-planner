# Meal Planner

Plan the family's meals on Friday, keep a recipe collection, and see what you ate when. Self-hosted on a NAS, a
sibling of family-budget-dashboard and family-job-tracking (same stack, look and login). German by default, English
per person.

- Design: [`docs/superpowers/specs/2026-10-29-meal-planner-design.md`](docs/superpowers/specs/2026-10-29-meal-planner-design.md)
- Deployment on the NAS: [`README_DOCKER.md`](README_DOCKER.md)

## Development

```bash
python3 -m venv venv
venv/bin/pip install -r backend/requirements.txt -r tests/requirements.txt
scripts/dev-backend.sh                 # API on :8000, Admin PIN 1111, database in backend/data
cd frontend && npm install && npm run dev   # app on :5173, /api forwarded to :8000
```

## Tests

```bash
venv/bin/pytest                         # backend
cd frontend && npm run lint && npm run build
cd e2e && E2E_PYTHON=../venv/bin/python npm test   # browser tests, see e2e/README.md
```

Visible texts live in `frontend/src/locales/{de,en}.ts`; `npm run lint` fails on text written directly in components.
