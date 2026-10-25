"""Core configuration for IncuBrix Signal Room."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_NAME: str = "IncuBrix Signal Room"
    TAGLINE: str = "Every signal has a source. Every decision has proof."
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"

    ENVIRONMENT: str = Field(default="development", description="development | production | testing")
    DEBUG: bool = Field(default=True, description="Enable debug mode")
    DEMO_MODE: bool = Field(default=True, description="Enables explicit DEMO badges on sample datasets")

    # Database: Default to user home or local SQLite for development, supports Postgres in deployment
    DATABASE_URL: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            f"sqlite:///{Path.home().as_posix()}/.signalroom/signalroom.db",
        ),
        description="Database connection string",
    )

    # Artifact Storage: Local filesystem directory with future S3-compatible abstraction
    ARTIFACT_STORAGE_PATH: str = Field(
        default_factory=lambda: os.getenv(
            "ARTIFACT_STORAGE_PATH",
            str(Path.home() / ".signalroom" / "evidence"),
        ),
        description="Directory path for raw evidence artifacts and ledger snapshots",
    )

    # CORS settings
    CORS_ORIGINS: Union[str, List[str]] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://127.0.0.1:3000"],
        description="Allowed CORS origins",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # Logging
    LOG_LEVEL: str = Field(default="INFO", description="DEBUG, INFO, WARNING, ERROR, CRITICAL")
    LOG_FORMAT: str = Field(default="console", description="console | json")

    # Server binding
    HOST: str = "0.0.0.0"
    PORT: int = 8000


settings = Settings()
