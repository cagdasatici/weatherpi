#!/bin/bash
# Manual WeatherPi Kiosk Startup
# Use this for immediate testing and troubleshooting

echo "🚀 Manual WeatherPi Kiosk Startup"
echo "================================="

# Kill any existing Firefox
echo "🧹 Cleaning up existing Firefox..."
sudo pkill -f firefox || true
sleep 2

# Check prerequisites
echo "✅ Checking prerequisites..."

# Check nginx
if ! systemctl is-active --quiet nginx; then
    echo "🔧 Starting nginx..."
    sudo systemctl start nginx
fi

# Check display
export DISPLAY=:0
if ! xset q >/dev/null 2>&1; then
    echo "❌ X11 display not available"
    echo "💡 Try: sudo systemctl restart lightdm"
    exit 1
fi

# Disable screen blanking
echo "🖥️ Configuring display..."
xset s off 2>/dev/null || true
xset -dpms 2>/dev/null || true
xset s noblank 2>/dev/null || true

# Test web server
echo "🌐 Testing web server..."
if ! curl -f -s http://localhost/weather.html >/dev/null; then
    echo "❌ Web server not responding"
    echo "💡 Check: sudo systemctl status nginx"
    exit 1
fi

echo "✅ All prerequisites OK"
echo "🦊 Starting Firefox in kiosk mode..."

# Start Firefox with full options
exec firefox-esr \
    --kiosk \
    --no-sandbox \
    --no-first-run \
    --disable-infobars \
    --disable-features=TranslateUI \
    --no-default-browser-check \
    --autoplay-policy=no-user-gesture-required \
    http://localhost/weather.html