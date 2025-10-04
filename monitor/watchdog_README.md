Watchdog Daemon

This is a long-running watchdog intended to be run as a systemd service (`watchdog.service`). It performs repeated health checks and attempts local self-heal, with escalation to an external MONITOR_URL.

Configuration via environment variables (examples):

CHECK_INTERVAL=30
SERVICE_NAMES="nginx,chromium-kiosk.service"
PROCESS_NAMES="chromium"
RESTART_THRESHOLD=2
ESCALATION_THRESHOLD=3
MONITOR_URL=https://example/ping
ALLOW_REBOOT=false

Install on the Pi:

sudo cp /opt/weatherpi/monitor/watchdog.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now watchdog.service
