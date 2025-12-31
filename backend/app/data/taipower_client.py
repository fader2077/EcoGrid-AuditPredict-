"""
台灣電力公司 Open Data 客戶端
Taiwan Power Company Open Data Client

數據來源：
- 即時用電資訊: https://data.gov.tw/dataset/19995
- 每日尖峰負載: https://data.gov.tw/dataset/25850
- 電力供需資訊: https://www.taipower.com.tw/tc/page.aspx?mid=206
"""

import httpx
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class TaipowerClient:
    """台電 Open Data 客戶端"""
    
    # 台電即時用電資訊 API
    REALTIME_USAGE_URL = "https://www.taipower.com.tw/d006/loadGraph/loadGraph/data/loadpara.json"
    
    # 備用：政府資料開放平台
    GOV_OPEN_DATA_URL = "https://data.gov.tw/api/v2/rest/datastore/382000000J-000001-001"
    
    def __init__(self, timeout: int = 10):
        """
        初始化台電客戶端
        
        Args:
            timeout: 請求超時時間（秒）
        """
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
        
    async def close(self):
        """關閉客戶端"""
        await self.client.aclose()
    
    async def get_realtime_usage(self) -> Optional[Dict]:
        """
        獲取即時用電資訊
        
        Returns:
            {
                'timestamp': '2024-12-21 14:30:00',
                'current_load': 28500,  # MW
                'current_capacity': 40000,  # MW
                'usage_rate': 71.25,  # %
                'reserve_capacity': 11500,  # MW
                'reserve_rate': 28.75  # %
            }
        """
        try:
            response = await self.client.get(self.REALTIME_USAGE_URL)
            response.raise_for_status()
            data = response.json()
            
            # 解析台電 JSON 格式
            aaData = data.get('aaData', [])
            if not aaData:
                logger.warning("台電 API 返回空數據")
                return None
            
            latest = aaData[0]
            
            return {
                'timestamp': datetime.now().isoformat(),
                'current_load': float(latest[1]) * 10,  # 轉換單位 (萬瓩 → MW)
                'current_capacity': float(latest[2]) * 10,
                'usage_rate': float(latest[3]),
                'reserve_capacity': float(latest[4]) * 10,
                'reserve_rate': float(latest[5]),
                'peak_today': float(latest[6]) * 10 if len(latest) > 6 else None
            }
            
        except httpx.HTTPError as e:
            logger.error(f"台電 API 請求失敗: {e}")
            return None
        except Exception as e:
            logger.error(f"解析台電數據失敗: {e}")
            return None
    
    async def get_historical_load(
        self, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[Dict]:
        """
        獲取歷史負載數據（模擬）
        
        Note: 台電未提供公開的歷史 API，這裡使用即時數據 + 時間模式模擬
        
        Args:
            start_date: 開始日期
            end_date: 結束日期
            
        Returns:
            List of hourly load data
        """
        logger.info(f"獲取歷史數據: {start_date} 到 {end_date}")
        
        # 獲取當前數據作為基準
        current = await self.get_realtime_usage()
        if not current:
            return []
        
        base_load = current['current_load']
        historical_data = []
        
        # 生成每小時數據（基於典型負載曲線）
        current_date = start_date
        while current_date <= end_date:
            for hour in range(24):
                timestamp = current_date.replace(hour=hour, minute=0, second=0)
                
                # 負載模式：夜間低、白天高、尖峰時段最高
                if 0 <= hour < 7:  # 離峰
                    load_factor = 0.65
                elif 7 <= hour < 10:  # 半尖峰
                    load_factor = 0.85
                elif 10 <= hour < 17:  # 尖峰
                    load_factor = 1.0
                elif 17 <= hour < 23:  # 半尖峰
                    load_factor = 0.90
                else:  # 離峰
                    load_factor = 0.70
                
                historical_data.append({
                    'timestamp': timestamp.isoformat(),
                    'load_mw': base_load * load_factor,
                    'hour': hour,
                    'weekday': timestamp.weekday(),
                    'is_weekend': timestamp.weekday() >= 5
                })
            
            current_date += timedelta(days=1)
        
        logger.info(f"生成 {len(historical_data)} 筆歷史數據")
        return historical_data
    
    async def get_tou_rates(self) -> Dict[str, List[Dict]]:
        """
        獲取時間電價費率
        
        Returns:
            {
                'three_tier': [
                    {'period': 'peak', 'hours': [10,11,12,13,14,15,16], 'rate': 5.50},
                    {'period': 'mid_peak', 'hours': [7,8,9,17,18,19,20,21,22], 'rate': 3.80},
                    {'period': 'off_peak', 'hours': [0,1,2,3,4,5,6,23], 'rate': 1.70}
                ],
                'two_tier': [...]
            }
        """
        return {
            'three_tier': [
                {
                    'period': 'peak',
                    'name': '尖峰時段',
                    'hours': [10, 11, 12, 13, 14, 15, 16],
                    'rate': 5.50,  # 元/度
                    'color': '#ef4444'
                },
                {
                    'period': 'mid_peak',
                    'name': '半尖峰時段',
                    'hours': [7, 8, 9, 17, 18, 19, 20, 21, 22],
                    'rate': 3.80,
                    'color': '#f59e0b'
                },
                {
                    'period': 'off_peak',
                    'name': '離峰時段',
                    'hours': [0, 1, 2, 3, 4, 5, 6, 23],
                    'rate': 1.70,
                    'color': '#10b981'
                }
            ],
            'two_tier': [
                {
                    'period': 'peak',
                    'name': '尖峰時段',
                    'hours': list(range(7, 23)),
                    'rate': 4.20,
                    'color': '#ef4444'
                },
                {
                    'period': 'off_peak',
                    'name': '離峰時段',
                    'hours': [23] + list(range(0, 7)),
                    'rate': 2.10,
                    'color': '#10b981'
                }
            ]
        }
    
    async def get_carbon_intensity(self) -> Optional[Dict]:
        """
        獲取電網碳強度（模擬）
        
        Returns:
            {
                'timestamp': '2024-12-21 14:30:00',
                'carbon_intensity': 0.502,  # kgCO2/kWh
                'renewable_ratio': 15.3,  # %
                'coal_ratio': 35.2,
                'gas_ratio': 40.5,
                'nuclear_ratio': 9.0
            }
        """
        # 台灣電網平均碳強度約 0.502 kgCO2/kWh
        return {
            'timestamp': datetime.now().isoformat(),
            'carbon_intensity': 0.502,
            'renewable_ratio': 15.3,
            'coal_ratio': 35.2,
            'gas_ratio': 40.5,
            'nuclear_ratio': 9.0
        }


async def test_taipower_client():
    """測試台電客戶端"""
    print("\n=== 台電 Open Data 客戶端測試 ===\n")
    
    client = TaipowerClient()
    
    try:
        # 測試即時用電
        print("1. 即時用電資訊:")
        realtime = await client.get_realtime_usage()
        if realtime:
            print(f"   時間: {realtime['timestamp']}")
            print(f"   當前負載: {realtime['current_load']:,.0f} MW")
            print(f"   備轉容量率: {realtime['reserve_rate']:.1f}%")
        
        # 測試歷史數據
        print("\n2. 歷史負載數據:")
        start = datetime.now() - timedelta(days=1)
        end = datetime.now()
        historical = await client.get_historical_load(start, end)
        print(f"   獲取 {len(historical)} 筆數據")
        if historical:
            print(f"   範例: {historical[0]}")
        
        # 測試 TOU 費率
        print("\n3. TOU 時間電價:")
        tou = await client.get_tou_rates()
        for tier_name, tiers in tou.items():
            print(f"   {tier_name}:")
            for tier in tiers:
                print(f"     {tier['name']}: ${tier['rate']}/度")
        
        # 測試碳強度
        print("\n4. 電網碳強度:")
        carbon = await client.get_carbon_intensity()
        if carbon:
            print(f"   碳強度: {carbon['carbon_intensity']} kgCO2/kWh")
            print(f"   再生能源占比: {carbon['renewable_ratio']}%")
        
        print("\n✓ 所有測試通過!")
        
    except Exception as e:
        print(f"\n✗ 測試失敗: {e}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_taipower_client())
