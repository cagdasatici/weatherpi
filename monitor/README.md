Monitoring helpers

Files:
- heartbeat.py - posts small JSON heartbeat to MONITOR_URL if set; otherwise prints payload (good for local testing).
- kiosk_watchdog.py - checks the local kiosk page and restarts nginx/chromium services if unreachable.

Suggested systemd units (copy to /etc/systemd/system on the Pi):

[Unit]
Description=WeatherPi Heartbeat

[Service]
Type=oneshot
Environment=MONITOR_URL=https://your-monitor.example.com/heartbeat
ExecStart=/usr/bin/python3 /opt/weatherpi/monitor/heartbeat.py

[Install]
WantedBy=multi-user.target

And timer:

[Unit]
Description=Run heartbeat every 5 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target

Kiosk watchdog service:

[Unit]
Description=WeatherPi Kiosk Watchdog

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /opt/weatherpi/monitor/kiosk_watchdog.py

[Install]
WantedBy=multi-user.target

And timer every 2 minutes:

[Timer]
OnBootSec=3min
OnUnitActiveSec=2min

