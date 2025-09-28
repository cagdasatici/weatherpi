#!/usr/bin/env python3
"""
Comprehensive iCloud CalDAV Authentication Test
Tests multiple methods and provides detailed diagnostics
"""

import requests
from requests.auth import HTTPBasicAuth
import json
import base64

def test_icloud_auth():
    """Test different iCloud authentication methods"""
    
    # Load credentials
    with open('calendar_credentials.json', 'r') as f:
        config = json.load(f)
    
    username = config['accounts'][0]['username']
    password = config['accounts'][0]['password']
    apple_id = username.split('@')[0]
    
    print(f"🔐 Testing authentication for: {username}")
    print(f"🔑 Apple ID: {apple_id}")
    print(f"🔑 Password: {password}")
    print()
    
    # Test 1: Basic connectivity to iCloud
    print("🌐 Test 1: Basic iCloud Connectivity")
    try:
        response = requests.get("https://www.icloud.com", timeout=10)
        print(f"✅ iCloud reachable: {response.status_code}")
    except Exception as e:
        print(f"❌ iCloud unreachable: {e}")
    
    # Test 2: CalDAV root discovery
    print("\n🔍 Test 2: CalDAV Root Discovery")
    caldav_root = "https://caldav.icloud.com/.well-known/caldav"
    
    try:
        response = requests.get(
            caldav_root,
            auth=HTTPBasicAuth(username, password),
            timeout=15,
            allow_redirects=True
        )
        print(f"Status: {response.status_code}")
        print(f"Final URL: {response.url}")
        if 'Location' in response.headers:
            print(f"Redirect: {response.headers['Location']}")
    except Exception as e:
        print(f"❌ CalDAV discovery failed: {e}")
    
    # Test 3: Direct principal URL
    print("\n👤 Test 3: User Principal Discovery")
    principal_urls = [
        f"https://caldav.icloud.com/{apple_id}/principal/",
        f"https://caldav.icloud.com/principals/users/{apple_id}/",
        f"https://caldav.icloud.com/{apple_id}/",
    ]
    
    for url in principal_urls:
        print(f"Trying: {url}")
        try:
            response = requests.request(
                'PROPFIND',
                url,
                auth=HTTPBasicAuth(username, password),
                headers={
                    'Depth': '0',
                    'Content-Type': 'application/xml; charset=utf-8'
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
            if response.status_code == 207:
                print(f"  ✅ SUCCESS! Principal found")
                print(f"  Response: {response.text[:300]}...")
                return url
            elif response.status_code == 401:
                print("  ❌ 401 Unauthorized")
            elif response.status_code == 403:
                print("  ❌ 403 Forbidden")
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    # Test 4: Alternative authentication
    print("\n🔐 Test 4: Authentication Troubleshooting")
    
    # Check if credentials work with a simple HTTP request
    auth_string = base64.b64encode(f"{username}:{password}".encode()).decode()
    print(f"Basic auth string: Basic {auth_string[:20]}...")
    
    # Test with explicit headers
    try:
        response = requests.get(
            f"https://caldav.icloud.com/{apple_id}/",
            headers={
                'Authorization': f'Basic {auth_string}',
                'User-Agent': 'WeatherPi Calendar/1.0',
                'Accept': 'text/xml, application/xml',
            },
            timeout=15
        )
        print(f"Manual auth test: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        
    except Exception as e:
        print(f"❌ Manual auth failed: {e}")
    
    print("\n💡 Troubleshooting Guide:")
    print("1. Make sure 2FA is enabled on your Apple ID")
    print("2. Generate the app-specific password AFTER enabling 2FA")
    print("3. Copy the password exactly (no spaces)")
    print("4. Try logging into iCloud.com first to verify account")
    print("5. Check if Calendar is enabled in iCloud settings")

if __name__ == "__main__":
    test_icloud_auth()