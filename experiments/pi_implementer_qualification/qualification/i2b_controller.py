"""I2B -- Category-B Zero-Prompt Live-Gate Controller (OFFLINE WIRING ONLY).

**This module runs no Pi/Node process, opens no socket, calls no model, and
reads no real credential.** It implements only the STATE-MACHINE / ORCHESTRATION
SHAPE for the future Category-B zero-prompt compatibility gates (I2A design
Sec. 15): the ordering, the credential-read boundary, the failure attribution,
and the teardown/cleanup/evidence discipline. Every future live operation --
launching Node/Pi in RPC mode, calling ``get_commands``/``get_state``,
evaluating H1/H2, checking the B300 route, confirming broker ``READY``, and
tearing everything down -- is represented ONLY as an injected callable. Every
offline test in this package's suite supplies a synthetic double for each of
them; none is ever a real subprocess, socket, or model call.

This is a NEW slice (5F3B-I2B), authorized directly by its own implementation
prompt rather than by a pre-existing section of
``docs/PHASE_5F3B_I2A_B300_PI_ROUTE_CREDENTIAL_BOUNDARY_DESIGN.md`` (I2A). It
consumes I2's already-accepted, frozen offline objects
(:class:`~qualification.i2_credentials.ConnectionValues`,
:class:`~qualification.i2_secret_context.QualificationRouteSecretContext`,
:class:`~qualification.i2_pi_config.GeneratedQualificationConfig`,
:class:`~qualification.i2_route.RouteDescriptor`,
:class:`~qualification.i2_environment.LaunchEnvironment`) and their
cross-object binding (:mod:`qualification.i2_composition`) UNCHANGED -- I2B
adds no new raw ``api_key``/config-path/provider-id/model-id parameter
anywhere; every identity value flows through those trusted objects only.

**Gate ordering (this module's own choice, since I2B has no prior design
section to inherit an order from).** I2A Sec. 15's own numbered list of
Category-B checks is a narrative CHECKLIST, not a call-dependency graph -- for
example, AR2's own H1 evaluator (``ar2.handshakes.evaluate_extension_identity``)
takes the ``get_commands`` result as an argument, so a strict reading of "H1
before get_commands" is not implementable as a literal call sequence. This
controller instead follows the EXACT stage order given directly in this
slice's own implementation prompt (the "CONTROLLER RESPONSIBILITY" pipeline),
representing H1 as its own narrow, self-contained injected gate
(``h1_check``) that a future live adapter satisfies using whatever internal
state it captured, and reserving the separate ``get_commands`` stage for (a)
proving that RPC call itself succeeded and (b) supplying the command-name
list the later, purely-computed "exact tool registry" gate compares against
the fixed authorized set. Concretely, in call order:

    non-secret preflight (Category A, reused i2_credentials wiring)
        -> connection-value read authorization (reused i2_credentials wiring)
        -> route descriptor (i2_route, candidate identity only)
        -> I2 secret context (i2_secret_context)
        -> disposable generated Pi config (i2_pi_config)              [pi_config_created]
        -> config/secret/route identity binding (i2_composition)
        -> positive-allowlist child environment (i2_environment)
        -> future Pi/Node RPC launch (injected launch_rpc)            [live_resource_created]
        -> H1 exact extension identity (injected h1_check)
        -> get_commands (injected get_commands)
        -> get_state (injected get_state)
        -> H2 exact candidate provider/model identity (computed here)
        -> exact tool registry (computed here, from get_commands)
        -> future /models exact-model route gate (reused i2_route wiring)
        -> broker READY (injected broker_ready)
        -> zero semantic prompts confirmed (structural -- see below)
        -> teardown (injected teardown, attempted iff live_resource_created)
        -> generated-config cleanup (reused i2_cleanup wiring, attempted iff pi_config_created)
        -> safe retained Category-B evidence (this module, reusing qualification.safety)

**Zero-prompt proof.** ``semantic_prompts_sent`` is a local constant ``0``
that is never assigned any other value anywhere in this module, and this
module defines NO function that accepts, sends, or forwards a semantic
prompt, a task prompt, or any agent instruction of any kind -- there is
nothing here for such a value to travel through. A source-level regression
test in this package's offline suite greps this file for prompt-shaped
identifiers to keep that true mechanically, not just by present intent.

**Failure attribution.** Every gate failure in this module is bounded to one
of :class:`CategoryBFailureCode`'s fixed members and is reported ONLY as an
:class:`CategoryBOutcome.INFRASTRUCTURE_REFUSAL` result with
``semantic_prompts_sent == 0`` -- never ``AUTONOMOUS_FAIL``, never a candidate
classification, never a scoring result. This module imports nothing from
:mod:`qualification.outcomes`, :mod:`qualification.hard_bar`,
:mod:`qualification.ranking`, or :mod:`qualification.records`'s record
builder -- there is no candidate-scoring machinery reachable from here at
all. An exception raised by any injected callable -- expected or not -- is
caught and reduced to the bounded ``UNEXPECTED_EXCEPTION`` code; its
``str()``/``repr()`` is never read, stored, or returned.

**Teardown and cleanup.** Every path reachable after a resource was created
attempts the corresponding teardown/cleanup exactly once, regardless of
whether that path is a later failure or the fully-passed case -- Category-B's
entire job is to CONFIRM compatibility, never to leave a disposable config or
a live process behind. ``teardown`` truthfulness is bounded: this module
never claims a launched process, a broker, or backend inference was actually
stopped -- only that AIDO's own teardown call was attempted and what it
reported. Generated-config cleanup reuses
:func:`~qualification.i2_cleanup.scrub_generated_qualification_config` and,
on any cleanup failure, :func:`~qualification.i2_cleanup.classify_cleanup_failure`
called with ``semantic_prompts_sent=0`` -- the ONLY value it can ever be
called with from this module, since Category-B never sends a prompt.

**Evidence.** :func:`build_category_b_evidence` builds a bounded,
credential-free fact structure and passes it through
:func:`qualification.safety.qualification_scrub_check` (an explicit
``ArtifactSafetyContext``, never a default) before declaring it
retention-ready -- reusing the existing I1 scrub primitive, never a second
scanner. It does not write anything to disk; persisting a Category-B
evidence artifact through :func:`qualification.safety.emit_evidence_or_refuse`
is a decision for a future, separately authorized live phase.

**Tool registry.** :data:`AUTHORIZED_TOOL_NAMES` duplicates, as a fixed
I2B-owned VALUE (never an import), the same exact tool pair AR1/AR2 already
established (``ar2.pi_config.TOOL_ALLOWLIST``) -- ``aido_read``/``aido_edit``,
nothing else. This mirrors the precedent
:mod:`qualification.i2_environment` already set for ``BASE_WINDOWS_NAMES``/
``FORBIDDEN_NAME_FRAGMENTS``: the accepted VALUE is duplicated as new,
I2-owned data, never imported as a dependency on the frozen ``ar2`` package.

**Not implemented here, and not authorized by this slice:** any live Pi/Node
process launch, any real RPC/broker call, any real credential read, a
generic ``RuntimeAdapter``/``AgentRuntime`` abstraction, a candidate
implementer, a fixer, or any code path that could send a semantic prompt.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Mapping, Sequence

from .i2_cleanup import (
    CleanupFailureClassification,
    classify_cleanup_failure,
    scrub_generated_qualification_config,
)
from .i2_composition import I2IdentityBindingError, verify_i2_identity_binding
from .i2_credentials import (
    ConnectionValues,
    InfrastructureRefusal,
    PreflightGateResult,
    resolve_connection_after_preflight,
)
from .i2_environment import EnvironmentPolicyError, LaunchEnvironment, build_child_environment
from .i2_pi_config import (
    CleanupAuthorityError,
    GeneratedQualificationConfig,
    QualificationPiConfigCleanupError,
    QualificationPiConfigError,
    write_qualification_pi_config,
)
from .i2_route import (
    RouteCheckOutcome,
    RouteDescriptor,
    RouteDescriptorError,
    route_descriptor_for_candidate,
    run_offline_route_check,
)
from .i2_secret_context import (
    InvalidBaseUrlError,
    QualificationRouteSecretContext,
    SecretContextError,
    build_secret_context,
)
from .safety import ArtifactSafetyContext, qualification_scrub_check

#: The exact, fixed authorized AIDO tool registry (I2A Sec. 15 item 6).
#: Duplicated as a VALUE from ``ar2.pi_config.TOOL_ALLOWLIST`` -- never
#: imported -- per this package's established i2_environment precedent.
AUTHORIZED_TOOL_NAMES: frozenset[str] = frozenset({"aido_read", "aido_edit"})


class CategoryBFailureCode(str, Enum):
    """Bounded, declared Category-B gate-failure codes. Never free-form prose."""

    NON_SECRET_PREFLIGHT_GATE_FAILED = "NON_SECRET_PREFLIGHT_GATE_FAILED"
    CONNECTION_VALUES_UNAVAILABLE = "CONNECTION_VALUES_UNAVAILABLE"
    ROUTE_DESCRIPTOR_INVALID = "ROUTE_DESCRIPTOR_INVALID"
    SECRET_CONTEXT_CONSTRUCTION_FAILED = "SECRET_CONTEXT_CONSTRUCTION_FAILED"
    PI_CONFIG_GENERATION_FAILED = "PI_CONFIG_GENERATION_FAILED"
    IDENTITY_BINDING_MISMATCH = "IDENTITY_BINDING_MISMATCH"
    CHILD_ENVIRONMENT_BUILD_FAILED = "CHILD_ENVIRONMENT_BUILD_FAILED"
    RPC_LAUNCH_FAILED = "RPC_LAUNCH_FAILED"
    RPC_LAUNCH_SHAPE_UNEXPECTED = "RPC_LAUNCH_SHAPE_UNEXPECTED"
    REQUIRED_LAUNCH_FLAGS_REJECTED = "REQUIRED_LAUNCH_FLAGS_REJECTED"
    LF_JSONL_CORRELATION_FAILED = "LF_JSONL_CORRELATION_FAILED"
    H1_EXTENSION_IDENTITY_MISMATCH = "H1_EXTENSION_IDENTITY_MISMATCH"
    GET_COMMANDS_FAILED = "GET_COMMANDS_FAILED"
    GET_STATE_FAILED = "GET_STATE_FAILED"
    H2_PROVIDER_MODEL_IDENTITY_MISMATCH = "H2_PROVIDER_MODEL_IDENTITY_MISMATCH"
    TOOL_REGISTRY_MISMATCH = "TOOL_REGISTRY_MISMATCH"
    ROUTE_CHECK_FAILED = "ROUTE_CHECK_FAILED"
    BROKER_NOT_READY = "BROKER_NOT_READY"
    PROTOCOL_OR_EXTENSION_ERROR = "PROTOCOL_OR_EXTENSION_ERROR"
    UNEXPECTED_EXCEPTION = "UNEXPECTED_EXCEPTION"


class CategoryBGateName(str, Enum):
    """Every stage this controller gates, in exactly its call order."""

    NON_SECRET_PREFLIGHT = "non_secret_preflight"
    CONNECTION_VALUES = "connection_values"
    ROUTE_DESCRIPTOR = "route_descriptor"
    SECRET_CONTEXT = "secret_context"
    PI_CONFIG_GENERATION = "pi_config_generation"
    IDENTITY_BINDING = "identity_binding"
    CHILD_ENVIRONMENT = "child_environment"
    RPC_LAUNCH = "rpc_launch"
    H1_EXTENSION_IDENTITY = "h1_extension_identity"
    GET_COMMANDS = "get_commands"
    GET_STATE = "get_state"
    H2_PROVIDER_MODEL_IDENTITY = "h2_provider_model_identity"
    TOOL_REGISTRY = "tool_registry"
    ROUTE_CHECK = "route_check"
    BROKER_READY = "broker_ready"


class CategoryBOutcome(str, Enum):
    """This controller's own terminal status. Never reuses/extends the I1
    ``AutonomousClassification`` enum -- Category-B never reaches a
    candidate-scoring decision, only a pre-prompt compatibility confirmation
    or a pre-prompt refusal. The refusal member's STRING VALUE deliberately
    matches ``qualification.outcomes.AutonomousClassification.INFRASTRUCTURE_REFUSAL``
    for vocabulary consistency with the rest of the package, without
    importing that (candidate-scoring-adjacent) enum into this slice.
    """

    CATEGORY_B_GATE_PASSED = "CATEGORY_B_GATE_PASSED"
    INFRASTRUCTURE_REFUSAL = "INFRASTRUCTURE_REFUSAL"


@dataclass(frozen=True)
class GateOutcome:
    """One bounded pass/fail outcome for one live Category-B gate.

    Mirrors the valid-by-construction discipline
    ``i2_credentials.PreflightGateResult``/``i2_route.RouteCheckOutcome``
    already establish: ``passed`` must be exactly ``bool``; a passing
    outcome carries no ``failure_code``; a failing outcome MUST carry one of
    the bounded :class:`CategoryBFailureCode` values. There is no free-text
    field anywhere on this object -- a live adapter's own raw RPC/provider
    text can never reach it structurally, only a bounded classification of
    what that text meant.
    """

    passed: bool
    failure_code: CategoryBFailureCode | None

    def __post_init__(self) -> None:
        if type(self.passed) is not bool:
            raise ValueError("GateOutcome.passed must be exactly a bool")
        if self.passed:
            if self.failure_code is not None:
                raise ValueError("GateOutcome: passed=True must not carry a failure_code")
        elif self.failure_code is None:
            raise ValueError("GateOutcome: passed=False requires a declared failure_code")


@dataclass(frozen=True)
class RpcLaunchOutcome:
    """The bounded result of the future Node-direct Pi RPC launch.

    Represents Category-B gates 1/3/4/5 as ONE injected outcome:
    Pi-installed/version observation, the Node-direct ``--mode rpc`` launch
    shape, required launch flags accepted, and LF-framed JSONL request/
    response correlation. ``gate.failure_code`` distinguishes which of these
    failed (``RPC_LAUNCH_SHAPE_UNEXPECTED``, ``REQUIRED_LAUNCH_FLAGS_REJECTED``,
    ``LF_JSONL_CORRELATION_FAILED``, or the generic ``RPC_LAUNCH_FAILED``).

    ``observed_pi_version`` is recorded for evidence provenance ONLY (Category-B
    gate 2: "version is provenance only") -- nothing in this module compares it
    against any pinned value or lets it influence ``gate.passed``.
    """

    gate: GateOutcome
    observed_pi_version: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.gate, GateOutcome):
            raise ValueError("RpcLaunchOutcome.gate must be a GateOutcome")
        if self.observed_pi_version is not None and not isinstance(self.observed_pi_version, str):
            raise ValueError("RpcLaunchOutcome.observed_pi_version must be a str or None")


@dataclass(frozen=True)
class GetCommandsOutcome:
    """The bounded result of the future ``get_commands`` RPC call.

    ``command_names`` carries only command-name strings -- no path, no
    ``sourceInfo``, no raw response body -- exactly enough for the
    controller's own, purely-computed "exact tool registry" gate.
    """

    gate: GateOutcome
    command_names: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.gate, GateOutcome):
            raise ValueError("GetCommandsOutcome.gate must be a GateOutcome")
        if not isinstance(self.command_names, tuple) or not all(
            isinstance(name, str) for name in self.command_names
        ):
            raise ValueError("GetCommandsOutcome.command_names must be a tuple of str")


@dataclass(frozen=True)
class GetStateOutcome:
    """The bounded result of the future ``get_state`` RPC call.

    ``reported_provider``/``reported_model`` are bounded identity strings
    only -- expected to equal the fixed candidate identity -- never a raw
    response body, a base URL, or a host.
    """

    gate: GateOutcome
    reported_provider: str | None
    reported_model: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.gate, GateOutcome):
            raise ValueError("GetStateOutcome.gate must be a GateOutcome")
        for name, value in (
            ("reported_provider", self.reported_provider),
            ("reported_model", self.reported_model),
        ):
            if value is not None and not isinstance(value, str):
                raise ValueError(f"GetStateOutcome.{name} must be a str or None")


@dataclass(frozen=True)
class TeardownStatus:
    """Whether teardown was attempted, and truthfully what it reported.

    ``attempted`` is ``False`` iff no live resource was ever created
    (``live_resource_created`` stayed ``False`` for the whole run) --
    teardown is never invoked when there was nothing to tear down.
    **Never claims a launched process, a broker, or backend inference was
    actually stopped** -- only that AIDO's own teardown call was attempted
    and what it reported.
    """

    attempted: bool
    outcome: GateOutcome | None

    def __post_init__(self) -> None:
        if type(self.attempted) is not bool:
            raise ValueError("TeardownStatus.attempted must be exactly a bool")
        if self.attempted and self.outcome is None:
            raise ValueError("TeardownStatus: attempted=True requires an outcome")
        if not self.attempted and self.outcome is not None:
            raise ValueError("TeardownStatus: attempted=False must not carry an outcome")


@dataclass(frozen=True)
class CleanupStatus:
    """Whether generated-config cleanup was attempted, and its phase-aware result.

    ``classification`` is populated ONLY on a failed/unverified cleanup, via
    :func:`~qualification.i2_cleanup.classify_cleanup_failure` called with
    ``semantic_prompts_sent=0`` -- the only value this module can ever supply,
    since Category-B never sends a prompt.
    """

    attempted: bool
    scrub_verified: bool | None
    classification: CleanupFailureClassification | None

    def __post_init__(self) -> None:
        if type(self.attempted) is not bool:
            raise ValueError("CleanupStatus.attempted must be exactly a bool")
        if not self.attempted:
            if self.scrub_verified is not None or self.classification is not None:
                raise ValueError("CleanupStatus: attempted=False must carry no other field")
            return
        if self.scrub_verified is None:
            raise ValueError("CleanupStatus: attempted=True requires scrub_verified")
        if self.scrub_verified and self.classification is not None:
            raise ValueError("CleanupStatus: a verified cleanup must not carry a classification")
        if not self.scrub_verified and self.classification is None:
            raise ValueError("CleanupStatus: a failed/unverified cleanup requires a classification")


@dataclass(frozen=True)
class CategoryBEvidenceResult:
    """Either a retention-ready safe evidence dict, or a bounded, non-leaking refusal.

    ``evidence`` is populated ONLY when ``retention_ready`` is ``True`` --
    mirrors ``i2_cleanup.DiagnosticRetentionResult``'s existing shape.
    """

    retention_ready: bool
    evidence: dict[str, Any] | None
    scrub: dict[str, Any]


@dataclass(frozen=True)
class CategoryBControllerResult:
    """The controller's one, complete, truthful result for one run.

    Valid by construction: ``semantic_prompts_sent`` is always exactly ``0``
    in this offline Category-B slice, a ``CATEGORY_B_GATE_PASSED`` outcome
    never carries a failure, and an ``INFRASTRUCTURE_REFUSAL`` outcome always
    does.
    """

    candidate: str
    outcome: CategoryBOutcome
    semantic_prompts_sent: int
    failed_gate: CategoryBGateName | None
    failure_code: CategoryBFailureCode | None
    gate_statuses: Mapping[str, str]
    pi_config_created: bool
    live_resource_created: bool
    teardown: TeardownStatus
    cleanup: CleanupStatus
    evidence: CategoryBEvidenceResult

    def __post_init__(self) -> None:
        if self.semantic_prompts_sent != 0:
            raise ValueError(
                "CategoryBControllerResult: semantic_prompts_sent must be exactly 0 in "
                "this offline Category-B slice"
            )
        if self.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED:
            if self.failed_gate is not None or self.failure_code is not None:
                raise ValueError(
                    "CategoryBControllerResult: a passed run must not carry a "
                    "failed_gate/failure_code"
                )
        else:
            if self.failed_gate is None or self.failure_code is None:
                raise ValueError(
                    "CategoryBControllerResult: an INFRASTRUCTURE_REFUSAL run must "
                    "carry both a failed_gate and a failure_code"
                )


def _attempt_teardown(
    *, live_resource_created: bool, teardown: Callable[[], GateOutcome]
) -> TeardownStatus:
    """Attempt teardown iff a live resource may exist. Never claims more than reported.

    ``live_resource_created`` is set by the caller as soon as the RPC launch
    is ATTEMPTED (not only on a confirmed success) -- a launch attempt that
    itself reports failure may still have started a process, so teardown is
    always attempted from that point on, fail-safe.
    """
    if not live_resource_created:
        return TeardownStatus(attempted=False, outcome=None)
    try:
        result = teardown()
    except Exception:
        return TeardownStatus(
            attempted=True,
            outcome=GateOutcome(passed=False, failure_code=CategoryBFailureCode.UNEXPECTED_EXCEPTION),
        )
    if not isinstance(result, GateOutcome):
        return TeardownStatus(
            attempted=True,
            outcome=GateOutcome(passed=False, failure_code=CategoryBFailureCode.UNEXPECTED_EXCEPTION),
        )
    return TeardownStatus(attempted=True, outcome=result)


def _attempt_cleanup(generated_config: GeneratedQualificationConfig | None) -> CleanupStatus:
    """Attempt generated-config cleanup iff a config was ever created.

    Reuses ``i2_cleanup.scrub_generated_qualification_config`` and, on any
    failure/unverified result, ``i2_cleanup.classify_cleanup_failure`` with
    ``semantic_prompts_sent=0`` unconditionally -- Category-B structurally
    cannot supply any other value.
    """
    if generated_config is None:
        return CleanupStatus(attempted=False, scrub_verified=None, classification=None)
    try:
        result = scrub_generated_qualification_config(generated_config)
    except (CleanupAuthorityError, Exception):  # noqa: B014 - deliberately catch-all, bounded below
        return CleanupStatus(
            attempted=True,
            scrub_verified=False,
            classification=classify_cleanup_failure(semantic_prompts_sent=0),
        )
    if result.scrub_verified:
        return CleanupStatus(attempted=True, scrub_verified=True, classification=None)
    return CleanupStatus(
        attempted=True,
        scrub_verified=False,
        classification=classify_cleanup_failure(semantic_prompts_sent=0),
    )


def _teardown_status_text(status: TeardownStatus) -> str:
    if not status.attempted:
        return "NOT_ATTEMPTED"
    assert status.outcome is not None
    if status.outcome.passed:
        return "SUCCEEDED"
    return f"FAILED:{status.outcome.failure_code.value}"


def _cleanup_status_text(status: CleanupStatus) -> str:
    if not status.attempted:
        return "NOT_ATTEMPTED"
    if status.scrub_verified:
        return "SUCCEEDED"
    assert status.classification is not None
    assert status.classification.autonomous_classification is not None
    return f"FAILED:{status.classification.autonomous_classification.value}"


def build_category_b_evidence(
    *,
    candidate: str,
    route_descriptor: RouteDescriptor | None,
    observed_pi_version: str | None,
    outcome: CategoryBOutcome,
    gate_statuses: Mapping[str, str],
    teardown: TeardownStatus,
    cleanup: CleanupStatus,
    secret_context: QualificationRouteSecretContext | None,
) -> CategoryBEvidenceResult:
    """Build, and scrub-check, the bounded Category-B compatibility evidence.

    Builds a full ``ArtifactSafetyContext`` explicitly BEFORE scrubbing --
    populated from ``secret_context`` when one exists (declaring its
    endpoint host/API key as needles, even though neither field is ever
    placed in the payload below), or ``ArtifactSafetyContext.none_declared()``
    when the run failed before a secret context existed. This is a
    defense-in-depth declaration, not a claim that the payload needs it: the
    evidence shape below carries no credential, host, or path field at all.

    Does NOT write anything to disk -- persisting this through
    ``qualification.safety.emit_evidence_or_refuse`` is a decision for a
    future, separately authorized live phase.
    """
    safety = (
        secret_context.to_safety_context(
            broker_token=None, pipe_name=None, capability_id=None, workspace_absolute_path=None
        )
        if secret_context is not None
        else ArtifactSafetyContext.none_declared()
    )
    payload: dict[str, Any] = {
        "candidate": candidate,
        "model_id": route_descriptor.model_id if route_descriptor is not None else None,
        "provider_id": route_descriptor.provider_id if route_descriptor is not None else None,
        "gateway_class": (
            route_descriptor.backend_gateway_class if route_descriptor is not None else None
        ),
        "observed_pi_version": observed_pi_version,
        "compatibility_gate_passed": outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED,
        "gate_statuses": dict(gate_statuses),
        "aido_requested_max_output_tokens": None,
        "models_json_omits_max_tokens": True,
        "provider_request_count_observation_available": False,
        "wire_level_max_tokens_observation_available": False,
        "semantic_prompts_sent": 0,
        "teardown_status": _teardown_status_text(teardown),
        "cleanup_status": _cleanup_status_text(cleanup),
    }
    check = qualification_scrub_check(payload, safety)
    if check["clean"]:
        return CategoryBEvidenceResult(retention_ready=True, evidence=payload, scrub=check)
    return CategoryBEvidenceResult(retention_ready=False, evidence=None, scrub=check)


def run_category_b_controller(
    *,
    candidate: str,
    experiment_root: str,
    ambient_environ: Mapping[str, str],
    node_executable: str,
    non_secret_gates: Sequence[Callable[[], PreflightGateResult]],
    read_connection: Callable[[], ConnectionValues],
    launch_rpc: Callable[[LaunchEnvironment], RpcLaunchOutcome],
    h1_check: Callable[[], GateOutcome],
    get_commands: Callable[[], GetCommandsOutcome],
    get_state: Callable[[], GetStateOutcome],
    route_checker: Callable[..., Any],
    broker_ready: Callable[[], GateOutcome],
    teardown: Callable[[], GateOutcome],
    git_executable: str | None = None,
) -> CategoryBControllerResult:
    """Drive one candidate's Category-B compatibility gate sequence, OFFLINE.

    Every live dependency (``launch_rpc``, ``h1_check``, ``get_commands``,
    ``get_state``, ``route_checker``, ``broker_ready``, ``teardown``) is
    REQUIRED and INJECTED -- there is no default that reaches a real
    process, socket, or model. ``read_connection`` is likewise required and
    is never called until every gate in ``non_secret_gates`` has reported
    ``passed=True`` (enforced by the already-accepted
    ``i2_credentials.resolve_connection_after_preflight``, reused here
    unmodified).

    The first failing gate halts the sequence immediately; every later gate
    is left ``"NOT_REACHED"`` in the returned ``gate_statuses`` map. Teardown
    and generated-config cleanup are ALWAYS attempted afterward, on every
    path (failure or full pass) once the corresponding resource may exist.

    ``semantic_prompts_sent`` is always exactly ``0`` -- there is no
    parameter, branch, or injected callable anywhere in this function through
    which a prompt could be sent.
    """
    gate_statuses: dict[str, str] = {gate.value: "NOT_REACHED" for gate in CategoryBGateName}
    failed_gate: CategoryBGateName | None = None
    failure_code: CategoryBFailureCode | None = None

    def _pass(gate: CategoryBGateName) -> None:
        gate_statuses[gate.value] = "PASSED"

    def _fail(gate: CategoryBGateName, code: CategoryBFailureCode) -> None:
        nonlocal failed_gate, failure_code
        gate_statuses[gate.value] = f"FAILED:{code.value}"
        failed_gate = gate
        failure_code = code

    def _safe_call(gate: CategoryBGateName, fn: Callable[..., Any], *args: Any) -> Any | None:
        try:
            return fn(*args)
        except Exception:
            _fail(gate, CategoryBFailureCode.UNEXPECTED_EXCEPTION)
            return None

    connection_values: ConnectionValues | None = None
    route_descriptor: RouteDescriptor | None = None
    secret_context: QualificationRouteSecretContext | None = None
    generated_config: GeneratedQualificationConfig | None = None
    launch_environment: LaunchEnvironment | None = None
    observed_pi_version: str | None = None
    live_resource_created = False
    commands_outcome: GetCommandsOutcome | None = None
    state_outcome: GetStateOutcome | None = None

    # -- NON_SECRET_PREFLIGHT + CONNECTION_VALUES (credential-read boundary) --
    try:
        connection_values = resolve_connection_after_preflight(
            non_secret_gates=non_secret_gates, read_connection=read_connection
        )
    except InfrastructureRefusal as exc:
        if exc.gate_name == "connection_values":
            _fail(CategoryBGateName.CONNECTION_VALUES, CategoryBFailureCode.CONNECTION_VALUES_UNAVAILABLE)
        else:
            _fail(
                CategoryBGateName.NON_SECRET_PREFLIGHT,
                CategoryBFailureCode.NON_SECRET_PREFLIGHT_GATE_FAILED,
            )
    except Exception:
        _fail(CategoryBGateName.NON_SECRET_PREFLIGHT, CategoryBFailureCode.UNEXPECTED_EXCEPTION)

    if connection_values is not None:
        _pass(CategoryBGateName.NON_SECRET_PREFLIGHT)
        _pass(CategoryBGateName.CONNECTION_VALUES)

        # -- ROUTE_DESCRIPTOR --
        try:
            route_descriptor = route_descriptor_for_candidate(candidate)
            _pass(CategoryBGateName.ROUTE_DESCRIPTOR)
        except RouteDescriptorError:
            _fail(CategoryBGateName.ROUTE_DESCRIPTOR, CategoryBFailureCode.ROUTE_DESCRIPTOR_INVALID)
        except Exception:
            _fail(CategoryBGateName.ROUTE_DESCRIPTOR, CategoryBFailureCode.UNEXPECTED_EXCEPTION)

    if route_descriptor is not None:
        # -- SECRET_CONTEXT --
        assert connection_values is not None
        try:
            secret_context = build_secret_context(
                base_url=connection_values.base_url,
                api_key=connection_values.api_key,
                model_id=route_descriptor.model_id,
            )
            _pass(CategoryBGateName.SECRET_CONTEXT)
        except (SecretContextError, InvalidBaseUrlError):
            _fail(
                CategoryBGateName.SECRET_CONTEXT, CategoryBFailureCode.SECRET_CONTEXT_CONSTRUCTION_FAILED
            )
        except Exception:
            _fail(CategoryBGateName.SECRET_CONTEXT, CategoryBFailureCode.UNEXPECTED_EXCEPTION)

    if secret_context is not None:
        # -- PI_CONFIG_GENERATION [RESOURCE CREATION POINT] --
        assert route_descriptor is not None
        try:
            generated_config = write_qualification_pi_config(
                experiment_root, model_id=route_descriptor.model_id, base_url=secret_context.base_url
            )
            _pass(CategoryBGateName.PI_CONFIG_GENERATION)
        except (QualificationPiConfigError, QualificationPiConfigCleanupError, CleanupAuthorityError):
            _fail(
                CategoryBGateName.PI_CONFIG_GENERATION, CategoryBFailureCode.PI_CONFIG_GENERATION_FAILED
            )
        except Exception:
            _fail(CategoryBGateName.PI_CONFIG_GENERATION, CategoryBFailureCode.UNEXPECTED_EXCEPTION)

    if generated_config is not None:
        # -- IDENTITY_BINDING (config/secret/route cross-object agreement) --
        assert secret_context is not None and route_descriptor is not None
        try:
            verify_i2_identity_binding(
                generated_config=generated_config,
                secret_context=secret_context,
                route_descriptor=route_descriptor,
            )
            _pass(CategoryBGateName.IDENTITY_BINDING)
        except I2IdentityBindingError:
            _fail(CategoryBGateName.IDENTITY_BINDING, CategoryBFailureCode.IDENTITY_BINDING_MISMATCH)
        except Exception:
            _fail(CategoryBGateName.IDENTITY_BINDING, CategoryBFailureCode.UNEXPECTED_EXCEPTION)

    if gate_statuses[CategoryBGateName.IDENTITY_BINDING.value] == "PASSED":
        # -- CHILD_ENVIRONMENT --
        assert generated_config is not None and secret_context is not None
        try:
            launch_environment = build_child_environment(
                ambient_environ=ambient_environ,
                node_executable=node_executable,
                generated_config=generated_config,
                secret_context=secret_context,
                git_executable=git_executable,
            )
            _pass(CategoryBGateName.CHILD_ENVIRONMENT)
        except EnvironmentPolicyError:
            _fail(
                CategoryBGateName.CHILD_ENVIRONMENT, CategoryBFailureCode.CHILD_ENVIRONMENT_BUILD_FAILED
            )
        except Exception:
            _fail(CategoryBGateName.CHILD_ENVIRONMENT, CategoryBFailureCode.UNEXPECTED_EXCEPTION)

    if launch_environment is not None:
        # -- RPC_LAUNCH [LIVE RESOURCE CREATION POINT] --
        # live_resource_created is set as soon as the launch is ATTEMPTED,
        # not only on a confirmed pass: a launch that itself reports failure
        # may still have started a process, so teardown must not be skipped.
        live_resource_created = True
        rpc_outcome = _safe_call(CategoryBGateName.RPC_LAUNCH, launch_rpc, launch_environment)
        if isinstance(rpc_outcome, RpcLaunchOutcome):
            observed_pi_version = rpc_outcome.observed_pi_version
            if rpc_outcome.gate.passed:
                _pass(CategoryBGateName.RPC_LAUNCH)
            else:
                assert rpc_outcome.gate.failure_code is not None
                _fail(CategoryBGateName.RPC_LAUNCH, rpc_outcome.gate.failure_code)
        elif rpc_outcome is not None:
            _fail(CategoryBGateName.RPC_LAUNCH, CategoryBFailureCode.UNEXPECTED_EXCEPTION)
        # else: _safe_call already recorded UNEXPECTED_EXCEPTION.

    if gate_statuses[CategoryBGateName.RPC_LAUNCH.value] == "PASSED":
        # -- H1_EXTENSION_IDENTITY --
        h1_outcome = _safe_call(CategoryBGateName.H1_EXTENSION_IDENTITY, h1_check)
        if isinstance(h1_outcome, GateOutcome):
            if h1_outcome.passed:
                _pass(CategoryBGateName.H1_EXTENSION_IDENTITY)
            else:
                assert h1_outcome.failure_code is not None
                _fail(CategoryBGateName.H1_EXTENSION_IDENTITY, h1_outcome.failure_code)
        elif h1_outcome is not None:
            _fail(CategoryBGateName.H1_EXTENSION_IDENTITY, CategoryBFailureCode.UNEXPECTED_EXCEPTION)

    if gate_statuses[CategoryBGateName.H1_EXTENSION_IDENTITY.value] == "PASSED":
        # -- GET_COMMANDS --
        result = _safe_call(CategoryBGateName.GET_COMMANDS, get_commands)
        if isinstance(result, GetCommandsOutcome):
            commands_outcome = result
            if result.gate.passed:
                _pass(CategoryBGateName.GET_COMMANDS)
            else:
                assert result.gate.failure_code is not None
                _fail(CategoryBGateName.GET_COMMANDS, result.gate.failure_code)
        elif result is not None:
            _fail(CategoryBGateName.GET_COMMANDS, CategoryBFailureCode.UNEXPECTED_EXCEPTION)

    if gate_statuses[CategoryBGateName.GET_COMMANDS.value] == "PASSED":
        # -- GET_STATE --
        result = _safe_call(CategoryBGateName.GET_STATE, get_state)
        if isinstance(result, GetStateOutcome):
            state_outcome = result
            if result.gate.passed:
                _pass(CategoryBGateName.GET_STATE)
            else:
                assert result.gate.failure_code is not None
                _fail(CategoryBGateName.GET_STATE, result.gate.failure_code)
        elif result is not None:
            _fail(CategoryBGateName.GET_STATE, CategoryBFailureCode.UNEXPECTED_EXCEPTION)

    if gate_statuses[CategoryBGateName.GET_STATE.value] == "PASSED":
        # -- H2_PROVIDER_MODEL_IDENTITY (computed here, no new live call) --
        assert state_outcome is not None and route_descriptor is not None
        if (
            state_outcome.reported_provider == route_descriptor.provider_id
            and state_outcome.reported_model == route_descriptor.model_id
        ):
            _pass(CategoryBGateName.H2_PROVIDER_MODEL_IDENTITY)
        else:
            _fail(
                CategoryBGateName.H2_PROVIDER_MODEL_IDENTITY,
                CategoryBFailureCode.H2_PROVIDER_MODEL_IDENTITY_MISMATCH,
            )

    if gate_statuses[CategoryBGateName.H2_PROVIDER_MODEL_IDENTITY.value] == "PASSED":
        # -- TOOL_REGISTRY (computed here, no new live call) --
        assert commands_outcome is not None
        if frozenset(commands_outcome.command_names) == AUTHORIZED_TOOL_NAMES:
            _pass(CategoryBGateName.TOOL_REGISTRY)
        else:
            _fail(CategoryBGateName.TOOL_REGISTRY, CategoryBFailureCode.TOOL_REGISTRY_MISMATCH)

    if gate_statuses[CategoryBGateName.TOOL_REGISTRY.value] == "PASSED":
        # -- ROUTE_CHECK (reused i2_route wiring, unmodified) --
        assert route_descriptor is not None and secret_context is not None
        try:
            route_outcome: RouteCheckOutcome = run_offline_route_check(
                descriptor=route_descriptor, secret_context=secret_context, checker=route_checker
            )
        except Exception:
            _fail(CategoryBGateName.ROUTE_CHECK, CategoryBFailureCode.UNEXPECTED_EXCEPTION)
        else:
            if route_outcome.passed:
                _pass(CategoryBGateName.ROUTE_CHECK)
            else:
                _fail(CategoryBGateName.ROUTE_CHECK, CategoryBFailureCode.ROUTE_CHECK_FAILED)

    if gate_statuses[CategoryBGateName.ROUTE_CHECK.value] == "PASSED":
        # -- BROKER_READY --
        broker_outcome = _safe_call(CategoryBGateName.BROKER_READY, broker_ready)
        if isinstance(broker_outcome, GateOutcome):
            if broker_outcome.passed:
                _pass(CategoryBGateName.BROKER_READY)
            else:
                assert broker_outcome.failure_code is not None
                _fail(CategoryBGateName.BROKER_READY, broker_outcome.failure_code)
        elif broker_outcome is not None:
            _fail(CategoryBGateName.BROKER_READY, CategoryBFailureCode.UNEXPECTED_EXCEPTION)

    # -- zero semantic prompts confirmed (structural: this local never changes) --
    semantic_prompts_sent = 0

    outcome = (
        CategoryBOutcome.CATEGORY_B_GATE_PASSED
        if gate_statuses[CategoryBGateName.BROKER_READY.value] == "PASSED"
        else CategoryBOutcome.INFRASTRUCTURE_REFUSAL
    )

    # -- teardown + generated-config cleanup: attempted on EVERY path, pass or fail --
    teardown_status = _attempt_teardown(live_resource_created=live_resource_created, teardown=teardown)
    cleanup_status = _attempt_cleanup(generated_config)

    evidence = build_category_b_evidence(
        candidate=candidate,
        route_descriptor=route_descriptor,
        observed_pi_version=observed_pi_version,
        outcome=outcome,
        gate_statuses=gate_statuses,
        teardown=teardown_status,
        cleanup=cleanup_status,
        secret_context=secret_context,
    )

    return CategoryBControllerResult(
        candidate=candidate,
        outcome=outcome,
        semantic_prompts_sent=semantic_prompts_sent,
        failed_gate=failed_gate,
        failure_code=failure_code,
        gate_statuses=dict(gate_statuses),
        pi_config_created=generated_config is not None,
        live_resource_created=live_resource_created,
        teardown=teardown_status,
        cleanup=cleanup_status,
        evidence=evidence,
    )
