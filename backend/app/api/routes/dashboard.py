"""
Dashboard API Routes
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Dict, Any

from app.db import get_db
from app.models import PowerLog
from app.schemas import DashboardSummary, ChartDataRequest, ChartDataResponse
from loguru import logger

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(db: Session = Depends(get_db)):
    """
    獲取 Dashboard 即時摘要
    
    Returns:
        DashboardSummary: 即時負載、成本、綠電比例等
    """
    try:
        # 獲取最新記錄
        latest_log = db.query(PowerLog).order_by(PowerLog.timestamp.desc()).first()
        
        if not latest_log:
            # 返回預設值（首次運行）
            return DashboardSummary(
                current_load_kw=0.0,
                current_solar_kw=0.0,
                current_wind_kw=0.0,
                renewable_ratio=0.0,
                battery_soc=0.5,
                estimated_cost_today=0.0,
                total_consumption_today=0.0,
                tou_period="off_peak",
                current_tariff=2.38
            )
        
        # 計算綠電比例
        total_renewable = latest_log.solar_kw + latest_log.wind_kw
        renewable_ratio = (total_renewable / latest_log.load_kw * 100) if latest_log.load_kw > 0 else 0.0
        
        # 計算今日總用電與成本
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_logs = db.query(PowerLog).filter(PowerLog.timestamp >= today_start).all()
        
        total_consumption_today = sum(log.load_kw for log in today_logs) if today_logs else 0.0
        estimated_cost_today = sum(log.cost_ntd for log in today_logs) if today_logs else 0.0
        
        return DashboardSummary(
            current_load_kw=latest_log.load_kw,
            current_solar_kw=latest_log.solar_kw,
            current_wind_kw=latest_log.wind_kw,
            renewable_ratio=renewable_ratio,
            battery_soc=latest_log.battery_soc,
            estimated_cost_today=estimated_cost_today,
            total_consumption_today=total_consumption_today,
            tou_period=latest_log.tou_period or "off_peak",
            current_tariff=latest_log.tariff_rate or 2.38,
            last_updated=latest_log.timestamp
        )
    
    except Exception as e:
        logger.error(f"Failed to get dashboard summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chart-data", response_model=ChartDataResponse)
async def get_chart_data(
    request: ChartDataRequest,
    db: Session = Depends(get_db)
):
    """
    獲取圖表數據（for ECharts）
    
    Args:
        request: 圖表數據請求（可使用 start_date+end_date 或 hours）
        
    Returns:
        ChartDataResponse: 時間序列數據
    """
    try:
        # 如果未提供日期範圍，使用 hours 參數計算
        if request.start_date is None or request.end_date is None:
            end_date = datetime.now()
            start_date = end_date - timedelta(hours=request.hours or 24)
        else:
            start_date = request.start_date
            end_date = request.end_date
        
        # 查詢數據
        logs = db.query(PowerLog).filter(
            PowerLog.timestamp >= start_date,
            PowerLog.timestamp <= end_date
        ).order_by(PowerLog.timestamp).all()
        
        if not logs:
            return ChartDataResponse(
                timestamps=[],
                series={}
            )
        
        # 格式化數據
        timestamps = [log.timestamp.strftime("%Y-%m-%d %H:%M") for log in logs]
        
        series = {
            "load": [log.load_kw for log in logs],
            "solar": [log.solar_kw for log in logs],
            "wind": [log.wind_kw for log in logs],
            "grid": [log.grid_import_kw for log in logs],
            "tariff": [log.tariff_rate for log in logs],
            "battery_soc": [log.battery_soc * 100 for log in logs]  # 轉為百分比
        }
        
        return ChartDataResponse(
            timestamps=timestamps,
            series=series
        )
    
    except Exception as e:
        logger.error(f"Failed to get chart data: {e}")
        raise HTTPException(status_code=500, detail=str(e))
