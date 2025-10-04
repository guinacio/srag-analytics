# SQL Tool Implementation Guide

## Current Status

The `sql_tool.py` is **available but not used in production** for security and reliability reasons.

The report agent currently uses **pre-defined SQL queries** in `metrics_tool.py` for:
- ✅ Predictable, tested results
- ✅ No SQL injection risks
- ✅ Consistent performance
- ✅ Easier debugging and auditing

## Why sql_tool Exists

The tool is designed for **future user-driven data exploration features** where users can ask natural language questions about SRAG data.

### Example Use Cases

**User Question** → **LLM-Generated SQL** → **Safe Execution**

```
User: "Show me age distribution of SRAG cases in São Paulo"
↓
SQL: SELECT
       CASE
         WHEN nu_idade_n < 18 THEN '0-17'
         WHEN nu_idade_n < 65 THEN '18-64'
         ELSE '65+'
       END as age_group,
       COUNT(*) as cases
     FROM srag_cases
     WHERE sg_uf_not = 'SP'
     GROUP BY age_group
```

```
User: "What's the trend of ICU admissions in the last 3 months?"
↓
SQL: SELECT dt_entuti::date as date, COUNT(*) as admissions
     FROM srag_cases
     WHERE dt_entuti >= CURRENT_DATE - INTERVAL '3 months'
     AND uti = 1
     GROUP BY dt_entuti
     ORDER BY dt_entuti
```

## Implementation Plan

### 1. Create New Endpoint

Add a dedicated `/query` endpoint (separate from `/report`):

```python
@app.post("/query")
async def natural_language_query(request: QueryRequest):
    """
    Execute natural language data query.
    Requires explicit user opt-in.
    """
    # 1. Generate SQL from natural language
    sql = sql_tool.generate_query(request.question)

    # 2. Show SQL to user for transparency
    logger.info(f"Generated SQL: {sql}")

    # 3. Execute with safety checks
    results = sql_tool.execute_query(sql)

    # 4. Return results with SQL for audit
    return {
        "question": request.question,
        "sql": sql,
        "results": results,
        "row_count": len(results)
    }
```

### 2. Frontend Implementation

Add a new "Data Explorer" tab in Streamlit:

```python
with tab_explorer:
    st.header("🔍 Explorador de Dados SRAG")

    st.warning("""
    ⚠️ Esta funcionalidade usa IA para gerar consultas SQL.
    A consulta SQL será exibida para sua revisão antes da execução.
    """)

    question = st.text_input("Faça uma pergunta sobre os dados SRAG:")

    if st.button("Consultar"):
        result = api_request("/query", method="POST", data={"question": question})

        # Show generated SQL
        with st.expander("📋 SQL Gerado"):
            st.code(result["sql"], language="sql")

        # Show results
        st.dataframe(pd.DataFrame(result["results"]))
```

### 3. Security Checklist

Before enabling sql_tool in production:

- [ ] **User Authentication**: Require logged-in users
- [ ] **Rate Limiting**: Max 10 queries per user per hour
- [ ] **Query Logging**: Log all questions, SQL, and results
- [ ] **SQL Display**: Always show generated SQL to users
- [ ] **Result Limits**: Enforce 10,000 row limit
- [ ] **Timeout**: 30-second query timeout active
- [ ] **Read-Only**: Verify readonly_user connection
- [ ] **Monitoring**: Alert on suspicious queries
- [ ] **Audit Trail**: Save to database for compliance

### 4. Testing

Test cases to validate before deployment:

```python
# Test 1: Valid query
question = "How many SRAG cases in São Paulo last month?"
# Expected: Valid SELECT query, returns results

# Test 2: SQL injection attempt
question = "'; DROP TABLE srag_cases; --"
# Expected: Query validation fails, no execution

# Test 3: DDL attempt
question = "Delete all records from srag_cases"
# Expected: Rejected (no DELETE allowed)

# Test 4: Performance
question = "Show all SRAG cases with all details"
# Expected: Row limit applied, timeout enforced
```

## Current Architecture (Safe)

```
User Request
    ↓
Report Agent (LangGraph)
    ↓
Pre-defined SQL Queries (metrics_tool.py)
    ↓
PostgreSQL (readonly_user)
    ↓
Results
```

## Future Architecture (With sql_tool)

```
User Question
    ↓
Natural Language → SQL (sql_tool + LLM)
    ↓
Safety Validation (sql_tool.validate_query)
    ↓
Display SQL to User (transparency)
    ↓
Execute with Guardrails (readonly_user, timeout, row limit)
    ↓
Results + Audit Log
```

## Safety Layers in sql_tool

1. **Database Level**
   - Read-only user (`readonly_user`)
   - Transaction read-only mode
   - No DDL/DML permissions

2. **Query Validation**
   - Only SELECT statements allowed
   - Table allowlist (srag_cases, data_dictionary, daily_metrics, monthly_metrics)
   - Dangerous keyword blocking (DROP, DELETE, UPDATE, etc.)

3. **Resource Limits**
   - 10,000 row limit (auto-added if missing)
   - 30-second query timeout
   - Connection pooling

4. **Logging & Audit**
   - All queries logged
   - Rejection reasons logged
   - User attribution required

## Recommendation

**Keep current architecture for production reports.**

Only implement sql_tool if there's a clear user need for ad-hoc data exploration, and follow the security checklist above.

The tool is production-ready from a code perspective, but requires additional safeguards (authentication, rate limiting, monitoring) before enabling.
