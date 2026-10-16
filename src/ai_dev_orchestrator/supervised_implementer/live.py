"""The live supervised implementer (ALPHA-P1B, DEC-SUP-LIVE).

Two entry points, reached only from the two CLI commands:

- :func:`prepare_supervised_implementation` re-derives everything one run would
  send, offline, and returns an authorization **draft**. It reads no provider
  environment variable, builds no client, and contacts nothing. A draft grants
  nothing.
- :func:`run_supervised_implementation` consumes one human-completed,
  single-use authorization. It re-derives every bound value in-process and
  compares each one exactly; only then reads the configured provider's
  environment, checks the endpoint against the human-typed consent, consumes
  the authorization in the durable ledger (:mod:`.live_ledger`, ALPHA-P1B-FU1)
  by one exclusive create, records a pending state, announces the
  transmission, and issues **exactly one** request through AIDO's own bounded
  counting transport under AIDO's own monotonic wait deadline. A reply is
  turned into a diff proposal by the unchanged P1A/5E3 path, and the run
  **stops** before human exact-diff approval (H6).

The model proposes file content and nothing else: no path, change type,
command, approval, retry, endpoint, model or lifecycle transition. Nothing here
opens a workspace file for writing, creates an approval, applies a diff, runs
verification, commits or pushes. The only workspace access is the shipped 5D2
bounded read and the 5F2C writer's read-only Git preflight (D-6 / R-1).

**Scope of the guarantees (A-19).** These are properties of AIDO's entry
points. No library function is a security boundary against other Python code
in the same process: such code can call ``LLMClient`` or private helpers
directly. The parameters whose names start with an underscore are private test
seams, not supported API.

See ``docs/PHASE_ALPHA_P1B_LIVE_IMPLEMENTER_AUTHORITY_DESIGN.md`` (§11 is
authoritative) and ``docs/PHASE_ALPHA_P1B_SUPERVISED_IMPLEMENTER_LIVE.md``.
"""

from __future__ import annotations

import math
import os
import secrets
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated, Literal
from urllib.parse import urlsplit

import httpx
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    StrictBool,
    StrictInt,
    StrictStr,
    ValidationError,
    model_validator,
)

from ai_dev_orchestrator import __version__
from ai_dev_orchestrator.diff_proposal.models import DiffProposalArtifact, _summarize_validation_error
from ai_dev_orchestrator.handoff.models import ApprovedL1PlanArtifact
from ai_dev_orchestrator.llm.client import (
    LLMAuthError,
    LLMClient,
    LLMClientError,
    LLMResponseError,
    LLMTimeoutError,
    LLMTransportError,
)
from ai_dev_orchestrator.llm.config import (
    ENV_API_KEY,
    ENV_BASE_URL,
    ENV_DEFAULT_MODEL,
    ENV_MAX_RETRIES,
    ENV_TIMEOUT_SECONDS,
    LLMConfigError,
    load_llm_client_config_from_env,
)
from ai_dev_orchestrator.llm.models import LLMClientConfig, LLMRequest, LLMResponse
from ai_dev_orchestrator.models import ProjectConfig, SupervisedImplementerConfig
from ai_dev_orchestrator.supervised_implementer.identity import (
    QUALIFICATION_CREDIT,
    SUPERVISED_IMPLEMENTER_ROLE,
)
from ai_dev_orchestrator.supervised_implementer.implementer import (
    TRANSPORT_MAX_RETRIES,
    SupervisedImplementerSettings,
    _ApprovedSource,
    _check_identity,
    _check_target_path,
    _private_copies,
    _proposal_from_reply,
    _read_approved_source,
    _usage,
    check_supervised_implementer_endpoint,
    check_supervised_implementer_gate,
)
from ai_dev_orchestrator.supervised_implementer.live_authorization import (
    AUTH_TTL,
    AUTHORIZATION_SCHEMA_VERSION,
    AUTHORIZATION_STAGE,
    CONSENT_CLOCK_SKEW,
    CONSENT_TEXT,
    MAX_RESPONSE_BODY_BYTES,
    PLAINTEXT_ACKNOWLEDGEMENT,
    AuthorizationBound,
    AwareTimestamp,
    ExactOne,
    ExactZero,
    Hex64,
    StrictFalse,
    TimeoutSeconds,
    canonical_json_bytes,
    compute_binding_sha256,
    parse_authorization,
    parse_timestamp,
    render_authorization_draft,
    sha256_hex,
    utc_timestamp,
)
from ai_dev_orchestrator.supervised_implementer.live_ledger import (
    LedgerSpentUnsettled,
    check_unspent,
    consume_issuance,
    issue_authorization,
    new_issuance_nonce,
)
from ai_dev_orchestrator.supervised_implementer.live_transport import (
    BoundedCountingTransport,
    LiveTransportViolation,
    OutboundExpectation,
    ResponseTooLarge,
    SupervisorDeadlineExpired,
    TransportObservation,
    await_one_response,
)
from ai_dev_orchestrator.supervised_implementer.live_workspace import (
    observe_clean_workspace_head,
)
from ai_dev_orchestrator.supervised_implementer.models import (
    MODEL_SOURCE,
    NEXT_STEP,
    ReportedUsage,
    SupervisedImplementerOutputRejected,
    SupervisedImplementerRefused,
    check_diff_agrees_with_content_provenance,
)
from ai_dev_orchestrator.supervised_implementer.request import (
    build_supervised_implementer_request,
)

#: D-2: the only provider the live path accepts.
LIVE_PROVIDER = "litellm"

#: D-3: the exact names the live path may read, and only for ``litellm``.
LIVE_LITELLM_ENV_NAMES: tuple[str, ...] = (
    ENV_BASE_URL,
    ENV_API_KEY,
    ENV_DEFAULT_MODEL,
    ENV_TIMEOUT_SECONDS,
    ENV_MAX_RETRIES,
)

TRANSPORT_KIND_LIVE = "live_http"
PROVENANCE_V2_SCHEMA_VERSION = "supervised-implementer-provenance.v2"
OUTCOME_SCHEMA_VERSION = "supervised-implementer-run-outcome.v1"
PENDING_SCHEMA_VERSION = "supervised-implementer-transmission-pending.v1"
WORKSPACE_GIT_STATE = "clean_tree_at_head_target_tracked_ordinary_blob"
NEXT_STEP_AFTER_FAILURE = "prepare_a_new_authorization"

#: Evidence file names under ``<evidence_dir>/<run_id>/``.
CONSUMED_FILE = "CONSUMED"
AUTHORIZATION_FILE = "authorization.json"
REQUEST_FILE = "request-messages.json"
PENDING_FILE = "transmission-pending.json"
RESPONSE_FILE = "response-content.txt"
DIFF_FILE = "diff-proposal.json"
PROVENANCE_FILE = "provenance.json"
OUTCOME_FILE = "outcome.json"

# Fixed, conditional wording (RS1 precedent): these describe what is true IF a
# stall happens. They are never a record that one did.
BACKEND_LIFETIME_IF_STALLED = (
    "IF a stall occurs: not observed. AIDO stops waiting at its deadline; the "
    "HTTP request and the backend's inference may continue. No cancellation is "
    "requested and none is observed."
)
WORKER_LIFETIME_IF_DEADLINE_EXPIRES = (
    "IF AIDO's deadline expires: the worker thread performing the request is "
    "abandoned, not stopped, and may outlive AIDO's wait. Its lifetime is "
    "neither bounded nor observed."
)

_LIVE_ASSUMPTION_TEMPLATE = (
    "The proposed content was authored by supervised implementer candidate "
    "{candidate} (model {model}) through one live HTTP request (run {run_id}), "
    "from one approved file read in-process by the Phase 5D2 reader. A separate "
    "supervised-implementer provenance record binds it by SHA-256. That record "
    "is not evidence of correctness and confers no qualification."
)


def _refuse(category: str, message: str) -> SupervisedImplementerRefused:
    return SupervisedImplementerRefused(category, message)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# -- Gates ---------------------------------------------------------------------


@dataclass(frozen=True)
class LiveSettings:
    """The live gate's resolved view: P1A's settings plus the live-only fields."""

    base: SupervisedImplementerSettings
    attempt_timeout_seconds: float
    authorization_ledger_dir: str


def check_supervised_implementer_live_gate(config: SupervisedImplementerConfig) -> LiveSettings:
    """P1A's gate, then the live-only rules. Exact types only; reads nothing else."""
    base = check_supervised_implementer_gate(config)
    if config.live_transmission_enabled is not True:
        raise _refuse(
            "live_not_enabled",
            "this project does not permit the live supervised implementer "
            "(supervised_implementer.live_transmission_enabled is not true). "
            "'enabled' alone never reaches a live client. Nothing was read or sent.",
        )
    if base.provider != LIVE_PROVIDER:
        raise _refuse(
            "live_provider_not_authorized",
            "the live supervised implementer is authorized for provider "
            "'litellm' only (D-2). Nothing was read or sent.",
        )
    if base.structured_output is not False:
        raise _refuse(
            "structured_output_not_authorized_for_live",
            "structured output is disabled for the live supervised implementer "
            "until its exact supported mode is established and separately "
            "authorized (D-9). Set supervised_implementer.structured_output to "
            "false. Nothing was read or sent.",
        )
    timeout = config.attempt_timeout_seconds
    if timeout is None:
        raise _refuse(
            "attempt_timeout_required",
            "supervised_implementer.attempt_timeout_seconds must be set explicitly "
            "for the live path; there is no default (D-4). Nothing was read or sent.",
        )
    if type(timeout) is not float or not math.isfinite(timeout) or not 0 < timeout <= 3600:
        raise _refuse(
            "config_wrong_type",
            "supervised_implementer.attempt_timeout_seconds must be a finite "
            "number greater than 0 and at most 3600.",
        )
    ledger = config.authorization_ledger_dir
    if ledger is None:
        raise _refuse(
            "authorization_ledger_required",
            "supervised_implementer.authorization_ledger_dir must name the durable "
            "single-use authorization ledger for the live path; there is no "
            "default (ALPHA-P1B-FU1). Nothing was read or sent.",
        )
    if type(ledger) is not str or not ledger or not os.path.isabs(ledger):
        raise _refuse(
            "authorization_ledger_invalid",
            "supervised_implementer.authorization_ledger_dir must be an absolute "
            "path. Nothing was read or sent.",
        )
    return LiveSettings(
        base=base, attempt_timeout_seconds=timeout, authorization_ledger_dir=ledger
    )


def _require_windows() -> None:
    if sys.platform != "win32":
        raise _refuse(
            "platform_unsupported",
            "the live supervised implementer observes the workspace with the "
            "5F2C writer's Git preflight, and that writer is Windows-only. "
            "Nothing was read or sent.",
        )


def supervised_implementer_env_names_for_provider(provider: object) -> tuple[str, ...]:
    """The exact environment names one live run may read, from the provider alone.

    Answered before any environment access. Only ``litellm`` has names (D-2,
    D-3); anything else refuses without resolving a single name.
    """
    if type(provider) is str and provider == LIVE_PROVIDER:
        return LIVE_LITELLM_ENV_NAMES
    raise _refuse(
        "live_provider_not_authorized",
        "no environment contract exists for this provider on the live path. "
        "No environment value was read.",
    )


# -- Endpoint ------------------------------------------------------------------


@dataclass(frozen=True)
class LiveEndpoint:
    scheme: str
    host: str
    port: int
    path_sha256: str
    chat_url: str


def _default_port(scheme: str) -> int:
    return 443 if scheme == "https" else 80


def check_live_endpoint(base_url: object, *, allow_insecure_http: bool) -> LiveEndpoint:
    """P1A's endpoint rules, tightened for the live path (A-5, R-6). Never echoes the URL."""
    if type(base_url) is not str:
        raise _refuse("endpoint_invalid", "the endpoint base URL is not a string.")
    if (
        not base_url.isascii()
        or any(ord(char) <= 32 or ord(char) == 127 for char in base_url)
        or any(char in base_url for char in "\\@?#")
    ):
        raise _refuse(
            "endpoint_invalid",
            "the endpoint base URL contains whitespace, a control character, a "
            "backslash, '@', a query, a fragment, or non-ASCII text. It is not "
            "echoed.",
        )
    scheme, host = check_supervised_implementer_endpoint(
        base_url, allow_insecure_http=allow_insecure_http
    )
    parts = urlsplit(base_url)
    try:
        explicit_port = parts.port
    except ValueError:
        raise _refuse("endpoint_invalid", "the endpoint base URL has an invalid port.") from None
    port = explicit_port if explicit_port is not None else _default_port(scheme)
    try:
        parsed = httpx.URL(base_url)
    except Exception:  # noqa: BLE001 - httpx raises several types; none is echoed.
        raise _refuse("endpoint_invalid", "the endpoint base URL could not be parsed.") from None
    parsed_port = parsed.port if parsed.port is not None else _default_port(parsed.scheme)
    if parsed.scheme != scheme or parsed.host != host or parsed_port != port:
        raise _refuse(
            "endpoint_parser_disagreement",
            "two URL parsers disagree about the endpoint's scheme, host or port, "
            "so which host would be contacted is ambiguous. It is not echoed.",
        )
    return LiveEndpoint(
        scheme=scheme,
        host=host,
        port=port,
        path_sha256=sha256_hex(parts.path.encode("utf-8")),
        chat_url=f"{base_url.rstrip('/')}/chat/completions",
    )


# -- The exact request ---------------------------------------------------------


def wire_payload(request: LLMRequest) -> dict:
    """The exact JSON body the shipped client sends for ``request``.

    It mirrors ``LLMClient._build_payload``. If the two ever drift, the
    transport wrapper refuses the outbound body before it reaches the network
    (fail closed), so a drift cannot send unconsented content.
    """
    if request.response_format is not None:
        raise _refuse(
            "structured_output_not_authorized_for_live",
            "the live path never sends a response_format (D-9).",
        )
    payload: dict[str, object] = {
        "model": request.model,
        "messages": [
            {"role": message.role, "content": message.content} for message in request.messages
        ],
    }
    if request.temperature is not None:
        payload["temperature"] = request.temperature
    if request.max_tokens is not None:
        payload["max_tokens"] = request.max_tokens
    return payload


def request_payload_sha256(request: LLMRequest) -> str:
    return sha256_hex(canonical_json_bytes(wire_payload(request)))


# -- Evidence directory ----------------------------------------------------------


def _same_or_under(candidate: str, root: str) -> bool:
    candidate_key = os.path.normcase(candidate)
    root_key = os.path.normcase(root)
    return candidate_key == root_key or candidate_key.startswith(root_key.rstrip(os.sep) + os.sep)


def _canonical_outside_dir(
    path: object, project: ProjectConfig, *, prefix: str, label: str
) -> tuple[str, str]:
    """Return ``(canonical_path, digest)`` for an existing directory outside the workspace.

    Used for the evidence directory (R-12, A-14) and the authorization ledger
    (ALPHA-P1B-FU1). Categories are ``<prefix>_invalid``, ``_inside_workspace``,
    ``_linked`` and ``_missing``. The path is never echoed.
    """
    if type(path) is not str or not path:
        raise _refuse(f"{prefix}_invalid", f"the {label} must be a path.")
    lexical = os.path.abspath(path)
    workspace_lexical = os.path.abspath(project.repo.workspace_path)
    if _same_or_under(lexical, workspace_lexical):
        raise _refuse(
            f"{prefix}_inside_workspace",
            f"the {label} is inside the configured workspace. It must live "
            "outside it. Nothing was read or sent.",
        )
    canonical = os.path.realpath(lexical)
    if _same_or_under(canonical, os.path.realpath(workspace_lexical)):
        raise _refuse(
            f"{prefix}_inside_workspace",
            f"the {label} resolves inside the configured workspace. "
            "Nothing was read or sent.",
        )
    if os.path.normcase(canonical) != os.path.normcase(lexical):
        raise _refuse(
            f"{prefix}_linked",
            f"the {label} path passes through a link, junction or non-canonical "
            "spelling. Name its canonical path. Nothing was read or sent.",
        )
    if not os.path.isdir(canonical):
        raise _refuse(
            f"{prefix}_missing",
            f"the {label} does not exist or is not a directory. Create it first; "
            "a missing directory is never treated as an empty one. Nothing was "
            "read or sent.",
        )
    digest = sha256_hex(os.path.normcase(canonical).encode("utf-8"))
    return canonical, digest


def _canonical_evidence_dir(evidence_dir: object, project: ProjectConfig) -> tuple[str, str]:
    return _canonical_outside_dir(
        evidence_dir, project, prefix="evidence_dir", label="evidence directory"
    )


def _canonical_ledger_dir(
    settings: LiveSettings, project: ProjectConfig, evidence_root: str
) -> tuple[str, str]:
    """The ledger, which must also be disjoint from the evidence directory (FU1).

    Run evidence is routinely deleted, rotated and archived; the ledger must not
    share that lifecycle, so neither directory may contain the other.
    """
    ledger_root, digest = _canonical_outside_dir(
        settings.authorization_ledger_dir,
        project,
        prefix="authorization_ledger",
        label="authorization ledger directory",
    )
    if _same_or_under(ledger_root, evidence_root) or _same_or_under(evidence_root, ledger_root):
        raise _refuse(
            "authorization_ledger_not_independent",
            "the authorization ledger and the evidence directory overlap. The "
            "ledger must not share the evidence directory's lifecycle. Nothing "
            "was read or sent.",
        )
    return ledger_root, digest


# -- Derivation: everything a run would send, re-derived in-process -------------


@dataclass(frozen=True)
class _Derived:
    source: _ApprovedSource
    head_object_id: str
    request: LLMRequest
    payload: dict
    request_sha256: str
    approved_plan_sha256: str
    project_config_sha256: str


def _derive(
    project: ProjectConfig,
    approved_plan: ApprovedL1PlanArtifact,
    target_path: object,
    settings: LiveSettings,
) -> _Derived:
    """Identity, target, Git observation, 5D2 read, Git observation, request, digests."""
    _check_identity(approved_plan, project)
    target = _check_target_path(target_path, approved_plan, project)
    head_before = observe_clean_workspace_head(project, target)
    source = _read_approved_source(project, approved_plan, target)
    head_after = observe_clean_workspace_head(project, target)
    if head_after != head_before:
        raise _refuse(
            "workspace_changed_during_read",
            "the workspace HEAD changed while the approved file was being read. "
            "Nothing was sent.",
        )
    request = build_supervised_implementer_request(
        approved_plan=approved_plan,
        target_path=source.target_path,
        current_text=source.original_text,
        model=settings.base.model,
        max_output_tokens=settings.base.max_output_tokens,
        structured_output=False,
    )
    payload = wire_payload(request)
    return _Derived(
        source=source,
        head_object_id=head_before,
        request=request,
        payload=payload,
        request_sha256=sha256_hex(canonical_json_bytes(payload)),
        approved_plan_sha256=sha256_hex(canonical_json_bytes(approved_plan.model_dump(mode="json"))),
        project_config_sha256=sha256_hex(canonical_json_bytes(project.model_dump(mode="json"))),
    )


def _bound_values(
    *,
    run_id: str,
    project: ProjectConfig,
    approved_plan: ApprovedL1PlanArtifact,
    settings: LiveSettings,
    derived: _Derived,
    evidence_dir_sha256: str,
    authorization_ledger_dir_sha256: str,
    issuance_sha256: str,
    prepared_at: str,
    expires_at: str,
) -> dict:
    return {
        "schema_version": AUTHORIZATION_SCHEMA_VERSION,
        "run_id": run_id,
        "stage": AUTHORIZATION_STAGE,
        "authorized_http_requests": 1,
        "authorized_semantic_requests": 1,
        "role": SUPERVISED_IMPLEMENTER_ROLE,
        "candidate": settings.base.candidate,
        "model": settings.base.model,
        "provider": settings.base.provider,
        "project_id": project.project_id,
        "repo": project.repo.github_repo,
        "issue_number": approved_plan.issue_number,
        "approved_plan_sha256": derived.approved_plan_sha256,
        "project_config_sha256": derived.project_config_sha256,
        "target_path": derived.source.target_path,
        "change_type": "modify",
        "source_sha256": derived.source.source_sha256,
        "source_bytes": derived.source.source_bytes,
        "workspace_head_object_id": derived.head_object_id,
        "workspace_git_state": WORKSPACE_GIT_STATE,
        "request_sha256": derived.request_sha256,
        "structured_output_mode": "none",
        "requested_max_output_tokens": settings.base.max_output_tokens,
        "attempt_timeout_seconds": settings.attempt_timeout_seconds,
        "max_response_body_bytes": MAX_RESPONSE_BODY_BYTES,
        "allow_insecure_http": settings.base.allow_insecure_http,
        "evidence_dir_sha256": evidence_dir_sha256,
        "authorization_ledger_dir_sha256": authorization_ledger_dir_sha256,
        "issuance_sha256": issuance_sha256,
        "prepared_at": prepared_at,
        "expires_at": expires_at,
        "aido_version": __version__,
    }


# -- Prepare -------------------------------------------------------------------


@dataclass(frozen=True)
class PreparedAuthorization:
    """A draft. It grants nothing until a human completes its consent block."""

    bound: AuthorizationBound
    draft: bytes


def prepare_supervised_implementation(
    *,
    project: ProjectConfig,
    approved_plan: ApprovedL1PlanArtifact,
    target_path: str,
    evidence_dir: str,
    _now: Callable[[], datetime] | None = None,
) -> PreparedAuthorization:
    """Re-derive one run's exact request and return an authorization draft.

    Reads the project's approved files through the 5D2 reader and observes the
    Git state read-only. Reads **no** provider environment variable, builds no
    client, and contacts nothing (acceptance criterion 1).

    Its one write is the ledger's issuance record (ALPHA-P1B-FU1), created
    exclusively as the last step. That record is what later proves the
    authorization unspent; on its own it grants nothing, because a run still
    needs a human-completed consent echoing ``binding_sha256``.
    """
    project, approved_plan = _private_copies(project, approved_plan)
    settings = check_supervised_implementer_live_gate(project.supervised_implementer)
    _require_windows()
    evidence_root, evidence_dir_sha256 = _canonical_evidence_dir(evidence_dir, project)
    ledger_root, ledger_dir_sha256 = _canonical_ledger_dir(settings, project, evidence_root)
    derived = _derive(project, approved_plan, target_path, settings)

    moment = (_now or _utc_now)().astimezone(timezone.utc).replace(microsecond=0)
    nonce, issuance_sha256 = new_issuance_nonce()
    values = _bound_values(
        run_id=secrets.token_hex(16),
        project=project,
        approved_plan=approved_plan,
        settings=settings,
        derived=derived,
        evidence_dir_sha256=evidence_dir_sha256,
        authorization_ledger_dir_sha256=ledger_dir_sha256,
        issuance_sha256=issuance_sha256,
        prepared_at=utc_timestamp(moment),
        expires_at=utc_timestamp(moment + AUTH_TTL),
    )
    values["binding_sha256"] = compute_binding_sha256(values)
    try:
        bound = AuthorizationBound.model_validate(values)
    except ValidationError as exc:  # pragma: no cover - AIDO built every value.
        raise _refuse("authorization_build_failed", _summarize_validation_error(exc)) from None
    issue_authorization(
        ledger_root,
        run_id=bound.run_id,
        binding_sha256=bound.binding_sha256,
        nonce=nonce,
        issued_at=bound.prepared_at,
    )
    del nonce
    return PreparedAuthorization(bound=bound, draft=render_authorization_draft(bound))


# -- Records -------------------------------------------------------------------


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


def _non_negative(value: float) -> float:
    if value < 0:
        raise ValueError("must not be negative.")
    return value


class AidoRequested(_Frozen):
    model: Literal["qwen3.8-27b"]
    provider: Literal["litellm"]
    requested_max_output_tokens: StrictInt | None
    structured_output_mode: Literal["none"]
    attempt_timeout_seconds: TimeoutSeconds
    max_response_body_bytes: StrictInt
    client_max_retries: ExactZero
    http_transport_retries: ExactZero


class TransportObserved(_Frozen):
    endpoint_scheme: Literal["http", "https"]
    endpoint_host: StrictStr
    endpoint_port: StrictInt
    transport_tls: StrictBool
    environment_proxies_consulted: StrictFalse
    redirects_followed: StrictFalse
    requests_forwarded_to_network_transport: ExactOne
    response_status_class: Literal["2xx"]
    response_body_bytes: StrictInt
    response_content_encoding: Literal["identity"]
    elapsed_seconds: Annotated[float, AfterValidator(_non_negative)]


class ServerReported(_Frozen):
    """Claims made by the server or model. Not facts AIDO observed."""

    response_model_field: StrictStr
    finish_reason: Literal["stop"]
    usage_reported: ReportedUsage | None


class AidoDerived(_Frozen):
    transmitted_file_count: ExactOne
    transmitted_source_bytes: StrictInt
    transmitted_source_sha256: Hex64
    request_sha256: Hex64
    response_content_sha256: Hex64
    proposed_content_sha256: Hex64
    workspace_head_object_id: StrictStr


class SupervisedImplementerLiveProvenance(_Frozen):
    """``supervised-implementer-provenance.v2``: the live record. v1 stays offline-only.

    Sections keep AIDO's requests, AIDO's transport observations, server
    claims and AIDO-derived digests apart. It is not evidence that the content
    is correct, safe or minimal, and it confers no qualification of any kind.
    """

    schema_version: Literal["supervised-implementer-provenance.v2"]
    role: Literal["supervised_implementer"]
    candidate: Literal["SUP-D"]
    model: Literal["qwen3.8-27b"]
    model_source: Literal["project_config.supervised_implementer.model"]
    transport_kind: Literal["live_http"]
    qualification_credit: Literal["none"]
    autonomous_implementer_qualified: StrictFalse
    model_output_is_evidence: StrictFalse

    run_id: StrictStr
    authorization_binding_sha256: Hex64

    project_id: StrictStr
    repo: StrictStr
    issue_number: StrictInt
    target_path: StrictStr
    change_type: Literal["modify"]
    outcome: Literal["diff_proposed", "no_change_proposed"]
    workspace_git_state_observed: Literal["clean_tree_at_bound_head_before_and_after_source_read"]

    aido_requested: AidoRequested
    transport_observed: TransportObserved
    server_reported: ServerReported
    aido_derived: AidoDerived

    orchestrator_approval_created: StrictFalse
    orchestrator_workspace_written: StrictFalse
    orchestrator_git_write_operations: StrictFalse
    orchestrator_retries_issued: ExactZero
    orchestrator_cancellation_requested: StrictFalse
    next_step: Literal["human_exact_diff_approval_required"]


class SupervisedImplementerLiveResult(_Frozen):
    """A diff proposal plus its v2 provenance, cross-checked by digest on construction."""

    diff_proposal: DiffProposalArtifact
    provenance: SupervisedImplementerLiveProvenance

    @model_validator(mode="after")
    def _records_agree(self) -> SupervisedImplementerLiveResult:
        prov = self.provenance
        check_diff_agrees_with_content_provenance(
            self.diff_proposal,
            project_id=prov.project_id,
            repo=prov.repo,
            issue_number=prov.issue_number,
            outcome=prov.outcome,
            target_path=prov.target_path,
            transmitted_source_sha256=prov.aido_derived.transmitted_source_sha256,
            proposed_content_sha256=prov.aido_derived.proposed_content_sha256,
        )
        return self


RunState = Literal[
    "diff_proposed",
    "no_change_proposed",
    "refused_after_consumption",
    "transport_failed",
    "implementer_stalled",
    "response_too_large",
    "output_rejected",
]


class SupervisedImplementerRunOutcome(_Frozen):
    """``outcome.json``: the terminal state of one consumed authorization.

    ``transmission_attempted`` is true as soon as the request worker started
    (R-8); it does not say whether bytes reached a server. ``completion_received``
    is true only when the client returned a normalized completion, so a failure
    record can never imply that a model response arrived when none did.
    """

    schema_version: Literal["supervised-implementer-run-outcome.v1"]
    run_id: StrictStr
    authorization_binding_sha256: Hex64
    state: RunState
    transmission_attempted: StrictBool
    worker_started: StrictBool
    requests_forwarded_to_network_transport_observed: StrictInt
    completion_received: StrictBool
    failure_category: StrictStr | None
    failure_message: StrictStr | None
    stall_source: Literal["supervisor_deadline", "client_timeout"] | None
    response_status_code_observed: StrictInt | None
    response_body_bytes_observed: StrictInt
    response_content_sha256: Hex64 | None
    response_content_chars: StrictInt | None
    finish_reason_reported: StrictStr | None
    elapsed_seconds: float | None
    consumed_at: AwareTimestamp
    finished_at: AwareTimestamp
    authorization_reusable: StrictFalse
    backend_inference_lifetime_if_stalled: StrictStr
    abandoned_worker_lifetime_if_supervisor_deadline_expires: StrictStr
    orchestrator_cancellation_requested: StrictFalse
    orchestrator_retries_issued: ExactZero
    orchestrator_approval_created: StrictFalse
    orchestrator_workspace_written: StrictFalse
    qualification_credit: Literal["none"]
    next_step: Literal["human_exact_diff_approval_required", "prepare_a_new_authorization"]


# -- The transmission notice -----------------------------------------------------


@dataclass(frozen=True)
class LiveTransmissionNotice:
    """Announced on stderr after consumption and before the request. Host and port only."""

    run_id: str
    authorization_binding_sha256: str
    target_path: str
    source_bytes: int
    source_sha256: str
    candidate: str
    model: str
    provider: str
    endpoint_scheme: str
    endpoint_host: str
    endpoint_port: int
    attempt_timeout_seconds: float

    def render(self) -> str:
        transport = (
            "TLS (https)"
            if self.endpoint_scheme == "https"
            else "PLAINTEXT HTTP — NOT TLS-ENCRYPTED (project and operator acknowledged)"
        )
        return "\n".join(
            [
                "=" * 78,
                "SUPERVISED IMPLEMENTER — LIVE SOURCE TRANSMISSION",
                f"  run id:        {self.run_id}",
                f"  authorization: {self.authorization_binding_sha256}",
                f"  file:          {self.target_path!r} ({self.source_bytes} bytes, "
                f"sha256 {self.source_sha256})",
                f"  candidate:     {self.candidate} / model {self.model}",
                f"  provider:      {self.provider}",
                f"  endpoint:      host {self.endpoint_host!r}, port {self.endpoint_port}",
                f"  transport:     {transport}",
                f"  AIDO wait:     at most {self.attempt_timeout_seconds:g} s (AIDO's own "
                "deadline; not a cancellation)",
                "  ONE request, zero retries, no fallback. The reply is untrusted "
                "proposed content;",
                "  nothing is written without a separate exact human diff approval.",
                "=" * 78,
            ]
        )


# -- Run -------------------------------------------------------------------------


@dataclass(frozen=True)
class LiveRunReport:
    """What one consumed run ended as. Pre-consumption refusals raise instead."""

    state: str
    exit_code: int
    run_dir: str
    transmission_attempted: bool
    outcome_recorded: bool
    failure_category: str | None = None
    failure_message: str | None = None
    stall_source: str | None = None
    result: SupervisedImplementerLiveResult | None = None


_EXIT_SUCCESS = 0
_EXIT_REFUSED = 1
_EXIT_TRANSMITTED_NO_PROPOSAL = 4
_EXIT_EVIDENCE_INCOMPLETE = 5

_CLIENT_ERROR_CATEGORIES: dict[type, str] = {
    LLMAuthError: "auth_rejected",
    LLMResponseError: "http_error_or_malformed_response",
    LLMTransportError: "connection_failed",
}


def _create_exclusive(path: str, data: bytes) -> None:
    """Create a new file exclusively, write it whole, and fsync it. Never overwrites."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _content_digest(text: str) -> str:
    return sha256_hex(text.encode("utf-8", "surrogatepass"))


class _RunRecorder:
    """Writes the run directory's evidence. Holds no source text of its own."""

    def __init__(
        self, *, run_dir: str, bound: AuthorizationBound, consumed_at: str, clock: Callable[[], datetime]
    ) -> None:
        self.run_dir = run_dir
        self.bound = bound
        self.consumed_at = consumed_at
        self.clock = clock
        self.worker_started = False
        self.observation = TransportObservation()
        self.elapsed: float | None = None

    def create(self, name: str, data: bytes) -> None:
        _create_exclusive(os.path.join(self.run_dir, name), data)

    def outcome(
        self,
        state: str,
        *,
        failure_category: str | None = None,
        failure_message: str | None = None,
        stall_source: str | None = None,
        response: LLMResponse | None = None,
    ) -> SupervisedImplementerRunOutcome:
        succeeded = state in ("diff_proposed", "no_change_proposed")
        return SupervisedImplementerRunOutcome(
            schema_version=OUTCOME_SCHEMA_VERSION,
            run_id=self.bound.run_id,
            authorization_binding_sha256=self.bound.binding_sha256,
            state=state,
            transmission_attempted=self.worker_started,
            worker_started=self.worker_started,
            requests_forwarded_to_network_transport_observed=self.observation.forwarded_to_network_transport,
            completion_received=response is not None,
            failure_category=failure_category,
            failure_message=failure_message,
            stall_source=stall_source,
            response_status_code_observed=self.observation.response_status_code,
            response_body_bytes_observed=self.observation.response_body_bytes,
            response_content_sha256=None if response is None else _content_digest(response.content),
            response_content_chars=None if response is None else len(response.content),
            finish_reason_reported=None if response is None else response.finish_reason,
            elapsed_seconds=self.elapsed,
            consumed_at=self.consumed_at,
            finished_at=utc_timestamp(self.clock()),
            authorization_reusable=False,
            backend_inference_lifetime_if_stalled=BACKEND_LIFETIME_IF_STALLED,
            abandoned_worker_lifetime_if_supervisor_deadline_expires=WORKER_LIFETIME_IF_DEADLINE_EXPIRES,
            orchestrator_cancellation_requested=False,
            orchestrator_retries_issued=0,
            orchestrator_approval_created=False,
            orchestrator_workspace_written=False,
            qualification_credit=QUALIFICATION_CREDIT,
            next_step=NEXT_STEP if succeeded else NEXT_STEP_AFTER_FAILURE,
        )

    def finish_failure(
        self,
        state: str,
        *,
        category: str,
        message: str,
        stall_source: str | None = None,
        response: LLMResponse | None = None,
    ) -> LiveRunReport:
        recorded = True
        try:
            record = self.outcome(
                state,
                failure_category=category,
                failure_message=message,
                stall_source=stall_source,
                response=response,
            )
            self.create(OUTCOME_FILE, (record.model_dump_json(indent=2) + "\n").encode("utf-8"))
        except (OSError, ValidationError):
            recorded = False
        if state == "refused_after_consumption" and not self.worker_started:
            exit_code = _EXIT_REFUSED
        elif recorded:
            exit_code = _EXIT_TRANSMITTED_NO_PROPOSAL
        else:
            exit_code = _EXIT_EVIDENCE_INCOMPLETE
        return LiveRunReport(
            state=state,
            exit_code=exit_code,
            run_dir=self.run_dir,
            transmission_attempted=self.worker_started,
            outcome_recorded=recorded,
            failure_category=category,
            failure_message=message,
            stall_source=stall_source,
        )


def _build_live_client_config(env: object, settings: LiveSettings) -> LLMClientConfig:
    """The shipped LiteLLM loader, then the overrides. Never echoes a value (R-11)."""
    if not isinstance(env, Mapping):
        raise _refuse("environment_invalid", "the environment reader returned no mapping.")
    try:
        loaded = load_llm_client_config_from_env(env)
        return LLMClientConfig(
            base_url=loaded.base_url,
            api_key=loaded.api_key,
            default_model=settings.base.model,
            timeout_seconds=settings.attempt_timeout_seconds,
            max_retries=TRANSPORT_MAX_RETRIES,
        )
    except (LLMConfigError, ValidationError):
        raise _refuse(
            "environment_invalid",
            "the AIDO_LITELLM_* environment is missing, blank or invalid. No "
            "value is echoed. Nothing was sent, and the authorization was not "
            "consumed.",
        ) from None


def _default_network_transport() -> httpx.BaseTransport:
    """The only network transport the live path builds (A-3, A-11, R-7)."""
    return httpx.HTTPTransport(retries=0, trust_env=False)


def _bound_mismatches(
    bound: AuthorizationBound,
    *,
    project: ProjectConfig,
    approved_plan: ApprovedL1PlanArtifact,
    settings: LiveSettings,
    derived: _Derived,
) -> list[str]:
    expected = {
        "candidate": settings.base.candidate,
        "model": settings.base.model,
        "provider": settings.base.provider,
        "project_id": project.project_id,
        "repo": project.repo.github_repo,
        "issue_number": approved_plan.issue_number,
        "approved_plan_sha256": derived.approved_plan_sha256,
        "project_config_sha256": derived.project_config_sha256,
        "target_path": derived.source.target_path,
        "source_sha256": derived.source.source_sha256,
        "source_bytes": derived.source.source_bytes,
        "workspace_head_object_id": derived.head_object_id,
        "request_sha256": derived.request_sha256,
        "requested_max_output_tokens": settings.base.max_output_tokens,
        "attempt_timeout_seconds": settings.attempt_timeout_seconds,
        "allow_insecure_http": settings.base.allow_insecure_http,
    }
    mismatched = []
    for name, value in expected.items():
        actual = getattr(bound, name)
        if type(actual) is not type(value) or actual != value:
            mismatched.append(name)
    return mismatched


def run_supervised_implementation(
    *,
    project: ProjectConfig,
    approved_plan: ApprovedL1PlanArtifact,
    authorization_bytes: bytes,
    evidence_dir: str,
    read_env: Callable[[str], Mapping[str, str]],
    announce: Callable[[LiveTransmissionNotice], None],
    _now: Callable[[], datetime] | None = None,
    _inner_transport_factory: Callable[[], httpx.BaseTransport] | None = None,
) -> LiveRunReport:
    """Consume one authorization and issue at most one request. Stops before H6.

    Raises:
        SupervisedImplementerRefused: refused **before consumption**. Nothing
            was sent and this invocation consumed nothing. The ledger alone
            says whether the authorization is still unspent: a missing,
            mismatched or spent ledger record refuses here, never the reverse.

    Returns:
        A :class:`LiveRunReport` for every run that consumed the authorization,
        whatever its outcome.
    """
    clock = _now or _utc_now
    if not callable(read_env) or not callable(announce):
        raise _refuse("callbacks_missing", "an environment reader and an announcer are required.")

    # a. Private copies and every config gate. Nothing else is read yet.
    project, approved_plan = _private_copies(project, approved_plan)
    settings = check_supervised_implementer_live_gate(project.supervised_implementer)
    _require_windows()

    # b. The authorization: strict parse (binding recomputed), then time.
    authorization = parse_authorization(authorization_bytes)
    bound, consent = authorization.bound, authorization.consent
    now = clock()
    prepared_at = parse_timestamp(bound.prepared_at)
    if now < prepared_at - CONSENT_CLOCK_SKEW:
        raise _refuse("authorization_not_yet_valid", "the authorization was prepared in the future.")
    if not now < parse_timestamp(bound.expires_at):
        raise _refuse(
            "authorization_expired",
            "the authorization has expired. Run prepare again. Nothing was sent.",
        )
    consented_at = parse_timestamp(consent.consented_at)
    if consented_at < prepared_at or consented_at > now + CONSENT_CLOCK_SKEW:
        raise _refuse(
            "consent_time_invalid",
            "consent.consented_at must lie between prepared_at and now. Nothing was sent.",
        )

    # c. The evidence directory, then the durable ledger (FU1), which alone
    #    decides single use. Evidence never proves an authorization unspent.
    evidence_root, evidence_dir_sha256 = _canonical_evidence_dir(evidence_dir, project)
    if evidence_dir_sha256 != bound.evidence_dir_sha256:
        raise _refuse(
            "evidence_dir_mismatch",
            "this authorization was prepared for a different evidence directory. "
            "Nothing was sent.",
        )
    ledger_root, ledger_dir_sha256 = _canonical_ledger_dir(settings, project, evidence_root)
    if ledger_dir_sha256 != bound.authorization_ledger_dir_sha256:
        raise _refuse(
            "authorization_ledger_mismatch",
            "this authorization was issued by a different authorization ledger. "
            "Nothing was sent.",
        )
    check_unspent(
        ledger_root,
        run_id=bound.run_id,
        binding_sha256=bound.binding_sha256,
        issuance_sha256=bound.issuance_sha256,
    )
    run_dir = os.path.join(evidence_root, bound.run_id)
    if os.path.lexists(run_dir):
        raise _refuse(
            "evidence_run_dir_exists",
            "a run directory for this authorization already exists in the "
            "evidence directory. Evidence is never overwritten; run prepare "
            "again. Nothing was sent.",
        )

    # d. Re-derive everything in-process and compare exactly.
    derived = _derive(project, approved_plan, bound.target_path, settings)
    mismatched = _bound_mismatches(
        bound, project=project, approved_plan=approved_plan, settings=settings, derived=derived
    )
    if mismatched:
        raise _refuse(
            "authorization_mismatch",
            "the authorization no longer matches what this run would send; "
            "mismatched: " + ", ".join(mismatched) + ". Run prepare again. Nothing was sent.",
        )

    # e. The configured provider's environment, exactly once, then the endpoint
    #    against the human-typed consent. Still nothing is sent or consumed.
    supervised_implementer_env_names_for_provider(settings.base.provider)
    env = read_env(settings.base.provider)
    client_config = _build_live_client_config(env, settings)
    del env
    endpoint = check_live_endpoint(
        client_config.base_url, allow_insecure_http=settings.base.allow_insecure_http
    )
    if endpoint.scheme == "http" and consent.plaintext_acknowledgement != PLAINTEXT_ACKNOWLEDGEMENT:
        raise _refuse("plaintext_not_acknowledged", "plaintext HTTP was not acknowledged.")
    if (endpoint.scheme, endpoint.host, endpoint.port) != (
        consent.endpoint_scheme,
        consent.normalized_host,
        consent.endpoint_port,
    ):
        raise _refuse(
            "endpoint_not_consented",
            f"the environment resolves to {endpoint.scheme} host {endpoint.host!r} "
            f"port {endpoint.port}, which is not the scheme, host and port the "
            "consent names. Nothing was sent, and the authorization was not consumed.",
        )
    if consent.consent_text != CONSENT_TEXT:  # pragma: no cover - the parser already enforced it.
        raise _refuse("consent_missing", "the consent phrase is not exact.")

    # f. CONSUME in the durable ledger: one exclusive create, then the issuance
    #    nonce is destroyed (FU1). A refusal raised here wrote nothing. From the
    #    moment the tombstone exists the authorization is spent, whatever
    #    happens, and only a settled ledger lets the run continue.
    consumed_at = utc_timestamp(clock())
    ledger_failure: LedgerSpentUnsettled | None = None
    try:
        consume_issuance(
            ledger_root,
            run_id=bound.run_id,
            binding_sha256=bound.binding_sha256,
            issuance_sha256=bound.issuance_sha256,
            consumed_at=consumed_at,
        )
    except LedgerSpentUnsettled as exc:
        ledger_failure = exc

    # f2. The run directory is evidence, not authority. If it cannot be made,
    #     the authorization stays spent and nothing is sent.
    try:
        os.mkdir(run_dir)
    except OSError:
        return LiveRunReport(
            state="refused_after_consumption",
            exit_code=_EXIT_REFUSED,
            run_dir=run_dir,
            transmission_attempted=False,
            outcome_recorded=False,
            failure_category=(
                ledger_failure.category if ledger_failure is not None else "evidence_write_failed"
            ),
            failure_message="the run directory could not be created after the "
            "authorization was consumed in the ledger. Nothing was sent. The "
            "authorization is spent.",
        )
    recorder = _RunRecorder(run_dir=run_dir, bound=bound, consumed_at=consumed_at, clock=clock)
    if ledger_failure is not None:
        return recorder.finish_failure(
            "refused_after_consumption",
            category=ledger_failure.category,
            message=ledger_failure.message,
        )
    try:
        return _consumed_run(
            recorder=recorder,
            authorization_bytes=authorization_bytes,
            bound=bound,
            settings=settings,
            project=project,
            approved_plan=approved_plan,
            derived=derived,
            client_config=client_config,
            endpoint=endpoint,
            announce=announce,
            inner_transport_factory=_inner_transport_factory or _default_network_transport,
        )
    except Exception as exc:  # noqa: BLE001 - never escape a consumed run unrecorded.
        state = "transport_failed" if recorder.worker_started else "refused_after_consumption"
        return recorder.finish_failure(
            state,
            category="internal_error",
            message=f"an unexpected {type(exc).__name__} ended the run. No detail is echoed.",
        )


def _consumed_run(
    *,
    recorder: _RunRecorder,
    authorization_bytes: bytes,
    bound: AuthorizationBound,
    settings: LiveSettings,
    project: ProjectConfig,
    approved_plan: ApprovedL1PlanArtifact,
    derived: _Derived,
    client_config: LLMClientConfig,
    endpoint: LiveEndpoint,
    announce: Callable[[LiveTransmissionNotice], None],
    inner_transport_factory: Callable[[], httpx.BaseTransport],
) -> LiveRunReport:
    # g. Evidence that must exist before anything could be sent.
    try:
        recorder.create(
            CONSUMED_FILE,
            canonical_json_bytes(
                {
                    "run_id": bound.run_id,
                    "binding_sha256": bound.binding_sha256,
                    "consumed_at": recorder.consumed_at,
                }
            ),
        )
        recorder.create(AUTHORIZATION_FILE, authorization_bytes)
        recorder.create(REQUEST_FILE, canonical_json_bytes(derived.payload))
        recorder.create(
            PENDING_FILE,
            canonical_json_bytes(
                {
                    "schema_version": PENDING_SCHEMA_VERSION,
                    "run_id": bound.run_id,
                    "authorization_binding_sha256": bound.binding_sha256,
                    "state": "transmission_pending",
                    "written_at": utc_timestamp(recorder.clock()),
                    "meaning": "If no outcome.json exists beside this file, treat "
                    "the approved source as possibly transmitted.",
                }
            ),
        )
    except OSError:
        return recorder.finish_failure(
            "refused_after_consumption",
            category="evidence_write_failed",
            message="the pre-transmission evidence could not be written. Nothing "
            "was sent. The authorization is spent.",
        )

    # h. Announce. If the operator cannot be told, nothing is sent.
    notice = LiveTransmissionNotice(
        run_id=bound.run_id,
        authorization_binding_sha256=bound.binding_sha256,
        target_path=derived.source.target_path,
        source_bytes=derived.source.source_bytes,
        source_sha256=derived.source.source_sha256,
        candidate=settings.base.candidate,
        model=settings.base.model,
        provider=settings.base.provider,
        endpoint_scheme=endpoint.scheme,
        endpoint_host=endpoint.host,
        endpoint_port=endpoint.port,
        attempt_timeout_seconds=settings.attempt_timeout_seconds,
    )
    try:
        announce(notice)
    except Exception:  # noqa: BLE001
        return recorder.finish_failure(
            "refused_after_consumption",
            category="announce_failed",
            message="the transmission notice could not be shown. Nothing was "
            "sent. The authorization is spent.",
        )

    # i. The transport and client, built only from checked copies, then the
    #    digest re-checked on the exact object handed to the worker (A-9).
    request = derived.request
    if request_payload_sha256(request) != bound.request_sha256:
        return recorder.finish_failure(
            "refused_after_consumption",
            category="request_changed_after_validation",
            message="the request no longer matches its consented digest. Nothing was sent.",
        )
    transport = BoundedCountingTransport(
        inner_transport_factory(),
        expectation=OutboundExpectation(
            url=httpx.URL(endpoint.chat_url),
            payload=derived.payload,
            scheme=endpoint.scheme,
            host=endpoint.host,
            port=endpoint.port,
        ),
        max_response_body_bytes=MAX_RESPONSE_BODY_BYTES,
        observation=recorder.observation,
    )
    client = LLMClient(client_config, transport=transport)

    # j. ONE request under AIDO's own deadline. Every failure is terminal.
    started = time.monotonic()
    recorder.worker_started = True
    try:
        response = await_one_response(
            client, request, deadline_seconds=settings.attempt_timeout_seconds
        )
    except SupervisorDeadlineExpired:
        recorder.elapsed = round(time.monotonic() - started, 6)
        return recorder.finish_failure(
            "implementer_stalled",
            category="implementer_stalled",
            message="AIDO's wait deadline expired before a reply arrived. AIDO "
            "stopped waiting; the request and the backend's inference may still "
            "be running, and no cancellation was requested or observed.",
            stall_source="supervisor_deadline",
        )
    except LLMTimeoutError:
        recorder.elapsed = round(time.monotonic() - started, 6)
        return recorder.finish_failure(
            "implementer_stalled",
            category="implementer_stalled",
            message="the client's network-inactivity timeout fired. The backend's "
            "inference may still be running; no cancellation was requested or observed.",
            stall_source="client_timeout",
        )
    except ResponseTooLarge as exc:
        recorder.elapsed = round(time.monotonic() - started, 6)
        return recorder.finish_failure(
            "response_too_large", category=exc.category, message=str(exc).split(": ", 1)[-1]
        )
    except LiveTransportViolation as exc:
        recorder.elapsed = round(time.monotonic() - started, 6)
        return recorder.finish_failure(
            "transport_failed", category=exc.category, message=str(exc).split(": ", 1)[-1]
        )
    except LLMClientError as exc:
        recorder.elapsed = round(time.monotonic() - started, 6)
        category = next(
            (name for kind, name in _CLIENT_ERROR_CATEGORIES.items() if isinstance(exc, kind)),
            "client_error",
        )
        return recorder.finish_failure(
            "transport_failed",
            category=category,
            message=f"the single request failed ({type(exc).__name__}). It is "
            "terminal: no retry and no fallback was attempted.",
        )
    except Exception as exc:  # noqa: BLE001
        recorder.elapsed = round(time.monotonic() - started, 6)
        return recorder.finish_failure(
            "transport_failed",
            category="unexpected_transport_exception",
            message=f"the single request raised {type(exc).__name__}. No detail is "
            "echoed. It is terminal.",
        )
    recorder.elapsed = round(time.monotonic() - started, 6)

    # k. The reply is untrusted: the unchanged P1A/5E3 path, rejected never repaired.
    try:
        diff_proposal, outcome, proposed_sha256 = _proposal_from_reply(
            response=response,
            settings=settings.base,
            project=project,
            approved_plan=approved_plan,
            source=derived.source,
            assumption_text=_LIVE_ASSUMPTION_TEMPLATE.format(
                candidate=settings.base.candidate,
                model=settings.base.model,
                run_id=bound.run_id,
            ),
        )
    except SupervisedImplementerOutputRejected as exc:
        return recorder.finish_failure(
            "output_rejected",
            category=exc.category,
            message="the reply was received and rejected. It was not repaired "
            "or retried, and its content is recorded by digest and length only.",
            response=response,
        )

    observation = recorder.observation
    try:
        result = SupervisedImplementerLiveResult(
            diff_proposal=diff_proposal,
            provenance=SupervisedImplementerLiveProvenance(
                schema_version=PROVENANCE_V2_SCHEMA_VERSION,
                role=SUPERVISED_IMPLEMENTER_ROLE,
                candidate=settings.base.candidate,
                model=settings.base.model,
                model_source=MODEL_SOURCE,
                transport_kind=TRANSPORT_KIND_LIVE,
                qualification_credit=QUALIFICATION_CREDIT,
                autonomous_implementer_qualified=False,
                model_output_is_evidence=False,
                run_id=bound.run_id,
                authorization_binding_sha256=bound.binding_sha256,
                project_id=project.project_id,
                repo=project.repo.github_repo,
                issue_number=approved_plan.issue_number,
                target_path=derived.source.target_path,
                change_type="modify",
                outcome=outcome,
                workspace_git_state_observed="clean_tree_at_bound_head_before_and_after_source_read",
                aido_requested=AidoRequested(
                    model=settings.base.model,
                    provider=settings.base.provider,
                    requested_max_output_tokens=settings.base.max_output_tokens,
                    structured_output_mode="none",
                    attempt_timeout_seconds=settings.attempt_timeout_seconds,
                    max_response_body_bytes=MAX_RESPONSE_BODY_BYTES,
                    client_max_retries=TRANSPORT_MAX_RETRIES,
                    http_transport_retries=0,
                ),
                transport_observed=TransportObserved(
                    endpoint_scheme=observation.observed_scheme,
                    endpoint_host=observation.observed_host,
                    endpoint_port=observation.observed_port,
                    transport_tls=observation.observed_scheme == "https",
                    environment_proxies_consulted=False,
                    redirects_followed=False,
                    requests_forwarded_to_network_transport=observation.forwarded_to_network_transport,
                    response_status_class=f"{observation.response_status_code // 100}xx",
                    response_body_bytes=observation.response_body_bytes,
                    response_content_encoding=observation.response_content_encoding,
                    elapsed_seconds=recorder.elapsed,
                ),
                server_reported=ServerReported(
                    response_model_field=response.model,
                    finish_reason=response.finish_reason,
                    usage_reported=_usage(response),
                ),
                aido_derived=AidoDerived(
                    transmitted_file_count=1,
                    transmitted_source_bytes=derived.source.source_bytes,
                    transmitted_source_sha256=derived.source.source_sha256,
                    request_sha256=bound.request_sha256,
                    response_content_sha256=_content_digest(response.content),
                    proposed_content_sha256=proposed_sha256,
                    workspace_head_object_id=derived.head_object_id,
                ),
                orchestrator_approval_created=False,
                orchestrator_workspace_written=False,
                orchestrator_git_write_operations=False,
                orchestrator_retries_issued=0,
                orchestrator_cancellation_requested=False,
                next_step=NEXT_STEP,
            ),
        )
        result = SupervisedImplementerLiveResult.model_validate_json(result.model_dump_json())
    except (ValidationError, ValueError, TypeError) as exc:
        detail = _summarize_validation_error(exc) if isinstance(exc, ValidationError) else type(exc).__name__
        return recorder.finish_failure(
            "output_rejected",
            category="result_inconsistent",
            message="the result failed its own cross-checks: " + detail,
            response=response,
        )

    # l. Evidence, then STOP before H6.
    try:
        recorder.create(RESPONSE_FILE, response.content.encode("utf-8"))
        recorder.create(
            DIFF_FILE, (result.diff_proposal.model_dump_json(indent=2) + "\n").encode("utf-8")
        )
        recorder.create(
            PROVENANCE_FILE, (result.provenance.model_dump_json(indent=2) + "\n").encode("utf-8")
        )
        record = recorder.outcome(outcome, response=response)
        recorder.create(OUTCOME_FILE, (record.model_dump_json(indent=2) + "\n").encode("utf-8"))
    except (OSError, ValidationError):
        return LiveRunReport(
            state="evidence_incomplete",
            exit_code=_EXIT_EVIDENCE_INCOMPLETE,
            run_dir=recorder.run_dir,
            transmission_attempted=True,
            outcome_recorded=False,
            failure_category="evidence_write_failed",
            failure_message="a reply was received and accepted, but its evidence "
            "could not be fully written. The source WAS transmitted.",
            result=result,
        )
    return LiveRunReport(
        state=outcome,
        exit_code=_EXIT_SUCCESS,
        run_dir=recorder.run_dir,
        transmission_attempted=True,
        outcome_recorded=True,
        result=result,
    )
