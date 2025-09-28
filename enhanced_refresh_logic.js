/**
 * Enhanced Weather Data Refresh Logic
 * Gets more aggressive as data ages while maintaining reliability
 */

class SmartWeatherRefresh {
    constructor() {
        this.baseInterval = 5 * 60 * 1000;      // 5 minutes baseline
        this.currentInterval = this.baseInterval;
        this.lastUpdateTime = null;
        this.refreshTimer = null;
        this.failureCount = 0;
        this.maxFailures = 3;
        
        // Escalation thresholds (in minutes)
        this.thresholds = {
            normal: 15,      // < 15min: normal refresh
            stale: 30,       // 15-30min: increase frequency  
            urgent: 60,      // 30-60min: urgent mode
            critical: 120    // > 60min: critical mode
        };
        
        this.intervals = {
            normal: 5 * 60 * 1000,      // 5 minutes
            stale: 2 * 60 * 1000,       // 2 minutes  
            urgent: 1 * 60 * 1000,      // 1 minute
            critical: 30 * 1000         // 30 seconds
        };
    }

    /**
     * Calculate data age and determine refresh strategy
     */
    getDataAge() {
        if (!this.lastUpdateTime) return 0;
        return Math.floor((new Date() - this.lastUpdateTime) / 60000);
    }

    /**
     * Determine refresh mode based on data age
     */
    getRefreshMode(ageMinutes) {
        if (ageMinutes < this.thresholds.normal) return 'normal';
        if (ageMinutes < this.thresholds.stale) return 'stale';
        if (ageMinutes < this.thresholds.urgent) return 'urgent';
        return 'critical';
    }

    /**
     * Get appropriate interval for current data age
     */
    getAdaptiveInterval() {
        const ageMinutes = this.getDataAge();
        const mode = this.getRefreshMode(ageMinutes);
        
        // Apply failure backoff (but not for critical mode)
        let interval = this.intervals[mode];
        if (mode !== 'critical' && this.failureCount > 0) {
            interval *= Math.min(this.failureCount * 1.5, 3); // Max 3x backoff
        }
        
        console.log(`🔄 Refresh mode: ${mode}, age: ${ageMinutes}min, interval: ${interval/1000}s, failures: ${this.failureCount}`);
        return interval;
    }

    /**
     * Enhanced cache indicator with urgency colors
     */
    updateCacheIndicator() {
        const ageMinutes = this.getDataAge();
        const mode = this.getRefreshMode(ageMinutes);
        
        const indicator = document.getElementById('cacheIndicator');
        const text = document.getElementById('cacheIndicatorText');
        
        if (indicator && text) {
            // Update text
            if (ageMinutes < 60) {
                text.textContent = `Data ${ageMinutes}m old`;
            } else {
                const hours = Math.floor(ageMinutes / 60);
                text.textContent = `Data ${hours}h old`;
            }
            
            // Update styling based on urgency
            indicator.className = `cache-indicator ${mode}`;
            
            // Add pulsing animation for urgent/critical
            if (mode === 'urgent' || mode === 'critical') {
                indicator.classList.add('pulse');
            }
            
            indicator.style.display = 'flex';
        }
    }

    /**
     * Enhanced fetch with retry logic and failure tracking
     */
    async enhancedFetch() {
        try {
            console.log(`🌤️  Fetching weather (attempt ${this.failureCount + 1})`);
            
            // Your existing fetchWeather logic here
            const response = await fetch('/weather_data.json');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            
            // Success - reset failure count and update timestamp
            this.failureCount = 0;
            this.lastUpdateTime = new Date();
            
            console.log(`✅ Weather data fetched successfully`);
            return data;
            
        } catch (error) {
            this.failureCount++;
            console.error(`❌ Fetch failed (${this.failureCount}/${this.maxFailures}):`, error.message);
            
            // For critical mode, try alternative endpoints or cached data
            if (this.getRefreshMode(this.getDataAge()) === 'critical') {
                console.log('🚨 Critical mode: Attempting fallback strategies');
                return this.tryFallbackStrategies();
            }
            
            throw error;
        }
    }

    /**
     * Fallback strategies for critical situations
     */
    async tryFallbackStrategies() {
        // Try alternative endpoints, cached data, etc.
        console.log('🔄 Trying fallback strategies...');
        
        // Strategy 1: Try cached data
        const cached = localStorage.getItem('weatherData');
        if (cached) {
            console.log('📦 Using emergency cached data');
            return JSON.parse(cached);
        }
        
        // Strategy 2: Basic weather service
        // Strategy 3: Offline mode
        
        throw new Error('All fallback strategies exhausted');
    }

    /**
     * Start the adaptive refresh system
     */
    start() {
        console.log('🚀 Starting adaptive weather refresh system');
        
        // Initial fetch
        this.enhancedFetch().catch(console.error);
        
        // Set up adaptive timer
        this.scheduleNextRefresh();
        
        // Update cache indicator every minute
        setInterval(() => this.updateCacheIndicator(), 60000);
    }

    /**
     * Schedule next refresh based on current conditions
     */
    scheduleNextRefresh() {
        if (this.refreshTimer) {
            clearTimeout(this.refreshTimer);
        }
        
        const interval = this.getAdaptiveInterval();
        this.currentInterval = interval;
        
        this.refreshTimer = setTimeout(async () => {
            try {
                await this.enhancedFetch();
            } catch (error) {
                console.error('Scheduled refresh failed:', error);
            }
            
            // Schedule next refresh
            this.scheduleNextRefresh();
        }, interval);
        
        console.log(`⏰ Next refresh in ${interval/1000} seconds`);
    }

    /**
     * Force immediate refresh (for manual triggers)
     */
    forceRefresh() {
        console.log('🔄 Force refresh triggered');
        if (this.refreshTimer) {
            clearTimeout(this.refreshTimer);
        }
        
        this.enhancedFetch().then(() => {
            this.scheduleNextRefresh();
        }).catch(console.error);
    }
}

// CSS for enhanced indicators
const enhancedStyles = `
    .cache-indicator.normal {
        background: rgba(76, 175, 80, 0.1);
        border-left: 3px solid #4CAF50;
    }
    
    .cache-indicator.stale {
        background: rgba(255, 193, 7, 0.1);
        border-left: 3px solid #FFC107;
    }
    
    .cache-indicator.urgent {
        background: rgba(255, 152, 0, 0.1);
        border-left: 3px solid #FF9800;
    }
    
    .cache-indicator.critical {
        background: rgba(244, 67, 54, 0.1);
        border-left: 3px solid #F44336;
    }
    
    .cache-indicator.pulse {
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.5; }
        100% { opacity: 1; }
    }
`;

// Usage example:
// const smartRefresh = new SmartWeatherRefresh();
// smartRefresh.start();