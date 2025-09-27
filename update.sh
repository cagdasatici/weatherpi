#!/bin/bash

# Configuration
APP_DIR="/home/pi/weatherpi"
BACKUP_DIR="/home/pi/weatherpi_backups"
LOG_DIR="$APP_DIR/logs"

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_DIR/update.log"
    echo "$1"
}

# Create directories if they don't exist
mkdir -p "$APP_DIR"
mkdir -p "$BACKUP_DIR"
mkdir -p "$LOG_DIR"

# Stop the service
log_message "Stopping weatherkiosk service..."
sudo systemctl stop weatherkiosk

# Backup current version
./backup.sh

# Update application files
log_message "Updating application files..."
rsync -av --exclude 'logs' --exclude '*.log' --exclude '*.service' . "$APP_DIR/"

# Update permissions
log_message "Updating permissions..."
sudo chown -R pi:pi "$APP_DIR"
chmod +x "$APP_DIR/main.py"
chmod +x "$APP_DIR"/*.sh

# Update service file if changed
if ! cmp --silent weatherkiosk.service /etc/systemd/system/weatherkiosk.service; then
    log_message "Updating service file..."
    sudo cp weatherkiosk.service /etc/systemd/system/
    sudo systemctl daemon-reload
fi

# Reinstall dependencies
log_message "Updating dependencies..."
pip3 install -r requirements.txt

# Start the service
log_message "Starting weatherkiosk service..."
sudo systemctl start weatherkiosk

# Check service status
sleep 2
if systemctl is-active --quiet weatherkiosk; then
    log_message "Update completed successfully!"
else
    log_message "ERROR: Service failed to start. Check journalctl -u weatherkiosk for details"
fi