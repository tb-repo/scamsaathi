"""Validate the knowledge base and build the retrieval indexes.

Usage (from the project root, PYTHONPATH=src):
    .venv\\Scripts\\python.exe scripts\\build_kb.py

Always validates YAML content and builds the lexical index. Builds and caches the embedding
index too when GEMINI_API_KEY is set and the mode is live.
"""

from __future__ import annotations

from scamsaathi.config import get_settings
from scamsaathi.kb.factory import build_retriever
from scamsaathi.kb.store import load_kb, load_kb_config
from scamsaathi.tools.intel_db import IntelDB


def main() -> int:
    kb = load_kb()
    print(f"KB {kb.version}: {len(kb.typologies)} typologies, {len(kb.chunks)} chunks, "
          f"{len(kb.sources)} sources, {len(kb.contacts)} contacts")
    secondary = sorted(k for k, s in kb.sources.items() if s.check == "snippet_only")
    if secondary:
        print(f"Sources still to read in full before release: {', '.join(secondary)}")
    retriever = build_retriever(kb, load_kb_config(), get_settings())
    print(f"Dense retrieval: {'ready' if retriever._dense else 'not configured'}")  # noqa: SLF001
    db = IntelDB.build()
    print(f"Intel: {len(db.official)} official domains")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
