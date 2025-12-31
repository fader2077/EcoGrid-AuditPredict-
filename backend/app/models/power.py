"""
Database Models - SQLAlchemy ORM Classes
"""

from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.db.session import Base


class PowerLog(Base):
    """
    時序電力數據記錄
    記錄每小時的實際負載、太陽能、風力等數據
    """
    __tablename__ = "power_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True, unique=True)
    
    # Load Data (kW)
    load_kw = Column(Float, nullable=False)
    
    # Renewable Energy (kW)
    solar_kw = Column(Float, default=0.0)
    wind_kw = Column(Float, default=0.0)
    
    # Grid Import/Export (kW)
    grid_import_kw = Column(Float, default=0.0)
    grid_export_kw = Column(Float, default=0.0)
    
    # Battery (kW)
    battery_charge_kw = Column(Float, default=0.0)
    battery_discharge_kw = Column(Float, default=0.0)
    battery_soc = Column(Float, default=0.5)  # State of Charge (0-1)
    
    # TOU Period
    tou_period = Column(String(20))  # peak, half_peak, off_peak
    tariff_rate = Column(Float)  # NTD/kWh
    
    # Cost
    cost_ntd = Column(Float, default=0.0)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<PowerLog {self.timestamp} - Load: {self.load_kw:.1f} kW>"


class ForecastResult(Base):
    """
    AI 預測結果
    儲存 XGBoost/LightGBM/Transformer 的負載與綠能預測
    """
    __tablename__ = "forecast_results"
    
    id = Column(Integer, primary_key=True, index=True)
    forecast_timestamp = Column(DateTime, nullable=False, index=True)  # 預測時間點
    created_at = Column(DateTime, default=datetime.utcnow, index=True)  # 產生預測的時間
    
    # Predicted Values (kW)
    predicted_load_kw = Column(Float, nullable=False)
    predicted_solar_kw = Column(Float, default=0.0)
    predicted_wind_kw = Column(Float, default=0.0)
    predicted_net_load_kw = Column(Float)  # Load - Solar - Wind
    
    # Model Info
    model_type = Column(String(50))  # xgboost, lightgbm, ensemble
    confidence = Column(Float)  # 0-1
    
    # Actual Values (填入後可計算誤差)
    actual_load_kw = Column(Float, nullable=True)
    actual_solar_kw = Column(Float, nullable=True)
    actual_wind_kw = Column(Float, nullable=True)
    
    # Metrics
    mae = Column(Float, nullable=True)
    rmse = Column(Float, nullable=True)
    
    def __repr__(self):
        return f"<Forecast {self.forecast_timestamp} - Load: {self.predicted_load_kw:.1f} kW>"


class OptimizationPlan(Base):
    """
    MILP 優化排程建議
    儲存 PuLP 求解器產出的最佳充放電策略
    """
    __tablename__ = "optimization_plans"
    
    id = Column(Integer, primary_key=True, index=True)
    plan_date = Column(DateTime, nullable=False, index=True)  # 排程日期
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Optimization Status
    status = Column(String(20))  # Optimal, Infeasible, Unbounded
    
    # Cost Savings
    baseline_cost_ntd = Column(Float)
    optimized_cost_ntd = Column(Float)
    savings_ntd = Column(Float)
    savings_percent = Column(Float)
    
    # Peak Reduction
    baseline_peak_kw = Column(Float)
    optimized_peak_kw = Column(Float)
    peak_reduction_percent = Column(Float)
    
    # Schedule Data (JSON Array)
    # [{"hour": 0, "grid_kw": 100, "battery_kw": -20, "solar_kw": 0}, ...]
    schedule_json = Column(JSON)
    
    # Recommendations
    recommendations = Column(Text)  # Multi-line text
    
    # Reference to forecast
    forecast_id = Column(Integer, ForeignKey("forecast_results.id"), nullable=True)
    forecast = relationship("ForecastResult", backref="optimization_plans")
    
    def __repr__(self):
        return f"<OptimizationPlan {self.plan_date} - Savings: {self.savings_percent:.1f}%>"


class AuditReport(Base):
    """
    LLM 產出的用電審計報告
    由 Ollama LLM Agent 透過 Agentic RAG 生成
    """
    __tablename__ = "audit_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    report_date = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Report Type
    report_type = Column(String(50))  # daily, weekly, monthly, custom
    
    # Date Range
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    
    # LLM-Generated Content (Markdown)
    content_markdown = Column(Text, nullable=False)
    
    # Summary Stats (extracted by LLM)
    total_consumption_kwh = Column(Float)
    total_cost_ntd = Column(Float)
    renewable_ratio_percent = Column(Float)
    carbon_emission_kg = Column(Float)
    
    # LLM Model Info
    llm_model = Column(String(50))  # llama3.2, gpt-4, etc.
    
    # User Query (if interactive)
    user_query = Column(Text, nullable=True)
    
    # Status
    is_archived = Column(Boolean, default=False)
    
    def __repr__(self):
        return f"<AuditReport {self.report_date} - {self.report_type}>"


class TaskStatus(Base):
    """
    背景任務狀態追蹤
    用於 Celery 或 BackgroundTasks 的長時間運算
    """
    __tablename__ = "task_status"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(100), unique=True, index=True)  # UUID
    task_type = Column(String(50))  # train_model, optimize, generate_report
    
    # Status
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    progress = Column(Float, default=0.0)  # 0-100
    
    # Result
    result_json = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<TaskStatus {self.task_id} - {self.status}>"
