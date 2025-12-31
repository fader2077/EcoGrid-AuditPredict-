"""
LLM Service - Ollama Local LLM Integration
"""

import json
from typing import Dict, Any, Optional
from datetime import datetime

from loguru import logger

# Import EcoGrid Agent
from ecogrid.llm.agent import EcoGridAuditAgent


class LLMService:
    """
    LLM Service for EcoGrid
    
    Uses Ollama local LLM for:
    - Power consumption analysis
    - Optimization suggestions
    - Audit report generation
    - Interactive Q&A
    """
    
    def __init__(self):
        self.agent: Optional[EcoGridAuditAgent] = None
        self._initialized = False
    
    def initialize(self):
        """Initialize LLM Agent (lazy loading)"""
        if self._initialized and self.agent:
            return
        
        try:
            logger.info("Initializing EcoGrid Audit Agent...")
            self.agent = EcoGridAuditAgent()
            self._initialized = True
            logger.info("✓ LLM Agent initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LLM Agent: {e}")
            self.agent = None
            self._initialized = False
    
    def generate_report(
        self,
        report_type: str,
        start_date: datetime,
        end_date: datetime,
        power_data: Dict[str, Any]
    ) -> str:
        """
        Generate audit report using LLM
        
        Args:
            report_type: Report type (energy, cost, carbon)
            start_date: Start date
            end_date: End date
            power_data: Power consumption data
            
        Returns:
            Generated report (Markdown format)
        """
        self.initialize()
        
        if not self.agent:
            return self._generate_fallback_report(
                report_type, start_date, end_date, power_data
            )
        
        try:
            prompt = self._build_report_prompt(
                report_type, start_date, end_date, power_data
            )
            
            response = self.agent.chat(prompt)
            return response
            
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            return self._generate_fallback_report(
                report_type, start_date, end_date, power_data
            )
    
    def query(self, user_query: str, context: Dict[str, Any]) -> str:
        """
        Interactive query using direct LLM (bypass Agent Executor)
        
        Args:
            user_query: User question
            context: Context data with recent power logs
            
        Returns:
            LLM answer in Traditional Chinese
        """
        self.initialize()
        
        logger.info(f"Processing query: {user_query}")
        
        if not self.agent:
            return "LLM service is not available. Please ensure Ollama is running."
        
        if not hasattr(self.agent, 'llm') or not self.agent.llm:
            return "LLM is not properly initialized."
        
        try:
            from langchain_core.messages import SystemMessage, HumanMessage
            
            # Build context string from recent data
            context_info = ""
            if context and 'recent_data' in context and context['recent_data']:
                latest = context['recent_data'][-1]
                load_kw = latest.get('load_kw', 0)
                solar_kw = latest.get('solar_kw', 0)
                wind_kw = latest.get('wind_kw', 0)
                total_renewable = solar_kw + wind_kw
                renewable_ratio = (total_renewable / load_kw * 100) if load_kw > 0 else 0
                
                context_info = f"""
Current Power Status:
- Load: {load_kw:.1f} kW
- Solar: {solar_kw:.1f} kW
- Wind: {wind_kw:.1f} kW
- Total Renewable: {total_renewable:.1f} kW
- Renewable Ratio: {renewable_ratio:.1f}%
"""
            
            system_prompt = f"""You are EcoGrid AI Assistant, an expert in smart grid energy management.

Your Role:
- Analyze current power consumption
- Provide energy optimization suggestions
- Explain renewable energy usage
- Answer user questions about electricity

Response Requirements:
- MUST answer in Traditional Chinese (繁體中文)
- Be professional, clear, and concise (3-5 sentences)
- Provide specific data and analysis
- Give actionable recommendations

{context_info}

Please answer the user's question based on the current power status above."""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_query)
            ]
            
            logger.info(f"Calling Ollama LLM directly...")
            response = self.agent.llm.invoke(messages)
            
            result = response.content if hasattr(response, 'content') else str(response)
            
            # Ensure UTF-8 encoding
            if isinstance(result, bytes):
                result = result.decode('utf-8', errors='replace')
            
            logger.info(f"LLM response received (length: {len(result)})")
            return result
                    
        except Exception as e:
            logger.error(f"Query failed: {e}", exc_info=True)
            return f"Sorry, query failed: {str(e)}"
    
    def _build_report_prompt(
        self,
        report_type: str,
        start_date: datetime,
        end_date: datetime,
        data: Dict[str, Any]
    ) -> str:
        """Build report generation prompt"""
        return f"""Please generate a professional power audit report based on the following data:

Report Type: {report_type}
Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}

Power Data:
- Total Consumption: {data.get('total_consumption_kwh', 0):.2f} kWh
- Total Cost: NTD {data.get('total_cost_ntd', 0):,.2f}
- Renewable Ratio: {data.get('renewable_ratio', 0):.1f}%
- Carbon Emission: {data.get('carbon_emission_kg', 0):.2f} kg CO2
- Average Load: {data.get('avg_load_kw', 0):.2f} kW
- Peak Load: {data.get('peak_load_kw', 0):.2f} kW

Please output in Markdown format with:
1. Executive Summary
2. Power Consumption Analysis
3. Cost Analysis
4. Energy-saving Recommendations
5. Carbon Emission Assessment

Use Traditional Chinese for all content."""
    
    def _generate_fallback_report(
        self,
        report_type: str,
        start_date: datetime,
        end_date: datetime,
        data: Dict[str, Any]
    ) -> str:
        """Generate fallback report when LLM is unavailable"""
        return f"""# Power Audit Report (Generated without LLM)

## Report Information
- **Type**: {report_type}
- **Period**: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}
- **Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Power Data Summary
- Total Consumption: {data.get('total_consumption_kwh', 0):.2f} kWh
- Total Cost: NTD {data.get('total_cost_ntd', 0):,.2f}
- Renewable Ratio: {data.get('renewable_ratio', 0):.1f}%
- Carbon Emission: {data.get('carbon_emission_kg', 0):.2f} kg CO2
- Average Load: {data.get('avg_load_kw', 0):.2f} kW
- Peak Load: {data.get('peak_load_kw', 0):.2f} kW

## Recommendations
1. Monitor peak load times to identify optimization opportunities
2. Increase renewable energy usage
3. Consider time-of-use tariff optimization
4. Implement energy monitoring system

---
*Note: This is an automated report. For detailed AI analysis, please ensure Ollama service is running.*
"""


# Global service instance
llm_service = LLMService()

