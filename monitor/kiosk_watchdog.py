#!/usr/bin/env python3
"""Simple watchdog: checks the kiosk page locally and restarts services if the page is unreachable.
- Checks http://127.0.0.1/weather.html
- If the page returns non-200 or times out, it restarts chromium-kiosk and nginx
- Intended for systemd timer every 1-5 minutes
"""
import sys
import time
import urllib.request
import subprocess

URL = 'http://127.0.0.1/weather.html'
TIMEOUT = 6


def page_ok():
    try:
        with urllib.request.urlopen(URL, timeout=TIMEOUT) as r:
            return 200 <= r.getcode() < 300
    except Exception:
        return False


def restart_service(svc):
    print('Restarting', svc)
    subprocess.run(['sudo', 'systemctl', 'restart', svc])


def main():
    if page_ok():
        print('kiosk page OK')
        return 0
    print('kiosk page not reachable, restarting services')
    restart_service('nginx')
    time.sleep(2)
    restart_service('chromium-kiosk.service')
    return 1

if __name__ == '__main__':
    sys.exit(main())
