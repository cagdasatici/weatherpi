#!/bin/bash
# WeatherPi Robust Kiosk Startup Script
# Handles all timing issues and dependencies properly

set -e

# Logging
LOG_FILE="/var/log/weatherpi-startup.log"
exec 1> >(tee -a "$LOG_FILE")
exec 2>&1

log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log_message "🚀 WeatherPi Kiosk Startup Script Starting"

# Wait for essential services with timeout
wait_for_service() {
    local service=$1
    local timeout=${2:-60}
    local count=0
    
    log_message "⏳ Waiting for $service service..."
    
    while [ $count -lt $timeout ]; do
        if systemctl is-active --quiet "$service"; then
            log_message "✅ $service is active"
            return 0
        fi
        sleep 1
        ((count++))
    done
    
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