# Browser tests

Playwright starts its own backend (port 8100, fresh SQLite database in `e2e/.tmp`, Admin PIN `1111`,
`DEFAULT_LANGUAGE=en`) and frontend (port 3100), so dev servers and their data are never touched.

```bash
cd e2e
npm install
npx playwright install chromium
E2E_PYTHON=../venv/bin/python npm test
```

`E2E_PYTHON` is the Python that has the backend's packages (the repo's `venv`). Projects: `tablet` (1180×820,
the iPad used for planning) runs everything; `phone` runs the login tests.
