#!/bin/bash
set -e

echo "<å SRAG Analytics - Setup Script"
echo "================================="
echo ""

# Check for .env file
if [ ! -f .env ]; then
    echo "=Ý Creating .env file from template..."
    cp .env.example .env
    echo "   IMPORTANT: Edit .env and add your API keys!"
    echo ""
    read -p "Press Enter after you've updated .env with your API keys..."
fi

# Start Docker services
echo "=3 Starting Docker services (PostgreSQL + Backend)..."
docker-compose up -d

# Wait for PostgreSQL to be ready
echo "ó Waiting for PostgreSQL to be ready..."
sleep 10

# Check if database is initialized
echo "=Ä  Checking database status..."
docker-compose exec -T postgres psql -U srag_user -d srag_analytics -c "\dt" > /dev/null 2>&1
DB_EXISTS=$?

if [ $DB_EXISTS -ne 0 ]; then
    echo "=Ê Initializing database and ingesting data..."
    echo "   This may take several minutes..."

    # Run ingestion
    docker-compose exec -T backend python -m backend.db.ingestion

    echo "=Ö Parsing data dictionary and creating embeddings..."
    docker-compose exec -T backend python -m backend.db.dictionary_parser

    echo " Database setup complete!"
else
    echo " Database already initialized"
fi

echo ""
echo "<‰ Setup Complete!"
echo ""
echo "Next steps:"
echo "  1. Install Python dependencies: pip install -e ."
echo "  2. Run Streamlit: streamlit run frontend/app.py"
echo "  3. Open browser: http://localhost:8501"
echo ""
echo "API Documentation: http://localhost:8000/docs"
echo ""
