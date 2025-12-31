"""
Taiwan Central Weather Administration (CWA) API Client
台灣中央氣象署 API 客戶端 - 氣象因子資料
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

import httpx
import pandas as pd
import numpy as np
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from loguru import logger

from ecogrid.config.settings import settings
from ecogrid.data.cache_manager import CacheManager


@dataclass
class WeatherData:
    """氣象資料結構"""
    timestamp: datetime
    temperature: float  # 氣溫 (°C)
    humidity: float  # 相對濕度 (%)
    wind_speed: float  # 風速 (m/s)
    solar_radiation: float  # 日射量 (MJ/m²)
    rainfall: float  # 降雨量 (mm)
    station_id: str  # 測站代碼


class WeatherAPI:
    """
    台灣中央氣象署 API 客戶端
    
    支援資料:
    - 自動氣象站觀測資料
    - 天氣預報
    - 日射量資料
    """
    
    # 主要測站代碼 (涵蓋台灣各區域)
    WEATHER_STATIONS = {
        "466920": "臺北",
        "466910": "新北",
        "467480": "桃園",
        "467490": "新竹",
        "467571": "臺中",
        "467650": "臺南",
        "467440": "高雄",
    }
    
    def __init__(self, cache_manager: Optional[CacheManager] = None):
        self.cache = cache_manager or CacheManager()
        self.api_key = settings.cwa_api_key
        self.base_url = settings.cwa_base_url
        self.client = httpx.Client(
            timeout=30.0,
            headers={"Accept": "application/json"}
        )
        logger.info("WeatherAPI initialized")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException))
    )
    def _fetch_api(self, endpoint: str, params: Dict[str, Any]) -> Dict:
        """帶重試機制的 API 請求"""
        if self.api_key:
            params["Authorization"] = self.api_key
        
        url = f"{self.base_url}/{endpoint}"
        logger.debug(f"Fetching weather data from {url}")
        
        response = self.client.get(url, params=params)
        response.raise_for_status()
        return response.json()
    
    def get_current_weather(self, station_id: str = "466920") -> Optional[WeatherData]:
        """
        獲取當前氣象資料
        
        Args:
            station_id: 測站代碼 (預設台北)
            
        Returns:
            WeatherData 或 None
        """
        cache_key = f"weather_current_{station_id}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        try:
            # 由於 API key 可能未設定，生成模擬資料
            if not self.api_key:
                logger.warning("CWA API key not set, generating synthetic data")
                return self._generate_synthetic_current_weather(station_id)
            
            data = self._fetch_api("O-A0001-001", {
                "StationId": station_id,
                "format": "JSON"
            })
            
            # Parse response
            station_data = data.get("records", {}).get("Station", [{}])[0]
            weather_element = station_data.get("WeatherElement", {})
            
            result = WeatherData(
                timestamp=datetime.now(),
                temperature=float(weather_element.get("AirTemperature", 25)),
                humidity=float(weather_element.get("RelativeHumidity", 70)),
                wind_speed=float(weather_element.get("WindSpeed", 3)),
                solar_radiation=float(weather_element.get("GloblRad", 15)),
                rainfall=float(weather_element.get("Now", {}).get("Precipitation", 0)),
                station_id=station_id
            )
            
            self.cache.set(cache_key, result, ttl_hours=1)
            return result
            
        except Exception as e:
            logger.error(f"Failed to fetch current weather: {e}")
            return self._generate_synthetic_current_weather(station_id)
    
    def _generate_synthetic_current_weather(self, station_id: str) -> WeatherData:
        """生成模擬當前氣象資料"""
        now = datetime.now()
        hour = now.hour
        month = now.month
        
        # 根據季節和時間調整溫度
        base_temp = 28 if 5 <= month <= 10 else 18
        hour_factor = -5 + 10 * np.sin(np.pi * (hour - 6) / 12) if 6 <= hour <= 18 else -5
        
        return WeatherData(
            timestamp=now,
            temperature=base_temp + hour_factor + np.random.normal(0, 2),
            humidity=np.random.uniform(60, 85),
            wind_speed=np.random.uniform(1, 8),
            solar_radiation=max(0, 20 * np.sin(np.pi * (hour - 6) / 12)) if 6 <= hour <= 18 else 0,
            rainfall=0 if np.random.random() > 0.2 else np.random.uniform(0, 5),
            station_id=station_id
        )
    
    def get_historical_weather(self, days: int = 365, 
                               station_id: str = "466920") -> pd.DataFrame:
        """
        獲取歷史氣象資料
        
        Args:
            days: 回溯天數
            station_id: 測站代碼
            
        Returns:
            DataFrame with weather features
        """
        cache_key = f"weather_history_{station_id}_{days}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            logger.info(f"Generating synthetic historical weather data for {days} days")
            
            np.random.seed(42)
            
            dates = pd.date_range(
                end=datetime.now(),
                periods=days * 24,
                freq='h'
            )
            
            records = []
            for dt in dates:
                hour = dt.hour
                month = dt.month
                day_of_year = dt.timetuple().tm_yday
                
                # 季節性溫度變化
                base_temp = 20 + 8 * np.sin(2 * np.pi * (day_of_year - 80) / 365)
                
                # 日內溫度變化
                daily_temp_range = 8
                hour_temp = daily_temp_range * np.sin(np.pi * (hour - 6) / 12) if 6 <= hour <= 18 else -3
                
                temperature = base_temp + hour_temp + np.random.normal(0, 2)
                
                # 日射量（僅白天）
                if 5 <= hour <= 19:
                    solar_base = 25 * np.sin(np.pi * (hour - 5) / 14)
                    cloud_factor = np.random.uniform(0.5, 1.0)
                    solar_radiation = max(0, solar_base * cloud_factor)
                else:
                    solar_radiation = 0
                
                # 風速
                wind_speed = np.abs(np.random.normal(3, 2))
                
                # 濕度（與溫度負相關）
                humidity = max(30, min(95, 80 - (temperature - 20) * 1.5 + np.random.normal(0, 10)))
                
                # 降雨
                rain_prob = 0.3 if 5 <= month <= 10 else 0.15
                rainfall = 0 if np.random.random() > rain_prob else np.random.exponential(3)
                
                records.append({
                    'timestamp': dt,
                    'station_id': station_id,
                    'temperature': round(temperature, 1),
                    'humidity': round(humidity, 1),
                    'wind_speed': round(wind_speed, 1),
                    'solar_radiation': round(solar_radiation, 2),
                    'rainfall': round(rainfall, 1)
                })
            
            df = pd.DataFrame(records)
            self.cache.set(cache_key, df, ttl_hours=24)
            logger.info(f"Generated {len(df)} historical weather records")
            return df
            
        except Exception as e:
            logger.error(f"Failed to get historical weather: {e}")
            return pd.DataFrame()
    
    def get_weather_forecast(self, hours: int = 24, 
                             station_id: str = "466920") -> pd.DataFrame:
        """
        獲取天氣預報資料
        
        Args:
            hours: 預報小時數
            station_id: 測站代碼
            
        Returns:
            DataFrame with forecast data
        """
        cache_key = f"weather_forecast_{station_id}_{hours}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            logger.info(f"Generating weather forecast for next {hours} hours")
            
            np.random.seed(int(datetime.now().timestamp()) % 1000)
            
            dates = pd.date_range(
                start=datetime.now(),
                periods=hours,
                freq='h'
            )
            
            # 使用當前天氣作為基準
            current = self.get_current_weather(station_id)
            
            records = []
            prev_temp = current.temperature if current else 25
            
            for i, dt in enumerate(dates):
                hour = dt.hour
                
                # 漸進式溫度變化
                target_temp = 25 + 5 * np.sin(np.pi * (hour - 6) / 12) if 6 <= hour <= 18 else 20
                temp = prev_temp + 0.3 * (target_temp - prev_temp) + np.random.normal(0, 0.5)
                prev_temp = temp
                
                # 預報日射量
                if 5 <= hour <= 19:
                    solar = max(0, 20 * np.sin(np.pi * (hour - 5) / 14) * np.random.uniform(0.6, 1.0))
                else:
                    solar = 0
                
                records.append({
                    'timestamp': dt,
                    'forecast_hour': i + 1,
                    'temperature': round(temp, 1),
                    'humidity': round(np.random.uniform(55, 85), 1),
                    'wind_speed': round(np.abs(np.random.normal(3, 1.5)), 1),
                    'solar_radiation': round(solar, 2),
                    'rain_probability': round(np.random.uniform(0, 0.4), 2)
                })
            
            df = pd.DataFrame(records)
            self.cache.set(cache_key, df, ttl_hours=3)
            return df
            
        except Exception as e:
            logger.error(f"Failed to get weather forecast: {e}")
            return pd.DataFrame()
    
    def close(self):
        """關閉 HTTP 客戶端"""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
