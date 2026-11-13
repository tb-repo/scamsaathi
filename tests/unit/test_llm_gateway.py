"""UT-LLM-01..08 (FR-072 to FR-076, NFR-005, NFR-006). Uses a fake provider; no network."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from scamsaathi.config import LLMConfig, Mode
from scamsaathi.llm import (
    BudgetExceeded,
    CacheMiss,
    LLMGateway,
    ModelNotConfigured,
    PIIDetectedInPrompt,
    ProviderUnavailable,
    RequestBudget,
    SchemaViolation,
)
from scamsaathi.llm.cache import DailyBudget, DiskCache
from scamsaathi.llm.errors import PermanentProviderError, TransientProviderError
from scamsaathi.llm.providers import ProviderResponse


class Verdict(BaseModel):
    label: str
    confidence: float


GOOD = '{"label": "scam", "confidence": 0.9}'


class FakeProvider:
    """Replays scripted outcomes: a JSON string, or an exception instance to raise."""

    def __init__(self, name: str, script: list[str | Exception]) -> None:
        self.name = name
        self._script = list(script)
        self.calls: list[dict[str, Any]] = []

    def generate(self, **kwargs: Any) -> ProviderResponse:
        self.calls.append(kwargs)
        outcome = self._script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return ProviderResponse(text=outcome, input_tokens=100, output_tokens=20)


def _config(model: str = "fake-model", fallbacks: bool = False) -> LLMConfig:
    data: dict[str, Any] = {
        "tiers": {"fast": {"provider": "primary", "model": model, "temperature": 0, "timeout_s": 5}},
        "retry": {"max_attempts": 3, "base_delay_s": 0.01, "max_delay_s": 0.02},
        "cost_per_million_tokens_inr": {"input": 10, "output": 40},
    }
    if fallbacks:
        data["fallbacks"] = {"fast": [{"provider": "backup", "model": "backup-model"}]}
    return LLMConfig.model_validate(data)


GatewayFactory = Callable[..., LLMGateway]


@pytest.fixture
def make_gateway(tmp_path: Path) -> GatewayFactory:
    def factory(
        providers: dict[str, FakeProvider],
        mode: Mode = Mode.LIVE,
        config: LLMConfig | None = None,
        daily_limit: int = 100,
    ) -> LLMGateway:
        return LLMGateway(
            config=config or _config(fallbacks="backup" in providers),
            mode=mode,
            providers=providers,
            cache=DiskCache(tmp_path / "cache"),
            daily_budget=DailyBudget(tmp_path / "cache", daily_limit, today=lambda: date(2026, 11, 11)),
            sleep=lambda _s: None,
        )

    return factory


def _call(gateway: LLMGateway, user: str = "Message: <PHONE_1> says KYC pending", budget: RequestBudget | None = None):  # type: ignore[no-untyped-def]
    return gateway.generate(
        task="classify",
        tier="fast",
        system="You classify messages.",
        user=user,
        schema=Verdict,
        budget=budget or RequestBudget(max_calls=4),
    )


def test_ut_llm_01_cache_miss_then_hit(make_gateway: GatewayFactory) -> None:
    provider = FakeProvider("primary", [GOOD])
    gateway = make_gateway({"primary": provider})
    first = _call(gateway)
    second = _call(gateway)
    assert first.output == Verdict(label="scam", confidence=0.9)
    assert not first.cache_hit and second.cache_hit
    assert len(provider.calls) == 1
    assert first.est_cost_inr == pytest.approx((100 * 10 + 20 * 40) / 1_000_000)


def test_ut_llm_02_retries_transient_errors(make_gateway: GatewayFactory) -> None:
    provider = FakeProvider("primary", [TransientProviderError("429"), TransientProviderError("503"), GOOD])
    result = _call(make_gateway({"primary": provider}))
    assert result.output.label == "scam"
    assert len(provider.calls) == 3


def test_ut_llm_03_falls_back_to_next_provider(make_gateway: GatewayFactory) -> None:
    primary = FakeProvider("primary", [PermanentProviderError("401")])
    backup = FakeProvider("backup", [GOOD])
    result = _call(make_gateway({"primary": primary, "backup": backup}))
    assert result.provider == "backup" and result.model == "backup-model"
    assert len(primary.calls) == 1  # permanent errors are not retried


def test_ut_llm_03b_all_providers_fail(make_gateway: GatewayFactory) -> None:
    provider = FakeProvider("primary", [TransientProviderError("503")] * 3)
    with pytest.raises(ProviderUnavailable):
        _call(make_gateway({"primary": provider}))


def test_ut_llm_04_request_cap_and_daily_budget(make_gateway: GatewayFactory) -> None:
    provider = FakeProvider("primary", [GOOD, GOOD, GOOD])
    gateway = make_gateway({"primary": provider}, daily_limit=2)
    budget = RequestBudget(max_calls=1)
    _call(gateway, user="first <PHONE_1>", budget=budget)
    with pytest.raises(BudgetExceeded, match="per-request"):
        _call(gateway, user="second <PHONE_1>", budget=budget)
    _call(gateway, user="third <PHONE_1>")
    with pytest.raises(BudgetExceeded, match="daily"):
        _call(gateway, user="fourth <PHONE_1>")


def test_ut_llm_05_schema_repair_once_then_fail(make_gateway: GatewayFactory) -> None:
    repaired = FakeProvider("primary", ["not json", "```json\n" + GOOD + "\n```"])
    budget = RequestBudget(max_calls=4)
    assert _call(make_gateway({"primary": repaired}), budget=budget).output.label == "scam"
    assert budget.calls == 2
    assert "previous reply was not valid JSON" in repaired.calls[1]["user"]

    broken = FakeProvider("primary", ['{"label": 1}', '{"oops": true}'])
    with pytest.raises(SchemaViolation):
        _call(make_gateway({"primary": broken}), user="other <PHONE_1>")


def test_ut_llm_06_rejects_unmasked_pii(make_gateway: GatewayFactory) -> None:
    provider = FakeProvider("primary", [GOOD])
    with pytest.raises(PIIDetectedInPrompt):
        _call(make_gateway({"primary": provider}), user="Call 9876543210 now")
    assert provider.calls == []


def test_ut_llm_07_cached_and_offline_modes_never_call_provider(
    make_gateway: GatewayFactory, tmp_path: Path
) -> None:
    _call(make_gateway({"primary": FakeProvider("primary", [GOOD])}))  # warm cache in live mode
    idle = FakeProvider("primary", [])
    for mode in (Mode.CACHED, Mode.OFFLINE):
        gateway = make_gateway({"primary": idle}, mode=mode)
        assert _call(gateway).cache_hit
        with pytest.raises(CacheMiss):
            _call(gateway, user="never seen <PHONE_1>")
    assert idle.calls == []


def test_ut_llm_07b_placeholder_model_refused(make_gateway: GatewayFactory) -> None:
    provider = FakeProvider("primary", [GOOD])
    gateway = make_gateway({"primary": provider}, config=_config(model="TBD"))
    with pytest.raises(ModelNotConfigured):
        _call(gateway)
    assert provider.calls == []


def test_ut_llm_08_logs_and_cache_hold_no_secrets_or_prompt_text(
    make_gateway: GatewayFactory, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    secret_marker = "UNIQUE-PROMPT-MARKER"
    with caplog.at_level(logging.INFO, logger="scamsaathi.llm"):
        _call(make_gateway({"primary": FakeProvider("primary", [GOOD])}), user=f"{secret_marker} <PHONE_1>")
    assert secret_marker not in caplog.text
    record = next(r for r in caplog.records if r.getMessage() == "llm_call")
    assert record.__dict__["cache_hit"] is False
    for path in (tmp_path / "cache").rglob("*.json"):
        assert secret_marker not in path.name
        assert secret_marker not in path.read_text(encoding="utf-8")
