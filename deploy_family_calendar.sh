#!/bin/bash
# Deploy Family Calendar Integration to WeatherPi
# Run this script when Pi is accessible

echo "🚀 Deploying Family Calendar Integration to WeatherPi"
echo "=================================================="

# Upload core calendar files
echo "📤 Uploading calendar files..."
scp calendar_fetcher.py calendar_config.py calendar_credentials.json weatherpi:~/
scp family_calendar_local.html family_calendar_fetcher.py weatherpi:~/

# Upload to web directory
echo "🌐 Deploying to web directory..."
ssh weatherpi "sudo cp family_calendar_local.html /var/www/html/family_calendar.html"
ssh weatherpi "sudo chown www-data:www-data /var/www/html/family_calendar.html"

# Test calendar fetch
echo "🧪 Testing calendar fetch on Pi..."
ssh weatherpi "cd ~ && python3 calendar_fetcher.py"

# Update cron job for family calendar
echo "⏰ Setting up family calendar cron job..."
ssh weatherpi "echo '*/15 * * * * cd /home/pi && python3 family_calendar_fetcher.py && sudo cp family_calendar_events.json /var/www/html/ 2>>/var/log/family_calendar.log' | crontab -"

# Deploy calendar events to web
echo "📅 Deploying calendar events..."
ssh weatherpi "sudo cp calendar_events.json /var/www/html/"
ssh weatherpi "sudo chown www-data:www-data /var/www/html/calendar_events.json"

# Test web access
echo "🔍 Testing web access..."
ssh weatherpi "curl -I http://127.0.0.1/calendar.html"
ssh weatherpi "curl -I http://127.0.0.1/family_calendar.html"

echo ""
echo "✅ Family Calendar Deployment Complete!"
echo "📱 Access your calendars:"
echo "   • Full calendar: http://weatherpi/calendar.html"
echo "   • Family only:   http://weatherpi/family_calendar.html"
echo ""
echo "🔄 Auto-updates every 15 minutes via cron"
echo "📊 View logs: ssh weatherpi 'tail -f /var/log/family_calendar.log'"
echo ""
echo "🎉 WeatherPi Family Calendar is ready! 🌤️📅"