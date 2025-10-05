#!/usr/bin/env python3
"""Lightweight monitoring server for the Pi.

Exposes:
  GET /monitor/          -> static dashboard (monitor.html)
  GET /api/metrics       -> JSON metrics

This is intended to run on the Pi and be accessible from the LAN so you can
open http://<pi-ip>/monitor/ to see Pi health even if SSH is down.
"""
from flask import Flask, jsonify, send_from_directory
import os
import time

app = Flask(__name__, static_folder='')

try:
    import psutil
except Exception:
    psutil = None


def gather_metrics():
    now = time.time()
    metrics = {'timestamp': now}
    try:
        if psutil:
            metrics['cpu_percent'] = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            metrics['mem_total'] = mem.total
            metrics['mem_used'] = mem.used
            metrics['mem_percent'] = mem.percent
            disk = psutil.disk_usage('/')
            metrics['disk_total'] = disk.total
            metrics['disk_used'] = disk.used
            metrics['disk_percent'] = disk.percent
            net = psutil.net_io_counters()
            metrics['net_bytes_sent'] = net.bytes_sent
            metrics['net_bytes_recv'] = net.bytes_recv
            try:
                temps = psutil.sensors_temperatures()
                metrics['temps'] = {k: [t.current for t in v] for k, v in temps.items()}
            except Exception:
                metrics['temps'] = {}
        else:
            metrics['error'] = 'psutil not installed'
    except Exception as e:
        metrics['error'] = str(e)

    return metrics


@app.route('/api/metrics')
def api_metrics():
    return jsonify(gather_metrics())


@app.route('/monitor/')
def monitor():
    return send_from_directory(os.path.dirname(__file__), 'monitor.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9000)
