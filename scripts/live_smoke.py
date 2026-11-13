"""Live smoke test for the Gemini gateway (task 1.10; ADR-001, ADR-008).

Usage (from the project root, with GEMINI_API_KEY set in .env):
    $env:PYTHONPATH="src"; .venv\\Scripts\\python.exe scripts\\live_smoke.py

What it does (about 4 paid calls, a fraction of a rupee):
1. Lists the models visible to the key and checks the configured IDs exist (ADR-008).
2. One gateway call per tier with a synthetic, already-masked prompt and a strict schema.
3. Repeats the fast-tier call to confirm the disk cache answers without a provider call.
4. Calls the reasoning-tier fallback model once, directly, so a broken fallback is caught now.

Output never includes the API key or prompt text; provider errors show the HTTP status only.
"""

from __future__ import annotations

import sys
from typing import Literal

from pydantic import BaseModel, Field

from scamsaathi.config import Mode, get_settings, load_llm_config
from scamsaathi.llm.errors import LLMGatewayError as LLMError
from scamsaathi.llm.gateway import RequestBudget, build_gateway

EMBEDDING_MODEL = "gemini-embedding-001"  # ADR-004 (revised)

SYSTEM = (
    "You are a scam-risk triage assistant for India. Placeholders such as <PHONE_1> stand "
    "for masked personal data. Reply with JSON only."
)
# Synthetic, already-masked message (no real PII; the gateway refuses unmasked prompts).
USER = (
    "Classify this SMS. Message: 'Dear customer, your SBI account will be blocked today. "
    "Update KYC now at http://sbi-kyc-update.example/verify or call <PHONE_1>.'"
)


class SmokeAnswer(BaseModel):
    risk_hint: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    reasons: list[str] = Field(min_length=1, max_length=3)


def _check_models(client: object, wanted: list[str]) -> bool:
    available = {m.name.removeprefix("models/") for m in client.models.list()}  # type: ignore[attr-defined]
    ok = True
    for model in wanted:
        present = model in available
        ok &= present
        print(f"  {'OK ' if present else 'MISSING'} {model}")
    return ok


def main() -> int:
    settings = get_settings()
    if settings.gemini_api_key is None:
        print("GEMINI_API_KEY is not set in .env")
        return 2
    if settings.mode is not Mode.LIVE:
        print(f"SCAMSAATHI_MODE is {settings.mode.value}; set it to live for this check")
        return 2

    config = load_llm_config(settings)
    fallback = config.fallbacks.get("reasoning", [])
    wanted = [t.model for t in config.tiers.values()] + [f.model for f in fallback]
    wanted.append(EMBEDDING_MODEL)

    from google import genai
    from google.genai import errors

    client = genai.Client(api_key=settings.gemini_api_key.get_secret_value())
    print("1. Model availability (ADR-008)")
    try:
        models_ok = _check_models(client, wanted)
    except errors.APIError as exc:
        print(f"  model list failed: HTTP {exc.code}")
        return 1

    gateway = build_gateway(settings)
    failures = 0 if models_ok else 1

    print("2. Gateway call per tier")
    for tier in config.tiers:
        try:
            result = gateway.generate(
                task="live_smoke", tier=tier, system=SYSTEM, user=USER, schema=SmokeAnswer,
                budget=RequestBudget(max_calls=2), prompt_version="smoke-v1",
            )
        except LLMError as exc:
            print(f"  FAIL {tier}: {type(exc).__name__}: {exc}")
            failures += 1
            continue
        print(f"  OK   {tier:<9} model={result.model} cache_hit={result.cache_hit} "
              f"risk_hint={result.output.risk_hint} tokens={result.input_tokens}/"
              f"{result.output_tokens} latency_ms={result.latency_ms} "
              f"est_cost_inr={result.est_cost_inr}")

    print("3. Cache check (repeat fast tier)")
    try:
        again = gateway.generate(
            task="live_smoke", tier="fast", system=SYSTEM, user=USER, schema=SmokeAnswer,
            budget=RequestBudget(max_calls=1), prompt_version="smoke-v1",
        )
        print(f"  {'OK  ' if again.cache_hit else 'FAIL'} cache_hit={again.cache_hit}")
        failures += 0 if again.cache_hit else 1
    except LLMError as exc:
        print(f"  FAIL: {type(exc).__name__}: {exc}")
        failures += 1

    print("4. Reasoning fallback model, direct call")
    for fb in fallback:
        try:
            response = client.models.generate_content(
                model=fb.model, contents="Reply with the single word OK.",
            )
            print(f"  OK   {fb.model} replied ({len(response.text or '')} chars)")
        except errors.APIError as exc:
            print(f"  FAIL {fb.model}: HTTP {exc.code}")
            failures += 1

    print("PASSED" if failures == 0 else f"FAILED ({failures} problem(s))")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
