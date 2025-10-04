#!/usr/bin/env python3
"""Simple local HTTP receiver for heartbeats.

Usage:
  python3 monitor/local_receiver.py

Endpoints:
  POST /heartbeat   Accepts JSON heartbeats and stores last payload.
  GET /             HTML page showing last heartbeat and a small status.

Runs on http://0.0.0.0:9000 by default.
"""
import http.server
import socketserver
import json
import os
from datetime import datetime

HOST = '0.0.0.0'
PORT = int(os.environ.get('LOCAL_RECEIVER_PORT', '9000'))
STORAGE = os.path.expanduser('~/.weatherpi_last_heartbeat.json')

class Handler(http.server.BaseHTTPRequestHandler):
    def _set_headers(self, status=200, content_type='text/html'):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()

    def do_POST(self):
        if self.path != '/heartbeat':
            return self._set_headers(404)
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length) if length else b''
        try:
            data = json.loads(body.decode('utf-8')) if body else {}
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(b'Invalid JSON')
            return

        # add receiver timestamp
        data['_received_at'] = datetime.utcnow().isoformat() + 'Z'
        try:
            with open(STORAGE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self._set_headers(500)
            self.wfile.write(b'Failed to write')
            return

        self._set_headers(200, 'application/json')
        self.wfile.write(json.dumps({'status': 'ok'}).encode('utf-8'))

    def do_GET(self):
        if self.path == '/heartbeat.json':
            if not os.path.exists(STORAGE):
                return self._set_headers(404, 'application/json')
            with open(STORAGE, 'r') as f:
                body = f.read()
            self._set_headers(200, 'application/json')
            self.wfile.write(body.encode('utf-8'))
            return

        # Serve simple HTML dashboard
        last = {}
        if os.path.exists(STORAGE):
            try:
                with open(STORAGE, 'r') as f:
                    last = json.load(f)
            except Exception:
                last = {'error': 'failed to load stored payload'}

        body = f"""
        <!doctype html>
        <html><head><meta charset='utf-8'><title>WeatherPi Heartbeat Receiver</title>
        <style>body{{font-family:Arial,Helvetica,sans-serif;margin:20px;background:#111;color:#eee}}pre{{background:#0b0b0b;padding:12px;border-radius:6px;overflow:auto}}</style>
        </head><body>
        <h1>WeatherPi Heartbeat Receiver</h1>
        <p>POST heartbeats to <code>/heartbeat</code>. JSON stored at <code>{STORAGE}</code>.</p>
        <h2>Last payload</h2>
        <pre>{json.dumps(last, indent=2)}</pre>
        </body></html>
        """
        self._set_headers(200, 'text/html')
        self.wfile.write(body.encode('utf-8'))

    def log_message(self, format, *args):
        # friendly short logging
        print("[local_receiver] %s - - %s" % (self.client_address[0], format%args))

if __name__ == '__main__':
    print(f"Starting local receiver on http://{HOST}:{PORT}/")
    with socketserver.TCPServer((HOST, PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\nShutting down')
            httpd.server_close()
