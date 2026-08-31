#!/usr/bin/env bash
# WaterSense AI - build + roll forward. Idempotent, safe to re-run.
#
#   sudo -iu watersense
#   cd /opt/watersense && bash deploy/deploy.sh
#
# Flags:
#   --no-pull    skip git pull (deploy the working tree as-is)

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

PULL=1
[[ "${1:-}" == "--no-pull" ]] && PULL=0

log()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
fail() { printf '\n\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

[[ -f .env ]] || fail ".env missing. cp deploy/.env.example .env && nano .env"

# shellcheck disable=SC1091
set -a; source .env; set +a

[[ -n "${DOMAIN:-}" ]]            || fail "DOMAIN not set in .env"
[[ -n "${POSTGRES_PASSWORD:-}" ]] || fail "POSTGRES_PASSWORD not set in .env (openssl rand -hex 32)"

# POSTGRES_PASSWORD lands inside postgresql+psycopg://user:PASS@db:5432/db, so
# URL-significant characters silently corrupt the connection string.
if [[ "$POSTGRES_PASSWORD" =~ [^A-Za-z0-9._~-] ]]; then
  fail "POSTGRES_PASSWORD contains characters that break the DATABASE_URL (/, +, =, @, :, #, ...).
       Use only [A-Za-z0-9._~-] - e.g. openssl rand -hex 32
       If the DB volume already exists, rotate the password inside postgres too:
         docker compose exec db psql -U ${POSTGRES_USER:-watersense} -c \"ALTER USER ${POSTGRES_USER:-watersense} WITH PASSWORD 'newpass';\""
fi

COMPOSE="docker compose -f docker-compose.prod.yml"

if [[ $PULL -eq 1 ]] && [[ -d .git ]]; then
  log "git pull"
  git pull --ff-only
fi

log "Building images (DOMAIN=$DOMAIN)"
$COMPOSE build

log "Starting stack"
$COMPOSE up -d --remove-orphans

log "Waiting for healthchecks"
deadline=$(( $(date +%s) + 240 ))
while :; do
  api_state=$(docker inspect -f '{{.State.Health.Status}}' watersense-api 2>/dev/null || echo missing)
  web_state=$(docker inspect -f '{{.State.Health.Status}}' watersense-web 2>/dev/null || echo missing)
  if [[ "$api_state" == healthy && "$web_state" == healthy ]]; then
    echo "  api=healthy web=healthy"
    break
  fi
  if [[ $(date +%s) -ge $deadline ]]; then
    echo "  api=$api_state web=$web_state"
    $COMPOSE ps
    $COMPOSE logs --tail=60 api
    fail "containers did not become healthy in 240s"
  fi
  printf '  api=%s web=%s\n' "$api_state" "$web_state"
  sleep 6
done

log "Local smoke test on 127.0.0.1:${WEB_PORT:-8770}"
curl -fsS "http://127.0.0.1:${WEB_PORT:-8770}/api/v1/health" && echo
curl -fsS -o /dev/null -w '  index.html -> HTTP %{http_code}\n' "http://127.0.0.1:${WEB_PORT:-8770}/"

log "Pruning dangling images"
docker image prune -f >/dev/null

log "Deployed"
$COMPOSE ps
echo
echo "  https://${DOMAIN}/            landing"
echo "  https://${DOMAIN}/dashboard   operations dashboard"
echo "  https://${DOMAIN}/demo-control presenter controls"
echo "  https://${DOMAIN}/docs        API docs"
