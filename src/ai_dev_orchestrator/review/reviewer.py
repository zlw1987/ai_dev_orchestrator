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
      verified                 → NOW select and load the CONFIGURED PROVIDER's
                                 environment, and review

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
``AIDO_LITELLM_BASE_URL``, ``AIDO_LITELLM_DEFAULT_MODEL``, ``AIDO_VLLM_BASE_URL``,
``AIDO_VLLM_API_KEY``, or any other reviewer credential or endpoint value. The
environment reader is **injected**, is handed the configured provider, and is
called only after the verifier returns ``verified``.

**Only the configured provider's names are ever read** (Phase 5F2E-V1-FU1). The
provider resolves to an exact name tuple *before* any environment is touched, so
a vLLM review never reads an ``AIDO_LITELLM_*`` value and a LiteLLM review never
reads an ``AIDO_VLLM_*`` value. V1 originally snapshotted both families and
discarded the unconfigured one afterwards; reading a credential and then dropping
it is still reading it, so that was corrected rather than re-documented.

Two reviewer providers, one ordering (Phase 5F2E-V1)
----------------------------------------------------

``controlled_review.provider`` selects between the existing internal
OpenAI-compatible LiteLLM path (``"litellm"``) and a direct OpenAI-compatible
vLLM endpoint (``"vllm"``). Matching is exact and case-sensitive; there is no
alias, no case folding, no glob, and no provider registry — just one explicit
branch. Everything else is shared: the same prompt, the same strict parser, the
same Phase 5F2E-RS1 supervision, and the same single ``LLMClient``.

The **model** is provider-independent and comes only from
``controlled_review.model``. Neither provider has an environment default-model
variable that could select one: the LiteLLM path overrides
``AIDO_LITELLM_DEFAULT_MODEL``, and the vLLM path has no such name at all.

Direct vLLM transport is refused over plaintext HTTP unless the project set
``controlled_review.vllm_allow_insecure_http``. That opt-in is an
acknowledgement, not a security property — see
:data:`VLLM_INSECURE_HTTP_OPT_IN_MEANING`. The rule is **not** applied to the
LiteLLM provider, whose accepted deployments predate it.

Structured vLLM output (Phase 5F2E-V2)
---------------------------------------

``controlled_review.vllm_structured_output`` adds one **generation constraint**
to the direct-vLLM path: the request carries the ``ModelReviewResult`` JSON
Schema in the OpenAI-compatible ``response_format``/``json_schema`` field, so the
server constrains what the model may emit.

It exists because of an observed compatibility failure, not a theory. A
controlled trial against a direct vLLM endpoint returned HTTP 200 with
``finish_reason="stop"`` and a review that correctly identified a seeded semantic
bug — wrapped in a ```` ```json ```` markdown fence, which the strict parser
rejected. **The reasoning was not the problem; the envelope was.** The identical
prompt with a JSON-Schema ``response_format`` produced one bare JSON object the
*unmodified* parser accepted.

Four properties are load-bearing:

- **the parser is unchanged and final.** Nothing strips a fence, extracts JSON,
  renames a field, coerces a type, or repairs a verdict. A schema-valid reply
  that violates an AIDO-only Pydantic validator is still rejected;
- **the schema is generated, never hand-maintained**, from the same class the
  parser validates against — see
  :func:`~ai_dev_orchestrator.review.request.build_review_response_format`;
- **both possible requests carry it.** The full attempt and the one bounded RS1
  compact retry expect the same output shape, so they send the same schema;
  there is no smaller second schema;
- **there is no fallback.** A server that rejects the schema — an HTTP 400, a
  structured-decoding 5xx — is an ordinary reviewer-stage request failure.
  AIDO never re-issues the request without ``response_format``: that would be an
  unauthorized fallback and would break RS1's retry ownership.

The opt-in applies to ``provider: "vllm"`` only. Setting it with any other
provider is **refused at the gate**, never silently ignored. LiteLLM sends no
``response_format`` from this feature at all.

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
from urllib.parse import urlsplit

from pydantic import ValidationError

from ai_dev_orchestrator.file_editing.models import ApprovedDiffProposalArtifact
from ai_dev_orchestrator.llm.config import LLMConfigError, load_llm_client_config_from_env
from ai_dev_orchestrator.llm.models import (
    LLMClientConfig,
    LLMJSONSchemaResponseFormat,
)
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
    STRUCTURED_OUTPUT_MODE_JSON_SCHEMA,
    STRUCTURED_OUTPUT_MODE_NONE,
    ReviewContext,
    build_model_review_request,
    build_review_context,
    build_review_response_format,
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

# The two supported reviewer providers, matched with ``==`` — no alias, no case
# folding, no prefix, no glob, no registry, and no plugin lookup. Phase 5F2E-V1
# added the second one; a small explicit branch dispatches them, deliberately
# rather than a generic "OpenAI-compatible provider" abstraction.
#
#   "litellm" — the existing internal OpenAI-compatible LiteLLM path, unchanged.
#               It remains supported for when internal infrastructure returns.
#   "vllm"    — a direct OpenAI-compatible vLLM endpoint, named by environment.
#
REVIEW_PROVIDER_LITELLM = "litellm"
REVIEW_PROVIDER_VLLM = "vllm"
SUPPORTED_REVIEW_PROVIDERS: tuple[str, ...] = (
    REVIEW_PROVIDER_LITELLM,
    REVIEW_PROVIDER_VLLM,
)

# The environment variable names the reviewer stage may read, and only after
# verification has returned `verified`. Named here so the ordering rule is a
# reviewable list rather than a comment.
#
# The LiteLLM contract is untouched by Phase 5F2E-V1: the same five names, loaded
# by the same shipped loader, with the same required/optional split.
LITELLM_REVIEWER_ENV_NAMES: tuple[str, ...] = (
    "AIDO_LITELLM_BASE_URL",
    "AIDO_LITELLM_API_KEY",
    "AIDO_LITELLM_DEFAULT_MODEL",
    "AIDO_LITELLM_TIMEOUT_SECONDS",
    "AIDO_LITELLM_MAX_RETRIES",
)

# The direct-vLLM contract is deliberately smaller: one required endpoint and one
# optional credential. There is **no** ``AIDO_VLLM_DEFAULT_MODEL``, because the
# reviewer model may only come from ``project_config.controlled_review.model``
# and an environment default must never be able to select one.
VLLM_ENV_BASE_URL = "AIDO_VLLM_BASE_URL"
VLLM_ENV_API_KEY = "AIDO_VLLM_API_KEY"
VLLM_REVIEWER_ENV_NAMES: tuple[str, ...] = (VLLM_ENV_BASE_URL, VLLM_ENV_API_KEY)

# The whole runtime read authority: which exact names the reviewer stage may
# read, given the configured provider. There is deliberately **no union**
# constant used as read authority. Phase 5F2E-V1-FU1 removed one, because a union
# is exactly what let the reader touch the unconfigured provider's names and
# discard them afterwards — reading a credential and then dropping it is still
# reading it.
#
# The provider is resolved to this exact tuple **before** any environment is
# accessed. See :func:`reviewer_env_names_for_provider`.
REVIEWER_ENV_NAMES_BY_PROVIDER: dict[str, tuple[str, ...]] = {
    REVIEW_PROVIDER_LITELLM: LITELLM_REVIEWER_ENV_NAMES,
    REVIEW_PROVIDER_VLLM: VLLM_REVIEWER_ENV_NAMES,
}

# A keyless vLLM server still receives an ``Authorization: Bearer ...`` header
# because the existing OpenAI-compatible client shape always sends one and
# ``LLMClientConfig.api_key`` is a required non-blank string. Rather than weaken
# that model for every caller, the vLLM path substitutes this fixed, non-secret
# literal when no ``AIDO_VLLM_API_KEY`` is set.
#
# It is NOT a credential and must never be described as authentication: it
# carries no secret, grants no access, and proves nothing about the endpoint.
VLLM_COMPATIBILITY_PLACEHOLDER_API_KEY = "no_api_key"

# The endpoint schemes a reviewer transport may use. Anything else is refused
# before a client is built — ``httpx`` could not have spoken it anyway.
SUPPORTED_ENDPOINT_SCHEMES: tuple[str, ...] = ("http", "https")

# What the explicit insecure-HTTP opt-in does and does not mean, stated once so
# no message, packet field, or document can quietly upgrade it.
VLLM_INSECURE_HTTP_OPT_IN_MEANING = (
    "controlled_review.vllm_allow_insecure_http records ONLY that this project "
    "explicitly permits source-derived reviewer material to be sent over direct "
    "vLLM PLAINTEXT HTTP transport. It does NOT make that transport secure, "
    "encrypted, private, authenticated, company-approved, or safe for secrets, "
    "and an internal, colleague-hosted, or same-network endpoint is not private "
    "merely because of where it sits."
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

    Phase 5F2E-V1 added ``provider``, ``endpoint_scheme`` and ``transport_tls``
    for one reason: a human about to send source-derived code deserves to know
    whether it is going over TLS. All three are derived from trusted project
    config and the validated connection settings — never from model output, and
    never from the base URL's path, query or userinfo, none of which is carried
    here.

    Phase 5F2E-V2 added ``structured_output_mode`` for the same reason at a
    smaller scale: it names whether the request will carry a JSON-Schema
    generation constraint. It is a **mode token** (``"none"`` or
    ``"json_schema"``) and never the schema document, so nothing large or
    surprising can reach the terminal through it.

    That is a statement about *provenance*, not about validation. ``RepoConfig``
    does **not** currently enforce an ``owner/repo`` shape, and ``ProjectConfig``
    does not constrain ``project_id`` beyond requiring the field; an earlier
    version of this docstring claimed otherwise and was wrong. No validator was
    added merely to make the prose true, and no terminal-escaping machinery was
    added either: the operator writes the project config, so its contents are
    trusted here in exactly the way the rest of this repository trusts it.
    """

    __slots__ = (
        "provider",
        "model",
        "endpoint_host",
        "endpoint_scheme",
        "transport_tls",
        "structured_output_mode",
        "project_id",
        "repo",
        "issue_number",
    )

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        endpoint_host: str,
        endpoint_scheme: str,
        transport_tls: bool,
        structured_output_mode: str = STRUCTURED_OUTPUT_MODE_NONE,
        project_id: str,
        repo: str,
        issue_number: int,
    ) -> None:
        self.provider = provider
        self.model = model
        self.endpoint_host = endpoint_host
        self.endpoint_scheme = endpoint_scheme
        self.transport_tls = transport_tls
        self.structured_output_mode = structured_output_mode
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


class ReviewerAuthority:
    """What trusted project config authorizes: one provider, one model, one mode.

    All three halves are established **before** verification runs, so an
    unsupported provider, a missing model, or a structured-output setting that
    contradicts the provider refuses before this command causes any workspace
    access, launches repository-controlled code, reads an environment value,
    builds a client, or contacts a model.

    Deliberately not a config object: it carries no endpoint, no credential, no
    environment-variable name, and no timeout. It answers "may this project be
    reviewed, by which backend, with which exact model, and under which
    generation constraint", and nothing else.

    ``structured_output_mode`` (Phase 5F2E-V2) is
    :data:`~ai_dev_orchestrator.review.request.STRUCTURED_OUTPUT_MODE_NONE` or
    :data:`~ai_dev_orchestrator.review.request.STRUCTURED_OUTPUT_MODE_JSON_SCHEMA`.
    It is **orchestrator-owned provenance**, derived here from trusted project
    config alone — never from model output, an environment value, or a CLI flag.
    """

    __slots__ = ("provider", "model", "structured_output_mode")

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        structured_output_mode: str = STRUCTURED_OUTPUT_MODE_NONE,
    ) -> None:
        self.provider = provider
        self.model = model
        self.structured_output_mode = structured_output_mode


def check_controlled_review_gate(project: ProjectConfig) -> ReviewerAuthority:
    """Validate the project's reviewer authority: the provider and exact model.

    Config-only, and fail-closed: an absent ``controlled_review`` block is
    identical to an explicitly disabled one, an unsupported provider is refused,
    and an enabled block without a model permits no review rather than falling
    back to a default.

    Provider matching is exact and **case-sensitive**. ``"LiteLLM"``, ``"VLLM"``,
    ``"openai"`` and ``"openai_compatible"`` are all refused: this phase
    dispatches two specifically named backends, not a family of compatible ones.

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

    if settings.provider not in SUPPORTED_REVIEW_PROVIDERS:
        supported = ", ".join(repr(name) for name in SUPPORTED_REVIEW_PROVIDERS)
        raise ReviewRefusedError(
            f"provider error: controlled_review.provider is "
            f"{settings.provider!r}, but the supported reviewer providers are "
            f"exactly {supported} — the existing internal OpenAI-compatible "
            "LiteLLM path, and a direct OpenAI-compatible vLLM endpoint. "
            "Matching is exact and case-sensitive: there is no alias, no case "
            "folding, no glob, and no generic OpenAI-compatible provider. "
            "Nothing was contacted."
        )

    model = settings.model
    if model is None or not model.strip():
        raise ReviewRefusedError(
            f"model error: project {project.project_id!r} enables controlled "
            "review but names no controlled_review.model. There is no default "
            "reviewer model, no environment variable of either provider may "
            "select one, and there is no CLI override. Nothing was contacted."
        )

    # Phase 5F2E-V2. The structured-output opt-in is vLLM-specific, and a
    # contradiction is REFUSED rather than silently ignored: quietly dropping a
    # setting an operator wrote would make the packet's provenance disagree with
    # the config that produced it.
    structured_output_mode = STRUCTURED_OUTPUT_MODE_NONE
    if settings.vllm_structured_output:
        if settings.provider != REVIEW_PROVIDER_VLLM:
            raise ReviewRefusedError(
                "structured output error: "
                "controlled_review.vllm_structured_output is true, but "
                f"controlled_review.provider is {settings.provider!r}. The "
                "JSON-Schema generation constraint applies to the "
                f"{REVIEW_PROVIDER_VLLM!r} provider only and is refused rather "
                "than ignored for any other. Either set the provider to "
                f"{REVIEW_PROVIDER_VLLM!r} or remove the structured-output "
                "opt-in. Nothing was contacted."
            )
        structured_output_mode = STRUCTURED_OUTPUT_MODE_JSON_SCHEMA

    return ReviewerAuthority(
        provider=settings.provider,
        model=model,
        structured_output_mode=structured_output_mode,
    )


def reviewer_env_names_for_provider(provider: str) -> tuple[str, ...]:
    """Return the exact environment names one provider's reviewer may read.

    This is the **only** thing that decides which names a reviewer environment
    reader touches, and it is answered from the provider alone — no environment
    access, no ``os.environ``, no default, no fallback, and no aliasing between
    the two name families.

    Phase 5F2E-V1-FU1 exists because of the ordering here. V1's reader snapshotted
    the union of both families from the real process environment and discarded
    the unconfigured provider's values afterwards; that is still *reading* them,
    and it contradicted the contract V1 documented. Now the provider resolves to
    an exact name tuple **first**, and only those names are ever looked up.

    A conforming reader is therefore:

    .. code-block:: python

        names = reviewer_env_names_for_provider(provider)   # no environment yet
        {name: environ[name] for name in names if name in environ}

    Raises:
        ReviewerEnvironmentError: ``provider`` names no reviewer environment
            contract. The gate refuses that far earlier; this is fail-closed
            defence for a caller that skipped it, and it fails **before** any
            environment name is resolved.
    """
    names = REVIEWER_ENV_NAMES_BY_PROVIDER.get(provider)
    if names is None:
        raise ReviewerEnvironmentError(
            f"reviewer provider error: {provider!r} names no reviewer "
            "environment contract. No environment value was read and nothing "
            "was contacted."
        )
    return names


def endpoint_scheme_from_base_url(base_url: str) -> str:
    """Reduce an endpoint base URL to ``"http"`` or ``"https"``.

    Pure string/URL parsing, like
    :func:`~ai_dev_orchestrator.plan.real_model_gate.endpoint_host_from_base_url`
    beside it: no DNS lookup, no connection, no filesystem access. The scheme is
    the one part of a URL that carries neither credential nor payload, so
    reporting it is safe — and a human deciding whether to transmit
    source-derived code needs it.

    Only ``http`` and ``https`` are accepted. Anything else is refused here
    rather than handed to ``httpx``, which could not have spoken it either.

    Raises:
        ReviewerEnvironmentError: The URL is blank, unparseable, or names an
            unsupported scheme. The message never echoes the URL, which may embed
            a credential in userinfo or a query string.
    """
    if not isinstance(base_url, str) or not base_url.strip():
        raise ReviewerEnvironmentError(
            "reviewer endpoint error: the endpoint base URL is missing or "
            "blank; refusing to derive a transport scheme."
        )

    try:
        scheme = urlsplit(base_url.strip()).scheme
    except ValueError as exc:  # pragma: no cover - defensive
        raise ReviewerEnvironmentError(
            "reviewer endpoint error: the endpoint base URL could not be parsed."
        ) from exc

    if scheme not in SUPPORTED_ENDPOINT_SCHEMES:
        supported = " or ".join(SUPPORTED_ENDPOINT_SCHEMES)
        raise ReviewerEnvironmentError(
            "reviewer endpoint error: the endpoint base URL must be an absolute "
            f"{supported} URL. The URL itself is not echoed."
        )
    return scheme


def _load_vllm_client_config(
    env: Mapping[str, str],
    *,
    model: str,
    attempt_timeout_seconds: float,
) -> LLMClientConfig:
    """Build connection settings for a **direct** OpenAI-compatible vLLM endpoint.

    A deliberately smaller contract than the LiteLLM loader's, because a direct
    vLLM server needs less:

    - ``AIDO_VLLM_BASE_URL`` — **required**, the endpoint's absolute
      OpenAI-compatible base URL (for example
      ``https://vllm.example.invalid/v1``);
    - ``AIDO_VLLM_API_KEY`` — **optional**, passed through as the client
      credential when it is set to a non-blank value.

    There is **no** ``AIDO_VLLM_DEFAULT_MODEL``, and no ``AIDO_LITELLM_*`` value
    is consulted, required, or accepted: the caller has already narrowed the
    mapping to this provider's two names. ``default_model`` is the exact
    project-configured reviewer model, so nothing in the environment can select
    what the review is performed with.

    **The keyless case.** A vLLM server started without ``--api-key`` accepts the
    OpenAI-compatible request regardless of the ``Authorization`` header, but
    :class:`~ai_dev_orchestrator.llm.models.LLMClientConfig` requires a non-blank
    ``api_key`` string and the shipped client always sends the header. Rather
    than make ``api_key`` optional for every caller — which would weaken a model
    that exists to keep the one credential copy in one place — the fixed literal
    :data:`VLLM_COMPATIBILITY_PLACEHOLDER_API_KEY` is substituted. It is a
    **compatibility placeholder, not a credential**: it carries no secret, grants
    no access, and is never described as authentication.

    Raises:
        ReviewerEnvironmentError: The base URL is missing, blank, or invalid. The
            message never echoes the base URL or the API key.
    """
    base_url = env.get(VLLM_ENV_BASE_URL)
    if base_url is None or not base_url.strip():
        raise ReviewerEnvironmentError(
            "reviewer environment error: the vLLM reviewer provider requires "
            f"{VLLM_ENV_BASE_URL} to be set to the endpoint's absolute "
            "OpenAI-compatible base URL. It is missing or blank. No "
            "AIDO_LITELLM_* variable substitutes for it, there is no "
            "AIDO_VLLM_DEFAULT_MODEL, and no model request was issued."
        )

    # Optional. A blank value is treated exactly as an absent one, so an empty
    # variable cannot become a blank Bearer token.
    supplied_key = env.get(VLLM_ENV_API_KEY)
    api_key = (
        supplied_key
        if supplied_key is not None and supplied_key.strip()
        else VLLM_COMPATIBILITY_PLACEHOLDER_API_KEY
    )

    try:
        return LLMClientConfig(
            base_url=base_url.strip(),
            api_key=api_key,
            default_model=model,
            timeout_seconds=attempt_timeout_seconds,
            max_retries=REVIEWER_TRANSPORT_MAX_RETRIES,
        )
    except ValidationError as exc:
        # Field names and constraints only — pydantic does not echo ``api_key``
        # into its message here, and the base URL failure mode is "blank", which
        # was already rejected above.
        raise ReviewerEnvironmentError(
            "reviewer environment error: the vLLM reviewer connection settings "
            f"are invalid: {exc.error_count()} field error(s). No value is "
            "echoed."
        ) from exc


def build_reviewer_client_config(
    env: Mapping[str, str],
    *,
    model: str,
    attempt_timeout_seconds: float,
    provider: str = REVIEW_PROVIDER_LITELLM,
    allow_insecure_http: bool = False,
) -> LLMClientConfig:
    """Build validated connection settings for the reviewer call.

    ``env`` is **injected** — this function never falls back to ``os.environ``, so
    a caller cannot read reviewer credentials by accident or out of order. It is
    expected to contain only ``provider``'s names — the reader resolves those via
    :func:`reviewer_env_names_for_provider` before touching any environment — and
    in any case each branch below reads only its own family, so a stray foreign
    name could not supply an endpoint, credential, or model.

    ``provider`` selects one of two explicit branches (Phase 5F2E-V1). Both end
    at the same :class:`~ai_dev_orchestrator.llm.models.LLMClientConfig` and the
    same single :class:`~ai_dev_orchestrator.llm.client.LLMClient`; there is no
    provider registry, no plugin lookup, and no generic OpenAI-compatible
    abstraction between them.

    - ``"litellm"`` uses the shipped ``AIDO_LITELLM_*`` loader, unchanged;
    - ``"vllm"`` uses the narrow ``AIDO_VLLM_*`` contract in
      :func:`_load_vllm_client_config`.

    **Insecure transport, vLLM only.** A direct vLLM endpoint reached over
    plaintext ``http`` is refused unless ``allow_insecure_http`` is true — that
    is, unless the project explicitly set
    ``controlled_review.vllm_allow_insecure_http``. The refusal happens here, in
    the same call that would otherwise produce the settings a client is built
    from, so no model request can be issued past it. The opt-in means only what
    :data:`VLLM_INSECURE_HTTP_OPT_IN_MEANING` says it means; it never upgrades,
    rewrites, or tunnels the URL, and it makes no claim of privacy. The rule is
    deliberately **not** applied to the LiteLLM provider, whose deployments were
    accepted before this phase existed.

    Three values are **overridden** rather than taken from the environment, and
    two of those overrides are load-bearing.

    ``default_model`` is replaced by the project-configured reviewer ``model``,
    exactly as the Phase 4J planning gate does for its own allowlisted model:
    ``AIDO_LITELLM_DEFAULT_MODEL`` supplies *connection* defaults and can never
    select *what is reviewed with*. The vLLM branch has no default-model variable
    at all, so the same property holds there by construction.

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
        ReviewerEnvironmentError: The provider is unsupported; a required
            environment value is missing, blank, or invalid; the base URL does
            not reduce to a host or a supported scheme; or a direct vLLM endpoint
            is plaintext ``http`` without the explicit project opt-in. The message
            never echoes the API key or the base URL.
    """
    if env is None or not isinstance(env, Mapping):
        raise ReviewerEnvironmentError(
            "an environment mapping must be injected explicitly; the reviewer "
            "stage never reads the process environment on its own."
        )

    if provider == REVIEW_PROVIDER_LITELLM:
        try:
            loaded = load_llm_client_config_from_env(env)
        except LLMConfigError as exc:
            raise ReviewerEnvironmentError(
                f"reviewer environment error: {exc}"
            ) from exc
        config = LLMClientConfig(
            base_url=loaded.base_url,
            api_key=loaded.api_key,
            default_model=model,
            timeout_seconds=attempt_timeout_seconds,
            max_retries=REVIEWER_TRANSPORT_MAX_RETRIES,
        )
    elif provider == REVIEW_PROVIDER_VLLM:
        config = _load_vllm_client_config(
            env, model=model, attempt_timeout_seconds=attempt_timeout_seconds
        )
    else:
        raise ReviewerEnvironmentError(
            f"reviewer provider error: {provider!r} is not a supported reviewer "
            "provider. Nothing was contacted."
        )

    try:
        endpoint_host_from_base_url(config.base_url)
    except RealModelPlanningGateError as exc:
        # The helper is shared; its error type is not. A reviewer environment
        # failure is not a planning-gate failure.
        raise ReviewerEnvironmentError(f"reviewer endpoint error: {exc}") from exc

    scheme = endpoint_scheme_from_base_url(config.base_url)

    # The insecure-transport gate. vLLM only, and it refuses BEFORE a client
    # exists, so no model request can be issued past this point. Nothing here
    # upgrades the scheme, rewrites the URL, or tunnels the connection.
    if (
        provider == REVIEW_PROVIDER_VLLM
        and scheme == "http"
        and not allow_insecure_http
    ):
        raise ReviewerEnvironmentError(
            "reviewer transport error: the configured direct vLLM endpoint uses "
            "PLAINTEXT HTTP, which would send this project's source-derived "
            "diff, plan prose and verification output unencrypted. That is "
            "refused by default. Set controlled_review.vllm_allow_insecure_http "
            "to true only if this project accepts that. "
            + VLLM_INSECURE_HTTP_OPT_IN_MEANING
            + " No model request was issued, and the base URL is not echoed."
        )

    return config


def request_model_review(
    context: ReviewContext,
    *,
    client: "LLMClient",
    model: str,
    max_output_tokens: int | None = None,
    response_format: LLMJSONSchemaResponseFormat | None = None,
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
        context,
        model=model,
        max_output_tokens=max_output_tokens,
        response_format=response_format,
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
    read_env: Callable[[str], Mapping[str, str]],
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
        read_env: **Injected** reader, called as ``read_env(provider)`` with the
            configured provider name. It is called **once**, only after the
            verifier returns ``verified``, and never before. The provider
            argument is not advisory: a conforming reader resolves it to that
            provider's exact names via
            :func:`reviewer_env_names_for_provider` **before** touching any
            environment, so the unconfigured provider's names are never read at
            all — not read-then-discarded.
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
    authority = check_controlled_review_gate(project)
    provider = authority.provider
    model = authority.model
    # Phase 5F2E-V2, orchestrator-owned provenance: which generation constraint
    # trusted project config authorized. Resolved here, before verification, so
    # a provider/opt-in contradiction refuses before anything runs.
    structured_output_mode = authority.structured_output_mode
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

    # 4. Only now may reviewer credentials enter this process — and only the
    #    configured provider's names. The provider is handed to the reader, which
    #    resolves it to an exact name tuple before touching any environment, so
    #    the other provider's names are never read (Phase 5F2E-V1-FU1).
    env = read_env(provider)
    config = build_reviewer_client_config(
        env,
        model=model,
        attempt_timeout_seconds=review_settings.attempt_timeout_seconds,
        provider=provider,
        allow_insecure_http=review_settings.vllm_allow_insecure_http,
    )
    try:
        endpoint_host = endpoint_host_from_base_url(config.base_url)
    except RealModelPlanningGateError as exc:  # pragma: no cover - defensive
        raise ReviewerEnvironmentError(f"reviewer endpoint error: {exc}") from exc
    # Already validated inside the config builder; re-derived here so the notice
    # and the packet report the scheme of the URL a client will actually use.
    endpoint_scheme = endpoint_scheme_from_base_url(config.base_url)
    transport_tls = endpoint_scheme == "https"

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
                provider=provider,
                model=model,
                endpoint_host=endpoint_host,
                endpoint_scheme=endpoint_scheme,
                transport_tls=transport_tls,
                structured_output_mode=structured_output_mode,
                project_id=verification.project_id,
                repo=verification.repo,
                issue_number=verification.issue_number,
            )
        )

    # 6. At most two supervised semantic reviewer requests, each exactly one
    #    HTTP/model request, each strictly parsed and never repaired. A second
    #    request is issued ONLY after a completed but unusable first response —
    #    never after a timeout, whose backend state AIDO cannot observe.
    #    When structured output is authorized, BOTH possible requests carry the
    #    same generated schema. A server that rejects it is an ordinary
    #    reviewer-stage failure: AIDO never re-issues the request unstructured,
    #    because that would be an unauthorized fallback and would break the
    #    accepted retry-ownership rule.
    response_format = (
        build_review_response_format()
        if structured_output_mode == STRUCTURED_OUTPUT_MODE_JSON_SCHEMA
        else None
    )
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
        response_format=response_format,
        on_event=on_supervision_event,
        **({} if monotonic is None else {"monotonic": monotonic}),
    )

    packet = build_review_packet(
        verification=verification,
        context=context,
        review=supervised.review,
        provider=provider,
        model=model,
        endpoint_host=endpoint_host,
        endpoint_scheme=endpoint_scheme,
        structured_output_mode=structured_output_mode,
        usage=supervised.usage,
        supervision=supervised.supervision,
    )
    return ControlledReviewOutcome(verification=verification, packet=packet)
