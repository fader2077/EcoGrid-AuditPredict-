"""
Taiwan Power API Client
台電資料 API 客戶端 - 電力供需、再生能源、時間電價
"""

import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

import httpx
import pandas as pd
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from loguru import logger

from ecogrid.config.settings import settings
from ecogrid.data.cache_manager import CacheManager


@dataclass
class PowerSupplyData:
    """電力供需資料結構"""
    timestamp: datetime
    load_mw: float  # 負載 (MW)
    supply_mw: float  # 供電 (MW)
    reserve_mw: float  # 備轉容量 (MW)
    reserve_rate: float  # 備轉容量率 (%)


@dataclass
class RenewableData:
    """再生能源資料結構"""
    timestamp: datetime
    solar_mw: float  # 太陽能 (MW)
    wind_mw: float  # 風力 (MW)
    hydro_mw: float  # 水力 (MW)
    total_renewable_mw: float  # 總再生能源 (MW)


class TaiwanPowerAPI:
    """
    台電資料 API 客戶端
    
    支援資料來源:
    - 台電今日電力資訊 (即時)
    - 台電過去電力供需資訊 (歷史)
    - 台電再生能源發電量
    - 台電時間電價表
    """
    
    # API Endpoints
    TAIPOWER_REALTIME_URL = "https://www.taipower.com.tw/d006/loadGraph/loadGraph/data/loadpara.txt"
    TAIPOWER_RENEWABLE_URL = "https://www.taipower.com.tw/d006/loadGraph/loadGraph/data/genloadareaperc.csv"
    TAIPOWER_HISTORY_URL = "https://www.taipower.com.tw/d006/loadGraph/loadGraph/data/sys_dem_sup.csv"
    
    def __init__(self, cache_manager: Optional[CacheManager] = None):
        self.cache = cache_manager or CacheManager()
        self.client = httpx.Client(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        logger.info("TaiwanPowerAPI initialized")
    
    @retry(
        stop=stop_after_attempt(settings.taipower_retry_attempts),
        wait=wait_exponential(multiplier=1, min=2, max=settings.taipower_retry_delay * 2),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException))
    )
    def _fetch_data(self, url: str) -> str:
        """帶重試機制的資料擷取"""
        logger.debug(f"Fetching data from {url}")
        response = self.client.get(url)
        response.raise_for_status()
        return response.text
    
    def get_realtime_power(self) -> Optional[PowerSupplyData]:
        """
        獲取即時電力供需資訊
        
        Returns:
            PowerSupplyData 或 None (失敗時)
        """
        cache_key = "taipower_realtime"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        try:
            data = self._fetch_data(self.TAIPOWER_REALTIME_URL)
            # Parse the JSON-like format
            import json
            power_data = json.loads(data)
            
            result = PowerSupplyData(
                timestamp=datetime.now(),
                load_mw=float(power_data.get("curr_load", 0)),
                supply_mw=float(power_data.get("curr_util_rate", 0)),
                reserve_mw=float(power_data.get("curr_reserve", 0)),
                reserve_rate=float(power_data.get("curr_reserve_rate", 0))
            )
            
            self.cache.set(cache_key, result, ttl_hours=1)
            return result
            
        except Exception as e:
            logger.error(f"Failed to fetch realtime power data: {e}")
            return None
    
    def get_historical_load(self, days: int = 365) -> pd.DataFrame:
        """
        獲取歷史電力負載資料
        
        Args:
            days: 回溯天數
            
        Returns:
            DataFrame with columns: [timestamp, load_mw, max_load_mw, min_load_mw]
        """
        cache_key = f"taipower_history_{days}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            # 生成模擬歷史資料（實際應從台電API獲取）
            logger.info(f"Generating synthetic historical load data for {days} days")
            
            import numpy as np
            np.random.seed(42)
            
            dates = pd.date_range(
                end=datetime.now(),
                periods=days * 24,
                freq='h'
            )
            
            # 模擬台灣電力負載模式
            base_load = 25000  # 基礎負載 MW
            hourly_pattern = np.array([
                0.75, 0.72, 0.70, 0.68, 0.67, 0.70,  # 0-5
                0.78, 0.88, 0.95, 1.00, 1.02, 1.00,  # 6-11
                0.98, 1.05, 1.08, 1.10, 1.05, 1.00,  # 12-17
                0.95, 0.92, 0.88, 0.85, 0.82, 0.78   # 18-23
            ])
            
            loads = []
            for dt in dates:
                hour = dt.hour
                month = dt.month
                
                # 季節性調整（夏季用電高峰）
                seasonal_factor = 1.2 if 6 <= month <= 9 else 1.0
                
                # 週末效應
                weekend_factor = 0.85 if dt.weekday() >= 5 else 1.0
                
                # 計算負載
                load = (base_load * hourly_pattern[hour] * seasonal_factor * 
                       weekend_factor * (1 + np.random.normal(0, 0.05)))
                loads.append(max(load, base_load * 0.5))
            
            df = pd.DataFrame({
                'timestamp': dates,
                'load_mw': loads
            })
            
            self.cache.set(cache_key, df, ttl_hours=24)
            logger.info(f"Generated {len(df)} historical load records")
            return df
            
        except Exception as e:
            logger.error(f"Failed to get historical load: {e}")
            return pd.DataFrame()
    
    def get_renewable_generation(self, days: int = 365) -> pd.DataFrame:
        """
        獲取再生能源發電資料
        
        Returns:
            DataFrame with columns: [timestamp, solar_mw, wind_mw, hydro_mw, total_mw]
        """
        cache_key = f"taipower_renewable_{days}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            logger.info(f"Generating synthetic renewable energy data for {days} days")
            
            import numpy as np
            np.random.seed(42)
            
            dates = pd.date_range(
                end=datetime.now(),
                periods=days * 24,
                freq='h'
            )
            
            # 太陽能發電模式 (日照時間產能)
            solar_pattern = np.array([
                0, 0, 0, 0, 0, 0.1,      # 0-5
                0.3, 0.5, 0.7, 0.85, 0.95, 1.0,  # 6-11
                0.98, 0.95, 0.85, 0.7, 0.5, 0.3,  # 12-17
                0.1, 0, 0, 0, 0, 0       # 18-23
            ])
            
            records = []
            for dt in dates:
                hour = dt.hour
                month = dt.month
                
                # 太陽能 (台灣平均約 5-8 GW 裝置容量)
                solar_capacity = 8000  # MW
                solar_factor = 0.3 if 4 <= month <= 9 else 0.2  # 容量因子
                cloud_factor = np.random.uniform(0.6, 1.0)
                solar_mw = (solar_capacity * solar_pattern[hour] * 
                           solar_factor * cloud_factor)
                
                # 風力 (台灣約 1-2 GW)
                wind_capacity = 2000  # MW
                wind_factor = np.random.uniform(0.15, 0.45)  # 風力較不穩定
                wind_mw = wind_capacity * wind_factor
                
                # 水力 (相對穩定)
                hydro_mw = np.random.uniform(200, 500)
                
                records.append({
                    'timestamp': dt,
                    'solar_mw': max(0, solar_mw),
                    'wind_mw': max(0, wind_mw),
                    'hydro_mw': max(0, hydro_mw),
                    'total_renewable_mw': max(0, solar_mw + wind_mw + hydro_mw)
                })
            
            df = pd.DataFrame(records)
            self.cache.set(cache_key, df, ttl_hours=24)
            logger.info(f"Generated {len(df)} renewable energy records")
            return df
            
        except Exception as e:
            logger.error(f"Failed to get renewable generation: {e}")
            return pd.DataFrame()
    
    def get_tou_tariff(self, timestamp: datetime) -> float:
        """
        根據時間戳獲取時間電價費率
        
        Args:
            timestamp: 時間戳
            
        Returns:
            電價費率 (NTD/kWh)
        """
        month = timestamp.month
        hour = timestamp.hour
        
        # 判斷季節
        is_summer = 6 <= month <= 9
        
        # 判斷時段
        if is_summer:
            # 夏季時段
            if (10 <= hour < 12) or (13 <= hour < 17):
                return settings.summer_peak_rate
            elif (7 <= hour < 10) or (12 <= hour < 13) or (17 <= hour < 23):
                return settings.summer_half_peak_rate
            else:
                return settings.summer_off_peak_rate
        else:
            # 非夏季時段
            if (10 <= hour < 12) or (13 <= hour < 17):
                return settings.non_summer_peak_rate
            elif (7 <= hour < 10) or (12 <= hour < 13) or (17 <= hour < 23):
                return settings.non_summer_half_peak_rate
            else:
                return settings.non_summer_off_peak_rate
    
    def get_tou_period(self, timestamp: datetime) -> str:
        """
        獲取時間電價時段類型
        
        Returns:
            'peak', 'half_peak', or 'off_peak'
        """
        hour = timestamp.hour
        
        if (10 <= hour < 12) or (13 <= hour < 17):
            return "peak"
        elif (7 <= hour < 10) or (12 <= hour < 13) or (17 <= hour < 23):
            return "half_peak"
        else:
            return "off_peak"
    
    def get_24h_tariff_schedule(self, date: datetime) -> List[Dict[str, Any]]:
        """
        獲取24小時電價時刻表
        
        Args:
            date: 日期
            
        Returns:
            24小時電價列表
        """
        schedule = []
        for hour in range(24):
            ts = date.replace(hour=hour, minute=0, second=0, microsecond=0)
            schedule.append({
                'hour': hour,
                'timestamp': ts,
                'tariff': self.get_tou_tariff(ts),
                'period': self.get_tou_period(ts)
            })
        return schedule
    
    def close(self):
        """關閉 HTTP 客戶端"""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
