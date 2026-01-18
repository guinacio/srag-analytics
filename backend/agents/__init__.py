"""SRAG Analytics Agents.

This module provides two agent paradigms:

1. SRAGReportAgent (report_agent.py)
   - ORCHESTRATED flow using fan-out/fan-in pattern
   - Parallel execution of metrics, news, and charts
   - Deterministic, structured report generation

2. SRAGChatAgent (chat_agent.py)
   - AUTONOMOUS flow using ReAct pattern
   - Interactive Q&A with tool selection
   - Flexible, exploratory data analysis
"""

from backend.agents.report_agent import report_agent, SRAGReportAgent
from backend.agents.chat_agent import chat_agent, SRAGChatAgent

__all__ = [
    "report_agent",
    "SRAGReportAgent",
    "chat_agent",
    "SRAGChatAgent",
]
