# Browser tests

Playwright starts its own family hub (port 8130, from a family-hub checkout next to this repo or `HUB_DIR`; Admin PIN
`1111`), backend (port 8100, fresh SQLite database in `e2e/.tmp`, `DEFAULT_LANGUAGE=en`) and frontend (port 3100), so
dev servers and their data are never touched. `HUB_PYTHON` is the Python with the hub's packages (default
`E2E_PYTHON`).

```bash
cd e2e
npm install
npx playwright install chromium
E2E_PYTHON=../venv/bin/python HUB_PYTHON=../../family-hub/.superpowers/venv/bin/python npm test
```

`E2E_PYTHON` is the Python that has the backend's packages (the repo's `venv`). Projects: `tablet` (1180×820,
the iPad used for planning) runs everything; `phone` runs the login tests.
