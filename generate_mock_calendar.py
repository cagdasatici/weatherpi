#!/usr/bin/env python3
"""
Mock Calendar Data Generator
Creates sample calendar events for testing the UI while debugging auth
"""

import json
from datetime import datetime, timedelta
import random

def generate_mock_events():
    """Generate sample calendar events for testing"""
    
    # Sample event types
    event_types = [
        ("Meeting with team", "💼"),
        ("Doctor appointment", "🏥"),
        ("Dentist", "🦷"),
        ("Lunch with friends", "🍽️"),
        ("Gym workout", "💪"),
        ("Family dinner", "👨‍👩‍👧‍👦"),
        ("Movie night", "🎬"),
        ("Shopping", "🛒"),
        ("Birthday party", "🎂"),
        ("Conference call", "📞"),
        ("Travel", "✈️"),
        ("Weekend getaway", "🏖️")
    ]
    
    events = []
    base_date = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    
    # Generate events for next 7 days
    for day in range(7):
        current_date = base_date + timedelta(days=day)
        
        # Random number of events per day (0-4)
        num_events = random.randint(0, 4)
        
        for event_num in range(num_events):
            event_name, emoji = random.choice(event_types)
            
            # Random time during the day
            hour = random.randint(8, 20)
            minute = random.choice([0, 15, 30, 45])
            
            event_start = current_date.replace(hour=hour, minute=minute)
            
            # Random duration (30min to 3 hours)
            duration = random.choice([30, 60, 90, 120, 180])
            event_end = event_start + timedelta(minutes=duration)
            
            # All-day event sometimes
            all_day = random.random() < 0.15  # 15% chance
            
            if all_day:
                event_start = current_date.replace(hour=0, minute=0)
                event_end = event_start + timedelta(days=1)
            
            events.append({
                "id": f"mock_{day}_{event_num}",
                "title": f"{emoji} {event_name}",
                "start": event_start.isoformat(),
                "end": event_end.isoformat(),
                "all_day": all_day,
                "description": f"Sample {event_name.lower()} event",
                "calendar": "Personal Mock Calendar"
            })
    
    return events

def save_mock_calendar_data():
    """Save mock calendar data to JSON file"""
    
    events = generate_mock_events()
    
    calendar_data = {
        "last_updated": datetime.now().isoformat(),
        "accounts": [
            {
                "name": "Personal iCloud (Mock)",
                "calendars": [
                    {
                        "name": "Personal Mock Calendar",
                        "events": events
                    }
                ]
            }
        ],
        "total_events": len(events),
        "status": "mock_data",
        "next_update": (datetime.now() + timedelta(minutes=15)).isoformat()
    }
    
    # Save to calendar events file
    with open('calendar_events.json', 'w') as f:
        json.dump(calendar_data, f, indent=2)
    
    print(f"📅 Generated {len(events)} mock calendar events")
    print("📁 Saved to: calendar_events.json")
    print("🌐 Calendar UI should now show sample events!")
    
    # Show summary
    today_events = [e for e in events if e['start'][:10] == datetime.now().strftime('%Y-%m-%d')]
    tomorrow_events = [e for e in events if e['start'][:10] == (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')]
    
    print(f"\n📊 Summary:")
    print(f"   Today: {len(today_events)} events")
    print(f"   Tomorrow: {len(tomorrow_events)} events")
    print(f"   This week: {len(events)} events total")
    
    return calendar_data

if __name__ == "__main__":
    print("🧪 Generating Mock Calendar Data")
    print("=" * 40)
    save_mock_calendar_data()
    print("\n💡 Now you can test the calendar UI while we fix authentication!")