"""
ETL Pipeline for EcoGrid Audit Predict
整合所有資料來源的 ETL 管道
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

import pandas as pd
import numpy as np
from loguru import logger

from ecogrid.config.settings import settings
from ecogrid.data.cache_manager import CacheManager
from ecogrid.data.taiwan_power_api import TaiwanPowerAPI
from ecogrid.data.weather_api import WeatherAPI


class ETLPipeline:
    """
    ETL 管道
    
    Extract: 從台電、氣象署等來源擷取資料
    Transform: 資料清洗、特徵工程
    Load: 存入本地或資料庫
    """
    
    def __init__(self):
        self.cache = CacheManager()
        self.power_api = TaiwanPowerAPI(self.cache)
        self.weather_api = WeatherAPI(self.cache)
        logger.info("ETLPipeline initialized")
    
    def extract_all(self, days: int = 365) -> Dict[str, pd.DataFrame]:
        """
        從所有來源擷取資料
        
        Args:
            days: 歷史資料天數
            
        Returns:
            字典包含各資料來源的 DataFrame
        """
        logger.info(f"Starting data extraction for {days} days")
        
        data = {}
        
        # 1. 電力負載資料
        logger.info("Extracting power load data...")
        data['load'] = self.power_api.get_historical_load(days)
        
        # 2. 再生能源發電資料
        logger.info("Extracting renewable energy data...")
        data['renewable'] = self.power_api.get_renewable_generation(days)
        
        # 3. 氣象資料
        logger.info("Extracting weather data...")
        data['weather'] = self.weather_api.get_historical_weather(days)
        
        # 4. 天氣預報
        logger.info("Extracting weather forecast...")
        data['forecast'] = self.weather_api.get_weather_forecast(hours=48)
        
        logger.info(f"Extraction complete: {list(data.keys())}")
        return data
    
    def transform(self, raw_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        資料轉換與特徵工程
        
        Args:
            raw_data: 原始資料字典
            
        Returns:
            合併並處理後的 DataFrame
        """
        logger.info("Starting data transformation...")
        
        # 確保所有資料都有 timestamp 欄位
        for key, df in raw_data.items():
            if df.empty:
                logger.warning(f"Empty DataFrame for {key}")
                continue
            if 'timestamp' not in df.columns:
                logger.warning(f"No timestamp column in {key}")
        
        # 合併負載和再生能源資料
        if not raw_data['load'].empty and not raw_data['renewable'].empty:
            df = pd.merge(
                raw_data['load'],
                raw_data['renewable'],
                on='timestamp',
                how='outer'
            )
        elif not raw_data['load'].empty:
            df = raw_data['load'].copy()
        else:
            df = pd.DataFrame()
        
        # 合併氣象資料
        if not df.empty and not raw_data['weather'].empty:
            df = pd.merge(
                df,
                raw_data['weather'].drop(columns=['station_id'], errors='ignore'),
                on='timestamp',
                how='left'
            )
        
        if df.empty:
            logger.warning("No data to transform, creating sample data")
            return self._create_sample_data()
        
        # 特徵工程
        df = self._add_time_features(df)
        df = self._add_tou_features(df)
        df = self._add_lag_features(df)
        df = self._add_rolling_features(df)
        
        # 處理缺失值
        df = self._handle_missing_values(df)
        
        logger.info(f"Transformation complete: {len(df)} rows, {len(df.columns)} columns")
        return df
    
    def _create_sample_data(self) -> pd.DataFrame:
        """建立樣本資料用於測試"""
        logger.info("Creating sample data for demonstration")
        
        np.random.seed(42)
        dates = pd.date_range(
            end=datetime.now(),
            periods=24 * 30,  # 30 days
            freq='h'
        )
        
        records = []
        for dt in dates:
            hour = dt.hour
            month = dt.month
            
            # 負載模式
            base_load = 1000  # kW
            hourly_factor = 0.7 + 0.3 * np.sin(np.pi * (hour - 6) / 12) if 6 <= hour <= 18 else 0.6
            seasonal_factor = 1.2 if 6 <= month <= 9 else 1.0
            load = base_load * hourly_factor * seasonal_factor * np.random.uniform(0.9, 1.1)
            
            # 太陽能
            solar = 200 * max(0, np.sin(np.pi * (hour - 6) / 12)) if 6 <= hour <= 18 else 0
            solar *= np.random.uniform(0.5, 1.0)
            
            records.append({
                'timestamp': dt,
                'load_mw': load / 1000,  # Convert to MW
                'solar_mw': solar / 1000,
                'wind_mw': np.random.uniform(0.01, 0.05),
                'temperature': 25 + 5 * np.sin(np.pi * (hour - 6) / 12) + np.random.normal(0, 2),
                'humidity': np.random.uniform(60, 80),
                'solar_radiation': max(0, 20 * np.sin(np.pi * (hour - 6) / 12)) if 6 <= hour <= 18 else 0
            })
        
        return pd.DataFrame(records)
    
    def _add_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """新增時間特徵"""
        df = df.copy()
        
        df['hour'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        df['day_of_month'] = df['timestamp'].dt.day
        df['month'] = df['timestamp'].dt.month
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
        
        # 台灣國定假日標記 (簡化版)
        df['is_holiday'] = 0
        holidays = ['01-01', '02-28', '04-04', '04-05', '05-01', '10-10']
        for holiday in holidays:
            month, day = map(int, holiday.split('-'))
            df.loc[(df['timestamp'].dt.month == month) & 
                   (df['timestamp'].dt.day == day), 'is_holiday'] = 1
        
        # 時間的週期性編碼
        df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
        df['day_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
        df['day_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
        df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
        df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
        
        return df
    
    def _add_tou_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """新增時間電價特徵"""
        df = df.copy()
        
        # 季節標記
        df['is_summer'] = df['month'].isin([6, 7, 8, 9]).astype(int)
        
        # TOU 時段
        def get_tou_period(row):
            hour = row['hour']
            if (10 <= hour < 12) or (13 <= hour < 17):
                return 'peak'
            elif (7 <= hour < 10) or (12 <= hour < 13) or (17 <= hour < 23):
                return 'half_peak'
            else:
                return 'off_peak'
        
        df['tou_period'] = df.apply(get_tou_period, axis=1)
        
        # One-hot encoding for TOU period
        df['is_peak'] = (df['tou_period'] == 'peak').astype(int)
        df['is_half_peak'] = (df['tou_period'] == 'half_peak').astype(int)
        df['is_off_peak'] = (df['tou_period'] == 'off_peak').astype(int)
        
        # 電價
        def get_tariff(row):
            is_summer = row['is_summer']
            tou = row['tou_period']
            
            if is_summer:
                if tou == 'peak':
                    return settings.summer_peak_rate
                elif tou == 'half_peak':
                    return settings.summer_half_peak_rate
                else:
                    return settings.summer_off_peak_rate
            else:
                if tou == 'peak':
                    return settings.non_summer_peak_rate
                elif tou == 'half_peak':
                    return settings.non_summer_half_peak_rate
                else:
                    return settings.non_summer_off_peak_rate
        
        df['tariff'] = df.apply(get_tariff, axis=1)
        
        return df
    
    def _add_lag_features(self, df: pd.DataFrame, target_col: str = 'load_mw') -> pd.DataFrame:
        """新增滯後特徵"""
        df = df.copy()
        
        if target_col not in df.columns:
            return df
        
        # 滯後特徵 (過去幾小時)
        for lag in [1, 2, 3, 6, 12, 24, 48, 168]:  # 168 = 1 week
            df[f'{target_col}_lag_{lag}h'] = df[target_col].shift(lag)
        
        return df
    
    def _add_rolling_features(self, df: pd.DataFrame, target_col: str = 'load_mw') -> pd.DataFrame:
        """新增滾動統計特徵"""
        df = df.copy()
        
        if target_col not in df.columns:
            return df
        
        # 滾動平均
        for window in [6, 12, 24, 48]:
            df[f'{target_col}_rolling_mean_{window}h'] = df[target_col].rolling(window=window).mean()
            df[f'{target_col}_rolling_std_{window}h'] = df[target_col].rolling(window=window).std()
        
        # 滾動最大/最小
        df[f'{target_col}_rolling_max_24h'] = df[target_col].rolling(window=24).max()
        df[f'{target_col}_rolling_min_24h'] = df[target_col].rolling(window=24).min()
        
        return df
    
    def _handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """處理缺失值"""
        df = df.copy()
        
        # 前向填充時間序列特徵
        time_cols = [col for col in df.columns if 'lag' in col or 'rolling' in col]
        for col in time_cols:
            df[col] = df[col].ffill().bfill()
        
        # 數值欄位用中位數填充
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if df[col].isna().any():
                median_val = df[col].median()
                if pd.isna(median_val):
                    median_val = 0
                df[col] = df[col].fillna(median_val)
        
        # 最終檢查：確保無 NaN
        df = df.fillna(0)
        
        return df
    
    def load(self, df: pd.DataFrame, filename: str = "processed_data.parquet") -> Path:
        """
        儲存處理後的資料
        
        Args:
            df: 處理後的 DataFrame
            filename: 檔案名稱
            
        Returns:
            儲存路徑
        """
        output_path = settings.data_processed_path / filename
        
        # 儲存為 Parquet 格式 (高效壓縮)
        df.to_parquet(output_path, index=False)
        logger.info(f"Data saved to {output_path}")
        
        # 同時儲存 CSV 供檢視
        csv_path = output_path.with_suffix('.csv')
        df.to_csv(csv_path, index=False)
        
        return output_path
    
    def run_pipeline(self, days: int = 365) -> Tuple[pd.DataFrame, Path]:
        """
        執行完整 ETL 流程
        
        Args:
            days: 歷史資料天數
            
        Returns:
            處理後的 DataFrame 和儲存路徑
        """
        logger.info("=" * 50)
        logger.info("Starting ETL Pipeline")
        logger.info("=" * 50)
        
        # Extract
        raw_data = self.extract_all(days)
        
        # Transform
        processed_df = self.transform(raw_data)
        
        # Load
        output_path = self.load(processed_df)
        
        logger.info("=" * 50)
        logger.info("ETL Pipeline Complete")
        logger.info(f"Output: {output_path}")
        logger.info(f"Rows: {len(processed_df)}, Columns: {len(processed_df.columns)}")
        logger.info("=" * 50)
        
        return processed_df, output_path
    
    def get_training_data(self, df: pd.DataFrame, 
                          target_col: str = 'load_mw',
                          test_ratio: float = 0.2) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        準備訓練資料
        
        Args:
            df: 處理後的資料
            target_col: 目標欄位
            test_ratio: 測試集比例
            
        Returns:
            X_train, X_test, y_train, y_test
        """
        # 移除不需要的欄位
        exclude_cols = ['timestamp', 'tou_period', target_col]
        feature_cols = [col for col in df.columns if col not in exclude_cols]
        
        # 移除含有 NaN 的行
        df_clean = df.dropna(subset=[target_col] + feature_cols)
        
        # 時間序列分割 (不隨機，保持時間順序)
        split_idx = int(len(df_clean) * (1 - test_ratio))
        
        train_df = df_clean.iloc[:split_idx]
        test_df = df_clean.iloc[split_idx:]
        
        X_train = train_df[feature_cols]
        X_test = test_df[feature_cols]
        y_train = train_df[target_col]
        y_test = test_df[target_col]
        
        logger.info(f"Training data: {len(X_train)} samples")
        logger.info(f"Test data: {len(X_test)} samples")
        logger.info(f"Features: {len(feature_cols)}")
        
        return X_train, X_test, y_train, y_test
    
    def close(self):
        """關閉所有連線"""
        self.power_api.close()
        self.weather_api.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
