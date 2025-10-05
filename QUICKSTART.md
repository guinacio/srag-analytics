# SRAG Analytics - Quick Start Guide

Get the SRAG Analytics system running in under 10 minutes!

## Prerequisites Checklist

- [ ] Python 3.12 or higher installed
- [ ] Docker and Docker Compose installed
- [ ] OpenAI API key (get from [platform.openai.com](https://platform.openai.com))
- [ ] Tavily API key (get from [tavily.com](https://tavily.com))

## 5-Step Setup

### Step 1: Clone & Navigate

```bash
git clone <your-repo-url>
cd desafio_indicium
```

### Step 2: Configure API Keys

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your keys
nano .env  # or use any text editor
```

**Required changes in `.env`:**
```env
OPENAI_API_KEY=sk-your-actual-key-here
TAVILY_API_KEY=tvly-your-actual-key-here
```

### Step 3: Start Docker Services

```bash
# Start PostgreSQL and backend
docker-compose up -d

# Check services are running
docker-compose ps
```

You should see:
- `srag_postgres` - Running on port 5432
- `srag_backend` - Running on port 8000

**Note**: Database tables are automatically created when the backend container starts.

### Step 4: Ingest Data

**Important**: The CSV files in `/data` need to be ingested.

```bash
# Option A: Run from host (if you have Python installed)
pip install -e .
python -m backend.db.ingestion
python -m backend.db.dictionary_parser

# Option B: Run inside Docker container
docker-compose exec backend python -m backend.db.ingestion
docker-compose exec backend python -m backend.db.dictionary_parser
```

**This will take 5-10 minutes** (Thousands of rows being processed)

### Step 5: Launch Frontend

```bash
# Install dependencies if not already done
pip install -e .

# Run Streamlit
streamlit run frontend/app.py
```

**You're done!** Open your browser to [http://localhost:8501](http://localhost:8501)

## Quick Test

### Test the Backend API

```bash
# Health check
curl http://localhost:8000/health

# List available tables
curl http://localhost:8000/sql/tables

# Get metrics
curl -X POST http://localhost:8000/metrics \
  -H "Content-Type: application/json" \
  -d '{"days": 30}'
```

### Test the Frontend

1. Open [http://localhost:8501](http://localhost:8501)
2. In the sidebar, click **"Generate Report"**
3. Wait 30-60 seconds for the AI to generate the report
4. View metrics, charts, and news context
5. Download the audit trail JSON

## Troubleshooting

### "Connection refused" when accessing backend

```bash
# Check if backend is running
docker-compose ps

# View backend logs
docker-compose logs backend

# Restart backend
docker-compose restart backend
```

### "Database connection error"

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# View PostgreSQL logs
docker-compose logs postgres

# Restart PostgreSQL
docker-compose restart postgres
```

### "OpenAI API error" or "Tavily API error"

- Double-check your API keys in `.env`
- Restart the backend: `docker-compose restart backend`
- Verify you have credits/quota remaining

### Data ingestion is too slow

The DATASUS CSV files are large (~42MB each). Ingestion is normal to take 5-10 minutes. You can:

1. Watch progress: `docker-compose logs -f backend`
2. Use a smaller sample for testing (edit `backend/db/ingestion.py`)

### Streamlit "Connection error" to backend

- Ensure backend is running on port 8000
- Check `API_BASE_URL` in `frontend/app.py` is set to `http://localhost:8000`
- Try accessing [http://localhost:8000/docs](http://localhost:8000/docs) directly

## Common Commands

```bash
# Start everything
docker-compose up -d
streamlit run frontend/app.py

# Stop everything
docker-compose down

# View logs
docker-compose logs -f backend
docker-compose logs -f postgres

# Restart a service
docker-compose restart backend

# Rebuild after code changes
docker-compose up -d --build backend

# Clean everything (including database)
docker-compose down -v

# Re-ingest data (tables auto-create when backend starts)
docker-compose up -d
docker-compose exec backend python -m backend.db.ingestion
docker-compose exec backend python -m backend.db.dictionary_parser
```

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Explore the API docs at [http://localhost:8000/docs](http://localhost:8000/docs)
- View the architecture diagram in [docs/architecture.md](docs/architecture.md)
- Customize metrics in `backend/tools/metrics_tool.py`
- Add new visualizations in `frontend/app.py`

## Getting Help

If you encounter issues:

1. Check logs: `docker-compose logs`
2. Verify environment variables: `docker-compose config`
3. Review the [README.md](README.md) troubleshooting section
4. Open an issue on GitHub with:
   - Error message
   - Docker logs
   - Steps to reproduce

---

**Happy analyzing!**
