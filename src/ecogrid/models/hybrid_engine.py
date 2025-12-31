"""
Hybrid Predictive Engine - 混合預測引擎
整合負載預測和再生能源預測，實作滾動式預測
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger

from ecogrid.config.settings import settings
from ecogrid.models.load_forecaster import LoadForecaster
from ecogrid.models.renewable_forecaster import RenewableForecaster


class HybridPredictiveEngine:
    """
    混合預測引擎
    
    整合:
    - 負載預測 (XGBoost + LightGBM + Transformer)
    - 再生能源預測 (Random Forest + LSTM)
    - 滾動式預測機制
    """
    
    def __init__(self):
        self.load_forecaster = LoadForecaster()
        self.renewable_forecaster = RenewableForecaster()
        self.is_fitted = False
        self.last_prediction_time: Optional[datetime] = None
        self.prediction_cache: Dict[str, Any] = {}
        
        logger.info("HybridPredictiveEngine initialized")
    
    def fit(self, df: pd.DataFrame, use_transformer: bool = True, 
            use_lstm: bool = True, **kwargs):
        """
        訓練所有預測模型
        
        Args:
            df: 包含所有特徵和目標的 DataFrame
            use_transformer: 是否使用 Transformer
            use_lstm: 是否使用 LSTM
            **kwargs: 額外訓練參數
        """
        logger.info("=" * 50)
        logger.info("Training Hybrid Predictive Engine")
        logger.info("=" * 50)
        
        # 準備訓練資料
        feature_cols = [col for col in df.columns if col not in 
                       ['timestamp', 'load_mw', 'solar_mw', 'wind_mw', 'tou_period',
                        'total_renewable_mw', 'hydro_mw']]
        
        X = df[feature_cols].copy()
        
        # 填充缺失值
        X = X.fillna(method='ffill').fillna(method='bfill').fillna(0)
        
        # 1. 訓練負載預測模型
        if 'load_mw' in df.columns:
            logger.info("Training Load Forecaster...")
            y_load = df['load_mw'].fillna(df['load_mw'].median())
            self.load_forecaster.fit(X, y_load, use_transformer=use_transformer, **kwargs)
        
        # 2. 訓練再生能源預測模型
        if 'solar_mw' in df.columns and 'wind_mw' in df.columns:
            logger.info("Training Renewable Forecaster...")
            y_solar = df['solar_mw'].fillna(0)
            y_wind = df['wind_mw'].fillna(0)
            self.renewable_forecaster.fit(X, y_solar, y_wind, use_lstm=use_lstm, **kwargs)
        
        self.is_fitted = True
        self.feature_cols = feature_cols
        
        logger.info("=" * 50)
        logger.info("Hybrid Predictive Engine Training Complete")
        logger.info("=" * 50)
        
        return self
    
    def predict(self, X: pd.DataFrame) -> Dict[str, np.ndarray]:
        """
        執行預測
        
        Args:
            X: 特徵 DataFrame
            
        Returns:
            預測結果字典 {'load', 'solar', 'wind', 'net_load'}
        """
        if not self.is_fitted:
            raise ValueError("Engine not fitted yet")
        
        results = {}
        
        # 負載預測
        try:
            results['load'] = self.load_forecaster.predict(X)
        except Exception as e:
            logger.error(f"Load prediction failed: {e}")
            results['load'] = np.zeros(len(X))
        
        # 再生能源預測
        try:
            renewable_pred = self.renewable_forecaster.predict(X)
            results['solar'] = renewable_pred['solar']
            results['wind'] = renewable_pred['wind']
        except Exception as e:
            logger.error(f"Renewable prediction failed: {e}")
            results['solar'] = np.zeros(len(X))
            results['wind'] = np.zeros(len(X))
        
        # 計算淨負載 (負載 - 再生能源)
        results['net_load'] = np.maximum(
            results['load'] - results['solar'] - results['wind'], 
            0
        )
        
        return results
    
    def rolling_forecast(self, current_features: pd.DataFrame, 
                        hours_ahead: int = 24) -> pd.DataFrame:
        """
        滾動式預測 - 每小時更新未來 N 小時預測
        
        Args:
            current_features: 當前特徵資料
            hours_ahead: 預測時間範圍（小時）
            
        Returns:
            預測結果 DataFrame
        """
        logger.info(f"Performing rolling forecast for next {hours_ahead} hours")
        
        if len(current_features) < 24:
            logger.warning("Insufficient historical data for rolling forecast")
            return pd.DataFrame()
        
        # 取最近的資料進行預測
        recent_data = current_features.tail(168)  # 最近 7 天
        
        predictions = self.predict(recent_data)
        
        # 建立預測時間序列
        start_time = datetime.now().replace(minute=0, second=0, microsecond=0)
        forecast_times = [start_time + timedelta(hours=i) for i in range(hours_ahead)]
        
        # 取預測結果的最後 N 小時
        n = min(hours_ahead, len(predictions['load']))
        
        forecast_df = pd.DataFrame({
            'timestamp': forecast_times[:n],
            'predicted_load_mw': predictions['load'][-n:],
            'predicted_solar_mw': predictions['solar'][-n:],
            'predicted_wind_mw': predictions['wind'][-n:],
            'predicted_net_load_mw': predictions['net_load'][-n:]
        })
        
        # 補充時間特徵
        forecast_df['hour'] = forecast_df['timestamp'].dt.hour
        forecast_df['tou_period'] = forecast_df['hour'].apply(self._get_tou_period)
        forecast_df['tariff'] = forecast_df.apply(
            lambda row: self._get_tariff(row['timestamp']), axis=1
        )
        
        # 計算預估成本
        forecast_df['estimated_cost'] = (
            forecast_df['predicted_net_load_mw'] * 1000 *  # MW to kW
            forecast_df['tariff']
        )
        
        self.last_prediction_time = datetime.now()
        self.prediction_cache = {
            'forecast': forecast_df,
            'timestamp': self.last_prediction_time
        }
        
        logger.info(f"Rolling forecast complete: {len(forecast_df)} hours predicted")
        
        return forecast_df
    
    def _get_tou_period(self, hour: int) -> str:
        """獲取時間電價時段"""
        if (10 <= hour < 12) or (13 <= hour < 17):
            return 'peak'
        elif (7 <= hour < 10) or (12 <= hour < 13) or (17 <= hour < 23):
            return 'half_peak'
        else:
            return 'off_peak'
    
    def _get_tariff(self, timestamp: datetime) -> float:
        """獲取電價"""
        month = timestamp.month
        hour = timestamp.hour
        is_summer = 6 <= month <= 9
        
        if is_summer:
            if (10 <= hour < 12) or (13 <= hour < 17):
                return settings.summer_peak_rate
            elif (7 <= hour < 10) or (12 <= hour < 13) or (17 <= hour < 23):
                return settings.summer_half_peak_rate
            else:
                return settings.summer_off_peak_rate
        else:
            if (10 <= hour < 12) or (13 <= hour < 17):
                return settings.non_summer_peak_rate
            elif (7 <= hour < 10) or (12 <= hour < 13) or (17 <= hour < 23):
                return settings.non_summer_half_peak_rate
            else:
                return settings.non_summer_off_peak_rate
    
    def evaluate(self, X: pd.DataFrame, y_load: pd.Series, 
                 y_solar: pd.Series, y_wind: pd.Series) -> Dict[str, Any]:
        """評估所有模型"""
        results = {}
        
        # 負載預測評估
        if self.load_forecaster.is_fitted:
            results['load'] = self.load_forecaster.evaluate(X, y_load)
        
        # 再生能源預測評估
        if self.renewable_forecaster.is_fitted:
            results['renewable'] = self.renewable_forecaster.evaluate(X, y_solar, y_wind)
        
        return results
    
    def get_feature_importance(self) -> Dict[str, pd.DataFrame]:
        """獲取各模型特徵重要性"""
        importance = {}
        
        if self.load_forecaster.xgb_model.is_fitted:
            importance['xgb_load'] = self.load_forecaster.xgb_model.get_feature_importance()
        
        if self.load_forecaster.lgbm_model.is_fitted:
            importance['lgbm_load'] = self.load_forecaster.lgbm_model.get_feature_importance()
        
        if self.renewable_forecaster.solar_rf.is_fitted:
            importance['rf_solar'] = self.renewable_forecaster.solar_rf.get_feature_importance()
        
        if self.renewable_forecaster.wind_rf.is_fitted:
            importance['rf_wind'] = self.renewable_forecaster.wind_rf.get_feature_importance()
        
        return importance
    
    def save_all_models(self, path: Optional[Path] = None):
        """儲存所有模型"""
        base_path = path or settings.model_path
        
        self.load_forecaster.save(base_path)
        self.renewable_forecaster.save(base_path)
        
        logger.info(f"All models saved to {base_path}")
    
    def get_prediction_summary(self, forecast_df: pd.DataFrame) -> Dict[str, Any]:
        """
        生成預測摘要
        
        Args:
            forecast_df: 預測結果 DataFrame
            
        Returns:
            摘要字典
        """
        if forecast_df.empty:
            return {}
        
        summary = {
            'prediction_time': self.last_prediction_time.isoformat() if self.last_prediction_time else None,
            'forecast_hours': len(forecast_df),
            'load': {
                'avg_mw': float(forecast_df['predicted_load_mw'].mean()),
                'max_mw': float(forecast_df['predicted_load_mw'].max()),
                'min_mw': float(forecast_df['predicted_load_mw'].min()),
                'peak_hour': int(forecast_df.loc[forecast_df['predicted_load_mw'].idxmax(), 'hour'])
            },
            'solar': {
                'avg_mw': float(forecast_df['predicted_solar_mw'].mean()),
                'max_mw': float(forecast_df['predicted_solar_mw'].max()),
                'total_mwh': float(forecast_df['predicted_solar_mw'].sum())
            },
            'wind': {
                'avg_mw': float(forecast_df['predicted_wind_mw'].mean()),
                'total_mwh': float(forecast_df['predicted_wind_mw'].sum())
            },
            'cost': {
                'total_estimated': float(forecast_df['estimated_cost'].sum()),
                'avg_hourly': float(forecast_df['estimated_cost'].mean()),
                'peak_cost': float(forecast_df[forecast_df['tou_period'] == 'peak']['estimated_cost'].sum()),
                'off_peak_cost': float(forecast_df[forecast_df['tou_period'] == 'off_peak']['estimated_cost'].sum())
            },
            'renewable_ratio': float(
                (forecast_df['predicted_solar_mw'].sum() + forecast_df['predicted_wind_mw'].sum()) /
                (forecast_df['predicted_load_mw'].sum() + 1e-8) * 100
            )
        }
        
        return summary
