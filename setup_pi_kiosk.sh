#!/bin/bash
# WeatherPi Complete Setup Script
# This script configures all the necessary components for the weather kiosk

echo "🚀 Setting up WeatherPi Kiosk..."

# 1. Install required packages
echo "📦 Installing packages..."
sudo apt update
sudo apt install -y nginx firefox-esr openbox xinit x11-xserver-utils

# 2. Enable nginx
echo "🌐 Enabling web server..."
sudo systemctl enable nginx
sudo systemctl start nginx

# 3. Copy weather files to web root
echo "📄 Deploying weather files..."
sudo cp weather.html /var/www/html/
sudo cp -r icons /var/www/html/
sudo chmod 644 /var/www/html/weather.html
sudo chmod -R 755 /var/www/html/icons
sudo chown -R www-data:www-data /var/www/html/icons

# 4. Install systemd service
echo "⚙️ Setting up systemd service..."
sudo cp pi_configs/weatherpi-kiosk.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable weatherpi-kiosk.service

# 5. Enable lightdm
echo "🖥️ Configuring display manager..."
sudo systemctl enable lightdm

# 6. Setup autostart configs (multiple methods for reliability)
echo "🔄 Setting up autostart..."
mkdir -p ~/.config/openbox
mkdir -p ~/.config/autostart

cp pi_configs/openbox-autostart ~/.config/openbox/autostart 2>/dev/null || true
cp pi_configs/weather-kiosk.desktop ~/.config/autostart/ 2>/dev/null || true
cp pi_configs/.xinitrc ~/ 2>/dev/null || true
chmod +x ~/.config/openbox/autostart 2>/dev/null || true
chmod +x pi_configs/start_weather.sh 2>/dev/null || true

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Reboot the Pi: sudo reboot"
echo "2. If autostart fails, run: ./pi_configs/start_weather.sh"
echo "3. Web interface: http://localhost/weather.html"
echo ""
echo "Troubleshooting:"
echo "- Check service: sudo systemctl status weatherpi-kiosk.service"
echo "- Manual start: firefox-esr --kiosk http://localhost/weather.html"
