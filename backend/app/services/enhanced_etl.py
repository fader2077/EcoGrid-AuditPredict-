"""
增強版 ETL Pipeline - 整合台電與氣象真實數據
Enhanced ETL Pipeline with Real Data Integration
"""
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger
import asyncio
import sys
import os

# 加入父目錄路徑以導入客戶端
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.data.taipower_client import TaipowerClient
from app.data.weather_client import WeatherClient


class EnhancedETL:
    """增強版 ETL，整合台電與氣象局真實數據"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            backend_dir = Path(__file__).parent.parent.parent
            db_path = str(backend_dir / "ecogrid.db")
        self.db_path = db_path
        self.taipower = TaipowerClient()
        self.weather = WeatherClient()
        
    async def close(self):
        """關閉客戶端連接"""
        await self.taipower.close()
        await self.weather.close()
    
    async def fetch_realtime_data(self) -> dict:
        """
        獲取即時數據（台電 + 氣象）
        
        Returns:
            {
                'timestamp': datetime,
                'load_mw': float,
                'temperature': float,
                'humidity': float,
                'solar_radiation': float,
                'carbon_intensity': float,
                ...
            }
        """
        logger.info("正在獲取即時數據...")
        
        # 並行獲取台電和氣象數據
        taipower_data = await self.taipower.get_realtime_usage()
        weather_data = await self.weather.get_current_weather()
        carbon_data = await self.taipower.get_carbon_intensity()
        
        # 合併數據
        realtime = {
            'timestamp': datetime.now(),
            'load_mw': taipower_data['current_load'] if taipower_data else 28000.0,
            'capacity_mw': taipower_data['current_capacity'] if taipower_data else 40000.0,
            'reserve_rate': taipower_data['reserve_rate'] if taipower_data else 30.0,
            'temperature': weather_data['temperature'] if weather_data else 25.0,
            'humidity': weather_data['humidity'] if weather_data else 70.0,
            'pressure': weather_data['pressure'] if weather_data else 1013.0,
            'solar_radiation': weather_data['solar_radiation'] if weather_data else 500.0,
            'wind_speed': weather_data['wind_speed'] if weather_data else 2.5,
            'carbon_intensity': carbon_data['carbon_intensity'] if carbon_data else 0.502,
            'renewable_ratio': carbon_data['renewable_ratio'] if carbon_data else 15.0
        }
        
        logger.info(f"即時數據: Load={realtime['load_mw']:.0f}MW, Temp={realtime['temperature']:.1f}°C")
        return realtime
    
    async def fetch_historical_with_weather(
        self, 
        start_date: datetime, 
        end_date: datetime
    ) -> pd.DataFrame:
        """
        獲取歷史數據（台電負載 + 氣象數據）
        
        Args:
            start_date: 開始日期
            end_date: 結束日期
            
        Returns:
            DataFrame with hourly data
        """
        logger.info(f"獲取歷史數據: {start_date} ~ {end_date}")
        
        # 並行獲取台電和氣象數據
        taipower_history = await self.taipower.get_historical_load(start_date, end_date)
        weather_forecast = await self.weather.get_hourly_forecast(
            hours=int((end_date - start_date).total_seconds() / 3600)
        )
        
        # 轉換為 DataFrame
        df_taipower = pd.DataFrame(taipower_history)
        df_weather = pd.DataFrame(weather_forecast)
        
        # 合併數據（基於時間戳）
        df_taipower['timestamp'] = pd.to_datetime(df_taipower['timestamp'])
        df_weather['timestamp'] = pd.to_datetime(df_weather['timestamp'])
        
        df = pd.merge(
            df_taipower, 
            df_weather[['timestamp', 'temperature', 'humidity', 'solar_radiation', 'wind_speed', 'rainfall']], 
            on='timestamp', 
            how='left'
        )
        
        # 填充缺失值
        df = df.fillna(method='ffill').fillna(method='bfill')
        
        logger.info(f"合併數據: {len(df)} 筆，特徵數: {len(df.columns)}")
        return df
    
    async def run_enhanced_pipeline(self, days: int = 30) -> tuple:
        """
        運行增強版 ETL 管道
        
        Args:
            days: 歷史數據天數
            
        Returns:
            (DataFrame, Path): 處理後的數據和路徑
        """
        logger.info(f"=== 開始增強版 ETL Pipeline (整合真實數據) ===")
        
        try:
            # 1. 獲取歷史數據
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            df = await self.fetch_historical_with_weather(start_date, end_date)
            
            # 2. 重命名列以匹配模型期望
            df = df.rename(columns={
                'load_mw': 'load_mw',
                'temperature': 'temp',
                'solar_radiation': 'solar_rad',
                'wind_speed': 'wind_speed'
            })
            
            # 3. 添加再生能源估算
            df = self._estimate_renewable_generation(df)
            
            # 4. 特徵工程
            df = self._add_time_features(df)
            df = self._add_tou_features(df)
            df = self._add_lag_features(df)
            df = self._add_rolling_features(df)
            df = self._add_weather_interaction_features(df)
            
            # 5. 移除缺失值
            df = df.fillna(method='ffill').fillna(method='bfill').fillna(0)
            
            logger.info(f"✓ ETL 完成: {len(df)} 筆, {len(df.columns)} 特徵")
            logger.info(f"  負載範圍: {df['load_mw'].min():.1f} ~ {df['load_mw'].max():.1f} MW")
            logger.info(f"  溫度範圍: {df['temp'].min():.1f} ~ {df['temp'].max():.1f} °C")
            logger.info(f"  太陽輻射: {df['solar_rad'].min():.0f} ~ {df['solar_rad'].max():.0f} W/m²")
            
            # 保存路徑
            output_path = Path("backend/enhanced_data.parquet")
            
            return df, output_path
            
        except Exception as e:
            logger.error(f"ETL Pipeline 失敗: {e}")
            raise
    
    def _estimate_renewable_generation(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        估算再生能源發電量
        
        基於太陽輻射和風速估算太陽能和風力發電
        """
        df = df.copy()
        
        # 太陽能發電（基於輻射量）
        # 假設台灣太陽能裝置容量 10 GW，效率 15%
        solar_capacity_mw = 10000.0
        solar_efficiency = 0.15
        standard_radiation = 1000.0  # W/m² (標準測試條件)
        
        df['solar_mw'] = (
            df['solar_rad'] / standard_radiation * 
            solar_capacity_mw * 
            solar_efficiency
        )
        
        # 風力發電（基於風速）
        # 風力發電與風速三次方成正比
        wind_capacity_mw = 2000.0
        rated_wind_speed = 12.0  # m/s
        
        df['wind_mw'] = np.minimum(
            (df['wind_speed'] / rated_wind_speed) ** 3 * wind_capacity_mw,
            wind_capacity_mw
        )
        
        # 確保非負
        df['solar_mw'] = df['solar_mw'].clip(lower=0)
        df['wind_mw'] = df['wind_mw'].clip(lower=0)
        
        logger.info(f"再生能源估算: 太陽能 {df['solar_mw'].mean():.0f} MW, 風力 {df['wind_mw'].mean():.0f} MW (平均)")
        
        return df
    
    def _add_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加時間特徵"""
        df = df.copy()
        
        df['hour'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        df['day_of_month'] = df['timestamp'].dt.day
        df['month'] = df['timestamp'].dt.month
        df['quarter'] = df['timestamp'].dt.quarter
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
        
        # 週期性編碼
        df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
        df['day_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
        df['day_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
        df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
        df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
        
        return df
    
    def _add_tou_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加時間電價特徵"""
        df = df.copy()
        
        def get_tou_period(hour):
            if 10 <= hour < 17:
                return 'peak'
            elif 7 <= hour < 10 or 17 <= hour < 23:
                return 'mid_peak'
            else:
                return 'off_peak'
        
        df['tou_period'] = df['hour'].apply(get_tou_period)
        df['is_peak'] = (df['tou_period'] == 'peak').astype(int)
        df['is_mid_peak'] = (df['tou_period'] == 'mid_peak').astype(int)
        df['is_off_peak'] = (df['tou_period'] == 'off_peak').astype(int)
        
        return df
    
    def _add_lag_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加滯後特徵"""
        df = df.copy()
        
        for lag in [1, 2, 3, 6, 12, 24]:
            df[f'load_lag_{lag}'] = df['load_mw'].shift(lag)
            if 'temp' in df.columns:
                df[f'temp_lag_{lag}'] = df['temp'].shift(lag)
        
        return df
    
    def _add_rolling_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加滾動統計特徵"""
        df = df.copy()
        
        for window in [3, 6, 12, 24]:
            df[f'load_rolling_mean_{window}'] = df['load_mw'].rolling(window, min_periods=1).mean()
            df[f'load_rolling_std_{window}'] = df['load_mw'].rolling(window, min_periods=1).std()
            df[f'load_rolling_max_{window}'] = df['load_mw'].rolling(window, min_periods=1).max()
            df[f'load_rolling_min_{window}'] = df['load_mw'].rolling(window, min_periods=1).min()
        
        return df
    
    def _add_weather_interaction_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加天氣交互特徵"""
        df = df.copy()
        
        if 'temp' in df.columns:
            # 溫度與負載交互（空調負載）
            df['temp_load_interaction'] = df['temp'] * df['load_mw']
            
            # 溫度平方（非線性效應）
            df['temp_squared'] = df['temp'] ** 2
            
            # 溫度與時段交互
            df['temp_hour_interaction'] = df['temp'] * df['hour']
        
        if 'humidity' in df.columns:
            # 濕度影響
            df['humidity_temp_interaction'] = df['humidity'] * df['temp']
        
        return df
    
    def save_to_database(self, df: pd.DataFrame):
        """
        將處理後的數據保存到資料庫
        
        Args:
            df: 處理後的 DataFrame
        """
        logger.info(f"保存數據到資料庫: {self.db_path}")
        
        conn = sqlite3.connect(self.db_path)
        
        # 準備插入數據
        insert_df = df[[
            'timestamp', 'load_mw', 'solar_mw', 'wind_mw', 
            'temp', 'humidity', 'solar_rad'
        ]].copy()
        
        # 轉換單位（MW → kW）
        insert_df['load_kw'] = insert_df['load_mw'] * 1000
        insert_df['solar_kw'] = insert_df['solar_mw'] * 1000
        insert_df['wind_kw'] = insert_df['wind_mw'] * 1000
        
        # 添加其他必要欄位
        insert_df['battery_soc'] = 50.0
        insert_df['grid_import_kw'] = insert_df['load_kw'] - insert_df['solar_kw'] - insert_df['wind_kw']
        insert_df['tariff_rate'] = insert_df.apply(
            lambda row: 5.5 if 10 <= row.name % 24 < 17 else 1.7, 
            axis=1
        )
        
        # 插入資料庫（替換現有數據）
        insert_df[['timestamp', 'load_kw', 'solar_kw', 'wind_kw', 'battery_soc', 'grid_import_kw', 'tariff_rate']].to_sql(
            'power_logs', 
            conn, 
            if_exists='replace', 
            index=False
        )
        
        conn.close()
        logger.info(f"✓ 已保存 {len(insert_df)} 筆數據到資料庫")


async def test_enhanced_etl():
    """測試增強版 ETL"""
    print("\n=== 增強版 ETL Pipeline 測試 ===\n")
    
    etl = EnhancedETL()
    
    try:
        # 測試即時數據
        print("1. 即時數據獲取:")
        realtime = await etl.fetch_realtime_data()
        for key, value in realtime.items():
            print(f"   {key}: {value}")
        
        # 測試完整 Pipeline
        print("\n2. 完整 ETL Pipeline (7 天數據):")
        df, path = await etl.run_enhanced_pipeline(days=7)
        print(f"   ✓ 處理完成: {len(df)} 筆, {len(df.columns)} 特徵")
        print(f"   特徵列表: {list(df.columns[:10])}...")
        
        # 保存到資料庫
        print("\n3. 保存到資料庫:")
        etl.save_to_database(df)
        
        print("\n✓ 所有測試通過!")
        
    except Exception as e:
        print(f"\n✗ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await etl.close()


if __name__ == "__main__":
    asyncio.run(test_enhanced_etl())
