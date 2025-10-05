#!/usr/bin/env python3
"""
Tests for the Working Enhanced Proxy Server
===========================================
"""

import pytest
import time
import tempfile
import shutil
import os
import json
from unittest.mock import patch, MagicMock
import sys

# Import the working app
sys.path.append('/Users/cagdasatici/Documents/GitHub/weatherpi/server')
from app_working import app, memory_cache, circuit_breaker, rate_limiter, error_tracker


@pytest.fixture
def client():
    """Flask test client"""
    app.config['TESTING'] = True
    app.config['OPENWEATHER_API_KEY'] = 'test_api_key'
    app.config['PROXY_TOKEN'] = 'test_token'
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_env():
    """Mock environment variables"""
    with patch.dict(os.environ, {
        'OPENWEATHER_API_KEY': 'test_api_key',
        'PROXY_TOKEN': 'test_token',
        'CACHE_TTL': '300',
        'MEMORY_CACHE_SIZE': '10',
        'CIRCUIT_FAILURE_THRESHOLD': '3',
        'RATE_LIMIT_REQUESTS': '5',
        'RATE_LIMIT_WINDOW': '60'
    }):
        yield


class TestBasicFunctionality:
    """Test basic functionality"""
    
    def test_health_endpoint(self, client):
        response = client.get('/api/health')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['status'] in ['ok', 'degraded']
        assert 'timestamp' in data
        assert 'cache' in data
    
    def test_metrics_endpoint(self, client):
        response = client.get('/metrics')
        assert response.status_code == 200
        assert 'text/plain' in response.headers['Content-Type']


class TestAuthentication:
    """Test authentication"""
    
    def test_weather_requires_token(self, client, mock_env):
        response = client.get('/api/weather?lat=40.7128&lon=-74.0060')
        assert response.status_code == 401
    
    def test_weather_with_valid_token(self, client, mock_env):
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'temp': 20}
            mock_get.return_value = mock_response
            
            response = client.get(
                '/api/weather?lat=40.7128&lon=-74.0060',
                headers={'X-Proxy-Token': 'test_token'}
            )
            assert response.status_code == 200


class TestValidation:
    """Test input validation"""
    
    def test_weather_validates_coordinates(self, client, mock_env):
        # Missing coordinates
        response = client.get(
            '/api/weather',
            headers={'X-Proxy-Token': 'test_token'}
        )
        assert response.status_code == 400
        
        # Invalid latitude
        response = client.get(
            '/api/weather?lat=invalid&lon=-74.0060',
            headers={'X-Proxy-Token': 'test_token'}
        )
        assert response.status_code == 400
        
        # Out of range coordinates
        response = client.get(
            '/api/weather?lat=91&lon=-74.0060',
            headers={'X-Proxy-Token': 'test_token'}
        )
        assert response.status_code == 400


class TestMemoryCache:
    """Test memory cache functionality"""
    
    def test_cache_basic_operations(self):
        from app_working import MemoryCache
        cache = MemoryCache(max_size=3, ttl=60)
        
        # Set and get
        cache.set('key1', 'value1')
        assert cache.get('key1') == 'value1'
        assert cache.get('nonexistent') is None
    
    def test_cache_ttl_expiry(self):
        from app_working import MemoryCache
        cache = MemoryCache(max_size=3, ttl=1)  # 1 second TTL
        
        cache.set('key1', 'value1')
        assert cache.get('key1') == 'value1'
        
        time.sleep(1.1)
        assert cache.get('key1') is None
    
    def test_cache_lru_eviction(self):
        from app_working import MemoryCache
        cache = MemoryCache(max_size=2, ttl=60)
        
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.set('key3', 'value3')  # Should evict key1
        
        assert cache.get('key1') is None
        assert cache.get('key2') == 'value2'
        assert cache.get('key3') == 'value3'


class TestCircuitBreaker:
    """Test circuit breaker"""
    
    def test_circuit_breaker_success(self):
        from app_working import CircuitBreaker
        cb = CircuitBreaker()
        
        def success_func():
            return "success"
        
        result = cb.call(success_func)
        assert result == "success"
        assert cb.state.state == "CLOSED"
    
    def test_circuit_breaker_opens_on_failures(self):
        from app_working import CircuitBreaker
        cb = CircuitBreaker()
        
        def failing_func():
            raise Exception("Test failure")
        
        # Trigger enough failures to open circuit
        for _ in range(5):  # More than threshold
            with pytest.raises(Exception):
                cb.call(failing_func)
        
        assert cb.state.state == "OPEN"


class TestRateLimiter:
    """Test rate limiter"""
    
    def test_rate_limiter_allows_within_limit(self):
        from app_working import RateLimiter
        rl = RateLimiter()
        
        # Should allow requests within limit
        for i in range(5):  # Default limit
            assert rl.is_allowed('client1') is True
    
    def test_rate_limiter_blocks_over_limit(self):
        from app_working import RateLimiter
        rl = RateLimiter()
        
        # Use up the limit
        for i in range(60):  # Default limit
            rl.is_allowed('client1')
        
        # Next request should be blocked
        assert rl.is_allowed('client1') is False


class TestErrorTracking:
    """Test error tracking"""
    
    def test_error_tracking(self):
        from app_working import ErrorTracker
        et = ErrorTracker()
        
        et.record_error('http_error', '/api/weather')
        et.record_error('timeout', '/api/forecast')
        
        # Should have recorded errors
        assert len(et.errors) == 2
    
    def test_error_rate_calculation(self):
        from app_working import ErrorTracker
        et = ErrorTracker()
        
        # Record some errors
        for i in range(5):
            et.record_error('test_error', '/test')
        
        error_rate = et.get_error_rate(window_seconds=60)
        assert error_rate > 0


class TestCacheManagement:
    """Test cache management endpoints"""
    
    def test_cache_clear_endpoint(self, client, mock_env):
        response = client.post(
            '/api/cache/clear',
            headers={'X-Proxy-Token': 'test_token'}
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'Cache cleared' in data['status']
    
    def test_circuit_breaker_reset_endpoint(self, client, mock_env):
        response = client.post(
            '/api/circuit-breaker/reset',
            headers={'X-Proxy-Token': 'test_token'}
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'Circuit breaker reset' in data['status']


class TestIntegration:
    """Integration tests"""
    
    def test_successful_weather_request(self, client, mock_env):
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'main': {'temp': 20.5},
                'weather': [{'description': 'clear sky'}]
            }
            mock_get.return_value = mock_response
            
            response = client.get(
                '/api/weather?lat=40.7128&lon=-74.0060',
                headers={'X-Proxy-Token': 'test_token'}
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'main' in data
            assert data['main']['temp'] == 20.5
    
    def test_forecast_request(self, client, mock_env):
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'list': [{'main': {'temp': 22.0}}]
            }
            mock_get.return_value = mock_response
            
            response = client.get(
                '/api/forecast?lat=40.7128&lon=-74.0060',
                headers={'X-Proxy-Token': 'test_token'}
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'list' in data


if __name__ == '__main__':
    pytest.main([__file__, '-v'])