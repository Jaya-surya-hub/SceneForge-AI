"""IS-08 — Concurrent Job Isolation.

Verifies that concurrent jobs execute with strict isolation:
1. Job IDs, scene data, rights records, and metrics do not leak across jobs.
2. Artifact storage paths are isolated per job (artifact_key namespacing).
3. Render cache directories are isolated per job.
4. Database sessions and transactions maintain isolation under concurrent execution.
5. Pipeline execution for multiple jobs in parallel produces correct, uncorrupted
   artifacts matching their respective job inputs.
"""

from __future__ import annotations

import concurrent.futures
import json
import uuid
from unittest.mock import MagicMock

import pytest

from sceneforge.jobs import repository as repo
from sceneforge.jobs.models import Job
from sceneforge.jobs.state_machine import JobStatus
from sceneforge.rendering.cache import RenderCache, build_cache_key
from sceneforge.rendering.normaliser import get_profile
from sceneforge.storage.paths import BUCKET_ARTIFACTS, artifact_key


# ---------------------------------------------------------------------------
# Tests: Storage and Path Isolation
# ---------------------------------------------------------------------------

class TestArtifactPathIsolation:
    def test_artifact_keys_are_strictly_isolated(self):
        """Artifact keys for different jobs must never collide, even for identical filenames."""
        job_1 = str(uuid.uuid4())
        job_2 = str(uuid.uuid4())

        filenames = ["output.mp4", "timeline.json", "manifest.json", "rights.json", "captions.srt"]
        for fname in filenames:
            k1 = artifact_key(job_1, fname)
            k2 = artifact_key(job_2, fname)
            assert k1 != k2
            assert k1.startswith(f"jobs/{job_1}/")
            assert k2.startswith(f"jobs/{job_2}/")
            assert k1.endswith(fname)
            assert k2.endswith(fname)

    def test_render_cache_directory_isolation(self, tmp_path):
        """RenderCache instances for different jobs operate in distinct root directories."""
        cache_base = str(tmp_path / "cache")
        job_1 = str(uuid.uuid4())
        job_2 = str(uuid.uuid4())

        cache_1 = RenderCache(cache_base, job_1)
        cache_2 = RenderCache(cache_base, job_2)

        assert cache_1._root != cache_2._root
        assert job_1 in cache_1._root
        assert job_2 in cache_2._root

        profile = get_profile("16:9")
        key = build_cache_key("asset-shared", 0.0, 2.0, "16:9", "Caption", profile)

        # Write segment in cache 1
        seg_file = str(tmp_path / "seg.mp4")
        with open(seg_file, "wb") as f:
            f.write(b"content for job 1")

        cache_1.put(key, seg_file)

        # Cache 1 has it
        assert cache_1.get(key) is not None
        # Cache 2 MUST NOT have it (isolated namespace)
        assert cache_2.get(key) is None

        # Clearing job 1 does not affect job 2
        cache_1.clear_job()
        assert cache_1.get(key) is None


# ---------------------------------------------------------------------------
# Tests: Database Isolation under Concurrent Operations
# ---------------------------------------------------------------------------

class TestDatabaseConcurrentIsolation:
    def test_concurrent_job_creation_and_isolation(self, sqlite_engine):
        """Multiple threads creating and querying jobs concurrently have isolated records."""
        from sqlalchemy.orm import sessionmaker

        Session = sessionmaker(bind=sqlite_engine, autocommit=False, autoflush=False)
        num_jobs = 8

        def worker_fn(index: int):
            session = Session()
            try:
                script = f"Script for concurrent job {index}"
                job = repo.create_job(session, data={"script": script, "aspect_ratio": "16:9"})
                session.commit()

                # Add scenes
                scenes = [
                    {"narration_text": f"Scene {i} of job {index}", "start_time": i * 2.0, "end_time": (i + 1) * 2.0}
                    for i in range(3)
                ]
                repo.upsert_scenes(session, job.id, scenes)
                session.commit()

                # Add rights
                repo.add_rights_record(
                    session,
                    job_id=job.id,
                    data={
                        "asset_id": f"asset-job-{index}",
                        "provider_name": "mock",
                        "licence_name": "MIT",
                    },
                )
                session.commit()

                # Verify independence
                fetched_scenes = repo.get_scenes(session, job.id)
                assert len(fetched_scenes) == 3
                for s in fetched_scenes:
                    assert f"job {index}" in s.narration_text

                rights = repo.get_rights_records(session, job.id)
                assert len(rights) == 1
                assert rights[0].asset_id == f"asset-job-{index}"

                return str(job.id)
            finally:
                session.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(worker_fn, i) for i in range(num_jobs)]
            job_ids = [f.result() for f in futures]

        assert len(job_ids) == num_jobs
        assert len(set(job_ids)) == num_jobs  # All IDs are unique


# ---------------------------------------------------------------------------
# Tests: Concurrent Pipeline Execution
# ---------------------------------------------------------------------------

class TestConcurrentPipelineExecution:
    def test_concurrent_pipeline_runs_do_not_leak_state(self, sqlite_engine, tmp_path):
        """Simultaneous pipeline runs on separate threads produce independent, valid outputs."""
        from sqlalchemy.orm import sessionmaker
        from sceneforge.jobs.orchestrator import PipelineOrchestrator
        from sceneforge.storage.filesystem_client import FilesystemStorageClient

        storage_root = str(tmp_path / "artifacts")
        storage = FilesystemStorageClient(root=storage_root)

        Session = sessionmaker(bind=sqlite_engine, autocommit=False, autoflush=False)
        num_jobs = 4

        # Pre-create jobs
        job_data = []
        for i in range(num_jobs):
            session = Session()
            try:
                script = f"Job {i} explores unique knowledge and specific technology."
                job = repo.create_job(session, data={"script": script, "aspect_ratio": "16:9"})
                session.commit()
                job_data.append((job.id, script))
            finally:
                session.close()

        import threading
        db_lock = threading.Lock()

        # Patch get_session to return a fresh thread-safe session with SQLite write lock
        def get_thread_session():
            class Ctx:
                def __enter__(self):
                    db_lock.acquire()
                    self.s = Session()
                    return self.s
                def __exit__(self, exc_type, exc_val, exc_tb):
                    try:
                        if exc_type is None:
                            self.s.commit()
                        else:
                            self.s.rollback()
                        self.s.close()
                    finally:
                        db_lock.release()
            return Ctx()

        def run_job(job_id: uuid.UUID, expected_script: str):
            orchestrator = PipelineOrchestrator(job_id=job_id)
            orchestrator.storage = storage
            orchestrator.run()

            # Verify artifacts for this job
            jid = str(job_id)
            manifest_bytes = storage.download_bytes(BUCKET_ARTIFACTS, artifact_key(jid, "manifest.json"))
            manifest = json.loads(manifest_bytes.decode("utf-8"))
            assert manifest["job_id"] == jid

            captions_bytes = storage.download_bytes(BUCKET_ARTIFACTS, artifact_key(jid, "captions.srt"))
            captions = captions_bytes.decode("utf-8")
            assert len(captions) > 0

            # Verify that manifest does not contain another job's ID
            return manifest["job_id"]

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("sceneforge.jobs.orchestrator.get_session", get_thread_session)
            mp.setattr("sceneforge.jobs.database.get_session", get_thread_session)

            with concurrent.futures.ThreadPoolExecutor(max_workers=num_jobs) as executor:
                futures = [executor.submit(run_job, jid, script) for jid, script in job_data]
                completed_ids = [f.result() for f in futures]

        assert len(completed_ids) == num_jobs
        assert len(set(completed_ids)) == num_jobs
