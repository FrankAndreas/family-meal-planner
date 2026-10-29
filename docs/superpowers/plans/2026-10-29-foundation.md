# Meal Planner — Plan 1: Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A deployable, empty meal planner: PIN login with PARENT/CHILD roles, family members and family settings
(family size, first day of the week), German/English UI in the Aurora theme, Docker images, CI and NAS docs.

**Architecture:** FastAPI + SQLAlchemy + SQLite with Alembic migrations, served behind nginx with a React/Vite SPA.
The backend is modelled on family-job-tracking (lean modules, `config.env()`, single settings row) and the
frontend on family-job-tracking's skeleton plus family-budget-dashboard's i18n, Aurora theme, text check and
Playwright setup. Later plans (2 Recipes, 3 Planner, 4 Import) build on the interfaces defined here.

**Tech Stack:** Python 3.14, FastAPI 0.162, SQLAlchemy 2.1, Alembic 1.20, bcrypt 5, PyJWT 2.15, pytest; React 19,
Vite 8, TypeScript 5.9, Tailwind 4, i18next 26 / react-i18next 17, axios, react-router 7; Playwright 1.63; Docker,
nginx-unprivileged, GitHub Actions → GHCR.

**Spec:** `docs/superpowers/specs/2026-10-29-meal-planner-design.md`

Reference apps (read, copy, adapt — never import from them):
- `JT` = `/home/andreas/work/family-job-tracking`
- `FB` = `/home/andreas/work/family-budget-dashboard`

## Global Constraints

- German is the default UI language, English optional, per person; `DEFAULT_LANGUAGE` in `.env` (`de`|`en`, default `de`).
- German texts: Swiss spelling (ss, never ß), informal "du".
- Visible frontend text only from `src/locales/{de,en}.ts`; `npm run lint` runs `check-texts` (copied from FB).
- Roles: `PARENT`, `CHILD`. Settings and family management are parent-only.
- PIN: exactly 4 digits. First parent "Admin" on an empty database; PIN from `INITIAL_ADMIN_PIN` or random, logged once.
- Backend errors carry a **code**, never prose: `detail` is a snake_case code string, or `{"code": str, ...params}`.
  The frontend translates `errors.<code>`.
- Week start stored as Python weekday `0`=Monday … `6`=Sunday; default `5` (Saturday). Family size default `4`, range 1–20.
- Database file `data/meals.db`; files under `data/`. `PORT` default **8085**.
- Images: `ghcr.io/frankandreas/meal-planer/backend` and `ghcr.io/frankandreas/meal-planer/frontend`.
- Container names `meals-backend`, `meals-frontend`. Backend never runs as root (`PUID`/`PGID`, default 999:999).
- Code style: black/isort line length 120 (copy FB `pyproject.toml`), comments explain *why*, like the sibling apps.

## Review Focus

1. **The last parent demotes or deletes themself** → refused (`last_parent`), otherwise nobody can reach settings again. Test in Task 2.
2. **A name that differs only in case** ("anna" vs "Anna") → treated as taken (`name_taken`), and login is case-insensitive; kids type names on an iPad keyboard that capitalises. Test in Task 2.
3. **A token of a deleted user, or issued before a PIN reset** → 401. A lost iPad must stop working after a parent resets that person's PIN. Test in Task 2.
4. **A child calls a parent-only endpoint directly** (`PATCH /api/settings`, `POST /api/users`) → 403 `parents_only`, not just a hidden button. Test in Task 3.
5. **A browser in neither German nor English, or a user who never chose a language** → falls back to `DEFAULT_LANGUAGE`, never shows raw keys. Test in Task 2 (backend) and Task 6 (e2e).

---

## File Structure

```
backend/
  requirements.txt            # JT's list minus PDF libs, plus alembic
  Dockerfile                  # copy of FB backend/Dockerfile
  app/
    __init__.py
    config.py                 # env(), data_dir(), default_language()
    database.py               # engine, SessionLocal, Base, get_db (JT)
    database_setup.py         # setup(engine): alembic upgrade head (FB, simplified)
    timeutil.py               # utcnow() (JT)
    models.py                 # UserRole, User, Settings
    schemas.py                # pydantic in/out models for users and settings
    auth.py                   # PIN hashing, tokens, authenticate, get_current_user, require_parent
    errors.py                 # api_error(status, code, **params)
    seed.py                   # seed_admin
    settings_store.py         # get_settings (JT)
    users_api.py              # /token, /me, /users …
    settings_api.py           # /settings
    main.py                   # app, startup, /health
    migrations/{env.py,script.py.mako,versions/0001_foundation.py}
tests/
  conftest.py, helpers.py, requirements.txt
  test_health.py, test_migrations.py, test_auth.py, test_users.py, test_settings.py
pytest.ini, pyproject.toml, .gitignore, .env.example, LICENSE
frontend/                     # JT skeleton + FB i18n/theme
  src/{main.tsx,App.tsx,AuthContext.tsx,api.ts,ui.ts,types.ts,i18n.ts,index.css}
  src/locales/{de.ts,en.ts}
  src/components/{Layout.tsx,PinInput.tsx}
  src/pages/{Login.tsx,SettingsPage.tsx,Placeholder.tsx}
  src/components/settings/{MySettings.tsx,FamilySettings.tsx,FamilyMembers.tsx}
  scripts/check-texts.mjs, nginx.conf, security-headers.conf, Dockerfile
e2e/                          # FB's Playwright setup
  package.json, playwright.config.ts, tests/{helpers.ts,login.spec.ts,settings.spec.ts}
docker-compose.yml, README.md, README_DOCKER.md
scripts/{nas-update.sh,deploy-nas.sh,dev-backend.sh}
.github/{dependabot.yml,workflows/{pr-checks.yml,pull-request.yml,ci-cd.yml}}
```

---

### Task 1: Backend skeleton with migrations and health check

**Files:**
- Create: `backend/requirements.txt`, `backend/app/{__init__,config,database,database_setup,timeutil,models,main}.py`, `backend/app/migrations/{env.py,script.py.mako,versions/0001_foundation.py}`
- Create: `pytest.ini`, `pyproject.toml`, `.gitignore`, `LICENSE` (MIT, copy FB), `tests/{conftest.py,helpers.py,requirements.txt,test_health.py,test_migrations.py}`

**Interfaces:**
- Produces:
  - `config.env(name: str, default: str = "") -> str`, `config.data_dir() -> Path` (env `DATA_DIR`, default `./data`), `config.default_language() -> Literal["de","en"]` (env `DEFAULT_LANGUAGE`, anything else → `"de"`).
  - `database.engine`, `database.SessionLocal`, `database.Base`, `database.get_db()`; default URL `sqlite:///./data/meals.db`; creates the SQLite folder (FB `ensure_sqlite_folder`); foreign keys on.
  - `database_setup.setup(engine) -> None`: `alembic upgrade head` from `app/migrations` (FB's `run()` with the SQLite foreign-key dance; no `catch_up`, no `NEW_COLUMNS`). `database_setup.HEAD = "0001"`.
  - `models.UserRole` (`PARENT`, `CHILD`), `models.User`, `models.Settings` — columns below.
  - `GET /health` → `{"status": "ok"}`.

`models.User` (`users`, `sqlite_autoincrement=True` so ids are never reused):
`id` int pk · `name` String(50) not null · `name_key` String(50) unique not null (= `name.casefold()`, for case-insensitive uniqueness and login) · `pin_hash` String not null · `role` Enum(UserRole) not null default CHILD · `language` String(2) nullable (None = default language) · `failed_logins` int default 0 · `locked_until` DateTime nullable · `token_version` int default 0 · `created_at` DateTime default utcnow.

`models.Settings` (`settings`, single row id=1): `id` int pk · `family_size` int not null default 4 · `week_start` int not null default 5.

- [ ] **Step 1: Write the failing tests**

`tests/conftest.py`: JT's conftest, adapted: env `DATABASE_URL` (temp), `DATA_DIR`, `SECRET_KEY=test-secret`, `INITIAL_ADMIN_PIN=1234`, `DEFAULT_LANGUAGE=de`; cheap bcrypt rounds; the `fresh_db` fixture runs `drop_all`/`create_all` and `seed_admin`; fixtures `db`, `client`, `admin_headers`. (Seeding arrives in Task 2 — until then `fresh_db` only recreates tables; add the seed call in Task 2.)

```python
# tests/test_health.py
def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}

# tests/test_migrations.py
from sqlalchemy import create_engine, inspect
from app import database_setup

def test_fresh_database_upgrades_to_head(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/m.db")
    database_setup.setup(engine)
    tables = set(inspect(engine).get_table_names())
    assert {"users", "settings", "alembic_version"} <= tables
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalar() == database_setup.HEAD

def test_setup_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/m.db")
    database_setup.setup(engine)
    database_setup.setup(engine)  # second start must not fail

def test_migration_matches_models(tmp_path):
    """The migration creates exactly the columns the models declare (catches a forgotten migration)."""
    from app import models
    engine = create_engine(f"sqlite:///{tmp_path}/m.db")
    database_setup.setup(engine)
    inspector = inspect(engine)
    for table in models.Base.metadata.sorted_tables:
        assert {c["name"] for c in inspector.get_columns(table.name)} == set(table.columns.keys()), table.name
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m venv venv && venv/bin/pip install -r backend/requirements.txt -r tests/requirements.txt && venv/bin/pytest`
Expected: FAIL (`ModuleNotFoundError: app`)

- [ ] **Step 3: Implement the skeleton**

`backend/requirements.txt`: fastapi==0.162.0, uvicorn==0.54.0, sqlalchemy==2.1.6, pydantic==2.14.1, python-multipart==0.0.32, bcrypt==5.0.0, pyjwt==2.15.1, alembic==1.20.1, tzdata==2026.5. `tests/requirements.txt`: copy JT's.
Migrations: copy FB `backend/app/migrations/env.py` and `script.py.mako`; write `0001_foundation.py` by hand (`op.create_table` for `users` and `settings`, with `sqlite_autoincrement=True` on users). `main.py`: logging as JT, `database_setup.setup(database.engine)` at import, `FastAPI(title="Meal Planner API")`, `/health`. Ignore in `.gitignore`: `venv/`, `data/*` (keep `data/.gitkeep`), `node_modules/`, `dist/`, `.superpowers/`, `__pycache__/`, `.pytest_cache/`, `.env`, `.deploy.env`, `e2e/.tmp/`, `e2e/test-results/`, `e2e/playwright-report/`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv/bin/pytest`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: backend skeleton with migrations and health check"
```

---

### Task 2: Login, users and roles

**Files:**
- Create: `backend/app/{auth,errors,schemas,seed,users_api}.py`, `tests/{test_auth,test_users}.py`
- Modify: `backend/app/main.py` (seed admin at startup, log the initial PIN like JT, include `users_api.router` at prefix `/api`), `tests/conftest.py` (seed in `fresh_db`), `tests/helpers.py`

**Interfaces:**
- Consumes: `models.User`, `models.UserRole`, `config`, `database.get_db`.
- Produces:
  - `errors.api_error(status: int, code: str, **params) -> HTTPException` — `detail` is `code` when no params, else `{"code": code, **params}`.
  - `auth.get_pin_hash(pin: str) -> str`, `auth.verify_pin(pin: str, hashed: str) -> bool`
  - `auth.create_access_token(user: models.User) -> str` — claims `sub` (id as str), `ver` (token_version), `exp` (30 days).
  - `auth.authenticate(db, name: str, pin: str) -> models.User` — lookup by `name.strip().casefold()`; 5 wrong PINs → locked 15 min (JT's rules).
  - `auth.get_current_user(...) -> models.User` (FastAPI dependency) — 401 `not_logged_in` when token missing/invalid/user gone/`ver` ≠ `token_version`.
  - `auth.require_parent(user=Depends(get_current_user)) -> models.User` — 403 `parents_only`.
  - `seed.seed_admin(db) -> str | None` — creates PARENT "Admin".
  - `tests/helpers.py`: `ADMIN="Admin"`, `ADMIN_PIN="1234"`, `login(client, name=ADMIN, pin=ADMIN_PIN) -> dict` (headers), `create_user(client, headers, name, pin="5678", role="CHILD") -> dict`.
  - Endpoints (all under `/api`):

| Method & path | Who | Body → Response |
|---|---|---|
| `GET /users/public` | anyone | → `[{id, name}]` sorted by name (login screen) |
| `POST /token` | anyone | `{name, pin}` → `{access_token}` |
| `GET /me` | logged in | → `UserOut` |
| `PATCH /me` | logged in | `{language: "de"\|"en"\|null}` → `UserOut` |
| `POST /me/pin` | logged in | `{current_pin, new_pin}` → 204; bumps `token_version`, response header `X-New-Token` with a fresh token so this device stays logged in |
| `GET /users` | parent | → `[UserOut]` |
| `POST /users` | parent | `{name, pin, role}` → 201 `UserOut` |
| `PATCH /users/{id}` | parent | `{name?, role?}` → `UserOut` |
| `POST /users/{id}/pin` | parent | `{pin}` → 204; resets lock, bumps `token_version` |
| `DELETE /users/{id}` | parent | → 204 |

`UserOut` = `{id, name, role, language}` where `language` is the **effective** language (`user.language or config.default_language()`), plus `language_chosen: bool`.

Error codes: `wrong_name_or_pin` (401), `locked` (429, param `minutes`), `not_logged_in` (401), `parents_only` (403), `user_not_found` (404), `name_taken` (409), `last_parent` (400), `cannot_delete_self` (400), `wrong_current_pin` (400). PIN validation: pydantic `pattern=r"^\d{4}$"` (422). Name: stripped, 1–50 chars.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_auth.py
from helpers import ADMIN, ADMIN_PIN, create_user, login

def test_login_and_me(client):
    me = client.get("/api/me", headers=login(client)).json()
    assert me["name"] == ADMIN and me["role"] == "PARENT"
    assert me["language"] == "de" and me["language_chosen"] is False

def test_login_is_case_insensitive(client):
    assert client.post("/api/token", json={"name": " admin ", "pin": ADMIN_PIN}).status_code == 200

def test_wrong_pin(client):
    r = client.post("/api/token", json={"name": ADMIN, "pin": "0000"})
    assert r.status_code == 401 and r.json()["detail"] == "wrong_name_or_pin"

def test_lock_after_five_wrong_pins(client):
    for _ in range(5):
        client.post("/api/token", json={"name": ADMIN, "pin": "0000"})
    r = client.post("/api/token", json={"name": ADMIN, "pin": ADMIN_PIN})
    assert r.status_code == 429 and r.json()["detail"] == {"code": "locked", "minutes": 15}

def test_pin_must_be_four_digits(client):
    assert client.post("/api/users", json={"name": "Lena", "pin": "12a4", "role": "CHILD"}, headers=login(client)).status_code == 422

def test_token_dies_with_pin_reset(client):
    admin = login(client)
    lena = create_user(client, admin, "Lena")
    old = login(client, "Lena", "5678")
    assert client.post(f"/api/users/{lena['id']}/pin", json={"pin": "9999"}, headers=admin).status_code == 204
    assert client.get("/api/me", headers=old).status_code == 401

def test_own_pin_change_keeps_this_device(client):
    headers = login(client)
    r = client.post("/api/me/pin", json={"current_pin": ADMIN_PIN, "new_pin": "4321"}, headers=headers)
    assert r.status_code == 204
    assert client.get("/api/me", headers=headers).status_code == 401
    fresh = {"Authorization": f"Bearer {r.headers['X-New-Token']}"}
    assert client.get("/api/me", headers=fresh).status_code == 200

def test_token_of_deleted_user(client):
    admin = login(client)
    lena = create_user(client, admin, "Lena")
    token = login(client, "Lena", "5678")
    client.delete(f"/api/users/{lena['id']}", headers=admin)
    create_user(client, admin, "Mia")  # must not inherit Lena's id
    assert client.get("/api/me", headers=token).status_code == 401

def test_language_choice(client):
    headers = login(client)
    me = client.patch("/api/me", json={"language": "en"}, headers=headers).json()
    assert me["language"] == "en" and me["language_chosen"] is True
    me = client.patch("/api/me", json={"language": None}, headers=headers).json()
    assert me["language"] == "de" and me["language_chosen"] is False

def test_unknown_default_language_falls_back_to_german(client, monkeypatch):
    monkeypatch.setenv("DEFAULT_LANGUAGE", "fr")
    assert client.get("/api/me", headers=login(client)).json()["language"] == "de"

# tests/test_users.py
from helpers import create_user, login

def test_child_cannot_manage_users(client):
    create_user(client, login(client), "Lena")
    kid = login(client, "Lena", "5678")
    r = client.post("/api/users", json={"name": "X", "pin": "1111", "role": "CHILD"}, headers=kid)
    assert r.status_code == 403 and r.json()["detail"] == "parents_only"
    assert client.get("/api/users", headers=kid).status_code == 403

def test_name_taken_ignores_case(client):
    admin = login(client)
    create_user(client, admin, "Lena")
    r = client.post("/api/users", json={"name": "lena", "pin": "1111", "role": "CHILD"}, headers=admin)
    assert r.status_code == 409 and r.json()["detail"] == "name_taken"

def test_last_parent_cannot_become_child(client):
    admin = login(client)
    me = client.get("/api/me", headers=admin).json()
    r = client.patch(f"/api/users/{me['id']}", json={"role": "CHILD"}, headers=admin)
    assert r.status_code == 400 and r.json()["detail"] == "last_parent"

def test_second_parent_can_be_demoted(client):
    admin = login(client)
    papa = create_user(client, admin, "Papa", role="PARENT")
    assert client.patch(f"/api/users/{papa['id']}", json={"role": "CHILD"}, headers=admin).json()["role"] == "CHILD"

def test_cannot_delete_self(client):
    admin = login(client)
    me = client.get("/api/me", headers=admin).json()
    assert client.delete(f"/api/users/{me['id']}", headers=admin).json()["detail"] == "cannot_delete_self"

def test_public_list_has_names_only(client):
    create_user(client, login(client), "Lena")
    assert client.get("/api/users/public").json() == [
        {"id": 1, "name": "Admin"}, {"id": 2, "name": "Lena"}
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/bin/pytest tests/test_auth.py tests/test_users.py`
Expected: FAIL (404 on `/api/token`)

- [ ] **Step 3: Implement** `errors.py`, `auth.py` (JT's `auth.py` adapted to the interfaces above), `schemas.py`, `seed.py` (JT's, with `role=PARENT`, PIN exactly 4 digits), `users_api.py` (JT's, with `require_parent`, `name_key`, the last-parent guard on both demote and delete, `token_version` bumps). Wire into `main.py` and `conftest.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv/bin/pytest`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: PIN login, family members and parent/child roles"
```

---

### Task 3: Family settings

**Files:**
- Create: `backend/app/{settings_store,settings_api}.py`, `tests/test_settings.py`
- Modify: `backend/app/main.py` (create the settings row at startup; include router), `backend/app/schemas.py`

**Interfaces:**
- Consumes: `auth.get_current_user`, `auth.require_parent`, `models.Settings`.
- Produces:
  - `settings_store.get_settings(db) -> models.Settings` (JT's).
  - `GET /api/settings` (logged in) → `{"family_size": int, "week_start": int}`
  - `PATCH /api/settings` (parent) `{family_size?: 1..20, week_start?: 0..6}` → same shape; out of range → 422.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_settings.py
from helpers import create_user, login

def test_defaults(client):
    assert client.get("/api/settings", headers=login(client)).json() == {"family_size": 4, "week_start": 5}

def test_parent_changes_settings(client):
    r = client.patch("/api/settings", json={"week_start": 0}, headers=login(client))
    assert r.json() == {"family_size": 4, "week_start": 0}

def test_child_reads_but_cannot_change(client):
    create_user(client, login(client), "Lena")
    kid = login(client, "Lena", "5678")
    assert client.get("/api/settings", headers=kid).status_code == 200
    r = client.patch("/api/settings", json={"family_size": 2}, headers=kid)
    assert r.status_code == 403 and r.json()["detail"] == "parents_only"

def test_ranges(client):
    headers = login(client)
    for body in ({"family_size": 0}, {"family_size": 21}, {"week_start": 7}, {"week_start": -1}):
        assert client.patch("/api/settings", json=body, headers=headers).status_code == 422
```

- [ ] **Step 2: Run to verify they fail** — Run: `venv/bin/pytest tests/test_settings.py` — Expected: FAIL (404)
- [ ] **Step 3: Implement** `settings_store.py`, `settings_api.py`, schemas `SettingsOut`, `SettingsPatch`.
- [ ] **Step 4: Run to verify they pass** — Run: `venv/bin/pytest` — Expected: all pass
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: family size and first day of the week"`

---

### Task 4: Frontend skeleton — theme, i18n, login, layout

**Files:**
- Create: `frontend/{package.json,index.html,vite.config.ts,tsconfig*.json,eslint.config.js,postcss.config.js,tailwind.config.js}` (copy JT, rename package to `meals-frontend`, add `i18next@26.5.8`, `react-i18next@17.1.6`, `date-fns`; `lint` script as FB incl. `check-texts`)
- Create: `frontend/scripts/check-texts.mjs` (copy FB), `frontend/src/{main.tsx,App.tsx,AuthContext.tsx,api.ts,ui.ts,types.ts,i18n.ts,index.css}`, `frontend/src/locales/{de,en}.ts`, `frontend/src/components/{Layout,PinInput}.tsx`, `frontend/src/pages/{Login,Placeholder}.tsx`

**Interfaces:**
- Consumes: `/api/users/public`, `/api/token`, `/api/me`, error codes from Task 2.
- Produces:
  - `types.ts`: `type Role = 'PARENT' | 'CHILD'`; `interface User { id: number; name: string; role: Role; language: Language; language_chosen: boolean }`; `interface FamilySettings { family_size: number; week_start: number }`.
  - `i18n.ts` (FB's): `type Language = 'de' | 'en'`, `browserLanguage()`, `applyLanguage(lang)`.
  - `api.ts` (JT's) with `errorMessage(error: unknown): string` translating `detail` via `i18n.t('errors.' + code, params)`; unknown code or validation list → `errors.generic`.
  - `AuthContext` (JT's): `{ user, isLoading, login(name, pin), logout(), refreshUser(), setToken(token) }`; applies `user.language` on every user load, `browserLanguage()` after logout.
  - `ui.ts`: Tailwind class constants `FIELD, INPUT, BUTTON, BUTTON_SECONDARY, BUTTON_DANGER, CARD` restyled to Aurora (`CARD` = glass card: `rounded-2xl border border-white/10 bg-slate-800/40 backdrop-blur-md shadow-…`; primary button cyan accent).
  - Routes: `/login`; inside `Layout` (requires login): `/` → `Placeholder` (title `nav.plan`), `/rezepte` → `Placeholder` (`nav.recipes`), `/einstellungen` → `SettingsPage` (Task 5).
  - Locale keys used later: `common.*`, `nav.{plan,recipes,inbox,history,settings,logout}`, `errors.*` (one per backend code, `errors.locked` with `{{minutes}}`), `login.*`, `roles.{PARENT,CHILD}`, `weekdays.{0..6}` (Monday first).
- `index.css`: FB's Aurora tokens and `.glass-card`, Inter font, body background/glows.
- `Login`: name chosen from `/api/users/public` as large touch-friendly buttons (iPad), then `PinInput`; errors via `errorMessage`.
- `Layout`: glass top bar with app name `common.appName` ("Menüplaner" / "Meal planner"), nav links, user name, logout; on phones the nav collapses into a bottom bar.

- [ ] **Step 1: Write the failing check** — create `locales/de.ts` with keys only for `common` and an `en.ts` missing one key.
- [ ] **Step 2: Run to verify it fails** — Run: `cd frontend && npm install && npm run build` — Expected: tsc error that `en` lacks the key (en.ts typed as `typeof de`, as in FB).
- [ ] **Step 3: Implement** all files above; fill both locales.
- [ ] **Step 4: Run to verify it passes** — Run: `npm run lint && npm run build` — Expected: no errors, `dist/` built. Start backend (`scripts/dev-backend.sh`, copied from FB, `INITIAL_ADMIN_PIN=1111`) and `npm run dev`; log in as Admin/1111 in the browser and see the placeholder page in German.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: frontend skeleton with Aurora theme, i18n and login"`

---

### Task 5: Settings page

**Files:**
- Create: `frontend/src/pages/SettingsPage.tsx`, `frontend/src/components/settings/{MySettings,FamilySettings,FamilyMembers}.tsx`
- Modify: `frontend/src/locales/{de,en}.ts`

**Interfaces:**
- Consumes: `/api/me` (PATCH), `/api/me/pin` (reads `X-New-Token` → `setToken`), `/api/settings`, `/api/users*`.
- Produces: nothing new for later plans; later plans add sections to `SettingsPage` (e.g. mail addresses, AI usage in Plan 4).

Sections (glass cards):
- **MySettings** (everyone): language select `Automatisch (Standard)` / `Deutsch` / `English` (null/de/en); change own PIN.
- **FamilySettings** (parents only): family size (number 1–20), first day of the week (select of `weekdays.*`).
- **FamilyMembers** (parents only): list with role badge; add (name, PIN, role); rename; change role; reset PIN; delete with `confirm`. Backend error codes shown via `errorMessage`.

- [ ] **Step 1: Write the failing e2e test** — after Task 6's harness exists this runs; write it now in `e2e/tests/settings.spec.ts`:
  - Admin sets first day to Monday and family size 5 → reload → values kept.
  - Admin adds child "Lena" (PIN 2222); Lena logs in and sees no family sections.
  - Admin tries to make themself a child → sees the German/English `errors.last_parent` text.
- [ ] **Step 2–4:** Implement; run `npm run lint && npm run build`; e2e runs in Task 6.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: settings page for language, PIN, family and members"`

---

### Task 6: Browser tests

**Files:**
- Create: `e2e/{package.json,playwright.config.ts,README.md}`, `e2e/tests/{helpers.ts,login.spec.ts}` (settings.spec.ts from Task 5)

**Interfaces:**
- Consumes: the running app. `playwright.config.ts` copied from FB: backend on 8100 with a fresh DB, `INITIAL_ADMIN_PIN=1111`, `DEFAULT_LANGUAGE=en`, `CORS_ORIGINS`; frontend via vite on 3100. Remove FB's AI/inbound env vars. Viewport **1180×820** (iPad landscape) as the default project; add a second project "phone" (`devices['iPhone 13']`) for `login.spec.ts` only.
- Requires `CORS_ORIGINS` handling in `backend/app/main.py` (FB's `CORSMiddleware` block) and `VITE_API_URL` in `api.ts` baseURL (FB) — add both here.

`login.spec.ts`:
- Admin logs in with 1111 → sees `Meal planner` and the nav.
- Wrong PIN → `errors.wrong_name_or_pin` text, not a raw code.
- Admin switches language to Deutsch → nav shows `Wochenplan`; reload keeps German; logout → login page in the browser's language (English here).
- Browser locale `fr-FR` (`test.use({ locale: 'fr-FR' })`) → login page in English (`browserLanguage()` returns `en` for every non-German browser); assert no raw keys (`errors.`, `login.`) appear on the page.
- After login, a user who never chose a language sees the backend's effective language (`DEFAULT_LANGUAGE=en` here), regardless of the browser.

- [ ] **Step 1:** Write `login.spec.ts` (and Task 5's `settings.spec.ts` is already there).
- [ ] **Step 2:** Run: `cd e2e && npm install && npx playwright install chromium && E2E_PYTHON=../venv/bin/python npm test` — Expected: fails until CORS/`VITE_API_URL` are wired.
- [ ] **Step 3:** Wire CORS and `VITE_API_URL`.
- [ ] **Step 4:** Run again — Expected: all specs pass on both projects.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "test: browser tests for login and settings"`

---

### Task 7: Docker, NAS deployment and CI

**Files:**
- Create: `backend/Dockerfile` (copy FB), `frontend/{Dockerfile,nginx.conf,security-headers.conf}` (copy FB; `client_max_body_size 26m` — room for several full-resolution screenshots in Plan 4), `docker-compose.yml`, `.env.example`, `data/.gitkeep`
- Create: `scripts/{nas-update.sh,deploy-nas.sh}` (copy JT; rename app/containers/db file `meals.db`), `.deploy.env.example` (copy JT)
- Create: `.github/dependabot.yml`, `.github/workflows/{pr-checks.yml,pull-request.yml,ci-cd.yml}` (copy JT; drop the worker job until Plan 4; add an `e2e` job modelled on FB's; image paths `ghcr.io/frankandreas/meal-planer/{backend,frontend}`)
- Create: `README.md` (what it is, dev setup, tests), `README_DOCKER.md` (FB's structure: Installation with `PORT=8085`, First login, HTTPS at home with `essen.local.<domain>`, Automatic updates, Backup of `data/`)

**Interfaces:**
- `docker-compose.yml`: services `backend` (`container_name: meals-backend`, `user: "${PUID:-999}:${PGID:-999}"`, `./data:/app/data`, env `DATABASE_URL=sqlite:///./data/meals.db`, `SECRET_KEY`, `INITIAL_ADMIN_PIN`, `DEFAULT_LANGUAGE=${DEFAULT_LANGUAGE:-de}`, `TZ=${TZ:-Europe/Zurich}`, healthcheck as FB) and `frontend` (`container_name: meals-frontend`, ports `"${PORT:-8085}:8080"`).
- `.env.example`: `PUID`, `PGID`, `PORT=8085`, `SECRET_KEY=`, `INITIAL_ADMIN_PIN=`, `DEFAULT_LANGUAGE=de`, `TZ=Europe/Zurich`.

- [ ] **Step 1:** Run: `docker compose config --quiet` — Expected: fails (no file).
- [ ] **Step 2:** Write the files.
- [ ] **Step 3:** Run: `docker compose config --quiet && PORT=8085 INITIAL_ADMIN_PIN=1111 docker compose up -d --build` — Expected: both containers healthy; `curl -s localhost:8085/api/users/public` → `[{"id":1,"name":"Admin"}]`; `docker logs meals-backend 2>&1 | grep "INITIAL PIN"` shows the PIN line.
- [ ] **Step 4:** Run: `docker compose down` and `bash -n scripts/*.sh` — Expected: clean.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "build: Docker images, NAS deployment docs and CI"`

---

## Next plans

- **Plan 2 — Recipes:** recipe model (yield, structured ingredients with groups and the fixed unit list, steps, tags, photo, source, soft delete), scaling and rounding as pure functions, ratings and favourites per person, recipe list/view/edit screens.
- **Plan 3 — Planner:** plan entries per date and slot (recipe or note, people), week grid with tap-tap and drag, suggestion tabs, closing the week, history, phone day view.
- **Plan 4 — Import:** inbox, mail worker and `/api/inbound`, URL + JSON-LD import, AI client with rate limit and usage log, drafts with uncertain spots, translation, mail addresses in settings.
