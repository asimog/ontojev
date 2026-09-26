"""Lightweight structured operational logging.

Operational logs are not scientific evidence: immutable ``run_events`` remain the
audit trail. This module only formats process logs with stable identifiers
(``run_id``, ``campaign_id``, ``program_id``, ``request_id``) so operators can
correlate a cycle, a dispatch and an API request without a telemetry platform.
"""

from __future__ import annotations

import json
import logging
from typing import Any

LOGGER_NAME = "cancerjev"
CORRELATION_FIELDS = ("run_id", "campaign_id", "program_id", "candidate_id", "request_id")


class StructuredFormatter(logging.Formatter):
    """One canonical JSON line per record; correlation fields are surfaced top-level."""

    def format(self, record: logging.LogRecord) -> str:
        fields: dict[str, Any] = {
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in CORRELATION_FIELDS:
            value = getattr(record, key, None)
            if value is not None:
                fields[key] = value
        if record.exc_info:
            fields["exception"] = self.formatException(record.exc_info)
        return json.dumps(fields, sort_keys=True, separators=(",", ":"), default=str)


def configure_logging(level: str = "INFO") -> logging.Logger:
    """Idempotent setup for long-running processes; never touches the root logger."""
    logger = logging.getLogger(LOGGER_NAME)
    if not any(isinstance(handler.formatter, StructuredFormatter)
               for handler in logger.handlers if handler.formatter is not None):
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredFormatter())
        logger.addHandler(handler)
    logger.setLevel(level.upper())
    return logger


def log_event(message: str, *, level: str = "info", **fields: Any) -> None:
    """Emit one structured record through the cancerjev logger."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.log(getattr(logging, level.upper()), message, extra=dict(fields))
