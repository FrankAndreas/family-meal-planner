# "Was habe ich?" — Recipes for What's at Home — Design

Status: agreed with Andreas on 2026-11-01. Builds on the main design (`2026-10-29-meal-planner-design.md`).

## Why

Andreas opens the vegetable drawer and sees potatoes that need using soon, maybe a leek and some tomatoes too. Mostly
it's vegetables and dairy that go bad over time. He wants **inspiration from the family's own collection** instead of
always landing on the same few dishes. Today the recipe list's search matches one word in titles, tags and ingredient
names. There's no way to ask with several ingredients at once, or to see what's missing.

## Goals

- Type in several ingredients you have at home and get recipes from the collection that use them.
- A switch between two ways of ranking:
  - **Aufbrauchen (use up):** recipes that use as many of the typed ingredients as possible. Missing ingredients are
    fine.
  - **Jetzt kochen (cook now):** recipes you can cook with what you have. Recipes missing a little still show,
    marked "fehlt: Rahm".
- **Basics** (salt, pepper, …) always count as at home, without typing them. Parents edit that list.
- Favour forgotten dishes: when the fit is equal, the recipe eaten longest ago (or never) comes first.

## Non-goals

- **No internet and no AI** in this search: only the family's own recipes. A later step *might* search a fixed list
  of recipe sites (e.g. swissmilk.ch, migusto.migros.ch) with prompt-injection precautions, but that's out of scope here
  and needs its own design.
- **No stock-keeping:** the app doesn't track what's in the fridge. What's typed is a search, not a stock list.
- No change to the Wochenplan suggestion panel (it was considered and not chosen).

## Anti-goals

- A search that confidently shows wrong matches, e.g. "Ei" finding "Reis" or "Eisbergsalat". A false hit is worse
  than a missed one here, because the point is trusting "✓ you have this".
- Treating basics as missing ("fehlt: Salz"): that would bury every recipe in "Jetzt kochen".

## Where it lives and how it looks (decided)

- On the **Rezepte** page: a switch at the top, **Suchen | 🧺 Was habe ich?**. "Suchen" is today's list unchanged.
  Same layout on phone and iPad (it's used at the drawer, often on the phone).
- In "Was habe ich?":
  - An ingredient input that makes **chips** (Enter or a suggestion adds one; × removes it). As you type, it suggests
    ingredient names that occur in the collection, so people hit the words the recipes use (*builder's call: how
    many suggestions and how they're picked*).
  - Below: the switch **Aufbrauchen | Jetzt kochen** (default: Aufbrauchen, *builder's call*).
  - Results as a list. Each result shows: photo, title, **"✓ Kartoffeln, Lauch"** (which of the typed ingredients
    it uses), **"fehlt: Rahm, Rüebli"** (recipe ingredients that are neither typed nor basics), and "zuletzt vor 5
    Wochen" / "noch nie" as on the planning screen.
  - Tapping a result opens the recipe view (from there it can be planned with the Planen button).
- The typed chips and the mode are **kept on that device** (localStorage) until cleared, so going to a recipe and
  back doesn't lose them. A "Leeren" button clears all chips (*builder's call*).
- Before anything is typed: a short hint what this is for, no results.
- Visible text from `src/locales` (German and English), as everywhere (`npm run check-texts`).

## Ranking (decided, numbers are builder's calls marked)

For a recipe: **used** = typed ingredients that match at least one of its ingredients; **missing** = its
ingredients matched by neither a typed ingredient nor a basic.

- **Aufbrauchen:** only recipes with at least one used. Order: more used first, then fewer missing, then eaten
  longest ago (never eaten counts as longest ago), then title.
- **Jetzt kochen:** only recipes with at most **2** missing (*builder's call*) and at least one used. Order: fewer
  missing first, then more used, then longest ago, then title.
- Deleted recipes never show.
- *Builder's call:* how ingredients without a name or with a note like "nach Belieben" / "optional" count (suggestion:
  an ingredient whose note says it's optional never counts as missing).

## Matching (the hard part; behaviour decided, method left to the builder)

Case and accents never matter (reuse `sort_key` in `recipes_api.py`). Beyond that, a typed ingredient should match
recipe ingredient names the way a person would. These must hold (put them in tests):

| Typed | Matches | Must not match |
|-------|---------|----------------|
| Kartoffeln | Kartoffel, festkochende Kartoffeln, Kartoffeln (mehlig) | |
| Tomate | Tomaten, Cherrytomaten, gehackte Tomaten (Dose) | Tomatenpüree is fine either way |
| Lauch | Lauch, Lauchstange | |
| Rahm | Rahm, Vollrahm, Halbrahm, saurer Halbrahm | |
| Ei | Ei, Eier | Reis, Eisbergsalat, Weizen, Hirsebrei, Griessbrei |
| Lauch | | Knoblauch, Schnittlauch, Bärlauch |
| Kartoffel | | Süsskartoffel |
| Zwiebel | Zwiebel, rote Zwiebeln | Frühlingszwiebel |
| Milch | | Kokosmilch |
| Butter | Butter, Kochbutter | Erdnussbutter |
| Milch | Milch, Vollmilch | Milchschokolade is fine either way |
| Härdöpfel | Kartoffeln (synonym) | |
| Sahne | Rahm (synonym) | |

- Light German plural/inflection handling (Tomate ↔ Tomaten, Ei ↔ Eier, Kartoffel ↔ Kartoffeln).
- Compound words: the typed word as the **head** (end) of a compound matches (Halb**rahm**, Cherry**tomaten**). As
  the start of a compound it matches only when it's long enough that it can't be an accident (*builder's call*, e.g.
  ≥ 4 letters: Lauch → Lauchstange yes, Ei → Eisbergsalat no).
- **Exception list (decided 2026-11-01):** compounds that end in the typed word but are a different food don't match.
  That includes close relatives: Knoblauch, Schnittlauch, Bärlauch (not Lauch), Süsskartoffel (not Kartoffel),
  Frühlingszwiebel (not Zwiebel), Kokosmilch (not Milch), Erdnussbutter (not Butter), …-brei (not Ei). A false ✓ is
  worse than a miss. The list lives in the code next to the synonyms; the builder extends it sensibly.
- A **short synonym list** in the code (Swiss/German/regional): Kartoffel = Härdöpfel = Erdapfel, Rahm = Sahne,
  Rüebli = Karotte = Möhre, Quark = Topfen, Zucchetti = Zucchini, Peperoni = Paprika, Nüsslisalat = Feldsalat, …
  (*builder's call* to extend sensibly; English names for recipes that were never translated are welcome but not
  required).
- Basics match **more strictly** (*Claude's call, 2026-11-01*): only as a whole word or as the head (end) of a
  compound, never as the start, so "Olivenöl" counts as Öl, "Meersalz" as Salz, "Gemüsebouillon" as Bouillon, but
  Zuckerschoten, Zuckermais, Wassermelone, Pfefferminze and Salzkartoffeln are **not** basics. Adjectives don't
  count: "mehlig" / "mehligkochend" is not Mehl. The exception list applies too.
- Words in brackets and descriptive words in an ingredient name ("(Dose)", "(mehlig)", "festkochend") don't make
  a match on their own (*Claude's call*).

## Basics ("Immer im Haus") — decided

- A family setting: a list of ingredient words, stored with the other family settings (new column on `settings`, new
  Alembic migration).
- Default: **Salz, Pfeffer, Öl, Wasser, Zucker, Mehl, Bouillon**.
- Parents edit it in **Settings → Familie** (add, remove; chips like the search). Kids see the effect but can't
  edit, like the other family settings.

## Backend (left to the builder, suggestion)

- An endpoint like `GET /api/recipes/use-up?have=Kartoffeln&have=Lauch&mode=use_up|cook_now` returning recipe
  summaries (as `RecipeSummary`, so "zuletzt …" and ratings are there) plus `used` and `missing` lists. All roles may
  use it.
- An endpoint for ingredient-name suggestions (distinct names from live recipes), or reuse of something existing.
- Settings: `staples` in `SettingsOut` / `SettingsPatch` (parents only, as now).
- The collection is small (a family's recipes), so matching in Python over `live_recipes()` is fine.

## Tests

- pytest: the matching table above, basics, both rankings and their order, deleted recipes, the setting (default,
  edit, parents only).
- Playwright (tablet, and the phone project since it's used at the drawer): type two ingredients, see a result with
  ✓ and "fehlt", switch to Jetzt kochen, open a result, come back and the chips are still there; a parent edits the
  basics and a "fehlt" disappears.

## Left to the builder

Everything marked *builder's call*, the endpoint shapes, component structure, and the exact texts (Swiss German
conventions as in `de.ts`: «», no ß, informal "du").
