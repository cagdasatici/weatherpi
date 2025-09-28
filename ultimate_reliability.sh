#!/bin/bash
# WeatherPi ULTIMATE Reliability Enhancement Script
# Maximum reliability for Pi kiosk systems with aggressive monitoring

set -e

echo "🛡️  WeatherPi ULTIMATE Reliability System"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 1. HARDWARE WATCHDOG - Auto reboot on system hangs
log_info "Setting up hardware watchdog..."
sudo apt-get update -y || true
sudo apt-get install -y watchdog || true

# Enable hardware watchdog
if ! grep -q "dtparam=watchdog=on" /boot/config.txt; then
    echo "dtparam=watchdog=on" | sudo tee -a /boot/config.txt
    log_info "Hardware watchdog enabled"
fi

# Configure aggressive watchdog settings
sudo tee /etc/watchdog.conf > /dev/null << 'EOF'
# Hardware watchdog device
watchdog-device = /dev/watchdog
watchdog-timeout = 15

# System load monitoring (aggressive)
max-load-1 = 10
max-load-5 = 8
max-load-15 = 6

# Memory monitoring
min-memory = 1024
allocatable-memory = 512

# Network connectivity test
ping = 8.8.8.8
ping-count = 3

# Critical file monitoring
file = /var/log/messages
change = 1407

# Service monitoring
pidfile = /var/run/nginx.pid
pidfile = /var/run/firefox.pid

# Temperature monitoring
temperature-device = /sys/class/thermal/thermal_zone0/temp
max-temperature = 75000

# Interface monitoring
interface = wlan0

# Repair attempts before reboot
repair-timeout = 60
repair-maximum = 3

# Logging
verbose = yes
logtick = yes
EOF

# Enable and start watchdog
sudo systemctl enable watchdog
sudo systemctl start watchdog

# 2. NETWORK WATCHDOG SERVICE
log_info "Creating network recovery service..."
sudo tee /etc/systemd/system/network-watchdog.service > /dev/null << 'EOF'
[Unit]
Description=Network Connectivity Watchdog
After=network.target

[Service]
Type=simple
Restart=always
RestartSec=30
ExecStart=/usr/local/bin/network-watchdog.sh
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Network watchdog script
sudo tee /usr/local/bin/network-watchdog.sh > /dev/null << 'EOF'
#!/bin/bash
# Aggressive network monitoring and recovery

LOG_FILE="/var/log/network-watchdog.log"
FAILURE_COUNT=0
MAX_FAILURES=3

log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
    echo "$1"
}

check_connectivity() {
    # Multiple connectivity tests
    ping -c 1 -W 5 8.8.8.8 >/dev/null 2>&1 && return 0
    ping -c 1 -W 5 1.1.1.1 >/dev/null 2>&1 && return 0
    ping -c 1 -W 5 google.com >/dev/null 2>&1 && return 0
    return 1
}

recover_network() {
    log_message "🔄 Attempting network recovery (attempt $FAILURE_COUNT/$MAX_FAILURES)"
    
    # Restart networking services
    sudo systemctl restart dhcpcd
    sleep 10
    sudo systemctl restart wpa_supplicant
    sleep 10
    
    # Reset network interface
    sudo ip link set wlan0 down
    sleep 5
    sudo ip link set wlan0 up
    sleep 10
    
    # Flush DNS
    sudo systemctl restart systemd-resolved
    
    log_message "Network recovery attempt completed"
}

while true; do
    if check_connectivity; then
        if [ $FAILURE_COUNT -gt 0 ]; then
            log_message "✅ Network connectivity restored"
            FAILURE_COUNT=0
        fi
        sleep 30
    else
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        log_message "❌ Network connectivity failed (failure $FAILURE_COUNT/$MAX_FAILURES)"
        
        if [ $FAILURE_COUNT -ge $MAX_FAILURES ]; then
            log_message "🚨 Max network failures reached - attempting recovery"
            recover_network
            FAILURE_COUNT=0
        fi
        
        sleep 10
    fi
done
EOF

sudo chmod +x /usr/local/bin/network-watchdog.sh
sudo systemctl enable network-watchdog
sudo systemctl start network-watchdog

# 3. SYSTEM HEALTH MONITOR
log_info "Creating system health monitor..."
sudo tee /etc/systemd/system/system-health-monitor.service > /dev/null << 'EOF'
[Unit]
Description=System Health Monitor
After=network.target

[Service]
Type=simple
Restart=always
RestartSec=60
ExecStart=/usr/local/bin/system-health-monitor.sh
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo tee /usr/local/bin/system-health-monitor.sh > /dev/null << 'EOF'
#!/bin/bash
# Comprehensive system health monitoring

LOG_FILE="/var/log/system-health.log"
CRITICAL_TEMP=80
CRITICAL_MEMORY_MB=50

log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
    echo "$1"
}

check_temperature() {
    if [ -f "/sys/class/thermal/thermal_zone0/temp" ]; then
        TEMP=$(cat /sys/class/thermal/thermal_zone0/temp)
        TEMP_C=$((TEMP / 1000))
        
        if [ $TEMP_C -gt $CRITICAL_TEMP ]; then
            log_message "🌡️  CRITICAL: Temperature $TEMP_C°C exceeds threshold"
            # Emergency throttling
            echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor >/dev/null
            return 1
        fi
    fi
    return 0
}

check_memory() {
    AVAILABLE_MB=$(free -m | awk '/^Mem:/{print $7}')
    if [ $AVAILABLE_MB -lt $CRITICAL_MEMORY_MB ]; then
        log_message "🧠 CRITICAL: Only ${AVAILABLE_MB}MB memory available"
        # Emergency memory cleanup
        sudo sync
        sudo sysctl -w vm.drop_caches=3
        return 1
    fi
    return 0
}

check_services() {
    SERVICES=("nginx" "firefox" "ssh")
    for service in "${SERVICES[@]}"; do
        if ! systemctl is-active --quiet "$service" 2>/dev/null; then
            log_message "⚙️  Service $service is not running - restarting"
            sudo systemctl restart "$service" || true
        fi
    done
}

check_disk_space() {
    DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ $DISK_USAGE -gt 90 ]; then
        log_message "💾 CRITICAL: Disk usage at ${DISK_USAGE}%"
        # Emergency cleanup
        sudo journalctl --vacuum-size=50M
        sudo apt-get autoremove -y
        sudo apt-get autoclean
        return 1
    fi
    return 0
}

while true; do
    check_temperature
    check_memory
    check_services
    check_disk_space
    
    # Health report every hour
    if [ $(($(date +%M) % 60)) -eq 0 ]; then
        UPTIME=$(uptime -p)
        TEMP=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null | awk '{print $1/1000}' || echo "N/A")
        MEM=$(free -h | awk '/^Mem:/{print $3 "/" $2}')
        log_message "📊 Health: Uptime: $UPTIME, Temp: ${TEMP}°C, Memory: $MEM"
    fi
    
    sleep 60
done
EOF

sudo chmod +x /usr/local/bin/system-health-monitor.sh
sudo systemctl enable system-health-monitor
sudo systemctl start system-health-monitor

# 4. THERMAL MONITORING AND CONTROL
log_info "Setting up thermal management..."
sudo tee /etc/systemd/system/thermal-monitor.service > /dev/null << 'EOF'
[Unit]
Description=Thermal Monitor and Control
After=multi-user.target

[Service]
Type=simple
Restart=always
RestartSec=30
ExecStart=/usr/local/bin/thermal-monitor.sh
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo tee /usr/local/bin/thermal-monitor.sh > /dev/null << 'EOF'
#!/bin/bash
# Aggressive thermal monitoring and control

TEMP_FILE="/sys/class/thermal/thermal_zone0/temp"
LOG_FILE="/var/log/thermal.log"
WARN_TEMP=70
CRITICAL_TEMP=75
EMERGENCY_TEMP=80

log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
    echo "$1"
}

while true; do
    if [ -f "$TEMP_FILE" ]; then
        TEMP_MILLIC=$(cat "$TEMP_FILE")
        TEMP_C=$((TEMP_MILLIC / 1000))
        
        if [ $TEMP_C -gt $EMERGENCY_TEMP ]; then
            log_message "🚨 EMERGENCY: Temperature $TEMP_C°C - Initiating emergency shutdown"
            sudo shutdown -h now
        elif [ $TEMP_C -gt $CRITICAL_TEMP ]; then
            log_message "🌡️  CRITICAL: Temperature $TEMP_C°C - Aggressive throttling"
            # Set CPU governor to powersave
            echo powersave | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor >/dev/null
            # Reduce GPU memory split
            # Kill non-essential processes if needed
        elif [ $TEMP_C -gt $WARN_TEMP ]; then
            log_message "⚠️  WARNING: Temperature $TEMP_C°C - Enabling thermal management"
            echo conservative | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor >/dev/null
        else
            echo ondemand | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor >/dev/null
        fi
    fi
    
    sleep 30
done
EOF

sudo chmod +x /usr/local/bin/thermal-monitor.sh
sudo systemctl enable thermal-monitor
sudo systemctl start thermal-monitor

# 5. OPTIMIZE BOOT AND SYSTEM SETTINGS
log_info "Optimizing system settings..."

# Disable unnecessary services
DISABLE_SERVICES=(
    "bluetooth"
    "hciuart"
    "avahi-daemon"
    "cups"
    "cups-browsed"
    "ModemManager"
    "pppd-dns"
)

for service in "${DISABLE_SERVICES[@]}"; do
    sudo systemctl disable "$service" 2>/dev/null || true
    sudo systemctl stop "$service" 2>/dev/null || true
done

# Configure swappiness for better performance
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf

# Increase file watchers for better monitoring
echo 'fs.inotify.max_user_watches=524288' | sudo tee -a /etc/sysctl.conf

# Network optimizations
echo 'net.core.rmem_max = 16777216' | sudo tee -a /etc/sysctl.conf
echo 'net.core.wmem_max = 16777216' | sudo tee -a /etc/sysctl.conf

# 6. CREATE RECOVERY SCRIPTS
log_info "Creating emergency recovery tools..."

# Emergency network reset
sudo tee /usr/local/bin/emergency-network-reset.sh > /dev/null << 'EOF'
#!/bin/bash
echo "🚨 EMERGENCY NETWORK RESET"
sudo systemctl stop dhcpcd
sudo systemctl stop wpa_supplicant
sudo ip link set wlan0 down
sleep 5
sudo ip link set wlan0 up
sudo systemctl start wpa_supplicant
sudo systemctl start dhcpcd
echo "Network reset completed"
EOF

# Emergency system cleanup
sudo tee /usr/local/bin/emergency-cleanup.sh > /dev/null << 'EOF'
#!/bin/bash
echo "🚨 EMERGENCY SYSTEM CLEANUP"
sudo journalctl --vacuum-size=10M
sudo apt-get autoremove -y
sudo apt-get autoclean
sudo sync
sudo sysctl -w vm.drop_caches=3
echo "Emergency cleanup completed"
EOF

sudo chmod +x /usr/local/bin/emergency-*.sh

# 7. FINAL SYSTEM STATUS
log_info "Reliability enhancement installation completed!"
echo
echo "📊 RELIABILITY FEATURES INSTALLED:"
echo "✅ Hardware watchdog with aggressive monitoring"
echo "✅ Network connectivity watchdog with auto-recovery"  
echo "✅ System health monitor with proactive alerts"
echo "✅ Thermal monitoring with emergency shutdown"
echo "✅ Service auto-restart on failures"
echo "✅ Emergency recovery tools"
echo
echo "📋 NEXT STEPS:"
echo "1. Reboot the Pi to activate hardware watchdog"
echo "2. Monitor logs: sudo journalctl -f"
echo "3. Check health: /usr/local/bin/emergency-cleanup.sh"
echo
log_warn "⚠️  IMPORTANT: A reboot is required to activate all features!"