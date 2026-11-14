"""LLM provider adapters (task 1.6).

A provider turns (model, system, user, schema) into raw JSON text plus token usage.
Validation, retries, caching, and budgets live in the gateway, not here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import SecretStr

from scamsaathi.llm.errors import PermanentProviderError, TransientProviderError

_TRANSIENT_HTTP_CODES = frozenset({408, 429, 500, 502, 503, 504})


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


class Provider(Protocol):
    name: str

    def generate(
        self,
        *,
        model: str,
        system: str,
        user: str,
        json_schema: dict[str, Any],
        temperature: float,
        timeout_s: float,
    ) -> ProviderResponse:
        """Return JSON text. Raise TransientProviderError or PermanentProviderError on failure."""
        ...


class GeminiProvider:
    """Google Gemini API via the google-genai SDK (verified against google-genai 3.2.0)."""

    name = "gemini"

    def __init__(self, api_key: SecretStr) -> None:
        from google import genai  # local import keeps tests and offline mode SDK-free

        self._client = genai.Client(api_key=api_key.get_secret_value())

    def generate(
        self,
        *,
        model: str,
        system: str,
        user: str,
        json_schema: dict[str, Any],
        temperature: float,
        timeout_s: float,
    ) -> ProviderResponse:
        from google.genai import errors, types

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json",
            response_json_schema=json_schema,
            http_options=types.HttpOptions(timeout=int(timeout_s * 1000)),
        )
        try:
            response = self._client.models.generate_content(
                model=model, contents=user, config=config
            )
        except errors.APIError as exc:
            # Message may echo request content, so only the status code is surfaced.
            if exc.code in _TRANSIENT_HTTP_CODES:
                raise TransientProviderError(f"gemini HTTP {exc.code}") from None
            raise PermanentProviderError(f"gemini HTTP {exc.code}") from None
        except (TimeoutError, ConnectionError, OSError) as exc:
            raise TransientProviderError(f"gemini {type(exc).__name__}") from None
        except Exception as exc:
            exc_name = type(exc).__name__
            if any(term in exc_name for term in ("Read", "Network", "Protocol", "Timeout", "Connect", "Remote", "HTTP")):
                raise TransientProviderError(f"gemini {exc_name}") from None
            raise

        text = response.text
        if not text:
            raise TransientProviderError("gemini returned an empty response")
        usage = response.usage_metadata
        return ProviderResponse(
            text=text,
            input_tokens=(usage.prompt_token_count or 0) if usage else 0,
            output_tokens=(usage.candidates_token_count or 0) if usage else 0,
        )


class GroqProvider:
    """Groq API client as a fast fallback provider (ADR-001)."""

    name = "groq"

    def __init__(self, api_key: SecretStr) -> None:
        from groq import Groq  # local import keeps tests and offline mode SDK-free

        self._client = Groq(api_key=api_key.get_secret_value())

    def generate(
        self,
        *,
        model: str,
        system: str,
        user: str,
        json_schema: dict[str, Any],
        temperature: float,
        timeout_s: float,
    ) -> ProviderResponse:
        from groq import APIConnectionError, APIStatusError, APITimeoutError

        try:
            response = self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                response_format={"type": "json_object"},
                timeout=timeout_s,
            )
        except (APITimeoutError, APIConnectionError, TimeoutError, ConnectionError, OSError) as exc:
            raise TransientProviderError(f"groq {type(exc).__name__}") from None
        except APIStatusError as exc:
            if exc.status_code in _TRANSIENT_HTTP_CODES:
                raise TransientProviderError(f"groq HTTP {exc.status_code}") from None
            raise PermanentProviderError(f"groq HTTP {exc.status_code}") from None
        except Exception as exc:
            exc_name = type(exc).__name__
            if any(term in exc_name for term in ("Read", "Network", "Protocol", "Timeout", "Connect", "Remote", "HTTP")):
                raise TransientProviderError(f"groq {exc_name}") from None
            raise

        choice = response.choices[0]
        text = choice.message.content or ""
        if not text:
            raise TransientProviderError("groq returned an empty response")
        usage = response.usage
        return ProviderResponse(
            text=text,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )

