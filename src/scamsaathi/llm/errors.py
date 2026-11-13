"""Gateway error hierarchy (docs/06 section 3.12)."""

from __future__ import annotations


class LLMGatewayError(Exception):
    """Base class. Callers catch this to fall back to deterministic results."""


class BudgetExceeded(LLMGatewayError):
    """Per-request call cap or daily budget reached (FR-076)."""


class ProviderUnavailable(LLMGatewayError):
    """All providers in the chain failed after retries."""


class SchemaViolation(LLMGatewayError):
    """Output did not validate against the schema, even after one repair attempt."""


class PIIDetectedInPrompt(LLMGatewayError):
    """A prompt still contained PII; the call was refused (FR-060)."""


class CacheMiss(LLMGatewayError):
    """No cached response in ``cached`` or ``offline`` mode."""


class ModelNotConfigured(LLMGatewayError):
    """Tier model is still the placeholder; set it in .env or config/llm.yaml (Q-3)."""


class TransientProviderError(Exception):
    """Retryable provider failure (429, 5xx, timeout). Internal to the gateway."""


class PermanentProviderError(Exception):
    """Non-retryable provider failure (auth, bad request). Internal to the gateway."""
