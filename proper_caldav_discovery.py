#!/usr/bin/env python3
"""
Proper iCloud CalDAV Discovery Implementation
Following Apple's CalDAV specification exactly
"""

import requests
from requests.auth import HTTPBasicAuth
import json
from xml.etree import ElementTree as ET
import urllib.parse

def proper_icloud_discovery():
    """Implement proper CalDAV discovery sequence for iCloud"""
    
    # Load credentials
    with open('calendar_credentials.json', 'r') as f:
        config = json.load(f)
    
    username = config['accounts'][0]['username']
    password = config['accounts'][0]['password']
    
    print(f"🔍 Starting proper CalDAV discovery for: {username}")
    print(f"🔑 Using password: {password}")
    
    # Step 1: Well-known CalDAV discovery
    print("\n📍 Step 1: Well-known CalDAV Discovery")
    well_known_url = "https://caldav.icloud.com/.well-known/caldav"
    
    try:
        response = requests.get(
            well_known_url,
            auth=HTTPBasicAuth(username, password),
            allow_redirects=False,
            timeout=15,
            headers={
                'User-Agent': 'WeatherPi/1.0 (CalDAV)',
                'Accept': 'text/xml, application/xml, text/plain'
            }
        )
        
        print(f"Status: {response.status_code}")
        if response.status_code in [301, 302, 307, 308]:
            principal_url = response.headers.get('Location')
            print(f"✅ Redirected to: {principal_url}")
        else:
            print("❌ No redirect - trying manual discovery")
            principal_url = None
            
    except Exception as e:
        print(f"❌ Well-known discovery failed: {e}")
        principal_url = None
    
    # Step 2: Find user principal
    if not principal_url:
        print("\n👤 Step 2: Manual Principal Discovery")
        # Try common iCloud principal paths
        principal_candidates = [
            f"https://caldav.icloud.com/{username.split('@')[0]}/principal/",
            f"https://caldav.icloud.com/principals/{username.split('@')[0]}/",
            f"https://caldav.icloud.com/{username.split('@')[0]}/"
        ]
        
        for candidate in principal_candidates:
            print(f"Trying: {candidate}")
            
            try:
                response = requests.request(
                    'PROPFIND',
                    candidate,
                    auth=HTTPBasicAuth(username, password),
                    headers={
                        'Depth': '0',
                        'Content-Type': 'application/xml; charset=utf-8',
                        'User-Agent': 'WeatherPi/1.0 (CalDAV)',
                        'Accept': 'application/xml, text/xml'
                    },
                    data='''<?xml version="1.0" encoding="utf-8"?>
<D:propfind xmlns:D="DAV:">
    <D:prop>
        <D:current-user-principal/>
        <D:principal-URL/>
        <D:displayname/>
    </D:prop>
</D:propfind>''',
                    timeout=15
                )
                
                print(f"  Status: {response.status_code}")
                
                if response.status_code == 207:  # Multi-Status success
                    principal_url = candidate
                    print(f"  ✅ Found principal at: {principal_url}")
                    break
                elif response.status_code == 401:
                    print("  ❌ 401 - Invalid credentials")
                    return False
                elif response.status_code == 403:
                    print("  ❌ 403 - Check app-specific password")
                    continue
                    
            except Exception as e:
                print(f"  ❌ Error: {e}")
                continue
    
    if not principal_url:
        print("❌ Could not find user principal")
        return False
    
    # Step 3: Find calendar home set
    print(f"\n🏠 Step 3: Finding Calendar Home Set from {principal_url}")
    
    try:
        response = requests.request(
            'PROPFIND',
            principal_url,
            auth=HTTPBasicAuth(username, password),
            headers={
                'Depth': '0',
                'Content-Type': 'application/xml; charset=utf-8',
                'User-Agent': 'WeatherPi/1.0 (CalDAV)'
            },
            data='''<?xml version="1.0" encoding="utf-8"?>
<D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
    <D:prop>
        <C:calendar-home-set/>
    </D:prop>
</D:propfind>''',
            timeout=15
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code != 207:
            print("❌ Failed to get calendar home set")
            return False
        
        # Parse response to find calendar home set
        root = ET.fromstring(response.text)
        
        # Look for calendar-home-set
        calendar_home = None
        for elem in root.iter():
            if elem.tag.endswith('calendar-home-set'):
                href = elem.find('.//{DAV:}href')
                if href is not None:
                    calendar_home = href.text
                    break
        
        if calendar_home:
            if not calendar_home.startswith('http'):
                calendar_home = urllib.parse.urljoin(principal_url, calendar_home)
            print(f"✅ Calendar home set: {calendar_home}")
        else:
            print("❌ No calendar home set found")
            return False
            
    except Exception as e:
        print(f"❌ Error finding calendar home set: {e}")
        return False
    
    # Step 4: Discover calendars
    print(f"\n📅 Step 4: Discovering Calendars at {calendar_home}")
    
    try:
        response = requests.request(
            'PROPFIND',
            calendar_home,
            auth=HTTPBasicAuth(username, password),
            headers={
                'Depth': '1',
                'Content-Type': 'application/xml; charset=utf-8',
                'User-Agent': 'WeatherPi/1.0 (CalDAV)'
            },
            data='''<?xml version="1.0" encoding="utf-8"?>
<D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
    <D:prop>
        <D:displayname/>
        <D:resourcetype/>
        <C:calendar-description/>
        <C:supported-calendar-component-set/>
    </D:prop>
</D:propfind>''',
            timeout=15
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code != 207:
            print(f"❌ Failed to discover calendars: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False
        
        # Parse calendars
        root = ET.fromstring(response.text)
        calendars = []
        
        namespaces = {
            'D': 'DAV:',
            'C': 'urn:ietf:params:xml:ns:caldav'
        }
        
        for response_elem in root.findall('.//D:response', namespaces):
            href_elem = response_elem.find('.//D:href', namespaces)
            displayname_elem = response_elem.find('.//D:displayname', namespaces)
            resourcetype_elem = response_elem.find('.//D:resourcetype', namespaces)
            
            # Check if this is a calendar
            if (href_elem is not None and 
                resourcetype_elem is not None and 
                resourcetype_elem.find('.//C:calendar', namespaces) is not None):
                
                calendar_name = displayname_elem.text if displayname_elem is not None else "Unnamed Calendar"
                calendar_href = href_elem.text
                
                if not calendar_href.startswith('http'):
                    calendar_url = urllib.parse.urljoin(calendar_home, calendar_href)
                else:
                    calendar_url = calendar_href
                
                calendars.append({
                    'name': calendar_name,
                    'href': calendar_href,
                    'url': calendar_url
                })
                
                print(f"✅ Found calendar: {calendar_name}")
                print(f"   URL: {calendar_url}")
        
        if calendars:
            print(f"\n🎉 SUCCESS! Found {len(calendars)} calendars")
            
            # Update config file with discovered calendars
            config['accounts'][0]['calendars'] = calendars
            with open('calendar_credentials.json', 'w') as f:
                json.dump(config, f, indent=2)
            
            print("💾 Updated calendar_credentials.json with discovered calendars")
            return True
        else:
            print("❌ No calendars found")
            return False
            
    except Exception as e:
        print(f"❌ Error discovering calendars: {e}")
        return False

if __name__ == "__main__":
    print("🍎 Proper iCloud CalDAV Discovery")
    print("=" * 50)
    
    if proper_icloud_discovery():
        print("\n🎉 Calendar discovery completed successfully!")
        print("🧪 Ready to fetch calendar events!")
    else:
        print("\n❌ Calendar discovery failed")
        print("🔧 Check credentials and try generating a new app-specific password")