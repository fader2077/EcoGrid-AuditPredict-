"""
Data Populator Service - 定期更新數據庫
"""
import asyncio
import numpy as np
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import PowerLog
from app.data.taipower_client import TaipowerClient
from app.data.weather_client import WeatherClient


class DataPopulator:
    """數據填充服務"""
    
    def __init__(self):
        self.taipower = TaipowerClient()
        self.weather = WeatherClient()
        self._running = False
    
    async def close(self):
        """關閉客戶端"""
        await self.taipower.close()
        await self.weather.close()
    
    async def fetch_and_insert_realtime(self):
        """獲取即時數據並插入資料庫"""
        try:
            # 並行獲取台電和氣象數據
            taipower_data = await self.taipower.get_realtime_usage()
            weather_data = await self.weather.get_current_weather()
            carbon_data = await self.taipower.get_carbon_intensity()
            
            # 安全獲取數據，使用預設值防止 None
            current_load_mw = taipower_data['current_load'] if taipower_data else 28000.0
            temperature = weather_data['temperature'] if weather_data else 25.0
            solar_radiation = weather_data['solar_radiation'] if weather_data else 500.0
            wind_speed = weather_data['wind_speed'] if weather_data else 2.5
            carbon_intensity = carbon_data['carbon_intensity'] if carbon_data else 0.502
            
            # 估算再生能源發電
            solar_kw = (solar_radiation / 1000.0) * 150  # 150kW 太陽能板容量
            wind_kw = (wind_speed ** 3) * 0.5  # 風力發電公式（簡化）
            
            # 計算電網供電
            load_kw = current_load_mw * 1000 * 0.01  # 取 1% 作為示例用戶
            grid_import_kw = max(0, load_kw - solar_kw - wind_kw)
            
            # 確定 TOU 時段
            hour = datetime.now().hour
            if (10 <= hour < 12) or (13 <= hour < 17):
                tou_period = "peak"
                tariff_rate = 5.50
            elif (7 <= hour < 10) or (17 <= hour < 22):
                tou_period = "half_peak"
                tariff_rate = 3.80
            else:
                tou_period = "off_peak"
                tariff_rate = 1.70
            
            # 計算成本
            cost_ntd = grid_import_kw * tariff_rate
            
            # 電池 SOC (簡單模擬)
            battery_soc = 0.5 + 0.3 * (solar_kw / 150.0)
            battery_soc = min(1.0, max(0.0, battery_soc))
            
            # 插入資料庫
            db = SessionLocal()
            try:
                power_log = PowerLog(
                    timestamp=datetime.now(),
                    load_kw=load_kw,
                    solar_kw=solar_kw,
                    wind_kw=wind_kw,
                    grid_import_kw=grid_import_kw,
                    battery_soc=battery_soc,
                    tariff_rate=tariff_rate,
                    tou_period=tou_period,
                    cost_ntd=cost_ntd
                )
                db.add(power_log)
                db.commit()
                
                logger.info(
                    f"✓ 數據已更新: Load={load_kw:.1f}kW, Solar={solar_kw:.1f}kW, "
                    f"Wind={wind_kw:.1f}kW, TOU={tou_period}, Tariff=${tariff_rate}"
                )
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"數據更新失敗: {e}")
    
    async def populate_historical(self, hours: int = 24):
        """填充歷史數據（初始化用）"""
        logger.info(f"開始填充歷史數據（{hours} 小時）...")
        
        db = SessionLocal()
        try:
            # 檢查是否已有數據
            count = db.query(PowerLog).count()
            if count > hours:
                logger.info(f"資料庫已有 {count} 筆數據，跳過初始化")
                return
            
            # 生成過去 N 小時的模擬數據
            now = datetime.now()
            for i in range(hours, 0, -1):
                timestamp = now - timedelta(hours=i)
                hour = timestamp.hour
                
                # 基於時段的負載模式
                base_load = 280.0
                if 8 <= hour < 18:
                    load_kw = base_load + 100.0 + np.random.normal(0, 15)
                elif 18 <= hour < 22:
                    load_kw = base_load + 50.0 + np.random.normal(0, 10)
                else:
                    load_kw = base_load + np.random.normal(0, 8)
                
                # 太陽能（日間高，夜間為0）
                if 6 <= hour <= 18:
                    solar_factor = np.sin((hour - 6) / 12 * np.pi)
                    solar_kw = 150.0 * solar_factor * np.random.uniform(0.7, 1.0)
                else:
                    solar_kw = 0.0
                
                # 風力（隨機波動）
                wind_kw = np.random.uniform(10, 60)
                
                grid_import_kw = max(0, load_kw - solar_kw - wind_kw)
                
                # TOU 時段
                if (10 <= hour < 12) or (13 <= hour < 17):
                    tou_period, tariff_rate = "peak", 5.50
                elif (7 <= hour < 10) or (17 <= hour < 22):
                    tou_period, tariff_rate = "half_peak", 3.80
                else:
                    tou_period, tariff_rate = "off_peak", 1.70
                
                power_log = PowerLog(
                    timestamp=timestamp,
                    load_kw=load_kw,
                    solar_kw=solar_kw,
                    wind_kw=wind_kw,
                    grid_import_kw=grid_import_kw,
                    battery_soc=np.random.uniform(0.3, 0.8),
                    tariff_rate=tariff_rate,
                    tou_period=tou_period,
                    cost_ntd=grid_import_kw * tariff_rate
                )
                db.add(power_log)
            
            db.commit()
            logger.info(f"✓ 成功填充 {hours} 筆歷史數據")
        finally:
            db.close()
    
    async def run_background_task(self, interval_seconds: int = 300):
        """背景任務：定期更新數據"""
        self._running = True
        logger.info(f"背景數據更新任務啟動（每 {interval_seconds} 秒更新一次）")
        
        # 初始化：填充歷史數據
        await self.populate_historical(hours=48)
        
        # 立即更新一次
        await self.fetch_and_insert_realtime()
        
        # 定期更新
        while self._running:
            try:
                await asyncio.sleep(interval_seconds)
                await self.fetch_and_insert_realtime()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"背景任務錯誤: {e}")
                await asyncio.sleep(10)
        
        logger.info("背景數據更新任務已停止")
    
    def stop(self):
        """停止背景任務"""
        self._running = False


# 全局實例
_populator_instance = None


async def get_data_populator() -> DataPopulator:
    """獲取數據填充器單例"""
    global _populator_instance
    if _populator_instance is None:
        _populator_instance = DataPopulator()
    return _populator_instance


async def start_background_data_population():
    """啟動背景數據填充（在 FastAPI startup 時調用）"""
    populator = await get_data_populator()
    # 在背景運行，不阻塞
    asyncio.create_task(populator.run_background_task(interval_seconds=60))  # 每分鐘更新
