import os
import sys
import logging
from datetime import datetime, timedelta
import requests
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.garden.graph import Graph, MeshLinePlot, SmoothLinePlot
from kivy.properties import ObjectProperty, StringProperty, ListProperty
from kivy.core.window import Window
from kivy.config import Config
from kivy.lang import Builder
Builder.load_file('weatherkiosk.kv')

# Basic Kivy configuration
Config.set('graphics', 'width', '800')
Config.set('graphics', 'height', '480')
Config.set('graphics', 'fullscreen', '1')
Config.write()

# Configuration
LAT, LON = 52.3008, 4.8639
API_KEY = os.getenv("OWM_API_KEY")
if not API_KEY:
    raise RuntimeError("Missing OWM_API_KEY in environment")

URL_CURRENT = "https://api.openweathermap.org/data/2.5/weather"
URL_FORECAST = "https://api.openweathermap.org/data/2.5/forecast"
REFRESH_SEC = 300  # 5 minutes

class ForecastCard(BoxLayout):
    date = StringProperty('')
    temp = StringProperty('')
    condition = StringProperty('')
    icon = StringProperty('')
    rain_chance = StringProperty('')
    
    def __init__(self, **kwargs):
        super(ForecastCard, self).__init__(**kwargs)
        self.orientation = 'vertical'

class WeatherGraph(Graph):
    def __init__(self, **kwargs):
        super(WeatherGraph, self).__init__(
            xlabel='Time',
            ylabel='Temperature (°C)',
            x_ticks_minor=0,
            x_ticks_major=1,
            y_ticks_major=5,
            y_grid_label=True,
            x_grid_label=True,
            padding=5,
            x_grid=True,
            y_grid=True,
            xmin=0,
            xmax=5,
            ymin=0,
            ymax=40,
            **kwargs
        )

class WeatherPage(Screen):
    current_temp = StringProperty('--')
    feels_like = StringProperty('--')
    min_temp = StringProperty('--')
    max_temp = StringProperty('--')
    condition = StringProperty('')
    date_time = StringProperty('')
    weather_icon = StringProperty('sun')  # Default icon
    forecast_data = ListProperty([])
    
    def __init__(self, **kwargs):
        super(WeatherPage, self).__init__(**kwargs)
        self.forecast_graph = None
        self.temp_plot = None
        self.rain_plot = None

    def on_kv_post(self, base_widget):
        self.forecast_graph = self.ids.get('forecast_graph')
    
    def update_weather(self, dt):
        try:
            current, forecast = self.fetch_weather()
            
            # Update current conditions
            self.current_temp = f"{int(current['main']['temp'])}°"
            self.feels_like = f"Feels like {int(current['main']['feels_like'])}°"
            self.min_temp = f"↓{int(current['main']['temp_min'])}°"
            self.max_temp = f"↑{int(current['main']['temp_max'])}°"
            self.condition = current['weather'][0]['main']
            self.date_time = datetime.now().strftime("%A, %B %d  %H:%M")
            
            # Update forecast graph
            self.update_forecast_graph(forecast)
            
        except Exception as e:
            print(f"Error updating weather: {e}")

    def fetch_weather(self):
        current = requests.get(URL_CURRENT, 
                             params={"lat": LAT, "lon": LON, 
                                    "appid": API_KEY, "units": "metric"}).json()
        forecast = requests.get(URL_FORECAST, 
                              params={"lat": LAT, "lon": LON, 
                                     "appid": API_KEY, "units": "metric"}).json()
        return current, forecast

    def update_forecast_graph(self, forecast):
        if not self.forecast_graph:
            return

        temps = []
        rains = []
        times = []

        # Clear previous forecast data
        self.forecast_data = []

        # Process next 5 days of data
        for i, item in enumerate(forecast['list'][:5]):
            temp = item['main']['temp']
            rain = item.get('rain', {}).get('3h', 0)
            temps.append(temp)
            rains.append(rain)
            times.append(i)

            # Update forecast cards data
            forecast_day = datetime.fromtimestamp(item['dt'])
            condition = item.get('weather', [{}])[0].get('main', 'Clouds')
            icon_name = self.get_weather_icon(condition)
            self.forecast_data.append({
                'date': forecast_day.strftime('%a'),
                'temp': f"{int(temp)}°",
                'condition': condition,
                'icon': icon_name,
                'rain_chance': f"{int(rain * 100)}%" if rain > 0 else "0%"
            })
        
        # Update temperature plot
        if not self.temp_plot:
            self.temp_plot = SmoothLinePlot(color=[1, 0.6, 0.2, 1])
            self.forecast_graph.add_plot(self.temp_plot)
        self.temp_plot.points = [(x, y) for x, y in zip(times, temps)]
        
        # Update rain plot
        if not self.rain_plot:
            self.rain_plot = SmoothLinePlot(color=[0.4, 0.8, 1, 0.5])
            self.forecast_graph.add_plot(self.rain_plot)
        self.rain_plot.points = [(x, y*10) for x, y in zip(times, rains)]  # Scale rain for visibility
        
        # Update graph range
        self.forecast_graph.ymin = min(temps) - 5
        self.forecast_graph.ymax = max(temps) + 5

    def get_weather_icon(self, condition):
        icon_map = {
            "Clear": "sun",
            "Clouds": "cloud",
            "Rain": "rain",
            "Drizzle": "drizzle",
            "Thunderstorm": "storm",
            "Snow": "snow",
            "Mist": "fog",
            "Fog": "fog"
        }
        if not condition or not isinstance(condition, str):
            return "cloud"
        icon = icon_map.get(condition, "cloud")
        if not icon or icon.strip() == "":
            return "cloud"
        return icon

class CalendarPage(Screen):
    pass

class BlankPage(Screen):
    pass

class WeatherKioskApp(App):
    def __init__(self, **kwargs):
        super(WeatherKioskApp, self).__init__(**kwargs)
        self.setup_logging()

    def setup_logging(self):
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'weatherpi.log')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
    def build(self):
        # Set window size to match your screen
        Window.size = (800, 480)
        logging.info("Starting Weather Kiosk Application")
        
        # Create screen manager with slide transition
        sm = ScreenManager(transition=SlideTransition())
        
        # Add pages
        sm.add_widget(WeatherPage(name='weather'))
        sm.add_widget(CalendarPage(name='calendar'))
        sm.add_widget(BlankPage(name='blank'))
        
        return sm

if __name__ == '__main__':
    WeatherKioskApp().run()