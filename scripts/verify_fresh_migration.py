"""Verification script for Alembic migration on a genuinely fresh database."""

import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from alembic import command
from alembic.config import Config

def verify_fresh_db():
    tmp_dir = tempfile.mkdtemp()
    db_file = os.path.join(tmp_dir, "fresh_migration_test.db").replace("\\", "/")
    db_url = f"sqlite:///{db_file}"
    print(f"Target Fresh DB: {db_url}")

    cfg = Config("alembic_signalroom.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Run upgrade head on completely fresh DB
    print("Executing: command.upgrade(cfg, 'head') ...")
    command.upgrade(cfg, "head")

    # 2. Inspect created tables
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"Discovered tables ({len(tables)}): {tables}")
    
    # 3. Check alembic version in db
    cursor.execute("SELECT version_num FROM alembic_version;")
    version = cursor.fetchone()[0]
    print(f"Alembic current version in DB: {version}")
    conn.close()

    # 4. Clean up
    os.remove(db_file)
    os.rmdir(tmp_dir)

    expected_tables = {"alembic_version", "projects", "questions", "runs", "evidence_references"}
    missing = expected_tables - set(tables)
    if missing:
        print(f"FAIL: Missing expected tables: {missing}")
        sys.exit(1)

    if version != "0001_signalroom_foundations":
        print(f"FAIL: Expected revision '0001_signalroom_foundations', got '{version}'")
        sys.exit(1)

    print("PASS: Migration successfully initialized fresh DB without stamping or pre-existing state.")

if __name__ == "__main__":
    verify_fresh_db()
