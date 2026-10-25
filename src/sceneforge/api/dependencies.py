"""FastAPI dependency factories (Depends() providers)."""

from __future__ import annotations

import os
from typing import Generator

import redis as redis_lib
from sqlalchemy.orm import Session

from sceneforge.jobs.database import SessionLocal
from sceneforge.storage.client import StorageClient, get_storage_client

# ---------------------------------------------------------------------------
# Database session
# ---------------------------------------------------------------------------

def get_db() -> Generator[Session, None, None]:
    """Yield a DB session and close it when the request completes."""
    from sceneforge.jobs.database import get_session_factory
    SessionFactory = get_session_factory()
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Redis client
# ---------------------------------------------------------------------------

_redis_client: redis_lib.Redis | None = None


def get_redis() -> redis_lib.Redis:
    global _redis_client
    if _redis_client is None:
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            _redis_client = redis_lib.Redis.from_url(redis_url, decode_responses=True)
        else:
            host = os.getenv("REDIS_HOST", "redis")
            port = int(os.getenv("REDIS_PORT", "6379"))
            db = int(os.getenv("REDIS_DB", "0"))
            password = os.getenv("REDIS_PASSWORD") or None
            _redis_client = redis_lib.Redis(
                host=host, port=port, db=db, password=password, decode_responses=True
            )
    return _redis_client


def reset_redis_client(client: redis_lib.Redis | None = None) -> None:
    """Replace the module-level Redis client (used in tests)."""
    global _redis_client
    _redis_client = client


# ---------------------------------------------------------------------------
# Storage client
# ---------------------------------------------------------------------------

def get_storage() -> StorageClient:
    return get_storage_client()


# ---------------------------------------------------------------------------
# RQ Queue
# ---------------------------------------------------------------------------

def get_queue():
    """Return the RQ default queue."""
    from rq import Queue
    return Queue(connection=get_redis())
