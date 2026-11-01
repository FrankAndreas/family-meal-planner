# Swissmilk Recipes in "Was habe ich?" — Design

Status: agreed with Andreas on 2026-11-01. Builds on `2026-11-01-use-up-design.md` ("Was habe ich?"). Migusto comes
later, in its own design: its search runs on an undocumented internal interface, and whether to use it is still open.

## Why

When the family's own collection has nothing that fits what's at home, Andreas wants ideas from a trusted recipe
site. He also wants to keep a good find for later use. He asked for the most secure way to do this. The worry is
prompt injection: text from foreign web pages reaching the AI. More generally, the worry is the app talking to
arbitrary websites.

## Goals

- From "Was habe ich?", with the ingredients already typed, search **swissmilk.ch** on request.
- Results look like the family's own: photo, title, "✓ Kartoffeln, Lauch", "fehlt: Rahm", and the same Aufbrauchen /
  Jetzt kochen switch and ranking.
- From a result, open the original page, or **take it over** into the family's recipes.

## Non-goals

- A free-text web search, other sites, AI suggestions. Migusto is a separate later step.
- Searching on every keystroke: the external search runs only when asked.

## Anti-goals

- **Any AI on what comes from these searches.** Neither search results nor recipes imported from them go through
  the AI. If the structured data can't be read, the result is left out, or the import fails with a clear message.
- The app talking to any host other than `www.swissmilk.ch` (and its image host, see below) for this feature.
- Showing or storing page markup: only extracted, checked data.

## Recon (2026-11-01, so the builder doesn't have to repeat it)

- **Search:** `https://www.swissmilk.ch/de/suche/?q=<words>` renders its results in the HTML. A result is an
  `<a href="/de/rezepte-kochideen/rezepte/<ID>/<slug>/" title="<Rezepttitel>">` inside `li.TeaserGridSection--item`,
  with an image from `https://api.swissmilk.ch/wp-content/uploads/…`.
- **Recipe pages:** there is no JSON-LD `Recipe` (only `Organization`, `WebSite`, `HowTo`, `BreadcrumbList`). The
  recipe is in **schema.org microdata**: `itemprop` `name`, `recipeIngredient` (one per line, e.g. "800 g
  mehligkochende* Kartoffeln"), `recipeInstructions`, `recipeYield`, `image`, `prepTime`, `cookTime`, `totalTime`,
  `recipeCategory`, `keywords`. The `HowTo` JSON-LD has the steps and `totalTime`.
- **robots.txt:** recipes and search are allowed for normal user agents. Only AI-*training* crawlers are excluded
  from `/de/rezepte-kochideen/rezepte/`. This feature isn't one: it fetches pages a person asked for.
- **Legal notice:** no separate terms of use, only "©2026" and the publisher (Schweizer Milchproduzenten SMP).
  Taking single recipes into a family's private collection, with the source link kept, is private use.
- Today a pasted Swissmilk link goes to the AI, because `jsonld.py` finds no recipe. The microdata reader below
  fixes that too.
- Saved copies of a search page and a recipe page from this recon are in the session scratchpad; save fresh ones as
  test fixtures (`tests/pages/`).

## How it works (decided)

### In "Was habe ich?"

- Below the family's own results is a button: **"Auch bei Swissmilk suchen"**. It's shown when at least one
  ingredient is typed.
- Tapping it shows a "Swissmilk" section with a loading state. The section updates when the chips or the mode change,
  as long as it's open. Leeren closes it (*builder's call* on exact behaviour; never a search per keystroke).
- Each result shows: photo, title, the site's name, ✓ used, fehlt, and two buttons:
  - **Ansehen ↗**: the original page, in a new tab.
  - **Übernehmen**: imports it as below.
- **Already there** (*Claude's call, 2026-11-01*): compared by Swissmilk's recipe number, the `<ID>` in
  `/rezepte/<ID>/` (any language, slash or query).
  - A live recipe whose `source_url` has that ID shows **"schon in deinen Rezepten"** with a link to it.
  - An inbox item still waiting or reading with that link shows **"wartet im Posteingang"**.
  - Neither shows an Übernehmen button. Deleted recipes don't count.
  - After Übernehmen, the result switches to the matching state at once.
- If Swissmilk can't be reached or its page can't be read, the section says so ("Swissmilk ist gerade nicht
  erreichbar"). The family's own results are never affected.
- Texts from the locales, German and English, Swiss conventions.

### Backend (decided where security matters; the rest is the builder's call)

- **Only fixed addresses.** A new module talks to exactly two hosts, over HTTPS:
  - `www.swissmilk.ch`, for the search page and recipe pages.
  - `api.swissmilk.ch`, for photos only.
- **Photos go through the backend** (*decided from "most secure", 2026-11-01*). The browser never loads anything
  from Swissmilk, so `frontend/security-headers.conf` (`img-src 'self' blob: data:`) stays as it is, and family
  devices never contact Swissmilk.
  - A small endpoint serves a result's photo: only `https://api.swissmilk.ch/wp-content/uploads/…` addresses that
  the search itself returned (no free URL parameter: e.g. the result's index or a server-side token).
  - Downscaled and re-encoded with the existing photo code, size-limited and cached like the pages.
  - Photos on other hosts (e.g. `res.cloudinary.com` in the microdata) are not used.

  Every fetch goes through `fetch.py`, which keeps its public-address checks and pinning, plus a host allowlist
  that applies to **every redirect**. Any other host is refused.
- **Search:** the typed words are joined into `q` (*builder's call*: all words, or the first few if Swissmilk returns
  nothing for many; check against the live site and note the choice).
  - Only links matching `^/de/rezepte-kochideen/rezepte/[A-Za-z0-9_]+/[a-z0-9-]+/$` count.
  - The search page lists about 48 teasers and matches any of the words. The first **12** recipe links are the
    candidates (*Claude's call*). Only those 12 recipe pages are fetched; candidates that don't fit are dropped, and
    the rest are shown ranked by the matcher (Swissmilk's order breaks ties).
- **Reading a recipe page:** a microdata reader for schema.org `Recipe` (new, next to `jsonld.py`). It gives the same
  draft shape as `jsonld.recipe_from_html`. Ingredient lines are split into amount, unit and name with the existing
  `ingredient_parse.parse_line`. The "*" footnote marks are dropped.
- **Ranking:** results are checked with the "Was habe ich?" matcher: typed words, basics, optional notes, at most 2
  missing in Jetzt kochen. They're ordered like the family's own results, minus "last eaten". A result with nothing
  used is left out.
- **Checked data only:** title ≤ 200 characters, at most 60 ingredient lines, names ≤ 200 characters, at most 5
  photos considered. Nothing else from the page is kept.
- **Politeness and speed:**
  - Recipe pages are fetched at most 4 at a time.
  - Pages are cached for about a day (*builder's call*: in memory is fine).
  - The whole search has a time budget of about 15 s, and partial results are fine.
  - At most one Swissmilk search per person every few seconds (*builder's call* on the number).
- **Endpoint (builder's call on shape):** e.g. `GET /api/use-up/swissmilk?have=…&mode=…`, returning results with
  `title`, `url`, a photo address on the app's own backend, `used`, `missing`, and the already-there state
  (`recipe_id`, or waiting in the inbox). Any logged-in person may search.

### Taking a recipe over ("Übernehmen")

- It goes through the existing link import: an inbox item of kind `url`. Parents' imports are read at once, and
  children's wait in the inbox for a parent, as today.
- The importer reads the page with the new microdata reader before anything else.
- **Every link on `www.swissmilk.ch`** (*Claude's call*, from the anti-goal) gets the same treatment, whether it was
  pasted, mailed or taken over, and whatever the page (recipe, article, `/fr/`).
  - It is fetched with the Swissmilk host allowlist: a redirect to another host is refused.
  - It **never goes to the AI**. If the reader finds no recipe, the link is skipped. A `url` item then fails with a
    clear message.
  - In a mail, the mail's own text can still go to the AI as today, since that's the family's own mail.
- Other links keep today's behaviour, but also get the microdata reader before the AI, which helps any site that
  uses microdata.
- The photo is downloaded by the existing photo code, from `api.swissmilk.ch` only.
- `source_url` is the Swissmilk page, so the recipe always points back to its origin.

## Tests

- pytest with saved pages, never the network:
  - the search page parser: only recipe links, at most 12 candidates, foreign hosts ignored
  - the photo endpoint: only addresses from a search result on `api.swissmilk.ch`, nothing else
  - the microdata reader on the saved recipe page: title, ingredients split, steps, servings, photo
  - the host allowlist, including a redirect to another host
  - ranking and filtering with the matcher
  - "schon in deinen Rezepten"
  - import of a Swissmilk link without any AI call (the fake AI must not be called)
  - a page without microdata failing cleanly
  - the time budget and partial results with a slow fake fetch
- Playwright with the backend talking to a fake Swissmilk. How to point it there in e2e is the *builder's call*,
  e.g. a test-only base URL setting that's off by default. It covers: type ingredients, "Auch bei Swissmilk suchen",
  see a result with ✓ and fehlt, Übernehmen, and the recipe shows up as a draft or recipe. Run on the tablet and
  the phone.

## Settled by the builder check (builder's calls, noted)

- Photo: the first `image` on `api.swissmilk.ch`.
- An equipment row marked as an ingredient ("ofenfeste Form ca. 2 l") is dropped.
- A line like "Salz, Pfeffer, Muskatnuss" keeps all three names when parsed, not Pfeffer as a note.

## Left to the builder

Everything marked *builder's call*, module and component structure, exact texts.
