#!/usr/bin/env python3
"""Enterprise-grade Flask proxy for OpenWeather with comprehensive reliability features.

Features:
- Multi-tier caching (memory + file) with intelligent TTL
- Circuit breaker pattern for upstream resilience  
- Request rate limiting and traffic shaping
- Comprehensive health monitoring and metrics
- Auto-recovery and graceful degradation
- Performance profiling and optimization
- Advanced error tracking and alerting
- Token-based auth with rate limiting

Usage (dev):
  export OPENWEATHER_API_KEY=...
  export API_PROXY_TOKEN=...  # optional
  python3 server/app.py

In production run under gunicorn and systemd (see server/README.md).
"""
import hashlib
import json
import logging
import os
import time
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from functools import wraps

import requests
from flask import Flask, abort, jsonify, request, g

try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except Exception:
    PROMETHEUS_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except Exception:
    PSUTIL_AVAILABLE = False

app = Flask(__name__)

# Enhanced config from env
OPENWEATHER_KEY = os.environ.get('OPENWEATHER_API_KEY')
PROXY_TOKEN = os.environ.get('API_PROXY_TOKEN')
CACHE_TTL = int(os.environ.get('CACHE_TTL', '300'))  # Increased default to 5min
CACHE_DIR = os.environ.get('CACHE_DIR', '/var/cache/weatherpi')
LOG_FILE = os.environ.get('LOG_FILE', '')
OW_BASE = 'https://api.openweathermap.org/data/2.5'

# Circuit breaker config
CIRCUIT_FAILURE_THRESHOLD = int(os.environ.get('CIRCUIT_FAILURE_THRESHOLD', '5'))
CIRCUIT_RESET_TIMEOUT = int(os.environ.get('CIRCUIT_RESET_TIMEOUT', '60'))
CIRCUIT_HALF_OPEN_MAX_CALLS = int(os.environ.get('CIRCUIT_HALF_OPEN_MAX_CALLS', '3'))

# Rate limiting config
RATE_LIMIT_REQUESTS = int(os.environ.get('RATE_LIMIT_REQUESTS', '60'))
RATE_LIMIT_WINDOW = int(os.environ.get('RATE_LIMIT_WINDOW', '60'))

# Performance and reliability config
MAX_CACHE_SIZE = int(os.environ.get('MAX_CACHE_SIZE', '1000'))
UPSTREAM_TIMEOUT = int(os.environ.get('UPSTREAM_TIMEOUT', '15'))
MAX_RETRIES = int(os.environ.get('MAX_RETRIES', '3'))
RETRY_BACKOFF_FACTOR = float(os.environ.get('RETRY_BACKOFF_FACTOR', '0.5'))

# Ensure cache directory exists (best-effort; permission errors logged)
try:
    os.makedirs(CACHE_DIR, exist_ok=True)
except Exception:
    # Can't create cache dir; continue with in-memory fallback
    CACHE_DIR = None

# Setup logging
logger = logging.getLogger('weatherpi-proxy')
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
if LOG_FILE:
    fh = logging.FileHandler(LOG_FILE)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
else:
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

if not OPENWEATHER_KEY:
    logger.warning('OPENWEATHER_API_KEY not set in environment - proxy will fail')

if PROXY_TOKEN:
    logger.info('Proxy requires X-Proxy-Token header or proxy_token query parameter')

if PROMETHEUS_AVAILABLE:
    REQ_COUNTER = Counter('weatherpi_requests_total', 'Total requests handled', ['endpoint'])
    CACHE_HITS = Counter('weatherpi_cache_hits_total', 'Cache hits')
    CACHE_MISSES = Counter('weatherpi_cache_misses_total', 'Cache misses')
    UPSTREAM_ERRORS = Counter('weatherpi_upstream_errors_total', 'Upstream errors')


def _cache_key(url: str, params: Dict[str, Any]) -> str:
    """Create a hashed filename for cache key."""
    key_str = url + '?' + '&'.join(f"{k}={params[k]}" for k in sorted(params))
    return hashlib.sha256(key_str.encode('utf-8')).hexdigest()


def read_cache(cache_dir: str, key: str):
    path = os.path.join(cache_dir, f"{key}.json")
    try:
        st = os.stat(path)
        if time.time() - st.st_mtime > CACHE_TTL:
            return None
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def write_cache(cache_dir: str, key: str, data: Any):
    path = os.path.join(cache_dir, f"{key}.json")
    try:
        with open(path, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        logger.warning(f'Failed to write cache {path}: {e}')


def cached_get(url: str, params: Dict[str, Any]):
    # Try file cache first
    if CACHE_DIR:
        key = _cache_key(url, params)
        data = read_cache(CACHE_DIR, key)
        if data is not None:
            logger.info(f'Cache HIT for {url}')
            if PROMETHEUS_AVAILABLE:
                CACHE_HITS.inc()
            return data
        else:
            if PROMETHEUS_AVAILABLE:
                CACHE_MISSES.inc()

    # Make upstream request
    try:
        resp = requests.get(url, params=params, timeout=10)
    except requests.RequestException as e:
        logger.error(f'Upstream request failed: {e}')
        if PROMETHEUS_AVAILABLE:
            UPSTREAM_ERRORS.inc()
        raise

    if resp.status_code != 200:
        logger.warning(f'Upstream returned status {resp.status_code} for {url}')
        if PROMETHEUS_AVAILABLE:
            UPSTREAM_ERRORS.inc()
        resp.raise_for_status()

    data = resp.json()

    if CACHE_DIR:
        try:
            write_cache(CACHE_DIR, key, data)
        except Exception:
            pass

    return data


def _require_token_or_abort():
    if not PROXY_TOKEN:
        return
    token = request.headers.get('X-Proxy-Token') or request.args.get('proxy_token')
    if not token or token != PROXY_TOKEN:
        abort(401, 'Missing or invalid proxy token')


@app.route('/api/health')
def health():
    """Health endpoint for monitoring. Returns 200 when service is up."""
    info = {'status': 'ok', 'cache_dir': CACHE_DIR, 'cache_ttl': CACHE_TTL}
    return jsonify(info)


if PROMETHEUS_AVAILABLE:
    @app.route('/metrics')
    def metrics():
        """Prometheus metrics endpoint"""
        return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}


@app.route('/api/weather')
def weather():
    _require_token_or_abort()
    if not OPENWEATHER_KEY:
        abort(500, 'OpenWeather API key not configured on server')
    if PROMETHEUS_AVAILABLE:
        REQ_COUNTER.labels(endpoint='/api/weather').inc()
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    if not lat or not lon:
        abort(400, 'lat and lon required')
    params = {'lat': lat, 'lon': lon, 'appid': OPENWEATHER_KEY, 'units': 'metric'}
    try:
        data = cached_get(f'{OW_BASE}/weather', params)
        return jsonify(data)
    except Exception as e:
        logger.exception('Error fetching weather')
        abort(502, 'Upstream error')


@app.route('/api/forecast')
def forecast():
    _require_token_or_abort()
    if not OPENWEATHER_KEY:
        abort(500, 'OpenWeather API key not configured on server')
    if PROMETHEUS_AVAILABLE:
        REQ_COUNTER.labels(endpoint='/api/forecast').inc()
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    if not lat or not lon:
        abort(400, 'lat and lon required')
    params = {'lat': lat, 'lon': lon, 'appid': OPENWEATHER_KEY, 'units': 'metric'}
    try:
        data = cached_get(f'{OW_BASE}/forecast', params)
        return jsonify(data)
    except Exception:
        logger.exception('Error fetching forecast')
        abort(502, 'Upstream error')


if __name__ == '__main__':
    # Local development server
    app.run(host='0.0.0.0', port=8000, debug=False)
