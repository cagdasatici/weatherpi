#!/bin/bash
# WeatherPi Web Server Diagnostic Script

echo "🔍 WeatherPi Web Server Diagnostics"
echo "===================================="

# Check nginx status
echo "📊 NGINX STATUS:"
systemctl is-active nginx && echo "✅ Active" || echo "❌ Inactive"

# Check if files exist
echo
echo "📁 FILE STATUS:"
ls -la /var/www/html/weather.html && echo "✅ weather.html exists" || echo "❌ weather.html missing"

# Test HTTP access
echo
echo "🌐 HTTP TESTS:"
echo "Testing localhost..."
curl -I -s http://localhost/weather.html | head -1 && echo "✅ localhost OK" || echo "❌ localhost failed"

echo "Testing 127.0.0.1..."
curl -I -s http://127.0.0.1/weather.html | head -1 && echo "✅ 127.0.0.1 OK" || echo "❌ 127.0.0.1 failed"

# Test DNS resolution
echo
echo "🔍 DNS TESTS:"
nslookup localhost >/dev/null 2>&1 && echo "✅ localhost DNS OK" || echo "❌ localhost DNS failed"

# Check Firefox processes
echo
echo "🦊 FIREFOX STATUS:"
if pgrep firefox >/dev/null; then
    echo "✅ Firefox is running"
    echo "Process count: $(pgrep firefox | wc -l)"
else
    echo "❌ Firefox not running"
fi

# Check display
echo
echo "🖥️ DISPLAY STATUS:"
if [ -n "$DISPLAY" ]; then
    echo "✅ DISPLAY variable set: $DISPLAY"
    if xset q >/dev/null 2>&1; then
        echo "✅ X11 display accessible"
    else
        echo "❌ X11 display not accessible"
    fi
else
    echo "❌ DISPLAY variable not set"
fi

# Test Firefox manually
echo
echo "🧪 MANUAL FIREFOX TEST:"
echo "Attempting to start Firefox with diagnostic output..."
timeout 10 firefox-esr --version 2>&1 && echo "✅ Firefox executable OK" || echo "❌ Firefox executable failed"

echo
echo "🎯 QUICK FIX SUGGESTIONS:"
if ! systemctl is-active --quiet nginx; then
    echo "🔧 Run: sudo systemctl restart nginx"
fi

if [ ! -f "/var/www/html/weather.html" ]; then
    echo "🔧 Weather.html is missing - redeploy files"
fi

if ! pgrep firefox >/dev/null; then
    echo "🔧 Start Firefox: DISPLAY=:0 firefox-esr --kiosk http://127.0.0.1/weather.html"
fi