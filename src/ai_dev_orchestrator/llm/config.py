"""Environment-driven loader for :class:`LLMClientConfig`.

Phase 3B constraints (deliberate):

- Reads ONLY environment variables (a ``Mapping`` that defaults to ``os.environ``).
- Does NOT read ``.env`` files.
- Does NOT make network calls or contact any model.

Canonical env var names use the ``AIDO_`` prefix to namespace orchestrator
settings (decided in Phase 3B; supersedes the unprefixed Phase 0 names).
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from pydantic import ValidationError

from ai_dev_orchestrator.llm.models import LLMClientConfig

# Canonical (AIDO_-prefixed) environment variable names.
ENV_BASE_URL = "AIDO_LITELLM_BASE_URL"
ENV_API_KEY = "AIDO_LITELLM_API_KEY"
ENV_DEFAULT_MODEL = "AIDO_LITELLM_DEFAULT_MODEL"
ENV_TIMEOUT_SECONDS = "AIDO_LITELLM_TIMEOUT_SECONDS"
ENV_MAX_RETRIES = "AIDO_LITELLM_MAX_RETRIES"


class LLMConfigError(Exception):
    """Raised when LLM client configuration is missing or invalid."""


def load_llm_client_config_from_env(
    environ: Mapping[str, str] | None = None,
) -> LLMClientConfig:
    """Build an :class:`LLMClientConfig` from environment variables.

    Args:
        environ: Mapping of environment variables to read. Defaults to
            ``os.environ``. Inject a mapping in tests to avoid mutating the
            global environment.

    Returns:
        A validated :class:`LLMClientConfig`.

    Raises:
        LLMConfigError: If a required variable is missing/blank, an optional
            numeric variable is non-numeric, or a value fails validation.
    """
    env = os.environ if environ is None else environ

    base_url = _get_required(env, ENV_BASE_URL)
    api_key = _get_required(env, ENV_API_KEY)
    default_model = _get_required(env, ENV_DEFAULT_MODEL)

    kwargs: dict[str, object] = {
        "base_url": base_url,
        "api_key": api_key,
        "default_model": default_model,
    }

    timeout_raw = env.get(ENV_TIMEOUT_SECONDS)
    if timeout_raw is not None:
        kwargs["timeout_seconds"] = _parse_float(timeout_raw, ENV_TIMEOUT_SECONDS)

    retries_raw = env.get(ENV_MAX_RETRIES)
    if retries_raw is not None:
        kwargs["max_retries"] = _parse_int(retries_raw, ENV_MAX_RETRIES)

    try:
        return LLMClientConfig(**kwargs)
    except ValidationError as exc:
        raise LLMConfigError(f"Invalid LLM client configuration:\n{exc}") from exc


def _get_required(env: Mapping[str, str], name: str) -> str:
    """Return a required env var, raising if missing or blank."""
    value = env.get(name)
    if value is None or not value.strip():
        raise LLMConfigError(
            f"Missing required environment variable: {name}"
        )
    return value


def _parse_float(raw: str, name: str) -> float:
    try:
        return float(raw)
    except ValueError as exc:
        raise LLMConfigError(
            f"Environment variable {name} must be a number, got {raw!r}."
        ) from exc


def _parse_int(raw: str, name: str) -> int:
    try:
        return int(raw)
    except ValueError as exc:
        raise LLMConfigError(
            f"Environment variable {name} must be an integer, got {raw!r}."
        ) from exc
