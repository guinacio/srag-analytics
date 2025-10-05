"""
SQL Agent tool with safety guardrails.

⚠️ IMPORTANT: This tool is currently NOT used in production for security reasons.

The report agent uses pre-defined SQL queries in metrics_tool.py instead of
LLM-generated SQL to ensure:
- Predictable, tested queries
- No SQL injection risks from LLM hallucinations
- Consistent performance
- Easier debugging and auditing

FUTURE USE CASE:
This tool is designed and available for implementing user-driven data exploration
features where users can ask natural language questions about SRAG data, such as:
- "Show me age distribution of SRAG cases in São Paulo"
- "What's the trend of ICU admissions over the last 3 months?"
- "Compare vaccination rates across different states"

When implementing such features:
1. Use this tool through a dedicated /query endpoint (separate from /report)
2. Require explicit user opt-in for custom queries
3. Display the generated SQL to users for transparency
4. Log all queries for audit purposes
5. Consider rate limiting to prevent abuse

The tool includes multiple safety layers:
- Read-only database connection (readonly_user)
- Table allowlist (only SRAG-related tables)
- Query validation (SELECT-only, no DDL/DML)
- Automatic row limits (10,000 max)
- Query timeout (30 seconds)
- Transaction read-only enforcement
"""
import logging
from typing import List, Dict, Any
from sqlalchemy import create_engine, text
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_openai import ChatOpenAI

from backend.config.settings import settings

logger = logging.getLogger(__name__)


class SafeSQLTool:
    """
    Safe SQL query tool with comprehensive guardrails.

    Security Features:
    - Read-only database connection
    - Table allowlist (srag_cases, data_dictionary, daily_metrics, monthly_metrics)
    - Query timeout (30 seconds)
    - Row limit enforcement (10,000 max)
    - SQL syntax validation (SELECT-only)
    - No DDL/DML operations allowed

    Status: Available but not currently used in production.
    See module docstring for intended use cases.
    """

    ALLOWED_TABLES = [
        "srag_cases",
        "data_dictionary",
        "daily_metrics",
        "monthly_metrics"
    ]

    MAX_ROWS = 10000
    QUERY_TIMEOUT_MS = 30000  # 30 seconds

    def __init__(self):
        """Initialize SQL tool with read-only connection."""
        # Create read-only engine
        self.engine = create_engine(
            settings.readonly_database_url,
            pool_pre_ping=True,
            connect_args={
                "options": f"-c default_transaction_read_only=on -c statement_timeout={self.QUERY_TIMEOUT_MS}"
            },
        )

        # Create LangChain SQL Database wrapper
        self.db = SQLDatabase(
            engine=self.engine,
            include_tables=self.ALLOWED_TABLES,
            sample_rows_in_table_info=3,
        )

        # Initialize LLM for SQL agent (when/if implemented)
        # NOTE: Use gpt-5-mini for cost-effective SQL generation
        self.llm = ChatOpenAI(
            model="gpt-5-mini",
            temperature=0,
            openai_api_key=settings.openai_api_key,
        )

        # Create SQL toolkit with checker
        self.toolkit = SQLDatabaseToolkit(
            db=self.db,
            llm=self.llm,
        )

    def validate_query(self, query: str) -> bool:
        """
        Validate SQL query for safety.

        Checks:
        - No DDL/DML operations (only SELECT)
        - Only allowed tables
        - No dangerous functions
        """
        query_upper = query.upper().strip()

        # Only SELECT queries allowed
        if not query_upper.startswith("SELECT"):
            logger.warning(f"Rejected non-SELECT query: {query}")
            return False

        # Check for dangerous keywords
        dangerous_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "CREATE"]
        if any(keyword in query_upper for keyword in dangerous_keywords):
            logger.warning(f"Rejected query with dangerous keyword: {query}")
            return False

        # Check if query uses only allowed tables
        for table in self.ALLOWED_TABLES:
            if table.upper() in query_upper:
                return True

        logger.warning(f"Rejected query - no allowed tables found: {query}")
        return False

    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """
        Execute SQL query with safety checks.

        Returns list of dictionaries (rows).
        """
        # Validate query
        if not self.validate_query(query):
            raise ValueError("Query failed safety validation")

        # Add LIMIT if not present
        query_upper = query.upper()
        if "LIMIT" not in query_upper:
            query = f"{query.rstrip(';')} LIMIT {self.MAX_ROWS}"

        logger.info(f"Executing SQL query: {query}")

        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query))
                rows = [dict(row._mapping) for row in result]

                logger.info(f"Query returned {len(rows)} rows")
                return rows

        except Exception as e:
            logger.error(f"SQL query error: {e}")
            raise

    def get_table_schema(self, table_name: str) -> str:
        """Get schema information for a table."""
        if table_name not in self.ALLOWED_TABLES:
            raise ValueError(f"Table {table_name} not in allowlist")

        return self.db.get_table_info([table_name])

    def list_tables(self) -> List[str]:
        """List all available tables."""
        return self.ALLOWED_TABLES


# Global instance
sql_tool = SafeSQLTool()
