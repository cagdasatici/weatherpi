# Pi Configuration Files

This directory contains all the configuration files needed to set up the WeatherPi kiosk on a Raspberry Pi.

## Files:

### `weatherpi-kiosk.service`
- **Purpose**: Systemd service that auto-starts Firefox in kiosk mode
- **Location**: `/etc/systemd/system/weatherpi-kiosk.service`
- **Key features**: Waits for graphical target, runs as cagdas user, auto-restarts

### `openbox-autostart` 
- **Purpose**: Openbox window manager autostart script
- **Location**: `~/.config/openbox/autostart`
- **Features**: Power management, Firefox kiosk launch, monitoring loop

### `weather-kiosk.desktop`
- **Purpose**: Desktop environment autostart entry
- **Location**: `~/.config/autostart/weather-kiosk.desktop`
- **Backup method**: Works with various desktop environments

### `.xinitrc`
- **Purpose**: X11 initialization script
- **Location**: `~/.xinitrc`
- **Function**: Starts openbox-session

### `start_weather.sh`
- **Purpose**: Manual Firefox launcher script
- **Usage**: Emergency/manual launch method
- **Command**: `./pi_configs/start_weather.sh`

## Setup:

1. **Automated**: Run `./setup_pi_kiosk.sh` (recommended)
2. **Manual**: Copy files to their respective locations
3. **Quick deploy**: Use `./fast_deploy.sh` for updates

## Troubleshooting:

- **Service status**: `sudo systemctl status weatherpi-kiosk.service`
- **Manual start**: `firefox-esr --kiosk http://localhost/weather.html`
- **Check display**: `echo $DISPLAY` (should be `:0`)
- **Web test**: `curl http://localhost/weather.html`

## Multiple Autostart Methods:

We use multiple autostart methods because Pi desktop environments vary:
1. **Systemd service** (primary) - Most reliable
2. **Desktop autostart** - Works with most DEs
3. **Openbox autostart** - For minimal setups
4. **Manual script** - Emergency backup
