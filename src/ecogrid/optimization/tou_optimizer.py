"""
TOU Optimizer - 時間電價優化模組
使用混合整數線性規劃 (MILP) 進行電力成本優化
"""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

import numpy as np
import pandas as pd
from loguru import logger

try:
    import pulp
    PULP_AVAILABLE = True
except ImportError:
    PULP_AVAILABLE = False
    logger.warning("PuLP not available, optimization features limited")

from ecogrid.config.settings import settings


@dataclass
class OptimizationResult:
    """優化結果資料結構"""
    status: str
    total_cost: float
    baseline_cost: float
    savings: float
    savings_percent: float
    battery_schedule: List[float]
    grid_consumption: List[float]
    solar_utilization: List[float]
    peak_reduction: float
    recommendations: List[str]


class TOUOptimizer:
    """
    時間電價優化器
    
    使用 MILP 模型優化:
    - 電池充放電策略
    - 市電與綠電配比
    - 削峰填谷 (Peak Shaving)
    
    目標函數:
    $$TotalCost = \sum(Load_t \times Tariff_t) - \sum(Solar_t \times Tariff_t)$$
    
    約束條件:
    - 電池 SoC 上下限
    - 合約容量限制
    - 能量平衡
    """
    
    def __init__(self):
        self.battery_capacity = settings.battery_capacity_kwh  # kWh
        self.max_contract = settings.max_contract_capacity_kw  # kW
        self.battery_efficiency = settings.battery_efficiency
        self.min_soc = settings.min_soc
        self.max_soc = settings.max_soc
        self.time_horizon = settings.optimization_time_horizon  # hours
        
        logger.info(f"TOUOptimizer initialized - Battery: {self.battery_capacity}kWh, "
                   f"Contract: {self.max_contract}kW")
    
    def optimize(self, 
                 load_forecast: np.ndarray,
                 solar_forecast: np.ndarray,
                 wind_forecast: np.ndarray,
                 tariffs: np.ndarray,
                 initial_soc: float = 0.5) -> OptimizationResult:
        """
        執行電力成本優化
        
        Args:
            load_forecast: 負載預測 (kW)
            solar_forecast: 太陽能預測 (kW)
            wind_forecast: 風力預測 (kW)
            tariffs: 電價時序 (NTD/kWh)
            initial_soc: 初始電池狀態 (0-1)
            
        Returns:
            OptimizationResult
        """
        if not PULP_AVAILABLE:
            logger.error("PuLP not available, returning baseline result")
            return self._baseline_result(load_forecast, solar_forecast, wind_forecast, tariffs)
        
        T = len(load_forecast)  # 時間段數
        
        logger.info(f"Starting optimization for {T} time periods")
        
        # 建立優化問題
        prob = pulp.LpProblem("TOU_Optimization", pulp.LpMinimize)
        
        # 決策變數
        # 電網購電量 (kW)
        grid_buy = [pulp.LpVariable(f"grid_buy_{t}", lowBound=0, upBound=self.max_contract) 
                   for t in range(T)]
        
        # 電池充電量 (kW)
        battery_charge = [pulp.LpVariable(f"battery_charge_{t}", lowBound=0, 
                         upBound=self.battery_capacity * 0.5) for t in range(T)]
        
        # 電池放電量 (kW)
        battery_discharge = [pulp.LpVariable(f"battery_discharge_{t}", lowBound=0,
                            upBound=self.battery_capacity * 0.5) for t in range(T)]
        
        # 電池狀態 (kWh)
        soc = [pulp.LpVariable(f"soc_{t}", lowBound=self.battery_capacity * self.min_soc,
               upBound=self.battery_capacity * self.max_soc) for t in range(T + 1)]
        
        # 太陽能使用量 (kW)
        solar_used = [pulp.LpVariable(f"solar_used_{t}", lowBound=0, 
                     upBound=max(solar_forecast[t], 0.001)) for t in range(T)]
        
        # 風力使用量 (kW)
        wind_used = [pulp.LpVariable(f"wind_used_{t}", lowBound=0,
                    upBound=max(wind_forecast[t], 0.001)) for t in range(T)]
        
        # 目標函數: 最小化總電力成本
        # Cost = Σ(Grid_t × Tariff_t) - Σ(Renewable_t × Tariff_t × credit_factor)
        renewable_credit = 0.8  # 綠電扣抵係數
        
        prob += pulp.lpSum([
            grid_buy[t] * tariffs[t] - 
            (solar_used[t] + wind_used[t]) * tariffs[t] * renewable_credit
            for t in range(T)
        ])
        
        # 約束條件
        
        # 1. 能量平衡: 負載 = 電網 + 太陽能 + 風力 + 電池放電 - 電池充電
        for t in range(T):
            prob += (grid_buy[t] + solar_used[t] + wind_used[t] + 
                    battery_discharge[t] * self.battery_efficiency - 
                    battery_charge[t] >= load_forecast[t])
        
        # 2. 電池 SoC 動態
        prob += soc[0] == self.battery_capacity * initial_soc
        
        for t in range(T):
            prob += soc[t + 1] == (soc[t] + 
                                  battery_charge[t] * self.battery_efficiency - 
                                  battery_discharge[t])
        
        # 3. 太陽能和風力使用不超過可用量
        for t in range(T):
            prob += solar_used[t] <= max(solar_forecast[t], 0)
            prob += wind_used[t] <= max(wind_forecast[t], 0)
        
        # 4. 充放電互斥 (簡化處理 - 用大 M 法)
        M = self.battery_capacity * 2
        charge_flag = [pulp.LpVariable(f"charge_flag_{t}", cat='Binary') for t in range(T)]
        
        for t in range(T):
            prob += battery_charge[t] <= M * charge_flag[t]
            prob += battery_discharge[t] <= M * (1 - charge_flag[t])
        
        # 5. 削峰約束 - 尖峰時段限制電網購電
        peak_limit = self.max_contract * 0.8  # 尖峰時段限制在 80%
        for t in range(T):
            if tariffs[t] >= settings.summer_peak_rate * 0.9:  # 尖峰時段
                prob += grid_buy[t] <= peak_limit
        
        # 求解
        solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=60)
        prob.solve(solver)
        
        status = pulp.LpStatus[prob.status]
        logger.info(f"Optimization status: {status}")
        
        if status != 'Optimal':
            logger.warning(f"Optimization not optimal: {status}")
            return self._baseline_result(load_forecast, solar_forecast, wind_forecast, tariffs)
        
        # 提取結果
        grid_schedule = [grid_buy[t].varValue or 0 for t in range(T)]
        charge_schedule = [battery_charge[t].varValue or 0 for t in range(T)]
        discharge_schedule = [battery_discharge[t].varValue or 0 for t in range(T)]
        solar_schedule = [solar_used[t].varValue or 0 for t in range(T)]
        wind_schedule = [wind_used[t].varValue or 0 for t in range(T)]
        soc_schedule = [(soc[t].varValue or 0) / self.battery_capacity for t in range(T + 1)]
        
        # 電池淨充放電 (正=充電, 負=放電)
        battery_schedule = [charge_schedule[t] - discharge_schedule[t] for t in range(T)]
        
        # 計算成本
        total_cost = pulp.value(prob.objective)
        baseline_cost = sum(load_forecast[t] * tariffs[t] for t in range(T))
        savings = baseline_cost - total_cost
        savings_percent = (savings / baseline_cost * 100) if baseline_cost > 0 else 0
        
        # 計算削峰效果
        baseline_peak = max(load_forecast)
        optimized_peak = max(grid_schedule)
        peak_reduction = ((baseline_peak - optimized_peak) / baseline_peak * 100 
                         if baseline_peak > 0 else 0)
        
        # 生成建議
        recommendations = self._generate_recommendations(
            load_forecast, solar_forecast, grid_schedule, 
            battery_schedule, tariffs, peak_reduction
        )
        
        logger.info(f"Optimization complete - Savings: {savings:.2f} NTD ({savings_percent:.1f}%)")
        
        return OptimizationResult(
            status=status,
            total_cost=total_cost,
            baseline_cost=baseline_cost,
            savings=savings,
            savings_percent=savings_percent,
            battery_schedule=battery_schedule,
            grid_consumption=grid_schedule,
            solar_utilization=solar_schedule,
            peak_reduction=peak_reduction,
            recommendations=recommendations
        )
    
    def _baseline_result(self, load_forecast: np.ndarray, solar_forecast: np.ndarray,
                        wind_forecast: np.ndarray, tariffs: np.ndarray) -> OptimizationResult:
        """生成基準結果（無優化）"""
        T = len(load_forecast)
        net_load = np.maximum(load_forecast - solar_forecast - wind_forecast, 0)
        baseline_cost = sum(net_load[t] * tariffs[t] for t in range(T))
        
        return OptimizationResult(
            status="Baseline",
            total_cost=baseline_cost,
            baseline_cost=baseline_cost,
            savings=0,
            savings_percent=0,
            battery_schedule=[0] * T,
            grid_consumption=list(net_load),
            solar_utilization=list(np.minimum(solar_forecast, load_forecast)),
            peak_reduction=0,
            recommendations=["建議安裝儲能系統以實現成本優化"]
        )
    
    def _generate_recommendations(self, load: np.ndarray, solar: np.ndarray,
                                  grid: List[float], battery: List[float],
                                  tariffs: np.ndarray, peak_reduction: float) -> List[str]:
        """生成優化建議"""
        recommendations = []
        
        # 1. 尖峰時段建議
        peak_hours = [i for i, t in enumerate(tariffs) if t >= settings.summer_peak_rate * 0.9]
        if peak_hours:
            peak_load = sum(load[h] for h in peak_hours)
            peak_grid = sum(grid[h] for h in peak_hours)
            if peak_grid < peak_load * 0.8:
                recommendations.append(
                    f"尖峰時段({peak_hours[0]}:00-{peak_hours[-1]+1}:00)成功減少"
                    f"{((peak_load - peak_grid) / peak_load * 100):.1f}%電網用電"
                )
        
        # 2. 電池使用建議
        total_discharge = sum(max(-b, 0) for b in battery)
        if total_discharge > 0:
            recommendations.append(
                f"電池在尖峰時段提供 {total_discharge:.1f} kWh 電力，有效降低尖峰需量"
            )
        
        # 3. 太陽能利用建議
        solar_available = sum(solar)
        solar_used = sum(min(s, l) for s, l in zip(solar, load))
        if solar_available > 0:
            utilization = solar_used / solar_available * 100
            recommendations.append(
                f"太陽能利用率達 {utilization:.1f}%，"
                f"{'建議增加儲能容量提升利用率' if utilization < 80 else '利用效率良好'}"
            )
        
        # 4. 削峰效果
        if peak_reduction > 5:
            recommendations.append(
                f"削峰效果顯著，尖峰負載降低 {peak_reduction:.1f}%"
            )
        
        # 5. 離峰充電建議
        off_peak_hours = [i for i, t in enumerate(tariffs) if t <= settings.summer_off_peak_rate * 1.1]
        if off_peak_hours:
            off_peak_charge = sum(max(battery[h], 0) for h in off_peak_hours if h < len(battery))
            if off_peak_charge > 0:
                recommendations.append(
                    f"建議在離峰時段({off_peak_hours[0]}:00-{off_peak_hours[-1]+1}:00)"
                    f"進行電池充電，充電量 {off_peak_charge:.1f} kWh"
                )
        
        return recommendations if recommendations else ["系統運行正常，目前無特別建議"]
    
    def optimize_schedule(self, forecast_df: pd.DataFrame, 
                          initial_soc: float = 0.5) -> Dict[str, Any]:
        """
        根據預測資料優化排程
        
        Args:
            forecast_df: 包含預測資料的 DataFrame
            initial_soc: 初始電池狀態
            
        Returns:
            優化結果和排程
        """
        # 準備輸入資料 (注意：原始資料是 MW 單位，代表系統級別)
        load_raw = forecast_df['predicted_load_mw'].values if 'predicted_load_mw' in forecast_df.columns else np.zeros(len(forecast_df))
        solar_raw = forecast_df['predicted_solar_mw'].values if 'predicted_solar_mw' in forecast_df.columns else np.zeros(len(forecast_df))
        wind_raw = forecast_df['predicted_wind_mw'].values if 'predicted_wind_mw' in forecast_df.columns else np.zeros(len(forecast_df))
        tariffs = forecast_df['tariff'].values if 'tariff' in forecast_df.columns else np.full(len(forecast_df), 5.0)
        
        # 縮放到企業規模
        # 假設企業用電約佔系統總負載的 0.0001% (約 20 kW ~ 300 kW 範圍)
        # 使負載峰值約為合約容量的 80%
        load_max_mw = np.max(load_raw) if np.max(load_raw) > 0 else 1
        target_peak_kw = self.max_contract * 0.8  # 目標峰值約 400 kW
        scale_factor = target_peak_kw / (load_max_mw * 1000)  # MW 轉 kW 並縮放
        
        load = load_raw * 1000 * scale_factor  # 轉換並縮放
        solar = solar_raw * 1000 * scale_factor
        wind = wind_raw * 1000 * scale_factor
        
        logger.info(f"Load scaled: max {np.max(load):.1f} kW, avg {np.mean(load):.1f} kW")
        
        # 執行優化
        result = self.optimize(load, solar, wind, tariffs, initial_soc)
        
        # 建立優化排程 DataFrame
        schedule_df = forecast_df.copy()
        schedule_df['optimized_grid_kw'] = result.grid_consumption
        schedule_df['battery_schedule_kw'] = result.battery_schedule
        schedule_df['solar_used_kw'] = result.solar_utilization
        schedule_df['baseline_cost'] = load * tariffs
        schedule_df['optimized_cost'] = np.array(result.grid_consumption) * tariffs
        
        return {
            'result': result,
            'schedule': schedule_df,
            'summary': {
                'total_cost': result.total_cost,
                'baseline_cost': result.baseline_cost,
                'savings': result.savings,
                'savings_percent': result.savings_percent,
                'peak_reduction': result.peak_reduction,
                'recommendations': result.recommendations
            }
        }
    
    def simulate_scenarios(self, forecast_df: pd.DataFrame, 
                          scenarios: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        模擬不同情境
        
        Args:
            forecast_df: 預測資料
            scenarios: 情境列表，每個情境包含不同的參數設定
            
        Returns:
            各情境的優化結果
        """
        results = []
        
        for i, scenario in enumerate(scenarios):
            logger.info(f"Simulating scenario {i + 1}: {scenario.get('name', 'Unnamed')}")
            
            # 更新參數
            original_capacity = self.battery_capacity
            original_contract = self.max_contract
            
            self.battery_capacity = scenario.get('battery_capacity', self.battery_capacity)
            self.max_contract = scenario.get('max_contract', self.max_contract)
            
            # 執行優化
            opt_result = self.optimize_schedule(
                forecast_df, 
                initial_soc=scenario.get('initial_soc', 0.5)
            )
            
            results.append({
                'scenario': scenario.get('name', f'Scenario_{i + 1}'),
                'battery_capacity': self.battery_capacity,
                'max_contract': self.max_contract,
                'result': opt_result
            })
            
            # 恢復原始參數
            self.battery_capacity = original_capacity
            self.max_contract = original_contract
        
        return results
