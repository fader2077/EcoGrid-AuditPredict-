"""
Audit Tools for LLM Agent
定義 LLM 可調用的計算工具，確保所有數值計算由 Python 處理
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from loguru import logger

from ecogrid.config.settings import settings


class AuditTools:
    """
    審計工具集
    
    提供 LLM 調用的計算功能，確保：
    1. 所有數值計算由 Python 執行
    2. LLM 只負責解釋結果
    3. 防止 LLM 幻覺（Hallucination）
    """
    
    def __init__(self):
        logger.info("AuditTools initialized")
    
    # ==================== 成本計算工具 ====================
    
    def calculate_electricity_cost(self, 
                                   consumption_kwh: float, 
                                   tariff_rate: float) -> Dict[str, Any]:
        """
        計算電費
        
        Args:
            consumption_kwh: 用電量 (kWh)
            tariff_rate: 電價費率 (NTD/kWh)
            
        Returns:
            計算結果字典
        """
        cost = consumption_kwh * tariff_rate
        return {
            "consumption_kwh": round(consumption_kwh, 2),
            "tariff_rate": round(tariff_rate, 2),
            "cost_ntd": round(cost, 2),
            "calculation": f"{consumption_kwh:.2f} kWh × {tariff_rate:.2f} NTD/kWh = {cost:.2f} NTD"
        }
    
    def calculate_period_cost(self, 
                             hourly_consumption: List[float],
                             hourly_tariffs: List[float]) -> Dict[str, Any]:
        """
        計算時段電費
        
        Args:
            hourly_consumption: 每小時用電量 (kWh)
            hourly_tariffs: 每小時電價 (NTD/kWh)
            
        Returns:
            分時段成本計算結果
        """
        if len(hourly_consumption) != len(hourly_tariffs):
            return {"error": "資料長度不一致"}
        
        total_consumption = sum(hourly_consumption)
        total_cost = sum(c * t for c, t in zip(hourly_consumption, hourly_tariffs))
        avg_rate = total_cost / total_consumption if total_consumption > 0 else 0
        
        # 分時段統計
        peak_cost = sum(c * t for c, t in zip(hourly_consumption, hourly_tariffs) 
                       if t >= settings.summer_peak_rate * 0.9)
        off_peak_cost = sum(c * t for c, t in zip(hourly_consumption, hourly_tariffs)
                          if t <= settings.summer_off_peak_rate * 1.1)
        half_peak_cost = total_cost - peak_cost - off_peak_cost
        
        return {
            "total_consumption_kwh": round(total_consumption, 2),
            "total_cost_ntd": round(total_cost, 2),
            "average_rate_ntd_kwh": round(avg_rate, 4),
            "peak_cost_ntd": round(peak_cost, 2),
            "half_peak_cost_ntd": round(half_peak_cost, 2),
            "off_peak_cost_ntd": round(off_peak_cost, 2),
            "peak_ratio": round(peak_cost / total_cost * 100, 1) if total_cost > 0 else 0
        }
    
    def calculate_savings(self, 
                         baseline_cost: float, 
                         optimized_cost: float) -> Dict[str, Any]:
        """
        計算節省金額
        
        Args:
            baseline_cost: 基準成本 (NTD)
            optimized_cost: 優化後成本 (NTD)
            
        Returns:
            節省計算結果
        """
        savings = baseline_cost - optimized_cost
        savings_percent = (savings / baseline_cost * 100) if baseline_cost > 0 else 0
        
        return {
            "baseline_cost_ntd": round(baseline_cost, 2),
            "optimized_cost_ntd": round(optimized_cost, 2),
            "savings_ntd": round(savings, 2),
            "savings_percent": round(savings_percent, 2),
            "annual_savings_estimate_ntd": round(savings * 365 / 30, 0)  # 月轉年估算
        }
    
    # ==================== 碳排計算工具 ====================
    
    def calculate_carbon_emission(self, 
                                  consumption_kwh: float,
                                  emission_factor: Optional[float] = None) -> Dict[str, Any]:
        """
        計算碳排放量
        
        Args:
            consumption_kwh: 用電量 (kWh)
            emission_factor: 排碳係數 (kg CO2/kWh)，預設使用台電係數
            
        Returns:
            碳排計算結果
        """
        factor = emission_factor or settings.carbon_emission_factor
        emission_kg = consumption_kwh * factor
        
        return {
            "consumption_kwh": round(consumption_kwh, 2),
            "emission_factor_kg_co2_kwh": round(factor, 3),
            "emission_kg_co2": round(emission_kg, 2),
            "emission_ton_co2": round(emission_kg / 1000, 4),
            "calculation": f"{consumption_kwh:.2f} kWh × {factor:.3f} kg CO2/kWh = {emission_kg:.2f} kg CO2"
        }
    
    def calculate_renewable_offset(self, 
                                   total_consumption_kwh: float,
                                   renewable_kwh: float) -> Dict[str, Any]:
        """
        計算再生能源抵減
        
        Args:
            total_consumption_kwh: 總用電量 (kWh)
            renewable_kwh: 再生能源使用量 (kWh)
            
        Returns:
            再生能源抵減計算結果
        """
        grid_consumption = max(total_consumption_kwh - renewable_kwh, 0)
        renewable_ratio = (renewable_kwh / total_consumption_kwh * 100) if total_consumption_kwh > 0 else 0
        
        baseline_emission = total_consumption_kwh * settings.carbon_emission_factor
        actual_emission = grid_consumption * settings.carbon_emission_factor
        emission_reduction = baseline_emission - actual_emission
        
        return {
            "total_consumption_kwh": round(total_consumption_kwh, 2),
            "renewable_kwh": round(renewable_kwh, 2),
            "grid_consumption_kwh": round(grid_consumption, 2),
            "renewable_ratio_percent": round(renewable_ratio, 2),
            "baseline_emission_kg_co2": round(baseline_emission, 2),
            "actual_emission_kg_co2": round(actual_emission, 2),
            "emission_reduction_kg_co2": round(emission_reduction, 2)
        }
    
    # ==================== 統計分析工具 ====================
    
    def calculate_statistics(self, data: List[float]) -> Dict[str, Any]:
        """
        計算統計指標
        
        Args:
            data: 數據列表
            
        Returns:
            統計指標
        """
        if not data:
            return {"error": "無資料"}
        
        arr = np.array(data)
        
        return {
            "count": len(data),
            "sum": round(float(np.sum(arr)), 2),
            "mean": round(float(np.mean(arr)), 4),
            "median": round(float(np.median(arr)), 4),
            "std": round(float(np.std(arr)), 4),
            "min": round(float(np.min(arr)), 4),
            "max": round(float(np.max(arr)), 4),
            "percentile_25": round(float(np.percentile(arr, 25)), 4),
            "percentile_75": round(float(np.percentile(arr, 75)), 4)
        }
    
    def calculate_comparison(self, 
                            predicted: List[float], 
                            actual: List[float]) -> Dict[str, Any]:
        """
        計算預測與實際比較指標
        
        Args:
            predicted: 預測值列表
            actual: 實際值列表
            
        Returns:
            比較指標
        """
        if len(predicted) != len(actual):
            return {"error": "資料長度不一致"}
        
        pred = np.array(predicted)
        act = np.array(actual)
        
        mae = np.mean(np.abs(pred - act))
        mse = np.mean((pred - act) ** 2)
        rmse = np.sqrt(mse)
        mape = np.mean(np.abs((act - pred) / (act + 1e-8))) * 100
        
        # R² Score
        ss_res = np.sum((act - pred) ** 2)
        ss_tot = np.sum((act - np.mean(act)) ** 2)
        r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        return {
            "mae": round(float(mae), 4),
            "mse": round(float(mse), 4),
            "rmse": round(float(rmse), 4),
            "mape_percent": round(float(mape), 2),
            "r2_score": round(float(r2), 4),
            "total_predicted": round(float(np.sum(pred)), 2),
            "total_actual": round(float(np.sum(act)), 2),
            "total_deviation": round(float(np.sum(pred) - np.sum(act)), 2),
            "total_deviation_percent": round(float((np.sum(pred) - np.sum(act)) / np.sum(act) * 100), 2) if np.sum(act) > 0 else 0
        }
    
    # ==================== 異常偵測工具 ====================
    
    def detect_anomalies(self, 
                        data: List[float], 
                        threshold_std: float = 2.0) -> Dict[str, Any]:
        """
        偵測異常值
        
        Args:
            data: 數據列表
            threshold_std: 異常閾值（標準差倍數）
            
        Returns:
            異常偵測結果
        """
        if len(data) < 3:
            return {"error": "資料量不足"}
        
        arr = np.array(data)
        mean = np.mean(arr)
        std = np.std(arr)
        
        upper_bound = mean + threshold_std * std
        lower_bound = mean - threshold_std * std
        
        anomalies = []
        for i, val in enumerate(data):
            if val > upper_bound or val < lower_bound:
                anomalies.append({
                    "index": i,
                    "value": round(val, 4),
                    "deviation_std": round((val - mean) / std, 2) if std > 0 else 0,
                    "type": "high" if val > upper_bound else "low"
                })
        
        return {
            "mean": round(mean, 4),
            "std": round(std, 4),
            "upper_bound": round(upper_bound, 4),
            "lower_bound": round(lower_bound, 4),
            "anomaly_count": len(anomalies),
            "anomaly_rate_percent": round(len(anomalies) / len(data) * 100, 2),
            "anomalies": anomalies
        }
    
    # ==================== TOU 分析工具 ====================
    
    def analyze_tou_distribution(self, 
                                 hourly_data: List[float],
                                 start_hour: int = 0) -> Dict[str, Any]:
        """
        分析時間電價分佈
        
        Args:
            hourly_data: 24小時數據（或更長）
            start_hour: 起始小時
            
        Returns:
            TOU 分佈分析
        """
        peak_hours = list(range(10, 12)) + list(range(13, 17))
        half_peak_hours = list(range(7, 10)) + [12] + list(range(17, 23))
        off_peak_hours = list(range(0, 7)) + [23]
        
        total = sum(hourly_data)
        
        # 按時段分類
        peak_consumption = sum(hourly_data[h % len(hourly_data)] for h in peak_hours if h < len(hourly_data))
        half_peak_consumption = sum(hourly_data[h % len(hourly_data)] for h in half_peak_hours if h < len(hourly_data))
        off_peak_consumption = sum(hourly_data[h % len(hourly_data)] for h in off_peak_hours if h < len(hourly_data))
        
        return {
            "total_consumption": round(total, 2),
            "peak": {
                "consumption": round(peak_consumption, 2),
                "ratio_percent": round(peak_consumption / total * 100, 1) if total > 0 else 0,
                "hours": peak_hours
            },
            "half_peak": {
                "consumption": round(half_peak_consumption, 2),
                "ratio_percent": round(half_peak_consumption / total * 100, 1) if total > 0 else 0,
                "hours": half_peak_hours
            },
            "off_peak": {
                "consumption": round(off_peak_consumption, 2),
                "ratio_percent": round(off_peak_consumption / total * 100, 1) if total > 0 else 0,
                "hours": off_peak_hours
            },
            "recommendation": self._generate_tou_recommendation(
                peak_consumption / total if total > 0 else 0,
                off_peak_consumption / total if total > 0 else 0
            )
        }
    
    def _generate_tou_recommendation(self, peak_ratio: float, off_peak_ratio: float) -> str:
        """生成 TOU 優化建議"""
        if peak_ratio > 0.4:
            return "尖峰用電比例偏高，建議將非關鍵負載移至離峰時段"
        elif off_peak_ratio < 0.2:
            return "離峰用電比例偏低，可考慮安排批次作業或充電排程至離峰時段"
        else:
            return "用電時段分佈尚可，持續監控優化空間"
    
    # ==================== 效益評估工具 ====================
    
    def estimate_shift_benefit(self,
                               consumption_kwh: float,
                               from_period: str,
                               to_period: str,
                               is_summer: bool = True) -> Dict[str, Any]:
        """
        估算負載移轉效益
        
        Args:
            consumption_kwh: 移轉用電量 (kWh)
            from_period: 原時段 ('peak', 'half_peak', 'off_peak')
            to_period: 目標時段
            is_summer: 是否夏季
            
        Returns:
            效益估算結果
        """
        rates = {
            'peak': settings.summer_peak_rate if is_summer else settings.non_summer_peak_rate,
            'half_peak': settings.summer_half_peak_rate if is_summer else settings.non_summer_half_peak_rate,
            'off_peak': settings.summer_off_peak_rate if is_summer else settings.non_summer_off_peak_rate
        }
        
        from_rate = rates.get(from_period, rates['half_peak'])
        to_rate = rates.get(to_period, rates['off_peak'])
        
        original_cost = consumption_kwh * from_rate
        new_cost = consumption_kwh * to_rate
        savings = original_cost - new_cost
        
        return {
            "consumption_kwh": round(consumption_kwh, 2),
            "from_period": from_period,
            "to_period": to_period,
            "from_rate_ntd_kwh": round(from_rate, 2),
            "to_rate_ntd_kwh": round(to_rate, 2),
            "original_cost_ntd": round(original_cost, 2),
            "new_cost_ntd": round(new_cost, 2),
            "savings_ntd": round(savings, 2),
            "savings_percent": round(savings / original_cost * 100, 1) if original_cost > 0 else 0,
            "monthly_estimate_ntd": round(savings * 30, 0),
            "annual_estimate_ntd": round(savings * 365, 0)
        }
    
    def get_available_tools(self) -> List[Dict[str, str]]:
        """獲取所有可用工具的說明"""
        return [
            {
                "name": "calculate_electricity_cost",
                "description": "計算電費：輸入用電量(kWh)和電價費率(NTD/kWh)"
            },
            {
                "name": "calculate_period_cost",
                "description": "計算時段電費：輸入每小時用電量和電價序列"
            },
            {
                "name": "calculate_savings",
                "description": "計算節省金額：比較基準成本和優化後成本"
            },
            {
                "name": "calculate_carbon_emission",
                "description": "計算碳排放量：輸入用電量(kWh)"
            },
            {
                "name": "calculate_renewable_offset",
                "description": "計算再生能源抵減：輸入總用電量和再生能源使用量"
            },
            {
                "name": "calculate_statistics",
                "description": "計算統計指標：輸入數據列表"
            },
            {
                "name": "calculate_comparison",
                "description": "計算預測與實際比較指標：輸入預測值和實際值列表"
            },
            {
                "name": "detect_anomalies",
                "description": "偵測異常值：輸入數據列表和閾值"
            },
            {
                "name": "analyze_tou_distribution",
                "description": "分析時間電價分佈：輸入24小時數據"
            },
            {
                "name": "estimate_shift_benefit",
                "description": "估算負載移轉效益：輸入移轉電量、原時段、目標時段"
            }
        ]
