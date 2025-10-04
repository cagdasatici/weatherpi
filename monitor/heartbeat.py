#!/usr/bin/env python3
"""Simple heartbeat monitor that POSTs to a user-configurable external monitoring endpoint.
Intended to be run from cron or systemd timer on the Pi.

Behavior:
- Reads MONITOR_URL from env or default to stdout-only dry-run.
- Sends a JSON payload with hostname, timestamp, and service statuses (nginx/chromium)
- Exits with 0 on success, non-zero on error (systemd will log failures)
"""
import os
import sys
import json
import socket
from datetime import datetime
import subprocess

MONITOR_URL = os.environ.get('MONITOR_URL')
TIMEOUT = int(os.environ.get('MONITOR_TIMEOUT', '6'))

HOSTNAME = socket.gethostname()


def check_service(name):
    try:
        subprocess.run(['systemctl', 'is-active', '--quiet', name], check=True)
        return 'active'
    except subprocess.CalledProcessError:
        return 'inactive'


def main():
    payload = {
        'hostname': HOSTNAME,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'services': {
            'nginx': check_service('nginx'),
            'chromium-kiosk': check_service('chromium-kiosk.service')
        }
    }

    if not MONITOR_URL:
        print(json.dumps(payload, indent=2))
        return 0

    try:
        import urllib.request as request
        req = request.Request(MONITOR_URL, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        with request.urlopen(req, timeout=TIMEOUT) as resp:
            code = resp.getcode()
            if 200 <= code < 300:
                print('heartbeat OK', code)
                return 0
            else:
                print('heartbeat bad code', code)
                return 2
    except Exception as e:
        print('heartbeat error', e)
        return 3


if __name__ == '__main__':
    sys.exit(main())
