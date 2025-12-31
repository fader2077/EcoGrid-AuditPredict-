"""
EcoGrid Audit Predict - API 測試腳本
測試 FastAPI Backend 所有端點
"""

import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any

# API 基礎 URL
BASE_URL = "http://localhost:8000/api/v1"

# 顏色輸出
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def print_success(msg: str):
    try:
        print(f"{Colors.GREEN}[OK] {msg}{Colors.RESET}")
    except:
        print(f"[OK] {msg}")

def print_error(msg: str):
    try:
        print(f"{Colors.RED}[ERROR] {msg}{Colors.RESET}")
    except:
        print(f"[ERROR] {msg}")

def print_info(msg: str):
    try:
        print(f"{Colors.BLUE}[INFO] {msg}{Colors.RESET}")
    except:
        print(f"[INFO] {msg}")

def print_warning(msg: str):
    try:
        print(f"{Colors.YELLOW}[WARNING] {msg}{Colors.RESET}")
    except:
        print(f"[WARNING] {msg}")

def test_server_health():
    """測試伺服器是否運行"""
    print("\n" + "="*60)
    print("測試 1: 伺服器健康檢查")
    print("="*60)
    
    try:
        response = requests.get(f"http://localhost:8000/docs", timeout=5)
        if response.status_code == 200:
            print_success("Backend 伺服器運行正常")
            print_info(f"Swagger 文檔: http://localhost:8000/docs")
            return True
        else:
            print_error(f"伺服器返回狀態碼: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_error("無法連接到 Backend 伺服器")
        print_warning("請確認 Backend 是否在運行: cd backend && python -m uvicorn main:app --reload")
        return False
    except Exception as e:
        print_error(f"連接錯誤: {str(e)}")
        return False

def test_dashboard_summary():
    """測試 Dashboard 摘要"""
    print("\n" + "="*60)
    print("測試 2: Dashboard 摘要")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/dashboard/summary", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print_success("Dashboard API 回應成功")
            print_info(f"當前負載: {data.get('current_load_kw', 0):.2f} kW")
            print_info(f"綠電比例: {data.get('renewable_ratio_percent', 0):.2f}%")
            print_info(f"今日成本: ${data.get('today_cost_ntd', 0):.2f} NTD")
            print_info(f"電池狀態: {data.get('battery_soc_percent', 0):.2f}%")
            print_info(f"TOU 時段: {data.get('tou_period', 'N/A')}")
            return True
        else:
            print_error(f"API 返回錯誤: {response.status_code}")
            print_error(f"回應內容: {response.text}")
            return False
    except Exception as e:
        print_error(f"測試失敗: {str(e)}")
        return False

def test_dashboard_chart():
    """測試 Dashboard 圖表數據"""
    print("\n" + "="*60)
    print("測試 3: Dashboard 圖表數據")
    print("="*60)
    
    payload = {
        "hours": 24
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/dashboard/chart-data",
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("圖表數據 API 回應成功")
            print_info(f"時間點數量: {len(data.get('timestamps', []))}")
            
            series = data.get('series', {})
            for key, values in series.items():
                if values:
                    avg = sum(values) / len(values)
                    print_info(f"{key} 平均值: {avg:.2f}")
            return True
        else:
            print_error(f"API 返回錯誤: {response.status_code}")
            print_error(f"回應內容: {response.text}")
            return False
    except Exception as e:
        print_error(f"測試失敗: {str(e)}")
        return False

def test_forecast_predict():
    """測試 AI 預測（異步）"""
    print("\n" + "="*60)
    print("測試 4: AI 負載預測")
    print("="*60)
    
    payload = {
        "hours_ahead": 24,
        "use_transformer": False,
        "use_lstm": False
    }
    
    try:
        # 1. 創建預測任務
        print_info("創建預測任務...")
        response = requests.post(
            f"{BASE_URL}/forecast/predict",
            json=payload,
            timeout=10
        )
        
        if response.status_code != 200:
            print_error(f"創建任務失敗: {response.status_code}")
            print_error(f"回應內容: {response.text}")
            return False
        
        data = response.json()
        task_id = data.get('task_id')
        print_success(f"任務已創建: {task_id}")
        
        # 2. 輪詢任務狀態
        print_info("等待預測完成...")
        max_attempts = 60  # 最多等待 60 秒
        for attempt in range(max_attempts):
            time.sleep(1)
            
            status_response = requests.get(
                f"{BASE_URL}/forecast/predict/{task_id}",
                timeout=10
            )
            
            if status_response.status_code != 200:
                print_error(f"查詢狀態失敗: {status_response.status_code}")
                return False
            
            status_data = status_response.json()
            status = status_data.get('status')
            progress = status_data.get('progress', 0)
            
            print(f"\r進度: {progress:.1f}% - 狀態: {status}", end='', flush=True)
            
            if status == 'completed':
                print()  # 換行
                print_success("預測完成！")
                
                result = status_data.get('result', {})
                print_info(f"預測數量: {result.get('forecast_count', 0)} 筆")
                print_info(f"平均負載: {result.get('avg_load_kw', 0):.2f} kW")
                
                # 3. 獲取最新預測結果
                latest_response = requests.get(
                    f"{BASE_URL}/forecast/latest",
                    params={"limit": 5},
                    timeout=10
                )
                
                if latest_response.status_code == 200:
                    latest_data = latest_response.json()
                    print_info(f"最新預測記錄: {len(latest_data)} 筆")
                
                return True
            
            elif status == 'failed':
                print()  # 換行
                error_msg = status_data.get('error_message', 'Unknown error')
                print_error(f"預測失敗: {error_msg}")
                return False
        
        print()  # 換行
        print_warning("任務超時")
        return False
        
    except Exception as e:
        print_error(f"測試失敗: {str(e)}")
        return False

def test_optimization():
    """測試 TOU 優化（異步）"""
    print("\n" + "="*60)
    print("測試 5: TOU 時間電價優化")
    print("="*60)
    
    payload = {
        "hours_ahead": 24,
        "initial_soc": 0.5,
        "battery_capacity_kwh": 100.0,
        "max_contract_kw": 500.0
    }
    
    try:
        # 1. 創建優化任務
        print_info("創建優化任務...")
        response = requests.post(
            f"{BASE_URL}/optimization/optimize",
            json=payload,
            timeout=10
        )
        
        if response.status_code != 200:
            print_error(f"創建任務失敗: {response.status_code}")
            print_error(f"回應內容: {response.text}")
            return False
        
        data = response.json()
        task_id = data.get('task_id')
        print_success(f"任務已創建: {task_id}")
        
        # 2. 輪詢任務狀態
        print_info("等待優化完成...")
        max_attempts = 60
        for attempt in range(max_attempts):
            time.sleep(1)
            
            status_response = requests.get(
                f"{BASE_URL}/optimization/optimize/{task_id}",
                timeout=10
            )
            
            if status_response.status_code != 200:
                print_error(f"查詢狀態失敗: {status_response.status_code}")
                return False
            
            status_data = status_response.json()
            status = status_data.get('status')
            progress = status_data.get('progress', 0)
            
            print(f"\r進度: {progress:.1f}% - 狀態: {status}", end='', flush=True)
            
            if status == 'completed':
                print()  # 換行
                print_success("優化完成！")
                
                result = status_data.get('result', {})
                plan_id = result.get('plan_id')
                
                # 3. 獲取優化計劃詳情
                if plan_id:
                    plan_response = requests.get(
                        f"{BASE_URL}/optimization/plan/{plan_id}",
                        timeout=10
                    )
                    
                    if plan_response.status_code == 200:
                        plan_data = plan_response.json()
                        print_info(f"基準成本: ${plan_data.get('baseline_cost_ntd', 0):.2f} NTD")
                        print_info(f"優化成本: ${plan_data.get('optimized_cost_ntd', 0):.2f} NTD")
                        print_info(f"節省金額: ${plan_data.get('savings_ntd', 0):.2f} NTD")
                        print_info(f"節省比例: {plan_data.get('savings_percent', 0):.2f}%")
                        print_info(f"削峰比例: {plan_data.get('peak_reduction_percent', 0):.2f}%")
                
                return True
            
            elif status == 'failed':
                print()  # 換行
                error_msg = status_data.get('error_message', 'Unknown error')
                print_error(f"優化失敗: {error_msg}")
                return False
        
        print()  # 換行
        print_warning("任務超時")
        return False
        
    except Exception as e:
        print_error(f"測試失敗: {str(e)}")
        return False

def test_audit_generate():
    """測試 LLM 審計報告生成（異步）"""
    print("\n" + "="*60)
    print("測試 6: LLM 審計報告生成")
    print("="*60)
    
    # 計算日期範圍（最近 7 天）
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    payload = {
        "report_type": "weekly",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "include_recommendations": True
    }
    
    try:
        # 1. 創建報告生成任務
        print_info("創建報告生成任務...")
        response = requests.post(
            f"{BASE_URL}/audit/generate",
            json=payload,
            timeout=10
        )
        
        if response.status_code != 200:
            print_error(f"創建任務失敗: {response.status_code}")
            print_error(f"回應內容: {response.text}")
            return False
        
        data = response.json()
        task_id = data.get('task_id')
        print_success(f"任務已創建: {task_id}")
        
        # 2. 輪詢任務狀態（LLM 生成較慢）
        print_info("等待 LLM 生成報告...")
        max_attempts = 120  # 最多等待 120 秒
        for attempt in range(max_attempts):
            time.sleep(2)
            
            status_response = requests.get(
                f"{BASE_URL}/audit/generate/{task_id}",
                timeout=10
            )
            
            if status_response.status_code != 200:
                print_error(f"查詢狀態失敗: {status_response.status_code}")
                return False
            
            status_data = status_response.json()
            status = status_data.get('status')
            progress = status_data.get('progress', 0)
            
            print(f"\r進度: {progress:.1f}% - 狀態: {status}", end='', flush=True)
            
            if status == 'completed':
                print()  # 換行
                print_success("報告生成完成！")
                
                result = status_data.get('result', {})
                report_id = result.get('report_id')
                
                # 3. 獲取報告內容
                if report_id:
                    report_response = requests.get(
                        f"{BASE_URL}/audit/report/{report_id}",
                        timeout=10
                    )
                    
                    if report_response.status_code == 200:
                        report_data = report_response.json()
                        print_info(f"報告類型: {report_data.get('report_type', 'N/A')}")
                        print_info(f"總用電量: {report_data.get('total_consumption_kwh', 0):.2f} kWh")
                        print_info(f"總成本: ${report_data.get('total_cost_ntd', 0):.2f} NTD")
                        print_info(f"綠電比例: {report_data.get('renewable_ratio_percent', 0):.2f}%")
                        print_info(f"碳排放: {report_data.get('carbon_emission_kg', 0):.2f} kg CO2")
                        print_info(f"LLM 模型: {report_data.get('llm_model', 'N/A')}")
                        
                        content = report_data.get('content_markdown', '')
                        if content:
                            print_info(f"報告內容長度: {len(content)} 字元")
                            print_info("報告預覽:")
                            print("-" * 60)
                            print(content[:500] + "..." if len(content) > 500 else content)
                            print("-" * 60)
                
                return True
            
            elif status == 'failed':
                print()  # 換行
                error_msg = status_data.get('error_message', 'Unknown error')
                print_error(f"報告生成失敗: {error_msg}")
                
                # 檢查是否為 Ollama 連接問題
                if 'ollama' in error_msg.lower() or 'connection' in error_msg.lower():
                    print_warning("可能是 Ollama 服務未啟動")
                    print_info("請執行: ollama serve")
                    print_info("並確認模型已安裝: ollama list")
                
                return False
        
        print()  # 換行
        print_warning("任務超時")
        return False
        
    except Exception as e:
        print_error(f"測試失敗: {str(e)}")
        return False

def test_audit_query():
    """測試 Chat Assistant 互動式查詢"""
    print("\n" + "="*60)
    print("測試 7: Chat Assistant 互動式查詢")
    print("="*60)
    
    payload = {
        "question": "為什麼今天下午的電費比較高？"
    }
    
    try:
        print_info(f"提問: {payload['question']}")
        response = requests.post(
            f"{BASE_URL}/audit/query",
            json=payload,
            timeout=60  # LLM 回應可能較慢
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("Chat Assistant 回應成功")
            print_info("回答:")
            print("-" * 60)
            print(data.get('answer', 'No answer'))
            print("-" * 60)
            return True
        else:
            print_error(f"API 返回錯誤: {response.status_code}")
            print_error(f"回應內容: {response.text}")
            
            if response.status_code == 503:
                print_warning("Ollama 服務可能未啟動")
                print_info("請執行: ollama serve")
            
            return False
    except requests.exceptions.Timeout:
        print_error("請求超時（LLM 回應時間過長）")
        return False
    except Exception as e:
        print_error(f"測試失敗: {str(e)}")
        return False

def check_gpu_usage():
    """檢查 GPU 使用情況"""
    print("\n" + "="*60)
    print("測試 8: GPU 使用情況檢查")
    print("="*60)
    
    try:
        import torch
        
        if torch.cuda.is_available():
            print_success(f"CUDA 可用: {torch.cuda.get_device_name(0)}")
            print_info(f"GPU 數量: {torch.cuda.device_count()}")
            
            # 記憶體使用情況
            for i in range(torch.cuda.device_count()):
                allocated = torch.cuda.memory_allocated(i) / 1024**3
                reserved = torch.cuda.memory_reserved(i) / 1024**3
                total = torch.cuda.get_device_properties(i).total_memory / 1024**3
                
                print_info(f"GPU {i}: 已分配 {allocated:.2f} GB / 已保留 {reserved:.2f} GB / 總共 {total:.2f} GB")
                
                # 檢查是否接近 OOM
                if allocated / total > 0.85:
                    print_warning(f"GPU {i} 記憶體使用率超過 85%，可能面臨 OOM 風險")
            
            return True
        else:
            print_warning("CUDA 不可用，將使用 CPU")
            return True
    except ImportError:
        print_warning("PyTorch 未安裝，無法檢查 GPU")
        return True
    except Exception as e:
        print_error(f"GPU 檢查失敗: {str(e)}")
        return False

def check_ollama_connection():
    """檢查 Ollama 連接"""
    print("\n" + "="*60)
    print("測試 9: Ollama LLM 連接檢查")
    print("="*60)
    
    try:
        # 嘗試連接 Ollama API
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            models = data.get('models', [])
            
            print_success("Ollama 服務運行正常")
            print_info(f"已安裝模型數量: {len(models)}")
            
            for model in models:
                model_name = model.get('name', 'Unknown')
                print_info(f"  - {model_name}")
            
            # 檢查是否有 llama3.2
            has_llama = any('llama3.2' in model.get('name', '') for model in models)
            if has_llama:
                print_success("llama3.2 模型已安裝")
            else:
                print_warning("未找到 llama3.2 模型")
                print_info("請執行: ollama pull llama3.2")
            
            return True
        else:
            print_error(f"Ollama API 返回錯誤: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_error("無法連接到 Ollama 服務")
        print_warning("請啟動 Ollama: ollama serve")
        print_info("或在新終端執行: ollama run llama3.2")
        return False
    except Exception as e:
        print_error(f"Ollama 檢查失敗: {str(e)}")
        return False

def main():
    """主測試函數"""
    print("\n" + "="*60)
    print("EcoGrid Audit Predict - API 完整測試")
    print("="*60)
    print(f"測試時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API 端點: {BASE_URL}")
    
    results = []
    
    # 基礎檢查
    results.append(("[1] 伺服器健康檢查", test_server_health()))
    
    if not results[-1][1]:
        print_error("\nBackend 伺服器未運行，測試中止")
        print_info("請先啟動 Backend:")
        print_info("  cd backend")
        print_info("  python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000")
        return
    
    # GPU 和 Ollama 檢查
    results.append(("[2] GPU 使用情況", check_gpu_usage()))
    results.append(("[3] Ollama 連接", check_ollama_connection()))
    
    # Dashboard API
    results.append(("[4] Dashboard 摘要", test_dashboard_summary()))
    results.append(("[5] Dashboard 圖表", test_dashboard_chart()))
    
    # AI 預測 API
    results.append(("[6] AI 負載預測", test_forecast_predict()))
    
    # TOU 優化 API
    results.append(("[7] TOU 優化", test_optimization()))
    
    # LLM 審計 API（需要 Ollama）
    if results[2][1]:  # 如果 Ollama 可用
        results.append(("[8] LLM 報告生成", test_audit_generate()))
        results.append(("[9] Chat Assistant", test_audit_query()))
    else:
        print_warning("\nOllama 不可用，跳過 LLM 相關測試")
    
    # 測試結果總結
    print("\n" + "="*60)
    print("測試結果總結")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        color = Colors.GREEN if result else Colors.RED
        try:
            print(f"{color}{status}{Colors.RESET} - {test_name}")
        except:
            print(f"{status} - {test_name}")
    
    print("\n" + "-"*60)
    print(f"通過: {passed}/{total} ({passed/total*100:.1f}%)")
    
    if passed == total:
        print_success("\n所有測試通過！")
    else:
        print_warning(f"\n{total - passed} 個測試失敗")

if __name__ == "__main__":
    main()
