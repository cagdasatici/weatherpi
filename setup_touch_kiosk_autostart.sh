#!/bin/bash
# WeatherPi Touch Kiosk Startup Script
# Optimized for touch-only navigation

# Create improved touch-friendly kiosk startup
cat > /tmp/touch_kiosk_startup.sh << 'EOF'
#!/bin/bash
# WeatherPi Touch-Friendly Kiosk Startup

echo "🚀 Starting WeatherPi Touch Kiosk..."

# Wait for display to be ready
sleep 10

# Kill any existing Firefox instances
pkill -f firefox-esr

# Wait a moment
sleep 2

# Set display
export DISPLAY=:0

# Disable screen blanking
xset s off
xset -dpms
xset s noblank

# Start Firefox in kiosk mode with touch-optimized settings
firefox-esr \
    --kiosk \
    --no-sandbox \
    --disable-infobars \
    --disable-features=TranslateUI \
    --no-default-browser-check \
    --disable-pinch \
    --overscroll-history-navigation=0 \
    --touch-events=enabled \
    --enable-features=TouchpadOverscrollHistoryNavigation:false \
    http://127.0.0.1/weather.html \
    > /tmp/firefox_touch_kiosk.log 2>&1 &

echo "✅ WeatherPi Touch Kiosk started"
echo "📱 Touch right side → Calendar"  
echo "📱 Touch left side → Refresh weather"

EOF

# Copy the startup script to Pi
echo "📤 Deploying touch kiosk startup script..."
scp /tmp/touch_kiosk_startup.sh weatherpi:~/
ssh weatherpi "chmod +x touch_kiosk_startup.sh"

# Create improved autostart desktop file
echo "🖥️ Creating touch-optimized autostart file..."
ssh weatherpi "cat > ~/.config/autostart/weather-kiosk.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=WeatherPi Touch Kiosk
Comment=Touch-friendly weather and family calendar kiosk
Exec=/home/cagdas/touch_kiosk_startup.sh
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
StartupNotify=false
Terminal=false
EOF"

# Also create systemd service for reliability
echo "🔧 Creating systemd service for touch kiosk..."
ssh weatherpi "sudo tee /etc/systemd/system/weatherpi-touch-kiosk.service > /dev/null << 'EOF'
[Unit]
Description=WeatherPi Touch Kiosk Display
After=graphical-session.target
Wants=graphical-session.target

[Service]
Type=simple
User=cagdas
Group=cagdas
ExecStart=/home/cagdas/touch_kiosk_startup.sh
Restart=always
RestartSec=10
Environment=DISPLAY=:0

[Install]
WantedBy=graphical-session.target
EOF"

# Enable the service
echo "⚙️ Enabling touch kiosk service..."
ssh weatherpi "sudo systemctl daemon-reload"
ssh weatherpi "sudo systemctl enable weatherpi-touch-kiosk.service"

# Test current setup
echo "🧪 Testing current setup..."
ssh weatherpi "curl -I http://127.0.0.1/weather.html | head -1"

echo ""
echo "✅ TOUCH KIOSK AUTO-START CONFIGURED!"
echo "🔄 To activate: sudo reboot on your Pi"
echo ""
echo "After reboot, your Pi will automatically show:"
echo "📱 Weather page with touch navigation"
echo "👆 Swipe/tap RIGHT → Family calendar"
echo "👆 Swipe/tap LEFT → Refresh weather"
echo ""
echo "🔧 To test without rebooting:"
echo "   ssh weatherpi './touch_kiosk_startup.sh'"