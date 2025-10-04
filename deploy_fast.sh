#!/usr/bin/env bash
# Quick, incremental deploy to the Pi using rsync over SSH.
# Usage: ./deploy_fast.sh [host_alias]
# Example: ./deploy_fast.sh weatherpi

set -euo pipefail
if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
	cat <<'USAGE'
Usage: ./deploy_fast.sh [host_alias]
Quick incremental deploy using rsync. Defaults to 'weatherpi'.
Example: ./deploy_fast.sh weatherpi
USAGE
	exit 0
fi

HOST=${1:-weatherpi}
SSH_ID=${SSH_ID:-$HOME/.ssh/id_ed25519}
CONTROL_PATH=${SSH_CONTROL_PATH:-$HOME/.ssh/controlmasters/%r@%h:%p}

RSYNC_OPTS=(--archive --delete --compress --omit-dir-times --chmod=Du=rwx,Dg=rx,Do=rx,Fu=rw,Fg=r --exclude .git --exclude __pycache__)

echo "Using host: $HOST"

# Ensure controlmaster socket (ssh config should already set this up)
mkdir -p "$(dirname "$CONTROL_PATH")" || true

# Sync project to /opt/weatherpi for Python/service files
echo "Syncing to /opt/weatherpi..."
rsync -e "ssh -i $SSH_ID -o ControlPath=$CONTROL_PATH" "${RSYNC_OPTS[@]}" ./ $HOST:/tmp/weatherpi_sync/
ssh -o ControlPath="$CONTROL_PATH" -i "$SSH_ID" $HOST "sudo rsync -a --delete /tmp/weatherpi_sync/ /opt/weatherpi/ && sudo chown -R $(whoami):$(whoami) /opt/weatherpi && rm -rf /tmp/weatherpi_sync"

# Sync web static files to web root
echo "Syncing web files to /var/www/html..."
rsync -e "ssh -i $SSH_ID -o ControlPath=$CONTROL_PATH" "${RSYNC_OPTS[@]}" ./weather.html ./calendar.html ./icons/ $HOST:/tmp/weatherpi_web_sync/
ssh -o ControlPath="$CONTROL_PATH" -i "$SSH_ID" $HOST "sudo rsync -a --delete /tmp/weatherpi_web_sync/ /var/www/html/ && sudo chown -R www-data:www-data /var/www/html && rm -rf /tmp/weatherpi_web_sync"

# Optionally reload services (uncomment if desired)
# echo "Reloading systemd and restarting services..."
# ssh -o ControlPath="$CONTROL_PATH" -i "$SSH_ID" $HOST "sudo systemctl daemon-reload && sudo systemctl restart calendar-fetcher.timer chromium-kiosk.service nginx"

echo "Deploy complete."
