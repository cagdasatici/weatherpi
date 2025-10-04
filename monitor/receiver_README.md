Local heartbeat receiver

Usage:

# Run the receiver
python3 monitor/local_receiver.py

# Point the Pi's MONITOR_URL to the receiver
export MONITOR_URL=http://<your-mac-ip>:9000/heartbeat
sudo MONITOR_URL=$MONITOR_URL /usr/bin/python3 /opt/weatherpi/monitor/heartbeat.py

# View the dashboard
Open http://<your-mac-ip>:9000/ in your browser
