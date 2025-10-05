#!/usr/bin/env python3
"""
Comprehensive Test Suite for WeatherPi Enhanced Proxy Server
===========================================================

Tests:
- Basic functionality
- Circuit breaker behavior
- Rate limiting
- Caching layers
- Error handling
- Authentication
- Performance under load
"""

import pytest
import time
import threading
import tempfile
import shutil
import os
import json
from unittest.mock import patch, MagicMock
import requests

# Import the app and components
import sys
sys.path.append('/Users/cagdasatici/Documents/GitHub/weatherpi/server')

from app_enhanced import (
    app, memory_cache, circuit_breaker, rate_limiter, error_tracker,
    EnhancedMemoryCache, CircuitBreaker, RateLimiter, ErrorTracker
)


@pytest.fixture
def client():
    """Flask test client"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def temp_cache_dir():
    """Temporary cache directory"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


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


class TestEnhancedMemoryCache:
    """Test the enhanced memory cache"""
    
    def test_cache_set_get(self):
        cache = EnhancedMemoryCache(max_size=3, ttl=60)
        
        cache.set('key1', 'value1')
        assert cache.get('key1') == 'value1'
        assert cache.get('nonexistent') is None
    
    def test_cache_ttl_expiry(self):
        cache = EnhancedMemoryCache(max_size=3, ttl=1)  # 1 second TTL
        
        cache.set('key1', 'value1')
        assert cache.get('key1') == 'value1'
        
        time.sleep(1.1)
        assert cache.get('key1') is None
    
    def test_cache_lru_eviction(self):
        cache = EnhancedMemoryCache(max_size=2, ttl=60)
        
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.set('key3', 'value3')  # Should evict key1
        
        assert cache.get('key1') is None
        assert cache.get('key2') == 'value2'
        assert cache.get('key3') == 'value3'
    
    def test_cache_access_ordering(self):
        cache = EnhancedMemoryCache(max_size=2, ttl=60)
        
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.get('key1')  # Access key1 to make it most recent
        cache.set('key3', 'value3')  # Should evict key2, not key1
        
        assert cache.get('key1') == 'value1'
        assert cache.get('key2') is None
        assert cache.get('key3') == 'value3'
    
    def test_cache_stats(self):
        cache = EnhancedMemoryCache(max_size=3, ttl=60)
        
        cache.set('key1', 'value1')
        cache.get('key1')  # Hit
        cache.get('key2')  # Miss
        
        assert cache.stats['hits'] == 1
        assert cache.stats['misses'] == 1


class TestCircuitBreaker:
    """Test the circuit breaker"""
    
    def test_circuit_breaker_closed_state(self):
        cb = CircuitBreaker()
        
        def success_func():
            return "success"
        
        result = cb.call(success_func)
        assert result == "success"
        assert cb.state.state == "CLOSED"
    
    def test_circuit_breaker_opens_on_failures(self):
        cb = CircuitBreaker()
        cb.state.failures = 2  # Set to 2, next failure should open
        
        def failing_func():
            raise Exception("Test failure")
        
        # This should open the circuit
        with pytest.raises(Exception):
            cb.call(failing_func)
        
        assert cb.state.state == "OPEN"
        assert cb.state.failures >= 3
    
    def test_circuit_breaker_open_state_blocks_calls(self):
        cb = CircuitBreaker()
        cb.state.state = "OPEN"
        cb.state.last_failure = time.time()
        
        def any_func():
            return "should not execute"
        
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            cb.call(any_func)
    
    def test_circuit_breaker_half_open_recovery(self):
        cb = CircuitBreaker()
        cb.state.state = "OPEN"
        cb.state.last_failure = time.time() - 70  # 70 seconds ago (recovery timeout is 60)
        
        def success_func():
            return "success"
        
        result = cb.call(success_func)
        assert result == "success"
        assert cb.state.state == "CLOSED"


class TestRateLimiter:
    """Test the rate limiter"""
    
    def test_rate_limiter_allows_within_limit(self):
        rl = RateLimiter()
        
        for i in range(5):  # RATE_LIMIT_REQUESTS = 5
            assert rl.is_allowed('client1') is True
    
    def test_rate_limiter_blocks_over_limit(self):
        rl = RateLimiter()
        
        # Use up the limit
        for i in range(5):
            rl.is_allowed('client1')
        
        # Next request should be blocked
        assert rl.is_allowed('client1') is False
    
    def test_rate_limiter_per_client(self):
        rl = RateLimiter()
        
        # Use up limit for client1
        for i in range(5):
            rl.is_allowed('client1')
        
        # client2 should still be allowed
        assert rl.is_allowed('client2') is True


class TestErrorTracker:
    """Test the error tracker"""
    
    def test_error_tracking(self):
        et = ErrorTracker()
        
        et.record_error('http_error', '/api/weather')
        et.record_error('timeout', '/api/forecast')
        
        summary = et.get_error_summary()
        assert summary['total_errors'] == 2
        assert 'http_error' in summary['by_type']
        assert '/api/weather' in summary['by_endpoint']
    
    def test_error_rate_calculation(self):
        et = ErrorTracker()
        
        # Record some errors
        for i in range(5):
            et.record_error('test_error', '/test')
        
        error_rate = et.get_error_rate(window_seconds=60)
        assert error_rate > 0


class TestHealthEndpoint:
    """Test the health endpoint"""
    
    def test_health_endpoint_basic(self, client):
        response = client.get('/api/health')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['status'] in ['ok', 'degraded']
        assert 'timestamp' in data
        assert 'cache' in data
        assert 'circuit_breaker' in data
    
    def test_health_endpoint_degraded_on_high_error_rate(self, client):
        # Inject high error rate
        for i in range(50):
            error_tracker.record_error('test', '/test')
        
        response = client.get('/api/health')
        data = json.loads(response.data)
        
        # Should be degraded due to high error rate
        assert response.status_code == 503 or data['status'] == 'degraded'


class TestAuthenticationRequired:
    """Test authentication requirements"""
    
    def test_weather_endpoint_requires_token(self, client, mock_env):
        response = client.get('/api/weather?lat=40.7128&lon=-74.0060')
        assert response.status_code == 401
    
    def test_weather_endpoint_with_valid_token(self, client, mock_env):
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
    
    def test_weather_endpoint_with_invalid_token(self, client, mock_env):
        response = client.get(
            '/api/weather?lat=40.7128&lon=-74.0060',
            headers={'X-Proxy-Token': 'wrong_token'}
        )
        assert response.status_code == 401


class TestWeatherEndpoint:
    """Test weather endpoint functionality"""
    
    def test_weather_endpoint_validates_coordinates(self, client, mock_env):
        response = client.get(
            '/api/weather',
            headers={'X-Proxy-Token': 'test_token'}
        )
        assert response.status_code == 400  # Missing lat/lon
        
        response = client.get(
            '/api/weather?lat=invalid&lon=-74.0060',
            headers={'X-Proxy-Token': 'test_token'}
        )
        assert response.status_code == 400  # Invalid lat
        
        response = client.get(
            '/api/weather?lat=91&lon=-74.0060',
            headers={'X-Proxy-Token': 'test_token'}
        )
        assert response.status_code == 400  # Out of range lat
    
    def test_weather_endpoint_successful_request(self, client, mock_env):
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


class TestCaching:
    """Test caching functionality"""
    
    def test_memory_cache_integration(self, client, mock_env, temp_cache_dir):
        with patch.dict(os.environ, {'CACHE_DIR': temp_cache_dir}):
            with patch('requests.get') as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {'temp': 20}
                mock_get.return_value = mock_response
                
                # First request - should hit upstream
                response1 = client.get(
                    '/api/weather?lat=40.7128&lon=-74.0060',
                    headers={'X-Proxy-Token': 'test_token'}
                )
                assert response1.status_code == 200
                assert mock_get.call_count == 1
                
                # Second request - should hit cache
                response2 = client.get(
                    '/api/weather?lat=40.7128&lon=-74.0060',
                    headers={'X-Proxy-Token': 'test_token'}
                )
                assert response2.status_code == 200
                assert mock_get.call_count == 1  # No additional call
    
    def test_file_cache_integration(self, client, mock_env, temp_cache_dir):
        with patch.dict(os.environ, {'CACHE_DIR': temp_cache_dir}):
            # Clear memory cache to test file cache
            memory_cache.clear()
            
            with patch('requests.get') as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {'temp': 20}
                mock_get.return_value = mock_response
                
                # First request
                client.get(
                    '/api/weather?lat=40.7128&lon=-74.0060',
                    headers={'X-Proxy-Token': 'test_token'}
                )
                
                # Clear memory cache but keep file cache
                memory_cache.clear()
                
                # Second request should hit file cache
                response = client.get(
                    '/api/weather?lat=40.7128&lon=-74.0060',
                    headers={'X-Proxy-Token': 'test_token'}
                )
                assert response.status_code == 200


class TestRateLimitingIntegration:
    """Test rate limiting integration"""
    
    def test_rate_limiting_blocks_excessive_requests(self, client, mock_env):
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'temp': 20}
            mock_get.return_value = mock_response
            
            # Make requests up to the limit
            for i in range(5):  # RATE_LIMIT_REQUESTS = 5
                response = client.get(
                    f'/api/weather?lat=40.{i}&lon=-74.0060',
                    headers={'X-Proxy-Token': 'test_token'}
                )
                assert response.status_code == 200
            
            # Next request should be rate limited
            response = client.get(
                '/api/weather?lat=40.9999&lon=-74.0060',
                headers={'X-Proxy-Token': 'test_token'}
            )
            assert response.status_code == 429


class TestCircuitBreakerIntegration:
    """Test circuit breaker integration"""
    
    def test_circuit_breaker_opens_on_repeated_failures(self, client, mock_env):
        with patch('requests.get') as mock_get:
            # Mock to raise exception (simulate upstream failure)
            mock_get.side_effect = requests.RequestException("Upstream failed")
            
            # Make requests to trigger circuit breaker
            for i in range(5):  # More than threshold
                response = client.get(
                    f'/api/weather?lat=40.{i}&lon=-74.0060',
                    headers={'X-Proxy-Token': 'test_token'}
                )
                assert response.status_code == 502  # Upstream error
            
            # Circuit breaker should now be open
            assert circuit_breaker.state.state == "OPEN"


class TestMetricsEndpoint:
    """Test Prometheus metrics endpoint"""
    
    def test_metrics_endpoint_available(self, client):
        response = client.get('/metrics')
        assert response.status_code == 200
        assert response.headers['Content-Type'] == 'text/plain; version=0.0.4; charset=utf-8'


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
        # Set circuit breaker to open state
        circuit_breaker.state.state = "OPEN"
        circuit_breaker.state.failures = 10
        
        response = client.post(
            '/api/circuit-breaker/reset',
            headers={'X-Proxy-Token': 'test_token'}
        )
        assert response.status_code == 200
        
        # Circuit breaker should be reset
        assert circuit_breaker.state.state == "CLOSED"
        assert circuit_breaker.state.failures == 0


class TestErrorHandling:
    """Test error handling"""
    
    def test_upstream_timeout_handling(self, client, mock_env):
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.Timeout("Request timeout")
            
            response = client.get(
                '/api/weather?lat=40.7128&lon=-74.0060',
                headers={'X-Proxy-Token': 'test_token'}
            )
            assert response.status_code == 502
    
    def test_upstream_error_retry(self, client, mock_env):
        with patch('requests.get') as mock_get:
            # First call fails, second succeeds
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'temp': 20}
            
            mock_get.side_effect = [
                requests.RequestException("First failure"),
                mock_response
            ]
            
            response = client.get(
                '/api/weather?lat=40.7128&lon=-74.0060',
                headers={'X-Proxy-Token': 'test_token'}
            )
            assert response.status_code == 200
            assert mock_get.call_count == 2  # Retry occurred


class TestConcurrency:
    """Test concurrent request handling"""
    
    def test_concurrent_requests(self, client, mock_env):
        """Test handling multiple concurrent requests"""
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'temp': 20}
            mock_get.return_value = mock_response
            
            results = []
            errors = []
            
            def make_request():
                try:
                    response = client.get(
                        '/api/weather?lat=40.7128&lon=-74.0060',
                        headers={'X-Proxy-Token': 'test_token'}
                    )
                    results.append(response.status_code)
                except Exception as e:
                    errors.append(e)
            
            # Create multiple threads
            threads = []
            for i in range(10):
                thread = threading.Thread(target=make_request)
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            # All requests should succeed
            assert len(errors) == 0
            assert all(status == 200 for status in results)


class TestPerformance:
    """Test performance characteristics"""
    
    def test_response_time_reasonable(self, client, mock_env):
        """Test that response times are reasonable"""
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'temp': 20}
            mock_get.return_value = mock_response
            
            start_time = time.time()
            response = client.get(
                '/api/weather?lat=40.7128&lon=-74.0060',
                headers={'X-Proxy-Token': 'test_token'}
            )
            end_time = time.time()
            
            assert response.status_code == 200
            assert (end_time - start_time) < 1.0  # Should respond within 1 second


if __name__ == '__main__':
    # Run the tests
    pytest.main([
        __file__,
        '-v',
        '--tb=short',
        '--durations=10'
    ])