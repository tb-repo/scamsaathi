"""Provider-agnostic LLM access (ADR-001)."""

from scamsaathi.llm.errors import (
    BudgetExceeded,
    CacheMiss,
    LLMGatewayError,
    ModelNotConfigured,
    PIIDetectedInPrompt,
    ProviderUnavailable,
    SchemaViolation,
)
from scamsaathi.llm.gateway import LLMGateway, LLMResult, RequestBudget

__all__ = [
    "BudgetExceeded",
    "CacheMiss",
    "LLMGateway",
    "LLMGatewayError",
    "LLMResult",
    "ModelNotConfigured",
    "PIIDetectedInPrompt",
    "ProviderUnavailable",
    "RequestBudget",
    "SchemaViolation",
]
