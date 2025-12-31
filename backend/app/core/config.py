"""
Core Configuration - FastAPI Application Settings
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application Settings"""
    
    # App Info
    APP_NAME: str = "EcoGrid Audit Predict API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    
    # CORS
    CORS_ORIGINS: list = ["http://localhost:5173", "http://localhost:3000"]
    
    # Database
    DATABASE_URL: str = "sqlite:///./ecogrid.db"
    
    # Security (Optional for future)
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Redis (for Celery - Optional)
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # AI Model Settings
    GPU_MEMORY_FRACTION: float = 0.6
    USE_CUDA: bool = True
    
    # Background Task Settings
    MAX_WORKERS: int = 2
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"  # 允許額外的環境變數


settings = Settings()
