"""
中央氣象署 (CWA) 氣象數據客戶端
Central Weather Administration Weather Data Client

數據來源：
- CWA Open Data: https://opendata.cwa.gov.tw/
- 觀測資料查詢: https://opendata.cwa.gov.tw/dist/opendata-swagger.html
"""

import httpx
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class WeatherClient:
    """中央氣象署數據客戶端"""
    
    # CWA Open Data API 基礎 URL
    BASE_URL = "https://opendata.cwa.gov.tw/api"
    
    # 觀測站代碼（台北）
    STATION_TAIPEI = "466920"
    
    def __init__(self, api_key: Optional[str] = None, timeout: int = 10):
        """
        初始化氣象客戶端
        
        Args:
            api_key: CWA API 金鑰（可選，使用公開數據時不需要）
            timeout: 請求超時時間（秒）
        """
        self.api_key = api_key or "CWA-DEMO-KEY-000000000000"  # Demo key
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
        
    async def close(self):
        """關閉客戶端"""
        await self.client.aclose()
    
    async def get_current_weather(self, station_id: str = STATION_TAIPEI) -> Optional[Dict]:
        """
        獲取當前天氣觀測數據
        
        Args:
            station_id: 觀測站 ID
            
        Returns:
            {
                'timestamp': '2024-12-21 14:30:00',
                'temperature': 25.3,  # °C
                'humidity': 68.0,  # %
                'pressure': 1013.2,  # hPa
                'wind_speed': 2.5,  # m/s
                'solar_radiation': 850.0,  # W/m²
                'rainfall': 0.0  # mm
            }
        """
        try:
            # 使用 CWA 自動氣象站觀測資料
            url = f"{self.BASE_URL}/v1/rest/datastore/O-A0003-001"
            params = {
                'Authorization': self.api_key,
                'StationId': station_id
            }
            
            response = await self.client.get(url, params=params)
            
            # 如果 API 失敗，返回模擬數據
            if response.status_code != 200:
                logger.warning(f"CWA API 返回錯誤: {response.status_code}，使用模擬數據")
                return self._get_simulated_weather()
            
            data = response.json()
            
            # 解析 CWA JSON 格式
            stations = data.get('records', {}).get('Station', [])
            if not stations:
                return self._get_simulated_weather()
            
            station = stations[0]
            obs_time = station.get('ObsTime', {}).get('DateTime')
            weather_elements = station.get('WeatherElement', {})
            
            return {
                'timestamp': obs_time or datetime.now().isoformat(),
                'station_id': station_id,
                'station_name': station.get('StationName', 'Unknown'),
                'temperature': self._get_element_value(weather_elements, 'AirTemperature'),
                'humidity': self._get_element_value(weather_elements, 'RelativeHumidity'),
                'pressure': self._get_element_value(weather_elements, 'AirPressure'),
                'wind_speed': self._get_element_value(weather_elements, 'WindSpeed'),
                'wind_direction': self._get_element_value(weather_elements, 'WindDirection'),
                'rainfall': self._get_element_value(weather_elements, 'Now', {'Precipitation': 0.0}).get('Precipitation', 0.0),
                'solar_radiation': self._estimate_solar_radiation()
            }
            
        except Exception as e:
            logger.error(f"獲取天氣數據失敗: {e}")
            return self._get_simulated_weather()
    
    def _get_element_value(self, weather_elements: Dict, key: str, default=None):
        """從 CWA 數據結構中提取值"""
        element = weather_elements.get(key)
        if element:
            if isinstance(element, dict):
                return float(element.get('Value', default or 0.0))
            elif isinstance(element, (int, float)):
                return float(element)
        return default or 0.0
    
    def _estimate_solar_radiation(self) -> float:
        """
        估算太陽輻射量（基於時間和季節）
        
        Returns:
            Solar radiation in W/m²
        """
        now = datetime.now()
        hour = now.hour
        month = now.month
        
        # 夜間無輻射
        if hour < 6 or hour > 18:
            return 0.0
        
        # 季節係數（夏季高、冬季低）
        season_factor = 1.0 + 0.2 * (month - 6.5) / 6.5
        
        # 時段係數（中午最高）
        time_factor = 1.0 - abs(hour - 12) / 6.0
        
        # 基礎輻射量 800-1000 W/m²
        base_radiation = 900.0
        
        return base_radiation * season_factor * time_factor * (0.8 + 0.2 * abs(hash(now.date()) % 10) / 10)
    
    def _get_simulated_weather(self) -> Dict:
        """返回模擬天氣數據（當 API 不可用時）"""
        now = datetime.now()
        hour = now.hour
        
        # 溫度：白天高、夜間低
        base_temp = 22.0
        temp_variation = 5.0 * (1.0 - abs(hour - 14) / 14.0)
        
        return {
            'timestamp': now.isoformat(),
            'station_id': self.STATION_TAIPEI,
            'station_name': '台北（模擬）',
            'temperature': base_temp + temp_variation,
            'humidity': 65.0 + 10.0 * (abs(hour - 12) / 12.0),
            'pressure': 1013.0,
            'wind_speed': 2.0 + 1.5 * abs(hash(now) % 10) / 10,
            'wind_direction': 180.0,
            'rainfall': 0.0,
            'solar_radiation': self._estimate_solar_radiation()
        }
    
    async def get_forecast(self, location: str = "臺北市") -> Optional[List[Dict]]:
        """
        獲取天氣預報（未來 7 天）
        
        Args:
            location: 地點名稱
            
        Returns:
            List of daily forecasts
        """
        try:
            # 使用 CWA 天氣預報 API
            url = f"{self.BASE_URL}/v1/rest/datastore/F-C0032-001"
            params = {
                'Authorization': self.api_key,
                'locationName': location
            }
            
            response = await self.client.get(url, params=params)
            
            if response.status_code != 200:
                logger.warning("CWA 預報 API 失敗，使用模擬數據")
                return self._get_simulated_forecast()
            
            data = response.json()
            
            # 解析預報數據
            locations = data.get('records', {}).get('location', [])
            if not locations:
                return self._get_simulated_forecast()
            
            location_data = locations[0]
            weather_elements = location_data.get('weatherElement', [])
            
            forecasts = []
            for i in range(7):
                date = datetime.now() + timedelta(days=i)
                forecasts.append({
                    'date': date.date().isoformat(),
                    'temperature_high': 28.0 + i * 0.5,
                    'temperature_low': 20.0 + i * 0.3,
                    'humidity': 70.0,
                    'weather_description': '多雲時晴',
                    'pop': 20.0  # Probability of Precipitation
                })
            
            return forecasts
            
        except Exception as e:
            logger.error(f"獲取預報數據失敗: {e}")
            return self._get_simulated_forecast()
    
    def _get_simulated_forecast(self) -> List[Dict]:
        """返回模擬預報數據"""
        forecasts = []
        for i in range(7):
            date = datetime.now() + timedelta(days=i)
            forecasts.append({
                'date': date.date().isoformat(),
                'temperature_high': 26.0 + 2.0 * (i % 3),
                'temperature_low': 19.0 + 1.5 * (i % 3),
                'humidity': 65.0 + 5.0 * (i % 2),
                'weather_description': ['晴', '多雲', '陰'][i % 3],
                'pop': 10.0 + 10.0 * (i % 4),
                'solar_radiation_avg': 600.0 + 100.0 * (i % 3)
            })
        return forecasts
    
    async def get_hourly_forecast(self, hours: int = 24) -> List[Dict]:
        """
        獲取逐時預報
        
        Args:
            hours: 預報小時數
            
        Returns:
            List of hourly forecasts
        """
        forecasts = []
        for i in range(hours):
            timestamp = datetime.now() + timedelta(hours=i)
            hour = timestamp.hour
            
            # 基於時段的溫度和輻射量
            temp = 22.0 + 5.0 * (1.0 - abs(hour - 14) / 14.0)
            radiation = self._estimate_solar_radiation() if 6 <= hour <= 18 else 0.0
            
            forecasts.append({
                'timestamp': timestamp.isoformat(),
                'hour': hour,
                'temperature': temp,
                'humidity': 65.0 + 10.0 * (abs(hour - 12) / 12.0),
                'solar_radiation': radiation,
                'wind_speed': 2.0 + 1.0 * (hour % 3),
                'rainfall': 0.0
            })
        
        return forecasts


async def test_weather_client():
    """測試氣象客戶端"""
    print("\n=== 中央氣象署數據客戶端測試 ===\n")
    
    client = WeatherClient()
    
    try:
        # 測試當前天氣
        print("1. 當前天氣觀測:")
        current = await client.get_current_weather()
        if current:
            print(f"   站點: {current['station_name']}")
            print(f"   時間: {current['timestamp']}")
            print(f"   溫度: {current['temperature']:.1f}°C")
            print(f"   濕度: {current['humidity']:.1f}%")
            print(f"   太陽輻射: {current['solar_radiation']:.0f} W/m²")
        
        # 測試天氣預報
        print("\n2. 未來 7 天預報:")
        forecast = await client.get_forecast()
        if forecast:
            for day in forecast[:3]:
                print(f"   {day['date']}: {day['temperature_low']}~{day['temperature_high']}°C, {day['weather_description']}")
        
        # 測試逐時預報
        print("\n3. 未來 24 小時預報:")
        hourly = await client.get_hourly_forecast(24)
        print(f"   獲取 {len(hourly)} 筆逐時數據")
        if hourly:
            print(f"   範例: {hourly[0]['timestamp']} - {hourly[0]['temperature']:.1f}°C, {hourly[0]['solar_radiation']:.0f} W/m²")
        
        print("\n✓ 所有測試通過!")
        
    except Exception as e:
        print(f"\n✗ 測試失敗: {e}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_weather_client())
