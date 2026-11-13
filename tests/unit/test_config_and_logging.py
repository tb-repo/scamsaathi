"""Settings, YAML loading, and PII-safe logging (tasks 1.2, 1.5)."""

from __future__ import annotations

import json
import logging

import pytest

from scamsaathi.config import CONFIG_DIR, Mode, Settings, load_llm_config
from scamsaathi.logging_setup import JsonFormatter, PIIRedactionFilter, set_request_id


def _settings(**env: str) -> Settings:
    return Settings(_env_file=None, **env)  # type: ignore[call-arg]


def test_defaults_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("GEMINI_API_KEY", "SCAMSAATHI_MODE", "GEMINI_MODEL_FAST"):
        monkeypatch.delenv(name, raising=False)
    settings = _settings()
    assert settings.mode is Mode.LIVE
    assert settings.gemini_api_key is None
    assert settings.llm_cache_dir.is_absolute()


def test_placeholder_key_treated_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "your-key-here")
    assert _settings().gemini_api_key is None


def test_key_is_secret_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "fake-secret-value")
    settings = _settings()
    assert "fake-secret-value" not in repr(settings)
    assert settings.gemini_api_key is not None


def test_env_model_overrides_yaml(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_MODEL_FAST", "model-from-env")
    monkeypatch.setenv("GEMINI_MODEL_REASONING", "TBD")  # placeholder keeps the YAML value
    config = load_llm_config(_settings(), CONFIG_DIR / "llm.yaml")
    assert config.tiers["fast"].model == "model-from-env"
    assert config.tiers["reasoning"].model == "gemini-3.8-flash"
    assert config.tiers["reasoning"].is_configured


def test_shipped_models_are_not_preview_or_deprecated() -> None:
    """ADR-008: production tiers use stable models; 2.x and preview IDs are rejected."""
    config = load_llm_config(_settings(), CONFIG_DIR / "llm.yaml")
    models = [t.model for t in config.tiers.values()]
    models += [fb.model for fbs in config.fallbacks.values() for fb in fbs]
    for model in models:
        assert "preview" not in model and "exp" not in model, model
        assert not model.startswith(("gemini-1", "gemini-2")), model


def test_invalid_mode_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCAMSAATHI_MODE", "turbo")
    with pytest.raises(ValueError):
        _settings()


def test_log_lines_are_json_and_pii_masked() -> None:
    record = logging.makeLogRecord(
        {"name": "scamsaathi.test", "levelname": "INFO", "msg": "user typed %s",
         "args": ("9876543210",), "note": "upi a.b@ybl"}
    )
    set_request_id("req-123")
    assert PIIRedactionFilter().filter(record)
    line = json.loads(JsonFormatter().format(record))
    assert line["request_id"] == "req-123"
    assert line["msg"] == "user typed <PHONE_1>"
    assert line["note"] == "upi <UPI_1>"
