#!/bin/bash

# Configuration
BACKUP_DIR="/home/pi/weatherpi_backups"
LOG_DIR="/home/pi/weatherpi/logs"
MAX_BACKUPS=5
MAX_LOG_SIZE_MB=10

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"
mkdir -p "$LOG_DIR"

# Create backup with timestamp
timestamp=$(date +%Y%m%d_%H%M%S)
backup_file="$BACKUP_DIR/weatherpi_backup_$timestamp.tar.gz"
tar -czf "$backup_file" /home/pi/weatherpi/

# Remove old backups keeping only MAX_BACKUPS
ls -t "$BACKUP_DIR"/weatherpi_backup_*.tar.gz | tail -n +$((MAX_BACKUPS + 1)) | xargs -r rm

# Log rotation
log_file="$LOG_DIR/weatherpi.log"
if [ -f "$log_file" ]; then
    size_mb=$(du -m "$log_file" | cut -f1)
    if [ "$size_mb" -gt "$MAX_LOG_SIZE_MB" ]; then
        mv "$log_file" "$log_file.$timestamp"
        gzip "$log_file.$timestamp"
    fi
fi

echo "Backup completed: $backup_file"