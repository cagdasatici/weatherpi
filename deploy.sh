#!/bin/bash
# Optimized deployment script for weatherpi
set -e

PI_HOST="weatherpi"
PI_PATH="/home/cagdas/weatherpi"

# Sync project (excluding venv)
rsync -avz --delete --exclude 'venv/' --exclude '*.pyc' --exclude '__pycache__/' ./ "$PI_HOST:$PI_PATH/"

# Only create venv if missing
ssh "$PI_HOST" "cd $PI_PATH && [ -d venv ] || python3 -m venv venv"

# Only install requirements if requirements.txt changed
rsync -avz requirements.txt "$PI_HOST:$PI_PATH/"
ssh "$PI_HOST" "cd $PI_PATH && source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt"

# Optionally restart the systemd service
ssh "$PI_HOST" "sudo systemctl restart weatherkiosk || true"

echo "Deployment complete. You can now run the app with:\nssh $PI_HOST 'cd $PI_PATH && source venv/bin/activate && python main.py'"