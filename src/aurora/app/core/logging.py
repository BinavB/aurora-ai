"""Centralized structured logging with secret redaction.

Logs are emitted as single-line JSON so they can be ingested by log
processors. A redaction filter scrubs any field whose key hints at a secret,
satisfying the architecture rule that secrets are never logged.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from aurora.app.core.constants import APP_NAME, SECRET_KEY_HINTS

_REDACTED = "***redacted***"
_RESERVED = frozenset(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


def redact(value: Any) -> Any:
    """Recursively redact values whose keys look sensitive.

    Args:
        value: Any JSON-like value (mappings and sequences are traversed).

    Returns:
        A copy with sensitive leaf values replaced by a redaction marker.
    """
    if isinstance(value, dict):
        return {
            key: (_REDACTED if _is_secret(key) else redact(val))
            for key, val in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value


def _is_secret(key: str) -> bool:
    lowered = str(key).lower()
    return any(hint in lowered for hint in SECRET_KEY_HINTS)


class JsonFormatter(logging.Formatter):
    """Format log records as redacted single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extras = {
            key: val
            for key, val in record.__dict__.items()
            if key not in _RESERVED and not key.startswith("_")
        }
        if extras:
            payload["context"] = redact(extras)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: int | str = logging.INFO) -> None:
    """Install the JSON formatter on the application logger (idempotent).

    Args:
        level: Minimum level to emit (name or numeric value).
    """
    logger = logging.getLogger(APP_NAME)
    logger.setLevel(level)
    if not any(getattr(h, "_aurora", False) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        handler._aurora = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
    logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the application namespace.

    Args:
        name: Dotted suffix identifying the caller (e.g. ``providers.openai``).
    """
    return logging.getLogger(f"{APP_NAME}.{name}")
