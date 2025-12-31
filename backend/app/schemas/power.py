"""
Pydantic Schemas - Request/Response Models
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ============ Dashboard Schemas ============

class DashboardSummary(BaseModel):
    """Dashboard 即時摘要"""
    current_load_kw: float = Field(..., description="當前負載 (kW)")
    current_solar_kw: float = Field(0.0, description="當前太陽能 (kW)")
    current_wind_kw: float = Field(0.0, description="當前風力 (kW)")
    renewable_ratio: float = Field(0.0, description="綠電比例 (%)")
    battery_soc: float = Field(0.5, description="電池狀態 (0-1)")
    
    estimated_cost_today: float = Field(0.0, description="今日預估成本 (NTD)")
    total_consumption_today: float = Field(0.0, description="今日總用電 (kWh)")
    
    tou_period: str = Field("off_peak", description="當前電價時段")
    current_tariff: float = Field(0.0, description="當前電價 (NTD/kWh)")
    
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "current_load_kw": 350.5,
                "current_solar_kw": 120.0,
                "renewable_ratio": 34.3,
                "battery_soc": 0.75,
                "estimated_cost_today": 12500.0,
                "tou_period": "peak",
                "current_tariff": 7.05
            }
        }


# ============ Forecast Schemas ============

class ForecastRequest(BaseModel):
    """預測請求"""
    hours_ahead: int = Field(24, ge=1, le=168, description="預測時長（小時）")
    use_transformer: bool = Field(False, description="是否使用 Transformer 模型")
    use_lstm: bool = Field(False, description="是否使用 LSTM 模型")


class ForecastDataPoint(BaseModel):
    """單一預測數據點"""
    timestamp: datetime
    predicted_load_kw: float
    predicted_solar_kw: float
    predicted_wind_kw: float
    predicted_net_load_kw: float
    tariff: float
    tou_period: str


class ForecastResponse(BaseModel):
    """預測回應"""
    forecast_data: List[ForecastDataPoint]
    model_info: Dict[str, Any]
    summary: Dict[str, Any]
    
    class Config:
        json_schema_extra = {
            "example": {
                "forecast_data": [
                    {
                        "timestamp": "2025-12-20T17:00:00",
                        "predicted_load_kw": 380.5,
                        "predicted_solar_kw": 50.0,
                        "predicted_wind_kw": 10.0,
                        "predicted_net_load_kw": 320.5,
                        "tariff": 5.63,
                        "tou_period": "half_peak"
                    }
                ],
                "model_info": {
                    "xgboost_r2": 0.82,
                    "lightgbm_r2": 0.77
                },
                "summary": {
                    "avg_load_kw": 350.0,
                    "peak_load_kw": 420.0,
                    "renewable_ratio": 15.5
                }
            }
        }


# ============ Optimization Schemas ============

class OptimizationRequest(BaseModel):
    """優化請求"""
    forecast_id: Optional[int] = Field(None, description="使用既有預測結果 ID")
    hours_ahead: int = Field(24, ge=1, le=168)
    initial_soc: float = Field(0.5, ge=0.0, le=1.0, description="電池初始狀態")
    battery_capacity_kwh: Optional[float] = Field(None, description="覆蓋電池容量")
    max_contract_kw: Optional[float] = Field(None, description="覆蓋合約容量")


class OptimizationSchedulePoint(BaseModel):
    """優化排程點"""
    hour: int
    timestamp: datetime
    grid_buy_kw: float
    battery_kw: float  # 正值充電，負值放電
    solar_used_kw: float
    wind_used_kw: float
    load_kw: float
    tariff: float
    cost_ntd: float


class OptimizationResponse(BaseModel):
    """優化回應"""
    plan_id: int
    status: str
    baseline_cost_ntd: float
    optimized_cost_ntd: float
    savings_ntd: float
    savings_percent: float
    peak_reduction_percent: float
    schedule: List[OptimizationSchedulePoint]
    recommendations: List[str]
    
    class Config:
        json_schema_extra = {
            "example": {
                "plan_id": 1,
                "status": "Optimal",
                "baseline_cost_ntd": 48132.0,
                "optimized_cost_ntd": 42591.0,
                "savings_ntd": 5540.0,
                "savings_percent": 11.5,
                "peak_reduction_percent": 7.5,
                "recommendations": [
                    "電池在尖峰時段提供 165.0 kWh 電力",
                    "太陽能利用率達 100.0%"
                ]
            }
        }


# ============ Audit Report Schemas ============

class AuditReportRequest(BaseModel):
    """審計報告請求"""
    report_type: str = Field("daily", description="報告類型: daily, weekly, monthly")
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    user_query: Optional[str] = Field(None, description="自訂問題（互動模式）")


class AuditReportResponse(BaseModel):
    """審計報告回應"""
    report_id: int
    report_type: str
    content_markdown: str
    summary: Dict[str, Any]
    created_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "report_id": 1,
                "report_type": "daily",
                "content_markdown": "# 每日用電審計報告\n\n...",
                "summary": {
                    "total_consumption_kwh": 8500.0,
                    "total_cost_ntd": 48000.0,
                    "renewable_ratio": 12.5,
                    "carbon_emission_kg": 4199.0
                },
                "created_at": "2025-12-20T16:00:00"
            }
        }


# ============ Task Status Schemas ============

class TaskStatusResponse(BaseModel):
    """任務狀態回應"""
    task_id: str
    task_type: str
    status: str  # pending, running, completed, failed
    progress: float  # 0-100
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


# ============ Chart Data Schemas ============

class ChartDataRequest(BaseModel):
    """圖表數據請求"""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    hours: Optional[int] = Field(24, description="最近 N 小時（如果未提供日期範圍）")
    data_type: str = Field("load", description="load, forecast, optimization")


class ChartDataResponse(BaseModel):
    """圖表數據回應（for ECharts）"""
    timestamps: List[str]
    series: Dict[str, List[float]]
    
    class Config:
        json_schema_extra = {
            "example": {
                "timestamps": ["2025-12-20 00:00", "2025-12-20 01:00"],
                "series": {
                    "actual_load": [350.5, 340.2],
                    "predicted_load": [355.0, 345.0],
                    "solar": [0.0, 0.0],
                    "tariff": [2.38, 2.38]
                }
            }
        }
