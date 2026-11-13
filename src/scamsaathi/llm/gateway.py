"""LLM gateway (tasks 1.6 to 1.8; FR-072 to FR-076, NFR-005, NFR-006).

The only path from agents to an external model. It guarantees, in order:
1. no PII in the prompt (refuses otherwise),
2. cache lookup by hashed masked prompt,
3. mode rules (``cached``/``offline`` never call a provider),
4. per-request and daily call budgets,
5. retries with backoff, then the configured fallback chain,
6. schema-validated output with one repair attempt,
7. telemetry without prompt text.
"""

from __future__ import annotations

import json
import logging
import random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from scamsaathi.config import LLMConfig, Mode, Settings, load_llm_config
from scamsaathi.llm.cache import DailyBudget, DiskCache, cache_key
from scamsaathi.llm.errors import (
    BudgetExceeded,
    CacheMiss,
    ModelNotConfigured,
    PermanentProviderError,
    PIIDetectedInPrompt,
    ProviderUnavailable,
    SchemaViolation,
    TransientProviderError,
)
from scamsaathi.llm.providers import GeminiProvider, Provider, ProviderResponse
from scamsaathi.tools.pii_masker import contains_pii

logger = logging.getLogger("scamsaathi.llm")

T = TypeVar("T", bound=BaseModel)

_REPAIR_SUFFIX = (
    "\n\nYour previous reply was not valid JSON for the required schema. "
    "Reply again with only a JSON object that matches the schema. Validation error: {error}"
)


@dataclass
class RequestBudget:
    """Per-request LLM call cap (FR-076). Create one per user request."""

    max_calls: int
    calls: int = 0

    def consume(self) -> None:
        if self.calls >= self.max_calls:
            raise BudgetExceeded(f"per-request cap of {self.max_calls} LLM calls reached")
        self.calls += 1

    @property
    def remaining(self) -> int:
        return self.max_calls - self.calls


@dataclass(frozen=True)
class LLMResult(Generic[T]):
    output: T
    cache_hit: bool
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    est_cost_inr: float = 0.0


def _strip_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else ""
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3]
    return stripped.strip()


class LLMGateway:
    def __init__(
        self,
        *,
        config: LLMConfig,
        mode: Mode,
        providers: Mapping[str, Provider],
        cache: DiskCache,
        daily_budget: DailyBudget,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._config = config
        self._mode = mode
        self._providers = dict(providers)
        self._cache = cache
        self._daily = daily_budget
        self._sleep = sleep
        self._clock = clock

    @property
    def mode(self) -> Mode:
        return self._mode

    def generate(
        self,
        *,
        task: str,
        tier: str,
        system: str,
        user: str,
        schema: type[T],
        budget: RequestBudget,
        prompt_version: str = "v1",
    ) -> LLMResult[T]:
        tier_cfg = self._config.tiers.get(tier)
        if tier_cfg is None:
            raise ValueError(f"unknown tier {tier!r}")

        if contains_pii(system) or contains_pii(user):
            logger.warning("llm_prompt_rejected_pii", extra={"task": task, "tier": tier})
            raise PIIDetectedInPrompt(f"prompt for task {task!r} contains unmasked PII")

        json_schema = schema.model_json_schema()
        key = cache_key(
            tier=tier,
            model=tier_cfg.model,
            task=task,
            prompt_version=prompt_version,
            system=system,
            user=user,
            schema=json.dumps(json_schema, sort_keys=True),
        )

        cached = self._from_cache(key, schema, tier_cfg.provider, tier_cfg.model)
        if cached is not None:
            self._log(task, tier, cached, attempts=0)
            return cached

        if self._mode is not Mode.LIVE:
            raise CacheMiss(f"no cached response for task {task!r} in {self._mode.value} mode")
        if not tier_cfg.is_configured:
            raise ModelNotConfigured(f"model for tier {tier!r} is not set (see Q-3)")

        budget.consume()
        started = self._clock()
        chain = [(tier_cfg.provider, tier_cfg.model)] + [
            (fb.provider, fb.model) for fb in self._config.fallbacks.get(tier, [])
        ]
        provider_name, model, response, attempts = self._call_chain(
            chain, system, user, json_schema, tier_cfg.temperature, tier_cfg.timeout_s
        )

        output, error = self._validate(response.text, schema)
        in_tokens, out_tokens = response.input_tokens, response.output_tokens
        if output is None:
            budget.consume()
            repair_user = user + _REPAIR_SUFFIX.format(error=error)
            provider_name, model, response, extra = self._call_chain(
                [(provider_name, model)],
                system,
                repair_user,
                json_schema,
                tier_cfg.temperature,
                tier_cfg.timeout_s,
            )
            attempts += extra
            in_tokens += response.input_tokens
            out_tokens += response.output_tokens
            output, error = self._validate(response.text, schema)
            if output is None:
                raise SchemaViolation(f"task {task!r}: output invalid after repair ({error})")

        self._cache.put(
            key,
            {
                "text": response.text,
                "provider": provider_name,
                "model": model,
                "created_at": datetime.now(UTC).isoformat(),
            },
        )
        result = LLMResult(
            output=output,
            cache_hit=False,
            provider=provider_name,
            model=model,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            latency_ms=int((self._clock() - started) * 1000),
            est_cost_inr=self._estimate_cost(in_tokens, out_tokens),
        )
        self._log(task, tier, result, attempts=attempts)
        return result

    # -- internals -----------------------------------------------------------

    def _from_cache(
        self, key: str, schema: type[T], provider: str, model: str
    ) -> LLMResult[T] | None:
        record = self._cache.get(key)
        if record is None or not isinstance(record.get("text"), str):
            return None
        output, _ = self._validate(record["text"], schema)
        if output is None:
            return None
        return LLMResult(
            output=output,
            cache_hit=True,
            provider=str(record.get("provider", provider)),
            model=str(record.get("model", model)),
        )

    @staticmethod
    def _validate(text: str, schema: type[T]) -> tuple[T | None, str]:
        try:
            return schema.model_validate_json(_strip_fences(text)), ""
        except ValidationError as exc:
            # Report only error locations and types, never the offending values.
            summary = "; ".join(
                f"{'.'.join(str(p) for p in err['loc']) or '<root>'}: {err['type']}"
                for err in exc.errors()[:5]
            )
            return None, summary

    def _call_chain(
        self,
        chain: list[tuple[str, str]],
        system: str,
        user: str,
        json_schema: dict[str, object],
        temperature: float,
        timeout_s: float,
    ) -> tuple[str, str, ProviderResponse, int]:
        attempts = 0
        for provider_name, model in chain:
            provider = self._providers.get(provider_name)
            if provider is None:
                logger.warning("llm_provider_missing", extra={"provider": provider_name})
                continue
            retry = self._config.retry
            for attempt in range(retry.max_attempts):
                self._daily.consume()
                attempts += 1
                try:
                    response = provider.generate(
                        model=model,
                        system=system,
                        user=user,
                        json_schema=dict(json_schema),
                        temperature=temperature,
                        timeout_s=timeout_s,
                    )
                    return provider_name, model, response, attempts
                except PermanentProviderError as exc:
                    logger.warning(
                        "llm_provider_permanent_error",
                        extra={"provider": provider_name, "error": str(exc)},
                    )
                    break
                except TransientProviderError as exc:
                    logger.warning(
                        "llm_provider_transient_error",
                        extra={"provider": provider_name, "error": str(exc), "attempt": attempt},
                    )
                    if attempt + 1 < retry.max_attempts:
                        delay = min(retry.max_delay_s, retry.base_delay_s * (2**attempt))
                        # Jitter for backoff only; not security-sensitive.
                        self._sleep(delay * random.uniform(0.5, 1.0))  # noqa: S311
        raise ProviderUnavailable("all providers failed")

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        cost = self._config.cost_per_million_tokens_inr
        return round((input_tokens * cost.input + output_tokens * cost.output) / 1_000_000, 6)

    @staticmethod
    def _log(task: str, tier: str, result: LLMResult[T], *, attempts: int) -> None:
        logger.info(
            "llm_call",
            extra={
                "task": task,
                "tier": tier,
                "provider": result.provider,
                "llm_model": result.model,
                "cache_hit": result.cache_hit,
                "attempts": attempts,
                "latency_ms": result.latency_ms,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "est_cost_inr": result.est_cost_inr,
            },
        )


def build_gateway(settings: Settings) -> LLMGateway:
    """Construct the gateway from settings. Gemini is registered only when a key is set."""
    providers: dict[str, Provider] = {}
    if settings.gemini_api_key is not None and settings.mode is Mode.LIVE:
        providers["gemini"] = GeminiProvider(settings.gemini_api_key)
    return LLMGateway(
        config=load_llm_config(settings),
        mode=settings.mode,
        providers=providers,
        cache=DiskCache(settings.llm_cache_dir),
        daily_budget=DailyBudget(settings.llm_cache_dir, settings.daily_call_budget),
    )
