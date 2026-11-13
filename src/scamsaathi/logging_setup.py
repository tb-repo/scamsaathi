"""Structured, PII-safe logging (task 1.5, FR-075, NFR-009, NFR-014).

Every record is emitted as one JSON line with the current request ID. A filter masks
PII in the message and in string extras as a second line of defence; callers should
still log only masked text, hashes, and metrics.
"""

from __future__ import annotations

import json
import logging
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from scamsaathi.tools.pii_masker import mask

_request_id: ContextVar[str] = ContextVar("request_id", default="-")

# Attributes present on every LogRecord; anything else was passed via `extra=`.
_STANDARD_ATTRS = frozenset(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime"}


def new_request_id() -> str:
    request_id = str(uuid.uuid4())
    _request_id.set(request_id)
    return request_id


def set_request_id(request_id: str) -> None:
    _request_id.set(request_id)


def get_request_id() -> str:
    return _request_id.get()


class PIIRedactionFilter(logging.Filter):
    """Masks PII in the formatted message and in string-valued extras."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = mask(record.getMessage()).masked_text
        record.args = None
        for key, value in list(vars(record).items()):
            if key not in _STANDARD_ATTRS and isinstance(value, str):
                setattr(record, key, mask(value).masked_text)
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": get_request_id(),
            "msg": record.getMessage(),
        }
        for key, value in vars(record).items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info and record.exc_info[0] is not None:
            payload["error_type"] = record.exc_info[0].__name__
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    """Idempotently configure the ``scamsaathi`` logger tree."""
    logger = logging.getLogger("scamsaathi")
    logger.setLevel(level)
    if any(getattr(h, "_scamsaathi", False) for h in logger.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(PIIRedactionFilter())
    handler._scamsaathi = True  # type: ignore[attr-defined]
    logger.addHandler(handler)
    logger.propagate = False
