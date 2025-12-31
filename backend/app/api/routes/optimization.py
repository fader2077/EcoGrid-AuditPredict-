"""
Optimization API Routes
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Dict, Any
import uuid
import json

from app.db import get_db
from app.models import ForecastResult, OptimizationPlan, TaskStatus
from app.schemas import (
    OptimizationRequest, 
    OptimizationResponse, 
    OptimizationSchedulePoint,
    TaskStatusResponse
)
from app.services import optimization_service, ai_service
from loguru import logger

router = APIRouter()


async def run_optimization_task(
    task_id: str,
    forecast_id: int,
    hours_ahead: int,
    initial_soc: float,
    battery_capacity_kwh: float,
    max_contract_kw: float,
    db_url: str
):
    """背景任務：執行優化"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import pandas as pd
    
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # 更新狀態
        task = db.query(TaskStatus).filter(TaskStatus.task_id == task_id).first()
        if task:
            task.status = "running"
            task.started_at = datetime.utcnow()
            task.progress = 10.0
            db.commit()
        
        logger.info(f"Task {task_id}: Starting optimization...")
        
        # 獲取預測數據
        if forecast_id:
            forecasts = db.query(ForecastResult).filter(
                ForecastResult.id >= forecast_id
            ).order_by(ForecastResult.forecast_timestamp).limit(hours_ahead).all()
            
            if not forecasts:
                raise ValueError("Forecast not found")
            
            # 轉換為 DataFrame
            forecast_df = pd.DataFrame([
                {
                    'timestamp': f.forecast_timestamp,
                    'predicted_load_mw': f.predicted_load_kw / 1000,
                    'predicted_solar_mw': f.predicted_solar_kw / 1000,
                    'predicted_wind_mw': f.predicted_wind_kw / 1000,
                    'tariff': 5.63  # 暫時使用固定值
                }
                for f in forecasts
            ])
        else:
            # 執行新預測
            predictions = ai_service.predict(hours_ahead, use_transformer=False, use_lstm=False)
            forecast_df = predictions
        
        if task:
            task.progress = 30.0
            db.commit()
        
        # 執行優化
        opt_result = optimization_service.optimize(
            forecast_df,
            initial_soc=initial_soc,
            battery_capacity_kwh=battery_capacity_kwh,
            max_contract_kw=max_contract_kw
        )
        
        if task:
            task.progress = 70.0
            db.commit()
        
        # 儲存優化計劃
        result = opt_result['result']
        schedule_df = opt_result['schedule']
        
        # 轉換 schedule 為 JSON
        schedule_json = []
        for i, row in schedule_df.iterrows():
            schedule_json.append({
                'hour': i,
                'timestamp': row['timestamp'].isoformat() if hasattr(row['timestamp'], 'isoformat') else str(row['timestamp']),
                'grid_kw': float(row.get('optimized_grid_kw', 0)),
                'battery_kw': float(row.get('battery_schedule_kw', 0)),
                'solar_kw': float(row.get('solar_used_kw', 0)),
                'load_kw': float(row.get('predicted_load_mw', 0)) * 1000 if 'predicted_load_mw' in row else 0,
                'tariff': float(row.get('tariff', 5.0)),
                'cost_ntd': float(row.get('optimized_cost', 0))
            })
        
        plan = OptimizationPlan(
            plan_date=datetime.now(),
            status=result.status,
            baseline_cost_ntd=result.baseline_cost,
            optimized_cost_ntd=result.total_cost,
            savings_ntd=result.savings,
            savings_percent=result.savings_percent,
            baseline_peak_kw=0.0,  # 需計算
            optimized_peak_kw=0.0,
            peak_reduction_percent=result.peak_reduction,
            schedule_json=schedule_json,
            recommendations="\n".join(result.recommendations)
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)
        
        # 更新任務狀態
        if task:
            task.status = "completed"
            task.progress = 100.0
            task.completed_at = datetime.utcnow()
            task.result_json = {
                "plan_id": plan.id,
                "status": result.status,
                "savings_percent": result.savings_percent
            }
            db.commit()
        
        logger.info(f"Task {task_id}: Optimization completed - Plan ID: {plan.id}")
    
    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}")
        if task:
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()
            db.commit()
    
    finally:
        db.close()


@router.post("/optimize", response_model=Dict[str, Any])
async def create_optimization(
    request: OptimizationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    創建優化任務（異步）
    
    MILP 求解耗時，使用 BackgroundTasks
    
    Args:
        request: 優化請求
        
    Returns:
        任務 ID
    """
    try:
        # 創建任務記錄
        task_id = str(uuid.uuid4())
        task = TaskStatus(
            task_id=task_id,
            task_type="optimize",
            status="pending",
            progress=0.0
        )
        db.add(task)
        db.commit()
        
        # 加入背景任務
        from app.core.config import settings
        background_tasks.add_task(
            run_optimization_task,
            task_id,
            request.forecast_id,
            request.hours_ahead,
            request.initial_soc,
            request.battery_capacity_kwh,
            request.max_contract_kw,
            settings.DATABASE_URL
        )
        
        logger.info(f"Optimization task created: {task_id}")
        
        return {
            "task_id": task_id,
            "status": "pending",
            "message": "Optimization task started"
        }
    
    except Exception as e:
        logger.error(f"Failed to create optimization task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/optimize/{task_id}", response_model=TaskStatusResponse)
async def get_optimization_status(task_id: str, db: Session = Depends(get_db)):
    """查詢優化任務狀態"""
    task = db.query(TaskStatus).filter(TaskStatus.task_id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    from app.schemas import TaskStatusResponse
    return TaskStatusResponse(
        task_id=task.task_id,
        task_type=task.task_type,
        status=task.status,
        progress=task.progress,
        result=task.result_json,
        error_message=task.error_message,
        created_at=task.created_at,
        completed_at=task.completed_at
    )


@router.get("/plan/{plan_id}", response_model=OptimizationResponse)
async def get_optimization_plan(plan_id: int, db: Session = Depends(get_db)):
    """
    獲取優化計劃詳情
    
    Args:
        plan_id: 計劃 ID
        
    Returns:
        OptimizationResponse: 優化結果與排程
    """
    plan = db.query(OptimizationPlan).filter(OptimizationPlan.id == plan_id).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    # 格式化 schedule
    schedule = [
        OptimizationSchedulePoint(
            hour=item['hour'],
            timestamp=datetime.fromisoformat(item['timestamp']),
            grid_buy_kw=item['grid_kw'],
            battery_kw=item['battery_kw'],
            solar_used_kw=item['solar_kw'],
            wind_used_kw=0.0,
            load_kw=item['load_kw'],
            tariff=item['tariff'],
            cost_ntd=item['cost_ntd']
        )
        for item in plan.schedule_json
    ]
    
    return OptimizationResponse(
        plan_id=plan.id,
        status=plan.status,
        baseline_cost_ntd=plan.baseline_cost_ntd,
        optimized_cost_ntd=plan.optimized_cost_ntd,
        savings_ntd=plan.savings_ntd,
        savings_percent=plan.savings_percent,
        peak_reduction_percent=plan.peak_reduction_percent,
        schedule=schedule,
        recommendations=plan.recommendations.split("\n") if plan.recommendations else []
    )


@router.get("/latest", response_model=OptimizationResponse)
async def get_latest_optimization(db: Session = Depends(get_db)):
    """獲取最新優化計劃"""
    plan = db.query(OptimizationPlan).order_by(OptimizationPlan.created_at.desc()).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="No optimization plan available")
    
    return await get_optimization_plan(plan.id, db)
