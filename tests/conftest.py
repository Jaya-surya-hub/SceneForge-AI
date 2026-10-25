"""Shared pytest fixtures for SceneForge AI tests.

All fixtures here are available to all test modules.
No external API keys, Docker services, or network calls are required
for the no-key test suite.

Key design choices:
- DATABASE_URL is set to SQLite in-memory BEFORE any sceneforge module is imported.
- SKIP_STARTUP_CHECKS=true prevents the FastAPI lifespan from connecting to MinIO/Redis.
- All external dependencies (DB, Redis, queue, storage) are overridden per-test.
- The sqlite_engine fixture creates tables fresh per session using the same in-memory URL.
"""

from __future__ import annotations

import os
import uuid
from unittest.mock import MagicMock

# ── Set environment BEFORE any sceneforge import ──────────────────────────────
# This must happen before the lazy engine is first created.
_SQLITE_URL = "sqlite:///C:/Users/Omen/sf_pytest.db"
os.environ["DATABASE_URL"] = _SQLITE_URL
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("MINIO_ENDPOINT", "http://localhost:9000")
os.environ.setdefault("CALLBACK_HMAC_SECRET", "test-secret-key-for-unit-tests")
os.environ.setdefault("STOCK_PROVIDER", "mock")
os.environ.setdefault("TTS_ADAPTER", "mock")
os.environ.setdefault("STT_ADAPTER", "mock")
os.environ.setdefault("LOG_FORMAT", "console")
os.environ["SKIP_STARTUP_CHECKS"] = "true"

import fakeredis
import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from sceneforge.jobs.models import Base


# ── SQLite engine shared across the session ───────────────────────────────────

@pytest.fixture(scope="session")
def sqlite_engine():
    """Create a file-based SQLite engine (avoids thread-safety issues with :memory:)."""
    db_path = "C:/Users/Omen/sf_pytest_session.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(sqlite_engine):
    """Transactional session that rolls back after each test."""
    connection = sqlite_engine.connect()
    transaction = connection.begin()
    TestSession = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = TestSession()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


# ── Fake Redis ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def fake_redis():
    """Return a fakeredis instance (no real Redis required)."""
    server = fakeredis.FakeServer()
    return fakeredis.FakeRedis(server=server, decode_responses=True)


# ── Mock storage ──────────────────────────────────────────────────────────────

@pytest.fixture()
def mock_storage():
    """Return a MagicMock storage client."""
    storage = MagicMock()
    storage.list_keys.return_value = []
    storage.object_exists.return_value = False
    storage.presigned_get_url.return_value = "http://mock-presigned-url/file"
    storage.upload_bytes.return_value = None
    storage.ensure_buckets.return_value = None
    return storage


# ── FastAPI test client ───────────────────────────────────────────────────────

@pytest.fixture()
def api_client(db_session, fake_redis, mock_storage):
    """Return a FastAPI TestClient with all external deps overridden."""
    from fastapi.testclient import TestClient
    from sceneforge.api.app import create_app
    from sceneforge.api.dependencies import get_db, get_redis, get_queue, get_storage

    app = create_app()

    # Generator-based override for DB
    def override_db():
        yield db_session

    mock_queue = MagicMock()
    mock_queue.enqueue.return_value = MagicMock(id="mock-rq-job-id")

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = lambda: fake_redis
    app.dependency_overrides[get_queue] = lambda: mock_queue
    app.dependency_overrides[get_storage] = lambda: mock_storage

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client

    app.dependency_overrides.clear()


# ── Unique idempotency key per test ───────────────────────────────────────────

@pytest.fixture()
def idem_key():
    return f"test-idem-{uuid.uuid4().hex[:12]}"
