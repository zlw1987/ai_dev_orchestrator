"""The one live request's transport boundary and wait deadline (ALPHA-P1B).

Two small mechanisms, both private to the supervised implementer.

**The bounded counting transport** wraps the network transport AIDO builds
itself. It is the only place the outbound request is observed, and it refuses,
**before anything reaches the network transport**:

- a second ``handle_request`` call (one consent, one request; A-11);
- a method other than ``POST``, or a URL other than exactly the consented
  ``<base>/chat/completions`` (scheme, host and port included; A-2, R-6);
- a body that does not decode to exactly the consented wire payload (R-5).

It sets ``Accept-Encoding: identity``, and it refuses a response with any other
``Content-Encoding``, a ``Content-Length`` above the bound, or a status outside
2xx/4xx/5xx (R-4; the shipped client would otherwise parse a 3xx body as a
completion). It counts response body bytes **as they are received** and raises
:class:`ResponseTooLarge` the moment the count passes the bound, so no byte
past the bound is handed to httpx (A-4). It records what it observed.

**The deadline worker** is the RS1-FU2 pattern, copied rather than shared so
the accepted reviewer module stays byte-identical: exactly one daemon thread
performs exactly ``client.chat(request)`` and publishes the response or the
exception into a one-shot slot; the main thread waits on AIDO's own monotonic
deadline. No join, no executor, no pool, no thread kill, no socket close, no
cancellation request, no asyncio, no process.

    AIDO wait ended  !=  worker stopped  !=  HTTP request cancelled
                     !=  backend inference stopped

None of this is a sandbox or a security boundary against code in the same
process (A-19). It is what makes AIDO's own entry point send at most one
request, to the consented place, with the consented content.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field

import httpx

from ai_dev_orchestrator.llm.models import LLMRequest, LLMResponse

#: The worker thread's name, so a test or an operator can recognise it.
WORKER_THREAD_NAME = "aido-supervised-implementer-request"


class LiveTransportViolation(Exception):
    """The wrapper refused a request or a response. Never an ``httpx`` error.

    Deliberately not an ``httpx.TransportError`` subclass, so the shipped
    client can neither swallow nor retry it. Messages are fixed text: they
    never carry a URL, a header, a body or a credential.
    """

    def __init__(self, category: str, message: str) -> None:
        super().__init__(f"{category}: {message}")
        self.category = category


class ResponseTooLarge(LiveTransportViolation):
    """The response body passed :data:`MAX_RESPONSE_BODY_BYTES`."""


class SupervisorDeadlineExpired(Exception):
    """AIDO's own wait deadline expired first. The worker was abandoned, not stopped."""


@dataclass(frozen=True)
class OutboundExpectation:
    """What the one outbound request must be, exactly."""

    url: httpx.URL
    payload: dict
    scheme: str
    host: str
    port: int


@dataclass
class TransportObservation:
    """What the wrapper observed. Written by the worker thread.

    The main thread reads it only after the worker published, or, after a
    stall, as "observed when AIDO stopped waiting", which may lag (R-8).
    """

    handle_request_calls: int = 0
    forwarded_to_network_transport: int = 0
    response_status_code: int | None = None
    response_body_bytes: int = 0
    response_content_encoding: str = "identity"
    observed_scheme: str | None = None
    observed_host: str | None = None
    observed_port: int | None = None


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _effective_port(url: httpx.URL) -> int:
    if url.port is not None:
        return url.port
    return 443 if url.scheme == "https" else 80


class _BoundedResponseStream(httpx.SyncByteStream):
    """Counts bytes as they arrive and refuses the first chunk past the bound."""

    def __init__(
        self, inner: httpx.SyncByteStream, *, limit: int, observation: TransportObservation
    ) -> None:
        self._inner = inner
        self._limit = limit
        self._observation = observation

    def __iter__(self) -> Iterator[bytes]:
        for chunk in self._inner:
            self._observation.response_body_bytes += len(chunk)
            if self._observation.response_body_bytes > self._limit:
                raise ResponseTooLarge(
                    "response_too_large",
                    "the response body passed AIDO's fixed byte bound. The rest "
                    "of the body was not buffered.",
                )
            yield chunk

    def close(self) -> None:
        close = getattr(self._inner, "close", None)
        if callable(close):
            close()


class BoundedCountingTransport(httpx.BaseTransport):
    """The only transport the live client is ever given. See the module docstring."""

    def __init__(
        self,
        inner: httpx.BaseTransport,
        *,
        expectation: OutboundExpectation,
        max_response_body_bytes: int,
        observation: TransportObservation,
    ) -> None:
        self._inner = inner
        self._expectation = expectation
        self._limit = max_response_body_bytes
        self._observation = observation

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        observation = self._observation
        observation.handle_request_calls += 1
        if observation.handle_request_calls != 1:
            raise LiveTransportViolation(
                "second_request_refused",
                "a second request under one authorization was refused before it "
                "reached the network transport.",
            )
        expected = self._expectation
        url = request.url
        observation.observed_scheme = url.scheme
        observation.observed_host = url.host
        observation.observed_port = _effective_port(url)
        if (
            request.method != "POST"
            or url != expected.url
            or url.scheme != expected.scheme
            or url.host != expected.host
            or _effective_port(url) != expected.port
        ):
            raise LiveTransportViolation(
                "outbound_request_mismatch",
                "the outbound request's method or URL is not exactly the "
                "consented endpoint. Nothing reached the network transport.",
            )
        # Canonical bytes, not Python ``==``: equality would conflate ``true``,
        # ``1`` and ``1.0``, which are different JSON.
        try:
            body = _canonical(json.loads(request.read().decode("utf-8")))
        except (UnicodeDecodeError, ValueError, TypeError):
            body = None
        if body is None or body != _canonical(expected.payload):
            raise LiveTransportViolation(
                "outbound_request_mismatch",
                "the outbound request body is not exactly the consented payload. "
                "Nothing reached the network transport.",
            )
        request.headers["Accept-Encoding"] = "identity"

        observation.forwarded_to_network_transport += 1
        response = self._inner.handle_request(request)

        status = response.status_code
        observation.response_status_code = status
        if not (200 <= status < 300 or 400 <= status < 600):
            response.close()
            raise LiveTransportViolation(
                "unexpected_status_class",
                f"the server answered with status class {status // 100}xx, which "
                "is neither a completion nor an error. Redirects are never followed.",
            )
        encoding = response.headers.get("content-encoding")
        if encoding is not None and encoding.strip().lower() != "identity":
            observation.response_content_encoding = "refused"
            response.close()
            raise LiveTransportViolation(
                "content_encoding_refused",
                "the response used a content encoding other than identity, so its "
                "decoded size could not be bounded. It was not read.",
            )
        length = response.headers.get("content-length")
        if length is not None:
            try:
                declared = int(length.strip())
            except ValueError:
                response.close()
                raise LiveTransportViolation(
                    "malformed_content_length", "the response Content-Length is not an integer."
                ) from None
            if declared > self._limit:
                response.close()
                raise ResponseTooLarge(
                    "response_too_large",
                    "the response declared a body larger than AIDO's fixed byte "
                    "bound. It was not read.",
                )
        return httpx.Response(
            status_code=status,
            headers=response.headers,
            stream=_BoundedResponseStream(
                response.stream, limit=self._limit, observation=observation
            ),
            extensions=response.extensions,
            request=request,
        )

    def close(self) -> None:
        self._inner.close()


@dataclass
class _Slot:
    """A one-shot publication box. Not a queue, a future or a task object."""

    response: LLMResponse | None = None
    error: BaseException | None = None
    done: threading.Event = field(default_factory=threading.Event)


def _publish_one_call(client, request: LLMRequest, slot: _Slot) -> None:
    """The worker body: exactly ``client.chat(request)``, then publish."""
    try:
        slot.response = client.chat(request)
    except BaseException as exc:  # noqa: BLE001 - republished on the main thread.
        slot.error = exc
    finally:
        slot.done.set()


def await_one_response(client, request: LLMRequest, *, deadline_seconds: float) -> LLMResponse:
    """Run one ``client.chat`` call under AIDO's own monotonic wait deadline.

    Raises:
        SupervisorDeadlineExpired: AIDO stopped waiting. The worker is abandoned,
            not stopped; the request and the backend's inference may continue.
        BaseException: whatever ``client.chat`` raised, re-raised unchanged.
    """
    slot = _Slot()
    worker = threading.Thread(
        target=_publish_one_call,
        args=(client, request, slot),
        name=WORKER_THREAD_NAME,
        daemon=True,
    )
    worker.start()
    if not slot.done.wait(timeout=deadline_seconds):
        raise SupervisorDeadlineExpired()
    if slot.error is not None:
        raise slot.error
    if slot.response is None:  # pragma: no cover - the worker always sets one.
        raise RuntimeError("the worker published neither a response nor an error.")
    return slot.response
