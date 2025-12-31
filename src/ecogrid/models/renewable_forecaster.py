"""
Renewable Energy Forecaster - 再生能源預測模型
太陽能與風力發電預測
"""

from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor
from loguru import logger

from ecogrid.config.settings import settings
from ecogrid.models.base_model import BasePredictor


class RandomForestForecaster(BasePredictor):
    """Random Forest 再生能源預測器"""
    
    def __init__(self, target: str = "solar"):
        super().__init__(f"rf_{target}_forecaster")
        self.target = target
        self.scaler = StandardScaler()
    
    def fit(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> 'RandomForestForecaster':
        self.feature_names = list(X.columns)
        X_scaled = self.scaler.fit_transform(X)
        
        params = {
            'n_estimators': kwargs.get('n_estimators', 100),
            'max_depth': kwargs.get('max_depth', 15),
            'min_samples_split': kwargs.get('min_samples_split', 5),
            'min_samples_leaf': kwargs.get('min_samples_leaf', 2),
            'max_features': 'sqrt',
            'random_state': 42,
            'n_jobs': -1
        }
        
        self.model = RandomForestRegressor(**params)
        self.model.fit(X_scaled, y)
        
        self.is_fitted = True
        self.training_metrics = self.evaluate(X, y)
        
        logger.info(f"Random Forest ({self.target}) fitted with {len(X)} samples")
        return self
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted:
            raise ValueError("Model not fitted yet")
        
        X = self._validate_features(X)
        X_scaled = self.scaler.transform(X)
        predictions = self.model.predict(X_scaled)
        
        # 確保預測值非負
        return np.maximum(predictions, 0)


class LSTMModel(nn.Module):
    """LSTM 模型用於時序預測"""
    
    def __init__(self, input_dim: int, hidden_dim: int = 64, 
                 num_layers: int = 2, dropout: float = 0.2):
        super().__init__()
        
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=False
        )
        
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 1)
        )
    
    def forward(self, x):
        # x shape: (batch, seq_len, input_dim)
        lstm_out, (h_n, c_n) = self.lstm(x)
        
        # 使用最後一個時間步的輸出
        last_output = lstm_out[:, -1, :]  # (batch, hidden_dim)
        
        output = self.fc(last_output)  # (batch, 1)
        return output.squeeze(-1)


class LSTMForecaster(BasePredictor):
    """LSTM 再生能源預測器"""
    
    def __init__(self, target: str = "solar", seq_len: int = 48):
        super().__init__(f"lstm_{target}_forecaster")
        self.target = target
        self.seq_len = seq_len
        self.scaler_X = StandardScaler()
        self.scaler_y = StandardScaler()
        self.device = self._get_device()
        self.model: Optional[LSTMModel] = None
    
    def _get_device(self) -> torch.device:
        if torch.cuda.is_available():
            torch.cuda.set_per_process_memory_fraction(settings.gpu_memory_fraction)
            torch.cuda.empty_cache()
            return torch.device('cuda')
        return torch.device('cpu')
    
    def _prepare_sequences(self, X: pd.DataFrame, y: Optional[pd.Series] = None) -> Tuple:
        """準備 LSTM 序列資料"""
        X_values = X.values
        
        if not hasattr(self.scaler_X, 'mean_') or self.scaler_X.mean_ is None:
            X_scaled = self.scaler_X.fit_transform(X_values)
        else:
            X_scaled = self.scaler_X.transform(X_values)
        
        sequences = []
        targets = []
        
        for i in range(len(X_scaled) - self.seq_len):
            seq = X_scaled[i:i + self.seq_len]
            sequences.append(seq)
            
            if y is not None:
                targets.append(y.values[i + self.seq_len])
        
        sequences = np.array(sequences)
        
        if y is not None:
            targets = np.array(targets).reshape(-1, 1)
            if not hasattr(self.scaler_y, 'mean_') or self.scaler_y.mean_ is None:
                targets_scaled = self.scaler_y.fit_transform(targets)
            else:
                targets_scaled = self.scaler_y.transform(targets)
            return sequences, targets_scaled.flatten()
        
        return sequences, None
    
    def fit(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> 'LSTMForecaster':
        self.feature_names = list(X.columns)
        input_dim = len(self.feature_names)
        
        X_seq, y_seq = self._prepare_sequences(X, y)
        
        if len(X_seq) < 10:
            logger.warning("Insufficient data for LSTM training")
            self.is_fitted = False
            return self
        
        # 建立模型
        self.model = LSTMModel(
            input_dim=input_dim,
            hidden_dim=kwargs.get('hidden_dim', 64),
            num_layers=kwargs.get('num_layers', 2),
            dropout=kwargs.get('dropout', 0.2)
        ).to(self.device)
        
        # 資料準備
        X_tensor = torch.FloatTensor(X_seq).to(self.device)
        y_tensor = torch.FloatTensor(y_seq).to(self.device)
        
        dataset = TensorDataset(X_tensor, y_tensor)
        batch_size = min(settings.batch_size, len(dataset))
        dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
        
        # 訓練
        optimizer = torch.optim.Adam(self.model.parameters(), lr=kwargs.get('lr', 1e-3))
        criterion = nn.MSELoss()
        
        epochs = kwargs.get('epochs', 50)
        best_loss = float('inf')
        patience = 10
        patience_counter = 0
        
        logger.info(f"Training LSTM for {epochs} epochs...")
        
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
            
            avg_loss = total_loss / len(dataloader)
            
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
            
            if self.device.type == 'cuda':
                torch.cuda.empty_cache()
        
        self.is_fitted = True
        logger.info(f"LSTM ({self.target}) training complete")
        
        return self
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted or self.model is None:
            raise ValueError("Model not fitted yet")
        
        X = self._validate_features(X)
        X_seq, _ = self._prepare_sequences(X)
        
        if len(X_seq) == 0:
            return np.array([])
        
        self.model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X_seq).to(self.device)
            predictions = self.model(X_tensor).cpu().numpy()
        
        # 反標準化
        predictions = self.scaler_y.inverse_transform(predictions.reshape(-1, 1)).flatten()
        
        # 確保非負
        return np.maximum(predictions, 0)


class RenewableForecaster:
    """
    再生能源預測整合器
    整合太陽能和風力發電預測
    """
    
    def __init__(self):
        # 太陽能預測模型
        self.solar_rf = RandomForestForecaster(target="solar")
        self.solar_lstm = LSTMForecaster(target="solar")
        
        # 風力預測模型
        self.wind_rf = RandomForestForecaster(target="wind")
        self.wind_lstm = LSTMForecaster(target="wind")
        
        self.weights = {'rf': 0.5, 'lstm': 0.5}
        self.is_fitted = False
        
        logger.info("RenewableForecaster initialized")
    
    def fit(self, X: pd.DataFrame, y_solar: pd.Series, y_wind: pd.Series, 
            use_lstm: bool = True, **kwargs):
        """訓練太陽能和風力預測模型"""
        logger.info("Training RenewableForecaster...")
        
        # 訓練太陽能模型
        try:
            self.solar_rf.fit(X, y_solar, **kwargs)
        except Exception as e:
            logger.error(f"Solar RF training failed: {e}")
        
        if use_lstm and len(X) > 100:
            try:
                self.solar_lstm.fit(X, y_solar, **kwargs)
            except Exception as e:
                logger.error(f"Solar LSTM training failed: {e}")
        
        # 訓練風力模型
        try:
            self.wind_rf.fit(X, y_wind, **kwargs)
        except Exception as e:
            logger.error(f"Wind RF training failed: {e}")
        
        if use_lstm and len(X) > 100:
            try:
                self.wind_lstm.fit(X, y_wind, **kwargs)
            except Exception as e:
                logger.error(f"Wind LSTM training failed: {e}")
        
        self.is_fitted = True
        logger.info("RenewableForecaster training complete")
        
        return self
    
    def predict_solar(self, X: pd.DataFrame) -> np.ndarray:
        """預測太陽能發電"""
        predictions = []
        weights = []
        
        # 處理 NaN 值
        X_clean = X.copy()
        numeric_cols = X_clean.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if X_clean[col].isna().any():
                X_clean[col] = X_clean[col].ffill().bfill().fillna(0)
        
        if self.solar_rf.is_fitted:
            try:
                pred = self.solar_rf.predict(X_clean)
                predictions.append(pred)
                weights.append(self.weights['rf'])
            except Exception as e:
                logger.warning(f"Solar RF prediction failed: {e}")
        
        if self.solar_lstm.is_fitted:
            try:
                pred = self.solar_lstm.predict(X_clean)
                if len(pred) > 0:
                    # 對齊長度
                    if len(pred) < len(X):
                        pred = np.pad(pred, (len(X) - len(pred), 0), mode='edge')
                    predictions.append(pred[:len(X)])
                    weights.append(self.weights['lstm'])
            except Exception as e:
                logger.warning(f"Solar LSTM prediction failed: {e}")
        
        if not predictions:
            return np.zeros(len(X))
        
        weights = np.array(weights) / sum(weights)
        return sum(w * p for w, p in zip(weights, predictions))
    
    def predict_wind(self, X: pd.DataFrame) -> np.ndarray:
        """預測風力發電"""
        predictions = []
        weights = []
        
        # 處理 NaN 值
        X_clean = X.copy()
        numeric_cols = X_clean.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if X_clean[col].isna().any():
                X_clean[col] = X_clean[col].ffill().bfill().fillna(0)
        
        if self.wind_rf.is_fitted:
            try:
                pred = self.wind_rf.predict(X_clean)
                predictions.append(pred)
                weights.append(self.weights['rf'])
            except Exception as e:
                logger.warning(f"Wind RF prediction failed: {e}")
        
        if self.wind_lstm.is_fitted:
            try:
                pred = self.wind_lstm.predict(X_clean)
                if len(pred) > 0:
                    if len(pred) < len(X):
                        pred = np.pad(pred, (len(X) - len(pred), 0), mode='edge')
                    predictions.append(pred[:len(X)])
                    weights.append(self.weights['lstm'])
            except Exception as e:
                logger.warning(f"Wind LSTM prediction failed: {e}")
        
        if not predictions:
            return np.zeros(len(X))
        
        weights = np.array(weights) / sum(weights)
        return sum(w * p for w, p in zip(weights, predictions))
    
    def predict(self, X: pd.DataFrame) -> Dict[str, np.ndarray]:
        """預測所有再生能源"""
        return {
            'solar': self.predict_solar(X),
            'wind': self.predict_wind(X),
            'total': self.predict_solar(X) + self.predict_wind(X)
        }
    
    def evaluate(self, X: pd.DataFrame, y_solar: pd.Series, 
                 y_wind: pd.Series) -> Dict[str, Dict[str, float]]:
        """評估模型"""
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
        
        results = {}
        
        # 太陽能評估
        solar_pred = self.predict_solar(X)
        if len(solar_pred) == len(y_solar):
            results['solar'] = {
                'mae': mean_absolute_error(y_solar, solar_pred),
                'rmse': np.sqrt(mean_squared_error(y_solar, solar_pred)),
                'r2': r2_score(y_solar, solar_pred)
            }
        
        # 風力評估
        wind_pred = self.predict_wind(X)
        if len(wind_pred) == len(y_wind):
            results['wind'] = {
                'mae': mean_absolute_error(y_wind, wind_pred),
                'rmse': np.sqrt(mean_squared_error(y_wind, wind_pred)),
                'r2': r2_score(y_wind, wind_pred)
            }
        
        return results
    
    def save(self, path: Optional[Path] = None):
        """儲存模型"""
        base_path = path or settings.model_path
        
        if self.solar_rf.is_fitted:
            self.solar_rf.save(base_path / "rf_solar_forecaster.joblib")
        if self.wind_rf.is_fitted:
            self.wind_rf.save(base_path / "rf_wind_forecaster.joblib")
        
        if self.solar_lstm.is_fitted and self.solar_lstm.model:
            torch.save({
                'model_state_dict': self.solar_lstm.model.state_dict(),
                'scaler_X': self.solar_lstm.scaler_X,
                'scaler_y': self.solar_lstm.scaler_y,
                'feature_names': self.solar_lstm.feature_names
            }, base_path / "lstm_solar_forecaster.pt")
        
        if self.wind_lstm.is_fitted and self.wind_lstm.model:
            torch.save({
                'model_state_dict': self.wind_lstm.model.state_dict(),
                'scaler_X': self.wind_lstm.scaler_X,
                'scaler_y': self.wind_lstm.scaler_y,
                'feature_names': self.wind_lstm.feature_names
            }, base_path / "lstm_wind_forecaster.pt")
        
        logger.info(f"RenewableForecaster models saved to {base_path}")
