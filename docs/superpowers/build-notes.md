# Build notes

Decisions made while building, and review findings deliberately left for later. Collected from the
execution logs of the four plans in `docs/superpowers/plans/`.

## Plan 1 — Foundation

**Decisions**

- work on branch `build` (fresh repo, master holds only docs) — keeps master clean until the user's review gate — cost if wrong: one branch rename
- Pre-flight: T2 consumes T1 models.User/config — consistent. T3 consumes T2 require_parent — consistent. T4 consumes T2 endpoints/error codes — consistent. T5 consumes X-New-Token (T2) — consistent. T6 needs CORS + VITE_API_URL — T4 api.ts per JT has no baseURL; Ruling: add in T6 as the plan says.
- Pre-flight: T1 conftest says fresh_db seeds admin; seed exists only in T2 — Ruling: T1 conftest without seed, add in T2 (plan says so).
- browser click-through of login deferred to Task 6's Playwright run — same check, automated — cost if wrong: login bugs found one task later
- built the Playwright harness, CORS and VITE_API_URL (planned for Task 6) at the start of Task 5 — Task 5's browser test needs a runnable harness to fail first — cost if wrong: none, Task 6 shrinks to login.spec
- e2e "last parent" case replaced by "rename to taken name" — the shared e2e database has many parents, so last_parent can't be reached; the backend test covers last_parent — cost if wrong: last_parent message untested in the browser
- weekdays locale keys are mon..sun with WEEKDAYS in types.ts mapping Python weekday → key — numeric keys break i18next's typed keys — cost if wrong: none
- language names "Deutsch"/"English" are locale entries identical in both languages — check-texts forbids inline text; endonyms are what a user looks for — cost if wrong: none
- login.spec passed on first run (harness wired in Task 5); validity shown by mutating errorMessage → wrong-PIN test failed, reverted — cost if wrong: none
- dropped the Google Fonts link from index.html — the CSP (style-src 'self', copied from FB) would block it; Inter falls back to system-ui like FB in practice — cost if wrong: a slightly different font
- e2e job lives in pr-checks.yml (runs before images are built) instead of FB's separate ci-cd job — one place for all checks — cost if wrong: none
- a browser in neither German nor English gets DEFAULT_LANGUAGE before login (plan's Task 6 said English, its Review Focus said default) — spec: "German default"; a Swiss iPad in French/Italian should get German — cost if wrong: one /api/config call
- edited migration 0001 instead of adding 0002 (lockouts column, named uq_users_name_key) — nothing is deployed yet — cost if wrong: a dev database from today must be deleted
- phone e2e project uses Pixel 7 (Chromium) not iPhone 13 — CI installs only Chromium; WebKit/iPad Safari untested — cost if wrong: Safari-only bugs found by hand

**Deferred minor findings**

- empty family size gives generic error instead of a range message
- simultaneous demotion of two parents can leave none (race)
- simultaneous duplicate-name create gives 500 instead of 409
- nas-update.sh CONTAINER_PREFIX logic unused (compose hard-codes meals-backend)
- unused Tailwind v3 tailwind.config.js

## Plan 2 — Recipes

**Decisions**

- list/tags sort accent-insensitively (sort_key strips diacritics) — plan said casefold, but casefold sorts Ä after Z — cost if wrong: none
- decimal comma via de-DE number format — de-CH formats with a point; plan and Swiss recipe sites use "0,5 dl" — cost if wrong: one locale string
- ingredient-row helpers live in src/ingredientRows.ts, not in IngredientEditor.tsx — react-refresh lint forbids non-component exports from component files — cost if wrong: none
- e2e login helper registers page listeners once per page — a second login on the same page double-accepted dialogs and threw — cost if wrong: none
- yield unit is a free text field (empty = people) instead of a "Personen"/free select — one field, same data — cost if wrong: small UX change

**Deferred minor findings**

- ⅓ and 0.125 drift to 0.33 / 0.13 on re-save
- decompression-bomb image gives 500 instead of photo_unreadable
- photo upload decodes on the event loop (async def)
- 422 for >40-char tags / >20 tags / >1440 min shows a generic error
- recipe list error message never clears
- normalize_tags preloads all ingredients

## Plan 3 — Planner

**Decisions**

- schemas use 'import datetime as dt' — a field named date shadows the type under Python 3.14 lazy annotations — cost if wrong: none
- e2e tests plan into a random far-future week via ?woche= (PlanPage reads it) — tests share one database and would collide in the current week — cost if wrong: none
- no tag chips in the suggestion panel; the search box matches tags — the panel is 17rem wide on an iPad — cost if wrong: one more row of chips later
- people shown on a chip only when they differ from the family size — keeps 7 narrow columns readable — cost if wrong: none
- MouseSensor + TouchSensor (hold 200 ms) instead of PointerSensor — dnd-kit's advice for touch screens; touch drag not covered by e2e (Playwright drives the mouse), tap-tap is the tested touch path — cost if wrong: touch drag needs a tweak on the real iPad
- close-week checkbox updates optimistically, reloads on error — a controlled checkbox waiting for the server felt (and tested) unresponsive — cost if wrong: none
- "Instead…" shows only for unticked entries — "instead" only makes sense for something not eaten — cost if wrong: one more button
- a week can be closed on its last day (end > today, not >=) — spec: closing is the first step of Friday's session; plan's Task 2 rule contradicted it; today's dinner still counts as eaten only from tomorrow — cost if wrong: a week closed before its last dinner

**Deferred minor findings**

- switching week while a change is in flight can show the old week's reload
- close page out-of-order reloads can show a wrong tick until the next action
- a deleted recipe's entry can be moved to a future day
- history links to deleted recipes without a "deleted" mark
- "last eaten" uses months after ~1 month and the client clock ("2 days ago" for yesterday late evening)
- VoiceOver context for chips, grid semantics, aria-modal/focus trap in dialogs
- "|" in a recipe title is cut in the drag overlay
- "Instead…" only offers a note, not a recipe (plan narrowed the spec)
- phone day view jumps to the first day on week change (partly fixed: DayView keyed by week)

## Plan 4 — Import

**Decisions**

- all plan-4 error texts added in Task 1 (test_error_texts guards every code) — cost if wrong: none
- connections are pinned to the checked IP (no second DNS lookup) — prevents DNS rebinding into the home network — cost if wrong: none
- recipe_from_ai returns (draft, raw, tokens) — tokens go to the usage log; no lang_hint (the prompt says keep the recipe's language) — cost if wrong: none
- processing runs in a daemon thread (importer.start), not FastAPI BackgroundTasks — the link-paste endpoint and the process endpoint share one starter; tests swap in the synchronous run — cost if wrong: none
- login-wall links (facebook, instagram, tiktok) are skipped when following mail links — they return nothing without a login — cost if wrong: one wasted fetch each
- the chosen mail picture is stored as an attachment index in the draft and decoded again on save — no photo file for drafts that get discarded — cost if wrong: none
- any recipe with language de is 'already_german' (also a translated one) — re-translating German makes no sense — cost if wrong: none
- worker copied from family-budget-dashboard (it checks dmarc=pass), not job-tracking as the spec said — the newer of the two, same pattern — cost if wrong: none
- images use apiUrl() (VITE_API_URL prefix) — photos were relative paths, which hit the wrong port in the browser tests and in any split dev setup; same-origin in Docker unchanged — cost if wrong: none
- settings and editor loads ignore late answers (cancellation flag) — React's double effect in dev let a late GET overwrite typed values; the settings e2e caught it — cost if wrong: none
- "Translate into German" shows for parents on recipes in English or of unknown language from an import, not on hand-typed ones — avoids the button on every family recipe — cost if wrong: a manual English recipe needs its language set first

**Deferred minor findings**

- two simultaneous "Process" clicks can start two runs (two AI calls)
- "Show original" pairs names by position after the ingredient list was edited
- a server trickling bytes can keep a fetch thread busy (no overall deadline)
- inbox count includes items being processed
- /inbound reads a chunked body before checking its size (behind the secret and nginx's limit)
- two simultaneous mails with the same Message-ID give a 500 (worker then forwards to the fallback)
- ingredient group headings aren't translated
- NAT64 / IPv4-compatible IPv6 addresses count as public
- link drafts that get discarded leave their photo file behind
