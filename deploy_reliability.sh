#!/bin/bash
# Deploy reliability enhancements and updated weather code

echo "🚀 WeatherPi Reliability Deployment"
echo "==================================="

# Check if Pi is reachable
if ! ping -c 1 -W 5 weatherpi > /dev/null 2>&1; then
    echo "❌ Pi is not reachable. Please check network connection."
    exit 1
fi

echo "✅ Pi is reachable, starting deployment..."

# First, deploy the updated weather.html with cache indicator
echo "📊 Deploying weather dashboard updates..."
scp weather.html weatherpi:/home/pi/
ssh weatherpi 'sudo cp /home/pi/weather.html /var/www/html/'

# Deploy reliability enhancement script
echo "🛡️  Deploying reliability enhancements..."
scp reliability_enhancements.sh weatherpi:/home/pi/
scp health_check.sh weatherpi:/home/pi/

# Make scripts executable on Pi
ssh weatherpi 'chmod +x /home/pi/reliability_enhancements.sh /home/pi/health_check.sh'

echo ""
echo "🎯 Deployment complete! Next steps:"
echo ""
echo "1. SSH to your Pi:"
echo "   ssh weatherpi"
echo ""
echo "2. Run reliability enhancements:"
echo "   ./reliability_enhancements.sh"
echo ""
echo "3. Reboot to activate all features:"
echo "   sudo reboot"
echo ""
echo "4. Check system health anytime with:"
echo "   ./health_check.sh"
echo ""
echo "🛡️  After running these steps, your Pi will be maximally reliable!"