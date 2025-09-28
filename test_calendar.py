#!/usr/bin/env python3
"""
Calendar Integration Test Script
- Tests iCloud CalDAV connection
- Validates configuration 
- Checks calendar discovery
- Verifies event fetching
"""

import sys
import json
from calendar_config import load_config, CONFIG_FILE
from calendar_fetcher import iCloudCalendarFetcher
from datetime import datetime, timedelta

def test_configuration():
    """Test if configuration file exists and is valid"""
    print("🔧 Testing configuration...")
    
    config = load_config()
    if not config:
        print("❌ Configuration file not found or invalid")
        print(f"Expected location: {CONFIG_FILE}")
        return False
    
    print("✅ Configuration loaded successfully")
    
    # Check accounts
    accounts = config.get('accounts', [])
    if not accounts:
        print("❌ No accounts configured")
        return False
    
    valid_accounts = 0
    for i, account in enumerate(accounts):
        name = account.get('name', f'Account {i+1}')
        username = account.get('username', '')
        password = account.get('password', '')
        
        if username and password:
            print(f"✅ Account '{name}': {username} (credentials present)")
            valid_accounts += 1
        else:
            print(f"⚠️  Account '{name}': Missing credentials")
    
    if valid_accounts == 0:
        print("❌ No accounts have valid credentials")
        return False
    
    print(f"✅ Found {valid_accounts} account(s) with credentials")
    return True

def test_calendar_discovery():
    """Test calendar discovery for configured accounts"""
    print("\n📅 Testing calendar discovery...")
    
    config = load_config()
    fetcher = iCloudCalendarFetcher()
    
    for account in config['accounts']:
        if not account.get('username') or not account.get('password'):
            continue
            
        name = account['name']
        username = account['username']
        password = account['password']
        
        print(f"\n🔍 Discovering calendars for {name} ({username})...")
        
        try:
            calendars = fetcher.discover_calendars(username, password)
            
            if calendars:
                print(f"✅ Found {len(calendars)} calendar(s):")
                for cal in calendars:
                    print(f"   - {cal['name']}")
                account['calendars'] = calendars
            else:
                print("❌ No calendars found or authentication failed")
                return False
                
        except Exception as e:
            print(f"❌ Error discovering calendars: {e}")
            return False
    
    # Save updated configuration with discovered calendars
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    
    print("✅ Calendar discovery completed")
    return True

def test_event_fetching():
    """Test fetching events from discovered calendars"""
    print("\n📋 Testing event fetching...")
    
    config = load_config()
    fetcher = iCloudCalendarFetcher()
    
    # Date range - next week
    start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + timedelta(days=7)
    
    total_events = 0
    
    for account in config['accounts']:
        if not account.get('username') or not account.get('password'):
            continue
        
        name = account['name']
        username = account['username']
        password = account['password']
        calendars = account.get('calendars', [])
        
        if not calendars:
            print(f"⚠️  No calendars found for {name}")
            continue
        
        print(f"\n📊 Fetching events for {name}...")
        
        account_events = 0
        for calendar in calendars:
            cal_name = calendar['name']
            cal_url = calendar['url']
            
            try:
                events = fetcher.fetch_events(username, password, cal_url, start_date, end_date)
                event_count = len(events)
                account_events += event_count
                total_events += event_count
                
                print(f"   {cal_name}: {event_count} events")
                
                # Show sample events
                for event in events[:3]:  # Show first 3 events
                    title = event.get('title', 'Untitled')
                    start = event.get('start')
                    if start:
                        print(f"     • {title} ({start.strftime('%m/%d %H:%M')})")
                    else:
                        print(f"     • {title}")
                
            except Exception as e:
                print(f"   ❌ {cal_name}: Error - {e}")
                return False
        
        print(f"✅ {name}: {account_events} total events")
    
    print(f"\n🎯 Total events found: {total_events}")
    return total_events > 0

def test_full_integration():
    """Run the full calendar fetcher as it would run in production"""
    print("\n🚀 Testing full integration...")
    
    try:
        from calendar_fetcher import fetch_all_calendars
        
        success = fetch_all_calendars()
        
        if success:
            print("✅ Full integration test passed")
            
            # Check if output file was created
            try:
                with open('/var/www/html/calendar_events.json', 'r') as f:
                    data = json.load(f)
                    events = data.get('events', [])
                    print(f"✅ Output file created with {len(events)} events")
            except FileNotFoundError:
                print("⚠️  Output file not created (may need to run as different user)")
            except Exception as e:
                print(f"⚠️  Could not read output file: {e}")
                
            return True
        else:
            print("❌ Full integration test failed")
            return False
            
    except Exception as e:
        print(f"❌ Integration test error: {e}")
        return False

def main():
    """Run all calendar integration tests"""
    print("=== WeatherPi Calendar Integration Test ===\n")
    
    # Test configuration
    if not test_configuration():
        print("\n❌ Configuration test failed!")
        print("\nNext steps:")
        print("1. Run: python3 calendar_config.py")
        print("2. Edit: /home/pi/calendar_credentials.json")
        print("3. Add your iCloud credentials")
        sys.exit(1)
    
    # Test calendar discovery
    if not test_calendar_discovery():
        print("\n❌ Calendar discovery failed!")
        print("\nNext steps:")
        print("1. Check iCloud credentials in config file")
        print("2. Verify app-specific passwords are correct")
        print("3. Ensure 2FA is properly configured")
        sys.exit(1)
    
    # Test event fetching
    if not test_event_fetching():
        print("\n❌ Event fetching failed!")
        print("\nThis might be normal if you have no events in the next week")
        print("The integration should still work correctly")
    
    # Test full integration
    if not test_full_integration():
        print("\n⚠️  Full integration test had issues")
        print("Check permissions for /var/www/html/ directory")
    
    print("\n🎉 Calendar integration testing completed!")
    print("\nIf all tests passed, your calendar integration is ready!")
    print("Run 'sudo systemctl start calendar-fetcher.service' to start syncing")

if __name__ == "__main__":
    main()