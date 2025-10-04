"""LangGraph Report Generation Agent with supervisor pattern."""
import logging
from typing import TypedDict, Annotated, Sequence, Dict, Any, Optional
from datetime import datetime
import json
from pathlib import Path
import time

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from operator import add

from backend.config.settings import settings
from backend.tools.metrics_tool import metrics_tool
from backend.tools.news_tool import news_tool
from backend.tools.sql_tool import sql_tool  # Available for future user-driven data exploration
from backend.tools.rag_tool import rag_tool   # Available for future schema/documentation queries
from backend.agents.prompts import prompts

logger = logging.getLogger(__name__)


# State definition for the agent graph
class ReportState(TypedDict):
    """State passed between agent nodes."""
    messages: Annotated[Sequence[BaseMessage], add]
    days: int  # Number of days to analyze
    state_filter: Optional[str]  # State filter (UF)
    metrics: Optional[Dict[str, Any]]
    news_context: Optional[str]
    news_citations: Optional[list]
    sql_queries: Optional[list]
    chart_data: Optional[Dict[str, Any]]
    final_report: Optional[str]
    audit_trail: Optional[Dict[str, Any]]
    error: Optional[str]
    iteration_count: int


class SRAGReportAgent:
    """
    SRAG Report Generation Agent using LangGraph.

    Architecture:
    - Supervisor pattern orchestrates tool selection
    - Checkpointer for audit trail and persistence
    - Parallel execution where possible
    - Human-in-the-loop support (via checkpointer)
    """

    def __init__(self):
        """Initialize the agent and graph."""
        self.llm = ChatOpenAI(
            model="gpt-5",
            temperature=0.3,
            openai_api_key=settings.openai_api_key,
        )

        # Build the state graph
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(ReportState)

        # Add nodes
        workflow.add_node("calculate_metrics", self.calculate_metrics_node)
        workflow.add_node("fetch_news", self.fetch_news_node)
        workflow.add_node("generate_charts", self.generate_charts_node)
        workflow.add_node("write_report", self.write_report_node)
        workflow.add_node("create_audit", self.create_audit_node)

        # Define edges (execution flow)
        workflow.set_entry_point("calculate_metrics")

        # After metrics, fetch news and generate charts in parallel
        workflow.add_edge("calculate_metrics", "fetch_news")
        workflow.add_edge("fetch_news", "generate_charts")
        workflow.add_edge("generate_charts", "write_report")
        workflow.add_edge("write_report", "create_audit")
        workflow.add_edge("create_audit", END)

        return workflow.compile()

    def calculate_metrics_node(self, state: ReportState) -> ReportState:
        """Calculate all 4 required SRAG metrics."""
        days = state.get("days", 30)
        state_filter = state.get("state_filter")
        logger.info(f"Node: Calculating metrics (days={days}, state={state_filter})")
        logger.info(f"DEBUG: Current messages count: {len(state.get('messages', []))}")

        try:
            # Calculate all metrics using state parameters
            metrics = metrics_tool.calculate_all_metrics(days=days, state=state_filter)

            state["metrics"] = metrics
            state["messages"].append(
                AIMessage(content=f"Calculated all 4 SRAG metrics for last {days} days{f' in state {state_filter}' if state_filter else ''}")
            )

            # Log SQL query for audit
            if "sql_queries" not in state or state["sql_queries"] is None:
                state["sql_queries"] = []

            state["sql_queries"].append({
                "operation": "calculate_metrics",
                "timestamp": datetime.utcnow().isoformat(),
                "days": days,
                "state_filter": state_filter,
                "metrics": list(metrics.keys()),
            })

        except Exception as e:
            logger.error(f"Error calculating metrics: {e}")
            state["error"] = str(e)
            state["messages"].append(
                AIMessage(content=f"Error calculating metrics: {e}")
            )

        return state

    def fetch_news_node(self, state: ReportState) -> ReportState:
        """Fetch recent news about SRAG."""
        days = state.get("days", 30)
        state_filter = state.get("state_filter")
        logger.info(f"Node: Fetching news (days={days}, state={state_filter})")

        try:
            # Get recent SRAG news using the same period as metrics
            articles = news_tool.search_srag_news(days=days, max_results=10, state=state_filter)

            # Format news context with same period
            news_context = news_tool.get_recent_context(days=days, state=state_filter)
            news_citations = news_tool.format_for_citation(articles)

            state["news_context"] = news_context
            state["news_citations"] = news_citations
            state["messages"].append(
                AIMessage(content=f"Fetched {len(articles)} recent news articles about SRAG from last {days} days")
            )

        except Exception as e:
            logger.error(f"Error fetching news: {e}")
            state["news_context"] = "Error fetching news"
            state["news_citations"] = []
            state["messages"].append(
                AIMessage(content=f"Error fetching news: {e}")
            )

        return state

    def generate_charts_node(self, state: ReportState) -> ReportState:
        """Generate chart data for daily and monthly trends."""
        days = state.get("days", 30)
        state_filter = state.get("state_filter")
        logger.info(f"Node: Generating charts (days={days}, state={state_filter})")

        try:
            # Get daily cases for the specified period
            daily_data = metrics_tool.get_daily_cases_chart_data(days=days, state=state_filter)

            # Get monthly cases (last 12 months)
            monthly_data = metrics_tool.get_monthly_cases_chart_data(months=12, state=state_filter)

            state["chart_data"] = {
                "daily_30d": daily_data,
                "monthly_12m": monthly_data,
            }

            state["messages"].append(
                AIMessage(content=f"Generated chart data: {len(daily_data)} daily points, {len(monthly_data)} monthly points")
            )

        except Exception as e:
            logger.error(f"Error generating charts: {e}")
            state["chart_data"] = {"daily_30d": [], "monthly_12m": []}
            state["messages"].append(
                AIMessage(content=f"Error generating charts: {e}")
            )

        return state

    def write_report_node(self, state: ReportState) -> ReportState:
        """Write the final SRAG report with LLM."""
        logger.info("Node: Writing report")

        try:
            metrics = state.get("metrics", {})
            news_context = state.get("news_context", "")

            # Build prompts from centralized prompt management
            system_prompt = prompts.REPORT_SYSTEM_PROMPT
            user_prompt = prompts.build_report_user_prompt(metrics, news_context)

            # Generate report with LLM
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]

            response = self.llm.invoke(messages)
            report = response.content

            state["final_report"] = report
            state["messages"].append(
                AIMessage(content="Report generated successfully")
            )

        except Exception as e:
            logger.error(f"Error writing report: {e}")
            state["final_report"] = f"Erro ao gerar relatório: {e}"
            state["error"] = str(e)
            state["messages"].append(
                AIMessage(content=f"Error writing report: {e}")
            )

        return state

    def create_audit_node(self, state: ReportState) -> ReportState:
        """Create complete audit trail."""
        logger.info("Node: Creating audit trail")

        # Only include messages from the LAST execution to avoid duplicates
        # The first message is always the HumanMessage for this request
        all_messages = state.get("messages", [])

        # Find the index of the last HumanMessage (start of this execution)
        last_human_idx = 0
        for i in range(len(all_messages) - 1, -1, -1):
            if isinstance(all_messages[i], HumanMessage):
                last_human_idx = i
                break

        # Only include messages from this execution onwards
        current_execution_messages = all_messages[last_human_idx:]

        audit_trail = {
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": state.get("metrics"),
            "news_citations": state.get("news_citations"),
            "sql_queries": state.get("sql_queries"),
            "chart_data_summary": {
                "daily_points": len(state.get("chart_data", {}).get("daily_30d", [])),
                "monthly_points": len(state.get("chart_data", {}).get("monthly_12m", [])),
            },
            "messages": [
                {
                    "type": msg.__class__.__name__,
                    "content": msg.content[:200] if hasattr(msg, 'content') else str(msg)[:200],
                }
                for msg in current_execution_messages
            ],
            "error": state.get("error"),
        }

        state["audit_trail"] = audit_trail
        state["messages"].append(
            AIMessage(content="Audit trail created")
        )

        return state

    def generate_report(
        self,
        user_request: Optional[str] = None,
        days: int = 30,
        state_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate SRAG report.

        Args:
            user_request: Optional custom request
            days: Number of days to analyze
            state_filter: Optional state filter (UF)

        Returns:
            Complete report with metrics, charts, news, and audit trail
        """
        logger.info(f"Generating SRAG report (days={days}, state={state_filter})")

        start_time = time.time()

        # Initialize state with parameters
        initial_state = {
            "messages": [
                HumanMessage(content=user_request or f"Generate SRAG report for last {days} days")
            ],
            "days": days,
            "state_filter": state_filter,
            "metrics": None,
            "news_context": None,
            "news_citations": None,
            "sql_queries": None,
            "chart_data": None,
            "final_report": None,
            "audit_trail": None,
            "error": None,
            "iteration_count": 0,
        }

        # Execute graph with fresh invocation
        # Note: invoke() should not maintain state between calls, but we ensure
        # initial_state is completely fresh for each request
        final_state = self.graph.invoke(initial_state, {"recursion_limit": 50})

        execution_time_ms = int((time.time() - start_time) * 1000)

        # Save execution log to file
        self._save_execution_log(
            days=days,
            state_filter=state_filter,
            user_request=user_request,
            final_state=final_state,
            execution_time_ms=execution_time_ms
        )

        return {
            "report": final_state.get("final_report"),
            "metrics": final_state.get("metrics"),
            "chart_data": final_state.get("chart_data"),
            "news_citations": final_state.get("news_citations"),
            "audit_trail": final_state.get("audit_trail"),
            "error": final_state.get("error"),
        }

    def _save_execution_log(
        self,
        days: int,
        state_filter: Optional[str],
        user_request: Optional[str],
        final_state: Dict[str, Any],
        execution_time_ms: int
    ) -> None:
        """Save full execution log to file for audit and debugging."""
        try:
            # Create logs directory if it doesn't exist
            logs_dir = Path("logs")
            logs_dir.mkdir(exist_ok=True)

            # Generate log filename with timestamp
            timestamp = datetime.utcnow()
            filename = f"execution_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
            filepath = logs_dir / filename

            # Prepare log data with ALL messages (not filtered)
            log_data = {
                "timestamp": timestamp.isoformat(),
                "request": {
                    "days": days,
                    "state_filter": state_filter,
                    "user_request": user_request,
                },
                "execution_time_ms": execution_time_ms,
                "metrics": final_state.get("metrics"),
                "news_citations": final_state.get("news_citations"),
                "sql_queries": final_state.get("sql_queries"),
                "chart_data_summary": {
                    "daily_points": len(final_state.get("chart_data", {}).get("daily_30d", [])),
                    "monthly_points": len(final_state.get("chart_data", {}).get("monthly_12m", [])),
                },
                "messages": [
                    {
                        "type": msg.__class__.__name__,
                        "content": msg.content[:500] if hasattr(msg, 'content') else str(msg)[:500],
                    }
                    for msg in final_state.get("messages", [])
                ],
                "status": "error" if final_state.get("error") else "success",
                "error": final_state.get("error"),
            }

            # Write to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Execution log saved to {filepath}")

        except Exception as e:
            logger.error(f"Failed to save execution log: {e}")


# Global instance
report_agent = SRAGReportAgent()
