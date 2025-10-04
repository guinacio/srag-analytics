"""FastAPI backend with LangServe for SRAG Analytics."""
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.config.settings import settings
from backend.db.connection import init_db
from backend.agents.report_agent import report_agent
from backend.agents.guardrails import sanitize_input, validate_output, scrub_pii
from backend.tools.metrics_tool import metrics_tool
from backend.tools.news_tool import news_tool
from backend.tools.sql_tool import sql_tool
from backend.tools.rag_tool import rag_tool

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting SRAG Analytics API...")
    try:
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

    yield

    # Shutdown
    logger.info("Shutting down SRAG Analytics API...")


# Initialize FastAPI app
app = FastAPI(
    title="SRAG Analytics API",
    description="AI-powered SRAG analytics with LangGraph agents",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class ReportRequest(BaseModel):
    """Request model for report generation."""
    user_request: Optional[str] = None
    days: int = 30
    state: Optional[str] = None


class ReportResponse(BaseModel):
    """Response model for generated report."""
    report: str
    metrics: Dict[str, Any]
    chart_data: Dict[str, Any]
    news_citations: list
    audit_trail: Dict[str, Any]


class MetricsRequest(BaseModel):
    """Request model for metrics calculation."""
    days: Optional[int] = 30
    state: Optional[str] = None


class NewsRequest(BaseModel):
    """Request model for news search."""
    query: Optional[str] = None
    days: int = 7
    max_results: int = 10


class ExplainFieldRequest(BaseModel):
    """Request model for field explanation."""
    field_name: str


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "environment": settings.environment}


# Main report generation endpoint
@app.post("/report", response_model=ReportResponse)
async def generate_report(request: ReportRequest):
    """
    Generate comprehensive SRAG report.

    This endpoint orchestrates:
    1. Metrics calculation
    2. News retrieval
    3. Chart generation
    4. Report writing
    5. Audit trail creation
    """
    try:
        logger.info(f"Report request: days={request.days}, state={request.state}")

        # Sanitize user input
        user_request = sanitize_input(request.user_request) if request.user_request else None

        # Generate report using agent
        result = report_agent.generate_report(
            user_request=user_request,
            days=request.days,
            state_filter=request.state,
        )

        # Validate and scrub output
        if result.get("report"):
            validation = validate_output(result["report"])
            if not validation["valid"]:
                logger.warning(f"Output validation issues: {validation['issues']}")
            result["report"] = validation["scrubbed_output"]

        # Check for errors
        if result.get("error"):
            raise HTTPException(status_code=500, detail=result["error"])

        return ReportResponse(
            report=result.get("report", ""),
            metrics=result.get("metrics", {}),
            chart_data=result.get("chart_data", {}),
            news_citations=result.get("news_citations", []),
            audit_trail=result.get("audit_trail", {}),
        )

    except Exception as e:
        logger.error(f"Report generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Metrics endpoint
@app.post("/metrics")
async def get_metrics(request: MetricsRequest):
    """Calculate SRAG metrics."""
    try:
        logger.info(f"Metrics request: days={request.days}, state={request.state}")

        metrics = metrics_tool.calculate_all_metrics(
            days=request.days,
            state=request.state,
        )

        return metrics

    except Exception as e:
        logger.error(f"Metrics calculation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# News endpoint
@app.post("/news")
async def search_news(request: NewsRequest):
    """Search for SRAG-related news."""
    try:
        logger.info(f"News request: query={request.query}, days={request.days}")

        articles = news_tool.search_srag_news(
            query=request.query,
            days=request.days,
            max_results=request.max_results,
        )

        citations = news_tool.format_for_citation(articles)

        return {
            "articles": articles,
            "citations": citations,
            "count": len(articles),
        }

    except Exception as e:
        logger.error(f"News search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Chart data endpoint
@app.get("/charts/daily")
async def get_daily_chart_data(days: int = Query(30, ge=1, le=365)):
    """Get daily cases chart data."""
    try:
        data = metrics_tool.get_daily_cases_chart_data(days=days)
        return {"data": data, "days": days}

    except Exception as e:
        logger.error(f"Chart data error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/charts/monthly")
async def get_monthly_chart_data(months: int = Query(12, ge=1, le=36)):
    """Get monthly cases chart data."""
    try:
        data = metrics_tool.get_monthly_cases_chart_data(months=months)
        return {"data": data, "months": months}

    except Exception as e:
        logger.error(f"Chart data error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Dictionary/RAG endpoints
@app.post("/dictionary/explain")
async def explain_field(request: ExplainFieldRequest):
    """Explain a data dictionary field."""
    try:
        explanation = rag_tool.explain_field(request.field_name)
        return {"field_name": request.field_name, "explanation": explanation}

    except Exception as e:
        logger.error(f"Field explanation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dictionary/search")
async def search_dictionary(query: str = Query(..., min_length=2)):
    """Semantic search in data dictionary."""
    try:
        results = rag_tool.semantic_search(query, top_k=5)
        return {"query": query, "results": results}

    except Exception as e:
        logger.error(f"Dictionary search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dictionary/fields")
async def list_fields():
    """List all available fields."""
    try:
        fields = rag_tool.list_all_fields()
        return {"fields": fields, "count": len(fields)}

    except Exception as e:
        logger.error(f"List fields error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# SQL preview endpoint (for transparency)
@app.get("/sql/tables")
async def list_tables():
    """List available database tables."""
    try:
        tables = sql_tool.list_tables()
        return {"tables": tables}

    except Exception as e:
        logger.error(f"List tables error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sql/schema/{table_name}")
async def get_table_schema(table_name: str):
    """Get schema for a specific table."""
    try:
        schema = sql_tool.get_table_schema(table_name)
        return {"table": table_name, "schema": schema}

    except Exception as e:
        logger.error(f"Get schema error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
