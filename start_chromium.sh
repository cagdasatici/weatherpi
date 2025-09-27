#!/bin/bash
# Chromium-only startup script (web server runs separately)

export DISPLAY=:0
export XDG_RUNTIME_DIR=/run/user/1000

# Wait for X server and web server to be ready
sleep 15

# Kill any existing Chromium processes
pkill -f chromium-browser || true

# Wait for web server to be available
while ! curl -s http://localhost:8000/weather.html > /dev/null; do
    echo "Waiting for web server..."
    sleep 2
done

echo "Starting Chromium kiosk mode..."

# Start Chromium in kiosk mode with more compatible flags
exec chromium-browser \
  --kiosk \
  --no-sandbox \
  --disable-dev-shm-usage \
  --disable-gpu \
  --disable-extensions \
  --disable-plugins \
  --disable-web-security \
  --disable-features=TranslateUI \
  --no-first-run \
  --disable-default-apps \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-restore-session-state \
  --start-fullscreen \
  --window-size=800,480 \
  "http://localhost:8000/weather.html"