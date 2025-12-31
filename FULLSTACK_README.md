# EcoGrid Audit Predict - 全棧 Web 應用

> 綠電優化與用電審計預測系統 - Taiwan Green Energy Optimization & Power Audit Prediction System

## 📖 專案結構

```
egoaudit/
├── backend/                      # FastAPI Backend
│   ├── app/
│   │   ├── api/                 # API Routes
│   │   │   └── routes/
│   │   │       ├── dashboard.py # Dashboard API
│   │   │       ├── forecast.py  # AI 預測 API
│   │   │       ├── optimization.py # TOU 優化 API
│   │   │       └── audit.py     # 審計報告 API
│   │   ├── core/                # 核心配置
│   │   │   └── config.py        # Settings
│   │   ├── db/                  # 資料庫連接
│   │   │   └── session.py       # SQLAlchemy Session
│   │   ├── models/              # SQLAlchemy Models
│   │   │   └── power.py         # PowerLog, ForecastResult, OptimizationPlan, AuditReport, TaskStatus
│   │   ├── schemas/             # Pydantic Schemas
│   │   │   └── power.py         # Request/Response Models
│   │   └── services/            # Business Logic
│   │       ├── ai_service.py    # AI 預測服務 (整合 ecogrid.models)
│   │       ├── optimization_service.py # 優化服務 (整合 ecogrid.optimization)
│   │       └── llm_service.py   # LLM 審計服務 (整合 ecogrid.llm)
│   ├── main.py                  # FastAPI Application
│   ├── requirements.txt         # Python Dependencies
│   └── ecogrid.db              # SQLite Database (自動生成)
│
├── frontend/                    # Vue 3 Frontend
│   ├── src/
│   │   ├── api/                # API Client
│   │   │   ├── index.js        # Axios Instance
│   │   │   └── endpoints.js    # API Endpoints
│   │   ├── components/         # Vue Components
│   │   │   ├── EnergyChart.vue # ECharts 圖表組件
│   │   │   ├── ChatAssistant.vue # LLM 對話組件
│   │   │   └── AuditReportCard.vue # 審計報告組件
│   │   ├── views/              # Pages
│   │   │   ├── Dashboard.vue   # 即時監控頁面
│   │   │   ├── Forecast.vue    # AI 預測頁面
│   │   │   ├── Optimization.vue # TOU 優化頁面
│   │   │   └── Audit.vue       # 審計報告頁面
│   │   ├── stores/             # Pinia Stores
│   │   │   └── dashboard.js    # Dashboard State
│   │   ├── router/             # Vue Router
│   │   │   └── index.js        # Routes
│   │   ├── App.vue             # Root Component
│   │   ├── main.js             # Entry Point
│   │   └── style.css           # Global Styles
│   ├── index.html              # HTML Template
│   ├── package.json            # NPM Dependencies
│   ├── vite.config.js          # Vite Config
│   └── tailwind.config.js      # Tailwind Config
│
└── src/ecogrid/                # 原 AI Core (已完成)
    ├── config/                 # 配置
    ├── data/                   # ETL Pipeline
    ├── models/                 # AI Models (XGBoost, LightGBM, Transformer, LSTM)
    ├── optimization/           # PuLP MILP Optimizer
    ├── llm/                    # Ollama LLM Agent
    └── utils/                  # Utilities
```

## 🚀 技術棧

### Backend
- **Framework**: FastAPI 0.115.0
- **Database**: SQLite + SQLAlchemy 2.0.36
- **Task Queue**: BackgroundTasks (可擴展為 Celery + Redis)
- **AI Integration**: 直接整合 `src/ecogrid` 模組
  - XGBoost 3.1.2 (GPU)
  - LightGBM 4.6.0 (GPU)
  - PyTorch 2.8.0+cu126 (Transformer/LSTM)
  - PuLP 3.3.0 (MILP)
  - LangChain + Ollama (llama3.2)

### Frontend
- **Framework**: Vue 3 + Vite
- **UI**: Tailwind CSS
- **State**: Pinia
- **Charts**: Apache ECharts 5.4.3
- **Markdown**: marked 11.1.1
- **HTTP Client**: Axios

## 📦 安裝與運行

### 1. Backend 安裝

```bash
cd backend
pip install -r requirements.txt
```

### 2. Backend 運行

```bash
# 方法 1: 使用 uvicorn (推薦)
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 方法 2: 直接運行
cd backend
python main.py
```

Backend API 將運行於: **http://localhost:8000**
- Swagger Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 3. Frontend 安裝（需要 Node.js）

```bash
cd frontend
npm install
```

### 4. Frontend 運行

```bash
cd frontend
npm run dev
```

Frontend 將運行於: **http://localhost:5173**

## 📊 Database Schema

### PowerLog（時序電力數據）
```sql
CREATE TABLE power_logs (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME NOT NULL UNIQUE,
    load_kw FLOAT NOT NULL,
    solar_kw FLOAT DEFAULT 0,
    wind_kw FLOAT DEFAULT 0,
    grid_import_kw FLOAT DEFAULT 0,
    battery_soc FLOAT DEFAULT 0.5,
    tou_period VARCHAR(20),
    tariff_rate FLOAT,
    cost_ntd FLOAT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### ForecastResult（AI 預測結果）
```sql
CREATE TABLE forecast_results (
    id INTEGER PRIMARY KEY,
    forecast_timestamp DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    predicted_load_kw FLOAT NOT NULL,
    predicted_solar_kw FLOAT DEFAULT 0,
    predicted_wind_kw FLOAT DEFAULT 0,
    model_type VARCHAR(50),
    confidence FLOAT,
    actual_load_kw FLOAT,
    mae FLOAT,
    rmse FLOAT
);
```

### OptimizationPlan（優化排程）
```sql
CREATE TABLE optimization_plans (
    id INTEGER PRIMARY KEY,
    plan_date DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20),
    baseline_cost_ntd FLOAT,
    optimized_cost_ntd FLOAT,
    savings_ntd FLOAT,
    savings_percent FLOAT,
    peak_reduction_percent FLOAT,
    schedule_json JSON,
    recommendations TEXT
);
```

### AuditReport（LLM 審計報告）
```sql
CREATE TABLE audit_reports (
    id INTEGER PRIMARY KEY,
    report_date DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    report_type VARCHAR(50),
    start_date DATETIME,
    end_date DATETIME,
    content_markdown TEXT NOT NULL,
    total_consumption_kwh FLOAT,
    total_cost_ntd FLOAT,
    renewable_ratio_percent FLOAT,
    carbon_emission_kg FLOAT,
    llm_model VARCHAR(50),
    user_query TEXT
);
```

### TaskStatus（背景任務狀態）
```sql
CREATE TABLE task_status (
    id INTEGER PRIMARY KEY,
    task_id VARCHAR(100) UNIQUE NOT NULL,
    task_type VARCHAR(50),
    status VARCHAR(20) DEFAULT 'pending',
    progress FLOAT DEFAULT 0,
    result_json JSON,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);
```

## 🔌 API Endpoints

### Dashboard API
- `GET /api/v1/dashboard/summary` - 獲取即時摘要
- `POST /api/v1/dashboard/chart-data` - 獲取圖表數據

### Forecast API
- `POST /api/v1/forecast/predict` - 創建預測任務（異步）
- `GET /api/v1/forecast/predict/{task_id}` - 查詢任務狀態
- `GET /api/v1/forecast/latest` - 獲取最新預測

### Optimization API
- `POST /api/v1/optimization/optimize` - 創建優化任務（異步）
- `GET /api/v1/optimization/optimize/{task_id}` - 查詢任務狀態
- `GET /api/v1/optimization/plan/{plan_id}` - 獲取優化計劃
- `GET /api/v1/optimization/latest` - 獲取最新優化

### Audit API
- `POST /api/v1/audit/generate` - 生成審計報告（異步）
- `GET /api/v1/audit/report/{report_id}` - 獲取報告
- `GET /api/v1/audit/latest` - 獲取最新報告
- `POST /api/v1/audit/query` - 互動式查詢（Chat Assistant）

## 🎯 核心功能

### 1. ETL 資料管道
- 自動抓取台電與氣象局數據
- 特徵工程（時間特徵、TOU 特徵、Lag/Rolling 特徵）
- 缺失值處理與數據清洗

### 2. AI 負載預測
- **XGBoost**: R² = 0.82（GPU 加速）
- **LightGBM**: R² = 0.77（GPU 加速）
- **Random Forest**: 太陽能/風力預測
- **Transformer** (可選): PatchTST 架構
- **LSTM** (可選): 序列預測

### 3. TOU 時間電價優化
- **MILP 求解器**: PuLP + CBC
- **目標函數**: 最小化總電力成本
  ```
  Minimize: Σ(Grid_t × Tariff_t) - Σ(Renewable_t × Tariff_t × 0.8)
  ```
- **約束條件**:
  - 能量平衡
  - 電池 SoC 上下限
  - 合約容量限制
  - 充放電互斥
  - 削峰限制

### 4. LLM 審計代理
- **模型**: Ollama llama3.2
- **功能**: 
  - 自動生成專業審計報告（Markdown）
  - 互動式查詢（Chat Assistant）
  - Function Calling（禁止 LLM 自行計算）
  - Agentic RAG（查詢 SQLite 數據）

### 5. BackgroundTasks
- 避免 API Timeout
- 長時間運算（AI 訓練、MILP 優化、LLM 生成）在背景執行
- 任務狀態追蹤（進度條）

## 💡 使用範例

### 1. 開始 AI 預測

```bash
curl -X POST http://localhost:8000/api/v1/forecast/predict \
  -H "Content-Type: application/json" \
  -d '{
    "hours_ahead": 24,
    "use_transformer": false,
    "use_lstm": false
  }'

# Response:
{
  "task_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "status": "pending",
  "message": "Prediction task started for 24 hours ahead"
}
```

### 2. 查詢任務狀態

```bash
curl http://localhost:8000/api/v1/forecast/predict/f47ac10b-58cc-4372-a567-0e02b2c3d479

# Response:
{
  "task_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "task_type": "forecast",
  "status": "completed",
  "progress": 100.0,
  "result": {
    "forecast_count": 24,
    "avg_load_kw": 379.2
  }
}
```

### 3. 開始 TOU 優化

```bash
curl -X POST http://localhost:8000/api/v1/optimization/optimize \
  -H "Content-Type: application/json" \
  -d '{
    "hours_ahead": 24,
    "initial_soc": 0.5,
    "battery_capacity_kwh": 100,
    "max_contract_kw": 500
  }'
```

### 4. Chat Assistant 互動

```bash
curl -X POST http://localhost:8000/api/v1/audit/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "為什麼今天下午電費這麼高？"
  }'

# Response:
{
  "question": "為什麼今天下午電費這麼高？",
  "answer": "今天下午電費較高主要有以下原因：\n1. 時段為尖峰時段（13:00-17:00），電價為 7.05 NTD/kWh\n2. 負載較高（約 420 kW），超過平均負載 30%\n3. 太陽能發電受雲層影響，發電量僅 50 kW\n建議：將部分高耗能設備移至離峰時段運作",
  "timestamp": "2025-12-20T17:00:00Z"
}
```

## 🎨 Frontend Components

### EnergyChart.vue
```vue
<EnergyChart
  :data="{
    timestamps: ['00:00', '01:00', '02:00'],
    series: {
      '負載': [350.5, 340.2, 330.1],
      '太陽能': [0, 0, 0],
      '電價': [2.38, 2.38, 2.38]
    }
  }"
  title="24小時用電趨勢"
  height="400px"
/>
```

### ChatAssistant.vue
- 類似 ChatGPT 的對話介面
- 實時與 Ollama LLM 互動
- 支援多輪對話

### AuditReportCard.vue
- Markdown 渲染
- 語法高亮
- 響應式設計

## ⚙️ 配置

### Backend (.env)
```env
# API
API_V1_PREFIX=/api/v1
DEBUG=True

# Database
DATABASE_URL=sqlite:///./ecogrid.db

# CORS
CORS_ORIGINS=["http://localhost:5173"]

# AI
USE_CUDA=True
GPU_MEMORY_FRACTION=0.6

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
```

### Frontend (.env)
```env
VITE_API_URL=http://localhost:8000/api/v1
```

## 🐛 除錯

### Backend 運行失敗
```bash
# 檢查端口佔用
netstat -ano | findstr :8000

# 檢查 GPU
python -c "import torch; print(torch.cuda.is_available())"

# 檢查 Ollama
ollama list
ollama serve
```

### Frontend 運行失敗
```bash
# 清除快取
rm -rf node_modules
npm install

# 檢查端口
netstat -ano | findstr :5173
```

## 📈 性能優化

### Backend
1. **GPU 加速**: XGBoost/LightGBM 自動使用 GPU
2. **BackgroundTasks**: 長時間運算不阻塞 API
3. **SQLAlchemy**: Lazy Loading + Connection Pool
4. **Cache**: diskcache 用於 ETL 數據快取

### Frontend
1. **Code Splitting**: Vue Router Lazy Loading
2. **Vite**: 極速 HMR
3. **ECharts**: 按需引入
4. **Tailwind**: PurgeCSS 移除未使用樣式

## 📝 未來擴展

- [ ] PostgreSQL 遷移
- [ ] Redis + Celery 分布式任務隊列
- [ ] Docker Compose 一鍵部署
- [ ] JWT 認證
- [ ] WebSocket 實時推送
- [ ] 多租戶支援
- [ ] Prometheus + Grafana 監控
- [ ] CI/CD Pipeline

## 📞 聯絡資訊

- **Project**: EcoGrid Audit Predict
- **Version**: 1.0.0
- **License**: MIT

---

**Made with ❤️ for Taiwan's Green Energy Future**
