#!/usr/bin/env python3
"""
Enhanced iCloud Calendar Diagnostic Tool
Tests different CalDAV endpoints and authentication methods
"""

import requests
import json
from requests.auth import HTTPBasicAuth
import ssl
import urllib3

# Suppress SSL warnings for testing
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_icloud_caldav():
    """Test iCloud CalDAV connection with detailed diagnostics"""
    
    # Load credentials
    try:
        with open('calendar_credentials.json', 'r') as f:
            config = json.load(f)
        
        account = config['accounts'][0]
        username = account['username']
        password = account['password']
        
        print(f"🔐 Testing credentials for: {username}")
        print(f"🔑 App-specific password: {password[:4]}...{password[-4:]}")
        
    except Exception as e:
        print(f"❌ Failed to load credentials: {e}")
        return False
    
    # Different iCloud CalDAV endpoints to try
    caldav_urls = [
        f"https://caldav.icloud.com/{username.split('@')[0]}/calendars/",
        f"https://p01-caldav.icloud.com/{username.split('@')[0]}/calendars/",
        f"https://p02-caldav.icloud.com/{username.split('@')[0]}/calendars/",
        f"https://p03-caldav.icloud.com/{username.split('@')[0]}/calendars/",
        "https://caldav.icloud.com/published/2/",
        f"https://caldav.icloud.com/{username}/calendars/",
    ]
    
    print("\n🌐 Testing different CalDAV endpoints...")
    
    for i, url in enumerate(caldav_urls, 1):
        print(f"\n{i}. Testing: {url}")
        
        try:
            # Test basic connectivity
            response = requests.get(
                url,
                auth=HTTPBasicAuth(username, password),
                timeout=30,
                verify=True,  # Use SSL verification
                headers={
                    'User-Agent': 'WeatherPi Calendar/1.0',
                    'Content-Type': 'application/xml',
                }
            )
            
            print(f"   Status: {response.status_code}")
            print(f"   Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                print("   ✅ SUCCESS! This endpoint works")
                return url
            elif response.status_code == 401:
                print("   ❌ 401 Unauthorized - Check credentials")
            elif response.status_code == 403:
                print("   ❌ 403 Forbidden - Check permissions/2FA")
            elif response.status_code == 404:
                print("   ❌ 404 Not Found - Wrong URL")
            else:
                print(f"   ⚠️  Unexpected status: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                
        except requests.exceptions.SSLError as e:
            print(f"   ❌ SSL Error: {e}")
        except requests.exceptions.ConnectTimeout:
            print("   ❌ Connection timeout")
        except requests.exceptions.ConnectionError as e:
            print(f"   ❌ Connection error: {e}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print("\n🔍 Additional Diagnostics:")
    
    # Test Apple ID login page
    try:
        response = requests.get("https://appleid.apple.com", timeout=10)
        print(f"✅ Apple ID reachable: {response.status_code}")
    except:
        print("❌ Apple ID not reachable")
    
    # Test basic iCloud
    try:
        response = requests.get("https://www.icloud.com", timeout=10)
        print(f"✅ iCloud reachable: {response.status_code}")
    except:
        print("❌ iCloud not reachable")
    
    print("\n💡 Troubleshooting suggestions:")
    print("1. Generate a NEW App-Specific Password at appleid.apple.com")
    print("2. Make sure 2FA is enabled on your Apple ID")
    print("3. Try signing into iCloud on the web first")
    print("4. Check if CalDAV is enabled in iCloud settings")
    
    return False

def test_manual_caldav():
    """Test manual CalDAV request"""
    print("\n🧪 Manual CalDAV Test:")
    
    try:
        with open('calendar_credentials.json', 'r') as f:
            config = json.load(f)
        
        account = config['accounts'][0]
        username = account['username']
        password = account['password']
        
        # Try the most common iCloud CalDAV URL
        url = "https://caldav.icloud.com/"
        
        print(f"Testing basic auth to: {url}")
        
        response = requests.request(
            'PROPFIND',
            url,
            auth=HTTPBasicAuth(username, password),
            headers={
                'Depth': '1',
                'Content-Type': 'application/xml; charset=utf-8',
                'User-Agent': 'WeatherPi/1.0'
            },
            data='''<?xml version="1.0" encoding="utf-8" ?>
                <D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
                    <D:prop>
                        <D:displayname />
                        <D:resourcetype />
                        <C:calendar-description />
                    </D:prop>
                </D:propfind>''',
            timeout=30
        )
        
        print(f"Response: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        if response.text:
            print(f"Body: {response.text[:500]}...")
            
    except Exception as e:
        print(f"❌ Manual test failed: {e}")

if __name__ == "__main__":
    print("🍎 Enhanced iCloud CalDAV Diagnostics")
    print("=" * 50)
    
    working_url = test_icloud_caldav()
    test_manual_caldav()
    
    if working_url:
        print(f"\n🎉 SUCCESS! Working CalDAV URL: {working_url}")
    else:
        print(f"\n❌ No working CalDAV endpoint found")
        print("\n🔧 Next steps:")
        print("1. Generate a fresh App-Specific Password")
        print("2. Double-check your Apple ID has 2FA enabled")
        print("3. Try logging into iCloud.com first")