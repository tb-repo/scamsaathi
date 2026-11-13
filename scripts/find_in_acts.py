"""Search the extracted Act texts (.cache/legal) and print matches with context.

Usage (from the project root):
    .venv\\Scripts\\python.exe scripts\\find_in_acts.py "BNS 2023" "^\\s*318\\." --after 25
    .venv\\Scripts\\python.exe scripts\\find_in_acts.py "*" "cheating by personation" --after 3

Arguments: file-name filter ("*" for all), a regular expression, and optional
--before/--after line counts and --max matches per file. Output is UTF-8.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGAL = ROOT / ".cache" / "legal"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("file_filter")
    parser.add_argument("pattern")
    parser.add_argument("--before", type=int, default=1)
    parser.add_argument("--after", type=int, default=12)
    parser.add_argument("--max", type=int, default=5)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    regex = re.compile(args.pattern, re.IGNORECASE | re.MULTILINE)
    files = sorted(LEGAL.glob("*.txt"))
    if args.file_filter != "*":
        files = [f for f in files if args.file_filter.lower() in f.name.lower()]

    out_lines: list[str] = []
    for path in files:
        lines = path.read_text(encoding="utf-8").splitlines()
        page = "?"
        hits = 0
        for i, line in enumerate(lines):
            if line.startswith("[page "):
                page = line[6:-1]
            if regex.search(line):
                hits += 1
                start, end = max(0, i - args.before), min(len(lines), i + args.after + 1)
                out_lines.append(f"===== {path.stem} | page {page} | line {i + 1}")
                out_lines.extend(lines[start:end])
                if hits >= args.max:
                    break
    text = "\n".join(out_lines) if out_lines else "no matches"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
