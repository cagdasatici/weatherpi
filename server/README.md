# WeatherPi OpenWeather Proxy

This small server proxies OpenWeather requests so the API key remains on the Pi instead of in the client HTML.

Quick setup (on the Pi):

1. Copy the example env and edit it:

   cp server/.env.example server/.env
   # edit server/.env and set OPENWEATHER_API_KEY and API_PROXY_TOKEN (optional)

2. Install Python dependencies (use virtualenv if preferred):

   sudo apt update
   sudo apt install -y python3-venv python3-pip
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt

3. Run locally for testing:

   export OPENWEATHER_API_KEY=...
   export API_PROXY_TOKEN=...   # if you set a token
   python3 server/app.py

   The proxy will be available at http://0.0.0.0:8000/api/weather

4. Production with gunicorn + systemd (recommended):

   - Copy `server/weatherpi-proxy.service` to `/etc/systemd/system/` and edit paths/user if needed.
   - Ensure `/home/pi/weatherpi/server/.env` exists and contains the variables.
   - Make the start script executable: `chmod +x server/gunicorn_start.sh`
   - Enable and start the service:

     sudo systemctl daemon-reload
     sudo systemctl enable weatherpi-proxy.service
     sudo systemctl start weatherpi-proxy.service

5. Update the kiosk `weather.html` to call the proxy (already done):

   The client should call `/api/weather?lat=...&lon=...` and send header `X-Proxy-Token` if you configured `API_PROXY_TOKEN`.

Security notes:
- Keep `server/.env` out of version control. Use `calendar_credentials.example.json` as template.
- Consider firewalling the Pi so only local network devices can access the proxy.
- For wider exposure, enable HTTPS (nginx reverse proxy + certbot) and stronger auth.

## NGINX + HTTPS (optional)

I included an example nginx site config at `server/nginx/weatherpi.conf` and a helper
script `server/setup_nginx.sh` which will:

- install nginx and certbot (Debian/Ubuntu)
- copy and enable the sample nginx config (you MUST change `server_name` and paths)
- optionally request a Let's Encrypt certificate for your domain (or create a self-signed cert)

Usage (on the Pi):

```bash
sudo bash server/setup_nginx.sh
```

After setup, nginx will serve the static `weather.html` from your repo and proxy `/api/`
to the local gunicorn server on port 8000.

Be sure to update `server/weatherpi-proxy.service` and `server/gunicorn_start.sh` paths
if your repository is not in `/home/pi/weatherpi`.

Kiosk startup ordering (recommended)
----------------------------------
To make the kiosk browser start only after the proxy is healthy, use the provided
`server/wait_for_health.sh` script and the sample systemd unit `server/kiosk-wait.service`.

Example steps on the Pi:

   sudo cp server/kiosk-wait.service /etc/systemd/system/kiosk-wait.service
   sudo cp server/wait_for_health.sh /usr/local/bin/wait_for_health.sh
   sudo chmod +x /usr/local/bin/wait_for_health.sh
   sudo systemctl daemon-reload
   sudo systemctl enable kiosk-wait.service

Then modify your existing `chromium-kiosk.service` to depend on `kiosk-wait.service` by
adding `After=kiosk-wait.service` and `Wants=kiosk-wait.service` in the `[Unit]` section.

This ensures the kiosk will only launch after the proxy reports healthy or the wait script
times out (which will keep your display from launching an empty page while services boot).


