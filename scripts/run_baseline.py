"""Print the rules-only baseline (B0) result for each demo case and check its outcome.

Usage (from the project root):
    .venv\\Scripts\\python.exe scripts\\run_baseline.py [path\\to\\cases.jsonl]

Outcome checks: scams warned about, genuine messages without alarm, required behaviours
(evaluation/labels.py). B0 cannot interview, so ambiguous cases are only reported.
Output contains masked text and derived values only.
"""

from __future__ import annotations

import sys
from pathlib import Path

from scamsaathi.config import PROJECT_ROOT
from scamsaathi.evaluation.labels import check_behaviours, check_core, load_cases
from scamsaathi.pipeline.baseline import assess
from scamsaathi.tools.intel_db import IntelDB


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT_ROOT / "data/demo/baseline_samples.jsonl"
    cases = load_cases(path)
    db = IntelDB.build()
    misses = 0
    try:
        for case in cases:
            result = assess(case.text, db)
            failures = check_core(case, result.risk, asked_questions=None) + check_behaviours(
                case, result.risk, advice=None, intel=result.intel, asked_questions=None)
            misses += bool(failures)
            print(f"{'OK ' if not failures else 'MISS'} {case.id:<26} {case.label:<9} -> "
                  f"{result.risk.level:<8} {result.risk.value:>3}  "
                  f"lang={result.language.language.value}")
            for failure in failures:
                print(f"       ** {failure}")
            for c in result.risk.contributions:
                print(f"       {c.points:>+6.1f}  {c.factor:<40} {','.join(c.evidence_ids)}")
            for o in result.risk.overrides:
                print(f"       override: {o}")
    finally:
        db.close()
    print(f"\n{len(cases) - misses}/{len(cases)} cases meet their outcome checks")
    return 1 if misses else 0


if __name__ == "__main__":
    raise SystemExit(main())
