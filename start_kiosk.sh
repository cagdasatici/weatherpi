#!/bin/bash
# Chromium Kiosk startup script

# Wait for X server to be ready
sleep 5

# Kill any existing Chromium processes
pkill -f chromium-browser || true

# Start web server in background
cd /home/cagdas/weatherpi
source venv/bin/activate
python3 webserver.py &
WEBSERVER_PID=$!

# Wait for web server to start
sleep 3

# Start Chromium in kiosk mode
DISPLAY=:0 chromium-browser \
  --kiosk \
  --no-sandbox \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-restore-session-state \
  --disable-extensions \
  --disable-plugins \
  --disable-web-security \
  --disable-features=TranslateUI \
  --disable-ipc-flooding-protection \
  --no-first-run \
  --fast \
  --fast-start \
  --disable-default-apps \
  --disable-popup-blocking \
  --disable-prompt-on-repost \
  --no-message-box \
  --force-device-scale-factor=1.0 \
  --window-size=800,480 \
  --start-fullscreen \
  "http://localhost:8000/weather.html"

# If Chromium exits, kill the web server
kill $WEBSERVER_PID 2>/dev/null || true