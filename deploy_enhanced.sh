#!/bin/bash
set -e

# WeatherPi Enhanced Deployment Script
# ==================================

# Configuration
PI_HOST="${PI_HOST:-raspberrypi.local}"
PI_USER="${PI_USER:-pi}"
DEPLOY_PATH="/home/pi/weatherpi"
SERVICE_NAME="weatherpi-proxy-enhanced"
BACKUP_DIR="/home/pi/weatherpi_backup"
LOG_FILE="/tmp/weatherpi_deploy.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

# Check dependencies
check_dependencies() {
    log "Checking local dependencies..."
    
    if ! command -v rsync &> /dev/null; then
        error "rsync is required but not installed"
    fi
    
    if ! command -v ssh &> /dev/null; then
        error "ssh is required but not installed"
    fi
    
    success "Dependencies check passed"
}

# Test SSH connection
test_ssh() {
    log "Testing SSH connection to ${PI_USER}@${PI_HOST}..."
    
    if ! ssh -o ConnectTimeout=10 -o BatchMode=yes "${PI_USER}@${PI_HOST}" "echo 'SSH connection successful'" &> /dev/null; then
        error "Cannot connect to ${PI_USER}@${PI_HOST}. Please check SSH configuration."
    fi
    
    success "SSH connection established"
}

# Create backup
create_backup() {
    log "Creating backup on Pi..."
    
    ssh "${PI_USER}@${PI_HOST}" "
        set -e
        if [ -d '$DEPLOY_PATH' ]; then
            sudo mkdir -p '$BACKUP_DIR'
            sudo tar -czf '$BACKUP_DIR/weatherpi_backup_\$(date +%Y%m%d_%H%M%S).tar.gz' \
                -C '\$(dirname $DEPLOY_PATH)' '\$(basename $DEPLOY_PATH)' || true
            # Keep only last 5 backups
            sudo find '$BACKUP_DIR' -name 'weatherpi_backup_*.tar.gz' -type f | \
                sort -r | tail -n +6 | sudo xargs rm -f || true
        fi
    "
    
    success "Backup created"
}

# Stop services
stop_services() {
    log "Stopping services on Pi..."
    
    ssh "${PI_USER}@${PI_HOST}" "
        set -e
        # Stop old services gracefully
        for service in weatherpi-proxy weatherpi-kiosk chromium-kiosk $SERVICE_NAME; do
            if sudo systemctl is-active --quiet \$service 2>/dev/null; then
                log 'Stopping service: \$service'
                sudo systemctl stop \$service || true
            fi
        done
        
        # Wait for services to stop
        sleep 3
        
        # Kill any remaining processes
        sudo pkill -f 'python.*app.py' || true
        sudo pkill -f 'gunicorn.*app' || true
        sudo pkill -f 'chromium.*kiosk' || true
        
        sleep 2
    "
    
    success "Services stopped"
}

# Deploy files
deploy_files() {
    log "Deploying files to Pi..."
    
    # Create directory structure on Pi
    ssh "${PI_USER}@${PI_HOST}" "
        sudo mkdir -p $DEPLOY_PATH
        sudo mkdir -p /var/log/weatherpi
        sudo mkdir -p /var/cache/weatherpi
        sudo chown -R $PI_USER:$PI_USER $DEPLOY_PATH
        sudo chown -R $PI_USER:$PI_USER /var/log/weatherpi
        sudo chown -R $PI_USER:$PI_USER /var/cache/weatherpi
    "
    
    # Sync files (excluding certain directories and files)
    rsync -avz --delete \
        --exclude='.git/' \
        --exclude='__pycache__/' \
        --exclude='*.pyc' \
        --exclude='.pytest_cache/' \
        --exclude='venv/' \
        --exclude='*.log' \
        --exclude='.DS_Store' \
        --exclude='pi_backup/' \
        --progress \
        ./ "${PI_USER}@${PI_HOST}:${DEPLOY_PATH}/"
    
    success "Files deployed"
}

# Setup Python environment
setup_python_env() {
    log "Setting up Python environment..."
    
    ssh "${PI_USER}@${PI_HOST}" "
        cd $DEPLOY_PATH
        
        # Create virtual environment if it doesn't exist
        if [ ! -d 'venv' ]; then
            python3 -m venv venv
        fi
        
        # Activate and install dependencies
        source venv/bin/activate
        pip install --upgrade pip
        pip install -r requirements.txt
        
        # Install additional production dependencies
        pip install gunicorn setproctitle
    "
    
    success "Python environment setup complete"
}

# Install and configure services
install_services() {
    log "Installing and configuring services..."
    
    ssh "${PI_USER}@${PI_HOST}" "
        cd $DEPLOY_PATH
        
        # Install enhanced proxy service
        sudo cp server/$SERVICE_NAME.service /etc/systemd/system/
        
        # Install other services
        sudo cp pi_configs/*.service /etc/systemd/system/ 2>/dev/null || true
        sudo cp pi_configs/*.timer /etc/systemd/system/ 2>/dev/null || true
        
        # Copy monitor services
        sudo cp monitor/*.service /etc/systemd/system/ 2>/dev/null || true
        sudo cp monitor/*.timer /etc/systemd/system/ 2>/dev/null || true
        
        # Reload systemd
        sudo systemctl daemon-reload
        
        # Enable main services
        sudo systemctl enable $SERVICE_NAME
        sudo systemctl enable weatherpi-kiosk-optimized 2>/dev/null || \
            sudo systemctl enable weatherpi-kiosk 2>/dev/null || true
        
        # Enable monitoring services
        sudo systemctl enable heartbeat.timer 2>/dev/null || true
        sudo systemctl enable kiosk-watchdog.timer 2>/dev/null || true
        sudo systemctl enable status-server 2>/dev/null || true
    "
    
    success "Services installed and enabled"
}

# Configure nginx (if available)
configure_nginx() {
    log "Configuring nginx..."
    
    ssh "${PI_USER}@${PI_HOST}" "
        if command -v nginx &> /dev/null; then
            if [ -f server/nginx.conf ]; then
                sudo cp server/nginx.conf /etc/nginx/sites-available/weatherpi
                sudo ln -sf /etc/nginx/sites-available/weatherpi /etc/nginx/sites-enabled/weatherpi
                sudo rm -f /etc/nginx/sites-enabled/default
                sudo nginx -t && sudo systemctl reload nginx || true
            fi
        fi
    "
    
    success "Nginx configured"
}

# Start services
start_services() {
    log "Starting services..."
    
    ssh "${PI_USER}@${PI_HOST}" "
        # Start main proxy service
        sudo systemctl start $SERVICE_NAME
        
        # Wait for proxy to be ready
        for i in {1..30}; do
            if curl -f http://localhost:8000/api/health &>/dev/null; then
                break
            fi
            sleep 1
        done
        
        # Start kiosk service
        sudo systemctl start weatherpi-kiosk-optimized 2>/dev/null || \
            sudo systemctl start weatherpi-kiosk 2>/dev/null || true
        
        # Start monitoring services
        sudo systemctl start heartbeat.timer 2>/dev/null || true
        sudo systemctl start kiosk-watchdog.timer 2>/dev/null || true
        sudo systemctl start status-server 2>/dev/null || true
    "
    
    success "Services started"
}

# Verify deployment
verify_deployment() {
    log "Verifying deployment..."
    
    ssh "${PI_USER}@${PI_HOST}" "
        # Check service status
        echo 'Service status:'
        sudo systemctl is-active $SERVICE_NAME || echo 'Proxy service not active'
        sudo systemctl is-active weatherpi-kiosk-optimized 2>/dev/null || \
            sudo systemctl is-active weatherpi-kiosk 2>/dev/null || echo 'Kiosk service not active'
        
        # Test health endpoint
        echo 'Testing health endpoint:'
        curl -f http://localhost:8000/api/health || echo 'Health check failed'
        
        # Check logs for errors
        echo 'Recent proxy logs:'
        sudo journalctl -u $SERVICE_NAME --no-pager -n 5 --since '5 minutes ago' || true
    "
    
    success "Deployment verification complete"
}

# Get status
get_status() {
    log "Getting system status..."
    
    ssh "${PI_USER}@${PI_HOST}" "
        echo '=== System Status ==='
        uptime
        echo
        
        echo '=== Service Status ==='
        systemctl is-active $SERVICE_NAME 2>/dev/null || echo '$SERVICE_NAME: inactive'
        systemctl is-active weatherpi-kiosk-optimized 2>/dev/null || \
            systemctl is-active weatherpi-kiosk 2>/dev/null || echo 'Kiosk: inactive'
        systemctl is-active status-server 2>/dev/null || echo 'Status server: inactive'
        echo
        
        echo '=== Health Check ==='
        curl -s http://localhost:8000/api/health | python3 -m json.tool 2>/dev/null || echo 'Health check failed'
        echo
        
        echo '=== Recent Logs ==='
        sudo journalctl -u $SERVICE_NAME --no-pager -n 10 --since '10 minutes ago' || true
    "
}

# Main deployment function
main() {
    log "Starting enhanced WeatherPi deployment..."
    
    case "${1:-deploy}" in
        "deploy")
            check_dependencies
            test_ssh
            create_backup
            stop_services
            deploy_files
            setup_python_env
            install_services
            configure_nginx
            start_services
            verify_deployment
            success "Deployment completed successfully!"
            ;;
        "status")
            test_ssh
            get_status
            ;;
        "restart")
            test_ssh
            stop_services
            start_services
            verify_deployment
            ;;
        "logs")
            ssh "${PI_USER}@${PI_HOST}" "sudo journalctl -u $SERVICE_NAME -f"
            ;;
        *)
            echo "Usage: $0 [deploy|status|restart|logs]"
            echo "  deploy  - Full deployment (default)"
            echo "  status  - Show system status"
            echo "  restart - Restart services"
            echo "  logs    - Show live logs"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"