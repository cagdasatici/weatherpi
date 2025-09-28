#!/bin/bash
# Update the kiosk service to handle crashes and session restore

ssh weatherpi << 'EOF'
    # Create a crash-resistant Firefox startup script
    tee /home/cagdas/crash_resistant_kiosk.sh > /dev/null << 'SCRIPT'
#!/bin/bash
# Crash-resistant WeatherPi Kiosk

export DISPLAY=:0
export XAUTHORITY=/home/cagdas/.Xauthority

# Wait for system to be ready
sleep 15

while true; do
    echo "[$(date)] Starting Firefox kiosk..." >> /var/log/weatherpi-kiosk.log
    
    # Clean up any hanging processes
    pkill -f firefox || true
    sleep 2
    
    # Configure Firefox for stability
    firefox-esr \
        --kiosk \
        --no-sandbox \
        --disable-infobars \
        --disable-features=TranslateUI \
        --no-default-browser-check \
        --autoplay-policy=no-user-gesture-required \
        --disable-background-timer-throttling \
        --disable-backgrounding-occluded-windows \
        --disable-renderer-backgrounding \
        --memory-pressure-off \
        --max_old_space_size=512 \
        http://127.0.0.1/weather.html \
        >> /var/log/weatherpi-kiosk.log 2>&1
    
    echo "[$(date)] Firefox exited, restarting in 10 seconds..." >> /var/log/weatherpi-kiosk.log
    sleep 10
done
SCRIPT

    # Make it executable
    chmod +x /home/cagdas/crash_resistant_kiosk.sh
    
    # Update the systemd service
    sudo tee /etc/systemd/system/weatherpi-kiosk-final.service > /dev/null << 'SERVICE'
[Unit]
Description=WeatherPi Kiosk Display (Crash Resistant)
After=graphical.target lightdm.service nginx.service
Wants=graphical.target
Requires=nginx.service

[Service]
Type=simple
User=cagdas
Group=cagdas
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/cagdas/.Xauthority
WorkingDirectory=/home/cagdas
ExecStart=/home/cagdas/crash_resistant_kiosk.sh
Restart=always
RestartSec=5
KillMode=mixed

[Install]
WantedBy=graphical.target
SERVICE

    # Enable the new service
    sudo systemctl daemon-reload
    sudo systemctl disable weatherpi-kiosk-simple || true
    sudo systemctl enable weatherpi-kiosk-final
    
    # Create log file
    sudo touch /var/log/weatherpi-kiosk.log
    sudo chown cagdas:cagdas /var/log/weatherpi-kiosk.log
    
    echo "✅ Crash-resistant kiosk service installed"
    echo "📋 Commands:"
    echo "   View logs: tail -f /var/log/weatherpi-kiosk.log"
    echo "   Service status: sudo systemctl status weatherpi-kiosk-final"
EOF