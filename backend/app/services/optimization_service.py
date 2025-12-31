"""
Optimization Service - 整合 ecogrid 的 TOU 優化器
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd
from loguru import logger

# Import ecogrid modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))
from ecogrid.optimization.tou_optimizer import TOUOptimizer


class OptimizationService:
    """優化服務"""
    
    def __init__(self):
        self.optimizer: Optional[TOUOptimizer] = None
    
    def initialize(self):
        """初始化優化器"""
        if self.optimizer is None:
            logger.info("Initializing Optimization Service...")
            self.optimizer = TOUOptimizer()
            logger.info("Optimization Service initialized")
    
    def optimize(
        self,
        forecast_df: pd.DataFrame,
        initial_soc: float = 0.5,
        battery_capacity_kwh: Optional[float] = None,
        max_contract_kw: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        執行 MILP 優化
        
        Args:
            forecast_df: 預測數據 DataFrame
            initial_soc: 初始電池狀態
            battery_capacity_kwh: 覆蓋電池容量
            max_contract_kw: 覆蓋合約容量
            
        Returns:
            優化結果
        """
        self.initialize()
        
        # 覆蓋參數（如果提供）
        if battery_capacity_kwh is not None:
            original_capacity = self.optimizer.battery_capacity
            self.optimizer.battery_capacity = battery_capacity_kwh
        
        if max_contract_kw is not None:
            original_contract = self.optimizer.max_contract
            self.optimizer.max_contract = max_contract_kw
        
        # 執行優化
        logger.info("Starting optimization...")
        opt_result = self.optimizer.optimize_schedule(
            forecast_df,
            initial_soc=initial_soc
        )
        
        # 恢復原始參數
        if battery_capacity_kwh is not None:
            self.optimizer.battery_capacity = original_capacity
        if max_contract_kw is not None:
            self.optimizer.max_contract = original_contract
        
        logger.info(f"Optimization complete: {opt_result['result'].status}")
        
        return opt_result


# Global instance
optimization_service = OptimizationService()
