"""
快速測試 Backend API（無需完整測試腳本）
"""

import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

print("=" * 60)
print("快速測試 EcoGrid Backend API")
print("=" * 60)

# 1. 測試 Dashboard Summary
print("\n1. 測試 Dashboard Summary...")
try:
    response = requests.get(f"{BASE_URL}/dashboard/summary", timeout=5)
    if response.status_code == 200:
        data = response.json()
        print(f"✓ 成功！當前負載: {data.get('current_load_kw', 0):.2f} kW")
        print(f"  綠電比例: {data.get('renewable_ratio_percent', 0):.2f}%")
        print(f"  今日成本: ${data.get('today_cost_ntd', 0):.2f} NTD")
    else:
        print(f"✗ 失敗: {response.status_code}")
except Exception as e:
    print(f"✗ 錯誤: {e}")

# 2. 測試 Dashboard Chart Data
print("\n2. 測試 Dashboard Chart Data...")
try:
    response = requests.post(
        f"{BASE_URL}/dashboard/chart-data",
        json={"hours": 24},
        timeout=5
    )
    if response.status_code == 200:
        data = response.json()
        print(f"✓ 成功！時間點數量: {len(data.get('timestamps', []))}")
    else:
        print(f"✗ 失敗: {response.status_code}")
except Exception as e:
    print(f"✗ 錯誤: {e}")

# 3. 測試 GPU
print("\n3. 測試 GPU 可用性...")
try:
    import torch
    if torch.cuda.is_available():
        print(f"✓ CUDA 可用: {torch.cuda.get_device_name(0)}")
        memory_allocated = torch.cuda.memory_allocated(0) / 1024**3
        memory_total = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"  GPU 記憶體: {memory_allocated:.2f} GB / {memory_total:.2f} GB")
    else:
        print("⚠ CUDA 不可用，將使用 CPU")
except Exception as e:
    print(f"✗ 錯誤: {e}")

# 4. 測試 Ollama
print("\n4. 測試 Ollama 連接...")
try:
    response = requests.get("http://localhost:11434/api/tags", timeout=3)
    if response.status_code == 200:
        models = response.json().get('models', [])
        print(f"✓ Ollama 運行中，已安裝 {len(models)} 個模型")
        for model in models:
            print(f"  - {model.get('name', 'Unknown')}")
    else:
        print(f"✗ Ollama 連接失敗: {response.status_code}")
except Exception as e:
    print("⚠ Ollama 未運行，請執行: ollama serve")

print("\n" + "=" * 60)
print("測試完成！")
print("=" * 60)
