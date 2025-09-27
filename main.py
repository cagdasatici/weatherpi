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
        logging.info("Starting weather update...")
        try:
            current, forecast = self.fetch_weather()
            logging.info("Successfully fetched weather data")
            
            # Validate API response
            if not current or not forecast:
                raise ValueError("Empty API response")
            
            if 'main' not in current or 'weather' not in current or not current['weather']:
                raise ValueError("Invalid current weather data structure")
                
            if 'list' not in forecast or not forecast['list']:
                raise ValueError("Invalid forecast data structure")
            
            # Update current conditions safely
            main_data = current['main']
            weather_data = current['weather'][0]
            
            self.current_temp = f"{int(main_data.get('temp', 0))}°"
            self.feels_like = f"Feels like {int(main_data.get('feels_like', 0))}°"
            self.min_temp = f"↓{int(main_data.get('temp_min', 0))}°"
            self.max_temp = f"↑{int(main_data.get('temp_max', 0))}°"
            self.condition = weather_data.get('main', 'Unknown')
            
            # Ensure weather icon is always valid
            icon_name = self.get_weather_icon(self.condition)
            self.weather_icon = icon_name if icon_name and icon_name.strip() else 'cloud'
            
            self.date_time = datetime.now().strftime("%A, %B %d  %H:%M")
            
            # Update forecast graph
            self.update_forecast_graph(forecast)
            
            logging.info("Weather update completed successfully")
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Network error updating weather: {e}")
            self._set_error_state("Network Error")
        except ValueError as e:
            logging.error(f"Data validation error: {e}")
            self._set_error_state("Data Error")
        except Exception as e:
            logging.error(f"Unexpected error updating weather: {e}", exc_info=True)
            self._set_error_state("System Error")
    
    def _set_error_state(self, error_type):
        """Set UI to error state with fallback values"""
        self.current_temp = '--'
        self.feels_like = f"{error_type}"
        self.min_temp = '--'
        self.max_temp = '--'
        self.condition = error_type
        self.weather_icon = 'cloud'
        self.date_time = datetime.now().strftime("%A, %B %d  %H:%M")
        self.forecast_data = []

    def fetch_weather(self):
        """Fetch weather data with timeout and error handling"""
        try:
            current = requests.get(
                URL_CURRENT, 
                params={"lat": LAT, "lon": LON, "appid": API_KEY, "units": "metric"},
                timeout=10
            )
            current.raise_for_status()
            current_data = current.json()
            
            forecast = requests.get(
                URL_FORECAST, 
                params={"lat": LAT, "lon": LON, "appid": API_KEY, "units": "metric"},
                timeout=10
            )
            forecast.raise_for_status()
            forecast_data = forecast.json()
            
            return current_data, forecast_data
            
        except requests.exceptions.Timeout:
            logging.error("Weather API request timed out")
            raise
        except requests.exceptions.HTTPError as e:
            logging.error(f"Weather API HTTP error: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logging.error(f"Weather API request failed: {e}")
            raise

    def update_forecast_graph(self, forecast):
        """Update forecast graph and cards with proper error handling"""
        if not self.forecast_graph:
            logging.warning("Forecast graph not available, skipping graph update")
            return

        try:
            if 'list' not in forecast or not forecast['list']:
                logging.error("No forecast data available")
                self.forecast_data = []
                return

            temps = []
            rains = []
            times = []

            # Clear previous forecast data
            self.forecast_data = []

            # Process next 5 days of data (or however many are available)
            forecast_items = forecast['list'][:5]
            
            for i, item in enumerate(forecast_items):
                try:
                    # Safely extract data with defaults
                    temp = item.get('main', {}).get('temp', 0)
                    rain = item.get('rain', {}).get('3h', 0)
                    weather_list = item.get('weather', [{}])
                    weather_main = weather_list[0].get('main', 'Clouds') if weather_list else 'Clouds'
                    
                    temps.append(temp)
                    rains.append(rain)
                    times.append(i)

                    # Update forecast cards data
                    try:
                        forecast_day = datetime.fromtimestamp(item.get('dt', 0))
                        date_str = forecast_day.strftime('%a')
                    except (ValueError, OSError):
                        date_str = f"Day {i+1}"

                    condition = weather_main
                    icon_name = self.get_weather_icon(condition)
                    
                    # Ensure icon name is never empty
                    if not icon_name or not icon_name.strip():
                        icon_name = 'cloud'
                        
                    self.forecast_data.append({
                        'date': date_str,
                        'temp': f"{int(temp)}°" if temp else '--',
                        'condition': condition,
                        'icon': icon_name,
                        'rain_chance': f"{int(rain * 100)}%" if rain > 0 else "0%"
                    })
                    
                except Exception as e:
                    logging.error(f"Error processing forecast item {i}: {e}")
                    # Add fallback data for this item
                    self.forecast_data.append({
                        'date': f"Day {i+1}",
                        'temp': '--',
                        'condition': 'Unknown',
                        'icon': 'cloud',
                        'rain_chance': '0%'
                    })

            # Update graphs only if we have valid data
            if temps and times:
                try:
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
                    if temps:
                        self.forecast_graph.ymin = max(min(temps) - 5, -20)  # Don't go below -20
                        self.forecast_graph.ymax = min(max(temps) + 5, 50)   # Don't go above 50
                        
                    logging.info(f"Updated forecast graph with {len(temps)} data points")
                    
                except Exception as e:
                    logging.error(f"Error updating forecast graph: {e}")

        except Exception as e:
            logging.error(f"Error in update_forecast_graph: {e}", exc_info=True)
            self.forecast_data = []

    def get_weather_icon(self, condition):
        """Get weather icon name with validation that the file exists"""
        icon_map = {
            "Clear": "sun",
            "Clouds": "cloud",
            "Rain": "rain",
            "Drizzle": "drizzle",
            "Thunderstorm": "storm",
            "Snow": "snow",
            "Mist": "fog",
            "Fog": "fog",
            "Wind": "wind"
        }
        
        if not condition or not isinstance(condition, str):
            return "cloud"
        
        icon_name = icon_map.get(condition, "cloud")
        
        if not icon_name or icon_name.strip() == "":
            logging.warning("Weather icon name was empty, using 'cloud' as fallback.")
            return "cloud"
        
        # Validate that the icon file exists
        icon_path = os.path.join(os.path.dirname(__file__), 'icons', f'{icon_name}.png')
        if not os.path.exists(icon_path):
            logging.warning(f"Icon file not found: {icon_path}, using 'cloud' as fallback.")
            return "cloud"
        
        return icon_name

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
        weather_page = WeatherPage(name='weather')
        sm.add_widget(weather_page)
        sm.add_widget(CalendarPage(name='calendar'))
        sm.add_widget(BlankPage(name='blank'))
        
        # Start weather updates immediately and schedule recurring updates
        Clock.schedule_once(weather_page.update_weather, 1)
        Clock.schedule_interval(weather_page.update_weather, REFRESH_SEC)
        
        return sm

if __name__ == '__main__':
    WeatherKioskApp().run()