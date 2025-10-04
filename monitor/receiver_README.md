Local heartbeat receiver

Usage:

# Run the receiver
python3 monitor/local_receiver.py

# Point the Pi's MONITOR_URL to the receiver
# Run the receiver
python3 monitor/local_receiver.py

# Point the Pi's MONITOR_URL to the receiver (example uses 127.0.0.0 as requested)
export MONITOR_URL=http://127.0.0.0:9000/heartbeat
sudo MONITOR_URL=$MONITOR_URL /usr/bin/python3 /opt/weatherpi/monitor/heartbeat.py

# View the dashboard
Open http://127.0.0.0:9000/ in your browser
