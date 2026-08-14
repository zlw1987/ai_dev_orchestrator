"""Verify first, review second — the Phase 5F2E composition.

This module is the ordering, and the ordering is the safety property::

    load + validate authority   (project config only; no credential is read)
              ↓
    verify_approved_file_edit(...)   (the ACCEPTED Phase 5F2D verifier)
              ↓
    verification outcome?
      refused                  → no model call, no reviewer environment read
      verification-failed      → no model call, no reviewer environment read
      workspace-state-untrusted→ no model call, no reviewer environment read
      verified                 → NOW load the LiteLLM environment and review

Why the command runs the verifier itself
----------------------------------------

Phase 5F2E does **not** run the writer. It starts from the exact state Phase
5F2C leaves behind — one approved ``modify`` applied, the approved post-image
present, exactly one Git-visible dirty path, the target a plain unstaged ``" M"``
— and it runs the **existing** Phase 5F2D verification internally rather than
accepting a verification result as input. There is deliberately no
``--verification-result`` option, and no previously saved result file is trusted
as authority.

That buys four things: the operator does not hand-carry a report between
commands; the verification is fresh for the review it informs; a reviewer
configuration, network, or parsing failure leaves the approved change intact and
the same command re-runnable; and reviewer credentials need not exist in AIDO's
process state while unsandboxed, repository-controlled verification code is
running.

Nothing here reinterprets or weakens Phase 5F2D. The verifier is **called**, not
copied: its Git proof, its state binding, its bounds and its report are used
exactly as accepted, and its refusal / not-passed / untrusted-workspace outcomes
keep their meanings and their exit semantics.

Credential ordering
-------------------

Before verification this module may read action flags, project config, the
approved diff artifact, the ``controlled_review`` block, and the configured
provider/model. It must **not** read ``AIDO_LITELLM_API_KEY``,
``AIDO_LITELLM_BASE_URL``, ``AIDO_LITELLM_DEFAULT_MODEL``, or any other reviewer
credential or endpoint value. The environment reader is **injected** and is
called only after the verifier returns ``verified``.

Reviewer failure semantics
--------------------------

Once verification has passed, a reviewer-stage failure — a missing or invalid
environment, a transport failure, a reply that is not strict JSON, or a
schema/consistency violation — raises
:class:`~ai_dev_orchestrator.review.models.ReviewerStageError`. **Scoped to
AIDO's review stage**: nothing is repaired or restored, no file is written into
the target workspace, no Git mutation is performed, no branch, commit, push or PR
happens, and the raw model response never appears in the error. The operator can
fix the reviewer configuration and run the same command again.

Phase 5F2E-RS1 changed exactly one thing about that: a project may opt into
**one** bounded compact second semantic request after a **completed but unusable**
first response — an exhausted output budget, or output the strict parser rejected
(see :mod:`~ai_dev_orchestrator.review.supervision`). That is a *separate,
smaller review request*, not a repair — attempt 1's reply is discarded whole,
never patched, never mined for partial findings, and never quoted back to the
model.

A **timeout is terminal**: AIDO stopped waiting, but it does not observe whether
the backend released its inference slot, so it never issues a second request that
could run concurrently with the first. The maximum number of semantic requests
AIDO may issue is two, always with the same configured model, and the reviewer
client is built with ``max_retries=0`` so each is exactly one HTTP/model request.

That scoping is not pedantry. By the time a reviewer-stage failure is possible,
the **unsandboxed** Phase 5F2D verification child has already run, and it may
have written Git-ignored files, written outside the repository, reached the
network, pushed, created a ref that leaves HEAD and the worktree unchanged, or
left descendants running. What is established about the workspace is exactly what
the passed verification established — the approved target's exact bytes, an
unchanged HEAD object id, and a Git-visible dirty state of exactly that one
unstaged path, subject to the same single-actor limitation. Phase 5F2E claims
nothing beyond Phase 5F2D's documented detection boundary and adds no detection
of its own.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from ai_dev_orchestrator.file_editing.models import ApprovedDiffProposalArtifact
from ai_dev_orchestrator.llm.config import LLMConfigError, load_llm_client_config_from_env
from ai_dev_orchestrator.llm.models import LLMClientConfig
from ai_dev_orchestrator.models import ProjectConfig
from ai_dev_orchestrator.plan.real_model_gate import (
    RealModelPlanningGateError,
    endpoint_host_from_base_url,
)
from ai_dev_orchestrator.review.models import (
    ModelReviewResult,
    ReviewerEnvironmentError,
    ReviewerStageError,
    ReviewerTransportError,
    ReviewRefusedError,
    parse_model_review_response,
)
from ai_dev_orchestrator.review.packet import ReviewPacket, build_review_packet
from ai_dev_orchestrator.review.request import (
    ReviewContext,
    build_model_review_request,
    build_review_context,
)
from ai_dev_orchestrator.review.supervision import (
    REVIEWER_TRANSPORT_MAX_RETRIES,
    ReviewSupervisionEvent,
    SupervisedReviewOutcome,
    run_supervised_review,
)
from ai_dev_orchestrator.verification import (
    VerificationResultReport,
    verify_approved_file_edit,
)

if TYPE_CHECKING:  # pragma: no cover - typing only, never imported at runtime.
    # Annotation-only. This module is *handed* a client factory; it must never be
    # able to build a real client itself, so the import stays out of globals.
    from ai_dev_orchestrator.llm.client import LLMClient

# The one supported reviewer provider: the existing internal OpenAI-compatible
# LiteLLM path. Matched with ``==`` — no alias, no case folding, no prefix.
SUPPORTED_REVIEW_PROVIDER = "litellm"

# The environment variable names the reviewer stage may read, and only after
# verification has returned `verified`. Named here so the ordering rule is a
# reviewable list rather than a comment.
REVIEWER_ENV_NAMES: tuple[str, ...] = (
    "AIDO_LITELLM_BASE_URL",
    "AIDO_LITELLM_API_KEY",
    "AIDO_LITELLM_DEFAULT_MODEL",
    "AIDO_LITELLM_TIMEOUT_SECONDS",
    "AIDO_LITELLM_MAX_RETRIES",
)


class ReviewerCallNotice:
    """The safe facts a caller may announce immediately before the real call.

    Deliberately carries no base URL, no API key, no absolute path, and no
    prompt text — only the model name, the endpoint **host**, and the coarse
    identity a human needs to recognize which run is about to transmit code.

    **There is deliberately no ``title`` field.** An issue title is free-form
    third-party text: it can contain newlines and banner-shaped lines, and the
    warning block it would appear in is a non-suppressible human-facing safety
    notice on stderr. Inside the prompt that text is contained by the
    untrusted-data delimiters, but a terminal has no such boundary, so a title
    could forge banner lines and misrepresent what is being transmitted. Rather
    than build terminal escaping or a sanitizer for one cosmetic field, the field
    is simply absent, and no caller can print what it does not have. The review
    packet and the model request still carry the real title, unchanged.

    ``project_id`` and ``repo`` are kept for a different reason: they identify the
    run, and both come from the **project config**, which this repository treats
    as trusted authority — unlike an issue title, which is third-party prose that
    arrives with the issue.

    That is a statement about *provenance*, not about validation. ``RepoConfig``
    does **not** currently enforce an ``owner/repo`` shape, and ``ProjectConfig``
    does not constrain ``project_id`` beyond requiring the field; an earlier
    version of this docstring claimed otherwise and was wrong. No validator was
    added merely to make the prose true, and no terminal-escaping machinery was
    added either: the operator writes the project config, so its contents are
    trusted here in exactly the way the rest of this repository trusts it.
    """

    __slots__ = ("model", "endpoint_host", "project_id", "repo", "issue_number")

    def __init__(
        self,
        *,
        model: str,
        endpoint_host: str,
        project_id: str,
        repo: str,
        issue_number: int,
    ) -> None:
        self.model = model
        self.endpoint_host = endpoint_host
        self.project_id = project_id
        self.repo = repo
        self.issue_number = issue_number


class ControlledReviewOutcome:
    """What one invocation produced.

    ``verification`` is always present once a verification process actually ran.
    ``packet`` is present only when the verification was ``verified`` *and* the
    reviewer produced a valid structured result — the two facts a caller needs to
    decide its exit code without re-deriving either.
    """

    __slots__ = ("verification", "packet")

    def __init__(
        self,
        *,
        verification: VerificationResultReport,
        packet: ReviewPacket | None,
    ) -> None:
        self.verification = verification
        self.packet = packet


def check_controlled_review_gate(project: ProjectConfig) -> str:
    """Validate the project's reviewer authority and return the exact model.

    Config-only, and fail-closed: an absent ``controlled_review`` block is
    identical to an explicitly disabled one, an unsupported provider is refused,
    and an enabled block without a model permits no review rather than falling
    back to a default.

    Reads **no** environment variable, builds no client, touches no workspace, and
    contacts nothing. ``real_model_planning`` is never consulted: planning
    authorization is not review authorization.

    Raises:
        ReviewRefusedError: The project does not authorize a reviewer model call.
    """
    settings = project.controlled_review

    if not settings.enabled:
        raise ReviewRefusedError(
            f"opt-in error: project {project.project_id!r} does not enable "
            "controlled review (controlled_review.enabled is false or the block "
            "is absent). Sending this project's source-derived diff to a "
            "reviewer model is opt-in per project, and real_model_planning does "
            "NOT authorize it. No workspace was touched, no environment value "
            "was read, and no model was contacted."
        )

    if settings.provider != SUPPORTED_REVIEW_PROVIDER:
        raise ReviewRefusedError(
            f"provider error: controlled_review.provider is "
            f"{settings.provider!r}, but the only supported reviewer provider is "
            f"{SUPPORTED_REVIEW_PROVIDER!r} (the existing internal "
            "OpenAI-compatible LiteLLM path). Nothing was contacted."
        )

    model = settings.model
    if model is None or not model.strip():
        raise ReviewRefusedError(
            f"model error: project {project.project_id!r} enables controlled "
            "review but names no controlled_review.model. There is no default "
            "reviewer model, the environment's default model may never select "
            "one, and there is no CLI override. Nothing was contacted."
        )

    return model


def build_reviewer_client_config(
    env: Mapping[str, str],
    *,
    model: str,
    attempt_timeout_seconds: float,
) -> LLMClientConfig:
    """Build validated connection settings for the reviewer call.

    ``env`` is **injected** — this function never falls back to ``os.environ``, so
    a caller cannot read reviewer credentials by accident or out of order.

    Three values are **overridden** rather than taken from the environment, and
    two of those overrides are load-bearing.

    ``default_model`` is replaced by the project-configured reviewer ``model``,
    exactly as the Phase 4J planning gate does for its own allowlisted model:
    ``AIDO_LITELLM_DEFAULT_MODEL`` supplies *connection* defaults and can never
    select *what is reviewed with*.

    ``timeout_seconds`` is replaced by the project's
    ``controlled_review.attempt_timeout_seconds``, so the reviewer's network
    timeout follows the project's declared reviewer budget rather than whatever
    generic value ``AIDO_LITELLM_TIMEOUT_SECONDS`` happens to carry.

    **What that timeout is, exactly.** It is the client's
    **network-operation/inactivity** timeout: it fires when an individual socket
    operation stalls, and a peer producing frequent activity can hold one request
    open past it without any single read ever timing out. It is therefore a useful
    *secondary* bound and **not** what establishes the invocation's wait bound.
    The wait bound is the reviewer supervisor's own monotonic deadline (Phase
    5F2E-RS1-FU2, see
    :func:`~ai_dev_orchestrator.review.supervision.run_one_review_attempt`), which
    fires on total elapsed wait whatever the network is doing. Both are set from
    the same configured ``attempt_timeout_seconds`` value.

    Neither mechanism proves that the HTTP request was cancelled or that backend
    inference terminated. Whichever fires, AIDO has stopped waiting — and that is
    the whole of the claim.

    ``max_retries`` is forced to :data:`REVIEWER_TRANSPORT_MAX_RETRIES` (zero),
    **overriding** any ``AIDO_LITELLM_MAX_RETRIES`` the environment supplied. That
    is Phase 5F2E-RS1's central rule: one semantic reviewer attempt must be
    exactly one HTTP/model request, so the supervisor — not the transport — owns
    any second attempt. Hidden transport retries would otherwise turn one
    timed-out semantic review of a local model into several full inference
    requests that nobody asked for and nothing recorded.

    **Only the reviewer is affected.** The generic
    :class:`~ai_dev_orchestrator.llm.client.LLMClient` keeps its shipped retry
    behavior, ``AIDO_LITELLM_MAX_RETRIES`` keeps its meaning for every other
    caller, and the planner and smoke-test paths are untouched.

    Raises:
        ReviewerEnvironmentError: A required ``AIDO_LITELLM_*`` value is missing,
            blank, or invalid, or the base URL does not reduce to a host. The
            message never echoes the API key or the base URL.
    """
    if env is None or not isinstance(env, Mapping):
        raise ReviewerEnvironmentError(
            "an environment mapping must be injected explicitly; the reviewer "
            "stage never reads the process environment on its own."
        )

    try:
        config = load_llm_client_config_from_env(env)
    except LLMConfigError as exc:
        raise ReviewerEnvironmentError(f"reviewer environment error: {exc}") from exc

    try:
        endpoint_host_from_base_url(config.base_url)
    except RealModelPlanningGateError as exc:
        # The helper is shared; its error type is not. A reviewer environment
        # failure is not a planning-gate failure.
        raise ReviewerEnvironmentError(f"reviewer endpoint error: {exc}") from exc

    return LLMClientConfig(
        base_url=config.base_url,
        api_key=config.api_key,
        default_model=model,
        timeout_seconds=attempt_timeout_seconds,
        max_retries=REVIEWER_TRANSPORT_MAX_RETRIES,
    )


def request_model_review(
    context: ReviewContext,
    *,
    client: "LLMClient",
    model: str,
    max_output_tokens: int | None = None,
) -> tuple[ModelReviewResult, object]:
    """Send **one** semantic reviewer request and parse the reply strictly.

    The low-level single-attempt path, kept for direct use and for tests. The
    command itself goes through
    :func:`~ai_dev_orchestrator.review.supervision.run_supervised_review`, which
    owns the bounded two-attempt policy.

    The client is always supplied by the caller: this module constructs none, and
    imports no transport. Exactly one :meth:`chat` call is made here — and,
    because a reviewer client is built with ``max_retries=0``, exactly one
    HTTP/model request. There is no application-level retry in this function, no
    second prompt, and no "fix your JSON" round trip.

    Returns the validated review and the response's usage block (or ``None``).

    Raises:
        ReviewerTransportError: The client failed under its own existing policy.
        ReviewParseError, ReviewValidationError: The reply was not exactly one
            strict, schema-valid, internally consistent JSON object.
    """
    from ai_dev_orchestrator.llm.client import LLMClientError

    request = build_model_review_request(
        context, model=model, max_output_tokens=max_output_tokens
    )
    try:
        response = client.chat(request)
    except LLMClientError as exc:
        # The raw response, the prompt and the diff never appear here; only the
        # error class and its own message, which the client guarantees is free of
        # the API key, the prompt, and the completion.
        raise ReviewerTransportError(
            f"reviewer transport error: {type(exc).__name__}: {exc}"
        ) from exc

    review = parse_model_review_response(response.content)
    return review, response.usage


def run_controlled_review(
    *,
    approved_diff: ApprovedDiffProposalArtifact,
    project: ProjectConfig,
    read_env: Callable[[], Mapping[str, str]],
    client_factory: Callable[[LLMClientConfig], "LLMClient"],
    on_before_model_call: Callable[[ReviewerCallNotice], None] | None = None,
    on_supervision_event: Callable[[ReviewSupervisionEvent], None] | None = None,
    monotonic: Callable[[], float] | None = None,
) -> ControlledReviewOutcome:
    """Verify one applied approved change, then review it — in that order.

    Args:
        approved_diff: The same validated ``approved-diff-proposal.v2`` approval
            the writer and the verifier consume.
        project: The project config the approval must match exactly, whose
            ``controlled_verification`` block authorizes the verification process
            and whose ``controlled_review`` block authorizes the reviewer model.
        read_env: **Injected** reader for the ``AIDO_LITELLM_*`` names. It is
            called only after the verifier returns ``verified``, and never
            before.
        client_factory: **Injected** builder for the chat client. The only thing
            in this flow that can reach a socket.
        on_before_model_call: Optional callback invoked with a
            :class:`ReviewerCallNotice` immediately before the real reviewer
            call, so a CLI can warn on stderr while the socket still does not
            exist.
        on_supervision_event: Optional sink for the Phase 5F2E-RS1
            circuit-breaker signals — the terminal "review stalled" notice, the
            "review unusable" notice printed before the one compact retry, and
            the terminal "reviewer unavailable" notice. Each event carries only
            the model name, attempt counters and a classification token.
        monotonic: Optional injected monotonic clock for attempt timing, so unit
            tests can assert durations deterministically. It measures AIDO's own
            wait and is never presented as backend inference time.

    Returns:
        A :class:`ControlledReviewOutcome`. A ``packet`` of ``None`` means a
        verification process ran and its outcome was not ``verified``; the
        verification report carries the whole story, no model was contacted, and
        no reviewer environment value was read.

    Raises:
        ReviewRefusedError: The project does not authorize controlled review.
            Nothing was verified, read, or contacted.
        VerificationRefusedError: Propagated unchanged from Phase 5F2D — a gate
            failed and no project process was started.
        ReviewerStageError: Verification passed but the reviewer stage failed.
            Model output was never repaired, and nothing in the workspace was
            restored. AIDO may have issued the one authorized compact second
            request — only after a completed but unusable first response, never
            after a timeout — and never more than two semantic requests in total.
    """
    # 1. Reviewer authority, from trusted project config only. Checked BEFORE the
    #    verification runs so a project that could never be reviewed does not
    #    cause repository-controlled code to be executed on its behalf.
    model = check_controlled_review_gate(project)
    # The Phase 5F2E-RS1 supervision settings come from the same trusted block and
    # were bounds-checked at load. They are plain policy numbers — no credential,
    # no endpoint — so reading them here does not breach the credential ordering.
    review_settings = project.controlled_review

    # 2. The accepted Phase 5F2D verifier, called — not duplicated. Its refusal
    #    propagates unchanged. No reviewer credential exists in this process yet.
    verification = verify_approved_file_edit(
        approved_diff=approved_diff, project=project
    )

    # 3. Any outcome other than `verified` ends here: no environment read, no
    #    client, no model call. The caller reports the verification result and
    #    preserves its exit semantics.
    if verification.outcome != "verified":
        return ControlledReviewOutcome(verification=verification, packet=None)

    # 4. Only now may reviewer credentials enter this process.
    env = read_env()
    config = build_reviewer_client_config(
        env,
        model=model,
        attempt_timeout_seconds=review_settings.attempt_timeout_seconds,
    )
    try:
        endpoint_host = endpoint_host_from_base_url(config.base_url)
    except RealModelPlanningGateError as exc:  # pragma: no cover - defensive
        raise ReviewerEnvironmentError(f"reviewer endpoint error: {exc}") from exc

    # Defensive: the config builder pins the model to the project-configured one.
    # If that ever stops holding, fail closed rather than review with a model the
    # project never named.
    if config.default_model != model:  # pragma: no cover - defensive
        raise ReviewerEnvironmentError(
            "internal reviewer configuration inconsistency: the validated "
            "configuration does not name the project-configured reviewer model."
        )

    # 5. The redacted transmission copy. The artifact and the verification report
    #    are not mutated.
    context = build_review_context(
        approved_diff=approved_diff, verification=verification
    )

    if on_before_model_call is not None:
        on_before_model_call(
            ReviewerCallNotice(
                model=model,
                endpoint_host=endpoint_host,
                project_id=verification.project_id,
                repo=verification.repo,
                issue_number=verification.issue_number,
            )
        )

    # 6. At most two supervised semantic reviewer requests, each exactly one
    #    HTTP/model request, each strictly parsed and never repaired. A second
    #    request is issued ONLY after a completed but unusable first response —
    #    never after a timeout, whose backend state AIDO cannot observe.
    client = client_factory(config)
    supervised: SupervisedReviewOutcome = run_supervised_review(
        context,
        client=client,
        model=model,
        attempt_timeout_seconds=review_settings.attempt_timeout_seconds,
        max_output_tokens=review_settings.max_output_tokens,
        compact_retry_on_unusable_output=(
            review_settings.compact_retry_on_unusable_output
        ),
        on_event=on_supervision_event,
        **({} if monotonic is None else {"monotonic": monotonic}),
    )

    packet = build_review_packet(
        verification=verification,
        context=context,
        review=supervised.review,
        model=model,
        endpoint_host=endpoint_host,
        usage=supervised.usage,
        supervision=supervised.supervision,
    )
    return ControlledReviewOutcome(verification=verification, packet=packet)
