#!/usr/bin/env python3
"""
Principal-based calendar home discovery
"""

import requests
from requests.auth import HTTPBasicAuth
import json
from xml.etree import ElementTree as ET

def discover_calendar_home():
    """Discover calendar home from principal"""
    
    # Load credentials
    with open('calendar_credentials.json', 'r') as f:
        config = json.load(f)
    
    username = config['accounts'][0]['username']
    password = config['accounts'][0]['password']
    
    print(f"🎯 Principal-based Calendar Home Discovery")
    print(f"🔐 Auth: {username}")
    
    # The principal we discovered
    principal_url = "https://caldav.icloud.com/1316810020/principal/"
    
    print(f"🔍 Querying principal: {principal_url}")
    
    try:
        # Query the principal for calendar-home-set
        response = requests.request(
            'PROPFIND',
            principal_url,
            auth=HTTPBasicAuth(username, password),
            headers={
                'Depth': '0',
                'Content-Type': 'application/xml; charset=utf-8',
            },
            data='''<?xml version="1.0" encoding="utf-8"?>
<D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
    <D:prop>
        <C:calendar-home-set/>
        <D:principal-URL/>
        <D:current-user-principal/>
        <D:displayname/>
    </D:prop>
</D:propfind>''',
            timeout=30
        )
        
        print(f"📋 Principal Query: {response.status_code}")
        
        if response.status_code == 207:
            print("✅ Principal query successful!")
            
            # Show response
            print(f"\n📄 Principal Response:")
            print("-" * 40)
            print(response.text)
            print("-" * 40)
            
            # Parse for calendar-home-set
            try:
                root = ET.fromstring(response.text)
                
                # Look for calendar-home-set
                calendar_home_elements = []
                for elem in root.iter():
                    if 'calendar-home-set' in str(elem.tag).lower():
                        print(f"🏠 Found calendar-home-set element: {elem.tag}")
                        
                        # Look for href within calendar-home-set
                        for href_elem in elem.iter():
                            if 'href' in str(href_elem.tag).lower() and href_elem.text:
                                calendar_home_href = href_elem.text
                                print(f"📍 Calendar home href: {calendar_home_href}")
                                
                                # Build full URL
                                if calendar_home_href.startswith('/'):
                                    calendar_home_url = f"https://caldav.icloud.com{calendar_home_href}"
                                else:
                                    calendar_home_url = calendar_home_href
                                
                                print(f"🌐 Full calendar home URL: {calendar_home_url}")
                                
                                # Now try to discover calendars at this URL
                                print(f"\n🔍 Discovering calendars at: {calendar_home_url}")
                                
                                cal_response = requests.request(
                                    'PROPFIND',
                                    calendar_home_url,
                                    auth=HTTPBasicAuth(username, password),
                                    headers={
                                        'Depth': '1',
                                        'Content-Type': 'application/xml; charset=utf-8',
                                    },
                                    data='''<?xml version="1.0" encoding="utf-8"?>
<D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
    <D:prop>
        <D:displayname/>
        <D:resourcetype/>
        <C:calendar-description/>
    </D:prop>
</D:propfind>''',
                                    timeout=30
                                )
                                
                                print(f"📅 Calendar discovery: {cal_response.status_code}")
                                
                                if cal_response.status_code == 207:
                                    print("🎉 CALENDARS FOUND!")
                                    print(f"Response length: {len(cal_response.text)}")
                                    
                                    # Parse calendar response
                                    cal_root = ET.fromstring(cal_response.text)
                                    namespaces = {
                                        'D': 'DAV:',
                                        'C': 'urn:ietf:params:xml:ns:caldav'
                                    }
                                    
                                    calendars = []
                                    for resp_elem in cal_root.findall('.//D:response', namespaces):
                                        href_elem = resp_elem.find('.//D:href', namespaces)
                                        displayname_elem = resp_elem.find('.//D:displayname', namespaces)
                                        resourcetype_elem = resp_elem.find('.//D:resourcetype', namespaces)
                                        
                                        if (href_elem is not None and 
                                            resourcetype_elem is not None and 
                                            resourcetype_elem.find('.//C:calendar', namespaces) is not None):
                                            
                                            name = displayname_elem.text if displayname_elem is not None else "Unnamed Calendar"
                                            href = href_elem.text
                                            
                                            if href.startswith('/'):
                                                url = f"https://caldav.icloud.com{href}"
                                            else:
                                                url = href
                                            
                                            calendars.append({
                                                'name': name,
                                                'href': href,
                                                'url': url
                                            })
                                            
                                            print(f"  📅 {name}: {url}")
                                    
                                    if calendars:
                                        print(f"\n🎉 SUCCESS! Found {len(calendars)} calendars!")
                                        
                                        # Update config
                                        config['accounts'][0]['calendars'] = calendars
                                        config['accounts'][0]['principal_url'] = principal_url
                                        config['accounts'][0]['calendar_home_url'] = calendar_home_url
                                        
                                        with open('calendar_credentials.json', 'w') as f:
                                            json.dump(config, f, indent=2)
                                        
                                        print("✅ Updated calendar_credentials.json")
                                        return True
                                    
                                else:
                                    print(f"❌ Calendar discovery failed: {cal_response.status_code}")
                                    print(f"Response: {cal_response.text[:200]}...")
                
                # If no calendar-home-set found, show all elements
                print("\n🔍 All elements in response:")
                for elem in root.iter():
                    if elem.text and elem.text.strip():
                        print(f"  {elem.tag}: {elem.text}")
                        
            except Exception as e:
                print(f"❌ XML parsing error: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"❌ Principal query failed: {response.status_code}")
            print(f"Response: {response.text[:300]}...")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    return False

if __name__ == "__main__":
    success = discover_calendar_home()
    if success:
        print("\n🎉🎉🎉 CALENDAR INTEGRATION SUCCESS! 🎉🎉🎉")
    else:
        print("\n🤔 Continuing investigation...")