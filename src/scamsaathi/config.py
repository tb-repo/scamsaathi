"""Application settings and configuration loading (task 1.2).

Secrets and runtime switches come from environment variables (or a local `.env`).
Tunable behaviour (model tiers, retries, costs) comes from `config/*.yaml`.
Environment values override YAML for model IDs, so `.env` is the one place to set them.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"

PLACEHOLDER_MODEL = "TBD"


class Mode(StrEnum):
    """Gateway operating mode (FR-073, FR-074)."""

    LIVE = "live"  # call provider, write cache
    CACHED = "cached"  # read cache only, fail on miss
    OFFLINE = "offline"  # cache only; callers degrade to deterministic results on miss


class Settings(BaseSettings):
    """Runtime settings. Names match `.env.example`."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: SecretStr | None = Field(default=None, validation_alias="GEMINI_API_KEY")
    gemini_model_fast: str = Field(default=PLACEHOLDER_MODEL, validation_alias="GEMINI_MODEL_FAST")
    gemini_model_reasoning: str = Field(
        default=PLACEHOLDER_MODEL, validation_alias="GEMINI_MODEL_REASONING"
    )
    gemini_embedding_model: str = Field(
        default=PLACEHOLDER_MODEL, validation_alias="GEMINI_EMBEDDING_MODEL"
    )

    groq_api_key: SecretStr | None = Field(default=None, validation_alias="GROQ_API_KEY")
    groq_model_fast: str = Field(default="llama-3.1-8b-instant", validation_alias="GROQ_MODEL_FAST")
    groq_model_reasoning: str = Field(
        default="llama-3.3-70b-versatile", validation_alias="GROQ_MODEL_REASONING"
    )

    mode: Mode = Field(default=Mode.LIVE, validation_alias="SCAMSAATHI_MODE")
    llm_cache_dir: Path = Field(
        default=PROJECT_ROOT / ".cache" / "llm", validation_alias="SCAMSAATHI_LLM_CACHE_DIR"
    )
    # 6 lets an interview case run every LLM step (extract, classify, extract and classify
    # again after answers, explain) with a repair retry to spare (ADR-001 addendum: quality first).
    max_llm_calls_per_request: int = Field(
        default=6, ge=1, le=20, validation_alias="SCAMSAATHI_MAX_LLM_CALLS_PER_REQUEST"
    )
    daily_call_budget: int = Field(
        default=500, ge=1, validation_alias="SCAMSAATHI_DAILY_CALL_BUDGET"
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", validation_alias="SCAMSAATHI_LOG_LEVEL"
    )

    @field_validator("llm_cache_dir")
    @classmethod
    def _resolve_cache_dir(cls, value: Path) -> Path:
        return value if value.is_absolute() else PROJECT_ROOT / value

    @field_validator("gemini_api_key", "groq_api_key")
    @classmethod
    def _blank_key_is_none(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        raw = value.get_secret_value().strip()
        if not raw or raw == "your-key-here":
            return None
        return value


class TierConfig(BaseModel):
    provider: str
    model: str
    temperature: float = Field(ge=0.0, le=2.0)
    timeout_s: float = Field(gt=0)

    @property
    def is_configured(self) -> bool:
        return bool(self.model) and self.model != PLACEHOLDER_MODEL


class FallbackConfig(BaseModel):
    provider: str
    model: str


class RetryConfig(BaseModel):
    max_attempts: int = Field(default=3, ge=1, le=10)
    base_delay_s: float = Field(default=1.0, ge=0)
    max_delay_s: float = Field(default=8.0, ge=0)


class CostConfig(BaseModel):
    input: float = Field(default=0.0, ge=0)
    output: float = Field(default=0.0, ge=0)


class LLMConfig(BaseModel):
    tiers: dict[str, TierConfig]
    fallbacks: dict[str, list[FallbackConfig]] = Field(default_factory=dict)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    cost_per_million_tokens_inr: CostConfig = Field(default_factory=CostConfig)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must contain a mapping at the top level")
    return data


def load_llm_config(settings: Settings, path: Path | None = None) -> LLMConfig:
    """Load `config/llm.yaml` and apply model overrides from the environment."""
    config = LLMConfig.model_validate(load_yaml(path or CONFIG_DIR / "llm.yaml"))
    overrides = {"fast": settings.gemini_model_fast, "reasoning": settings.gemini_model_reasoning}
    for tier_name, model in overrides.items():
        tier = config.tiers.get(tier_name)
        if tier is not None and tier.provider == "gemini" and model != PLACEHOLDER_MODEL:
            config.tiers[tier_name] = tier.model_copy(update={"model": model})

    if settings.groq_api_key is not None:
        groq_fallbacks = {
            "fast": FallbackConfig(provider="groq", model=settings.groq_model_fast),
            "reasoning": FallbackConfig(provider="groq", model=settings.groq_model_reasoning),
        }
        for tier_name, fb in groq_fallbacks.items():
            existing = config.fallbacks.get(tier_name, [])
            if not any(f.provider == "groq" for f in existing):
                config.fallbacks[tier_name] = [*existing, fb]

    return config


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
