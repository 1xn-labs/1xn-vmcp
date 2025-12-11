"""
Database connection and session management.

This module handles PostgreSQL database connections using SQLAlchemy.
"""

import logging
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import Pool

from vmcp.config import settings
from vmcp.storage.models import Base
from vmcp.utilities.logging import get_logger

logger = get_logger(__name__)

# Ensure database directory exists for SQLite
def _ensure_db_directory():
    """Ensure the database directory exists for SQLite databases."""
    if "sqlite" in settings.database_url:
        # Extract the file path from the SQLite URL
        db_path = settings.database_url.replace("sqlite:///", "")
        db_file = Path(db_path)
        db_dir = db_file.parent
        
        # Create the directory if it doesn't exist
        if not db_dir.exists():
            logger.info(f"Creating database directory: {db_dir}")
            db_dir.mkdir(parents=True, exist_ok=True)

# Ensure directory exists before creating engine
_ensure_db_directory()

# Normalize PostgreSQL URL to use psycopg2 if available
def _normalize_database_url(url: str) -> str:
    """Normalize database URL, preferring psycopg2 for PostgreSQL if available."""
    if url.startswith("postgresql://") and not url.startswith("postgresql+psycopg2://"):
        try:
            import psycopg2  # type: ignore  # noqa: F401
            return url.replace("postgresql://", "postgresql+psycopg2://")
        except ImportError:
            # psycopg2 not available, use URL as-is (SQLAlchemy will handle error)
            return url
    return url

# Create engine
engine = create_engine(
    _normalize_database_url(settings.database_url),
    echo=settings.database_echo,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)


# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(Pool, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Set SQLite pragma for foreign keys if using SQLite."""
    if "sqlite" in settings.database_url:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_engine():
    """Get the SQLAlchemy engine."""
    return engine


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for getting a database session.

    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize the database by creating all tables and running migrations.

    This should be called on application startup.
    """
    try:
        logger.info("Initializing database...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        
        # Run migrations to handle schema changes
        from vmcp.storage.migrations import run_migrations
        run_migrations()
        
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        raise


def drop_db() -> None:
    """
    Drop all database tables.

    WARNING: This will delete all data!
    """
    logger.warning("Dropping all database tables...")
    Base.metadata.drop_all(bind=engine)
    logger.info("All tables dropped")
