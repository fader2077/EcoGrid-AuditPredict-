"""
簡化版 ETL Pipeline - 直接從資料庫讀取並訓練
"""
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from loguru import logger


class SimpleETL:
    """簡化版 ETL，直接從 SQLite 資料庫讀取"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # 使用絕對路徑
            from pathlib import Path
            backend_dir = Path(__file__).parent.parent.parent
            db_path = str(backend_dir / "ecogrid.db")
        self.db_path = db_path
        
    def run_pipeline(self, days: int = 30) -> tuple:
        """
        從資料庫讀取數據並進行特徵工程
        
        Returns:
            (DataFrame, Path): 處理後的數據和路徑
        """
        logger.info(f"Loading data from database: {self.db_path}")
        
        # 讀取資料庫
        conn = sqlite3.connect(self.db_path)
        
        query = f"""
        SELECT 
            timestamp,
            load_kw,
            solar_kw,
            wind_kw,
            battery_soc,
            grid_import_kw,
            tariff_rate
        FROM power_logs
        ORDER BY timestamp DESC
        LIMIT {days * 24}
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            raise ValueError("No data in database")
        
        # 轉換時間戳
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        logger.info(f"Loaded {len(df)} records")
        
        # **關鍵修正：將 kW 轉換為 MW，確保與模型訓練單位一致**
        df['load_mw'] = df['load_kw'] / 1000.0
        df['solar_mw'] = df['solar_kw'] / 1000.0
        df['wind_mw'] = df['wind_kw'] / 1000.0
        
        # 特徵工程
        df = self._add_time_features(df)
        df = self._add_tou_features(df)
        df = self._add_lag_features(df)
        df = self._add_rolling_features(df)
        
        # 移除缺失值
        df = df.fillna(method='ffill').fillna(method='bfill').fillna(0)
        
        logger.info(f"Feature engineering complete: {len(df.columns)} features")
        logger.info(f"Load range: {df['load_mw'].min():.3f} ~ {df['load_mw'].max():.3f} MW")
        
        # 保存路徑（僅用於兼容性）
        output_path = Path("backend/processed_data.parquet")
        
        return df, output_path
    
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
        
        df['is_summer'] = df['month'].isin([6, 7, 8, 9]).astype(int)
        
        def get_tou_period(hour):
            if (10 <= hour < 12) or (13 <= hour < 17):
                return 'peak'
            elif (7 <= hour < 10) or (12 <= hour < 13) or (17 <= hour < 23):
                return 'half_peak'
            else:
                return 'off_peak'
        
        df['tou_period'] = df['hour'].apply(get_tou_period)
        df['is_peak'] = (df['tou_period'] == 'peak').astype(int)
        df['is_half_peak'] = (df['tou_period'] == 'half_peak').astype(int)
        df['is_off_peak'] = (df['tou_period'] == 'off_peak').astype(int)
        
        return df
    
    def _add_lag_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加滯後特徵"""
        df = df.copy()
        
        # 負載滯後特徵
        for lag in [1, 2, 3, 24, 168]:  # 1h, 2h, 3h, 1天, 1週
            if len(df) > lag:
                df[f'load_lag_{lag}h'] = df['load_mw'].shift(lag)
                df[f'solar_lag_{lag}h'] = df['solar_mw'].shift(lag)
                df[f'wind_lag_{lag}h'] = df['wind_mw'].shift(lag)
        
        return df
    
    def _add_rolling_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加滾動統計特徵"""
        df = df.copy()
        
        windows = [3, 6, 12, 24]
        for window in windows:
            if len(df) > window:
                df[f'load_roll_mean_{window}h'] = df['load_mw'].rolling(window, min_periods=1).mean()
                df[f'load_roll_std_{window}h'] = df['load_mw'].rolling(window, min_periods=1).std()
                df[f'solar_roll_mean_{window}h'] = df['solar_mw'].rolling(window, min_periods=1).mean()
                df[f'wind_roll_mean_{window}h'] = df['wind_mw'].rolling(window, min_periods=1).mean()
        
        return df
