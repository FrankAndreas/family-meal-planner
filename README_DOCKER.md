# Deploying the Meal Planner on a Synology NAS (or any Docker system)

The app runs as two containers from images on GitHub Container Registry (GHCR):

- **backend** (`ghcr.io/frankandreas/family-meal-planner/backend`): the API, with the SQLite database and files in `./data`
- **frontend** (`ghcr.io/frankandreas/family-meal-planner/frontend`): nginx serving the app on port 8080 inside the
  container, forwarding `/api` to the backend

Same setup as family-budget-dashboard and family-job-tracking, so all of them run side by side on one NAS
(budget 8081, job tracking 8082, meal planner **8085**).

## Prerequisites

- A Synology NAS with **Container Manager** (Docker) installed.
- SSH access to the NAS (**Control Panel → Terminal & SNMP → Enable SSH**).
- If the GitHub repository or its packages are **private**, a GitHub token with `read:packages` on the NAS
  (`sudo docker login ghcr.io`).

## Installation

1. **Choose the user the app runs as.** Reuse the DSM user of the other family apps (e.g. `familyapps`) and look up its
   IDs over SSH: `id familyapps` (e.g. `uid=1031(familyapps) gid=100(users)`). Skip this to run as the image's
   built-in user (999:999).
2. **Prepare the folder.** Create `/volume1/docker/meals`, upload `docker-compose.yml` into it **renamed to
   `compose.yaml`**, and create the data folder, owned by the app's user:
   ```bash
   cd /volume1/docker/meals
   sudo mkdir -p data
   sudo chown -R 1031:100 data    # the IDs from step 1, or 999:999
   ```
3. **Create `.env`** (see `.env.example` for all settings; the family hub must already run, see below):
   ```bash
   printf 'PUID=1031\nPGID=100\nPORT=8085\nHUB_URL=http://<NAS_IP>:8086\nHUB_PUBLIC_URL=https://home.local.<domain>\n' | sudo tee .env
   sudo chmod 600 .env
   ```
4. **Start** it:
   ```bash
   sudo docker-compose pull
   sudo docker-compose up -d
   ```
5. **Open** `https://essen.local.<domain>` once [HTTPS at home](#https-at-home-recommended) is set up: the family
   hub's login cookie only reaches addresses under `local.<domain>`.

### Logging in: the family hub

The planner has no PINs of its own: the family logs in at the family hub (FrankAndreas/family-hub), which runs on the
same NAS. In the hub's **Einstellungen → Apps**, give the planner's tile the app key `meals` and tick everyone who
uses it; parents and children, names and languages all come from the hub. Parents can do everything; children can plan,
add and rate recipes. "Abmelden" here logs out in the hub (and so in every family app).

In the planner's **Einstellungen**:

- **Personen am Tisch**: the family size, the default number of people for every planned meal
- **Erster Tag der Woche**: default Saturday, so Friday's planning covers the coming week
- **Im Familien-Hub entfernt**: people the hub no longer gives the planner. They're hidden, with their stars and
  favourites, until a parent deletes their data here.

**Switching an existing installation** to the hub: add `HUB_URL`, `HUB_PUBLIC_URL` and `HUB_APP_KEY` to the backend's
`environment:` in the NAS's `compose.yaml` (as in `docker-compose.yml`; a value only in `.env` doesn't reach the
container), remove `SECRET_KEY` and `INITIAL_ADMIN_PIN`, set the values in `.env`, then update. Before the first login,
make sure every planner person exists in the hub with the same name and role and is ticked: each is linked to that
hub person at the first login, and only then, so their stars and favourites stay theirs.

### Where the data is

`data/` holds everything worth keeping: the database `meals.db`, recipe photos (`data/photos/`) and the recipe mails
with their originals (`data/inbox/`). Back up the whole folder: the update script's database backup does not include
the files.

### HTTPS at home (recommended)

The DNS record and the `*.local.<domain>` wildcard certificate from family-budget-dashboard (its README_DOCKER.md,
"HTTPS at home") cover this app too. Only the reverse proxy entry is new:

1. **Control Panel → Login Portal → Advanced → Reverse Proxy → Create**: source HTTPS, `essen.local.<domain>`,
   port 443, **Enable HSTS**; destination HTTP, `localhost`, port 8085.
2. **Control Panel → Security → Certificate → Settings**: pick the `*.local.<domain>` certificate for the new entry.
3. Open `https://essen.local.<domain>` on the iPad and the phones and save it to the home screen.

### From outside: Cloudflare Tunnel and Access (optional)

Away from home the family logs in with Cloudflare Access (an e-mail code); the planner passes that login on to the
family hub, which knows each person by their **confirmed** e-mail address there. A hub cookie arriving through the
tunnel counts for nothing.

1. **Tunnel route.** **Zero Trust → Networks → Connectors → Cloudflare Tunnels** → the NAS's tunnel → **Published
   application routes → Add**: subdomain e.g. `essen`, your domain, path empty, service `HTTP`, URL `<NAS_IP>:8085`.
2. **Access application.** **Access controls → Applications → Create new application → Public DNS**: subdomain
   `essen`, your domain, path empty, with a policy that allows the family's e-mail addresses. Note its **Application
   Audience (AUD) Tag**.
3. **The hub:** add that AUD tag to `CF_AUDIENCE` in the hub's `.env` (comma-separated, next to the hub's own) and
   restart the hub; give the planner's tile the outside address `https://essen.<domain>`, so its tile shows outside.
4. Everyone who uses it from outside needs a **confirmed** e-mail address in the hub (the one Cloudflare's code is sent
   to). Unknown addresses see "No access".

"Log out" from outside ends the Cloudflare login (`/cdn-cgi/access/logout`).

### Recipe mails (Cloudflare Email Worker, optional)

Family members share a recipe (a Facebook post, a screenshot, a link) **by mail** to e.g. `rezepte@<domain>`. It waits
**unopened** in the **Posteingang** until a parent taps **Verarbeiten**; only then is the mail read, are its links
followed and may the AI see it. Mails are taken only

- if Cloudflare found them authentic (`dmarc=pass`; the worker checks this), and
- from an address registered for a family member in **Einstellungen → Mail-Adressen** (the app checks this).

Everything else is rejected, and the sender gets a bounce. The worker posts to one path, behind its own Access
application with a service token (separate from the people's access from outside, see below). The setup is the same as family-budget-dashboard's "Receipt
mails", with these names (Cloudflare renames dashboard menus from time to time):

1. **Secret for the app.** Add it to `.env`, then restart and check the log:
   ```bash
   echo "INBOUND_SECRET=$(openssl rand -hex 32)" | sudo tee -a .env
   sudo docker-compose up -d
   sudo docker logs meals-backend 2>&1 | grep "Recipe mails"    # must say: configured
   ```
2. **Tunnel route for the worker only.** **Zero Trust → Networks → Connectors → Cloudflare Tunnels**, the NAS's tunnel
   → **Published application routes → Add**: subdomain e.g. `rezepte-inbound`, your domain, **path `^/api/inbound$`**,
   service `HTTP`, URL `<NAS_IP>:8085`.
3. **Service token** `meals-inbound` (**Access controls → Service credentials → Service Tokens**, non-expiring); note
   the Client ID and Secret.
4. **Policy** `meals-inbound-token`: action **Service Auth**, include **Service Token** = `meals-inbound`.
5. **Access application** (Public DNS): subdomain `rezepte-inbound`, path `api/inbound`, policy
   `meals-inbound-token`. Check:
   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" -X POST https://rezepte-inbound.<domain>/api/inbound   # 302 or 401
   ```
6. **Deploy the worker** from a checkout of this repository:
   ```bash
   cd cloudflare/email-worker
   npm ci
   npx wrangler login
   npx wrangler deploy
   # APP_URL=https://rezepte-inbound.<domain>, INBOUND_SECRET from step 1, the token from step 3
   for name in APP_URL INBOUND_SECRET CF_ACCESS_CLIENT_ID CF_ACCESS_CLIENT_SECRET; do
     printf %s "${!name}" | npx wrangler secret put "$name"
   done
   ```
   Optional: `FALLBACK_ADDRESS` (a verified Email Routing destination outside the domain) gets a mail the app can't
   take (NAS down) instead of a bounce.
7. **Route the address** `rezepte` to the worker `meals-inbound` (**Email → Email Routing → Routing rules**).
8. **Register the addresses** everyone shares from in **Einstellungen → Mail-Adressen**.
9. **Test:** share a recipe from a registered mailbox to `rezepte@<domain>`; it shows in the Posteingang within
   seconds. A mail from an unregistered address must bounce.

Mails wait in `data/inbox/`; part of the `data/` backup.

### AI (Infomaniak, optional)

The AI reads recipes from screenshots and mail text, and translates recipes into German. **Only parents** start it
(Verarbeiten, Übersetzen); recipe pages with built-in recipe data (Swissmilk, Fooby, Betty Bossi, most blogs) are
read **without** it.

What the AI service sees (Infomaniak processes it in Switzerland): the text of the mail or page and its pictures for a
recipe import; the recipe's text for a translation. Nothing else from the app.

1. In the Infomaniak Manager, create an API token with **only the `ai-tools` scope** and a lifetime, and note the AI
   product's ID. **Set a spending limit** on the AI product: it is the outer cost control.
2. Put both in `.env` (never in the repository) and restart:
   `INFOMANIAK_AI_TOKEN=…`, `INFOMANIAK_AI_PRODUCT_ID=…`, then `sudo docker-compose up -d`; the log says `AI: configured`.
3. Optional: `AI_MODEL` (default `google/gemma-4-31B-it`) and `AI_CALLS_PER_HOUR` (default 30 per person; `0` turns
   the AI off while keeping the token).

Parents see each person's AI calls this month in **Einstellungen → KI-Nutzung**. The NAS needs outgoing HTTPS to
`api.infomaniak.com` and, for links, to the recipe sites.

## Automatic updates

`scripts/nas-update.sh` checks for new images and installs them, the same way as in the other family
apps:
- it pulls the images
- if there is a new one, it backs up the database to `db-backups/`, keeps the old images as
  `:previous` and restarts the app
- it waits until the backend is healthy, logging to `logs/update.log`

1. Copy `scripts/nas-update.sh` into `/volume1/docker/meals` and make it executable (or let
   `scripts/deploy-nas.sh` upload it):
   ```bash
   sudo chmod +x /volume1/docker/meals/nas-update.sh
   sudo /volume1/docker/meals/nas-update.sh     # should end with "Up to date" or "Update complete"
   ```
2. In **Control Panel → Task Scheduler → Create → Scheduled Task → User-defined script**:
   - user **root**
   - daily, a few minutes apart from the other apps' updates (e.g. 04:00)
   - command `bash /volume1/docker/meals/nas-update.sh`

If the images are private, log in to the registry once as root:
`sudo docker login ghcr.io -u <github-user>` with a token that has `read:packages`.

To deploy right away from your computer:
```bash
cp .deploy.env.example .deploy.env   # once; then set NAS_HOST and NAS_DIR
scripts/deploy-nas.sh
```

### Rolling back an update

If a new version misbehaves, go back to the previous one. First **disable the scheduled task**, otherwise the next
night installs the same version again. Then, in the app folder:

```bash
cd /volume1/docker/meals
# 1. Point latest at the previous images (frontend only if it was updated; see logs/update.log)
sudo docker tag ghcr.io/frankandreas/family-meal-planner/backend:previous ghcr.io/frankandreas/family-meal-planner/backend:latest
sudo docker tag ghcr.io/frankandreas/family-meal-planner/frontend:previous ghcr.io/frankandreas/family-meal-planner/frontend:latest

# 2. Restore the database from the backup taken right before the update
#    (the new version may have changed it). Changes made since the update are lost.
sudo docker stop meals-backend
sudo sh -c 'gunzip -c db-backups/meals-YYYYMMDD-HHMMSS.sqlite.gz > data/meals.db'

# 3. Start the previous version
sudo docker-compose up -d backend frontend
```

Re-enable the task once a fixed version is published.
