#!/bin/bash
# Ultra-fast static deployment script

echo "🚀 Deploying weather app..."

# Copy HTML file directly to nginx
scp weather.html weatherpi:/tmp/
ssh weatherpi 'sudo cp /tmp/weather.html /var/www/html/ && sudo chmod 644 /var/www/html/weather.html'

# Copy icons to web server
scp -r icons/ weatherpi:/tmp/
ssh weatherpi 'sudo cp -r /tmp/icons /var/www/html/ && sudo chmod -R 755 /var/www/html/icons && sudo chown -R www-data:www-data /var/www/html/icons'

# Copy kiosk script
scp simple_kiosk.sh weatherpi:/home/cagdas/

echo "✅ Deployment complete!"
echo "📱 Web: http://192.168.178.36/weather.html"
echo "🖥️  Kiosk: ssh weatherpi './simple_kiosk.sh'"