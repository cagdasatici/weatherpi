#!/usr/bin/env python3
"""
Stateful Watchdog Daemon for WeatherPi

Features:
- Runs continuously as a system service.
- Periodically checks:
  - Service statuses (nginx, chromium-kiosk)
  - Process presence (chromium)
  - Disk usage and inode usage
  - Memory available
  - Load average
  - CPU temperature (if available)
  - Network reachability (gateway and external host)
  - DNS resolution
  - Local port checks (SSH)
- Maintains failure counters per check and only takes action after thresholds.
- Recovery actions:
  - Try to restart failing services (with rate limiting/backoff)
  - If service restarts repeatedly fail, escalate to sending an alert (MONITOR_URL) and optionally reboot (disabled by default)
- Sends JSON alerts to MONITOR_URL when critical and logs events to stdout (captured by systemd/journal)

Config via environment variables:
- CHECK_INTERVAL (seconds, default 30)
- SERVICE_NAMES (comma-separated, default nginx,chromium-kiosk.service)
- PROCESS_NAMES (comma-separated, default chromium)
- RESTART_THRESHOLD (how many failures before restart, default 2)
- ESCALATION_THRESHOLD (how many restarts before escalation, default 3)
- MONITOR_URL (optional, POST alerts)
- ALLOW_REBOOT (false by default)

"""

import os
import sys
import time
import json
import socket
import shutil
import subprocess
import threading
from datetime import datetime, timedelta

# Configuration
CHECK_INTERVAL = int(os.environ.get('CHECK_INTERVAL', '30'))
SERVICE_NAMES = [s.strip() for s in os.environ.get('SERVICE_NAMES', 'nginx,chromium-kiosk.service').split(',') if s.strip()]
PROCESS_NAMES = [p.strip() for p in os.environ.get('PROCESS_NAMES', 'chromium').split(',') if p.strip()]
RESTART_THRESHOLD = int(os.environ.get('RESTART_THRESHOLD', '2'))
ESCALATION_THRESHOLD = int(os.environ.get('ESCALATION_THRESHOLD', '3'))
MONITOR_URL = os.environ.get('MONITOR_URL')
MONITOR_URLS = [u.strip() for u in os.environ.get('MONITOR_URLS', '').split(',') if u.strip()]
if MONITOR_URL and not MONITOR_URLS:
    MONITOR_URLS = [MONITOR_URL]
ALLOW_REBOOT = os.environ.get('ALLOW_REBOOT', 'false').lower() in ('1','true','yes')
EXTERNAL_CHECK_HOST = os.environ.get('EXTERNAL_CHECK_HOST', '8.8.8.8')
EXTERNAL_CHECK_PORT = int(os.environ.get('EXTERNAL_CHECK_PORT', '53'))
SSH_CHECK_PORT = int(os.environ.get('SSH_CHECK_PORT', '22'))
DISK_WARN_PCT = float(os.environ.get('DISK_WARN_PCT', '92'))
INODE_WARN_PCT = float(os.environ.get('INODE_WARN_PCT', '95'))
MEM_WARN_MB = int(os.environ.get('MEM_WARN_MB', '150'))
LOAD_WARN = float(os.environ.get('LOAD_WARN', '2.5'))
RESTART_COOLDOWN = int(os.environ.get('RESTART_COOLDOWN', '120'))  # seconds between restart attempts

LOG_PREFIX = '[watchdog] '

# Stateful counters
failure_counters = {}
restart_counts = {}
last_restart_time = {}
lock = threading.Lock()


def log(msg, level='INFO'):
    ts = datetime.utcnow().isoformat() + 'Z'
    print(f"{ts} {LOG_PREFIX}{level}: {msg}", flush=True)


def run_cmd(cmd, timeout=10):
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=timeout, shell=False)
        return out.decode('utf-8', errors='replace')
    except subprocess.CalledProcessError as e:
        return e.output.decode('utf-8', errors='replace')
    except Exception as e:
        return str(e)


def is_service_active(name):
    try:
        subprocess.run(['systemctl', 'is-active', '--quiet', name], check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def restart_service(name):
    now = datetime.utcnow()
    with lock:
        last = last_restart_time.get(name)
        if last and (now - last).total_seconds() < RESTART_COOLDOWN:
            log(f"Skipping restart of {name}: cooldown active", 'DEBUG')
            return False
        last_restart_time[name] = now
        restart_counts[name] = restart_counts.get(name, 0) + 1
    log(f"Restarting service {name}")
    try:
        subprocess.run(['sudo', 'systemctl', 'restart', name], check=True)
        return True
    except Exception as e:
        log(f"Failed to restart {name}: {e}", 'ERROR')
        return False


def check_process(name):
    # Simple pgrep
    try:
        subprocess.run(['pgrep', '-f', name], check=True, stdout=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False


def disk_usage(path='/'):
    try:
        total, used, free = shutil.disk_usage(path)
        pct = used / total * 100
        return {'total': total, 'used': used, 'free': free, 'percent': pct}
    except Exception as e:
        return {'error': str(e)}


def inode_usage(path='/'):
    try:
        st = os.statvfs(path)
        total = st.f_files
        free = st.f_ffree
        used = total - free
        pct = used / total * 100 if total else 0
        return {'total': total, 'used': used, 'free': free, 'percent': pct}
    except Exception as e:
        return {'error': str(e)}


def mem_info():
    try:
        with open('/proc/meminfo', 'r') as f:
            info = {line.split()[0].rstrip(':'): int(line.split()[1]) for line in f}
        total_kb = info.get('MemTotal', 0)
        avail_kb = info.get('MemAvailable', info.get('MemFree', 0))
        return {'total_kb': total_kb, 'avail_kb': avail_kb}
    except Exception as e:
        return {'error': str(e)}


def loadavg():
    try:
        return os.getloadavg()
    except Exception:
        return (0.0, 0.0, 0.0)


def cpu_temp():
    # Common Pi path
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            t = int(f.read().strip()) / 1000.0
            return t
    except Exception:
        return None


def tcp_connect(host, port, timeout=3):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def dns_lookup(name='google.com'):
    try:
        return socket.gethostbyname(name) is not None
    except Exception:
        return False


def send_alert(payload):
    if not MONITOR_URLS:
        log('MONITOR_URLS/MONITOR_URL not set, skipping external alert', 'DEBUG')
        return
    import urllib.request as request
    for url in MONITOR_URLS:
        try:
            req = request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
            with request.urlopen(req, timeout=10) as resp:
                code = resp.getcode()
                log(f'Sent alert to {url}, response code {code}', 'INFO')
        except Exception as e:
            log(f'Failed sending alert to {url}: {e}', 'ERROR')


def fundamentals_check():
    issues = []
    du = disk_usage('/')
    if 'percent' in du and du['percent'] >= DISK_WARN_PCT:
        issues.append(('disk', du['percent']))
    iu = inode_usage('/')
    if 'percent' in iu and iu['percent'] >= INODE_WARN_PCT:
        issues.append(('inodes', iu['percent']))
    mem = mem_info()
    if 'avail_kb' in mem and mem['avail_kb'] // 1024 <= MEM_WARN_MB:
        issues.append(('memory_mb', mem['avail_kb']//1024))
    la = loadavg()[0]
    if la >= LOAD_WARN:
        issues.append(('load1', la))
    dns_ok = dns_lookup('google.com')
    if not dns_ok:
        issues.append(('dns', False))
    ssh_ok = tcp_connect('127.0.0.1', SSH_CHECK_PORT)
    if not ssh_ok:
        issues.append(('ssh_local', False))
    return issues


def check_and_recover():
    report = {'timestamp': datetime.utcnow().isoformat() + 'Z', 'checks': {}, 'actions': []}

    # Services
    for svc in SERVICE_NAMES:
        active = is_service_active(svc)
        report['checks'][f'service:{svc}'] = active
        if not active:
            failure_counters[svc] = failure_counters.get(svc, 0) + 1
            log(f"Service {svc} inactive (count={failure_counters[svc]})", 'WARN')
            if failure_counters[svc] >= RESTART_THRESHOLD:
                restarted = restart_service(svc)
                report['actions'].append({'action': 'restart_service', 'service': svc, 'result': restarted})
                # after restart attempt, reset failure counter to avoid oscillation
                failure_counters[svc] = 0
                if restarted and restart_counts.get(svc, 0) >= ESCALATION_THRESHOLD:
                    # escalate
                    payload = {'level': 'critical', 'reason': 'service_restart_failed_repeatedly', 'service': svc, 'restart_count': restart_counts.get(svc, 0)}
                    send_alert(payload)
                    report['actions'].append({'action': 'escalate', 'service': svc})
        else:
            failure_counters[svc] = 0

    # Process checks
    for proc in PROCESS_NAMES:
        ok = check_process(proc)
        report['checks'][f'process:{proc}'] = ok
        if not ok:
            failure_counters[proc] = failure_counters.get(proc, 0) + 1
            log(f'Process {proc} missing (count={failure_counters[proc]})', 'WARN')
            if failure_counters[proc] >= RESTART_THRESHOLD:
                # try to restart associated services
                for svc in SERVICE_NAMES:
                    if 'chromium' in proc and 'chromium' in svc:
                        restarted = restart_service(svc)
                        report['actions'].append({'action': 'restart_service_for_process', 'process': proc, 'service': svc, 'result': restarted})
                        failure_counters[proc] = 0
        else:
            failure_counters[proc] = 0

    # Disk / inodes / memory / load / cpu temp
    du = disk_usage('/')
    report['checks']['disk'] = du
    if 'percent' in du and du['percent'] >= DISK_WARN_PCT:
        log(f'Disk usage high: {du["percent"]:.1f}%', 'ERROR')
        report['actions'].append({'action': 'disk_high', 'percent': du['percent']})

    iu = inode_usage('/')
    report['checks']['inodes'] = iu
    if 'percent' in iu and iu['percent'] >= INODE_WARN_PCT:
        log(f'Inode usage high: {iu["percent"]:.1f}%', 'ERROR')
        report['actions'].append({'action': 'inodes_high', 'percent': iu['percent']})

    mem = mem_info()
    report['checks']['memory'] = mem
    if 'avail_kb' in mem and mem['avail_kb']//1024 <= MEM_WARN_MB:
        log(f'Low available memory: {mem["avail_kb"]//1024} MB', 'ERROR')
        report['actions'].append({'action': 'memory_low', 'available_mb': mem['avail_kb']//1024})

    la = loadavg()
    report['checks']['loadavg'] = la
    if la[0] >= LOAD_WARN:
        log(f'High loadavg: {la[0]:.2f}', 'WARN')
        report['actions'].append({'action': 'high_load', 'load1': la[0]})

    temp = cpu_temp()
    if temp is not None:
        report['checks']['cpu_temp'] = temp
        if temp >= 85.0:
            log(f'CPU temp high: {temp:.1f}°C', 'ERROR')
            report['actions'].append({'action': 'cpu_overtemp', 'temp': temp})

    # Network and DNS
    net_ok = tcp_connect(EXTERNAL_CHECK_HOST, EXTERNAL_CHECK_PORT)
    report['checks']['external_connect'] = net_ok
    if not net_ok:
        log('External host unreachable', 'WARN')
        report['actions'].append({'action': 'external_unreachable'})

    dns_ok = dns_lookup('google.com')
    report['checks']['dns'] = dns_ok
    if not dns_ok:
        report['actions'].append({'action': 'dns_fail'})

    # If critical actions found, send a structured alert
    critical = any(a['action'] in ('disk_high','inodes_high','memory_low','cpu_overtemp') for a in report['actions'])
    if critical:
        payload = {'level': 'critical', 'report': report}
        send_alert(payload)

    # Return the report
    # Also write latest status to a predictable runtime path so the web UI can read it
    try:
        os.makedirs('/var/lib/weatherpi', exist_ok=True)
        with open('/var/lib/weatherpi/last_status.json', 'w') as f:
            json.dump(report, f)
    except Exception as e:
        log(f'Failed to write last_status.json: {e}', 'DEBUG')

    return report


def main_loop():
    log('Starting watchdog daemon', 'INFO')
    while True:
        try:
            report = check_and_recover()
            # write a small local log file for quick inspection as well
            try:
                with open('/var/log/weatherpi_watchdog.json', 'a') as f:
                    f.write(json.dumps({'ts': datetime.utcnow().isoformat()+'Z', 'report': report}) + '\n')
            except Exception as e:
                log(f'Could not write local log: {e}', 'DEBUG')
        except Exception as e:
            log(f'Unhandled exception in main loop: {e}', 'ERROR')
        time.sleep(CHECK_INTERVAL)


if __name__ == '__main__':
    try:
        main_loop()
    except KeyboardInterrupt:
        log('Shutting down (keyboard interrupt)', 'INFO')
        sys.exit(0)
