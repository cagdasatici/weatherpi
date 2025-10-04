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

URL = os.environ.get('KIOSK_URL', 'http://127.0.0.1/weather.html')
TIMEOUT = int(os.environ.get('KIOSK_TIMEOUT', '6'))
DISK_PATH = os.environ.get('DISK_PATH', '/')
DISK_WARN_PCT = float(os.environ.get('DISK_WARN_PCT', '95'))
MEM_WARN_MB = int(os.environ.get('MEM_WARN_MB', '100'))
LOAD_WARN = float(os.environ.get('LOAD_WARN', '3.0'))


def page_ok():
    try:
        with urllib.request.urlopen(URL, timeout=TIMEOUT) as r:
            return 200 <= r.getcode() < 300
    except Exception:
        return False


def disk_high(path, pct_threshold):
    try:
        import shutil
        total, used, free = shutil.disk_usage(path)
        pct = used / total * 100
        return pct >= pct_threshold, round(pct, 1)
    except Exception:
        return False, None


def mem_low(mb_threshold):
    try:
        with open('/proc/meminfo', 'r') as f:
            info = {line.split()[0].rstrip(':'): int(line.split()[1]) for line in f}
        avail_kb = info.get('MemAvailable', info.get('MemFree', 0))
        avail_mb = avail_kb // 1024
        return avail_mb <= mb_threshold, avail_mb
    except Exception:
        return False, None


def load_high(threshold):
    try:
        load1, load5, load15 = tuple(map(float, os.getloadavg()))
        return load1 >= threshold, load1
    except Exception:
        return False, None


def restart_service(svc):
    print('Restarting', svc)
    subprocess.run(['sudo', 'systemctl', 'restart', svc])


def main():
    if page_ok():
        print('kiosk page OK')
        return 0

    # Gather diagnostics
    disk_bad, disk_pct = disk_high(DISK_PATH, DISK_WARN_PCT)
    mem_bad, avail_mb = mem_low(MEM_WARN_MB)
    load_bad, load1 = load_high(LOAD_WARN)

    print('kiosk page not reachable; diagnostics: disk_pct=%s mem_avail_mb=%s load1=%s' % (disk_pct, avail_mb, load1))

    # If system resources are critically low, log and avoid restart loops
    if disk_bad or mem_bad or load_bad:
        print('Resource constraints detected; skipping automated restart to avoid thrash')
        return 2

    # Restart services (local self-heal)
    print('Restarting services (nginx + chromium)')
    restart_service('nginx')
    time.sleep(2)
    restart_service('chromium-kiosk.service')
    # Small cooldown to prevent immediate repeated restarts
    time.sleep(4)
    return 1

if __name__ == '__main__':
    sys.exit(main())
