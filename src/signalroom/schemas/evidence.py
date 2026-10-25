"""Evidence Reference Pydantic schemas for Proof Ledger."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class EvidenceReferenceBase(BaseModel):
    question_id: str
    run_id: str
    provider: str = Field(..., description="google_search | chatgpt | claude | gemini | perplexity")
    collection_method: str = Field(..., description="official_api | manual_capture | browser_fixture")
    market: str = Field(default="US", max_length=8)
    location: str = Field(default="United States", max_length=128)
    language: str = Field(default="en", max_length=8)
    artifact_path: str = Field(..., description="Relative path in storage/evidence")
    sha256_hash: str = Field(..., min_length=64, max_length=64, description="Artifact SHA-256")
    prev_ledger_hash: str = Field(..., min_length=64, max_length=64, description="Previous entry hash")
    current_ledger_hash: str = Field(..., min_length=64, max_length=64, description="Cryptographic chain hash")
    execution_status: str = Field(default="success", description="success | failed | restricted | timeout")
    runtime_ms: int = Field(default=0)
    cost_usd: float = Field(default=0.0)
    is_demo: bool = Field(default=False)
    notes: Optional[str] = None


class EvidenceReferenceCreate(EvidenceReferenceBase):
    id: Optional[str] = Field(default=None, max_length=64)


class EvidenceReferenceRead(EvidenceReferenceBase):
    id: str
    timestamp: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class LedgerVerificationResult(BaseModel):
    is_valid: bool
    total_entries_verified: int
    chain_breaks_detected: int
    missing_artifacts: int
    corrupted_artifacts: int
    errors: List[str] = Field(default_factory=list)
    genesis_hash: str
    latest_hash: Optional[str] = None
