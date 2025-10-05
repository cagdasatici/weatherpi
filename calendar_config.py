#!/usr/bin/env python3
"""
Apple Calendar (iCloud) Configuration
- Handles multiple iCloud accounts
- Fetches calendar events via CalDAV
- Saves to JSON for web display
"""

import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Configuration file path - local development vs Pi deployment
import os
import sys

# Use the current user's home directory where appropriate so the project
# works regardless of the username on the device (pi, cagdas, etc.).
HOME_DIR = os.path.expanduser('~')

# Default deployment paths (web output is expected under the webserver root)
CONFIG_FILE = os.path.join(HOME_DIR, 'calendar_credentials.json')
DEFAULT_OUTPUT = '/var/www/html/calendar_events.json'

# If /var/www/html isn't writable in the current environment (dev machine),
# fall back to a local output file so the project is still usable.
if os.access(os.path.dirname(DEFAULT_OUTPUT), os.W_OK):
    OUTPUT_FILE = DEFAULT_OUTPUT
else:
    OUTPUT_FILE = os.path.join(os.getcwd(), 'calendar_events.json')

# Default configuration structure
DEFAULT_CONFIG = {
    "accounts": [
        {
            "name": "Account 1",
            "username": "",  # iCloud email
            "password": "",  # App-specific password recommended
            "calendars": []  # Will be auto-discovered
        },
        {
            "name": "Account 2", 
            "username": "",  # iCloud email
            "password": "",  # App-specific password recommended
            "calendars": []  # Will be auto-discovered
        }
    ],
    "settings": {
        "days_ahead": 7,        # Next week
        "update_interval": 900,  # 15 minutes in seconds
        "include_all_day": True,
        "include_timed": True,
        "max_events_per_day": 10
    }
}

def create_config_file():
    """Create initial configuration file if it doesn't exist"""
    if not os.path.exists(CONFIG_FILE):
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        print(f"Created configuration file: {CONFIG_FILE}")
        print("Please edit this file with your iCloud credentials")
        return False
    return True

def load_config():
    """Load configuration from file"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Config file not found: {CONFIG_FILE}")
        return None
    except json.JSONDecodeError as e:
        print(f"Invalid JSON in config file: {e}")
        return None

def save_events(events: List[Dict[str, Any]]):
    """Save events to JSON file for web display"""
    try:
        # Ensure output directory exists
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        
        # Convert datetime objects to ISO strings
        serializable_events = []
        for event in events:
            event_copy = event.copy()
            for key, value in event_copy.items():
                if isinstance(value, datetime):
                    event_copy[key] = value.isoformat()
            serializable_events.append(event_copy)
        
        output_data = {
            "events": serializable_events,
            "last_updated": datetime.now().isoformat(),
            "next_update": (datetime.now() + timedelta(minutes=15)).isoformat()
        }
        
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"Saved {len(events)} events to {OUTPUT_FILE}")
        return True
    except Exception as e:
        print(f"Error saving events: {e}")
        return False

if __name__ == "__main__":
    create_config_file()