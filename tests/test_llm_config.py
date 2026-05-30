"""Phase 3B tests: env-driven LLM client config loading.

Tests inject a mapping; they never mutate global ``os.environ``.
"""

import pytest

from ai_dev_orchestrator.llm.config import (
    ENV_API_KEY,
    ENV_BASE_URL,
    ENV_DEFAULT_MODEL,
    ENV_MAX_RETRIES,
    ENV_TIMEOUT_SECONDS,
    LLMConfigError,
    load_llm_client_config_from_env,
)


def _base_env() -> dict[str, str]:
    return {
        ENV_BASE_URL: "http://internal/llm",
        ENV_API_KEY: "secret",
        ENV_DEFAULT_MODEL: "minimax-m2.7",
    }


def test_loads_valid_config_with_defaults():
    cfg = load_llm_client_config_from_env(_base_env())
    assert cfg.base_url == "http://internal/llm"
    assert cfg.api_key == "secret"
    assert cfg.default_model == "minimax-m2.7"
    # Defaults applied when optional vars absent.
    assert cfg.timeout_seconds == 30.0
    assert cfg.max_retries == 2


def test_optional_overrides_parse():
    env = _base_env()
    env[ENV_TIMEOUT_SECONDS] = "12.5"
    env[ENV_MAX_RETRIES] = "5"
    cfg = load_llm_client_config_from_env(env)
    assert cfg.timeout_seconds == 12.5
    assert cfg.max_retries == 5


@pytest.mark.parametrize("missing", [ENV_BASE_URL, ENV_API_KEY, ENV_DEFAULT_MODEL])
def test_missing_required_var_raises(missing):
    env = _base_env()
    del env[missing]
    with pytest.raises(LLMConfigError):
        load_llm_client_config_from_env(env)


@pytest.mark.parametrize("blank", [ENV_BASE_URL, ENV_API_KEY, ENV_DEFAULT_MODEL])
def test_blank_required_var_raises(blank):
    env = _base_env()
    env[blank] = "   "
    with pytest.raises(LLMConfigError):
        load_llm_client_config_from_env(env)


def test_invalid_timeout_raises():
    env = _base_env()
    env[ENV_TIMEOUT_SECONDS] = "not-a-number"
    with pytest.raises(LLMConfigError):
        load_llm_client_config_from_env(env)


def test_invalid_max_retries_raises():
    env = _base_env()
    env[ENV_MAX_RETRIES] = "3.5"
    with pytest.raises(LLMConfigError):
        load_llm_client_config_from_env(env)


def test_nonpositive_timeout_raises():
    env = _base_env()
    env[ENV_TIMEOUT_SECONDS] = "0"
    with pytest.raises(LLMConfigError):
        load_llm_client_config_from_env(env)


def test_negative_max_retries_raises():
    env = _base_env()
    env[ENV_MAX_RETRIES] = "-1"
    with pytest.raises(LLMConfigError):
        load_llm_client_config_from_env(env)


def test_empty_mapping_raises():
    with pytest.raises(LLMConfigError):
        load_llm_client_config_from_env({})
