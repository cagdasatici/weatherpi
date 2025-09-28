#!/bin/bash
# Simple Fix: Update the systemd service to work properly

ssh weatherpi << 'EOF'
    # Create a simpler, working service
    sudo tee /etc/systemd/system/weatherpi-kiosk-simple.service > /dev/null << 'SERVICE'
[Unit]
Description=WeatherPi Kiosk Display (Simple)
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
ExecStartPre=/bin/sleep 30
ExecStart=/home/cagdas/manual_start_kiosk.sh
Restart=always
RestartSec=15
KillMode=mixed

[Install]
WantedBy=graphical.target
SERVICE

    # Enable the simple service
    sudo systemctl daemon-reload
    sudo systemctl disable weatherpi-kiosk-robust
    sudo systemctl enable weatherpi-kiosk-simple
    
    echo "✅ Simple kiosk service installed"
    echo "🔄 Reboot to test automatic startup"
EOF