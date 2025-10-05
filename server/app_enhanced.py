#!/usr/bin/env python3
"""
WeatherPi Enterprise-Grade Proxy Server
========================================

Features:
- Circuit breaker pattern for fault tolerance
- Rate limiting with sliding window
- Multi-tier caching (memory + file)
- Comprehensive error tracking and recovery
- Performance profiling and metrics
- Graceful degradation
- Request deduplication
- Health monitoring with detailed status
"""

import os
import sys
import json
import time
import hashlib
import logging
import threading
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque
from functools import wraps
from dataclasses import dataclass, asdict
import signal
import atexit

import requests
from flask import Flask, request, jsonify, abort
from werkzeug.exceptions import HTTPException

# Try to import optional dependencies
try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

app = Flask(__name__)

# Configuration
OPENWEATHER_KEY = os.environ.get('OPENWEATHER_API_KEY', '')
PROXY_TOKEN = os.environ.get('PROXY_TOKEN', '')
OW_BASE = 'https://api.openweathermap.org/data/2.5'
CACHE_DIR = os.environ.get('CACHE_DIR', '/tmp/weatherpi_cache')
LOG_FILE = os.environ.get('LOG_FILE', '/var/log/weatherpi/proxy.log')

# Cache configuration
CACHE_TTL = int(os.environ.get('CACHE_TTL', '300'))  # 5 minutes
MEMORY_CACHE_SIZE = int(os.environ.get('MEMORY_CACHE_SIZE', '100'))
MEMORY_CACHE_TTL = int(os.environ.get('MEMORY_CACHE_TTL', '60'))  # 1 minute

# Circuit breaker configuration
CIRCUIT_FAILURE_THRESHOLD = int(os.environ.get('CIRCUIT_FAILURE_THRESHOLD', '5'))
CIRCUIT_RECOVERY_TIMEOUT = int(os.environ.get('CIRCUIT_RECOVERY_TIMEOUT', '60'))
CIRCUIT_HALF_OPEN_MAX_CALLS = int(os.environ.get('CIRCUIT_HALF_OPEN_MAX_CALLS', '3'))

# Rate limiting configuration
RATE_LIMIT_REQUESTS = int(os.environ.get('RATE_LIMIT_REQUESTS', '60'))
RATE_LIMIT_WINDOW = int(os.environ.get('RATE_LIMIT_WINDOW', '60'))
RATE_LIMIT_BURST = int(os.environ.get('RATE_LIMIT_BURST', '10'))

# Performance configuration
UPSTREAM_TIMEOUT = int(os.environ.get('UPSTREAM_TIMEOUT', '15'))
MAX_RETRIES = int(os.environ.get('MAX_RETRIES', '3'))
RETRY_BACKOFF_FACTOR = float(os.environ.get('RETRY_BACKOFF_FACTOR', '0.5'))
REQUEST_TIMEOUT = int(os.environ.get('REQUEST_TIMEOUT', '30'))

# Error tracking configuration
ERROR_WINDOW_SIZE = int(os.environ.get('ERROR_WINDOW_SIZE', '100'))
MAX_ERROR_RATE = float(os.environ.get('MAX_ERROR_RATE', '0.5'))

# Setup directories
try:
    for directory in [CACHE_DIR, os.path.dirname(LOG_FILE)]:
        if directory:
            os.makedirs(directory, exist_ok=True)
except Exception as e:
    print(f"Warning: Could not create directories: {e}")

# Setup logging
logger = logging.getLogger('weatherpi-proxy')
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

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

if not OPENWEATHER_KEY:
    logger.warning('OPENWEATHER_API_KEY not set - proxy will fail for actual requests')

# Metrics setup
if PROMETHEUS_AVAILABLE:
    REQUEST_COUNTER = Counter('weatherpi_requests_total', 'Total requests', ['endpoint', 'status'])
    REQUEST_DURATION = Histogram('weatherpi_request_duration_seconds', 'Request duration', ['endpoint'])
    CACHE_HITS = Counter('weatherpi_cache_hits_total', 'Cache hits', ['cache_type'])
    CACHE_MISSES = Counter('weatherpi_cache_misses_total', 'Cache misses')
    UPSTREAM_ERRORS = Counter('weatherpi_upstream_errors_total', 'Upstream errors', ['error_type'])
    CIRCUIT_STATE = Gauge('weatherpi_circuit_breaker_state', 'Circuit breaker state')
    RATE_LIMIT_REJECTIONS = Counter('weatherpi_rate_limit_rejections_total', 'Rate limit rejections')
    ACTIVE_REQUESTS = Gauge('weatherpi_active_requests', 'Currently active requests')
    MEMORY_CACHE_SIZE_GAUGE = Gauge('weatherpi_memory_cache_size', 'Memory cache size')


@dataclass
class CacheEntry:
    data: Any
    timestamp: float
    access_count: int = 0
    last_access: float = 0


@dataclass
class CircuitBreakerState:
    failures: int = 0
    last_failure: float = 0
    state: str = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    half_open_calls: int = 0


@dataclass
class RateLimitWindow:
    requests: deque
    tokens: int


class EnhancedMemoryCache:
    """LRU memory cache with TTL and statistics"""
    
    def __init__(self, max_size: int, ttl: int):
        self.max_size = max_size
        self.ttl = ttl
        self.cache: Dict[str, CacheEntry] = {}
        self.access_order = deque()
        self.lock = threading.RLock()
        self.stats = {'hits': 0, 'misses': 0, 'evictions': 0}
    
    def get(self, key: str) -> Optional[Any]:
        with self.lock:
            entry = self.cache.get(key)
            if not entry:
                self.stats['misses'] += 1
                return None
            
            if time.time() - entry.timestamp > self.ttl:
                del self.cache[key]
                try:
                    self.access_order.remove(key)
                except ValueError:
                    pass
                self.stats['misses'] += 1
                return None
            
            entry.access_count += 1
            entry.last_access = time.time()
            self.stats['hits'] += 1
            
            # Move to end for LRU
            try:
                self.access_order.remove(key)
            except ValueError:
                pass
            self.access_order.append(key)
            
            return entry.data
    
    def set(self, key: str, data: Any):
        with self.lock:
            now = time.time()
            
            if key in self.cache:
                self.cache[key].data = data
                self.cache[key].timestamp = now
                return
            
            while len(self.cache) >= self.max_size:
                if not self.access_order:
                    break
                oldest = self.access_order.popleft()
                if oldest in self.cache:
                    del self.cache[oldest]
                    self.stats['evictions'] += 1
            
            self.cache[key] = CacheEntry(data=data, timestamp=now, last_access=now)
            self.access_order.append(key)
    
    def clear(self):
        with self.lock:
            self.cache.clear()
            self.access_order.clear()
    
    def size(self) -> int:
        return len(self.cache)


class CircuitBreaker:
    """Circuit breaker implementation for fault tolerance"""
    
    def __init__(self):
        self.state = CircuitBreakerState()
        self.lock = threading.RLock()
    
    def call(self, func, *args, **kwargs):
        with self.lock:
            if self.state.state == 'OPEN':
                if time.time() - self.state.last_failure > CIRCUIT_RECOVERY_TIMEOUT:
                    self.state.state = 'HALF_OPEN'
                    self.state.half_open_calls = 0
                    logger.info("Circuit breaker transitioning to HALF_OPEN")
                else:
                    raise Exception("Circuit breaker is OPEN")
            
            if self.state.state == 'HALF_OPEN':
                if self.state.half_open_calls >= CIRCUIT_HALF_OPEN_MAX_CALLS:
                    self.state.state = 'OPEN'
                    logger.warning("Circuit breaker back to OPEN after failed half-open test")
                    raise Exception("Circuit breaker is OPEN")
                self.state.half_open_calls += 1
        
        try:
            result = func(*args, **kwargs)
            with self.lock:
                if self.state.state == 'HALF_OPEN':
                    self.state.state = 'CLOSED'
                    self.state.failures = 0
                    logger.info("Circuit breaker recovered to CLOSED")
                elif self.state.state == 'CLOSED':
                    self.state.failures = max(0, self.state.failures - 1)
            return result
        except Exception as e:
            with self.lock:
                self.state.failures += 1
                self.state.last_failure = time.time()
                
                if self.state.failures >= CIRCUIT_FAILURE_THRESHOLD:
                    self.state.state = 'OPEN'
                    logger.error(f"Circuit breaker OPENED after {self.state.failures} failures")
                
                if PROMETHEUS_AVAILABLE:
                    CIRCUIT_STATE.set({'CLOSED': 0, 'HALF_OPEN': 1, 'OPEN': 2}[self.state.state])
            
            raise e


class RateLimiter:
    """Token bucket rate limiter with burst support"""
    
    def __init__(self):
        self.windows: Dict[str, RateLimitWindow] = defaultdict(
            lambda: RateLimitWindow(requests=deque(), tokens=RATE_LIMIT_BURST)
        )
        self.lock = threading.RLock()
    
    def is_allowed(self, client_id: str) -> bool:
        with self.lock:
            now = time.time()
            window = self.windows[client_id]
            
            # Remove old requests
            while window.requests and now - window.requests[0] > RATE_LIMIT_WINDOW:
                window.requests.popleft()
            
            # Check if we're at the limit
            if len(window.requests) >= RATE_LIMIT_REQUESTS:
                if PROMETHEUS_AVAILABLE:
                    RATE_LIMIT_REJECTIONS.inc()
                return False
            
            # Allow the request
            window.requests.append(now)
            return True


class ErrorTracker:
    """Track and analyze error patterns"""
    
    def __init__(self):
        self.errors = deque(maxlen=ERROR_WINDOW_SIZE)
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
    
    def get_error_summary(self) -> Dict[str, Any]:
        with self.lock:
            error_types = defaultdict(int)
            endpoints = defaultdict(int)
            
            for error in list(self.errors):
                error_types[error['type']] += 1
                endpoints[error['endpoint']] += 1
            
            return {
                'total_errors': len(self.errors),
                'error_rate': self.get_error_rate(),
                'by_type': dict(error_types),
                'by_endpoint': dict(endpoints)
            }


# Global instances
memory_cache = EnhancedMemoryCache(MEMORY_CACHE_SIZE, MEMORY_CACHE_TTL)
circuit_breaker = CircuitBreaker()
rate_limiter = RateLimiter()
error_tracker = ErrorTracker()
active_requests = 0
request_deduplication: Dict[str, threading.Event] = {}


def _cache_key(url: str, params: Dict[str, Any]) -> str:
    """Create a hashed cache key"""
    key_str = url + '?' + '&'.join(f"{k}={v}" for k, v in sorted(params.items()))
    return hashlib.sha256(key_str.encode('utf-8')).hexdigest()


def _get_client_id() -> str:
    """Get client identifier for rate limiting"""
    return request.headers.get('X-Forwarded-For', request.remote_addr) or 'unknown'


def _file_cache_get(key: str) -> Optional[Any]:
    """Get data from file cache"""
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
    """Set data in file cache"""
    if not CACHE_DIR:
        return
    
    path = os.path.join(CACHE_DIR, f"{key}.json")
    try:
        with open(path, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        logger.warning(f'Failed to write cache {path}: {e}')


def _upstream_request(url: str, params: Dict[str, Any]) -> Any:
    """Make upstream request with retries and timeout"""
    last_exception = None
    
    for attempt in range(MAX_RETRIES + 1):
        try:
            if attempt > 0:
                delay = RETRY_BACKOFF_FACTOR * (2 ** (attempt - 1))
                time.sleep(delay)
                logger.info(f"Retry {attempt}/{MAX_RETRIES} after {delay}s delay")
            
            response = requests.get(
                url, 
                params=params, 
                timeout=UPSTREAM_TIMEOUT,
                headers={'User-Agent': 'WeatherPi-Proxy/1.0'}
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code in (429, 503, 502, 504):
                # Retriable errors
                last_exception = Exception(f"HTTP {response.status_code}: {response.text}")
                continue
            else:
                # Non-retriable error
                response.raise_for_status()
                
        except requests.exceptions.Timeout as e:
            last_exception = e
            logger.warning(f"Request timeout on attempt {attempt + 1}")
        except requests.exceptions.RequestException as e:
            last_exception = e
            logger.warning(f"Request failed on attempt {attempt + 1}: {e}")
    
    raise last_exception or Exception("All retry attempts failed")


def _cached_get(url: str, params: Dict[str, Any]) -> Any:
    """Get data with multi-tier caching"""
    cache_key = _cache_key(url, params)
    
    # Try memory cache first
    data = memory_cache.get(cache_key)
    if data is not None:
        logger.debug(f'Memory cache HIT for {url}')
        if PROMETHEUS_AVAILABLE:
            CACHE_HITS.labels(cache_type='memory').inc()
        return data
    
    # Try file cache
    data = _file_cache_get(cache_key)
    if data is not None:
        logger.debug(f'File cache HIT for {url}')
        if PROMETHEUS_AVAILABLE:
            CACHE_HITS.labels(cache_type='file').inc()
        # Promote to memory cache
        memory_cache.set(cache_key, data)
        return data
    
    if PROMETHEUS_AVAILABLE:
        CACHE_MISSES.inc()
    
    # Check for request deduplication
    if cache_key in request_deduplication:
        logger.debug(f'Waiting for ongoing request: {url}')
        request_deduplication[cache_key].wait(timeout=REQUEST_TIMEOUT)
        # Try caches again after waiting
        data = memory_cache.get(cache_key)
        if data is not None:
            return data
        data = _file_cache_get(cache_key)
        if data is not None:
            memory_cache.set(cache_key, data)
            return data
    
    # Create deduplication event
    request_deduplication[cache_key] = threading.Event()
    
    try:
        # Make upstream request through circuit breaker
        data = circuit_breaker.call(_upstream_request, url, params)
        
        # Cache the result
        memory_cache.set(cache_key, data)
        _file_cache_set(cache_key, data)
        
        logger.info(f'Upstream request successful for {url}')
        return data
        
    finally:
        # Signal other waiting requests
        event = request_deduplication.pop(cache_key, None)
        if event:
            event.set()


def _require_token():
    """Check authentication token"""
    if not PROXY_TOKEN:
        return
    
    token = request.headers.get('X-Proxy-Token') or request.args.get('proxy_token')
    if not token or token != PROXY_TOKEN:
        abort(401, 'Missing or invalid proxy token')


def _track_request(endpoint: str):
    """Decorator for request tracking and metrics"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            global active_requests
            
            client_id = _get_client_id()
            start_time = time.time()
            
            # Rate limiting
            if not rate_limiter.is_allowed(client_id):
                abort(429, 'Rate limit exceeded')
            
            active_requests += 1
            if PROMETHEUS_AVAILABLE:
                ACTIVE_REQUESTS.set(active_requests)
                MEMORY_CACHE_SIZE_GAUGE.set(memory_cache.size())
            
            try:
                result = func(*args, **kwargs)
                
                if PROMETHEUS_AVAILABLE:
                    REQUEST_COUNTER.labels(endpoint=endpoint, status='success').inc()
                    REQUEST_DURATION.labels(endpoint=endpoint).observe(time.time() - start_time)
                
                return result
                
            except HTTPException as e:
                error_tracker.record_error('http_error', endpoint)
                if PROMETHEUS_AVAILABLE:
                    REQUEST_COUNTER.labels(endpoint=endpoint, status='error').inc()
                    UPSTREAM_ERRORS.labels(error_type='http_error').inc()
                raise
            except Exception as e:
                error_tracker.record_error('internal_error', endpoint)
                logger.exception(f'Internal error in {endpoint}')
                if PROMETHEUS_AVAILABLE:
                    REQUEST_COUNTER.labels(endpoint=endpoint, status='error').inc()
                    UPSTREAM_ERRORS.labels(error_type='internal_error').inc()
                abort(500, 'Internal server error')
            finally:
                active_requests -= 1
                if PROMETHEUS_AVAILABLE:
                    ACTIVE_REQUESTS.set(active_requests)
        
        return wrapper
    return decorator


@app.route('/api/health')
@_track_request('/api/health')
def health():
    """Enhanced health endpoint with detailed system status"""
    status = {
        'status': 'ok',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '2.0.0',
        'uptime': time.time() - app.start_time if hasattr(app, 'start_time') else 0,
        'cache': {
            'memory_size': memory_cache.size(),
            'memory_stats': memory_cache.stats,
            'file_cache_dir': CACHE_DIR,
            'ttl': CACHE_TTL
        },
        'circuit_breaker': {
            'state': circuit_breaker.state.state,
            'failures': circuit_breaker.state.failures,
            'last_failure': circuit_breaker.state.last_failure
        },
        'rate_limiting': {
            'requests_per_window': RATE_LIMIT_REQUESTS,
            'window_seconds': RATE_LIMIT_WINDOW,
            'burst_size': RATE_LIMIT_BURST
        },
        'active_requests': active_requests,
        'error_summary': error_tracker.get_error_summary()
    }
    
    # Add system metrics if available
    if PSUTIL_AVAILABLE:
        try:
            status['system'] = {
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent,
                'load_average': os.getloadavg()
            }
        except Exception:
            pass
    
    # Check if system is healthy
    error_rate = error_tracker.get_error_rate()
    if (error_rate > MAX_ERROR_RATE or 
        circuit_breaker.state.state == 'OPEN' or
        active_requests > 50):
        status['status'] = 'degraded'
        return jsonify(status), 503
    
    return jsonify(status)


if PROMETHEUS_AVAILABLE:
    @app.route('/metrics')
    def metrics():
        """Prometheus metrics endpoint"""
        return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}


@app.route('/api/weather')
@_track_request('/api/weather')
def weather():
    """Weather endpoint with enhanced error handling"""
    _require_token()
    
    if not OPENWEATHER_KEY:
        abort(500, 'OpenWeather API key not configured')
    
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    
    if not lat or not lon:
        abort(400, 'lat and lon parameters required')
    
    try:
        lat_f = float(lat)
        lon_f = float(lon)
        if not (-90 <= lat_f <= 90) or not (-180 <= lon_f <= 180):
            abort(400, 'Invalid lat/lon coordinates')
    except ValueError:
        abort(400, 'lat and lon must be valid numbers')
    
    params = {
        'lat': lat,
        'lon': lon,
        'appid': OPENWEATHER_KEY,
        'units': 'metric'
    }
    
    try:
        data = _cached_get(f'{OW_BASE}/weather', params)
        return jsonify(data)
    except Exception as e:
        logger.exception('Error fetching weather data')
        error_tracker.record_error('upstream_error', '/api/weather')
        abort(502, 'Unable to fetch weather data')


@app.route('/api/forecast')
@_track_request('/api/forecast')
def forecast():
    """Forecast endpoint with enhanced error handling"""
    _require_token()
    
    if not OPENWEATHER_KEY:
        abort(500, 'OpenWeather API key not configured')
    
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    
    if not lat or not lon:
        abort(400, 'lat and lon parameters required')
    
    try:
        lat_f = float(lat)
        lon_f = float(lon)
        if not (-90 <= lat_f <= 90) or not (-180 <= lon_f <= 180):
            abort(400, 'Invalid lat/lon coordinates')
    except ValueError:
        abort(400, 'lat and lon must be valid numbers')
    
    params = {
        'lat': lat,
        'lon': lon,
        'appid': OPENWEATHER_KEY,
        'units': 'metric'
    }
    
    try:
        data = _cached_get(f'{OW_BASE}/forecast', params)
        return jsonify(data)
    except Exception as e:
        logger.exception('Error fetching forecast data')
        error_tracker.record_error('upstream_error', '/api/forecast')
        abort(502, 'Unable to fetch forecast data')


@app.route('/api/cache/clear', methods=['POST'])
@_track_request('/api/cache/clear')
def clear_cache():
    """Clear all caches (requires admin token)"""
    _require_token()
    
    try:
        # Clear memory cache
        memory_cache.clear()
        
        # Clear file cache
        if CACHE_DIR and os.path.exists(CACHE_DIR):
            import shutil
            shutil.rmtree(CACHE_DIR)
            os.makedirs(CACHE_DIR, exist_ok=True)
        
        logger.info('Cache cleared successfully')
        return jsonify({'status': 'Cache cleared'})
    except Exception as e:
        logger.exception('Error clearing cache')
        abort(500, 'Failed to clear cache')


@app.route('/api/circuit-breaker/reset', methods=['POST'])
@_track_request('/api/circuit-breaker/reset')
def reset_circuit_breaker():
    """Reset circuit breaker (requires admin token)"""
    _require_token()
    
    with circuit_breaker.lock:
        circuit_breaker.state = CircuitBreakerState()
        logger.info('Circuit breaker reset')
    
    return jsonify({'status': 'Circuit breaker reset'})


@app.errorhandler(Exception)
def handle_exception(e):
    """Global exception handler"""
    if isinstance(e, HTTPException):
        return e
    
    logger.exception('Unhandled exception')
    error_tracker.record_error('unhandled_exception', request.endpoint or 'unknown')
    
    return jsonify({'error': 'Internal server error'}), 500


def graceful_shutdown(signum, frame):
    """Handle graceful shutdown"""
    logger.info(f'Received signal {signum}, shutting down gracefully...')
    # Add cleanup logic here if needed
    sys.exit(0)


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    signal.signal(signal.SIGTERM, graceful_shutdown)
    signal.signal(signal.SIGINT, graceful_shutdown)


if __name__ == '__main__':
    app.start_time = time.time()
    setup_signal_handlers()
    
    logger.info('Starting WeatherPi Enhanced Proxy Server')
    logger.info(f'Cache TTL: {CACHE_TTL}s, Memory cache: {MEMORY_CACHE_SIZE} items')
    logger.info(f'Rate limit: {RATE_LIMIT_REQUESTS} req/{RATE_LIMIT_WINDOW}s')
    logger.info(f'Circuit breaker threshold: {CIRCUIT_FAILURE_THRESHOLD} failures')
    
    # Development server (production should use gunicorn)
    app.run(host='0.0.0.0', port=8000, debug=False, threaded=True)