"""LangGraph Report Generation Agent with supervisor pattern."""
import logging
from typing import TypedDict, Annotated, Sequence, Dict, Any, Optional, List
from datetime import datetime
import json
from pathlib import Path
import time
import uuid

from langgraph.graph import StateGraph, END, START
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


# Custom reducers for parallel state updates
def keep_first(existing: Any, new: Any) -> Any:
    """Reducer that keeps the first non-None value (for read-only fields)."""
    if existing is not None:
        return existing
    return new


def keep_latest(existing: Any, new: Any) -> Any:
    """Reducer that keeps the latest non-None value."""
    if new is not None:
        return new
    return existing


def merge_dicts(existing: Optional[Dict], new: Optional[Dict]) -> Optional[Dict]:
    """Reducer that merges dictionaries (for parallel updates to different keys)."""
    if existing is None:
        return new
    if new is None:
        return existing
    return {**existing, **new}


def merge_lists(existing: Optional[List], new: Optional[List]) -> Optional[List]:
    """Reducer that concatenates lists."""
    if existing is None:
        return new
    if new is None:
        return existing
    return existing + new


# State definition for the agent graph
class ReportState(TypedDict):
    """State passed between agent nodes.
    
    Uses Annotated types with reducers to support parallel node execution.
    The fan-out/fan-in pattern requires reducers for proper state merging.
    """
    messages: Annotated[Sequence[BaseMessage], add]
    # Read-only config fields - keep first value set at initialization
    days: Annotated[int, keep_first]
    state_filter: Annotated[Optional[str], keep_first]
    iteration_count: Annotated[int, keep_first]
    # Data fields updated by parallel nodes - merge/keep latest
    metrics: Annotated[Optional[Dict[str, Any]], merge_dicts]
    news_context: Annotated[Optional[str], keep_latest]
    news_citations: Annotated[Optional[list], merge_lists]
    sql_queries: Annotated[Optional[list], merge_lists]
    chart_data: Annotated[Optional[Dict[str, Any]], merge_dicts]
    # Sequential node fields - keep latest
    final_report: Annotated[Optional[str], keep_latest]
    audit_trail: Annotated[Optional[Dict[str, Any]], keep_latest]
    error: Annotated[Optional[str], keep_latest]


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
            model="gpt-4o", # Originally gpt-5, changed to gpt-4o for speed responses on demo
            temperature=0.3,
            openai_api_key=settings.openai_api_key,
        )

        # Initialize PostgreSQL checkpointer for persistence using modern from_conn_string pattern
        try:
            self.checkpointer = PostgresSaver.from_conn_string(
                settings.langgraph_checkpoint_url
            )
            self.checkpointer.setup()
            logger.info("PostgreSQL checkpointer initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to setup checkpointer (may already exist): {e}")

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
        # Fan-out: START branches to 3 parallel nodes for concurrent execution
        workflow.add_edge(START, "calculate_metrics")
        workflow.add_edge(START, "fetch_news")
        workflow.add_edge(START, "generate_charts")

        # Fan-in: all 3 parallel nodes converge to write_report
        workflow.add_edge("calculate_metrics", "write_report")
        workflow.add_edge("fetch_news", "write_report")
        workflow.add_edge("generate_charts", "write_report")

        # Sequential: report writing followed by audit
        workflow.add_edge("write_report", "create_audit")
        workflow.add_edge("create_audit", END)

        return workflow.compile(checkpointer=self.checkpointer)

    def calculate_metrics_node(self, state: ReportState) -> Dict[str, Any]:
        """Calculate all 4 required SRAG metrics.
        
        Returns only the fields this node updates (for parallel execution support).
        """
        days = state.get("days", 30)
        state_filter = state.get("state_filter")
        logger.info(f"Node: Calculating metrics (days={days}, state={state_filter})")

        try:
            # Calculate all metrics using state parameters
            metrics = metrics_tool.calculate_all_metrics(days=days, state=state_filter)

            # Return only the fields we update
            return {
                "metrics": metrics,
                "messages": [
                    AIMessage(content=f"Calculated all 4 SRAG metrics for last {days} days{f' in state {state_filter}' if state_filter else ''}")
                ],
                "sql_queries": [{
                    "operation": "calculate_metrics",
                    "timestamp": datetime.utcnow().isoformat(),
                    "days": days,
                    "state_filter": state_filter,
                    "metrics": list(metrics.keys()),
                }],
            }

        except Exception as e:
            logger.error(f"Error calculating metrics: {e}")
            return {
                "error": str(e),
                "messages": [AIMessage(content=f"Error calculating metrics: {e}")],
            }

    def fetch_news_node(self, state: ReportState) -> Dict[str, Any]:
        """Fetch recent news about SRAG.
        
        Returns only the fields this node updates (for parallel execution support).
        """
        days = state.get("days", 30)
        state_filter = state.get("state_filter")
        logger.info(f"Node: Fetching news (days={days}, state={state_filter})")

        try:
            # Get recent SRAG news using the same period as metrics
            articles = news_tool.search_srag_news(days=days, max_results=10, state=state_filter)

            # Format news context with same period
            news_context = news_tool.get_recent_context(days=days, state=state_filter)
            news_citations = news_tool.format_for_citation(articles)

            return {
                "news_context": news_context,
                "news_citations": news_citations,
                "messages": [
                    AIMessage(content=f"Fetched {len(articles)} recent news articles about SRAG from last {days} days")
                ],
            }

        except Exception as e:
            logger.error(f"Error fetching news: {e}")
            return {
                "news_context": "Error fetching news",
                "news_citations": [],
                "messages": [AIMessage(content=f"Error fetching news: {e}")],
            }

    def generate_charts_node(self, state: ReportState) -> Dict[str, Any]:
        """Generate chart data for daily and monthly trends.
        
        Returns only the fields this node updates (for parallel execution support).
        """
        days = state.get("days", 30)
        state_filter = state.get("state_filter")
        logger.info(f"Node: Generating charts (days={days}, state={state_filter})")

        try:
            # Get daily cases for the specified period
            daily_data = metrics_tool.get_daily_cases_chart_data(days=days, state=state_filter)

            # Get monthly cases (last 12 months)
            monthly_data = metrics_tool.get_monthly_cases_chart_data(months=12, state=state_filter)

            return {
                "chart_data": {
                    "daily_30d": daily_data,
                    "monthly_12m": monthly_data,
                },
                "messages": [
                    AIMessage(content=f"Generated chart data: {len(daily_data)} daily points, {len(monthly_data)} monthly points")
                ],
            }

        except Exception as e:
            logger.error(f"Error generating charts: {e}")
            return {
                "chart_data": {"daily_30d": [], "monthly_12m": []},
                "messages": [AIMessage(content=f"Error generating charts: {e}")],
            }

    def write_report_node(self, state: ReportState) -> Dict[str, Any]:
        """Write the final SRAG report with LLM.
        
        This is the fan-in node that receives merged state from parallel nodes.
        """
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

            return {
                "final_report": report,
                "messages": [AIMessage(content="Report generated successfully")],
            }

        except Exception as e:
            logger.error(f"Error writing report: {e}")
            return {
                "final_report": f"Erro ao gerar relatório: {e}",
                "error": str(e),
                "messages": [AIMessage(content=f"Error writing report: {e}")],
            }

    def create_audit_node(self, state: ReportState) -> Dict[str, Any]:
        """Create complete audit trail."""
        logger.info("Node: Creating audit trail")

        # Only include messages from the LAST execution to avoid duplicates
        # The first message is always the HumanMessage for this request
        all_messages = list(state.get("messages", []))

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

        return {
            "audit_trail": audit_trail,
            "messages": [AIMessage(content="Audit trail created")],
        }

    def generate_report(
        self,
        user_request: Optional[str] = None,
        days: int = 30,
        state_filter: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate SRAG report.

        Args:
            user_request: Optional custom request
            days: Number of days to analyze
            state_filter: Optional state filter (UF)
            thread_id: Optional thread ID for checkpointing (enables conversation persistence)

        Returns:
            Complete report with metrics, charts, news, and audit trail
        """
        logger.info(f"Generating SRAG report (days={days}, state={state_filter}, thread_id={thread_id})")

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

        # Configure checkpointing with thread_id (auto-generate if not provided)
        if not thread_id:
            thread_id = str(uuid.uuid4())

        config = {
            "recursion_limit": 50,
            "configurable": {"thread_id": thread_id}
        }

        # Execute graph with checkpointing support
        final_state = self.graph.invoke(initial_state, config)

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
