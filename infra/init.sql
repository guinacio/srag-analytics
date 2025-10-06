-- Initialize database for SRAG Analytics
-- Enable pgvector extension for embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- Create read-only user for SQL agent (security best practice)
CREATE USER srag_readonly WITH PASSWORD 'readonly_pass';

-- We'll grant permissions after tables are created by the ingestion script
