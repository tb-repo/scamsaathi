"""Typed loading and validation of the knowledge base (task 3.1, docs/07 sections 3 and 4).

All content lives in reviewable YAML under ``data/``. Loading fails loudly on schema errors,
unknown source IDs, or mismatched file names, so bad content cannot reach the agents.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from scamsaathi.config import CONFIG_DIR, PROJECT_ROOT, load_yaml
from scamsaathi.schemas import OfficialContact, SignalName

DATA_DIR = PROJECT_ROOT / "data"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(_Strict):
    title: str
    url: str | None = Field(default=None, pattern=r"^https://")
    path: str | None = None  # official document kept in the repo (docs/IndianOfficialDocs)
    type: Literal["primary", "secondary"]
    accessed: date
    check: Literal["page_loaded", "official_index", "snippet_only", "document_read"]

    @model_validator(mode="after")
    def _has_location(self) -> Source:
        if not self.url and not self.path:
            raise ValueError("a source needs a url or a path")
        return self


class Typology(_Strict):
    code: str = Field(pattern=r"^SC-\d{2}$")
    name: str
    version: int = Field(ge=1)
    last_reviewed: date
    summary: str
    how_it_works: list[str] = Field(min_length=1)
    red_flags: list[str] = Field(min_length=1)
    legit_contrast: list[str] = Field(min_length=1)
    typical_signals: list[SignalName] = Field(min_length=1)
    example_phrases_en: list[str] = Field(min_length=1)
    example_phrases_hinglish: list[str] = Field(min_length=1)
    recommended_actions: list[str] = Field(min_length=1)
    sources: list[str] = Field(min_length=1)
    # Internal traceability only; never shown to users (FR-083). Format "ACT s.N".
    legal_refs: list[str] = Field(default_factory=list)


class Contact(_Strict):
    id: str
    name: str
    channel: Literal["phone", "url"]
    value: str
    use_when: Literal["money_lost", "suspected", "danger", "child_safety", "spam"]
    verified_on: date
    source_url: str = Field(pattern=r"^https://")
    note: str | None = None

    def to_official(self) -> OfficialContact:
        return OfficialContact(
            name=self.name, channel=self.channel, value=self.value,
            verified_on=self.verified_on.isoformat(),
        )


class AdviceTemplates(_Strict):
    version: int
    urgent_recovery: list[str] = Field(min_length=1)
    child_safety: list[str] = Field(min_length=1)
    evidence: list[str] = Field(min_length=1)
    police_reporting: list[str] = Field(min_length=1)
    by_level: dict[Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"], list[str]]
    report_suspected: list[str] = Field(min_length=1)
    spam: list[str] = Field(min_length=1)
    by_typology: dict[str, list[str]]
    contacts_by_situation: dict[
        Literal["money_lost", "suspected", "child_safety", "spam"], list[str]
    ]
    contacts_by_typology: dict[str, list[str]] = Field(default_factory=dict)


class KBChunk(_Strict):
    chunk_id: str
    code: str
    name: str
    section: str
    language: Literal["en", "hinglish"]
    text: str
    source_ids: list[str]


class KBConfig(BaseModel):
    top_k: int = Field(ge=1, le=20)
    rrf_k: int = Field(ge=1)
    min_lexical_score: float = Field(ge=0)
    embedding: dict[str, Any]
    freshness: dict[str, int]


@dataclass(frozen=True)
class KnowledgeBase:
    typologies: dict[str, Typology]
    sources: dict[str, Source]
    contacts: dict[str, Contact]
    advice: AdviceTemplates
    chunks: tuple[KBChunk, ...]
    version: str  # short content hash, reported by /health and used in index cache keys


_SECTIONS: tuple[tuple[str, str], ...] = (
    ("summary", "en"),
    ("how_it_works", "en"),
    ("red_flags", "en"),
    ("legit_contrast", "en"),
    ("example_phrases_en", "en"),
    ("example_phrases_hinglish", "hinglish"),
    ("recommended_actions", "en"),
)


def _chunks(typology: Typology) -> list[KBChunk]:
    out: list[KBChunk] = []
    for section, language in _SECTIONS:
        value = getattr(typology, section)
        body = value if isinstance(value, str) else " ".join(value)
        out.append(
            KBChunk(
                chunk_id=f"{typology.code}:{section}",
                code=typology.code,
                name=typology.name,
                section=section,
                language=language,  # type: ignore[arg-type]
                text=f"{typology.name}. {body.strip()}",
                source_ids=typology.sources,
            )
        )
    return out


def load_kb(data_dir: Path = DATA_DIR) -> KnowledgeBase:
    hasher = hashlib.sha256()

    def read(path: Path) -> dict[str, Any]:
        hasher.update(path.name.encode())
        hasher.update(path.read_bytes())
        return load_yaml(path)

    sources = {
        key: Source.model_validate(value)
        for key, value in read(data_dir / "kb" / "sources.yaml")["sources"].items()
    }
    typologies: dict[str, Typology] = {}
    for path in sorted((data_dir / "kb" / "typologies").glob("SC-*.yaml")):
        typology = Typology.model_validate(read(path))
        if typology.code != path.stem:
            raise ValueError(f"{path.name}: code {typology.code} does not match the file name")
        unknown = set(typology.sources) - set(sources)
        if unknown:
            raise ValueError(f"{path.name}: unknown source IDs {sorted(unknown)}")
        bad_refs = [
            ref for ref in typology.legal_refs
            if ref.split(" ", 1)[0] not in sources or not sources[ref.split(" ", 1)[0]].path
        ]
        if bad_refs:
            raise ValueError(f"{path.name}: legal_refs must cite a repo Act source: {bad_refs}")
        typologies[typology.code] = typology

    contacts = {
        c.id: c
        for c in (
            Contact.model_validate(item)
            for item in read(data_dir / "contacts" / "contacts.yaml")["contacts"]
        )
    }
    advice = AdviceTemplates.model_validate(read(data_dir / "advice" / "advice.yaml"))
    for situation, ids in advice.contacts_by_situation.items():
        missing = set(ids) - set(contacts)
        if missing:
            raise ValueError(f"advice contacts_by_situation.{situation}: unknown {sorted(missing)}")
    unknown_codes = (set(advice.by_typology) | set(advice.contacts_by_typology)) - set(typologies)
    if unknown_codes:
        raise ValueError(f"advice by_typology: unknown codes {sorted(unknown_codes)}")
    for code, ids in advice.contacts_by_typology.items():
        missing = set(ids) - set(contacts)
        if missing:
            raise ValueError(f"advice contacts_by_typology.{code}: unknown {sorted(missing)}")

    chunks = tuple(c for t in typologies.values() for c in _chunks(t))
    return KnowledgeBase(
        typologies=typologies,
        sources=sources,
        contacts=contacts,
        advice=advice,
        chunks=chunks,
        version=hasher.hexdigest()[:12],
    )


@lru_cache(maxsize=2)
def load_kb_config(path: Path = CONFIG_DIR / "kb.yaml") -> KBConfig:
    return KBConfig.model_validate(load_yaml(path))
