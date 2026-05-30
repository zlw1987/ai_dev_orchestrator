"""Typed LLM request/response/config models for the AI Dev Orchestrator.

Phase 3B: pure data models only. These describe the SHAPE of chat-completion
requests and responses and the resolved connection settings. They make no
network calls, read no environment variables, and contact no model. They mirror
the OpenAI chat schema so a future LiteLLM client can map payloads directly.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _require_non_blank(value: str, field_name: str) -> str:
    """Reject empty or whitespace-only strings."""
    if value is None or not value.strip():
        raise ValueError(f"{field_name} must not be empty or whitespace-only.")
    return value


class LLMMessage(BaseModel):
    """A single chat message in an OpenAI-compatible conversation."""

    role: Literal["system", "user", "assistant"]
    content: str

    @field_validator("content")
    @classmethod
    def _content_not_blank(cls, value: str) -> str:
        return _require_non_blank(value, "content")


class LLMRequest(BaseModel):
    """A chat-completion request.

    Minimal field set for chat completion; no tools, functions, or streaming
    fields yet (kept out by scope).
    """

    model: str
    messages: list[LLMMessage]
    temperature: float | None = None
    max_tokens: int | None = None

    @field_validator("model")
    @classmethod
    def _model_not_blank(cls, value: str) -> str:
        return _require_non_blank(value, "model")

    @field_validator("messages")
    @classmethod
    def _messages_not_empty(cls, value: list[LLMMessage]) -> list[LLMMessage]:
        if not value:
            raise ValueError("messages must contain at least one message.")
        return value

    @field_validator("temperature")
    @classmethod
    def _temperature_in_range(cls, value: float | None) -> float | None:
        if value is not None and not (0.0 <= value <= 2.0):
            raise ValueError("temperature must be between 0 and 2 inclusive.")
        return value

    @field_validator("max_tokens")
    @classmethod
    def _max_tokens_positive(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("max_tokens must be positive.")
        return value


class LLMUsage(BaseModel):
    """Token accounting for a completion (enables cost/audit logging)."""

    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class LLMResponse(BaseModel):
    """A normalized chat-completion result.

    Callers depend on this small normalized shape rather than raw provider JSON.
    ``content`` may be empty (a provider can legitimately return empty text);
    provider behavior is not special-cased here.
    """

    model: str
    content: str
    finish_reason: str | None = None
    usage: LLMUsage | None = None

    @field_validator("model")
    @classmethod
    def _model_not_blank(cls, value: str) -> str:
        return _require_non_blank(value, "model")


class LLMClientConfig(BaseModel):
    """Resolved connection settings, built from environment variables.

    This is the only object that holds the API key. ``api_key`` is excluded from
    ``repr`` so it does not leak into logs or tracebacks.
    """

    base_url: str
    api_key: str = Field(repr=False)
    default_model: str
    timeout_seconds: float = Field(default=30.0, gt=0)
    max_retries: int = Field(default=2, ge=0)

    @field_validator("base_url")
    @classmethod
    def _base_url_not_blank(cls, value: str) -> str:
        return _require_non_blank(value, "base_url")

    @field_validator("api_key")
    @classmethod
    def _api_key_not_blank(cls, value: str) -> str:
        return _require_non_blank(value, "api_key")

    @field_validator("default_model")
    @classmethod
    def _default_model_not_blank(cls, value: str) -> str:
        return _require_non_blank(value, "default_model")
