#!/usr/bin/env python3
"""
WeatherPi Enhanced Monitoring Dashboard
=======================================

Features:
- Real-time system metrics visualization
- Circuit breaker and rate limiting status
- Cache performance monitoring
- Error tracking and analysis
- Performance profiling
- Alerting system
- Historical data storage
"""

import os
import json
import time
import threading
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import logging

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from flask import Flask, render_template_string, jsonify, request

# Configuration
MONITOR_PORT = int(os.environ.get('MONITOR_PORT', '9001'))
PROXY_URL = os.environ.get('PROXY_URL', 'http://localhost:8000')
UPDATE_INTERVAL = int(os.environ.get('UPDATE_INTERVAL', '5'))
HISTORY_DAYS = int(os.environ.get('HISTORY_DAYS', '7'))
DB_PATH = os.environ.get('DB_PATH', '/var/lib/weatherpi/monitoring.db')
LOG_FILE = os.environ.get('MONITOR_LOG_FILE', '/var/log/weatherpi/monitor.log')

# Setup logging
logger = logging.getLogger('weatherpi-monitor')
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

if LOG_FILE:
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
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
class SystemMetrics:
    timestamp: float
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    load_average: List[float]
    network_io: Dict[str, int]
    temperature: Optional[float] = None


@dataclass
class ProxyMetrics:
    timestamp: float
    status: str
    active_requests: int
    cache_memory_size: int
    cache_memory_hits: int
    cache_memory_misses: int
    circuit_breaker_state: str
    circuit_breaker_failures: int
    error_rate: float
    uptime: float


@dataclass
class Alert:
    timestamp: float
    level: str  # info, warning, error, critical
    component: str
    message: str
    resolved: bool = False


class MonitoringDB:
    """SQLite database for storing monitoring data"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables"""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        except Exception:
            pass
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS system_metrics (
                    timestamp REAL PRIMARY KEY,
                    cpu_percent REAL,
                    memory_percent REAL,
                    disk_percent REAL,
                    load_1m REAL,
                    load_5m REAL,
                    load_15m REAL,
                    temperature REAL
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS proxy_metrics (
                    timestamp REAL PRIMARY KEY,
                    status TEXT,
                    active_requests INTEGER,
                    cache_memory_size INTEGER,
                    cache_hits INTEGER,
                    cache_misses INTEGER,
                    circuit_breaker_state TEXT,
                    circuit_breaker_failures INTEGER,
                    error_rate REAL,
                    uptime REAL
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    level TEXT,
                    component TEXT,
                    message TEXT,
                    resolved INTEGER DEFAULT 0
                )
            ''')
            
            # Create indices for performance
            conn.execute('CREATE INDEX IF NOT EXISTS idx_system_timestamp ON system_metrics(timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_proxy_timestamp ON proxy_metrics(timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp)')
    
    def store_system_metrics(self, metrics: SystemMetrics):
        """Store system metrics"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO system_metrics 
                (timestamp, cpu_percent, memory_percent, disk_percent, 
                 load_1m, load_5m, load_15m, temperature)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                metrics.timestamp, metrics.cpu_percent, metrics.memory_percent,
                metrics.disk_percent, metrics.load_average[0] if len(metrics.load_average) > 0 else 0,
                metrics.load_average[1] if len(metrics.load_average) > 1 else 0,
                metrics.load_average[2] if len(metrics.load_average) > 2 else 0,
                metrics.temperature
            ))
    
    def store_proxy_metrics(self, metrics: ProxyMetrics):
        """Store proxy metrics"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO proxy_metrics
                (timestamp, status, active_requests, cache_memory_size,
                 cache_hits, cache_misses, circuit_breaker_state,
                 circuit_breaker_failures, error_rate, uptime)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                metrics.timestamp, metrics.status, metrics.active_requests,
                metrics.cache_memory_size, metrics.cache_memory_hits,
                metrics.cache_memory_misses, metrics.circuit_breaker_state,
                metrics.circuit_breaker_failures, metrics.error_rate, metrics.uptime
            ))
    
    def store_alert(self, alert: Alert):
        """Store alert"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO alerts (timestamp, level, component, message, resolved)
                VALUES (?, ?, ?, ?, ?)
            ''', (alert.timestamp, alert.level, alert.component, alert.message, alert.resolved))
    
    def get_recent_metrics(self, table: str, hours: int = 1) -> List[Dict]:
        """Get recent metrics from specified table"""
        cutoff = time.time() - (hours * 3600)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(f'''
                SELECT * FROM {table} 
                WHERE timestamp > ? 
                ORDER BY timestamp ASC
            ''', (cutoff,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_recent_alerts(self, hours: int = 24) -> List[Dict]:
        """Get recent alerts"""
        cutoff = time.time() - (hours * 3600)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM alerts 
                WHERE timestamp > ? 
                ORDER BY timestamp DESC
            ''', (cutoff,))
            return [dict(row) for row in cursor.fetchall()]
    
    def cleanup_old_data(self):
        """Remove old data beyond retention period"""
        cutoff = time.time() - (HISTORY_DAYS * 24 * 3600)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM system_metrics WHERE timestamp < ?', (cutoff,))
            conn.execute('DELETE FROM proxy_metrics WHERE timestamp < ?', (cutoff,))
            conn.execute('DELETE FROM alerts WHERE timestamp < ?', (cutoff,))


class SystemMonitor:
    """Collect system metrics"""
    
    def get_metrics(self) -> Optional[SystemMetrics]:
        """Get current system metrics"""
        if not PSUTIL_AVAILABLE:
            return None
        
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            load_avg = os.getloadavg()
            
            # Network I/O
            net_io = psutil.net_io_counters()
            network_io = {
                'bytes_sent': net_io.bytes_sent,
                'bytes_recv': net_io.bytes_recv,
                'packets_sent': net_io.packets_sent,
                'packets_recv': net_io.packets_recv
            }
            
            # Temperature (Raspberry Pi specific)
            temperature = None
            try:
                with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                    temperature = float(f.read().strip()) / 1000.0
            except Exception:
                pass
            
            return SystemMetrics(
                timestamp=time.time(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                disk_percent=disk.percent,
                load_average=list(load_avg),
                network_io=network_io,
                temperature=temperature
            )
        except Exception as e:
            logger.exception(f"Error collecting system metrics: {e}")
            return None


class ProxyMonitor:
    """Monitor the proxy server"""
    
    def get_metrics(self) -> Optional[ProxyMetrics]:
        """Get current proxy metrics"""
        if not REQUESTS_AVAILABLE:
            return None
        
        try:
            response = requests.get(f"{PROXY_URL}/api/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                
                return ProxyMetrics(
                    timestamp=time.time(),
                    status=data.get('status', 'unknown'),
                    active_requests=data.get('active_requests', 0),
                    cache_memory_size=data.get('cache', {}).get('memory_size', 0),
                    cache_memory_hits=data.get('cache', {}).get('memory_stats', {}).get('hits', 0),
                    cache_memory_misses=data.get('cache', {}).get('memory_stats', {}).get('misses', 0),
                    circuit_breaker_state=data.get('circuit_breaker', {}).get('state', 'unknown'),
                    circuit_breaker_failures=data.get('circuit_breaker', {}).get('failures', 0),
                    error_rate=data.get('error_summary', {}).get('error_rate', 0),
                    uptime=data.get('uptime', 0)
                )
            else:
                return ProxyMetrics(
                    timestamp=time.time(),
                    status='unhealthy',
                    active_requests=0,
                    cache_memory_size=0,
                    cache_memory_hits=0,
                    cache_memory_misses=0,
                    circuit_breaker_state='unknown',
                    circuit_breaker_failures=0,
                    error_rate=1.0,
                    uptime=0
                )
        except Exception as e:
            logger.error(f"Error collecting proxy metrics: {e}")
            return ProxyMetrics(
                timestamp=time.time(),
                status='error',
                active_requests=0,
                cache_memory_size=0,
                cache_memory_hits=0,
                cache_memory_misses=0,
                circuit_breaker_state='unknown',
                circuit_breaker_failures=0,
                error_rate=1.0,
                uptime=0
            )


class AlertManager:
    """Manage alerts and notifications"""
    
    def __init__(self, db: MonitoringDB):
        self.db = db
        self.alert_history = {}
    
    def check_alerts(self, system_metrics: Optional[SystemMetrics], 
                    proxy_metrics: Optional[ProxyMetrics]):
        """Check for alert conditions"""
        alerts = []
        
        if system_metrics:
            # CPU alert
            if system_metrics.cpu_percent > 90:
                alerts.append(Alert(
                    timestamp=time.time(),
                    level='critical',
                    component='system',
                    message=f'High CPU usage: {system_metrics.cpu_percent:.1f}%'
                ))
            elif system_metrics.cpu_percent > 80:
                alerts.append(Alert(
                    timestamp=time.time(),
                    level='warning',
                    component='system',
                    message=f'Elevated CPU usage: {system_metrics.cpu_percent:.1f}%'
                ))
            
            # Memory alert
            if system_metrics.memory_percent > 95:
                alerts.append(Alert(
                    timestamp=time.time(),
                    level='critical',
                    component='system',
                    message=f'High memory usage: {system_metrics.memory_percent:.1f}%'
                ))
            elif system_metrics.memory_percent > 85:
                alerts.append(Alert(
                    timestamp=time.time(),
                    level='warning',
                    component='system',
                    message=f'Elevated memory usage: {system_metrics.memory_percent:.1f}%'
                ))
            
            # Disk alert
            if system_metrics.disk_percent > 95:
                alerts.append(Alert(
                    timestamp=time.time(),
                    level='critical',
                    component='system',
                    message=f'Low disk space: {system_metrics.disk_percent:.1f}% used'
                ))
            elif system_metrics.disk_percent > 85:
                alerts.append(Alert(
                    timestamp=time.time(),
                    level='warning',
                    component='system',
                    message=f'Disk space warning: {system_metrics.disk_percent:.1f}% used'
                ))
            
            # Temperature alert (Raspberry Pi)
            if system_metrics.temperature and system_metrics.temperature > 80:
                alerts.append(Alert(
                    timestamp=time.time(),
                    level='critical',
                    component='system',
                    message=f'High temperature: {system_metrics.temperature:.1f}°C'
                ))
            elif system_metrics.temperature and system_metrics.temperature > 70:
                alerts.append(Alert(
                    timestamp=time.time(),
                    level='warning',
                    component='system',
                    message=f'Elevated temperature: {system_metrics.temperature:.1f}°C'
                ))
        
        if proxy_metrics:
            # Proxy health alert
            if proxy_metrics.status in ('error', 'unhealthy'):
                alerts.append(Alert(
                    timestamp=time.time(),
                    level='critical',
                    component='proxy',
                    message=f'Proxy service unhealthy: {proxy_metrics.status}'
                ))
            elif proxy_metrics.status == 'degraded':
                alerts.append(Alert(
                    timestamp=time.time(),
                    level='warning',
                    component='proxy',
                    message='Proxy service degraded'
                ))
            
            # Circuit breaker alert
            if proxy_metrics.circuit_breaker_state == 'OPEN':
                alerts.append(Alert(
                    timestamp=time.time(),
                    level='critical',
                    component='proxy',
                    message=f'Circuit breaker open: {proxy_metrics.circuit_breaker_failures} failures'
                ))
            
            # Error rate alert
            if proxy_metrics.error_rate > 0.5:
                alerts.append(Alert(
                    timestamp=time.time(),
                    level='critical',
                    component='proxy',
                    message=f'High error rate: {proxy_metrics.error_rate:.1%}'
                ))
            elif proxy_metrics.error_rate > 0.1:
                alerts.append(Alert(
                    timestamp=time.time(),
                    level='warning',
                    component='proxy',
                    message=f'Elevated error rate: {proxy_metrics.error_rate:.1%}'
                ))
        
        # Store alerts (with deduplication)
        for alert in alerts:
            alert_key = f"{alert.component}:{alert.message}"
            last_time = self.alert_history.get(alert_key, 0)
            
            # Only store if not seen recently (5 minutes)
            if time.time() - last_time > 300:
                self.db.store_alert(alert)
                self.alert_history[alert_key] = time.time()
                logger.warning(f"Alert: [{alert.level}] {alert.component}: {alert.message}")


# Global instances
db = MonitoringDB(DB_PATH)
system_monitor = SystemMonitor()
proxy_monitor = ProxyMonitor()
alert_manager = AlertManager(db)

# Background monitoring thread
monitoring_thread = None
monitoring_active = threading.Event()


def monitoring_loop():
    """Background monitoring loop"""
    logger.info("Starting monitoring loop")
    
    while monitoring_active.is_set():
        try:
            # Collect metrics
            system_metrics = system_monitor.get_metrics()
            proxy_metrics = proxy_monitor.get_metrics()
            
            # Store metrics
            if system_metrics:
                db.store_system_metrics(system_metrics)
            if proxy_metrics:
                db.store_proxy_metrics(proxy_metrics)
            
            # Check for alerts
            alert_manager.check_alerts(system_metrics, proxy_metrics)
            
            # Cleanup old data periodically
            if int(time.time()) % 3600 == 0:  # Every hour
                db.cleanup_old_data()
            
        except Exception as e:
            logger.exception(f"Error in monitoring loop: {e}")
        
        time.sleep(UPDATE_INTERVAL)


def start_monitoring():
    """Start background monitoring"""
    global monitoring_thread
    
    if monitoring_thread and monitoring_thread.is_alive():
        return
    
    monitoring_active.set()
    monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
    monitoring_thread.start()


def stop_monitoring():
    """Stop background monitoring"""
    monitoring_active.clear()
    if monitoring_thread:
        monitoring_thread.join(timeout=5)


# Dashboard HTML template
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WeatherPi Enhanced Monitoring</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .metric {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid #eee;
        }
        .metric:last-child {
            border-bottom: none;
        }
        .metric-value {
            font-weight: bold;
            font-size: 1.2em;
        }
        .status-ok { color: #4CAF50; }
        .status-warning { color: #FF9800; }
        .status-error { color: #F44336; }
        .chart-container {
            position: relative;
            height: 300px;
            margin-top: 20px;
        }
        .alert {
            padding: 10px;
            margin: 5px 0;
            border-radius: 5px;
            border-left: 4px solid;
        }
        .alert-critical {
            background: #ffebee;
            border-color: #f44336;
            color: #c62828;
        }
        .alert-warning {
            background: #fff3e0;
            border-color: #ff9800;
            color: #ef6c00;
        }
        .alert-info {
            background: #e3f2fd;
            border-color: #2196f3;
            color: #1565c0;
        }
        .refresh-info {
            text-align: center;
            color: #666;
            font-size: 0.9em;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🌤️ WeatherPi Enhanced Monitoring</h1>
        <p>Real-time system and application monitoring dashboard</p>
    </div>

    <div class="grid">
        <div class="card">
            <h3>System Status</h3>
            <div id="system-metrics">
                <div class="metric">
                    <span>Loading...</span>
                </div>
            </div>
        </div>

        <div class="card">
            <h3>Proxy Status</h3>
            <div id="proxy-metrics">
                <div class="metric">
                    <span>Loading...</span>
                </div>
            </div>
        </div>

        <div class="card">
            <h3>Recent Alerts</h3>
            <div id="alerts">
                <div class="alert alert-info">Loading alerts...</div>
            </div>
        </div>
    </div>

    <div class="grid">
        <div class="card">
            <h3>System Performance</h3>
            <div class="chart-container">
                <canvas id="systemChart"></canvas>
            </div>
        </div>

        <div class="card">
            <h3>Proxy Performance</h3>
            <div class="chart-container">
                <canvas id="proxyChart"></canvas>
            </div>
        </div>
    </div>

    <div class="refresh-info">
        Last updated: <span id="last-update">Never</span> | 
        Auto-refresh: <span id="refresh-interval">{{ refresh_interval }}s</span>
    </div>

    <script>
        const REFRESH_INTERVAL = {{ refresh_interval }} * 1000;
        let systemChart, proxyChart;

        // Initialize charts
        function initCharts() {
            const systemCtx = document.getElementById('systemChart').getContext('2d');
            systemChart = new Chart(systemCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        {
                            label: 'CPU %',
                            data: [],
                            borderColor: '#f44336',
                            backgroundColor: 'rgba(244, 67, 54, 0.1)',
                            tension: 0.1
                        },
                        {
                            label: 'Memory %',
                            data: [],
                            borderColor: '#2196f3',
                            backgroundColor: 'rgba(33, 150, 243, 0.1)',
                            tension: 0.1
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100
                        }
                    }
                }
            });

            const proxyCtx = document.getElementById('proxyChart').getContext('2d');
            proxyChart = new Chart(proxyCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        {
                            label: 'Active Requests',
                            data: [],
                            borderColor: '#4caf50',
                            backgroundColor: 'rgba(76, 175, 80, 0.1)',
                            tension: 0.1
                        },
                        {
                            label: 'Cache Size',
                            data: [],
                            borderColor: '#ff9800',
                            backgroundColor: 'rgba(255, 152, 0, 0.1)',
                            tension: 0.1,
                            yAxisID: 'y1'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            type: 'linear',
                            display: true,
                            position: 'left',
                        },
                        y1: {
                            type: 'linear',
                            display: true,
                            position: 'right',
                            grid: {
                                drawOnChartArea: false,
                            },
                        }
                    }
                }
            });
        }

        // Update dashboard
        async function updateDashboard() {
            try {
                const [systemResponse, proxyResponse, alertsResponse] = await Promise.all([
                    fetch('/api/system-metrics'),
                    fetch('/api/proxy-metrics'),
                    fetch('/api/alerts')
                ]);

                const systemData = await systemResponse.json();
                const proxyData = await proxyResponse.json();
                const alertsData = await alertsResponse.json();

                updateSystemMetrics(systemData);
                updateProxyMetrics(proxyData);
                updateAlerts(alertsData);
                updateCharts(systemData, proxyData);

                document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
            } catch (error) {
                console.error('Error updating dashboard:', error);
            }
        }

        function updateSystemMetrics(data) {
            const container = document.getElementById('system-metrics');
            if (!data.length) {
                container.innerHTML = '<div class="metric"><span>No data available</span></div>';
                return;
            }

            const latest = data[data.length - 1];
            container.innerHTML = `
                <div class="metric">
                    <span>CPU Usage</span>
                    <span class="metric-value ${getStatusClass(latest.cpu_percent, 80, 90)}">${latest.cpu_percent.toFixed(1)}%</span>
                </div>
                <div class="metric">
                    <span>Memory Usage</span>
                    <span class="metric-value ${getStatusClass(latest.memory_percent, 85, 95)}">${latest.memory_percent.toFixed(1)}%</span>
                </div>
                <div class="metric">
                    <span>Disk Usage</span>
                    <span class="metric-value ${getStatusClass(latest.disk_percent, 85, 95)}">${latest.disk_percent.toFixed(1)}%</span>
                </div>
                <div class="metric">
                    <span>Load Average</span>
                    <span class="metric-value">${latest.load_1m.toFixed(2)}</span>
                </div>
                ${latest.temperature ? `
                <div class="metric">
                    <span>Temperature</span>
                    <span class="metric-value ${getStatusClass(latest.temperature, 70, 80)}">${latest.temperature.toFixed(1)}°C</span>
                </div>
                ` : ''}
            `;
        }

        function updateProxyMetrics(data) {
            const container = document.getElementById('proxy-metrics');
            if (!data.length) {
                container.innerHTML = '<div class="metric"><span>No data available</span></div>';
                return;
            }

            const latest = data[data.length - 1];
            const statusClass = latest.status === 'ok' ? 'status-ok' : 
                               latest.status === 'degraded' ? 'status-warning' : 'status-error';
            
            const cacheHitRate = latest.cache_hits + latest.cache_misses > 0 ? 
                                (latest.cache_hits / (latest.cache_hits + latest.cache_misses) * 100) : 0;

            container.innerHTML = `
                <div class="metric">
                    <span>Status</span>
                    <span class="metric-value ${statusClass}">${latest.status.toUpperCase()}</span>
                </div>
                <div class="metric">
                    <span>Active Requests</span>
                    <span class="metric-value">${latest.active_requests}</span>
                </div>
                <div class="metric">
                    <span>Cache Hit Rate</span>
                    <span class="metric-value">${cacheHitRate.toFixed(1)}%</span>
                </div>
                <div class="metric">
                    <span>Circuit Breaker</span>
                    <span class="metric-value ${latest.circuit_breaker_state === 'CLOSED' ? 'status-ok' : 'status-error'}">${latest.circuit_breaker_state}</span>
                </div>
                <div class="metric">
                    <span>Error Rate</span>
                    <span class="metric-value ${getStatusClass(latest.error_rate * 100, 10, 50)}">${(latest.error_rate * 100).toFixed(1)}%</span>
                </div>
                <div class="metric">
                    <span>Uptime</span>
                    <span class="metric-value">${formatUptime(latest.uptime)}</span>
                </div>
            `;
        }

        function updateAlerts(alerts) {
            const container = document.getElementById('alerts');
            
            if (!alerts.length) {
                container.innerHTML = '<div class="alert alert-info">No recent alerts</div>';
                return;
            }

            container.innerHTML = alerts.slice(0, 5).map(alert => `
                <div class="alert alert-${alert.level}">
                    <strong>[${alert.level.toUpperCase()}]</strong> 
                    ${alert.component}: ${alert.message}
                    <br><small>${new Date(alert.timestamp * 1000).toLocaleString()}</small>
                </div>
            `).join('');
        }

        function updateCharts(systemData, proxyData) {
            // Update system chart
            if (systemData.length > 0) {
                const labels = systemData.map(d => new Date(d.timestamp * 1000).toLocaleTimeString());
                const cpuData = systemData.map(d => d.cpu_percent);
                const memoryData = systemData.map(d => d.memory_percent);

                systemChart.data.labels = labels.slice(-20); // Last 20 points
                systemChart.data.datasets[0].data = cpuData.slice(-20);
                systemChart.data.datasets[1].data = memoryData.slice(-20);
                systemChart.update('none');
            }

            // Update proxy chart
            if (proxyData.length > 0) {
                const labels = proxyData.map(d => new Date(d.timestamp * 1000).toLocaleTimeString());
                const activeRequests = proxyData.map(d => d.active_requests);
                const cacheSize = proxyData.map(d => d.cache_memory_size);

                proxyChart.data.labels = labels.slice(-20); // Last 20 points
                proxyChart.data.datasets[0].data = activeRequests.slice(-20);
                proxyChart.data.datasets[1].data = cacheSize.slice(-20);
                proxyChart.update('none');
            }
        }

        function getStatusClass(value, warning, critical) {
            if (value >= critical) return 'status-error';
            if (value >= warning) return 'status-warning';
            return 'status-ok';
        }

        function formatUptime(seconds) {
            const days = Math.floor(seconds / 86400);
            const hours = Math.floor((seconds % 86400) / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            
            if (days > 0) return `${days}d ${hours}h ${minutes}m`;
            if (hours > 0) return `${hours}h ${minutes}m`;
            return `${minutes}m`;
        }

        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            initCharts();
            updateDashboard();
            setInterval(updateDashboard, REFRESH_INTERVAL);
        });
    </script>
</body>
</html>
'''


@app.route('/')
def dashboard():
    """Main dashboard"""
    return render_template_string(DASHBOARD_HTML, refresh_interval=UPDATE_INTERVAL)


@app.route('/api/system-metrics')
def api_system_metrics():
    """Get recent system metrics"""
    hours = request.args.get('hours', 1, type=int)
    metrics = db.get_recent_metrics('system_metrics', hours)
    return jsonify(metrics)


@app.route('/api/proxy-metrics')
def api_proxy_metrics():
    """Get recent proxy metrics"""
    hours = request.args.get('hours', 1, type=int)
    metrics = db.get_recent_metrics('proxy_metrics', hours)
    return jsonify(metrics)


@app.route('/api/alerts')
def api_alerts():
    """Get recent alerts"""
    hours = request.args.get('hours', 24, type=int)
    alerts = db.get_recent_alerts(hours)
    return jsonify(alerts)


@app.route('/api/status')
def api_status():
    """Get overall system status"""
    system_metrics = system_monitor.get_metrics()
    proxy_metrics = proxy_monitor.get_metrics()
    
    return jsonify({
        'timestamp': time.time(),
        'system': asdict(system_metrics) if system_metrics else None,
        'proxy': asdict(proxy_metrics) if proxy_metrics else None,
        'monitoring': {
            'active': monitoring_active.is_set(),
            'update_interval': UPDATE_INTERVAL,
            'history_days': HISTORY_DAYS
        }
    })


if __name__ == '__main__':
    logger.info(f"Starting WeatherPi Enhanced Monitoring Dashboard on port {MONITOR_PORT}")
    
    # Start background monitoring
    start_monitoring()
    
    try:
        app.run(host='0.0.0.0', port=MONITOR_PORT, debug=False, threaded=True)
    finally:
        stop_monitoring()