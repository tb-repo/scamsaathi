"""Deterministic advice selection (A8 core; FR-050 to FR-052, FR-083).

Picks curated actions and verified contacts by risk level, typology, and situation. The LLM
(Phase 4) may reword these for language and tone but cannot add actions or contacts.

Order of precedence:
1. Child-safety path (minor + sexual content): replaces all other advice.
2. Urgent recovery (money sent or secrets shared): 1930 first, then police-reporting steps.
3. Level advice, then reporting (suspected fraud), then typology advice.
Evidence steps are added for HIGH/CRITICAL and urgent cases.
"""

from __future__ import annotations

from collections.abc import Sequence

from scamsaathi.kb.store import KnowledgeBase
from scamsaathi.schemas import Action, AdviceBundle, RiskLevel
from scamsaathi.tools.risk_scorer import Situation

MAX_TYPOLOGIES = 2


def build_advice(
    kb: KnowledgeBase,
    level: RiskLevel,
    typology_codes: Sequence[str],
    situation: Situation | None = None,
    telemarketing_number: bool = False,
) -> AdviceBundle:
    """``telemarketing_number``: a TRAI 140-series number or a promotional (-P) sender header
    appeared, so the spam (UCC) route applies (FR-085)."""
    situation = situation or Situation()
    templates = kb.advice

    if situation.child_involved:
        actions = [Action(priority=i, text=t) for i, t in enumerate(templates.child_safety, 1)]
        contacts = [kb.contacts[c].to_official() for c in templates.contacts_by_situation["child_safety"]]
        return AdviceBundle(actions=actions, contacts=contacts, urgent_recovery_mode=True)

    urgent = situation.money_sent or situation.credentials_shared
    codes = list(dict.fromkeys(typology_codes))[:MAX_TYPOLOGIES]
    suspected = not urgent and level in ("MEDIUM", "HIGH", "CRITICAL")

    texts: list[str] = list(templates.urgent_recovery) if urgent else list(templates.by_level[level])
    if suspected:
        # Reporting comes straight after "stop contact": it protects other people too.
        texts.extend(templates.report_suspected)
    if level != "LOW" or urgent:
        for code in codes:
            texts.extend(templates.by_typology.get(code, []))
    if situation.app_installed and not urgent:
        texts.extend(templates.by_typology.get("SC-11", [])[1:])
    if urgent or level in ("HIGH", "CRITICAL"):
        texts.extend(templates.evidence)
    if urgent:
        texts.extend(templates.police_reporting)
    if telemarketing_number and not urgent:
        texts.extend(templates.spam)

    unique = list(dict.fromkeys(texts))
    actions = [Action(priority=i, text=t) for i, t in enumerate(unique, start=1)]

    contact_ids: list[str] = []
    if urgent:
        contact_ids += templates.contacts_by_situation["money_lost"]
    elif suspected:
        contact_ids += templates.contacts_by_situation["suspected"]
    if level != "LOW" or urgent:
        for code in codes:
            contact_ids += templates.contacts_by_typology.get(code, [])
    if telemarketing_number and not urgent:
        contact_ids += templates.contacts_by_situation["spam"]
    contacts = [kb.contacts[cid].to_official() for cid in dict.fromkeys(contact_ids)]

    return AdviceBundle(actions=actions, contacts=contacts, urgent_recovery_mode=urgent)
