#!/bin/bash
# Chromium Kiosk startup script

export DISPLAY=:0
export XDG_RUNTIME_DIR=/run/user/1000

# Wait for X server to be ready
sleep 10

# Kill any existing processes
pkill -f chromium-browser || true
pkill -f webserver.py || true

# Start web server in background
cd /home/cagdas/weatherpi
source venv/bin/activate
python3 webserver.py &
WEBSERVER_PID=$!
echo $WEBSERVER_PID > /tmp/webserver.pid

# Wait for web server to start
sleep 5

# Start Chromium in kiosk mode with more compatible flags
chromium-browser \
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
  "http://localhost:8000/weather.html" &

CHROMIUM_PID=$!
echo $CHROMIUM_PID > /tmp/chromium.pid

# Wait for Chromium (this keeps the service running)
wait $CHROMIUM_PID

# Cleanup on exit
kill $WEBSERVER_PID 2>/dev/null || true