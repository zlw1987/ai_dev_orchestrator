"""Internal LiteLLM / OpenAI-compatible chat-completion client.

Phase 3C: a thin, mockable transport boundary over an OpenAI-compatible
``/chat/completions`` endpoint. It consumes the Phase 3B typed models/config
and:

- makes **no** network call at import time or construction time;
- reads **no** environment variables (env loading lives in ``llm/config.py``);
- creates **no** global client at import time;
- never logs the API key, prompts, or completions.

The client accepts an :class:`LLMRequest`, performs one chat completion against
the configured internal endpoint, and returns a normalized :class:`LLMResponse`
(or raises a typed error). Interpreting or acting on model output is never the
client's job.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import httpx
from pydantic import ValidationError

from ai_dev_orchestrator.llm.models import (
    LLMClientConfig,
    LLMRequest,
    LLMResponse,
    LLMUsage,
)

_USER_AGENT = "ai-dev-orchestrator"
# Base multiplier for exponential backoff between retries. Kept small; tests
# inject a no-op ``sleep`` so retry timing never slows the suite.
_BACKOFF_BASE_SECONDS = 0.5


class LLMClientError(Exception):
    """Base class for all errors raised by :class:`LLMClient`.

    Messages never include the API key, full prompts, or full completions.
    """


class LLMAuthError(LLMClientError):
    """The endpoint rejected the credentials (HTTP 401/403)."""


class LLMTimeoutError(LLMClientError):
    """The request exceeded the configured timeout (after the retry budget)."""


class LLMTransportError(LLMClientError):
    """A connection/network failure occurred (after the retry budget)."""


class LLMResponseError(LLMClientError):
    """A non-2xx response (after retries) or an unparseable/malformed body."""


class LLMClient:
    """Chat-completion client for an OpenAI-compatible endpoint.

    The client is inert until :meth:`chat` is called. Inject ``client`` or
    ``transport`` (e.g. ``httpx.MockTransport``) to keep tests fully offline.
    """

    def __init__(
        self,
        config: LLMClientConfig,
        *,
        client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        """Build a client.

        Args:
            config: Resolved connection settings (holds the only API key copy).
            client: Optional pre-built ``httpx.Client``. When provided it is
                reused across retries and is **not** closed by this client.
            transport: Optional ``httpx.BaseTransport`` (e.g.
                ``httpx.MockTransport``). A short-lived ``httpx.Client`` is
                built around it per :meth:`chat` call and closed afterwards.
            sleep: Optional sleep function used for retry backoff. Defaults to
                ``time.sleep``; inject a no-op in tests to keep them fast.

        No environment variables are read and no network call is made here.
        """
        self._config = config
        self._client = client
        self._transport = transport
        self._sleep = sleep if sleep is not None else time.sleep

    def chat(self, request: LLMRequest) -> LLMResponse:
        """Perform one chat completion and return a normalized response.

        Raises:
            LLMAuthError: On HTTP 401/403 (never retried).
            LLMTimeoutError: On request timeout, after the retry budget.
            LLMTransportError: On connection/network failure, after retries.
            LLMResponseError: On a non-2xx response (429/5xx after retries, or
                any other 4xx immediately) or a malformed/unparseable body.
        """
        url = f"{self._config.base_url.rstrip('/')}/chat/completions"
        payload = self._build_payload(request)
        headers = self._headers()

        client, owns_client = self._acquire_client()
        try:
            return self._send_with_retries(client, url, payload, headers, request)
        finally:
            if owns_client:
                client.close()

    # -- internals -----------------------------------------------------------

    def _acquire_client(self) -> tuple[httpx.Client, bool]:
        """Return ``(client, owns_client)``; owned clients are closed by us."""
        if self._client is not None:
            return self._client, False
        if self._transport is not None:
            return (
                httpx.Client(
                    transport=self._transport,
                    timeout=self._config.timeout_seconds,
                ),
                True,
            )
        return httpx.Client(timeout=self._config.timeout_seconds), True

    def _send_with_retries(
        self,
        client: httpx.Client,
        url: str,
        payload: dict[str, object],
        headers: dict[str, str],
        request: LLMRequest,
    ) -> LLMResponse:
        # Total attempts = initial try + bounded retries. Only transient cases
        # (timeout, transport error, HTTP 429/5xx) consume a retry; 4xx auth and
        # validation failures fail fast.
        attempts = self._config.max_retries + 1
        for attempt in range(attempts):
            is_last = attempt == attempts - 1
            try:
                response = client.post(url, json=payload, headers=headers)
            except httpx.TimeoutException as exc:
                # TimeoutException is a subclass of TransportError: handle first.
                if is_last:
                    raise LLMTimeoutError("LLM request timed out.") from exc
                self._backoff(attempt)
                continue
            except httpx.TransportError as exc:
                if is_last:
                    raise LLMTransportError(
                        "LLM request failed due to a connection/transport error."
                    ) from exc
                self._backoff(attempt)
                continue

            status = response.status_code
            if status in (401, 403):
                # Credentials rejected: never retried.
                raise LLMAuthError(
                    f"LLM endpoint rejected the request with status {status}."
                )
            if status == 429 or 500 <= status < 600:
                if is_last:
                    raise LLMResponseError(
                        f"LLM endpoint returned retryable status {status} "
                        "after exhausting retries."
                    )
                self._backoff(attempt)
                continue
            if status >= 400:
                # Other non-retryable 4xx (e.g. 400/404).
                raise LLMResponseError(
                    f"LLM endpoint returned non-retryable status {status}."
                )

            return self._parse_response(response, request)

        # Unreachable: the loop always returns or raises.
        raise LLMResponseError("LLM request failed for an unknown reason.")

    def _backoff(self, attempt: int) -> None:
        delay = _BACKOFF_BASE_SECONDS * (2**attempt)
        if delay > 0:
            self._sleep(delay)

    def _build_payload(self, request: LLMRequest) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": request.model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in request.messages
            ],
        }
        # Optional sampling controls are omitted entirely when unset so the
        # provider applies its own defaults.
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        return payload

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        }

    def _parse_response(
        self, response: httpx.Response, request: LLMRequest
    ) -> LLMResponse:
        try:
            data = response.json()
        except ValueError as exc:
            raise LLMResponseError("LLM response body was not valid JSON.") from exc

        if not isinstance(data, dict):
            raise LLMResponseError("LLM response body was not a JSON object.")

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMResponseError("LLM response contained no choices.")

        first = choices[0]
        if not isinstance(first, dict):
            raise LLMResponseError("LLM response choice was malformed.")

        message = first.get("message")
        if not isinstance(message, dict):
            raise LLMResponseError("LLM response choice had no message object.")

        # A missing/null content is a valid empty completion; a non-string is not.
        content = message.get("content")
        if content is None:
            content = ""
        elif not isinstance(content, str):
            raise LLMResponseError("LLM response message content was not a string.")

        finish_reason = first.get("finish_reason")
        model = data.get("model") or request.model
        usage = self._parse_usage(data.get("usage"))

        try:
            return LLMResponse(
                model=model,
                content=content,
                finish_reason=finish_reason,
                usage=usage,
            )
        except ValidationError as exc:
            raise LLMResponseError(
                f"LLM response could not be normalized: {exc}"
            ) from exc

    @staticmethod
    def _parse_usage(usage_data: object) -> LLMUsage | None:
        if usage_data is None:
            return None
        if not isinstance(usage_data, dict):
            raise LLMResponseError("LLM response usage was malformed.")
        try:
            return LLMUsage(**usage_data)
        except ValidationError as exc:
            raise LLMResponseError("LLM response usage was malformed.") from exc
