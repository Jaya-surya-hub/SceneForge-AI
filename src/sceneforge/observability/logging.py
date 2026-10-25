"""Structured JSON logging via structlog.

Every log line is a JSON object containing at minimum:
  timestamp, level, correlation_id, job_id, module, event

Usage:
    from sceneforge.observability.logging import get_logger
    log = get_logger(__name__)
    log.info("scene_rendered", scene_id="s-001", duration_ms=420)

No sensitive data (API keys, passwords, tokens) must appear in log output.
The _scrub_secrets processor strips known secret field names.
"""

from __future__ import annotations

import logging
import os
import sys
from contextvars import ContextVar
from typing import Any

import structlog

# ---------------------------------------------------------------------------
# Context variables propagated across sync and async code
# ---------------------------------------------------------------------------

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")
_job_id: ContextVar[str] = ContextVar("job_id", default="")

# Keys whose values must never appear in logs
_SECRET_KEYS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "authorization",
        "auth",
        "credential",
        "private_key",
        "access_key",
        "secret_key",
        "minio_root_password",
        "callback_hmac_secret",
        "openai_api_key",
        "pexels_api_key",
        "pixabay_api_key",
    }
)


def set_correlation_id(cid: str) -> None:
    _correlation_id.set(cid)


def get_correlation_id() -> str:
    return _correlation_id.get()


def set_job_id(jid: str) -> None:
    _job_id.set(jid)


def get_job_id() -> str:
    return _job_id.get()


# ---------------------------------------------------------------------------
# Custom processors
# ---------------------------------------------------------------------------

def _inject_context(
    logger: Any, method: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Inject correlation_id and job_id from context vars."""
    cid = _correlation_id.get()
    jid = _job_id.get()
    if cid:
        event_dict.setdefault("correlation_id", cid)
    if jid:
        event_dict.setdefault("job_id", jid)
    return event_dict


def _scrub_secrets(
    logger: Any, method: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Replace values of known secret keys with '[REDACTED]'."""
    for key in list(event_dict.keys()):
        if key.lower() in _SECRET_KEYS:
            event_dict[key] = "[REDACTED]"
    return event_dict


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def configure_logging() -> None:
    """Configure structlog. Call once at application startup."""
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    log_format = os.getenv("LOG_FORMAT", "json").lower()

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        _inject_context,
        _scrub_secrets,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    if log_format == "json":
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)

    # Silence noisy third-party loggers
    for name in ("boto3", "botocore", "urllib3", "s3transfer"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger for the given module name."""
    return structlog.get_logger(name)
