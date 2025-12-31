"""
產生測試數據到資料庫
模擬 24 小時的電力數據
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from datetime import datetime, timedelta
import random
import math

from app.db.session import SessionLocal
from app.models.power import PowerLog
from app.db import init_db

def get_tou_info(hour):
    """根據時間返回 TOU 時段和電價"""
    if 10 <= hour < 12 or 13 <= hour < 17:
        return "peak", 7.05
    elif 7 <= hour < 10 or 17 <= hour < 22:
        return "half_peak", 4.46
    else:
        return "off_peak", 2.38

def generate_power_data(hours=168):
    """
    產生測試用電力數據
    
    Args:
        hours: 產生多少小時的數據（預設 168 = 7 天）
    """
    # 先初始化資料庫
    print("初始化資料庫...")
    init_db()
    print("資料庫初始化完成")
    
    db = SessionLocal()
    
    try:
        # 清空現有數據（可選）
        # db.query(PowerLog).delete()
        # db.commit()
        
        now = datetime.now()
        start_time = now - timedelta(hours=hours)
        
        print(f"開始產生 {hours} 小時的測試數據...")
        print(f"時間範圍: {start_time.strftime('%Y-%m-%d %H:%M')} - {now.strftime('%Y-%m-%d %H:%M')}")
        
        data_points = []
        
        for i in range(hours):
            timestamp = start_time + timedelta(hours=i)
            hour = timestamp.hour
            
            # 模擬負載曲線（工業用電模式）
            # 白天高、夜間低
            base_load = 300
            time_factor = math.sin((hour - 6) * math.pi / 12) * 100  # 6-18 點高峰
            noise = random.uniform(-20, 20)
            load_kw = max(200, base_load + time_factor + noise)
            
            # 模擬太陽能發電（日出到日落）
            if 6 <= hour <= 18:
                solar_factor = math.sin((hour - 6) * math.pi / 12)
                solar_kw = solar_factor * random.uniform(80, 120)
            else:
                solar_kw = 0.0
            
            # 模擬風力發電（較穩定但有波動）
            wind_kw = random.uniform(20, 50)
            
            # 計算電網購電量
            renewable_total = solar_kw + wind_kw
            grid_import_kw = max(0, load_kw - renewable_total)
            
            # 模擬電池 SoC（簡化版）
            battery_soc = 0.3 + 0.4 * math.sin((hour - 12) * math.pi / 12)  # 0.3-0.7
            
            # 獲取 TOU 資訊
            tou_period, tariff_rate = get_tou_info(hour)
            
            # 計算成本（假設每小時）
            cost_ntd = (grid_import_kw * tariff_rate) - (renewable_total * tariff_rate * 0.2)  # 綠電有 80% 折扣
            
            # 建立記錄
            log = PowerLog(
                timestamp=timestamp,
                load_kw=round(load_kw, 2),
                solar_kw=round(solar_kw, 2),
                wind_kw=round(wind_kw, 2),
                grid_import_kw=round(grid_import_kw, 2),
                battery_soc=round(battery_soc, 3),
                tou_period=tou_period,
                tariff_rate=tariff_rate,
                cost_ntd=round(cost_ntd, 2)
            )
            
            data_points.append(log)
            
            if (i + 1) % 24 == 0:
                print(f"  已產生 {i + 1}/{hours} 小時...")
        
        # 批次插入
        db.bulk_save_objects(data_points)
        db.commit()
        
        print(f"\n✓ 成功產生 {len(data_points)} 筆測試數據")
        
        # 顯示統計資訊
        total_load = sum(log.load_kw for log in data_points)
        total_solar = sum(log.solar_kw for log in data_points)
        total_wind = sum(log.wind_kw for log in data_points)
        total_cost = sum(log.cost_ntd for log in data_points)
        
        print(f"\n統計資訊:")
        print(f"  總負載: {total_load:.2f} kWh")
        print(f"  太陽能發電: {total_solar:.2f} kWh")
        print(f"  風力發電: {total_wind:.2f} kWh")
        print(f"  綠電比例: {(total_solar + total_wind) / total_load * 100:.2f}%")
        print(f"  總成本: ${total_cost:.2f} NTD")
        print(f"  平均負載: {total_load / hours:.2f} kW")
        
    except Exception as e:
        print(f"✗ 錯誤: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    # 產生 7 天（168 小時）的數據
    generate_power_data(hours=168)
