#!/bin/bash
# Clean Firefox Startup - Clears cache and profile issues

echo "🧹 Clean Firefox Kiosk Startup"
echo "=============================="

# Kill any existing Firefox
echo "🛑 Stopping existing Firefox processes..."
sudo pkill -f firefox || true
sleep 5

# Clear Firefox cache and profile issues
echo "🗑️ Cleaning Firefox cache..."
rm -rf ~/.mozilla/firefox/*/storage
rm -rf ~/.mozilla/firefox/*/webappsstore.sqlite*
rm -rf ~/.mozilla/firefox/*/places.sqlite*
rm -rf ~/.cache/mozilla
rm -rf /tmp/.org.chromium*

# Set up display
export DISPLAY=:0
export XAUTHORITY=/home/cagdas/.Xauthority

# Test web server first
echo "🌐 Testing web server..."
if ! curl -f -s http://localhost/weather.html > /dev/null; then
    echo "❌ Web server not responding"
    echo "🔧 Restarting nginx..."
    sudo systemctl restart nginx
    sleep 3
fi

# Test again
if curl -f -s http://localhost/weather.html > /dev/null; then
    echo "✅ Web server OK"
else
    echo "❌ Web server still not responding"
    exit 1
fi

# Disable screen blanking
echo "🖥️ Configuring display..."
xset s off 2>/dev/null || true
xset -dpms 2>/dev/null || true  
xset s noblank 2>/dev/null || true

# Start Firefox with fresh profile
echo "🦊 Starting Firefox with clean profile..."
exec firefox-esr \
    --kiosk \
    --no-sandbox \
    --no-first-run \
    --disable-infobars \
    --disable-features=TranslateUI \
    --no-default-browser-check \
    --autoplay-policy=no-user-gesture-required \
    --disable-web-security \
    --disable-features=VizDisplayCompositor \
    --temp-profile \
    --no-remote \
    http://127.0.0.1/weather.html