# Swissmilk Recipes in "Was habe ich?" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** From "Was habe ich?", search swissmilk.ch on request, show fitting recipes with ✓ / fehlt, and take one
over into the family's recipes, with no AI anywhere on that path.

**Architecture:**
- **Reader:** a schema.org microdata reader (`backend/app/microdata.py`) turns a recipe page into the same draft as
  `jsonld.recipe_from_html`. Both share one draft builder.
- **Swissmilk access:** `backend/app/swissmilk.py` is the only code that talks to Swissmilk. It uses fixed addresses
  and `fetch.fetch` with a host allowlist on every redirect, caches pages and photos, and parses the search page.
- **Search:** `backend/app/swissmilk_api.py` ranks candidates with the "Was habe ich?" matcher, and serves photos
  through the backend.
- **Import:** the importer reads microdata before the AI, and never sends a Swissmilk page to the AI.
- **Frontend:** a Swissmilk section in `UseUp.tsx`.

**Tech Stack:** FastAPI, SQLAlchemy, stdlib `html.parser`, Pillow (existing `photos.py`), pytest; React + TS, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-01-swissmilk-search-design.md`

## Global Constraints

- Hosts: pages only from `https://www.swissmilk.ch`, photos only from `https://api.swissmilk.ch/wp-content/uploads/`.
  Any other host, also after a redirect, raises `fetch.FetchRefused`.
- No AI on this path: no call into `ai.*` for search results or for any page on `www.swissmilk.ch`.
- Search: `https://www.swissmilk.ch/de/suche/?q=<words joined by space, URL-encoded>`. Candidates are links matching
  `^/de/rezepte-kochideen/rezepte/[A-Za-z0-9_]+/[a-z0-9-]+/$`, the first **12**, in page order, without duplicates.
- Checked data only: title ≤ 200 characters, ≤ 60 ingredient lines, names ≤ 200 characters.
- Politeness: ≤ 4 recipe pages fetched at a time; pages and photos cached ~24 h; whole search budget 15 s (partial
  results OK); one Swissmilk search per person per 5 s (429 `too_many_searches` otherwise).
- Tests never touch the network: Swissmilk calls are faked by monkeypatching `swissmilk._get` (pytest) and by
  `page.route` on the app's own `/api/...` calls (Playwright). Ruling: no test-only setting that points the
  backend at another Swissmilk address. Such a switch would be a way around the host allowlist in production code.
  The backend path is covered by pytest instead.
- Visible text only from `frontend/src/locales/{de,en}.ts`; Swiss German (no ß, «»).
- Commands: `venv/bin/python -m pytest -q`; `cd frontend && npm run type-check && npm run lint && npm test`;
  `cd e2e && E2E_PYTHON=../venv/bin/python HUB_PYTHON=../../family-hub/.superpowers/venv/bin/python npx playwright test`.

## Review Focus

1. A Swissmilk recipe page that changed layout (no `itemtype` Recipe): the result is dropped silently from search,
   and the import fails with `swissmilk_unreadable`. Never AI → tests in Task 1 and Task 4.
2. A slow Swissmilk (one page hangs): the search returns what it has within the budget, not an error → Task 3.
3. The photo endpoint asked for anything not handed out by a search (a guessed key, another host's URL): 404 →
   Task 3.
4. A recipe taken over twice (double tap, or a child's waiting item): the second time shows "wartet im Posteingang"
   / "schon in deinen Rezepten" and creates no second inbox item → Task 3 (state) and Task 5 (button disappears).
5. Typed words with umlauts or `&`/`#` reach Swissmilk correctly encoded in `q`, and never as part of the path →
   Task 2.

---

### Task 1: Microdata reader, Swissmilk recipe reading

**Files:**
- Create: `backend/app/microdata.py`; Modify: `backend/app/jsonld.py` (extract the draft builder)
- Create: `backend/app/swissmilk.py` (only `read_recipe` in this task)
- Create: `tests/pages/swissmilk-recipe.html` (copy of the recon page
  `/tmp/claude-1000/-home-andreas-work-meal-planer/ba34868e-9de7-4436-96be-2d3975da9fe8/scratchpad/recon/sm_recipe.html`,
  with every `<script>…</script>` except `application/ld+json` ones removed to keep it small)
- Test: `tests/test_swissmilk.py`

**Interfaces:**
- Produces:
  - `jsonld.draft_from_node(node: dict, page_url: str) -> dict | None`: the existing body of `recipe_from_html`'s
    loop, unchanged in behaviour (`recipe_from_html` calls it).
  - `microdata.recipe_node(page: str, *, keep_ingredient: Callable[[dict[str, str]], bool] = lambda attrs: True) -> dict | None`:
    the first `itemscope` whose `itemtype` ends in `schema.org/Recipe`, as a JSON-LD-like dict.
    - Each property is a list of strings. The value is `content` on `meta`, `src` on `img`, `href` on `link`/`a`,
      else the element's whitespace-collapsed text.
    - Properties of **nested** itemscopes (video, rating, nutrition) are not the recipe's. The exception is a nested
      scope whose own `itemprop` is on the recipe (e.g. `recipeInstructions` on a `HowToStep`): it counts as that
      property, with its text.
    - `keep_ingredient` gets the attributes of a `recipeIngredient` element.
  - `microdata.recipe_from_html(page: str, page_url: str, **kw) -> dict | None` = `draft_from_node(recipe_node(...))`.
  - `swissmilk.read_recipe(page: str, page_url: str) -> dict | None`:
    - only rows whose `class` contains the word `Ingredient` (drops "ofenfeste Form ca. 2 l")
    - "*" removed from names
    - an amount-less line whose comma parts all start with a capital letter becomes one ingredient per part
      ("Salz, Pfeffer, Muskatnuss")
    - `image_url` is the first image on `https://api.swissmilk.ch/wp-content/uploads/`, else `None`

- [ ] **Step 1: Write the failing tests** in `tests/test_swissmilk.py`, on the fixture page:

```python
def test_reads_a_swissmilk_recipe():
    draft = swissmilk.read_recipe(PAGE, URL)  # URL = ".../LM_div_0812_03/kartoffelgratin/"
    assert draft["title"] == "Kartoffelgratin"
    assert draft["servings"] == 4 and draft["servings_unit"] is None
    assert (draft["prep_minutes"], draft["cook_minutes"]) == (20, 50)
    assert [i["name"] for i in draft["ingredients"]] == [
        "mehligkochende Kartoffeln", "Milch", "Rahm", "Knoblauchzehen", "Salz", "Pfeffer", "Muskatnuss",
        "Gruyère AOP", "Butterflöckli",
    ]
    assert draft["ingredients"][0]["amount"] == 800 and draft["ingredients"][0]["unit"] == "g"
    assert "nach Belieben" in draft["ingredients"][3]["note"]
    assert len(draft["steps"]) == 6 and draft["steps"][1] == "Kartoffelscheiben in die Form schichten."
    assert draft["image_url"] == "https://api.swissmilk.ch/wp-content/uploads/2019/06/kartoffelgratin-2560x1920.jpg"
    assert "Vegetarisch" in draft["tags"] and draft["source_url"] == URL
```

Plus:
- `test_video_name_is_not_the_title`: covered by the title assertion.
- `test_page_without_recipe_microdata`: `swissmilk.read_recipe("<html><body>Nichts</body></html>", URL) is None`.
- `test_generic_microdata_keeps_all_rows`: `microdata.recipe_from_html(PAGE, URL)` has "ofenfeste Form" as its first
  ingredient (the filter is Swissmilk's).
- `test_jsonld_unchanged`: the existing `tests/test_jsonld.py` passes unchanged.

- [ ] **Step 2: Run** `venv/bin/python -m pytest tests/test_swissmilk.py -q`. Expected: import error (no modules).

- [ ] **Step 3: Implement** with `html.parser.HTMLParser` and a stack of open elements. Void elements (`meta`,
  `img`, `link`, `br`, `source`, `input`) never get pushed. Range lines like "1 - 2 Knoblauchzehen" may need
  `parse_line` to accept spaces around the dash: change `ingredient_parse._LINE` only if the test needs it, and keep
  `tests/test_ingredient_parse.py` green.

- [ ] **Step 4: Run** the whole backend suite. Expected: all pass.

- [ ] **Step 5: Commit** `feat(swissmilk): read recipe pages from their microdata`

### Task 2: Talking to Swissmilk safely

**Files:**
- Modify: `backend/app/fetch.py` (host allowlist), `backend/app/photos.py` (expose downscaling), `backend/app/swissmilk.py`
- Create: `tests/pages/swissmilk-search.html` (recon `sm_search.html`, scripts stripped as in Task 1)
- Test: `tests/test_swissmilk.py`, `tests/test_fetch.py`

**Interfaces:**
- Produces:
  - `fetch.fetch(url, accept=PAGE_TYPES, *, allowed_hosts: frozenset[str] | None = None) -> Page`: with
    `allowed_hosts`, the scheme must be `https` and every URL, including each redirect target, must have a host in
    the set, else `FetchRefused`. All existing checks stay.
  - `photos.downscale(data: bytes) -> bytes`: JPEG bytes, longest side `MAX_SIDE`, no metadata. `store_photo` uses
    it.
  - `swissmilk.PAGE_HOST = "www.swissmilk.ch"`, `swissmilk.PHOTO_PREFIX = "https://api.swissmilk.ch/wp-content/uploads/"`.
  - `swissmilk._get(url: str, accept=fetch.PAGE_TYPES) -> fetch.Page`: the single network call. It uses
    `fetch.fetch` with `allowed_hosts={"www.swissmilk.ch"}` for pages, or `{"api.swissmilk.ch"}` for photos (chosen
    by URL). Tests monkeypatch it.
  - `swissmilk.candidates(page: str) -> list[str]`: absolute `https://www.swissmilk.ch/de/rezepte-kochideen/rezepte/…/`
    URLs, the Global Constraints pattern, the first 12, no duplicates.
  - `swissmilk.search_url(words: list[str]) -> str`.
  - `swissmilk.recipe(url: str) -> dict | None`: cached `read_recipe(_get(url).text, url)`. Only for URLs that
    `is_recipe_url` accepts.
  - `swissmilk.photo(url: str) -> bytes`: cached `photos.downscale(_get(url, accept=IMAGE_TYPES).body)`. Only for URLs
    starting with `PHOTO_PREFIX`.
  - `swissmilk.is_swissmilk(url: str) -> bool` (host is `www.swissmilk.ch`); `swissmilk.recipe_id(url: str) -> str | None`
    (the `<ID>` after `/rezepte/` or `/recettes/` or `/ricette/`, any language).
  - Cache: a module-level TTL dict (24 h, at most 500 entries, oldest dropped first). `swissmilk.clear_cache()` is
    for tests.

- [ ] **Step 1: Write the failing tests**
- `test_fetch_refuses_hosts_outside_the_allowlist`: monkeypatch `fetch._checked`/`fetch._open` (see existing
  `tests/test_fetch.py` for how it fakes connections). A 302 from `www.swissmilk.ch` to `evil.example` raises
  `FetchRefused`. `http://www.swissmilk.ch` raises `FetchRefused`. Without `allowed_hosts`, the same redirect is
  followed.
- `test_candidates_from_the_search_page`: 12 URLs. The first is
  `https://www.swissmilk.ch/de/rezepte-kochideen/rezepte/LM_div_0812_03/kartoffelgratin/`. All match the pattern.
  An extra `<a href="https://evil.example/de/rezepte-kochideen/rezepte/X/y/">` and `<a href="/de/suche/">` added to
  the page are not among them.
- `test_search_url_encodes_words` (Review Focus 5): `search_url(["Rüebli", "Salz & Pfeffer", "#1"])` is
  `https://www.swissmilk.ch/de/suche/?q=R%C3%BCebli+Salz+%26+Pfeffer+%231`.
- `test_recipe_and_photo_refuse_other_addresses`: `swissmilk.recipe("https://www.swissmilk.ch/de/suche/")` and
  `swissmilk.photo("https://res.cloudinary.com/x.jpg")` raise `fetch.FetchRefused` without calling `_get`.
- `test_recipe_is_cached`: two calls → `_get` called once.
- `test_recipe_id`: `.../rezepte/LM_div_0812_03/kartoffelgratin/` and `/fr/recettes-idees/recettes/LM_div_0812_03/gratin/?x=1`
  → `"LM_div_0812_03"`; a non-recipe URL → `None`.

- [ ] **Step 2: Run** them; expected failures (missing names).
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the whole backend suite. Expected: all pass, incl. existing photo and fetch tests.
- [ ] **Step 5: Commit** `feat(swissmilk): fixed addresses, allowlisted fetching, cached pages and photos`

### Task 3: Search endpoint and photos through the backend

**Files:**
- Create: `backend/app/swissmilk_api.py`; Modify: `backend/app/main.py`, `backend/app/schemas.py`, `backend/app/use_up_api.py`
  (extract the per-recipe check), `frontend/src/locales/*.ts` (error codes)
- Test: `tests/test_swissmilk_api.py`

**Interfaces:**
- Consumes: Task 2's `swissmilk.*`; `pantry.matches/covered`; `use_up_api._typed`.
- Produces:
  - `use_up_api.check(names: list[tuple[str, str]], typed: list[str], staples: list[str]) -> tuple[list[str], list[str]]`:
    `(used, missing)` for ingredient `(name, note)` pairs. The existing search uses it too, so its behaviour is
    unchanged.
  - `GET /api/use-up/swissmilk?have=…&mode=use_up|cook_now` → `list[schemas.SwissmilkResult]`, where
    `SwissmilkResult = {title, url, photo: str | None, used, missing, recipe_id: int | None, waiting: bool}`. `photo`
    is `/api/use-up/swissmilk/photo/<key>`, where `key` = first 16 hex characters of sha256(photo URL). The key is
    remembered server-side (TTL map key → URL, same cache rules) only when a search returns it.
  - `GET /api/use-up/swissmilk/photo/{key}` → `image/jpeg` from `swissmilk.photo(url)`. 404 for an unknown key.
    Login needed (any role).
  - `swissmilk_api.reset_limits()` (tests: called in the same fixture as `swissmilk.clear_cache()`).
  - Errors: 429 `too_many_searches` (same person within 5 s); 502 `swissmilk_unreachable` when the search page
    itself fails. Recipe pages that fail or can't be read are skipped.
  - `have` limits as in `/api/use-up` (1–20; none left → `[]` without calling Swissmilk).

- [ ] **Step 1: Write the failing tests** (fake `_get` serving the two fixture pages, the recipe fixture for every
  candidate URL, and a 1×1 JPEG for photo URLs; `swissmilk.clear_cache()` in a fixture):
  - `test_search_ranks_and_checks`: `have=Kartoffeln&mode=use_up`. The Kartoffelgratin result has
    `used == ["Kartoffeln"]`, `missing == ["Milch", "Rahm", "Muskatnuss", "Gruyère AOP"]` (Salz and Pfeffer are basics;
    Knoblauch and Butterflöckli are "nach Belieben"), and a `photo` starting `/api/use-up/swissmilk/photo/`.
  - `test_cook_now_drops_too_many_missing`: with `mode=cook_now`, Kartoffelgratin (4 missing) is absent.
  - `test_unreadable_page_is_skipped` (Review Focus 1): `_get` returns `<html></html>` for one candidate → that one
    is absent, the others are there, no error.
  - `test_slow_page_within_budget` (Review Focus 2): monkeypatch the budget to 0.5 s and make one candidate's `_get`
    sleep 2 s → the response arrives in under 1.5 s with the other results.
  - `test_search_page_down`: `_get` raises `FetchFailed` for the search URL → 502 `swissmilk_unreachable`.
  - `test_already_there`: a live recipe with `source_url` `https://www.swissmilk.ch/fr/recettes-idees/recettes/LM_div_0812_03/gratin/`
    → Kartoffelgratin has `recipe_id` set. A deleted one → `None`. A `url` inbox item with status `waiting` for the
    German link → `waiting == True`.
  - `test_photo_only_for_handed_out_keys` (Review Focus 3): the key from a result → 200 `image/jpeg`. `0000000000000000`
    → 404.
  - `test_one_search_per_5_seconds`: a second call right away → 429 `too_many_searches`. A child may search (200).
  - `test_no_ai_called`: monkeypatch `ai.client_for` to raise → searches still work.
- [ ] **Step 2: Run** `venv/bin/python -m pytest tests/test_swissmilk_api.py -q`. Expected: 404s.
- [ ] **Step 3: Implement.** Use a `concurrent.futures.ThreadPoolExecutor(max_workers=4)` and `wait(timeout=budget)`.
  Put the budget in a module constant `BUDGET_SECONDS = 15`. Order like `/api/use-up` (no last-eaten). Ties keep
  candidate order. Add the error codes to both locales (`too_many_searches`, `swissmilk_unreachable`).
- [ ] **Step 4: Run** the whole backend suite (incl. `test_error_texts.py`). Expected: all pass.
- [ ] **Step 5: Commit** `feat(swissmilk): search Swissmilk from Was habe ich?`

### Task 4: Import without AI for Swissmilk

**Files:**
- Modify: `backend/app/importer.py`; Test: `tests/test_importer.py`, `frontend/src/locales/*.ts`

**Interfaces:**
- Consumes: `swissmilk.is_swissmilk`, `swissmilk.read_recipe`, `swissmilk._get`, `microdata.recipe_from_html`.
- Produces, in `importer.process`:
  - Each link that `swissmilk.is_swissmilk` accepts is fetched with `swissmilk._get` and read with
    `swissmilk.read_recipe`. Its photo comes through `swissmilk.photo` → `photos.store_photo`. Such a page is
    **never** `page_without_recipe`, so it never goes to the AI.
  - Every other link: `jsonld.recipe_from_html`, then `microdata.recipe_from_html`, then today's behaviour.
  - A `url` item whose only link is Swissmilk and unreadable fails with error `swissmilk_unreadable` (texts in both
    locales). A mail falls through to its own text as today.

- [ ] **Step 1: Write the failing tests** (`tests/test_importer.py` has the fakes for fetch and AI; reuse them):
  - `test_swissmilk_link_imported_without_ai`: a `url` item for the Kartoffelgratin URL. `_get` serves the fixture,
    and the AI fake raises if called. The draft has title "Kartoffelgratin" and 9 ingredients.
  - `test_swissmilk_unreadable_never_ai` (Review Focus 1): `_get` returns an article page without microdata → status
    `failed`, error `swissmilk_unreadable`, AI not called.
  - `test_swissmilk_redirect_elsewhere_refused`: `_get`'s real allowlist (not monkeypatched; fake `fetch._open`) on
    a redirect to `evil.example` → item fails, AI not called.
  - `test_other_site_microdata_before_ai`: a non-Swissmilk page with only microdata → draft from microdata, AI not
    called.
- [ ] **Step 2: Run** them; expected failures.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the whole backend suite. Expected: all pass.
- [ ] **Step 5: Commit** `feat(swissmilk): take Swissmilk recipes over without AI`

### Task 5: Swissmilk section in "Was habe ich?"

**Files:**
- Create: `frontend/src/components/recipes/SwissmilkResults.tsx`; Modify: `frontend/src/components/recipes/UseUp.tsx`,
  `frontend/src/useUp.ts`, locales
- Test: `e2e/tests/swissmilk.spec.ts` (`e2e/playwright.config.ts`: add `swissmilk` to the phone project's `testMatch`)

**Interfaces:**
- Consumes: Task 3's endpoints; `POST /api/inbox/urls` `{url}` (existing).
- Produces:
  - `useUp.ts`: `interface SwissmilkResult { title; url; photo: string | null; used: string[]; missing: string[]; recipe_id: number | null; waiting: boolean }`
    and `fetchSwissmilk(have, mode)`.
  - `SwissmilkResults({ have, mode })`:
    - shown in `UseUp` below the own results while `have.length > 0`
    - first a button "Auch bei Swissmilk suchen". After the tap, a section that searches now and again when
      `have`/`mode` change (no debounce below 600 ms), keyed like the own results so stale cards never show
    - closed again by Leeren
  - Each card:
    - photo (`AuthImage` if the app's own images need the login, else `<img>`), title, "Swissmilk"
    - `✓ …` and `fehlt: …`
    - **Ansehen ↗**: `<a target="_blank" rel="noopener noreferrer">`
    - and one of three:
      - **Übernehmen**: POST `/api/inbox/urls`, then the card shows "wartet im Posteingang" with a link to
        `/posteingang`
      - "schon in deinen Rezepten" linking `/rezepte/{recipe_id}`
      - "wartet im Posteingang"
  - Errors shown in the section with the error texts. "Keine passenden Rezepte bei Swissmilk." when empty.
  - Texts (en/de):
    - `Also search Swissmilk` / `Auch bei Swissmilk suchen`
    - `Searching Swissmilk…` / `Suche bei Swissmilk…`
    - `View ↗` / `Ansehen ↗`
    - `Take over` / `Übernehmen`
    - `already in your recipes` / `schon in deinen Rezepten`
    - `waiting in the inbox` / `wartet im Posteingang`
    - `No fitting recipes on Swissmilk.` / `Keine passenden Rezepte bei Swissmilk.`

- [ ] **Step 1: Write the failing e2e test** `e2e/tests/swissmilk.spec.ts`. `page.route('**/api/use-up/swissmilk?*')`
  answers with two results:
  - (a) "Kartoffelgratin": `used ["Kartoffeln"]`, `missing ["Milch"]`, `recipe_id null`, `waiting false`, photo
    null
  - (b) "Kartoffelsalat": `recipe_id` of a recipe the test created via API

  `page.route('**/api/inbox/urls')` answers 201 and records the body. Steps:
  - Type "Kartoffeln", click "Also search Swissmilk".
  - (a) shows "✓ Kartoffeln" and "missing: Milch", and its "View ↗" link has `href` of its url and `target=_blank`.
  - (b) shows "already in your recipes".
  - Click (a)'s "Take over": the recorded body is `{url: <a's url>}`, and (a) now shows "waiting in the inbox" and
    no "Take over" (Review Focus 4).
  - Click "Clear": the Swissmilk section is gone.
- [ ] **Step 2: Run** `npx playwright test swissmilk`. Expected: fails (button not found).
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the frontend checks and the full e2e suite. Expected: all pass on tablet and phone.
- [ ] **Step 5: Commit** `feat(swissmilk): Swissmilk results in Was habe ich?`
