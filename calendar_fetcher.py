#!/usr/bin/env python3
"""
Apple Calendar Fetcher
- Connects to iCloud CalDAV servers
- Fetches events from multiple accounts
- Processes and saves calendar data
"""

import sys
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import requests
from requests.auth import HTTPBasicAuth
from xml.etree import ElementTree as ET
import urllib.parse

# Import our config handler
from calendar_config import load_config, save_events, CONFIG_FILE

import os

# Set up logging to go to stdout (systemd/journal) by default. If an
# environment variable CALENDAR_LOG is set to a writable path, also write
# a file there for offline debugging.
log_handlers = [logging.StreamHandler()]
log_file = os.environ.get('CALENDAR_LOG')
if log_file:
    try:
        log_handlers.insert(0, logging.FileHandler(log_file))
    except Exception:
        # If file handler can't be created, continue with stream only
        pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=log_handlers
)
logger = logging.getLogger(__name__)

class iCloudCalendarFetcher:
    """Fetches calendar events from iCloud CalDAV"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'WeatherPi Calendar/1.0',
            'Content-Type': 'application/xml; charset=utf-8'
        })
    
    def discover_calendars(self, username: str, password: str) -> List[Dict[str, str]]:
        """Discover available calendars for an iCloud account"""
        try:
            # Extract Apple ID (part before @) for iCloud CalDAV URL
            apple_id = username.split('@')[0] if '@' in username else username
            
            # iCloud CalDAV server - try multiple possible URLs
            possible_urls = [
                f"https://caldav.icloud.com/{apple_id}/calendars/",
                f"https://p27-caldav.icloud.com/{apple_id}/calendars/",
                f"https://p41-caldav.icloud.com/{apple_id}/calendars/",
            ]
            
            for base_url in possible_urls:
                logger.info(f"Trying CalDAV URL: {base_url}")
                
                # PROPFIND request to discover calendars
                propfind_body = '''<?xml version="1.0" encoding="UTF-8"?>
<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
    <d:prop>
        <d:displayname/>
        <d:resourcetype/>
        <c:calendar-description/>
    </d:prop>
</d:propfind>'''
                
                try:
                    response = self.session.request(
                        'PROPFIND',
                        base_url,
                        data=propfind_body,
                        auth=HTTPBasicAuth(username, password),
                        headers={
                            'Depth': '1',
                            'Content-Type': 'application/xml; charset=utf-8'
                        },
                        timeout=30
                    )
                    
                    logger.info(f"Response status: {response.status_code}")
                    logger.debug(f"Response headers: {response.headers}")
                    logger.debug(f"Response body: {response.text[:500]}...")
                    
                    if response.status_code == 207:  # Multi-Status - Success!
                        logger.info(f"✅ Success with URL: {base_url}")
                        return self._parse_calendar_response(response.text, base_url, username)
                    elif response.status_code == 401:
                        logger.error(f"❌ 401 Unauthorized - Check credentials")
                        break  # Don't try other URLs if credentials are wrong
                    elif response.status_code == 403:
                        logger.error(f"❌ 403 Forbidden - Check 2FA/app-specific password")
                        break  # Don't try other URLs if forbidden
                    else:
                        logger.warning(f"⚠️ Unexpected status {response.status_code} for {base_url}")
                        continue  # Try next URL
                        
                except requests.exceptions.RequestException as e:
                    logger.error(f"Request failed for {base_url}: {e}")
                    continue  # Try next URL
            
            logger.error("❌ All CalDAV URLs failed")
            return []
            
        except Exception as e:
            logger.error(f"Error discovering calendars for {username}: {e}")
            return []
    
    def _parse_calendar_response(self, xml_text: str, base_url: str, username: str) -> List[Dict[str, str]]:
        """Parse CalDAV PROPFIND response XML"""
        try:
            root = ET.fromstring(xml_text)
            calendars = []
            
            # Define namespaces
            namespaces = {
                'd': 'DAV:',
                'c': 'urn:ietf:params:xml:ns:caldav'
            }
            
            for response_elem in root.findall('.//d:response', namespaces):
                href_elem = response_elem.find('.//d:href', namespaces)
                displayname_elem = response_elem.find('.//d:displayname', namespaces)
                resourcetype_elem = response_elem.find('.//d:resourcetype', namespaces)
                
                # Check if this is a calendar collection
                if (href_elem is not None and 
                    resourcetype_elem is not None and 
                    resourcetype_elem.find('.//c:calendar', namespaces) is not None):
                    
                    calendar_name = displayname_elem.text if displayname_elem is not None else "Unnamed Calendar"
                    calendar_href = href_elem.text
                    
                    # Build full URL
                    if calendar_href.startswith('http'):
                        calendar_url = calendar_href
                    else:
                        calendar_url = urllib.parse.urljoin(base_url, calendar_href)
                    
                    calendars.append({
                        'name': calendar_name,
                        'href': calendar_href,
                        'url': calendar_url
                    })
                    
                    logger.info(f"Found calendar: {calendar_name} -> {calendar_url}")
            
            logger.info(f"✅ Discovered {len(calendars)} calendars for {username}")
            return calendars
            
        except ET.ParseError as e:
            logger.error(f"Failed to parse XML response: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing calendar response: {e}")
            return []
    
    def fetch_events(self, username: str, password: str, calendar_url: str, 
                    start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Fetch events from a specific calendar"""
        try:
            # REPORT request to get events
            report_body = f'''<?xml version="1.0" encoding="UTF-8"?>
            <c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
                <d:prop>
                    <d:getetag/>
                    <c:calendar-data/>
                </d:prop>
                <c:filter>
                    <c:comp-filter name="VCALENDAR">
                        <c:comp-filter name="VEVENT">
                            <c:time-range start="{start_date.strftime('%Y%m%dT%H%M%SZ')}" 
                                         end="{end_date.strftime('%Y%m%dT%H%M%SZ')}"/>
                        </c:comp-filter>
                    </c:comp-filter>
                </c:filter>
            </c:calendar-query>'''
            
            response = self.session.request(
                'REPORT',
                calendar_url,
                data=report_body,
                auth=HTTPBasicAuth(username, password),
                headers={'Depth': '1'}
            )
            
            if response.status_code != 207:
                logger.error(f"Failed to fetch events from {calendar_url}: {response.status_code}")
                return []
            
            # Parse events from response
            return self.parse_calendar_events(response.text)
            
        except Exception as e:
            logger.error(f"Error fetching events from {calendar_url}: {e}")
            return []
    
    def parse_calendar_events(self, xml_content: str) -> List[Dict[str, Any]]:
        """Parse calendar events from XML response"""
        events = []
        try:
            root = ET.fromstring(xml_content)
            
            for response_elem in root.findall('.//{DAV:}response'):
                calendar_data = response_elem.find('.//{urn:ietf:params:xml:ns:caldav}calendar-data')
                
                if calendar_data is not None and calendar_data.text:
                    # Parse iCalendar data
                    events.extend(self.parse_icalendar(calendar_data.text))
            
            return events
            
        except Exception as e:
            logger.error(f"Error parsing calendar events: {e}")
            return []
    
    def parse_icalendar(self, ical_text: str) -> List[Dict[str, Any]]:
        """Parse iCalendar format to extract event information"""
        events = []
        try:
            lines = ical_text.strip().split('\n')
            current_event = {}
            in_event = False
            
            for line in lines:
                line = line.strip()
                
                if line == 'BEGIN:VEVENT':
                    in_event = True
                    current_event = {}
                elif line == 'END:VEVENT' and in_event:
                    if current_event:
                        events.append(self.process_event(current_event))
                    in_event = False
                elif in_event and ':' in line:
                    key, value = line.split(':', 1)
                    # Handle parameters (like DTSTART;VALUE=DATE)
                    if ';' in key:
                        key = key.split(';')[0]
                    current_event[key] = value
            
            return events
            
        except Exception as e:
            logger.error(f"Error parsing iCalendar: {e}")
            return []
    
    def process_event(self, raw_event: Dict[str, str]) -> Dict[str, Any]:
        """Process raw event data into standardized format"""
        try:
            event = {
                'title': raw_event.get('SUMMARY', 'Untitled Event'),
                'start': self.parse_datetime(raw_event.get('DTSTART', '')),
                'end': self.parse_datetime(raw_event.get('DTEND', '')),
                'all_day': self.is_all_day_event(raw_event.get('DTSTART', '')),
                'uid': raw_event.get('UID', ''),
                'description': raw_event.get('DESCRIPTION', ''),
                'location': raw_event.get('LOCATION', '')
            }
            
            # Calculate display date
            if event['start']:
                event['display_date'] = event['start'].strftime('%Y-%m-%d')
                event['display_time'] = '' if event['all_day'] else event['start'].strftime('%H:%M')
            
            return event
            
        except Exception as e:
            logger.error(f"Error processing event: {e}")
            return {}
    
    def parse_datetime(self, dt_string: str) -> Optional[datetime]:
        """Parse iCalendar datetime string"""
        if not dt_string:
            return None
        
        try:
            # Remove VALUE=DATE parameter if present
            dt_string = dt_string.split(':')[-1]
            
            # Handle different datetime formats
            if len(dt_string) == 8:  # YYYYMMDD (all-day)
                return datetime.strptime(dt_string, '%Y%m%d')
            elif dt_string.endswith('Z'):  # UTC
                return datetime.strptime(dt_string, '%Y%m%dT%H%M%SZ')
            elif 'T' in dt_string:  # Local time
                return datetime.strptime(dt_string, '%Y%m%dT%H%M%S')
            else:
                return datetime.strptime(dt_string, '%Y%m%d')
                
        except Exception as e:
            logger.error(f"Error parsing datetime '{dt_string}': {e}")
            return None
    
    def is_all_day_event(self, dt_string: str) -> bool:
        """Check if event is all-day based on datetime format"""
        if not dt_string:
            return False
        # All-day events typically use DATE format (8 chars) vs DATETIME
        return len(dt_string.split(':')[-1]) == 8

def fetch_all_calendars():
    """Main function to fetch events from all configured calendars"""
    logger.info("Starting calendar fetch process")
    
    # Load configuration
    config = load_config()
    if not config:
        logger.error("Failed to load configuration")
        return False
    
    # Initialize fetcher
    fetcher = iCloudCalendarFetcher()
    
    # Calculate date range
    start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + timedelta(days=config['settings']['days_ahead'])
    
    all_events = []
    
    # Process each account
    for account in config['accounts']:
        if not account['username'] or not account['password']:
            logger.warning(f"Skipping account '{account['name']}' - missing credentials")
            continue
        
        logger.info(f"Processing account: {account['name']}")
        
        # Discover calendars if not configured
        if not account['calendars']:
            logger.info(f"Discovering calendars for {account['username']}")
            calendars = fetcher.discover_calendars(account['username'], account['password'])
            account['calendars'] = calendars
            
            # Save updated config
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
        
        # Fetch events from each calendar
        for calendar in account['calendars']:
            logger.info(f"Fetching events from calendar: {calendar['name']}")
            events = fetcher.fetch_events(
                account['username'], 
                account['password'], 
                calendar['url'], 
                start_date, 
                end_date
            )
            
            # Add account/calendar info to events
            for event in events:
                event['account'] = account['name']
                event['calendar'] = calendar['name']
            
            all_events.extend(events)
    
    # Sort events by date/time
    all_events.sort(key=lambda x: x['start'] if x['start'] else datetime.min)
    
    # Save events
    success = save_events(all_events)
    logger.info(f"Completed calendar fetch: {len(all_events)} events, success: {success}")
    
    return success

if __name__ == "__main__":
    try:
        success = fetch_all_calendars()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)