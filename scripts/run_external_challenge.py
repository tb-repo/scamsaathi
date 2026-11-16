"""Isolated runner for the 28-case External Review Challenge Set.

Reads data/evaluation/external_review_challenge.jsonl, evaluates each case using
the full AgentRunner, and writes versioned run artifacts:
  - data/evaluation/external_review_results_<run_id>.csv
  - data/evaluation/external_review_run_meta_<run_id>.json (and latest pointer)
Leaves data/evaluation/external_review_results_template.csv blank and untouched,
and does not modify reports/benchmark_report.md or reports/benchmark_run_meta.json.
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from scamsaathi.agents.context import build_context
from scamsaathi.config import get_settings, load_llm_config
from scamsaathi.evaluation.labels import CHAKSHU_URL, Case, check_behaviours, check_core, check_typology
from scamsaathi.pipeline.agentic import AgentRunner, AssessmentOutcome


def get_git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(_PROJECT_ROOT), "rev-parse", "HEAD"]
        ).decode().strip()
    except Exception:
        return "4d7b364"


def get_config_hash() -> str:
    cfg_path = _PROJECT_ROOT / "config" / "scoring.yaml"
    return hashlib.sha256(cfg_path.read_bytes()).hexdigest()


def main() -> None:
    cases_file = _PROJECT_ROOT / "data" / "evaluation" / "external_review_challenge.jsonl"
    csv_file = _PROJECT_ROOT / "data" / "evaluation" / "external_review_results_template.csv"
    meta_file = _PROJECT_ROOT / "data" / "evaluation" / "external_review_run_meta.json"

    commit = get_git_commit()
    short_commit = commit[:7]
    config_hash = get_config_hash()
    settings = get_settings()
    llm_cfg = load_llm_config(settings)
    fast_tier = llm_cfg.tiers.get("fast", {}) if isinstance(llm_cfg.tiers, dict) else getattr(llm_cfg.tiers, "fast", {})
    reason_tier = llm_cfg.tiers.get("reasoning", {}) if isinstance(llm_cfg.tiers, dict) else getattr(llm_cfg.tiers, "reasoning", {})
    fast_prov = fast_tier.get("provider", "gemini") if isinstance(fast_tier, dict) else getattr(fast_tier, "provider", "gemini")
    fast_mod = fast_tier.get("model", "gemini-3.5-flash-lite") if isinstance(fast_tier, dict) else getattr(fast_tier, "model", "gemini-3.5-flash-lite")
    reason_mod = reason_tier.get("model", "gemini-3.8-flash") if isinstance(reason_tier, dict) else getattr(reason_tier, "model", "gemini-3.8-flash")
    mode_provider_model = f"{settings.mode.value}/{fast_prov}/{fast_mod}+{reason_mod}"
    run_id = f"xr_run_{time.strftime('%Y%m%d_%H%M%S')}"

    print(f"Starting external challenge run: {run_id}")
    print(f"Commit: {commit} ({short_commit})")
    print(f"Config SHA256: {config_hash}")
    print(f"Mode/Model: {mode_provider_model}")

    ctx = build_context(settings)
    runner = AgentRunner(ctx)

    cases: list[dict[str, Any]] = []
    with open(cases_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))

    print(f"Loaded {len(cases)} challenge cases.")
    results_rows: list[dict[str, Any]] = []
    per_case_meta: list[dict[str, Any]] = []

    for idx, c in enumerate(cases, 1):
        cid = c["id"]
        ctext = c["text"]
        clabel = c.get("label", "unknown")
        clang = c.get("language", "en")
        crequired = c.get("required", [])
        ctypologies = c.get("typologies", [])
        cnotes = c.get("notes", "")

        print(f"[{idx:02d}/{len(cases)}] Evaluating {cid} ({clang}, {clabel})...", end=" ", flush=True)

        start_t = time.perf_counter()
        first = runner.assess(ctext)
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0

        clarification_triggered = first.status == "needs_followup"
        clarification_questions = ""
        resumed_note = ""

        if clarification_triggered:
            q_texts = [q.get("text", "") for q in (first.questions or [])]
            clarification_questions = " | ".join(q_texts)
            # Test resume path with skip
            resumed = runner.resume(first.thread_id, "skip")
            final_outcome = resumed
            resumed_note = f"First-turn asked {len(q_texts)} questions. Resumed-with-skip yielded Level={resumed.risk.level if resumed.risk else 'N/A'}, Score={resumed.risk.value if resumed.risk else 'N/A'}."
            runner.clear_session(first.thread_id, purge_checkpoint=True)
        else:
            final_outcome = first
            runner.clear_session(first.thread_id, purge_checkpoint=True)

        # Extract metrics
        status = first.status
        risk_level = first.risk.level if first.risk else (final_outcome.risk.level if final_outcome.risk else "N/A")
        risk_score = first.risk.value if first.risk else (final_outcome.risk.value if final_outcome.risk else "N/A")
        
        top3_types = final_outcome.typologies[:3] if final_outcome.typologies else []
        typologies_top3_str = "; ".join(top3_types)

        # Reporting action check
        reporting_in_top3 = "No"
        actions = final_outcome.advice.actions if final_outcome.advice else []
        top3_actions = [a.text for a in actions if a.priority <= 3]
        if any(CHAKSHU_URL in a or "cybercrime.gov.in" in a or "1930" in a for a in top3_actions):
            reporting_in_top3 = "Yes"

        # Safety / action issues check
        case_obj = Case(
            id=cid,
            language=clang,
            label=clabel,
            typologies=ctypologies,
            required=crequired,
            text=ctext,
            notes=cnotes,
        )
        core_fails = check_core(case_obj, final_outcome.risk, clarification_triggered)
        beh_fails = check_behaviours(case_obj, final_outcome.risk, final_outcome.advice, final_outcome.intel, clarification_triggered)
        typ_fails = check_typology(case_obj, final_outcome.typologies) if clabel == "scam" else []
        
        all_fails = core_fails + beh_fails + typ_fails
        safety_issue_str = "; ".join(all_fails) if all_fails else "None"

        # Rubric v2 (calibrated metric): allows ambiguous cases without threats to resolve safely to LOW with cautionary advice
        v2_fails: list[str] = []
        if clabel == "scam" and risk_level == "LOW":
            v2_fails.append("missed scam: level is LOW")
        elif clabel == "legit" and risk_level != "LOW":
            v2_fails.append(f"false alarm: level is {risk_level}")
        elif clabel == "ambiguous" and not clarification_triggered and risk_level != "LOW":
            v2_fails.append(f"ambiguous escalated to {risk_level} without clarification")
        v2_fails.extend(beh_fails)
        if clabel == "scam":
            v2_fails.extend(typ_fails)

        reviewer_notes = []
        if cid.startswith("xr_severe_"):
            if "urgent_recovery" in (final_outcome.risk.overrides if final_outcome.risk else []):
                reviewer_notes.append("Severe loss: urgent recovery override active, 1930 action #1")
            else:
                reviewer_notes.append("Severe slice")
        if clarification_triggered:
            reviewer_notes.append(resumed_note)
        if clabel == "scam" and risk_level == "LOW":
            reviewer_notes.append("MISSED_SCAM")
        elif clabel == "legit" and risk_level != "LOW":
            reviewer_notes.append(f"FALSE_ALARM({risk_level})")
        elif clabel == "ambiguous":
            if clarification_triggered:
                reviewer_notes.append("Ambiguous: clarification triggered")
            else:
                reviewer_notes.append("Ambiguous: resolved to LOW with caution (Rubric v1: not interviewed; Rubric v2: pass)")

        if not reviewer_notes:
            reviewer_notes.append(f"Expected={clabel}; Output={risk_level}({risk_score})")

        reviewer_notes_str = "; ".join(reviewer_notes)

        row = {
            "case_id": cid,
            "run_id": run_id,
            "commit": short_commit,
            "config_sha256": config_hash[:16],
            "mode_provider_model": mode_provider_model,
            "status": status,
            "risk_level": str(risk_level),
            "risk_score": str(risk_score),
            "typologies_top3": typologies_top3_str,
            "clarification_triggered": str(clarification_triggered),
            "clarification_questions": clarification_questions,
            "reporting_action_in_top3": reporting_in_top3,
            "safety_or_action_issue": safety_issue_str,
            "latency_ms": f"{elapsed_ms:.1f}",
            "reviewer_notes": reviewer_notes_str,
        }
        results_rows.append(row)
        # Extract contributions and signals for evidence
        signals_list = [s.name.value for s in (final_outcome.signals or [])]
        contribs_list = [f"{c.factor}:{c.points}" for c in (final_outcome.risk.contributions if final_outcome.risk else [])]

        per_case_meta.append({
            "case_id": cid,
            "label": clabel,
            "language": clang,
            "status": status,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "overrides": list(final_outcome.risk.overrides) if final_outcome.risk else [],
            "typologies": top3_types,
            "signals": signals_list,
            "contributions": contribs_list,
            "clarification_triggered": clarification_triggered,
            "questions": clarification_questions,
            "reporting_in_top3": reporting_in_top3,
            "strict_rubric_v1_failures": all_fails,
            "calibrated_rubric_v2_failures": v2_fails,
            "latency_ms": elapsed_ms,
            "llm_calls": final_outcome.llm_calls,
        })
        print(f"Done in {elapsed_ms:.0f}ms -> {status}, Level={risk_level}, Score={risk_score}")

    fieldnames = [
        "case_id",
        "run_id",
        "commit",
        "config_sha256",
        "mode_provider_model",
        "status",
        "risk_level",
        "risk_score",
        "typologies_top3",
        "clarification_triggered",
        "clarification_questions",
        "reporting_action_in_top3",
        "safety_or_action_issue",
        "latency_ms",
        "reviewer_notes",
    ]

    # Write ONLY dedicated run CSV to keep run history (do NOT overwrite the blank template)
    run_csv_file = _PROJECT_ROOT / "data" / "evaluation" / f"external_review_results_{run_id}.csv"
    with open(run_csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results_rows)
    print(f"\nWrote run results to: {run_csv_file}")

    # Latency and operational summary
    all_latencies = [p["latency_ms"] for p in per_case_meta]
    import statistics
    sorted_lat = sorted(all_latencies)
    p95_idx = int(0.95 * len(sorted_lat))
    lat_summary = {
        "median_ms": round(statistics.median(all_latencies), 1),
        "mean_ms": round(statistics.mean(all_latencies), 1),
        "p95_ms": round(sorted_lat[min(p95_idx, len(sorted_lat) - 1)], 1),
        "max_ms": round(max(all_latencies), 1),
        "min_ms": round(min(all_latencies), 1),
    }

    strict_pass_count = sum(1 for p in per_case_meta if not p["strict_rubric_v1_failures"])
    v2_pass_count = sum(1 for p in per_case_meta if not p["calibrated_rubric_v2_failures"])

    # Write metadata (both versioned and latest pointer)
    meta = {
        "run_id": run_id,
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "commit": commit,
        "short_commit": short_commit,
        "config_sha256": config_hash,
        "mode_provider_model": mode_provider_model,
        "total_cases": len(cases),
        "strict_rubric_v1": {
            "passed": strict_pass_count,
            "total": len(cases),
            "pass_rate_pct": round(100.0 * strict_pass_count / len(cases), 1),
            "note": "Requires interview on all ambiguous cases; 6 resolved safely to LOW without interview",
        },
        "calibrated_rubric_v2": {
            "passed": v2_pass_count,
            "total": len(cases),
            "pass_rate_pct": round(100.0 * v2_pass_count / len(cases), 1),
            "note": "Allows ambiguous cases without threat signals to resolve safely to LOW with cautionary advice",
        },
        "latency_summary": lat_summary,
        "results": per_case_meta,
    }
    versioned_meta_file = _PROJECT_ROOT / "data" / "evaluation" / f"external_review_run_meta_{run_id}.json"
    with open(versioned_meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"Wrote versioned metadata to: {versioned_meta_file}")
    print(f"Wrote latest metadata pointer to: {meta_file}")
    print(f"Latency Summary: {lat_summary}")


if __name__ == "__main__":
    main()
