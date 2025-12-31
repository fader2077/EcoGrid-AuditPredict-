"""
生成更真實的訓練數據（模擬台灣用電模式）
基於台灣實際用電特徵
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from datetime import datetime, timedelta
import random
import math
import numpy as np

from app.db.session import SessionLocal
from app.models.power import PowerLog
from app.db import init_db

def get_tou_info(hour):
    """台灣時間電價時段"""
    if 10 <= hour < 12 or 13 <= hour < 17:
        return "peak", 7.05  # 尖峰
    elif 7 <= hour < 10 or 17 <= hour < 22:
        return "half_peak", 4.46  # 半尖峰
    else:
        return "off_peak", 2.38  # 離峰

def generate_realistic_power_data(days=30):
    """
    生成真實的台灣用電數據
    
    特徵：
    1. 工作日vs週末差異
    2. 夏季冷氣負載高峰
    3. 太陽能發電曲線（日照影響）
    4. 風力發電變化
    5. 電池充放電策略
    """
    db = SessionLocal()
    
    try:
        # 初始化資料庫
        print("初始化資料庫...")
        init_db()
        
        # 清空舊數據
        db.query(PowerLog).delete()
        db.commit()
        print("已清空舊數據")
        
        now = datetime.now()
        start_time = now - timedelta(days=days)
        
        print(f"\n生成 {days} 天的真實訓練數據...")
        print(f"時間範圍: {start_time.strftime('%Y-%m-%d')} - {now.strftime('%Y-%m-%d')}")
        print(f"總共: {days * 24} 小時")
        
        data_points = []
        
        for day_offset in range(days):
            current_date = start_time + timedelta(days=day_offset)
            is_weekend = current_date.weekday() >= 5  # 週六日
            
            # 季節因子（夏季用電高）
            month = current_date.month
            if 6 <= month <= 9:  # 夏季
                season_factor = 1.3
            elif 12 <= month or month <= 2:  # 冬季
                season_factor = 1.1
            else:  # 春秋
                season_factor = 1.0
            
            for hour in range(24):
                timestamp = current_date + timedelta(hours=hour)
                
                # === 1. 負載曲線（工業+商業） ===
                base_load = 350  # 基礎負載 (kW)
                
                # 工作日 vs 週末
                if is_weekend:
                    weekday_factor = 0.7  # 週末降低 30%
                else:
                    weekday_factor = 1.0
                
                # 時間因子（台灣用電高峰: 13-16點）
                if 9 <= hour <= 17:
                    # 工作時段
                    time_factor = 1.0 + 0.4 * math.sin((hour - 9) * math.pi / 8)
                elif 18 <= hour <= 22:
                    # 晚間時段
                    time_factor = 0.9
                else:
                    # 深夜/凌晨
                    time_factor = 0.6
                
                # 隨機波動（±10%）
                noise = random.gauss(1.0, 0.1)
                
                # 總負載
                load_kw = base_load * season_factor * weekday_factor * time_factor * noise
                load_kw = max(200, min(600, load_kw))  # 限制在 200-600 kW
                
                # === 2. 太陽能發電 ===
                if 6 <= hour <= 18:
                    # 高斯曲線模擬日照
                    hour_from_noon = abs(hour - 12)
                    solar_efficiency = math.exp(-(hour_from_noon ** 2) / 18)
                    
                    # 雲層影響（隨機）
                    cloud_factor = random.uniform(0.7, 1.0)
                    
                    # 季節影響（夏季日照強）
                    if 5 <= month <= 8:
                        solar_season = 1.2
                    else:
                        solar_season = 0.8
                    
                    solar_kw = 150 * solar_efficiency * cloud_factor * solar_season
                else:
                    solar_kw = 0.0
                
                # === 3. 風力發電 ===
                # 風速變化（白天風力較強）
                if 10 <= hour <= 16:
                    wind_base = 50
                else:
                    wind_base = 30
                
                wind_noise = random.gauss(1.0, 0.3)
                wind_kw = max(10, min(80, wind_base * wind_noise))
                
                # === 4. 能源平衡 ===
                renewable_total = solar_kw + wind_kw
                net_demand = load_kw - renewable_total
                
                # 電網購電
                if net_demand > 0:
                    grid_import_kw = net_demand
                    grid_export_kw = 0.0
                else:
                    grid_import_kw = 0.0
                    grid_export_kw = -net_demand
                
                # === 5. 電池策略 ===
                # 離峰充電、尖峰放電
                tou_period, tariff_rate = get_tou_info(hour)
                
                if tou_period == "off_peak" and renewable_total > load_kw * 0.5:
                    # 離峰+綠電充裕 → 充電
                    battery_charge_kw = min(30, renewable_total * 0.3)
                    battery_discharge_kw = 0.0
                    battery_soc_change = 0.05
                elif tou_period == "peak" and load_kw > renewable_total:
                    # 尖峰+綠電不足 → 放電
                    battery_discharge_kw = min(40, load_kw * 0.2)
                    battery_charge_kw = 0.0
                    battery_soc_change = -0.06
                else:
                    battery_charge_kw = 0.0
                    battery_discharge_kw = 0.0
                    battery_soc_change = 0.0
                
                # 電池 SoC（限制 20%-90%）
                if day_offset == 0 and hour == 0:
                    battery_soc = 0.5  # 初始 50%
                else:
                    prev_soc = data_points[-1].battery_soc if data_points else 0.5
                    battery_soc = prev_soc + battery_soc_change
                    battery_soc = max(0.2, min(0.9, battery_soc))
                
                # === 6. 成本計算 ===
                # 電網購電成本
                grid_cost = grid_import_kw * tariff_rate
                
                # 綠電獎勵（假設 FIT 0.8 倍電價）
                renewable_credit = renewable_total * tariff_rate * 0.8
                
                # 電池充放電成本（簡化）
                battery_cost = battery_charge_kw * tariff_rate * 0.1
                
                cost_ntd = grid_cost - renewable_credit + battery_cost
                
                # 建立記錄
                log = PowerLog(
                    timestamp=timestamp,
                    load_kw=round(load_kw, 2),
                    solar_kw=round(solar_kw, 2),
                    wind_kw=round(wind_kw, 2),
                    grid_import_kw=round(grid_import_kw, 2),
                    grid_export_kw=round(grid_export_kw, 2),
                    battery_charge_kw=round(battery_charge_kw, 2),
                    battery_discharge_kw=round(battery_discharge_kw, 2),
                    battery_soc=round(battery_soc, 3),
                    tou_period=tou_period,
                    tariff_rate=tariff_rate,
                    cost_ntd=round(cost_ntd, 2)
                )
                
                data_points.append(log)
            
            if (day_offset + 1) % 5 == 0:
                print(f"  已生成 {day_offset + 1}/{days} 天... ({len(data_points)} 筆)")
        
        # 批次插入
        print("\n寫入資料庫...")
        db.bulk_save_objects(data_points)
        db.commit()
        
        print(f"\n✓ 成功生成 {len(data_points)} 筆真實訓練數據")
        
        # 統計資訊
        total_load = sum(log.load_kw for log in data_points)
        total_solar = sum(log.solar_kw for log in data_points)
        total_wind = sum(log.wind_kw for log in data_points)
        total_cost = sum(log.cost_ntd for log in data_points)
        
        print(f"\n=== 數據統計 ===")
        print(f"總負載: {total_load:,.2f} kWh")
        print(f"太陽能發電: {total_solar:,.2f} kWh ({total_solar/total_load*100:.1f}%)")
        print(f"風力發電: {total_wind:,.2f} kWh ({total_wind/total_load*100:.1f}%)")
        print(f"綠電比例: {(total_solar + total_wind) / total_load * 100:.1f}%")
        print(f"總成本: ${total_cost:,.2f} NTD")
        print(f"平均負載: {total_load / len(data_points):.2f} kW")
        print(f"平均太陽能: {total_solar / len(data_points):.2f} kW")
        print(f"平均風力: {total_wind / len(data_points):.2f} kW")
        
    except Exception as e:
        print(f"✗ 錯誤: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    # 生成 30 天真實數據
    generate_realistic_power_data(days=30)
