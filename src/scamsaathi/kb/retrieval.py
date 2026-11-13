"""Hybrid retrieval over the knowledge base (task 3.4, FR-020, ADR-004).

- ``LexicalRetriever``: BM25 over chunk text. No network, no model download, works in offline
  mode, and handles Hinglish keywords well.
- ``DenseRetriever``: cosine similarity over embeddings from a pluggable ``Embedder``
  (Gemini by default). Document vectors and query vectors are cached on disk so cached and
  offline modes can still use them.
- ``HybridRetriever``: reciprocal rank fusion of both; falls back to lexical only if the dense
  side fails (NFR-005).

At this scale (about 100 chunks) a vector database adds nothing, so vectors are held in memory
and persisted as JSON. The ``Retriever`` interface allows a swap to Chroma later (ADR-004).
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, Protocol

from scamsaathi.kb.store import KBChunk, KnowledgeBase
from scamsaathi.tools.pii_masker import contains_pii

logger = logging.getLogger("scamsaathi.kb")

_TOKEN: Final = re.compile(r"[a-z0-9]+|[\u0900-\u097f]+")
_STOPWORDS: Final = frozenset(
    """
    a an the and or but if of to in on at by for with from as is are was were be been being
    this that these those it its you your yours i me my we our they them their he she his her
    do does did have has had will would can could should may might not no so than then there
    here what which who whom when where why how all any each more most other some such only
    own same too very just also into about over after before again further once
    ka ki ke ko se hai hain ho
    """.split()
)


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens with a tiny suffix stemmer; digits-only tokens are dropped."""
    tokens: list[str] = []
    for token in _TOKEN.findall(text.lower()):
        if token in _STOPWORDS or token.isdigit():
            continue
        for suffix in ("ing", "ed", "es", "s"):
            if token.endswith(suffix) and len(token) - len(suffix) >= 4:
                token = token[: -len(suffix)]
                break
        tokens.append(token)
    return tokens


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: KBChunk
    score: float
    method: Literal["lexical", "dense", "hybrid"]


class Retriever(Protocol):
    def retrieve(
        self, query: str, k: int = 4, codes: Iterable[str] | None = None
    ) -> list[RetrievedChunk]: ...


def _allowed(chunk: KBChunk, codes: set[str] | None) -> bool:
    return codes is None or chunk.code in codes


class LexicalRetriever:
    """Okapi BM25 (k1=1.5, b=0.75)."""

    def __init__(
        self, kb: KnowledgeBase, min_score: float = 0.5, k1: float = 1.5, b: float = 0.75
    ) -> None:
        self._chunks = kb.chunks
        self._docs = [Counter(tokenize(c.text)) for c in kb.chunks]
        self._lengths = [sum(d.values()) for d in self._docs]
        self._avg = sum(self._lengths) / max(1, len(self._lengths))
        df: Counter[str] = Counter()
        for doc in self._docs:
            df.update(doc.keys())
        n = len(self._docs)
        self._idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self._k1, self._b, self._min = k1, b, min_score

    def scores(self, query: str) -> list[float]:
        terms = tokenize(query)
        out: list[float] = []
        for doc, length in zip(self._docs, self._lengths, strict=True):
            total = 0.0
            for term in terms:
                tf = doc.get(term, 0)
                if tf:
                    norm = tf + self._k1 * (1 - self._b + self._b * length / self._avg)
                    total += self._idf[term] * tf * (self._k1 + 1) / norm
            out.append(total)
        return out

    def retrieve(
        self, query: str, k: int = 4, codes: Iterable[str] | None = None
    ) -> list[RetrievedChunk]:
        allowed = set(codes) if codes is not None else None
        ranked = sorted(
            (
                (score, i)
                for i, score in enumerate(self.scores(query))
                if score >= self._min and _allowed(self._chunks[i], allowed)
            ),
            key=lambda item: (-item[0], item[1]),
        )
        return [RetrievedChunk(self._chunks[i], round(s, 4), "lexical") for s, i in ranked[:k]]


# --- Dense retrieval -------------------------------------------------------------------


class Embedder(Protocol):
    name: str

    def embed(self, texts: Sequence[str], kind: Literal["document", "query"]) -> list[list[float]]:
        ...


class GeminiEmbedder:
    """Gemini embeddings via google-genai (API verified against google-genai 3.2.0)."""

    def __init__(self, api_key: str, model: str, output_dimensionality: int | None = None) -> None:
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._dims = output_dimensionality
        self.name = f"gemini:{model}:{output_dimensionality or 'default'}"

    def embed(self, texts: Sequence[str], kind: Literal["document", "query"]) -> list[list[float]]:
        from google.genai import types

        if any(contains_pii(t) for t in texts):
            raise ValueError("refusing to embed text that contains unmasked PII")
        task = "RETRIEVAL_DOCUMENT" if kind == "document" else "RETRIEVAL_QUERY"
        vectors: list[list[float]] = []
        for start in range(0, len(texts), 100):
            batch = list(texts[start : start + 100])
            response = self._client.models.embed_content(
                model=self._model,
                contents=batch,
                config=types.EmbedContentConfig(
                    task_type=task, output_dimensionality=self._dims
                ),
            )
            for embedding in response.embeddings or []:
                vectors.append(list(embedding.values or []))
        if len(vectors) != len(texts):
            raise RuntimeError("embedding count mismatch")
        return vectors


def _normalise(vector: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


class DenseRetriever:
    """Cosine search over cached document vectors; query vectors are cached by hash."""

    def __init__(
        self, kb: KnowledgeBase, embedder: Embedder, cache_dir: Path, offline: bool = False
    ) -> None:
        self._kb = kb
        self._embedder = embedder
        self._offline = offline
        safe = re.sub(r"[^a-z0-9]+", "-", embedder.name.lower())
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = cache_dir / f"kb-index-{kb.version}-{safe}.json"
        self._query_path = cache_dir / f"kb-queries-{safe}.json"
        self._vectors = self._load_or_build()
        self._queries: dict[str, list[float]] = (
            json.loads(self._query_path.read_text(encoding="utf-8"))
            if self._query_path.exists()
            else {}
        )

    def _load_or_build(self) -> dict[str, list[float]]:
        if self._index_path.exists():
            data = json.loads(self._index_path.read_text(encoding="utf-8"))
            return {k: list(v) for k, v in data["vectors"].items()}
        if self._offline:
            raise FileNotFoundError(f"no embedding index at {self._index_path.name} (offline)")
        texts = [c.text for c in self._kb.chunks]
        vectors = self._embedder.embed(texts, "document")
        index = {c.chunk_id: _normalise(v) for c, v in zip(self._kb.chunks, vectors, strict=True)}
        self._index_path.write_text(
            json.dumps({"kb_version": self._kb.version, "model": self._embedder.name,
                        "vectors": index}),
            encoding="utf-8",
        )
        logger.info("kb_index_built", extra={"chunks": len(index), "embedder": self._embedder.name})
        return index

    def _query_vector(self, query: str) -> list[float]:
        key = hashlib.sha256(query.encode("utf-8")).hexdigest()
        if key not in self._queries:
            if self._offline:
                raise KeyError("query embedding not cached (offline)")
            self._queries[key] = _normalise(self._embedder.embed([query], "query")[0])
            self._query_path.write_text(json.dumps(self._queries), encoding="utf-8")
        return self._queries[key]

    def retrieve(
        self, query: str, k: int = 4, codes: Iterable[str] | None = None
    ) -> list[RetrievedChunk]:
        allowed = set(codes) if codes is not None else None
        qv = self._query_vector(query)
        ranked = sorted(
            (
                (_dot(qv, self._vectors[c.chunk_id]), i, c)
                for i, c in enumerate(self._kb.chunks)
                if _allowed(c, allowed) and c.chunk_id in self._vectors
            ),
            key=lambda item: (-item[0], item[1]),
        )
        return [RetrievedChunk(c, round(s, 4), "dense") for s, _, c in ranked[:k]]


class HybridRetriever:
    """Reciprocal rank fusion of lexical and (optional) dense results."""

    def __init__(
        self, lexical: LexicalRetriever, dense: Retriever | None = None, rrf_k: int = 60
    ) -> None:
        self._lexical = lexical
        self._dense = dense
        self._rrf_k = rrf_k
        self.degraded = False

    def retrieve(
        self, query: str, k: int = 4, codes: Iterable[str] | None = None
    ) -> list[RetrievedChunk]:
        pool = max(k * 5, 20)
        allowed = list(codes) if codes is not None else None
        lists = [self._lexical.retrieve(query, pool, allowed)]
        self.degraded = False
        if self._dense is not None:
            try:
                lists.append(self._dense.retrieve(query, pool, allowed))
            except Exception as exc:  # noqa: BLE001 - any dense failure degrades to lexical
                self.degraded = True
                logger.warning("kb_dense_failed", extra={"error_type": type(exc).__name__})
        if len(lists) == 1:
            return lists[0][:k]

        fused: dict[str, float] = {}
        chunks: dict[str, KBChunk] = {}
        for results in lists:
            for rank, item in enumerate(results, start=1):
                fused[item.chunk.chunk_id] = fused.get(item.chunk.chunk_id, 0.0) + 1 / (
                    self._rrf_k + rank
                )
                chunks[item.chunk.chunk_id] = item.chunk
        ranked = sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))
        return [RetrievedChunk(chunks[cid], round(score, 6), "hybrid") for cid, score in ranked[:k]]


def rank_typologies(results: Sequence[RetrievedChunk]) -> list[tuple[str, float]]:
    """Aggregate chunk results into typology codes (best chunk score, then hit count)."""
    best: dict[str, float] = {}
    hits: Counter[str] = Counter()
    for item in results:
        best[item.chunk.code] = max(best.get(item.chunk.code, 0.0), item.score)
        hits[item.chunk.code] += 1
    return sorted(best.items(), key=lambda kv: (-kv[1], -hits[kv[0]], kv[0]))
