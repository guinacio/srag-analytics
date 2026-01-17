"""Database connection and session management."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from contextlib import contextmanager
from typing import Generator
import logging

from backend.config.settings import settings
from backend.db.models import Base

logger = logging.getLogger(__name__)


# Main database engine (full permissions)
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=settings.environment == "development",
)

# Read-only engine for SQL agent (security)
readonly_engine = create_engine(
    settings.readonly_database_url,
    pool_pre_ping=True,
    pool_size=3,
    max_overflow=5,
    connect_args={
        "options": "-c default_transaction_read_only=on -c statement_timeout=30000"
    },
)

# Session factories
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
ReadOnlySessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=readonly_engine)


def init_db() -> None:
    """Initialize database: create tables and extensions."""
    logger.info("Initializing database...")

    # Create all tables
    Base.metadata.create_all(bind=engine)

    logger.info("Database initialized successfully")


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Get database session (context manager)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        db.close()


