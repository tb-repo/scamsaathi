"""Local threat-intelligence store (task 2.3, 2.4; FR-022, FR-024; docs/07 section 5).

Built from the reviewable CSV/TXT files in ``data/intel``. Lookups use normalised values
(E.164 phones, lowercase UPI IDs and domains).
"""

from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from scamsaathi.config import PROJECT_ROOT
from scamsaathi.tools.pii_masker import DESIGNATED_SERIES

DEFAULT_DATA_DIR: Final = PROJECT_ROOT / "data" / "intel"

_SCHEMA: Final = """
CREATE TABLE IF NOT EXISTS blocklist (
  id INTEGER PRIMARY KEY,
  kind TEXT CHECK(kind IN ('phone','upi','domain','url')) NOT NULL,
  value_norm TEXT NOT NULL,
  category TEXT,
  source TEXT NOT NULL,
  added_on TEXT NOT NULL,
  UNIQUE(kind, value_norm)
);
CREATE TABLE IF NOT EXISTS allowlist (
  id INTEGER PRIMARY KEY,
  kind TEXT NOT NULL,
  value_norm TEXT NOT NULL,
  org TEXT,
  source TEXT NOT NULL,
  UNIQUE(kind, value_norm)
);
CREATE TABLE IF NOT EXISTS official_domains (
  id INTEGER PRIMARY KEY,
  org TEXT NOT NULL,
  org_type TEXT NOT NULL,
  domain TEXT NOT NULL UNIQUE,
  status TEXT CHECK(status IN ('verified','legacy','unverified')) NOT NULL,
  verified_on TEXT,
  source_url TEXT NOT NULL,
  brand_tokens TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class OfficialDomain:
    org: str
    org_type: str
    domain: str
    status: str
    brand_tokens: tuple[str, ...]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(handle)]


def _read_list(path: Path) -> frozenset[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return frozenset(
        line.strip().lower() for line in lines if line.strip() and not line.startswith("#")
    )


class IntelDB:
    def __init__(
        self,
        conn: sqlite3.Connection,
        shorteners: frozenset[str],
        suspicious_tlds: frozenset[str],
    ) -> None:
        self._conn = conn
        self.shorteners = shorteners
        self.suspicious_tlds = suspicious_tlds
        self._official = self._load_official()

    @classmethod
    def build(cls, data_dir: Path = DEFAULT_DATA_DIR, db_path: str = ":memory:") -> IntelDB:
        blocked = _read_csv(data_dir / "blocklist.csv")
        bad = [r["value"] for r in blocked if r["kind"] == "phone" and DESIGNATED_SERIES.search(r["value"])]
        if bad:
            # FR-081 / ADR-009: TRAI-designated series must never be blocklisted.
            raise ValueError(f"blocklist.csv contains designated-series numbers: {len(bad)} rows")
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.executescript(_SCHEMA)
        with conn:
            conn.executemany(
                "INSERT OR REPLACE INTO blocklist(kind, value_norm, category, source, added_on)"
                " VALUES (?, ?, ?, ?, ?)",
                [
                    (r["kind"], r["value"].lower(), r["category"], r["source"], r["added_on"])
                    for r in blocked
                ],
            )
            conn.executemany(
                "INSERT OR REPLACE INTO allowlist(kind, value_norm, org, source) VALUES (?, ?, ?, ?)",
                [
                    (r["kind"], r["value"].lower(), r["org"], r["source"])
                    for r in _read_csv(data_dir / "allowlist.csv")
                ],
            )
            conn.executemany(
                "INSERT OR REPLACE INTO official_domains"
                "(org, org_type, domain, status, verified_on, source_url, brand_tokens)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        r["org"], r["org_type"], r["domain"].lower(), r["status"],
                        r["verified_on"] or None, r["source_url"], r["brand_tokens"].lower(),
                    )
                    for r in _read_csv(data_dir / "official_domains.csv")
                ],
            )
        return cls(
            conn,
            shorteners=_read_list(data_dir / "shorteners.txt"),
            suspicious_tlds=_read_list(data_dir / "suspicious_tlds.txt"),
        )

    def _load_official(self) -> tuple[OfficialDomain, ...]:
        rows = self._conn.execute(
            "SELECT org, org_type, domain, status, brand_tokens FROM official_domains"
        ).fetchall()
        return tuple(
            OfficialDomain(org, org_type, domain, status, tuple(t for t in tokens.split("|") if t))
            for org, org_type, domain, status, tokens in rows
        )

    @property
    def official(self) -> tuple[OfficialDomain, ...]:
        return self._official

    def official_for_domain(self, registrable: str) -> OfficialDomain | None:
        return next((o for o in self._official if o.domain == registrable.lower()), None)

    def blocklist_category(self, kind: str, value_norm: str) -> str | None:
        row = self._conn.execute(
            "SELECT category FROM blocklist WHERE kind = ? AND value_norm = ?",
            (kind, value_norm.lower()),
        ).fetchone()
        return None if row is None else str(row[0] or "")

    def allowlist_org(self, kind: str, value_norm: str) -> str | None:
        row = self._conn.execute(
            "SELECT org FROM allowlist WHERE kind = ? AND value_norm = ?",
            (kind, value_norm.lower()),
        ).fetchone()
        return None if row is None else str(row[0] or "")

    def close(self) -> None:
        self._conn.close()
