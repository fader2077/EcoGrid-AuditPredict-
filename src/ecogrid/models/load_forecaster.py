"""
Load Forecaster - 電力負載預測模型
整合 XGBoost, LightGBM, Prophet 和 Transformer
"""

import warnings
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import StandardScaler
from loguru import logger

from ecogrid.config.settings import settings
from ecogrid.models.base_model import BasePredictor

warnings.filterwarnings('ignore')


class XGBoostForecaster(BasePredictor):
    """XGBoost 負載預測器 - 處理 Tabular 特徵"""
    
    def __init__(self):
        super().__init__("xgboost_load_forecaster")
        self.scaler = StandardScaler()
    
    def fit(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> 'XGBoostForecaster':
        import xgboost as xgb
        
        self.feature_names = list(X.columns)
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # XGBoost parameters optimized for time series
        params = {
            'objective': 'reg:squarederror',
            'max_depth': kwargs.get('max_depth', 6),
            'learning_rate': kwargs.get('learning_rate', 0.1),
            'n_estimators': kwargs.get('n_estimators', 200),
            'min_child_weight': 3,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'random_state': 42,
            'n_jobs': -1
        }
        
        # GPU support if available
        if torch.cuda.is_available():
            params['tree_method'] = 'hist'
            params['device'] = 'cuda'
            logger.info("XGBoost using GPU acceleration")
        
        self.model = xgb.XGBRegressor(**params)
        self.model.fit(X_scaled, y, eval_set=[(X_scaled, y)], verbose=False)
        
        self.is_fitted = True
        self.training_metrics = self.evaluate(X, y)
        
        logger.info(f"XGBoost fitted with {len(X)} samples")
        return self
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted:
            raise ValueError("Model not fitted yet")
        
        X = self._validate_features(X)
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)


class LightGBMForecaster(BasePredictor):
    """LightGBM 負載預測器"""
    
    def __init__(self):
        super().__init__("lightgbm_load_forecaster")
        self.scaler = StandardScaler()
    
    def fit(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> 'LightGBMForecaster':
        import lightgbm as lgb
        
        self.feature_names = list(X.columns)
        X_scaled = self.scaler.fit_transform(X)
        
        params = {
            'objective': 'regression',
            'metric': 'rmse',
            'boosting_type': 'gbdt',
            'num_leaves': kwargs.get('num_leaves', 31),
            'learning_rate': kwargs.get('learning_rate', 0.1),
            'n_estimators': kwargs.get('n_estimators', 200),
            'min_child_samples': 20,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'random_state': 42,
            'n_jobs': -1,
            'verbose': -1
        }
        
        # GPU support
        if torch.cuda.is_available():
            params['device'] = 'gpu'
            logger.info("LightGBM using GPU acceleration")
        
        self.model = lgb.LGBMRegressor(**params)
        self.model.fit(X_scaled, y)
        
        self.is_fitted = True
        self.training_metrics = self.evaluate(X, y)
        
        logger.info(f"LightGBM fitted with {len(X)} samples")
        return self
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted:
            raise ValueError("Model not fitted yet")
        
        X = self._validate_features(X)
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)


class TransformerBlock(nn.Module):
    """Transformer Block for time series"""
    
    def __init__(self, d_model: int, n_heads: int, d_ff: int, dropout: float = 0.1):
        super().__init__()
        self.attention = nn.MultiheadAttention(d_model, n_heads, dropout=dropout, batch_first=True)
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.ff = nn.Sequential(
            nn.Linear(d_model, d_ff),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_ff, d_model),
            nn.Dropout(dropout)
        )
    
    def forward(self, x):
        # Self-attention
        attn_out, _ = self.attention(x, x, x)
        x = self.norm1(x + attn_out)
        
        # Feed forward
        ff_out = self.ff(x)
        x = self.norm2(x + ff_out)
        
        return x


class PatchTSTModel(nn.Module):
    """
    PatchTST-inspired Transformer for time series forecasting
    簡化版本，適合中小規模資料
    """
    
    def __init__(self, input_dim: int, seq_len: int, pred_len: int = 24,
                 d_model: int = 64, n_heads: int = 4, n_layers: int = 2,
                 patch_size: int = 8, dropout: float = 0.1):
        super().__init__()
        
        self.input_dim = input_dim
        self.seq_len = seq_len
        self.pred_len = pred_len
        self.patch_size = patch_size
        self.n_patches = seq_len // patch_size
        
        # Patch embedding
        self.patch_embed = nn.Linear(patch_size * input_dim, d_model)
        
        # Positional encoding
        self.pos_embed = nn.Parameter(torch.randn(1, self.n_patches, d_model) * 0.02)
        
        # Transformer blocks
        self.transformer_blocks = nn.ModuleList([
            TransformerBlock(d_model, n_heads, d_model * 4, dropout)
            for _ in range(n_layers)
        ])
        
        # Output projection
        self.output_proj = nn.Sequential(
            nn.Linear(d_model * self.n_patches, d_model * 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model * 2, pred_len)
        )
        
        self.dropout = nn.Dropout(dropout)
    
    def forward(self, x):
        # x shape: (batch, seq_len, input_dim)
        batch_size = x.shape[0]
        
        # Create patches: (batch, n_patches, patch_size * input_dim)
        x = x.unfold(1, self.patch_size, self.patch_size)  # (batch, n_patches, input_dim, patch_size)
        x = x.permute(0, 1, 3, 2)  # (batch, n_patches, patch_size, input_dim)
        x = x.reshape(batch_size, self.n_patches, -1)  # (batch, n_patches, patch_size * input_dim)
        
        # Patch embedding
        x = self.patch_embed(x)  # (batch, n_patches, d_model)
        
        # Add positional encoding
        x = x + self.pos_embed
        x = self.dropout(x)
        
        # Transformer blocks
        for block in self.transformer_blocks:
            x = block(x)
        
        # Flatten and project
        x = x.flatten(1)  # (batch, n_patches * d_model)
        x = self.output_proj(x)  # (batch, pred_len)
        
        return x


class TransformerForecaster(BasePredictor):
    """
    Transformer 負載預測器
    使用 PatchTST 架構處理長序列依賴
    """
    
    def __init__(self, seq_len: int = 168, pred_len: int = 24):
        super().__init__("transformer_load_forecaster")
        self.seq_len = seq_len  # 輸入序列長度 (7 days * 24 hours)
        self.pred_len = pred_len  # 預測長度 (24 hours)
        self.scaler_X = StandardScaler()
        self.scaler_y = StandardScaler()
        self.device = self._get_device()
        self.model: Optional[PatchTSTModel] = None
        
        logger.info(f"TransformerForecaster initialized on {self.device}")
    
    def _get_device(self) -> torch.device:
        """獲取計算設備，管理 GPU 記憶體"""
        if torch.cuda.is_available():
            # 設定 GPU 記憶體上限以避免 OOM
            torch.cuda.set_per_process_memory_fraction(settings.gpu_memory_fraction)
            torch.cuda.empty_cache()
            device = torch.device('cuda')
            logger.info(f"Using GPU: {torch.cuda.get_device_name(0)}")
            logger.info(f"GPU Memory Fraction: {settings.gpu_memory_fraction}")
        else:
            device = torch.device('cpu')
            logger.info("Using CPU")
        return device
    
    def _prepare_sequences(self, X: pd.DataFrame, y: Optional[pd.Series] = None) -> Tuple:
        """準備序列資料"""
        X_values = X.values
        
        # 標準化
        if not hasattr(self.scaler_X, 'mean_') or self.scaler_X.mean_ is None:
            X_scaled = self.scaler_X.fit_transform(X_values)
        else:
            X_scaled = self.scaler_X.transform(X_values)
        
        sequences = []
        targets = []
        
        # 建立滑動視窗序列
        for i in range(len(X_scaled) - self.seq_len - self.pred_len + 1):
            seq = X_scaled[i:i + self.seq_len]
            sequences.append(seq)
            
            if y is not None:
                target = y.values[i + self.seq_len:i + self.seq_len + self.pred_len]
                targets.append(target)
        
        sequences = np.array(sequences)
        
        if y is not None:
            targets = np.array(targets)
            # 標準化目標
            targets_reshaped = targets.reshape(-1, 1)
            if not hasattr(self.scaler_y, 'mean_') or self.scaler_y.mean_ is None:
                targets_scaled = self.scaler_y.fit_transform(targets_reshaped)
            else:
                targets_scaled = self.scaler_y.transform(targets_reshaped)
            targets = targets_scaled.reshape(targets.shape)
            return sequences, targets
        
        return sequences, None
    
    def fit(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> 'TransformerForecaster':
        self.feature_names = list(X.columns)
        input_dim = len(self.feature_names)
        
        # 準備序列資料
        X_seq, y_seq = self._prepare_sequences(X, y)
        
        if len(X_seq) < 10:
            logger.warning("Insufficient data for Transformer training")
            self.is_fitted = False
            return self
        
        # 建立模型
        self.model = PatchTSTModel(
            input_dim=input_dim,
            seq_len=self.seq_len,
            pred_len=self.pred_len,
            d_model=kwargs.get('d_model', 64),
            n_heads=kwargs.get('n_heads', 4),
            n_layers=kwargs.get('n_layers', 2),
            patch_size=kwargs.get('patch_size', 8),
            dropout=kwargs.get('dropout', 0.1)
        ).to(self.device)
        
        # 轉換為 Tensor
        X_tensor = torch.FloatTensor(X_seq).to(self.device)
        y_tensor = torch.FloatTensor(y_seq).to(self.device)
        
        # 資料集
        dataset = TensorDataset(X_tensor, y_tensor)
        batch_size = min(settings.batch_size, len(dataset))
        dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
        
        # 訓練設定
        optimizer = torch.optim.AdamW(self.model.parameters(), lr=kwargs.get('lr', 1e-3))
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=kwargs.get('epochs', 50))
        criterion = nn.MSELoss()
        
        epochs = kwargs.get('epochs', 50)
        best_loss = float('inf')
        patience = 10
        patience_counter = 0
        
        logger.info(f"Training Transformer for {epochs} epochs...")
        
        self.model.train()
        for epoch in range(epochs):
            total_loss = 0
            for batch_X, batch_y in dataloader:
                optimizer.zero_grad()
                
                outputs = self.model(batch_X)
                loss = criterion(outputs, batch_y)
                
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                optimizer.step()
                
                total_loss += loss.item()
            
            scheduler.step()
            avg_loss = total_loss / len(dataloader)
            
            # Early stopping
            if avg_loss < best_loss:
                best_loss = avg_loss
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    logger.info(f"Early stopping at epoch {epoch + 1}")
                    break
            
            if (epoch + 1) % 10 == 0:
                logger.info(f"Epoch {epoch + 1}/{epochs}, Loss: {avg_loss:.6f}")
            
            # 清理 GPU 記憶體
            if self.device.type == 'cuda':
                torch.cuda.empty_cache()
        
        self.is_fitted = True
        logger.info(f"Transformer training complete, Best Loss: {best_loss:.6f}")
        
        return self
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted or self.model is None:
            raise ValueError("Model not fitted yet")
        
        X = self._validate_features(X)
        X_seq, _ = self._prepare_sequences(X)
        
        if len(X_seq) == 0:
            logger.warning("Insufficient data for prediction")
            return np.array([])
        
        self.model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X_seq).to(self.device)
            predictions = self.model(X_tensor).cpu().numpy()
        
        # 反標準化
        predictions_flat = predictions.reshape(-1, 1)
        predictions_original = self.scaler_y.inverse_transform(predictions_flat)
        predictions = predictions_original.reshape(predictions.shape)
        
        # 返回最後一個預測
        return predictions[-1] if len(predictions) > 0 else np.array([])
    
    def predict_rolling(self, X: pd.DataFrame, steps: int = 24) -> np.ndarray:
        """滾動式預測"""
        predictions = []
        current_X = X.copy()
        
        for _ in range(steps // self.pred_len + 1):
            pred = self.predict(current_X)
            if len(pred) == 0:
                break
            predictions.extend(pred[:min(steps - len(predictions), len(pred))])
            
            if len(predictions) >= steps:
                break
        
        return np.array(predictions[:steps])


class LoadForecaster:
    """
    負載預測整合器
    結合多個模型進行集成預測
    """
    
    def __init__(self):
        self.xgb_model = XGBoostForecaster()
        self.lgbm_model = LightGBMForecaster()
        self.transformer_model = TransformerForecaster()
        self.weights = {'xgb': 0.35, 'lgbm': 0.35, 'transformer': 0.30}
        self.is_fitted = False
        
        logger.info("LoadForecaster initialized with ensemble models")
    
    def fit(self, X: pd.DataFrame, y: pd.Series, use_transformer: bool = True, **kwargs):
        """訓練所有模型"""
        logger.info("Training LoadForecaster ensemble...")
        
        # 訓練 XGBoost
        try:
            self.xgb_model.fit(X, y, **kwargs)
        except Exception as e:
            logger.error(f"XGBoost training failed: {e}")
        
        # 訓練 LightGBM
        try:
            self.lgbm_model.fit(X, y, **kwargs)
        except Exception as e:
            logger.error(f"LightGBM training failed: {e}")
        
        # 訓練 Transformer (可選)
        if use_transformer and len(X) > 200:
            try:
                self.transformer_model.fit(X, y, **kwargs)
            except Exception as e:
                logger.error(f"Transformer training failed: {e}")
                self.weights = {'xgb': 0.5, 'lgbm': 0.5, 'transformer': 0.0}
        else:
            self.weights = {'xgb': 0.5, 'lgbm': 0.5, 'transformer': 0.0}
        
        self.is_fitted = True
        logger.info("LoadForecaster ensemble training complete")
        
        return self
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """集成預測"""
        predictions = []
        weights = []
        
        if self.xgb_model.is_fitted:
            try:
                pred = self.xgb_model.predict(X)
                predictions.append(pred)
                weights.append(self.weights['xgb'])
            except Exception as e:
                logger.warning(f"XGBoost prediction failed: {e}")
        
        if self.lgbm_model.is_fitted:
            try:
                pred = self.lgbm_model.predict(X)
                predictions.append(pred)
                weights.append(self.weights['lgbm'])
            except Exception as e:
                logger.warning(f"LightGBM prediction failed: {e}")
        
        if self.transformer_model.is_fitted and self.weights['transformer'] > 0:
            try:
                pred = self.transformer_model.predict(X)
                if len(pred) > 0:
                    # Transformer 預測的是未來序列，取均值作為單點預測
                    pred = np.full(len(X), np.mean(pred))
                    predictions.append(pred)
                    weights.append(self.weights['transformer'])
            except Exception as e:
                logger.warning(f"Transformer prediction failed: {e}")
        
        if not predictions:
            raise ValueError("No model available for prediction")
        
        # 加權平均
        weights = np.array(weights)
        weights = weights / weights.sum()
        
        ensemble_pred = np.zeros_like(predictions[0])
        for pred, w in zip(predictions, weights):
            ensemble_pred += w * pred
        
        return ensemble_pred
    
    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Dict[str, float]]:
        """評估所有模型"""
        results = {}
        
        if self.xgb_model.is_fitted:
            results['xgboost'] = self.xgb_model.evaluate(X, y)
        
        if self.lgbm_model.is_fitted:
            results['lightgbm'] = self.lgbm_model.evaluate(X, y)
        
        # Ensemble evaluation
        try:
            from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
            ensemble_pred = self.predict(X)
            results['ensemble'] = {
                'mae': mean_absolute_error(y, ensemble_pred),
                'mse': mean_squared_error(y, ensemble_pred),
                'rmse': np.sqrt(mean_squared_error(y, ensemble_pred)),
                'r2': r2_score(y, ensemble_pred)
            }
        except Exception as e:
            logger.warning(f"Ensemble evaluation failed: {e}")
        
        return results
    
    def save(self, path: Optional[Path] = None):
        """儲存所有模型"""
        base_path = path or settings.model_path
        
        if self.xgb_model.is_fitted:
            self.xgb_model.save(base_path / "xgb_load_forecaster.joblib")
        
        if self.lgbm_model.is_fitted:
            self.lgbm_model.save(base_path / "lgbm_load_forecaster.joblib")
        
        if self.transformer_model.is_fitted:
            # Save Transformer state dict
            torch.save({
                'model_state_dict': self.transformer_model.model.state_dict(),
                'scaler_X': self.transformer_model.scaler_X,
                'scaler_y': self.transformer_model.scaler_y,
                'feature_names': self.transformer_model.feature_names,
                'seq_len': self.transformer_model.seq_len,
                'pred_len': self.transformer_model.pred_len
            }, base_path / "transformer_load_forecaster.pt")
        
        logger.info(f"LoadForecaster models saved to {base_path}")
