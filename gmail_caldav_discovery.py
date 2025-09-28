#!/usr/bin/env python3
"""
Gmail Apple ID CalDAV Discovery
Special handling for Gmail-based Apple IDs
"""

import requests
from requests.auth import HTTPBasicAuth
import json
import hashlib
import urllib.parse

def gmail_apple_id_discovery():
    """Special CalDAV discovery for Gmail-based Apple IDs"""
    
    # Load credentials
    with open('calendar_credentials.json', 'r') as f:
        config = json.load(f)
    
    username = config['accounts'][0]['username']
    password = config['accounts'][0]['password']
    
    print(f"🔍 Gmail Apple ID CalDAV Discovery for: {username}")
    print(f"🔑 Using password: {password}")
    
    # For Gmail Apple IDs, the CalDAV path is different
    # Apple uses a hash-based system for non-icloud emails
    
    # Method 1: Try common Gmail Apple ID patterns
    print("\n📍 Method 1: Common Gmail Apple ID Patterns")
    
    # Extract the username part
    email_user = username.split('@')[0]  # cagdasatici
    
    # Apple sometimes uses different formats for Gmail Apple IDs
    url_patterns = [
        f"https://caldav.icloud.com/{email_user}/",
        f"https://caldav.icloud.com/users/{email_user}/",
        f"https://caldav.icloud.com/{username}/",  # Full email
        f"https://caldav.icloud.com/users/{username}/",  # Full email with users
        # Try with URL encoding
        f"https://caldav.icloud.com/{urllib.parse.quote(username, safe='')}/",
    ]
    
    for url in url_patterns:
        print(f"Trying: {url}")
        
        try:
            response = requests.request(
                'PROPFIND',
                url,
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
            
            if response.status_code == 207:  # Success!
                print(f"  ✅ SUCCESS! Working URL: {url}")
                return url
            elif response.status_code == 401:
                print("  ❌ 401 - Invalid credentials")
                return None
            elif response.status_code == 403:
                print("  ❌ 403 - Forbidden")
            elif response.status_code == 404:
                print("  ❌ 404 - Not found")
            else:
                print(f"  ⚠️ {response.status_code} - {response.text[:100] if response.text else 'No content'}")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    # Method 2: Try alternative CalDAV servers
    print("\n📍 Method 2: Alternative CalDAV Servers")
    
    alt_servers = [
        "https://p27-caldav.icloud.com",
        "https://p41-caldav.icloud.com", 
        "https://p57-caldav.icloud.com",
    ]
    
    for server in alt_servers:
        for path_pattern in [f"/{email_user}/", f"/{username}/"]:
            url = server + path_pattern
            print(f"Trying: {url}")
            
            try:
                response = requests.get(
                    url,
                    auth=HTTPBasicAuth(username, password),
                    headers={'User-Agent': 'WeatherPi/1.0'},
                    timeout=10
                )
                
                print(f"  Status: {response.status_code}")
                
                if response.status_code not in [401, 403, 404]:
                    print(f"  ⚡ Potential working server: {server}")
                    
            except Exception as e:
                print(f"  ❌ Error: {e}")
    
    # Method 3: Check if CalDAV is enabled for this Apple ID
    print("\n🔍 Method 3: CalDAV Availability Check")
    
    try:
        # Try a very basic request to see what Apple returns
        response = requests.options(
            "https://caldav.icloud.com/",
            auth=HTTPBasicAuth(username, password),
            timeout=10
        )
        
        print(f"OPTIONS request: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if 'Allow' in response.headers:
            print(f"Allowed methods: {response.headers['Allow']}")
            
        if response.status_code == 403:
            print("\n❌ 403 Forbidden on OPTIONS - Possible causes:")
            print("1. CalDAV is not enabled for Gmail-based Apple IDs")
            print("2. Your region restricts CalDAV access")
            print("3. Your Apple ID has specific limitations")
            print("4. iCloud Calendar sync is disabled")
            
    except Exception as e:
        print(f"OPTIONS request failed: {e}")
    
    print("\n💡 Gmail Apple ID CalDAV Issues:")
    print("- Some Gmail Apple IDs have limited CalDAV access")
    print("- Try enabling Calendar sync in iCloud settings first")
    print("- Consider using the iOS Calendar app to verify sync works")
    
    return None

if __name__ == "__main__":
    print("📧 Gmail Apple ID CalDAV Discovery")
    print("=" * 50)
    
    working_url = gmail_apple_id_discovery()
    
    if working_url:
        print(f"\n🎉 SUCCESS! Working CalDAV URL: {working_url}")
    else:
        print(f"\n❌ No working CalDAV endpoint found")
        print("\n🚧 Next steps:")
        print("1. Verify Calendar sync is enabled in iCloud settings")
        print("2. Try using a different calendar client to test")
        print("3. Consider that Gmail Apple IDs may have CalDAV restrictions")