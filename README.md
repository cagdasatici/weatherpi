# WeatherPi - Raspberry Pi Weather & Calendar Kiosk

A touch-friendly weather and calendar display for Raspberry Pi 3A+ with Waveshare 4.3" screen, designed for kiosk mode operation.

## Features

- **Weather Display**: Current conditions, 5-day forecast, hourly temperature chart
- **Family Calendar**: iCloud calendar integration with touch navigation  
- **Kiosk Mode**: Full-screen operation with automatic startup
- **Touch Optimized**: Large buttons and smooth navigation for touchscreen use
- **Auto-Return**: Calendar view automatically returns to weather after 15 seconds
- **Smart Precipitation**: Chart only shows rain bars when meaningful precipitation (>0.5mm) is forecast

## Main Files

- `weather.html` - Main weather display with calendar navigation
- `calendar.html` - Calendar view with family events
- `calendar_fetcher.py` - iCloud calendar data fetcher
- `weatherpi-kiosk-auto.service` - Systemd service for auto-startup
- `weatherpi_robust_startup.sh` - Startup script for kiosk mode

## Installation

1. Clone repository to Pi
2. Run `setup_pi_kiosk.sh` for initial setup
3. Configure calendar credentials in `calendar_config.py`
4. Enable auto-startup: `sudo systemctl enable weatherpi-kiosk-auto`

## Usage

- **Touch calendar icon** on weather page to view events
- **15-second auto-return** from calendar to weather
- **Touch-optimized** interface designed for Pi touchscreen
- **Automatic startup** on boot into kiosk mode

## System Requirements

- Raspberry Pi 3A+ (or compatible)
- Waveshare 4.3" touchscreen display
- Network connection for weather and calendar data
