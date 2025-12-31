"""
AI Service - 整合 ecogrid 的 AI 預測引擎（帶 GPU 優化）
"""

import sys
import torch
import gc
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np
from loguru import logger

# Import ecogrid modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))
from ecogrid.models.hybrid_engine import HybridPredictiveEngine
# 使用簡化版 ETL，直接從資料庫讀取並正確轉換 kW -> MW
from app.services.simple_etl import SimpleETL
from ecogrid.config import settings as ecogrid_settings


def clear_gpu_memory():
    """清理 GPU 記憶體以避免 OOM"""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        gc.collect()
        logger.info(f"GPU memory cleared. Allocated: {torch.cuda.memory_allocated() / 1e9:.2f} GB")


def check_gpu_memory():
    """檢查 GPU 記憶體使用率"""
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated() / 1e9
        reserved = torch.cuda.memory_reserved() / 1e9
        total = torch.cuda.get_device_properties(0).total_memory / 1e9
        usage_percent = (allocated / total) * 100
        
        logger.info(f"GPU Memory: {allocated:.2f}/{total:.2f} GB ({usage_percent:.1f}%)")
        
        # 如果使用率超過 60%，警告並清理
        if usage_percent > 60:
            logger.warning(f"GPU memory usage high ({usage_percent:.1f}%), clearing cache...")
            clear_gpu_memory()
        
        return usage_percent
    return 0


class AIService:
    """AI 預測服務（帶 GPU 優化）"""
    
    def __init__(self):
        self.engine: Optional[HybridPredictiveEngine] = None
        self.etl: Optional[SimpleETL] = None
        self.is_trained = False
        
        # 初始化時檢查 GPU
        if torch.cuda.is_available():
            logger.info(f"GPU Available: {torch.cuda.get_device_name(0)}")
            check_gpu_memory()
        else:
            logger.warning("No GPU available, using CPU")
        
    def initialize(self):
        """初始化 AI 引擎"""
        if self.engine is None:
            logger.info("Initializing AI Service...")
            self.engine = HybridPredictiveEngine()
            self.etl = SimpleETL()  # 使用簡化版 ETL
            logger.info("AI Service initialized")
    
    def train_models(
        self, 
        use_transformer: bool = False,
        use_lstm: bool = False,
        n_estimators: int = 50
    ) -> Dict[str, Any]:
        """
        訓練 AI 模型（帶 GPU 記憶體管理）
        
        Args:
            use_transformer: 是否使用 Transformer
            use_lstm: 是否使用 LSTM
            n_estimators: 樹模型數量
            
        Returns:
            訓練結果
        """
        self.initialize()
        
        # 訓練前清理 GPU 記憶體
        clear_gpu_memory()
        
        logger.info("Starting model training with GPU optimization...")
        check_gpu_memory()
        
        try:
            # 運行 ETL 獲取訓練數據
            data, data_path = self.etl.run_pipeline(days=30)
            
            if data.empty:
                raise ValueError("No training data available")
            
            # 訓練模型
            self.engine.fit(
                data,
                use_transformer=use_transformer,
                use_lstm=use_lstm,
                n_estimators=n_estimators,
                epochs=10
            )
            
            self.is_trained = True
            
            # 訓練後清理記憶體
            clear_gpu_memory()
            
            logger.info("Model training complete")
            check_gpu_memory()
            
            return {
                "status": "success",
                "data_rows": len(data),
                "features": list(data.columns),
                "models_trained": {
                    "xgboost": True,
                    "lightgbm": True,
                    "transformer": use_transformer,
                    "lstm": use_lstm
                },
                "gpu_usage_percent": check_gpu_memory()
            }
        except torch.cuda.OutOfMemoryError as e:
            logger.error(f"GPU OOM Error! {e}")
            clear_gpu_memory()
            # 降級為只使用樹模型
            logger.warning("Falling back to tree models only (no Transformer/LSTM)")
            return self.train_models(use_transformer=False, use_lstm=False, n_estimators=30)
        except Exception as e:
            clear_gpu_memory()
            raise e
    
    def predict(
        self,
        hours_ahead: int = 24,
        use_transformer: bool = False,
        use_lstm: bool = False
    ) -> pd.DataFrame:
        """
        執行負載預測（帶 GPU 記憶體管理）
        
        Args:
            hours_ahead: 預測時長（小時）
            use_transformer: 是否使用 Transformer
            use_lstm: 是否使用 LSTM
            
        Returns:
            預測結果 DataFrame
        """
        self.initialize()
        
        # 預測前檢查 GPU 記憶體
        check_gpu_memory()
        
        try:
            # 如果未訓練，先訓練
            if not self.is_trained:
                logger.warning("Models not trained, training now...")
                self.train_models(use_transformer, use_lstm)
            
            # 獲取最新數據
            data, data_path = self.etl.run_pipeline(days=30)
            
            if data.empty:
                raise ValueError("No data available for prediction")
            
            # 執行預測
            predictions = self.engine.rolling_forecast(
                data, 
                hours_ahead=hours_ahead
            )
            
            # 預測後清理
            clear_gpu_memory()
            
            return predictions
            
        except torch.cuda.OutOfMemoryError as e:
            logger.error(f"GPU OOM during prediction! {e}")
            clear_gpu_memory()
            # 重試
            logger.warning("Retrying prediction after memory clear...")
            return self.predict(hours_ahead, use_transformer=False, use_lstm=False)
    
    def get_model_info(self) -> Dict[str, Any]:
        """獲取模型資訊"""
        if not self.is_trained or self.engine is None:
            return {
                "is_trained": False,
                "message": "Models not trained"
            }
        
        return {
            "is_trained": True,
            "load_forecaster": {
                "xgboost_fitted": self.engine.load_forecaster.xgboost.is_fitted,
                "lightgbm_fitted": self.engine.load_forecaster.lightgbm.is_fitted,
            },
            "renewable_forecaster": {
                "solar_rf_fitted": self.engine.renewable_forecaster.solar_rf.is_fitted,
                "wind_rf_fitted": self.engine.renewable_forecaster.wind_rf.is_fitted,
            }
        }


# Global instance
ai_service = AIService()
