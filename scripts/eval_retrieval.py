"""ADR-004 comparison: typology recall@1 and @3 for each retrieval method.

Usage (from the project root, PYTHONPATH=src):
    .venv\\Scripts\\python.exe scripts\\eval_retrieval.py            # lexical only
    .venv\\Scripts\\python.exe scripts\\eval_retrieval.py --dense    # also dense + hybrid (needs GEMINI_API_KEY)

Queries are synthetic and contain no PII. Dense runs make a small number of embedding calls
(about 84 chunks + 24 queries) and cache the vectors.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict

from scamsaathi.config import PROJECT_ROOT, get_settings
from scamsaathi.kb.factory import build_retriever
from scamsaathi.kb.retrieval import HybridRetriever, LexicalRetriever, Retriever, rank_typologies
from scamsaathi.kb.store import load_kb, load_kb_config


def evaluate(name: str, retriever: Retriever, queries: list[dict[str, str]]) -> None:
    by_lang: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    misses = []
    for q in queries:
        codes = [code for code, _ in rank_typologies(retriever.retrieve(q["query"], k=12))]
        stats = by_lang[q["lang"]]
        stats[0] += 1
        stats[1] += codes[:1] == [q["expected"]]
        stats[2] += q["expected"] in codes[:3]
        if codes[:1] != [q["expected"]]:
            misses.append((q["id"], q["expected"], codes[:3]))
    total = [sum(s[i] for s in by_lang.values()) for i in range(3)]
    print(f"\n== {name}: recall@1 {total[1]}/{total[0]} ({total[1] / total[0]:.0%}), "
          f"recall@3 {total[2]}/{total[0]} ({total[2] / total[0]:.0%})")
    for lang, (n, r1, r3) in sorted(by_lang.items()):
        print(f"   {lang:<9} recall@1 {r1}/{n}  recall@3 {r3}/{n}")
    for qid, expected, got in misses:
        print(f"   miss {qid}: expected {expected}, top3 {got}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dense", action="store_true")
    args = parser.parse_args()

    kb = load_kb()
    config = load_kb_config()
    path = PROJECT_ROOT / "data" / "kb" / "retrieval_eval.jsonl"
    queries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(f"KB version {kb.version}: {len(kb.typologies)} typologies, {len(kb.chunks)} chunks, "
          f"{len(queries)} queries")

    lexical = LexicalRetriever(kb, min_score=config.min_lexical_score)
    evaluate("lexical (BM25)", lexical, queries)
    if args.dense:
        hybrid = build_retriever(kb, config, get_settings())
        dense = hybrid._dense  # noqa: SLF001 - evaluation script
        if dense is None:
            print("\nDense retrieval unavailable (no GEMINI_API_KEY or index).")
            return 1
        evaluate("dense", dense, queries)
        evaluate("hybrid (RRF)", HybridRetriever(lexical, dense, rrf_k=config.rrf_k), queries)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
