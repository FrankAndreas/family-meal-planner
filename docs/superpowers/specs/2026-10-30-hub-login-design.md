# Meal planner: log in through the family hub

Date: 2026-10-30. Rollout step 3 of the family hub (FrankAndreas/family-hub), after the budget app.

The decisions follow the budget app's switch (FrankAndreas/family-budget-dashboard,
`docs/superpowers/specs/2026-10-30-hub-login-design.md`) and the hub hardening
(`family-hub/docs/superpowers/specs/2026-10-30-hub-hardening-design.md`). The user said "go" without further questions,
so points marked **(my call)** were settled by Claude.

## Why

- **One login for the family.** Parents add recipes and the kids vote on them (stars, favourites). Today every family
  member has a second PIN here, managed here.
- **One place for security.** The hub holds the login, the PINs, the lock after wrong PINs and "log out everywhere".

## Goals

1. **Login:** through the hub's `hub_session` cookie (set for `local.<domain>`). There are no PINs, PIN screens or
   people management in the planner any more.
2. **People:** they come from the hub, for the app key `meals` (**my call**). Name, role (parent/child) and language
   follow the hub.
3. **Existing data stays with its person:** each row from before the hub is linked to the hub person with the same name
   and role, once, at the first sync. This covers stars, favourites, sender addresses, inbox items and AI calls. Later
   no row is linked by name: a new person with an old name must not take over that row.
4. **"Log out"** sends the browser to `<HUB_PUBLIC_URL>/logout?next=<the app>`.
5. **Home only, as now.** A request carrying `Cf-Connecting-Ip` is no login. The tunnel still opens only `/api/inbound`
   for the recipe-mail worker, with its own secret.

## Non-goals

- Outside access to the planner.
- Changing recipes, the plan, suggestions, the inbox, photos or the AI, beyond whose login it is.
- E-mail addresses from the hub. The planner keeps its own list of sender addresses per person; the hub deliberately
  doesn't hand addresses to apps.

## Behaviour

### Login
Same rules as the budget app:
- **Token:** the cookie `hub_session`, or `Authorization: Bearer` for tests and scripts.
- **Who it is:** the hub's `/api/session?app=meals` says whose login it is and whether they may use the planner. A valid
  login with access is kept for 60 s, and so is "no valid login" (at most 1000 tokens, by SHA-256). "No access" is never
  kept, so someone given access gets in at once.
- **Changes:** a change through the cookie needs the header `X-Requested-With: meals`.
- **Errors:** each error carries a JSON `code`:
  - 401 `not_logged_in`;
  - 403 `no_access`;
  - 503 `hub_unavailable`;
  - 403 `csrf`.
- **The frontend:**
  - on 401 it sends the browser to the hub (`<login_url>/?next=<current address>`);
  - on `no_access` it shows a "No access" page with "Log in as someone else";
  - on `hub_unavailable` it shows "The family hub can't be reached" with "Try again".

### People (`hub_people`, as in the budget app)
- **Sync:**
  - The list is refreshed from `/api/apps/meals/people` at most once a minute, asked with the token of the person
    using the app.
  - Only one refresh runs at a time, and after the hub fails to answer the next try waits 10 s.
  - "Not yet refreshed" is `None`, not 0.0: on a machine up for less than a minute, 0.0 would look like a refresh a
    moment ago.
- **`users` table:**
  - new: `hub_id` (unique) and `is_active`;
  - removed: `pin_hash`, `failed_logins`, `locked_until`, `lockouts`, `token_version`;
  - `language` follows the hub.
- **Someone no longer listed** is hidden (`is_active` false):
  - Their stars keep counting in the recipe scores, and their favourites, sender addresses and history stay, until a
    parent deletes their data **(my call)**.
  - Deleting is `DELETE /users/{id}`, only for hidden people: an active person gives 409 `still_in_hub`.
- **Settings:**
  - "Family" lists the active people with their role (read-only).
  - "Removed in the family hub" lists the hidden ones, each with a delete button.
- **Sender addresses** stay per person as today, parents only. A hidden person's addresses no longer let mail in: mail
  from them is refused like mail from an unknown address **(my call)**.

### Endpoints
- **Removed:**
  - `POST /api/token`, `GET /api/users/public`;
  - `POST /api/users`, `PATCH /api/users/{id}`, `POST /api/users/{id}/pin`;
  - `POST /api/me/pin`, `PATCH /api/me` (the language lives in the hub).
- **Kept:**
  - `GET /api/me`;
  - `GET /api/users` (parents; active people);
  - `GET /api/config` (the language for the "no access" page).
- **New:**
  - `GET /api/users/removed` (parents);
  - `GET /api/hub` returning `{"login_url": HUB_PUBLIC_URL}`.
- **Gone from the backend:** `SECRET_KEY`, `INITIAL_ADMIN_PIN`, the seeded Admin, `bcrypt` and `PyJWT`.

### Frontend
- **Removed:**
  - the Login page and `PinInput`;
  - the PIN part of "My settings" (its language picker becomes a note: "Language and PIN are in the family hub",
    linking to the hub);
  - the add/edit/PIN controls of the family list;
  - the token in local storage.
  - `AuthImage` fetches with the cookie.
- **Requests** use `withCredentials` and the `X-Requested-With: meals` header.
- **The browser tests** run against the backend through a Vite proxy (`API_PROXY`), so the cookie is the page's own, as
  in the budget app. `VITE_API_URL` and `CORS_ORIGINS` go away.

## Tests
- **Backend:** a fake hub (as the budget app's `tests/fake_hub.py`); the tests' login helper returns a fake token.
  Covered:
  - login, CSRF, the tunnel header, hub down;
  - sync, linking by name only at the switch and with the same role;
  - removed people hidden, their data kept, then deleted;
  - stars of hidden people keep counting;
  - mail from a hidden person's address refused.
- **e2e:** a real hub from a family-hub checkout next to the repo (as in the budget app), on its own port. The existing
  tests log in with the hub cookie instead of the PIN screen.
- **CI:** checks out family-hub for the e2e job.

## Deploy
- **NAS `compose.yaml`:** the backend `environment:` gets `HUB_URL`, `HUB_PUBLIC_URL` and `HUB_APP_KEY`;
  `SECRET_KEY` and `INITIAL_ADMIN_PIN` go away.
- **In the hub:** the planner's tile gets the app key `meals`, with everyone ticked. Each hub person's name and role
  must match their planner account before the first login.
