#!/bin/bash
"""
Calendar Setup Script for WeatherPi
- Installs Python dependencies
- Creates configuration files
- Sets up systemd service
- Configures web server permissions
"""

set -e

echo "=== WeatherPi Calendar Integration Setup ==="
echo

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo -e "${RED}This script should not be run as root${NC}"
   echo "Run as pi user: ./setup_calendar.sh"
   exit 1
fi

echo -e "${YELLOW}Step 1: Installing Python dependencies...${NC}"
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv

# Create virtual environment for calendar fetcher
if [ ! -d "/home/pi/calendar-env" ]; then
    python3 -m venv /home/pi/calendar-env
fi

# Install required Python packages
/home/pi/calendar-env/bin/pip install requests lxml

echo -e "${GREEN}✓ Python dependencies installed${NC}"
echo

echo -e "${YELLOW}Step 2: Setting up calendar configuration...${NC}"

# Copy calendar scripts to proper location
sudo mkdir -p /opt/weatherpi
sudo cp calendar_config.py calendar_fetcher.py /opt/weatherpi/
sudo chown pi:pi /opt/weatherpi/*.py
sudo chmod +x /opt/weatherpi/calendar_fetcher.py

# Create initial configuration (user will need to edit this)
python3 /opt/weatherpi/calendar_config.py

echo -e "${GREEN}✓ Calendar scripts installed to /opt/weatherpi/${NC}"
echo

echo -e "${YELLOW}Step 3: Creating systemd service...${NC}"

# Create systemd service file
sudo tee /etc/systemd/system/calendar-fetcher.service > /dev/null <<EOF
[Unit]
Description=WeatherPi Calendar Fetcher
After=network.target

[Service]
Type=oneshot
User=pi
WorkingDirectory=/opt/weatherpi
Environment=PATH=/home/pi/calendar-env/bin
ExecStart=/home/pi/calendar-env/bin/python3 /opt/weatherpi/calendar_fetcher.py
StandardOutput=journal
StandardError=journal
EOF

# Create systemd timer for regular updates (every 15 minutes)
sudo tee /etc/systemd/system/calendar-fetcher.timer > /dev/null <<EOF
[Unit]
Description=Run WeatherPi Calendar Fetcher every 15 minutes
Requires=calendar-fetcher.service

[Timer]
OnBootSec=2min
OnUnitActiveSec=15min

[Install]
WantedBy=timers.target
EOF

# Enable and start the timer
sudo systemctl daemon-reload
sudo systemctl enable calendar-fetcher.timer
sudo systemctl start calendar-fetcher.timer

echo -e "${GREEN}✓ Systemd service and timer created${NC}"
echo

echo -e "${YELLOW}Step 4: Setting up web server permissions...${NC}"

# Ensure calendar data directory exists and is writable
sudo mkdir -p /var/www/html
sudo chown www-data:www-data /var/www/html
sudo chmod 755 /var/www/html

# Allow pi user to write calendar data
sudo usermod -a -G www-data pi

echo -e "${GREEN}✓ Web server permissions configured${NC}"
echo

echo -e "${YELLOW}Step 5: Deploying calendar HTML...${NC}"

# Copy calendar.html to web directory
sudo cp calendar.html /var/www/html/
sudo chown www-data:www-data /var/www/html/calendar.html

echo -e "${GREEN}✓ Calendar page deployed${NC}"
echo

echo -e "${GREEN}=== Setup Complete! ===${NC}"
echo
echo -e "${YELLOW}NEXT STEPS:${NC}"
echo "1. Edit calendar credentials:"
echo "   nano /home/pi/calendar_credentials.json"
echo
echo "2. Add your iCloud account details:"
echo "   - username: your@icloud.com"
echo "   - password: app-specific password (recommended)"
echo
echo "3. Test the calendar fetcher:"
echo "   sudo systemctl start calendar-fetcher.service"
echo "   sudo journalctl -u calendar-fetcher.service -f"
echo
echo "4. Check calendar data:"
echo "   cat /var/www/html/calendar_events.json"
echo
echo -e "${YELLOW}To create App-Specific Passwords:${NC}"
echo "1. Go to https://appleid.apple.com"
echo "2. Sign In > App-Specific Passwords > Generate Password"
echo "3. Use this password instead of your main iCloud password"
echo
echo -e "${GREEN}Calendar integration is now ready!${NC}"