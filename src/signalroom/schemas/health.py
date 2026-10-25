"""Health check Pydantic schemas."""

from __future__ import annotations

from typing import Any, Dict
from pydantic import BaseModel, Field


class HealthDatabaseInfo(BaseModel):
    connected: bool = Field(..., description="True if database ping succeeded")
    dialect: str = Field(..., description="sqlite | postgresql")
    latency_ms: float = Field(..., description="Round-trip ping time in milliseconds")


class HealthStorageInfo(BaseModel):
    writable: bool = Field(..., description="True if artifact directory is accessible and writable")
    path: str = Field(..., description="Path to the evidence artifact store")


class HealthLedgerInfo(BaseModel):
    total_records: int = Field(default=0, description="Total number of evidence entries recorded")
    verified: bool = Field(default=True, description="True if tamper-evident hash chain is intact")


class HealthResponse(BaseModel):
    status: str = Field(..., description="'healthy' or 'degraded'")
    app: str = Field(..., description="Application name")
    version: str = Field(..., description="Semantic version")
    environment: str = Field(..., description="Runtime environment")
    demo_mode: bool = Field(..., description="Whether demo data mode is active")
    timestamp: str = Field(..., description="Current UTC ISO-8601 timestamp")
    database: HealthDatabaseInfo
    storage: HealthStorageInfo
    ledger: HealthLedgerInfo
