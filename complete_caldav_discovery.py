#!/usr/bin/env python3
"""
Complete Apple CalDAV discovery with discovered principal
"""

import requests
from requests.auth import HTTPBasicAuth
import json
from xml.etree import ElementTree as ET
import urllib.parse

def complete_calendar_discovery():
    """Complete calendar discovery with the discovered principal"""
    
    # Load credentials
    with open('calendar_credentials.json', 'r') as f:
        config = json.load(f)
    
    username = config['accounts'][0]['username']
    password = config['accounts'][0]['password']
    
    print(f"🎯 Complete Apple CalDAV Discovery")
    print(f"🔐 Auth: {username}")
    print(f"🆔 Principal: /1316810020/principal/")
    
    # The discovered principal path
    principal_path = "/1316810020/principal/"
    calendar_home_path = "/1316810020/principal/calendars/"
    
    # Build full URLs
    base_url = "https://caldav.icloud.com"
    calendar_home_url = f"{base_url}{calendar_home_path}"
    
    print(f"🏠 Calendar Home: {calendar_home_url}")
    
    try:
        # PROPFIND to discover calendars
        response = requests.request(
            'PROPFIND',
            calendar_home_url,
            auth=HTTPBasicAuth(username, password),
            headers={
                'Depth': '1',
                'Content-Type': 'application/xml; charset=utf-8',
                'User-Agent': 'WeatherPi/1.0 (CalDAV)',
                'Accept': 'application/xml, text/xml'
            },
            data='''<?xml version="1.0" encoding="utf-8"?>
<D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
    <D:prop>
        <D:displayname/>
        <D:resourcetype/>
        <C:calendar-description/>
        <C:supported-calendar-component-set/>
        <C:calendar-color/>
    </D:prop>
</D:propfind>''',
            timeout=30
        )
        
        print(f"📋 Calendar Discovery: {response.status_code}")
        
        if response.status_code == 207:  # Multi-Status - Success!
            print("🎉 SUCCESS! Calendar discovery worked!")
            
            # Show raw response for debugging
            print("\n📄 Raw Response:")
            print("-" * 40)
            print(response.text[:1000] + ("..." if len(response.text) > 1000 else ""))
            print("-" * 40)
            
            # Parse calendars
            try:
                root = ET.fromstring(response.text)
                namespaces = {
                    'D': 'DAV:',
                    'C': 'urn:ietf:params:xml:ns:caldav'
                }
                
                calendars = []
                print(f"\n📅 Processing calendar responses...")
                
                for response_elem in root.findall('.//D:response', namespaces):
                    href_elem = response_elem.find('.//D:href', namespaces)
                    displayname_elem = response_elem.find('.//D:displayname', namespaces)
                    resourcetype_elem = response_elem.find('.//D:resourcetype', namespaces)
                    
                    if href_elem is not None:
                        href = href_elem.text
                        print(f"  📍 Found resource: {href}")
                        
                        # Check if this is a calendar
                        if (resourcetype_elem is not None and 
                            resourcetype_elem.find('.//C:calendar', namespaces) is not None):
                            
                            calendar_name = displayname_elem.text if displayname_elem is not None else "Unnamed Calendar"
                            
                            # Build full calendar URL
                            if href.startswith('/'):
                                calendar_url = f"{base_url}{href}"
                            else:
                                calendar_url = href
                            
                            calendar_info = {
                                'name': calendar_name,
                                'href': href,
                                'url': calendar_url
                            }
                            
                            calendars.append(calendar_info)
                            print(f"    ✅ Calendar: {calendar_name}")
                            print(f"       URL: {calendar_url}")
                
                if calendars:
                    print(f"\n🎉 FOUND {len(calendars)} CALENDARS!")
                    
                    # Update the config with discovered calendars
                    config['accounts'][0]['calendars'] = calendars
                    config['accounts'][0]['principal_url'] = f"{base_url}{principal_path}"
                    config['accounts'][0]['calendar_home_url'] = calendar_home_url
                    
                    # Save updated config
                    with open('calendar_credentials.json', 'w') as f:
                        json.dump(config, f, indent=2)
                    
                    print("💾 Updated calendar_credentials.json with calendar URLs")
                    
                    # Test fetching events from first calendar
                    if len(calendars) > 0:
                        first_calendar = calendars[0]
                        print(f"\n🧪 Testing event fetch from: {first_calendar['name']}")
                        
                        # Fetch recent events
                        from datetime import datetime, timedelta
                        now = datetime.now()
                        start = now - timedelta(days=7)
                        end = now + timedelta(days=30)
                        
                        event_response = requests.request(
                            'REPORT',
                            first_calendar['url'],
                            auth=HTTPBasicAuth(username, password),
                            headers={
                                'Depth': '1',
                                'Content-Type': 'application/xml; charset=utf-8',
                            },
                            data=f'''<?xml version="1.0" encoding="utf-8"?>
<C:calendar-query xmlns:C="urn:ietf:params:xml:ns:caldav" xmlns:D="DAV:">
    <D:prop>
        <D:getetag/>
        <C:calendar-data/>
    </D:prop>
    <C:filter>
        <C:comp-filter name="VCALENDAR">
            <C:comp-filter name="VEVENT">
                <C:time-range start="{start.strftime('%Y%m%dT%H%M%SZ')}" 
                            end="{end.strftime('%Y%m%dT%H%M%SZ')}"/>
            </C:comp-filter>
        </C:comp-filter>
    </C:filter>
</C:calendar-query>''',
                            timeout=30
                        )
                        
                        print(f"📋 Event Query: {event_response.status_code}")
                        
                        if event_response.status_code == 207:
                            print("🎉 Events fetched successfully!")
                            
                            # Count events in response
                            event_count = response.text.count('<C:calendar-data')
                            print(f"📊 Found {event_count} events")
                            
                            if event_count > 0:
                                print("✅ FULL SUCCESS! Calendar integration is working!")
                                return True
                    
                    return True
                else:
                    print("⚠️ No calendars found in response")
                    
            except ET.ParseError as e:
                print(f"❌ XML parsing error: {e}")
                
        else:
            print(f"❌ Calendar discovery failed: {response.status_code}")
            print(f"Response: {response.text[:300]}...")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    return False

if __name__ == "__main__":
    print("🎯 Complete Apple CalDAV Discovery")
    print("=" * 50)
    
    success = complete_calendar_discovery()
    
    if success:
        print("\n🎉🎉🎉 CALENDAR INTEGRATION SUCCESS! 🎉🎉🎉")
        print("✅ Apple Calendar is now connected to WeatherPi!")
        print("📅 Ready to display events on your weather dashboard!")
    else:
        print("\n🤔 Still troubleshooting...")