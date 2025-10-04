#!/usr/bin/env python3
"""
Lightweight status HTTP server for WeatherPi watchdog
- Serves /status.json (raw JSON) and / (simple HTML dashboard)
- Binds to 0.0.0.0:8080 by default (env LOCAL_STATUS_BIND)
- No external dependencies
"""
import os
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime

BIND = os.environ.get('LOCAL_STATUS_BIND', '0.0.0.0')
PORT = int(os.environ.get('LOCAL_STATUS_PORT', '8080'))
STATUS_FILE = '/var/lib/weatherpi/last_status.json'

HTML_TEMPLATE = '''<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>WeatherPi — Local Status</title>
<style>
body{font-family:Inter, Arial, sans-serif;background:#0f1724;color:#e6eef6;margin:0;padding:20px}
.container{max-width:980px;margin:0 auto}
.header{display:flex;align-items:center;justify-content:space-between}
.header h1{margin:0;font-size:20px}
.card{background:linear-gradient(180deg,#0b1220, #0d1522);border-radius:12px;padding:16px;margin-top:16px;box-shadow:0 6px 20px rgba(2,6,23,0.6)}
.kv{display:flex;gap:12px;align-items:center}
.k{color:#9fb1c9;width:160px}
.v{font-weight:700}
.bad{color:#ffb4b4}
.good{color:#b8f2b8}
.small{font-size:12px;color:#9fb1c9}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>WeatherPi — Local Status</h1>
    <div class="small">Updated: {updated}</div>
  </div>
  <div class="card">
    <div class="kv"><div class="k">Services</div><div class="v">{services}</div></div>
    <div class="kv"><div class="k">Disk</div><div class="v">{disk_pct}% used ({disk_free} bytes free)</div></div>
    <div class="kv"><div class="k">Inodes</div><div class="v">{inode_pct}% used</div></div>
    <div class="kv"><div class="k">Memory</div><div class="v">{mem_avail} MB available</div></div>
    <div class="kv"><div class="k">Load (1m)</div><div class="v">{load1}</div></div>
    <div class="kv"><div class="k">CPU temp</div><div class="v">{cpu_temp}</div></div>
    <div class="kv"><div class="k">Network</div><div class="v">DNS: {dns_ok}, External reach: {external_ok}</div></div>
    <div style="margin-top:12px" class="small">Raw JSON: <a href="/status.json">/status.json</a></div>
  </div>
</div>
</body>
</html>
'''

class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.end_headers()

    def do_GET(self):
        if self.path == '/status.json':
            if not os.path.exists(STATUS_FILE):
                self.send_response(404)
                self._cors()
                self.end_headers()
                return
            with open(STATUS_FILE, 'r') as f:
                body = f.read()
            self.send_response(200)
            self._cors()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(body.encode('utf-8'))
            return

        # serve HTML with safe defaults
        status = {}
        try:
            if os.path.exists(STATUS_FILE):
                with open(STATUS_FILE, 'r') as f:
                    status = json.load(f)
        except Exception:
            status = {}

        services = ', '.join(f"{k}:{'OK' if v else 'DOWN'}" for k,v in status.get('checks', {}).items() if k.startswith('service:')) or 'unknown'
        disk = status.get('checks', {}).get('disk', {})
        disk_pct = disk.get('percent', 'n/a')
        disk_free = disk.get('free', 'n/a')
        inodes = status.get('checks', {}).get('inodes', {})
        inode_pct = inodes.get('percent', 'n/a')
        mem = status.get('checks', {}).get('memory', {})
        mem_avail = mem.get('avail_kb', mem.get('available_kb', 0)) // 1024 if isinstance(mem.get('avail_kb', None), int) or isinstance(mem.get('available_kb', None), int) else 'n/a'
        load = status.get('checks', {}).get('loadavg', (0.0,0.0,0.0))
        load1 = load[0] if isinstance(load, (list,tuple)) else 'n/a'
        cpu = status.get('checks', {}).get('cpu_temp', 'n/a')
        network = status.get('checks', {}).get('network', {})
        dns_ok = network.get('dns_ok', 'n/a')
        external_ok = network.get('external_connect', 'n/a')

        body = HTML_TEMPLATE.format(updated=datetime.utcnow().isoformat()+'Z', services=services, disk_pct=disk_pct, disk_free=disk_free, inode_pct=inode_pct, mem_avail=mem_avail, load1=load1, cpu_temp=cpu, dns_ok=dns_ok, external_ok=external_ok)
        self.send_response(200)
        self._cors()
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(body.encode('utf-8'))

    def log_message(self, format, *args):
        print(f"[status_server] {format % args}")

if __name__ == '__main__':
    server = HTTPServer((BIND, PORT), Handler)
    print(f"Starting status server on http://{BIND}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
        print('Shutting down')
