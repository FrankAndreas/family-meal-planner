# Recipe Categories and Suggestions That Fit the Slot — Design

Status: agreed with Andreas on 2026-11-05 (he chose multi-select categories, suggestions ranked by slot, and asked for the
design without a round of questions. Every decision below not stated by him is marked *builder's call* or *my call*.
Builds on the main design (`2026-10-29-meal-planner-design.md`).

## Why

The suggestion panel shows the same recipes whatever slot is being filled. When you plan *Znüni & Zvieri*, the main
dishes are mixed in with the snacks, and when you plan *Znacht* you scroll past cakes. Free tags can't fix this,
because they aren't consistent: one person writes "Hauptgang", another "Main", a third nothing. Imports bring
whatever the website's `recipeCategory` says.

A small **fixed** list of categories, set automatically at import wherever possible, gives the app one reliable
signal to bring the fitting recipes up first.

## Goals

- Each recipe can have **zero or more categories** from a fixed list (multi-select: a Wähe is a main dish and an
  apéro).
- The suggestion panel can be told **which slot is being filled**. It then **ranks** recipes that fit that slot
  first. It never hides anything.
- Imports fill in categories without anyone having to think about it: from the website's structured data, or from
  the AI.
- Existing recipes get categories from their existing tags where the tags already say it, with no AI and no manual
  sorting session.
- On the Rezepte page you can filter by category.

## Non-goals

- **No hiding.** A slot never filters the list down. An unusual choice (a soup for Zmorge, a cake for Znacht) stays
  one scroll away.
- **No family-editable category list.** The list is fixed in code. Free tags stay for everything else (*vegi,
  schnell, Kinder-Liebling*).
- **No learning from history** (e.g. "this was always planned for Znacht"). It was considered, not chosen. It could
  come later as a second signal.
- **No bulk AI run** to categorise old recipes.
- No change to which recipes a tab contains (Favoriten, Lange her, Neu, Nochmals planen?). Only their order changes.

## Anti-goals

- Making a recipe vanish because it has no category, or the wrong one. That would be worse than no ranking at all,
  since nobody would notice what's missing.
- Doubling the work: the same word showing up both as a category and as a tag on new imports ("Dessert" chip and
  "Dessert" tag).
- A category list so long that choosing one is a decision. About ten entries, each obvious.

## The categories (my call)

Stored as stable keys. The text shown comes from `src/locales` (German and English). Because the keys aren't
language text, **translating a recipe never touches them**.

| Key | Deutsch | English |
|-----|---------|---------|
| `breakfast` | Frühstück | Breakfast |
| `apero` | Apéro | Apéro |
| `starter` | Vorspeise | Starter |
| `soup` | Suppe | Soup |
| `salad` | Salat | Salad |
| `main` | Hauptgericht | Main dish |
| `side` | Beilage | Side dish |
| `dessert` | Dessert | Dessert |
| `baking` | Gebäck & Kuchen | Baking |
| `snack` | Snack | Snack |

This order is the order everywhere they're listed.

## Which categories fit which slot (my call)

| Slot | Fits |
|------|------|
| Zmorge (`breakfast`) | breakfast, baking |
| Znüni & Zvieri (`snack`) | snack, baking, apero |
| Zmittag (`lunch`) | main, soup, salad, starter |
| Znacht (`dinner`) | main, soup, salad, starter |

Side dishes and desserts fit no slot on their own. They're usually added *next to* a main dish (a slot holds
several entries), so they rank in the middle group (see below) rather than at the top or bottom. The table lives in
one place in the backend, so it's easy to change.

## Ranking (decided: rank, never filter)

When the panel has a slot set, each recipe in the tab's result falls into one of three groups:

1. **Fits:** at least one of its categories fits the slot.
2. **Neutral:** no categories at all, or only `side` / `dessert`.
3. **Doesn't fit:** it has categories, and none of them fit the slot.

The groups come in that order. **Within a group, the tab's own order stays exactly as today** (best average for
Favoriten, longest ago for Lange her, and so on). The grouping is applied **before** the `limit` cut, so a fitting
recipe is never cut off by unfitting ones ahead of it.

Uncategorised recipes sit in the middle on purpose: we don't know, so they're neither pushed up nor buried.

With no slot set ("Alle"), the order is exactly today's.

The search box and tag filter work as today; the ranking applies to their results too.

## Where the slot comes from (my call)

- **Planning screen (iPad, layout A):** the panel gets a row of choices above the tabs: **Für: Alle · Zmorge ·
  Znüni & Zvieri · Zmittag · Znacht**. Default *Alle*. The choice is **kept on that device** (localStorage, wrapped
  so a blocked storage just means *Alle*), because a Friday session is usually many Znacht in a row. Tap-tap and
  drag work exactly as today. The slot choice only affects order, not where a card can be dropped.
- **Phones (day view):** tapping "+" on a slot opens the suggestions for that slot, so the slot is **set from the
  tap**, shown preselected in the same row, and can be changed there. It doesn't overwrite the iPad's remembered
  choice (*builder's call* whether the phone remembers anything at all; suggestion: it doesn't, since the tap always
  sets it).
- **Was habe ich?** and the Rezepte list: no slot, no ranking change.

## Setting categories on a recipe

- **Recipe form** (new and edit, open to everyone as today): the ten categories as toggle chips, below the tags.
  Nothing preselected for a new hand-written recipe.
- **Recipe view:** the recipe's categories shown as small chips near the tags (*builder's call* on exact placement).
- **Import drafts** come with categories prefilled; the parent sees and can change them in the draft like any other
  field.
- The API accepts only known keys; unknown ones are a validation error from the form, and dropped silently when they
  come from an import (AI answer or website).

## Filling categories automatically

### From the website's structured data (JSON-LD, microdata, Swissmilk)

- `recipeCategory` and `keywords` values are matched against a word table, ignoring
  case and accents (reuse `sort_key`). The table is the builder's to complete; it must at least cover:

  | Category | Words (de / en / fr where common) |
  |----------|-----------------------------------|
  | main | Hauptgericht, Hauptspeise, Hauptgang, Main course, Main dish, Plat principal |
  | dessert | Dessert, Nachspeise, Nachtisch, Süssspeise |
  | apero | Apéro, Apero, Fingerfood, Appetizer, Häppchen |
  | starter | Vorspeise, Starter, Entrée |
  | soup | Suppe, Soup, Soupe |
  | salad | Salat, Salad, Salade |
  | side | Beilage, Side dish, Accompagnement |
  | breakfast | Frühstück, Zmorge, Brunch, Breakfast |
  | baking | Gebäck, Kuchen, Backen, Brot, Guetzli, Torte, Cake, Baking |
  | snack | Snack, Zvieri, Znüni, Imbiss |

  Matching is by whole word (or the whole value), not substring: "Salatsauce" is not a salad. The match must hold up
  the way the use-up design's ingredient matching does: put the table's words and a few must-not-match cases in tests.
- A value that **matched a category is not also added as a tag**. Values that didn't match go into the tags as
  today. Existing tags on existing recipes are left alone (see migration).

### From the AI (page text, mail, pasted text)

- The import prompt asks for `"categories"` as a list chosen from the ten keys, with a one-line description of each
  so the model picks consistently. The answer is validated like the rest: unknown keys dropped, duplicates removed.
- No extra AI call: it's one more field in the existing request.
- Translating a recipe doesn't send or change categories.

### Existing recipes (one-off migration)

- An Alembic migration (`0007_categories`) adds the column (a JSON list, default empty, like `tags`) and fills it
  for existing recipes by running **their tags** through the same word table.
- Tags that matched are **kept** as tags on existing recipes (*my call*: removing someone's tags behind their back is
  surprising, and they're easy to remove by hand). Only new imports skip the duplicate.
- Recipes with no matching tags stay uncategorised, and so rank neutral. The Rezepte filter's **"Ohne Kategorie"**
  choice (below) makes it quick to find and tag them over time.

## Rezepte page

- Next to the tag filter: a category filter with the ten categories plus **Ohne Kategorie**, single choice
  (*builder's call*: same chip style as the tag filter, can be combined with search and tags).
- `GET /api/recipes` takes `category=<key>` or `category=none`.

## API summary (builder's call on details)

- `Recipe` gets `categories: list[str]` in the model, `RecipeIn`, `RecipeOut` and `RecipeSummary`.
- `GET /api/suggestions` takes an optional `slot` (one of the four slot keys). Without it the order is unchanged.
- `GET /api/recipes` takes an optional `category`.
- The slot → categories table and the word table are in the backend. The frontend only needs the list of keys (for
  the chips) and the locale texts.

## Tests that must exist

- Ranking: for each slot, a mix of fitting, neutral (none / only side / only dessert) and unfitting recipes comes
  back in group order, with the tab's own order inside each group; the limit applies after grouping; no slot means
  today's order.
- Word table: each listed word maps to its category; "Salatsauce", "Suppengrün", "Kuchenblech" don't map; case and
  accents don't matter.
- JSON-LD import: `recipeCategory: "Hauptgericht, Vegetarisch"` gives `categories: ["main"]` and tags
  `["Vegetarisch"]`.
- AI import: unknown and duplicate keys are dropped.
- Migration: tags map to categories, tags stay.
- Translation leaves categories untouched.
- Frontend: the "Für" row changes the order; the phone sheet opens with the tapped slot selected; visible text comes
  from the locales (`npm run lint`, including `check-texts`).

## Left to the builder

- The visual design of the "Für" row and the category chips, within the existing style.
- Whether the panel shows a subtle hint where the "fits" group ends.
- Exact placement of categories in the recipe view.
- Extra words in the word table, as long as the tests above hold.
