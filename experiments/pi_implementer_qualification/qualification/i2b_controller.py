"""I2B -- Category-B Zero-Prompt Live-Gate Controller (OFFLINE WIRING ONLY).

**This module runs no Pi/Node process, opens no socket, calls no model, and
reads no real credential.** It contains no ``subprocess``, ``socket``,
``http``, ``urllib`` or ``os.environ`` primitive at all -- a source-level
regression test in this package's offline suite enforces that mechanically.
What it implements is the STATE MACHINE, the RESOURCE AUTHORITY, and the
LIFECYCLE CLOSURE rule for the future Category-B zero-prompt compatibility
gate. Every future live operation is an INJECTED adapter; every offline test
supplies a synthetic double.

5F3B-I2B-FU2 -- what changed, and why
=====================================

I2B-FU1 was never accepted. The frozen 5F3B-I2A/FU3 design family names six
defects in it, every one of which is corrected here.

**1. ``get_commands`` enumerates SLASH COMMANDS, not the active tool
registry (FU3 Sec. 5).** FU1 gated ``TOOL_REGISTRY`` on
``sorted(reported command names) == ("aido_edit", "aido_read")``. That gate
was both unprovable -- Pi exposes NO RPC command that enumerates the active
tool registry, a fact source-verified in AR0-FU1 Sec. 4.1(j) and repeated in
AR1, AR2 and AR2D -- and unsatisfiable: ``aido_read``/``aido_edit`` are
registered with ``pi.registerTool`` while ``get_commands`` reports
``pi.registerCommand`` slash commands, so those two names can never appear
in a response at all. The gate is now
:attr:`CategoryBGateName.EXTENSION_COMMAND_NAMESPACE`, a PROVENANCE
partition over the top-level-``"extension"``-sourced entries: exactly one
``sourceInfo.source == "cli"`` entry, which must be the H1-validated
sentinel; any number of mechanically-established ``"inline"`` (Pi-owned)
entries, tolerated; anything else fails closed. The evidence records
``active_tool_registry_observation_available: false`` explicitly, and
carries AR2D Sec. 2.2's mandated three-way distinction verbatim.

**2. H1 is recomputed by AIDO from components (FU3 Sec. 6).** FU1 recorded
``GetCommandsObservation.extension_identity_matched`` -- a single
caller-supplied verdict -- as the compatibility fact without deriving
anything. The observation now carries the frozen evaluator's own five
components, and AIDO evaluates the conjunction itself.

**3. Every deterministic non-secret refusal now precedes the credential read
(FU3 Sec. 7).** FU1 called ``resolve_connection_after_preflight`` FIRST and
only then ``route_descriptor_for_candidate``, so
``run_category_b_controller(candidate="typo", ...)`` invoked the credential
reader once before refusing. The pre-credential prefix is now
``RUN_CORRELATION -> WORKSPACE_AUTHORITY -> ROUTE_DESCRIPTOR ->
NON_SECRET_PREFLIGHT``, and only then ``CONNECTION_VALUES``.

**4. Workspace authority is minted, never named (FU3 Sec. 8).** FU1 took
``workspace_root: str`` and ``experiment_root: str`` as arbitrary
caller-supplied strings and performed ``mkdir`` under one of them. Both
parameters are REMOVED; the controller takes one
:class:`~qualification.i2b_workspace.QualificationRunWorkspace`, which can
only be obtained by CREATING a fresh disposable root, and re-verifies it at
every consumption boundary.

**5. The creator partial-failure contract (FU3 Sec. 9.3/9.3.1).** No
authority-bearing partial handle crosses into the controller. Ownership
either transfers whole (a trusted full session) or stays with the creator
(which performs at most one bounded internal close and reports facts). AIDO
alone derives ``cleanup_verified_success``.

**6. Possession is not authority (FU3 Sec. 9.4).** FU1 still CALLED the
shutdown adapter for a session whose ``run_id``/``broker_session_id`` did
not match this run -- a live, side-effecting action against a resource this
run never proved it owns -- and merely withheld ``closure_satisfied``. The
adapter is now never called at all for such a session, and the refusal is
reported as its own honest state.

Plus FU3 Sec. 10: correlation-id generation failure is bounded as
``RUN_CORRELATION_UNAVAILABLE`` instead of escaping as a raw exception.

Gate order (this controller's own, derived from the frozen lifecycle)
--------------------------------------------------------------------

.. code-block:: text

      run correlation id minted           (bounded; FU3 Sec. 10)
      -> synthetic workspace authority     (verified + claimed for this run)
      -> route descriptor                  (deterministic, non-secret)
      -> non-secret preflight              (reused i2_credentials, unmodified)
    ------------------------------------------------ CREDENTIAL BOUNDARY
      -> connection-value read authority   (reused i2_credentials, unmodified)
      -> run-scoped secret context         (i2_secret_context)
      -> disposable generated Pi config    (i2_pi_config)     [RESOURCE]
      -> config/secret/route binding       (i2_composition)
      -> positive-allowlist child env      (i2_environment)
      -> broker session created            (injected)         [RESOURCE]
      -> broker reached READY              (from that session)
      -> runtime launched with the binding (injected)         [RESOURCE]
      -> Pi version observed        \\
      -> RPC launch shape valid      |  four INDEPENDENT facts from
      -> required flags accepted     |  ONE launch observation
      -> LF JSONL correlation        /
      -> get_commands understood    \\  three DISTINCT facts from
      -> H1 exact extension identity |  ONE get_commands observation
      -> extension command namespace/
      -> get_state understood       \\  two DISTINCT facts from
      -> H2 exact provider/model    /   ONE get_state observation
      -> no protocol/extension error       (injected, session-bound)
      -> exact candidate model served      (reused i2_route, unmodified)
      -- compatibility facts end here --
      -> runtime teardown                  (frozen O1 order: runtime first)
      -> broker shutdown                   (frozen O1 order: broker second)
      -> generated-config cleanup          (reused i2_cleanup, unmodified)
      -> retained-evidence safety gate     (reused qualification.safety)

Zero-prompt authority
---------------------

:data:`SEMANTIC_PROMPTS_SENT` is a module constant ``0``, and no name in this
module is ever bound to any other value for it. This module defines NO
function that accepts, sends, or forwards a semantic prompt, a task prompt,
or an agent instruction of any kind -- there is nothing here for such a value
to travel through. There is no candidate classification, no hard bar, no
ranking, and no ``AUTONOMOUS_PASS``/``AUTONOMOUS_FAIL``. **Every**
Category-B failure is a pre-prompt infrastructure refusal.

Truthful claim scope
--------------------

Teardown truthfulness is bounded. This module reports only that AIDO's own
teardown call was attempted and what it returned, and -- separately -- that
the broker's own lifecycle reached ``CLOSED``. It **never** claims a
descendant process was terminated, that Pi/provider inference stopped, or
that GPU work stopped. It likewise never claims anything about the contents
of the active tool registry, which Pi exposes no zero-prompt observation of.

Not implemented here, and not authorized by this slice: any live Pi/Node
launch, any real RPC/broker call, any real credential read, a real live
adapter, a generic ``RuntimeAdapter``/``AgentRuntime`` framework, a candidate
implementer, a fixer, or any code path that could send a semantic prompt.
"""

from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass, field, fields
from enum import Enum
from types import MappingProxyType
from typing import Any, Callable, ClassVar, Mapping, Sequence

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
    CREDENTIAL_MECHANISM,
    RouteCheckOutcome,
    RouteDescriptor,
    RouteDescriptorError,
    route_descriptor_for_candidate,
    run_offline_route_check,
)
from .records import CANDIDATE_MODEL_IDS
from .i2_secret_context import (
    InvalidBaseUrlError,
    QualificationRouteSecretContext,
    SecretContextError,
    build_secret_context,
)
from .i2b_session import (
    BrokerCreationObservation,
    BrokerCreationRequest,
    BrokerSession,
    BrokerShutdownObservation,
    GetCommandsObservation,
    GetStateObservation,
    ObservationError,
    ProtocolObservation,
    RuntimeLaunchObservation,
    RuntimeLaunchRequest,
    RuntimeSession,
    RuntimeShutdownObservation,
    require_exact_bool,
)
from .i2b_workspace import (
    QualificationRunWorkspace,
    WorkspaceAuthorityError,
    claim_run_workspace,
    verify_run_workspace,
)
from .safety import ArtifactSafetyContext, qualification_scrub_check

#: Category-B sends no semantic prompt, ever. Nothing in this module binds
#: any other value to the run's prompt count.
SEMANTIC_PROMPTS_SENT: int = 0

#: AR2D Sec. 2.2's MANDATED three-way distinction, carried in every Category-B
#: evidence body so an archived packet can never be read as a claim about the
#: active tool registry's contents.
#:
#: The old I2B-FU1 gate asserted exactly the fourth line's "NOT established"
#: statement as though it were established. It is not, and no zero-prompt
#: observation of it exists.
#:
#: **One line is deliberately scoped to THIS run rather than copied.** AR2D's
#: own second line reads "aido_read x2, aido_edit x1, no other observed" --
#: AR2's own live run's counts. A Category-B run sends zero semantic prompts,
#: so it observes NO tool call at all; reproducing AR2's counts here would
#: fabricate an observation this run never made. Every other line, and the
#: distinction's structure, are AR2D's verbatim.
TOOL_REGISTRY_CLAIM_SCOPE: tuple[str, ...] = (
    "configured registry allowlist   : aido_read, aido_edit      (AIDO's own argv)",
    "observed live tool calls        : not observed in a zero-prompt Category-B run",
    "extension identity              : independently handshaken (get_commands, H1)",
    "NOT established                 : an RPC registry query proving the active",
    "                                  runtime registry contained only those two",
)

_STATUS_NOT_REACHED = "NOT_REACHED"
_STATUS_PASSED = "PASSED"
_STATUS_NOT_REQUIRED = "NOT_REQUIRED"

#: The bounded shape every scrub FINDING CODE this package ever produces
#: actually has (FU2B). Every real code -- ``ar2.record``'s own
#: ``_FORBIDDEN_RECORD_SUBSTRINGS`` codes (e.g.
#: ``"authorization_header_text_present"``), ``ArtifactSafetyContext``'s own
#: needle codes (e.g. ``"api_key_value_present"``), this package's structural
#: findings (``"ipv4_literal_present"``, ``"record_not_ascii_representable"``),
#: and this module's own (``"safety_context_unprovable"``,
#: ``"evidence_not_yet_built"``) -- is lowercase ASCII words joined by
#: underscores. This is a CHARSET/LENGTH bound, deliberately not an exhaustive
#: enum: enumerating every code those other, independently-owned modules may
#: ever emit would be a second, drifting declaration of a fact only they
#: should own. A finding that is not a `str` at all, or does not match this
#: shape, is refused outright -- never coerced with `str(...)`, and never
#: echoed into the refusal message (the offending value could itself be the
#: unsafe thing this check exists to keep out).
_FINDING_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

#: FU2F: the three EXCLUSIVE construction origins a ``CategoryBEvidence``
#: instance can ever have -- WHICH classmethod (if any) produced it. Tracked
#: only to bind ``EVIDENCE_SAFETY``'s failure code to the actual evidence-
#: construction path, never to duplicate the scrub layer's own finding-code
#: taxonomy: this records WHICH BUILDER ran, nothing about WHAT it found.
_EVIDENCE_ORIGIN_UNBUILT = "unbuilt"
_EVIDENCE_ORIGIN_REFUSED = "refused"
_EVIDENCE_ORIGIN_BUILT = "built"
_EVIDENCE_ORIGINS: frozenset[str] = frozenset(
    {_EVIDENCE_ORIGIN_UNBUILT, _EVIDENCE_ORIGIN_REFUSED, _EVIDENCE_ORIGIN_BUILT}
)


class CategoryBFailureCode(str, Enum):
    """Bounded, declared Category-B failure codes. Never free-form prose."""

    RUN_CORRELATION_UNAVAILABLE = "RUN_CORRELATION_UNAVAILABLE"
    WORKSPACE_AUTHORITY_UNVERIFIED = "WORKSPACE_AUTHORITY_UNVERIFIED"
    NON_SECRET_PREFLIGHT_GATE_FAILED = "NON_SECRET_PREFLIGHT_GATE_FAILED"
    CONNECTION_VALUES_UNAVAILABLE = "CONNECTION_VALUES_UNAVAILABLE"
    ROUTE_DESCRIPTOR_INVALID = "ROUTE_DESCRIPTOR_INVALID"
    SECRET_CONTEXT_CONSTRUCTION_FAILED = "SECRET_CONTEXT_CONSTRUCTION_FAILED"
    PI_CONFIG_GENERATION_FAILED = "PI_CONFIG_GENERATION_FAILED"
    IDENTITY_BINDING_MISMATCH = "IDENTITY_BINDING_MISMATCH"
    CHILD_ENVIRONMENT_BUILD_FAILED = "CHILD_ENVIRONMENT_BUILD_FAILED"
    BROKER_CREATION_FAILED = "BROKER_CREATION_FAILED"
    BROKER_SESSION_MISMATCH = "BROKER_SESSION_MISMATCH"
    BROKER_NOT_READY = "BROKER_NOT_READY"
    RUNTIME_LAUNCH_FAILED = "RUNTIME_LAUNCH_FAILED"
    RUNTIME_LAUNCH_REQUEST_UNCONSTRUCTIBLE = "RUNTIME_LAUNCH_REQUEST_UNCONSTRUCTIBLE"
    RUNTIME_SESSION_MISMATCH = "RUNTIME_SESSION_MISMATCH"
    PI_VERSION_NOT_OBSERVED = "PI_VERSION_NOT_OBSERVED"
    RPC_LAUNCH_SHAPE_UNEXPECTED = "RPC_LAUNCH_SHAPE_UNEXPECTED"
    REQUIRED_LAUNCH_FLAGS_REJECTED = "REQUIRED_LAUNCH_FLAGS_REJECTED"
    LF_JSONL_CORRELATION_FAILED = "LF_JSONL_CORRELATION_FAILED"
    GET_COMMANDS_FAILED = "GET_COMMANDS_FAILED"
    GET_COMMANDS_RESPONSE_SHAPE_NOT_UNDERSTOOD = "GET_COMMANDS_RESPONSE_SHAPE_NOT_UNDERSTOOD"
    H1_EXTENSION_IDENTITY_MISMATCH = "H1_EXTENSION_IDENTITY_MISMATCH"
    UNEXPECTED_CLI_EXTENSION_COMMAND = "UNEXPECTED_CLI_EXTENSION_COMMAND"
    EXTENSION_COMMAND_PROVENANCE_UNKNOWN = "EXTENSION_COMMAND_PROVENANCE_UNKNOWN"
    GET_STATE_FAILED = "GET_STATE_FAILED"
    GET_STATE_RESPONSE_SHAPE_NOT_UNDERSTOOD = "GET_STATE_RESPONSE_SHAPE_NOT_UNDERSTOOD"
    H2_PROVIDER_MODEL_IDENTITY_MISMATCH = "H2_PROVIDER_MODEL_IDENTITY_MISMATCH"
    PROTOCOL_VIOLATION_OBSERVED = "PROTOCOL_VIOLATION_OBSERVED"
    EXTENSION_ERROR_OBSERVED = "EXTENSION_ERROR_OBSERVED"
    ROUTE_CHECK_FAILED = "ROUTE_CHECK_FAILED"
    RUNTIME_TEARDOWN_FAILED = "RUNTIME_TEARDOWN_FAILED"
    RUNTIME_TEARDOWN_AUTHORITY_UNAVAILABLE = "RUNTIME_TEARDOWN_AUTHORITY_UNAVAILABLE"
    RUNTIME_SHUTDOWN_REFUSED_FOREIGN_SESSION = "RUNTIME_SHUTDOWN_REFUSED_FOREIGN_SESSION"
    BROKER_SHUTDOWN_INCOMPLETE = "BROKER_SHUTDOWN_INCOMPLETE"
    BROKER_SHUTDOWN_AUTHORITY_UNAVAILABLE = "BROKER_SHUTDOWN_AUTHORITY_UNAVAILABLE"
    BROKER_SHUTDOWN_REFUSED_FOREIGN_SESSION = "BROKER_SHUTDOWN_REFUSED_FOREIGN_SESSION"
    CLOSED_BY_CREATOR_UNVERIFIED = "CLOSED_BY_CREATOR_UNVERIFIED"
    PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT = (
        "PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT"
    )
    GENERATED_CONFIG_CLEANUP_UNVERIFIED = "GENERATED_CONFIG_CLEANUP_UNVERIFIED"
    EVIDENCE_SCRUB_REFUSED = "EVIDENCE_SCRUB_REFUSED"
    SAFETY_CONTEXT_UNPROVABLE = "SAFETY_CONTEXT_UNPROVABLE"
    MALFORMED_ADAPTER_RESULT = "MALFORMED_ADAPTER_RESULT"
    ADAPTER_RAISED = "ADAPTER_RAISED"


class CategoryBGateName(str, Enum):
    """Every stage this controller gates, in exactly its evaluation order."""

    # -- compatibility facts, pre-credential --
    RUN_CORRELATION = "run_correlation"
    WORKSPACE_AUTHORITY = "workspace_authority"
    ROUTE_DESCRIPTOR = "route_descriptor"
    NON_SECRET_PREFLIGHT = "non_secret_preflight"
    # -- CREDENTIAL BOUNDARY --
    CONNECTION_VALUES = "connection_values"
    SECRET_CONTEXT = "secret_context"
    PI_CONFIG_GENERATION = "pi_config_generation"
    IDENTITY_BINDING = "identity_binding"
    CHILD_ENVIRONMENT = "child_environment"
    BROKER_SESSION = "broker_session"
    BROKER_READY = "broker_ready"
    RUNTIME_LAUNCH = "runtime_launch"
    PI_VERSION_OBSERVED = "pi_version_observed"
    RPC_LAUNCH_SHAPE = "rpc_launch_shape"
    REQUIRED_LAUNCH_FLAGS = "required_launch_flags"
    LF_JSONL_CORRELATION = "lf_jsonl_correlation"
    GET_COMMANDS = "get_commands"
    H1_EXTENSION_IDENTITY = "h1_extension_identity"
    EXTENSION_COMMAND_NAMESPACE = "extension_command_namespace"
    GET_STATE = "get_state"
    H2_PROVIDER_MODEL_IDENTITY = "h2_provider_model_identity"
    PROTOCOL_INTEGRITY = "protocol_integrity"
    ROUTE_CHECK = "route_check"
    # -- lifecycle closure --
    RUNTIME_TEARDOWN = "runtime_teardown"
    BROKER_SHUTDOWN = "broker_shutdown"
    GENERATED_CONFIG_CLEANUP = "generated_config_cleanup"
    EVIDENCE_SAFETY = "evidence_safety"


#: The gates that establish Category-B COMPATIBILITY, in order. Every one
#: must be ``PASSED`` for a run to be eligible for a terminal pass.
#:
#: **The order is load-bearing, not cosmetic** (FU3 Sec. 7.4): the position
#: of ``CONNECTION_VALUES`` -- the one credential read -- must be strictly
#: greater than ``RUN_CORRELATION``, ``WORKSPACE_AUTHORITY`` and
#: ``ROUTE_DESCRIPTOR``. A source-level offline test asserts exactly that.
COMPATIBILITY_GATES: tuple[CategoryBGateName, ...] = (
    CategoryBGateName.RUN_CORRELATION,
    CategoryBGateName.WORKSPACE_AUTHORITY,
    CategoryBGateName.ROUTE_DESCRIPTOR,
    CategoryBGateName.NON_SECRET_PREFLIGHT,
    CategoryBGateName.CONNECTION_VALUES,
    CategoryBGateName.SECRET_CONTEXT,
    CategoryBGateName.PI_CONFIG_GENERATION,
    CategoryBGateName.IDENTITY_BINDING,
    CategoryBGateName.CHILD_ENVIRONMENT,
    CategoryBGateName.BROKER_SESSION,
    CategoryBGateName.BROKER_READY,
    CategoryBGateName.RUNTIME_LAUNCH,
    CategoryBGateName.PI_VERSION_OBSERVED,
    CategoryBGateName.RPC_LAUNCH_SHAPE,
    CategoryBGateName.REQUIRED_LAUNCH_FLAGS,
    CategoryBGateName.LF_JSONL_CORRELATION,
    CategoryBGateName.GET_COMMANDS,
    CategoryBGateName.H1_EXTENSION_IDENTITY,
    CategoryBGateName.EXTENSION_COMMAND_NAMESPACE,
    CategoryBGateName.GET_STATE,
    CategoryBGateName.H2_PROVIDER_MODEL_IDENTITY,
    CategoryBGateName.PROTOCOL_INTEGRITY,
    CategoryBGateName.ROUTE_CHECK,
)

#: The one gate at which a credential value is read. Named so the ordering
#: assertion above is expressed against a symbol, not a literal index.
CREDENTIAL_READ_GATE: CategoryBGateName = CategoryBGateName.CONNECTION_VALUES

#: Every gate that must be established BEFORE the credential boundary.
PRE_CREDENTIAL_GATES: tuple[CategoryBGateName, ...] = (
    CategoryBGateName.RUN_CORRELATION,
    CategoryBGateName.WORKSPACE_AUTHORITY,
    CategoryBGateName.ROUTE_DESCRIPTOR,
    CategoryBGateName.NON_SECRET_PREFLIGHT,
)

#: The gates that establish LIFECYCLE CLOSURE. A compatibility pass whose
#: closure gates did not all pass is an ``INFRASTRUCTURE_REFUSAL``.
CLOSURE_GATES: tuple[CategoryBGateName, ...] = (
    CategoryBGateName.RUNTIME_TEARDOWN,
    CategoryBGateName.BROKER_SHUTDOWN,
    CategoryBGateName.GENERATED_CONFIG_CLEANUP,
    CategoryBGateName.EVIDENCE_SAFETY,
)


class CategoryBOutcome(str, Enum):
    """This controller's own terminal status.

    Never reuses or extends the I1 ``AutonomousClassification`` enum --
    Category-B never reaches a candidate-scoring decision, only a pre-prompt
    compatibility confirmation or a pre-prompt refusal. The refusal member's
    STRING VALUE deliberately matches
    ``qualification.outcomes.AutonomousClassification.INFRASTRUCTURE_REFUSAL``
    for vocabulary consistency, without importing that
    candidate-scoring-adjacent enum into this slice.
    """

    CATEGORY_B_GATE_PASSED = "CATEGORY_B_GATE_PASSED"
    INFRASTRUCTURE_REFUSAL = "INFRASTRUCTURE_REFUSAL"


class CategoryBControllerInputError(ValueError):
    """An AIDO-supplied controller argument is unusable. Refused before ANYTHING.

    Deliberately raised, not folded into a gate result. These are AIDO's OWN
    arguments, never adapter data or observation data. Refusing here --
    before the run correlation id is even minted, and therefore long before
    any connection value could be read -- means a call that could never have
    proceeded causes no credential read at all.
    """


class CategoryBSafetyContextError(Exception):
    """The run's full artifact safety context could not be PROVEN complete.

    Raised rather than silently emitting a partially-declared context.
    Carries a bounded reason code only -- never a value.
    """

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"category-B safety context refused: {reason_code}")
        self.reason_code = reason_code


# -- individually established compatibility facts ------------------------------


@dataclass(frozen=True)
class CompatibilityFacts:
    """The thirteen independently-established Category-B compatibility facts.

    Deliberately NOT one caller-supplied ``passed`` boolean. Each field
    records what AIDO itself derived from a bounded observation, so a reader
    can see WHICH fact was observed rather than only that "something passed".
    Every field is exactly ``bool``.

    ``pi_version_observed`` is provenance only: it records that a version was
    OBSERVABLE for this run, never that a particular version was authorized.

    ``no_unexpected_extension_command_observed`` replaces I2B-FU1's
    ``authorized_tool_registry_exact``. It records exactly what the corrected
    Category-B observability contract establishes -- that every reported
    top-level-``"extension"``-sourced command classified either as the one
    valid AIDO ``"cli"`` entry or as a mechanically-established Pi-owned
    ``"inline"`` entry -- and **never** anything about the contents of the
    active tool registry, which Pi exposes no zero-prompt observation of.
    """

    pi_version_observed: bool = False
    rpc_launch_shape_valid: bool = False
    required_launch_flags_accepted: bool = False
    lf_jsonl_correlation_succeeded: bool = False
    get_commands_response_shape_understood: bool = False
    h1_extension_identity_matched: bool = False
    no_unexpected_extension_command_observed: bool = False
    get_state_response_shape_understood: bool = False
    h2_provider_model_identity_matched: bool = False
    no_protocol_violation_observed: bool = False
    no_extension_error_observed: bool = False
    exact_candidate_model_served: bool = False
    broker_reached_required_ready_state: bool = False

    def __post_init__(self) -> None:
        for spec in fields(self):
            value = getattr(self, spec.name)
            if type(value) is not bool:
                raise ValueError(
                    f"CompatibilityFacts.{spec.name} must be exactly a bool; "
                    f"got {type(value).__name__}"
                )

    @property
    def all_established(self) -> bool:
        """Whether EVERY required compatibility fact was established."""
        return all(getattr(self, spec.name) for spec in fields(self))

    def as_dict(self) -> dict[str, bool]:
        """A FRESH dict copy. Mutating it cannot affect this object."""
        return {spec.name: getattr(self, spec.name) for spec in fields(self)}


# -- lifecycle closure statuses ------------------------------------------------


class ResourceClosureState(str, Enum):
    """The mutually exclusive closure outcomes ONE created resource can have.

    Modelled as one state rather than a bag of booleans so a contradictory
    combination -- "refused to act, yet attempted", "closed by its creator,
    yet AIDO holds authority" -- is not merely rejected by a validator but
    is unrepresentable. ``attempted``/``authority_available``/
    ``closure_satisfied`` are all DERIVED from this single value.
    """

    #: No creation was attempted, or nothing was ever created. Nothing owed.
    NOT_REQUIRED = "NOT_REQUIRED"
    #: AIDO's own shutdown call ran against a session it proved is its own,
    #: and the resource-kind's postcondition held.
    CLOSED_BY_ORCHESTRATOR = "CLOSED_BY_ORCHESTRATOR"
    #: AIDO's own shutdown ran and the postcondition did NOT hold (or the
    #: adapter raised, or returned a mismatched session id).
    SHUTDOWN_FAILED = "SHUTDOWN_FAILED"
    #: FU3 Sec. 9.4: the returned session is not provably this run's own, so
    #: the shutdown adapter is NEVER CALLED. Possession is not authority.
    SHUTDOWN_REFUSED_FOREIGN_SESSION = "SHUTDOWN_REFUSED_FOREIGN_SESSION"
    #: A creation was attempted but produced no object AIDO can act on.
    SHUTDOWN_AUTHORITY_UNAVAILABLE = "SHUTDOWN_AUTHORITY_UNAVAILABLE"
    #: FU3 Sec. 9.3 row 3: the creator retained ownership, attempted exactly
    #: one bounded internal close, and its observed postcondition held.
    CLOSED_BY_CREATOR_VERIFIED = "CLOSED_BY_CREATOR_VERIFIED"
    #: FU3 Sec. 9.3 row 3: same, but the postcondition did NOT hold.
    CLOSED_BY_CREATOR_UNVERIFIED = "CLOSED_BY_CREATOR_UNVERIFIED"
    #: FU3 Sec. 9.3 row 4: a resource was created and NO cleanup was ever
    #: attempted, by anyone. No controller recovery action is authorized.
    PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT = (
        "PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT"
    )


#: The only states in which this run left AIDO's own resource truthfully
#: closed (or had nothing to close).
_CLOSURE_SATISFIED_STATES = frozenset(
    {
        ResourceClosureState.NOT_REQUIRED,
        ResourceClosureState.CLOSED_BY_ORCHESTRATOR,
        ResourceClosureState.CLOSED_BY_CREATOR_VERIFIED,
    }
)

#: The only states in which AIDO's own shutdown adapter was actually called.
#: Every other state -- including both foreign-session refusals and every
#: creator-retained-ownership branch -- means ZERO calls by the controller.
_ORCHESTRATOR_ATTEMPTED_STATES = frozenset(
    {ResourceClosureState.CLOSED_BY_ORCHESTRATOR, ResourceClosureState.SHUTDOWN_FAILED}
)

#: FU2D: the only states reachable when the creation adapter actually returned
#: a FULL session object. Read directly off ``_close_runtime``/``_close_broker``:
#: both functions return every OTHER state from a branch ABOVE their
#: ``observation.session is None`` check, so a session-bearing state is
#: structurally unreachable without a returned session -- and, symmetrically,
#: once a session WAS returned, the authority-unavailable and
#: creator-retained-ownership branches can no longer be reached at all.
#:
#: **A FOREIGN session is still a session.** ``SHUTDOWN_REFUSED_FOREIGN_SESSION``
#: belongs here: the run refused to CALL the shutdown adapter for it, but the
#: adapter did return a real session object, so the corresponding
#: ``broker_created``/``runtime_session_established`` existence boolean is
#: ``True``. Refusing to act on a resource is not the same fact as the resource
#: never having been handed over.
_SESSION_BEARING_CLOSURE_STATES = frozenset(
    {
        ResourceClosureState.CLOSED_BY_ORCHESTRATOR,
        ResourceClosureState.SHUTDOWN_FAILED,
        ResourceClosureState.SHUTDOWN_REFUSED_FOREIGN_SESSION,
    }
)


@dataclass(frozen=True)
class _ResourceClosureStatus:
    """Shared closure accounting for one created resource. Never instantiated.

    Subclassed once per resource kind so each can name its own success text
    and its own failure codes, while the state machine, the derived booleans
    and the coherence rules are written exactly once.
    """

    state: ResourceClosureState
    failure_code: CategoryBFailureCode | None = None

    #: FU2C: per-STATE allowed failure-code sets for THIS resource kind, read
    #: directly off the concrete subclass's own ``_close_runtime``/
    #: ``_close_broker`` producer function. A ``ClassVar`` -- it describes
    #: the RESOURCE KIND, not one instance, and is therefore never a
    #: dataclass field. MUST be overridden by every concrete subclass; the
    #: empty default here refuses every unsatisfied state outright, so
    #: ``_ResourceClosureStatus`` itself (never instantiated -- see its own
    #: docstring) cannot silently accept an unconstrained code.
    _ALLOWED_FAILURE_CODES_BY_STATE: ClassVar[
        Mapping[ResourceClosureState, frozenset[CategoryBFailureCode]]
    ] = MappingProxyType({})

    def __post_init__(self) -> None:
        if not isinstance(self.state, ResourceClosureState):
            raise ValueError(f"{type(self).__name__}.state must be a ResourceClosureState")
        # FU2B: EXACT type, checked before `closure_satisfied` even inspects
        # it. Previously `failure_code` was only checked None-vs-not-None --
        # a raw string such as `"RUNTIME_TEARDOWN_FAILED"` constructed
        # successfully and only blew up LATER, with an unrelated
        # `AttributeError`, the first time `.status_text` read `.value` off
        # it. Found during this design's own post-implementation self-review.
        if self.failure_code is not None and type(self.failure_code) is not CategoryBFailureCode:
            raise ValueError(
                f"{type(self).__name__}.failure_code must be None or exactly a "
                "CategoryBFailureCode"
            )
        if self.closure_satisfied:
            if self.failure_code is not None:
                raise ValueError(
                    f"{type(self).__name__}: a satisfied closure must not carry a "
                    "failure_code"
                )
            return
        if self.failure_code is None:
            raise ValueError(
                f"{type(self).__name__}: an unsatisfied closure must name a failure_code"
            )
        # FU2C: constrain failure_code by BOTH resource kind (this concrete
        # subclass's own table below) AND closure state -- never merely "any
        # CategoryBFailureCode member". Independent review reproduced e.g.
        # ``RuntimeTeardownStatus(state=SHUTDOWN_FAILED,
        # failure_code=BROKER_SHUTDOWN_INCOMPLETE)`` and a foreign-session
        # state carrying the generic teardown-failed code instead of the
        # foreign-session-specific one -- both constructed successfully
        # before this check existed, so the closure gate then trusted that
        # typed object's own ``status_text`` as internally-consistent but
        # FALSE evidence. A code valid for one state, or for one resource
        # kind, is not automatically valid for another.
        allowed = type(self)._ALLOWED_FAILURE_CODES_BY_STATE.get(self.state, frozenset())
        if self.failure_code not in allowed:
            raise ValueError(
                f"{type(self).__name__}: failure_code {self.failure_code.value!r} is "
                f"not valid for state {self.state.value!r} on this resource kind "
                f"(allowed: {sorted(code.value for code in allowed)})"
            )

    @property
    def closure_satisfied(self) -> bool:
        return self.state in _CLOSURE_SATISFIED_STATES

    @property
    def attempted(self) -> bool:
        """Whether AIDO's OWN shutdown adapter was called for this resource."""
        return self.state in _ORCHESTRATOR_ATTEMPTED_STATES

    @property
    def authority_available(self) -> bool:
        """Whether AIDO held a session it had proven authority to act on.

        ``False`` for every foreign-session refusal: possession of a returned
        object is not authority over the resource it names.
        """
        return self.attempted

    @property
    def resource_creation_attempted(self) -> bool:
        return self.state is not ResourceClosureState.NOT_REQUIRED


@dataclass(frozen=True)
class RuntimeTeardownStatus(_ResourceClosureStatus):
    """Whether AIDO's own runtime teardown was required, possible, and closed.

    **Claim scope.** ``succeeded`` means AIDO's own shutdown call returned AND
    reported that AIDO's own DIRECT child exited. It is never a claim that a
    descendant process was terminated, that Pi/provider inference stopped, or
    that GPU work stopped.
    """

    #: FU2C: mechanically read off ``_close_runtime``'s own return sites --
    #: never guessed. ``CLOSED_BY_CREATOR_UNVERIFIED``/
    #: ``PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT`` genuinely ARE the
    #: same two codes on both resource kinds (``_RUNTIME_CLOSURE_FAILURE_CODES``
    #: and ``_BROKER_CLOSURE_FAILURE_CODES`` are literally the same mapping
    #: in the source); every other entry here is runtime-only.
    _ALLOWED_FAILURE_CODES_BY_STATE: ClassVar[
        Mapping[ResourceClosureState, frozenset[CategoryBFailureCode]]
    ] = MappingProxyType(
        {
            ResourceClosureState.SHUTDOWN_AUTHORITY_UNAVAILABLE: frozenset(
                {CategoryBFailureCode.RUNTIME_TEARDOWN_AUTHORITY_UNAVAILABLE}
            ),
            ResourceClosureState.SHUTDOWN_REFUSED_FOREIGN_SESSION: frozenset(
                {CategoryBFailureCode.RUNTIME_SHUTDOWN_REFUSED_FOREIGN_SESSION}
            ),
            # `_close_runtime`'s SHUTDOWN_FAILED branches: the adapter-raised/
            # malformed-result branch and the postcondition-not-held branch
            # both emit RUNTIME_TEARDOWN_FAILED; the session-id-mismatch
            # branch emits RUNTIME_SESSION_MISMATCH. No other code is ever
            # returned for this state.
            ResourceClosureState.SHUTDOWN_FAILED: frozenset(
                {
                    CategoryBFailureCode.RUNTIME_TEARDOWN_FAILED,
                    CategoryBFailureCode.RUNTIME_SESSION_MISMATCH,
                }
            ),
            ResourceClosureState.CLOSED_BY_CREATOR_UNVERIFIED: frozenset(
                {CategoryBFailureCode.CLOSED_BY_CREATOR_UNVERIFIED}
            ),
            ResourceClosureState.PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT: frozenset(
                {CategoryBFailureCode.PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT}
            ),
        }
    )

    @property
    def succeeded(self) -> bool:
        return self.state is ResourceClosureState.CLOSED_BY_ORCHESTRATOR

    @property
    def status_text(self) -> str:
        if self.state is ResourceClosureState.NOT_REQUIRED:
            return _STATUS_NOT_REQUIRED
        if self.state is ResourceClosureState.CLOSED_BY_ORCHESTRATOR:
            return "SUCCEEDED"
        if self.state is ResourceClosureState.CLOSED_BY_CREATOR_VERIFIED:
            return ResourceClosureState.CLOSED_BY_CREATOR_VERIFIED.value
        code = self.failure_code or CategoryBFailureCode.RUNTIME_TEARDOWN_FAILED
        return f"FAILED:{code.value}"


@dataclass(frozen=True)
class BrokerShutdownStatus(_ResourceClosureStatus):
    """Whether AIDO's own broker shutdown was required, possible, and CLOSED.

    ``reached_closed`` is the broker lifecycle's own terminal state, as frozen
    AR2's ``BrokerServer.shutdown()`` reports it -- never a claim about any
    process. ``STATE_TEARDOWN_INCOMPLETE`` is not verified closure.
    """

    #: FU2C: mechanically read off ``_close_broker``'s own return sites --
    #: the exact mirror of ``RuntimeTeardownStatus``'s own table, with the
    #: broker's own authority/foreign-session/failed codes in place of the
    #: runtime ones. The two creator-retained-ownership codes are genuinely
    #: shared (see ``RuntimeTeardownStatus`` for why).
    _ALLOWED_FAILURE_CODES_BY_STATE: ClassVar[
        Mapping[ResourceClosureState, frozenset[CategoryBFailureCode]]
    ] = MappingProxyType(
        {
            ResourceClosureState.SHUTDOWN_AUTHORITY_UNAVAILABLE: frozenset(
                {CategoryBFailureCode.BROKER_SHUTDOWN_AUTHORITY_UNAVAILABLE}
            ),
            ResourceClosureState.SHUTDOWN_REFUSED_FOREIGN_SESSION: frozenset(
                {CategoryBFailureCode.BROKER_SHUTDOWN_REFUSED_FOREIGN_SESSION}
            ),
            # `_close_broker`'s SHUTDOWN_FAILED branches: the adapter-raised/
            # malformed-result branch and the reached_closed=False branch
            # both emit BROKER_SHUTDOWN_INCOMPLETE; the session-id-mismatch
            # branch emits BROKER_SESSION_MISMATCH. No other code is ever
            # returned for this state.
            ResourceClosureState.SHUTDOWN_FAILED: frozenset(
                {
                    CategoryBFailureCode.BROKER_SHUTDOWN_INCOMPLETE,
                    CategoryBFailureCode.BROKER_SESSION_MISMATCH,
                }
            ),
            ResourceClosureState.CLOSED_BY_CREATOR_UNVERIFIED: frozenset(
                {CategoryBFailureCode.CLOSED_BY_CREATOR_UNVERIFIED}
            ),
            ResourceClosureState.PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT: frozenset(
                {CategoryBFailureCode.PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT}
            ),
        }
    )

    @property
    def reached_closed(self) -> bool:
        return self.state is ResourceClosureState.CLOSED_BY_ORCHESTRATOR

    @property
    def status_text(self) -> str:
        if self.state is ResourceClosureState.NOT_REQUIRED:
            return _STATUS_NOT_REQUIRED
        if self.state is ResourceClosureState.CLOSED_BY_ORCHESTRATOR:
            return "CLOSED"
        if self.state is ResourceClosureState.CLOSED_BY_CREATOR_VERIFIED:
            return ResourceClosureState.CLOSED_BY_CREATOR_VERIFIED.value
        code = self.failure_code or CategoryBFailureCode.BROKER_SHUTDOWN_INCOMPLETE
        return f"FAILED:{code.value}"


#: Sanity (FU2C): every UNSATISFIED closure state (every ``ResourceClosureState``
#: member outside ``_CLOSURE_SATISFIED_STATES``) has an entry in BOTH
#: resource-kind tables above -- never a subset, a superset, or a state one
#: table forgot. Asserted at import time so the tables can never silently
#: drift from ``ResourceClosureState`` itself.
_UNSATISFIED_CLOSURE_STATES: frozenset[ResourceClosureState] = frozenset(
    set(ResourceClosureState) - _CLOSURE_SATISFIED_STATES
)
assert set(RuntimeTeardownStatus._ALLOWED_FAILURE_CODES_BY_STATE) == _UNSATISFIED_CLOSURE_STATES
assert set(BrokerShutdownStatus._ALLOWED_FAILURE_CODES_BY_STATE) == _UNSATISFIED_CLOSURE_STATES


def _require_category_b_cleanup_failure_shape(
    classification: CleanupFailureClassification,
) -> None:
    """FU2C: bind ``classification`` to the ONE shape Category-B can ever
    produce -- ``classify_cleanup_failure(semantic_prompts_sent=0)`` -- by
    comparing it field-by-field against a FRESH call to that same frozen,
    reused function, rather than trusting the exact-TYPE check alone.

    ``CleanupFailureClassification`` (frozen ``i2_cleanup``, deliberately not
    modified here) performs no field validation of its own, so an exact-
    type-correct but internally-impossible instance -- e.g.
    ``CleanupFailureClassification(semantic_prompts_sent=1,
    autonomous_classification=<the pre-prompt member>, run_validity=None,
    scoring_eligible=False)``, a shape ``classify_cleanup_failure`` itself
    can never return -- previously constructed successfully and was accepted
    by ``CleanupStatus`` on type alone. Category-B is structurally
    pre-prompt (:data:`SEMANTIC_PROMPTS_SENT` is always ``0``), so a genuine
    cleanup failure here can only ever be that function's own ``0`` branch.

    Comparing against a freshly minted REFERENCE instance -- rather than
    re-declaring its four field values by importing the ``outcomes``/
    ``validity`` enums here -- means this check can never itself drift from
    what ``classify_cleanup_failure`` actually returns, and this module never
    needs to name ``AutonomousClassification`` (see
    ``test_no_candidate_scoring_machinery_is_reachable``, which forbids that
    token here). Every comparison is by IDENTITY or exact type, never by
    truthiness: a hand-built ``semantic_prompts_sent=False`` (``False == 0``
    in Python) or ``scoring_eligible`` as a non-``bool`` stand-in is refused
    outright rather than coerced.
    """
    reference = classify_cleanup_failure(semantic_prompts_sent=SEMANTIC_PROMPTS_SENT)
    if (
        type(classification.semantic_prompts_sent) is not int
        or classification.semantic_prompts_sent != reference.semantic_prompts_sent
    ):
        raise ValueError(
            "CleanupStatus.classification.semantic_prompts_sent must be exactly "
            f"{reference.semantic_prompts_sent!r} -- Category-B is structurally "
            "pre-prompt"
        )
    if classification.autonomous_classification is not reference.autonomous_classification:
        raise ValueError(
            "CleanupStatus.classification.autonomous_classification must be "
            "exactly classify_cleanup_failure(semantic_prompts_sent=0)'s own "
            "pre-prompt classification"
        )
    if classification.run_validity is not None:
        raise ValueError(
            "CleanupStatus.classification.run_validity must be None -- a "
            "pre-prompt refusal carries no run_validity"
        )
    require_exact_bool(
        "CleanupStatus.classification.scoring_eligible", classification.scoring_eligible
    )
    if classification.scoring_eligible:
        raise ValueError("CleanupStatus.classification.scoring_eligible must be exactly False")


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
        require_exact_bool("CleanupStatus.attempted", self.attempted)
        if not self.attempted:
            if self.scrub_verified is not None or self.classification is not None:
                raise ValueError("CleanupStatus: attempted=False must carry no other field")
            return
        if self.scrub_verified is None:
            raise ValueError("CleanupStatus: attempted=True requires scrub_verified")
        # FU2A: EXACT bool, never Python truthiness. "false", 1, 0, None-like
        # sentinels and any other truthy/falsy stand-in are refused outright --
        # the earlier `if self.scrub_verified` / `bool(self.scrub_verified)`
        # shape let a non-empty string such as "false" construct successfully
        # and then report VERIFIED_REMOVED / closure_satisfied=True.
        require_exact_bool("CleanupStatus.scrub_verified", self.scrub_verified)
        if self.scrub_verified and self.classification is not None:
            raise ValueError("CleanupStatus: a verified cleanup must not carry a classification")
        if not self.scrub_verified and self.classification is None:
            raise ValueError("CleanupStatus: a failed/unverified cleanup requires a classification")
        # FU2B: EXACT type, same reasoning as _ResourceClosureStatus.failure_code
        # above -- a raw non-`CleanupFailureClassification` value previously
        # constructed successfully and only failed LATER, inside
        # `.status_text`, with an unrelated `AttributeError`.
        if self.classification is not None and type(self.classification) is not CleanupFailureClassification:
            raise ValueError(
                "CleanupStatus.classification must be None or exactly a "
                "CleanupFailureClassification"
            )
        if self.classification is not None:
            # FU2C: exact TYPE alone does not prove the classification is an
            # actually-reachable Category-B shape -- see
            # `_require_category_b_cleanup_failure_shape`.
            _require_category_b_cleanup_failure_shape(self.classification)

    @property
    def closure_satisfied(self) -> bool:
        """No config created is satisfied; a created config must be VERIFIED gone.

        ``scrub_verified`` is already proven to be an exact ``bool`` by
        ``__post_init__`` (or ``None`` when nothing was attempted) -- this
        never applies ``bool(...)`` to a value that has not already passed
        that check, so no truthy/falsy stand-in can slip through here.
        """
        if not self.attempted:
            return True
        return self.scrub_verified

    @property
    def status_text(self) -> str:
        """The gate-status text for THIS cleanup, in the SAME
        ``CategoryBFailureCode`` universe every other gate's text uses.

        FU2B fix: this used to embed
        ``self.classification.autonomous_classification.value`` -- an
        ``AutonomousClassification`` member, a DIFFERENT enum than
        ``CategoryBFailureCode``. The controller's own closure loop always
        separately calls
        ``_fail(GENERATED_CONFIG_CLEANUP, CategoryBFailureCode.GENERATED_CONFIG_CLEANUP_UNVERIFIED)``
        for an unverified cleanup (``CleanupStatus`` carries no
        ``failure_code`` field for ``getattr(status, "failure_code", None)``
        to find, so the loop's ``or default_code`` fallback always fires) --
        and `_fail` OVERWRITES `gate_statuses[GENERATED_CONFIG_CLEANUP]` with
        that fixed code immediately afterward. So the typed object's own
        property and what the controller actually recorded for the SAME gate
        DISAGREED, and the evidence body carried BOTH strings under two
        different keys (``gate_statuses['generated_config_cleanup']`` and
        ``orchestrator_generated_config_cleanup_status``) -- found via the
        new gate-status/typed-object equality binding added in this phase,
        reproduced through the real controller pipeline, not merely
        synthetically. ``classification`` remains a real, useful diagnostic
        fact on this object (unchanged, still required/validated); it is
        simply no longer the source of the STATUS TEXT surface, which must
        agree with the controller's own fixed code for this gate.
        """
        if not self.attempted:
            return _STATUS_NOT_REQUIRED
        if self.scrub_verified:
            return "VERIFIED_REMOVED"
        assert self.classification is not None
        return f"FAILED:{CategoryBFailureCode.GENERATED_CONFIG_CLEANUP_UNVERIFIED.value}"


# -- immutable evidence --------------------------------------------------------


@dataclass(frozen=True)
class CategoryBEvidence:
    """Either a retention-ready safe evidence body, or a bounded refusal.

    **FU2A: ``retention_ready``/``scrub_clean``/the serialized body are no
    longer caller-supplied constructor arguments at all.** Independent review
    found that the PUBLIC dataclass constructor accepted them as ordinary
    fields -- so
    ``CategoryBEvidence(retention_ready=True, scrub_clean=True,
    scrub_findings=(), _serialized='{"api_key": "raw-secret"}')`` constructed
    successfully. Nothing proved the serialized body had ever actually been
    passed through :func:`~qualification.safety.qualification_scrub_check`;
    ``retention_ready`` was partly a caller ASSERTION, exactly the class of
    defect this design already closed once for H1 and for the FU3C cleanup
    postcondition -- a component/verdict split, never a bare trusted boolean.

    **The fix, mirroring that same pattern.** Every field is now
    ``init=False``: the public, auto-generated ``__init__`` takes NO
    arguments and always constructs the safe, inert, ``retention_ready=False``
    default. There is no supported way to pass ``retention_ready=True`` (or
    any other field) directly to the constructor -- attempting to do so is a
    ``TypeError`` (unexpected keyword argument), not a value that could be
    validated and accepted. The ONLY way to obtain a populated instance is
    through the two package-internal classmethods below, and both DERIVE
    every field rather than accepting it:

    - :meth:`_build_from_payload` runs the frozen, unmodified
      ``qualification_scrub_check`` on the payload ITSELF, inside this
      class -- the boolean and the serialized body it returns are always a
      direct function of that one real call, never of a caller's say-so;
    - :meth:`_refused` is for the one caller (a run whose safety context
      could not be proven complete) that never gets a payload to check at
      all; it can only ever produce the unconditionally-false, unconditionally
      body-less shape.

    Both are single-underscore, package-internal, and are called from exactly
    one production call site each (``_build_evidence`` and
    ``run_category_b_controller``'s safety-context-unprovable branch). This is
    a correctness/integrity control against a caller (including a future
    refactor) that starts trusting a value rather than deriving it -- the
    same honestly-scoped residual already stated for the H1 adapter contract:
    it does not defend against a caller willing to import and call the
    private classmethod directly with a fabricated ``safety`` object, because
    at that point the caller already has everything needed to fabricate
    unsafe evidence by construction, and this object cannot see past its own
    inputs.

    **FU2F: each classmethod also stamps its own construction origin**
    (:data:`_EVIDENCE_ORIGIN_REFUSED`/:data:`_EVIDENCE_ORIGIN_BUILT`, the bare
    constructor's untouched default is :data:`_EVIDENCE_ORIGIN_UNBUILT`) --
    tracked so :class:`CategoryBControllerResult` can bind ``EVIDENCE_SAFETY``'s
    failure code to WHICH construction path actually produced this instance,
    not merely to ``retention_ready``. This is a provenance marker naming
    which builder ran, never a second declaration of what the scrub layer
    found.

    **Immutable after construction, through every supported API.** The body is
    held as one canonical, already-scrub-checked JSON string; every
    :meth:`as_dict` call returns a FRESHLY deserialized dict, so no caller
    ever receives a reference into this object's state and no mutation of a
    returned dict can rewrite the evidence, the gate statuses nested inside
    it, or a later reader's view. The scrub result is exposed as an immutable
    ``tuple`` of bounded finding codes plus a ``bool`` -- never a mutable dict
    whose ``clean`` key could be flipped after validation.

    **The payload is never retained on a refused instance, and never retained
    at all beyond the one scrub-check call.** ``_build_from_payload`` takes
    the raw payload as a local parameter, never as a stored field -- it is
    not assigned to ``self`` anywhere, so no raw (possibly secret-bearing)
    diagnostic can be read back off a refused (or any) evidence object,
    including through ``repr()``/``str()``, which this class never overrides
    to print internal state beyond the bounded fields below.

    ``retention_ready`` is ``True`` only when the scrub gate found nothing; a
    refused body is not retained here in any form.
    """

    retention_ready: bool = field(init=False, default=False)
    scrub_clean: bool = field(init=False, default=False)
    scrub_findings: tuple[str, ...] = field(init=False, default=("evidence_not_yet_built",))
    _serialized: str | None = field(init=False, default=None, repr=False)
    #: FU2F: WHICH classmethod (if any) produced this instance -- never
    #: caller-settable, and never a finding-code taxonomy. See
    #: :data:`_EVIDENCE_ORIGINS` for the exact three values.
    _origin: str = field(init=False, default=_EVIDENCE_ORIGIN_UNBUILT, repr=False)

    def __post_init__(self) -> None:
        self._check_invariants()

    def _check_invariants(self) -> None:
        """The ONE coherence check, run at ordinary construction AND again,
        explicitly, after either classmethod below mutates a fresh instance
        via ``object.__setattr__`` (which does not re-trigger
        ``__post_init__``). Never trust a single call site to have been the
        only path to a populated instance.

        **Subclassing is refused outright, not merely discouraged.** For an
        ``init=False`` field with a plain (non-factory) default, the
        dataclass-generated ``__init__`` never calls ``object.__setattr__``
        at all -- it relies on the class-level default attribute. That means
        a SUBCLASS overriding ``retention_ready`` as a read-only property
        can construct successfully via the bare, no-argument ``cls()`` call
        (no ``AttributeError``, unlike assigning to an ordinary frozen
        field) and immediately report ``retention_ready is True`` with
        NOTHING ever having been scrub-checked -- found during this design's
        own post-implementation self-review. The exact-type check at
        :class:`CategoryBControllerResult`'s consumption boundary already
        refuses any such subclass instance, but this object should not rely
        on a single downstream caller to be the only thing enforcing that;
        it refuses the subclass itself, at the earliest possible point.
        """
        if type(self) is not CategoryBEvidence:
            raise ValueError(
                "CategoryBEvidence: subclassing is refused -- every field this "
                "object reports must be derivable only through this exact type's "
                "own construction paths"
            )
        if type(self.retention_ready) is not bool or type(self.scrub_clean) is not bool:
            raise ValueError("CategoryBEvidence: retention_ready/scrub_clean must be exactly bool")
        if not isinstance(self.scrub_findings, tuple) or not all(
            isinstance(entry, str) for entry in self.scrub_findings
        ):
            raise ValueError("CategoryBEvidence.scrub_findings must be a tuple of str")
        # FU2F: exact membership in the three recognized construction
        # origins -- never a free-form string. This is a provenance marker,
        # not a scrub-finding vocabulary.
        if self._origin not in _EVIDENCE_ORIGINS:
            raise ValueError(
                "CategoryBEvidence._origin must be one of the recognized construction "
                f"origins {sorted(_EVIDENCE_ORIGINS)}"
            )
        if self.scrub_clean != (not self.scrub_findings):
            raise ValueError(
                "CategoryBEvidence: scrub_clean must agree exactly with scrub_findings "
                "-- a 'clean' result carrying findings, or a 'dirty' result carrying "
                "none, is not a state this object may describe"
            )
        if self.retention_ready:
            if not self.scrub_clean:
                raise ValueError("CategoryBEvidence: retention_ready requires a clean scrub")
            if self._serialized is None:
                raise ValueError("CategoryBEvidence: retention_ready requires an evidence body")
        elif self._serialized is not None:
            raise ValueError("CategoryBEvidence: a refused evidence body is never retained")

    @classmethod
    def _build_from_payload(
        cls, payload: Mapping[str, Any], safety: ArtifactSafetyContext
    ) -> "CategoryBEvidence":
        """The ONLY path to a ``retention_ready=True`` instance.

        Runs the frozen ``qualification_scrub_check`` itself, on ``payload``
        exactly as given, and derives every field from that ONE call's
        result -- never from a caller-asserted boolean. ``payload`` is a
        local parameter only; it is never stored on the returned instance.
        """
        check = qualification_scrub_check(dict(payload), safety)
        raw_clean = check.get("clean") if isinstance(check, dict) else None
        raw_findings = check.get("findings") if isinstance(check, dict) else None
        # FU2A: the frozen helper's OWN return shape is consumed fail-closed,
        # exactly the same discipline applied to i2_cleanup's result above --
        # never `bool(...)` on a value that has not already been proven to be
        # exactly the expected type. A malformed/unexpected shape from a
        # trusted internal helper is refused loudly (this should never
        # happen against the real implementation) rather than silently
        # coerced into a passing verdict.
        if type(raw_clean) is not bool or not isinstance(raw_findings, list):
            raise ValueError(
                "CategoryBEvidence: qualification_scrub_check returned an "
                "unrecognized shape; refusing rather than guessing"
            )
        # FU2B: every finding must ALREADY be an exact, bounded str -- never
        # `str(entry)`. A hostile/malformed entry (a non-string object, or a
        # string outside the bounded shape every real finding code has) is
        # refused outright, and its value is never interpolated into the
        # refusal message: `str()`/`repr()` of an untrusted object is exactly
        # the kind of accidental disclosure this scrub layer exists to
        # prevent, and calling either on it here would defeat that purpose.
        for _entry in raw_findings:
            if type(_entry) is not str or not _FINDING_CODE_PATTERN.fullmatch(_entry):
                raise ValueError(
                    "CategoryBEvidence: qualification_scrub_check returned an "
                    "unrecognized finding entry; refusing rather than "
                    "stringifying or retaining it"
                )
        findings = tuple(raw_findings)
        instance = cls()
        object.__setattr__(instance, "scrub_findings", findings)
        object.__setattr__(instance, "scrub_clean", raw_clean)
        object.__setattr__(instance, "_origin", _EVIDENCE_ORIGIN_BUILT)
        if raw_clean:
            object.__setattr__(instance, "retention_ready", True)
            object.__setattr__(
                instance, "_serialized", json.dumps(dict(payload), ensure_ascii=True, sort_keys=True)
            )
        instance._check_invariants()
        return instance

    @classmethod
    def _refused(cls, finding_codes: tuple[str, ...]) -> "CategoryBEvidence":
        """The unconditional-refusal shape, for a run with no payload to check.

        ``retention_ready``/``scrub_clean`` stay at their safe ``False``
        defaults and no body is ever set -- this classmethod cannot produce a
        retained body under any input.
        """
        # FU2B: EXACT str type (never a subclass) and the SAME bounded
        # charset/length shape `_build_from_payload` requires -- one finding-
        # code contract, enforced identically at both construction paths.
        if not isinstance(finding_codes, tuple) or not finding_codes:
            raise ValueError("CategoryBEvidence._refused requires a non-empty tuple of str codes")
        for _entry in finding_codes:
            if type(_entry) is not str or not _FINDING_CODE_PATTERN.fullmatch(_entry):
                raise ValueError(
                    "CategoryBEvidence._refused: every finding code must be an exact, "
                    "bounded str"
                )
        instance = cls()
        object.__setattr__(instance, "scrub_findings", finding_codes)
        object.__setattr__(instance, "_origin", _EVIDENCE_ORIGIN_REFUSED)
        instance._check_invariants()
        return instance

    def as_dict(self) -> dict[str, Any]:
        """A FRESH, independent copy of the retained body (``{}`` if refused)."""
        if self._serialized is None:
            return {}
        return json.loads(self._serialized)

    def as_json(self) -> str:
        """The canonical serialized body, or ``""`` when nothing was retained."""
        return self._serialized or ""


#: FU2E: the exact SAFE INTERMEDIATE shape the bare, no-argument
#: ``CategoryBEvidence()`` constructor produces -- legitimate to construct
#: (it is the harmless placeholder before either builder classmethod runs),
#: but never a shape ``run_category_b_controller`` itself returns: every real
#: path calls either ``_refused`` (a real, non-empty finding-code tuple) or
#: ``_build_from_payload`` (a real scrub-check result). Derived from a fresh
#: instance rather than a duplicated literal, so this can never drift from
#: the dataclass field default it names.
_EVIDENCE_NOT_YET_BUILT_SENTINEL: tuple[str, ...] = CategoryBEvidence().scrub_findings

#: FU2F: the exact, sole finding-code shape the controller's own
#: safety-context-unprovable branch ever passes to ``CategoryBEvidence._refused``
#: (the ONE production call site, in ``run_category_b_controller``). Defined
#: once and reused at BOTH that real call site and the terminal-result
#: validator below, so the two can never drift apart.
_SAFETY_CONTEXT_UNPROVABLE_REFUSAL: tuple[str, ...] = ("safety_context_unprovable",)


# -- terminal-result cross-field + gate-status + evidence-binding closure ------
# -- (FU2A structural checks, made PER-GATE and CROSS-FIELD in FU2B) -----------
#
# FU2A closed individual TYPES (exact-type checks on every nested value) and
# a single GLOBAL vocabulary of gate-status strings. Independent review found
# that was not enough: the vocabulary was global, so ANY known-good string
# was accepted on ANY gate -- a genuine, reproduced counterexample had
# ``route_check = "NOT_REQUIRED"`` (a text only a CLOSURE gate ever produces)
# accepted inside an otherwise-passing result. Worse, nothing at all related
# ``pi_config_created``/``broker_created``/``runtime_session_established`` to
# the TYPED closure objects describing the very same resources, so
# ``pi_config_created=True`` alongside ``cleanup.attempted=False`` -- and
# ``runtime_teardown.state=NOT_REQUIRED``/``broker_shutdown.state=NOT_REQUIRED``
# alongside a genuine trusted session -- both constructed a
# ``CATEGORY_B_GATE_PASSED`` result. And nothing bound the retained
# ``CategoryBEvidence`` body to the RESULT consuming it at all: an evidence
# object scrub-built from an unrelated payload (``{"ok": True}``) was accepted
# into any result whatsoever.
#
# What follows closes all three, each by the SMALLEST mechanically sound
# means available:
#
# 1. **Per-gate status validation.** The three LIFECYCLE CLOSURE gates
#    (``RUNTIME_TEARDOWN``/``BROKER_SHUTDOWN``/``GENERATED_CONFIG_CLEANUP``)
#    are bound by DIRECT EQUALITY to the already-computed, already-validated
#    ``status_text`` of the RESULT's own typed
#    ``runtime_teardown``/``broker_shutdown``/``cleanup`` objects -- no
#    second vocabulary is needed for them at all, because the typed object
#    IS the single source of truth and the recorded string must simply agree
#    with it. ``EVIDENCE_SAFETY`` is bound the same way, but to
#    ``evidence.retention_ready`` AND ``evidence``'s own construction origin
#    (FU2F) -- there is no typed status object for it, so
#    :data:`_EVIDENCE_ORIGIN_REFUSED`/:data:`_EVIDENCE_ORIGIN_BUILT` are what
#    take that role instead.
#    The remaining 21 COMPATIBILITY gates each get their OWN bounded set of
#    failure codes -- read directly off the source, in
#    :data:`_COMPATIBILITY_GATE_ALLOWED_FAILURE_CODE_VALUES` below -- so a
#    status text valid on one gate (e.g. ``"CLOSED"``, a broker-only text)
#    can never be accepted on another (e.g. ``h1_extension_identity``).
# 2. **Cross-field invariants**, added directly in
#    ``CategoryBControllerResult.__post_init__``: ``pi_config_created``
#    equals ``cleanup.attempted`` (both are literally the SAME
#    ``generated_config is not None`` fact, for every controller code path);
#    ``facts.pi_version_observed`` equals ``observed_pi_version is not None``
#    (both come from the SAME ``RuntimeLaunchObservation`` at the SAME call
#    site); and a terminal PASS additionally requires
#    ``pi_config_created``/``broker_created``/``runtime_session_established``
#    all ``True``, and ``runtime_teardown.state``/``broker_shutdown.state``
#    exactly ``CLOSED_BY_ORCHESTRATOR`` (never ``NOT_REQUIRED`` -- that text
#    means nothing existed, which cannot be true of a resource the result
#    itself says was created).
# 3. **Evidence binding.** When ``evidence.retention_ready``, the retained
#    body's ``candidate``/``semantic_prompts_sent``/
#    ``compatibility_gate_passed``/``compatibility_facts``/
#    ``observed_pi_version``/``gate_statuses``/the three closure status
#    strings are compared, key by key, against THIS RESULT's own
#    already-validated fields (never a caller-supplied duplicate boolean).
#    An evidence body scrub-built from any other payload -- including a
#    genuinely clean, unrelated one -- disagrees on at least one key and is
#    refused. See :func:`_require_evidence_describes_this_result`.
#
# **Stated residual, honestly, matching every other component/verdict split
# in this design:** this is a correctness/integrity control against a caller
# (including a future refactor) inside the trust boundary. It is not a
# defense against a caller willing to import
# ``CategoryBEvidence._build_from_payload`` directly and hand-craft a payload
# dict whose keys happen to match a target result's own fields -- a caller in
# that position already controls both sides of the comparison.

#: Every gate name this controller ever declares. ``_gate_status_pairs`` must
#: name EXACTLY this set, once each -- never a subset, a superset, or a
#: duplicate.
_ALL_GATE_NAMES: frozenset[str] = frozenset(gate.value for gate in CategoryBGateName)

#: The three gates whose recorded text is bound by DIRECT EQUALITY to a typed
#: closure object's own ``status_text`` -- never a separate vocabulary.
_TYPED_CLOSURE_STATUS_GATES: tuple[CategoryBGateName, ...] = (
    CategoryBGateName.RUNTIME_TEARDOWN,
    CategoryBGateName.BROKER_SHUTDOWN,
    CategoryBGateName.GENERATED_CONFIG_CLEANUP,
)

#: FU2F: ``EVIDENCE_SAFETY``'s failure code is bound below by DIRECT,
#: PER-ORIGIN EQUALITY (mirroring how the three closure gates above are bound
#: to a typed object's own ``status_text``) rather than through a shared
#: vocabulary set -- see the ``evidence._origin``-keyed block in
#: ``CategoryBControllerResult.__post_init__``.
#:
#: ``run_category_b_controller`` has THREE ``_fail(EVIDENCE_SAFETY, ...)``
#: call sites, not two: ``SAFETY_CONTEXT_UNPROVABLE`` (``safety is None``,
#: evidence always ``_refused``), ``EVIDENCE_SCRUB_REFUSED`` (a built evidence
#: body is not retention-ready), and a THIRD, defensive
#: ``_fail(EVIDENCE_SAFETY, MALFORMED_ADAPTER_RESULT)`` guarding
#: ``outcome is INFRASTRUCTURE_REFUSAL and failed_gate is None``. That third
#: call site is PROVABLY UNREACHABLE under the controller's own invariants:
#: ``EVIDENCE_SAFETY`` is unconditionally resolved to ``PASSED`` or one of the
#: other two codes on EVERY path before that guard runs (the safety/evidence
#: block above it always calls either ``_pass``-equivalent or ``_fail`` for
#: this exact gate), so ``failed_gate`` can never still be ``None`` when the
#: guard's condition is checked. ``MALFORMED_ADAPTER_RESULT`` is therefore
#: deliberately never bound to a reachable ``evidence._origin`` here: if that
#: dead defensive line ever fired due to a future regression, the resulting
#: ``CategoryBControllerResult`` construction would itself raise -- loudly,
#: immediately, at this gate -- rather than silently accepting a code the
#: source can no longer actually produce on any live path.

#: **Per-gate** allowed failure codes for every COMPATIBILITY gate (FU2B).
#: Read directly off each gate's own ``_fail(CategoryBGateName.X, ...)`` call
#: site(s) in ``run_category_b_controller`` -- never guessed, never a shared
#: pool. A gate driven through ``_invoke`` (an injected adapter call) always
#: carries ``ADAPTER_RAISED``/``MALFORMED_ADAPTER_RESULT`` in addition to its
#: own specific code(s); a gate resolved entirely by AIDO's own deterministic
#: logic (``RUN_CORRELATION``, ``BROKER_READY``, the four launch facts, both
#: handshake-identity gates, ``CONNECTION_VALUES``, ``ROUTE_CHECK``) carries
#: EXACTLY one.
_COMPATIBILITY_GATE_ALLOWED_FAILURE_CODE_VALUES: dict[str, frozenset[str]] = {
    CategoryBGateName.RUN_CORRELATION.value: frozenset(
        {CategoryBFailureCode.RUN_CORRELATION_UNAVAILABLE.value}
    ),
    CategoryBGateName.WORKSPACE_AUTHORITY.value: frozenset(
        {
            CategoryBFailureCode.WORKSPACE_AUTHORITY_UNVERIFIED.value,
            CategoryBFailureCode.ADAPTER_RAISED.value,
        }
    ),
    CategoryBGateName.ROUTE_DESCRIPTOR.value: frozenset(
        {
            CategoryBFailureCode.ROUTE_DESCRIPTOR_INVALID.value,
            CategoryBFailureCode.ADAPTER_RAISED.value,
        }
    ),
    CategoryBGateName.NON_SECRET_PREFLIGHT.value: frozenset(
        {
            CategoryBFailureCode.NON_SECRET_PREFLIGHT_GATE_FAILED.value,
            CategoryBFailureCode.ADAPTER_RAISED.value,
        }
    ),
    CategoryBGateName.CONNECTION_VALUES.value: frozenset(
        {CategoryBFailureCode.CONNECTION_VALUES_UNAVAILABLE.value}
    ),
    CategoryBGateName.SECRET_CONTEXT.value: frozenset(
        {
            CategoryBFailureCode.SECRET_CONTEXT_CONSTRUCTION_FAILED.value,
            CategoryBFailureCode.ADAPTER_RAISED.value,
        }
    ),
    CategoryBGateName.PI_CONFIG_GENERATION.value: frozenset(
        {
            CategoryBFailureCode.WORKSPACE_AUTHORITY_UNVERIFIED.value,
            CategoryBFailureCode.PI_CONFIG_GENERATION_FAILED.value,
            CategoryBFailureCode.ADAPTER_RAISED.value,
        }
    ),
    CategoryBGateName.IDENTITY_BINDING.value: frozenset(
        {
            CategoryBFailureCode.IDENTITY_BINDING_MISMATCH.value,
            CategoryBFailureCode.ADAPTER_RAISED.value,
        }
    ),
    CategoryBGateName.CHILD_ENVIRONMENT.value: frozenset(
        {
            CategoryBFailureCode.CHILD_ENVIRONMENT_BUILD_FAILED.value,
            CategoryBFailureCode.ADAPTER_RAISED.value,
        }
    ),
    CategoryBGateName.BROKER_SESSION.value: frozenset(
        {
            CategoryBFailureCode.BROKER_CREATION_FAILED.value,
            CategoryBFailureCode.BROKER_SESSION_MISMATCH.value,
            CategoryBFailureCode.MALFORMED_ADAPTER_RESULT.value,
        }
    ),
    CategoryBGateName.BROKER_READY.value: frozenset(
        {CategoryBFailureCode.BROKER_NOT_READY.value}
    ),
    CategoryBGateName.RUNTIME_LAUNCH.value: frozenset(
        {
            CategoryBFailureCode.RUNTIME_LAUNCH_REQUEST_UNCONSTRUCTIBLE.value,
            CategoryBFailureCode.RUNTIME_LAUNCH_FAILED.value,
            CategoryBFailureCode.RUNTIME_SESSION_MISMATCH.value,
            CategoryBFailureCode.ADAPTER_RAISED.value,
            CategoryBFailureCode.MALFORMED_ADAPTER_RESULT.value,
        }
    ),
    CategoryBGateName.PI_VERSION_OBSERVED.value: frozenset(
        {CategoryBFailureCode.PI_VERSION_NOT_OBSERVED.value}
    ),
    CategoryBGateName.RPC_LAUNCH_SHAPE.value: frozenset(
        {CategoryBFailureCode.RPC_LAUNCH_SHAPE_UNEXPECTED.value}
    ),
    CategoryBGateName.REQUIRED_LAUNCH_FLAGS.value: frozenset(
        {CategoryBFailureCode.REQUIRED_LAUNCH_FLAGS_REJECTED.value}
    ),
    CategoryBGateName.LF_JSONL_CORRELATION.value: frozenset(
        {CategoryBFailureCode.LF_JSONL_CORRELATION_FAILED.value}
    ),
    CategoryBGateName.GET_COMMANDS.value: frozenset(
        {
            CategoryBFailureCode.RUNTIME_SESSION_MISMATCH.value,
            CategoryBFailureCode.GET_COMMANDS_FAILED.value,
            CategoryBFailureCode.GET_COMMANDS_RESPONSE_SHAPE_NOT_UNDERSTOOD.value,
            CategoryBFailureCode.ADAPTER_RAISED.value,
            CategoryBFailureCode.MALFORMED_ADAPTER_RESULT.value,
        }
    ),
    CategoryBGateName.H1_EXTENSION_IDENTITY.value: frozenset(
        {CategoryBFailureCode.H1_EXTENSION_IDENTITY_MISMATCH.value}
    ),
    CategoryBGateName.EXTENSION_COMMAND_NAMESPACE.value: frozenset(
        {
            CategoryBFailureCode.EXTENSION_COMMAND_PROVENANCE_UNKNOWN.value,
            CategoryBFailureCode.UNEXPECTED_CLI_EXTENSION_COMMAND.value,
        }
    ),
    CategoryBGateName.GET_STATE.value: frozenset(
        {
            CategoryBFailureCode.RUNTIME_SESSION_MISMATCH.value,
            CategoryBFailureCode.GET_STATE_FAILED.value,
            CategoryBFailureCode.GET_STATE_RESPONSE_SHAPE_NOT_UNDERSTOOD.value,
            CategoryBFailureCode.ADAPTER_RAISED.value,
            CategoryBFailureCode.MALFORMED_ADAPTER_RESULT.value,
        }
    ),
    CategoryBGateName.H2_PROVIDER_MODEL_IDENTITY.value: frozenset(
        {CategoryBFailureCode.H2_PROVIDER_MODEL_IDENTITY_MISMATCH.value}
    ),
    CategoryBGateName.PROTOCOL_INTEGRITY.value: frozenset(
        {
            CategoryBFailureCode.RUNTIME_SESSION_MISMATCH.value,
            CategoryBFailureCode.PROTOCOL_VIOLATION_OBSERVED.value,
            CategoryBFailureCode.EXTENSION_ERROR_OBSERVED.value,
            CategoryBFailureCode.ADAPTER_RAISED.value,
            CategoryBFailureCode.MALFORMED_ADAPTER_RESULT.value,
        }
    ),
    CategoryBGateName.ROUTE_CHECK.value: frozenset(
        {CategoryBFailureCode.ROUTE_CHECK_FAILED.value}
    ),
}

#: Sanity: every compatibility gate has an entry, and no closure/evidence gate
#: does (those are bound structurally, not through this table). Asserted at
#: import time so the table can never silently drift from ``COMPATIBILITY_GATES``.
assert set(_COMPATIBILITY_GATE_ALLOWED_FAILURE_CODE_VALUES) == {
    gate.value for gate in COMPATIBILITY_GATES
}

#: **FU2D: the exact prerequisite for each compatibility gate being EVALUATED
#: AT ALL**, transcribed one-for-one from ``run_category_b_controller``'s own
#: `if` conditions -- never inferred from gate names or from the declaration
#: order alone.
#:
#: Each entry names the gates that must ALL read ``PASSED`` for that gate's
#: block to be entered. The relationship the validator enforces is a
#: **biconditional**, not merely an implication: every one of these blocks,
#: once entered, unconditionally records a status for its gate on every path
#: through it (verified branch-by-branch against the source), so
#: "prerequisite satisfied" and "gate reached" are the SAME fact. That is what
#: makes ``NOT_REACHED`` a checkable claim rather than a free pass.
#:
#: The source conditions this table encodes, in order:
#:
#: - ``if run_id is not None`` -- ``run_id`` is non-``None`` exactly when
#:   ``RUN_CORRELATION`` passed, so ``WORKSPACE_AUTHORITY`` keys off that gate;
#: - ``if _passed(WORKSPACE_AUTHORITY)`` / ``if _passed(ROUTE_DESCRIPTOR)``;
#: - the preflight block sets ``NON_SECRET_PREFLIGHT`` on every path, and
#:   sets ``CONNECTION_VALUES`` exactly on the two paths where
#:   ``NON_SECRET_PREFLIGHT`` passed (the ``"connection_values"``-scoped
#:   refusal, and the clean ``else``) -- hence the chain through it;
#: - ``if connection_values is not None`` / ``if secret_context is not None``
#:   / ``if generated_config is not None`` -- each of those locals is assigned
#:   only inside its own gate's success path, so each is equivalent to the
#:   PRECEDING gate having passed;
#: - ``if _passed(IDENTITY_BINDING)``, ``if launch_environment is not None``
#:   (equivalent to ``CHILD_ENVIRONMENT`` passing),
#:   ``if _passed(BROKER_SESSION)``, ``if _passed(BROKER_READY)``;
#: - ``if _passed(RUNTIME_LAUNCH)`` gates the four-launch-fact loop, which
#:   always sets ALL FOUR gates together;
#: - ``if _all_passed(<the four launch gates>)`` gates ``GET_COMMANDS``;
#: - ``H1_EXTENSION_IDENTITY`` and ``EXTENSION_COMMAND_NAMESPACE`` are both
#:   set in the ``else`` branch that also passes ``GET_COMMANDS`` -- ONE
#:   observation, two independently-failable facts;
#: - ``if _all_passed(GET_COMMANDS, H1, EXTENSION_COMMAND_NAMESPACE)`` gates
#:   ``GET_STATE``; ``H2`` is set in the ``else`` branch that passes it;
#: - ``if _all_passed(GET_STATE, H2)`` gates ``PROTOCOL_INTEGRITY``;
#: - ``if _passed(PROTOCOL_INTEGRITY)`` gates ``ROUTE_CHECK``.
#:
#: ``RUN_CORRELATION`` has an EMPTY prerequisite tuple: the controller always
#: attempts it, so it is the one gate that may never read ``NOT_REACHED``.
#:
#: The four LIFECYCLE CLOSURE gates and ``EVIDENCE_SAFETY`` are deliberately
#: absent. They are resolved on EVERY controller path regardless of where
#: compatibility stopped, so they are not "later gates" in this sense at all;
#: their coherence is proven against actual RESOURCE EXISTENCE instead (see
#: ``_require_resource_existence_coherence``).
_GATE_PREREQUISITES: dict[CategoryBGateName, tuple[CategoryBGateName, ...]] = {
    CategoryBGateName.RUN_CORRELATION: (),
    CategoryBGateName.WORKSPACE_AUTHORITY: (CategoryBGateName.RUN_CORRELATION,),
    CategoryBGateName.ROUTE_DESCRIPTOR: (CategoryBGateName.WORKSPACE_AUTHORITY,),
    CategoryBGateName.NON_SECRET_PREFLIGHT: (CategoryBGateName.ROUTE_DESCRIPTOR,),
    CategoryBGateName.CONNECTION_VALUES: (CategoryBGateName.NON_SECRET_PREFLIGHT,),
    CategoryBGateName.SECRET_CONTEXT: (CategoryBGateName.CONNECTION_VALUES,),
    CategoryBGateName.PI_CONFIG_GENERATION: (CategoryBGateName.SECRET_CONTEXT,),
    CategoryBGateName.IDENTITY_BINDING: (CategoryBGateName.PI_CONFIG_GENERATION,),
    CategoryBGateName.CHILD_ENVIRONMENT: (CategoryBGateName.IDENTITY_BINDING,),
    CategoryBGateName.BROKER_SESSION: (CategoryBGateName.CHILD_ENVIRONMENT,),
    CategoryBGateName.BROKER_READY: (CategoryBGateName.BROKER_SESSION,),
    CategoryBGateName.RUNTIME_LAUNCH: (CategoryBGateName.BROKER_READY,),
    CategoryBGateName.PI_VERSION_OBSERVED: (CategoryBGateName.RUNTIME_LAUNCH,),
    CategoryBGateName.RPC_LAUNCH_SHAPE: (CategoryBGateName.RUNTIME_LAUNCH,),
    CategoryBGateName.REQUIRED_LAUNCH_FLAGS: (CategoryBGateName.RUNTIME_LAUNCH,),
    CategoryBGateName.LF_JSONL_CORRELATION: (CategoryBGateName.RUNTIME_LAUNCH,),
    CategoryBGateName.GET_COMMANDS: (
        CategoryBGateName.PI_VERSION_OBSERVED,
        CategoryBGateName.RPC_LAUNCH_SHAPE,
        CategoryBGateName.REQUIRED_LAUNCH_FLAGS,
        CategoryBGateName.LF_JSONL_CORRELATION,
    ),
    CategoryBGateName.H1_EXTENSION_IDENTITY: (CategoryBGateName.GET_COMMANDS,),
    CategoryBGateName.EXTENSION_COMMAND_NAMESPACE: (CategoryBGateName.GET_COMMANDS,),
    CategoryBGateName.GET_STATE: (
        CategoryBGateName.GET_COMMANDS,
        CategoryBGateName.H1_EXTENSION_IDENTITY,
        CategoryBGateName.EXTENSION_COMMAND_NAMESPACE,
    ),
    CategoryBGateName.H2_PROVIDER_MODEL_IDENTITY: (CategoryBGateName.GET_STATE,),
    CategoryBGateName.PROTOCOL_INTEGRITY: (
        CategoryBGateName.GET_STATE,
        CategoryBGateName.H2_PROVIDER_MODEL_IDENTITY,
    ),
    CategoryBGateName.ROUTE_CHECK: (CategoryBGateName.PROTOCOL_INTEGRITY,),
}

#: Sanity: the table names EXACTLY the compatibility gates, once each -- never
#: a closure/evidence gate, never a missing one -- and every prerequisite it
#: names is itself a compatibility gate that comes STRICTLY EARLIER in
#: ``COMPATIBILITY_GATES``. The second half is what makes the validator a
#: single forward pass rather than a fixed-point computation, and rules out a
#: cyclic table by construction. Asserted at import time.
assert set(_GATE_PREREQUISITES) == set(COMPATIBILITY_GATES)
for _gate, _prereqs in _GATE_PREREQUISITES.items():
    for _prereq in _prereqs:
        assert COMPATIBILITY_GATES.index(_prereq) < COMPATIBILITY_GATES.index(_gate), (
            f"_GATE_PREREQUISITES[{_gate}] names a non-earlier prerequisite {_prereq}"
        )
del _gate, _prereqs, _prereq


def _require_reachable_gate_trace(status_by_gate: Mapping[str, str]) -> None:
    """FU2D: every compatibility gate is reached EXACTLY when the controller
    would have reached it.

    Walks ``COMPATIBILITY_GATES`` once, in order, and requires
    ``(status != NOT_REACHED) == (every prerequisite is PASSED)`` for each --
    a biconditional, so BOTH directions are closed:

    - a gate claiming ``PASSED``/``FAILED:...`` whose prerequisite never
      passed is refused (e.g. ``ROUTE_DESCRIPTOR`` failing while
      ``WORKSPACE_AUTHORITY`` reads ``NOT_REACHED``; ``ROUTE_CHECK`` passing
      after an early-prefix failure; a launch-fact gate reporting a verdict
      while ``RUNTIME_LAUNCH`` itself failed; ``H1``/the namespace gate
      reporting a verdict while ``GET_COMMANDS`` failed);
    - a gate claiming ``NOT_REACHED`` whose prerequisite DID pass is refused
      too (e.g. three launch-fact gates left ``NOT_REACHED`` while the fourth
      reports a verdict -- the controller's loop always sets all four
      together, so that trace never happened either).

    **This is deliberately not a generic workflow engine**, and must not grow
    into one. It is one table transcribed from one function's own ``if``
    conditions, plus one forward pass. It says nothing about WHICH status a
    reached gate holds -- the per-gate failure-code vocabulary (FU2B) and the
    first-failure attribution rule (FU2C) already own that -- only about
    whether that gate could have been evaluated at all.

    The intentional multi-fact observation groups survive untouched: the four
    launch-fact gates share one prerequisite and may independently pass or
    fail; ``H1_EXTENSION_IDENTITY`` and ``EXTENSION_COMMAND_NAMESPACE`` share
    one prerequisite and may both fail from the SAME successful
    ``get_commands`` response.
    """
    for gate in COMPATIBILITY_GATES:
        reached = status_by_gate[gate.value] != _STATUS_NOT_REACHED
        prerequisites_met = all(
            status_by_gate[prerequisite.value] == _STATUS_PASSED
            for prerequisite in _GATE_PREREQUISITES[gate]
        )
        if reached == prerequisites_met:
            continue
        if reached:
            raise ValueError(
                f"CategoryBControllerResult: gate_statuses[{gate.value!r}] is "
                f"{status_by_gate[gate.value]!r}, but this controller evaluates that "
                "gate only when "
                f"{[prerequisite.value for prerequisite in _GATE_PREREQUISITES[gate]]} "
                "all PASSED -- this is not a trace the controller could have produced"
            )
        raise ValueError(
            f"CategoryBControllerResult: gate_statuses[{gate.value!r}] is "
            f"{_STATUS_NOT_REACHED!r}, but its prerequisites "
            f"{[prerequisite.value for prerequisite in _GATE_PREREQUISITES[gate]]} "
            "all PASSED, so the controller would have evaluated it -- this is not a "
            "trace the controller could have produced"
        )


#: FU2D: the gate status(es) that mean the creation adapter returned a FULL
#: session object for each resource kind. Both are read directly off the
#: controller's own assignment sites: ``broker_session = broker_observation
#: .session`` / ``runtime_session = launch_observation.session`` are reached
#: only when the adapter returned a well-typed observation, and the branch
#: immediately below each refuses a ``None`` session with its own distinct
#: code -- so a non-``None`` session survives into EXACTLY the mismatch-refusal
#: branch or the success branch, and nowhere else.
_BROKER_SESSION_RETURNED_STATUSES: frozenset[str] = frozenset(
    {
        _STATUS_PASSED,
        f"FAILED:{CategoryBFailureCode.BROKER_SESSION_MISMATCH.value}",
    }
)
_RUNTIME_SESSION_RETURNED_STATUSES: frozenset[str] = frozenset(
    {
        _STATUS_PASSED,
        f"FAILED:{CategoryBFailureCode.RUNTIME_SESSION_MISMATCH.value}",
    }
)


def _failed(code: CategoryBFailureCode) -> str:
    return f"FAILED:{code.value}"


#: **FU2D, second adversarial review.** Binding the closure state only to
#: "was a session returned" was not tight enough: with ``BROKER_SESSION``
#: failed the runtime is never launched at all, yet a creator-retained or
#: authority-unavailable RUNTIME teardown state still constructed -- states
#: that require the launch adapter to have been CALLED. Found by an
#: exhaustive (closure state x existence boolean) sweep over three reachable
#: traces during this phase's own second review, not by the mandatory list.
#:
#: These two maps are the complete status -> reachable-closure-state
#: partitions, transcribed from the creation block and the ``_close_*``
#: function of each resource kind together:
#:
#: - ``NOT_REACHED`` / an UNCONSTRUCTIBLE request: the creation adapter was
#:   never invoked, so ``launch_attempted``/``creation_attempted`` is False
#:   and the only reachable state is ``NOT_REQUIRED``;
#: - the adapter raised or returned a malformed value: ``_invoke`` yields
#:   ``None``, so ``observation is None`` and the only reachable state is
#:   ``SHUTDOWN_AUTHORITY_UNAVAILABLE``;
#: - the adapter returned an observation carrying NO session: the
#:   creator-retained-ownership branch, whose three states
#:   ``_creator_retained_ownership_state`` selects between;
#: - a session-mismatch refusal: ``SHUTDOWN_REFUSED_FOREIGN_SESSION`` only;
#: - ``PASSED``: AIDO called its own shutdown, so ``CLOSED_BY_ORCHESTRATOR``
#:   or ``SHUTDOWN_FAILED``.
#:
#: The broker's ``BROKER_CREATION_FAILED`` is deliberately the one code
#: mapping to SEVERAL states: the controller reuses it for the
#: unconstructible-request branch, for an adapter that RAISED (``_invoke``'s
#: ``ADAPTER_RAISED`` is rewritten to it at that call site), and for a
#: returned observation with no session. It is a set, not a guess.
_RUNTIME_LAUNCH_STATUS_TO_CLOSURE_STATES: Mapping[str, frozenset[ResourceClosureState]] = (
    MappingProxyType(
        {
            _STATUS_NOT_REACHED: frozenset({ResourceClosureState.NOT_REQUIRED}),
            _failed(CategoryBFailureCode.RUNTIME_LAUNCH_REQUEST_UNCONSTRUCTIBLE): frozenset(
                {ResourceClosureState.NOT_REQUIRED}
            ),
            _failed(CategoryBFailureCode.ADAPTER_RAISED): frozenset(
                {ResourceClosureState.SHUTDOWN_AUTHORITY_UNAVAILABLE}
            ),
            _failed(CategoryBFailureCode.MALFORMED_ADAPTER_RESULT): frozenset(
                {ResourceClosureState.SHUTDOWN_AUTHORITY_UNAVAILABLE}
            ),
            # ...including NOT_REQUIRED: `_creator_retained_ownership_state`
            # returns it whenever the creator reports `resource_created=False`
            # (the launch was attempted but nothing was actually created), so
            # this is a FOUR-state set, not three. Caught immediately by the
            # real-controller-trace sweep when an earlier draft omitted it.
            _failed(CategoryBFailureCode.RUNTIME_LAUNCH_FAILED): frozenset(
                {
                    ResourceClosureState.NOT_REQUIRED,
                    ResourceClosureState.CLOSED_BY_CREATOR_VERIFIED,
                    ResourceClosureState.CLOSED_BY_CREATOR_UNVERIFIED,
                    ResourceClosureState.PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT,
                }
            ),
            _failed(CategoryBFailureCode.RUNTIME_SESSION_MISMATCH): frozenset(
                {ResourceClosureState.SHUTDOWN_REFUSED_FOREIGN_SESSION}
            ),
            _STATUS_PASSED: frozenset(
                {
                    ResourceClosureState.CLOSED_BY_ORCHESTRATOR,
                    ResourceClosureState.SHUTDOWN_FAILED,
                }
            ),
        }
    )
)

_BROKER_SESSION_STATUS_TO_CLOSURE_STATES: Mapping[str, frozenset[ResourceClosureState]] = (
    MappingProxyType(
        {
            _STATUS_NOT_REACHED: frozenset({ResourceClosureState.NOT_REQUIRED}),
            _failed(CategoryBFailureCode.BROKER_CREATION_FAILED): frozenset(
                {
                    ResourceClosureState.NOT_REQUIRED,
                    ResourceClosureState.SHUTDOWN_AUTHORITY_UNAVAILABLE,
                    ResourceClosureState.CLOSED_BY_CREATOR_VERIFIED,
                    ResourceClosureState.CLOSED_BY_CREATOR_UNVERIFIED,
                    ResourceClosureState.PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT,
                }
            ),
            _failed(CategoryBFailureCode.MALFORMED_ADAPTER_RESULT): frozenset(
                {ResourceClosureState.SHUTDOWN_AUTHORITY_UNAVAILABLE}
            ),
            _failed(CategoryBFailureCode.BROKER_SESSION_MISMATCH): frozenset(
                {ResourceClosureState.SHUTDOWN_REFUSED_FOREIGN_SESSION}
            ),
            _STATUS_PASSED: frozenset(
                {
                    ResourceClosureState.CLOSED_BY_ORCHESTRATOR,
                    ResourceClosureState.SHUTDOWN_FAILED,
                }
            ),
        }
    )
)

#: Sanity: each map's keys are EXACTLY ``NOT_REACHED``, ``PASSED``, and one
#: entry per failure code that gate's own producer can emit (the FU2B
#: per-gate vocabulary) -- so a future code added to one table without the
#: other cannot silently fall through to "no constraint". Asserted at import.
for _gate, _map, _returned in (
    (
        CategoryBGateName.RUNTIME_LAUNCH,
        _RUNTIME_LAUNCH_STATUS_TO_CLOSURE_STATES,
        _RUNTIME_SESSION_RETURNED_STATUSES,
    ),
    (
        CategoryBGateName.BROKER_SESSION,
        _BROKER_SESSION_STATUS_TO_CLOSURE_STATES,
        _BROKER_SESSION_RETURNED_STATUSES,
    ),
):
    assert set(_map) == {_STATUS_NOT_REACHED, _STATUS_PASSED} | {
        f"FAILED:{_code}"
        for _code in _COMPATIBILITY_GATE_ALLOWED_FAILURE_CODE_VALUES[_gate.value]
    }, f"{_gate.value}: status -> closure-state map disagrees with its failure-code vocabulary"
    # ...and the two INDEPENDENTLY-written tables must agree with each other:
    # a status that means a session was returned may map ONLY to
    # session-bearing closure states, and a status that means none was
    # returned ONLY to the others. This is what keeps
    # `_SESSION_BEARING_CLOSURE_STATES` (the coarse fact, read off the
    # `observation.session is None` branch point) and the per-status maps
    # (the fine fact, read off each branch individually) from drifting apart.
    for _status, _states in _map.items():
        _expected_bearing = _status in _returned
        assert all(
            (_state in _SESSION_BEARING_CLOSURE_STATES) is _expected_bearing
            for _state in _states
        ), (
            f"{_gate.value}: status {_status!r} maps to a closure state whose "
            "session-bearing-ness contradicts _SESSION_BEARING_CLOSURE_STATES"
        )
del _gate, _map, _returned, _status, _states, _expected_bearing


def _require_resource_existence_coherence(
    *,
    status_by_gate: Mapping[str, str],
    pi_config_created: bool,
    broker_created: bool,
    runtime_session_established: bool,
    runtime_teardown: "RuntimeTeardownStatus",
    broker_shutdown: "BrokerShutdownStatus",
) -> None:
    """FU2D: the three existence booleans must agree with the gate trace AND
    with the typed closure objects describing the very same resources.

    Every rule here is a biconditional transcribed from the controller's own
    terminal field expressions -- ``pi_config_created=generated_config is not
    None``, ``broker_created=broker_session is not None``,
    ``runtime_session_established=runtime_session is not None`` -- combined
    with where each of those three locals is actually assigned.

    **The distinction this deliberately PRESERVES.** "A physical partial
    resource may exist" and "a full session object crossed the boundary" are
    two different facts, and only the second is what these booleans report. A
    creator-retained partial broker (``BrokerCreationObservation`` with
    ``resource_created=True`` but ``session=None``) therefore yields
    ``broker_created=False`` -- correctly, because no ``BrokerSession`` was
    ever handed over -- while a FOREIGN full session yields
    ``broker_created=True`` even though this run refused to act on it. Neither
    is collapsed into the other.
    """
    # 1. The generated Pi config. `generated_config` is assigned only inside
    #    PI_CONFIG_GENERATION's own success path, so its existence and that
    #    gate's PASSED status are literally the same fact. Combined with the
    #    already-enforced `pi_config_created == cleanup.attempted`, this is
    #    what makes a PI_CONFIG_GENERATION PASS incompatible with a
    #    NOT_REQUIRED generated-config cleanup.
    config_gate_passed = (
        status_by_gate[CategoryBGateName.PI_CONFIG_GENERATION.value] == _STATUS_PASSED
    )
    if pi_config_created != config_gate_passed:
        raise ValueError(
            "CategoryBControllerResult: pi_config_created "
            f"({pi_config_created!r}) must equal "
            f"(gate_statuses['pi_config_generation'] == 'PASSED') "
            f"({config_gate_passed!r}) -- the controller assigns generated_config "
            "only on that gate's own success path"
        )

    for (
        label,
        established,
        gate,
        returned_statuses,
        closure_status,
        reachable_states_by_status,
    ) in (
        (
            "runtime_session_established",
            runtime_session_established,
            CategoryBGateName.RUNTIME_LAUNCH,
            _RUNTIME_SESSION_RETURNED_STATUSES,
            runtime_teardown,
            _RUNTIME_LAUNCH_STATUS_TO_CLOSURE_STATES,
        ),
        (
            "broker_created",
            broker_created,
            CategoryBGateName.BROKER_SESSION,
            _BROKER_SESSION_RETURNED_STATUSES,
            broker_shutdown,
            _BROKER_SESSION_STATUS_TO_CLOSURE_STATES,
        ),
    ):
        gate_status = status_by_gate[gate.value]
        # 2a. The existence boolean IS "the adapter returned a session":
        #     exactly the success status or that gate's own session-mismatch
        #     refusal, and no other status.
        session_returned = gate_status in returned_statuses
        if established != session_returned:
            raise ValueError(
                f"CategoryBControllerResult: {label} ({established!r}) must equal "
                f"whether the creation adapter returned a session, which "
                f"gate_statuses[{gate.value!r}] ({gate_status!r}) determines "
                f"(a session is returned exactly for {sorted(returned_statuses)}) "
                "-- note a FOREIGN session is still a returned session"
            )
        # 2b. ...and the typed closure object must be a state THAT EXACT gate
        #     status can actually produce. This is strictly stronger than
        #     "session-bearing vs not" (which it implies): it additionally
        #     rules out, for example, a creator-retained or
        #     authority-unavailable RUNTIME teardown when the launch adapter
        #     was never called at all -- the bypass this phase's own second
        #     adversarial sweep found.
        reachable_states = reachable_states_by_status[gate_status]
        if closure_status.state not in reachable_states:
            raise ValueError(
                f"CategoryBControllerResult: the typed closure state "
                f"({closure_status.state.value!r}) is not reachable when "
                f"gate_statuses[{gate.value!r}] is {gate_status!r} -- that status "
                f"can only produce {sorted(state.value for state in reachable_states)}"
            )

#: Which ``CompatibilityFacts`` field is set at the SAME call site as which
#: gate's ``_pass``/``_fail`` (FU2B, found during post-implementation
#: self-review: nothing previously bound these together at all, so a
#: hand-built REFUSAL result could claim
#: ``facts.h1_extension_identity_matched=True`` while
#: ``gate_statuses['h1_extension_identity']`` read ``FAILED:...`` -- two
#: individually-typed, individually-valid objects disagreeing about the same
#: underlying fact). Eleven of the thirteen facts map to exactly one gate
#: each; the remaining two (``no_protocol_violation_observed``/
#: ``no_extension_error_observed``) jointly gate ONE compatibility gate
#: (``PROTOCOL_INTEGRITY``) and are checked by conjunction, separately below
#: -- deliberately excluded from this table rather than force-mapped
#: one-to-one, which the source does not support.
_SINGLE_FACT_TO_GATE: dict[str, CategoryBGateName] = {
    "broker_reached_required_ready_state": CategoryBGateName.BROKER_READY,
    "pi_version_observed": CategoryBGateName.PI_VERSION_OBSERVED,
    "rpc_launch_shape_valid": CategoryBGateName.RPC_LAUNCH_SHAPE,
    "required_launch_flags_accepted": CategoryBGateName.REQUIRED_LAUNCH_FLAGS,
    "lf_jsonl_correlation_succeeded": CategoryBGateName.LF_JSONL_CORRELATION,
    "get_commands_response_shape_understood": CategoryBGateName.GET_COMMANDS,
    "h1_extension_identity_matched": CategoryBGateName.H1_EXTENSION_IDENTITY,
    "no_unexpected_extension_command_observed": CategoryBGateName.EXTENSION_COMMAND_NAMESPACE,
    "get_state_response_shape_understood": CategoryBGateName.GET_STATE,
    "h2_provider_model_identity_matched": CategoryBGateName.H2_PROVIDER_MODEL_IDENTITY,
    "exact_candidate_model_served": CategoryBGateName.ROUTE_CHECK,
}

#: Sanity: every field this table names is a real ``CompatibilityFacts``
#: field, and the two PROTOCOL_INTEGRITY facts are deliberately absent.
assert set(_SINGLE_FACT_TO_GATE) == {
    spec.name for spec in fields(CompatibilityFacts)
} - {"no_protocol_violation_observed", "no_extension_error_observed"}

#: FU2E blocker 2: the four facts genuinely recorded from a RUNTIME_LAUNCH
#: observation BEFORE the controller knows whether RUNTIME_LAUNCH itself will
#: pass -- read directly off the real controller's own RUNTIME_LAUNCH block:
#: ``fact_values["pi_version_observed"]`` etc. are assigned immediately after
#: ``_invoke(launch_runtime, ...)`` returns a non-``None`` observation,
#: strictly BEFORE the ``runtime_session is None`` / session-mismatch checks
#: that can still fail RUNTIME_LAUNCH itself. This is the ONE honest place
#: "gate reached" and "fact observed" genuinely diverge (I2A's own accepted
#: asymmetry) -- every other single-mapped fact below is set unconditionally
#: alongside its own gate's ``_pass``/``_fail``, in the SAME block, on every
#: path through it.
_LAUNCH_FACT_NAMES: frozenset[str] = frozenset(
    {
        "pi_version_observed",
        "rpc_launch_shape_valid",
        "required_launch_flags_accepted",
        "lf_jsonl_correlation_succeeded",
    }
)
assert _LAUNCH_FACT_NAMES <= set(_SINGLE_FACT_TO_GATE)

#: FU2E blocker 2: the ONLY two RUNTIME_LAUNCH statuses at which a valid
#: RuntimeLaunchObservation was genuinely consumed while the four launch
#: facts' OWN gates remain ``NOT_REACHED``. ``PASSED`` is deliberately absent
#: here: when RUNTIME_LAUNCH passes, the four launch-fact gates are
#: themselves reached (their sole prerequisite IS RUNTIME_LAUNCH, per
#: ``_GATE_PREREQUISITES`` and ``_require_reachable_gate_trace``), so they
#: fall through to the ordinary per-own-gate equality check instead of this
#: exception. Every OTHER RUNTIME_LAUNCH status --
#: ``NOT_REACHED``/``RUNTIME_LAUNCH_REQUEST_UNCONSTRUCTIBLE``/
#: ``ADAPTER_RAISED``/``MALFORMED_ADAPTER_RESULT`` -- never reaches the
#: ``fact_values[...] = launch_observation....`` assignment at all: no valid
#: observation was ever obtained, so none of the four facts can legitimately
#: be ``True``.
_RUNTIME_LAUNCH_STATUSES_WITH_VALID_OBSERVATION_BUT_OWN_GATE_UNREACHED: frozenset[str] = (
    frozenset(
        {
            f"FAILED:{CategoryBFailureCode.RUNTIME_LAUNCH_FAILED.value}",
            f"FAILED:{CategoryBFailureCode.RUNTIME_SESSION_MISMATCH.value}",
        }
    )
)


def _is_allowed_compatibility_status(gate: CategoryBGateName, status: str) -> bool:
    """Whether ``status`` is a text THIS SPECIFIC compatibility gate can emit."""
    if status in (_STATUS_NOT_REACHED, _STATUS_PASSED):
        return True
    if status.startswith("FAILED:"):
        allowed = _COMPATIBILITY_GATE_ALLOWED_FAILURE_CODE_VALUES.get(gate.value, frozenset())
        return status[len("FAILED:") :] in allowed
    return False


def _validate_gate_status_shape(pairs: Any) -> dict[str, str]:
    """Structural checks only: an exact tuple of ``(str, str)`` pairs naming
    every declared gate EXACTLY once. Returns the pairs as a plain ``dict``
    for the per-gate/typed-object checks that follow -- safe to build only
    AFTER this function has already proven no duplicate/missing name exists.
    """
    if not isinstance(pairs, tuple):
        raise ValueError("CategoryBControllerResult._gate_status_pairs must be a tuple")
    seen: set[str] = set()
    for entry in pairs:
        if (
            type(entry) is not tuple
            or len(entry) != 2
            or type(entry[0]) is not str
            or type(entry[1]) is not str
        ):
            raise ValueError(
                "CategoryBControllerResult._gate_status_pairs entries must each be "
                "an exact (str, str) tuple"
            )
        name, _status = entry
        if name not in _ALL_GATE_NAMES:
            raise ValueError(
                f"CategoryBControllerResult._gate_status_pairs: unrecognized gate "
                f"name {name!r}"
            )
        if name in seen:
            raise ValueError(
                f"CategoryBControllerResult._gate_status_pairs: duplicate gate name "
                f"{name!r}"
            )
        seen.add(name)
    if seen != _ALL_GATE_NAMES:
        raise ValueError(
            "CategoryBControllerResult._gate_status_pairs must record every "
            "declared gate exactly once"
        )
    return dict(pairs)


def _require_evidence_describes_this_result(
    *,
    evidence: "CategoryBEvidence",
    candidate: str,
    semantic_prompts_sent: int,
    compatibility_gate_passed: bool,
    facts: "CompatibilityFacts",
    observed_pi_version: str | None,
    status_by_gate: Mapping[str, str],
    runtime_teardown_status_text: str,
    broker_shutdown_status_text: str,
    cleanup_status_text: str,
) -> None:
    """Bind a RETENTION-READY evidence body to the exact result consuming it.

    FU2B. Compares the retained body, key by key, against the RESULT's own
    already-validated fields -- never a caller-supplied duplicate boolean.
    A body scrub-built from any other payload, including a genuinely clean,
    unrelated one (``{"ok": True}``), disagrees on at least one key here and
    is refused.

    Only the fields already represented as typed ``CategoryBControllerResult``
    fields are bound. The frozen route/model/provider facts
    (``model_id``/``provider_id``/``gateway_class``) and the safety-context
    needle codes are part of the canonical evidence body but are NOT typed
    fields on this result object (they live only in local variables inside
    ``run_category_b_controller``) -- an honest, stated residual, not a
    silent gap: "where available" (per this phase's own brief) currently
    means exactly this set.
    """
    if not evidence.retention_ready:
        return
    body = evidence.as_dict()
    expected_gate_statuses = {
        name: status
        for name, status in status_by_gate.items()
        if name != CategoryBGateName.EVIDENCE_SAFETY.value
    }
    expected: dict[str, Any] = {
        "candidate": candidate,
        "semantic_prompts_sent": semantic_prompts_sent,
        "compatibility_gate_passed": compatibility_gate_passed,
        "compatibility_facts": facts.as_dict(),
        "observed_pi_version": observed_pi_version,
        "gate_statuses": expected_gate_statuses,
        "orchestrator_runtime_teardown_status": runtime_teardown_status_text,
        "orchestrator_broker_shutdown_status": broker_shutdown_status_text,
        "orchestrator_generated_config_cleanup_status": cleanup_status_text,
    }
    for key, expected_value in expected.items():
        if key not in body or body[key] != expected_value:
            raise ValueError(
                "CategoryBControllerResult: retention-ready evidence does not "
                f"describe this result's own {key!r} -- an evidence body built "
                "from an unrelated payload cannot be consumed by this result"
            )


# -- the controller result -----------------------------------------------------


@dataclass(frozen=True)
class CategoryBControllerResult:
    """The controller's one, complete, truthful result for one run.

    **Immutable after construction, through every supported API.** Gate
    statuses are held as an immutable tuple of pairs; :attr:`gate_statuses`
    hands back a ``MappingProxyType`` over a throwaway dict, so neither the
    proxy nor any dict a caller obtains from it can rewrite this object.

    Valid by construction: ``semantic_prompts_sent`` is always exactly ``0``;
    a ``CATEGORY_B_GATE_PASSED`` outcome never carries a failure, and an
    ``INFRASTRUCTURE_REFUSAL`` outcome always does; and a pass requires every
    compatibility fact, every closure status, and retention-ready evidence.
    """

    candidate: str
    outcome: CategoryBOutcome
    semantic_prompts_sent: int
    failed_gate: CategoryBGateName | None
    failure_code: CategoryBFailureCode | None
    facts: CompatibilityFacts
    observed_pi_version: str | None
    pi_config_created: bool
    broker_created: bool
    runtime_session_established: bool
    runtime_teardown: RuntimeTeardownStatus
    broker_shutdown: BrokerShutdownStatus
    cleanup: CleanupStatus
    evidence: CategoryBEvidence
    _gate_status_pairs: tuple[tuple[str, str], ...] = field(default=(), repr=False)

    def __post_init__(self) -> None:
        # -- FU2A: every field is checked, EXACT type where authority is
        # -- carried, before anything derived from it is trusted. ------------
        if type(self.candidate) is not str or not self.candidate.strip():
            raise ValueError("CategoryBControllerResult.candidate must be a non-blank str")
        # `type(x) is int` deliberately excludes `bool`: `False == 0` is
        # `True` in Python, so a bare `!= SEMANTIC_PROMPTS_SENT` comparison
        # alone would silently accept `semantic_prompts_sent=False` as if it
        # were the integer 0.
        if type(self.semantic_prompts_sent) is not int:
            raise ValueError("CategoryBControllerResult.semantic_prompts_sent must be exactly an int")
        if self.semantic_prompts_sent != SEMANTIC_PROMPTS_SENT:
            raise ValueError(
                "CategoryBControllerResult: semantic_prompts_sent must be exactly 0 -- "
                "Category-B is a zero-semantic-prompt gate"
            )
        if type(self.outcome) is not CategoryBOutcome:
            raise ValueError("CategoryBControllerResult.outcome must be exactly a CategoryBOutcome")
        if self.failed_gate is not None and type(self.failed_gate) is not CategoryBGateName:
            raise ValueError(
                "CategoryBControllerResult.failed_gate must be None or exactly a "
                "CategoryBGateName"
            )
        if self.failure_code is not None and type(self.failure_code) is not CategoryBFailureCode:
            raise ValueError(
                "CategoryBControllerResult.failure_code must be None or exactly a "
                "CategoryBFailureCode"
            )
        if self.observed_pi_version is not None and type(self.observed_pi_version) is not str:
            raise ValueError(
                "CategoryBControllerResult.observed_pi_version must be None or exactly a str"
            )
        for name in ("pi_config_created", "broker_created", "runtime_session_established"):
            require_exact_bool(f"CategoryBControllerResult.{name}", getattr(self, name))
        # EXACT type, never `isinstance` -- a subclass overriding
        # `all_established`/`closure_satisfied`/`retention_ready` as a
        # computed property (rather than the dataclass field these classes
        # actually use) would satisfy `isinstance` while lying about its own
        # state, exactly the class of defect this design already closed once
        # for H1 and for the FU3C cleanup-postcondition derivation. None of
        # these five types is a contract this module is required to accept
        # polymorphically -- every one is controller-owned.
        for name, expected in (
            ("facts", CompatibilityFacts),
            ("evidence", CategoryBEvidence),
            ("runtime_teardown", RuntimeTeardownStatus),
            ("broker_shutdown", BrokerShutdownStatus),
            ("cleanup", CleanupStatus),
        ):
            value = getattr(self, name)
            if type(value) is not expected:
                raise ValueError(
                    f"CategoryBControllerResult.{name} must be exactly a "
                    f"{expected.__name__} (a subclass or unrelated object with a "
                    "matching interface is refused)"
                )

        # -- FU2B: cross-field invariants, TRUE for EVERY outcome ------------
        # ``pi_config_created`` and ``cleanup.attempted`` are, in the real
        # controller, literally the SAME `generated_config is not None` fact
        # -- `_attempt_cleanup(None)` iff no config was ever created, always
        # attempted otherwise. A hand-built result claiming one without the
        # other is refused.
        if self.pi_config_created != self.cleanup.attempted:
            raise ValueError(
                "CategoryBControllerResult: pi_config_created must equal "
                "cleanup.attempted -- both describe whether a generated config "
                "was ever created, and the controller derives them from the SAME "
                "fact"
            )
        # `facts.pi_version_observed` and `observed_pi_version is not None`
        # both come from the SAME `RuntimeLaunchObservation`, assigned at the
        # SAME call site.
        if self.facts.pi_version_observed != (self.observed_pi_version is not None):
            raise ValueError(
                "CategoryBControllerResult: facts.pi_version_observed must equal "
                "(observed_pi_version is not None) -- both are derived from the "
                "SAME launch observation"
            )

        pass_required = self.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED

        # -- gate-status structural shape, for EVERY outcome -----------------
        status_by_gate = _validate_gate_status_shape(self._gate_status_pairs)

        # -- FU2D: the gate trace must be one this controller could actually -
        # -- have walked, for EVERY outcome. Runs BEFORE the per-gate --------
        # -- vocabulary and fact-agreement checks below, because a gate that -
        # -- was never reachable makes every downstream question about its ---
        # -- status meaningless. ---------------------------------------------
        _require_reachable_gate_trace(status_by_gate)

        # -- the three typed-object-bound closure gates, for EVERY outcome --
        # DIRECT EQUALITY against the already-validated typed object's own
        # `status_text` -- no separate vocabulary, no possibility of drift
        # between the typed object and its string projection.
        for gate, typed_status in (
            (CategoryBGateName.RUNTIME_TEARDOWN, self.runtime_teardown.status_text),
            (CategoryBGateName.BROKER_SHUTDOWN, self.broker_shutdown.status_text),
            (CategoryBGateName.GENERATED_CONFIG_CLEANUP, self.cleanup.status_text),
        ):
            recorded = status_by_gate[gate.value]
            if recorded != typed_status:
                raise ValueError(
                    f"CategoryBControllerResult: gate_statuses[{gate.value!r}] "
                    f"({recorded!r}) disagrees with the typed closure object's own "
                    f"status_text ({typed_status!r})"
                )

        # -- FU2D: the three existence booleans must agree with the gate -----
        # -- trace AND with the typed closure objects for the SAME resources -
        # -- (runs after the typed-object equality binding above, so the -----
        # -- closure states it reads are already proven to match what --------
        # -- gate_statuses records for them). --------------------------------
        _require_resource_existence_coherence(
            status_by_gate=status_by_gate,
            pi_config_created=self.pi_config_created,
            broker_created=self.broker_created,
            runtime_session_established=self.runtime_session_established,
            runtime_teardown=self.runtime_teardown,
            broker_shutdown=self.broker_shutdown,
        )

        # -- FU2F: EVIDENCE_SAFETY bound to the ACTUAL evidence-construction --
        # -- path, not merely to evidence.retention_ready. Read directly off --
        # -- the real controller's own two REACHABLE `_fail(EVIDENCE_SAFETY, -
        # -- ...)` call sites: `SAFETY_CONTEXT_UNPROVABLE` is emitted ONLY ---
        # -- when `safety is None`, in which case `evidence` is ALWAYS built -
        # -- via `_refused(_SAFETY_CONTEXT_UNPROVABLE_REFUSAL)` (never -------
        # -- `_build_from_payload`); `EVIDENCE_SCRUB_REFUSED` is emitted -----
        # -- ONLY when `evidence.retention_ready` is False AFTER a real -----
        # -- `_build_from_payload` call. The two refusal origins are --------
        # -- therefore mutually exclusive and jointly exhaustive of every ---
        # -- non-retention-ready evidence body a real run can produce -- a --
        # -- hand-built result pairing the WRONG code with an origin is -----
        # -- refused, closing the reproduced counterexample
        # -- (`EVIDENCE_SCRUB_REFUSED` + `_refused(("safety_context_
        # -- unprovable",))`). `MALFORMED_ADAPTER_RESULT` is deliberately ---
        # -- unreachable here -- see the module-level note above this --
        # -- gate's now-removed shared vocabulary set for why.
        evidence_safety_status = status_by_gate[CategoryBGateName.EVIDENCE_SAFETY.value]
        if self.evidence.retention_ready:
            if evidence_safety_status != _STATUS_PASSED:
                raise ValueError(
                    "CategoryBControllerResult: evidence.retention_ready is True but "
                    f"gate_statuses['evidence_safety'] is {evidence_safety_status!r}, "
                    "not PASSED"
                )
        elif self.evidence._origin == _EVIDENCE_ORIGIN_REFUSED:
            expected = f"FAILED:{CategoryBFailureCode.SAFETY_CONTEXT_UNPROVABLE.value}"
            if (
                evidence_safety_status != expected
                or self.evidence.scrub_findings != _SAFETY_CONTEXT_UNPROVABLE_REFUSAL
            ):
                raise ValueError(
                    "CategoryBControllerResult: evidence was constructed via "
                    "CategoryBEvidence._refused (the real controller's safety-context-"
                    f"unprovable path), so gate_statuses['evidence_safety'] must be "
                    f"{expected!r} and evidence.scrub_findings must be "
                    f"{_SAFETY_CONTEXT_UNPROVABLE_REFUSAL!r}; got "
                    f"{evidence_safety_status!r} / {self.evidence.scrub_findings!r}"
                )
        elif self.evidence._origin == _EVIDENCE_ORIGIN_BUILT:
            expected = f"FAILED:{CategoryBFailureCode.EVIDENCE_SCRUB_REFUSED.value}"
            if evidence_safety_status != expected:
                raise ValueError(
                    "CategoryBControllerResult: evidence was constructed via "
                    "CategoryBEvidence._build_from_payload and is not retention-ready "
                    f"(a real scrub refusal), so gate_statuses['evidence_safety'] must "
                    f"be {expected!r}; got {evidence_safety_status!r}"
                )
        # else: self.evidence._origin == _EVIDENCE_ORIGIN_UNBUILT -- the bare,
        # never-built placeholder. Left unconstrained HERE; the terminal
        # `evidence_not_yet_built` sentinel check (FU2E, unchanged) is what
        # refuses a terminal result carrying it, regardless of what
        # gate_statuses['evidence_safety'] text accompanies it.

        # -- each CompatibilityFacts field must agree with the gate it was --
        # -- set alongside, for EVERY outcome (found in post-implementation --
        # -- self-review: nothing previously bound these together). ---------
        #
        # FU2E blocker 1: ``NOT_REACHED`` does NOT mean a fact may float
        # freely. For seven of the eleven single-mapped facts, the fact and
        # its gate's own `_pass`/`_fail` are set together, unconditionally,
        # in the SAME block on every path through it -- "gate reached",
        # "observation available" and "fact observed" are the SAME fact for
        # them, so a fact claiming `True` while its own gate never ran is
        # refused exactly like a fact disagreeing with a REACHED gate always
        # was.
        #
        # FU2E blocker 2: the four LAUNCH facts are the ONE place those three
        # notions genuinely diverge (I2A's own accepted asymmetry): they are
        # recorded from the RUNTIME_LAUNCH observation BEFORE the controller
        # knows whether RUNTIME_LAUNCH itself will pass (a session mismatch,
        # or a `session is None` result, can still fail RUNTIME_LAUNCH AFTER
        # a fact already reads `True`). So they are bound to RUNTIME_LAUNCH's
        # OWN status rather than to their individual gates:
        # ``_RUNTIME_LAUNCH_STATUSES_WITH_VALID_OBSERVATION_BUT_OWN_GATE_UNREACHED``
        # (RUNTIME_LAUNCH_FAILED / RUNTIME_SESSION_MISMATCH) is the sole
        # exception -- a valid observation was genuinely consumed, so each
        # fact may independently be True or False. Every OTHER RUNTIME_LAUNCH
        # status at which their own gate reads NOT_REACHED
        # (NOT_REACHED/RUNTIME_LAUNCH_REQUEST_UNCONSTRUCTIBLE/ADAPTER_RAISED/
        # MALFORMED_ADAPTER_RESULT) never reached that assignment at all, so
        # all four must remain False. Once RUNTIME_LAUNCH itself PASSES, the
        # four launch-fact gates are themselves reached (their sole
        # prerequisite IS RUNTIME_LAUNCH), so they fall through to the
        # ordinary per-own-gate equality check below like every other fact.
        runtime_launch_status = status_by_gate[CategoryBGateName.RUNTIME_LAUNCH.value]
        for fact_name, gate in _SINGLE_FACT_TO_GATE.items():
            gate_status = status_by_gate[gate.value]
            fact_value = getattr(self.facts, fact_name)
            if gate_status != _STATUS_NOT_REACHED:
                gate_passed = gate_status == _STATUS_PASSED
                if fact_value != gate_passed:
                    raise ValueError(
                        f"CategoryBControllerResult: facts.{fact_name} ({fact_value!r}) "
                        f"disagrees with gate_statuses[{gate.value!r}] ({gate_status!r}) "
                        "-- both are set from the SAME observation at the SAME call site"
                    )
                continue
            # gate_status == NOT_REACHED
            if fact_name in _LAUNCH_FACT_NAMES:
                if (
                    runtime_launch_status
                    in _RUNTIME_LAUNCH_STATUSES_WITH_VALID_OBSERVATION_BUT_OWN_GATE_UNREACHED
                ):
                    # the one honest exception: a valid RuntimeLaunchObservation
                    # was consumed even though this fact's own gate never ran.
                    continue
                if fact_value:
                    raise ValueError(
                        f"CategoryBControllerResult: facts.{fact_name} is True but "
                        f"gate_statuses['runtime_launch'] is {runtime_launch_status!r}, "
                        "which means no valid RuntimeLaunchObservation was ever "
                        "obtained -- this fact cannot legitimately be True"
                    )
                continue
            if fact_value:
                raise ValueError(
                    f"CategoryBControllerResult: facts.{fact_name} is True but "
                    f"gate_statuses[{gate.value!r}] is NOT_REACHED -- its producing "
                    "observation was never reached, so this fact cannot legitimately "
                    "be True"
                )

        # -- FU2E blocker 3: PROTOCOL_INTEGRITY's failure code must agree ---
        # -- with EXACTLY which multi-field interpretation of the same -----
        # -- observation it names -- not merely "the conjunction agrees with
        # -- pass/fail", which cannot tell PROTOCOL_VIOLATION_OBSERVED apart
        # -- from EXTENSION_ERROR_OBSERVED. Read directly off the real -----
        # -- controller's PROTOCOL_INTEGRITY block: both facts are set from
        # -- the raw observation booleans BEFORE the if/elif that classifies
        # -- the failure, so PROTOCOL_VIOLATION_OBSERVED (checked FIRST) ---
        # -- pins only `no_protocol_violation_observed=False` (the other ---
        # -- fact may independently be True or False -- protocol violation
        # -- has precedence when both were observed), EXTENSION_ERROR_OBSERVED
        # -- (the `elif`) pins both exactly, and every failure code reached
        # -- BEFORE a valid ProtocolObservation was ever consumed
        # -- (RUNTIME_SESSION_MISMATCH/ADAPTER_RAISED/MALFORMED_ADAPTER_RESULT)
        # -- plus NOT_REACHED pin both facts False.
        protocol_gate_status = status_by_gate[CategoryBGateName.PROTOCOL_INTEGRITY.value]
        no_protocol_violation = self.facts.no_protocol_violation_observed
        no_extension_error = self.facts.no_extension_error_observed
        if protocol_gate_status == _STATUS_PASSED:
            if not (no_protocol_violation and no_extension_error):
                raise ValueError(
                    "CategoryBControllerResult: gate_statuses['protocol_integrity'] "
                    "is PASSED, so facts.no_protocol_violation_observed AND "
                    "facts.no_extension_error_observed must both be True"
                )
        elif protocol_gate_status == _failed(CategoryBFailureCode.PROTOCOL_VIOLATION_OBSERVED):
            if no_protocol_violation:
                raise ValueError(
                    "CategoryBControllerResult: gate_statuses['protocol_integrity'] "
                    "is FAILED:PROTOCOL_VIOLATION_OBSERVED, so "
                    "facts.no_protocol_violation_observed must be False"
                )
        elif protocol_gate_status == _failed(CategoryBFailureCode.EXTENSION_ERROR_OBSERVED):
            if not no_protocol_violation or no_extension_error:
                raise ValueError(
                    "CategoryBControllerResult: gate_statuses['protocol_integrity'] "
                    "is FAILED:EXTENSION_ERROR_OBSERVED, so "
                    "facts.no_protocol_violation_observed must be True and "
                    "facts.no_extension_error_observed must be False"
                )
        else:
            # NOT_REACHED, or a failure reached BEFORE a valid
            # ProtocolObservation was ever consumed (RUNTIME_SESSION_MISMATCH/
            # ADAPTER_RAISED/MALFORMED_ADAPTER_RESULT) -- both facts are only
            # ever populated inside the `else` branch that follows a matched
            # session id, so both must remain False.
            if no_protocol_violation or no_extension_error:
                raise ValueError(
                    "CategoryBControllerResult: gate_statuses['protocol_integrity'] "
                    f"is {protocol_gate_status!r} -- no valid ProtocolObservation was "
                    "ever consumed, so facts.no_protocol_violation_observed and "
                    "facts.no_extension_error_observed must both be False"
                )

        # -- FU2E: a terminal result may never carry the SAFE INTERMEDIATE --
        # -- "not yet built" sentinel a bare `CategoryBEvidence()` produces. -
        # -- Legitimate to construct in isolation, but never a shape ---------
        # -- `run_category_b_controller` itself returns: every real path ----
        # -- calls either `_refused` or `_build_from_payload`. ---------------
        if (
            not self.evidence.retention_ready
            and self.evidence.scrub_findings == _EVIDENCE_NOT_YET_BUILT_SENTINEL
        ):
            raise ValueError(
                "CategoryBControllerResult.evidence carries the intermediate "
                "'evidence_not_yet_built' sentinel -- a terminal result must carry "
                "either retention-ready evidence or a real refusal"
            )

        # -- every COMPATIBILITY gate, checked against ITS OWN bounded ------
        # -- vocabulary -- never a text only some OTHER gate can produce. ---
        for gate in COMPATIBILITY_GATES:
            status = status_by_gate[gate.value]
            if pass_required:
                # A terminal PASS requires EXACTLY "PASSED" on every
                # compatibility gate -- never merely "a text that gate's
                # producer could have emitted", which would still accept a
                # FAILED/NOT_REACHED entry sitting alongside an otherwise
                # passing result. Found during this phase's own mandatory
                # counterexample #5 (`route_check` status `NOT_REQUIRED` --
                # and, in the regression suite, `NOT_REACHED`/`FAILED:...`
                # too) reproduced against the FIRST implementation of this
                # loop, which only checked the per-gate vocabulary and did
                # not itself distinguish PASS from REFUSAL.
                if status != _STATUS_PASSED:
                    raise ValueError(
                        f"CategoryBControllerResult: a passed run's "
                        f"gate_statuses[{gate.value!r}] must be exactly "
                        f"{_STATUS_PASSED!r}; got {status!r}"
                    )
            elif not _is_allowed_compatibility_status(gate, status):
                raise ValueError(
                    f"CategoryBControllerResult: gate_statuses[{gate.value!r}] "
                    f"({status!r}) is not a status this gate's own producer can emit"
                )

        # -- failed_gate/failure_code must agree with THAT gate's own -------
        # -- recorded entry -- never a disagreeing pair. ---------------------
        if self.failed_gate is not None:
            expected_text = f"FAILED:{self.failure_code.value}"
            recorded = status_by_gate[self.failed_gate.value]
            if recorded != expected_text:
                raise ValueError(
                    "CategoryBControllerResult: failed_gate/failure_code "
                    f"({self.failed_gate.value!r} -> {expected_text!r}) disagrees "
                    f"with gate_statuses[{self.failed_gate.value!r}] ({recorded!r})"
                )

        # -- FU2C: failed_gate must be the FIRST failed gate, in the --------
        # -- controller's OWN declared evaluation order -- never merely "a" -
        # -- failed gate that happens to agree with its own recorded text. --
        #
        # The real controller's `_fail()` sets failed_gate/failure_code ONLY
        # when failed_gate is still `None` (its own first call), and every
        # later `_fail()` call updates only THAT gate's own `gate_statuses`
        # entry. So the result semantics are: `failed_gate` = the first
        # failed gate encountered by this controller run. Without this check
        # a hand-built result could name an EARLIER genuinely-failed gate in
        # `gate_statuses` while nominating a LATER one as `failed_gate` --
        # each individually-valid check above (the per-gate vocabulary, and
        # the failed_gate/failure_code agreement just above) is silent about
        # that, because neither compares gate POSITIONS.
        #
        # `CategoryBGateName`'s own declaration order IS that evaluation
        # order: the 23 ``COMPATIBILITY_GATES``, in that exact order,
        # followed by the four ``CLOSURE_GATES``
        # (RUNTIME_TEARDOWN -> BROKER_SHUTDOWN -> GENERATED_CONFIG_CLEANUP ->
        # EVIDENCE_SAFETY), in that exact order -- both match the real
        # controller's own source sequence, not merely a claim about it.
        if pass_required:
            for gate in CategoryBGateName:
                status = status_by_gate[gate.value]
                if status.startswith("FAILED:"):
                    raise ValueError(
                        "CategoryBControllerResult: a CATEGORY_B_GATE_PASSED result "
                        f"must have no FAILED gate; gate_statuses[{gate.value!r}] is "
                        f"{status!r}"
                    )
        else:
            first_failed_gate: CategoryBGateName | None = None
            for gate in CategoryBGateName:
                if status_by_gate[gate.value].startswith("FAILED:"):
                    first_failed_gate = gate
                    break
            if first_failed_gate is None:
                raise ValueError(
                    "CategoryBControllerResult: an INFRASTRUCTURE_REFUSAL result "
                    "must have at least one FAILED gate"
                )
            if self.failed_gate is None:
                raise ValueError(
                    "CategoryBControllerResult: an INFRASTRUCTURE_REFUSAL result "
                    "must carry a failed_gate"
                )
            if self.failed_gate is not first_failed_gate:
                raise ValueError(
                    "CategoryBControllerResult: failed_gate must be the FIRST "
                    "failed gate in the controller's own evaluation order; the "
                    f"first FAILED gate is {first_failed_gate.value!r} but "
                    f"failed_gate is {self.failed_gate.value!r}"
                )

        # -- evidence binding: a retention-ready body must DESCRIBE this ----
        # -- exact result, for EVERY outcome (not merely PASS). -------------
        _require_evidence_describes_this_result(
            evidence=self.evidence,
            candidate=self.candidate,
            semantic_prompts_sent=self.semantic_prompts_sent,
            compatibility_gate_passed=pass_required,
            facts=self.facts,
            observed_pi_version=self.observed_pi_version,
            status_by_gate=status_by_gate,
            runtime_teardown_status_text=self.runtime_teardown.status_text,
            broker_shutdown_status_text=self.broker_shutdown.status_text,
            cleanup_status_text=self.cleanup.status_text,
        )

        if pass_required:
            if self.failed_gate is not None or self.failure_code is not None:
                raise ValueError(
                    "CategoryBControllerResult: a passed run must not carry a "
                    "failed_gate/failure_code"
                )
            if self.candidate not in CANDIDATE_MODEL_IDS:
                raise ValueError(
                    "CategoryBControllerResult: a passed run's candidate must be one "
                    f"of the frozen candidates {sorted(CANDIDATE_MODEL_IDS)}"
                )
            # FU2B: the actual successful Category-B SHAPE, not merely
            # "closure_satisfied". `NOT_REQUIRED` means nothing existed; it
            # cannot authorize a PASS for a result that says the resource
            # WAS created.
            if not (
                self.pi_config_created
                and self.broker_created
                and self.runtime_session_established
            ):
                raise ValueError(
                    "CategoryBControllerResult: a passed run requires "
                    "pi_config_created, broker_created and "
                    "runtime_session_established to all be True"
                )
            if self.runtime_teardown.state is not ResourceClosureState.CLOSED_BY_ORCHESTRATOR:
                raise ValueError(
                    "CategoryBControllerResult: a passed run's runtime_teardown must "
                    "be CLOSED_BY_ORCHESTRATOR -- NOT_REQUIRED means nothing existed, "
                    "which cannot be true when runtime_session_established is True"
                )
            if self.broker_shutdown.state is not ResourceClosureState.CLOSED_BY_ORCHESTRATOR:
                raise ValueError(
                    "CategoryBControllerResult: a passed run's broker_shutdown must "
                    "be CLOSED_BY_ORCHESTRATOR -- NOT_REQUIRED means nothing existed, "
                    "which cannot be true when broker_created is True"
                )
            if not (self.cleanup.attempted and self.cleanup.scrub_verified):
                raise ValueError(
                    "CategoryBControllerResult: a passed run's cleanup must be "
                    "attempted and scrub_verified -- a generated config always "
                    "exists on a genuine pass"
                )
            if self.observed_pi_version is None:
                raise ValueError(
                    "CategoryBControllerResult: a passed run requires an observed "
                    "Pi version"
                )
            if not self.facts.all_established:
                raise ValueError(
                    "CategoryBControllerResult: a passed run requires every "
                    "compatibility fact to be established"
                )
            if not (
                self.runtime_teardown.closure_satisfied
                and self.broker_shutdown.closure_satisfied
                and self.cleanup.closure_satisfied
            ):
                raise ValueError(
                    "CategoryBControllerResult: a passed run requires every required "
                    "teardown/cleanup to have closed truthfully"
                )
            if not self.evidence.retention_ready:
                raise ValueError(
                    "CategoryBControllerResult: a passed run requires retention-ready "
                    "safe evidence"
                )
        elif self.failed_gate is None or self.failure_code is None:
            raise ValueError(
                "CategoryBControllerResult: an INFRASTRUCTURE_REFUSAL run must carry "
                "both a failed_gate and a failure_code"
            )

    @property
    def compatibility_gate_passed(self) -> bool:
        """The ONE terminal claim. Never true alongside a failed teardown/cleanup."""
        return self.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED

    @property
    def gate_statuses(self) -> Mapping[str, str]:
        """A READ-ONLY view. Assigning through it raises ``TypeError``."""
        return MappingProxyType(dict(self._gate_status_pairs))


# -- internal helpers ----------------------------------------------------------


def _mint_run_correlation_id() -> str:
    """Mint this invocation's own ``run_id`` nonce.

    Factored out so its failure is BOUNDED (FU3 Sec. 10): the caller wraps
    this in one ``try`` and refuses as ``RUN_CORRELATION_UNAVAILABLE`` rather
    than letting a raw exception -- an exhausted OS entropy source being the
    realistic case -- escape a controller whose entire design is bounded
    refusal. The exception's ``str()``/``repr()`` is never read or retained.
    """
    return secrets.token_hex(16)


def _invoke(
    fn: Callable[..., Any], *args: Any, expected: type
) -> tuple[Any, CategoryBFailureCode | None]:
    """Call one injected adapter, bounding BOTH failure modes.

    Distinguishes "the adapter raised" from "the adapter returned something
    that is not the declared observation type". Neither the exception's
    ``str()``/``repr()`` nor the unexpected value is ever read or retained.

    The type check is ``type(value) is expected``, NOT ``isinstance`` -- a
    subclass could override a validated field with a property that returns a
    different value on each read, defeating both the exact-bool rule and the
    session-id comparisons. No legitimate adapter needs a subclass of these
    value objects, so the exact-type rule costs nothing and closes the
    substitution.
    """
    try:
        value = fn(*args)
    except Exception:
        return None, CategoryBFailureCode.ADAPTER_RAISED
    if type(value) is not expected:
        return None, CategoryBFailureCode.MALFORMED_ADAPTER_RESULT
    return value, None


def build_run_safety_context(
    *,
    secret_context: QualificationRouteSecretContext | None,
    broker_session: BrokerSession | None,
    run_workspace: QualificationRunWorkspace | None,
    route_descriptor: RouteDescriptor | None,
) -> ArtifactSafetyContext:
    """Build the run's FULL ``ArtifactSafetyContext`` -- no silent ``None``.

    Every field I1's :class:`~qualification.safety.ArtifactSafetyContext`
    declares is populated from the run's real value WHEN THAT VALUE EXISTS:

    ===========================  ==========================================
    ``endpoint_host``            the run's secret context
    ``api_key``                  the run's secret context
    ``bearer_token``             DERIVED -- see below
    ``broker_token``             the run's live broker session
    ``pipe_name``                the run's live broker session
    ``capability_id``            the run's live broker session
    ``workspace_absolute_path``  the run's verified synthetic EXPERIMENT ROOT
    ===========================  ==========================================

    **The workspace needle is the EXPERIMENT ROOT, deliberately.** The run
    has three absolute paths that could leak: the disposable experiment root,
    the workspace (repository) root beneath it, and the generated Pi config
    directory beside that. The latter two are both strictly BENEATH the
    experiment root, and ``ar2.record.scrub_check`` matches substrings -- so
    declaring the enclosing root refuses an artifact carrying ANY of the
    three, while declaring only the narrower workspace root would leave the
    generated-config directory undeclared. This is a strictly stronger needle
    drawn from the same one verified workspace identity, never a different
    one.

    **``bearer_token`` is DERIVED, not assumed.** I2A's frozen credential
    mechanism for this route is
    ``i2_route.CREDENTIAL_MECHANISM == "models_json_env_interpolation"``: the
    credential travels as the generated ``models.json`` env interpolation of
    the one child carrier, and NO separate bearer value is ever minted for
    it. This function refuses (:class:`CategoryBSafetyContextError`) rather
    than guessing if the run's descriptor ever reports a different mechanism
    -- so ``None`` here is a proven absence, not an omission.

    A run that failed before a secret context existed still declares whatever
    it DOES have, rather than falling back to
    ``ArtifactSafetyContext.none_declared()``, which would silently drop a
    real needle.
    """
    if (
        route_descriptor is not None
        and route_descriptor.credential_mechanism != CREDENTIAL_MECHANISM
    ):
        raise CategoryBSafetyContextError("UNEXPECTED_CREDENTIAL_MECHANISM")
    broker_token = broker_session.broker_token if broker_session is not None else None
    pipe_name = broker_session.pipe_name if broker_session is not None else None
    capability_id = broker_session.capability_id if broker_session is not None else None
    workspace_absolute_path = (
        run_workspace.experiment_root if run_workspace is not None else None
    )
    if secret_context is not None:
        return secret_context.to_safety_context(
            broker_token=broker_token,
            pipe_name=pipe_name,
            capability_id=capability_id,
            workspace_absolute_path=workspace_absolute_path,
        )
    return ArtifactSafetyContext(
        endpoint_host=None,
        api_key=None,
        bearer_token=None,
        broker_token=broker_token,
        pipe_name=pipe_name,
        capability_id=capability_id,
        workspace_absolute_path=workspace_absolute_path,
    )


def _build_evidence(
    *,
    candidate: str,
    route_descriptor: RouteDescriptor | None,
    observed_pi_version: str | None,
    facts: CompatibilityFacts,
    compatibility_gate_passed: bool,
    gate_status_pairs: tuple[tuple[str, str], ...],
    runtime_teardown: RuntimeTeardownStatus,
    broker_shutdown: BrokerShutdownStatus,
    cleanup: CleanupStatus,
    safety: ArtifactSafetyContext,
) -> CategoryBEvidence:
    """Build, scrub-check, and FREEZE the bounded Category-B evidence.

    ``compatibility_gate_passed`` is supplied by the controller only AFTER
    every compatibility fact, every teardown and the config cleanup have been
    resolved -- it is never true alongside a failed closure. Nothing is
    written to disk here.

    The ``evidence_safety`` gate is deliberately OMITTED from the recorded
    ``gate_statuses``: an evidence body cannot truthfully record the outcome
    of the gate that is about to judge it, and recording it as
    ``NOT_REACHED`` would be a false statement about a gate that always runs.
    Its outcome lives on the controller result instead.
    """
    payload: dict[str, Any] = {
        "candidate": candidate,
        "model_id": route_descriptor.model_id if route_descriptor is not None else None,
        "provider_id": route_descriptor.provider_id if route_descriptor is not None else None,
        "gateway_class": (
            route_descriptor.backend_gateway_class if route_descriptor is not None else None
        ),
        "observed_pi_version": observed_pi_version,
        "pi_version_is_provenance_only": True,
        "compatibility_facts": facts.as_dict(),
        "compatibility_gate_passed": compatibility_gate_passed,
        "gate_statuses": {
            name: status
            for name, status in gate_status_pairs
            if name != CategoryBGateName.EVIDENCE_SAFETY.value
        },
        "semantic_prompts_sent": SEMANTIC_PROMPTS_SENT,
        "aido_requested_max_output_tokens": None,
        "models_json_omits_max_tokens": True,
        "provider_request_count_observation_available": False,
        "wire_level_max_tokens_observation_available": False,
        "active_tool_registry_observation_available": False,
        "tool_registry_claim_scope": list(TOOL_REGISTRY_CLAIM_SCOPE),
        "orchestrator_runtime_teardown_status": runtime_teardown.status_text,
        "orchestrator_broker_shutdown_status": broker_shutdown.status_text,
        "orchestrator_generated_config_cleanup_status": cleanup.status_text,
        "safety_context_declared_needle_codes": sorted(
            code for code, _ in safety.forbidden_needles()
        ),
        "backend_inference_lifetime_after_teardown": "not observed",
        "descendant_process_lifetime_after_teardown": "not observed",
        "claim_scope": (
            "AIDO attempted a bounded shutdown of the runtime and broker resources "
            "it created for this run, and reports only what its own calls returned. "
            "This is NOT a claim that a descendant process was terminated, that "
            "Pi/provider inference stopped, or that GPU work stopped. get_commands "
            "enumerates SLASH COMMANDS and proves extension identity and command "
            "provenance; it is NOT an observation of the active tool registry, and "
            "Pi exposes no RPC command that enumerates one. No semantic prompt was "
            "sent, and no candidate model was scored."
        ),
    }
    # FU2A: the scrub check itself now runs INSIDE CategoryBEvidence's own
    # construction path, not here -- this function no longer computes
    # retention_ready/scrub_clean/the serialized body and hand them to the
    # constructor as trusted booleans.
    return CategoryBEvidence._build_from_payload(payload, safety)


def _attempt_cleanup(generated_config: GeneratedQualificationConfig | None) -> CleanupStatus:
    """Attempt generated-config cleanup iff a config was ever created.

    Reuses ``i2_cleanup.scrub_generated_qualification_config`` and, on any
    failure or unverified result, ``i2_cleanup.classify_cleanup_failure`` with
    ``semantic_prompts_sent=0`` unconditionally -- Category-B structurally
    cannot supply any other value.
    """
    if generated_config is None:
        return CleanupStatus(attempted=False, scrub_verified=None, classification=None)
    try:
        result = scrub_generated_qualification_config(generated_config)
        raw_verified = result.scrub_verified
    except Exception:  # noqa: BLE001 - bounded below; the text is never read
        raw_verified = False
    # FU2A: the frozen i2_cleanup result is CONSUMED fail-closed, never
    # coerced. `bool(...)` on a non-bool ``scrub_verified`` would silently
    # accept a truthy stand-in as verified; instead, anything that is not
    # exactly ``True`` -- including a value that is not exactly a ``bool`` at
    # all -- is treated as unverified, and CleanupStatus's own exact-bool
    # requirement below is what actually enforces the type.
    verified = raw_verified is True
    if verified:
        return CleanupStatus(attempted=True, scrub_verified=True, classification=None)
    return CleanupStatus(
        attempted=True,
        scrub_verified=False,
        classification=classify_cleanup_failure(semantic_prompts_sent=SEMANTIC_PROMPTS_SENT),
    )


# -- the controller ------------------------------------------------------------


def run_category_b_controller(
    *,
    candidate: str,
    run_workspace: QualificationRunWorkspace,
    ambient_environ: Mapping[str, str],
    node_executable: str,
    non_secret_gates: Sequence[Callable[[], PreflightGateResult]],
    read_connection: Callable[[], ConnectionValues],
    create_broker: Callable[[BrokerCreationRequest], BrokerCreationObservation],
    launch_runtime: Callable[[RuntimeLaunchRequest], RuntimeLaunchObservation],
    get_commands: Callable[[RuntimeSession], GetCommandsObservation],
    get_state: Callable[[RuntimeSession], GetStateObservation],
    observe_protocol: Callable[[RuntimeSession], ProtocolObservation],
    route_checker: Callable[..., Any],
    shutdown_runtime: Callable[[RuntimeSession], RuntimeShutdownObservation],
    shutdown_broker: Callable[[BrokerSession], BrokerShutdownObservation],
    git_executable: str | None = None,
) -> CategoryBControllerResult:
    """Drive one candidate's Category-B compatibility gate sequence, OFFLINE.

    Every live dependency is REQUIRED and INJECTED -- there is no default
    anywhere that reaches a real process, socket, or model, and no adapter
    receives a raw credential, base URL, config path or argv.

    **There is no ``workspace_root``/``experiment_root`` parameter.** The one
    ``run_workspace`` argument can only be obtained from
    :func:`~qualification.i2b_workspace.mint_qualification_run_workspace`,
    which CREATES a fresh disposable root; no function anywhere converts an
    existing path into one. A real workspace or a sibling project is
    therefore not "denied" here -- it is structurally unnameable.

    Resource authority is bound MECHANICALLY, not by convention:

    - the controller mints one per-run ``run_id`` nonce, refuses a broker
      session that does not carry it, and claims the run workspace for that
      exact ``run_id`` (single use, so cross-run reuse fails closed);
    - the runtime launch request is CONSTRUCTED by the controller from that
      broker session, and is unconstructible unless the broker already
      reached ``READY`` (frozen O1's observed ordering) and the workspace
      re-verifies against the filesystem for this run;
    - every post-launch observation must carry the ``runtime_session_id`` the
      launch actually returned;
    - teardown targets that exact runtime session and that exact broker
      session, and is NEVER attempted for a session this run cannot prove is
      its own.

    A failing compatibility gate halts the sequence before ANY further LIVE
    operation, and every gate that would have needed one is left
    ``"NOT_REACHED"``. Facts still derivable from an observation ALREADY IN
    HAND are recorded anyway -- H1 and the extension command namespace both
    come from one ``get_commands`` response, so a failed H1 does not erase
    what that same response proved about the namespace, and neither costs an
    extra live call. Runtime teardown, broker shutdown and generated-config
    cleanup are always resolved for whatever resources may exist -- on the
    failure path and on the fully-passed path alike, in frozen O1's order.

    A terminal ``CATEGORY_B_GATE_PASSED`` requires ALL of: every
    compatibility fact established, ``semantic_prompts_sent == 0``, every
    required teardown closed truthfully, verified generated-config cleanup,
    and retention-ready safe evidence. No teardown or cleanup fact is ever
    computed after that decision -- all of them are inputs to it. Anything
    else is ``INFRASTRUCTURE_REFUSAL`` with ``semantic_prompts_sent = 0``.
    """
    # AIDO's OWN arguments are checked FIRST -- before the run correlation id
    # is minted, and therefore long before any connection value is read.
    for _name, _value in (("candidate", candidate), ("node_executable", node_executable)):
        if not isinstance(_value, str) or not _value.strip():
            raise CategoryBControllerInputError(
                f"category-B controller refused: {_name} must be a non-blank str"
            )
    if type(run_workspace) is not QualificationRunWorkspace:
        raise CategoryBControllerInputError(
            "category-B controller refused: run_workspace must be a "
            "QualificationRunWorkspace minted by "
            "qualification.i2b_workspace.mint_qualification_run_workspace; there is "
            "no path parameter, and no supported conversion from a path"
        )

    gate_statuses: dict[str, str] = {
        gate.value: _STATUS_NOT_REACHED for gate in CategoryBGateName
    }
    failed_gate: CategoryBGateName | None = None
    failure_code: CategoryBFailureCode | None = None

    def _pass(gate: CategoryBGateName) -> None:
        gate_statuses[gate.value] = _STATUS_PASSED

    def _fail(gate: CategoryBGateName, code: CategoryBFailureCode) -> None:
        nonlocal failed_gate, failure_code
        gate_statuses[gate.value] = f"FAILED:{code.value}"
        if failed_gate is None:
            failed_gate = gate
            failure_code = code

    def _passed(gate: CategoryBGateName) -> bool:
        return gate_statuses[gate.value] == _STATUS_PASSED

    def _all_passed(*gates: CategoryBGateName) -> bool:
        """Whether EVERY named gate passed.

        Stage gating uses this rather than "the last gate passed": several
        facts are derived from ONE observation, so a later fact from that same
        observation can pass while an earlier one from it failed. No further
        LIVE operation may be issued unless every fact established so far
        actually passed.
        """
        return all(_passed(gate) for gate in gates)

    run_id: str | None = None
    connection_values: ConnectionValues | None = None
    route_descriptor: RouteDescriptor | None = None
    secret_context: QualificationRouteSecretContext | None = None
    generated_config: GeneratedQualificationConfig | None = None
    launch_environment: LaunchEnvironment | None = None
    broker_observation: BrokerCreationObservation | None = None
    broker_session: BrokerSession | None = None
    broker_session_trusted = False
    broker_creation_attempted = False
    launch_observation: RuntimeLaunchObservation | None = None
    runtime_session: RuntimeSession | None = None
    runtime_session_trusted = False
    launch_attempted = False
    observed_pi_version: str | None = None
    fact_values: dict[str, bool] = {}

    # -- RUN_CORRELATION (FU3 Sec. 10) -- bounded, before anything else ------
    try:
        run_id = _mint_run_correlation_id()
    except Exception:  # noqa: BLE001 - bounded; the text is never read
        run_id = None
        _fail(
            CategoryBGateName.RUN_CORRELATION,
            CategoryBFailureCode.RUN_CORRELATION_UNAVAILABLE,
        )
    else:
        _pass(CategoryBGateName.RUN_CORRELATION)

    if run_id is not None:
        # -- WORKSPACE_AUTHORITY (FU3 Sec. 8) -- verify, then CLAIM once ------
        try:
            claim_run_workspace(run_workspace, run_id=run_id)
            _pass(CategoryBGateName.WORKSPACE_AUTHORITY)
        except WorkspaceAuthorityError:
            _fail(
                CategoryBGateName.WORKSPACE_AUTHORITY,
                CategoryBFailureCode.WORKSPACE_AUTHORITY_UNVERIFIED,
            )
        except Exception:  # noqa: BLE001
            _fail(CategoryBGateName.WORKSPACE_AUTHORITY, CategoryBFailureCode.ADAPTER_RAISED)

    if _passed(CategoryBGateName.WORKSPACE_AUTHORITY):
        # -- ROUTE_DESCRIPTOR -- deterministic, non-secret, PRE-CREDENTIAL ----
        # Moved ahead of the credential boundary (FU3 Sec. 7): this is a
        # membership test against the frozen candidate mapping plus
        # fixed-constant equality. It consumes nothing from the connection,
        # so an unknown candidate must never cause a credential read.
        try:
            route_descriptor = route_descriptor_for_candidate(candidate)
            _pass(CategoryBGateName.ROUTE_DESCRIPTOR)
        except RouteDescriptorError:
            _fail(CategoryBGateName.ROUTE_DESCRIPTOR, CategoryBFailureCode.ROUTE_DESCRIPTOR_INVALID)
        except Exception:  # noqa: BLE001
            _fail(CategoryBGateName.ROUTE_DESCRIPTOR, CategoryBFailureCode.ADAPTER_RAISED)

    if _passed(CategoryBGateName.ROUTE_DESCRIPTOR):
        # -- NON_SECRET_PREFLIGHT + CONNECTION_VALUES (credential boundary) --
        # The frozen I2 helper is reused UNMODIFIED: it evaluates every
        # non-secret gate in order and calls read_connection exactly once,
        # only if all of them passed.
        try:
            connection_values = resolve_connection_after_preflight(
                non_secret_gates=non_secret_gates, read_connection=read_connection
            )
        except InfrastructureRefusal as exc:
            if exc.gate_name == "connection_values":
                _pass(CategoryBGateName.NON_SECRET_PREFLIGHT)
                _fail(
                    CategoryBGateName.CONNECTION_VALUES,
                    CategoryBFailureCode.CONNECTION_VALUES_UNAVAILABLE,
                )
            else:
                _fail(
                    CategoryBGateName.NON_SECRET_PREFLIGHT,
                    CategoryBFailureCode.NON_SECRET_PREFLIGHT_GATE_FAILED,
                )
        except Exception:  # noqa: BLE001 - bounded; the text is never read
            _fail(CategoryBGateName.NON_SECRET_PREFLIGHT, CategoryBFailureCode.ADAPTER_RAISED)
        else:
            _pass(CategoryBGateName.NON_SECRET_PREFLIGHT)
            _pass(CategoryBGateName.CONNECTION_VALUES)

    if connection_values is not None:
        # -- SECRET_CONTEXT --
        assert route_descriptor is not None
        try:
            secret_context = build_secret_context(
                base_url=connection_values.base_url,
                api_key=connection_values.api_key,
                model_id=route_descriptor.model_id,
            )
            _pass(CategoryBGateName.SECRET_CONTEXT)
        except (SecretContextError, InvalidBaseUrlError):
            _fail(
                CategoryBGateName.SECRET_CONTEXT,
                CategoryBFailureCode.SECRET_CONTEXT_CONSTRUCTION_FAILED,
            )
        except Exception:  # noqa: BLE001
            _fail(CategoryBGateName.SECRET_CONTEXT, CategoryBFailureCode.ADAPTER_RAISED)

    if secret_context is not None:
        # -- PI_CONFIG_GENERATION [DISPOSABLE RESOURCE CREATION POINT] --------
        # A CONSUMPTION BOUNDARY for the run workspace: its authority is
        # re-proved against the filesystem here rather than inherited from
        # the WORKSPACE_AUTHORITY gate, because this stage creates a
        # directory beneath the verified experiment root.
        assert route_descriptor is not None
        try:
            verify_run_workspace(run_workspace)
            generated_config = write_qualification_pi_config(
                run_workspace.experiment_root,
                model_id=route_descriptor.model_id,
                base_url=secret_context.base_url,
            )
            _pass(CategoryBGateName.PI_CONFIG_GENERATION)
        except WorkspaceAuthorityError:
            _fail(
                CategoryBGateName.PI_CONFIG_GENERATION,
                CategoryBFailureCode.WORKSPACE_AUTHORITY_UNVERIFIED,
            )
        except (
            QualificationPiConfigError,
            QualificationPiConfigCleanupError,
            CleanupAuthorityError,
        ):
            _fail(
                CategoryBGateName.PI_CONFIG_GENERATION,
                CategoryBFailureCode.PI_CONFIG_GENERATION_FAILED,
            )
        except Exception:  # noqa: BLE001
            _fail(CategoryBGateName.PI_CONFIG_GENERATION, CategoryBFailureCode.ADAPTER_RAISED)

    if generated_config is not None:
        # -- IDENTITY_BINDING (config/secret/route cross-object agreement) ----
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
        except Exception:  # noqa: BLE001
            _fail(CategoryBGateName.IDENTITY_BINDING, CategoryBFailureCode.ADAPTER_RAISED)

    if _passed(CategoryBGateName.IDENTITY_BINDING):
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
                CategoryBGateName.CHILD_ENVIRONMENT,
                CategoryBFailureCode.CHILD_ENVIRONMENT_BUILD_FAILED,
            )
        except Exception:  # noqa: BLE001
            _fail(CategoryBGateName.CHILD_ENVIRONMENT, CategoryBFailureCode.ADAPTER_RAISED)

    if launch_environment is not None:
        # -- BROKER_SESSION [LIVE RESOURCE CREATION POINT, FROZEN O1 ORDER] ---
        # Frozen O1 mints the broker binding and reaches READY BEFORE Pi is
        # launched, because the launch writes that binding into the disposable
        # extension. The broker is therefore created here, not confirmed at
        # the end of the sequence. Constructing the request re-verifies the
        # run workspace at this consumption boundary.
        assert run_id is not None
        creation_request: BrokerCreationRequest | None
        try:
            creation_request = BrokerCreationRequest(run_id=run_id, workspace=run_workspace)
        except ObservationError:
            creation_request = None
            _fail(CategoryBGateName.BROKER_SESSION, CategoryBFailureCode.BROKER_CREATION_FAILED)
        if creation_request is not None:
            # Recorded only once the CREATION ADAPTER is actually invoked: an
            # unconstructible request never reached the adapter, so nothing
            # was created and nothing is owed.
            broker_creation_attempted = True
            broker_observation, adapter_code = _invoke(
                create_broker, creation_request, expected=BrokerCreationObservation
            )
            if adapter_code is not None:
                _fail(
                    CategoryBGateName.BROKER_SESSION,
                    CategoryBFailureCode.BROKER_CREATION_FAILED
                    if adapter_code is CategoryBFailureCode.ADAPTER_RAISED
                    else adapter_code,
                )
            else:
                broker_session = broker_observation.session
                if broker_session is None:
                    _fail(
                        CategoryBGateName.BROKER_SESSION,
                        CategoryBFailureCode.BROKER_CREATION_FAILED,
                    )
                elif broker_session.run_id != run_id:
                    # FU3 Sec. 9.4: possession is not authority. The session
                    # object is retained ONLY so the result can report the
                    # refusal truthfully; shutdown_broker is never called.
                    _fail(
                        CategoryBGateName.BROKER_SESSION,
                        CategoryBFailureCode.BROKER_SESSION_MISMATCH,
                    )
                else:
                    broker_session_trusted = True
                    _pass(CategoryBGateName.BROKER_SESSION)

    if _passed(CategoryBGateName.BROKER_SESSION):
        # -- BROKER_READY (from that exact session, before any launch) --------
        assert broker_session is not None
        fact_values["broker_reached_required_ready_state"] = broker_session.reached_ready
        if broker_session.reached_ready:
            _pass(CategoryBGateName.BROKER_READY)
        else:
            _fail(CategoryBGateName.BROKER_READY, CategoryBFailureCode.BROKER_NOT_READY)

    if _passed(CategoryBGateName.BROKER_READY):
        # -- RUNTIME_LAUNCH [LIVE RESOURCE CREATION POINT] --------------------
        assert broker_session is not None and launch_environment is not None
        assert route_descriptor is not None and run_id is not None
        launch_request: RuntimeLaunchRequest | None
        try:
            launch_request = RuntimeLaunchRequest(
                run_id=run_id,
                broker_session=broker_session,
                launch_environment=launch_environment,
                workspace=run_workspace,
                provider_id=route_descriptor.provider_id,
                model_id=route_descriptor.model_id,
            )
        except ObservationError:
            launch_request = None
            _fail(
                CategoryBGateName.RUNTIME_LAUNCH,
                CategoryBFailureCode.RUNTIME_LAUNCH_REQUEST_UNCONSTRUCTIBLE,
            )
        if launch_request is not None:
            # Recorded as soon as the launch is ATTEMPTED, never only on a
            # confirmed success: an attempt that reports failure may still
            # have started a process, so closure must not be skipped.
            launch_attempted = True
            launch_observation, adapter_code = _invoke(
                launch_runtime, launch_request, expected=RuntimeLaunchObservation
            )
            if adapter_code is not None:
                _fail(CategoryBGateName.RUNTIME_LAUNCH, adapter_code)
            else:
                observed_pi_version = launch_observation.observed_pi_version
                runtime_session = launch_observation.session
                fact_values["pi_version_observed"] = launch_observation.pi_version_observed
                fact_values["rpc_launch_shape_valid"] = launch_observation.launch_shape_valid
                fact_values["required_launch_flags_accepted"] = (
                    launch_observation.required_flags_accepted
                )
                fact_values["lf_jsonl_correlation_succeeded"] = (
                    launch_observation.lf_jsonl_correlation_succeeded
                )
                if runtime_session is None:
                    _fail(
                        CategoryBGateName.RUNTIME_LAUNCH,
                        CategoryBFailureCode.RUNTIME_LAUNCH_FAILED,
                    )
                elif (
                    runtime_session.run_id != run_id
                    or runtime_session.broker_session_id != broker_session.session_id
                ):
                    # FU3 Sec. 9.4 again: a foreign run_id OR a same-run,
                    # wrong-broker substitution. shutdown_runtime is never
                    # called for either.
                    _fail(
                        CategoryBGateName.RUNTIME_LAUNCH,
                        CategoryBFailureCode.RUNTIME_SESSION_MISMATCH,
                    )
                else:
                    runtime_session_trusted = True
                    _pass(CategoryBGateName.RUNTIME_LAUNCH)

    if _passed(CategoryBGateName.RUNTIME_LAUNCH):
        # -- the four INDEPENDENT launch facts (I2A Sec. 15 items 1-4) --------
        for gate, key, code in (
            (
                CategoryBGateName.PI_VERSION_OBSERVED,
                "pi_version_observed",
                CategoryBFailureCode.PI_VERSION_NOT_OBSERVED,
            ),
            (
                CategoryBGateName.RPC_LAUNCH_SHAPE,
                "rpc_launch_shape_valid",
                CategoryBFailureCode.RPC_LAUNCH_SHAPE_UNEXPECTED,
            ),
            (
                CategoryBGateName.REQUIRED_LAUNCH_FLAGS,
                "required_launch_flags_accepted",
                CategoryBFailureCode.REQUIRED_LAUNCH_FLAGS_REJECTED,
            ),
            (
                CategoryBGateName.LF_JSONL_CORRELATION,
                "lf_jsonl_correlation_succeeded",
                CategoryBFailureCode.LF_JSONL_CORRELATION_FAILED,
            ),
        ):
            if fact_values.get(key):
                _pass(gate)
            else:
                _fail(gate, code)

    if _all_passed(
        CategoryBGateName.PI_VERSION_OBSERVED,
        CategoryBGateName.RPC_LAUNCH_SHAPE,
        CategoryBGateName.REQUIRED_LAUNCH_FLAGS,
        CategoryBGateName.LF_JSONL_CORRELATION,
    ):
        # -- ONE get_commands observation -> GET_COMMANDS + H1 + NAMESPACE ----
        assert runtime_session is not None
        commands_observation, adapter_code = _invoke(
            get_commands, runtime_session, expected=GetCommandsObservation
        )
        if adapter_code is not None:
            _fail(CategoryBGateName.GET_COMMANDS, adapter_code)
        elif commands_observation.runtime_session_id != runtime_session.runtime_session_id:
            _fail(CategoryBGateName.GET_COMMANDS, CategoryBFailureCode.RUNTIME_SESSION_MISMATCH)
        elif not commands_observation.call_succeeded:
            _fail(CategoryBGateName.GET_COMMANDS, CategoryBFailureCode.GET_COMMANDS_FAILED)
        elif not commands_observation.response_shape_understood:
            _fail(
                CategoryBGateName.GET_COMMANDS,
                CategoryBFailureCode.GET_COMMANDS_RESPONSE_SHAPE_NOT_UNDERSTOOD,
            )
        else:
            fact_values["get_commands_response_shape_understood"] = True
            _pass(CategoryBGateName.GET_COMMANDS)

            # H1 -- RECOMPUTED BY AIDO from the frozen rule's own five
            # components, derived from THIS response, never a second snapshot
            # and never a single adapter-supplied verdict.
            h1_matched = commands_observation.h1_identity_established
            fact_values["h1_extension_identity_matched"] = h1_matched
            if h1_matched:
                _pass(CategoryBGateName.H1_EXTENSION_IDENTITY)
            else:
                _fail(
                    CategoryBGateName.H1_EXTENSION_IDENTITY,
                    CategoryBFailureCode.H1_EXTENSION_IDENTITY_MISMATCH,
                )

            # The corrected Category-B observability contract, derived from
            # THE SAME response. Sorted SEQUENCES throughout, never sets: a
            # duplicated CLI entry must not collapse into one.
            partition = commands_observation.extension_command_partition()
            namespace_code: CategoryBFailureCode | None = None
            if partition.unrecognized_entry_count:
                namespace_code = CategoryBFailureCode.EXTENSION_COMMAND_PROVENANCE_UNKNOWN
            elif partition.cli_command_names != (commands_observation.sentinel_command_name,):
                # Exactly ONE cli-sourced entry, and it must be the sentinel.
                namespace_code = CategoryBFailureCode.UNEXPECTED_CLI_EXTENSION_COMMAND
            elif not h1_matched:
                # ...and that one entry must be the H1-VALIDATED sentinel.
                namespace_code = CategoryBFailureCode.UNEXPECTED_CLI_EXTENSION_COMMAND
            fact_values["no_unexpected_extension_command_observed"] = namespace_code is None
            if namespace_code is None:
                _pass(CategoryBGateName.EXTENSION_COMMAND_NAMESPACE)
            else:
                _fail(CategoryBGateName.EXTENSION_COMMAND_NAMESPACE, namespace_code)

    if _all_passed(
        CategoryBGateName.GET_COMMANDS,
        CategoryBGateName.H1_EXTENSION_IDENTITY,
        CategoryBGateName.EXTENSION_COMMAND_NAMESPACE,
    ):
        # -- ONE get_state observation -> GET_STATE + H2 ----------------------
        assert runtime_session is not None and route_descriptor is not None
        state_observation, adapter_code = _invoke(
            get_state, runtime_session, expected=GetStateObservation
        )
        if adapter_code is not None:
            _fail(CategoryBGateName.GET_STATE, adapter_code)
        elif state_observation.runtime_session_id != runtime_session.runtime_session_id:
            _fail(CategoryBGateName.GET_STATE, CategoryBFailureCode.RUNTIME_SESSION_MISMATCH)
        elif not state_observation.call_succeeded:
            _fail(CategoryBGateName.GET_STATE, CategoryBFailureCode.GET_STATE_FAILED)
        elif not state_observation.response_shape_understood:
            _fail(
                CategoryBGateName.GET_STATE,
                CategoryBFailureCode.GET_STATE_RESPONSE_SHAPE_NOT_UNDERSTOOD,
            )
        else:
            fact_values["get_state_response_shape_understood"] = True
            _pass(CategoryBGateName.GET_STATE)

            h2 = (
                state_observation.reported_provider == route_descriptor.provider_id
                and state_observation.reported_model == route_descriptor.model_id
            )
            fact_values["h2_provider_model_identity_matched"] = h2
            if h2:
                _pass(CategoryBGateName.H2_PROVIDER_MODEL_IDENTITY)
            else:
                _fail(
                    CategoryBGateName.H2_PROVIDER_MODEL_IDENTITY,
                    CategoryBFailureCode.H2_PROVIDER_MODEL_IDENTITY_MISMATCH,
                )

    if _all_passed(CategoryBGateName.GET_STATE, CategoryBGateName.H2_PROVIDER_MODEL_IDENTITY):
        # -- PROTOCOL_INTEGRITY (I2A Sec. 15 item 8), session-bound -----------
        assert runtime_session is not None
        protocol_observation, adapter_code = _invoke(
            observe_protocol, runtime_session, expected=ProtocolObservation
        )
        if adapter_code is not None:
            _fail(CategoryBGateName.PROTOCOL_INTEGRITY, adapter_code)
        elif protocol_observation.runtime_session_id != runtime_session.runtime_session_id:
            _fail(
                CategoryBGateName.PROTOCOL_INTEGRITY, CategoryBFailureCode.RUNTIME_SESSION_MISMATCH
            )
        else:
            fact_values["no_protocol_violation_observed"] = (
                not protocol_observation.protocol_violation_observed
            )
            fact_values["no_extension_error_observed"] = (
                not protocol_observation.extension_error_observed
            )
            if protocol_observation.protocol_violation_observed:
                _fail(
                    CategoryBGateName.PROTOCOL_INTEGRITY,
                    CategoryBFailureCode.PROTOCOL_VIOLATION_OBSERVED,
                )
            elif protocol_observation.extension_error_observed:
                _fail(
                    CategoryBGateName.PROTOCOL_INTEGRITY,
                    CategoryBFailureCode.EXTENSION_ERROR_OBSERVED,
                )
            else:
                _pass(CategoryBGateName.PROTOCOL_INTEGRITY)

    if _passed(CategoryBGateName.PROTOCOL_INTEGRITY):
        # -- ROUTE_CHECK (reused i2_route wiring, unmodified) -----------------
        assert route_descriptor is not None and secret_context is not None
        try:
            route_outcome: RouteCheckOutcome = run_offline_route_check(
                descriptor=route_descriptor, secret_context=secret_context, checker=route_checker
            )
        except Exception:  # noqa: BLE001
            _fail(CategoryBGateName.ROUTE_CHECK, CategoryBFailureCode.ROUTE_CHECK_FAILED)
        else:
            fact_values["exact_candidate_model_served"] = route_outcome.passed
            if route_outcome.passed:
                _pass(CategoryBGateName.ROUTE_CHECK)
            else:
                _fail(CategoryBGateName.ROUTE_CHECK, CategoryBFailureCode.ROUTE_CHECK_FAILED)

    facts = CompatibilityFacts(**fact_values)

    # -- LIFECYCLE CLOSURE, in frozen O1's order: runtime, then broker, ------
    # -- then the generated config. Resolved on EVERY path, and always -------
    # -- BEFORE the terminal decision, never after it. -----------------------
    runtime_teardown = _close_runtime(
        launch_attempted=launch_attempted,
        observation=launch_observation,
        session_trusted=runtime_session_trusted,
        shutdown_runtime=shutdown_runtime,
    )
    broker_status = _close_broker(
        creation_attempted=broker_creation_attempted,
        observation=broker_observation,
        session_trusted=broker_session_trusted,
        shutdown_broker=shutdown_broker,
    )
    cleanup_status = _attempt_cleanup(generated_config)

    for gate, status, default_code in (
        (
            CategoryBGateName.RUNTIME_TEARDOWN,
            runtime_teardown,
            CategoryBFailureCode.RUNTIME_TEARDOWN_FAILED,
        ),
        (
            CategoryBGateName.BROKER_SHUTDOWN,
            broker_status,
            CategoryBFailureCode.BROKER_SHUTDOWN_INCOMPLETE,
        ),
        (
            CategoryBGateName.GENERATED_CONFIG_CLEANUP,
            cleanup_status,
            CategoryBFailureCode.GENERATED_CONFIG_CLEANUP_UNVERIFIED,
        ),
    ):
        gate_statuses[gate.value] = status.status_text
        if not status.closure_satisfied:
            # Each status already carries its own precise code for every
            # unsatisfied state it can reach; the per-gate default exists so a
            # future state that forgot one can never inherit ANOTHER gate's
            # code.
            _fail(gate, getattr(status, "failure_code", None) or default_code)

    compatibility_established = all(_passed(gate) for gate in COMPATIBILITY_GATES)
    closure_established = (
        runtime_teardown.closure_satisfied
        and broker_status.closure_satisfied
        and cleanup_status.closure_satisfied
    )
    # NEVER true alongside a failed teardown/cleanup -- this single boolean is
    # what the evidence body records as ``compatibility_gate_passed``.
    provisional_pass = compatibility_established and closure_established

    # -- retained-evidence safety gate ---------------------------------------
    safety: ArtifactSafetyContext | None
    try:
        safety = build_run_safety_context(
            secret_context=secret_context,
            broker_session=broker_session,
            run_workspace=run_workspace,
            route_descriptor=route_descriptor,
        )
    except CategoryBSafetyContextError:
        safety = None

    if safety is None:
        evidence = CategoryBEvidence._refused(_SAFETY_CONTEXT_UNPROVABLE_REFUSAL)
        _fail(CategoryBGateName.EVIDENCE_SAFETY, CategoryBFailureCode.SAFETY_CONTEXT_UNPROVABLE)
    else:
        evidence = _build_evidence(
            candidate=candidate,
            route_descriptor=route_descriptor,
            observed_pi_version=observed_pi_version,
            facts=facts,
            compatibility_gate_passed=provisional_pass,
            gate_status_pairs=tuple(sorted(gate_statuses.items())),
            runtime_teardown=runtime_teardown,
            broker_shutdown=broker_status,
            cleanup=cleanup_status,
            safety=safety,
        )
        if evidence.retention_ready:
            gate_statuses[CategoryBGateName.EVIDENCE_SAFETY.value] = _STATUS_PASSED
        else:
            _fail(CategoryBGateName.EVIDENCE_SAFETY, CategoryBFailureCode.EVIDENCE_SCRUB_REFUSED)

    outcome = (
        CategoryBOutcome.CATEGORY_B_GATE_PASSED
        if provisional_pass and evidence.retention_ready
        else CategoryBOutcome.INFRASTRUCTURE_REFUSAL
    )
    if outcome is CategoryBOutcome.INFRASTRUCTURE_REFUSAL and failed_gate is None:
        # Defensive, and PROVABLY UNREACHABLE (FU2F): EVIDENCE_SAFETY is
        # unconditionally resolved -- to PASSED, or via one of the two
        # `_fail(EVIDENCE_SAFETY, ...)` calls immediately above -- on EVERY
        # path through the safety/evidence block above, before this line
        # ever runs. `provisional_pass=False` likewise always traces back to
        # an earlier `_fail` call (every compatibility gate that is not
        # PASSED chains back, through `_GATE_PREREQUISITES`, to a genuinely
        # FAILED gate -- RUN_CORRELATION is never NOT_REACHED -- and every
        # closure gate that is not satisfied is `_fail`-ed in the loop
        # above). So `failed_gate` can never still be `None` here. This line
        # is kept as a belt-and-suspenders invariant guard, not a reachable
        # branch: `MALFORMED_ADAPTER_RESULT` is deliberately NOT part of
        # EVIDENCE_SAFETY's accepted terminal vocabulary (see the module-level
        # note above `CategoryBControllerResult`'s per-gate binding), so if
        # this line ever fires due to a future regression, the
        # `CategoryBControllerResult` constructed immediately below will
        # itself raise loudly rather than silently accepting a code the
        # current source can never actually produce.
        _fail(CategoryBGateName.EVIDENCE_SAFETY, CategoryBFailureCode.MALFORMED_ADAPTER_RESULT)

    return CategoryBControllerResult(
        candidate=candidate,
        outcome=outcome,
        semantic_prompts_sent=SEMANTIC_PROMPTS_SENT,
        failed_gate=failed_gate,
        failure_code=failure_code,
        facts=facts,
        observed_pi_version=observed_pi_version,
        pi_config_created=generated_config is not None,
        broker_created=broker_session is not None,
        runtime_session_established=runtime_session is not None,
        runtime_teardown=runtime_teardown,
        broker_shutdown=broker_status,
        cleanup=cleanup_status,
        evidence=evidence,
        _gate_status_pairs=tuple(sorted(gate_statuses.items())),
    )


def _creator_retained_ownership_state(
    *, resource_created: bool, cleanup_attempted: bool, cleanup_verified_success: bool
) -> ResourceClosureState:
    """The shared FU3 Sec. 9.3 rows 2-4 mapping, written exactly ONCE.

    The controller has NO partial-close callable for any of these rows -- not
    for the stranded one, and not for the attempted one. Zero cleanup calls
    occur here by anyone, so no repeat-close-safety assumption is ever
    required, and no controller recovery action is authorized for a stranded
    resource.
    """
    if not resource_created:
        return ResourceClosureState.NOT_REQUIRED
    if not cleanup_attempted:
        return ResourceClosureState.PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT
    if cleanup_verified_success:
        return ResourceClosureState.CLOSED_BY_CREATOR_VERIFIED
    return ResourceClosureState.CLOSED_BY_CREATOR_UNVERIFIED


def _close_runtime(
    *,
    launch_attempted: bool,
    observation: RuntimeLaunchObservation | None,
    session_trusted: bool,
    shutdown_runtime: Callable[[RuntimeSession], RuntimeShutdownObservation],
) -> RuntimeTeardownStatus:
    """Close AIDO's runtime resource, targeting THAT EXACT session.

    **Possession is not authority (FU3 Sec. 9.4).** When the launch handed
    back a session that does not carry this run's own ``run_id``, or carries a
    foreign ``broker_session_id``, ``shutdown_runtime`` is **not called at
    all** -- not called and then discounted, not called. A live shutdown
    against a resource this run cannot prove it owns could race another,
    possibly still-active invocation's lifecycle. The refusal is reported as
    ``RUNTIME_SHUTDOWN_REFUSED_FOREIGN_SESSION`` with ``attempted=False``,
    ``authority_available=False``, ``closure_satisfied=False``.

    **No partial handle crosses this boundary (FU3 Sec. 9.3).** When the
    creator returned no trusted session it retained its own cleanup
    authority; this function has no callable for that branch and issues zero
    close calls. It reads only the creator's three orthogonal facts, and
    derives ``cleanup_verified_success`` through the observation's own
    AIDO-owned property -- never from a creator-supplied verdict, and never
    from "the close call returned without raising".

    Never claims a descendant process, provider inference or GPU work
    stopped.
    """
    if not launch_attempted:
        return RuntimeTeardownStatus(state=ResourceClosureState.NOT_REQUIRED)
    if observation is None:
        # The adapter raised or returned a malformed value: no observation
        # object exists, so AIDO holds nothing it could act on. It genuinely
        # cannot distinguish "raised having created nothing" from "raised
        # having created something and abandoned it" -- both are refused
        # identically and conservatively.
        return RuntimeTeardownStatus(
            state=ResourceClosureState.SHUTDOWN_AUTHORITY_UNAVAILABLE,
            failure_code=CategoryBFailureCode.RUNTIME_TEARDOWN_AUTHORITY_UNAVAILABLE,
        )
    if observation.session is None:
        state = _creator_retained_ownership_state(
            resource_created=observation.resource_created,
            cleanup_attempted=observation.cleanup_attempted,
            cleanup_verified_success=observation.cleanup_verified_success,
        )
        return RuntimeTeardownStatus(
            state=state, failure_code=_RUNTIME_CLOSURE_FAILURE_CODES.get(state)
        )
    if not session_trusted:
        return RuntimeTeardownStatus(
            state=ResourceClosureState.SHUTDOWN_REFUSED_FOREIGN_SESSION,
            failure_code=CategoryBFailureCode.RUNTIME_SHUTDOWN_REFUSED_FOREIGN_SESSION,
        )

    shutdown_observation, adapter_code = _invoke(
        shutdown_runtime, observation.session, expected=RuntimeShutdownObservation
    )
    if adapter_code is not None:
        return RuntimeTeardownStatus(
            state=ResourceClosureState.SHUTDOWN_FAILED,
            failure_code=CategoryBFailureCode.RUNTIME_TEARDOWN_FAILED,
        )
    if shutdown_observation.runtime_session_id != observation.session.runtime_session_id:
        return RuntimeTeardownStatus(
            state=ResourceClosureState.SHUTDOWN_FAILED,
            failure_code=CategoryBFailureCode.RUNTIME_SESSION_MISMATCH,
        )
    succeeded = (
        shutdown_observation.shutdown_call_returned
        and shutdown_observation.orchestrator_direct_child_reported_exit
    )
    if succeeded:
        return RuntimeTeardownStatus(state=ResourceClosureState.CLOSED_BY_ORCHESTRATOR)
    return RuntimeTeardownStatus(
        state=ResourceClosureState.SHUTDOWN_FAILED,
        failure_code=CategoryBFailureCode.RUNTIME_TEARDOWN_FAILED,
    )


def _close_broker(
    *,
    creation_attempted: bool,
    observation: BrokerCreationObservation | None,
    session_trusted: bool,
    shutdown_broker: Callable[[BrokerSession], BrokerShutdownObservation],
) -> BrokerShutdownStatus:
    """Shut down THAT EXACT broker session, and report only what it returned.

    The broker side is the exact mirror of :func:`_close_runtime`, including
    FU3 Sec. 9.4's absolute refusal: a broker session carrying a foreign
    ``run_id`` is **never** passed to ``shutdown_broker``. I2B-FU1 called it
    anyway and merely withheld ``closure_satisfied``; that was a live action
    against a resource this run never proved it owns.

    ``reached_closed`` is the broker lifecycle's own terminal state --
    ``STATE_TEARDOWN_INCOMPLETE`` is not verified closure -- and is never a
    claim about any process.
    """
    if not creation_attempted:
        return BrokerShutdownStatus(state=ResourceClosureState.NOT_REQUIRED)
    if observation is None:
        return BrokerShutdownStatus(
            state=ResourceClosureState.SHUTDOWN_AUTHORITY_UNAVAILABLE,
            failure_code=CategoryBFailureCode.BROKER_SHUTDOWN_AUTHORITY_UNAVAILABLE,
        )
    if observation.session is None:
        state = _creator_retained_ownership_state(
            resource_created=observation.resource_created,
            cleanup_attempted=observation.cleanup_attempted,
            cleanup_verified_success=observation.cleanup_verified_success,
        )
        return BrokerShutdownStatus(
            state=state, failure_code=_BROKER_CLOSURE_FAILURE_CODES.get(state)
        )
    if not session_trusted:
        return BrokerShutdownStatus(
            state=ResourceClosureState.SHUTDOWN_REFUSED_FOREIGN_SESSION,
            failure_code=CategoryBFailureCode.BROKER_SHUTDOWN_REFUSED_FOREIGN_SESSION,
        )

    shutdown_observation, adapter_code = _invoke(
        shutdown_broker, observation.session, expected=BrokerShutdownObservation
    )
    if adapter_code is not None:
        return BrokerShutdownStatus(
            state=ResourceClosureState.SHUTDOWN_FAILED,
            failure_code=CategoryBFailureCode.BROKER_SHUTDOWN_INCOMPLETE,
        )
    if shutdown_observation.session_id != observation.session.session_id:
        return BrokerShutdownStatus(
            state=ResourceClosureState.SHUTDOWN_FAILED,
            failure_code=CategoryBFailureCode.BROKER_SESSION_MISMATCH,
        )
    if shutdown_observation.reached_closed:
        return BrokerShutdownStatus(state=ResourceClosureState.CLOSED_BY_ORCHESTRATOR)
    return BrokerShutdownStatus(
        state=ResourceClosureState.SHUTDOWN_FAILED,
        failure_code=CategoryBFailureCode.BROKER_SHUTDOWN_INCOMPLETE,
    )


#: The per-resource-kind failure code for each UNSATISFIED creator-retained
#: closure state. ``NOT_REQUIRED`` and ``CLOSED_BY_CREATOR_VERIFIED`` are
#: deliberately absent: both are satisfied closures and must carry no code.
_RUNTIME_CLOSURE_FAILURE_CODES: Mapping[ResourceClosureState, CategoryBFailureCode] = (
    MappingProxyType(
        {
            ResourceClosureState.CLOSED_BY_CREATOR_UNVERIFIED: (
                CategoryBFailureCode.CLOSED_BY_CREATOR_UNVERIFIED
            ),
            ResourceClosureState.PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT: (
                CategoryBFailureCode.PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT
            ),
        }
    )
)

_BROKER_CLOSURE_FAILURE_CODES: Mapping[ResourceClosureState, CategoryBFailureCode] = (
    _RUNTIME_CLOSURE_FAILURE_CODES
)
