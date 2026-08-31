# WaterSense AI — Docker deployment

`https://watersense.selenos.world`

Single VPS, **shared with your other apps** (Selene included). Three Docker containers behind your existing host nginx. Postgres is containerised so it doesn't touch the system Postgres your other apps use, and nothing in this stack collides with the `selene` stack.

## What runs on the box

### Outside Docker (your existing setup, untouched)
- **nginx** on :80 / :443 — already serving `selenos.world` and friends. We add ONE site config (`/etc/nginx/sites-available/watersense`) that proxies `watersense.selenos.world` to the web container.
- **certbot** — issues + auto-renews the Let's Encrypt cert for `watersense.selenos.world` against the host nginx.
- Everything else on the box (Selene's stack, other apps, system Postgres) — we don't touch it.

### Inside Docker (`name: watersense`)
| Container | Image | Purpose |
|-----------|-------|---------|
| `watersense-web` | built from `frontend/Dockerfile` | nginx serving the built React SPA, and reverse-proxying `/api`, `/ws`, `/docs` to the API. Bound to `127.0.0.1:${WEB_PORT}` (default 8770) |
| `watersense-api` | built from `backend/Dockerfile` | FastAPI via uvicorn — telemetry ingest, risk engine, Isolation Forest, forecasts, WebSocket, simulator |
| `watersense-db` | `postgres:16-alpine` | WaterSense's database, isolated |

`watersense-db` publishes NO host port — it's only reachable from inside the `watersense` docker network. `watersense-api` publishes no host port either; the browser reaches it through `watersense-web` on the same origin, so there are no CORS preflights and no mixed-content on the WebSocket.

Persistent data lives in the named volume `watersense_postgres_data` and survives `docker compose down`. `down -v` wipes it — don't do that on prod.

### Why the API runs exactly one process
The telemetry simulator and the WebSocket `ConnectionManager` both live in the Python process. Running `uvicorn --workers 2` would start **two simulators** writing duplicate readings and would split live subscribers across workers, so half the dashboards would miss events. `docker-compose.prod.yml` pins `--workers 1`. Scale by adding an external broker + queue, not by adding workers.

## First-time deploy

1. **DNS**: add an A record for `watersense.selenos.world` pointing at the server IP. Wait for propagation:
   ```bash
   dig watersense.selenos.world +short
   ```

2. **SSH in as root** and bootstrap the box. Safe on a shared server — it skips Docker if Docker is already installed, doesn't touch your firewall, doesn't touch nginx/postgres/redis or the Selene stack:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/Kwendo-sean/WaterSense/main/deploy/server-bootstrap.sh -o bootstrap.sh
   sudo bash bootstrap.sh
   ```
   It installs Docker (if missing), creates a `watersense` user, makes `/opt/watersense` and `/var/backups/watersense`, and installs a nightly backup cron. **It does NOT clone the repo** — that's step 3.

3. **Clone the repo** as the `watersense` user. The repo is public, so no credentials are needed. Run this **as root** — `sudo -u` rather than `sudo -iu`, so you stay in your root shell:
   ```bash
   sudo -u watersense git clone https://github.com/Kwendo-sean/WaterSense.git /opt/watersense
   ```
   > `sudo -iu watersense` opens an *interactive login shell*; any further commands you paste get swallowed by it. And `watersense` is a `--system` account with no password and no sudo rights, so `sudo` fails from inside it. Do the root-level steps (5, 6) as root, and use `sudo -u watersense <cmd>` for the app-level ones.
   <details>
   <summary>If you later make the repo private</summary>

   Add a read-only deploy key so `deploy.sh` can still `git pull` unattended:
   ```bash
   sudo -iu watersense
   ssh-keygen -t ed25519 -C "watersense-deploy@$(hostname)" -f ~/.ssh/id_ed25519 -N ''
   cat ~/.ssh/id_ed25519.pub
   ```
   Paste the public key into GitHub → repo → **Settings → Deploy keys → Add deploy key**, "Allow write access" OFF. Then switch the remote:
   ```bash
   cd /opt/watersense
   git remote set-url origin git@github.com:Kwendo-sean/WaterSense.git
   ```
   </details>

4. **Fill in env.** As root, generate the password and write it in without an editor:
   ```bash
   sudo -u watersense cp /opt/watersense/deploy/.env.example /opt/watersense/.env
   PW=$(openssl rand -hex 32)
   sudo -u watersense sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PW}|" /opt/watersense/.env
   sudo -u watersense chmod 600 /opt/watersense/.env
   unset PW
   ```
   `DOMAIN=watersense.selenos.world` and `WEB_PORT=8770` are already the defaults (Selene uses 8765, so they don't collide). `POSTGRES_PASSWORD` is the only required value.

   **Use hex, not base64.** The password is interpolated into `postgresql+psycopg://user:PASSWORD@db:5432/db`; base64's `/`, `+` and `=` corrupt that URL. `deploy.sh` rejects a password outside `[A-Za-z0-9._~-]` rather than letting you find out via a confusing connection error.

5. **Hook into the host nginx**:
   ```bash
   sudo cp /opt/watersense/deploy/nginx-watersense.conf /etc/nginx/sites-available/watersense
   sudo ln -sf /etc/nginx/sites-available/watersense /etc/nginx/sites-enabled/watersense
   sudo nginx -t
   sudo systemctl reload nginx
   ```

6. **Issue the TLS cert**:
   ```bash
   sudo certbot --nginx -d watersense.selenos.world
   ```
   Certbot edits `/etc/nginx/sites-available/watersense` in place to add the cert paths and reloads nginx. Renewals happen automatically. (If you also want `www.watersense.selenos.world`, add the DNS record first, then `-d www.watersense.selenos.world` as well.)

7. **Bring the Docker stack up**:
   ```bash
   bash deploy/deploy.sh
   ```
   Builds both images, brings everything up, waits for healthchecks, smoke-tests `127.0.0.1:8770`. First build takes ~4–6 min (scikit-learn/numpy wheels + `npm ci`); after that it's seconds.

8. **Verify**:
   ```bash
   curl -s https://watersense.selenos.world/api/v1/health
   # {"status":"healthy","service":"watersense-api","simulator":true}
   ```
   Then open:
   - `https://watersense.selenos.world/` — landing page
   - `https://watersense.selenos.world/dashboard` — operations dashboard, check the **LIVE LINK** indicator is green (that's the WebSocket)
   - `https://watersense.selenos.world/demo-control` — presenter controls
   - `https://watersense.selenos.world/docs` — API docs

On first start the API creates the schema and seeds 12 demo stations with ~48h of history per station. That runs once — the seed is skipped on subsequent boots because the data is already in the volume.

## Subsequent deploys

```bash
sudo -iu watersense
cd /opt/watersense
bash deploy/deploy.sh
```

`deploy.sh` is idempotent: `git pull`, rebuild only what changed, `compose up -d`, wait for health, prune dangling images. Use `bash deploy/deploy.sh --no-pull` to deploy the working tree without pulling.

Expect a **~2–5 second gap in the WebSocket stream** while `watersense-api` restarts; the dashboard reconnects on its own. There is no zero-downtime path here because the app is single-process by design.

## Day-to-day ops

`COMPOSE_FILE=docker-compose.prod.yml` in `.env` means plain `docker compose` picks up the prod file automatically:

```bash
cd /opt/watersense
docker compose ps                                       # what's running
docker compose logs -f api                              # tail FastAPI
docker compose logs -f web                              # tail the SPA nginx
docker compose restart api                              # restart just the API
docker compose exec db psql -U watersense watersense    # psql into the DB
docker compose down                                     # stop everything (keeps data)
docker compose down -v                                  # NUKE the volume (DB!)
sudo tail -f /var/log/nginx/watersense.access.log       # host nginx access log
sudo journalctl -u nginx -n 100                         # host nginx
```

Handy app-level commands:

```bash
# stop / start the demo simulator without a redeploy
curl -X POST https://watersense.selenos.world/api/v1/simulator/stop
curl -X POST https://watersense.selenos.world/api/v1/simulator/start

# fire a scenario on a station
curl -X POST https://watersense.selenos.world/api/v1/simulator/scenario \
  -H 'Content-Type: application/json' \
  -d '{"station_id":4,"scenario":"CONTAMINATION_EVENT","intensity":1}'

# watch live events from the shell
docker compose exec api python -c "print('use wscat/websocat against wss://watersense.selenos.world/ws/live')"
```

## Backups

Cron (installed by `server-bootstrap.sh`) runs `deploy/backup-db.sh` nightly at 03:40 — 03:40 rather than Selene's 03:30 so the two dumps don't contend. Backups land in `/var/backups/watersense/watersense-YYYY-MM-DD_HHMMSS.sql.gz`, 14-day rotation. Log: `/var/log/watersense-backup.log`.

Run one by hand:
```bash
cd /opt/watersense && bash deploy/backup-db.sh
```

Restore:
```bash
cd /opt/watersense
gunzip -c /var/backups/watersense/watersense-2026-08-31_034000.sql.gz \
  | docker compose exec -T db psql -U watersense watersense
docker compose restart api
```

Off-site copy (recommended): rsync `/var/backups/watersense/` to S3/B2/Hetzner Storage Box nightly.

## Updating environment variables

1. Edit `/opt/watersense/.env`.
2. `docker compose up -d` — Compose detects the change and recreates affected containers.

Two exceptions that need a **rebuild**, not a recreate, because they're baked into the JS bundle at build time:
- `DOMAIN` (drives `VITE_API_URL` / `VITE_WS_URL`)

For those, run `bash deploy/deploy.sh` instead. And don't use `docker compose restart` for env changes at all — it doesn't re-read env files.

## Going from demo to real devices

The stack ships with `SIMULATOR_ENABLED=true`, which means synthetic telemetry flows continuously into the same pipeline real hardware uses. Once you have field nodes:

1. Create the station: `POST https://watersense.selenos.world/api/v1/stations`.
2. Point the ESP32 at `POST /api/v1/telemetry`, or run the serial bridge against the live host:
   ```bash
   python scripts/arduino_serial_bridge.py --port COM4 --baud 9600 \
     --api https://watersense.selenos.world/api/v1/telemetry
   ```
3. Set `SIMULATOR_ENABLED=false` in `.env` and `docker compose up -d`, otherwise synthetic readings mix with real ones in the same tables.

## Security notes — read before sharing the URL

The app has **no authentication** (the README lists auth/RBAC as out of hackathon scope). Anyone with the URL can drive the simulator, acknowledge and resolve alerts, and create or delete stations. TLS protects the transport, not the endpoints.

Mitigations, cheapest first:
- Leave it as-is if it's a demo you're actively presenting and will take down after.
- Uncomment the `auth_basic` blocks in `deploy/nginx-watersense.conf` to password-protect `/demo-control` and `/api/v1/simulator/` (instructions are in the file).
- Restrict `POST`/`PATCH`/`DELETE` on `/api/v1/` to known IPs with an nginx `allow`/`deny` block.
- Build real auth before any of this carries decisions people act on.

Also worth knowing: telemetry ingest is unauthenticated and unthrottled, so anyone can inject readings for a known `station_code`.

## Common gotchas

- **502 Bad Gateway**: the host nginx is reaching :8770 but the web container isn't healthy. `docker compose ps`, then `docker compose logs web api`. Verify `WEB_PORT` in `.env` matches `upstream watersense_web` in `/etc/nginx/sites-available/watersense`.
- **Port 8770 already used**: change `WEB_PORT` in `.env` AND `upstream watersense_web` in the nginx site to a free port, then `docker compose up -d` and `sudo systemctl reload nginx`.
- **Dashboard loads but LIVE LINK is dead / data never updates**: the WebSocket isn't upgrading. Check the browser console for the `wss://watersense.selenos.world/ws/live` connection. Both nginx layers need the `Upgrade`/`Connection` headers and `proxy_buffering off` — keep the `location /ws/` blocks intact if you edit either config. Also confirm the bundle was built with the right `DOMAIN`: if `VITE_WS_URL` still says `ws://localhost:8000`, the build used the wrong args — rerun `bash deploy/deploy.sh`.
- **Page loads, all API calls fail**: the bundle was built with a stale `DOMAIN`. `VITE_API_URL` is compile-time. Rebuild: `bash deploy/deploy.sh`.
- **Mixed-content blocked in the browser**: same cause — the bundle is pointing at `http://`/`ws://` instead of `https://`/`wss://`. Rebuild.
- **`POSTGRES_PASSWORD` change**: Compose won't re-init Postgres if the data volume already exists. Either rotate via SQL (`ALTER USER watersense WITH PASSWORD '…';`) then update `.env`, or dump → `down` → `docker volume rm watersense_postgres_data` → restore.
- **API stuck `unhealthy` on first boot**: the seed writes ~48h × 12 stations of history and can take up to a minute on a small box. `start_period` is 45s; if your VPS is slow, raise it in `docker-compose.prod.yml`. Check `docker compose logs api` for the actual error before assuming it's slowness.
- **Duplicate telemetry / events reaching only some browsers**: someone raised `--workers` above 1. Put it back to 1 (see "Why the API runs exactly one process").
- **Map tiles blank**: the dashboard's OpenStreetMap layer needs outbound internet from the *browser*, not the server. The rest of the dashboard degrades gracefully.
- **TLS not issuing**: DNS must resolve to the server before certbot runs. `dig watersense.selenos.world +short`. If `certbot --nginx` errors, read `/var/log/letsencrypt/letsencrypt.log`.
- **Disk filling up**: telemetry accumulates forever — there's no retention policy. With the simulator at 3s × 12 stations that's ~350k rows/day. Either disable the simulator, raise `SIMULATOR_INTERVAL_SECONDS`, or prune old readings periodically.

## What's NOT in this setup

- **Authentication / RBAC** — see the security notes above.
- **Telemetry retention / partitioning** — the tables grow without bound.
- **Off-site DB backups** — local 14-day rotation only.
- **Horizontal scaling** — single-process by design (in-memory simulator + WebSocket registry).
- **Database migrations** — schema comes from `Base.metadata.create_all`. A model change on an existing volume will not alter existing tables; you'll need Alembic or a manual `ALTER`.
- **Container resource limits** — add `mem_limit` per service if the box is tight.
- **Log shipping** — logs go to stdout via the Docker logging driver.
