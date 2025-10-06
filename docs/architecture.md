# SRAG Analytics - Architecture Diagram

## System Architecture Overview

```
+----------------------------------------------------------------------+
|                        USER INTERFACE                                |
|                                                                      |
|  +------------------------------------------------------------+      |
|  |          Streamlit Frontend (Port 8501)                    |      |
|  |  +---------+  +---------+  +---------+  +----------+      |      |
|  |  |Dashboard|  | Metrics |  |  News   |  |Dictionary|      |      |
|  |  |  View   |  |  View   |  |  View   |  |   RAG    |      |      |
|  |  +---------+  +---------+  +---------+  +----------+      |      |
|  +------------------------------------------------------------+      |
+----------------------------------------------------------------------+
                               |
                               | HTTP REST API
                               V
+----------------------------------------------------------------------+
|                    BACKEND API LAYER                                 |
|                                                                      |
|  +------------------------------------------------------------+      |
|  |         FastAPI + LangServe (Port 8000)                    |      |
|  |                                                            |      |
|  |  Endpoints:                                                |      |
|  |  " POST /report      - Generate full report                |      |
|  |  " POST /metrics     - Calculate metrics                   |      |
|  |  " POST /news        - Search news                         |      |
|  |  " GET  /charts/*    - Chart data                          |      |
|  |  " GET  /dictionary/* - Field explanations                 |      |
|  +------------------------------------------------------------+      |
+----------------------------------------------------------------------+
                               |
                               V
+----------------------------------------------------------------------+
|               LANGGRAPH AGENT ORCHESTRATOR                           |
|                                                                      |
|  +----------------------------------------------------+            |
|  |          Main Orchestrator Agent (Supervisor)        |            |
|  |                                                      |            |
|  |  State Graph:                                        |            |
|  |  1. Calculate Metrics                              |            |
|  |  2. Fetch News Context                             |            |
|  |  3. Generate Charts                                |            |
|  |  4. Write Report (LLM)                            |            |
|  |  5. Create Audit Trail                            |            |
|  +----------------------------------------------------+            |
|                                                                      |
|           |          |          |          |                        |
|           V          V          V          V                        |
|     +---------+ +--------+ +--------+ +----------+                 |
|     | Metrics | |  News  | |  RAG   | |   SQL    |                 |
|     |  Tool   | |  Tool  | |  Tool  | |  Agent   |                 |
|     +---------+ +--------+ +--------+ +----------+                 |
+----------------------------------------------------------------------+
       |            |            |            |
       |            |            |            |
       V            V            V            V
+----------+  +----------+  +----------+  +--------------+
|PostgreSQL|  | Tavily   |  | OpenAI   |  |  LangSmith   |
|+pgvector |  |  News    |  |   LLM    |  |  Tracing     |
|          |  |   API    |  | GPT-4o   |  |  (Optional)  |
|  Tables: |  |          |  |          |  |              |
|  " srag_ |  |  Real-   |  | Embedds: |  | Observ-      |
|    cases |  |  time    |  | text-emb |  | ability      |
|  " data_ |  |  news    |  | -3-small |  |              |
|    dict  |  |  search  |  |          |  |              |
|  " daily |  |          |  |          |  |              |
|  " monthl|  |          |  |          |  |              |
+----------+  +----------+  +----------+  +--------------+
```

## Component Details

### 1. Frontend Layer (Streamlit)

- **Technology**: Streamlit 1.40+
- **Features**:
  - Interactive dashboards
  - Filters (date range, state)
  - Plotly charts
  - News display
  - Audit trail download
- **Communication**: REST API calls to backend

### 2. Backend API Layer (FastAPI)

- **Technology**: FastAPI 0.115+ with LangServe
- **Features**:
  - RESTful API endpoints
  - Request validation (Pydantic)
  - CORS middleware
  - Health checks
  - Auto-generated OpenAPI docs
- **Security**:
  - Input sanitization
  - PII scrubbing
  - Error handling

### 3. Agent Orchestration (LangGraph)

#### Main Orchestrator Agent

- **Framework**: LangGraph 0.6.8
- **Pattern**: Supervisor with state graph
- **Nodes**:
  1. **Calculate Metrics Node**
     - Calls metrics tool
     - Computes 4 required metrics
  2. **Fetch News Node**
     - Calls Tavily Search
     - Retrieves recent SRAG news
  3. **Generate Charts Node**
     - Queries daily/monthly aggregates
     - Formats for Plotly
  4. **Write Report Node**
     - Uses GPT-4o to synthesize report
     - Combines metrics + news context
  5. **Create Audit Node**
     - Logs all operations
     - Creates JSON audit trail

- **Features**:
  - Checkpointer for persistence
  - State management
  - Error handling

### 4. Tools Layer

#### A. SQL Agent Tool

- **Technology**: LangChain SQL Toolkit
- **Database**: PostgreSQL (read-only connection)
- **Safety Guardrails**:
  - Table allowlist (4 tables only)
  - Query validation (SELECT only)
  - Timeouts (30s)
  - Row limits (10k max)
  - Read-only user permissions

#### B. News Tool

- **Technology**: Tavily Search API
- **Features**:
  - Real-time news search
  - Topic filter: "news"
  - Geographic filter: Brazil
  - Depth: advanced
  - Configurable days/results

#### C. RAG Tool

- **Technology**: pgvector semantic search
- **Features**:
  - OpenAI embeddings (1536 dim)
  - Cosine similarity search
  - Data dictionary lookup
  - Field explanations

#### D. Metrics Tool

- **Technology**: Direct SQL queries
- **Features**:
  - Pre-computed aggregates
  - Materialized views
  - 4 metric calculations
  - Chart data generation

### 5. Data Layer

#### PostgreSQL + pgvector

**Tables**:

1. **srag_cases**
   - Main fact table (~165k rows)
   - Curated from DATASUS CSV
   - Indexed for performance

2. **data_dictionary**
   - Field definitions
   - Vector embeddings (pgvector)
   - Source: SIVEP-Gripe PDF

3. **daily_metrics**
   - Materialized daily aggregates
   - Fast chart rendering

4. **monthly_metrics**
   - Materialized monthly aggregates
   - 12-month trends

**Security**:
- Two users: `srag_user` (admin), `srag_readonly` (agent)
- Read-only connection for SQL agent

### 6. External Services

#### A. LLM (OpenAI)

- **Model**: GPT-4o (main), GPT-4o-mini (SQL)
- **Usage**:
  - Report generation
  - SQL query generation
  - Text embeddings

#### B. News API (Tavily)

- **Purpose**: Real-time SRAG news
- **Features**:
  - Advanced search
  - News topic filter
  - Recent articles only

#### C. Observability (LangSmith - Optional)

- **Features**:
  - Agent trace logging
  - Prompt tracking
  - Eval datasets
  - Debugging

## Data Flow

### Report Generation Flow

```
1. User clicks "Generate Report" in Streamlit
   “
2. POST /report ’ FastAPI endpoint
   “
3. LangGraph orchestrator invoked
   “
4. Parallel execution:
   - Metrics Tool ’ PostgreSQL (SELECT queries)
   - News Tool ’ Tavily API
   - RAG Tool ’ pgvector search
   “
5. LLM synthesis (GPT-4o)
   - Combines metrics + news
   - Generates narrative
   “
6. Audit trail creation
   - Logs all operations
   - JSON format
   “
7. Response to Streamlit
   - Report markdown
   - Metrics JSON
   - Chart data
   - News citations
   - Audit trail
   “
8. Streamlit renders:
   - Formatted report
   - Plotly charts
   - News cards
   - Download buttons
```

## Security & Governance

### Guardrails

1. **Input Sanitization**
   - Remove SQL injection patterns
   - Length limits
   - Special character filtering

2. **PII Scrubbing**
   - Regex-based detection
   - Pre-prompt and output redaction
   - Patterns: CPF, RG, phone, email, credit card

3. **SQL Safety**
   - Read-only database user
   - Query validation
   - Table allowlist
   - Timeouts
   - Row limits

4. **Output Validation**
   - Schema constraints
   - Length limits
   - PII detection

### Audit Trail

Every report includes:
- Timestamp
- Metrics calculated
- SQL queries executed
- News sources cited
- LLM prompts/responses
- Error logs

**Format**: JSON (downloadable)

### Observability

- LangSmith tracing (optional)
- FastAPI logging
- Database query logs

## Deployment

### Development

```bash
docker-compose up -d      # Backend + PostgreSQL
streamlit run frontend/app.py  # Frontend
```

### Production Considerations

1. Add authentication (OAuth2/JWT)
2. Implement rate limiting
3. Use secrets manager (not .env)
4. Add caching (Redis)
5. Horizontal scaling (K8s)
6. CDN for frontend
7. Database replication
8. Monitoring (Prometheus/Grafana)

## Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Frontend | Streamlit | 1.40+ |
| Backend | FastAPI | 0.115+ |
| Agent Framework | LangGraph | 0.6.8 |
| LLM | OpenAI GPT-4o / 5 | Latest |
| Database | PostgreSQL | 17 |
| Vector Store | pgvector | Latest |
| News API | Tavily | Latest |
| Observability | LangSmith | Optional |

---

**Document Version**: 1.0
**Date**: 2025-10-04
**Author**: Guilherme Inácio
