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
import shutil
import subprocess
from datetime import datetime
import subprocess

MONITOR_URL = os.environ.get('MONITOR_URL')
TIMEOUT = int(os.environ.get('MONITOR_TIMEOUT', '6'))
PING_HOST = os.environ.get('PING_HOST', '8.8.8.8')
DISK_PATH = os.environ.get('DISK_PATH', '/')
DISK_WARN_PCT = float(os.environ.get('DISK_WARN_PCT', '90'))
MEM_WARN_MB = int(os.environ.get('MEM_WARN_MB', '150'))
LOAD_WARN = float(os.environ.get('LOAD_WARN', '2.0'))

HOSTNAME = socket.gethostname()


def check_service(name):
    try:
        subprocess.run(['systemctl', 'is-active', '--quiet', name], check=True)
        return 'active'
    except subprocess.CalledProcessError:
        return 'inactive'


def disk_usage(path):
    try:
        total, used, free = shutil.disk_usage(path)
        pct = round(used / total * 100, 1)
        return {'total': total, 'used': used, 'free': free, 'percent': pct}
    except Exception as e:
        return {'error': str(e)}


def mem_info():
    # Read /proc/meminfo for Linux systems
    info = {}
    try:
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                parts = line.split()
                key = parts[0].rstrip(':')
                val = int(parts[1])
                info[key] = val
        # values in kB
        mem_total_kb = info.get('MemTotal', 0)
        mem_avail_kb = info.get('MemAvailable', info.get('MemFree', 0))
        return {'total_kb': mem_total_kb, 'available_kb': mem_avail_kb}
    except Exception as e:
        return {'error': str(e)}


def is_port_open(host, port, timeout=3):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def main():
    payload = {
        'hostname': HOSTNAME,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'services': {
            'nginx': check_service('nginx'),
            'chromium-kiosk': check_service('chromium-kiosk.service')
        },
        'disk': disk_usage(DISK_PATH),
        'memory': mem_info(),
        'loadavg': os.getloadavg(),
        'network': {
            'ping_host': PING_HOST,
            'dns_ok': is_port_open('8.8.8.8', 53),
            'ssh_ok': is_port_open('127.0.0.1', 22)
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
