"""Shared pytest fixtures for IncuBrix Signal Room."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Ensure src is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))

# Override DB and Storage to isolated test paths
_TEST_DB_PATH = Path.home() / ".signalroom" / "test_signalroom.db"
_TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
_TEST_STORAGE_PATH = Path.home() / ".signalroom" / "test_evidence"
_TEST_STORAGE_PATH.mkdir(parents=True, exist_ok=True)

os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH.as_posix()}"
os.environ["ARTIFACT_STORAGE_PATH"] = str(_TEST_STORAGE_PATH)
os.environ["ENVIRONMENT"] = "testing"
os.environ["DEMO_MODE"] = "true"

from signalroom.api.app import app
from signalroom.core.config import settings
from signalroom.db.base import Base
from signalroom.db.session import get_db
import signalroom.models


test_engine = create_engine(
    f"sqlite:///{_TEST_DB_PATH.as_posix()}",
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def clean_tables(db_session: Session):
    """Ensures each test starts with an empty database."""
    for table in reversed(Base.metadata.sorted_tables):
        db_session.execute(table.delete())
    db_session.commit()
    yield


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provides a transactional database session per test."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient with overridden get_db dependency."""
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
