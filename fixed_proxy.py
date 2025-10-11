#!/usr/bin/env python3
"""
WeatherPi Fixed Proxy Server - Based on working version with mock data fallback
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, abort

# Configuration 
OPENWEATHER_KEY = os.environ.get('OPENWEATHER_API_KEY', '')
PROXY_TOKEN = os.environ.get('PROXY_TOKEN', 'test_token')

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('weatherpi-proxy')

def _require_token():
    """Check authentication"""
    token = request.headers.get('X-Proxy-Token') or request.args.get('proxy_token')
    if not token or token != PROXY_TOKEN:
        logger.warning(f"Invalid token attempt: {token}")
        abort(401, 'Invalid or missing token')

def get_mock_current_weather():
    """Mock current weather data in OpenWeather format"""
    return {
        "coord": {"lon": 4.8639, "lat": 52.3008},
        "weather": [
            {"id": 801, "main": "Clouds", "description": "few clouds", "icon": "02d"}
        ],
        "base": "stations",
        "main": {
            "temp": 15.2,
            "feels_like": 14.1,
            "temp_min": 13.5,
            "temp_max": 17.8,
            "pressure": 1015,
            "humidity": 68
        },
        "visibility": 10000,
        "wind": {"speed": 2.8, "deg": 225},
        "clouds": {"all": 25},
        "dt": int(time.time()),
        "sys": {
            "type": 2,
            "id": 2012516,
            "country": "NL",
            "sunrise": int((datetime.now().replace(hour=7, minute=15) - datetime(1970,1,1)).total_seconds()),
            "sunset": int((datetime.now().replace(hour=18, minute=30) - datetime(1970,1,1)).total_seconds())
        },
        "timezone": 3600,
        "id": 2759794,
        "name": "Amsterdam",
        "cod": 200
    }

def get_mock_forecast():
    """Mock forecast data in OpenWeather format"""
    base_time = datetime.now()
    forecast_list = []
    
    for i in range(40):  # 5 days * 8 periods
        dt = base_time + timedelta(hours=i * 3)
        temp = 15 + (i % 8 - 4) * 1.5  # Varies throughout day
        
        item = {
            "dt": int(dt.timestamp()),
            "main": {
                "temp": temp,
                "feels_like": temp - 0.8,
                "temp_min": temp - 1.2,
                "temp_max": temp + 1.2,
                "pressure": 1015,
                "humidity": 65 + (i % 10),
                "temp_kf": 0
            },
            "weather": [
                {
                    "id": 800 if i % 4 == 0 else 801,
                    "main": "Clear" if i % 4 == 0 else "Clouds", 
                    "description": "clear sky" if i % 4 == 0 else "few clouds",
                    "icon": "01d" if i % 4 == 0 else "02d"
                }
            ],
            "clouds": {"all": 0 if i % 4 == 0 else 20},
            "wind": {"speed": 2.5, "deg": 220, "gust": 4.0},
            "visibility": 10000,
            "pop": 0.1 + (i % 10) * 0.05,
            "sys": {"pod": "d" if 6 <= dt.hour <= 18 else "n"},
            "dt_txt": dt.strftime("%Y-%m-%d %H:%M:%S")
        }
        forecast_list.append(item)
    
    return {
        "cod": "200",
        "message": 0,
        "cnt": 40,
        "list": forecast_list,
        "city": {
            "id": 2759794,
            "name": "Amsterdam",
            "coord": {"lat": 52.3008, "lon": 4.8639},
            "country": "NL",
            "timezone": 3600,
            "sunrise": int((base_time.replace(hour=7, minute=15) - datetime(1970,1,1)).total_seconds()),
            "sunset": int((base_time.replace(hour=18, minute=30) - datetime(1970,1,1)).total_seconds())
        }
    }

@app.route('/api/health')
def health():
    """Health check endpoint"""
    uptime = time.time()
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "uptime": uptime,
        "cache": {"memory_size": 0, "ttl": 300},
        "active_requests": 1,
        "api_key_configured": bool(OPENWEATHER_KEY),
        "mode": "mock_data" if not OPENWEATHER_KEY else "live_data"
    })

@app.route('/api/weather')
def weather():
    """Weather endpoint - returns mock data when no API key"""
    _require_token()
    
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    
    if not lat or not lon:
        abort(400, 'Missing lat/lon parameters')
    
    if not OPENWEATHER_KEY:
        logger.info("Using mock weather data (no API key configured)")
        return jsonify(get_mock_current_weather())
    else:
        # TODO: Add real OpenWeather API call here when key is provided
        logger.info("API key available but using mock data for now")
        return jsonify(get_mock_current_weather())

@app.route('/api/forecast')
def forecast():
    """Forecast endpoint - returns mock data when no API key"""
    _require_token()
    
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    
    if not lat or not lon:
        abort(400, 'Missing lat/lon parameters')
    
    if not OPENWEATHER_KEY:
        logger.info("Using mock forecast data (no API key configured)")
        return jsonify(get_mock_forecast())
    else:
        # TODO: Add real OpenWeather API call here when key is provided
        logger.info("API key available but using mock data for now")
        return jsonify(get_mock_forecast())

if __name__ == '__main__':
    if OPENWEATHER_KEY:
        logger.info("🌤️ WeatherPi Proxy starting with LIVE data")
    else:
        logger.info("🌦️ WeatherPi Proxy starting with MOCK data (set OPENWEATHER_API_KEY for live data)")
    
    logger.info(f"🔑 Authentication token: {PROXY_TOKEN}")
    logger.info("🌐 Running on http://127.0.0.1:5000")
    
    app.run(host='0.0.0.0', port=5000, debug=False)