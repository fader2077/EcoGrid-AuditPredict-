"""
測試 AI 預測修正後的結果
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import requests
import time

BASE_URL = "http://localhost:8000/api/v1"

print("=" * 60)
print("測試 AI 預測修正（使用簡化 ETL + 單位轉換）")
print("=" * 60)

# 等待 Backend 啟動
print("\n等待 Backend 啟動...")
time.sleep(5)

# 測試連接
try:
    response = requests.get(f"{BASE_URL}/dashboard/summary", timeout=5)
    print(f"✓ Backend 已就緒 (狀態: {response.status_code})")
except:
    print("✗ Backend 未啟動，請稍候...")
    time.sleep(5)

# 發起預測任務
print("\n發起預測任務（使用修正後的 ETL）...")
payload = {
    "hours_ahead": 24,
    "use_transformer": False,
    "use_lstm": False
}

response = requests.post(f"{BASE_URL}/forecast/predict", json=payload)
if response.status_code != 200:
    print(f"✗ 預測請求失敗: {response.status_code}")
    print(response.text)
    sys.exit(1)

task = response.json()
task_id = task["task_id"]
print(f"✓ 任務 ID: {task_id}")

# 輪詢任務狀態
print("\n輪詢任務狀態...")
max_wait = 300
start_time = time.time()

while time.time() - start_time < max_wait:
    status_response = requests.get(f"{BASE_URL}/forecast/predict/{task_id}")
    status = status_response.json()
    
    print(f"  進度: {status['progress']:.1f}% - {status['status']}")
    
    if status["status"] == "completed":
        print(f"\n✓ 預測完成！耗時: {time.time() - start_time:.1f} 秒")
        break
    elif status["status"] == "failed":
        print(f"\n✗ 預測失敗: {status.get('error_message', 'Unknown')}")
        sys.exit(1)
    
    time.sleep(3)

# 取得最新預測結果
print("\n取得預測結果...")
results_response = requests.get(f"{BASE_URL}/forecast/latest")

if results_response.status_code == 200:
    results = results_response.json()
    forecast_data = results["forecast_data"]
    
    # 提取負載預測值
    loads = [item["predicted_load_kw"] for item in forecast_data]
    
    print(f"\n{'=' * 60}")
    print("預測結果統計（24 小時）")
    print(f"{'=' * 60}")
    print(f"平均負載: {sum(loads)/len(loads):.2f} kW")
    print(f"最小負載: {min(loads):.2f} kW")
    print(f"最大負載: {max(loads):.2f} kW")
    print(f"標準差: {(sum((x - sum(loads)/len(loads))**2 for x in loads) / len(loads)) ** 0.5:.2f} kW")
    
    # 驗證結果
    avg_load = sum(loads) / len(loads)
    
    print(f"\n{'=' * 60}")
    if 150 <= avg_load <= 700:
        print("✅ 預測值在合理範圍內（150-700 kW）")
        print("✅ 單位轉換修正成功！")
        print(f"{'=' * 60}")
        
        # 顯示前 5 小時預測
        print("\n前 5 小時預測詳情:")
        for i, item in enumerate(forecast_data[:5]):
            print(f"  {item['timestamp']}: {item['predicted_load_kw']:.2f} kW")
        
        sys.exit(0)
    else:
        print(f"⚠️  預測值仍然異常: {avg_load:.2f} kW")
        print("需要進一步檢查模型訓練...")
        print(f"{'=' * 60}")
        sys.exit(1)
else:
    print(f"\n✗ 無法取得預測結果: {results_response.status_code}")
    sys.exit(1)
