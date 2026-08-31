#!/usr/bin/env bash
# WaterSense AI - nightly postgres dump with 14-day rotation.
# Installed as a cron job by server-bootstrap.sh; also safe to run by hand.

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

BACKUP_DIR=${BACKUP_DIR:-/var/backups/watersense}
RETENTION_DAYS=${RETENTION_DAYS:-14}

# shellcheck disable=SC1091
[[ -f .env ]] && { set -a; source .env; set +a; }

PGUSER=${POSTGRES_USER:-watersense}
PGDB=${POSTGRES_DB:-watersense}

mkdir -p "$BACKUP_DIR"
stamp=$(date +%Y-%m-%d_%H%M%S)
out="$BACKUP_DIR/watersense-$stamp.sql.gz"

echo "[$(date -Is)] dumping $PGDB -> $out"

docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U "$PGUSER" -d "$PGDB" --clean --if-exists \
  | gzip -9 > "$out.partial"

mv "$out.partial" "$out"
chmod 640 "$out"

echo "[$(date -Is)] ok, $(du -h "$out" | cut -f1)"

deleted=$(find "$BACKUP_DIR" -name 'watersense-*.sql.gz' -mtime +"$RETENTION_DAYS" -print -delete | wc -l)
echo "[$(date -Is)] rotated out $deleted backup(s) older than ${RETENTION_DAYS}d"
