"""
Audit Report API Routes
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Dict, Any
import uuid

from app.db import get_db
from app.models import AuditReport, PowerLog, TaskStatus
from app.schemas import AuditReportRequest, AuditReportResponse
from app.services import llm_service
from loguru import logger

router = APIRouter()


async def run_report_generation_task(
    task_id: str,
    report_type: str,
    start_date: datetime,
    end_date: datetime,
    user_query: str,
    db_url: str
):
    """背景任務：生成審計報告"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
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
        
        logger.info(f"Task {task_id}: Generating audit report...")
        
        # 查詢電力數據
        logs = db.query(PowerLog).filter(
            PowerLog.timestamp >= start_date,
            PowerLog.timestamp <= end_date
        ).all()
        
        # 計算摘要統計
        total_consumption = sum(log.load_kw for log in logs) if logs else 0.0
        total_cost = sum(log.cost_ntd for log in logs) if logs else 0.0
        total_solar = sum(log.solar_kw for log in logs) if logs else 0.0
        total_wind = sum(log.wind_kw for log in logs) if logs else 0.0
        total_renewable = total_solar + total_wind
        renewable_ratio = (total_renewable / total_consumption * 100) if total_consumption > 0 else 0.0
        carbon_emission = total_consumption * 0.494  # kg CO2 per kWh
        
        avg_load = total_consumption / len(logs) if logs else 0.0
        peak_load = max((log.load_kw for log in logs), default=0.0)
        
        power_data = {
            "total_consumption_kwh": total_consumption,
            "total_cost_ntd": total_cost,
            "renewable_ratio": renewable_ratio,
            "carbon_emission_kg": carbon_emission,
            "avg_load_kw": avg_load,
            "peak_load_kw": peak_load,
            "solar_ratio": (total_solar / total_consumption * 100) if total_consumption > 0 else 0.0,
            "wind_ratio": (total_wind / total_consumption * 100) if total_consumption > 0 else 0.0,
            "offpeak_load_kw": 0.0  # 需額外計算
        }
        
        if task:
            task.progress = 40.0
            db.commit()
        
        # 使用 LLM 生成報告
        content_markdown = llm_service.generate_report(
            report_type,
            start_date,
            end_date,
            power_data
        )
        
        if task:
            task.progress = 80.0
            db.commit()
        
        # 儲存報告
        report = AuditReport(
            report_date=datetime.now(),
            report_type=report_type,
            start_date=start_date,
            end_date=end_date,
            content_markdown=content_markdown,
            total_consumption_kwh=total_consumption,
            total_cost_ntd=total_cost,
            renewable_ratio_percent=renewable_ratio,
            carbon_emission_kg=carbon_emission,
            llm_model="llama3.2",
            user_query=user_query
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        
        # 更新任務狀態
        if task:
            task.status = "completed"
            task.progress = 100.0
            task.completed_at = datetime.utcnow()
            task.result_json = {
                "report_id": report.id,
                "report_type": report_type
            }
            db.commit()
        
        logger.info(f"Task {task_id}: Report generated - Report ID: {report.id}")
    
    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}")
        if task:
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()
            db.commit()
    
    finally:
        db.close()


@router.post("/generate", response_model=Dict[str, Any])
async def generate_audit_report(
    request: AuditReportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    生成審計報告（異步）
    
    LLM 生成耗時，使用 BackgroundTasks
    
    Args:
        request: 審計報告請求
        
    Returns:
        任務 ID
    """
    try:
        # 設定日期範圍
        if request.start_date is None or request.end_date is None:
            if request.report_type == "daily":
                request.end_date = datetime.now()
                request.start_date = request.end_date - timedelta(days=1)
            elif request.report_type == "weekly":
                request.end_date = datetime.now()
                request.start_date = request.end_date - timedelta(days=7)
            elif request.report_type == "monthly":
                request.end_date = datetime.now()
                request.start_date = request.end_date - timedelta(days=30)
        
        # 創建任務記錄
        task_id = str(uuid.uuid4())
        task = TaskStatus(
            task_id=task_id,
            task_type="generate_report",
            status="pending",
            progress=0.0
        )
        db.add(task)
        db.commit()
        
        # 加入背景任務
        from app.core.config import settings
        background_tasks.add_task(
            run_report_generation_task,
            task_id,
            request.report_type,
            request.start_date,
            request.end_date,
            request.user_query,
            settings.DATABASE_URL
        )
        
        logger.info(f"Report generation task created: {task_id}")
        
        return {
            "task_id": task_id,
            "status": "pending",
            "message": f"Report generation started for {request.report_type}"
        }
    
    except Exception as e:
        logger.error(f"Failed to create report generation task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report/{report_id}", response_model=AuditReportResponse)
async def get_audit_report(report_id: int, db: Session = Depends(get_db)):
    """
    獲取審計報告
    
    Args:
        report_id: 報告 ID
        
    Returns:
        AuditReportResponse: 審計報告內容
    """
    report = db.query(AuditReport).filter(AuditReport.id == report_id).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return AuditReportResponse(
        report_id=report.id,
        report_type=report.report_type,
        content_markdown=report.content_markdown,
        summary={
            "total_consumption_kwh": report.total_consumption_kwh,
            "total_cost_ntd": report.total_cost_ntd,
            "renewable_ratio": report.renewable_ratio_percent,
            "carbon_emission_kg": report.carbon_emission_kg
        },
        created_at=report.created_at
    )


@router.get("/latest", response_model=AuditReportResponse)
async def get_latest_report(db: Session = Depends(get_db)):
    """獲取最新審計報告"""
    report = db.query(AuditReport).order_by(AuditReport.created_at.desc()).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="No report available")
    
    return await get_audit_report(report.id, db)


@router.post("/query")
async def interactive_query(
    query: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    互動式查詢（Chat Assistant）
    
    Args:
        query: {"query": "..."} 或 {"question": "...", "context": {...}}
        
    Returns:
        LLM 回答
    """
    try:
        # 支持兩種格式
        user_question = query.get("query") or query.get("question", "")
        user_context = query.get("context", {})
        
        if not user_question:
            raise HTTPException(status_code=400, detail="Question/query is required")
        
        # 獲取上下文（最近的電力數據）
        recent_logs = db.query(PowerLog).order_by(
            PowerLog.timestamp.desc()
        ).limit(24).all()
        
        context = {
            "recent_data": [
                {
                    "timestamp": log.timestamp.isoformat(),
                    "load_kw": log.load_kw,
                    "solar_kw": log.solar_kw,
                    "wind_kw": log.wind_kw,
                    "tou_period": log.tou_period,
                    "tariff": log.tariff_rate
                }
                for log in recent_logs
            ],
            "current_status": user_context  # 使用前端提供的即時狀態
        }
        
        # 使用 LLM 回答
        answer = llm_service.query(user_question, context)
        
        # 確保中文編碼正確
        if isinstance(answer, bytes):
            answer = answer.decode('utf-8', errors='ignore')
        
        from fastapi.responses import JSONResponse
        return JSONResponse(
            content={
                "question": user_question,
                "answer": answer,
                "response": answer,  # 兼容兩種欄位名稱
                "timestamp": datetime.now().isoformat()
            },
            media_type="application/json; charset=utf-8"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
