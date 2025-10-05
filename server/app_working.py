#!/usr/bin/env python3
"""
WeatherPi Working Enhanced Proxy Server
=======================================

A simplified but robust version focusing on core enterprise features:
- Circuit breaker pattern
- Rate limiting  
- Multi-tier caching
- Error tracking
- Health monitoring
"""

import os
import sys
import json
import time
import hashlib
import logging
import threading
from typing import Dict, Any, Optional
from datetime import datetime
from collections import defaultdict, deque
from functools import wraps
from dataclasses import dataclass

import requests
from flask import Flask, request, jsonify, abort

# Configuration from environment
OPENWEATHER_KEY = os.environ.get('OPENWEATHER_API_KEY', '')
PROXY_TOKEN = os.environ.get('PROXY_TOKEN', 'test_token')
OW_BASE = 'https://api.openweathermap.org/data/2.5'
CACHE_DIR = os.environ.get('CACHE_DIR', '/tmp/weatherpi_cache')
LOG_FILE = os.environ.get('LOG_FILE', '/var/log/weatherpi/proxy.log')

# Configuration
CACHE_TTL = int(os.environ.get('CACHE_TTL', '300'))
MEMORY_CACHE_SIZE = int(os.environ.get('MEMORY_CACHE_SIZE', '100'))
CIRCUIT_FAILURE_THRESHOLD = int(os.environ.get('CIRCUIT_FAILURE_THRESHOLD', '5'))
CIRCUIT_RECOVERY_TIMEOUT = int(os.environ.get('CIRCUIT_RECOVERY_TIMEOUT', '60'))
RATE_LIMIT_REQUESTS = int(os.environ.get('RATE_LIMIT_REQUESTS', '60'))
RATE_LIMIT_WINDOW = int(os.environ.get('RATE_LIMIT_WINDOW', '60'))
UPSTREAM_TIMEOUT = int(os.environ.get('UPSTREAM_TIMEOUT', '15'))

# Setup directories
try:
    os.makedirs(CACHE_DIR, exist_ok=True)
    if LOG_FILE:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
except Exception:
    pass

# Setup logging
logger = logging.getLogger('weatherpi-proxy')
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

if LOG_FILE:
    try:
        fh = logging.FileHandler(LOG_FILE)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except Exception:
        pass

ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)

app = Flask(__name__)


@dataclass
class CircuitBreakerState:
    failures: int = 0
    last_failure: float = 0
    state: str = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN


class MemoryCache:
    """Simple memory cache with TTL"""
    
    def __init__(self, max_size: int, ttl: int):
        self.max_size = max_size
        self.ttl = ttl
        self.cache = {}
        self.access_order = deque()
        self.lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        with self.lock:
            if key not in self.cache:
                return None
            
            data, timestamp = self.cache[key]
            if time.time() - timestamp > self.ttl:
                del self.cache[key]
                try:
                    self.access_order.remove(key)
                except ValueError:
                    pass
                return None
            
            # Move to end for LRU
            try:
                self.access_order.remove(key)
            except ValueError:
                pass
            self.access_order.append(key)
            
            return data
    
    def set(self, key: str, data: Any):
        with self.lock:
            # Remove oldest if at capacity
            while len(self.cache) >= self.max_size:
                if not self.access_order:
                    break
                oldest = self.access_order.popleft()
                if oldest in self.cache:
                    del self.cache[oldest]
            
            self.cache[key] = (data, time.time())
            if key not in self.access_order:
                self.access_order.append(key)
    
    def clear(self):
        with self.lock:
            self.cache.clear()
            self.access_order.clear()


class CircuitBreaker:
    """Circuit breaker for fault tolerance"""
    
    def __init__(self):
        self.state = CircuitBreakerState()
        self.lock = threading.RLock()
    
    def call(self, func, *args, **kwargs):
        with self.lock:
            if self.state.state == 'OPEN':
                if time.time() - self.state.last_failure > CIRCUIT_RECOVERY_TIMEOUT:
                    self.state.state = 'HALF_OPEN'
                    logger.info("Circuit breaker -> HALF_OPEN")
                else:
                    raise Exception("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            
            with self.lock:
                if self.state.state == 'HALF_OPEN':
                    self.state.state = 'CLOSED'
                    self.state.failures = 0
                    logger.info("Circuit breaker -> CLOSED")
                elif self.state.state == 'CLOSED':
                    self.state.failures = max(0, self.state.failures - 1)
            
            return result
            
        except Exception as e:
            with self.lock:
                self.state.failures += 1
                self.state.last_failure = time.time()
                
                if self.state.failures >= CIRCUIT_FAILURE_THRESHOLD:
                    self.state.state = 'OPEN'
                    logger.error(f"Circuit breaker -> OPEN ({self.state.failures} failures)")
            
            raise e


class RateLimiter:
    """Simple rate limiter"""
    
    def __init__(self):
        self.clients = defaultdict(lambda: deque())
        self.lock = threading.RLock()
    
    def is_allowed(self, client_id: str) -> bool:
        with self.lock:
            now = time.time()
            client_requests = self.clients[client_id]
            
            # Remove old requests
            while client_requests and now - client_requests[0] > RATE_LIMIT_WINDOW:
                client_requests.popleft()
            
            # Check limit
            if len(client_requests) >= RATE_LIMIT_REQUESTS:
                return False
            
            client_requests.append(now)
            return True


class ErrorTracker:
    """Track errors over time"""
    
    def __init__(self):
        self.errors = deque(maxlen=100)
        self.lock = threading.RLock()
    
    def record_error(self, error_type: str, endpoint: str):
        with self.lock:
            self.errors.append({
                'timestamp': time.time(),
                'type': error_type,
                'endpoint': endpoint
            })
    
    def get_error_rate(self, window_seconds: int = 300) -> float:
        with self.lock:
            now = time.time()
            recent_errors = [e for e in self.errors if now - e['timestamp'] <= window_seconds]
            return len(recent_errors) / window_seconds if window_seconds > 0 else 0


# Global instances
memory_cache = MemoryCache(MEMORY_CACHE_SIZE, 60)  # 1 minute TTL for memory
circuit_breaker = CircuitBreaker()
rate_limiter = RateLimiter()
error_tracker = ErrorTracker()
active_requests = 0


def _cache_key(url: str, params: Dict[str, Any]) -> str:
    """Create cache key"""
    key_str = url + '?' + '&'.join(f"{k}={v}" for k, v in sorted(params.items()))
    return hashlib.sha256(key_str.encode('utf-8')).hexdigest()


def _file_cache_get(key: str) -> Optional[Any]:
    """Get from file cache"""
    if not CACHE_DIR:
        return None
    
    path = os.path.join(CACHE_DIR, f"{key}.json")
    try:
        stat = os.stat(path)
        if time.time() - stat.st_mtime > CACHE_TTL:
            return None
        
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def _file_cache_set(key: str, data: Any):
    """Set file cache"""
    if not CACHE_DIR:
        return
    
    path = os.path.join(CACHE_DIR, f"{key}.json")
    try:
        with open(path, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        logger.warning(f'Cache write failed: {e}')


def _upstream_request(url: str, params: Dict[str, Any]) -> Any:
    """Make upstream request"""
    response = requests.get(url, params=params, timeout=UPSTREAM_TIMEOUT)
    
    if response.status_code == 200:
        return response.json()
    else:
        response.raise_for_status()


def _cached_get(url: str, params: Dict[str, Any]) -> Any:
    """Get with caching"""
    cache_key = _cache_key(url, params)
    
    # Try memory cache
    data = memory_cache.get(cache_key)
    if data is not None:
        logger.debug(f'Memory cache HIT: {url}')
        return data
    
    # Try file cache
    data = _file_cache_get(cache_key)
    if data is not None:
        logger.debug(f'File cache HIT: {url}')
        memory_cache.set(cache_key, data)
        return data
    
    # Get from upstream via circuit breaker
    data = circuit_breaker.call(_upstream_request, url, params)
    
    # Cache the result
    memory_cache.set(cache_key, data)
    _file_cache_set(cache_key, data)
    
    logger.info(f'Upstream request: {url}')
    return data


def _get_client_id() -> str:
    """Get client identifier"""
    return request.headers.get('X-Forwarded-For', request.remote_addr) or 'unknown'


def _require_token():
    """Check authentication"""
    if not PROXY_TOKEN:
        return
    
    token = request.headers.get('X-Proxy-Token') or request.args.get('proxy_token')
    if not token or token != PROXY_TOKEN:
        abort(401, 'Invalid or missing token')


def _track_request(endpoint: str):
    """Request tracking decorator"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            global active_requests
            
            # Rate limiting
            client_id = _get_client_id()
            if not rate_limiter.is_allowed(client_id):
                abort(429, 'Rate limit exceeded')
            
            active_requests += 1
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                error_tracker.record_error('error', endpoint)
                logger.exception(f'Error in {endpoint}')
                raise
            finally:
                active_requests -= 1
        
        return wrapper
    return decorator


@app.route('/api/health')
@_track_request('/api/health')
def health():
    """Health check endpoint"""
    status = {
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'uptime': time.time() - getattr(app, 'start_time', time.time()),
        'cache': {
            'memory_size': len(memory_cache.cache),
            'file_cache_dir': CACHE_DIR,
            'ttl': CACHE_TTL
        },
        'circuit_breaker': {
            'state': circuit_breaker.state.state,
            'failures': circuit_breaker.state.failures,
            'last_failure': circuit_breaker.state.last_failure
        },
        'active_requests': active_requests,
        'error_rate': error_tracker.get_error_rate()
    }
    
    # Check if degraded
    if (error_tracker.get_error_rate() > 0.5 or 
        circuit_breaker.state.state == 'OPEN' or
        active_requests > 50):
        status['status'] = 'degraded'
        return jsonify(status), 503
    
    return jsonify(status)


@app.route('/metrics')
def metrics():
    """Simple metrics endpoint"""
    metrics_data = {
        'active_requests': active_requests,
        'circuit_breaker_state': circuit_breaker.state.state,
        'cache_size': len(memory_cache.cache),
        'error_rate': error_tracker.get_error_rate()
    }
    
    # Format as prometheus-style text
    output = []
    for metric, value in metrics_data.items():
        if isinstance(value, str):
            output.append(f'weatherpi_{metric}{{state="{value}"}} 1')
        else:
            output.append(f'weatherpi_{metric} {value}')
    
    return '\n'.join(output), 200, {'Content-Type': 'text/plain; version=0.0.4; charset=utf-8'}


@app.route('/api/weather')
@_track_request('/api/weather')
def weather():
    """Weather endpoint"""
    _require_token()
    
    # Get API key from config or environment
    api_key = app.config.get('OPENWEATHER_API_KEY') or OPENWEATHER_KEY
    if not api_key:
        abort(500, 'API key not configured')
    
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    
    if not lat or not lon:
        abort(400, 'lat and lon required')
    
    try:
        lat_f = float(lat)
        lon_f = float(lon)
        if not (-90 <= lat_f <= 90) or not (-180 <= lon_f <= 180):
            abort(400, 'Invalid coordinates')
    except ValueError:
        abort(400, 'Invalid coordinate format')
    
    params = {
        'lat': lat,
        'lon': lon, 
        'appid': api_key,
        'units': 'metric'
    }
    
    try:
        data = _cached_get(f'{OW_BASE}/weather', params)
        return jsonify(data)
    except Exception as e:
        logger.exception('Weather request failed')
        error_tracker.record_error('upstream_error', '/api/weather')
        abort(502, 'Upstream service error')


@app.route('/api/forecast')
@_track_request('/api/forecast')  
def forecast():
    """Forecast endpoint"""
    _require_token()
    
    # Get API key from config or environment
    api_key = app.config.get('OPENWEATHER_API_KEY') or OPENWEATHER_KEY
    if not api_key:
        abort(500, 'API key not configured')
    
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    
    if not lat or not lon:
        abort(400, 'lat and lon required')
    
    try:
        lat_f = float(lat)
        lon_f = float(lon)
        if not (-90 <= lat_f <= 90) or not (-180 <= lon_f <= 180):
            abort(400, 'Invalid coordinates')
    except ValueError:
        abort(400, 'Invalid coordinate format')
    
    params = {
        'lat': lat,
        'lon': lon,
        'appid': api_key, 
        'units': 'metric'
    }
    
    try:
        data = _cached_get(f'{OW_BASE}/forecast', params)
        return jsonify(data)
    except Exception as e:
        logger.exception('Forecast request failed')
        error_tracker.record_error('upstream_error', '/api/forecast')
        abort(502, 'Upstream service error')


@app.route('/api/cache/clear', methods=['POST'])
@_track_request('/api/cache/clear')
def clear_cache():
    """Clear cache"""
    _require_token()
    
    try:
        memory_cache.clear()
        
        if CACHE_DIR and os.path.exists(CACHE_DIR):
            import shutil
            shutil.rmtree(CACHE_DIR)
            os.makedirs(CACHE_DIR, exist_ok=True)
        
        return jsonify({'status': 'Cache cleared'})
    except Exception as e:
        logger.exception('Cache clear failed')
        abort(500, 'Cache clear failed')


@app.route('/api/circuit-breaker/reset', methods=['POST'])
@_track_request('/api/circuit-breaker/reset')
def reset_circuit_breaker():
    """Reset circuit breaker"""
    _require_token()
    
    with circuit_breaker.lock:
        circuit_breaker.state = CircuitBreakerState()
        logger.info('Circuit breaker reset')
    
    return jsonify({'status': 'Circuit breaker reset'})


@app.errorhandler(Exception)
def handle_exception(e):
    """Global error handler"""
    from werkzeug.exceptions import HTTPException
    
    if isinstance(e, HTTPException):
        return e
    
    logger.exception('Unhandled exception')
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    app.start_time = time.time()
    logger.info('Starting WeatherPi Enhanced Proxy')
    logger.info(f'Cache TTL: {CACHE_TTL}s, Rate limit: {RATE_LIMIT_REQUESTS}/{RATE_LIMIT_WINDOW}s')
    
    app.run(host='0.0.0.0', port=8000, debug=False, threaded=True)