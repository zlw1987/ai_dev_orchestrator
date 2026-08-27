"""I2B -- Category-B Zero-Prompt Live-Gate Controller (OFFLINE WIRING ONLY).

**This module runs no Pi/Node process, opens no socket, calls no model, and
reads no real credential.** It contains no ``subprocess``, ``socket``,
``http``, ``urllib`` or ``os.environ`` primitive at all -- a source-level
regression test in this package's offline suite enforces that mechanically.
What it implements is the STATE MACHINE, the RESOURCE AUTHORITY, and the
LIFECYCLE CLOSURE rule for the future Category-B zero-prompt compatibility
gate (I2A design Sec. 15). Every future live operation is an INJECTED
adapter; every offline test supplies a synthetic double.

5F3B-I2B-FU1 -- what changed, and why
=====================================

The first I2B controller was a plausible-looking pipeline that could not
actually prove what it claimed. FU1 rebuilt it around the frozen AR2/O1
lifecycle rather than around I2A Sec. 15's narrative checklist. The five
substantive corrections:

**1. Broker first, launch second -- because frozen O1 says so.** The
initial controller placed ``broker_ready`` LAST, after the route check.
Frozen O1's observed lifecycle
(``experiments/pi_external_runtime_ar2_o1/run_o1.py``) mints the broker
binding, starts ``BrokerServer``, observes ``STATE_READY``, and only THEN
calls ``launch_and_handshake(..., pipe_name=server.pipe_name,
capability_id=binding.capability_id, token=binding.token)`` -- the launch
writes that binding into the disposable extension, so it cannot precede a
ready broker. I2A Sec. 15's numbered list is a CHECKLIST, not a dependency
graph; the frozen runtime fact wins. Here the ordering is enforced by the
type system: :class:`~qualification.i2b_session.RuntimeLaunchRequest` is
unconstructible from a broker session that is not ``reached_ready``.

**2. Every live observation is bound to the SAME runtime.** No-argument
callbacks (``h1_check()``, ``get_state()``, ``teardown()``) could each
return a valid result describing a DIFFERENT runtime instance, and nothing
would notice. Every adapter now takes the run's
:class:`~qualification.i2b_session.RuntimeSession` (or
:class:`~qualification.i2b_session.BrokerSession`) and returns an
observation carrying the session id it was produced from; the controller
compares it against the session the launch actually returned and refuses a
mismatch. Substituting runtime B's ``get_state``/teardown into runtime A's
run is refused, not silently accepted.

**3. H1 and the tool registry come from ONE ``get_commands`` response.**
Frozen AR2's own H1 evaluator takes the ``get_commands`` command list as
its argument (``ar2.handshakes.evaluate_extension_identity(commands,
extension_entry=...)``), so modelling H1 as an unrelated observation was
never faithful to the seam. They remain two DISTINCT gate facts, but both
are derived from one :class:`~qualification.i2b_session.GetCommandsObservation`
-- structurally unable to refer to two unrelated snapshots. ``get_state``
and H2 follow the same rule.

**4. The terminal pass rule includes lifecycle closure.** The initial
controller decided ``CATEGORY_B_GATE_PASSED`` purely from the last
compatibility gate, BEFORE teardown, cleanup and the evidence scrub ran --
so a run whose teardown failed still returned a pass, and its evidence
still said ``compatibility_gate_passed: true``. A Category-B PASS now
additionally requires: every required teardown closed truthfully, generated-
config cleanup verified, and the evidence's own scrub gate clean.

**5. The safety context carries the run's REAL sensitive values.** The
initial controller hard-coded ``broker_token=None, pipe_name=None,
capability_id=None, workspace_absolute_path=None`` -- silently substituting
``None`` for values a live run genuinely has, which is exactly how an
endpoint or a binding survives into a retained artifact. The broker session
now carries the binding and the controller declares all of it, plus the
run's workspace root, to the already-accepted, UNMODIFIED I1
``ArtifactSafetyContext``.

Gate order (this controller's own, derived from the frozen lifecycle)
--------------------------------------------------------------------

.. code-block:: text

    non-secret preflight                  (reused i2_credentials, unmodified)
      -> connection-value read authority   (reused i2_credentials, unmodified)
      -> route descriptor                  (i2_route, candidate identity only)
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
      -> exact authorized registry  /
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

:data:`SEMANTIC_PROMPTS_SENT` is a module constant ``0``, and no name in
this module is ever bound to any other value for it. This module defines
NO function that accepts, sends, or forwards a semantic prompt, a task
prompt, or an agent instruction of any kind -- there is nothing here for
such a value to travel through. There is no candidate classification, no
hard bar, no ranking, and no ``AUTONOMOUS_PASS``/``AUTONOMOUS_FAIL``: this
module imports nothing from :mod:`qualification.outcomes`,
:mod:`qualification.hard_bar`, :mod:`qualification.ranking`, or
:mod:`qualification.records`'s record builder. **Every** Category-B failure
is a pre-prompt infrastructure refusal.

Truthful claim scope
--------------------

Teardown truthfulness is bounded. This module reports only that AIDO's own
teardown call was attempted and what it returned, and -- separately -- that
the broker's own lifecycle reached ``CLOSED``. It **never** claims a
descendant process was terminated, that Pi/provider inference stopped, or
that GPU work stopped. A returned local teardown call is not a claim about
backend inference.

Not implemented here, and not authorized by this slice: any live Pi/Node
launch, any real RPC/broker call, any real credential read, a real live
adapter, a generic ``RuntimeAdapter``/``AgentRuntime`` framework, a
candidate implementer, a fixer, or any code path that could send a
semantic prompt.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass, field, fields
from enum import Enum
from types import MappingProxyType
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
    CREDENTIAL_MECHANISM,
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
from .i2b_session import (
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
)
from .safety import ArtifactSafetyContext, qualification_scrub_check

#: Category-B sends no semantic prompt, ever. Nothing in this module binds
#: any other value to the run's prompt count.
SEMANTIC_PROMPTS_SENT: int = 0

#: The exact, fixed authorized AIDO tool registry (I2A Sec. 15 item 6), as an
#: ORDERED, SORTED tuple rather than a set. Duplicated as a VALUE from
#: ``ar2.pi_config.TOOL_ALLOWLIST`` -- never imported -- per this package's
#: established ``i2_environment`` precedent.
#:
#: **Deliberately not a ``frozenset``.** The initial I2B compared
#: ``frozenset(observed) == frozenset(authorized)``, which collapses
#: duplicates: a runtime reporting ``("aido_read", "aido_read")`` alongside a
#: genuine ``aido_edit`` -- or reporting the same command twice from two
#: different sources -- compared equal. The registry gate now compares the
#: SORTED OBSERVED NAME SEQUENCE, so a duplicate or a missing entry fails
#: closed.
AUTHORIZED_TOOL_NAMES: tuple[str, ...] = ("aido_edit", "aido_read")

_STATUS_NOT_REACHED = "NOT_REACHED"
_STATUS_PASSED = "PASSED"
_STATUS_NOT_REQUIRED = "NOT_REQUIRED"
_STATUS_CLOSED_BY_CREATOR = "CLOSED_BY_CREATOR"


class CategoryBFailureCode(str, Enum):
    """Bounded, declared Category-B failure codes. Never free-form prose."""

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
    TOOL_REGISTRY_MISMATCH = "TOOL_REGISTRY_MISMATCH"
    GET_STATE_FAILED = "GET_STATE_FAILED"
    GET_STATE_RESPONSE_SHAPE_NOT_UNDERSTOOD = "GET_STATE_RESPONSE_SHAPE_NOT_UNDERSTOOD"
    H2_PROVIDER_MODEL_IDENTITY_MISMATCH = "H2_PROVIDER_MODEL_IDENTITY_MISMATCH"
    PROTOCOL_VIOLATION_OBSERVED = "PROTOCOL_VIOLATION_OBSERVED"
    EXTENSION_ERROR_OBSERVED = "EXTENSION_ERROR_OBSERVED"
    ROUTE_CHECK_FAILED = "ROUTE_CHECK_FAILED"
    RUNTIME_TEARDOWN_FAILED = "RUNTIME_TEARDOWN_FAILED"
    RUNTIME_TEARDOWN_AUTHORITY_UNAVAILABLE = "RUNTIME_TEARDOWN_AUTHORITY_UNAVAILABLE"
    BROKER_SHUTDOWN_INCOMPLETE = "BROKER_SHUTDOWN_INCOMPLETE"
    BROKER_SHUTDOWN_AUTHORITY_UNAVAILABLE = "BROKER_SHUTDOWN_AUTHORITY_UNAVAILABLE"
    GENERATED_CONFIG_CLEANUP_UNVERIFIED = "GENERATED_CONFIG_CLEANUP_UNVERIFIED"
    EVIDENCE_SCRUB_REFUSED = "EVIDENCE_SCRUB_REFUSED"
    SAFETY_CONTEXT_UNPROVABLE = "SAFETY_CONTEXT_UNPROVABLE"
    MALFORMED_ADAPTER_RESULT = "MALFORMED_ADAPTER_RESULT"
    ADAPTER_RAISED = "ADAPTER_RAISED"


class CategoryBGateName(str, Enum):
    """Every stage this controller gates, in exactly its evaluation order."""

    # -- compatibility facts --
    NON_SECRET_PREFLIGHT = "non_secret_preflight"
    CONNECTION_VALUES = "connection_values"
    ROUTE_DESCRIPTOR = "route_descriptor"
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
    TOOL_REGISTRY = "tool_registry"
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
COMPATIBILITY_GATES: tuple[CategoryBGateName, ...] = (
    CategoryBGateName.NON_SECRET_PREFLIGHT,
    CategoryBGateName.CONNECTION_VALUES,
    CategoryBGateName.ROUTE_DESCRIPTOR,
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
    CategoryBGateName.TOOL_REGISTRY,
    CategoryBGateName.GET_STATE,
    CategoryBGateName.H2_PROVIDER_MODEL_IDENTITY,
    CategoryBGateName.PROTOCOL_INTEGRITY,
    CategoryBGateName.ROUTE_CHECK,
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
    Category-B never reaches a candidate-scoring decision, only a
    pre-prompt compatibility confirmation or a pre-prompt refusal. The
    refusal member's STRING VALUE deliberately matches
    ``qualification.outcomes.AutonomousClassification.INFRASTRUCTURE_REFUSAL``
    for vocabulary consistency, without importing that
    candidate-scoring-adjacent enum into this slice.
    """

    CATEGORY_B_GATE_PASSED = "CATEGORY_B_GATE_PASSED"
    INFRASTRUCTURE_REFUSAL = "INFRASTRUCTURE_REFUSAL"


class CategoryBControllerInputError(ValueError):
    """An AIDO-supplied controller argument is unusable. Refused before ANYTHING.

    Deliberately raised, not folded into a gate result. These are AIDO's
    OWN arguments, never adapter data or observation data, and a blank
    ``workspace_root`` in particular is not merely a bad input: it is the
    value :func:`build_run_safety_context` would have to declare as the
    workspace needle, so a run carrying one could never produce provably
    safe evidence. Refusing here -- before the non-secret preflight, and
    therefore before any connection value is read -- means a run that can
    never be safe never causes a credential read at all.
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
    records what AIDO itself derived from a bounded observation, so a
    reader can see WHICH fact was observed rather than only that "something
    passed". Every field is exactly ``bool``.

    ``pi_version_observed`` is provenance only: it records that a version
    was OBSERVABLE for this run, never that a particular version was
    authorized. Nothing anywhere in this package compares an observed Pi
    version against a pinned value.
    """

    pi_version_observed: bool = False
    rpc_launch_shape_valid: bool = False
    required_launch_flags_accepted: bool = False
    lf_jsonl_correlation_succeeded: bool = False
    get_commands_response_shape_understood: bool = False
    h1_extension_identity_matched: bool = False
    authorized_tool_registry_exact: bool = False
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


@dataclass(frozen=True)
class RuntimeTeardownStatus:
    """Whether AIDO's own runtime teardown was required, possible, and closed.

    **Claim scope.** ``succeeded`` means AIDO's own shutdown call returned
    AND reported that AIDO's own DIRECT child exited. It is never a claim
    that a descendant process was terminated, that Pi/provider inference
    stopped, or that GPU work stopped.

    ``closed_by_creator`` is the honest name for the one case where AIDO
    performs no teardown yet nothing is stranded: the launch adapter failed
    and declared, in its own
    :class:`~qualification.i2b_session.RuntimeLaunchObservation`, that it
    cleaned its partial resource internally before reporting failure.
    """

    launch_attempted: bool
    closed_by_creator: bool
    authority_available: bool
    attempted: bool
    succeeded: bool
    failure_code: CategoryBFailureCode | None

    def __post_init__(self) -> None:
        for name in (
            "launch_attempted",
            "closed_by_creator",
            "authority_available",
            "attempted",
            "succeeded",
        ):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"RuntimeTeardownStatus.{name} must be exactly a bool")
        if not self.launch_attempted and (
            self.closed_by_creator or self.authority_available or self.attempted
        ):
            raise ValueError(
                "RuntimeTeardownStatus: nothing can have been created, closed by its "
                "creator, or torn down when no launch was attempted"
            )
        if self.closed_by_creator and (self.attempted or self.authority_available):
            raise ValueError(
                "RuntimeTeardownStatus: a resource its creator already closed leaves "
                "AIDO no authority to tear down and nothing to attempt"
            )
        if self.succeeded and not self.attempted:
            raise ValueError("RuntimeTeardownStatus: succeeded requires attempted")
        if self.attempted and not self.authority_available:
            raise ValueError("RuntimeTeardownStatus: attempted requires authority_available")
        if self.succeeded and self.failure_code is not None:
            raise ValueError("RuntimeTeardownStatus: a success must not carry a failure_code")

    @property
    def closure_satisfied(self) -> bool:
        """Whether this run left AIDO's runtime resource truthfully closed."""
        if not self.launch_attempted:
            return True
        if self.closed_by_creator:
            return True
        return self.attempted and self.succeeded

    @property
    def status_text(self) -> str:
        if not self.launch_attempted:
            return _STATUS_NOT_REQUIRED
        if self.closed_by_creator:
            return _STATUS_CLOSED_BY_CREATOR
        if self.succeeded:
            return "SUCCEEDED"
        code = self.failure_code or CategoryBFailureCode.RUNTIME_TEARDOWN_FAILED
        return f"FAILED:{code.value}"


@dataclass(frozen=True)
class BrokerShutdownStatus:
    """Whether AIDO's own broker shutdown was required, possible, and CLOSED.

    ``reached_closed`` is the broker lifecycle's own terminal state, as
    frozen AR2's ``BrokerServer.shutdown()`` reports it -- never a claim
    about any process.
    """

    creation_attempted: bool
    authority_available: bool
    attempted: bool
    reached_closed: bool
    failure_code: CategoryBFailureCode | None

    def __post_init__(self) -> None:
        for name in ("creation_attempted", "authority_available", "attempted", "reached_closed"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"BrokerShutdownStatus.{name} must be exactly a bool")
        if not self.creation_attempted and (
            self.authority_available or self.attempted or self.reached_closed
        ):
            raise ValueError(
                "BrokerShutdownStatus: nothing can have been closed when no broker "
                "creation was attempted"
            )
        if self.reached_closed and not self.attempted:
            raise ValueError("BrokerShutdownStatus: reached_closed requires attempted")
        if self.attempted and not self.authority_available:
            raise ValueError("BrokerShutdownStatus: attempted requires authority_available")
        if self.reached_closed and self.failure_code is not None:
            raise ValueError("BrokerShutdownStatus: a closed broker must not carry a failure_code")

    @property
    def closure_satisfied(self) -> bool:
        if not self.creation_attempted:
            return True
        return self.attempted and self.reached_closed

    @property
    def status_text(self) -> str:
        if not self.creation_attempted:
            return _STATUS_NOT_REQUIRED
        if self.reached_closed:
            return "CLOSED"
        code = self.failure_code or CategoryBFailureCode.BROKER_SHUTDOWN_INCOMPLETE
        return f"FAILED:{code.value}"


@dataclass(frozen=True)
class CleanupStatus:
    """Whether generated-config cleanup was attempted, and its phase-aware result.

    ``classification`` is populated ONLY on a failed/unverified cleanup, via
    :func:`~qualification.i2_cleanup.classify_cleanup_failure` called with
    ``semantic_prompts_sent=0`` -- the only value this module can ever
    supply, since Category-B never sends a prompt.
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

    @property
    def closure_satisfied(self) -> bool:
        """No config created is satisfied; a created config must be VERIFIED gone."""
        if not self.attempted:
            return True
        return bool(self.scrub_verified)

    @property
    def status_text(self) -> str:
        if not self.attempted:
            return _STATUS_NOT_REQUIRED
        if self.scrub_verified:
            return "VERIFIED_REMOVED"
        assert self.classification is not None
        assert self.classification.autonomous_classification is not None
        return f"FAILED:{self.classification.autonomous_classification.value}"


# -- immutable evidence --------------------------------------------------------


@dataclass(frozen=True)
class CategoryBEvidence:
    """Either a retention-ready safe evidence body, or a bounded refusal.

    **Immutable after construction, through every supported API.** The body
    is held as one canonical, already-scrub-checked JSON string; every
    :meth:`as_dict` call returns a FRESHLY deserialized dict, so no caller
    ever receives a reference into this object's state and no mutation of a
    returned dict can rewrite the evidence, the gate statuses nested inside
    it, or a later reader's view. The scrub result is exposed as an
    immutable ``tuple`` of bounded finding codes plus a ``bool`` -- never a
    mutable dict whose ``clean`` key could be flipped after validation.

    ``retention_ready`` is ``True`` only when the scrub gate found nothing;
    a refused body is not retained here in any form.
    """

    retention_ready: bool
    scrub_clean: bool
    scrub_findings: tuple[str, ...]
    _serialized: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        for name in ("retention_ready", "scrub_clean"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"CategoryBEvidence.{name} must be exactly a bool")
        if not isinstance(self.scrub_findings, tuple) or not all(
            isinstance(entry, str) for entry in self.scrub_findings
        ):
            raise ValueError("CategoryBEvidence.scrub_findings must be a tuple of str")
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
            raise ValueError(
                "CategoryBEvidence: a refused evidence body is never retained"
            )

    def as_dict(self) -> dict[str, Any]:
        """A FRESH, independent copy of the retained body (``{}`` if refused)."""
        if self._serialized is None:
            return {}
        return json.loads(self._serialized)

    def as_json(self) -> str:
        """The canonical serialized body, or ``""`` when nothing was retained."""
        return self._serialized or ""


# -- the controller result -----------------------------------------------------


@dataclass(frozen=True)
class CategoryBControllerResult:
    """The controller's one, complete, truthful result for one run.

    **Immutable after construction, through every supported API.** Gate
    statuses are held as an immutable tuple of pairs; :attr:`gate_statuses`
    hands back a ``MappingProxyType`` over a throwaway dict, so neither the
    proxy nor any dict a caller obtains from it can rewrite this object.
    The initial I2B exposed the underlying ``dict`` directly, and
    ``result.gate_statuses["broker_ready"] = "PASSED"`` silently rewrote a
    validated result.

    Valid by construction: ``semantic_prompts_sent`` is always exactly
    ``0``; a ``CATEGORY_B_GATE_PASSED`` outcome never carries a failure, and
    an ``INFRASTRUCTURE_REFUSAL`` outcome always does; and a pass requires
    every compatibility fact, every closure status, and retention-ready
    evidence.
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
        if self.semantic_prompts_sent != SEMANTIC_PROMPTS_SENT:
            raise ValueError(
                "CategoryBControllerResult: semantic_prompts_sent must be exactly 0 -- "
                "Category-B is a zero-semantic-prompt gate"
            )
        if not isinstance(self.facts, CompatibilityFacts):
            raise ValueError("CategoryBControllerResult.facts must be a CompatibilityFacts")
        if not isinstance(self.evidence, CategoryBEvidence):
            raise ValueError("CategoryBControllerResult.evidence must be a CategoryBEvidence")
        if self.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED:
            if self.failed_gate is not None or self.failure_code is not None:
                raise ValueError(
                    "CategoryBControllerResult: a passed run must not carry a "
                    "failed_gate/failure_code"
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


def _invoke(fn: Callable[..., Any], *args: Any, expected: type) -> tuple[Any, CategoryBFailureCode | None]:
    """Call one injected adapter, bounding BOTH failure modes.

    Distinguishes "the adapter raised" from "the adapter returned something
    that is not the declared observation type" -- the initial I2B collapsed
    both into ``None`` and then, for an adapter that simply returned
    ``None``, recorded no failure at all and crashed later on its own
    result invariant. Neither the exception's ``str()``/``repr()`` nor the
    unexpected value is ever read or retained.

    The type check is ``type(value) is expected``, NOT ``isinstance`` -- a
    subclass could override a validated field with a property that returns
    a different value on each read, defeating both the exact-bool rule and
    the session-id comparisons. No legitimate adapter needs a subclass of
    these value objects, so the exact-type rule costs nothing and closes
    the substitution.
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
    workspace_root: str,
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
    ``workspace_absolute_path``  the controller's required workspace root
    ===========================  ==========================================

    **``bearer_token`` is DERIVED, not assumed.** I2A's frozen credential
    mechanism for this route is
    ``i2_route.CREDENTIAL_MECHANISM == "models_json_env_interpolation"``:
    the credential travels as the generated ``models.json`` env
    interpolation of the one child carrier, and NO separate bearer value is
    ever minted for it. This function refuses (
    :class:`CategoryBSafetyContextError`) rather than guessing if the run's
    descriptor ever reports a different mechanism -- so ``None`` here is a
    proven absence, not an omission. The frozen, unmodified I2
    ``QualificationRouteSecretContext.to_safety_context`` already encodes
    exactly that, and is reused rather than reimplemented.

    A run that failed before a secret context existed still declares
    whatever it DOES have -- the workspace root always exists -- rather than
    falling back to ``ArtifactSafetyContext.none_declared()``, which would
    silently drop a real needle.
    """
    if route_descriptor is not None and route_descriptor.credential_mechanism != CREDENTIAL_MECHANISM:
        raise CategoryBSafetyContextError("UNEXPECTED_CREDENTIAL_MECHANISM")
    broker_token = broker_session.broker_token if broker_session is not None else None
    pipe_name = broker_session.pipe_name if broker_session is not None else None
    capability_id = broker_session.capability_id if broker_session is not None else None
    if secret_context is not None:
        return secret_context.to_safety_context(
            broker_token=broker_token,
            pipe_name=pipe_name,
            capability_id=capability_id,
            workspace_absolute_path=workspace_root,
        )
    return ArtifactSafetyContext(
        endpoint_host=None,
        api_key=None,
        bearer_token=None,
        broker_token=broker_token,
        pipe_name=pipe_name,
        capability_id=capability_id,
        workspace_absolute_path=workspace_root,
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
    every compatibility fact, every teardown and the config cleanup have
    been resolved -- it is never true alongside a failed closure. Nothing
    is written to disk here; persisting a Category-B artifact through
    :func:`qualification.safety.emit_evidence_or_refuse` is a decision for a
    future, separately authorized live phase.

    The ``evidence_safety`` gate is deliberately OMITTED from the recorded
    ``gate_statuses``: an evidence body cannot truthfully record the outcome
    of the gate that is about to judge it, and recording it as
    ``NOT_REACHED`` would be a false statement about a gate that always
    runs. Its outcome lives on the controller result instead.
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
            "Pi/provider inference stopped, or that GPU work stopped. No semantic "
            "prompt was sent, and no candidate model was scored."
        ),
    }
    check = qualification_scrub_check(payload, safety)
    findings = tuple(str(entry) for entry in check["findings"])
    if check["clean"]:
        return CategoryBEvidence(
            retention_ready=True,
            scrub_clean=True,
            scrub_findings=findings,
            _serialized=json.dumps(payload, ensure_ascii=True, sort_keys=True),
        )
    return CategoryBEvidence(
        retention_ready=False, scrub_clean=False, scrub_findings=findings, _serialized=None
    )


def _attempt_cleanup(generated_config: GeneratedQualificationConfig | None) -> CleanupStatus:
    """Attempt generated-config cleanup iff a config was ever created.

    Reuses ``i2_cleanup.scrub_generated_qualification_config`` and, on any
    failure or unverified result, ``i2_cleanup.classify_cleanup_failure``
    with ``semantic_prompts_sent=0`` unconditionally -- Category-B
    structurally cannot supply any other value.
    """
    if generated_config is None:
        return CleanupStatus(attempted=False, scrub_verified=None, classification=None)
    try:
        result = scrub_generated_qualification_config(generated_config)
        verified = bool(result.scrub_verified)
    except Exception:  # noqa: BLE001 - bounded below; the text is never read
        verified = False
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
    experiment_root: str,
    workspace_root: str,
    ambient_environ: Mapping[str, str],
    node_executable: str,
    non_secret_gates: Sequence[Callable[[], PreflightGateResult]],
    read_connection: Callable[[], ConnectionValues],
    create_broker: Callable[[BrokerCreationRequest], BrokerSession],
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

    Resource authority is bound MECHANICALLY, not by convention:

    - the controller mints one per-run ``run_id`` nonce and refuses a broker
      session that does not carry it;
    - the runtime launch request is CONSTRUCTED by the controller from that
      broker session, and is unconstructible unless the broker already
      reached ``READY`` (frozen O1's observed ordering);
    - every post-launch observation must carry the ``runtime_session_id``
      the launch actually returned;
    - teardown targets that exact runtime session and that exact broker
      session.

    A failing compatibility gate halts the sequence before ANY further LIVE
    operation, and every gate that would have needed one is left
    ``"NOT_REACHED"``. Facts still derivable from an observation ALREADY IN
    HAND are recorded anyway -- H1 and the exact tool registry both come
    from one ``get_commands`` response, so a failed H1 does not erase what
    that same response proved about the registry, and neither costs an
    extra live call. Runtime
    teardown, broker shutdown and generated-config cleanup are always
    attempted for whatever resources may exist -- on the failure path and
    on the fully-passed path alike, in frozen O1's order (runtime first,
    broker second, generated config last).

    A terminal ``CATEGORY_B_GATE_PASSED`` requires ALL of: every
    compatibility fact established, ``semantic_prompts_sent == 0``, every
    required teardown closed truthfully, verified generated-config cleanup,
    and retention-ready safe evidence. Anything else is
    ``INFRASTRUCTURE_REFUSAL`` with ``semantic_prompts_sent = 0``.
    """
    # AIDO's OWN arguments are checked FIRST -- before the non-secret
    # preflight, and therefore before any connection value can be read.
    for _name, _value in (
        ("candidate", candidate),
        ("experiment_root", experiment_root),
        ("workspace_root", workspace_root),
        ("node_executable", node_executable),
    ):
        if not isinstance(_value, str) or not _value.strip():
            raise CategoryBControllerInputError(
                f"category-B controller refused: {_name} must be a non-blank str"
            )

    run_id = secrets.token_hex(16)
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
        facts are derived from ONE observation, so a later fact from that
        same observation can pass while an earlier one from it failed. No
        further LIVE operation may be issued unless every fact established
        so far actually passed.
        """
        return all(_passed(gate) for gate in gates)

    connection_values: ConnectionValues | None = None
    route_descriptor: RouteDescriptor | None = None
    secret_context: QualificationRouteSecretContext | None = None
    generated_config: GeneratedQualificationConfig | None = None
    launch_environment: LaunchEnvironment | None = None
    broker_session: BrokerSession | None = None
    broker_creation_attempted = False
    runtime_session: RuntimeSession | None = None
    launch_attempted = False
    closed_by_creator = False
    observed_pi_version: str | None = None
    fact_values: dict[str, bool] = {}

    # -- NON_SECRET_PREFLIGHT + CONNECTION_VALUES (credential-read boundary) --
    try:
        connection_values = resolve_connection_after_preflight(
            non_secret_gates=non_secret_gates, read_connection=read_connection
        )
    except InfrastructureRefusal as exc:
        if exc.gate_name == "connection_values":
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

    if connection_values is not None:
        _pass(CategoryBGateName.NON_SECRET_PREFLIGHT)
        _pass(CategoryBGateName.CONNECTION_VALUES)

        # -- ROUTE_DESCRIPTOR --
        try:
            route_descriptor = route_descriptor_for_candidate(candidate)
            _pass(CategoryBGateName.ROUTE_DESCRIPTOR)
        except RouteDescriptorError:
            _fail(CategoryBGateName.ROUTE_DESCRIPTOR, CategoryBFailureCode.ROUTE_DESCRIPTOR_INVALID)
        except Exception:  # noqa: BLE001
            _fail(CategoryBGateName.ROUTE_DESCRIPTOR, CategoryBFailureCode.ADAPTER_RAISED)

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
                CategoryBGateName.SECRET_CONTEXT,
                CategoryBFailureCode.SECRET_CONTEXT_CONSTRUCTION_FAILED,
            )
        except Exception:  # noqa: BLE001
            _fail(CategoryBGateName.SECRET_CONTEXT, CategoryBFailureCode.ADAPTER_RAISED)

    if secret_context is not None:
        # -- PI_CONFIG_GENERATION [DISPOSABLE RESOURCE CREATION POINT] --
        assert route_descriptor is not None
        try:
            generated_config = write_qualification_pi_config(
                experiment_root, model_id=route_descriptor.model_id, base_url=secret_context.base_url
            )
            _pass(CategoryBGateName.PI_CONFIG_GENERATION)
        except (QualificationPiConfigError, QualificationPiConfigCleanupError, CleanupAuthorityError):
            _fail(
                CategoryBGateName.PI_CONFIG_GENERATION,
                CategoryBFailureCode.PI_CONFIG_GENERATION_FAILED,
            )
        except Exception:  # noqa: BLE001
            _fail(CategoryBGateName.PI_CONFIG_GENERATION, CategoryBFailureCode.ADAPTER_RAISED)

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
        # -- BROKER_SESSION [LIVE RESOURCE CREATION POINT, FROZEN O1 ORDER] --
        # Frozen O1 mints the broker binding and reaches READY BEFORE Pi is
        # launched, because the launch writes that binding into the
        # disposable extension. The broker is therefore created here, not
        # confirmed at the end of the sequence.
        broker_creation_attempted = True
        try:
            creation_request = BrokerCreationRequest(run_id=run_id, workspace_root=workspace_root)
        except ObservationError:
            creation_request = None  # type: ignore[assignment]
            _fail(CategoryBGateName.BROKER_SESSION, CategoryBFailureCode.BROKER_CREATION_FAILED)
        if creation_request is not None:
            candidate_session, adapter_code = _invoke(
                create_broker, creation_request, expected=BrokerSession
            )
            if adapter_code is not None:
                _fail(
                    CategoryBGateName.BROKER_SESSION,
                    CategoryBFailureCode.BROKER_CREATION_FAILED
                    if adapter_code is CategoryBFailureCode.ADAPTER_RAISED
                    else adapter_code,
                )
            else:
                # Authority is retained for shutdown even when the session is
                # refused below -- a broker that was created for a different
                # run still has to be closed, not abandoned.
                broker_session = candidate_session
                if broker_session.run_id != run_id:
                    _fail(
                        CategoryBGateName.BROKER_SESSION,
                        CategoryBFailureCode.BROKER_SESSION_MISMATCH,
                    )
                else:
                    _pass(CategoryBGateName.BROKER_SESSION)

    if _passed(CategoryBGateName.BROKER_SESSION):
        # -- BROKER_READY (from that exact session, before any launch) --
        assert broker_session is not None
        fact_values["broker_reached_required_ready_state"] = broker_session.reached_ready
        if broker_session.reached_ready:
            _pass(CategoryBGateName.BROKER_READY)
        else:
            _fail(CategoryBGateName.BROKER_READY, CategoryBFailureCode.BROKER_NOT_READY)

    if _passed(CategoryBGateName.BROKER_READY):
        # -- RUNTIME_LAUNCH [LIVE RESOURCE CREATION POINT] --
        assert broker_session is not None and launch_environment is not None
        assert route_descriptor is not None
        try:
            launch_request = RuntimeLaunchRequest(
                run_id=run_id,
                broker_session=broker_session,
                launch_environment=launch_environment,
                workspace_root=workspace_root,
                provider_id=route_descriptor.provider_id,
                model_id=route_descriptor.model_id,
            )
        except ObservationError:
            launch_request = None  # type: ignore[assignment]
            _fail(
                CategoryBGateName.RUNTIME_LAUNCH,
                CategoryBFailureCode.RUNTIME_LAUNCH_REQUEST_UNCONSTRUCTIBLE,
            )
        if launch_request is not None:
            # Recorded as soon as the launch is ATTEMPTED, never only on a
            # confirmed success: an attempt that reports failure may still
            # have started a process, so closure must not be skipped.
            launch_attempted = True
            observation, adapter_code = _invoke(
                launch_runtime, launch_request, expected=RuntimeLaunchObservation
            )
            if adapter_code is not None:
                _fail(CategoryBGateName.RUNTIME_LAUNCH, adapter_code)
            else:
                observed_pi_version = observation.observed_pi_version
                runtime_session = observation.session
                closed_by_creator = observation.partial_resource_cleaned_internally
                fact_values["pi_version_observed"] = observation.pi_version_observed
                fact_values["rpc_launch_shape_valid"] = observation.launch_shape_valid
                fact_values["required_launch_flags_accepted"] = observation.required_flags_accepted
                fact_values["lf_jsonl_correlation_succeeded"] = (
                    observation.lf_jsonl_correlation_succeeded
                )
                if runtime_session is None:
                    _fail(
                        CategoryBGateName.RUNTIME_LAUNCH, CategoryBFailureCode.RUNTIME_LAUNCH_FAILED
                    )
                elif (
                    runtime_session.run_id != run_id
                    or runtime_session.broker_session_id != broker_session.session_id
                ):
                    _fail(
                        CategoryBGateName.RUNTIME_LAUNCH,
                        CategoryBFailureCode.RUNTIME_SESSION_MISMATCH,
                    )
                else:
                    _pass(CategoryBGateName.RUNTIME_LAUNCH)

    if _passed(CategoryBGateName.RUNTIME_LAUNCH):
        # -- the four INDEPENDENT launch facts (I2A Sec. 15 items 1-4) --
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
        # -- ONE get_commands observation -> GET_COMMANDS + H1 + TOOL_REGISTRY --
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

            # H1 -- derived from THIS response, never a second snapshot.
            matched = commands_observation.extension_identity_matched
            fact_values["h1_extension_identity_matched"] = matched
            if matched:
                _pass(CategoryBGateName.H1_EXTENSION_IDENTITY)
            else:
                _fail(
                    CategoryBGateName.H1_EXTENSION_IDENTITY,
                    CategoryBFailureCode.H1_EXTENSION_IDENTITY_MISMATCH,
                )

            # Exact authorized registry -- derived from THE SAME response.
            # A SORTED SEQUENCE comparison, so a duplicated entry cannot
            # collapse into a matching set.
            observed = tuple(sorted(commands_observation.command_names_in_report_order()))
            exact = observed == AUTHORIZED_TOOL_NAMES
            fact_values["authorized_tool_registry_exact"] = exact
            if exact:
                _pass(CategoryBGateName.TOOL_REGISTRY)
            else:
                _fail(CategoryBGateName.TOOL_REGISTRY, CategoryBFailureCode.TOOL_REGISTRY_MISMATCH)

    if _all_passed(
        CategoryBGateName.GET_COMMANDS,
        CategoryBGateName.H1_EXTENSION_IDENTITY,
        CategoryBGateName.TOOL_REGISTRY,
    ):
        # -- ONE get_state observation -> GET_STATE + H2 --
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

    if _all_passed(
        CategoryBGateName.GET_STATE, CategoryBGateName.H2_PROVIDER_MODEL_IDENTITY
    ):
        # -- PROTOCOL_INTEGRITY (I2A Sec. 15 item 8), session-bound --
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
        # -- ROUTE_CHECK (reused i2_route wiring, unmodified) --
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
    # -- then the generated config. Attempted on EVERY path. -----------------
    runtime_teardown = _close_runtime(
        launch_attempted=launch_attempted,
        closed_by_creator=closed_by_creator,
        runtime_session=runtime_session,
        session_trusted=_passed(CategoryBGateName.RUNTIME_LAUNCH),
        shutdown_runtime=shutdown_runtime,
    )
    broker_status = _close_broker(
        creation_attempted=broker_creation_attempted,
        broker_session=broker_session,
        session_trusted=_passed(CategoryBGateName.BROKER_SESSION),
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
            # unsatisfied state it can reach; the per-gate default exists so
            # a future state that forgot one can never inherit ANOTHER
            # gate's code.
            _fail(gate, getattr(status, "failure_code", None) or default_code)

    compatibility_established = all(_passed(gate) for gate in COMPATIBILITY_GATES)
    closure_established = (
        runtime_teardown.closure_satisfied
        and broker_status.closure_satisfied
        and cleanup_status.closure_satisfied
    )
    # NEVER true alongside a failed teardown/cleanup -- this single boolean
    # is what the evidence body records as ``compatibility_gate_passed``.
    provisional_pass = compatibility_established and closure_established

    # -- retained-evidence safety gate --------------------------------------
    try:
        safety = build_run_safety_context(
            secret_context=secret_context,
            broker_session=broker_session,
            workspace_root=workspace_root,
            route_descriptor=route_descriptor,
        )
    except CategoryBSafetyContextError:
        safety = None  # type: ignore[assignment]

    if safety is None:
        evidence = CategoryBEvidence(
            retention_ready=False,
            scrub_clean=False,
            scrub_findings=("safety_context_unprovable",),
            _serialized=None,
        )
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
        # Defensive: a refusal always names a gate. Reaching here would mean
        # an unclassified refusal, which is itself a defect -- report it as
        # a bounded malformed-adapter refusal rather than crashing on the
        # result's own invariant (the initial I2B did exactly that when an
        # adapter returned ``None``).
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


def _close_runtime(
    *,
    launch_attempted: bool,
    closed_by_creator: bool,
    runtime_session: RuntimeSession | None,
    session_trusted: bool,
    shutdown_runtime: Callable[[RuntimeSession], RuntimeShutdownObservation],
) -> RuntimeTeardownStatus:
    """Close AIDO's runtime resource, targeting THAT EXACT session.

    Three honest states, and no fourth:

    - the launch was never attempted, so nothing is owed;
    - the launch adapter failed and declared it closed its own partial
      resource internally, so AIDO performs no teardown and nothing is
      stranded;
    - a session exists, so AIDO's own shutdown is attempted against exactly
      that session and its returned observation must carry that session id.

    A launch that was attempted but handed back neither a session nor an
    internal-cleanup declaration is ``RUNTIME_TEARDOWN_AUTHORITY_UNAVAILABLE``
    -- closure is NOT satisfied, and the run cannot pass. Never claims a
    descendant process or backend inference stopped.

    ``session_trusted`` is ``False`` when the launch handed back a session
    that did NOT belong to this run (or to this run's broker). AIDO still
    attempts the shutdown -- that returned session is the only authority it
    holds, and abandoning it would strand a resource -- but closure is
    never reported satisfied for a session AIDO could not tie to its own
    run.
    """
    if not launch_attempted:
        return RuntimeTeardownStatus(
            launch_attempted=False,
            closed_by_creator=False,
            authority_available=False,
            attempted=False,
            succeeded=False,
            failure_code=None,
        )
    if runtime_session is None:
        if closed_by_creator:
            return RuntimeTeardownStatus(
                launch_attempted=True,
                closed_by_creator=True,
                authority_available=False,
                attempted=False,
                succeeded=False,
                failure_code=None,
            )
        return RuntimeTeardownStatus(
            launch_attempted=True,
            closed_by_creator=False,
            authority_available=False,
            attempted=False,
            succeeded=False,
            failure_code=CategoryBFailureCode.RUNTIME_TEARDOWN_AUTHORITY_UNAVAILABLE,
        )
    observation, adapter_code = _invoke(
        shutdown_runtime, runtime_session, expected=RuntimeShutdownObservation
    )
    if adapter_code is not None:
        return RuntimeTeardownStatus(
            launch_attempted=True,
            closed_by_creator=False,
            authority_available=True,
            attempted=True,
            succeeded=False,
            failure_code=CategoryBFailureCode.RUNTIME_TEARDOWN_FAILED,
        )
    if observation.runtime_session_id != runtime_session.runtime_session_id:
        return RuntimeTeardownStatus(
            launch_attempted=True,
            closed_by_creator=False,
            authority_available=True,
            attempted=True,
            succeeded=False,
            failure_code=CategoryBFailureCode.RUNTIME_SESSION_MISMATCH,
        )
    if not session_trusted:
        return RuntimeTeardownStatus(
            launch_attempted=True,
            closed_by_creator=False,
            authority_available=True,
            attempted=True,
            succeeded=False,
            failure_code=CategoryBFailureCode.RUNTIME_SESSION_MISMATCH,
        )
    succeeded = (
        observation.shutdown_call_returned
        and observation.orchestrator_direct_child_reported_exit
    )
    return RuntimeTeardownStatus(
        launch_attempted=True,
        closed_by_creator=False,
        authority_available=True,
        attempted=True,
        succeeded=succeeded,
        failure_code=None if succeeded else CategoryBFailureCode.RUNTIME_TEARDOWN_FAILED,
    )


def _close_broker(
    *,
    creation_attempted: bool,
    broker_session: BrokerSession | None,
    session_trusted: bool,
    shutdown_broker: Callable[[BrokerSession], BrokerShutdownObservation],
) -> BrokerShutdownStatus:
    """Shut down THAT EXACT broker session, and report only what it returned.

    Attempted whenever AIDO holds a broker session -- including a session
    whose ``run_id`` was refused, because a broker created for the wrong run
    still has to be closed rather than abandoned. ``session_trusted`` is
    ``False`` in exactly that case: the shutdown is still attempted, but
    closure is never reported satisfied for a broker AIDO could not tie to
    its own run. When broker creation was attempted but produced no session
    object at all, AIDO holds no authority to close anything: that is
    reported truthfully as ``BROKER_SHUTDOWN_AUTHORITY_UNAVAILABLE`` and
    closure is NOT satisfied.
    """
    if not creation_attempted:
        return BrokerShutdownStatus(
            creation_attempted=False,
            authority_available=False,
            attempted=False,
            reached_closed=False,
            failure_code=None,
        )
    if broker_session is None:
        return BrokerShutdownStatus(
            creation_attempted=True,
            authority_available=False,
            attempted=False,
            reached_closed=False,
            failure_code=CategoryBFailureCode.BROKER_SHUTDOWN_AUTHORITY_UNAVAILABLE,
        )
    observation, adapter_code = _invoke(
        shutdown_broker, broker_session, expected=BrokerShutdownObservation
    )
    if adapter_code is not None:
        return BrokerShutdownStatus(
            creation_attempted=True,
            authority_available=True,
            attempted=True,
            reached_closed=False,
            failure_code=CategoryBFailureCode.BROKER_SHUTDOWN_INCOMPLETE,
        )
    if observation.session_id != broker_session.session_id or not session_trusted:
        return BrokerShutdownStatus(
            creation_attempted=True,
            authority_available=True,
            attempted=True,
            reached_closed=False,
            failure_code=CategoryBFailureCode.BROKER_SESSION_MISMATCH,
        )
    return BrokerShutdownStatus(
        creation_attempted=True,
        authority_available=True,
        attempted=True,
        reached_closed=observation.reached_closed,
        failure_code=(
            None
            if observation.reached_closed
            else CategoryBFailureCode.BROKER_SHUTDOWN_INCOMPLETE
        ),
    )
