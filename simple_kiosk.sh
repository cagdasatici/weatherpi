#!/bin/bash
# Ultra-simple Chromium kiosk script
export DISPLAY=:0

# Wait for system to be ready
sleep 10

# Kill existing Chromium
pkill -f chromium-browser || true

# Start Chromium in kiosk mode pointing to nginx
exec chromium-browser \
  --kiosk \
  --no-sandbox \
  --disable-dev-shm-usage \
  --disable-extensions \
  --no-first-run \
  --disable-infobars \
  --start-fullscreen \
  "http://localhost/weather.html"