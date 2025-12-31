"""
Forecast API Routes
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Dict, Any
import uuid

from app.db import get_db
from app.models import ForecastResult, TaskStatus
from app.schemas import ForecastRequest, ForecastResponse, ForecastDataPoint, TaskStatusResponse
from app.services import ai_service
from loguru import logger

router = APIRouter()


async def run_prediction_task(
    task_id: str,
    hours_ahead: int,
    use_transformer: bool,
    use_lstm: bool,
    db_url: str
):
    """背景任務：執行預測"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    # 創建新的 DB session（背景任務需要獨立連接）
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # 更新狀態為 running
        task = db.query(TaskStatus).filter(TaskStatus.task_id == task_id).first()
        if task:
            task.status = "running"
            task.started_at = datetime.utcnow()
            task.progress = 10.0
            db.commit()
        
        # 執行預測
        logger.info(f"Task {task_id}: Starting prediction...")
        predictions = ai_service.predict(hours_ahead, use_transformer, use_lstm)
        
        if task:
            task.progress = 50.0
            db.commit()
        
        # 儲存預測結果到資料庫
        for _, row in predictions.iterrows():
            forecast = ForecastResult(
                forecast_timestamp=row['timestamp'],
                predicted_load_kw=row['predicted_load_mw'] * 1000,  # MW to kW
                predicted_solar_kw=row['predicted_solar_mw'] * 1000,
                predicted_wind_kw=row['predicted_wind_mw'] * 1000,
                predicted_net_load_kw=row['predicted_net_load_mw'] * 1000,
                model_type="ensemble",
                confidence=0.85
            )
            db.add(forecast)
        
        db.commit()
        
        # 更新狀態為 completed
        if task:
            task.status = "completed"
            task.progress = 100.0
            task.completed_at = datetime.utcnow()
            task.result_json = {
                "forecast_count": len(predictions),
                "avg_load_kw": float(predictions['predicted_load_mw'].mean() * 1000)
            }
            db.commit()
        
        logger.info(f"Task {task_id}: Prediction completed")
    
    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}")
        if task:
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()
            db.commit()
    
    finally:
        db.close()


@router.post("/predict", response_model=Dict[str, Any])
async def create_forecast(
    request: ForecastRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    創建預測任務（異步）
    
    由於 AI 預測耗時，使用 BackgroundTasks 避免 API Timeout
    
    Args:
        request: 預測請求
        
    Returns:
        任務 ID，可用於查詢狀態
    """
    try:
        # 創建任務記錄
        task_id = str(uuid.uuid4())
        task = TaskStatus(
            task_id=task_id,
            task_type="forecast",
            status="pending",
            progress=0.0
        )
        db.add(task)
        db.commit()
        
        # 加入背景任務
        from app.core.config import settings
        background_tasks.add_task(
            run_prediction_task,
            task_id,
            request.hours_ahead,
            request.use_transformer,
            request.use_lstm,
            settings.DATABASE_URL
        )
        
        logger.info(f"Forecast task created: {task_id}")
        
        return {
            "task_id": task_id,
            "status": "pending",
            "message": f"Prediction task started for {request.hours_ahead} hours ahead"
        }
    
    except Exception as e:
        logger.error(f"Failed to create forecast task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train", response_model=Dict[str, Any])
async def train_models(
    use_transformer: bool = False,
    use_lstm: bool = False,
    n_estimators: int = 50,
    db: Session = Depends(get_db)
):
    """
    訓練 AI 預測模型
    
    Args:
        use_transformer: 是否使用 Transformer
        use_lstm: 是否使用 LSTM
        n_estimators: 樹模型數量
        
    Returns:
        訓練結果
    """
    try:
        logger.info(f"Starting model training: Transformer={use_transformer}, LSTM={use_lstm}")
        
        # 訓練模型
        result = ai_service.train_models(
            use_transformer=use_transformer,
            use_lstm=use_lstm,
            n_estimators=n_estimators
        )
        
        logger.info("Model training completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Model training failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/predict/{task_id}", response_model=TaskStatusResponse)
async def get_forecast_status(task_id: str, db: Session = Depends(get_db)):
    """
    查詢預測任務狀態
    
    Args:
        task_id: 任務 ID
        
    Returns:
        TaskStatusResponse: 任務狀態
    """
    task = db.query(TaskStatus).filter(TaskStatus.task_id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
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


@router.get("/latest", response_model=ForecastResponse)
async def get_latest_forecast(db: Session = Depends(get_db)):
    """
    獲取最新預測結果
    
    Returns:
        ForecastResponse: 最新的預測數據
    """
    try:
        # 獲取最新一批預測（同一個 created_at）
        latest_forecast = db.query(ForecastResult).order_by(
            ForecastResult.created_at.desc()
        ).first()
        
        if not latest_forecast:
            raise HTTPException(status_code=404, detail="No forecast available")
        
        # 獲取該批次所有預測點
        forecasts = db.query(ForecastResult).filter(
            ForecastResult.created_at == latest_forecast.created_at
        ).order_by(ForecastResult.forecast_timestamp).all()
        
        # 格式化數據
        forecast_data = [
            ForecastDataPoint(
                timestamp=f.forecast_timestamp,
                predicted_load_kw=f.predicted_load_kw,
                predicted_solar_kw=f.predicted_solar_kw,
                predicted_wind_kw=f.predicted_wind_kw,
                predicted_net_load_kw=f.predicted_net_load_kw,
                tariff=5.63,  # 可從其他來源獲取
                tou_period="half_peak"
            )
            for f in forecasts
        ]
        
        # 計算摘要
        avg_load = sum(f.predicted_load_kw for f in forecasts) / len(forecasts)
        peak_load = max(f.predicted_load_kw for f in forecasts)
        total_renewable = sum(f.predicted_solar_kw + f.predicted_wind_kw for f in forecasts)
        total_load = sum(f.predicted_load_kw for f in forecasts)
        renewable_ratio = (total_renewable / total_load * 100) if total_load > 0 else 0.0
        
        return ForecastResponse(
            forecast_data=forecast_data,
            model_info={
                "model_type": "ensemble",
                "xgboost_r2": 0.82,
                "lightgbm_r2": 0.77
            },
            summary={
                "avg_load_kw": avg_load,
                "peak_load_kw": peak_load,
                "renewable_ratio": renewable_ratio,
                "forecast_hours": len(forecasts)
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get latest forecast: {e}")
        raise HTTPException(status_code=500, detail=str(e))
