"""
ReAct-style conversational agent for SRAG data exploration.

This agent demonstrates the AUTONOMOUS agent paradigm (vs the ORCHESTRATED
fan-out/fan-in pattern used in report_agent.py), allowing users to ask
open-ended questions about SRAG data.

The agent has access to 4 tools:
- query_database: Execute SQL queries on SRAG data
- search_news: Search recent SRAG-related news
- lookup_field: Look up field definitions in data dictionary
- get_metrics: Get current SRAG metrics
"""
import logging
import json
from typing import TypedDict, Annotated, Optional, List, Dict, Any
from operator import add

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection

from backend.config.settings import settings
from backend.tools.sql_tool import sql_tool
from backend.tools.news_tool import news_tool
from backend.tools.rag_tool import rag_tool
from backend.tools.metrics_tool import metrics_tool
from backend.agents.guardrails import sanitize_input, validate_output, scrub_pii, log_security_event

logger = logging.getLogger(__name__)


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

CHAT_SYSTEM_PROMPT = """Você é um assistente especializado em dados de SRAG (Síndrome Respiratória Aguda Grave) do Brasil.

Você tem acesso às seguintes ferramentas:
- get_table_schema: Obter nomes e tipos das colunas de uma tabela
- lookup_field: Consultar o dicionário de dados para entender o SIGNIFICADO de colunas e seus valores válidos
- query_database: Consultar o banco de dados SRAG com SQL
- search_news: Buscar notícias recentes sobre SRAG e surtos respiratórios
- get_metrics: Obter métricas atuais (taxa de casos, mortalidade, UTI, vacinação)

Tabelas disponíveis:
- srag_cases: Casos individuais de SRAG (~165K registros)
- monthly_metrics: Métricas mensais agregadas
- daily_metrics: Métricas diárias agregadas
- data_dictionary: Dicionário de dados

IMPORTANTE - Fluxo para consultas SQL:
1. PRIMEIRO: Use get_table_schema para ver as colunas disponíveis e seus tipos
2. SEGUNDO: Use lookup_field para entender o SIGNIFICADO das colunas relevantes e seus valores válidos
   - Exemplo: lookup_field("EVOLUCAO") revela que 1=Cura, 2=Óbito, 3=Óbito por outras causas
   - Exemplo: lookup_field("VACINA_COV") revela que 1=Sim, 2=Não, 9=Ignorado
   - Isso é ESSENCIAL para saber como filtrar corretamente!
3. TERCEIRO: Agora sim, escreva a query SQL com os filtros corretos

Diretrizes:
- Sempre responda em português
- Seja conciso e objetivo
- Quando usar dados do banco, cite a fonte e mostre números específicos
- Nunca invente dados - use as ferramentas disponíveis para obter informações precisas
- Se não souber algo, diga que não sabe e sugira como o usuário pode obter a informação
"""


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

@tool
def get_table_schema(table_name: str) -> str:
    """
    Get the schema (column names and types) for a database table.

    ALWAYS call this tool BEFORE writing a SQL query to ensure you use
    the correct column names. This prevents errors like "column not found".

    Available tables:
    - srag_cases: Individual SRAG case records (~165K rows)
    - monthly_metrics: Monthly aggregated metrics
    - daily_metrics: Daily aggregated metrics
    - data_dictionary: Field definitions

    Args:
        table_name: Name of the table to get schema for

    Returns:
        Table schema with column names, types, and sample data
    """
    try:
        allowed_tables = ['srag_cases', 'monthly_metrics', 'daily_metrics', 'data_dictionary']

        if table_name not in allowed_tables:
            return f"Erro: Tabela '{table_name}' não permitida. Tabelas disponíveis: {', '.join(allowed_tables)}"

        schema = sql_tool.get_table_schema(table_name)
        return schema

    except Exception as e:
        logger.error(f"Schema lookup error: {e}")
        return f"Erro ao obter schema: {str(e)}"


@tool
def query_database(sql_query: str) -> str:
    """
    Execute a SQL query on the SRAG database.

    IMPORTANT: Always call get_table_schema first to verify column names!

    Only SELECT queries are allowed on these tables:
    - srag_cases: Individual SRAG case records (~165K rows)
    - daily_metrics: Daily aggregated metrics
    - monthly_metrics: Monthly aggregated metrics
    - data_dictionary: Field definitions

    Args:
        sql_query: A valid SELECT SQL query

    Returns:
        Query results as formatted text, or error message
    """
    try:
        log_security_event("sql_query_attempt", {"query": sql_query[:200]})

        # Validate and execute query
        if not sql_tool.validate_query(sql_query):
            return "Erro: Query rejeitada por razões de segurança. Use apenas SELECT em tabelas permitidas."

        results = sql_tool.execute_query(sql_query)

        if not results:
            return "A consulta retornou 0 resultados."

        # Format results as readable text
        if len(results) <= 10:
            formatted = json.dumps(results, indent=2, ensure_ascii=False, default=str)
        else:
            # Summarize if too many rows
            formatted = f"Retornados {len(results)} registros. Primeiros 5:\n"
            formatted += json.dumps(results[:5], indent=2, ensure_ascii=False, default=str)
            formatted += f"\n... e mais {len(results) - 5} registros."

        # Scrub any PII from results
        formatted = scrub_pii(formatted)

        log_security_event("sql_query_success", {"rows_returned": len(results)})
        return formatted

    except Exception as e:
        logger.error(f"SQL query error: {e}")
        log_security_event("sql_query_error", {"error": str(e)})
        return f"Erro ao executar query: {str(e)}"


@tool
def search_news(query: Optional[str] = None, days: int = 30) -> str:
    """
    Search for recent news about SRAG and respiratory outbreaks.

    Args:
        query: Optional additional search terms (e.g., "São Paulo", "surto gripe")
               If not provided, searches for general SRAG news.
        days: How many days back to search (default 30)

    Returns:
        Formatted list of relevant news articles
    """
    try:
        # Build enhanced query: base SRAG terms + user terms (if provided)
        # This ensures we always search for SRAG-related content
        base_query = "SRAG síndrome respiratória aguda grave COVID-19 Brasil"
        if query:
            enhanced_query = f"{base_query} {query}"
        else:
            enhanced_query = None  # Let news_tool use its default optimized query

        articles = news_tool.search_srag_news(
            query=enhanced_query,
            days=days,
            max_results=10
        )

        if not articles:
            search_desc = f"'{query}'" if query else "SRAG"
            return f"Nenhuma notícia encontrada sobre {search_desc} nos últimos {days} dias."

        # Format articles
        result = f"Encontradas {len(articles)} notícias relevantes:\n\n"
        for i, article in enumerate(articles, 1):
            result += f"{i}. **{article.get('title', 'Sem título')}**\n"
            result += f"   Fonte: {article.get('url', 'N/A')}\n"
            if article.get('published_date'):
                result += f"   Data: {article['published_date']}\n"
            content = article.get('content', '')[:200]
            if content:
                result += f"   Resumo: {content}...\n"
            result += "\n"

        return scrub_pii(result)

    except Exception as e:
        logger.error(f"News search error: {e}")
        return f"Erro ao buscar notícias: {str(e)}"


@tool
def lookup_field(field_name: str) -> str:
    """
    Look up a field definition in the SRAG data dictionary.

    ALWAYS use this tool BEFORE writing SQL queries to understand:
    - What a column means semantically
    - What values are valid (e.g., EVOLUCAO: 1=Cura, 2=Óbito)
    - How to correctly filter data

    This is ESSENTIAL for writing correct SQL filters!

    Examples:
    - lookup_field("EVOLUCAO") -> Returns: 1=Cura, 2=Óbito, 3=Óbito outras causas
    - lookup_field("VACINA_COV") -> Returns: 1=Sim, 2=Não, 9=Ignorado
    - lookup_field("UTI") -> Returns: 1=Sim (internado UTI), 2=Não

    Args:
        field_name: The field/column name to look up (e.g., "EVOLUCAO", "VACINA_COV", "UTI")

    Returns:
        Field definition including description, valid values, and how to use in queries
    """
    try:
        # Try exact match first
        field = rag_tool.get_field_by_name(field_name)

        if field:
            return rag_tool.explain_field(field_name)

        # Try semantic search if exact match fails
        results = rag_tool.semantic_search(field_name, top_k=3)

        if not results:
            return f"Campo '{field_name}' não encontrado. Verifique o nome ou tente uma busca diferente."

        # Format results
        output = f"Campo exato não encontrado. Campos similares:\n\n"
        for field in results:
            output += f"**{field['field_name']}** ({field.get('display_name', '')})\n"
            output += f"Descrição: {field.get('description', 'N/A')}\n"
            if field.get('categories'):
                output += f"Valores: {field['categories']}\n"
            output += f"Similaridade: {field.get('similarity', 0):.0%}\n\n"

        return output

    except Exception as e:
        logger.error(f"Field lookup error: {e}")
        return f"Erro ao consultar campo: {str(e)}"


@tool
def get_metrics(days: int = 30, state: Optional[str] = None) -> str:
    """
    Get current SRAG metrics.

    Returns the 4 key metrics:
    - Case increase rate (taxa de aumento de casos)
    - Mortality rate (taxa de mortalidade)
    - ICU occupancy rate (taxa de ocupação de UTI)
    - Vaccination rate (taxa de vacinação)

    Args:
        days: Period in days to calculate metrics (default 30)
        state: Brazilian state code (e.g., "SP", "RJ") or None for national

    Returns:
        Formatted metrics summary
    """
    try:
        metrics = metrics_tool.calculate_all_metrics(days=days, state=state)

        state_label = f"Estado: {state}" if state else "Nacional"

        result = f"**Métricas SRAG - {state_label} (últimos {days} dias)**\n\n"

        # Case increase rate
        case_data = metrics.get('case_increase', {}) or {}
        result += f"📈 **Taxa de Aumento de Casos**: {(case_data.get('increase_rate') or 0):.1f}%\n"
        result += f"   Período atual: {(case_data.get('current_period_cases') or 0):,} casos\n"
        result += f"   Período anterior: {(case_data.get('previous_period_cases') or 0):,} casos\n\n"

        # Mortality rate
        mort_data = metrics.get('mortality', {}) or {}
        result += f"💀 **Taxa de Mortalidade**: {(mort_data.get('mortality_rate') or 0):.1f}%\n"
        result += f"   Total de óbitos: {(mort_data.get('total_deaths') or 0):,}\n"
        result += f"   Total de casos: {(mort_data.get('total_cases') or 0):,}\n\n"

        # ICU occupancy
        icu_data = metrics.get('icu_occupancy', {}) or {}
        result += f"🏥 **Taxa de Ocupação de UTI**: {(icu_data.get('icu_occupancy_rate') or 0):.1f}%\n"
        result += f"   Admissões UTI: {(icu_data.get('icu_admissions') or 0):,}\n"
        result += f"   Total hospitalizações: {(icu_data.get('total_hospitalizations') or 0):,}\n\n"

        # Vaccination rate
        vax_data = metrics.get('vaccination', {}) or {}
        result += f"💉 **Taxa de Vacinação**: {(vax_data.get('vaccination_rate') or 0):.1f}%\n"
        result += f"   Casos vacinados: {(vax_data.get('vaccinated_cases') or 0):,}\n"
        result += f"   Taxa vacinação completa: {(vax_data.get('full_vaccination_rate') or 0):.1f}%\n"

        return result

    except Exception as e:
        logger.error(f"Metrics error: {e}")
        return f"Erro ao calcular métricas: {str(e)}"


# =============================================================================
# AGENT STATE
# =============================================================================

class ChatState(TypedDict):
    """State for the chat agent."""
    messages: Annotated[list, add_messages]


# =============================================================================
# AGENT GRAPH
# =============================================================================

# List of tools available to the agent
tools = [get_table_schema, query_database, search_news, lookup_field, get_metrics]


def create_chat_agent():
    """Create and compile the chat agent graph."""

    # Initialize LLM with tools
    llm = ChatOpenAI(
        model="gpt-5-mini",
        temperature=0.3,
        openai_api_key=settings.openai_api_key,
    )
    llm_with_tools = llm.bind_tools(tools)

    # Define the assistant node
    def assistant(state: ChatState) -> dict:
        """Process messages and decide on tool use or response."""
        messages = state["messages"]

        # Add system prompt as first message if not present
        if not messages or not isinstance(messages[0], dict) or messages[0].get("role") != "system":
            system_msg = {"role": "system", "content": CHAT_SYSTEM_PROMPT}
            messages = [system_msg] + list(messages)

        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    # Define the routing function
    def should_continue(state: ChatState) -> str:
        """Determine if we should continue to tools or end."""
        messages = state["messages"]
        last_message = messages[-1]

        # If there are tool calls, route to tools
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"

        # Otherwise, end
        return END

    # Build the graph
    graph = StateGraph(ChatState)

    # Add nodes
    graph.add_node("assistant", assistant)
    graph.add_node("tools", ToolNode(tools))

    # Add edges
    graph.add_edge(START, "assistant")
    graph.add_conditional_edges(
        "assistant",
        should_continue,
        {"tools": "tools", END: END}
    )
    graph.add_edge("tools", "assistant")

    # Compile with checkpointer for conversation persistence using sync connection
    db_connection = Connection.connect(
        settings.langgraph_checkpoint_url,
        autocommit=True,
        prepare_threshold=0
    )
    checkpointer = PostgresSaver(conn=db_connection)
    checkpointer.setup()

    return graph.compile(checkpointer=checkpointer)


# =============================================================================
# CHAT AGENT CLASS
# =============================================================================

class SRAGChatAgent:
    """
    Chat agent for interactive SRAG data exploration.

    Demonstrates the AUTONOMOUS agent paradigm using ReAct pattern:
    - User asks question
    - Agent decides which tools to use
    - Agent executes tools and synthesizes response
    - Conversation persists via PostgresSaver
    """

    def __init__(self):
        """Initialize the chat agent."""
        self.graph = create_chat_agent()
        logger.info("SRAGChatAgent initialized with ReAct pattern")

    def chat(
        self,
        message: str,
        thread_id: str,
    ) -> Dict[str, Any]:
        """
        Process a chat message.

        Args:
            message: User's message
            thread_id: Unique conversation thread ID for persistence

        Returns:
            {
                "response": str,
                "thread_id": str,
                "tool_calls": List[Dict] - tools that were called
            }
        """
        # Sanitize input
        sanitized_message = sanitize_input(message)
        log_security_event("chat_message_received", {
            "thread_id": thread_id,
            "message_length": len(message)
        })

        # Prepare input state
        input_state = {
            "messages": [HumanMessage(content=sanitized_message)]
        }

        # Configuration for checkpointer
        config = {"configurable": {"thread_id": thread_id}}

        try:
            # Run the agent
            result = self.graph.invoke(input_state, config)

            # Extract response and tool calls
            messages = result.get("messages", [])

            # Find the index of the last HumanMessage (the one we just sent)
            last_human_idx = -1
            for i, msg in enumerate(messages):
                if isinstance(msg, HumanMessage):
                    last_human_idx = i

            # Collect only NEW tool calls (after the last HumanMessage)
            response_text = ""
            tool_calls_made = []

            # First pass: collect tool messages only from this turn
            for msg in messages[last_human_idx + 1:]:
                if isinstance(msg, ToolMessage):
                    tool_calls_made.append({
                        "name": msg.name,
                        "result_preview": str(msg.content)[:100]
                    })

            # Second pass: find the last AI message with content (the final response)
            for msg in reversed(messages):
                if isinstance(msg, AIMessage) and msg.content:
                    response_text = msg.content
                    break

            # Validate output and extract scrubbed text
            validation_result = validate_output(response_text)
            response_text = validation_result.get("scrubbed_output", response_text)

            log_security_event("chat_response_sent", {
                "thread_id": thread_id,
                "tools_used": len(tool_calls_made)
            })

            return {
                "response": response_text,
                "thread_id": thread_id,
                "tool_calls": tool_calls_made
            }

        except Exception as e:
            logger.error(f"Chat error: {e}")
            log_security_event("chat_error", {
                "thread_id": thread_id,
                "error": str(e)
            })
            return {
                "response": f"Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente.",
                "thread_id": thread_id,
                "tool_calls": []
            }


# Global instance
chat_agent = SRAGChatAgent()
