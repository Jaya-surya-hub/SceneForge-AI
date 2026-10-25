"""Evidence artifact storage and cryptographic ledger hashing."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from signalroom.core.config import settings
from signalroom.core.exceptions import ProofIntegrityException
from signalroom.core.logging import get_logger

logger = get_logger(__name__)

GENESIS_PREV_HASH = "0" * 64


class LocalArtifactStore:
    """Local filesystem artifact store with cryptographic hashing and immutability checks."""

    def __init__(self, base_dir: Optional[str] = None):
        target = Path(base_dir or settings.ARTIFACT_STORAGE_PATH)
        self.base_dir = target.absolute()
        os.makedirs(str(self.base_dir), exist_ok=True)

    @staticmethod
    def calculate_sha256(content: bytes) -> str:
        """Computes the SHA-256 digest of arbitrary bytes."""
        hasher = hashlib.sha256()
        hasher.update(content)
        return hasher.hexdigest()

    @staticmethod
    def compute_ledger_entry_hash(
        prev_ledger_hash: str,
        question_id: str,
        run_id: str,
        provider: str,
        market: str,
        timestamp_iso: str,
        artifact_sha256: str,
    ) -> str:
        """Computes tamper-evident blockchain-style hash for a ledger entry."""
        raw_string = f"{prev_ledger_hash}|{question_id}|{run_id}|{provider}|{market}|{timestamp_iso}|{artifact_sha256}"
        return hashlib.sha256(raw_string.encode("utf-8")).hexdigest()

    def save_artifact(
        self,
        subfolder: str,
        filename: str,
        content: bytes,
    ) -> Tuple[str, str]:
        """Saves artifact to subfolder, returning (relative_path, sha256_hash).
        
        Does not overwrite existing files if content has changed.
        """
        target_dir = self.base_dir / subfolder
        os.makedirs(str(target_dir), exist_ok=True)

        target_file = target_dir / filename
        content_hash = self.calculate_sha256(content)

        if target_file.exists():
            existing_hash = self.calculate_sha256(target_file.read_bytes())
            if existing_hash != content_hash:
                raise ProofIntegrityException(
                    message=f"Attempted to overwrite existing evidence artifact {filename} with conflicting hash.",
                    details={"file": str(target_file), "existing_hash": existing_hash, "new_hash": content_hash},
                )
            logger.info(f"Artifact {filename} already exists with identical hash {content_hash}.")
        else:
            target_file.write_bytes(content)
            logger.info(f"Saved artifact {filename} with SHA-256: {content_hash}")

        # Return path relative to base_dir (or posix format)
        rel_path = str(target_file.relative_to(self.base_dir)).replace("\\", "/")
        return rel_path, content_hash

    def read_artifact(self, relative_path: str) -> bytes:
        """Reads artifact bytes by relative path."""
        target_file = (self.base_dir / relative_path).resolve()
        if not target_file.exists():
            raise FileNotFoundError(f"Artifact not found at path: {relative_path}")
        return target_file.read_bytes()

    def verify_artifact(self, relative_path: str, expected_hash: str) -> bool:
        """Verifies that the stored artifact matches the recorded SHA-256 hash."""
        target_file = (self.base_dir / relative_path).resolve()
        if not target_file.exists():
            return False
        actual_hash = self.calculate_sha256(target_file.read_bytes())
        return actual_hash.lower() == expected_hash.lower()


artifact_store = LocalArtifactStore()
