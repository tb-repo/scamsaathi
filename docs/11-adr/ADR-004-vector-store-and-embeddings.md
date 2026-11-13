# ADR-004: Vector store and embeddings

| Field | Value |
|---|---|
| Status | Accepted (revised in P3): hybrid BM25 + Gemini embeddings (`gemini-embedding-001`), no vector DB. Dense comparison done 2026-11-13 |
| Date | 2026-11-11 |
| Deciders | Thiagarajan Baskarasubramanian |

## Context

The KB is small (tens to low hundreds of chunks) and multilingual (English, Hinglish). The laptop has 16 GB RAM and no GPU. Data in the KB is public-guidance paraphrase, not sensitive.

## Options

Vector store:
1. **Chroma (persistent).** Simple, metadata filters, easy local use.
2. FAISS. Fast, lower-level, no built-in metadata.
3. In-memory numpy cosine search. Enough for this scale, minimal dependencies.

Embeddings:
1. **Local multilingual model on CPU** (for example multilingual-e5-small class). No per-call cost, offline capable, download size and CPU latency to measure.
2. **Gemini embedding API.** No local weights, per-call cost small, requires network and sends KB text/queries (masked) to the provider.

## Why not an external or managed database (Pinecone, MongoDB Atlas, etc.)

- **Scale:** The KB is tens to low hundreds of chunks. Managed vector databases are built for millions of vectors and add no benefit here.
- **Cost and accounts:** They need extra sign-ups, keys, and possibly cost or free-tier limits to track.
- **Privacy and offline:** Local storage keeps data on the laptop and supports the offline demo mode (FR-074). A hosted service breaks offline mode.
- **Reproducibility:** The index is rebuilt from files in `data/kb/`, so graders can reproduce it with one script.
- **Complexity:** Extra network dependency, latency, and failure modes for no gain.
- **Revisit when:** The KB grows to a very large size, multiple users need shared writable data, or the app is deployed as a multi-instance service. This is listed as future work, and the retriever interface hides the store so a swap is a small change.

## Original proposal (superseded below)

Chroma persistent collection with a local multilingual embedding model, compared against the Gemini embedding API in P3.

## Decision (revised 2026-11-11, Phase 3)

**Hybrid retrieval with no vector database:**

1. **Lexical BM25** over the KB chunks, always on. Pure Python, no download, works in offline mode.
2. **Dense retrieval with Gemini embeddings** (`gemini-embedding-001` by default; `gemini-embedding-2` is the alternative candidate), enabled when `GEMINI_API_KEY` is set. Document and query vectors are cached as JSON in `.cache/kb/`, so cached and offline modes can reuse them.
3. **Fusion** by reciprocal rank (RRF, k=60). If the dense side fails, retrieval falls back to lexical only and is flagged as degraded.
4. Vectors are held in memory. The `Retriever` interface lets Chroma (or another store) be swapped in later without changing callers.

### Why the change

| Factor | Finding |
|---|---|
| Scale | 84 chunks (12 typologies x 7 sections). Exhaustive cosine search over 84 vectors is trivial in pure Python; a vector database adds dependencies without benefit |
| Device constraints | Application Control already blocks one native tool (ruff, I-002). Chroma and local embedding models pull in large native dependencies (an ONNX or PyTorch runtime, model downloads). They were not attempted, to avoid a likely second blocker; this risk is assumed, not tested |
| Offline mode (FR-074) | BM25 needs nothing external; cached vectors cover known queries |
| Measured baseline | BM25 on 24 synthetic queries (12 English, 12 Hinglish): typology recall@1 23/24 (96%), recall@3 24/24 (100%). Caveat: the author wrote both the KB and the queries, so vocabulary overlap inflates this; the real test set will be harder |

### Dense comparison (2026-11-13, task 3.3): hybrid confirmed

`scripts/eval_retrieval.py --dense`, KB version 44d52746704f: 15 typologies, 105 chunks, 30 synthetic queries (15 English, 15 Hinglish). Embedding model `gemini-embedding-001` at its default dimensionality. Cost was a few paise; vectors are cached in `.cache/kb/`.

| Method | recall@1 | recall@3 | Hinglish recall@1 / @3 | Misses at rank 1 |
|---|---|---|---|---|
| Lexical (BM25) | 27/30 (90%) | 29/30 (97%) | 13/15 / 15/15 | R02, R03, R24 |
| Dense (Gemini) | 27/30 (90%) | 30/30 (100%) | 12/15 / 15/15 | R08, R12, R24 |
| **Hybrid (RRF, k=60)** | **29/30 (97%)** | **30/30 (100%)** | **14/15 / 15/15** | R24 |

**Decision:** keep hybrid with `gemini-embedding-001` at the default dimensionality. The keep condition (no loss of Hinglish recall@3 against lexical) is met, and hybrid improves recall@1 by 2 queries. Lexical and dense fail on *different* queries, which is why fusion helps. R24 (SC-12, "relative or friend in trouble") is ranked third by all three methods. It is a known overlap with SC-14 and SC-07 wording, to be revisited when the evaluation set grows (Phase 7). `gemini-embedding-2` was not tested: the current model meets the target, and a switch would need a fresh index and evaluation.

Caveat (unchanged): the author wrote both the KB and the queries, so these numbers are optimistic. The Phase 7 test set is the real measure.

## Consequences

No new dependencies. Retrieval works with or without the API key. Hybrid adds a small, measured gain over lexical alone (recall@1 90% to 97%). A local embedding model remains a documented option if offline semantic search becomes a requirement.

## Related
FR-020, FR-074, document 07.
