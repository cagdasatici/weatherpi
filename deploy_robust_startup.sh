#!/bin/bash
# Deploy Robust Kiosk Startup System

echo "🛠️ Deploying Robust WeatherPi Kiosk Startup"
echo "============================================"

# Make scripts executable
chmod +x weatherpi_robust_startup.sh
chmod +x manual_start_kiosk.sh

# Deploy to Pi
echo "📦 Copying files to Pi..."
scp weatherpi_robust_startup.sh weatherpi:~/
scp manual_start_kiosk.sh weatherpi:~/
scp weatherpi-kiosk-robust.service weatherpi:~/

# Install on Pi
ssh weatherpi << 'EOF'
    echo "🔧 Installing robust kiosk system..."
    
    # Stop existing service
    sudo systemctl stop weatherpi-kiosk || true
    sudo systemctl disable weatherpi-kiosk || true
    
    # Install new startup script
    sudo cp weatherpi_robust_startup.sh /home/cagdas/
    sudo chown cagdas:cagdas /home/cagdas/weatherpi_robust_startup.sh
    sudo chmod +x /home/cagdas/weatherpi_robust_startup.sh
    
    # Install manual startup script
    sudo cp manual_start_kiosk.sh /home/cagdas/
    sudo chown cagdas:cagdas /home/cagdas/manual_start_kiosk.sh
    sudo chmod +x /home/cagdas/manual_start_kiosk.sh
    
    # Install new service
    sudo cp weatherpi-kiosk-robust.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable weatherpi-kiosk-robust
    
    # Create log directory
    sudo mkdir -p /var/log
    sudo touch /var/log/weatherpi-startup.log
    sudo chown cagdas:cagdas /var/log/weatherpi-startup.log
    
    echo "✅ Installation complete!"
    echo
    echo "📋 Available commands:"
    echo "   Manual start:  ~/manual_start_kiosk.sh"
    echo "   Service start: sudo systemctl start weatherpi-kiosk-robust"
    echo "   Check status:  sudo systemctl status weatherpi-kiosk-robust"
    echo "   View logs:     journalctl -u weatherpi-kiosk-robust -f"
    echo "   Startup log:   tail -f /var/log/weatherpi-startup.log"
EOF

echo
echo "🎉 Deployment complete!"
echo "🧪 Ready to test the new robust startup system"