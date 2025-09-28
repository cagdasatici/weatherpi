#!/usr/bin/env python3
"""
Family Calendar Fetcher - Only fetch Family calendar events
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from calendar_fetcher import CalDAVFetcher
from calendar_config import load_config, save_events, CONFIG_FILE
from datetime import datetime, timedelta
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('family_calendar.log')
    ]
)

def main():
    """Fetch only Family calendar events"""
    logger = logging.getLogger(__name__)
    logger.info("🏠 Starting FAMILY calendar fetch process")
    
    # Load configuration
    config = load_config()
    if not config:
        logger.error("Failed to load configuration")
        return False
    
    # Date range - next 30 days
    start_date = datetime.now() - timedelta(days=1)  # Include today
    end_date = datetime.now() + timedelta(days=30)   # Next month
    
    fetcher = CalDAVFetcher()
    all_events = []
    
    try:
        for account in config['accounts']:
            logger.info(f"Processing account: {account['name']}")
            
            # Filter for FAMILY calendars only
            family_calendars = [cal for cal in account['calendars'] 
                              if 'family' in cal['name'].lower()]
            
            logger.info(f"Found {len(family_calendars)} Family calendars")
            
            for calendar in family_calendars:
                logger.info(f"📅 Fetching FAMILY events from: {calendar['name']}")
                events = fetcher.fetch_events(
                    account['username'], 
                    account['password'], 
                    calendar['url'], 
                    start_date, 
                    end_date
                )
                
                # Add metadata to events
                for event in events:
                    event['account'] = account['name']
                    event['calendar'] = calendar['name']
                
                all_events.extend(events)
                logger.info(f"✅ Got {len(events)} events from {calendar['name']}")
        
        # Filter out old events (before today)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        future_events = [e for e in all_events if datetime.fromisoformat(e['start'].replace('Z', '')) >= today]
        
        logger.info(f"🏠 FAMILY calendar summary: {len(future_events)} upcoming events")
        
        # Save to special family events file
        family_output = './family_calendar_events.json'
        
        # Save with family-specific structure
        import json
        family_data = {
            "family_events": future_events,
            "total_events": len(future_events),
            "last_updated": datetime.now().isoformat(),
            "next_update": (datetime.now() + timedelta(minutes=15)).isoformat(),
            "calendar_filter": "Family Only"
        }
        
        try:
            with open(family_output, 'w') as f:
                # Handle datetime serialization
                serializable_events = []
                for event in future_events:
                    event_copy = event.copy()
                    for key, value in event_copy.items():
                        if isinstance(value, datetime):
                            event_copy[key] = value.isoformat()
                    serializable_events.append(event_copy)
                
                family_data['family_events'] = serializable_events
                json.dump(family_data, f, indent=2)
            
            logger.info(f"✅ Saved {len(future_events)} FAMILY events to {family_output}")
            
            # Also update regular calendar file for compatibility
            success = save_events(all_events)
            logger.info(f"📅 Regular calendar update: {'Success' if success else 'Failed'}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving family events: {e}")
            return False
        
    except Exception as e:
        logger.error(f"❌ Family calendar fetch error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("🏠 Family calendar updated successfully!")
    else:
        print("❌ Family calendar update failed!")
        sys.exit(1)