"""Config loading placeholder.

Phase 0: defines the typed shape of orchestrator settings and a loader that
reads ONLY environment variables. It performs no network calls, contacts no
GitHub or LiteLLM endpoint, and stores no secrets in files.

External AI providers (OpenAI, Anthropic, Copilot/Codex) are disabled by
default; the internal LiteLLM endpoint is the intended default provider.
"""

from __future__ import annotations

import os

from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Runtime settings for the orchestrator.

    All fields are optional in Phase 0. Credentials are read from the
    environment at load time and are never persisted to disk by this code.
    """

    # Internal LiteLLM OpenAI-compatible endpoint — the intended default provider.
    litellm_base_url: str | None = Field(
        default=None, description="Base URL of the internal LiteLLM endpoint."
    )
    litellm_api_key: str | None = Field(
        default=None, description="API key for the internal LiteLLM endpoint."
    )

    # GitHub credentials (read but UNUSED in Phase 0 — no API calls are made).
    github_token: str | None = Field(
        default=None, description="GitHub token; not used until a later phase."
    )

    # External paid AI providers are disabled by default.
    enable_external_providers: bool = Field(
        default=False,
        description="Must be explicitly enabled to use OpenAI/Anthropic/etc.",
    )


def load_settings() -> Settings:
    """Load settings from environment variables only.

    Does NOT read a .env file, make network calls, or validate credentials.
    """
    return Settings(
        litellm_base_url=os.environ.get("LITELLM_BASE_URL"),
        litellm_api_key=os.environ.get("LITELLM_API_KEY"),
        github_token=os.environ.get("GITHUB_TOKEN"),
    )
