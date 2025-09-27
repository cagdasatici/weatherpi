import os
import logging
import requests
from datetime import datetime
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.properties import StringProperty
from kivy.clock import Clock
from kivy.core.window import Window
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

class WeatherPage(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Create UI programmatically
        main_layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        
        # Current weather section
        current_layout = BoxLayout(orientation='horizontal', size_hint_y=0.6)
        
        # Left side - temperature and condition
        left_layout = BoxLayout(orientation='vertical')
        
        self.temp_label = Label(
            text="--°", 
            font_size='48sp', 
            color=(1, 1, 1, 1),
            size_hint_y=0.4
        )
        self.condition_label = Label(
            text="Loading...", 
            font_size='24sp', 
            color=(0.8, 0.8, 0.8, 1),
            size_hint_y=0.3
        )
        self.feels_label = Label(
            text="Feels like --°", 
            font_size='18sp', 
            color=(0.7, 0.7, 0.7, 1),
            size_hint_y=0.3
        )
        
        left_layout.add_widget(self.temp_label)
        left_layout.add_widget(self.condition_label)
        left_layout.add_widget(self.feels_label)
        
        # Right side - date and min/max
        right_layout = BoxLayout(orientation='vertical')
        
        self.date_label = Label(
            text="Loading...", 
            font_size='16sp', 
            color=(0.8, 0.8, 0.8, 1),
            size_hint_y=0.5
        )
        self.minmax_label = Label(
            text="--° / --°", 
            font_size='18sp', 
            color=(0.9, 0.9, 0.9, 1),
            size_hint_y=0.5
        )
        
        right_layout.add_widget(self.date_label)
        right_layout.add_widget(self.minmax_label)
        
        current_layout.add_widget(left_layout)
        current_layout.add_widget(right_layout)
        
        # Forecast section
        self.forecast_label = Label(
            text="Loading forecast...", 
            font_size='14sp', 
            color=(0.8, 0.8, 0.8, 1),
            text_size=(None, None),
            halign='left',
            valign='top',
            size_hint_y=0.4
        )
        
        main_layout.add_widget(current_layout)
        main_layout.add_widget(self.forecast_label)
        
        self.add_widget(main_layout)
        
        # Initialize data
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
            
            self.temp_label.text = f"{int(main['temp'])}°"
            self.condition_label.text = weather['main']
            self.feels_label.text = f"Feels like {int(main['feels_like'])}°"
            self.minmax_label.text = f"↓{int(main['temp_min'])}° / ↑{int(main['temp_max'])}°"
            self.date_label.text = datetime.now().strftime("%A, %B %d  %H:%M")
            
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
                    
            self.forecast_label.text = "\n".join(forecast_lines)
            # Set text_size for proper text wrapping
            self.forecast_label.text_size = (self.forecast_label.width, None)
            
            logging.info("Weather UI updated successfully")
            
        except Exception as e:
            logging.error(f"Error updating UI: {e}")
            self.set_error_state("Display Error")
    
    def set_error_state(self, error_msg):
        """Set error state"""
        self.temp_label.text = "--°"
        self.condition_label.text = f"Error: {error_msg}"
        self.feels_label.text = "Unable to fetch data"
        self.forecast_label.text = "Please check network connection"
    
    def update_weather(self, dt):
        """Start weather update in background thread"""
        logging.info("Starting weather update...")
        thread = Thread(target=self.fetch_weather_thread)
        thread.daemon = True
        thread.start()

class CalendarPage(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout()
        label = Label(text="Calendar Page", font_size='24sp')
        layout.add_widget(label)
        self.add_widget(layout)

class BlankPage(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout()
        self.add_widget(layout)

class WeatherKioskApp(App):
    def build(self):
        # Set window size
        Window.size = (800, 480)
        
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