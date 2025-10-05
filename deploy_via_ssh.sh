#!/usr/bin/env bash
set -euo pipefail

# deploy_via_ssh.sh
# Usage: ./deploy_via_ssh.sh
# This script packages the minimal set of files from the repo, copies them to
# the Raspberry Pi via the user's ssh shortcut `ssh weatherpi`, and runs remote
# installation steps (virtualenv, systemd units, copying web files).

SSH_ALIAS="weatherpi"
TMP_TAR="/tmp/weatherpi_deploy.tar.gz"
LOCAL_TMPDIR="/tmp/weatherpi_deploy_local"

# Remote runtime user (set to your username on the Pi)
REMOTE_USER="cagdas"

# Files to include (relative to repo root)
OPT_FILES=(calendar_config.py calendar_fetcher.py)
SYSTEMD_FILES=(pi_configs/calendar-fetcher.service pi_configs/calendar-fetcher.timer pi_configs/chromium-kiosk.service pi_configs/weatherpi-kiosk.service pi_configs/weatherpi-kiosk-optimized.service)
WWW_FILES=(weather.html calendar.html)
ICONS_DIR="icons"

# Clean local temp dir
rm -rf "$LOCAL_TMPDIR"
mkdir -p "$LOCAL_TMPDIR/opt_weatherpi"
mkdir -p "$LOCAL_TMPDIR/systemd"
mkdir -p "$LOCAL_TMPDIR/www"
mkdir -p "$LOCAL_TMPDIR/www/icons"

# Copy opt files
for f in "${OPT_FILES[@]}"; do
  if [ -f "$f" ]; then
    cp "$f" "$LOCAL_TMPDIR/opt_weatherpi/"
  else
    echo "Warning: $f not found, skipping"
  fi
done

# Copy systemd files
for f in "${SYSTEMD_FILES[@]}"; do
  if [ -f "$f" ]; then
    cp "$f" "$LOCAL_TMPDIR/systemd/"
  else
    echo "Warning: $f not found, skipping"
  fi
done

# Copy web files
for f in "${WWW_FILES[@]}"; do
  if [ -f "$f" ]; then
    cp "$f" "$LOCAL_TMPDIR/www/"
  else
    echo "Warning: $f not found, skipping"
  fi
done

# Copy icons if present
if [ -d "$ICONS_DIR" ]; then
  cp -r "$ICONS_DIR"/* "$LOCAL_TMPDIR/www/icons/" || true
fi

# Create tarball
rm -f "/tmp/weatherpi_deploy.tar.gz"
( cd "$LOCAL_TMPDIR" && tar czf "$TMP_TAR" . )

echo "Uploading package to Pi via scp (ssh alias: $SSH_ALIAS)..."

# Use SSH multiplexing so you enter your password once and subsequent
# scp/ssh commands reuse the authenticated connection. This avoids storing
# the password in the script.
CONTROL_DIR="$HOME/.ssh/controlmasters"
mkdir -p "$CONTROL_DIR"
CONTROL_PATH="$CONTROL_DIR/${SSH_ALIAS}_cm_socket"

echo "Opening SSH control master (you'll be prompted once for password)..."
# Establish control master connection in background (will prompt for password once)
ssh -o ControlMaster=yes -o ControlPath="$CONTROL_PATH" -o ControlPersist=600s "$SSH_ALIAS" 'echo control-master-ready' || true

scp -o ControlPath="$CONTROL_PATH" "$TMP_TAR" "${SSH_ALIAS}:/tmp/" || { echo "scp failed"; exit 2; }

echo "Running remote install on Pi (reusing the SSH control master)..."

ssh -o ControlPath="$CONTROL_PATH" "$SSH_ALIAS" "REMOTE_USER_VAR=${REMOTE_USER} bash -s" <<'REMOTE'
set -euo pipefail
# Remote-side install steps
TMP_EXTRACT_DIR="/tmp/weatherpi_deploy"
mkdir -p "$TMP_EXTRACT_DIR"
cd /tmp
if [ -f /tmp/weatherpi_deploy.tar.gz ]; then
  tar xzf /tmp/weatherpi_deploy.tar.gz -C "$TMP_EXTRACT_DIR"
else
  echo "Deployment archive not found on remote /tmp/" >&2
  exit 3
fi

# Install Python files to /opt/weatherpi
## REMOTE_USER_VAR is set by the ssh command environment
sudo mkdir -p /opt/weatherpi
sudo cp -r "$TMP_EXTRACT_DIR/opt_weatherpi/." /opt/weatherpi/
sudo chown -R ${REMOTE_USER_VAR}:${REMOTE_USER_VAR} /opt/weatherpi
sudo chmod +x /opt/weatherpi/calendar_fetcher.py || true

# Create virtualenv and install dependencies (in user's home)
if [ ! -d /home/${REMOTE_USER_VAR}/calendar-env ]; then
  echo "Creating virtualenv at /home/${REMOTE_USER_VAR}/calendar-env"
  python3 -m venv /home/${REMOTE_USER_VAR}/calendar-env
  sudo chown -R ${REMOTE_USER_VAR}:${REMOTE_USER_VAR} /home/${REMOTE_USER_VAR}/calendar-env
fi
/home/${REMOTE_USER_VAR}/calendar-env/bin/pip install --upgrade pip
/home/${REMOTE_USER_VAR}/calendar-env/bin/pip install requests lxml || true

# Install systemd units
if [ -d "$TMP_EXTRACT_DIR/systemd" ]; then
  sudo cp -r "$TMP_EXTRACT_DIR/systemd/." /etc/systemd/system/
  sudo systemctl daemon-reload
  # Enable timer and services if present
  sudo systemctl enable --now calendar-fetcher.timer || true
  sudo systemctl enable --now chromium-kiosk.service || true
  sudo systemctl enable --now weatherpi-kiosk.service || true
fi

# Deploy web files
sudo mkdir -p /var/www/html
sudo cp -r "$TMP_EXTRACT_DIR/www/." /var/www/html/
# Ensure correct ownership and permissions
sudo chown -R www-data:www-data /var/www/html
sudo chmod -R 755 /var/www/html

# Add the remote user to www-data group so calendar fetcher can write if necessary
sudo usermod -a -G www-data ${REMOTE_USER_VAR} || true

# Optional: install chromium if not present (recommended for Pi4)
if ! command -v chromium >/dev/null 2>&1; then
  echo "Chromium not found, installing..."
  sudo apt-get update
  sudo apt-get install -y chromium || true
fi

echo "Remote install steps completed. You can check services with:"
echo "  sudo systemctl status calendar-fetcher.timer"
echo "  sudo systemctl status chromium-kiosk.service"
REMOTE

# Cleanup local temp
rm -rf "$LOCAL_TMPDIR"
rm -f "$TMP_TAR"

echo "Deployment finished. Check the Pi with 'ssh weatherpi sudo systemctl status calendar-fetcher.timer' and 'ssh weatherpi sudo journalctl -u calendar-fetcher.service -f'"
