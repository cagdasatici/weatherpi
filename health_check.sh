#!/bin/bash
# WeatherPi System Health Check - Remote monitoring script

echo "🛡️  WeatherPi System Health Report"
echo "===================================="
echo "Timestamp: $(date)"
echo ""

# System uptime
echo "📊 SYSTEM STATUS:"
echo "Uptime: $(uptime -p)"
echo "Load: $(uptime | awk -F'load average:' '{print $2}')"

# Memory usage
echo ""
echo "🧠 MEMORY USAGE:"
free -h | grep -E "Mem|Swap"

# Disk usage
echo ""
echo "💾 DISK USAGE:"
df -h | grep -E "Filesystem|/dev/root"

# Temperature
echo ""
echo "🌡️  SYSTEM TEMPERATURE:"
if [ -f /sys/class/thermal/thermal_zone0/temp ]; then
    temp=$(cat /sys/class/thermal/thermal_zone0/temp)
    echo "CPU: $((temp/1000))°C"
else
    echo "Temperature monitoring not available"
fi

# Network connectivity
echo ""
echo "🌐 NETWORK STATUS:"
if ping -c 1 -W 3 8.8.8.8 > /dev/null 2>&1; then
    echo "✅ Internet connectivity: OK"
else
    echo "❌ Internet connectivity: FAILED"
fi

# Check if Firefox is running
echo ""
echo "🌦️  WEATHER KIOSK STATUS:"
if pgrep -f firefox > /dev/null; then
    echo "✅ Firefox: Running"
    firefox_mem=$(ps -eo pid,comm,%mem --sort=-%mem | grep firefox | head -1 | awk '{print $3}')
    echo "   Memory usage: ${firefox_mem}%"
else
    echo "❌ Firefox: Not running"
fi

# Service status
echo ""
echo "⚙️  SERVICE STATUS:"
services=("nginx" "weatherpi-kiosk" "watchdog" "network-watchdog" "system-health-monitor" "thermal-monitor")
for service in "${services[@]}"; do
    if systemctl is-active --quiet "$service"; then
        echo "✅ $service: Active"
    else
        echo "❌ $service: Inactive"
    fi
done

# Recent errors (if log exists)
echo ""
echo "⚠️  RECENT ISSUES:"
if [ -f /var/log/system_health.log ]; then
    echo "Last 5 system health events:"
    tail -5 /var/log/system_health.log || echo "No recent events"
else
    echo "System health log not found (normal if reliability enhancements not yet installed)"
fi

# Hardware info
echo ""
echo "🔧 HARDWARE INFO:"
echo "Model: $(cat /proc/device-tree/model 2>/dev/null | tr -d '\0' || echo 'Unknown')"
echo "Firmware: $(vcgencmd version | head -1)"

echo ""
echo "===================================="
echo "Health check completed at $(date)"