"""Bounded reviewer runtime supervision (Phase 5F2E-RS1).

Why this module exists
----------------------

Phase 5F2E made one semantic reviewer request and reported whatever came back.
That is fine against a hosted endpoint that either answers or errors, and it is
**not** fine against a local reviewer model, where a request that never produces
a usable review still consumes real, scarce resources:

- inference wall time;
- GPU occupancy;
- concurrent-request capacity;
- context occupancy.

For a local model the cost of a useless review is not an API line item, so AIDO
needs a bounded reviewer-attempt policy rather than an open-ended wait.

What this module can honestly observe — and what it cannot
----------------------------------------------------------

The reviewer here is **not an agent** and the existing client is **not
streaming**. There are no tool calls, no file reads, no test runs, and no partial
generation events to watch. So this module classifies attempts using only facts
the current architecture actually produces:

- the request returned a response, or raised a typed
  :class:`~ai_dev_orchestrator.llm.client.LLMClientError`;
- which typed error it raised (timeout vs. auth vs. response vs. transport);
- the response's ``finish_reason``, when the provider supplied one;
- the response's ``usage``, when the provider supplied one;
- whether the content was empty;
- whether the strict parser produced a valid
  :class:`~ai_dev_orchestrator.review.models.ModelReviewResult`.

It deliberately does **not** compute reasoning similarity, inspect
chain-of-thought, ask the model to expose its reasoning, poll tokens, open a
stream, or count tools, files or tests. None of those are observable here, and
reporting them would be fabrication. This is *observable resource supervision*,
not *private-reasoning or agent-progress supervision*.

Retry ownership is explicit
---------------------------

The generic :class:`~ai_dev_orchestrator.llm.client.LLMClient` keeps its
already-shipped bounded transport retries for every other caller, unchanged. The
**controlled reviewer** forces ``max_retries`` to :data:`REVIEWER_TRANSPORT_MAX_RETRIES`
(zero) in its own config builder, so that:

- one semantic attempt is exactly one HTTP/model request;
- the supervisor here — not the transport — owns any second attempt;
- the maximum number of HTTP/model requests AIDO may **issue** in one review
  command is exactly :data:`MAX_SEMANTIC_REVIEW_ATTEMPTS`, and is two only when
  the project opted into the compact retry *and* the first response actually
  came back unusable.

Hidden transport retries were the wrong owner for a supervised local reviewer: a
client with ``max_retries = 2`` would have turned one timed-out semantic review
into three full inference requests without the operator, the packet, or this
module ever seeing it.

AIDO's wait bound is AIDO's OWN deadline, not httpx's timeout
-------------------------------------------------------------

Two different mechanisms share one configured number, and only one of them is
the proof:

```text
httpx timeout           = network-operation / inactivity timeout. It fires when
                          an individual socket operation stalls. A peer that
                          keeps producing activity often enough can hold one
                          request open far longer than the configured value
                          without any single read ever reaching its timeout.

RS1 supervisor deadline = an AIDO-owned monotonic wall-clock deadline around
                          ONE `client.chat(request)` call. It fires on total
                          elapsed wait, whatever the network was doing.
```

So ``attempt_timeout_seconds`` means: **the maximum time AIDO waits for the
reviewer HTTP/model call to complete**, subject only to small local scheduling
overhead. The reviewer's client still receives the same value as a secondary
network-inactivity timeout, which is useful — but it is **not** the proof of
the wait bound, and RS1 must never present it as one.

The mechanism is the smallest one that can be honest: one daemon worker thread
per semantic attempt performs exactly ``client.chat(request)`` and publishes
either the returned response or the exception it raised; the main thread waits
to the deadline and owns the decision. There is no executor, no pool, no
registry, no reusable task framework, no cancellation request, no process, no
asyncio, and no join.

AIDO's wait ended != the worker stopped
---------------------------------------

When the deadline wins, the worker is **abandoned, not terminated**:

- AIDO's wait is bounded;
- AIDO does not wait for that worker afterwards, and never joins it;
- the worker may outlive this review invocation in a long-lived Python process;
- the network operation may still be active;
- backend inference may still be active;
- process exit may ultimately end local daemon-thread state, but RS1 does not
  use, and must never claim, interpreter exit as a cancellation mechanism.

That is the HTTP-side equivalent of the accepted Phase 5F2D abandoned-reader
limitation. Nothing here kills a thread, closes a socket from another thread,
asks a backend to cancel, or tracks workers. Because a stall is terminal,
**one command invocation can leave at most one abandoned reviewer worker.**

A stall is TERMINAL, and that is the whole safety argument
------------------------------------------------------------

An attempt classifies as ``review_stalled`` from either source — the client
raised :class:`~ai_dev_orchestrator.llm.client.LLMTimeoutError` first, or AIDO's
own deadline expired first — and both mean the same thing to the policy: **AIDO
stopped waiting**. AIDO may **not** say that the backend stopped inference: a
remote or internal server's cancellation semantics are outside this phase's
observation boundary.

That asymmetry decides the retry policy. Retrying after a stall would mean:

```text
request 1 reaches a local inference backend
  -> the client times out, or AIDO's own deadline expires
  -> AIDO stops waiting
  -> the backend may STILL be generating, holding its slot and context
  -> AIDO issues compact request 2
  -> the same local model may now hold TWO concurrent inference jobs
```

For the exact production problem this phase exists to solve — a *local* model
whose scarce resource is GPU occupancy and concurrency — that would make things
**worse**, not better. A client timeout is not evidence that the inference slot
was released, and this architecture has no way to obtain that evidence.

So ``review_stalled`` is **not** in :data:`RETRY_ELIGIBLE_OUTCOMES`. It ends the
review, and the human is told exactly why. There is deliberately no sleep, no
backoff, no polling, no cancellation request, no streaming, and no thread here to
guess that the first job finished. A timeout could only become retryable in a
future, separately authorized phase in which AIDO gains an observable,
trustworthy backend-cancellation acknowledgement — which does not exist today.

The two retry-eligible conditions are the ones where the first request is **no
longer an unknown in flight**: a response was actually returned to AIDO, and it
was merely unusable.

What RS1 bounds, stated exactly
-------------------------------

RS1 bounds **AIDO's reviewer request issuance and AIDO's wait budget**. It
proves:

- reviewer transport retries issued by AIDO = 0;
- at most 2 semantic requests issued by AIDO;
- an AIDO-owned monotonic deadline on each attempt's wait, established by the
  supervisor here rather than by httpx timeout semantics;
- the requested max output tokens;
- the completed-response retry policy.

It does **not** prove a bound on: the abandoned worker's lifetime, the HTTP
request's lifetime after AIDO stops waiting, backend inference lifetime, GPU
occupancy lifetime after a client disconnect, backend context lifetime, or
server-side cancellation latency. **Total GPU time is not bounded here**, and no
document, field, or message in this phase may claim it is.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict

from ai_dev_orchestrator.llm.models import LLMRequest, LLMResponse, LLMUsage
from ai_dev_orchestrator.review.models import (
    ModelReviewResult,
    ReviewerAttemptExhaustedError,
    ReviewError,
    parse_model_review_response,
)
from ai_dev_orchestrator.review.request import (
    COMPACT_RETRY_MAX_FINDINGS,
    ReviewContext,
    build_compact_model_review_request,
    build_model_review_request,
)

if TYPE_CHECKING:  # pragma: no cover - typing only, never imported at runtime.
    from ai_dev_orchestrator.llm.client import LLMClient

# The hard ceiling. Not configurable, not derived from project config, and not
# reachable from a CLI flag: two supervised semantic attempts, never three.
MAX_SEMANTIC_REVIEW_ATTEMPTS = 2

# The reviewer's transport retry budget. Forced to zero so one semantic attempt
# is exactly one HTTP/model request. The generic client's own default is
# untouched for every other caller.
REVIEWER_TRANSPORT_MAX_RETRIES = 0

# Exactly one HTTP/model request per semantic attempt, by construction.
TRANSPORT_REQUESTS_PER_ATTEMPT = 1

# The name given to the one daemon worker thread per semantic attempt. Only for
# recognizing it in a stack dump or a debugger; nothing looks it up, and no
# registry, pool or tracking table exists.
REVIEWER_ATTEMPT_THREAD_NAME = "aido-reviewer-attempt"

# How AIDO's wait is bounded, as a token rather than only as prose — because the
# whole FU2 correction is that this is NOT httpx timeout semantics.
ATTEMPT_WAIT_BOUND = "orchestrator_monotonic_deadline"

# Worker-scoped, and therefore a string rather than a boolean, exactly like
# `BACKEND_INFERENCE_LIFETIME_IF_STALLED` below: if AIDO ever stops waiting it
# observes nothing further about the worker, so it must not report a claim in
# either direction.
#
# **Conditional, and that phrasing is load-bearing.** A successful review packet
# can only exist after `run_supervised_review` returned a valid review, and a
# stall is terminal — it raises `ReviewerAttemptExhaustedError` and the command
# exits 4 with no packet at all. So a packet carrying this field is *never*
# describing an abandoned worker that actually existed; it states what would and
# would not be known **if** a supervisor deadline were to expire. Wording it as a
# fact ("the worker thread is abandoned rather than stopped") made every ordinary
# successful run read as though one had been left behind.
ABANDONED_WORKER_LIFETIME_IF_DEADLINE_EXPIRES = (
    "Conditional policy, not a record of this run: IF an AIDO supervisor deadline "
    "expires on an attempt, that attempt's worker is abandoned rather than "
    "terminated — its lifetime is not observed, its HTTP request may still be "
    "active, and it may outlive the review invocation in a long-lived process. "
    "Such an attempt is a terminal stall, so no successful review packet can "
    "describe one: this field never asserts that it happened."
)

# Provider ``finish_reason`` values that mean "the output budget ran out".
# A tiny explicit set, compared after stripping and lower-casing, because this is
# a provider enum rather than a model *name* — reviewer model matching stays
# exact and case-sensitive.
OUTPUT_BUDGET_FINISH_REASONS: frozenset[str] = frozenset(
    {"length", "max_tokens", "max_output_tokens"}
)

ReviewAttemptKind = Literal["full", "compact"]

# Which of the two mechanisms ended the wait. A small closed set, recorded only
# for truthful auditing: `supervisor_deadline` is precisely the case in which an
# abandoned worker exists, and `client_timeout` is precisely the case in which it
# does not. Nothing branches on it — both are `review_stalled` and both are
# terminal.
StallSource = Literal["client_timeout", "supervisor_deadline"]

ReviewAttemptOutcome = Literal[
    # The attempt produced a strict, schema-valid, consistent review.
    "valid_review",
    # The client reported a timeout. AIDO stopped waiting; the backend's own
    # inference state is NOT observed and is never claimed — which is exactly why
    # this outcome is TERMINAL and never buys a second request.
    "review_stalled",
    # The provider said the output budget ran out and no valid review resulted.
    "review_output_budget_exhausted",
    # A response came back and the strict parser rejected it. Not repaired.
    "review_unusable_output",
    # A compact retry parsed cleanly but exceeded the retry-only finding cap.
    "review_retry_finding_cap_exceeded",
    # Failures a shorter prompt cannot plausibly solve: no compact retry.
    "reviewer_auth_failed",
    "reviewer_response_error",
    "reviewer_transport_failed",
]

# The only TWO conditions that may buy the one compact retry, and the property
# they share is the whole point: in both, the first HTTP/model response was
# actually **returned to AIDO**, so the first request is no longer an unknown
# in-flight operation on the backend.
#
# `review_stalled` is deliberately absent. A client timeout leaves the first
# request in an unobserved state, and issuing a second request could put a second
# concurrent inference job on the same local model — increasing exactly the GPU
# occupancy, concurrency and context pressure this phase exists to contain.
#
# Everything else — authentication, non-retryable 4xx, 429, 5xx, connection
# refusal, the retry finding cap, and any already-valid review — is likewise
# terminal.
RETRY_ELIGIBLE_OUTCOMES: tuple[str, ...] = (
    "review_output_budget_exhausted",
    "review_unusable_output",
)

# Human-facing wording for each classification. Kept here so the CLI, the packet
# and the error message cannot drift into calling a parse error a "stall".
ATTEMPT_OUTCOME_LABELS: dict[str, str] = {
    "valid_review": "a strict, schema-valid review",
    "review_stalled": (
        "stalled — AIDO stopped waiting, either because the client reported a "
        "request timeout or because AIDO's own attempt deadline expired first. "
        "Neither the in-flight request nor the backend's inference state is "
        "observed: both may still be running, so this outcome is TERMINAL and no "
        "second request is issued"
    ),
    "review_output_budget_exhausted": (
        "output budget exhausted — the provider reported a length finish_reason "
        "and no valid review resulted"
    ),
    "review_unusable_output": (
        "unusable output — a response was returned and the strict parser "
        "rejected it (never repaired)"
    ),
    "review_retry_finding_cap_exceeded": (
        f"unusable output — the compact retry returned more than "
        f"{COMPACT_RETRY_MAX_FINDINGS} findings, which the retry contract "
        "rejects rather than truncates"
    ),
    "reviewer_auth_failed": "authentication rejected by the endpoint",
    "reviewer_response_error": (
        "the endpoint returned an error status or a malformed body"
    ),
    "reviewer_transport_failed": "a connection/transport failure",
}

# The notes that keep the packet honest. Each states a limit rather than a
# reassurance, and none of them may be softened.
SUPERVISION_TIMEOUT_NOTE = (
    "attempt_timeout_seconds bounds how long AIDO waits for ONE reviewer "
    "HTTP/model call, and that bound is established by AIDO's own monotonic "
    "attempt deadline in the supervisor — NOT by the client's timeout, which is "
    "a network-operation/inactivity timeout that a peer producing frequent "
    "activity can outlive. The client still receives the same value as a "
    "secondary network-inactivity timeout. It is NOT a process-style hard "
    "wall-clock kill: when the deadline wins, the worker performing the call is "
    "ABANDONED, not stopped, and AIDO does NOT observe or claim that the backend "
    "stopped inference when the client timed out — backend cancellation "
    "semantics are outside this phase's observation boundary. Because neither "
    "release is observed, a stalled attempt is TERMINAL in RS1: no compact retry "
    "is issued after a timeout, since a second request could place a second "
    "concurrent inference job on the same model."
)

SUPERVISION_WAIT_BOUND_NOTE = (
    "How AIDO's wait is bounded, exactly. One semantic attempt runs its single "
    "client call on one daemon worker thread and publishes either the response "
    "or the raised exception; the main thread waits to an AIDO-owned monotonic "
    "deadline and owns the decision. If the deadline expires first, the attempt "
    "is classified review_stalled and AIDO stops waiting — it does not join that "
    "worker, issue any second request, close its socket, ask a backend to cancel "
    "anything, or claim the worker stopped. The worker is ABANDONED: its "
    "lifetime, its HTTP request's lifetime, and any backend inference are all "
    "unobserved and unbounded here, the HTTP-side equivalent of the accepted "
    "Phase 5F2D abandoned-reader limitation. Because a stall is terminal, one "
    "command invocation can leave at most one abandoned reviewer worker. No "
    "executor, worker pool, worker registry, task framework, process, or asyncio "
    "machinery is used, and no thread is killed."
)

# Backend-scoped, and therefore a string rather than a boolean: AIDO observes
# nothing about the model's own lifetime once it stops waiting. Conditional for
# the same reason as `ABANDONED_WORKER_LIFETIME_IF_DEADLINE_EXPIRES` above — a
# stall is terminal, so a successful packet never describes one that happened.
BACKEND_INFERENCE_LIFETIME_IF_STALLED = (
    "Conditional policy, not a record of this run: IF a reviewer attempt stalls, "
    "backend inference lifetime is not observed — the model may still be running "
    "and holding its slot and context after AIDO stops waiting. Such an attempt "
    "is a terminal stall, so no successful review packet can describe one: this "
    "field never asserts that it happened."
)

SUPERVISION_SCOPE_NOTE = (
    "What this supervision bounds, exactly: AIDO's reviewer REQUEST ISSUANCE and "
    "AIDO's WAIT budget. It proves that AIDO issued zero transport retries, that "
    "AIDO issued at most 2 semantic requests, that each attempt's wait was bound "
    "by an AIDO-owned monotonic deadline (the supervisor's, not the client's "
    "network-inactivity timeout), which output cap was requested, and that a "
    "second request was issued only after a COMPLETED but unusable response. It "
    "does NOT prove any bound on the abandoned worker's lifetime, the HTTP "
    "request's lifetime after AIDO stops waiting, backend inference lifetime "
    "after a timeout, GPU occupancy lifetime after a client disconnect, backend "
    "context lifetime, or server-side cancellation latency. Total backend/GPU "
    "time is NOT bounded by this phase and is not claimed to be."
)

SUPERVISION_COMPACT_RETRY_NOTE = (
    "The one compact retry is available only for a COMPLETED but unusable first "
    "response — output-budget exhaustion or a strict-parser rejection — because "
    "in those cases the first response actually came back and the first request "
    "is no longer an unknown in-flight operation. It is never issued after a "
    "timeout, an authentication failure, a non-retryable 4xx, a 429, a 5xx, a "
    "connection failure, or an already-valid review. It is a separate, smaller "
    "review request using the SAME configured model: the rejected reply is "
    "never edited, partially mined, quoted back, or merged."
)

SUPERVISION_OUTPUT_CAP_NOTE = (
    "max_output_tokens is a REQUESTED model-output cap, sent as the "
    "OpenAI-compatible 'max_tokens' field. It is not a guarantee: provider "
    "semantics differ, and it says nothing about hidden reasoning or backend "
    "accounting. Reported usage is whatever the provider actually returned; when "
    "a provider returned none, usage is recorded as unknown rather than zero."
)

SUPERVISION_OBSERVABILITY_NOTE = (
    "This is observable resource supervision, not agent-progress supervision. "
    "The reviewer is a single non-streaming request with no tools, so AIDO "
    "observes only: whether the request returned or raised a typed client error, "
    "the finish_reason and usage the provider supplied, whether the content was "
    "empty, and whether the strict parser accepted it. AIDO deliberately does "
    "NOT observe private reasoning, reasoning repetition, time-to-first-token, "
    "time-to-first-finding, tool calls, files the reviewer inspected, or tests "
    "the reviewer ran. None of those are observable in this architecture and "
    "none are reported."
)

SUPERVISION_RETRY_OWNERSHIP_NOTE = (
    "Retry ownership is explicit. The generic LLM client keeps its bounded "
    "transport retries for other callers; the controlled reviewer forces "
    "max_retries=0, so one semantic attempt is exactly one HTTP/model request "
    "and this supervisor owns the only second attempt. The maximum number of "
    "semantic requests AIDO may ISSUE is two, and there is no third, no "
    "retry-on-timeout, no fallback model, and no second reviewer."
)


class _Strict(BaseModel):
    """Base model that rejects unknown fields, so forged extras fail loudly."""

    model_config = ConfigDict(extra="forbid")


class ReviewAttemptRecord(_Strict):
    """Safe, auditable metadata about **one** semantic reviewer attempt.

    Deliberately absent, because there is no field for any of them: the prompt,
    the raw completion, the approved diff, the reviewer's private reasoning, an
    API key, a base URL, an absolute path, or any timing claim finer than the
    elapsed wall time this process measured.

    ``usage_reported`` exists so a missing usage block reads as *unknown* rather
    than as zero tokens. ``elapsed_seconds`` is measured with a monotonic clock
    around AIDO's own call; it is **not** a claim about backend inference time.
    On a supervisor-deadline stall it is how long **AIDO waited** before
    declaring the attempt stalled, and says nothing about how long the request or
    any backend inference eventually ran.

    ``stall_source`` is ``None`` unless the outcome is ``review_stalled``. It
    exists for truthful auditing rather than for control flow: only
    ``supervisor_deadline`` implies an abandoned worker thread.
    """

    attempt: int
    kind: ReviewAttemptKind
    outcome: ReviewAttemptOutcome
    transport_requests: Literal[TRANSPORT_REQUESTS_PER_ATTEMPT]  # type: ignore[valid-type]
    requested_max_output_tokens: int
    finish_reason: str | None
    usage_reported: bool
    usage: LLMUsage | None
    elapsed_seconds: float
    stall_source: StallSource | None = None


class ReviewSupervisionBlock(_Strict):
    """The reviewer-attempt accounting carried by ``review-packet.v2``.

    Every field is about **AIDO's own** reviewer stage. None of them says anything
    about the verification child process, whose facts stay inside the embedded
    verification report where they were honestly established.

    Two kinds of field live here, and conflating them is exactly the bug this
    class must not reintroduce:

    - **facts about this run** — ``semantic_attempts_used``, ``compact_retry_used``,
      ``first_attempt_outcome``, ``final_attempt_outcome``, and each
      :class:`ReviewAttemptRecord` in ``attempts`` with its ``outcome`` and
      ``stall_source``;
    - **conditional policy** — ``timeout_attempt_is_terminal``,
      ``backend_inference_lifetime_if_stalled`` and
      ``abandoned_worker_lifetime_if_supervisor_deadline_expires``, which describe
      what would and would not be known **if** a stall were to occur.

    A supervision block only ever reaches a packet on the success path: a stall is
    terminal, raises
    :class:`~ai_dev_orchestrator.review.models.ReviewerAttemptExhaustedError`, and
    the command exits 4 with no packet. So in **every** packet that exists, no
    attempt outcome is ``review_stalled``, every ``stall_source`` is ``None``, and
    no abandoned worker was left behind — and the conditional fields are worded
    from an explicit "IF" so a reader cannot mistake them for a record of one.
    """

    supervision_enabled: Literal[True]
    supervision_scope: Literal["orchestrator_request_issuance_and_wait_budget"]
    max_semantic_attempts: Literal[MAX_SEMANTIC_REVIEW_ATTEMPTS]  # type: ignore[valid-type]
    semantic_attempts_used: int
    transport_retries_per_attempt: Literal[REVIEWER_TRANSPORT_MAX_RETRIES]  # type: ignore[valid-type]
    transport_requests_per_attempt: Literal[TRANSPORT_REQUESTS_PER_ATTEMPT]  # type: ignore[valid-type]

    compact_retry_enabled: bool
    compact_retry_used: bool
    compact_retry_finding_cap: Literal[COMPACT_RETRY_MAX_FINDINGS]  # type: ignore[valid-type]
    # The FU1 contract, as a field rather than only as prose: a client timeout
    # never buys a second request, because the backend's release of its inference
    # slot is unobserved.
    timeout_attempt_is_terminal: Literal[True]
    # The FU2 contract: what actually bounds AIDO's wait. Stated as a token so a
    # reader cannot mistake the client's network-inactivity timeout for the
    # proof.
    attempt_wait_bound: Literal[ATTEMPT_WAIT_BOUND]  # type: ignore[valid-type]
    # The two CONDITIONAL residual-limit statements. Both are strings rather than
    # booleans — the Phase 5F2D `child_process_*` precedent, since AIDO observes
    # neither and must not claim in either direction — and both are worded from an
    # explicit "IF", because a stall is terminal and therefore **cannot** have
    # occurred in any invocation that produced this packet. They describe what
    # would and would not be known after a future stall; they never assert that
    # one happened. See `attempts[*].outcome` and `attempts[*].stall_source` for
    # what this run actually did.
    backend_inference_lifetime_if_stalled: Literal[  # type: ignore[valid-type]
        BACKEND_INFERENCE_LIFETIME_IF_STALLED
    ]
    abandoned_worker_lifetime_if_supervisor_deadline_expires: Literal[  # type: ignore[valid-type]
        ABANDONED_WORKER_LIFETIME_IF_DEADLINE_EXPIRES
    ]

    configured_attempt_timeout_seconds: float
    requested_max_output_tokens: int

    first_attempt_outcome: ReviewAttemptOutcome
    final_attempt_outcome: ReviewAttemptOutcome
    attempts: list[ReviewAttemptRecord]

    same_model_used_for_every_attempt: Literal[True]
    fallback_reviewer_model_available: Literal[False]

    supervision_scope_note: str
    retry_ownership_note: str
    compact_retry_policy_note: str
    timeout_semantics_note: str
    wait_bound_note: str
    output_cap_note: str
    observability_note: str


class ReviewSupervisionEvent:
    """One safe, human-facing circuit-breaker signal.

    Three kinds, and the difference between the first two is load-bearing:

    - ``stalled`` — AIDO stopped waiting, because the client reported a timeout
      or because AIDO's own attempt deadline expired first. **Terminal**: no
      compact retry follows it, because AIDO observes neither whether the request
      ended nor whether the backend released its inference slot. It is always
      followed by an ``unavailable`` event;
    - ``unusable`` — a response was **returned** and was unusable (output budget
      exhausted, or rejected by the strict parser), and the project authorized
      the one compact retry, which is about to be issued;
    - ``unavailable`` — the terminal notice, emitted once no further attempt is
      authorized.

    Carries only the reviewer **model name**, the attempt counters, and a
    classification token. It deliberately has no field for the prompt, the diff,
    the completion, an API key, a base URL, or an absolute path — so a CLI that
    renders it cannot print one.
    """

    __slots__ = (
        "kind",
        "model",
        "attempt",
        "max_attempts",
        "outcome",
        "outcome_label",
        "attempts_used",
        "compact_retry_enabled",
    )

    def __init__(
        self,
        *,
        kind: Literal["stalled", "unusable", "unavailable"],
        model: str,
        attempt: int,
        max_attempts: int,
        outcome: str,
        outcome_label: str,
        attempts_used: int,
        compact_retry_enabled: bool,
    ) -> None:
        self.kind = kind
        self.model = model
        self.attempt = attempt
        self.max_attempts = max_attempts
        self.outcome = outcome
        self.outcome_label = outcome_label
        self.attempts_used = attempts_used
        self.compact_retry_enabled = compact_retry_enabled


class SupervisedReviewOutcome:
    """A valid review plus the accounting that proves how it was obtained."""

    __slots__ = ("review", "usage", "supervision")

    def __init__(
        self,
        *,
        review: ModelReviewResult,
        usage: LLMUsage | None,
        supervision: ReviewSupervisionBlock,
    ) -> None:
        self.review = review
        self.usage = usage
        self.supervision = supervision


class _AttemptResult:
    """Internal: what one attempt produced, before any policy is applied."""

    __slots__ = ("record", "review", "usage")

    def __init__(
        self,
        *,
        record: ReviewAttemptRecord,
        review: ModelReviewResult | None,
        usage: LLMUsage | None,
    ) -> None:
        self.record = record
        self.review = review
        self.usage = usage


class _ReviewerAttemptDeadlineExceeded(Exception):
    """Internal: AIDO's own wait deadline expired before the worker published.

    Never leaves this module and is never surfaced to a caller: it is translated
    immediately into the ``review_stalled`` classification, which is the same
    outcome a client-reported timeout produces.
    """


class _ReviewerAttemptSlot:
    """A one-shot publication box between the worker and the supervisor.

    Deliberately not a queue, a future, or a task object. The worker writes
    exactly one of the two fields and then sets ``done``; ``Event.set`` /
    ``Event.wait`` provide the ordering, so no extra lock is needed. The
    supervisor reads it **only** after ``done`` is set, and if the deadline wins
    it never reads it at all.
    """

    __slots__ = ("response", "error", "done")

    def __init__(self) -> None:
        self.response: LLMResponse | None = None
        self.error: BaseException | None = None
        self.done = threading.Event()


def _publish_reviewer_call(
    client: "LLMClient", request: LLMRequest, slot: _ReviewerAttemptSlot
) -> None:
    """The worker body. Performs the one blocking call and publishes the result.

    It does exactly ``client.chat(request)`` and nothing else: no classification,
    no parsing, no retry, no timing, no logging, and no decision. Every exception
    is captured and republished so the supervisor can re-raise it on the main
    thread and behave exactly as a direct call would have.

    The client is **not** closed here and must not be closed by anyone else while
    this call may still be running: ``LLMClient.chat`` owns and closes any
    temporary transport client it created, if and when it returns.
    """
    try:
        slot.response = client.chat(request)
    except BaseException as exc:  # noqa: BLE001 - republished verbatim below.
        slot.error = exc
    finally:
        slot.done.set()


def _await_reviewer_response(
    request: LLMRequest,
    *,
    client: "LLMClient",
    attempt_timeout_seconds: float,
) -> LLMResponse:
    """Run one ``client.chat`` call under AIDO's own wall-clock deadline.

    This is the FU2 correction, and it is deliberately the smallest mechanism
    that can establish the claim. The client's own timeout is a
    network-operation/inactivity timeout: a peer producing frequent activity can
    keep a request open past ``attempt_timeout_seconds`` without any individual
    read ever timing out. The deadline here fires on **total elapsed wait**
    regardless.

    Exactly one daemon worker per semantic attempt, and the main thread:

    - never joins the worker — not indefinitely, and not at all;
    - never kills it, closes its socket, or asks a backend to cancel anything;
    - never retries, and never issues a second request because of the deadline.

    ``Event.wait`` returns on a monotonic deadline and does not return early
    spuriously, so a single bounded wait is enough; no loop and no polling exist.

    Raises:
        _ReviewerAttemptDeadlineExceeded: The deadline expired first. The worker
            is abandoned, still possibly executing ``client.chat``, and AIDO
            makes no claim about its lifetime.
        BaseException: Whatever ``client.chat`` raised, re-raised unchanged on
            the main thread.
    """
    slot = _ReviewerAttemptSlot()
    worker = threading.Thread(
        target=_publish_reviewer_call,
        args=(client, request, slot),
        name=REVIEWER_ATTEMPT_THREAD_NAME,
        daemon=True,
    )
    worker.start()

    if not slot.done.wait(timeout=attempt_timeout_seconds):
        # AIDO's wait is over. The worker is NOT stopped, NOT joined, and NOT
        # waited for again; the caller classifies this as `review_stalled`, which
        # is terminal, so no second request follows it.
        raise _ReviewerAttemptDeadlineExceeded()

    if slot.error is not None:
        raise slot.error

    response = slot.response
    if response is None:  # pragma: no cover - the worker always sets one or the other.
        raise RuntimeError(
            "reviewer attempt worker published neither a response nor an error"
        )
    return response


def _finish_reason_means_output_budget(finish_reason: str | None) -> bool:
    """Whether the provider said the output budget, not the model, ended it."""
    if finish_reason is None:
        return False
    return finish_reason.strip().lower() in OUTPUT_BUDGET_FINISH_REASONS


def _classify_client_error(exc: Exception) -> ReviewAttemptOutcome:
    """Map a typed client error onto an attempt outcome.

    **None of these is retry-eligible.** Every one of them means no response came
    back, so the first request is either an unknown still in flight (a timeout) or
    a failure a shorter prompt cannot plausibly solve (authentication, a
    non-retryable 4xx, a 429, a 5xx, a connection failure). Because reviewer
    transport retries are zero, each surfaces once rather than being retried
    invisibly.
    """
    from ai_dev_orchestrator.llm.client import (
        LLMAuthError,
        LLMResponseError,
        LLMTimeoutError,
    )

    if isinstance(exc, LLMTimeoutError):
        return "review_stalled"
    if isinstance(exc, LLMAuthError):
        return "reviewer_auth_failed"
    if isinstance(exc, LLMResponseError):
        return "reviewer_response_error"
    return "reviewer_transport_failed"


def run_one_review_attempt(
    request: LLMRequest,
    *,
    client: "LLMClient",
    attempt: int,
    kind: ReviewAttemptKind,
    requested_max_output_tokens: int,
    attempt_timeout_seconds: float,
    monotonic: Callable[[], float] = time.monotonic,
) -> _AttemptResult:
    """Issue **one** reviewer request under AIDO's deadline and classify it.

    Exactly one :meth:`LLMClient.chat` call, which — because the reviewer client
    is built with ``max_retries=0`` — is exactly one HTTP/model request. Nothing
    here retries, re-prompts, repairs, or merges anything, and the deadline below
    never creates a second request.

    ``attempt_timeout_seconds`` is AIDO's own wall-clock wait bound, applied here
    by :func:`_await_reviewer_response`. The reviewer's client was separately
    configured with the same value as a *network-inactivity* timeout; that is a
    useful secondary bound and is explicitly **not** what establishes this one.
    Either mechanism ending the wait produces the same terminal
    ``review_stalled`` classification, distinguished only by ``stall_source``.

    The raw response text never leaves this function: a rejected reply becomes a
    classification, not an echoed string.
    """
    from ai_dev_orchestrator.llm.client import LLMClientError

    started = monotonic()

    def _record(
        outcome: ReviewAttemptOutcome,
        *,
        finish_reason: str | None = None,
        usage: LLMUsage | None = None,
        stall_source: StallSource | None = None,
    ) -> ReviewAttemptRecord:
        return ReviewAttemptRecord(
            attempt=attempt,
            kind=kind,
            outcome=outcome,
            transport_requests=TRANSPORT_REQUESTS_PER_ATTEMPT,
            requested_max_output_tokens=requested_max_output_tokens,
            finish_reason=finish_reason,
            usage_reported=usage is not None,
            usage=usage,
            elapsed_seconds=round(max(monotonic() - started, 0.0), 6),
            stall_source=stall_source,
        )

    try:
        response = _await_reviewer_response(
            request, client=client, attempt_timeout_seconds=attempt_timeout_seconds
        )
    except _ReviewerAttemptDeadlineExceeded:
        # AIDO's own deadline won. The worker is abandoned — not stopped, not
        # joined, not cancelled — and `review_stalled` is terminal, so this
        # attempt is the last request of the invocation.
        return _AttemptResult(
            record=_record("review_stalled", stall_source="supervisor_deadline"),
            review=None,
            usage=None,
        )
    except LLMClientError as exc:
        # Only the error class matters here. The client guarantees its own
        # message carries no API key, prompt, or completion, and this function
        # keeps even that out of the record.
        outcome = _classify_client_error(exc)
        return _AttemptResult(
            record=_record(
                outcome,
                stall_source=(
                    "client_timeout" if outcome == "review_stalled" else None
                ),
            ),
            review=None,
            usage=None,
        )

    finish_reason = response.finish_reason
    usage = response.usage

    try:
        review = parse_model_review_response(response.content)
    except ReviewError:
        # Rejected, never repaired: no fence stripping, no key renaming, no
        # partial-finding extraction, and no second prompt built from this reply.
        outcome: ReviewAttemptOutcome = (
            "review_output_budget_exhausted"
            if _finish_reason_means_output_budget(finish_reason)
            else "review_unusable_output"
        )
        return _AttemptResult(
            record=_record(outcome, finish_reason=finish_reason, usage=usage),
            review=None,
            usage=usage,
        )

    if kind == "compact" and len(review.findings) > COMPACT_RETRY_MAX_FINDINGS:
        # The retry-only cap, enforced after strict parsing rather than trusted
        # from the reply — and enforced by rejection, never by truncation.
        return _AttemptResult(
            record=_record(
                "review_retry_finding_cap_exceeded",
                finish_reason=finish_reason,
                usage=usage,
            ),
            review=None,
            usage=usage,
        )

    return _AttemptResult(
        record=_record("valid_review", finish_reason=finish_reason, usage=usage),
        review=review,
        usage=usage,
    )


def _build_supervision_block(
    *,
    records: list[ReviewAttemptRecord],
    compact_retry_enabled: bool,
    attempt_timeout_seconds: float,
    max_output_tokens: int,
) -> ReviewSupervisionBlock:
    return ReviewSupervisionBlock(
        supervision_enabled=True,
        supervision_scope="orchestrator_request_issuance_and_wait_budget",
        max_semantic_attempts=MAX_SEMANTIC_REVIEW_ATTEMPTS,
        semantic_attempts_used=len(records),
        transport_retries_per_attempt=REVIEWER_TRANSPORT_MAX_RETRIES,
        transport_requests_per_attempt=TRANSPORT_REQUESTS_PER_ATTEMPT,
        compact_retry_enabled=compact_retry_enabled,
        compact_retry_used=any(record.kind == "compact" for record in records),
        compact_retry_finding_cap=COMPACT_RETRY_MAX_FINDINGS,
        timeout_attempt_is_terminal=True,
        attempt_wait_bound=ATTEMPT_WAIT_BOUND,
        backend_inference_lifetime_if_stalled=BACKEND_INFERENCE_LIFETIME_IF_STALLED,
        abandoned_worker_lifetime_if_supervisor_deadline_expires=(
            ABANDONED_WORKER_LIFETIME_IF_DEADLINE_EXPIRES
        ),
        configured_attempt_timeout_seconds=attempt_timeout_seconds,
        requested_max_output_tokens=max_output_tokens,
        first_attempt_outcome=records[0].outcome,
        final_attempt_outcome=records[-1].outcome,
        attempts=list(records),
        same_model_used_for_every_attempt=True,
        fallback_reviewer_model_available=False,
        supervision_scope_note=SUPERVISION_SCOPE_NOTE,
        retry_ownership_note=SUPERVISION_RETRY_OWNERSHIP_NOTE,
        compact_retry_policy_note=SUPERVISION_COMPACT_RETRY_NOTE,
        timeout_semantics_note=SUPERVISION_TIMEOUT_NOTE,
        wait_bound_note=SUPERVISION_WAIT_BOUND_NOTE,
        output_cap_note=SUPERVISION_OUTPUT_CAP_NOTE,
        observability_note=SUPERVISION_OBSERVABILITY_NOTE,
    )


def run_supervised_review(
    context: ReviewContext,
    *,
    client: "LLMClient",
    model: str,
    attempt_timeout_seconds: float,
    max_output_tokens: int,
    compact_retry_on_unusable_output: bool,
    on_event: Callable[[ReviewSupervisionEvent], None] | None = None,
    monotonic: Callable[[], float] = time.monotonic,
) -> SupervisedReviewOutcome:
    """Issue at most two supervised semantic reviewer requests.

    Attempt 1 is the accepted Phase 5F2E full request, unchanged except for the
    configured ``max_tokens``. Attempt 2 exists only when the project enabled it
    **and** attempt 1 returned a **completed but unusable response** — an
    exhausted output budget, or output the strict parser rejected. It is the
    bounded compact request, using the **same** configured model and a strict
    subset of the same transmitted material.

    **A stall never buys attempt 2.** ``review_stalled`` is terminal, whether the
    client reported a timeout or AIDO's own deadline expired first: AIDO stopped
    waiting, but the request and the backend may both still be running, and a
    second request could make that worse rather than better.

    The two attempts are never merged. Attempt 1's reply is discarded whole: it
    is not repaired, not partially mined for findings, and not quoted into the
    second prompt.

    Args:
        context: The redacted transmission copy both requests are built from.
        client: The injected chat client, built with ``max_retries=0`` so one
            semantic attempt is one HTTP/model request.
        model: The exact ``controlled_review.model``, used for **every** attempt.
        attempt_timeout_seconds: **AIDO's own wall-clock wait bound** for each
            attempt, applied here as a monotonic deadline around the single
            ``client.chat`` call. The reviewer's client was separately configured
            with the same value as a network-inactivity timeout; that is a useful
            secondary bound and is explicitly not what establishes this one.
        max_output_tokens: The requested output cap placed on each request.
        compact_retry_on_unusable_output: The project opt-in for the one compact
            retry after a completed but unusable response.
        on_event: Optional sink for the human-facing circuit-breaker signals.
        monotonic: Injectable monotonic clock, so attempt timing is deterministic
            in tests. It measures AIDO's own wait, not backend inference time.

    Returns:
        A :class:`SupervisedReviewOutcome` when some attempt produced a valid
        review.

    Raises:
        ReviewerAttemptExhaustedError: No attempt produced a valid review and no
            further attempt is authorized. There is no third semantic request, no
            transport retry, no retry after a timeout, no fallback model, no
            fixer, no workspace mutation, no re-verification, and no repair or
            restore.
    """
    records: list[ReviewAttemptRecord] = []

    first = run_one_review_attempt(
        build_model_review_request(
            context, model=model, max_output_tokens=max_output_tokens
        ),
        client=client,
        attempt=1,
        kind="full",
        requested_max_output_tokens=max_output_tokens,
        attempt_timeout_seconds=attempt_timeout_seconds,
        monotonic=monotonic,
    )
    records.append(first.record)

    if first.review is not None:
        return SupervisedReviewOutcome(
            review=first.review,
            usage=first.usage,
            supervision=_build_supervision_block(
                records=records,
                compact_retry_enabled=compact_retry_on_unusable_output,
                attempt_timeout_seconds=attempt_timeout_seconds,
                max_output_tokens=max_output_tokens,
            ),
        )

    # A completed-but-unusable response is the ONLY thing that may buy a second
    # request. A timeout is not eligible, so this branch can never be reached with
    # `review_stalled` and the notice below is never a stall notice.
    retry_eligible = first.record.outcome in RETRY_ELIGIBLE_OUTCOMES
    if not (compact_retry_on_unusable_output and retry_eligible):
        raise _exhausted(
            records=records,
            model=model,
            compact_retry_enabled=compact_retry_on_unusable_output,
            on_event=on_event,
        )

    _emit(
        on_event,
        ReviewSupervisionEvent(
            kind="unusable",
            model=model,
            attempt=1,
            max_attempts=MAX_SEMANTIC_REVIEW_ATTEMPTS,
            outcome=first.record.outcome,
            outcome_label=ATTEMPT_OUTCOME_LABELS[first.record.outcome],
            attempts_used=1,
            compact_retry_enabled=compact_retry_on_unusable_output,
        ),
    )

    second = run_one_review_attempt(
        build_compact_model_review_request(
            context, model=model, max_output_tokens=max_output_tokens
        ),
        client=client,
        attempt=2,
        kind="compact",
        requested_max_output_tokens=max_output_tokens,
        attempt_timeout_seconds=attempt_timeout_seconds,
        monotonic=monotonic,
    )
    records.append(second.record)

    if second.review is not None:
        return SupervisedReviewOutcome(
            review=second.review,
            usage=second.usage,
            supervision=_build_supervision_block(
                records=records,
                compact_retry_enabled=compact_retry_on_unusable_output,
                attempt_timeout_seconds=attempt_timeout_seconds,
                max_output_tokens=max_output_tokens,
            ),
        )

    raise _exhausted(
        records=records,
        model=model,
        compact_retry_enabled=compact_retry_on_unusable_output,
        on_event=on_event,
    )


def _emit(
    on_event: Callable[[ReviewSupervisionEvent], None] | None,
    event: ReviewSupervisionEvent,
) -> None:
    if on_event is not None:
        on_event(event)


def _exhausted(
    *,
    records: list[ReviewAttemptRecord],
    model: str,
    compact_retry_enabled: bool,
    on_event: Callable[[ReviewSupervisionEvent], None] | None,
) -> ReviewerAttemptExhaustedError:
    """Announce the terminal reviewer failure and build the error to raise.

    When the run ended on a stall a **terminal** ``stalled`` notice is emitted
    first, so the human learns the one thing that distinguishes this failure from
    every other: AIDO stopped waiting, but the request and the backend may still
    be running. That notice is terminal wording — it never says a compact retry
    was authorized, because after a stall none ever is.

    The message names the final classification and the attempt counts and nothing
    else — no raw response, no prompt, no diff, no credential, no endpoint.
    """
    final = records[-1].outcome
    attempts_used = len(records)

    if final == "review_stalled":
        _emit(
            on_event,
            ReviewSupervisionEvent(
                kind="stalled",
                model=model,
                attempt=attempts_used,
                max_attempts=MAX_SEMANTIC_REVIEW_ATTEMPTS,
                outcome=final,
                outcome_label=ATTEMPT_OUTCOME_LABELS[final],
                attempts_used=attempts_used,
                compact_retry_enabled=compact_retry_enabled,
            ),
        )

    _emit(
        on_event,
        ReviewSupervisionEvent(
            kind="unavailable",
            model=model,
            attempt=attempts_used,
            max_attempts=MAX_SEMANTIC_REVIEW_ATTEMPTS,
            outcome=final,
            outcome_label=ATTEMPT_OUTCOME_LABELS[final],
            attempts_used=attempts_used,
            compact_retry_enabled=compact_retry_enabled,
        ),
    )

    stall_clause = ""
    if final == "review_stalled":
        source = records[-1].stall_source
        how = (
            "AIDO's own attempt deadline expired first, so the worker performing "
            "the call was ABANDONED — not stopped, not joined, and not cancelled"
            if source == "supervisor_deadline"
            else "the client reported a request timeout"
        )
        stall_clause = (
            f" The attempt stalled: {how}. AIDO stopped waiting, but neither the "
            "request's nor the backend's state is observed and both may still be "
            "running, so no second request was issued."
        )
    return ReviewerAttemptExhaustedError(
        "reviewer unavailable for this review: final classification "
        f"{final!r} ({ATTEMPT_OUTCOME_LABELS[final]}) after "
        f"{attempts_used} of at most {MAX_SEMANTIC_REVIEW_ATTEMPTS} supervised "
        f"semantic attempts, each exactly one HTTP/model request. No further "
        "semantic request, no transport retry, and no fallback reviewer model "
        f"were attempted; a human decision is required.{stall_clause}"
    )
