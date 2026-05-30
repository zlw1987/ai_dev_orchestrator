"""Phase 3B tests: typed LLM model validation."""

import pytest
from pydantic import ValidationError

from ai_dev_orchestrator.llm.models import (
    LLMClientConfig,
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMUsage,
)


def test_valid_message():
    msg = LLMMessage(role="user", content="hello")
    assert msg.role == "user"
    assert msg.content == "hello"


def test_message_empty_content_fails():
    with pytest.raises(ValidationError):
        LLMMessage(role="user", content="")


def test_message_whitespace_content_fails():
    with pytest.raises(ValidationError):
        LLMMessage(role="user", content="   ")


def test_message_invalid_role_fails():
    with pytest.raises(ValidationError):
        LLMMessage(role="robot", content="hi")


def test_valid_request_minimal():
    req = LLMRequest(model="minimax-m2.7", messages=[LLMMessage(role="user", content="hi")])
    assert req.model == "minimax-m2.7"
    assert req.temperature is None
    assert req.max_tokens is None


def test_valid_request_full():
    req = LLMRequest(
        model="minimax-m2.7",
        messages=[LLMMessage(role="system", content="be terse")],
        temperature=0.5,
        max_tokens=256,
    )
    assert req.temperature == 0.5
    assert req.max_tokens == 256


def test_request_empty_model_fails():
    with pytest.raises(ValidationError):
        LLMRequest(model="", messages=[LLMMessage(role="user", content="hi")])


def test_request_whitespace_model_fails():
    with pytest.raises(ValidationError):
        LLMRequest(model="  ", messages=[LLMMessage(role="user", content="hi")])


def test_request_empty_messages_fails():
    with pytest.raises(ValidationError):
        LLMRequest(model="m", messages=[])


@pytest.mark.parametrize("temperature", [-0.1, 2.1])
def test_request_invalid_temperature_fails(temperature):
    with pytest.raises(ValidationError):
        LLMRequest(
            model="m",
            messages=[LLMMessage(role="user", content="hi")],
            temperature=temperature,
        )


@pytest.mark.parametrize("temperature", [0.0, 2.0])
def test_request_temperature_bounds_ok(temperature):
    req = LLMRequest(
        model="m",
        messages=[LLMMessage(role="user", content="hi")],
        temperature=temperature,
    )
    assert req.temperature == temperature


@pytest.mark.parametrize("max_tokens", [0, -1])
def test_request_invalid_max_tokens_fails(max_tokens):
    with pytest.raises(ValidationError):
        LLMRequest(
            model="m",
            messages=[LLMMessage(role="user", content="hi")],
            max_tokens=max_tokens,
        )


def test_valid_usage_defaults():
    usage = LLMUsage()
    assert usage.prompt_tokens == 0
    assert usage.completion_tokens == 0
    assert usage.total_tokens == 0


def test_valid_usage_values():
    usage = LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    assert usage.total_tokens == 15


@pytest.mark.parametrize(
    "field", ["prompt_tokens", "completion_tokens", "total_tokens"]
)
def test_usage_negative_tokens_fail(field):
    with pytest.raises(ValidationError):
        LLMUsage(**{field: -1})


def test_valid_response_minimal():
    resp = LLMResponse(model="m", content="done")
    assert resp.finish_reason is None
    assert resp.usage is None


def test_valid_response_full():
    resp = LLMResponse(
        model="m",
        content="done",
        finish_reason="stop",
        usage=LLMUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3),
    )
    assert resp.finish_reason == "stop"
    assert resp.usage.total_tokens == 3


def test_response_empty_content_allowed():
    # An empty completion is permitted; provider behavior is not special-cased.
    resp = LLMResponse(model="m", content="")
    assert resp.content == ""


def test_response_empty_model_fails():
    with pytest.raises(ValidationError):
        LLMResponse(model="", content="done")


def test_valid_client_config_defaults():
    cfg = LLMClientConfig(
        base_url="http://internal/llm",
        api_key="secret",
        default_model="minimax-m2.7",
    )
    assert cfg.timeout_seconds == 30.0
    assert cfg.max_retries == 2


@pytest.mark.parametrize("field", ["base_url", "api_key", "default_model"])
def test_client_config_blank_required_fields_fail(field):
    values = {
        "base_url": "http://internal/llm",
        "api_key": "secret",
        "default_model": "m",
    }
    values[field] = "   "
    with pytest.raises(ValidationError):
        LLMClientConfig(**values)


def test_client_config_nonpositive_timeout_fails():
    with pytest.raises(ValidationError):
        LLMClientConfig(
            base_url="http://internal/llm",
            api_key="secret",
            default_model="m",
            timeout_seconds=0,
        )


def test_client_config_negative_retries_fails():
    with pytest.raises(ValidationError):
        LLMClientConfig(
            base_url="http://internal/llm",
            api_key="secret",
            default_model="m",
            max_retries=-1,
        )


def test_client_config_api_key_not_in_repr():
    cfg = LLMClientConfig(
        base_url="http://internal/llm",
        api_key="super-secret-value",
        default_model="m",
    )
    assert "super-secret-value" not in repr(cfg)
    # The secret is still accessible as an attribute.
    assert cfg.api_key == "super-secret-value"
