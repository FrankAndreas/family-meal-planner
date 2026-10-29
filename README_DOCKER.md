# Deploying the Meal Planner on a Synology NAS (or any Docker system)

The app runs as two containers from images on GitHub Container Registry (GHCR):

- **backend** (`ghcr.io/frankandreas/meal-planer/backend`): the API, with the SQLite database and files in `./data`
- **frontend** (`ghcr.io/frankandreas/meal-planer/frontend`): nginx serving the app on port 8080 inside the
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
3. **Create `.env`** (see `.env.example` for all settings):
   ```bash
   printf 'PUID=1031\nPGID=100\nPORT=8085\nSECRET_KEY=%s\n' "$(openssl rand -hex 32)" | sudo tee .env
   sudo chmod 600 .env
   ```
   > **Why `SECRET_KEY` matters:** it signs the logins. If it is empty, the backend picks a random one on every start,
   > and everyone is logged out after each update.
4. **Start** it:
   ```bash
   sudo docker-compose pull
   sudo docker-compose up -d
   ```
5. **Open** `http://<NAS_IP>:8085`. For daily use, set up [HTTPS at home](#https-at-home-recommended): on plain HTTP
   the PINs cross the Wi-Fi unencrypted.

### First login

On an empty database the backend creates the parent **Admin** with a random 4-digit PIN, printed once in its log:

```bash
sudo docker logs meals-backend 2>&1 | grep "INITIAL PIN"
```

Log in as `Admin`, change the PIN in **Einstellungen**, rename Admin, and add the other family members there (there is
no sign-up page). Parents can do everything; children can plan and add recipes. There also:

- **Personen am Tisch**: the family size, the default number of people for every planned meal
- **Erster Tag der Woche**: default Saturday, so Friday's planning covers the coming week

To choose the first PIN yourself, set `INITIAL_ADMIN_PIN=1234` in `.env` before the first start. The app is German
unless a person picks English in **Einstellungen**; `DEFAULT_LANGUAGE=en` makes English the default.

If you lose the PIN before anyone uses the app, stop it, delete `data/meals.db` and start again.
**This deletes all data.** Otherwise another parent can reset it.

### Where the data is

`data/` holds everything worth keeping: the database `meals.db` and, in later versions, recipe photos and imported
mails. Back up the whole folder.

### HTTPS at home (recommended)

The DNS record and the `*.local.<domain>` wildcard certificate from family-budget-dashboard (its README_DOCKER.md,
"HTTPS at home") cover this app too. Only the reverse proxy entry is new:

1. **Control Panel → Login Portal → Advanced → Reverse Proxy → Create**: source HTTPS, `essen.local.<domain>`,
   port 443, **Enable HSTS**; destination HTTP, `localhost`, port 8085.
2. **Control Panel → Security → Certificate → Settings**: pick the `*.local.<domain>` certificate for the new entry.
3. Open `https://essen.local.<domain>` on the iPad and the phones and save it to the home screen.

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
