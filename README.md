# EcoGrid Audit Predict 🌱⚡

## 綠電優化與用電審計預測系統
Taiwan Green Energy Optimization & Power Audit Prediction System

### 系統概述

本系統專為台灣企業設計，在複雜的「時間電價 (TOU)」環境下，利用 AI 預測模型優化市電與再生能源配比，並透過 LLM (Agentic RAG) 生成專業用電審計報告。

### 核心功能

1. **Data Pipeline & ETL** - 台灣本土能源數據整合
2. **AI Predictive Engine** - 混合式預測引擎 (XGBoost/LightGBM/Prophet/Transformer)
3. **TOU Optimization** - 時間電價優化 (MILP)
4. **LLM-as-an-Analyst** - 智慧審計報告生成

### 專案結構

```
ecogrid-audit-predict/
├── src/
│   └── ecogrid/
│       ├── __init__.py
│       ├── main.py                 # 主程式入口
│       ├── config/                 # 配置管理
│       │   ├── __init__.py
│       │   └── settings.py
│       ├── data/                   # ETL 數據管道
│       │   ├── __init__.py
│       │   ├── etl_pipeline.py
│       │   ├── taiwan_power_api.py
│       │   ├── weather_api.py
│       │   └── cache_manager.py
│       ├── models/                 # AI 預測模型
│       │   ├── __init__.py
│       │   ├── base_model.py
│       │   ├── load_forecaster.py
│       │   ├── renewable_forecaster.py
│       │   └── hybrid_engine.py
│       ├── optimization/           # TOU 優化模組
│       │   ├── __init__.py
│       │   └── tou_optimizer.py
│       ├── llm/                    # LLM 審計系統
│       │   ├── __init__.py
│       │   ├── agent.py
│       │   ├── tools.py
│       │   └── prompts.py
│       └── utils/                  # 工具函數
│           ├── __init__.py
│           └── helpers.py
├── data/                           # 數據存儲
│   ├── raw/
│   ├── processed/
│   └── cache/
├── models/                         # 模型存儲
├── logs/                           # 日誌
├── tests/                          # 測試
├── notebooks/                      # Jupyter 筆記本
├── pyproject.toml
├── requirements.txt
└── README.md
```

### 安裝與設定

```bash
# 建立虛擬環境
python -m venv venv
venv\Scripts\activate  # Windows

# 安裝依賴
pip install -e .

# 設定環境變數
copy .env.example .env
# 編輯 .env 填入必要的 API Keys
```

### 環境變數

```env
# OpenAI API (LLM)
OPENAI_API_KEY=your_openai_api_key

# 台灣氣象署 API
CWA_API_KEY=your_cwa_api_key

# 系統設定
LOG_LEVEL=INFO
CACHE_ENABLED=true
GPU_MEMORY_FRACTION=0.7
```

### 使用方式

```python
from ecogrid.main import EcoGridSystem

# 初始化系統
system = EcoGridSystem()

# 執行完整流程
system.run_full_pipeline()

# 或分別執行各模組
system.run_etl()
system.run_prediction()
system.run_optimization()
system.generate_audit_report()
```

### 技術規格

- **Python**: 3.10+
- **Deep Learning**: PyTorch (GPU 支援)
- **ML Models**: XGBoost, LightGBM, Prophet, Transformer
- **Optimization**: PuLP (MILP)
- **LLM**: LangChain + OpenAI

### License

MIT License
