"""
Base Predictor Class
預測模型基底類別
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import joblib
from loguru import logger

from ecogrid.config.settings import settings


class BasePredictor(ABC):
    """
    預測模型基底類別
    
    定義所有預測模型的共同介面
    """
    
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.model = None
        self.is_fitted = False
        self.feature_names: List[str] = []
        self.training_metrics: Dict[str, float] = {}
        self.model_path = settings.model_path / f"{model_name}.joblib"
        
        logger.info(f"Initialized {model_name} predictor")
    
    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> 'BasePredictor':
        """
        訓練模型
        
        Args:
            X: 特徵矩陣
            y: 目標變數
            **kwargs: 額外參數
            
        Returns:
            self
        """
        pass
    
    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        預測
        
        Args:
            X: 特徵矩陣
            
        Returns:
            預測結果
        """
        pass
    
    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """
        評估模型效能
        
        Args:
            X: 特徵矩陣
            y: 真實值
            
        Returns:
            評估指標字典
        """
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
        
        predictions = self.predict(X)
        
        metrics = {
            'mae': mean_absolute_error(y, predictions),
            'mse': mean_squared_error(y, predictions),
            'rmse': np.sqrt(mean_squared_error(y, predictions)),
            'r2': r2_score(y, predictions),
            'mape': np.mean(np.abs((y - predictions) / (y + 1e-8))) * 100
        }
        
        logger.info(f"{self.model_name} Evaluation - MAE: {metrics['mae']:.4f}, "
                   f"RMSE: {metrics['rmse']:.4f}, R2: {metrics['r2']:.4f}")
        
        return metrics
    
    def save(self, path: Optional[Path] = None) -> Path:
        """
        儲存模型
        
        Args:
            path: 儲存路徑
            
        Returns:
            儲存的路徑
        """
        save_path = path or self.model_path
        
        model_data = {
            'model': self.model,
            'model_name': self.model_name,
            'feature_names': self.feature_names,
            'training_metrics': self.training_metrics,
            'is_fitted': self.is_fitted,
            'saved_at': datetime.now().isoformat()
        }
        
        joblib.dump(model_data, save_path)
        logger.info(f"Model saved to {save_path}")
        
        return save_path
    
    def load(self, path: Optional[Path] = None) -> 'BasePredictor':
        """
        載入模型
        
        Args:
            path: 模型路徑
            
        Returns:
            self
        """
        load_path = path or self.model_path
        
        if not load_path.exists():
            raise FileNotFoundError(f"Model not found at {load_path}")
        
        model_data = joblib.load(load_path)
        
        self.model = model_data['model']
        self.model_name = model_data['model_name']
        self.feature_names = model_data['feature_names']
        self.training_metrics = model_data['training_metrics']
        self.is_fitted = model_data['is_fitted']
        
        logger.info(f"Model loaded from {load_path}")
        
        return self
    
    def _validate_features(self, X: pd.DataFrame) -> pd.DataFrame:
        """驗證並對齊特徵"""
        if not self.feature_names:
            return X
        
        # 檢查缺失特徵
        missing = set(self.feature_names) - set(X.columns)
        if missing:
            logger.warning(f"Missing features: {missing}")
            for col in missing:
                X[col] = 0
        
        # 保持特徵順序一致
        return X[self.feature_names]
    
    def get_feature_importance(self) -> Optional[pd.DataFrame]:
        """
        獲取特徵重要性 (如果模型支援)
        
        Returns:
            特徵重要性 DataFrame
        """
        if not self.is_fitted or not hasattr(self.model, 'feature_importances_'):
            return None
        
        importance_df = pd.DataFrame({
            'feature': self.feature_names,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        return importance_df
