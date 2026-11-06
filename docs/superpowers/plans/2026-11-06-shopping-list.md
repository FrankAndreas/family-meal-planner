# Shopping List and Bring! Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parents pick the week's meals to shop for and get a combined, scaled ingredient list. They can drop or add items and send it to Bring! with a family member's Bring! account. One shared list at a time, deleted once sent.

**Architecture:**
- **Combining:** a pure module `backend/app/shopping.py` combines the scaled ingredients of the ticked plan entries into lines keyed by name.
- **Storage:** migration `0008` adds the open list (`shopping_lists`), the ticked meals (`shopping_meals`), the parents' per-line decisions (`shopping_choices`), the free items (`shopping_extras`) and the Bring! login (`bring_login`).
- **Endpoints:** `backend/app/shopping_api.py` holds one endpoint per change, and the list is recomputed on every read.
- **Sending:** the read returns a `version` fingerprint. `POST /api/shopping/send` refuses with 409 when the version is stale, so only what the sender saw goes out.
- **Bring! client:** `backend/app/bring.py` wraps the unofficial Bring! REST API behind a small protocol with a fake (`BRING_FAKE=1`) for tests and e2e.
- **Frontend:** a Bring! section in Einstellungen, an `/einkaufsliste` page, and a link from the week header.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic (SQLite), pytest, urllib (no new dependency); React + TypeScript, i18next, Tailwind, vitest, Playwright e2e.

**Spec:** `docs/superpowers/specs/2026-11-06-shopping-list-design.md`

## Global Constraints

- **Parents only:**
  - Every `/api/shopping*` and `/api/bring*` endpoint uses `auth.require_parent`, so children get 403.
  - The frontend hides the link and the settings section for children.
- **One open list.** It belongs to a week stored by its start date (`week_start`, a `Date`).
- **Ticking and moving meals:**
  - Starting a list ticks every entry of that week that has a recipe.
  - Entries planned later are unticked.
  - An entry that leaves the week loses its tick.
  - An entry deleted from the plan drops out (FK `ON DELETE CASCADE`; foreign keys are on, see `database.enable_foreign_keys`).
- **Scaling:**
  - Each entry is scaled with `scaling.factor(recipe.servings, recipe.servings_unit, entry.people or family_size, family_size)` and `scaling.scale`, exactly as `recipes_api` does for the recipe view.
  - Recipes soft-deleted after planning still count.
- **Combining:**
  - Lines are keyed by `text.sort_key(name)`.
  - `g`+`kg` add up, `ml`+`dl`+`l` add up, and the same unit adds up.
  - `unit None` with an amount ("2 Eier") is its own unit.
  - Amounts that can't be added stay on one line as separate parts.
  - A line where some ingredient has no amount shows only the amounts it has. A line where no ingredient has an amount has `amounts == []`.
- **Staples:** a line that `pantry.covered(name, settings.staples)` covers starts dropped with `staple: true`. A parent's "kept" choice wins over it, permanently.
- **Free items:** a free item whose `sort_key(name)` equals a recipe line's key joins that line (its text is appended to `extras`). Otherwise it is its own line.
- **Bring! login:**
  - The password never appears in any response.
  - The backend talks to Bring!; the browser never does.
  - The planner logs in to Bring! afresh for every action (login check, lists, send). It stores email, password, list uuid and list name, and no tokens. This is a *builder's call* the spec allowed.
- **Sending:**
  - A failed send leaves the list untouched. A successful send deletes it.
  - A stale `version` gives 409 `shopping_changed` and sends nothing.
- **Texts:**
  - Visible text only from `frontend/src/locales/de.ts` and `en.ts`; error codes get texts in both.
  - Run `npm run lint` (includes `check-texts`) in `frontend/`, not only eslint.
- **Tests:**
  - pytest runs with `venv/bin/pytest -q`.
  - e2e runs with `cd e2e && E2E_PYTHON=../venv/bin/python HUB_PYTHON=../../family-hub/.superpowers/venv/bin/python npx playwright test`, using English texts.

## Review Focus

1. **The list or the plan changes between load and send.** Examples: the other parent drops a line, someone changes the people from 6 to 8, or a child plans a meal. → `test_send_refused_when_changed` (Task 3) covers all three changes; e2e in Task 6.
2. **An entry moved out of the week and back.** It must come back unticked, not ticked. → `test_entry_moved_out_and_back_is_unticked` (Task 3).
3. **Bring! fails halfway through, or the login is wrong.** The list stays, and the next send works. → `test_send_failure_keeps_list` (Task 3).
4. **The same ingredient with and without an amount, and with units that don't add up.** For example "Pfeffer" next to "1 Prise Pfeffer", or "1 Bund" and "50 g Petersilie". → Task 1 tests.
5. **A staple ticked back on, after which the staples list changes.** It must stay ticked. → `test_kept_staple_stays_kept` (Task 3).

---

### Task 1: Combining ingredients

**Files:**
- Create: `backend/app/shopping.py`
- Test: `tests/test_shopping.py`

**Interfaces:**
- Consumes: `scaling.round_amount`, `text.sort_key`, `pantry.covered`.
- Produces:
  - `Part = tuple[float, str | None]`: an amount and a unit key.
  - `@dataclass Source`: `name: str`, `amount: float | None`, `unit: str | None`, `meal: str` (the recipe title).
  - `@dataclass Line`: `key: str`, `name: str` (first spelling seen), `amounts: list[Part]`, `extras: list[str]` (free-item texts), `meals: list[str]` (titles, de-duplicated, in plan order), `staple: bool`.
  - `combine(sources: list[Source], extras: list[tuple[str, str]], staples: list[str]) -> list[Line]`. `extras` are (name, amount text) pairs. Lines come back in the order of each key's first appearance, recipe lines first and then the extra-only lines.
  - `add_up(parts: list[Part]) -> list[Part]`. It combines mass and volume, sums the same units, and keeps the part order by first appearance.

- [ ] **Step 1: Write the failing tests** in `tests/test_shopping.py`:
  - `test_same_name_same_unit_adds`: two `Source("Hörnli", 200, "g", …)` and `(…300, "g")` give one line with `amounts == [(500, "g")]`.
  - `test_case_and_accents_combine`: "Rüebli" and "rüebli" give one line, named "Rüebli".
  - `test_mass_adds_across_units`: `add_up([(200,"g"),(0.5,"kg")]) == [(700,"g")]`, and `add_up([(800,"g"),(0.5,"kg")]) == [(1.3,"kg")]`.
  - `test_volume_adds_across_units`: `add_up([(3,"dl"),(4,"dl")]) == [(7,"dl")]`, `add_up([(5,"dl"),(1,"l")]) == [(1.5,"l")]` and `add_up([(50,"ml"),(20,"ml")]) == [(70,"ml")]`.
    - Display rule: a volume total below 100 ml shows in ml, below 1000 ml in dl, otherwise in l.
    - A mass total below 1000 g shows in g, otherwise in kg.
    - Each total goes through `round_amount`.
  - `test_units_that_dont_add_stay_on_one_line`: "1 Bund" and "50 g" of "Petersilie" give one line with `amounts == [(1,"bunch"),(50,"g")]`.
  - `test_unitless_amount_is_its_own_unit`: `(2,None)+(3,None)` gives `[(5,None)]`, and `(2,None)` with `(100,"g")` gives two parts.
  - `test_no_amount_adds_nothing`: "Pfeffer" with no amount plus "1 Prise Pfeffer" gives `amounts == [(1,"pinch")]`. "Pfeffer" with no amount twice gives `amounts == []`.
  - `test_meals_listed_once_in_order`: the same ingredient from "Lasagne", "Suppe" and "Lasagne" gives `meals == ["Lasagne", "Suppe"]`.
  - `test_staples_marked`: with `staples=["Salz"]`, "Salz" has `staple=True` and "Hörnli" has `staple=False`.
  - `test_extra_joins_line_of_same_name`: the extra `("hörnli", "1 Pack")` gives the Hörnli line `extras == ["1 Pack"]`.
  - `test_extra_alone_is_its_own_line`: the extra `("WC-Papier", "")` gives a last line with key `sort_key("WC-Papier")`, `amounts == []`, `extras == [""]` and `meals == []`.
- [ ] **Step 2: Run** `venv/bin/pytest tests/test_shopping.py -q`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement `backend/app/shopping.py`.** Convert mass to g and volume to ml before summing, then convert back with the display rule.
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit** `feat(shopping): combine the week's ingredients`.

### Task 2: Storage

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/app/migrations/versions/0008_shopping.py`
- Modify: `backend/app/database_setup.py` (`HEAD = "0008"`)
- Test: `tests/test_migrations.py`

**Interfaces:**
- Produces these models:
  - `ShoppingList`: `id`, `week_start: Date` (not null), `created_by` (FK users, SET NULL), `created_at`, `updated_by` (FK users, SET NULL), `updated_at`. The API enforces "at most one row"; the table doesn't.
  - `ShoppingMeal`: `list_id` (FK shopping_lists, CASCADE) and `entry_id` (FK plan_entries, CASCADE), together the primary key. A row means the entry is ticked.
  - `ShoppingChoice`: `list_id` (FK, CASCADE) and `key: String(200)`, together the primary key, plus `buy: Boolean`. `False` means dropped and `True` means kept. A key without a row follows the default, which drops staples and keeps everything else.
  - `ShoppingExtra`: `id`, `list_id` (FK, CASCADE), `name: String(100)`, `amount: String(50)` default `""`, `position: Integer`.
  - `BringLogin` (single row, id 1): `email: String(200)`, `password: String(200)`, `list_uuid: String(64)` nullable, `list_name: String(100)` nullable.
  - Relationships: `ShoppingList.meals`, `.choices` and `.extras` (cascade delete-orphan).

- [ ] **Step 1: Write the failing tests** in `tests/test_migrations.py`, in its existing style:
  - `test_0008_tables`: after upgrading to head, the five tables exist with those columns.
  - `test_0008_from_0007`: upgrading a 0007 database keeps its recipes and plan entries.
- [ ] **Step 2: Run** `venv/bin/pytest tests/test_migrations.py -q`. Expected: FAIL.
- [ ] **Step 3: Add the models, the migration and `HEAD`.**
- [ ] **Step 4: Run** `venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(shopping): tables for the open list and the Bring! login`.

### Task 3: Bring! client and the shopping API

**Files:**
- Create: `backend/app/bring.py`, `backend/app/shopping_api.py`
- Modify: `backend/app/schemas.py`, `backend/app/main.py` (include the router), `backend/app/plan_api.py` (moving an entry out of the open list's week deletes its `ShoppingMeal`), `frontend/src/locales/de.ts` and `en.ts` (error texts only)
- Test: `tests/test_bring.py`, `tests/test_shopping_api.py`

**Interfaces:**
- Consumes: `shopping.combine`, `Source`, `Line` (Task 1) and the Task 2 models.
- Produces, in `bring.py`:
  - `class BringFailed(Exception)` with `code: str`, either `"bring_login_failed"` or `"bring_failed"`.
  - `class BringClient(Protocol)` with three methods:
    - `login(email, password) -> Session`;
    - `lists(session) -> list[tuple[str, str]]`, giving (uuid, name) pairs;
    - `add(session, list_uuid, items: list[tuple[str, str]]) -> None`, taking (name, spec) pairs.
  - `client() -> BringClient`: `FakeBring` when `BRING_FAKE=1`, otherwise `HttpBring`.
  - `FakeBring` behaviour:
    - Password `"wrong"` raises `BringFailed("bring_login_failed")`.
    - Its lists are `[("fake-home", "Zuhause"), ("fake-office", "Büro")]`.
    - `add` appends to the module-level `FakeBring.sent: list[tuple[str, list[tuple[str, str]]]]`.
    - An item named `"FAIL"` raises `BringFailed("bring_failed")`, so e2e can trigger a failure.
  - `HttpBring` talks to `https://api.getbring.com/rest/` with urllib and a 20 s timeout. Its calls are the ones the `bring-api` library (github.com/miaucl/bring-api, used by Home Assistant) makes; check them against that library's source before writing:
    - `POST v2/bringauth`, form `email`/`password`, returns `uuid` and `access_token`. A 401 or 400 means `bring_login_failed`.
    - `GET bringusers/{uuid}/lists`, returns `lists[].listUuid` and `.name`.
    - `PUT v2/bringlists/{listUuid}/items` with JSON `{"changes": [{"itemId": name, "spec": spec, "uuid": <new uuid4>, "operation": "TO_PURCHASE", "accuracy": "0.0", "altitude": "0.0", "latitude": "0.0", "longitude": "0.0"}], "sender": ""}`.
    - Headers: `X-BRING-API-KEY` (the library's constant), `X-BRING-CLIENT: webApp`, `X-BRING-COUNTRY: CH`, `X-BRING-USER-UUID`, `Authorization: Bearer …`.
    - Any other HTTP error, URL error or unreadable JSON means `bring_failed`.
- Produces these endpoints (all parent-only):
  - **Bring! login:**
    - `GET /api/bring` → `{"email": str | None, "list_uuid": str | None, "list_name": str | None}`.
    - `POST /api/bring/login {email, password}` logs in, then stores the email and password and clears the list. It returns `{"lists": [{"uuid","name"}]}`. A failure gives 400 `bring_login_failed`, and nothing is stored.
    - `GET /api/bring/lists` → `{"lists": […]}`. Without a login it gives 400 `bring_not_set_up`.
    - `PUT /api/bring/list {uuid}` stores the list's uuid and name. A uuid the account doesn't have gives 400 `bring_unknown_list`.
    - `DELETE /api/bring` → 204, and the row is gone.
  - **The shopping list:**
    - `GET /api/shopping` → `{"list": ShoppingOut | None}`.
    - `POST /api/shopping {week_start, replace: bool = false}` → `ShoppingOut`:
      - With no list open, it creates one with every recipe entry of that week ticked.
      - With one open for the same week, it returns that list.
      - With one open for another week, it gives 409 `shopping_other_week` unless `replace`, in which case it deletes that list first.
      - `week_start` must be a week start under the current setting; otherwise it gives 400 `shopping_bad_week`.
    - `DELETE /api/shopping` → 204.
    - `PUT /api/shopping/meals/{entry_id} {ticked}` → `ShoppingOut`. An entry outside the week, or one without a recipe, gives 400 `shopping_not_in_week`.
    - `PUT /api/shopping/lines {key, buy: bool | None}` → `ShoppingOut`. `None` removes the choice.
    - `POST /api/shopping/extras {name (1–100), amount (0–50)}` → `ShoppingOut`.
    - `DELETE /api/shopping/extras/{id}` → `ShoppingOut`.
    - `POST /api/shopping/send {version, specs: dict[str, str]}` → `{"sent": n}`:
      - **Errors, in this order:** with no list, 404 `shopping_none`. Without a Bring! login or list, 400 `bring_not_set_up`. A stale version gives 409 `shopping_changed`. A `BringFailed` gives 502 with its code.
      - **Items:** every line whose `buy` is true, named by the line's name, with the spec `specs.get(key, "")`. The frontend formats the specs, because the unit labels live in its locales.
      - **Success:** the list is deleted.
    - Every endpoint that changes the list sets `updated_by`/`updated_at`. Without an open list, the change endpoints give 404 `shopping_none`.
  - `ShoppingOut` fields:
    - `week_start`, `week_end`, `started_by: str | None`, `changed_by: str | None`, `changed_at`.
    - `meals: [{entry_id, date, slot, title, people, ticked}]`, covering the week's recipe entries in plan order.
    - `notes: [{date, slot, note}]`, the entries without a recipe, shown but not tickable.
    - `lines: [{key, name, amounts: [{amount, unit}], extras: [str], meals: [str], staple, buy}]`.
    - `extras: [{id, name, amount}]`.
    - `version: str`: a sha256 of the JSON of `meals`, `lines` and `extras`, so a change to a tick, the people, a choice, a free item, a recipe or the staples changes it.

- [ ] **Step 1: Write the failing tests.**
  - In `tests/test_bring.py`, covering `HttpBring` against a stubbed `urllib.request.urlopen`:
    - `test_login_sends_form_and_reads_uuid`
    - `test_login_401_is_login_failed`
    - `test_add_sends_changes`, which checks the JSON body's `itemId`/`spec`/`operation`
    - `test_unreachable_is_bring_failed`
  - In `tests/test_shopping_api.py` (with `BRING_FAKE=1`, `FakeBring.sent` cleared per test, and the `plan` and `create_recipe` helpers):
    - `test_start_ticks_recipe_entries_only`: two recipe entries and one note give `ticked` on both meals, and the note appears in `notes`.
    - `test_lines_scaled_per_entry`: a 4-serving recipe with 200 g Hörnli, planned for 6 people, gives a line with `[{amount: 300, unit: "g"}]`.
    - `test_entry_without_people_uses_family_size`.
    - `test_later_entry_unticked`.
    - `test_deleted_entry_drops_out`.
    - `test_entry_moved_out_and_back_is_unticked`: move it with `PATCH /api/plan/entries/{id}` to the next week and back.
    - `test_entry_moved_within_week_stays_ticked`.
    - `test_recipe_deleted_after_planning_still_counts`.
    - `test_staple_starts_dropped` and `test_kept_staple_stays_kept`: keep Salz, then `PATCH /api/settings` staples without Salz and back with Salz; `buy` stays true throughout.
    - `test_drop_survives_amount_change`: drop Hörnli, change the entry's people, and the line is still `buy: false`.
    - `test_extra_added_and_removed` and `test_extra_merges_with_line`.
    - `test_other_week_conflict_and_replace`.
    - `test_bad_week_start`.
    - `test_shows_who_started_and_changed`: one parent starts the list and a second parent drops a line.
    - `test_children_refused`: every endpoint returns 403.
    - `test_bring_login_lists_and_choice`: covers wrong password, success, an unknown list and a good list. `GET /api/bring` never contains the password.
    - `test_send_needs_bring` gives 400 `bring_not_set_up`.
    - `test_send_sends_ticked_lines_with_specs_and_deletes`: `FakeBring.sent == [("fake-home", [("Hörnli", "300 g"), ("WC-Papier", "")])]`, and `GET /api/shopping` then returns `{"list": None}`.
    - `test_send_refused_when_changed`: parametrised over three changes, each made after the `GET`: dropping a line, `PATCH`ing an entry's people, and a child planning a new meal in that week. The new meal arrives unticked but changes `meals`, which changes `version`. Each gives 409 `shopping_changed` and `FakeBring.sent == []`.
    - `test_send_failure_keeps_list`: an extra named `"FAIL"` gives 502 `bring_failed` and the list is unchanged. Removing the extra and sending again works.
- [ ] **Step 2: Run** `venv/bin/pytest tests/test_bring.py tests/test_shopping_api.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Build the `Source`s from the ticked `ShoppingMeal`s whose entries lie in the week, iterating the week's entries in `plan_api._entries` order. Add the error texts (`bring_login_failed`, `bring_failed`, `bring_not_set_up`, `bring_unknown_list`, `shopping_none`, `shopping_other_week`, `shopping_bad_week`, `shopping_not_in_week`, `shopping_changed`) to both locales' error section.
- [ ] **Step 4: Run** `venv/bin/pytest -q` and, in `frontend/`, `npm run lint`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(shopping): the shared list and sending it to Bring!`.

### Task 4: Bring! in Einstellungen

**Files:**
- Create: `frontend/src/bring.ts`, `frontend/src/components/settings/BringSettings.tsx`
- Modify: `frontend/src/pages/SettingsPage.tsx` (parents' block), locales
- Test: `e2e/tests/shopping.spec.ts` (settings part)

**Interfaces:**
- Consumes: the `/api/bring*` endpoints from Task 3.
- Produces: in `bring.ts`, `fetchBring()`, `bringLogin(email, password)`, `fetchBringLists()`, `chooseBringList(uuid)` and `bringLogout()`.

- [ ] **Step 1: Write the failing e2e test** `bring settings` (as a parent):
  - A wrong password shows the `bring_login_failed` text.
  - The right login shows a list picker with "Zuhause" and "Büro". Picking "Zuhause" shows "Signed in as … · list Zuhause".
  - After a reload, the password field is empty and the email is shown.
  - "Sign out" goes back to the login form.
  - A child doesn't see the section.
- [ ] **Step 2: Run** `npx playwright test shopping` (from `e2e/`). Expected: FAIL.
- [ ] **Step 3: Implement the section.**
  - Texts: German heading "Bring!", "E-Mail", "Passwort", "Anmelden", "Liste", "Angemeldet als {{email}} · Liste {{list}}", "Abmelden", and English equivalents.
  - Add `BRING_FAKE: '1'` to the backend `env` in `e2e/playwright.config.ts`.
- [ ] **Step 4: Run** the e2e test and `npm run lint`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(bring): log in to Bring! in the settings`.

### Task 5: Formatting specs (frontend helper)

**Files:**
- Create: `frontend/src/shopping.ts`, `frontend/src/shopping.test.ts`

**Interfaces:**
- Produces:
  - The types `ShoppingList`, `ShoppingLine`, `ShoppingMeal`.
  - API calls: `fetchShopping()`, `startShopping(weekStart, replace?)`, `discardShopping()`, `tickMeal(entryId, ticked)`, `chooseLine(key, buy)`, `addExtra(name, amount)`, `removeExtra(id)`, `sendShopping(version, specs)`.
  - `formatSpec(line: ShoppingLine, t: TFunction, lang: Language): string`. It joins with `" + "` the parts formatted as `formatAmount(amount, lang)` followed by `t('units.'+unit)` (the label is left out when `unit` is null), followed by the non-empty `extras`.

- [ ] **Step 1: Write the failing vitest tests:**
  - `[(500,"g")]` gives `"500 g"`.
  - `[(1,"bunch"),(50,"g")]` gives `"1 Bund + 50 g"` in German.
  - `[(1.5,"l")]` gives `"1,5 l"` in German and `"1.5 l"` in English.
  - `[(5,null)]` gives `"5"`.
  - `amounts [], extras ["2 Pack"]` gives `"2 Pack"`.
  - `amounts [(500,"g")], extras ["1 Pack"]` gives `"500 g + 1 Pack"`.
  - Nothing at all gives `""`.
- [ ] **Step 2: Run** `npx vitest run src/shopping.test.ts` (from `frontend/`). Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the tests and `npm run lint`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(shopping): API calls and amount texts for the list`.

### Task 6: The Einkaufsliste page

**Files:**
- Create: `frontend/src/pages/ShoppingPage.tsx`
- Modify:
  - `frontend/src/App.tsx`: route `einkaufsliste`.
  - `frontend/src/components/plan/WeekHeader.tsx`: for parents, a link "🛒 Einkaufsliste" to `/einkaufsliste?start=<week.start>`.
  - Locales.
- Test: `e2e/tests/shopping.spec.ts`

**Interfaces:**
- Consumes: `shopping.ts` (Task 5) and `bring.ts` (Task 4).

The page has these states:
- **No list open:** "Start the list for <week>", from `?start`, or the plan's current week when `?start` is missing.
- **A list open for another week:** "There's a list for <week>" with two buttons, "Open it" and "Discard it and start this week".
- **A list open:**
  - The header shows "Started by X · changed by Y, HH:MM".
  - Section 1 lists the meals with checkboxes, and the notes greyed out.
  - Section 2 lists the lines. Each line shows its amount text from `formatSpec`, its name and its meals. A dropped line is crossed out; a staple also shows "usually at home". Tapping a line toggles `buy`.
  - Below the lines: a field to add an item (name and amount) and the added items with ✕.
  - Discard asks before deleting.
- **The send button "Send to Bring! (n)":**
  - Without a Bring! login, it is replaced by a link to Einstellungen.
  - On 409 it reloads the list and shows "The list changed in the meantime. Please check it again."
  - On 502 or 400 it shows the error text and keeps the list.
  - On success it shows "{{count}} items in Bring!" and the start state.

- [ ] **Step 1: Write the failing e2e tests** in `shopping.spec.ts`. Each logs in as a parent, sets up the fake Bring! login, and plans two recipes and a note in a week:
  - `list from the week`:
    - Opening the week's "Shopping list" and starting it shows both meals ticked and the note not tickable.
    - The ingredient lines show amounts, and Salz is crossed out with "usually at home".
    - Unticking a meal removes its lines.
  - `drop, add and send`:
    - Drop a line, add "Toilet paper", then send.
    - The test expects "n items in Bring!" and, after a reload, the start state.
  - `changed meanwhile`: with the page open, change the list through the API with `page.request` (drop a line). Clicking send then shows the "changed in the meantime" text, and the line is now crossed out. Sending again succeeds.
  - `bring fails`: add an item "FAIL"; sending shows the `bring_failed` text and the list is still there.
  - `children don't see it`: the week header has no link for a child.
  - `phone`: the page works in the phone project. The meals and lines are visible, and there is no horizontal scroll.
- [ ] **Step 2: Run** `npx playwright test shopping`. Expected: FAIL.
- [ ] **Step 3: Implement the page, the route and the link.**
- [ ] **Step 4: Run** the full e2e suite, `npm run lint` and `venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(shopping): the Einkaufsliste page`.
