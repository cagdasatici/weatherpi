#!/usr/bin/env python3
"""
WeatherPi Performance Monitor and Load Tester
==============================================

Features:
- Real-time performance monitoring
- Load testing capabilities
- Latency analysis
- Circuit breaker testing
- Rate limiting validation
- Cache performance evaluation
- Stress testing scenarios
"""

import asyncio
import aiohttp
import time
import statistics
import argparse
import json
import sys
from datetime import datetime
from typing import List, Dict, Any
from dataclasses import dataclass, asdict
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class RequestResult:
    timestamp: float
    status_code: int
    response_time: float
    size: int
    error: str = ""


@dataclass
class PerformanceMetrics:
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    p50_response_time: float
    p95_response_time: float
    p99_response_time: float
    requests_per_second: float
    error_rate: float
    errors_by_type: Dict[str, int]
    status_codes: Dict[int, int]


class PerformanceMonitor:
    """Monitor performance and collect metrics"""
    
    def __init__(self, base_url: str, proxy_token: str = ""):
        self.base_url = base_url.rstrip('/')
        self.proxy_token = proxy_token
        self.results: List[RequestResult] = []
        self.start_time = None
        self.end_time = None
    
    async def make_request(self, session: aiohttp.ClientSession, endpoint: str, 
                          params: Dict[str, Any] = None) -> RequestResult:
        """Make a single request and record metrics"""
        headers = {}
        if self.proxy_token:
            headers['X-Proxy-Token'] = self.proxy_token
        
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        try:
            async with session.get(url, params=params, headers=headers) as response:
                content = await response.read()
                end_time = time.time()
                
                return RequestResult(
                    timestamp=start_time,
                    status_code=response.status,
                    response_time=end_time - start_time,
                    size=len(content),
                    error=""
                )
        except Exception as e:
            end_time = time.time()
            return RequestResult(
                timestamp=start_time,
                status_code=0,
                response_time=end_time - start_time,
                size=0,
                error=str(e)
            )
    
    async def run_load_test(self, endpoint: str, params: Dict[str, Any] = None,
                           concurrent_users: int = 10, duration: int = 60,
                           requests_per_user: int = None) -> PerformanceMetrics:
        """Run a load test scenario"""
        logger.info(f"Starting load test: {concurrent_users} users, {duration}s duration")
        
        self.results = []
        self.start_time = time.time()
        
        connector = aiohttp.TCPConnector(limit=100)
        timeout = aiohttp.ClientTimeout(total=30)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            tasks = []
            
            if requests_per_user:
                # Fixed number of requests per user
                for user_id in range(concurrent_users):
                    task = asyncio.create_task(
                        self._user_fixed_requests(session, endpoint, params, requests_per_user)
                    )
                    tasks.append(task)
            else:
                # Time-based test
                for user_id in range(concurrent_users):
                    task = asyncio.create_task(
                        self._user_time_based(session, endpoint, params, duration)
                    )
                    tasks.append(task)
            
            # Wait for all tasks to complete
            await asyncio.gather(*tasks, return_exceptions=True)
        
        self.end_time = time.time()
        return self._calculate_metrics()
    
    async def _user_fixed_requests(self, session: aiohttp.ClientSession, 
                                  endpoint: str, params: Dict[str, Any],
                                  num_requests: int):
        """Simulate a user making a fixed number of requests"""
        for _ in range(num_requests):
            result = await self.make_request(session, endpoint, params)
            self.results.append(result)
            
            # Small delay between requests
            await asyncio.sleep(0.1)
    
    async def _user_time_based(self, session: aiohttp.ClientSession,
                              endpoint: str, params: Dict[str, Any],
                              duration: int):
        """Simulate a user making requests for a specific duration"""
        end_time = time.time() + duration
        
        while time.time() < end_time:
            result = await self.make_request(session, endpoint, params)
            self.results.append(result)
            
            # Small delay between requests
            await asyncio.sleep(0.1)
    
    def _calculate_metrics(self) -> PerformanceMetrics:
        """Calculate performance metrics from results"""
        if not self.results:
            return PerformanceMetrics(
                total_requests=0, successful_requests=0, failed_requests=0,
                avg_response_time=0, min_response_time=0, max_response_time=0,
                p50_response_time=0, p95_response_time=0, p99_response_time=0,
                requests_per_second=0, error_rate=0,
                errors_by_type={}, status_codes={}
            )
        
        total_requests = len(self.results)
        successful_requests = sum(1 for r in self.results if 200 <= r.status_code < 300)
        failed_requests = total_requests - successful_requests
        
        response_times = [r.response_time for r in self.results]
        avg_response_time = statistics.mean(response_times)
        min_response_time = min(response_times)
        max_response_time = max(response_times)
        
        # Percentiles
        sorted_times = sorted(response_times)
        p50_response_time = sorted_times[int(len(sorted_times) * 0.5)]
        p95_response_time = sorted_times[int(len(sorted_times) * 0.95)]
        p99_response_time = sorted_times[int(len(sorted_times) * 0.99)]
        
        # Requests per second
        duration = self.end_time - self.start_time if self.end_time and self.start_time else 1
        requests_per_second = total_requests / duration
        
        # Error analysis
        error_rate = failed_requests / total_requests
        errors_by_type = {}
        status_codes = {}
        
        for result in self.results:
            if result.error:
                errors_by_type[result.error] = errors_by_type.get(result.error, 0) + 1
            status_codes[result.status_code] = status_codes.get(result.status_code, 0) + 1
        
        return PerformanceMetrics(
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time=avg_response_time,
            min_response_time=min_response_time,
            max_response_time=max_response_time,
            p50_response_time=p50_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            requests_per_second=requests_per_second,
            error_rate=error_rate,
            errors_by_type=errors_by_type,
            status_codes=status_codes
        )
    
    async def test_circuit_breaker(self) -> Dict[str, Any]:
        """Test circuit breaker functionality"""
        logger.info("Testing circuit breaker behavior...")
        
        # First, ensure circuit is closed by making successful requests
        connector = aiohttp.TCPConnector(limit=10)
        async with aiohttp.ClientSession(connector=connector) as session:
            # Test with health endpoint first (should always work)
            for _ in range(3):
                result = await self.make_request(session, '/api/health')
                if result.status_code != 200:
                    logger.warning("Health endpoint not responding properly")
            
            # Now try to trigger circuit breaker with invalid requests
            # (These should fail and increment the failure counter)
            circuit_breaker_results = []
            
            # Make requests that should fail (invalid coordinates)
            for i in range(10):
                params = {'lat': 'invalid', 'lon': 'invalid'}
                result = await self.make_request(session, '/api/weather', params)
                circuit_breaker_results.append(result)
                
                if i > 5:  # After several failures, check circuit state
                    health_result = await self.make_request(session, '/api/health')
                    if health_result.status_code == 200:
                        try:
                            health_data = json.loads(await (await session.get(
                                f"{self.base_url}/api/health"
                            )).text())
                            if health_data.get('circuit_breaker', {}).get('state') == 'OPEN':
                                logger.info(f"Circuit breaker opened after {i+1} failures")
                                break
                        except:
                            pass
                
                await asyncio.sleep(0.1)
        
        return {
            'circuit_breaker_test': 'completed',
            'failed_requests': len([r for r in circuit_breaker_results if r.status_code >= 400])
        }
    
    async def test_rate_limiting(self, requests_per_second: int = 20) -> Dict[str, Any]:
        """Test rate limiting functionality"""
        logger.info(f"Testing rate limiting with {requests_per_second} req/s...")
        
        rate_limit_results = []
        connector = aiohttp.TCPConnector(limit=10)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            # Make rapid requests to trigger rate limiting
            start_time = time.time()
            
            while time.time() - start_time < 5:  # 5 seconds of rapid requests
                result = await self.make_request(session, '/api/health')
                rate_limit_results.append(result)
                
                # Control the rate
                await asyncio.sleep(1.0 / requests_per_second)
        
        rate_limited_count = sum(1 for r in rate_limit_results if r.status_code == 429)
        
        return {
            'rate_limit_test': 'completed',
            'total_requests': len(rate_limit_results),
            'rate_limited_requests': rate_limited_count,
            'rate_limit_percentage': rate_limited_count / len(rate_limit_results) * 100
        }
    
    async def test_cache_performance(self) -> Dict[str, Any]:
        """Test cache performance"""
        logger.info("Testing cache performance...")
        
        cache_test_results = {'cold': [], 'warm': []}
        connector = aiohttp.TCPConnector(limit=10)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            # Clear cache first
            if self.proxy_token:
                headers = {'X-Proxy-Token': self.proxy_token}
                await session.post(f"{self.base_url}/api/cache/clear", headers=headers)
            
            # Cold cache test (first requests)
            params = {'lat': '40.7128', 'lon': '-74.0060'}
            for _ in range(5):
                result = await self.make_request(session, '/api/weather', params)
                cache_test_results['cold'].append(result.response_time)
                await asyncio.sleep(0.1)
            
            # Warm cache test (repeated requests)
            for _ in range(5):
                result = await self.make_request(session, '/api/weather', params)
                cache_test_results['warm'].append(result.response_time)
                await asyncio.sleep(0.1)
        
        cold_avg = statistics.mean(cache_test_results['cold']) if cache_test_results['cold'] else 0
        warm_avg = statistics.mean(cache_test_results['warm']) if cache_test_results['warm'] else 0
        
        return {
            'cache_test': 'completed',
            'cold_cache_avg_time': cold_avg,
            'warm_cache_avg_time': warm_avg,
            'cache_speedup': cold_avg / warm_avg if warm_avg > 0 else 0
        }


def print_metrics(metrics: PerformanceMetrics):
    """Print performance metrics in a formatted way"""
    print("\n" + "="*60)
    print("PERFORMANCE METRICS")
    print("="*60)
    print(f"Total Requests:     {metrics.total_requests:,}")
    print(f"Successful:         {metrics.successful_requests:,} ({metrics.successful_requests/metrics.total_requests*100:.1f}%)")
    print(f"Failed:             {metrics.failed_requests:,} ({metrics.error_rate*100:.1f}%)")
    print(f"Requests/Second:    {metrics.requests_per_second:.2f}")
    print("\nResponse Times (seconds):")
    print(f"  Average:          {metrics.avg_response_time:.3f}")
    print(f"  Minimum:          {metrics.min_response_time:.3f}")
    print(f"  Maximum:          {metrics.max_response_time:.3f}")
    print(f"  50th percentile:  {metrics.p50_response_time:.3f}")
    print(f"  95th percentile:  {metrics.p95_response_time:.3f}")
    print(f"  99th percentile:  {metrics.p99_response_time:.3f}")
    
    if metrics.status_codes:
        print("\nStatus Codes:")
        for code, count in sorted(metrics.status_codes.items()):
            print(f"  {code}: {count:,}")
    
    if metrics.errors_by_type:
        print("\nErrors by Type:")
        for error_type, count in metrics.errors_by_type.items():
            print(f"  {error_type}: {count}")


async def main():
    parser = argparse.ArgumentParser(description='WeatherPi Performance Monitor')
    parser.add_argument('--url', default='http://localhost:8000', 
                       help='Base URL of the proxy server')
    parser.add_argument('--token', default='', 
                       help='Proxy authentication token')
    parser.add_argument('--test', choices=['load', 'circuit', 'rate', 'cache', 'all'],
                       default='all', help='Type of test to run')
    parser.add_argument('--users', type=int, default=10, 
                       help='Number of concurrent users for load test')
    parser.add_argument('--duration', type=int, default=60,
                       help='Duration of load test in seconds')
    parser.add_argument('--requests', type=int, default=None,
                       help='Number of requests per user (overrides duration)')
    parser.add_argument('--endpoint', default='/api/health',
                       help='Endpoint to test')
    parser.add_argument('--output', help='Output file for results (JSON format)')
    
    args = parser.parse_args()
    
    monitor = PerformanceMonitor(args.url, args.token)
    results = {}
    
    print(f"🚀 WeatherPi Performance Monitor")
    print(f"Target: {args.url}")
    print(f"Test Type: {args.test}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    try:
        if args.test in ['load', 'all']:
            print(f"\n📊 Running load test...")
            params = None
            if 'weather' in args.endpoint or 'forecast' in args.endpoint:
                params = {'lat': '40.7128', 'lon': '-74.0060'}
            
            metrics = await monitor.run_load_test(
                args.endpoint, params, args.users, args.duration, args.requests
            )
            print_metrics(metrics)
            results['load_test'] = asdict(metrics)
        
        if args.test in ['circuit', 'all']:
            print(f"\n🔄 Running circuit breaker test...")
            circuit_results = await monitor.test_circuit_breaker()
            print(f"Circuit breaker test results: {circuit_results}")
            results['circuit_breaker_test'] = circuit_results
        
        if args.test in ['rate', 'all']:
            print(f"\n⏱️  Running rate limiting test...")
            rate_results = await monitor.test_rate_limiting()
            print(f"Rate limiting test results: {rate_results}")
            results['rate_limiting_test'] = rate_results
        
        if args.test in ['cache', 'all']:
            print(f"\n💾 Running cache performance test...")
            cache_results = await monitor.test_cache_performance()
            print(f"Cache performance test results: {cache_results}")
            results['cache_test'] = cache_results
        
        # Save results to file if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"\n📄 Results saved to {args.output}")
        
        print(f"\n✅ Performance testing completed!")
        
    except KeyboardInterrupt:
        print(f"\n⏹️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        logger.exception("Test failed")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())