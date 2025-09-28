#!/bin/bash
# Deploy updated touch-friendly calendar to Pi

echo "🚀 Deploying Touch-Friendly Family Calendar"
echo "==========================================="

# Test connection first
if ! ssh weatherpi "echo 'Connection test OK'"; then
    echo "❌ Cannot connect to Pi. Is it online?"
    exit 1
fi

# Deploy weather.html with improved touch navigation
echo "📱 Deploying weather.html with touch navigation..."
scp weather.html weatherpi:/tmp/
ssh weatherpi "sudo cp /tmp/weather.html /var/www/html/"

# Deploy family-only calendar.html
echo "👪 Deploying family-only calendar.html..."
scp calendar.html weatherpi:/tmp/
ssh weatherpi "sudo cp /tmp/calendar.html /var/www/html/"

# Deploy standalone family calendar
echo "🏠 Deploying standalone family_calendar.html..."
scp family_calendar_local.html weatherpi:/tmp/
ssh weatherpi "sudo cp /tmp/family_calendar_local.html /var/www/html/family_calendar.html"

# Set proper permissions
echo "🔐 Setting permissions..."
ssh weatherpi "sudo chown www-data:www-data /var/www/html/*.html"

# Test the deployment
echo "🧪 Testing deployment..."
ssh weatherpi "curl -I http://127.0.0.1/weather.html | head -1"
ssh weatherpi "curl -I http://127.0.0.1/calendar.html | head -1"
ssh weatherpi "curl -I http://127.0.0.1/family_calendar.html | head -1"

echo ""
echo "✅ Touch-Friendly Family Calendar Deployed!"
echo "📱 Navigation Instructions:"
echo "   • Weather Page: Swipe/tap RIGHT → Go to family calendar"
echo "   • Weather Page: Swipe/tap LEFT → Refresh weather"
echo "   • Calendar Page: Swipe/tap LEFT → Go back to weather"
echo ""
echo "🌐 Access URLs:"
echo "   • Weather: http://weatherpi/weather.html"
echo "   • Family Calendar: http://weatherpi/calendar.html"
echo "   • Standalone Family: http://weatherpi/family_calendar.html"
echo ""
echo "👆 Just TOUCH and SWIPE to navigate - no keyboard needed!"