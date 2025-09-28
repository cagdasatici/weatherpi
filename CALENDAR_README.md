# WeatherPi Calendar Integration

Complete Apple iCloud Calendar integration for WeatherPi with swipe navigation and auto-timeout.

## 📋 Features

### ✅ **Core Functionality**
- **Real Apple iCloud CalDAV integration** (2 accounts supported)
- **Next 7 days events** with smart display
- **All-day and timed events** support  
- **Event titles only** (clean, minimal display)
- **15-minute auto-sync** with caching system
- **Account badges** to identify calendar sources

### 🎯 **User Experience** 
- **Swipe navigation** (Weather ↔ Calendar)
- **15-second auto-return** to weather after inactivity  
- **Visual countdown** warning before auto-return
- **Keyboard shortcuts** for desktop testing (Arrow keys)
- **Apple-style design** matching weather interface
- **Offline support** with cached data fallback

### 🔒 **Security & Reliability**
- **App-specific passwords** support (recommended)
- **Server-side credential storage** (not exposed to browser)
- **Graceful error handling** with fallback displays
- **Memory optimized** for Pi 3A+ (512MB constraint)

## 🚀 **Quick Setup**

### 1. **Deploy to Pi**
```bash
# On your Mac - push calendar integration
git add .
git commit -m "Complete Apple Calendar integration"
git push origin calendar-integration

# On Pi - pull and setup
ssh weatherpi
cd /var/www/html
git pull origin calendar-integration
sudo ./setup_calendar.sh
```

### 2. **Configure iCloud Accounts**
```bash
# Edit configuration with your iCloud details
sudo nano /home/pi/calendar_credentials.json
```

**Configuration Format:**
```json
{
  "accounts": [
    {
      "name": "Personal",
      "username": "your-personal@icloud.com",
      "password": "app-specific-password-here",
      "calendars": []
    },
    {
      "name": "Work", 
      "username": "your-work@icloud.com",
      "password": "app-specific-password-here",
      "calendars": []
    }
  ],
  "settings": {
    "days_ahead": 7,
    "update_interval": 900,
    "include_all_day": true,
    "include_timed": true,
    "max_events_per_day": 10
  }
}
```

### 3. **Create App-Specific Passwords**

For security, use app-specific passwords instead of main iCloud passwords:

1. Go to [appleid.apple.com](https://appleid.apple.com) 
2. **Sign In** → **App-Specific Passwords**
3. **Generate Password** → Enter "WeatherPi Calendar"
4. **Copy the generated password** (format: xxxx-xxxx-xxxx-xxxx)
5. Use this in your configuration instead of main password

### 4. **Test & Verify**
```bash
# Test calendar fetching manually
sudo systemctl start calendar-fetcher.service

# Check logs for any issues
sudo journalctl -u calendar-fetcher.service -f

# Verify calendar data file
cat /var/www/html/calendar_events.json

# Check service status
sudo systemctl status calendar-fetcher.timer
```

## 📱 **Navigation Guide**

### **From Weather to Calendar:**
- **Swipe right** → Calendar page
- **Right Arrow key** → Calendar page

### **From Calendar back to Weather:**  
- **Swipe left** → Weather page
- **Left Arrow key** → Weather page
- **Wait 15 seconds** → Auto-return to weather

### **Visual Indicators:**
- **Account badge** (first letter) shows calendar source
- **Time display** shows event times (or "All Day")
- **Countdown warning** appears 5 seconds before auto-return
- **Cache indicator** shows data age if offline

## 🛠 **Technical Architecture**

### **Components:**
1. **`calendar_fetcher.py`** - Python CalDAV client
2. **`calendar_config.py`** - Configuration management
3. **`calendar.html`** - Web interface with gestures  
4. **`setup_calendar.sh`** - Automated setup script
5. **Systemd service** - Auto-sync every 15 minutes

### **Data Flow:**
```
iCloud CalDAV → Python Fetcher → JSON File → JavaScript Display
     ↓              ↓              ↓           ↓
 App Password → HTTP Requests → Local Cache → Web UI
```

### **Files & Locations:**
- **Configuration:** `/home/pi/calendar_credentials.json`
- **Calendar Data:** `/var/www/html/calendar_events.json`
- **Python Scripts:** `/opt/weatherpi/calendar_*.py`
- **Web Files:** `/var/www/html/{calendar.html,weather.html}`
- **Logs:** `journalctl -u calendar-fetcher.service`

## 🔧 **Customization Options**

### **Display Settings** (in config):
- **`days_ahead`**: How many days to show (default: 7)
- **`max_events_per_day`**: Limit events shown (default: 10)
- **`include_all_day`**: Show all-day events (default: true)
- **`include_timed`**: Show timed events (default: true)

### **Sync Settings:**
- **`update_interval`**: Sync frequency in seconds (default: 900 = 15min)
- **Auto-return timeout**: Hardcoded 15 seconds in HTML
- **Cache retention**: 24 hours in localStorage

### **Account Management:**
- **Add more accounts**: Extend `accounts` array in config
- **Calendar filtering**: Auto-discovers all calendars per account
- **Account naming**: Customize `name` field for badge display

## 🐛 **Troubleshooting**

### **Calendar not showing:**
```bash
# Check if service is running
sudo systemctl status calendar-fetcher.timer

# Check recent logs
sudo journalctl -u calendar-fetcher.service -n 50

# Test credentials manually
cd /opt/weatherpi && python3 calendar_fetcher.py
```

### **Authentication issues:**
- ✅ Verify app-specific passwords are correct
- ✅ Check iCloud account hasn't changed 2FA settings
- ✅ Ensure usernames are complete email addresses

### **Display problems:**
- ✅ Check `/var/www/html/calendar_events.json` exists
- ✅ Verify web server permissions (`ls -la /var/www/html/`)
- ✅ Test calendar page directly: `http://weatherpi-ip/calendar.html`

### **Swipe navigation not working:**
- ✅ Try keyboard arrows instead (Left/Right)
- ✅ Check browser console for JavaScript errors
- ✅ Ensure Hammer.js CDN is accessible

## 📊 **Expected Performance**

### **Pi 3A+ Resource Usage:**
- **Memory**: ~50MB for Python fetcher (15-min intervals)
- **Storage**: ~100KB for calendar data JSON
- **Network**: ~2KB per sync (minimal CalDAV requests)
- **CPU**: <1% average (brief spikes during sync)

### **Sync Timing:**
- **Initial load**: 2-5 seconds (depends on calendar size)  
- **Cached display**: <1 second page load
- **Auto-sync**: Every 15 minutes via systemd timer
- **Manual refresh**: Swipe navigation triggers immediate check

## 🎯 **Next Steps**

Calendar integration is now **production ready**! 

**Your setup checklist:**
1. ✅ **Run setup script**: `./setup_calendar.sh` 
2. ✅ **Add iCloud credentials**: Edit config file
3. ✅ **Create app-specific passwords**: For security
4. ✅ **Test calendar sync**: Verify data appears
5. ✅ **Test navigation**: Swipe between weather/calendar
6. ✅ **Deploy to production**: Copy files to Pi web directory

**Future enhancements could include:**
- Multiple calendar views (week/month)
- Event details on tap/hover
- Calendar color coding
- Event creation via web interface
- Integration with other calendar services

The calendar integration is designed to be **lightweight, reliable, and user-friendly** while maintaining the clean aesthetic of your WeatherPi kiosk! 🌤️📅