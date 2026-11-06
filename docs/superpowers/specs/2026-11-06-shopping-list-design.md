# Shopping List and Bring! — Design

Status: talked through with Andreas on 2026-11-06. What Andreas decided is stated plainly; everything else is marked
*my call* (decided while writing this, open to correction) or *builder's call* (left to whoever builds it). Builds on
the main design (`2026-10-29-meal-planner-design.md`, section "Later"), which planned the shopping list and the
Bring! upload but left them out of the first version.

## Why

Planning the week ends in the planner, and shopping starts in Bring!. Today someone reads every planned recipe,
works out the amounts for the number of people and types them into Bring! by hand. The planner already knows the
recipes, the people per meal and how to scale; it should do the adding up, and Bring! should get the result with one
tap.

The two parents share this job: one often starts the list, the other finishes it, and either can look it over before
it goes out.

## Goals

- A parent picks **which of the week's planned meals** to shop for. Not all of them: leftovers, a night out or a meal
  already bought for are left out.
- The planner **combines the ingredients** of those meals, each scaled to that meal's number of people.
- A parent **drops what they don't need** (salt, pepper, …) and can **add things** that aren't in any recipe.
- **One button sends the list to Bring!**, logged in as a family member's own Bring! account.
- The list is **shared between the parents** until it's sent: either can open it, change it and send it.
- Once it's in Bring!, the list in the planner is **gone**.

## Non-goals

- Ticking items off while shopping. That happens in Bring!.
- More than one open shopping list, or a history of sent lists.
- Merging with what is already on the Bring! list (see [Bring!](#bring)).
- Matching ingredient names that are written differently ("Ei" and "Eier", "Rüebli" and "Karotten"). The main design
  left name normalising for later; that stays so.
- Telling the other parent that the list is ready. Andreas chose "just shared": you tell each other in person.
- Children using the shopping list.

## Anti-goals

- The list going out **wrong without anyone noticing**: an amount that's silently missing, a meal that's silently
  added, a failed upload that looks like it worked.
- Anything in the planner reachable from the internet without a login so that Bring! can read it.

## Who

Parents only. Children can plan meals but don't see the shopping list or the Bring! settings (*my call*, in line with
the other parent-only parts: the inbox, the AI sorting, the settings).

## The list

There is **at most one open shopping list**. It belongs to **one week** (the planner's week, starting on the day set
in Einstellungen → Erster Tag der Woche). It is shared: both parents see and change the same list. It shows **who
started it** and **who changed it last, and when** (Andreas chose this over a "please check" signal).

Starting a list for another week while one is open: the planner asks whether to throw the open one away (*my call*).

### Step 1: which meals

The week's plan entries are listed by day and slot, each with its recipe and number of people.

- When the list is **started**, every entry with a recipe is ticked.
- Entries with only a note ("Resten", "Auswärts") are shown but can't be ticked; they have no ingredients.
- A meal **planned for that week after the list was started** shows up **unticked**: the list only changes when a
  parent decides (Andreas).
- A ticked meal that is **removed from the plan** drops out of the list (*my call*). A meal moved to another day of
  the same week stays ticked; moved out of the week, it drops out.
- The same recipe planned twice counts twice.
- The list's week is stored by its **start date**: changing Erster Tag der Woche later doesn't move it (*my call*).
- A meal moved out of the week and back in comes back **unticked**, like any new meal (*my call*).
- A recipe deleted after it was planned still counts, since the plan still shows it (*my call*).

### Step 2: what to buy

The ingredients of the ticked meals, combined, each line showing **which meals it comes from**.

- **Live, not a snapshot** (*my call*). The list stores the parents' decisions (which meals, what's dropped, what's
  added), not the amounts. Amounts are worked out from the plan whenever the list is opened, so changing Lasagne
  from 6 to 8 people changes the Hackfleisch.
- **Scaling** uses the planner's existing scaling (`backend/app/scaling.py`) with each entry's people (or the family
  size if the entry has none), the same numbers the recipe view shows.
- **Combining** (*my call*): lines with the **same name** (case and accents ignored, as elsewhere in the planner)
  are added up when their units can be:
  - same unit: added (2 Eier + 3 Eier = 5 Eier);
  - g and kg add up, and so do ml, dl and l; the sum is shown in a sensible unit (700 g, 1.2 kg, 7 dl, 1.5 l;
    *builder's call* where the thresholds lie, rounded with the existing rounding);
  - units that can't be added stay on **one line**, side by side: "1 Bund + 50 g Petersilie";
  - an ingredient with **no amount** ("Pfeffer") appears once, without an amount; next to an amount it doesn't add
    anything ("200 g + etwas" is not shown, just "200 g").
- **Dropping** a line unticks it; it stays visible, crossed out, so it can be ticked again. A dropped line stays
  dropped when amounts change.
- **What's always at home starts dropped** (*my call*, replacing my earlier guess of "remember what you dropped
  twice"). The planner already has this list: Einstellungen → staples (default Salz, Pfeffer, Öl, Wasser, Zucker,
  Mehl, Bouillon), and the "Was habe ich?" feature already decides with it whether an ingredient is covered
  (`pantry.covered`). Lines it covers start dropped, marked "meist zu Hause"; one tap ticks them back on, and a line
  ticked back on stays ticked even if the staples change later.
- **Adding** a free item: a name and an optional amount as text ("WC-Papier", "2 Pack"). Added items can be removed
  again.
- Ingredient groups ("Für die Sauce") and notes ("fein gehackt") don't appear; optional ingredients are listed like
  the others (*my call*; a parent drops them if not wanted).

Two parents changing the list at the same time must not undo each other's changes: each tick, drop or added item is
its own change, not a save of the whole list (*builder's call* how).

## Bring!

Bring! has no official way for an app to write to someone's list. Andreas chose to **log in with a family member's
own Bring! account** through the API the Bring! apps use, as Home Assistant does. The alternative, Bring!'s official
"import a recipe" link, would need a page Bring!'s servers can read without a login, which the anti-goals rule out.

**Known risk:** the API isn't official. If Bring! changes it, sending stops working until the planner is fixed. The
list in the planner must survive that: nothing is lost, and the parents can still read the list off the screen.

### Settings

Einstellungen → **Bring!** (parents only):

- Email and password of the Bring! account. The planner checks them by logging in when they're saved, and says
  clearly if that fails.
- After a successful login, the parent **picks which Bring! list** the items go to (from that account's lists).
- The password is **stored on the NAS** (in the planner's database; *builder's call* whether encrypted with the
  planner's secret key) so the planner can log in again when Bring!
  asks it to. It is **never sent back** to the browser after saving; the settings show only the email and the
  chosen list (*my call*). *Builder's call* whether to keep Bring!'s login tokens and use the password only when
  they expire.
- "Abmelden" removes the email, password, tokens and chosen list.

Without a Bring! login set up, the shopping list still works, and the send button says where to set it up (*my
call*).

### Sending

"In Bring! schicken (n)", n being the ticked lines plus added items.

- Each line becomes one Bring! item: the **name** as the planner shows it, and the **amount as Bring!'s description**
  ("500 g", "1 Bund + 50 g"). Lines without an amount go without a description. The unit labels are the ones the
  planner shows in the family's language.
- If an item of that name is **already on the Bring! list**, Bring! replaces its description; the planner accepts
  that and doesn't try to add to what's there.
- **Success:** the planner says so ("12 Sachen in Bring!") and the list is deleted.
- **Failure** (wrong login, Bring! unreachable, an answer the planner doesn't understand): the list stays exactly as
  it was, with a message saying what went wrong in plain words, and the parent can try again. Sending again after a
  failure halfway through is safe, since Bring! replaces items of the same name rather than doubling them.
- The planner talks to Bring! from the **backend**, never from the browser, so the password never leaves the NAS.
- **What goes out is what the sender saw** (*my call*, from the anti-goal). The list can change while it's on screen:
  the other parent ticks or drops something, or someone (children too) changes the plan. If anything that affects
  the lines has changed since the page was loaded, sending is refused, the page shows the list as it is now with
  the changes visible, and the parent sends again. Nothing goes to Bring! that nobody looked at. The page doesn't
  need to refresh by itself while open (*builder's call* whether it does).
- A **free item with the same name** as a recipe line is merged into that line ("500 g + 2 Pack"), since Bring!
  would otherwise overwrite one amount with the other (*my call*).

## Look

Both steps on one page (or two views of one page on the phone; *builder's call*), reachable from the week in the
plan ("Einkaufsliste") for parents. It works on the iPad and on the phone, like the rest of the planner. German and
English texts, as everywhere.

## Left to the builder

- How the list is stored, and how concurrent changes are kept apart.
- How lines are keyed so that a drop survives amount changes (name and unit kind is the obvious key).
- Where exactly the entry point sits in the plan, and the page layout on each device.
- Which Bring! client to use (a maintained library or a few direct HTTP calls), and token handling.
- The unit thresholds for showing sums (g → kg, dl → l).
