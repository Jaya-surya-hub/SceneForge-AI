"""Database engine and session factory.

The engine and SessionLocal are created lazily on first access so that
test code can set DATABASE_URL via os.environ before the first import.

Usage:
    from sceneforge.jobs.database import get_session, get_engine

    with get_session() as session:
        session.add(job)
        session.commit()
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from sceneforge.jobs.models import Base

_engine = None
_SessionLocal = None


def _build_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return url
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "sceneforge")
    user = os.getenv("POSTGRES_USER", "sceneforge")
    password = os.getenv("POSTGRES_PASSWORD", "sceneforge")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


def get_engine():
    """Return the module-level SQLAlchemy engine (lazy-created)."""
    global _engine
    if _engine is None:
        url = _build_url()
        is_sqlite = url.startswith("sqlite")
        kwargs: dict = {
            "echo": os.getenv("DB_ECHO", "false").lower() == "true",
        }
        if not is_sqlite:
            kwargs["pool_pre_ping"] = True
            kwargs["pool_size"] = 5
            kwargs["max_overflow"] = 10
        _engine = create_engine(url, **kwargs)
    return _engine


def get_session_factory():
    """Return (and lazily create) the SessionLocal factory."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(), autocommit=False, autoflush=False
        )
    return _SessionLocal


# Backward-compatible alias used by Alembic env.py and legacy imports
@property
def _engine_prop():
    return get_engine()


class _LazySessionLocal:
    """Proxy that creates sessions via the lazy factory."""
    def __call__(self):
        return get_session_factory()()


# Module-level names used by FastAPI dependencies and tests
class _EngineLazy:
    def __getattr__(self, name):
        return getattr(get_engine(), name)
    def connect(self):
        return get_engine().connect()


engine = _EngineLazy()
SessionLocal = _LazySessionLocal()


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context manager that provides a scoped DB session and rolls back on error."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_tables() -> None:
    """Create all tables (used in tests; migrations handle production)."""
    Base.metadata.create_all(bind=get_engine())


def drop_tables() -> None:
    """Drop all tables (tests only)."""
    Base.metadata.drop_all(bind=get_engine())


def reset_engine() -> None:
    """Reset the cached engine and session factory (used in tests)."""
    global _engine, _SessionLocal
    if _engine:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
