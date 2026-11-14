"""A9 Guardrail and Privacy Agent (FR-060 to FR-065, NFR-019; docs/05, docs/08).

Final safety gate before output is returned to users or clients:
1. PII Leakage Check: ensures no unmasked raw phone numbers, emails, UPI IDs,
   accounts, or IDs leak into headlines, reasons, actions, or questions.
2. Banned Claims: ensures no absolute or definitive claims ('100% safe', 'definitely a scam').
3. Legal Sections (FR-083): ensures no law section numbers, charges, or penal words appear.
4. Credential Requests (FR-064): ensures user is never asked for OTP, PIN, password, or CVV.
5. Verified Contacts (FR-050, NFR-019): ensures all contact numbers and URLs in advice match
   verified registry entries.
6. Consistency: ensures headline risk level matches scorer level and reasons cite valid evidence IDs.
7. Disclaimer (FR-065): standard advisory notice is attached.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from scamsaathi.agents.context import AgentContext
from scamsaathi.schemas import Action, AdviceBundle, Explanation, Reason
from scamsaathi.tools import rule_signals
from scamsaathi.tools.pii_masker import DESIGNATED_SERIES, _PATTERNS

if TYPE_CHECKING:
    from scamsaathi.pipeline.agentic import AssessmentOutcome

STANDARD_DISCLAIMER: Final = (
    "ScamSaathi provides risk assessments for guidance only. It is not a legal or definitive "
    "determination. Always verify independently through official channels."
)

_BANNED_CLAIMS: Final = re.compile(
    r"100\s?% (?:safe|scam)|definitely (?:a )?(?:scam|safe|fraud)|completely safe|"
    r"guaranteed|no risk at all|certainly (?:a )?scam",
    re.I,
)

# FR-083: no legal sections, penal charges, or punishments in user-facing text.
_LEGAL_SECTIONS: Final = re.compile(
    r"\b(?:section\s+\d+|sec\.\s*\d+|u/s\s*\d+|s\.\s*\d+|bns\s+\d+|bnss\s+\d+|ipc\s+\d+|"
    r"it act\s+\d+|pocso\s+\d+|imprisonment|jail|punishable)\b",
    re.I,
)

# FR-064: never instruct user to provide secrets (e.g. "enter your OTP", "share your PIN")
_SECRET_DEMAND: Final = re.compile(
    r"\b(?:enter|provide|type|submit|tell us|give us|share with us)\s+(?:your\s+)?"
    r"(?:otp|o\.t\.p|pin|password|cvv|passcode|card number)\b",
    re.I,
)

_LEVEL_MENTION: Final = re.compile(
    r"\b(very high|extremely high|critical|high|medium|moderate|low)[\s-]*risk\b", re.I
)
_LEVEL_OF: Final = {
    "very high": "CRITICAL",
    "extremely high": "CRITICAL",
    "critical": "CRITICAL",
    "high": "HIGH",
    "medium": "MEDIUM",
    "moderate": "MEDIUM",
    "low": "LOW",
}

_URL_RE: Final = re.compile(r"https?://[^\s<>\"']+", re.I)
_PHONE_TOKEN_RE: Final = re.compile(r"(?:\+91[\s-]?)?[6-9]\d{9}\b")


@dataclass(frozen=True)
class GuardrailViolation:
    code: str
    message: str
    field: str


@dataclass(frozen=True)
class GuardrailResult:
    passed: bool
    violations: list[GuardrailViolation] = field(default_factory=list)
    disclaimer: str = STANDARD_DISCLAIMER


class GuardrailAgent:
    """Evaluates an outcome against the safety and privacy checklist."""

    def __init__(self, ctx: AgentContext):
        self.ctx = ctx
        self._verified_urls: set[str] = {
            c.value.lower().rstrip("/")
            for c in ctx.kb.contacts.values()
            if c.channel == "url"
        }
        self._official_domains: set[str] = {
            od.domain.lower() for od in ctx.db.official
        }
        self._verified_phones: set[str] = {
            re.sub(r"\D", "", c.value)[-10:]
            for c in ctx.kb.contacts.values()
            if c.channel in ("phone", "sms") and len(re.sub(r"\D", "", c.value)) >= 3
        }
        # Add shortcodes (1930, 112, 1909)
        self._verified_phones.update({"1930", "112", "1909"})

    def check_pii(self, text: str, field_name: str) -> list[GuardrailViolation]:
        """Check whether unmasked PII patterns leak into text."""
        violations: list[GuardrailViolation] = []
        cleaned = re.sub(r"<(?:PHONE|EMAIL|UPI|ACCT|ID|URL)_\d+>", "", text)
        cleaned = DESIGNATED_SERIES.sub("", cleaned)
        for kind, pattern, validator in _PATTERNS:
            for match in pattern.finditer(cleaned):
                val = match.group()
                if validator is None or validator(val):
                    violations.append(
                        GuardrailViolation(
                            "PII_LEAK",
                            f"Unmasked {kind} pattern found in {field_name}",
                            field_name,
                        )
                    )
                    break
        return violations

    def check_banned_and_legal(self, text: str, field_name: str) -> list[GuardrailViolation]:
        violations: list[GuardrailViolation] = []
        if _BANNED_CLAIMS.search(text):
            violations.append(
                GuardrailViolation("BANNED_CLAIM", f"Absolute/guaranteed claim found in {field_name}", field_name)
            )
        if _LEGAL_SECTIONS.search(text):
            violations.append(
                GuardrailViolation("LEGAL_SECTION", f"Legal section or penal word found in {field_name}", field_name)
            )
        return violations

    def check_secret_request(self, text: str, field_name: str) -> list[GuardrailViolation]:
        violations: list[GuardrailViolation] = []
        if _SECRET_DEMAND.search(text):
            violations.append(
                GuardrailViolation("CREDENTIAL_REQUEST", f"Instruction asking for user secrets in {field_name}", field_name)
            )
        return violations

    def check_contacts(self, text: str, field_name: str) -> list[GuardrailViolation]:
        violations: list[GuardrailViolation] = []
        for url in _URL_RE.findall(text):
            norm = url.lower().rstrip("/")
            # Check against verified contacts or official domains
            matched = any(norm.startswith(v) for v in self._verified_urls)
            if not matched:
                # Also check if domain is in official domains
                host = norm.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]
                matched = any(
                    host == dom or host.endswith("." + dom)
                    for dom in self._official_domains
                )
            if not matched:
                violations.append(
                    GuardrailViolation("UNVERIFIED_URL", f"Unverified URL '{url}' in {field_name}", field_name)
                )
        for phone in _PHONE_TOKEN_RE.findall(text):
            if DESIGNATED_SERIES.search(phone):
                continue
            digits = re.sub(r"\D", "", phone)[-10:]
            if digits not in self._verified_phones:
                violations.append(
                    GuardrailViolation("UNVERIFIED_PHONE", f"Unverified phone '{phone}' in {field_name}", field_name)
                )
        return violations

    def verify(self, outcome: AssessmentOutcome) -> GuardrailResult:
        violations: list[GuardrailViolation] = []

        # 1. Check questions if in followup state
        for i, q in enumerate(outcome.questions, 1):
            q_text = q.get("text", "")
            f_name = f"question[{i}]"
            violations.extend(self.check_pii(q_text, f_name))
            violations.extend(self.check_banned_and_legal(q_text, f_name))
            violations.extend(self.check_secret_request(q_text, f_name))

        # 2. Check explanation and advice if complete
        if outcome.status == "complete":
            if outcome.explanation is not None:
                headline = outcome.explanation.headline
                violations.extend(self.check_pii(headline, "headline"))
                violations.extend(self.check_banned_and_legal(headline, "headline"))
                violations.extend(self.check_secret_request(headline, "headline"))

                # Consistency of risk level in headline
                if outcome.risk is not None:
                    mentioned = _LEVEL_MENTION.findall(headline)
                    for m in mentioned:
                        if _LEVEL_OF.get(m.lower()) != outcome.risk.level:
                            violations.append(
                                GuardrailViolation(
                                    "RISK_LEVEL_MISMATCH",
                                    f"Headline stated '{m}' but scorer level is '{outcome.risk.level}'",
                                    "headline",
                                )
                            )

                for j, r in enumerate(outcome.explanation.reasons, 1):
                    f_name = f"reason[{j}]"
                    violations.extend(self.check_pii(r.text, f_name))
                    violations.extend(self.check_banned_and_legal(r.text, f_name))
                    if not r.evidence_ids:
                        violations.append(
                            GuardrailViolation("NO_EVIDENCE_ID", f"Reason {j} cites no evidence IDs", f_name)
                        )

                violations.extend(self.check_pii(outcome.explanation.uncertainty, "uncertainty"))
                violations.extend(self.check_banned_and_legal(outcome.explanation.uncertainty, "uncertainty"))

            if outcome.advice is not None:
                for k, a in enumerate(outcome.advice.actions, 1):
                    f_name = f"action[{k}]"
                    violations.extend(self.check_pii(a.text, f_name))
                    violations.extend(self.check_banned_and_legal(a.text, f_name))
                    violations.extend(self.check_secret_request(a.text, f_name))
                    violations.extend(self.check_contacts(a.text, f_name))

                for m, c in enumerate(outcome.advice.contacts, 1):
                    f_name = f"contact[{m}]"
                    if c.channel == "url":
                        violations.extend(self.check_contacts(c.value, f_name))

        return GuardrailResult(passed=len(violations) == 0, violations=violations)

    def sanitize(self, outcome: AssessmentOutcome) -> AssessmentOutcome:
        """If guardrail fails, sanitize outcome with deterministic safe templates."""
        result = self.verify(outcome)
        if result.passed:
            return outcome

        error_notes = [f"guardrail: {v.code} in {v.field}: {v.message}" for v in result.violations]
        all_errors = [*outcome.errors, *error_notes]

        from scamsaathi.pipeline.agentic import AssessmentOutcome

        if outcome.status == "needs_followup":
            # Sanitize question texts that failed
            safe_questions: list[dict[str, str]] = []
            for q in outcome.questions:
                q_text = q.get("text", "")
                if self.check_pii(q_text, "q") or self.check_banned_and_legal(q_text, "q") or self.check_secret_request(q_text, "q"):
                    continue
                safe_questions.append(q)
            if not safe_questions:
                safe_questions = [{"id": "Q1", "text": "Did you transfer any money or provide sensitive details?"}]
            return AssessmentOutcome(
                thread_id=outcome.thread_id,
                status="needs_followup",
                questions=safe_questions,
                signals=outcome.signals,
                intel=outcome.intel,
                language=outcome.language,
                input_mode=outcome.input_mode,
                llm_calls=outcome.llm_calls,
                degraded=True,
                errors=all_errors,
                masked_text=outcome.masked_text,
            )

        # For complete outcomes, rebuild safe deterministic explanation & advice
        from scamsaathi.agents.explain_advise import evidence_catalogue, template_explanation
        from scamsaathi.kb.advice import build_advice
        from scamsaathi.tools.risk_scorer import Situation

        risk = outcome.risk
        assert risk is not None
        names = [self.ctx.kb.typologies[c].name for c in outcome.typologies if c in self.ctx.kb.typologies]
        state_dummy = {
            "signals": [s.model_dump() for s in outcome.signals],
            "intel": outcome.intel.model_dump() if outcome.intel else {},
            "kb_chunk_ids": [],
            "masked_text": outcome.masked_text,
        }
        catalogue = evidence_catalogue(state_dummy, self.ctx, risk)  # type: ignore[arg-type]
        safe_explanation = template_explanation(risk, catalogue, "en", names)
        is_telemarketing = bool(re.search(r"(?:\+91[ -]?)?140[ -]?(?:\d[ -]?){7}", outcome.masked_text))
        safe_advice = build_advice(
            self.ctx.kb, risk.level, outcome.typologies, Situation(), telemarketing_number=is_telemarketing
        )
        source = "template" if outcome.explanation_source == "template" else "template_sanitized"

        return AssessmentOutcome(
            thread_id=outcome.thread_id,
            status="complete",
            questions=[],
            risk=risk,
            explanation=safe_explanation,
            advice=safe_advice,
            typologies=outcome.typologies,
            signals=outcome.signals,
            intel=outcome.intel,
            language="en",
            input_mode=outcome.input_mode,
            explanation_source=source,
            llm_calls=outcome.llm_calls,
            degraded=True,
            errors=all_errors,
            masked_text=outcome.masked_text,
        )
