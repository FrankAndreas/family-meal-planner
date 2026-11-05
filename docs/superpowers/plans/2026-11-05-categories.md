# Recipe Categories Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recipes get zero or more categories from a fixed list of ten. Imports and a one-off migration fill them in, and the suggestion panel ranks recipes that fit the chosen slot first, without hiding any.

**Architecture:** A new pure module `backend/app/categories.py` holds the keys, the slot → categories table, the word table and the matching. A JSON `categories` column on `recipes` is backfilled from tags by migration `0007` (frozen copy of the table). `GET /api/suggestions?slot=` regroups each tab's result before the limit is applied. `GET /api/recipes?category=` filters. `POST /api/recipes/categorize` (parent) lets the AI fill uncategorised recipes, 25 per call. The frontend adds category chips to the form, view and list, plus a "Für" slot row in `SuggestionPanel`.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic (SQLite), pytest; React + TypeScript, i18next, Tailwind, Playwright e2e.

**Spec:** `docs/superpowers/specs/2026-11-05-categories-design.md`

## Global Constraints

- Category keys, in this order everywhere: `breakfast, apero, starter, soup, salad, main, side, dessert, baking, snack`.
- Slot fits: `breakfast → breakfast, baking`; `snack → snack, baking, apero`; `lunch → main, soup, salad, starter`; `dinner → main, soup, salad, starter`.
- Groups: 0 = fits; 1 = no categories, or only `side`/`dessert`; 2 = has categories, none fit. Within a group the tab's order stays. Grouping happens before `limit`.
- Never filter by slot. No slot = today's order exactly.
- Visible text only from `frontend/src/locales/de.ts` and `en.ts`. Run `npm run lint` (includes `check-texts`) in `frontend/`, not only eslint.
- Category keys are not sent to or changed by translation.
- Word matching ignores case and accents (`app.text.sort_key`) and matches whole words or phrases only, never substrings.
- localStorage access is wrapped in try/catch. A blocked or empty storage means "Alle".

## Review Focus

1. **Old inbox drafts without `categories`:** opening a draft saved before this change must not crash the form; it starts with no categories. → test in Task 5.
2. **A recipe whose stored `categories` holds an unknown key** (hand-edited DB, a key removed later): it must still list, rank as if that key weren't there, and save again. → test in Task 1 (`slot_group` ignores unknown keys) and Task 2 (`RecipeOut` drops unknown keys).
3. **`limit` smaller than the number of unfitting recipes:** fitting recipes must still come back. → test in Task 3.
4. **Phone sheet then iPad:** opening the phone sheet for Zmorge must not change the remembered iPad choice. → covered by the design of `SuggestionPanel` props in Task 6 (the phone passes `slot`, only the iPad persists); e2e check in Task 6.
5. **A `recipeCategory` that is all categories** ("Hauptgericht, Dessert"): both categories, no tag left over; and keywords that are long phrases ("Kuchen & Torten") still map. → test in Task 1.

---

### Task 1: The categories module

**Files:**
- Create: `backend/app/categories.py`
- Test: `tests/test_categories.py`

**Interfaces:**
- Produces:
  - `CATEGORIES: tuple[str, ...]`: the ten keys in order.
  - `Category = Literal[...]`: the same ten.
  - `SLOT_FITS: dict[str, frozenset[str]]`, keyed by the four slot keys.
  - `NEUTRAL: frozenset[str] = {"side", "dessert"}`.
  - `WORDS: dict[str, tuple[str, ...]]`: category → words, at least the spec's table. Extras: plurals such as "Hauptgerichte", "Desserts", "Salate", "Suppen", "Kuchen & Torten" works via "Kuchen".
  - `clean(values: Iterable[object]) -> list[str]`: known keys only, no duplicates, in `CATEGORIES` order.
  - `from_words(values: Iterable[str]) -> tuple[list[str], list[str]]`: returns (categories found, the values that matched nothing), keeping the leftovers' original spelling and order.
  - `slot_group(categories: Iterable[str], slot: str) -> int`: returns 0, 1 or 2. Unknown keys are ignored.

- [ ] **Step 1: Write the failing tests** in `tests/test_categories.py`:
  - `test_every_listed_word_maps`: parametrised over the spec's table, e.g. `from_words(["Hauptgericht"]) == (["main"], [])`, `from_words(["Main course"]) == (["main"], [])`, `from_words(["Apéro"])` and `from_words(["apero"])` both give `["apero"]`, `from_words(["ZMORGE"]) == (["breakfast"], [])`.
  - `test_no_substring_matches`: each of `"Salatsauce"`, `"Suppengrün"`, `"Kuchenblech"`, `"Brotaufstrich"` gives `([], [value])`.
  - `test_whole_word_inside_a_phrase`: `from_words(["Kuchen & Torten"]) == (["baking"], [])` and `from_words(["Schnelle Suppe"]) == (["soup"], [])`.
  - `test_leftovers_keep_spelling_and_order`: `from_words(["Vegetarisch", "Hauptgericht", "schnell", "Dessert"]) == (["main", "dessert"], ["Vegetarisch", "schnell"])`.
  - `test_clean`: `clean(["snack", "main", "nope", "main", 3]) == ["main", "snack"]`.
  - `test_slot_group`, with these cases:

    | categories | slot | group |
    |---|---|---|
    | `["main"]` | dinner | 0 |
    | `["main", "apero"]` | snack | 0 |
    | `[]` | dinner | 1 |
    | `["dessert"]` | dinner | 1 |
    | `["side", "dessert"]` | lunch | 1 |
    | `["baking"]` | dinner | 2 |
    | `["baking", "dessert"]` | dinner | 2 |
    | `["breakfast"]` | breakfast | 0 |
    | `["gone"]` | dinner | 1 |

- [ ] **Step 2: Run** `pytest tests/test_categories.py -v`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement `backend/app/categories.py`.** Matching: `sort_key` the value and every word. A word matches if `re.search(rf"(?<!\w){re.escape(word)}(?!\w)", value)` finds it. `from_words` does not split values itself: callers have already split them on commas.
- [ ] **Step 4: Run** `pytest tests/test_categories.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(categories): the fixed list, the slot table and the word table`.

### Task 2: Store, save, return and filter categories

**Files:**
- Modify: `backend/app/models.py`. On `Recipe`, after `tags`: `categories = Column(JSON, nullable=False, default=list)`, and `ai_categorized_at = Column(DateTime)` (when the AI was last asked to categorise it; used by Task 7).
- Create: `backend/app/migrations/versions/0007_categories.py`
- Modify: `backend/app/database_setup.py` (`HEAD = "0007"`)
- Modify: `backend/app/schemas.py`: `RecipeIn.categories: list[Category] = []` with a validator returning `categories.clean(...)`; `RecipeSummary.categories: list[str]`
- Modify: `backend/app/recipes_api.py`: `Votes.summary` returns `"categories": categories.clean(recipe.categories)`; `_apply` saves `body.categories`; `filter_recipes(recipes, q, tag, category="")`; `list_recipes(..., category: str = Query("", pattern=...))` with the pattern allowing `""`, `"none"` or a key
- Test: `tests/test_recipes.py`, `tests/test_migrations.py`

**Interfaces:**
- Consumes: `categories.CATEGORIES`, `Category`, `clean`.
- Produces: `filter_recipes(recipes, q: str, tag: str, category: str = "") -> list[models.Recipe]`. Here `category == "none"` keeps recipes whose cleaned categories are empty, and a key keeps recipes that have that key. Every recipe JSON carries `categories`.

- [ ] **Step 1: Write the failing tests.**
  - `tests/test_recipes.py`:
    - `test_categories_saved_in_order`: create with `categories=["snack", "main", "main"]`, then read back `["main", "snack"]`.
    - `test_unknown_category_rejected`: POST with `categories=["pizza"]` gives 422.
    - `test_filter_by_category`: three recipes (`["main"]`, `["dessert"]`, `[]`). `?category=main` gives the first, `?category=none` gives the third, and `?category=pizza` gives 422.
    - `test_unknown_stored_key_is_dropped(db)`: set `recipe.categories = ["gone", "main"]` directly in the DB. `GET /api/recipes/{id}` shows `["main"]`, and a PUT of that body succeeds.
  - `tests/test_migrations.py`:
    - `test_categories_backfilled_from_tags`: upgrade to `"0006"` with `database_setup.run(engine, command.upgrade, "0006")`. Insert a recipe row with tags `["Hauptgericht", "vegi", "Dessert"]` (raw SQL, filling the NOT NULL columns). Upgrade to head. Expected: `categories == ["main", "dessert"]` and tags unchanged.
- [ ] **Step 2: Run** `pytest tests/test_recipes.py tests/test_migrations.py -v`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement.** Migration `0007` does two things:
  - `batch_alter_table("recipes")` adds `categories` as JSON, `nullable=False`, `server_default="[]"`, and `ai_categorized_at` as a nullable DateTime.
  - It backfills every recipe row by running its tags through a **frozen copy** of the word table and matcher inside the migration file (no import from `app.categories`, so the migration never changes with the app; same reasoning as `0006`'s written-out defaults). Downgrade drops the column.
- [ ] **Step 4: Run** `pytest -q`. Expected: all PASS, including `test_migration_matches_models`.
- [ ] **Step 5: Commit** `feat(categories): stored on recipes, filled from tags, filter in the list`.

### Task 3: Suggestions ranked by slot

**Files:**
- Modify: `backend/app/suggestions_api.py`
- Test: `tests/test_suggestions.py`

**Interfaces:**
- Consumes: `categories.slot_group`, `schemas.Slot`.
- Produces: `GET /api/suggestions?tab=…&slot=<breakfast|snack|lunch|dinner>`, where `slot: schemas.Slot | None = None`.

- [ ] **Step 1: Write the failing tests** (use `create_recipe(..., categories=[...])`):
  - `test_slot_ranks_fitting_first`: on the `new` tab (newest first), create in this order: Kuchen `["baking"]`, Ohne `[]`, Beilage `["side"]`, Lasagne `["main"]`, Suppe `["soup"]`. With no slot: Suppe, Lasagne, Beilage, Ohne, Kuchen. With `&slot=snack`: Kuchen, Beilage, Ohne, Suppe, Lasagne.
  - `test_slot_keeps_tab_order_inside_groups`: on the `favorites` tab, two `main` favourites rated 5 and 3 and one `baking` favourite rated 4. With `slot=dinner`: main-5, main-3, baking-4. With no slot: main-5, baking-4, main-3.
  - `test_limit_after_grouping`: create a `main` recipe first (oldest), then 3 `baking` ones. `?tab=new&slot=dinner&limit=1` gives the main recipe.
  - `test_slot_never_hides`: with `slot=breakfast`, the count equals the count without a slot.
  - `test_bad_slot`: `slot=brunch` gives 422.
- [ ] **Step 2: Run** `pytest tests/test_suggestions.py -v`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement.** After each tab has built `chosen` (its own order), and only if `slot` is set: `chosen.sort(key=lambda r: slot_group(r.categories, slot))`. Python's sort is stable, so the tab order inside each group stays. Then apply `[:limit]`.
- [ ] **Step 4: Run** `pytest tests/test_suggestions.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(suggestions): what fits the slot comes first`.

### Task 4: Categories from imports

**Files:**
- Modify: `backend/app/jsonld.py`. `_tags(node)` becomes `_tags_and_categories(node) -> tuple[list[str], list[str]]`: split as today (comma-split, dedupe), then `from_words` on the values. The leftovers become tags (still `[:MAX_TAGS]`, `[:40]` each) and the matches become categories. `draft_from_node` returns `"categories"`. Microdata and Swissmilk go through `draft_from_node`, so they need nothing extra.
- Modify: `backend/app/ai.py`:
  - `RECIPE_PROMPT`: add `"categories": [str]` to the JSON shape, plus a rule line listing the ten keys with a short German gloss each, e.g. `breakfast` (Frühstück/Zmorge), `apero` (Apéro, Fingerfood), `starter` (Vorspeise), `soup`, `salad`, `main` (Hauptgericht), `side` (Beilage), `dessert`, `baking` (Kuchen, Gebäck, Brot), `snack` (Znüni/Zvieri). Pick all that fit; `[]` if unsure.
  - `validate_draft` returns `"categories": categories.clean(_list(data.get("categories")))`.
  - `FakeClient`'s recipe answer gains `"categories": ["main", "pizza"]`.
  - `ai.translate`'s input and output stay as they are (no categories).
- Modify: `backend/app/importer.py` only if a draft dict is rebuilt key by key somewhere and would drop `categories`. Check with `grep -n '"tags"' backend/app/importer.py backend/app/inbox_api.py`.
- Test: `tests/test_jsonld.py`, `tests/test_ai.py`, `tests/test_translate.py`

**Interfaces:**
- Consumes: `categories.from_words`, `categories.clean`.
- Produces: every import draft dict has `categories: list[str]`.

- [ ] **Step 1: Write the failing tests.**
  - `test_jsonld.py::test_category_split_from_tags`: a node with `recipeCategory: "Hauptgericht, Vegetarisch"` and `keywords: "schnell"` gives `draft["categories"] == ["main"]` and `draft["tags"] == ["schnell", "Vegetarisch"]`. The order follows today's `keywords`-then-`recipeCategory` loop, so check the existing order and assert it.
  - `test_jsonld.py::test_all_values_are_categories`: `recipeCategory: ["Hauptgericht", "Dessert"]` gives categories `["main", "dessert"]` and tags `[]`.
  - `test_ai.py::test_draft_categories_cleaned`: `validate_draft` on an answer with `"categories": ["snack", "pizza", "snack", 7]` gives `["snack"]`. A missing key gives `[]`.
  - An inbox processing test through the fake AI (extend the existing one in `test_inbox.py` or `test_paste_text.py`): the stored draft has `categories == ["main"]`.
  - `test_translate.py::test_translation_keeps_categories`: a recipe with `["main"]` translated with the fake still has `["main"]`, and the fake's received text has no `categories` key.
- [ ] **Step 2: Run** `pytest tests/test_jsonld.py tests/test_ai.py tests/test_translate.py tests/test_inbox.py tests/test_paste_text.py -v`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement** as described under Files.
- [ ] **Step 4: Run** `pytest -q`. Expected: all PASS.
- [ ] **Step 5: Commit** `feat(import): categories from the website's data and from the AI`.

### Task 5: Categories in the form, view and list (frontend)

**Files:**
- Create: `frontend/src/categories.ts`: `export const CATEGORIES = [...] as const; export type Category = (typeof CATEGORIES)[number];` with the order from Global Constraints and a comment pointing to `backend/app/categories.py`.
- Modify: `frontend/src/recipes.ts`: `RecipeSummary.categories: Category[]`, `RecipeInput.categories: Category[]`, `RecipeFilter.category?: Category | 'none' | ''`.
- Modify: `frontend/src/locales/de.ts`, `en.ts`. Under `recipes`:
  - `categories` (label): "Kategorien" / "Categories".
  - `category: { breakfast: …, … }` with the texts from the spec's table.
  - `allCategories`: "Alle" / "All".
  - `noCategory`: "Ohne Kategorie" / "No category".
- Modify: `frontend/src/pages/RecipeEdit.tsx`:
  - Toggle chips for the ten categories below the tags field, kept as `Category[]` in form state.
  - Prefilled from `recipe.categories`, or from `draft.categories ?? []` for a draft.
  - Sent in `RecipeInput`, sorted in `CATEGORIES` order.
- Modify: `frontend/src/inbox.ts`: `Draft` has `categories?: Category[]`, optional because older drafts don't have it.
- Modify: `frontend/src/pages/RecipeView.tsx`: category chips (translated) before the tag chips, in a visibly different style from tags.
- Modify: `frontend/src/pages/Recipes.tsx`: a chip row "Alle · <ten> · Ohne Kategorie" above the tag row. It's single choice, passed as `category` to `fetchRecipes`, and works together with `q`, `tag` and `onlyMine`.
- Test: `e2e/tests/recipes.spec.ts` (extend). Check how drafts are set up in `e2e/tests/import.spec.ts`.

**Interfaces:**
- Consumes: `categories` on every recipe JSON; `GET /api/recipes?category=`.
- Produces: `CATEGORIES` and `Category` from `frontend/src/categories.ts`, and the locale keys `recipes.category.<key>`, which Task 6 doesn't need but can reuse.

- [ ] **Step 1: Write the failing e2e test** `recipes.spec.ts › categories`:
  - Create a recipe by hand, tick "Hauptgericht" and "Apéro", save. The view shows both chips.
  - On Rezepte, "Hauptgericht" shows it, "Dessert" doesn't, and "Ohne Kategorie" doesn't.
  - Edit, untick both, save. "Ohne Kategorie" now shows it.
- [ ] **Step 2: Add a draft test** to `import.spec.ts`. An imported draft (fake AI) opens with "Hauptgericht" ticked. Also seed an inbox draft **without** a `categories` key (through the same route the existing tests use to seed drafts, or directly in the DB if that's how they work). It opens without error, with nothing ticked. This covers Review Focus 1.
- [ ] **Step 3: Run** the two specs the way the e2e README says. Expected: FAIL.
- [ ] **Step 4: Implement** as described under Files.
- [ ] **Step 5: Run** the specs again, then `npm run lint`, `npm run type-check` and `npm test` in `frontend/`. Expected: all pass.
- [ ] **Step 6: Commit** `feat(recipes): categories in the form, the recipe and the list`.

### Task 6: "Für" slot row in the suggestion panel

**Files:**
- Modify: `frontend/src/plan.ts`: `fetchSuggestions(tab: SuggestionTab, q: string, slot: Slot | null)` sends `slot` only when set.
- Modify: `frontend/src/components/plan/SuggestionPanel.tsx`:
  - New optional prop `slot?: Slot`. When it's given (phone sheet), it's the initial choice and nothing is persisted.
  - Without it (iPad), the initial choice is read from localStorage key `plan.suggestionSlot`, and every change is written back. Both accesses are in try/catch, and an invalid stored value means `null`.
  - A row above the tabs: label "Für", then "Alle" and the four slot names (reuse `plan.slots.*`). Single choice, same chip style as the tabs.
  - The choice goes into the effect's dependencies.
- Modify: `frontend/src/components/plan/DayView.tsx`: pass `slot={adding}` to `SuggestionPanel`.
- Modify: locales, under `plan`: `suggestFor`: "Für" / "For", and `allSlots`: "Alle" / "All".
- Test: `e2e/tests/plan.spec.ts`, `e2e/tests/plan-phone.spec.ts`

**Interfaces:**
- Consumes: `GET /api/suggestions?slot=` from Task 3; `Slot`, `SLOTS` from `plan.ts`; the `categories` field on recipe create from Task 2.

- [ ] **Step 1: Write the failing e2e tests.**
  - `plan.spec.ts › slot row ranks`: create recipes "Kuchen" `["baking"]` (older) and "Lasagne" `["main"]` (newer) through the API. On the **Neu** tab, both "Alle" and "Znacht" show Lasagne first; "Znüni & Zvieri" shows Kuchen first. Reload the page: "Znüni & Zvieri" is still selected. Tap-tapping Kuchen into a Znacht cell still works, because the slot only affects order.
  - `plan-phone.spec.ts › sheet opens for the tapped slot`: "+" on Zmorge opens the sheet with "Zmorge" selected. Then open the iPad viewport in the same browser context (or read localStorage): the stored choice isn't `breakfast`. This covers Review Focus 4.
- [ ] **Step 2: Run** both specs. Expected: FAIL.
- [ ] **Step 3: Implement** as described under Files.
- [ ] **Step 4: Run** both specs, the full e2e suite, `npm run lint`, `npm run type-check`, `npm test` in `frontend/`, and `pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(plan): suggestions for a chosen slot`.

### Task 7: Sorting existing recipes with the AI (backend)

**Files:**
- Modify: `backend/app/ai.py`:
  - `CATEGORIZE_PROMPT` (German, like the other prompts). It reuses the ten keys and their glosses from Task 4's `RECIPE_PROMPT` line; move that line into a shared constant `CATEGORY_GLOSSES` so both prompts use the same text. It asks for `{"<id>": [keys]}` only.
  - `CATEGORIZE_MARKER`, so `FakeClient` can answer: it returns `["main"]` for every id it receives, and `["pizza"]` plus an extra id `"999999"` that wasn't sent, so validation is exercised.
  - `categorize(client: AiClient, recipes: list[dict]) -> tuple[dict[int, list[str]], int | None]`. The input is `[{id, title, tags, ingredients: [str]}]`. The output maps only ids that were sent to cleaned keys, plus the tokens. Raises `AiFailed` when the answer isn't a JSON object.
- Create: `backend/app/categorize_api.py`, with a router registered next to the others in `backend/app/main.py`:
  - `BATCH = 25` and `MAX_INGREDIENTS = 15`.
  - `_untried(db) -> list[models.Recipe]`: live recipes with `clean(categories) == []` and `ai_categorized_at IS NULL`, ordered by id.
  - `GET /api/recipes/categorize`, parent only: returns `{"remaining": len(_untried(db))}`.
  - `POST /api/recipes/categorize`, parent only, body `schemas.CategorizeIn {recipe_id: int | None = None}`. It returns `schemas.CategorizeOut {categorized: int, remaining: int}`. Steps:
    1. Pick the batch: with an id, that one recipe (404 if it doesn't exist or is deleted, 400 `already_categorized` if it has categories); without an id, `_untried(db)[:BATCH]`. An empty batch returns `{0, 0}` without an AI call.
    2. `ai.take_call(db, parent, "categorize")`, then `ai.categorize(...)`. On `AiFailed`, return a 502 `ai_failed` and change no recipe.
    3. Record `call.tokens`. For every recipe in the batch, set `ai_categorized_at = utcnow()`, and set `categories` only if the recipe's cleaned categories are still empty. Refresh before writing.
    4. Commit and return.
  - In `backend/app/main.py`, include `categorize_api.router` **before** `recipes_api.router`. Otherwise `GET /api/recipes/{recipe_id}` (an int path) catches `/api/recipes/categorize` and answers 422.
- Modify: `backend/app/schemas.py`: `CategorizeIn`, `CategorizeOut`.
- Modify: the error-text tables, if `already_categorized` needs a text. Check how `tests/test_error_texts.py` finds error codes, and add `already_categorized` to both locales' error texts in Task 8.
- Test: `tests/test_categorize.py`

**Interfaces:**
- Consumes: `categories.clean`, `ai.take_call`, `ai.client_for`, the `Recipe.ai_categorized_at` column from Task 2.
- Produces: `GET`/`POST /api/recipes/categorize` as above.

- [ ] **Step 1: Write the failing tests** in `tests/test_categorize.py`. They use the fake AI, so set `AI_FAKE=1` and whatever else the AI fixtures in `test_translate.py` set.
  - `test_batch_fills_untried`:
    - Recipes A `[]`, B `["dessert"]`, C `[]`.
    - POST `{}` gives `{"categorized": 2, "remaining": 0}`.
    - A and C are now `["main"]`, and B is unchanged.
    - `GET` gives `{"remaining": 0}`.
    - Exactly one `AiCall` was made, with purpose `"categorize"`.
  - `test_batch_size`: 30 untried recipes. The first POST gives `{"categorized": 25, "remaining": 5}`; a second gives `{5, 0}`.
  - `test_unknown_ids_and_keys_ignored`: the fake's extra id and the `"pizza"` key change nothing, and no error is raised.
  - `test_not_sent_again`: monkeypatch `ai.categorize` to return `{}`. After one POST, the recipe is still `[]`, `remaining == 0`, and a second POST makes no AI call.
  - `test_edited_meanwhile_not_overwritten`: monkeypatch `ai.categorize` to set the recipe's categories to `["soup"]` in the DB before returning `{id: ["main"]}`. Afterwards the recipe has `["soup"]`.
  - `test_single_recipe_ignores_tried`: the recipe has `ai_categorized_at` set and no categories. POST `{"recipe_id": id}` fills it. A recipe that has categories gives 400 `already_categorized`.
  - `test_failed_answer_marks_nothing`: `ai.categorize` raises `AiFailed`. The POST gives 502, and `remaining` is unchanged.
  - `test_children_refused`: a child's POST and GET both give 403.
  - `test_ai_off`: 503, as for translation.
  - `test_empty_batch_no_call`: with no untried recipes, `{0, 0}` comes back and no `AiCall` is recorded.
- [ ] **Step 2: Run** `pytest tests/test_categorize.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** as described under Files.
- [ ] **Step 4: Run** `pytest -q`. Expected: all PASS.
- [ ] **Step 5: Commit** `feat(categories): the AI sorts recipes without a category`.

### Task 8: The AI sorting buttons (frontend)

**Files:**
- Modify: `frontend/src/recipes.ts`:
  - `fetchUncategorized(): Promise<number>`, from `GET /api/recipes/categorize`.
  - `categorize(recipeId?: number): Promise<{ categorized: number; remaining: number }>`.
- Modify: `frontend/src/pages/Recipes.tsx`:
  - Shown when the "Ohne Kategorie" filter is chosen, the user is a parent, the AI is on (use the same check the recipe view's translate button uses) and the remaining count is above 0: a button "Mit KI einordnen ({{count}})".
  - Clicking it loops `categorize()` until `remaining === 0`, showing "{{done}} von {{total}}" during the run.
  - It stops at the first error and shows `errorMessage(err)`. Afterwards it reloads the list and the count.
  - The button is disabled while running.
- Modify: `frontend/src/pages/RecipeView.tsx`: for a parent, with the AI on and a recipe without categories, a button "Kategorien vorschlagen" calls `categorize(recipe.id)` and reloads the recipe. Errors are shown the same way as the translate button's.
- Modify: locales (de/en):
  - `recipes.categorizeAll`: "Mit KI einordnen ({{count}})" / "Sort with AI ({{count}})".
  - `recipes.categorizeProgress`: "{{done}} von {{total}}" / "{{done}} of {{total}}".
  - `recipes.categorizeOne`: "Kategorien vorschlagen" / "Suggest categories".
  - The error text for `already_categorized`.
- Test: `e2e/tests/recipes.spec.ts`

**Interfaces:**
- Consumes: Task 7's endpoints and Task 5's "Ohne Kategorie" filter.

- [ ] **Step 1: Write the failing e2e tests.** They use the e2e fake AI, so check how `import.spec.ts` turns it on.
  - `recipes.spec.ts › AI sorts uncategorised`: create two recipes without categories as a parent. On the "Ohne Kategorie" filter, the button reads "Mit KI einordnen (2)". After clicking it, the list under "Ohne Kategorie" is empty and "Hauptgericht" lists both.
  - `recipes.spec.ts › suggest categories on one recipe`: the button on the view fills "Hauptgericht" and then disappears.
  - `recipes.spec.ts › children don't see it`: logged in as a child, neither button shows.
- [ ] **Step 2: Run** the spec. Expected: FAIL.
- [ ] **Step 3: Implement** as described under Files.
- [ ] **Step 4: Run** the full e2e suite, `npm run lint`, `npm run type-check` and `npm test` in `frontend/`, and `pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(recipes): sort recipes with the AI`.
