# SRAG Analytics - Complete Setup Instructions

## Prerequisites

Before starting, ensure you have:

- [x] Python 3.11 or higher
- [x] Docker and Docker Compose
- [x] OpenAI API key ([Get one here](https://platform.openai.com/api-keys))
- [x] Tavily API key ([Get one here](https://tavily.com))

## Step-by-Step Setup

### 1. Configure Environment Variables

```bash
# Copy the example file
cp .env.example .env

# Edit .env and add your API keys
# Use any text editor (nano, vim, VSCode, etc.)
nano .env
```

Update these lines in `.env`:
```env
OPENAI_API_KEY=sk-your-actual-openai-key-here
TAVILY_API_KEY=tvly-your-actual-tavily-key-here
```

### 2. Start Docker Services

```bash
# Start PostgreSQL and backend containers
docker-compose up -d

# Verify services are running
docker-compose ps
```

You should see:
- `srag_postgres` - Running (port 5432)
- `srag_backend` - Running (port 8000)

### 3. Install Python Dependencies (Local)

```bash
# Install the project in editable mode
pip install -e .
```

This installs all dependencies from `pyproject.toml`.

### 4. Initialize Database

Run these commands **in order**:

#### 4a. Create Database Tables

```bash
# Option 1: Run locally (recommended)
python -m backend.db.init_database

# Option 2: Run in Docker container
docker-compose exec backend python -m backend.db.init_database
```

Expected output:
```
Creating pgvector extension...
Creating read-only user...
Creating database tables...
Database initialization complete!
```

#### 4b. Ingest SRAG Data

**IMPORTANT**: This step processes ~165,000 rows and takes 5-10 minutes.

```bash
# Option 1: Run locally (recommended)
python -m backend.db.ingestion

# Option 2: Run in Docker container
docker-compose exec backend python -m backend.db.ingestion
```

Expected output:
```
Starting ingestion of data/INFLUD25-29-09-2025.csv
Ingested 1000 rows...
Ingested 2000 rows...
...
Successfully ingested 165000 rows
Computing daily metrics...
Computing monthly metrics...
Granting read-only permissions...
Data ingestion complete!
```

#### 4c. Parse Data Dictionary

```bash
# Option 1: Run locally (recommended)
python -m backend.db.dictionary_parser

# Option 2: Run in Docker container
docker-compose exec backend python -m backend.db.dictionary_parser
```

Expected output:
```
Parsing PDF dictionary...
Extracted 11 field definitions
Generating embeddings...
Successfully populated 11 dictionary entries
```

### 5. Launch Streamlit Frontend

```bash
# Start the Streamlit app
streamlit run frontend/app.py
```

The app will open automatically at: http://localhost:8501

## Verification

### Test 1: Backend API

```bash
# Health check
curl http://localhost:8000/health

# Expected: {"status":"healthy","environment":"development"}
```

### Test 2: List Database Tables

```bash
curl http://localhost:8000/sql/tables

# Expected: {"tables":["srag_cases","data_dictionary","daily_metrics","monthly_metrics"]}
```

### Test 3: Get Metrics

```bash
curl -X POST http://localhost:8000/metrics \
  -H "Content-Type: application/json" \
  -d '{"days": 30}'

# Should return JSON with all 4 metrics
```

### Test 4: Generate Report (Frontend)

1. Open http://localhost:8501
2. Click "Generate Report" in sidebar
3. Wait 30-60 seconds
4. View metrics, charts, and news

## Troubleshooting

### Issue: "Connection refused" to backend

```bash
# Check backend logs
docker-compose logs backend

# Restart backend
docker-compose restart backend
```

### Issue: "Database connection error"

```bash
# Check PostgreSQL logs
docker-compose logs postgres

# Ensure PostgreSQL is ready
docker-compose exec postgres pg_isready -U srag_user
```

### Issue: "Relation srag_cases does not exist"

You need to run the initialization first:

```bash
python -m backend.db.init_database
```

### Issue: "ModuleNotFoundError"

Install dependencies:

```bash
pip install -e .
```

### Issue: "OpenAI API error"

- Verify your API key is correct in `.env`
- Check you have credits: https://platform.openai.com/usage
- Restart backend after updating `.env`:
  ```bash
  docker-compose restart backend
  ```

### Issue: CSV ingestion is too slow

This is normal! The DATASUS files are large (42MB+ each). The ingestion:
- Parses ~165,000 rows
- Cleans and transforms data
- Inserts into PostgreSQL
- Computes aggregates

**Expected time**: 5-10 minutes

Watch progress:
```bash
# If running locally
# (Progress logs appear in terminal)

# If running in Docker
docker-compose logs -f backend
```

## What's Next?

After successful setup:

1. **Explore the Dashboard** - Click "Generate Report" to see the AI in action
2. **View API Docs** - Visit http://localhost:8000/docs
3. **Read Architecture** - See `docs/architecture.md`
4. **Customize Metrics** - Edit `backend/tools/metrics_tool.py`
5. **Add Visualizations** - Modify `frontend/app.py`

## Common Commands

```bash
# Start everything
docker-compose up -d

# Stop everything
docker-compose down

# View logs
docker-compose logs -f backend
docker-compose logs -f postgres

# Restart a service
docker-compose restart backend

# Rebuild after code changes
docker-compose up -d --build backend

# Clean everything (WARNING: deletes data!)
docker-compose down -v

# Re-run ingestion
python -m backend.db.init_database
python -m backend.db.ingestion
python -m backend.db.dictionary_parser
```

## Development Workflow

1. **Backend changes**: Edit code in `backend/`, restart:
   ```bash
   docker-compose restart backend
   ```

2. **Frontend changes**: Streamlit auto-reloads, just refresh browser

3. **Database changes**: Re-run migrations or ingestion

4. **Add new dependencies**: Update `pyproject.toml`, then:
   ```bash
   pip install -e .
   docker-compose up -d --build backend
   ```

## Need Help?

- Review [README.md](README.md) for detailed docs
- Check [PROJECT_COMPLETION_SUMMARY.md](PROJECT_COMPLETION_SUMMARY.md) for architecture
- Open an issue with:
  - Error message
  - Steps to reproduce
  - Docker logs: `docker-compose logs`

---

**Ready to analyze SRAG data!**