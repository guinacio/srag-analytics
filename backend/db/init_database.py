"""Initialize database: create tables and extensions."""
import logging
from sqlalchemy import text

from backend.db.connection import engine
from backend.db.models import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_database():
    """
    Initialize the database:
    1. Create pgvector extension
    2. Create all tables
    3. Create read-only user
    """
    logger.info("Starting database initialization...")

    with engine.connect() as conn:
        # Create pgvector extension
        logger.info("Creating pgvector extension...")
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
            logger.info(" pgvector extension created")
        except Exception as e:
            logger.warning(f"pgvector extension may already exist: {e}")

        # Create read-only user if not exists
        logger.info("Creating read-only user...")
        try:
            conn.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'srag_readonly') THEN
                        CREATE USER srag_readonly WITH PASSWORD 'readonly_pass';
                    END IF;
                END
                $$;
            """))
            conn.commit()
            logger.info(" Read-only user created/verified")
        except Exception as e:
            logger.warning(f"Read-only user creation issue (may already exist): {e}")

    # Create all tables
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info(" All tables created")

    # Grant permissions to read-only user
    logger.info("Granting permissions to read-only user...")
    with engine.connect() as conn:
        try:
            conn.execute(text("GRANT SELECT ON ALL TABLES IN SCHEMA public TO srag_readonly"))
            conn.execute(text("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO srag_readonly"))
            conn.commit()
            logger.info(" Permissions granted")
        except Exception as e:
            logger.warning(f"Permission grant issue: {e}")

    logger.info(" Database initialization complete!")
    logger.info("\nCreated tables:")
    logger.info("  - srag_cases (main fact table)")
    logger.info("  - data_dictionary (field definitions + embeddings)")
    logger.info("  - daily_metrics (materialized daily aggregates)")
    logger.info("  - monthly_metrics (materialized monthly aggregates)")
    logger.info("\nNext steps:")
    logger.info("  1. Run ingestion: python -m backend.db.ingestion")
    logger.info("  2. Parse dictionary: python -m backend.db.dictionary_parser")


if __name__ == "__main__":
    init_database()
