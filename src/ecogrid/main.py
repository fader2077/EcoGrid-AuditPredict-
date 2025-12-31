"""
EcoGrid Audit Predict - Main Application
主程式入口，整合所有模組執行完整流程
"""

import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import pandas as pd
import numpy as np
from loguru import logger

# 忽略不必要的警告
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=UserWarning)

from ecogrid.config.settings import settings
from ecogrid.utils.helpers import (
    setup_logging, 
    get_device_info, 
    create_directories,
    print_banner,
    clear_gpu_memory
)
from ecogrid.data.etl_pipeline import ETLPipeline
from ecogrid.models.hybrid_engine import HybridPredictiveEngine
from ecogrid.optimization.tou_optimizer import TOUOptimizer
from ecogrid.llm.agent import EcoGridAuditAgent
from ecogrid.llm.tools import AuditTools


class EcoGridSystem:
    """
    EcoGrid 系統主類別
    整合 ETL、預測、優化、LLM 審計所有模組
    """
    
    def __init__(self):
        # 初始化
        print_banner()
        setup_logging()
        create_directories()
        
        # 顯示設備資訊
        device_info = get_device_info()
        logger.info(f"Device Info: {device_info}")
        
        # 初始化模組
        self.etl_pipeline = ETLPipeline()
        self.predictive_engine = HybridPredictiveEngine()
        self.optimizer = TOUOptimizer()
        self.audit_agent = EcoGridAuditAgent()
        self.audit_tools = AuditTools()
        
        # 資料儲存
        self.data: Optional[pd.DataFrame] = None
        self.predictions: Optional[pd.DataFrame] = None
        self.optimization_result: Optional[Dict[str, Any]] = None
        
        logger.info("EcoGrid System initialized successfully")
    
    def run_etl(self, days: int = 30) -> pd.DataFrame:
        """
        執行 ETL 流程
        
        Args:
            days: 歷史資料天數
            
        Returns:
            處理後的資料
        """
        logger.info("=" * 60)
        logger.info("PHASE 1: ETL Pipeline")
        logger.info("=" * 60)
        
        self.data, output_path = self.etl_pipeline.run_pipeline(days)
        
        logger.info(f"ETL Complete - Data shape: {self.data.shape}")
        logger.info(f"Output saved to: {output_path}")
        
        return self.data
    
    def run_prediction(self, use_transformer: bool = True, 
                       use_lstm: bool = True) -> pd.DataFrame:
        """
        執行預測
        
        Args:
            use_transformer: 是否使用 Transformer
            use_lstm: 是否使用 LSTM
            
        Returns:
            預測結果
        """
        logger.info("=" * 60)
        logger.info("PHASE 2: AI Predictive Engine")
        logger.info("=" * 60)
        
        if self.data is None:
            logger.warning("No data available, running ETL first")
            self.run_etl()
        
        # 清理 GPU 記憶體
        clear_gpu_memory()
        
        # 訓練模型
        logger.info("Training predictive models...")
        self.predictive_engine.fit(
            self.data, 
            use_transformer=use_transformer,
            use_lstm=use_lstm
        )
        
        # 執行滾動式預測
        logger.info("Running rolling forecast...")
        self.predictions = self.predictive_engine.rolling_forecast(
            self.data, 
            hours_ahead=24
        )
        
        if not self.predictions.empty:
            # 獲取預測摘要
            summary = self.predictive_engine.get_prediction_summary(self.predictions)
            logger.info(f"Prediction Summary:")
            logger.info(f"  - Avg Load: {summary['load']['avg_mw']:.2f} MW")
            logger.info(f"  - Peak Hour: {summary['load']['peak_hour']}:00")
            logger.info(f"  - Solar Total: {summary['solar']['total_mwh']:.2f} MWh")
            logger.info(f"  - Renewable Ratio: {summary['renewable_ratio']:.1f}%")
        
        # 儲存模型
        self.predictive_engine.save_all_models()
        
        return self.predictions
    
    def run_optimization(self, initial_soc: float = 0.5) -> Dict[str, Any]:
        """
        執行優化
        
        Args:
            initial_soc: 初始電池狀態
            
        Returns:
            優化結果
        """
        logger.info("=" * 60)
        logger.info("PHASE 3: TOU Optimization")
        logger.info("=" * 60)
        
        if self.predictions is None or self.predictions.empty:
            logger.warning("No predictions available, running prediction first")
            self.run_prediction()
        
        # 執行優化
        self.optimization_result = self.optimizer.optimize_schedule(
            self.predictions,
            initial_soc=initial_soc
        )
        
        result = self.optimization_result['result']
        summary = self.optimization_result['summary']
        
        logger.info(f"Optimization Results:")
        logger.info(f"  - Status: {result.status}")
        logger.info(f"  - Baseline Cost: NTD {summary['baseline_cost']:,.0f}")
        logger.info(f"  - Optimized Cost: NTD {summary['total_cost']:,.0f}")
        logger.info(f"  - Savings: NTD {summary['savings']:,.0f} ({summary['savings_percent']:.1f}%)")
        logger.info(f"  - Peak Reduction: {summary['peak_reduction']:.1f}%")
        
        logger.info("Recommendations:")
        for i, rec in enumerate(result.recommendations, 1):
            logger.info(f"  {i}. {rec}")
        
        return self.optimization_result
    
    def generate_audit_report(self) -> str:
        """
        生成審計報告
        
        Returns:
            審計報告文本
        """
        logger.info("=" * 60)
        logger.info("PHASE 4: LLM Audit Report Generation")
        logger.info("=" * 60)
        
        # 準備報告數據
        prediction_data = {}
        optimization_data = {}
        
        if self.predictions is not None and not self.predictions.empty:
            prediction_data = {
                "forecast_hours": len(self.predictions),
                "total_consumption_kwh": float(self.predictions['predicted_load_mw'].sum() * 1000),
                "avg_load_kw": float(self.predictions['predicted_load_mw'].mean() * 1000),
                "peak_load_kw": float(self.predictions['predicted_load_mw'].max() * 1000),
                "renewable_kwh": float(
                    (self.predictions['predicted_solar_mw'].sum() + 
                     self.predictions['predicted_wind_mw'].sum()) * 1000
                )
            }
        
        if self.optimization_result:
            optimization_data = self.optimization_result['summary']
        
        # 測試 LLM 連接
        logger.info("Testing LLM connection...")
        if self.audit_agent.test_connection():
            logger.info("LLM connection successful")
            report = self.audit_agent.generate_audit_report(
                prediction_data,
                optimization_data
            )
        else:
            logger.warning("LLM connection failed, generating fallback report")
            report = self._generate_fallback_report(prediction_data, optimization_data)
        
        # 儲存報告
        report_path = settings.project_root / "reports"
        report_path.mkdir(exist_ok=True)
        report_file = report_path / f"audit_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        report_file.write_text(report, encoding='utf-8')
        logger.info(f"Report saved to: {report_file}")
        
        return report
    
    def _generate_fallback_report(self, prediction_data: Dict, 
                                   optimization_data: Dict) -> str:
        """生成備用報告（當 LLM 不可用時）"""
        
        # 使用 AuditTools 進行計算
        carbon_result = {}
        savings_result = {}
        renewable_result = {}
        
        if prediction_data.get('total_consumption_kwh'):
            carbon_result = self.audit_tools.calculate_carbon_emission(
                prediction_data['total_consumption_kwh']
            )
        
        if optimization_data.get('baseline_cost') and optimization_data.get('total_cost'):
            savings_result = self.audit_tools.calculate_savings(
                optimization_data['baseline_cost'],
                optimization_data['total_cost']
            )
        
        if prediction_data.get('total_consumption_kwh') and prediction_data.get('renewable_kwh'):
            renewable_result = self.audit_tools.calculate_renewable_offset(
                prediction_data['total_consumption_kwh'],
                prediction_data['renewable_kwh']
            )
        
        report = f"""# EcoGrid 用電審計報告

**報告生成時間**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 1. 執行摘要

本報告基於 EcoGrid 系統的預測與優化結果自動生成。

## 2. 用電分析

### 預測數據
- 預測時間範圍: {prediction_data.get('forecast_hours', 'N/A')} 小時
- 預估總用電量: {prediction_data.get('total_consumption_kwh', 0):,.0f} kWh
- 平均負載: {prediction_data.get('avg_load_kw', 0):,.0f} kW
- 尖峰負載: {prediction_data.get('peak_load_kw', 0):,.0f} kW

### 再生能源使用
- 再生能源發電量: {prediction_data.get('renewable_kwh', 0):,.0f} kWh
- 綠電比例: {renewable_result.get('renewable_ratio_percent', 0):.1f}%

## 3. 優化成效

### 成本分析
- 基準成本: NTD {optimization_data.get('baseline_cost', 0):,.0f}
- 優化後成本: NTD {optimization_data.get('total_cost', 0):,.0f}
- 節省金額: NTD {savings_result.get('savings_ntd', 0):,.0f}
- 節省比例: {savings_result.get('savings_percent', 0):.1f}%
- 年度節省估算: NTD {savings_result.get('annual_savings_estimate_ntd', 0):,.0f}

### 削峰效果
- 尖峰負載降低: {optimization_data.get('peak_reduction', 0):.1f}%

## 4. 碳排與 ESG

### 碳排放量
- 總碳排放量: {carbon_result.get('emission_kg_co2', 0):,.0f} kg CO2
- 排碳係數: {carbon_result.get('emission_factor_kg_co2_kwh', 0.494)} kg CO2/kWh

### 再生能源抵減
- 碳排減少量: {renewable_result.get('emission_reduction_kg_co2', 0):,.0f} kg CO2

## 5. 建議事項

### 優化系統建議
"""
        
        # 添加優化建議
        recommendations = optimization_data.get('recommendations', [])
        if recommendations:
            for i, rec in enumerate(recommendations, 1):
                report += f"{i}. {rec}\n"
        else:
            report += "1. 建議安裝儲能系統以實現更大的成本優化\n"
            report += "2. 考慮將非關鍵負載移至離峰時段\n"
            report += "3. 定期監控設備用電狀況，及早發現異常\n"
        
        report += """
## 6. 下一步行動

1. **短期 (1-2週)**: 
   - 檢視尖峰時段用電設備
   - 調整空調溫度設定

2. **中期 (1-3月)**:
   - 評估儲能系統投資效益
   - 建立用電監控儀表板

3. **長期 (6-12月)**:
   - 導入智慧能源管理系統
   - 評估再生能源投資

---

*本報告由 EcoGrid Audit Predict 系統自動生成*
*如需更詳細的分析，請確保 Ollama LLM 服務正常運行*
"""
        
        return report
    
    def run_full_pipeline(self, days: int = 30, 
                          use_transformer: bool = True,
                          use_lstm: bool = True,
                          initial_soc: float = 0.5) -> Dict[str, Any]:
        """
        執行完整流程
        
        Args:
            days: 歷史資料天數
            use_transformer: 是否使用 Transformer
            use_lstm: 是否使用 LSTM
            initial_soc: 初始電池狀態
            
        Returns:
            完整執行結果
        """
        logger.info("=" * 60)
        logger.info("Starting EcoGrid Full Pipeline")
        logger.info("=" * 60)
        
        start_time = datetime.now()
        
        results = {
            "start_time": start_time.isoformat(),
            "status": "running"
        }
        
        try:
            # Phase 1: ETL
            self.run_etl(days)
            results["etl_status"] = "success"
            results["data_rows"] = len(self.data)
            
            # Phase 2: Prediction
            self.run_prediction(use_transformer, use_lstm)
            results["prediction_status"] = "success"
            results["prediction_hours"] = len(self.predictions) if self.predictions is not None else 0
            
            # Phase 3: Optimization
            opt_result = self.run_optimization(initial_soc)
            results["optimization_status"] = "success"
            results["optimization_summary"] = opt_result['summary']
            
            # Phase 4: Report Generation
            report = self.generate_audit_report()
            results["report_status"] = "success"
            results["report_length"] = len(report)
            
            results["status"] = "completed"
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            results["status"] = "failed"
            results["error"] = str(e)
        
        end_time = datetime.now()
        results["end_time"] = end_time.isoformat()
        results["duration_seconds"] = (end_time - start_time).total_seconds()
        
        logger.info("=" * 60)
        logger.info(f"Pipeline {results['status'].upper()}")
        logger.info(f"Duration: {results['duration_seconds']:.1f} seconds")
        logger.info("=" * 60)
        
        return results
    
    def interactive_mode(self):
        """互動模式 - 與 LLM 對話"""
        logger.info("Entering interactive mode...")
        print("\n" + "=" * 60)
        print("EcoGrid 互動模式")
        print("輸入問題與系統對話，輸入 'quit' 退出")
        print("=" * 60 + "\n")
        
        while True:
            try:
                user_input = input("您: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("退出互動模式")
                    break
                
                if not user_input:
                    continue
                
                response = self.audit_agent.chat(user_input)
                print(f"\nEcoGrid: {response}\n")
                
            except KeyboardInterrupt:
                print("\n退出互動模式")
                break
            except Exception as e:
                print(f"錯誤: {e}")


def main():
    """主程式入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="EcoGrid Audit Predict System")
    parser.add_argument("--mode", type=str, default="full", 
                       choices=["full", "etl", "predict", "optimize", "interactive"],
                       help="執行模式")
    parser.add_argument("--days", type=int, default=30, help="歷史資料天數")
    parser.add_argument("--no-transformer", action="store_true", help="不使用 Transformer")
    parser.add_argument("--no-lstm", action="store_true", help="不使用 LSTM")
    parser.add_argument("--soc", type=float, default=0.5, help="初始電池狀態 (0-1)")
    
    args = parser.parse_args()
    
    # 初始化系統
    system = EcoGridSystem()
    
    if args.mode == "full":
        system.run_full_pipeline(
            days=args.days,
            use_transformer=not args.no_transformer,
            use_lstm=not args.no_lstm,
            initial_soc=args.soc
        )
    elif args.mode == "etl":
        system.run_etl(args.days)
    elif args.mode == "predict":
        system.run_etl(args.days)
        system.run_prediction(not args.no_transformer, not args.no_lstm)
    elif args.mode == "optimize":
        system.run_etl(args.days)
        system.run_prediction(not args.no_transformer, not args.no_lstm)
        system.run_optimization(args.soc)
    elif args.mode == "interactive":
        system.run_etl(args.days)
        system.run_prediction(not args.no_transformer, not args.no_lstm)
        system.run_optimization(args.soc)
        system.interactive_mode()


if __name__ == "__main__":
    main()
