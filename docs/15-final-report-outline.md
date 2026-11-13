# 15. Final Report and Presentation Outline

| Field | Value |
|---|---|
| Version | 0.1 (Outline; filled in during P9) |
| Date | 2026-11-11 |

Adjust to the certification's required template once known (Q-1, Q-2).

## 1. Final report structure

| Section | Content | Source documents |
|---|---|---|
| 1. Executive summary | Problem, solution, results, key learnings (one page) | 01, 09 |
| 2. Problem and motivation | Scam landscape with cited, dated statistics | 02 |
| 3. Objectives and scope | Goals, in/out of scope | 01 |
| 4. Requirements | Summary and traceability | 03 |
| 5. Architecture | Context, agent topology, state, sequences | 04 |
| 6. Agent and tool design | Roles, prompts, tools, schemas | 05, 06 |
| 7. Data and knowledge base | Typologies, dataset construction | 07 |
| 8. Agentic design choices | Why multi-agent, LangGraph, tiering, hybrid scoring | ADR-001 to 007 |
| 9. Security, privacy, responsible AI | Threat model, guardrails, limitations | 08 |
| 10. Implementation | Phases, challenges, solutions, code highlights | 13 |
| 11. Evaluation | Metrics, baselines, ablations, error analysis, cost | 09 |
| 12. Limitations and risks | Honest discussion | 12 |
| 13. Future work | Voice, image, more languages, feedback learning, real integrations | 01 |
| 14. Conclusion | Outcomes against objectives | 01 |
| Appendices | Prompts, config, dataset schema, demo script, spend | 13, 14 |

## 2. Presentation outline (about 15 slides)

1. Title and one-line value proposition
2. The problem (real scenarios)
3. Who it helps (personas)
4. Solution overview (user flow)
5. Why agentic (single prompt vs agents)
6. Architecture diagram
7. Agent roster and tools
8. Hybrid scoring and explainability
9. RAG and threat intelligence
10. Interview agent (human in the loop)
11. Guardrails, privacy, responsible AI
12. Live demo (or recorded)
13. Evaluation results vs baselines, per-language slices
14. Cost, latency, lessons learned
15. Limitations, future work, Q&A

## 3. Evidence checklist for evaluators

| Evidence | Where |
|---|---|
| Working demo (live, cached, offline) | Demo guide |
| Multi-agent graph diagram exported from code | `docs/assets/graph.mmd` (to generate) |
| Traces for sample runs | `reports/traces/` (to generate) |
| Test results and coverage | `reports/tests/` |
| Evaluation report with ablations | `reports/eval-YYYYMMDD/` |
| Decision records | `docs/11-adr/` |
| Risk log and issues with resolutions | `docs/12-risk-issues-log.md` |
| Spend summary | `docs/13-implementation-log.md` Appendix C |

## 4. Likely evaluator questions and prepared answers (to complete)

| Question | Prepared point |
|---|---|
| Why is this agentic and not a prompt? | Multiple specialised nodes, tools, conditional routing, loops, human-in-the-loop, guardrails; ablation B1 vs Full |
| Why LangGraph? | ADR-002 comparison and spike results |
| How do you prevent hallucination? | Evidence IDs, curated contacts, deterministic scorer, guardrail |
| How do you handle privacy? | Masking, no raw persistence, synthetic data, ADR-007 |
| How accurate is it? | Actual numbers, per slice, with limitations |
| What does it cost? | Spend tracker and cost per request |
| What would you do next? | Future work list |
