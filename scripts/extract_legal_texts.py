"""Extract plain text from the official Act PDFs in docs/IndianOfficialDocs.

Usage (from the project root):
    .venv\\Scripts\\python.exe scripts\\extract_legal_texts.py

Writes one UTF-8 .txt per PDF to .cache/legal/ (git-ignored) and prints a summary of
pages and characters so empty (scanned, image-only) PDFs are easy to spot.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "IndianOfficialDocs"
TARGET = ROOT / ".cache" / "legal"


def main() -> int:
    TARGET.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(SOURCE.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {SOURCE}")
        return 1
    for pdf in pdfs:
        try:
            reader = PdfReader(pdf)
            pages = [page.extract_text() or "" for page in reader.pages]
        except Exception as exc:  # noqa: BLE001 - report and continue with other files
            print(f"FAILED  {pdf.name}: {type(exc).__name__}: {exc}")
            continue
        text = "\n\n".join(f"[page {i}]\n{t}" for i, t in enumerate(pages, start=1))
        out = TARGET / (pdf.stem + ".txt")
        out.write_text(text, encoding="utf-8")
        chars = sum(len(t) for t in pages)
        flag = "  (little text: may be scanned)" if chars < 200 * max(1, len(pages)) else ""
        print(f"OK  {len(pages):>4} pages {chars:>9,} chars  {pdf.name}{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
