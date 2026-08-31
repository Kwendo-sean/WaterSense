#!/usr/bin/env bash
# WaterSense AI - VPS bootstrap. Run once, as root.
#
#   sudo bash server-bootstrap.sh
#
# Safe on a shared box: skips Docker if already installed, does NOT touch the
# firewall, nginx, the system postgres/redis, or any other app on the server.
# It does NOT clone the repo - you need a deploy key first (see DEPLOYMENT.md).

set -euo pipefail

APP_USER=watersense
APP_DIR=/opt/watersense
BACKUP_DIR=/var/backups/watersense

if [[ $EUID -ne 0 ]]; then
  echo "run as root: sudo bash $0" >&2
  exit 1
fi

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

log "Base packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl gnupg git cron >/dev/null

if command -v docker >/dev/null 2>&1; then
  log "Docker already installed ($(docker --version)) - skipping"
else
  log "Installing Docker Engine + compose plugin"
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin >/dev/null
  systemctl enable --now docker
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose v2 plugin missing - install docker-compose-plugin" >&2
  exit 1
fi

log "App user: $APP_USER"
if id -u "$APP_USER" >/dev/null 2>&1; then
  echo "exists - skipping"
else
  adduser --system --group --shell /bin/bash --home "/home/$APP_USER" "$APP_USER"
  mkdir -p "/home/$APP_USER/.ssh"
  chmod 700 "/home/$APP_USER/.ssh"
  chown -R "$APP_USER:$APP_USER" "/home/$APP_USER"
fi
usermod -aG docker "$APP_USER"

log "Directories"
mkdir -p "$APP_DIR" "$BACKUP_DIR"
chown "$APP_USER:$APP_USER" "$APP_DIR" "$BACKUP_DIR"
chmod 750 "$BACKUP_DIR"

log "Nightly DB backup cron (03:40)"
cat > /etc/cron.d/watersense-backup <<EOF
# WaterSense AI nightly postgres dump, 14-day rotation
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
40 3 * * * $APP_USER cd $APP_DIR && bash deploy/backup-db.sh >> /var/log/watersense-backup.log 2>&1
EOF
chmod 644 /etc/cron.d/watersense-backup
touch /var/log/watersense-backup.log
chown "$APP_USER:$APP_USER" /var/log/watersense-backup.log

cat > /etc/logrotate.d/watersense <<'EOF'
/var/log/watersense-backup.log {
    weekly
    rotate 6
    compress
    missingok
    notifempty
    copytruncate
}
EOF

log "Done"
cat <<EOF

Next:
  1. sudo -iu $APP_USER
  2. git clone https://github.com/Kwendo-sean/WaterSense.git $APP_DIR
  3. cd $APP_DIR && cp deploy/.env.example .env && nano .env && chmod 600 .env
     (POSTGRES_PASSWORD is required: openssl rand -base64 32)
  4. host nginx site + certbot  (see DEPLOYMENT.md steps 5-6)
  5. bash deploy/deploy.sh

Full walkthrough: $APP_DIR/DEPLOYMENT.md
EOF
