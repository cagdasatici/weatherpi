HTML_TEMPLATE = '''<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>WeatherPi — Local Status</title>
    <style>
        body {{ font-family: Inter, Arial, sans-serif; background: #0f1724; color: #e6eef6; margin: 0; padding: 20px; }}
        .container {{ max-width: 980px; margin: 0 auto; }}
        .header {{ display:flex; align-items:center; justify-content:space-between; }}
        .header h1 {{ margin:0; font-size:20px }}
        .card {{ background: linear-gradient(180deg,#0b1220,#0d1522); border-radius:12px; padding:16px; margin-top:16px; box-shadow:0 6px 20px rgba(2,6,23,0.6); }}
        .kv {{ display:flex; gap:12px; align-items:center }}
        .k {{ color:#9fb1c9; width:160px }}
        .v {{ font-weight:700 }}
        .small {{ font-size:12px; color:#9fb1c9 }}
        .grid2 {{ display:grid; grid-template-columns: 1fr 1fr; gap:12px; margin-top:12px }}
        canvas {{ width:100% !important; height:120px !important }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>WeatherPi — Local Status</h1>
            <div class="small">Updated: {updated}</div>
        </div>

        <div class="card">
            <div style="display:flex;gap:20px;flex-wrap:wrap">
                <div style="flex:1;min-width:260px">
                    <div class="kv"><div class="k">Services</div><div class="v">{services}</div></div>
                </div>
                <div style="flex:1;min-width:260px">
                    <div class="kv"><div class="k">Network</div><div class="v">DNS: {dns_ok}, External: {external_ok}</div></div>
                </div>
            </div>

            <div class="grid2">
                <div class="card"><canvas id="loadChart"></canvas></div>
                <div class="card"><canvas id="memChart"></canvas></div>
                <div class="card"><canvas id="diskChart"></canvas></div>
                <div style="padding:8px">
                    <div class="kv"><div class="k">CPU temp</div><div class="v">{cpu_temp}</div></div>
                    <div class="kv"><div class="k">Inodes</div><div class="v">{inode_pct}%</div></div>
                    <div class="kv"><div class="k">Raw JSON</div><div class="v small"><a href="/status.json">/status.json</a></div></div>
                </div>
            </div>
        </div>

    </div>

    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.3.0/dist/chart.umd.min.js"></script>
    <script>
        const MAX_POINTS = 30;
        function createChart(ctx,label,color){
            return new Chart(ctx,{type:'line',data:{labels:[],datasets:[{label:label,data:[],borderColor:color,backgroundColor:color,fill:false,tension:0.25}]},options:{animation:false,scales:{x:{display:false}}}});
        }
        let loadChart, memChart, diskChart;
        function initCharts(){
            loadChart = createChart(document.getElementById('loadChart'), 'Load (1m)', '#FFD166');
            memChart = createChart(document.getElementById('memChart'), 'Memory MB', '#06D6A0');
            diskChart = createChart(document.getElementById('diskChart'), 'Disk %', '#EF476F');
        }
        function pushPoint(chart,val){ const ds=chart.data.datasets[0]; const labels=chart.data.labels; ds.data.push(Number(val)||0); labels.push(''); if(ds.data.length>MAX_POINTS){ ds.data.shift(); labels.shift(); } chart.update(); }
        async function refresh(){
            try{
                const r = await fetch('/status.json'); if(!r.ok) return; const data = await r.json();
                const la = (data.checks.loadavg && data.checks.loadavg[0])||0;
                const mem = (data.checks.memory && (data.checks.memory.avail_kb||data.checks.memory.available_kb))||0;
                const mem_mb = Math.round(mem/1024);
                const disk = (data.checks.disk && data.checks.disk.percent)||0;
                const servicesText = Object.entries(data.checks).filter(([k])=>k.startsWith('service:')).map(([k,v])=>k.split(':')[1]+':' + (v? 'OK':'DOWN')).join(', ');
                document.querySelector('.header .small').textContent = 'Updated: ' + new Date().toISOString();
                const svcElem = document.querySelector('.kv .v'); if(svcElem) svcElem.textContent = servicesText || 'unknown';
                pushPoint(loadChart, la); pushPoint(memChart, mem_mb); pushPoint(diskChart, disk);
            }catch(e){ console.error(e); }
        }
        window.addEventListener('load', ()=>{ initCharts(); refresh(); setInterval(refresh, 5000); });
    </script>

</body>
</html>
'''
    'const MAX_POINTS = 30;'
    'function createChart(ctx,label,color){return new Chart(ctx,{type:"line",data:{labels:[],datasets:[{label:label,data:[],borderColor:color,backgroundColor:color,fill:false,tension:0.25}]},options:{animation:false,scales:{x:{display:false}}}});} '
    'let loadChart, memChart, diskChart;'
    'function initCharts(){loadChart = createChart(document.getElementById("loadChart"),"Load (1m)","#FFD166");memChart = createChart(document.getElementById("memChart"),"Memory MB","#06D6A0");diskChart = createChart(document.getElementById("diskChart"),"Disk %","#EF476F");} '
    'function pushPoint(chart,val){const ds=chart.data.datasets[0];const labels=chart.data.labels;ds.data.push(Number(val)||0);labels.push("");if(ds.data.length>MAX_POINTS){ds.data.shift();labels.shift()}chart.update()} '
    'async function refresh(){try{const r=await fetch("/status.json");if(!r.ok) return;const data=await r.json();const la=(data.checks.loadavg && data.checks.loadavg[0])||0;const mem=(data.checks.memory && (data.checks.memory.avail_kb||data.checks.memory.available_kb) )||0;const mem_mb=Math.round(mem/1024);const disk=(data.checks.disk && data.checks.disk.percent)||0;document.querySelector(".header .small").textContent="Updated: "+new Date().toISOString();document.querySelectorAll('.v')[0].textContent = Object.entries(data.checks).filter(([k]) => k.startsWith('service:')).map(([k,v])=>k.split(':')[1]+":"+(v?"OK":"DOWN")).join(', ');pushPoint(loadChart,la);pushPoint(memChart,mem_mb);pushPoint(diskChart,disk);}catch(e){console.error(e)}} '
    'window.addEventListener("load",()=>{initCharts();refresh();setInterval(refresh,5000)});'
    '</script>'
    '</body>'
    '</html>'
    '      <div class="card" style="padding:10px"><canvas id="memChart" height="120"></canvas></div>'
    '      <div class="card" style="padding:10px"><canvas id="diskChart" height="120"></canvas></div>'
    '      <div style="padding:8px"> <div class="kv"><div class="k">CPU temp</div><div class="v">{cpu_temp}</div></div> <div class="kv"><div class="k">Inodes</div><div class="v">{inode_pct}%</div></div> <div class="kv"><div class="k">Raw JSON</div><div class="v small"><a href="/status.json">/status.json</a></div></div></div>'
    '    </div>'
    '  </div>'
        '</body>'
        '</html>'
)

class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')

    def _forbidden(self):
        self.send_response(403)
        self._cors()
        self.end_headers()
        self.wfile.write(b'Forbidden')

    def _authorized(self):
        # allow if client IP in allowlist
        client_ip = self.client_address[0]
        if client_ip in ALLOWED_IPS:
            return True
        # allow if token provided and matches
        if STATUS_TOKEN:
            # check header first
            token = self.headers.get('X-Status-Token')
            if not token:
                # fallback to ?token= in URL
                from urllib.parse import urlparse, parse_qs
                q = urlparse(self.path).query
                token = parse_qs(q).get('token', [None])[0]
            if token == STATUS_TOKEN:
                return True
        return False

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.end_headers()

    def do_GET(self):
        if not self._authorized():
            return self._forbidden()
        if self.path == '/status.json':
            if not os.path.exists(STATUS_FILE):
                self.send_response(404)
                self._cors()
                self.end_headers()
                return
            with open(STATUS_FILE, 'r') as f:
                body = f.read()
            self.send_response(200)
            self._cors()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(body.encode('utf-8'))
            return

        # serve HTML with safe defaults
        status = {}
        try:
            if os.path.exists(STATUS_FILE):
                with open(STATUS_FILE, 'r') as f:
                    status = json.load(f)
        except Exception:
            status = {}

        services = ', '.join(f"{k}:{'OK' if v else 'DOWN'}" for k,v in status.get('checks', {}).items() if k.startswith('service:')) or 'unknown'
        disk = status.get('checks', {}).get('disk', {})
        disk_pct = disk.get('percent', 'n/a')
        disk_free = disk.get('free', 'n/a')
        inodes = status.get('checks', {}).get('inodes', {})
        inode_pct = inodes.get('percent', 'n/a')
        mem = status.get('checks', {}).get('memory', {})
        mem_avail = mem.get('avail_kb', mem.get('available_kb', 0)) // 1024 if isinstance(mem.get('avail_kb', None), int) or isinstance(mem.get('available_kb', None), int) else 'n/a'
        load = status.get('checks', {}).get('loadavg', (0.0,0.0,0.0))
        load1 = load[0] if isinstance(load, (list,tuple)) else 'n/a'
        cpu = status.get('checks', {}).get('cpu_temp', 'n/a')
        network = status.get('checks', {}).get('network', {})
        dns_ok = network.get('dns_ok', 'n/a')
        external_ok = network.get('external_connect', 'n/a')

        body = HTML_TEMPLATE.format(updated=datetime.utcnow().isoformat()+'Z', services=services, disk_pct=disk_pct, disk_free=disk_free, inode_pct=inode_pct, mem_avail=mem_avail, load1=load1, cpu_temp=cpu, dns_ok=dns_ok, external_ok=external_ok)
        self.send_response(200)
        self._cors()
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(body.encode('utf-8'))
        # Prepend a small JS/Chart.js payload to the HTML by monkey-patching template at runtime
        # Inject charts script at the end of the template before serving
        # We'll just run the server loop — the template already contains canvas elements

    def log_message(self, format, *args):
        print(f"[status_server] {format % args}")

if __name__ == '__main__':
    server = HTTPServer((BIND, PORT), Handler)
    print(f"Starting status server on http://{BIND}:{PORT}")
    try:
           # Prepend a small JS/Chart.js payload to the HTML by monkey-patching template at runtime
           # Inject charts script at the end of the template before serving
           # We'll just run the server loop — the template already contains canvas elements
           server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
        print('Shutting down')
