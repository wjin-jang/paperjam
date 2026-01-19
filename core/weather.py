"""
Weather data fetching and caching.

Uses Open-Meteo API (free, no API key required).
Caches weather data locally and updates when internet is available.
"""
import json
import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.request import urlopen, Request
from urllib.error import URLError

import config as cfg

logger = logging.getLogger(__name__)

# Cache file for weather data
WEATHER_CACHE_FILE = cfg.DATA_DIR / "weather_cache.json"
WEATHER_CONFIG_FILE = cfg.CONFIG_DIR / "weather.json"

# Open-Meteo API endpoints
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

# Update interval (1 hour)
UPDATE_INTERVAL = 3600

# Weather condition codes to icons/descriptions
# Based on WMO Weather interpretation codes
WMO_CODES = {
    0: ('clear', '☀'),
    1: ('mostly_clear', '🌤'),
    2: ('partly_cloudy', '⛅'),
    3: ('overcast', '☁'),
    45: ('fog', '🌫'),
    48: ('fog', '🌫'),
    51: ('drizzle', '🌧'),
    53: ('drizzle', '🌧'),
    55: ('drizzle', '🌧'),
    56: ('freezing_drizzle', '🌧'),
    57: ('freezing_drizzle', '🌧'),
    61: ('rain', '🌧'),
    63: ('rain', '🌧'),
    65: ('heavy_rain', '🌧'),
    66: ('freezing_rain', '🌧'),
    67: ('freezing_rain', '🌧'),
    71: ('snow', '❄'),
    73: ('snow', '❄'),
    75: ('heavy_snow', '❄'),
    77: ('snow_grains', '❄'),
    80: ('rain_showers', '🌦'),
    81: ('rain_showers', '🌦'),
    82: ('heavy_showers', '🌦'),
    85: ('snow_showers', '🌨'),
    86: ('snow_showers', '🌨'),
    95: ('thunderstorm', '⛈'),
    96: ('thunderstorm_hail', '⛈'),
    99: ('thunderstorm_hail', '⛈'),
}


@dataclass
class HourlyForecast:
    """Hourly weather forecast data."""
    time: str  # ISO format
    temperature: float  # Celsius
    precipitation_probability: int  # Percentage
    weather_code: int

    @property
    def hour(self) -> str:
        """Get hour string (e.g., '14:00')."""
        try:
            dt = datetime.fromisoformat(self.time)
            return dt.strftime("%H:%M")
        except (ValueError, TypeError):
            return "00:00"

    @property
    def condition(self) -> Tuple[str, str]:
        """Get condition name and icon."""
        return WMO_CODES.get(self.weather_code, ('unknown', '?'))


@dataclass
class DailyForecast:
    """Daily weather forecast data."""
    date: str  # ISO format (YYYY-MM-DD)
    temperature_max: float
    temperature_min: float
    precipitation_probability: int
    weather_code: int

    @property
    def day_name(self) -> str:
        """Get short day name (e.g., 'MON')."""
        try:
            dt = datetime.fromisoformat(self.date)
            return dt.strftime("%a").upper()
        except (ValueError, TypeError):
            return "???"

    @property
    def avg_temperature(self) -> float:
        """Get average temperature."""
        return (self.temperature_max + self.temperature_min) / 2

    @property
    def condition(self) -> Tuple[str, str]:
        """Get condition name and icon."""
        return WMO_CODES.get(self.weather_code, ('unknown', '?'))


@dataclass
class CurrentWeather:
    """Current weather conditions."""
    temperature: float
    weather_code: int
    wind_speed: float  # km/h
    humidity: int  # Percentage
    precipitation_probability: int  # From hourly data

    @property
    def condition(self) -> Tuple[str, str]:
        """Get condition name and icon."""
        return WMO_CODES.get(self.weather_code, ('unknown', '?'))


@dataclass
class WeatherData:
    """Complete weather data structure."""
    location_name: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    current: Optional[CurrentWeather] = None
    hourly: List[HourlyForecast] = field(default_factory=list)
    daily: List[DailyForecast] = field(default_factory=list)
    last_updated: float = 0.0  # Unix timestamp

    def is_stale(self) -> bool:
        """Check if data needs updating."""
        return time.time() - self.last_updated > UPDATE_INTERVAL

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'location_name': self.location_name,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'current': asdict(self.current) if self.current else None,
            'hourly': [asdict(h) for h in self.hourly],
            'daily': [asdict(d) for d in self.daily],
            'last_updated': self.last_updated
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'WeatherData':
        """Create from dictionary."""
        wd = cls(
            location_name=data.get('location_name', ''),
            latitude=data.get('latitude', 0.0),
            longitude=data.get('longitude', 0.0),
            last_updated=data.get('last_updated', 0.0)
        )

        if data.get('current'):
            wd.current = CurrentWeather(**data['current'])

        wd.hourly = [HourlyForecast(**h) for h in data.get('hourly', [])]
        wd.daily = [DailyForecast(**d) for d in data.get('daily', [])]

        return wd


@dataclass
class WeatherConfig:
    """Weather app configuration."""
    location_name: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    units: str = "metric"  # metric or imperial

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'WeatherConfig':
        return cls(**{k: v for k, v in data.items() if k in ['location_name', 'latitude', 'longitude', 'units']})


class WeatherManager:
    """Manages weather data fetching and caching."""

    def __init__(self):
        self._data: Optional[WeatherData] = None
        self._config: WeatherConfig = WeatherConfig()
        self._lock = threading.Lock()
        self._updating = False
        self._last_error: Optional[str] = None

        self._load_config()
        self._load_cache()

    @property
    def data(self) -> Optional[WeatherData]:
        """Get current weather data."""
        with self._lock:
            return self._data

    @property
    def config(self) -> WeatherConfig:
        """Get weather configuration."""
        return self._config

    @property
    def is_updating(self) -> bool:
        """Check if update is in progress."""
        return self._updating

    @property
    def last_error(self) -> Optional[str]:
        """Get last error message."""
        return self._last_error

    @property
    def is_configured(self) -> bool:
        """Check if location is configured."""
        return self._config.latitude != 0.0 and self._config.longitude != 0.0

    def _load_config(self):
        """Load configuration from disk."""
        if WEATHER_CONFIG_FILE.exists():
            try:
                with open(WEATHER_CONFIG_FILE, 'r') as f:
                    self._config = WeatherConfig.from_dict(json.load(f))
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"Error loading weather config: {e}")

    def _save_config(self):
        """Save configuration to disk."""
        try:
            with open(WEATHER_CONFIG_FILE, 'w') as f:
                json.dump(self._config.to_dict(), f)
        except OSError as e:
            logger.error(f"Error saving weather config: {e}")

    def _load_cache(self):
        """Load cached weather data from disk."""
        if WEATHER_CACHE_FILE.exists():
            try:
                with open(WEATHER_CACHE_FILE, 'r') as f:
                    self._data = WeatherData.from_dict(json.load(f))
                logger.info(f"Loaded cached weather for {self._data.location_name}")
            except (json.JSONDecodeError, OSError, TypeError) as e:
                logger.error(f"Error loading weather cache: {e}")

    def _save_cache(self):
        """Save weather data to disk."""
        if self._data:
            try:
                with open(WEATHER_CACHE_FILE, 'w') as f:
                    json.dump(self._data.to_dict(), f)
            except OSError as e:
                logger.error(f"Error saving weather cache: {e}")

    def set_location(self, name: str, latitude: float, longitude: float):
        """Set location for weather data."""
        self._config.location_name = name
        self._config.latitude = latitude
        self._config.longitude = longitude
        self._save_config()

        # Clear cached data for new location
        self._data = None
        if WEATHER_CACHE_FILE.exists():
            WEATHER_CACHE_FILE.unlink()

    def set_units(self, units: str):
        """Set temperature units ('metric' or 'imperial')."""
        self._config.units = units
        self._save_config()

    def search_location(self, query: str) -> List[dict]:
        """Search for a location by name."""
        try:
            url = f"{GEOCODING_URL}?name={query}&count=5&language=en&format=json"
            req = Request(url, headers={'User-Agent': 'PaperJam/1.0'})

            with urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                results = data.get('results', [])
                return [
                    {
                        'name': r.get('name', ''),
                        'country': r.get('country', ''),
                        'admin1': r.get('admin1', ''),  # State/region
                        'latitude': r.get('latitude', 0),
                        'longitude': r.get('longitude', 0)
                    }
                    for r in results
                ]
        except (URLError, json.JSONDecodeError, OSError) as e:
            logger.error(f"Location search error: {e}")
            self._last_error = str(e)
            return []

    def update_async(self):
        """Start async weather update."""
        if self._updating or not self.is_configured:
            return

        self._updating = True
        thread = threading.Thread(target=self._update_worker, daemon=True)
        thread.start()

    def update_sync(self) -> bool:
        """Synchronous weather update. Returns True on success."""
        if not self.is_configured:
            self._last_error = "Location not configured"
            return False

        return self._fetch_weather()

    def _update_worker(self):
        """Background worker for weather updates."""
        try:
            self._fetch_weather()
        finally:
            self._updating = False

    def _fetch_weather(self) -> bool:
        """Fetch weather data from API."""
        self._last_error = None

        try:
            # Build API URL
            params = [
                f"latitude={self._config.latitude}",
                f"longitude={self._config.longitude}",
                "current=temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m",
                "hourly=temperature_2m,precipitation_probability,weather_code",
                "daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "timezone=auto",
                "forecast_days=7"
            ]

            if self._config.units == 'imperial':
                params.append("temperature_unit=fahrenheit")
                params.append("wind_speed_unit=mph")

            url = f"{WEATHER_URL}?{'&'.join(params)}"
            req = Request(url, headers={'User-Agent': 'PaperJam/1.0'})

            with urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode())

            # Parse response
            weather = WeatherData(
                location_name=self._config.location_name,
                latitude=self._config.latitude,
                longitude=self._config.longitude,
                last_updated=time.time()
            )

            # Current weather
            current_data = data.get('current', {})
            hourly_data = data.get('hourly', {})

            # Get current hour's precipitation probability
            current_precip = 0
            if hourly_data.get('precipitation_probability'):
                current_precip = hourly_data['precipitation_probability'][0]

            weather.current = CurrentWeather(
                temperature=current_data.get('temperature_2m', 0),
                weather_code=current_data.get('weather_code', 0),
                wind_speed=current_data.get('wind_speed_10m', 0),
                humidity=current_data.get('relative_humidity_2m', 0),
                precipitation_probability=current_precip
            )

            # Hourly forecasts (next 24 hours)
            hourly_times = hourly_data.get('time', [])[:24]
            hourly_temps = hourly_data.get('temperature_2m', [])[:24]
            hourly_precip = hourly_data.get('precipitation_probability', [])[:24]
            hourly_codes = hourly_data.get('weather_code', [])[:24]

            for i, t in enumerate(hourly_times):
                weather.hourly.append(HourlyForecast(
                    time=t,
                    temperature=hourly_temps[i] if i < len(hourly_temps) else 0,
                    precipitation_probability=hourly_precip[i] if i < len(hourly_precip) else 0,
                    weather_code=hourly_codes[i] if i < len(hourly_codes) else 0
                ))

            # Daily forecasts (7 days)
            daily_data = data.get('daily', {})
            daily_dates = daily_data.get('time', [])
            daily_max = daily_data.get('temperature_2m_max', [])
            daily_min = daily_data.get('temperature_2m_min', [])
            daily_precip = daily_data.get('precipitation_probability_max', [])
            daily_codes = daily_data.get('weather_code', [])

            for i, d in enumerate(daily_dates):
                weather.daily.append(DailyForecast(
                    date=d,
                    temperature_max=daily_max[i] if i < len(daily_max) else 0,
                    temperature_min=daily_min[i] if i < len(daily_min) else 0,
                    precipitation_probability=daily_precip[i] if i < len(daily_precip) else 0,
                    weather_code=daily_codes[i] if i < len(daily_codes) else 0
                ))

            with self._lock:
                self._data = weather

            self._save_cache()
            logger.info(f"Weather updated for {weather.location_name}")
            return True

        except URLError as e:
            self._last_error = "No internet connection"
            logger.error(f"Weather fetch error: {e}")
            return False
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            self._last_error = f"Parse error: {e}"
            logger.error(f"Weather parse error: {e}")
            return False
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"Weather error: {e}")
            return False

    def needs_update(self) -> bool:
        """Check if weather data needs updating."""
        if not self._data:
            return True
        return self._data.is_stale()

    def get_temperature_unit(self) -> str:
        """Get temperature unit symbol."""
        return "°F" if self._config.units == 'imperial' else "°C"

    def get_speed_unit(self) -> str:
        """Get wind speed unit."""
        return "mph" if self._config.units == 'imperial' else "km/h"
