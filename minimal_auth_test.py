#!/usr/bin/env python3
"""
Minimal iCloud Authentication Test
Tests basic auth against Apple's servers
"""

import requests
from requests.auth import HTTPBasicAuth
import json

def minimal_auth_test():
    """Test minimal authentication against iCloud"""
    
    # Load credentials
    with open('calendar_credentials.json', 'r') as f:
        config = json.load(f)
    
    username = config['accounts'][0]['username']
    password = config['accounts'][0]['password']
    
    print(f"🔐 Testing minimal auth for: {username}")
    print(f"🔑 Password: {password}")
    
    # Test 1: Basic iCloud access
    print("\n🌐 Test 1: Basic iCloud Access")
    try:
        response = requests.get(
            "https://www.icloud.com",
            timeout=10
        )
        print(f"iCloud.com reachable: {response.status_code} ✅")
    except Exception as e:
        print(f"iCloud.com unreachable: {e} ❌")
        return
    
    # Test 2: Try the most basic CalDAV endpoint
    print("\n🔍 Test 2: Basic CalDAV Root")
    try:
        response = requests.get(
            "https://caldav.icloud.com/",
            auth=HTTPBasicAuth(username, password),
            headers={
                'User-Agent': 'WeatherPi/1.0',
                'Accept': '*/*'
            },
            timeout=15
        )
        
        print(f"CalDAV root status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if response.status_code == 401:
            print("❌ 401 Unauthorized - Wrong username/password")
        elif response.status_code == 403:
            print("❌ 403 Forbidden - App-specific password issue")
        elif response.status_code == 200:
            print("✅ 200 OK - Authentication working!")
        elif response.status_code == 400:
            print("⚠️  400 Bad Request - Wrong request format but auth might be OK")
            
    except Exception as e:
        print(f"❌ CalDAV root test failed: {e}")
    
    # Test 3: Check if it's a 2FA issue
    print("\n🔒 Test 3: Two-Factor Authentication Check")
    print("Please verify:")
    print("1. ✅ 2FA is enabled on your Apple ID")
    print("2. ✅ You generated the app-specific password AFTER enabling 2FA")
    print("3. ✅ You can log into iCloud.com with your regular password")
    print("4. ✅ Calendar is enabled/synced in iCloud settings")
    
    # Test 4: Try alternative authentication
    print("\n🧪 Test 4: Alternative URL Format")
    
    # Some users need different URL formats
    alt_urls = [
        "https://caldav.icloud.com/dav/",
        "https://p27-caldav.icloud.com/",
        "https://caldav.icloud.com/.well-known/",
    ]
    
    for url in alt_urls:
        try:
            response = requests.get(
                url,
                auth=HTTPBasicAuth(username, password),
                timeout=10,
                headers={'User-Agent': 'WeatherPi/1.0'}
            )
            print(f"{url} -> {response.status_code}")
            
            if response.status_code not in [401, 403]:
                print(f"  ⚡ Potential working endpoint!")
                
        except Exception as e:
            print(f"{url} -> Error: {e}")

if __name__ == "__main__":
    print("🔬 Minimal iCloud Authentication Test")
    print("=" * 45)
    minimal_auth_test()
    
    print("\n💡 If all tests show 403:")
    print("1. Check that Calendar is enabled in iCloud.com settings")
    print("2. Try logging into iCloud.com first")
    print("3. Make sure you're not in a restricted country/region")
    print("4. Consider that some Apple IDs have CalDAV restrictions")