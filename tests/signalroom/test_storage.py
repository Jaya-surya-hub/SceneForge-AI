"""Tests for evidence artifact store and cryptographic hashing."""

import pytest
from signalroom.core.exceptions import ProofIntegrityException
from signalroom.storage.artifact_store import LocalArtifactStore, GENESIS_PREV_HASH


def test_calculate_sha256():
    content = b"IncuBrix Signal Room Evidence"
    digest = LocalArtifactStore.calculate_sha256(content)
    assert len(digest) == 64
    assert isinstance(digest, str)
    # Deterministic
    assert digest == LocalArtifactStore.calculate_sha256(content)


def test_compute_ledger_entry_hash():
    prev_hash = GENESIS_PREV_HASH
    entry_hash = LocalArtifactStore.compute_ledger_entry_hash(
        prev_ledger_hash=prev_hash,
        question_id="Q-001",
        run_id="RUN-001",
        provider="google_search",
        market="US",
        timestamp_iso="2026-10-22T06:00:00Z",
        artifact_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    assert len(entry_hash) == 64
    assert entry_hash != prev_hash


def test_save_and_verify_artifact(tmp_path):
    store = LocalArtifactStore(base_dir=str(tmp_path))
    content = b"Raw JSON observation payload"
    rel_path, sha_hash = store.save_artifact("test_sub", "artifact_01.json", content)

    assert rel_path == "test_sub/artifact_01.json"
    assert len(sha_hash) == 64

    # Verify matching hash
    assert store.verify_artifact(rel_path, sha_hash) is True

    # Verify mismatching hash
    assert store.verify_artifact(rel_path, "0" * 64) is False

    # Verify read bytes
    assert store.read_artifact(rel_path) == content


def test_tamper_detection_on_save(tmp_path):
    store = LocalArtifactStore(base_dir=str(tmp_path))
    store.save_artifact("test_sub", "immutability_test.json", b"original")

    # Attempting to save DIFFERENT content to the same filename raises ProofIntegrityException
    with pytest.raises(ProofIntegrityException):
        store.save_artifact("test_sub", "immutability_test.json", b"tampered")
