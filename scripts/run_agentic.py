"""Task 4.6: run the demo cases through the full agent graph and check outcomes.

Usage (from the project root, PYTHONPATH=src):
    .venv\\Scripts\\python.exe -u scripts\\run_agentic.py            # mode from .env
    .venv\\Scripts\\python.exe -u scripts\\run_agentic.py --verbose  # reasons, actions, contacts

Cases are judged by outcomes that exist in reality (scam caught, no false alarm on a genuine
message, questions asked when the case is vague, required behaviours, typology), not by
risk level (evaluation/labels.py). Interviews are answered with "skip".

Live mode makes about 3 Gemini calls per case. Responses are cached, so repeat runs with
unchanged inputs are free; `live_calls` counts only calls that reached the API.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

# Ensure 'src' is in sys.path so scamsaathi is discoverable when launched directly
_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from scamsaathi.agents.context import build_context
from scamsaathi.config import PROJECT_ROOT, get_settings
from scamsaathi.evaluation.labels import check_behaviours, check_core, check_typology, load_cases
from scamsaathi.logging_setup import configure_logging
from scamsaathi.pipeline.agentic import AgentRunner


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    settings = get_settings()
    configure_logging("WARNING")
    runner = AgentRunner(build_context(settings))
    cases = load_cases(PROJECT_ROOT / "data" / "demo" / "baseline_samples.jsonl")
    print(f"mode={settings.mode.value} cases={len(cases)} "
          f"max_llm_calls={settings.max_llm_calls_per_request}")

    totals: Counter[str] = Counter()
    passed = live_calls = 0
    for case in cases:
        outcome = None
        try:
            first = runner.assess(case.text)
            asked = first.status == "needs_followup"
            outcome = first
            n_questions = 0
            while outcome.status == "needs_followup":
                n_questions += len(outcome.questions)
                outcome = runner.resume(outcome.thread_id, "skip")
            assert outcome.risk is not None and outcome.explanation is not None
            core = check_core(case, outcome.risk, asked)
            behaviours = check_behaviours(case, outcome.risk, outcome.advice, outcome.intel, asked)
            typology = check_typology(case, outcome.typologies)
            failures = core + behaviours + typology
            passed += not failures
            live_calls += outcome.llm_calls
            totals[f"{case.label}_total"] += 1
            totals[f"{case.label}_ok"] += not core
            if case.required:
                totals["behaviour_total"] += 1
                totals["behaviour_ok"] += not behaviours
            if case.label == "scam" and case.typologies:
                totals["typology_total"] += 1
                totals["typology_ok"] += not typology

            flags = ("degraded " if outcome.degraded else "") + (
                f"asked={n_questions} " if n_questions else "")
            print(f"{'OK  ' if not failures else 'FAIL'} {case.id:<25} {case.label:<9} "
                  f"-> {outcome.risk.level:<8} {outcome.risk.value:>3}  "
                  f"typ={','.join(outcome.typologies) or '-':<13} live_calls={outcome.llm_calls} "
                  f"expl={outcome.explanation_source} lang={outcome.language} {flags}")
            print(f"       {outcome.explanation.headline}")
            for failure in failures:
                print(f"       ** {failure}")
            if args.verbose and outcome.advice is not None:
                for reason in outcome.explanation.reasons:
                    print(f"       - {reason.text} {reason.evidence_ids}")
                for action in outcome.advice.actions:
                    print(f"       {action.priority}. {action.text}")
                for contact in outcome.advice.contacts:
                    print(f"       > {contact.name}: {contact.value}")
            for error in outcome.errors:
                print(f"       note: {error}")
        finally:
            if outcome is not None:
                runner.clear_session(outcome.thread_id, purge_checkpoint=True)

    def rate(key: str) -> str:
        return f"{totals[key + '_ok']}/{totals[key + '_total']}"

    print("\nOutcomes")
    print(f"  scams warned about (not LOW)        {rate('scam')}")
    print(f"  genuine messages without alarm      {rate('legit')}")
    print(f"  ambiguous cases interviewed         {rate('ambiguous')}")
    print(f"  required behaviours met             {rate('behaviour')}")
    print(f"  top typology correct (scams)        {rate('typology')}")
    print(f"  cases fully passing                 {passed}/{len(cases)}")
    print(f"  live LLM calls (cache hits are free) {live_calls}")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
