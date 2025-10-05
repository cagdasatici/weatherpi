#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <pi-user@pi-host> [remote-path=/home/pi/weatherpi]"
  exit 1
fi

REMOTE=$1
REMOTE_PATH=${2:-/home/pi/weatherpi}

echo "Deploying to $REMOTE:$REMOTE_PATH"

rsync -avz --delete --exclude '.git' --exclude 'server/.env' . ${REMOTE}:${REMOTE_PATH}

ssh ${REMOTE} bash -lc "'
  set -e
  cd ${REMOTE_PATH}
  python3 -m venv venv || true
  source venv/bin/activate
  pip install -r requirements.txt
  pip install -r requirements-dev.txt || true
  sudo cp server/weatherpi-proxy@.service /etc/systemd/system/weatherpi-proxy@.service || true
  sudo cp server/weatherpi-proxy.service /etc/systemd/system/weatherpi-proxy.service || true
  sudo cp server/monitor.service /etc/systemd/system/monitor.service || true
  sudo cp server/healthcheck.service /etc/systemd/system/healthcheck.service || true
  sudo cp server/healthcheck.timer /etc/systemd/system/healthcheck.timer || true
  sudo cp server/kiosk-wait.service /etc/systemd/system/kiosk-wait.service || true
  sudo cp server/backup.service /etc/systemd/system/backup.service || true
  sudo cp server/backup.timer /etc/systemd/system/backup.timer || true
  sudo systemctl daemon-reload
  sudo systemctl enable --now weatherpi-proxy@default
  sudo systemctl enable --now monitor.service || true
  sudo systemctl enable --now healthcheck.timer || true
  sudo systemctl enable --now kiosk-wait.service || true
  sudo systemctl enable --now backup.timer || true

  # Patch chromium-kiosk.service to depend on kiosk-wait.service (idempotent)
  if [ -f /etc/systemd/system/chromium-kiosk.service ]; then
    sudo sed -n '1,200p' /etc/systemd/system/chromium-kiosk.service | sudo tee /tmp/chromium-kiosk.service >/dev/null || true
    if ! sudo grep -q "Wants=kiosk-wait.service" /etc/systemd/system/chromium-kiosk.service 2>/dev/null; then
      sudo sed -i '/\[Unit\]/a Wants=kiosk-wait.service\nAfter=kiosk-wait.service' /etc/systemd/system/chromium-kiosk.service || true
      sudo systemctl daemon-reload || true
    fi
  fi
'"

echo "Deploy completed. Check journalctl on the Pi for logs."
#!/usr/bin/env bash
set -euo pipefail

# Minimal deploy helper for this repository.
# Usage: ./deploy_to_pi.sh [-n|--dry-run] [-r user@host] [-d remote_dir] [-s service_name] [-e entrypoint]
# Defaults: user@host=pi@pii, remote_dir=/home/$user/weatherpi, service_name=weatherpi, entrypoint=main.py

DRY_RUN=0
REMOTE="pi@pii"
REMOTE_DIR=""
SERVICE_NAME="weatherpi"
ENTRYPOINT="main.py"

print_usage() {
  cat <<EOF
Usage: $0 [options]
Options:
  -n, --dry-run        Do not perform remote changes; show actions only
  -r, --remote USER@HOST  SSH target (default: pi@pii)
  -d, --remote-dir DIR   Remote install directory (default: /home/<user>/weatherpi)
  -s, --service NAME     systemd service name to create (default: weatherpi)
  -e, --entrypoint FILE  entrypoint script on remote (default: main.py)
  -h, --help             Show this help

Example:
  $0 -r pi@192.168.1.10 -d /home/pi/weatherpi -s weatherpi -e main.py
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--dry-run)
      DRY_RUN=1; shift;;
    -r|--remote)
      REMOTE="$2"; shift 2;;
    -d|--remote-dir)
      REMOTE_DIR="$2"; shift 2;;
    -s|--service)
      SERVICE_NAME="$2"; shift 2;;
    -e|--entrypoint)
      ENTRYPOINT="$2"; shift 2;;
    -h|--help)
      print_usage; exit 0;;
    --)
      shift; break;;
    *)
      echo "Unknown option: $1"; print_usage; exit 1;;
  esac
done

# derive remote_dir from remote user if not provided
REMOTE_USER=${REMOTE%%@*}
if [[ -z "$REMOTE_DIR" ]]; then
  REMOTE_DIR="/home/${REMOTE_USER}/weatherpi"
fi

echo "Deploy configuration:"
echo "  remote:     $REMOTE"
echo "  remote dir: $REMOTE_DIR"
echo "  service:    $SERVICE_NAME"
echo "  entrypoint: $ENTRYPOINT"
echo "  dry-run:    $DRY_RUN"

confirm() {
  if [[ $DRY_RUN -eq 1 ]]; then
    return 0
  fi
  read -r -p "$1 [y/N]: " ans
  case "$ans" in
    [Yy]|[Yy][Ee][Ss]) return 0;;
    *) return 1;;
  esac
}

# check that local working dir exists
LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ ! -d "$LOCAL_DIR" ]]; then
  echo "Can't find local dir: $LOCAL_DIR" >&2
  exit 1
fi

echo "Local dir: $LOCAL_DIR"

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync is required on your Mac. Install it and try again." >&2
  exit 1
fi

RSYNC_EXCLUDES=(".git" ".venv" "__pycache__" "*.pyc")
RSYNC_EXCLUDE_ARGS=()
for ex in "${RSYNC_EXCLUDES[@]}"; do
  RSYNC_EXCLUDE_ARGS+=(--exclude "$ex")
done

if [[ $DRY_RUN -eq 1 ]]; then
  echo "DRY RUN: would run rsync to $REMOTE:$REMOTE_DIR"
  echo "rsync -avz --delete ${RSYNC_EXCLUDE_ARGS[*]} $LOCAL_DIR/ $REMOTE:$REMOTE_DIR/"
else
  echo "Syncing files to $REMOTE:$REMOTE_DIR"
  rsync -avz --delete "${RSYNC_EXCLUDE_ARGS[@]}" "$LOCAL_DIR/" "$REMOTE:$REMOTE_DIR/"
fi

echo "Preparing remote environment"

# Build a compact remote setup script to run over ssh
read -r -d '' REMOTE_SETUP_SCRIPT <<'REMOTE'
set -euo pipefail
mkdir -p "${REMOTE_DIR}"
cd "${REMOTE_DIR}"
# ensure python3 available
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found on remote. Please install python3." >&2
  exit 2
fi
python3 -m venv .venv || true
. .venv/bin/activate
pip install --upgrade pip setuptools wheel || true
if [[ -f requirements.txt ]]; then
  pip install -r requirements.txt || true
fi
REMOTE

if [[ $DRY_RUN -eq 1 ]]; then
  echo "DRY RUN: would run remote setup script:\n$REMOTE_SETUP_SCRIPT"
else
  ssh "$REMOTE" bash -lc "$REMOTE_SETUP_SCRIPT"
fi

# create systemd service unit
read -r -d '' SERVICE_UNIT <<'UNIT'
[Unit]
Description=weatherpi service (deployed from git)
After=network.target

[Service]
User=${REMOTE_USER}
WorkingDirectory=${REMOTE_DIR}
Environment=PATH=${REMOTE_DIR}/.venv/bin
ExecStart=${REMOTE_DIR}/.venv/bin/python ${REMOTE_DIR}/${ENTRYPOINT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

echo "Installing systemd unit /etc/systemd/system/${SERVICE_NAME}.service"
if [[ $DRY_RUN -eq 1 ]]; then
  echo "DRY RUN: would write unit with contents:\n$SERVICE_UNIT"
else
  printf '%s\n' "$SERVICE_UNIT" | ssh "$REMOTE" "sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null"
  ssh "$REMOTE" "sudo systemctl daemon-reload && sudo systemctl enable ${SERVICE_NAME}.service || true && sudo systemctl restart ${SERVICE_NAME}.service || true"
fi

echo
echo "Service installation completed. To follow logs, run:" 
echo "  ssh $REMOTE 'sudo journalctl -u ${SERVICE_NAME}.service -f -n 200'"

if [[ $DRY_RUN -eq 1 ]]; then
  echo "Dry run complete. No remote changes were made."
else
  echo "Tailing logs now (press Ctrl-C to exit)"
  ssh "$REMOTE" "sudo journalctl -u ${SERVICE_NAME}.service -f -n 200"
fi

exit 0
