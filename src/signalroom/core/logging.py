"""Structured logging for IncuBrix Signal Room."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from signalroom.core.config import settings


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "line": record.lineno,
        }

        # Include custom extra attributes if present
        for key, val in record.__dict__.items():
            if key not in {
                "args", "asctime", "created", "exc_info", "exc_text", "filename",
                "funcName", "levelname", "levelno", "lineno", "module", "msecs",
                "message", "msg", "name", "pathname", "process", "processName",
                "relativeCreated", "stack_info", "thread", "threadName"
            }:
                log_data[key] = val

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging() -> None:
    """Configures application-wide logging based on settings."""
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL.upper())

    # Avoid adding duplicate handlers on multiple calls
    if root_logger.handlers:
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)

    if settings.LOG_FORMAT.lower() == "json":
        console_handler.setFormatter(JSONFormatter())
    else:
        standard_format = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
        console_handler.setFormatter(logging.Formatter(standard_format, datefmt="%Y-%m-%d %H:%M:%S"))

    root_logger.addHandler(console_handler)

    # Silence overly verbose external loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Convenience getter for a named logger."""
    return logging.getLogger(name)
