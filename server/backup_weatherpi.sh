#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR=${1:-/var/backups/weatherpi}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_DIR"

FILES=(/home/pi/weatherpi/calendar_events.json /home/pi/weatherpi/calendar_credentials.json)

tar -czf "$BACKUP_DIR/weatherpi_backup_${TIMESTAMP}.tgz" "${FILES[@]}" || echo "Warning: some files missing"
echo "Backup written to $BACKUP_DIR/weatherpi_backup_${TIMESTAMP}.tgz"
