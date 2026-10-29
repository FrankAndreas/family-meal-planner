# Family Meal Planner — Design

Date: 2026-10-29

## Purpose

A family of four (two parents, a teenager, a young girl) plans most of next week's meals together every **Friday**,
so the weekend shopping can happen Friday evening or Saturday. The app holds the family's recipe collection, the week
plan, and the history of what was actually eaten.

Recipes come from three places:
- **Facebook while scrolling.** Facebook can't be copied or read by other apps, so today this means screenshots that
  are often cut off or hard to read.
- **Websites while planning**, e.g. https://www.swissmilk.ch/de/rezepte-kochideen/.
- **By hand**, for the family's own classics.

The app is a sibling of the family's other self-hosted apps (family-budget-dashboard, family-job-tracking,
family-chore): same stack, same look, same NAS deployment, same login model. Where those apps already solve something
(PIN login, roles, i18n, AI client, mail inbox, Cloudflare Email Worker, Docker/NAS setup), this app **copies the
pattern**; it doesn't invent a new one.

## Goals

- Friday planning on a 10–15" screen (iPad or similar), together: the week on one screen, with suggestions from
  **favourites** and from recipes **not had in a while**.
- About 70% of next week's meals get planned; the remaining slots stay empty **on purpose** and the app doesn't nag
  about them.
- During the week, anyone (kids too) can fill a slot or add a recipe.
- Getting a recipe in from Facebook takes one share from the phone; turning it into a clean recipe happens later, under
  a parent's control.
- History of what was eaten, ratings per person, and favourites, so planning starts from "what did we like".
- Structured, scalable ingredients, so a shopping list (and Bring!) can be added later without reworking recipes.

## Non-goals (first version)

- Shopping list, combining ingredients across recipes, and Bring! upload. These come later. The data model must make
  them possible (see [Later](#later-not-in-the-first-version)).
- Nutrition values.
- Importing recipe **videos** (Reels). A caption or a link in a video post can still be imported.
- Installing as a share target (PWA Web Share Target). Mail covers Android, iPhone and desktop alike.
- Automatic translation. Translation exists only as an action a parent triggers.

## Anti-goals

- **AI costs running out of control without anyone noticing.** No AI call happens without a parent triggering it,
  every call is rate-limited per user and counted, and the AI is off when no token is set. Cost control on the
  Infomaniak side is the outer limit.
- Nothing from a mail is decoded, fetched or sent to the AI before a parent releases it.
- Making the planner feel like a to-do list: empty slots are normal, not warnings.

## Users and roles

- Each family member has a login with a **4-digit PIN**, exactly as in family-budget-dashboard (`backend/app/auth.py`):
  bcrypt hashes, JWT tokens, lockout with growing lock times after wrong PINs, the first parent "Admin" created on an
  empty database with a PIN printed once in the log, no sign-up page.
- Roles **PARENT** and **CHILD**:

| Action | Parent | Child |
|---|---|---|
| Plan meals, edit the plan, set the number of people at a meal | ✓ | ✓ |
| Add recipes by hand, edit recipes | ✓ | ✓ |
| Delete a recipe (soft delete, so history stays intact) | ✓ | – |
| Paste a URL / send a recipe by mail (lands in the inbox) | ✓ | ✓ |
| Rate, mark favourite (their own) | ✓ | ✓ |
| Close the week | ✓ | ✓ (*builder's call*) |
| **Process an inbox item** (link fetching + AI), **translate a recipe with AI** | ✓ | – |
| Settings: family size, first day of the week, family members, mail addresses, PINs | ✓ | – |

## Language

- The interface is German by default, with English as an option. Each person picks theirs, as in the budget app
  (i18next, `locales/de.ts` and `locales/en.ts`, `DEFAULT_LANGUAGE` in `.env`, the same `check-texts` lint).
- Recipes keep the language they were imported in. A parent can **translate a recipe into German** with the AI. This
  creates a German version of the text (title, ingredient names and notes, steps) and keeps the original, so the
  original can still be shown.

## Recipes

A recipe has:
- **Title, photo** (optional; for imports, taken from the website or cropped from a screenshot if the AI can say
  where), and **source**: URL, "Mail" (with sender and date), or "manuell".
- **Yield:** a number and a unit. "Personen" is the usual unit, but others like "Blech" or "Stück" are allowed.
- **Prep and cook time** (optional).
- **Ingredients, structured:** amount (optional), unit (optional), name, and note. Example: `400 | g | Hackfleisch |
  gemischt`. Ingredients can be grouped ("Für den Teig"). An ingredient without an amount ("Salz", "Pfeffer nach
  Belieben") is never scaled.
- **Steps:** a numbered list.
- **Tags:** a free list (*vegi, schnell, Kinder-Liebling, Wähe …*), used for filtering in the suggestion panel.
- **Ratings:** 1–5 stars **per person**. The app shows the average and, on tap, each person's rating. A person can
  change their rating any time.
- **Favourite:** a ★ toggle **per person**. A recipe counts as a favourite in the suggestions if anyone in the family
  marked it.
- **History** (derived): the date it was last eaten and how often it was eaten.
- **Originals:** for imported recipes, the original mail, screenshots, page URL and the raw AI answer are kept and can
  be opened from the recipe, so anyone can check what the import read.

### Scaling

- A recipe is shown for its own yield by default. When opened from a planned meal, it is shown **scaled to that meal's
  number of people** (for cooking). The number can be changed in the view without changing the plan.
- Scaling multiplies every amount that has one. Results are rounded sensibly. Counted things ("Ei", "Zwiebel", "Stück",
  no unit) round to whole or half units, never below a half. Weights and volumes round to sensible steps (e.g. 347.5 g
  → 350 g). The exact rules are the builder's call; they must be pure, tested functions, because the shopping list
  will reuse them.
- Scaling a recipe whose yield isn't in people (e.g. "1 Blech") uses the ratio between the meal's number of people and
  the family size. *Builder's call.*

## Getting recipes in

All routes end in the same place: a **draft** recipe that someone checks and saves. Nothing imported goes straight into
the collection.

### 1. Mail (main route for Facebook and phone finds)

- A family member shares the Facebook post (or anything else) **by mail** to `rezepte@<domain>`. A mail can carry the
  post's link, copied text, and **several screenshots**. Several screenshots usually mean one long recipe cut across
  screens.
- The **Cloudflare Email Worker** from family-job-tracking/family-budget-dashboard is reused almost unchanged
  (`cloudflare/email-worker`). It posts the raw mail to `/api/inbound` with `X-Inbound-Secret`, the envelope
  recipient, and the Cloudflare Access service token. It forwards to a fallback address or bounces when the NAS is
  unreachable. It accepts only mails Cloudflare found authentic (`dmarc=pass`).
- The app accepts mail only from **addresses registered for an active family member** (set by parents in the
  settings), as the budget app's `inbox.py` does. Other mails are dropped and logged.
- On arrival the app reads **only headers and the MIME structure**: sender, subject, date, the names and sizes of
  attachments, and the links in the text part. *Builder's call:* reading the plain-text part to list links is fine,
  but no URL is fetched. The raw mail is stored as a file. Nothing is decoded for content, nothing is fetched, and no
  AI runs.

### 2. URL in the app (main route while planning)

- Anyone pastes a URL. It lands in the same inbox as an item of its own.
- When a **parent** pastes it, *builder's call:* the paste counts as the release and it is processed right away. When
  a child pastes it, it waits for a parent.

### 3. By hand

- An empty recipe form, open to everyone. No inbox, no AI.

### Recipe inbox

- A list of items waiting for processing: who sent it, when, what it holds ("3 Bilder, 1 Link"), with thumbnails of
  the screenshots. *Builder's call:* thumbnails are made locally on the NAS from the attachments when the inbox is
  viewed by a parent; generating them isn't "processing". If that's not wanted, show file names only.
- A **parent** chooses **Verarbeiten** (process) or **Verwerfen** (discard). Children see **only their own items**
  (*builder's call*, so parents' mail senders and subjects stay private) and no process button.
- A badge shows how many items are waiting. It also appears on the planning screen, as a reminder to clear the inbox
  at the start of the Friday session.

### Processing (only on a parent's click)

In order, stopping at the first route that gives a usable recipe:
1. **Links.** For each link in the item: fetch the page (following redirects; Facebook links usually give nothing
   useful) and look for structured recipe data (schema.org `Recipe` in JSON-LD or microdata). Swissmilk and most
   recipe sites have it. This costs no AI.
2. **AI on page text.** If a page was fetched but has no structured data, send its main text to the AI and ask for a
   recipe in the app's JSON shape.
3. **AI on the mail.** Send the mail text and **all screenshots at full resolution** (no downscaling beyond what the
   AI service requires) in **one** request, asking for one recipe.

The AI answer is **untrusted** and is validated against the recipe shape. The AI also returns a list of **uncertain
spots** ("200 g oder 250 g?"), which the draft shows highlighted. The parent fixes the draft and saves it. A failed or
empty result leaves the item in the inbox with the error shown, so it can be retried or discarded.

### AI

- Same service and client as the budget app: **Infomaniak AI**, OpenAI-compatible `/chat/completions`, a vision model
  (budget app default `google/gemma-4-31B-it`), behind a small `AiClient` interface with a fake for tests
  (`backend/app/receipt_ai.py` is the template). Token, product ID and model come from `.env`, and the token never
  appears in a response or log line. No token means the AI features are off and the buttons say so.
- **Rate limit** per user per hour (`AI_CALLS_PER_HOUR`, default 30), as in the budget app's `take_read`.
- **Usage log:** every AI call is recorded (who, when, what for: import or translation, recipe or inbox item, and the
  tokens reported by the service if any). Parents see a small summary in the settings (calls this month, per person).
  The app does not compute costs in francs; Infomaniak's own limits are the cost control.

## Week planner

### Week and slots

- A week has 7 days, **starting on the weekday parents configure** (default: Saturday, *builder's call*, matching the
  Friday planning and weekend shopping). Entries belong to a **date**, not to a week, so changing the first day only
  regroups the days on screen; closed-week state is likewise stored per date range (*builder's call*).
- Each day has four slots, in this order: **Zmorge, Znüni & Zvieri, Zmittag, Znacht**. (English: Breakfast, Snacks,
  Lunch, Dinner.)
- A slot holds **zero or more entries**. An entry is either a **recipe** or a **note** with no recipe ("Pizza-Abend",
  "Resten", "auswärts", "Schule / Büro").
- Each recipe entry has a **number of people**, defaulting to the **family size** that parents set in the settings.

### Friday planning screen (designed for 10–15", landscape)

Layout "A" from the mockups:
- **Header:** the week ("Sa 31.10. – Fr 6.11."), arrows to move between weeks, a neutral counter ("13 von 28
  geplant"; a slot counts as planned when it holds any entry, notes included), and the inbox badge.
- **Week grid:** days as columns, slots as rows, entries as cards in the cells.
- **Suggestion panel** on the right, with tabs:
  - **★ Favoriten:** recipes anyone marked as favourite, best average rating first.
  - **Lange her:** recipes eaten before, the longest ago first. Recipes with a poor average rating (*builder's call:*
    below 3 stars) are left out.
  - **Neu:** recipes saved but never eaten (where Facebook finds end up).
  - **Nochmals planen?:** recipes that were planned but marked as not eaten when a week was closed, and haven't been
    planned again since.
  - A search box (title, tags, ingredients) and tag filters.
  - Each card shows the photo, title, average rating, and "zuletzt vor 5 Wochen" / "noch nie".
- **Placing a recipe:** drag a card onto a cell, **or** tap a card, then tap a cell. Tap-tap must work, because
  dragging on an iPad is fiddly. Tapping an entry opens a small menu: open the recipe, change the number of people,
  move, remove.
- **Adding a note:** tap an empty part of a cell → "Notiz".

### Phones

- The same data as a day-by-day view (layout "B" from the mockups): day tabs, the four slots listed, tap an empty slot
  → suggestions slide up. Planning there is for quick additions during the week, not for the Friday session.

## Closing the week ("Woche abschliessen")

- The **first step of the Friday session**. The planning screen offers it when the week before the one being planned
  hasn't been closed.
- It lists every planned recipe entry of that week, **ticked as eaten** by default. People untick what didn't happen,
  or replace it with what was eaten instead (a recipe or a note, e.g. "Pizza bestellt").
- Next to each eaten recipe there is a **quick star rating** for the person closing. Ratings can be given any time
  during the week from the recipe or the plan; closing is just the last reminder.
- Closing marks the week as closed. Unticked entries are kept as "nicht gegessen" (they feed **Nochmals planen?**) and
  don't count in the history.
- **A week that is never closed counts as eaten as planned.** Past weeks, closed or not, can still be edited.
  "Zuletzt gegessen" and the history always follow the current state of the plan.

## History

- "Last eaten" and "times eaten" per recipe are derived from **past plan entries that weren't marked as not eaten**.
  There is no separate log.
- A history view: scroll back through past weeks (read-only by default, edit on demand), and per recipe a list of the
  dates it was eaten.

## Later (not in the first version)

The first version only has to make these possible:
- **Shopping list:** from the chosen week's recipe entries, each scaled to its number of people (the same scaling
  functions), ingredients combined by name and unit, ticking items off.
- **Bring! upload** of that list.
- Combining ingredients well needs consistent ingredient names and units. *Builder's call:* keep a small, fixed list of
  units (g, kg, ml, dl, l, TL, EL, Prise, Stück, Bund, Dose, Becher, Pck. …) that the importer and the AI map to, and
  store ingredient names as given (normalising names is a later problem).

## Look and feel

- The family-budget-dashboard's **"Aurora" theme**: dark slate background with soft indigo/magenta radial glows,
  frosted **glass cards** (`.glass-card`), cyan/magenta/indigo accents, green for success and red for danger, the Inter
  font. Copy its `index.css` tokens and shared components (e.g. `Section`, `PinInput`, the login page) rather than
  restyling.
- Mockups from the brainstorming session: `.superpowers/brainstorm/*/content/friday-planning.html`.

## Stack and deployment

As family-budget-dashboard and family-job-tracking:
- **Backend:** Python, FastAPI, SQLAlchemy 2, SQLite (`data/meals.db`), Alembic migrations, bcrypt and PyJWT, Pillow
  for images. Files (mails, screenshots, recipe photos) under `data/`.
- **Frontend:** React 19, Vite, TypeScript, Tailwind 4, i18next, react-router, axios, date-fns. Drag and drop must
  work with touch. The library is the builder's call.
- **Docker:** two images on GHCR (`ghcr.io/frankandreas/meal-planer/backend` and `/frontend`, nginx serving the app
  and proxying `/api`), `docker-compose.yml` copied to the NAS as `compose.yaml`, running as an unprivileged DSM user
  (`PUID`/`PGID`), healthcheck, `PORT` default **8085** (budget 8081, job tracking 8082). The nightly update script and
  deploy scripts are copied from the budget app.
- **HTTPS at home** through the existing `*.local.<domain>` wildcard certificate and the DSM reverse proxy, e.g.
  `essen.local.<domain>`. The Cloudflare Tunnel and Access expose only `/api/inbound` for the mail worker, as in the
  sibling apps.
- `README_DOCKER.md` with installation, first login, HTTPS, the mail setup (worker secrets, Email Routing for
  `rezepte@<domain>`), and the AI settings.

### Configuration (`.env`)

`PUID`, `PGID`, `PORT`, `SECRET_KEY`, `INITIAL_ADMIN_PIN`, `DEFAULT_LANGUAGE`, `INFOMANIAK_AI_TOKEN`,
`INFOMANIAK_AI_PRODUCT_ID`, `AI_MODEL`, `AI_CALLS_PER_HOUR`, `INBOUND_SECRET`. An empty value turns that feature off.

## Testing

As in the sibling apps: pytest for the backend, with a fake AI client and test mails (import routes, the inbox's "no
processing before release" rule, roles, rate limit, scaling and rounding, week closing, history). Vitest for the mail
worker. Playwright end-to-end tests for login, planning by tap-tap, and closing a week.

## Left to the builder

Marked *builder's call* above, plus: the API shape, the database schema, the drag-and-drop library, the exact rounding
rules, the page structure outside the planning screen (recipe list, recipe view, inbox, history, settings), and how
the recipe photo is cropped from a screenshot.
