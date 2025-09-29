#!/bin/bash#!/bin/bash

# WeatherPi Robust Kiosk Startup Script

# WeatherPi Robust Startup Script# Handles all timing issues and dependencies properly

# Ensures Firefox starts reliably in kiosk mode

set -e

export DISPLAY=:0

export XAUTHORITY=/home/cagdas/.Xauthority# Logging

LOG_FILE="/var/log/weatherpi-startup.log"

echo "Starting WeatherPi kiosk at $(date)"exec 1> >(tee -a "$LOG_FILE")

exec 2>&1

# Wait for X11 to be ready

while ! xset q &>/dev/null; dolog_message() {

    echo "Waiting for X11..."    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"

    sleep 2}

done

log_message "🚀 WeatherPi Kiosk Startup Script Starting"

# Kill any existing Firefox processes

pkill firefox-esr 2>/dev/null || true# Wait for essential services with timeout

sleep 2wait_for_service() {

    local service=$1

# Wait for network    local timeout=${2:-60}

while ! ping -c 1 google.com &>/dev/null; do    local count=0

    echo "Waiting for network..."    

    sleep 5    log_message "⏳ Waiting for $service service..."

done    

    while [ $count -lt $timeout ]; do

# Start calendar fetcher in background        if systemctl is-active --quiet "$service"; then

cd /var/www/html && python3 /var/www/html/calendar_fetcher.py &            log_message "✅ $service is active"

            return 0

# Wait a moment for calendar to load        fi

sleep 3        sleep 1

        ((count++))

# Start Firefox in kiosk mode    done

exec firefox-esr --kiosk --no-remote --new-instance --disable-session-restore http://127.0.0.1/weather.html    
    log_message "❌ Timeout waiting for $service after ${timeout}s"
    return 1
}

# Wait for network connectivity
wait_for_network() {
    local timeout=${1:-60}
    local count=0
    
    log_message "🌐 Waiting for network connectivity..."
    
    while [ $count -lt $timeout ]; do
        if ping -c 1 -W 5 localhost >/dev/null 2>&1; then
            log_message "✅ Network connectivity confirmed"
            return 0
        fi
        sleep 2
        ((count += 2))
    done
    
    log_message "❌ Network timeout after ${timeout}s"
    return 1
}

# Wait for web server
wait_for_webserver() {
    local timeout=${1:-60}
    local count=0
    
    log_message "🌐 Waiting for web server..."
    
    while [ $count -lt $timeout ]; do
        if curl -f -s http://localhost/weather.html >/dev/null 2>&1; then
            log_message "✅ Web server responding"
            return 0
        fi
        sleep 2
        ((count += 2))
    done
    
    log_message "❌ Web server timeout after ${timeout}s"
    return 1
}

# Wait for X11 display
wait_for_display() {
    local timeout=${1:-60}
    local count=0
    
    log_message "🖥️ Waiting for X11 display..."
    
    while [ $count -lt $timeout ]; do
        if [ -n "$DISPLAY" ] && xset q >/dev/null 2>&1; then
            log_message "✅ X11 display available"
            return 0
        fi
        sleep 2
        ((count += 2))
    done
    
    log_message "❌ X11 display timeout after ${timeout}s"
    return 1
}

# Kill any existing Firefox instances
cleanup_firefox() {
    log_message "🧹 Cleaning up existing Firefox processes..."
    pkill -f firefox || true
    sleep 3
}

# Setup X11 environment
setup_display() {
    log_message "🖥️ Setting up display environment..."
    
    # Export display
    export DISPLAY=:0
    
    # Setup Xauthority
    if [ ! -f "/home/cagdas/.Xauthority" ]; then
        touch /home/cagdas/.Xauthority
        chown cagdas:cagdas /home/cagdas/.Xauthority
    fi
    export XAUTHORITY=/home/cagdas/.Xauthority
    
    # Disable screen blanking
    xset s off 2>/dev/null || true
    xset -dpms 2>/dev/null || true
    xset s noblank 2>/dev/null || true
    
    log_message "✅ Display environment configured"
}

# Start Firefox with robust error handling
start_firefox() {
    log_message "🦊 Starting Firefox in kiosk mode..."
    
    # Firefox startup options
    FIREFOX_OPTS=(
        --kiosk
        --no-sandbox
        --no-first-run
        --disable-infobars
        --disable-features=TranslateUI
        --disable-web-security
        --disable-extensions
        --no-default-browser-check
        --autoplay-policy=no-user-gesture-required
        --disable-background-timer-throttling
        --disable-backgrounding-occluded-windows
        --disable-renderer-backgrounding
        http://localhost/weather.html
    )
    
    # Start Firefox
    exec /usr/bin/firefox-esr "${FIREFOX_OPTS[@]}"
}

# Main execution flow
main() {
    log_message "🚀 Starting WeatherPi Kiosk..."
    
    # Phase 1: Wait for system services
    log_message "📋 Phase 1: System Services"
    wait_for_service "graphical.target" 30
    wait_for_service "lightdm" 30
    wait_for_service "nginx" 30
    
    # Phase 2: Additional startup delay
    log_message "📋 Phase 2: Additional Startup Delay"
    log_message "⏳ Waiting additional 15 seconds for system stabilization..."
    sleep 15
    
    # Phase 3: Network and web server
    log_message "📋 Phase 3: Network & Web Server"
    wait_for_network 30
    wait_for_webserver 30
    
    # Phase 4: Display setup
    log_message "📋 Phase 4: Display Setup"
    wait_for_display 30
    setup_display
    
    # Phase 5: Firefox cleanup and startup
    log_message "📋 Phase 5: Browser Launch"
    cleanup_firefox
    
    # Additional delay before Firefox launch
    log_message "⏳ Final 5-second delay before Firefox launch..."
    sleep 5
    
    # Launch Firefox
    start_firefox
}

# Error handling
trap 'log_message "❌ Startup script failed"; exit 1' ERR

# Run main function
main