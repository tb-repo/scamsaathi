"""Build the configured retriever (lexical always; dense when a key and index allow)."""

from __future__ import annotations

import logging

from scamsaathi.config import Mode, Settings
from scamsaathi.kb.retrieval import DenseRetriever, GeminiEmbedder, HybridRetriever, LexicalRetriever
from scamsaathi.kb.store import KBConfig, KnowledgeBase

logger = logging.getLogger("scamsaathi.kb")


def build_retriever(kb: KnowledgeBase, config: KBConfig, settings: Settings) -> HybridRetriever:
    lexical = LexicalRetriever(kb, min_score=config.min_lexical_score)
    dense = None
    emb = config.embedding
    if emb.get("enabled") and settings.gemini_api_key is not None:
        try:
            dense = DenseRetriever(
                kb,
                GeminiEmbedder(
                    settings.gemini_api_key.get_secret_value(),
                    model=str(emb["model"]),
                    output_dimensionality=emb.get("output_dimensionality"),
                ),
                cache_dir=settings.llm_cache_dir.parent / "kb",
                offline=settings.mode is not Mode.LIVE,
            )
        except Exception as exc:  # noqa: BLE001 - dense retrieval is optional
            logger.warning("kb_dense_unavailable", extra={"error_type": type(exc).__name__})
    return HybridRetriever(lexical, dense, rrf_k=config.rrf_k)
