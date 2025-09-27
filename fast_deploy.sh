#!/bin/bash
# Ultra-fast static deployment script

echo "🚀 Deploying weather app..."

# Copy HTML file directly to nginx
scp weather.html weatherpi:/tmp/
ssh weatherpi 'sudo cp /tmp/weather.html /var/www/html/ && sudo chmod 644 /var/www/html/weather.html'

# Copy kiosk script
scp simple_kiosk.sh weatherpi:/home/cagdas/

echo "✅ Deployment complete!"
echo "📱 Web: http://192.168.178.36/weather.html"
echo "🖥️  Kiosk: ssh weatherpi './simple_kiosk.sh'"