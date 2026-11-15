# External Review Challenge Set

This is a separate, synthetic challenge set for an exploratory quality review. It contains **28 cases**: 13 scam, 8 legitimate, and 7 ambiguous. It is not part of the approved 50-case benchmark, does not replace the held-out evaluation set, and must not be used to tune and then report performance on the same cases.

## What it probes

- Scam detection across coercion, credential theft, UPI, job/task, loan, parcel, lottery, investment, utility, remote-access, and impersonation scenarios.
- Strong escalation signals versus warning-worthy but less conclusive content. IDs beginning `xr_severe_` are a **review slice** with strong signals or reported loss; they are not ground-truth risk levels.
- False alarms on ordinary banking, payroll, delivery, personal, school, OTP-context, and awareness messages.
- Clarification on incomplete messages and resistance to prompt-injection text embedded in a message.
- English, Hinglish, and Hindi examples.

All cases are synthetic. There are no real phone numbers, account identifiers, or live malicious links. The message text and the requested action are the evidence; a brand name, keyword, or score alone is not proof of fraud or legitimacy.

## Run and record

1. Freeze the app commit, scoring configuration, provider/model, and run mode before starting. Use a fresh session for every case; do not change weights or prompts during the run.
2. Start the app using the documented local command in `docs/14-user-deployment-demo-guide.md` and paste each case's `text` exactly as written.
3. Record the first-turn risk level and score, top typologies, whether clarification was requested, the safety/reporting guidance, and any unexpected behavior in `data/evaluation/external_review_results_template.csv`. For ambiguous cases, record the actual questions; if you test the resume path, record the answer and resumed result separately.
4. Do not enter real personal or financial data. Preserve outputs and error details, but redact API keys, tokens, session identifiers, and any accidentally entered personal data before sharing.

## How to interpret the run

- The case labels support outcome checks: scams should be warned about, legitimate messages should avoid false alarms, and ambiguous messages should prompt appropriate clarification.
- `xr_severe_` is useful for a **separate descriptive HIGH/CRITICAL escalation slice**. Report its numerator and denominator, plus individual misses. The IDs do not establish that a particular numerical level is objectively correct.
- Review score severity and explanation against the actual evidence. Do not infer safety from LOW, infer certainty from MEDIUM/HIGH, or treat this small curated set as a population estimate.
- Report all cases, including misses and false alarms. Do not merge these results into the approved benchmark or update headline figures until the run is reviewed and the evaluation protocol/dataset split is formally revised.

## Important runner limitation

Do **not** pass this file to the current `scripts/run_benchmarks.py` for an exploratory run. Although it accepts `--dataset`, it always writes to `reports/benchmark_report.md` and `reports/benchmark_run_meta.json`; its report narrative also contains figures and commentary specific to the existing 50-case run. That could overwrite the project benchmark artifacts and create misleading output. Use the UI protocol above, or first add an isolated runner that writes to a dedicated external-review output directory.

When you share results for external review, include the completed CSV, app commit, config hash, mode/provider/model, run date, and any concise screenshots or sanitized per-case outputs. I can then check case-by-case correctness, severity calibration, explanation quality, false alarms, clarification behavior, safety guidance, and the validity of any summary metrics before you decide whether to revise the formal evaluation.
