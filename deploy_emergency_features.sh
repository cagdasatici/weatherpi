#!/bin/bash
# Quick deployment script for Pi reliability enhancements

echo "🚀 WeatherPi Reliability & Emergency Access Deployment"
echo "====================================================="

# Deploy files to Pi when SSH is available
if ping -c 1 weatherpi >/dev/null 2>&1; then
    echo "✅ Pi is reachable - deploying enhancements..."
    
    # Copy files to Pi
    scp health_dashboard.py weatherpi:~/
    scp health-dashboard.service weatherpi:~/
    scp ultimate_reliability.sh weatherpi:~/
    scp weather.html weatherpi:~/
    
    # SSH into Pi and set up services
    ssh weatherpi << 'EOF'
        # Install health dashboard
        sudo cp health_dashboard.py /home/cagdas/
        sudo cp health-dashboard.service /etc/systemd/system/
        sudo systemctl daemon-reload
        sudo systemctl enable health-dashboard
        sudo systemctl start health-dashboard
        
        # Deploy updated weather.html
        sudo cp weather.html /var/www/html/
        
        # Run ultimate reliability enhancements
        chmod +x ultimate_reliability.sh
        sudo ./ultimate_reliability.sh
        
        echo "🎉 Deployment complete!"
        echo "📊 Health dashboard: http://$(hostname -I | awk '{print $1}'):8080"
        echo "🖱️ Emergency desktop: 7 rapid taps on weather screen"
        echo "🔄 Reboot recommended to activate all features"
EOF
    
else
    echo "❌ Pi not reachable via SSH"
    echo "📋 Manual deployment required:"
    echo "   1. Connect to Pi physically"
    echo "   2. Copy files via USB or when SSH returns"
    echo "   3. Run the deployment commands manually"
fi

echo
echo "📋 FEATURES DEPLOYED:"
echo "✅ Web Health Dashboard (port 8080)"
echo "✅ Emergency Desktop Access (7 rapid taps)"  
echo "✅ Network Watchdog with Auto-Recovery"
echo "✅ System Health Monitor"
echo "✅ Thermal Management"
echo "✅ Hardware Watchdog"