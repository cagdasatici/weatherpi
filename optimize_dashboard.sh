#!/bin/bash
# Optimize Health Dashboard for Minimal Resource Usage

ssh weatherpi << 'EOF'
    # Create optimized health dashboard config
    tee /home/cagdas/health_dashboard_optimized.py > /dev/null << 'SCRIPT'
# Add these optimizations to the health dashboard
import gc
import time

# Memory optimization
gc.set_threshold(100, 10, 5)  # More aggressive garbage collection

# Reduce refresh intervals
DEFAULT_REFRESH = 60  # 60 seconds instead of 30
MAX_LOG_ENTRIES = 10  # Reduce from 20

# Cache system data to reduce calls
class CachedSystemInfo:
    def __init__(self):
        self.cache = {}
        self.cache_timeout = 30
    
    def get_cached_or_fresh(self, key, fetch_func):
        now = time.time()
        if key in self.cache:
            data, timestamp = self.cache[key]
            if now - timestamp < self.cache_timeout:
                return data
        
        data = fetch_func()
        self.cache[key] = (data, now)
        return data

# Use this for system calls to reduce CPU load
SCRIPT

    echo "📊 Dashboard optimization options:"
    echo "1. Increase refresh interval to 60s (current: 30s)"
    echo "2. Reduce log entries to 10 (current: 20)" 
    echo "3. Enable aggressive caching"
    echo "4. Disable dashboard entirely if not needed"
    echo
    echo "Current impact: ~25MB RAM, ~0.5% CPU - very reasonable for monitoring"
EOF