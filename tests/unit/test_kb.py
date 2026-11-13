"""Knowledge base integrity, freshness, advice, and retrieval (tasks 3.1 to 3.4; IT-RAG-01)."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Literal

import pytest

from scamsaathi.config import PROJECT_ROOT
from scamsaathi.kb.advice import build_advice
from scamsaathi.kb.retrieval import (
    DenseRetriever,
    HybridRetriever,
    LexicalRetriever,
    rank_typologies,
    tokenize,
)
from scamsaathi.kb.store import load_kb, load_kb_config
from scamsaathi.tools import rule_signals
from scamsaathi.tools.pii_masker import contains_pii
from scamsaathi.tools.risk_scorer import Situation

KB = load_kb()
CFG = load_kb_config()
TODAY = date.today()


# --- Integrity and freshness (R-009) ---------------------------------------------------


def test_all_typologies_present_and_sourced() -> None:
    assert sorted(KB.typologies) == [f"SC-{i:02d}" for i in range(1, 16)]
    for typology in KB.typologies.values():
        assert typology.sources and set(typology.sources) <= set(KB.sources)


def test_every_typology_has_a_primary_source_or_is_flagged() -> None:
    lacking = [
        t.code for t in KB.typologies.values()
        if not any(KB.sources[s].type == "primary" for s in t.sources)
    ]
    assert lacking == [], f"add a primary source for {lacking}"


def test_typologies_reviewed_within_window() -> None:
    limit = CFG.freshness["typology_max_age_days"]
    stale = [t.code for t in KB.typologies.values() if (TODAY - t.last_reviewed).days > limit]
    assert stale == []


def test_contacts_fresh_and_sourced() -> None:
    limit = CFG.freshness["contacts_max_age_days"]
    for contact in KB.contacts.values():
        assert (TODAY - contact.verified_on).days <= limit, f"re-verify {contact.id}"
        assert contact.source_url.startswith("https://")


def test_kb_content_has_no_pii() -> None:
    for chunk in KB.chunks:
        assert not contains_pii(chunk.text), chunk.chunk_id


def test_kb_version_is_stable() -> None:
    assert load_kb().version == KB.version and len(KB.version) == 12


def test_chunks_cover_both_languages() -> None:
    assert {c.language for c in KB.chunks} == {"en", "hinglish"}
    assert len(KB.chunks) == len(KB.typologies) * 7


# --- Advice (FR-050 to FR-052, FR-064) --------------------------------------------------

_NUMBER_OR_URL = re.compile(r"https?://\S+|\b\d{3,}\b")


def _all_advice_texts() -> list[str]:
    a = KB.advice
    texts = (list(a.urgent_recovery) + a.child_safety + a.evidence + a.police_reporting
             + a.report_suspected + a.spam)
    texts += [t for items in a.by_level.values() for t in items]
    texts += [t for items in a.by_typology.values() for t in items]
    texts += [t for ty in KB.typologies.values() for t in ty.recommended_actions]
    return texts


def test_advice_never_asks_for_secrets() -> None:
    for text in _all_advice_texts():
        names = {s.name.value for s in rule_signals.detect(text, has_link=False)}
        assert "credential_request" not in names, text


def test_advice_numbers_and_urls_come_from_verified_contacts() -> None:
    # TRAI series prefixes are number ranges, not phone numbers (docs/16 section 4).
    allowed = {c.value for c in KB.contacts.values()} | {"140", "1600"}
    for text in _all_advice_texts():
        for token in _NUMBER_OR_URL.findall(text):
            assert token in allowed or token.isdigit() and len(token) <= 2, (token, text)


def test_urgent_recovery_comes_first_with_1930() -> None:
    bundle = build_advice(KB, "LOW", ["SC-04"], Situation(money_sent=True))
    assert bundle.urgent_recovery_mode
    assert "1930" in bundle.actions[0].text
    assert [c.value for c in bundle.contacts] == ["1930", "https://cybercrime.gov.in"]


def test_suspected_case_points_to_chakshu_not_1930() -> None:
    bundle = build_advice(KB, "HIGH", ["SC-02"])
    values = [c.value for c in bundle.contacts]
    assert "https://sancharsaathi.gov.in/sfc" in values and "1930" not in values
    assert any(".bank.in" in a.text for a in bundle.actions)
    assert [a.priority for a in bundle.actions] == list(range(1, len(bundle.actions) + 1))


def test_low_risk_advice_is_calm_and_has_no_contacts() -> None:
    bundle = build_advice(KB, "LOW", ["SC-08"])
    assert len(bundle.actions) == 1 and bundle.contacts == []


# --- Retrieval (FR-020, IT-RAG-01) ------------------------------------------------------

_QUERIES = [
    json.loads(line)
    for line in (PROJECT_ROOT / "data/kb/retrieval_eval.jsonl").read_text(encoding="utf-8").splitlines()
    if line.strip()
]


def test_tokenizer() -> None:
    assert tokenize("Blocked accounts, parcels & OTP 123456") == ["block", "account", "parcel", "otp"]


def test_it_rag_01_kyc_query_retrieves_sc02() -> None:
    lexical = LexicalRetriever(KB, min_score=CFG.min_lexical_score)
    results = lexical.retrieve("Your account will be blocked, update KYC at the link", k=CFG.top_k)
    assert results and results[0].chunk.code == "SC-02"


def test_retrieval_filters_and_empty_results() -> None:
    lexical = LexicalRetriever(KB, min_score=CFG.min_lexical_score)
    only = lexical.retrieve("parcel customs fee", k=4, codes=["SC-07"])
    assert only and {r.chunk.code for r in only} == {"SC-07"}
    assert lexical.retrieve("zzqx unrelated", k=4) == []


def test_lexical_recall_on_eval_set() -> None:
    """Regression floor for the ADR-004 baseline (actual figures in docs/13)."""
    lexical = LexicalRetriever(KB, min_score=CFG.min_lexical_score)
    hits = sum(
        q["expected"] in [c for c, _ in rank_typologies(lexical.retrieve(q["query"], k=12))][:3]
        for q in _QUERIES
    )
    assert hits / len(_QUERIES) >= 0.75


class _FakeEmbedder:
    """Deterministic bag-of-words embedder to exercise the dense and hybrid code paths."""

    name = "fake:bow"

    def __init__(self) -> None:
        self.vocab = sorted({t for c in KB.chunks for t in tokenize(c.text)})
        self.calls = 0

    def embed(self, texts: Sequence[str], kind: Literal["document", "query"]) -> list[list[float]]:
        self.calls += 1
        index = {t: i for i, t in enumerate(self.vocab)}
        out = []
        for text in texts:
            vec = [0.0] * len(self.vocab)
            for token in tokenize(text):
                if token in index:
                    vec[index[token]] += 1.0
            out.append(vec)
        return out


def test_dense_index_cached_and_offline_reuse(tmp_path: Path) -> None:
    embedder = _FakeEmbedder()
    dense = DenseRetriever(KB, embedder, tmp_path)
    assert dense.retrieve("lucky draw prize fee", k=1)[0].chunk.code == "SC-08"
    calls = embedder.calls

    offline = DenseRetriever(KB, embedder, tmp_path, offline=True)
    assert offline.retrieve("lucky draw prize fee", k=1)[0].chunk.code == "SC-08"
    assert embedder.calls == calls  # index and query vector both served from cache
    with pytest.raises(KeyError):
        offline.retrieve("a query never embedded", k=1)


def test_hybrid_fuses_and_degrades_to_lexical(tmp_path: Path) -> None:
    lexical = LexicalRetriever(KB, min_score=CFG.min_lexical_score)
    hybrid = HybridRetriever(lexical, DenseRetriever(KB, _FakeEmbedder(), tmp_path))
    fused = hybrid.retrieve("install AnyDesk for refund", k=3)
    assert fused[0].method == "hybrid" and fused[0].chunk.code == "SC-11"

    broken = HybridRetriever(lexical, DenseRetriever(KB, _FakeEmbedder(), tmp_path, offline=True))
    results = broken.retrieve("query not in the offline cache", k=3)
    assert broken.degraded and all(r.method == "lexical" for r in results)


def test_kb_loader_rejects_unknown_source(tmp_path: Path) -> None:
    import shutil

    data = tmp_path / "data"
    shutil.copytree(PROJECT_ROOT / "data", data)
    path = data / "kb" / "typologies" / "SC-01.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("sources: [", "sources: [NOPE, "),
                    encoding="utf-8")
    with pytest.raises(ValueError, match="unknown source IDs"):
        load_kb(data)
