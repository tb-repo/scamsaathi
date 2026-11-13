"""Disk cache and daily budget for the LLM gateway (task 1.7, FR-073, FR-076).

Cache keys are SHA-256 hashes of masked prompts, so no raw text appears in file names.
Cached files hold masked prompts' responses only (ADR-007).
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from scamsaathi.llm.errors import BudgetExceeded


def cache_key(**parts: str) -> str:
    """Stable key from named parts (order-independent)."""
    canonical = json.dumps(parts, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class DiskCache:
    def __init__(self, directory: Path) -> None:
        self._dir = directory

    def _path(self, key: str) -> Path:
        return self._dir / key[:2] / f"{key}.json"

    def get(self, key: str) -> dict[str, Any] | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None  # corrupt entry behaves as a miss
        return data if isinstance(data, dict) else None

    def put(self, key: str, record: dict[str, Any]) -> None:
        _atomic_write_json(self._path(key), record)


class DailyBudget:
    """Counts real provider calls per calendar day and refuses calls above the limit."""

    def __init__(
        self, directory: Path, limit: int, today: Callable[[], date] = date.today
    ) -> None:
        self._dir = directory
        self._limit = limit
        self._today = today

    def _path(self) -> Path:
        return self._dir / f"budget-{self._today().isoformat()}.json"

    def used(self) -> int:
        path = self._path()
        if not path.exists():
            return 0
        try:
            return int(json.loads(path.read_text(encoding="utf-8")).get("calls", 0))
        except (OSError, ValueError, AttributeError):
            return 0

    def consume(self) -> None:
        used = self.used()
        if used >= self._limit:
            raise BudgetExceeded(f"daily call budget of {self._limit} reached")
        _atomic_write_json(self._path(), {"calls": used + 1})
