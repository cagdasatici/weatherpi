# WeatherPi Restore Guide

## Quick Setup on Fresh Pi
```bash
# 1. Install packages
sudo apt update && sudo apt install -y nginx firefox-esr openbox xinit x11-xserver-utils

# 2. Enable services  
sudo systemctl enable nginx

# 3. Deploy from this repo
./fast_deploy.sh

# 4. Restore configs from backup (if needed)
cd pi_backup
tar xzf weatherpi_config_backup_*.tar.gz
sudo cp -r etc/* /etc/
cp -r home/cagdas/.* ~/
```

## What's Backed Up
- `/etc/systemd/system/weather-kiosk.service` - Main service
- `/home/cagdas/.xinitrc` - X11 startup 
- `/home/cagdas/.config/openbox/autostart` - Firefox kiosk launcher
- `/var/www/html/weather.html` - Weather interface
- `/etc/nginx/sites-available/default` - Web server config

## Key Commands
- `sudo systemctl status weather-kiosk.service` - Check service
- `sudo systemctl restart weather-kiosk.service` - Restart display
- `./fast_deploy.sh` - Deploy updates