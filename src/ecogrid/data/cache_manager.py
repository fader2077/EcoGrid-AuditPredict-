"""
Cache Manager for ETL Pipeline
實作本地快取機制，避免 API 限流與重複請求
"""

import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
import pickle

from loguru import logger
from diskcache import Cache

from ecogrid.config.settings import settings


class CacheManager:
    """
    本地快取管理器
    - 支援 TTL (Time-To-Live) 過期機制
    - 支援 disk-based 快取（大型資料集）
    - 支援 JSON 和 Pickle 序列化
    """
    
    def __init__(self, cache_dir: Optional[Path] = None, ttl_hours: Optional[int] = None):
        self.cache_dir = cache_dir or settings.data_cache_path
        self.ttl_hours = ttl_hours or settings.cache_ttl_hours
        self.enabled = settings.cache_enabled
        
        # Initialize disk cache
        self.cache = Cache(str(self.cache_dir / "diskcache"))
        logger.info(f"CacheManager initialized at {self.cache_dir}")
    
    def _generate_key(self, identifier: str, params: Optional[dict] = None) -> str:
        """生成唯一快取鍵"""
        key_data = identifier
        if params:
            key_data += json.dumps(params, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, identifier: str, params: Optional[dict] = None) -> Optional[Any]:
        """
        從快取獲取資料
        
        Args:
            identifier: 資料識別符
            params: 額外參數（用於區分不同查詢）
            
        Returns:
            快取的資料，若不存在或過期則返回 None
        """
        if not self.enabled:
            return None
        
        key = self._generate_key(identifier, params)
        
        try:
            data = self.cache.get(key)
            if data is not None:
                logger.debug(f"Cache HIT for {identifier}")
                return data
            logger.debug(f"Cache MISS for {identifier}")
            return None
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
            return None
    
    def set(self, identifier: str, data: Any, params: Optional[dict] = None, 
            ttl_hours: Optional[int] = None) -> bool:
        """
        存入快取
        
        Args:
            identifier: 資料識別符
            data: 要快取的資料
            params: 額外參數
            ttl_hours: 自訂 TTL（小時）
            
        Returns:
            是否成功存入
        """
        if not self.enabled:
            return False
        
        key = self._generate_key(identifier, params)
        ttl = (ttl_hours or self.ttl_hours) * 3600  # Convert to seconds
        
        try:
            self.cache.set(key, data, expire=ttl)
            logger.debug(f"Cached {identifier} with TTL={ttl_hours or self.ttl_hours}h")
            return True
        except Exception as e:
            logger.warning(f"Cache write error: {e}")
            return False
    
    def delete(self, identifier: str, params: Optional[dict] = None) -> bool:
        """刪除特定快取"""
        key = self._generate_key(identifier, params)
        try:
            del self.cache[key]
            return True
        except KeyError:
            return False
    
    def clear(self) -> None:
        """清除所有快取"""
        self.cache.clear()
        logger.info("Cache cleared")
    
    def get_stats(self) -> dict:
        """獲取快取統計"""
        return {
            "size": len(self.cache),
            "volume": self.cache.volume(),
            "directory": str(self.cache_dir)
        }
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cache.close()
