#!/usr/bin/env python3
"""
WeatherPi Health Dashboard Server
Lightweight health monitoring accessible via web browser
Runs independently of SSH and other services
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import subprocess
import psutil
import datetime
import threading
import time
import os
import socket

class HealthDashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.serve_dashboard()
        elif self.path == '/api/health':
            self.serve_health_data()
        elif self.path == '/api/restart-network':
            self.restart_network()
        elif self.path == '/api/emergency-reboot':
            self.emergency_reboot()
        else:
            self.send_error(404)

    def serve_dashboard(self):
        """Serve the main dashboard HTML"""
        html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WeatherPi Health Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 30px; }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .status-grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .status-card {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .status-title { font-size: 1.3em; margin-bottom: 15px; display: flex; align-items: center; }
        .status-title .emoji { margin-right: 10px; font-size: 1.2em; }
        .metric { margin-bottom: 10px; display: flex; justify-content: space-between; }
        .metric-label { opacity: 0.8; }
        .metric-value { font-weight: bold; }
        .health-good { color: #4CAF50; }
        .health-warning { color: #FF9800; }
        .health-critical { color: #F44336; }
        .action-buttons {
            display: flex;
            gap: 15px;
            justify-content: center;
            margin-top: 30px;
        }
        .btn {
            padding: 12px 25px;
            border: none;
            border-radius: 25px;
            font-size: 1em;
            cursor: pointer;
            transition: all 0.3s;
            backdrop-filter: blur(10px);
        }
        .btn-primary { 
            background: rgba(76, 175, 80, 0.3);
            color: white;
            border: 1px solid #4CAF50;
        }
        .btn-warning { 
            background: rgba(255, 152, 0, 0.3);
            color: white;
            border: 1px solid #FF9800;
        }
        .btn-danger { 
            background: rgba(244, 67, 54, 0.3);
            color: white;
            border: 1px solid #F44336;
        }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.3); }
        .log-container {
            background: rgba(0, 0, 0, 0.3);
            border-radius: 10px;
            padding: 15px;
            max-height: 300px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }
        .timestamp { opacity: 0.7; margin-right: 10px; }
        .auto-refresh { 
            position: fixed;
            top: 20px;
            right: 20px;
            background: rgba(0, 0, 0, 0.5);
            padding: 10px;
            border-radius: 20px;
            font-size: 0.9em;
        }
        @media (max-width: 768px) {
            .status-grid { grid-template-columns: 1fr; }
            .action-buttons { flex-direction: column; }
        }
    </style>
</head>
<body>
    <div class="auto-refresh">
        🔄 Auto-refresh: <span id="countdown">30</span>s
    </div>

    <div class="container">
        <div class="header">
            <h1>🛡️ WeatherPi Health Dashboard</h1>
            <p>Real-time system monitoring & emergency controls</p>
        </div>

        <div class="status-grid">
            <div class="status-card">
                <div class="status-title">
                    <span class="emoji">🖥️</span>
                    System Status
                </div>
                <div id="system-metrics"></div>
            </div>

            <div class="status-card">
                <div class="status-title">
                    <span class="emoji">🌐</span>
                    Network Status
                </div>
                <div id="network-metrics"></div>
            </div>

            <div class="status-card">
                <div class="status-title">
                    <span class="emoji">🌡️</span>
                    Thermal Status
                </div>
                <div id="thermal-metrics"></div>
            </div>

            <div class="status-card">
                <div class="status-title">
                    <span class="emoji">⚙️</span>
                    Services Status
                </div>
                <div id="services-metrics"></div>
            </div>
        </div>

        <div class="action-buttons">
            <button class="btn btn-primary" onclick="refreshData()">🔄 Refresh Now</button>
            <button class="btn btn-warning" onclick="restartNetwork()">🌐 Restart Network</button>
            <button class="btn btn-danger" onclick="emergencyReboot()" 
                    ondblclick="this.style.display='none'; document.getElementById('confirm-reboot').style.display='inline'">
                🚨 Emergency Reboot
            </button>
            <button id="confirm-reboot" class="btn btn-danger" style="display:none" onclick="confirmReboot()">
                ⚠️ CONFIRM REBOOT
            </button>
        </div>

        <div class="status-card" style="margin-top: 30px;">
            <div class="status-title">
                <span class="emoji">📋</span>
                Recent System Logs
            </div>
            <div class="log-container" id="system-logs"></div>
        </div>
    </div>

    <script>
        let countdownTimer;
        let countdown = 30;

        function updateCountdown() {
            document.getElementById('countdown').textContent = countdown;
            countdown--;
            if (countdown < 0) {
                countdown = 30;
                refreshData();
            }
        }

        function formatMetric(label, value, className = '') {
            return `<div class="metric"><span class="metric-label">${label}:</span><span class="metric-value ${className}">${value}</span></div>`;
        }

        function getHealthClass(value, thresholds) {
            if (value >= thresholds.critical) return 'health-critical';
            if (value >= thresholds.warning) return 'health-warning';
            return 'health-good';
        }

        function refreshData() {
            fetch('/api/health')
                .then(response => response.json())
                .then(data => {
                    updateSystemMetrics(data.system);
                    updateNetworkMetrics(data.network);
                    updateThermalMetrics(data.thermal);
                    updateServicesMetrics(data.services);
                    updateLogs(data.logs);
                })
                .catch(error => {
                    console.error('Failed to fetch health data:', error);
                    document.getElementById('system-metrics').innerHTML = 
                        '<div class="metric health-critical">❌ Failed to fetch data</div>';
                });
        }

        function updateSystemMetrics(system) {
            const container = document.getElementById('system-metrics');
            const memClass = getHealthClass(system.memory_percent, {warning: 80, critical: 90});
            const diskClass = getHealthClass(system.disk_percent, {warning: 80, critical: 90});
            const loadClass = getHealthClass(system.load_avg, {warning: 2, critical: 4});
            
            container.innerHTML = 
                formatMetric('Uptime', system.uptime) +
                formatMetric('Memory Usage', `${system.memory_percent}%`, memClass) +
                formatMetric('Disk Usage', `${system.disk_percent}%`, diskClass) +
                formatMetric('Load Average', system.load_avg, loadClass) +
                formatMetric('Last Boot', system.boot_time);
        }

        function updateNetworkMetrics(network) {
            const container = document.getElementById('network-metrics');
            container.innerHTML = 
                formatMetric('WiFi Status', network.wifi_connected ? '✅ Connected' : '❌ Disconnected', 
                           network.wifi_connected ? 'health-good' : 'health-critical') +
                formatMetric('IP Address', network.ip_address || 'None') +
                formatMetric('Internet', network.internet_access ? '✅ Available' : '❌ No Access',
                           network.internet_access ? 'health-good' : 'health-critical') +
                formatMetric('SSH Status', network.ssh_active ? '✅ Active' : '❌ Inactive',
                           network.ssh_active ? 'health-good' : 'health-warning');
        }

        function updateThermalMetrics(thermal) {
            const container = document.getElementById('thermal-metrics');
            const tempClass = getHealthClass(thermal.cpu_temp, {warning: 70, critical: 80});
            
            container.innerHTML = 
                formatMetric('CPU Temperature', `${thermal.cpu_temp}°C`, tempClass) +
                formatMetric('Throttling', thermal.throttling ? '⚠️ Active' : '✅ Normal',
                           thermal.throttling ? 'health-warning' : 'health-good') +
                formatMetric('CPU Governor', thermal.cpu_governor) +
                formatMetric('GPU Memory', `${thermal.gpu_memory}MB`);
        }

        function updateServicesMetrics(services) {
            const container = document.getElementById('services-metrics');
            let html = '';
            for (const [service, status] of Object.entries(services)) {
                const statusClass = status === 'active' ? 'health-good' : 'health-critical';
                const statusText = status === 'active' ? '✅ Running' : '❌ Stopped';
                html += formatMetric(service, statusText, statusClass);
            }
            container.innerHTML = html;
        }

        function updateLogs(logs) {
            const container = document.getElementById('system-logs');
            container.innerHTML = logs.map(log => 
                `<div><span class="timestamp">${log.timestamp}</span>${log.message}</div>`
            ).join('');
            container.scrollTop = container.scrollHeight;
        }

        function restartNetwork() {
            if (confirm('Restart network services? This may temporarily interrupt connectivity.')) {
                fetch('/api/restart-network', {method: 'POST'})
                    .then(response => response.text())
                    .then(data => alert(data))
                    .catch(error => alert('Network restart failed: ' + error));
            }
        }

        function emergencyReboot() {
            alert('Double-click the Emergency Reboot button to confirm');
        }

        function confirmReboot() {
            if (confirm('⚠️ EMERGENCY REBOOT CONFIRMATION\\n\\nThis will immediately restart the Pi.\\nAll unsaved data will be lost.\\n\\nContinue?')) {
                fetch('/api/emergency-reboot', {method: 'POST'})
                    .then(() => {
                        alert('🚨 EMERGENCY REBOOT INITIATED\\n\\nThe Pi is restarting now.\\nPlease wait 60 seconds before refreshing.');
                    })
                    .catch(error => alert('Reboot failed: ' + error));
            }
        }

        // Initialize
        refreshData();
        countdownTimer = setInterval(updateCountdown, 1000);
    </script>
</body>
</html>
        """
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html_content.encode())

    def serve_health_data(self):
        """Serve health data as JSON"""
        try:
            health_data = self.get_system_health()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(health_data, indent=2).encode())
        except Exception as e:
            self.send_error(500, str(e))

    def get_system_health(self):
        """Collect comprehensive system health data"""
        
        # System metrics
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        load_avg = os.getloadavg()[0] if hasattr(os, 'getloadavg') else 0
        
        # Network status
        network_info = self.get_network_status()
        
        # Thermal status
        thermal_info = self.get_thermal_status()
        
        # Services status
        services_info = self.get_services_status()
        
        # Recent logs
        logs = self.get_recent_logs()
        
        return {
            "timestamp": datetime.datetime.now().isoformat(),
            "system": {
                "uptime": str(datetime.datetime.now() - boot_time).split('.')[0],
                "memory_percent": round(memory.percent, 1),
                "disk_percent": round(disk.percent, 1),
                "load_avg": round(load_avg, 2),
                "boot_time": boot_time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "network": network_info,
            "thermal": thermal_info,
            "services": services_info,
            "logs": logs
        }

    def get_network_status(self):
        """Get network connectivity status"""
        try:
            # Check WiFi interface
            wifi_connected = False
            ip_address = None
            
            interfaces = psutil.net_if_addrs()
            for interface, addresses in interfaces.items():
                if interface.startswith('wlan') or interface.startswith('wifi'):
                    for addr in addresses:
                        if addr.family == socket.AF_INET:
                            wifi_connected = True
                            ip_address = addr.address
                            break
            
            # Test internet connectivity
            internet_access = self.test_internet_connectivity()
            
            # Check SSH service
            ssh_active = self.is_service_active('ssh')
            
            return {
                "wifi_connected": wifi_connected,
                "ip_address": ip_address,
                "internet_access": internet_access,
                "ssh_active": ssh_active
            }
        except:
            return {
                "wifi_connected": False,
                "ip_address": None,
                "internet_access": False,
                "ssh_active": False
            }

    def get_thermal_status(self):
        """Get thermal and CPU status"""
        try:
            # CPU temperature
            cpu_temp = 0
            try:
                with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                    cpu_temp = int(f.read().strip()) / 1000
            except:
                pass
            
            # Check for throttling
            throttling = False
            try:
                result = subprocess.run(['vcgencmd', 'get_throttled'], 
                                      capture_output=True, text=True, timeout=5)
                if 'throttled=0x0' not in result.stdout:
                    throttling = True
            except:
                pass
            
            # CPU governor
            cpu_governor = "unknown"
            try:
                with open('/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor', 'r') as f:
                    cpu_governor = f.read().strip()
            except:
                pass
            
            # GPU memory
            gpu_memory = 0
            try:
                result = subprocess.run(['vcgencmd', 'get_mem', 'gpu'], 
                                      capture_output=True, text=True, timeout=5)
                if 'gpu=' in result.stdout:
                    gpu_memory = int(result.stdout.split('=')[1].replace('M', ''))
            except:
                pass
            
            return {
                "cpu_temp": round(cpu_temp, 1),
                "throttling": throttling,
                "cpu_governor": cpu_governor,
                "gpu_memory": gpu_memory
            }
        except:
            return {
                "cpu_temp": 0,
                "throttling": False,
                "cpu_governor": "unknown",
                "gpu_memory": 0
            }

    def get_services_status(self):
        """Check status of critical services"""
        services = ['nginx', 'ssh', 'dhcpcd', 'wpa_supplicant']
        status = {}
        
        for service in services:
            status[service] = 'active' if self.is_service_active(service) else 'inactive'
        
        return status

    def is_service_active(self, service_name):
        """Check if a systemd service is active"""
        try:
            result = subprocess.run(['systemctl', 'is-active', service_name], 
                                  capture_output=True, text=True, timeout=5)
            return result.stdout.strip() == 'active'
        except:
            return False

    def test_internet_connectivity(self):
        """Test internet connectivity"""
        try:
            result = subprocess.run(['ping', '-c', '1', '-W', '3', '8.8.8.8'], 
                                  capture_output=True, timeout=10)
            return result.returncode == 0
        except:
            return False

    def get_recent_logs(self):
        """Get recent system logs"""
        logs = []
        try:
            result = subprocess.run(['journalctl', '-n', '20', '--no-pager', '-o', 'short'], 
                                  capture_output=True, text=True, timeout=10)
            for line in result.stdout.split('\n')[-10:]:
                if line.strip():
                    parts = line.split(' ', 2)
                    if len(parts) >= 3:
                        logs.append({
                            "timestamp": f"{parts[0]} {parts[1]}",
                            "message": parts[2]
                        })
        except:
            logs.append({
                "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
                "message": "Unable to fetch system logs"
            })
        
        return logs

    def restart_network(self):
        """Restart network services"""
        try:
            subprocess.run(['sudo', 'systemctl', 'restart', 'dhcpcd'], timeout=10)
            subprocess.run(['sudo', 'systemctl', 'restart', 'wpa_supplicant'], timeout=10)
            
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Network services restarted successfully")
        except Exception as e:
            self.send_error(500, f"Failed to restart network: {str(e)}")

    def emergency_reboot(self):
        """Emergency system reboot"""
        try:
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Emergency reboot initiated")
            
            # Delay reboot to allow response to be sent
            threading.Timer(2.0, lambda: os.system('sudo reboot')).start()
        except Exception as e:
            self.send_error(500, f"Failed to initiate reboot: {str(e)}")

def run_health_dashboard(port=8080):
    """Run the health dashboard server"""
    server_address = ('', port)
    httpd = HTTPServer(server_address, HealthDashboardHandler)
    
    print(f"🌐 WeatherPi Health Dashboard running on:")
    print(f"   http://localhost:{port}")
    print(f"   http://<pi-ip-address>:{port}")
    print(f"🛡️  Access from any device on your network!")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🔄 Health Dashboard stopped")
        httpd.server_close()

if __name__ == "__main__":
    # Install required packages if not available
    try:
        import psutil
    except ImportError:
        print("Installing required package: psutil")
        subprocess.run(['pip3', 'install', 'psutil'])
        import psutil
    
    run_health_dashboard()