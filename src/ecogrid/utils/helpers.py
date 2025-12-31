"""
Helper utilities for EcoGrid system
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

import torch
from loguru import logger

from ecogrid.config.settings import settings


def setup_logging(log_level: Optional[str] = None, log_file: bool = True):
    """
    設定日誌系統
    
    Args:
        log_level: 日誌等級 (DEBUG, INFO, WARNING, ERROR)
        log_file: 是否輸出到檔案
    """
    level = log_level or settings.log_level
    
    # 移除預設 handler
    logger.remove()
    
    # 加入 console handler
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>",
        colorize=True
    )
    
    # 加入 file handler
    if log_file:
        log_path = settings.logs_path / f"ecogrid_{datetime.now().strftime('%Y%m%d')}.log"
        logger.add(
            log_path,
            level=level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            rotation="100 MB",
            retention="30 days",
            compression="zip"
        )
    
    logger.info(f"Logging initialized at level {level}")


def get_device_info() -> dict:
    """
    獲取計算設備資訊
    
    Returns:
        設備資訊字典
    """
    info = {
        "cuda_available": torch.cuda.is_available(),
        "device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
        "current_device": None,
        "device_name": None,
        "memory_allocated": None,
        "memory_reserved": None,
        "memory_total": None
    }
    
    if torch.cuda.is_available():
        info["current_device"] = torch.cuda.current_device()
        info["device_name"] = torch.cuda.get_device_name(0)
        info["memory_allocated"] = f"{torch.cuda.memory_allocated(0) / 1024**3:.2f} GB"
        info["memory_reserved"] = f"{torch.cuda.memory_reserved(0) / 1024**3:.2f} GB"
        
        total_memory = torch.cuda.get_device_properties(0).total_memory
        info["memory_total"] = f"{total_memory / 1024**3:.2f} GB"
    
    return info


def format_currency(amount: float, currency: str = "NTD") -> str:
    """
    格式化貨幣金額
    
    Args:
        amount: 金額
        currency: 貨幣單位
        
    Returns:
        格式化字串
    """
    if amount >= 1_000_000:
        return f"{currency} {amount/1_000_000:.2f}M"
    elif amount >= 1_000:
        return f"{currency} {amount/1_000:.2f}K"
    else:
        return f"{currency} {amount:.2f}"


def format_percentage(value: float, decimals: int = 1) -> str:
    """
    格式化百分比
    
    Args:
        value: 數值 (0-100 或 0-1)
        decimals: 小數位數
        
    Returns:
        格式化字串
    """
    if value <= 1:
        value *= 100
    return f"{value:.{decimals}f}%"


def create_directories():
    """建立專案所需目錄"""
    directories = [
        settings.data_raw_path,
        settings.data_processed_path,
        settings.data_cache_path,
        settings.model_path,
        settings.logs_path
    ]
    
    for dir_path in directories:
        dir_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Directory ensured: {dir_path}")


def clear_gpu_memory():
    """清理 GPU 記憶體"""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        logger.info("GPU memory cleared")


def check_gpu_memory(threshold_gb: float = 1.0) -> bool:
    """
    檢查 GPU 記憶體是否足夠
    
    Args:
        threshold_gb: 最低可用記憶體閾值 (GB)
        
    Returns:
        是否足夠
    """
    if not torch.cuda.is_available():
        return False
    
    free_memory = torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_allocated(0)
    free_gb = free_memory / 1024**3
    
    if free_gb < threshold_gb:
        logger.warning(f"Low GPU memory: {free_gb:.2f} GB available")
        return False
    
    return True


def get_taiwan_time() -> datetime:
    """獲取台灣時間"""
    from datetime import timezone, timedelta
    taiwan_tz = timezone(timedelta(hours=8))
    return datetime.now(taiwan_tz)


def is_peak_hour(hour: Optional[int] = None) -> bool:
    """
    判斷是否為尖峰時段
    
    Args:
        hour: 小時 (0-23)，預設為當前小時
        
    Returns:
        是否為尖峰時段
    """
    if hour is None:
        hour = get_taiwan_time().hour
    
    return (10 <= hour < 12) or (13 <= hour < 17)


def is_summer_season(month: Optional[int] = None) -> bool:
    """
    判斷是否為夏季電價期間
    
    Args:
        month: 月份 (1-12)，預設為當前月份
        
    Returns:
        是否為夏季
    """
    if month is None:
        month = get_taiwan_time().month
    
    return 6 <= month <= 9


def print_banner():
    """印出程式 Banner"""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   ███████╗ ██████╗ ██████╗  ██████╗ ██████╗ ██╗██████╗       ║
║   ██╔════╝██╔════╝██╔═══██╗██╔════╝ ██╔══██╗██║██╔══██╗      ║
║   █████╗  ██║     ██║   ██║██║  ███╗██████╔╝██║██║  ██║      ║
║   ██╔══╝  ██║     ██║   ██║██║   ██║██╔══██╗██║██║  ██║      ║
║   ███████╗╚██████╗╚██████╔╝╚██████╔╝██║  ██║██║██████╔╝      ║
║   ╚══════╝ ╚═════╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝╚═════╝       ║
║                                                               ║
║        綠電優化與用電審計預測系統 v1.0.0                      ║
║        Taiwan Green Energy Optimization System                ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
"""
    print(banner)
