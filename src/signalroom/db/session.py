"""Database session management and connection lifecycle."""

from __future__ import annotations

import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from signalroom.core.config import settings
from signalroom.core.logging import get_logger
from signalroom.db.base import Base

logger = get_logger(__name__)

is_sqlite = settings.DATABASE_URL.startswith("sqlite")

connect_args = {"check_same_thread": False} if is_sqlite else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
    future=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a thread-local database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initializes tables in database if they do not exist yet."""
    import signalroom.models  # Ensure all models are registered with Base metadata
    logger.info(f"Initializing database tables using engine: {settings.DATABASE_URL}")
    Base.metadata.create_all(bind=engine)
