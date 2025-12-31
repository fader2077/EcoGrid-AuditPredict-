"""
Configuration settings for EcoGrid Audit Predict system.
使用 Pydantic Settings 管理配置，支援環境變數覆寫。
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """系統配置設定"""
    
    # Project Paths
    project_root: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent.parent.parent.parent
    )
    
    @property
    def data_raw_path(self) -> Path:
        path = self.project_root / "data" / "raw"
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def data_processed_path(self) -> Path:
        path = self.project_root / "data" / "processed"
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def data_cache_path(self) -> Path:
        path = self.project_root / "data" / "cache"
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def model_path(self) -> Path:
        path = self.project_root / "models"
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def logs_path(self) -> Path:
        path = self.project_root / "logs"
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    # Ollama LLM Configuration (Local)
    ollama_base_url: str = Field(default="http://localhost:11434", env="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.2", env="OLLAMA_MODEL")
    
    # Taiwan Central Weather Administration API
    cwa_api_key: str = Field(default="", env="CWA_API_KEY")
    cwa_base_url: str = Field(
        default="https://opendata.cwa.gov.tw/api/v1/rest/datastore",
        env="CWA_BASE_URL"
    )
    
    # System Configuration
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    cache_enabled: bool = Field(default=True, env="CACHE_ENABLED")
    cache_ttl_hours: int = Field(default=24, env="CACHE_TTL_HOURS")
    
    # GPU Configuration (prevent CUDA OOM)
    gpu_memory_fraction: float = Field(default=0.6, env="GPU_MEMORY_FRACTION")
    batch_size: int = Field(default=32, env="BATCH_SIZE")
    max_sequence_length: int = Field(default=168, env="MAX_SEQUENCE_LENGTH")  # 7 days * 24 hours
    
    # Taiwan Power Configuration
    taipower_retry_attempts: int = Field(default=3, env="TAIPOWER_RETRY_ATTEMPTS")
    taipower_retry_delay: int = Field(default=5, env="TAIPOWER_RETRY_DELAY")
    
    # Optimization Settings
    optimization_time_horizon: int = Field(default=24, env="OPTIMIZATION_TIME_HORIZON")
    battery_capacity_kwh: float = Field(default=100.0, env="BATTERY_CAPACITY_KWH")
    max_contract_capacity_kw: float = Field(default=500.0, env="MAX_CONTRACT_CAPACITY_KW")
    battery_efficiency: float = Field(default=0.9, env="BATTERY_EFFICIENCY")
    min_soc: float = Field(default=0.1, env="MIN_SOC")  # 最小電池狀態 10%
    max_soc: float = Field(default=0.9, env="MAX_SOC")  # 最大電池狀態 90%
    
    # Taiwan TOU Tariff Configuration (台電時間電價 - 2024)
    # 夏季 (6-9月)
    summer_peak_rate: float = Field(default=9.34, env="SUMMER_PEAK_RATE")  # 尖峰
    summer_half_peak_rate: float = Field(default=5.80, env="SUMMER_HALF_PEAK_RATE")  # 半尖峰
    summer_off_peak_rate: float = Field(default=2.29, env="SUMMER_OFF_PEAK_RATE")  # 離峰
    
    # 非夏季 (10-5月)
    non_summer_peak_rate: float = Field(default=9.10, env="NON_SUMMER_PEAK_RATE")
    non_summer_half_peak_rate: float = Field(default=5.54, env="NON_SUMMER_HALF_PEAK_RATE")
    non_summer_off_peak_rate: float = Field(default=2.18, env="NON_SUMMER_OFF_PEAK_RATE")
    
    # Carbon Emission Factor (電力排碳係數 kg CO2/kWh)
    carbon_emission_factor: float = Field(default=0.494, env="CARBON_EMISSION_FACTOR")
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }


# Taiwan TOU Period Definitions (台電時間電價時段定義)
TOU_PERIODS = {
    "summer": {  # 6-9月
        "peak": [(10, 12), (13, 17)],  # 尖峰: 10-12, 13-17
        "half_peak": [(7, 10), (12, 13), (17, 23)],  # 半尖峰
        "off_peak": [(0, 7), (23, 24)]  # 離峰
    },
    "non_summer": {  # 10-5月
        "peak": [(10, 12), (13, 17)],
        "half_peak": [(7, 10), (12, 13), (17, 23)],
        "off_peak": [(0, 7), (23, 24)]
    }
}

# Taiwan Holidays (台灣國定假日 - 用於負載預測)
TAIWAN_HOLIDAYS = [
    "01-01",  # 元旦
    "02-28",  # 和平紀念日
    "04-04",  # 兒童節
    "04-05",  # 清明節
    "05-01",  # 勞動節
    "10-10",  # 國慶日
    # 農曆節日需動態計算
]

# Global settings instance
settings = Settings()
