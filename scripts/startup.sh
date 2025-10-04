#!/bin/bash
set -e

echo "🚀 Starting SRAG Analytics Backend..."

# Wait for database to be ready
echo "⏳ Waiting for database to be ready..."
until python -c "
import psycopg
import os
try:
    conn = psycopg.connect(
        host='${POSTGRES_HOST:-postgres}',
        port='${POSTGRES_PORT:-5432}',
        dbname='${POSTGRES_DB:-srag_analytics}',
        user='${POSTGRES_USER:-srag_user}',
        password='${POSTGRES_PASSWORD:-srag_password}'
    )
    conn.close()
    print('Database is ready!')
except Exception as e:
    print(f'Database not ready: {e}')
    exit(1)
"; do
  echo "Database is unavailable - sleeping"
  sleep 2
done

# Initialize database if tables don't exist
echo "🔧 Checking database initialization..."
python -c "
from backend.db.connection import engine
from sqlalchemy import text
import sys

try:
    with engine.connect() as conn:
        # Check if srag_cases table exists
        result = conn.execute(text(\"\"\"
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'srag_cases'
            );
        \"\"\"))
        table_exists = result.scalar()
        
        if not table_exists:
            print('Tables not found, initializing database...')
            sys.exit(1)
        else:
            print('Database already initialized!')
            sys.exit(0)
except Exception as e:
    print(f'Error checking database: {e}')
    sys.exit(1)
" || {
    echo "📊 Initializing database..."
    python -m backend.db.init_database
    echo "✅ Database initialization complete!"
}

# Start the application
echo "🌐 Starting FastAPI server..."
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
