#!/bin/bash

echo "<å SRAG Analytics - Starting Application"
echo "========================================="
echo ""

# Check if Docker services are running
if ! docker-compose ps | grep -q "Up"; then
    echo "   Docker services not running. Starting..."
    docker-compose up -d
    sleep 5
fi

echo " Backend API: http://localhost:8000"
echo " API Docs: http://localhost:8000/docs"
echo ""
echo "=€ Starting Streamlit frontend..."
echo ""

streamlit run frontend/app.py
