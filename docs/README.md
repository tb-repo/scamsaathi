# ScamSaathi Documentation Index

| Field | Value |
|---|---|
| Document set version | 0.1 |
| Last updated | 2026-11-11 |
| Owner | Thiagarajan Baskarasubramanian (project lead / author) |
| Status | Draft for review |

## How to use this set

Documents are numbered in reading order. Requirements (03) drive design (04 to 07), which drive tests (09). Decisions are in `11-adr/`. Living documents (12, 13, CHANGELOG) are updated throughout implementation.

| # | Document | Purpose | Type |
|---|---|---|---|
| 01 | [Project Charter](01-project-charter.md) | Vision, scope, success criteria, stakeholders, assumptions | Stable |
| 02 | [Business Case and Problem Statement](02-business-case-problem-statement.md) | Why this project, users, personas, scam landscape | Stable |
| 03 | [Requirements](03-requirements.md) | Functional and non-functional requirements, traceability | Stable |
| 04 | [Architecture](04-architecture.md) | Context, agent topology, state, data flow, deployment | Stable |
| 05 | [Agent Specifications](05-agent-specifications.md) | Role, I/O, prompts, tools, failure modes per agent | Stable |
| 06 | [Tool Specifications](06-tool-specifications.md) | Tool contracts and API schemas | Stable |
| 07 | [Data and Knowledge Base Design](07-data-knowledge-base-design.md) | Scam typologies, KB, blocklists, datasets | Stable |
| 08 | [Security, Privacy and Responsible AI](08-security-privacy-responsible-ai.md) | Threat model, guardrails, PII, ethics | Stable |
| 09 | [Test and Evaluation Strategy](09-test-evaluation-strategy.md) | Test levels, metrics, datasets, acceptance | Stable |
| 10 | [Project Plan](10-project-plan.md) | Milestones, WBS, RACI, schedule | Living |
| 11 | [Architecture Decision Records](11-adr/README.md) | Decisions and alternatives | Append-only |
| 12 | [Risk, Issues and Challenges Log](12-risk-issues-log.md) | Risks, issues, assumptions, open questions | Living |
| 13 | [Implementation Log](13-implementation-log.md) | Chronological build journal | Living |
| 14 | [User, Deployment and Demo Guide](14-user-deployment-demo-guide.md) | Setup, run, demo script | Living |
| 15 | [Final Report and Presentation Outline](15-final-report-outline.md) | Certification submission structure | Living |
| 16 | [Legal and Regulatory Reference](16-legal-regulatory-reference.md) | Indian laws, TRAI/DoT/I4C/MeitY rules, and how they shape the app | Living |
| - | [CHANGELOG](../CHANGELOG.md) | Versioned change history | Living |

## Conventions

- **Requirement IDs:** `FR-xxx` functional, `NFR-xxx` non-functional, `CON-xxx` constraint.
- **Decision IDs:** `ADR-xxx`. Superseded decisions are marked, never deleted.
- **Risk IDs:** `R-xxx`. **Issue IDs:** `I-xxx`. **Assumption IDs:** `A-xxx`. **Open question IDs:** `Q-xxx`.
- **TBD** means a value that must be confirmed. Nothing marked TBD should be treated as fact.
- Diagrams use Mermaid and render in Kiro and GitHub.
- Dates use ISO format (YYYY-MM-DD).

## Document status legend

Draft, In review, Approved, Superseded. All documents in this set are currently **Draft** until the author approves them.
