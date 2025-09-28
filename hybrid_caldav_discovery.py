#!/usr/bin/env python3
"""
Hybrid Apple ID CalDAV Discovery
Gmail auth with iCloud path discovery
"""

import requests
from requests.auth import HTTPBasicAuth
import json
from xml.etree import ElementTree as ET
import urllib.parse

def hybrid_apple_id_discovery():
    """Gmail auth with iCloud path discovery"""
    
    # Load credentials
    with open('calendar_credentials.json', 'r') as f:
        config = json.load(f)
    
    username = config['accounts'][0]['username']  # cagdasatici@gmail.com
    password = config['accounts'][0]['password']
    
    print(f"🔗 Hybrid Apple ID CalDAV Discovery")
    print(f"🔐 Auth with: {username}")
    print(f"🔑 Password: {password}")
    
    # Since your accounts are linked, try both username formats for paths
    gmail_user = username.split('@')[0]  # cagdasatici
    icloud_email = f"{gmail_user}@icloud.com"  # cagdasatici@icloud.com
    
    print(f"📧 Testing paths for both: {gmail_user} and {icloud_email}")
    
    # Method 1: Gmail auth + iCloud paths
    print("\n🔗 Method 1: Gmail Auth + iCloud Paths")
    
    path_candidates = [
        # Standard iCloud paths but with Gmail auth
        f"https://caldav.icloud.com/{gmail_user}/calendars/",
        f"https://caldav.icloud.com/{gmail_user}/principal/", 
        f"https://caldav.icloud.com/principals/users/{gmail_user}/",
        # Try with .icloud.com extension in path
        f"https://caldav.icloud.com/{icloud_email.replace('@', '%40')}/calendars/",
        f"https://caldav.icloud.com/{gmail_user}.icloud.com/calendars/",
    ]
    
    for url in path_candidates:
        print(f"\nTrying: {url}")
        print(f"  Auth: {username} (Gmail)")
        
        try:
            # Try PROPFIND for calendar discovery
            response = requests.request(
                'PROPFIND',
                url,
                auth=HTTPBasicAuth(username, password),  # Gmail auth
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
    </D:prop>
</D:propfind>''',
                timeout=15
            )
            
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 207:  # Multi-Status - Success!
                print(f"  🎉 SUCCESS! Found calendars at: {url}")
                
                # Parse the response
                try:
                    root = ET.fromstring(response.text)
                    namespaces = {
                        'D': 'DAV:',
                        'C': 'urn:ietf:params:xml:ns:caldav'
                    }
                    
                    calendars = []
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
                                calendar_url = urllib.parse.urljoin(url, calendar_href)
                            else:
                                calendar_url = calendar_href
                            
                            calendars.append({
                                'name': calendar_name,
                                'href': calendar_href,
                                'url': calendar_url
                            })
                            
                            print(f"    📅 Found: {calendar_name}")
                    
                    if calendars:
                        print(f"\n🎉 BREAKTHROUGH! Found {len(calendars)} calendars!")
                        
                        # Update config
                        config['accounts'][0]['calendars'] = calendars
                        with open('calendar_credentials.json', 'w') as f:
                            json.dump(config, f, indent=2)
                        
                        print("✅ Updated calendar_credentials.json")
                        return True
                    
                except ET.ParseError as e:
                    print(f"    ⚠️ XML parsing error: {e}")
                    print(f"    Raw response: {response.text[:300]}...")
                
            elif response.status_code == 401:
                print("  ❌ 401 - Auth failed")
                return False
            elif response.status_code == 403:
                print("  ❌ 403 - Forbidden")
            elif response.status_code == 404:
                print("  ❌ 404 - Not found") 
            else:
                print(f"  ⚠️ {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    # Method 2: Try the reverse - iCloud auth paths
    print(f"\n🔄 Method 2: Alternative Discovery")
    print("Testing current-user-principal discovery...")
    
    try:
        # Try to discover the actual user principal
        response = requests.request(
            'PROPFIND',
            "https://caldav.icloud.com/",
            auth=HTTPBasicAuth(username, password),
            headers={
                'Depth': '0',
                'Content-Type': 'application/xml; charset=utf-8',
            },
            data='''<?xml version="1.0" encoding="utf-8"?>
<D:propfind xmlns:D="DAV:">
    <D:prop>
        <D:current-user-principal/>
    </D:prop>
</D:propfind>''',
            timeout=15
        )
        
        print(f"Principal discovery: {response.status_code}")
        
        if response.status_code == 207:
            print("Response content:")
            print(response.text[:500] + "..." if len(response.text) > 500 else response.text)
            
            # Try to extract the actual principal URL
            try:
                root = ET.fromstring(response.text)
                for elem in root.iter():
                    if 'current-user-principal' in str(elem.tag):
                        href = elem.find('.//{DAV:}href')
                        if href is not None:
                            principal_url = href.text
                            print(f"🎯 Found principal: {principal_url}")
                            
                            # Now try calendar discovery on the real principal
                            calendar_home_url = principal_url.rstrip('/') + '/calendars/'
                            print(f"🔍 Trying calendar home: {calendar_home_url}")
                            # Continue with calendar discovery...
                            
            except Exception as e:
                print(f"XML parsing error: {e}")
                
    except Exception as e:
        print(f"Principal discovery error: {e}")
    
    return False

if __name__ == "__main__":
    print("🔗 Hybrid Apple ID CalDAV Discovery")
    print("=" * 50)
    
    success = hybrid_apple_id_discovery()
    
    if success:
        print("\n🎉 SUCCESS! Calendar integration configured!")
        print("🧪 Ready to test calendar fetching!")
    else:
        print("\n🤔 Still investigating the path structure...")
        print("💡 Your linked accounts make this tricky - Apple's internal routing is complex")