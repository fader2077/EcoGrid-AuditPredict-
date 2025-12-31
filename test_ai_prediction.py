"""
直接測試 AI 預測功能（使用 GPU）
"""

import requests
import time
import json
import sys

# 設置輸出編碼
sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://localhost:8000/api/v1"

print("="*60)
print("測試 AI 負載預測（GPU 加速）")
print("="*60)

# 1. 創建預測任務
print("\n[1] 創建 AI 預測任務...")
payload = {
    "hours_ahead": 24,
    "use_transformer": False,  # 不使用 Transformer（省時間）
    "use_lstm": False  # 不使用 LSTM（省時間）
}

response = requests.post(f"{BASE_URL}/forecast/predict", json=payload, timeout=10)

if response.status_code != 200:
    print(f"✗ 失敗: {response.status_code}")
    print(f"錯誤: {response.text}")
    exit(1)

data = response.json()
task_id = data.get('task_id')
print(f"✓ 任務已創建: {task_id}")

# 2. 輪詢任務狀態
print("\n[2] 等待 AI 預測完成...")
print("注意: 首次運行會訓練模型（約 5-10 分鐘），後續預測僅需數秒")
print("-" * 60)

max_attempts = 600  # 最多等待 10 分鐘
for attempt in range(max_attempts):
    time.sleep(2)
    
    try:
        status_response = requests.get(
            f"{BASE_URL}/forecast/predict/{task_id}",
            timeout=10
        )
        
        if status_response.status_code != 200:
            print(f"\n✗ 查詢狀態失敗: {status_response.status_code}")
            continue
        
        status_data = status_response.json()
        status = status_data.get('status')
        progress = status_data.get('progress', 0)
        
        # 顯示進度
        bar_length = 40
        filled = int(bar_length * progress / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        print(f"\r進度: [{bar}] {progress:.1f}% - {status}", end='', flush=True)
        
        if status == 'completed':
            print()  # 換行
            print("\n" + "="*60)
            print("✓ AI 預測完成！")
            print("="*60)
            
            result = status_data.get('result', {})
            print(f"\n預測結果:")
            print(f"  - 預測數量: {result.get('forecast_count', 0)} 筆")
            print(f"  - 平均負載: {result.get('avg_load_kw', 0):.2f} kW")
            print(f"  - 模型類型: {result.get('model_type', 'N/A')}")
            
            # 3. 獲取最新預測詳情
            print("\n[3] 獲取詳細預測結果...")
            latest_response = requests.get(
                f"{BASE_URL}/forecast/latest",
                params={"limit": 5},
                timeout=10
            )
            
            if latest_response.status_code == 200:
                latest_data = latest_response.json()
                print(f"\n最新 5 筆預測:")
                print("-" * 60)
                for i, forecast in enumerate(latest_data[:5], 1):
                    timestamp = forecast.get('forecast_timestamp', 'N/A')
                    predicted = forecast.get('predicted_load_kw', 0)
                    model = forecast.get('model_type', 'N/A')
                    confidence = forecast.get('confidence', 0) * 100
                    print(f"{i}. {timestamp} | 負載: {predicted:.2f} kW | 模型: {model} | 信心度: {confidence:.1f}%")
            
            print("\n" + "="*60)
            print("GPU 使用情況:")
            print("="*60)
            
            import torch
            if torch.cuda.is_available():
                for i in range(torch.cuda.device_count()):
                    allocated = torch.cuda.memory_allocated(i) / 1024**3
                    reserved = torch.cuda.memory_reserved(i) / 1024**3
                    total = torch.cuda.get_device_properties(i).total_memory / 1024**3
                    usage_percent = (allocated / total) * 100
                    
                    print(f"\nGPU {i}: {torch.cuda.get_device_name(i)}")
                    print(f"  已分配: {allocated:.2f} GB")
                    print(f"  已保留: {reserved:.2f} GB")
                    print(f"  總容量: {total:.2f} GB")
                    print(f"  使用率: {usage_percent:.1f}%")
                    
                    if usage_percent > 85:
                        print(f"  ⚠️  警告: GPU 記憶體使用率超過 85%，接近 OOM 風險")
                    elif usage_percent > 60:
                        print(f"  ✓ GPU 記憶體使用正常（目標: <60%）")
                    else:
                        print(f"  ✓ GPU 記憶體充足")
            
            break
        
        elif status == 'failed':
            print()  # 換行
            error_msg = status_data.get('error_message', 'Unknown error')
            print(f"\n✗ 預測失敗: {error_msg}")
            break
        
    except Exception as e:
        print(f"\n✗ 錯誤: {e}")
        time.sleep(5)

else:
    print("\n✗ 任務超時（超過 10 分鐘）")

print("\n測試完成！")
