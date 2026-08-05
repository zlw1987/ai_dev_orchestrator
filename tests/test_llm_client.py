"""Phase 3C tests: mockable LiteLLM/OpenAI-compatible chat client.

All HTTP is faked with ``httpx.MockTransport`` — no socket is ever opened and
no real model is called. A no-op ``sleep`` is injected so retry backoff never
slows the suite.
"""

import httpx
import pytest

from ai_dev_orchestrator.llm.client import (
    LLMAuthError,
    LLMClient,
    LLMClientError,
    LLMResponseError,
    LLMTimeoutError,
    LLMTransportError,
)
from ai_dev_orchestrator.llm.models import (
    LLMClientConfig,
    LLMMessage,
    LLMRequest,
)

SECRET = "super-secret-key-do-not-leak"
BASE_URL = "http://internal-litellm/v1"


def _config(**overrides) -> LLMClientConfig:
    values = {
        "base_url": BASE_URL,
        "api_key": SECRET,
        "default_model": "minimax-m2.7",
        "timeout_seconds": 5.0,
        "max_retries": 2,
    }
    values.update(overrides)
    return LLMClientConfig(**values)


def _client(handler, **config_overrides) -> LLMClient:
    """Build an LLMClient wired to a MockTransport with a no-op backoff sleep."""
    transport = httpx.MockTransport(handler)
    return LLMClient(
        _config(**config_overrides),
        transport=transport,
        sleep=lambda _seconds: None,
    )


def _request(**overrides) -> LLMRequest:
    values = {
        "model": "minimax-m2.7",
        "messages": [
            LLMMessage(role="system", content="be helpful"),
            LLMMessage(role="user", content="hello"),
        ],
    }
    values.update(overrides)
    return LLMRequest(**values)


def _ok_payload(**overrides) -> dict:
    payload = {
        "model": "minimax-m2.7",
        "choices": [
            {
                "message": {"role": "assistant", "content": "hi there"},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 1,
            "completion_tokens": 2,
            "total_tokens": 3,
        },
    }
    payload.update(overrides)
    return payload


# 1. Successful chat completion ------------------------------------------------


def test_successful_chat_completion_builds_request_and_maps_response():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        captured["content_type"] = request.headers.get("Content-Type")
        captured["accept"] = request.headers.get("Accept")
        captured["user_agent"] = request.headers.get("User-Agent")
        import json

        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_ok_payload())

    response = _client(handler).chat(
        _request(temperature=0.2, max_tokens=128)
    )

    assert captured["method"] == "POST"
    assert captured["url"] == "http://internal-litellm/v1/chat/completions"
    assert captured["auth"] == f"Bearer {SECRET}"
    assert captured["content_type"] == "application/json"
    assert captured["accept"] == "application/json"
    assert captured["user_agent"] == "ai-dev-orchestrator"
    assert captured["body"] == {
        "model": "minimax-m2.7",
        "messages": [
            {"role": "system", "content": "be helpful"},
            {"role": "user", "content": "hello"},
        ],
        "temperature": 0.2,
        "max_tokens": 128,
    }

    assert response.model == "minimax-m2.7"
    assert response.content == "hi there"
    assert response.finish_reason == "stop"
    assert response.usage is not None
    assert response.usage.prompt_tokens == 1
    assert response.usage.completion_tokens == 2
    assert response.usage.total_tokens == 3


def test_response_model_falls_back_to_request_model_when_absent():
    payload = _ok_payload()
    del payload["model"]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    response = _client(handler).chat(_request(model="qwen3.6-27b"))
    assert response.model == "qwen3.6-27b"


# 2. Optional request fields ---------------------------------------------------


def test_optional_fields_omitted_when_none():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_ok_payload())

    _client(handler).chat(_request())

    assert "temperature" not in captured["body"]
    assert "max_tokens" not in captured["body"]


def test_optional_fields_included_when_provided():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_ok_payload())

    _client(handler).chat(_request(temperature=0.0, max_tokens=64))

    assert captured["body"]["temperature"] == 0.0
    assert captured["body"]["max_tokens"] == 64


# 3. Empty/missing usage -------------------------------------------------------


def test_usage_is_none_when_provider_omits_it():
    payload = _ok_payload()
    del payload["usage"]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    response = _client(handler).chat(_request())
    assert response.usage is None


# 4. Auth errors ---------------------------------------------------------------


@pytest.mark.parametrize("status", [401, 403])
def test_auth_status_raises_auth_error_without_retry(status):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(status, json={"error": "nope"})

    with pytest.raises(LLMAuthError):
        _client(handler, max_retries=3).chat(_request())

    assert calls["count"] == 1  # no retry


# 5. Non-retryable 4xx ---------------------------------------------------------


@pytest.mark.parametrize("status", [400, 404])
def test_non_retryable_4xx_raises_response_error_without_retry(status):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(status, json={"error": "bad"})

    with pytest.raises(LLMResponseError):
        _client(handler, max_retries=3).chat(_request())

    assert calls["count"] == 1  # no retry


# 6. Retryable status ----------------------------------------------------------


def test_429_retries_then_succeeds():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] < 3:
            return httpx.Response(429, json={"error": "slow down"})
        return httpx.Response(200, json=_ok_payload())

    response = _client(handler, max_retries=2).chat(_request())

    assert calls["count"] == 3  # 1 initial + 2 retries
    assert response.content == "hi there"


def test_5xx_retries_then_raises_response_error_when_never_succeeds():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(503, json={"error": "unavailable"})

    with pytest.raises(LLMResponseError):
        _client(handler, max_retries=2).chat(_request())

    assert calls["count"] == 3  # 1 initial + 2 retries, all 5xx


# 7. Timeout / transport -------------------------------------------------------


def test_timeout_maps_to_timeout_error_after_retry_budget():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(LLMTimeoutError):
        _client(handler, max_retries=2).chat(_request())

    assert calls["count"] == 3  # retried up to the budget


def test_transport_error_maps_to_transport_error_after_retry_budget():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(LLMTransportError):
        _client(handler, max_retries=2).chat(_request())

    assert calls["count"] == 3


def test_timeout_then_success_recovers():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.ReadTimeout("timed out", request=request)
        return httpx.Response(200, json=_ok_payload())

    response = _client(handler, max_retries=2).chat(_request())
    assert calls["count"] == 2
    assert response.content == "hi there"


# 8. Malformed response --------------------------------------------------------


def test_invalid_json_raises_response_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json at all")

    with pytest.raises(LLMResponseError):
        _client(handler).chat(_request())


def test_missing_choices_raises_response_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"model": "minimax-m2.7"})

    with pytest.raises(LLMResponseError):
        _client(handler).chat(_request())


def test_empty_choices_raises_response_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"model": "m", "choices": []})

    with pytest.raises(LLMResponseError):
        _client(handler).chat(_request())


def test_missing_content_maps_to_empty_string():
    payload = {
        "model": "minimax-m2.7",
        "choices": [{"message": {"role": "assistant"}, "finish_reason": "stop"}],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    response = _client(handler).chat(_request())
    assert response.content == ""
    assert response.finish_reason == "stop"


def test_null_content_maps_to_empty_string():
    payload = {
        "model": "minimax-m2.7",
        "choices": [
            {"message": {"role": "assistant", "content": None}, "finish_reason": "stop"}
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    response = _client(handler).chat(_request())
    assert response.content == ""


def test_missing_message_object_raises_response_error():
    payload = {"model": "m", "choices": [{"finish_reason": "stop"}]}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    with pytest.raises(LLMResponseError):
        _client(handler).chat(_request())


# 9. Secret safety -------------------------------------------------------------


@pytest.mark.parametrize(
    "handler_factory",
    [
        lambda: (lambda request: httpx.Response(401, json={"error": "x"})),
        lambda: (lambda request: httpx.Response(400, json={"error": "x"})),
        lambda: (lambda request: httpx.Response(503, json={"error": "x"})),
        lambda: (lambda request: httpx.Response(200, content=b"not json")),
    ],
)
def test_exception_messages_never_contain_the_api_key(handler_factory):
    handler = handler_factory()

    with pytest.raises(LLMClientError) as exc:
        _client(handler, max_retries=1).chat(_request())

    assert SECRET not in str(exc.value)
    assert SECRET not in repr(exc.value)


def test_timeout_and_transport_messages_never_contain_the_api_key():
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("boom", request=request)

    with pytest.raises(LLMTimeoutError) as exc:
        _client(timeout_handler, max_retries=0).chat(_request())
    assert SECRET not in str(exc.value)

    def transport_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    with pytest.raises(LLMTransportError) as exc:
        _client(transport_handler, max_retries=0).chat(_request())
    assert SECRET not in str(exc.value)


# 10. Constructor behavior -----------------------------------------------------


def test_construction_makes_no_request():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json=_ok_payload())

    client = _client(handler)
    assert calls["count"] == 0  # nothing sent until chat() is called

    client.chat(_request())
    assert calls["count"] == 1


def test_injected_client_is_reused_and_not_closed():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_ok_payload())

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = LLMClient(_config(), client=http_client, sleep=lambda _s: None)

    client.chat(_request())
    # The injected client is owned by the caller, so it stays open.
    assert http_client.is_closed is False
    http_client.close()
