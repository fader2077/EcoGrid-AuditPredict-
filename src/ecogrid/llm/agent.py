"""
EcoGrid Audit Agent - LLM 智慧審計代理
使用 Ollama Local LLM 和 LangChain 建構 Agentic RAG 系統
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime

from loguru import logger

try:
    from langchain_community.llms import Ollama
    from langchain_community.chat_models import ChatOllama
    from langchain.agents import AgentExecutor, create_react_agent
    from langchain.tools import Tool, StructuredTool
    from langchain.prompts import PromptTemplate
    from langchain.schema import HumanMessage, SystemMessage, AIMessage
    from langchain.callbacks.manager import CallbackManager
    from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logger.warning("LangChain not available, LLM features limited")

from ecogrid.config.settings import settings
from ecogrid.llm.tools import AuditTools
from ecogrid.llm.prompts import SYSTEM_PROMPT, AUDIT_PROMPT_TEMPLATE


class EcoGridAuditAgent:
    """
    EcoGrid 智慧審計代理
    
    使用 Ollama 本地 LLM 進行：
    - 用電數據分析解讀
    - 優化建議生成
    - 審計報告撰寫
    - ESG 合規評估
    
    重要：所有數值計算透過 AuditTools 執行，LLM 僅負責解釋
    """
    
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.ollama_model
        self.base_url = settings.ollama_base_url
        self.audit_tools = AuditTools()
        self.conversation_history: List[Dict[str, str]] = []
        
        self.llm = None
        self.agent = None
        
        if LANGCHAIN_AVAILABLE:
            self._initialize_llm()
        else:
            logger.warning("LangChain not available, using fallback mode")
        
        logger.info(f"EcoGridAuditAgent initialized with model: {self.model_name}")
    
    def _initialize_llm(self):
        """初始化 Ollama LLM"""
        try:
            # 初始化 Ollama Chat Model
            self.llm = ChatOllama(
                model=self.model_name,
                base_url=self.base_url,
                temperature=0.3,  # 較低溫度確保一致性
                callback_manager=CallbackManager([StreamingStdOutCallbackHandler()])
            )
            
            # 建立工具
            self.tools = self._create_tools()
            
            # 建立 Agent
            self._create_agent()
            
            logger.info(f"LLM initialized: {self.model_name} at {self.base_url}")
            
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            self.llm = None
    
    def _create_tools(self) -> List[Tool]:
        """建立 LangChain 工具"""
        tools = [
            Tool(
                name="calculate_electricity_cost",
                func=lambda x: json.dumps(
                    self.audit_tools.calculate_electricity_cost(
                        **json.loads(x) if isinstance(x, str) else x
                    ), ensure_ascii=False
                ),
                description="計算電費。輸入JSON: {\"consumption_kwh\": 數值, \"tariff_rate\": 數值}"
            ),
            Tool(
                name="calculate_savings",
                func=lambda x: json.dumps(
                    self.audit_tools.calculate_savings(
                        **json.loads(x) if isinstance(x, str) else x
                    ), ensure_ascii=False
                ),
                description="計算節省金額。輸入JSON: {\"baseline_cost\": 數值, \"optimized_cost\": 數值}"
            ),
            Tool(
                name="calculate_carbon_emission",
                func=lambda x: json.dumps(
                    self.audit_tools.calculate_carbon_emission(
                        **json.loads(x) if isinstance(x, str) else x
                    ), ensure_ascii=False
                ),
                description="計算碳排放量。輸入JSON: {\"consumption_kwh\": 數值}"
            ),
            Tool(
                name="calculate_statistics",
                func=lambda x: json.dumps(
                    self.audit_tools.calculate_statistics(
                        json.loads(x) if isinstance(x, str) else x
                    ), ensure_ascii=False
                ),
                description="計算統計指標。輸入JSON數據列表"
            ),
            Tool(
                name="detect_anomalies",
                func=lambda x: json.dumps(
                    self.audit_tools.detect_anomalies(
                        **json.loads(x) if isinstance(x, str) else x
                    ), ensure_ascii=False
                ),
                description="偵測異常值。輸入JSON: {\"data\": [數值列表], \"threshold_std\": 數值}"
            ),
            Tool(
                name="analyze_tou_distribution",
                func=lambda x: json.dumps(
                    self.audit_tools.analyze_tou_distribution(
                        **json.loads(x) if isinstance(x, str) else x
                    ), ensure_ascii=False
                ),
                description="分析時間電價分佈。輸入JSON: {\"hourly_data\": [24小時數據]}"
            ),
            Tool(
                name="estimate_shift_benefit",
                func=lambda x: json.dumps(
                    self.audit_tools.estimate_shift_benefit(
                        **json.loads(x) if isinstance(x, str) else x
                    ), ensure_ascii=False
                ),
                description="估算負載移轉效益。輸入JSON: {\"consumption_kwh\": 數值, \"from_period\": \"peak/half_peak/off_peak\", \"to_period\": \"peak/half_peak/off_peak\"}"
            ),
        ]
        
        return tools
    
    def _create_agent(self):
        """建立 ReAct Agent"""
        if not self.llm or not self.tools:
            return
        
        # ReAct 風格的提示詞模板
        react_template = """你是 EcoGrid 智慧能源審計師。請使用提供的工具來回答問題。

可用工具:
{tools}

工具名稱列表: {tool_names}

重要規則:
1. 所有數值計算必須使用工具，禁止自行計算
2. 使用繁體中文回答
3. 引用工具返回的結果時要準確

回答格式:
Question: 使用者的問題
Thought: 思考需要使用什麼工具
Action: 工具名稱
Action Input: 工具輸入（JSON格式）
Observation: 工具返回結果
... (重複 Thought/Action/Observation 直到有答案)
Thought: 我現在知道答案了
Final Answer: 最終答案

開始:

Question: {input}
Thought: {agent_scratchpad}"""

        prompt = PromptTemplate(
            template=react_template,
            input_variables=["input", "agent_scratchpad", "tools", "tool_names"]
        )
        
        try:
            self.agent = create_react_agent(
                llm=self.llm,
                tools=self.tools,
                prompt=prompt
            )
            
            self.agent_executor = AgentExecutor(
                agent=self.agent,
                tools=self.tools,
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=15,
                max_execution_time=60,
                early_stopping_method="generate"
            )
            
            logger.info("ReAct Agent created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create agent: {e}")
            self.agent = None
    
    def chat(self, message: str) -> str:
        """
        與 Agent 對話
        
        Args:
            message: 使用者訊息
            
        Returns:
            Agent 回應
        """
        if not LANGCHAIN_AVAILABLE:
            return self._fallback_response(message)
        
        try:
            if self.agent_executor:
                try:
                    response = self.agent_executor.invoke({"input": message})
                    result = response.get("output", "")
                    
                    # 如果 Agent 回應為空或超時訊息，嘗試直接使用 LLM
                    if not result or "iteration limit" in result.lower() or "time limit" in result.lower():
                        logger.warning("Agent failed, falling back to direct LLM")
                        if self.llm:
                            messages = [
                                SystemMessage(content=SYSTEM_PROMPT),
                                HumanMessage(content=message)
                            ]
                            response = self.llm.invoke(messages)
                            result = response.content
                        else:
                            result = self._fallback_response(message)
                except Exception as e:
                    logger.error(f"Agent executor error: {e}, falling back to LLM")
                    if self.llm:
                        messages = [
                            SystemMessage(content=SYSTEM_PROMPT),
                            HumanMessage(content=message)
                        ]
                        response = self.llm.invoke(messages)
                        result = response.content
                    else:
                        result = self._fallback_response(message)
            elif self.llm:
                # 直接使用 LLM（無 Agent）
                messages = [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=message)
                ]
                response = self.llm.invoke(messages)
                result = response.content
            else:
                result = self._fallback_response(message)
            
            # 記錄對話歷史
            self.conversation_history.append({
                "role": "user",
                "content": message,
                "timestamp": datetime.now().isoformat()
            })
            self.conversation_history.append({
                "role": "assistant",
                "content": result,
                "timestamp": datetime.now().isoformat()
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return f"處理請求時發生錯誤: {str(e)}"
    
    def _fallback_response(self, message: str) -> str:
        """當 LLM 不可用時的備用回應"""
        return f"""
[系統備用模式]

您的問題: {message}

由於 LLM 服務目前不可用，請確認：
1. Ollama 服務是否已啟動 (ollama serve)
2. 模型是否已下載 (ollama pull {self.model_name})
3. 服務地址是否正確 ({self.base_url})

如需進行計算，您可以直接使用 AuditTools：

```python
from ecogrid.llm.tools import AuditTools
tools = AuditTools()

# 計算電費
result = tools.calculate_electricity_cost(consumption_kwh=1000, tariff_rate=5.80)
print(result)
```
"""
    
    def generate_audit_report(self, 
                              prediction_data: Dict[str, Any],
                              optimization_data: Dict[str, Any],
                              actual_data: Optional[Dict[str, Any]] = None) -> str:
        """
        生成完整審計報告
        
        Args:
            prediction_data: 預測數據
            optimization_data: 優化結果
            actual_data: 實際數據（可選，用於比較）
            
        Returns:
            審計報告文本
        """
        # 使用工具進行計算
        calculations = {}
        
        # 成本計算
        if "total_cost" in optimization_data:
            calculations["savings"] = self.audit_tools.calculate_savings(
                baseline_cost=optimization_data.get("baseline_cost", 0),
                optimized_cost=optimization_data.get("total_cost", 0)
            )
        
        # 碳排計算
        if "total_consumption_kwh" in prediction_data:
            calculations["carbon"] = self.audit_tools.calculate_carbon_emission(
                consumption_kwh=prediction_data["total_consumption_kwh"]
            )
        
        # 再生能源分析
        if "renewable_kwh" in prediction_data:
            calculations["renewable"] = self.audit_tools.calculate_renewable_offset(
                total_consumption_kwh=prediction_data.get("total_consumption_kwh", 0),
                renewable_kwh=prediction_data.get("renewable_kwh", 0)
            )
        
        # 準備報告提示
        report_prompt = f"""請根據以下數據生成用電審計報告：

## 預測數據
{json.dumps(prediction_data, ensure_ascii=False, indent=2)}

## 優化結果
{json.dumps(optimization_data, ensure_ascii=False, indent=2)}

## 計算結果（由工具計算）
{json.dumps(calculations, ensure_ascii=False, indent=2)}

請生成包含以下章節的審計報告：
1. 執行摘要
2. 用電分析
3. 優化成效
4. 碳排與 ESG
5. 具體建議
6. 下一步行動

注意：所有數值必須引用上述計算結果，不要自行計算。
"""
        
        return self.chat(report_prompt)
    
    def analyze_anomalies(self, data: List[float], context: str = "") -> str:
        """
        分析異常用電
        
        Args:
            data: 用電數據
            context: 額外背景資訊
            
        Returns:
            異常分析報告
        """
        # 使用工具偵測異常
        anomaly_result = self.audit_tools.detect_anomalies(data)
        stats = self.audit_tools.calculate_statistics(data)
        
        prompt = f"""請分析以下用電異常情況：

## 異常偵測結果（由工具計算）
{json.dumps(anomaly_result, ensure_ascii=False, indent=2)}

## 統計資訊
{json.dumps(stats, ensure_ascii=False, indent=2)}

## 背景資訊
{context}

請提供：
1. 異常原因分析
2. 可能的設備問題
3. 處理建議
4. 預防措施
"""
        
        return self.chat(prompt)
    
    def get_optimization_advice(self, 
                                hourly_consumption: List[float],
                                hourly_tariffs: List[float]) -> str:
        """
        獲取優化建議
        
        Args:
            hourly_consumption: 每小時用電量
            hourly_tariffs: 每小時電價
            
        Returns:
            優化建議
        """
        # 分析 TOU 分佈
        tou_analysis = self.audit_tools.analyze_tou_distribution(hourly_consumption)
        
        # 計算成本
        cost_analysis = self.audit_tools.calculate_period_cost(
            hourly_consumption, 
            hourly_tariffs
        )
        
        # 估算移轉效益
        peak_consumption = tou_analysis["peak"]["consumption"]
        shift_benefit = self.audit_tools.estimate_shift_benefit(
            consumption_kwh=peak_consumption * 0.2,  # 假設可移轉 20%
            from_period="peak",
            to_period="off_peak"
        )
        
        prompt = f"""請根據以下分析結果提供用電優化建議：

## TOU 分佈分析
{json.dumps(tou_analysis, ensure_ascii=False, indent=2)}

## 成本分析
{json.dumps(cost_analysis, ensure_ascii=False, indent=2)}

## 負載移轉效益估算（移轉 20% 尖峰負載）
{json.dumps(shift_benefit, ensure_ascii=False, indent=2)}

請提供：
1. 具體可執行的優化措施
2. 預期效益（使用上述計算結果）
3. 實施優先順序
4. 注意事項
"""
        
        return self.chat(prompt)
    
    def clear_history(self):
        """清除對話歷史"""
        self.conversation_history = []
        logger.info("Conversation history cleared")
    
    def get_conversation_history(self) -> List[Dict[str, str]]:
        """獲取對話歷史"""
        return self.conversation_history
    
    def test_connection(self) -> bool:
        """測試 Ollama 連接"""
        if not LANGCHAIN_AVAILABLE:
            return False
        
        try:
            response = self.llm.invoke([HumanMessage(content="你好，請用繁體中文回應。")])
            logger.info(f"Ollama connection test successful: {response.content[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Ollama connection test failed: {e}")
            return False
