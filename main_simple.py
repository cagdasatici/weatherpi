import os
import logging
import requests
from datetime import datetime
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from threading import Thread
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# API Configuration
OWM_API_KEY = os.getenv('OWM_API_KEY', '98cea08ababd57c4fa475e6481b6f4c0')
LAT = 52.3008
LON = 4.8639
URL_CURRENT = "https://api.openweathermap.org/data/2.5/weather"
URL_FORECAST = "https://api.openweathermap.org/data/2.5/forecast"

# Simple KV string without graph
KV = '''
<WeatherPage>:
    BoxLayout:
        orientation: 'vertical'
        padding: 20
        spacing: 10
        
        # Current weather
        BoxLayout:
            orientation: 'horizontal'
            size_hint_y: 0.6
            
            BoxLayout:
                orientation: 'vertical'
                
                Label:
                    text: root.current_temp
                    font_size: '48sp'
                    color: 1, 1, 1, 1
                    
                Label:
                    text: root.condition
                    font_size: '24sp'
                    color: 0.8, 0.8, 0.8, 1
                    
                Label:
                    text: root.feels_like
                    font_size: '18sp'
                    color: 0.7, 0.7, 0.7, 1
                    
            BoxLayout:
                orientation: 'vertical'
                
                Label:
                    text: root.date_time
                    font_size: '16sp'
                    color: 0.8, 0.8, 0.8, 1
                    
                Label:
                    text: f"{root.min_temp} / {root.max_temp}"
                    font_size: '18sp'
                    color: 0.9, 0.9, 0.9, 1
                    
        # Simple forecast
        BoxLayout:
            orientation: 'horizontal'
            size_hint_y: 0.4
            spacing: 10
            
            Label:
                text: root.forecast_text
                font_size: '14sp'
                color: 0.8, 0.8, 0.8, 1
                text_size: self.size
                halign: 'left'
                valign: 'top'

<CalendarPage>:
    Label:
        text: "Calendar Page"
        font_size: '24sp'

<BlankPage>:
    Label:
        text: ""
'''

class WeatherPage(Screen):
    current_temp = StringProperty("--°")
    condition = StringProperty("Loading...")
    feels_like = StringProperty("Feels like --°")
    min_temp = StringProperty("--°")
    max_temp = StringProperty("--°")
    date_time = StringProperty("Loading...")
    forecast_text = StringProperty("Loading forecast...")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.weather_data = {}
        
    def fetch_weather_thread(self):
        """Fetch weather data in background thread"""
        try:
            # Current weather
            current_params = {
                'lat': LAT, 'lon': LON, 'appid': OWM_API_KEY, 'units': 'metric'
            }
            current_response = requests.get(URL_CURRENT, params=current_params, timeout=10)
            current_response.raise_for_status()
            current_data = current_response.json()
            
            # Forecast
            forecast_response = requests.get(URL_FORECAST, params=current_params, timeout=10)
            forecast_response.raise_for_status()
            forecast_data = forecast_response.json()
            
            # Schedule UI update on main thread
            Clock.schedule_once(lambda dt: self.update_ui(current_data, forecast_data), 0)
            
        except Exception as e:
            logging.error(f"Error fetching weather: {e}")
            Clock.schedule_once(lambda dt: self.set_error_state(str(e)), 0)
    
    def update_ui(self, current_data, forecast_data):
        """Update UI on main thread"""
        try:
            # Current weather
            main = current_data['main']
            weather = current_data['weather'][0]
            
            self.current_temp = f"{int(main['temp'])}°"
            self.condition = weather['main']
            self.feels_like = f"Feels like {int(main['feels_like'])}°"
            self.min_temp = f"↓{int(main['temp_min'])}°"
            self.max_temp = f"↑{int(main['temp_max'])}°"
            self.date_time = datetime.now().strftime("%A, %B %d  %H:%M")
            
            # Simple forecast text
            forecast_lines = []
            for item in forecast_data['list'][:5]:
                try:
                    day = datetime.fromtimestamp(item['dt']).strftime('%a')
                    temp = int(item['main']['temp'])
                    condition = item['weather'][0]['main']
                    forecast_lines.append(f"{day}: {temp}° {condition}")
                except:
                    continue
                    
            self.forecast_text = "\\n".join(forecast_lines)
            
            logging.info("Weather UI updated successfully")
            
        except Exception as e:
            logging.error(f"Error updating UI: {e}")
            self.set_error_state("Display Error")
    
    def set_error_state(self, error_msg):
        """Set error state"""
        self.current_temp = "--°"
        self.condition = f"Error: {error_msg}"
        self.feels_like = "Unable to fetch data"
        self.forecast_text = "Please check network connection"
    
    def update_weather(self, dt):
        """Start weather update in background thread"""
        logging.info("Starting weather update...")
        thread = Thread(target=self.fetch_weather_thread)
        thread.daemon = True
        thread.start()

class CalendarPage(Screen):
    pass

class BlankPage(Screen):
    pass

class WeatherKioskApp(App):
    def build(self):
        # Set window size
        Window.size = (800, 480)
        
        # Load KV
        Builder.load_string(KV)
        
        # Create screen manager
        sm = ScreenManager()
        
        # Add pages
        weather_page = WeatherPage(name='weather')
        sm.add_widget(weather_page)
        sm.add_widget(CalendarPage(name='calendar'))
        sm.add_widget(BlankPage(name='blank'))
        
        # Start weather updates
        Clock.schedule_once(weather_page.update_weather, 2)  # Initial delay
        Clock.schedule_interval(weather_page.update_weather, 300)  # Every 5 minutes
        
        logging.info("Weather Kiosk App started")
        return sm

if __name__ == '__main__':
    WeatherKioskApp().run()