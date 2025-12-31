"""
EcoGrid System Runner - 簡化執行腳本
用於測試和演示系統功能
"""

import sys
import os

# 添加 src 到路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import warnings
warnings.filterwarnings('ignore')

from datetime import datetime
import pandas as pd
import numpy as np

def run_demo():
    """執行演示流程"""
    print("=" * 70)
    print("EcoGrid Audit Predict - 綠電優化與用電審計預測系統")
    print("=" * 70)
    print()
    
    # Step 1: 檢查依賴
    print("[Step 1] 檢查系統依賴...")
    check_dependencies()
    
    # Step 2: 初始化設定
    print("\n[Step 2] 初始化系統設定...")
    from ecogrid.config.settings import settings
    from ecogrid.utils.helpers import setup_logging, create_directories, get_device_info
    
    setup_logging()
    create_directories()
    
    device_info = get_device_info()
    print(f"  - CUDA 可用: {device_info['cuda_available']}")
    if device_info['cuda_available']:
        print(f"  - GPU: {device_info['device_name']}")
        print(f"  - GPU 記憶體: {device_info['memory_total']}")
    
    # Step 3: ETL 流程
    print("\n[Step 3] 執行 ETL 資料管道...")
    from ecogrid.data.etl_pipeline import ETLPipeline
    
    etl = ETLPipeline()
    data, output_path = etl.run_pipeline(days=30)  # 使用 30 天資料加快演示
    print(f"  - 資料筆數: {len(data)}")
    print(f"  - 特徵數量: {len(data.columns)}")
    print(f"  - 資料儲存: {output_path}")
    
    # Step 4: AI 預測引擎
    print("\n[Step 4] 訓練 AI 預測模型...")
    from ecogrid.models.hybrid_engine import HybridPredictiveEngine
    
    engine = HybridPredictiveEngine()
    
    # 使用較少的參數加快訓練
    engine.fit(
        data,
        use_transformer=False,  # 先不使用 Transformer 加快演示
        use_lstm=False,  # 先不使用 LSTM 加快演示
        n_estimators=50,  # 減少樹的數量
        epochs=10
    )
    
    # 滾動式預測
    print("\n[Step 5] 執行滾動式預測...")
    predictions = engine.rolling_forecast(data, hours_ahead=24)
    
    if not predictions.empty:
        summary = engine.get_prediction_summary(predictions)
        print(f"  - 預測時間: 未來 {len(predictions)} 小時")
        print(f"  - 平均負載: {summary['load']['avg_mw']:.2f} MW")
        print(f"  - 尖峰時段: {summary['load']['peak_hour']}:00")
        print(f"  - 太陽能總量: {summary['solar']['total_mwh']:.2f} MWh")
        print(f"  - 綠電比例: {summary['renewable_ratio']:.1f}%")
    
    # Step 6: TOU 優化
    print("\n[Step 6] 執行時間電價優化...")
    from ecogrid.optimization.tou_optimizer import TOUOptimizer
    
    optimizer = TOUOptimizer()
    opt_result = optimizer.optimize_schedule(predictions, initial_soc=0.5)
    
    result = opt_result['result']
    opt_summary = opt_result['summary']
    
    print(f"  - 優化狀態: {result.status}")
    print(f"  - 基準成本: NTD {opt_summary['baseline_cost']:,.0f}")
    print(f"  - 優化成本: NTD {opt_summary['total_cost']:,.0f}")
    print(f"  - 節省金額: NTD {opt_summary['savings']:,.0f} ({opt_summary['savings_percent']:.1f}%)")
    print(f"  - 削峰效果: {opt_summary['peak_reduction']:.1f}%")
    
    print("\n  優化建議:")
    for i, rec in enumerate(result.recommendations[:3], 1):
        print(f"    {i}. {rec}")
    
    # Step 7: LLM 審計工具演示
    print("\n[Step 7] 審計工具計算演示...")
    from ecogrid.llm.tools import AuditTools
    
    tools = AuditTools()
    
    # 電費計算
    cost_result = tools.calculate_electricity_cost(
        consumption_kwh=1000,
        tariff_rate=5.80
    )
    print(f"  - 電費計算: {cost_result['calculation']}")
    
    # 碳排計算
    carbon_result = tools.calculate_carbon_emission(consumption_kwh=10000)
    print(f"  - 碳排計算: {carbon_result['calculation']}")
    
    # 負載移轉效益
    shift_result = tools.estimate_shift_benefit(
        consumption_kwh=500,
        from_period="peak",
        to_period="off_peak",
        is_summer=True
    )
    print(f"  - 負載移轉: 將 500 kWh 從尖峰移至離峰")
    print(f"    - 節省: NTD {shift_result['savings_ntd']:,.0f}")
    print(f"    - 年度估算: NTD {shift_result['annual_estimate_ntd']:,.0f}")
    
    # Step 8: LLM Agent 測試
    print("\n[Step 8] 測試 LLM Agent 連接...")
    from ecogrid.llm.agent import EcoGridAuditAgent
    
    agent = EcoGridAuditAgent()
    
    if agent.test_connection():
        print("  - Ollama LLM 連接成功!")
        print("  - 可使用 interactive 模式進行對話")
    else:
        print("  - Ollama LLM 連接失敗")
        print("  - 請確認:")
        print("    1. Ollama 服務已啟動 (ollama serve)")
        print("    2. 模型已下載 (ollama pull llama3.2)")
    
    # 完成
    print("\n" + "=" * 70)
    print("演示完成!")
    print("=" * 70)
    print()
    print("後續操作:")
    print("  1. 完整執行: python run_demo.py --full")
    print("  2. 互動模式: python -m ecogrid.main --mode interactive")
    print("  3. 查看報告: reports/ 目錄")
    print()
    
    return {
        "data_rows": len(data),
        "prediction_hours": len(predictions),
        "baseline_cost": opt_summary['baseline_cost'],
        "optimized_cost": opt_summary['total_cost'],
        "savings": opt_summary['savings']
    }


def check_dependencies():
    """檢查必要依賴"""
    dependencies = {
        "pandas": "資料處理",
        "numpy": "數值計算",
        "torch": "深度學習",
        "sklearn": "機器學習",
        "xgboost": "XGBoost",
        "lightgbm": "LightGBM",
        "pulp": "優化求解",
        "langchain": "LLM框架",
        "loguru": "日誌系統",
        "httpx": "HTTP客戶端"
    }
    
    missing = []
    for pkg, desc in dependencies.items():
        try:
            if pkg == "sklearn":
                __import__("sklearn")
            else:
                __import__(pkg)
            print(f"  ✓ {pkg} ({desc})")
        except ImportError:
            print(f"  ✗ {pkg} ({desc}) - 未安裝")
            missing.append(pkg)
    
    if missing:
        print(f"\n警告: 缺少以下套件: {', '.join(missing)}")
        print("請執行: pip install -r requirements.txt")
        return False
    
    return True


def run_full_demo():
    """執行完整演示（包含 Transformer 和 LSTM）"""
    print("=" * 70)
    print("EcoGrid 完整流程演示")
    print("=" * 70)
    
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
    
    from ecogrid.main import EcoGridSystem
    
    system = EcoGridSystem()
    results = system.run_full_pipeline(
        days=30,
        use_transformer=True,
        use_lstm=True,
        initial_soc=0.5
    )
    
    print("\n執行結果:")
    print(f"  - 狀態: {results['status']}")
    print(f"  - 執行時間: {results['duration_seconds']:.1f} 秒")
    
    if results.get('optimization_summary'):
        print(f"  - 節省金額: NTD {results['optimization_summary']['savings']:,.0f}")
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="執行完整流程")
    args = parser.parse_args()
    
    if args.full:
        run_full_demo()
    else:
        run_demo()
