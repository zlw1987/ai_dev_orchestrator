"""5F3B-Q1-PRE1 -- ONE semantic task-attempt controller. OFFLINE WIRING ONLY.

**This module runs no Pi/Node process, opens no socket, calls no model, and
reads no real credential.** Every live operation -- broker creation, runtime
launch, the get_commands/get_state/protocol observations, the route check,
sending the one semantic prompt, collecting broker activity, collecting the
model's final report claims, and both teardown calls -- is an INJECTED
adapter. Every offline test supplies a synthetic double. This phase (5F3B-
Q1-PRE1) authorizes no live invocation of any of them: a future, separately
authorized phase would add real implementations, exactly the way
:mod:`qualification.i2b_live_adapters` was added only after
:mod:`qualification.i2b_controller` shipped offline.

Why this module exists, and why it is not ``i2b_controller`` reused
---------------------------------------------------------------------

:func:`qualification.i2b_controller.run_category_b_controller` is one atomic
function: it establishes Category-B compatibility and unconditionally tears
the runtime and broker down before it ever returns a result. That is exactly
correct for Category-B, which sends zero prompts by definition and therefore
has nothing further to do with a live session. A semantic task run needs the
opposite shape: the SAME compatibility facts must be established, and then
the SAME runtime session must be used to send exactly one prompt and observe
its turn to completion, BEFORE any teardown happens. There is no way to
obtain a not-yet-torn-down session from ``run_category_b_controller`` --
closure is baked into that one function body, and its internals
(``_close_runtime``, ``_close_broker``, the per-gate evaluation loop) are all
module-private. This is exactly the "frozen component cannot truthfully
represent a required semantic-run fact" case this phase's own instructions
anticipate: rather than editing ``i2b_controller.py`` (forbidden) or forcing
a session out of it (impossible -- there is nothing to force; the type
system and the function body do not expose one), this module is new,
qualification-owned orchestration that REUSES every reusable frozen piece:

- :mod:`qualification.i2b_session`'s typed resource-authority/observation
  objects (``BrokerCreationRequest``, ``BrokerSession``, ``RuntimeSession``,
  ``RuntimeLaunchRequest``, ``GetCommandsObservation``, ``GetStateObservation``,
  ``ProtocolObservation``, ...) -- imported, never redefined;
- :class:`qualification.i2b_controller.CompatibilityFacts` -- the identical
  13-field shape, reused directly rather than re-declared, because the 13
  facts a semantic run must establish before its prompt are the SAME 13
  facts Category-B establishes (this phase's own "PRE-PROMPT PREFIX"
  requirement lists exactly them);
- :class:`qualification.i2b_controller.RuntimeTeardownStatus` /
  :class:`qualification.i2b_controller.BrokerShutdownStatus` /
  :class:`qualification.i2b_controller.ResourceClosureState` -- reused
  directly for closure accounting, because resource-closure semantics do not
  depend on whether a prompt was sent;
- ``qualification.i2_route`` / ``i2_credentials`` / ``i2_secret_context`` /
  ``i2_pi_config`` / ``i2_composition`` / ``i2_environment`` / ``i2_cleanup``
  -- called exactly as :mod:`qualification.i2b_controller` calls them, in the
  same order, for the same reason (credential-read ordering, Sec. 7);
- ``ar2.observation`` / ``ar2.verification`` -- called directly (not
  injected), exactly as :mod:`qualification.fixtures` already calls them,
  because they are pure, deterministic, AIDO-owned functions of
  ``git_executable``/``python_executable`` plus a workspace path, not live
  model-facing operations;
- :mod:`qualification.outcomes` / ``validity`` / ``scope`` /
  ``report_accuracy`` / ``records`` / ``safety`` -- the SAME layer-2/3/4
  classification and emission machinery any qualification record must be
  built from, called exactly the way the design's five-layer model (Sec.
  17.3) requires.

**One genuinely new frozen-incompatibility, and its honest resolution.**
:class:`qualification.i2b_controller.CleanupStatus` hard-asserts, inside its
own ``__post_init__`` (via ``_require_category_b_cleanup_failure_shape``),
that any carried :class:`~qualification.i2_cleanup.CleanupFailureClassification`
is EXACTLY ``classify_cleanup_failure(semantic_prompts_sent=0)``'s own shape
-- because Category-B is structurally pre-prompt. A semantic task run's
cleanup can fail AFTER its one prompt was sent (``semantic_prompts_sent ==
1``), which that exact assertion refuses by construction. Reusing
``CleanupStatus`` unmodified would therefore be **silently wrong** for a
post-prompt cleanup failure -- not merely inconvenient. This module defines
its own :class:`SemanticCleanupStatus`, identical in shape and in the
underlying frozen function it calls (``i2_cleanup.classify_cleanup_failure``,
unmodified), parameterized by the run's ACTUAL ``semantic_prompts_sent``
rather than a hard-coded ``0``. No cleanup POLICY is duplicated: the same one
frozen classifier function is called either way.

Gate order
----------

.. code-block:: text

      run correlation id minted
      -> workspace authority (mint -- unmodified i2b_workspace -- then
         POPULATE with this task's fixture content, then verify the
         fixture's baseline against its frozen contract)
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
      -> Pi version / RPC launch shape / required flags / LF JSONL   (1 observation, 4 facts)
      -> get_commands / H1 / extension command namespace             (1 observation, 3 facts)
      -> get_state / H2                                              (1 observation, 2 facts)
      -> no protocol/extension error       (injected, session-bound)
      -> exact candidate model served      (reused i2_route, unmodified)
      -- compatibility facts end here; same 13 facts as Category-B --
      -> ONE semantic prompt dispatched    (injected)   [NEW]
      -> turn completion observed          (agent_settled / deadline_reached)   [NEW]
      -> broker activity collected         (injected)   [NEW]
      -> repository observed               (reused ar2.observation, unmodified)   [NEW]
      -> authoritative verification        (reused ar2.verification, unmodified)   [NEW]
      -> final report claims collected     (injected)   [NEW]
      -- post-turn facts end here --
      -> runtime teardown                  (frozen O1 order: runtime first)
      -> broker shutdown                   (frozen O1 order: broker second)
      -> generated-config cleanup          (reused i2_cleanup, unmodified)
      -> retained-evidence safety gate     (reused qualification.safety)

Exactly ONE semantic prompt
----------------------------

:data:`MAX_SEMANTIC_PROMPTS_PER_ATTEMPT` is a module constant ``1``. This
module defines no retry, no continuation, and no second call to the prompt
adapter for any reason -- not a stall, not a wrong result, not an adapter
error.

**5F3B-Q1-PRE1-FU1 -- ``semantic_prompts_sent`` is truth, not timing.**
Independent review reproduced a defect in this module's ORIGINAL PRE1 form:
``semantic_prompts_sent = 1`` was assigned immediately BEFORE the dispatch
adapter (``send_semantic_prompt``) was even called, so ANY dispatch-gate
outcome -- including one mechanically established as never having been sent
-- was recorded as though the one authorized prompt had been spent. This
module now sets ``semantic_prompts_sent`` to ``1`` in exactly ONE place, and
only AFTER a returned, well-typed
:class:`~qualification.semantic_session.SemanticPromptDispatchObservation`
mechanically establishes ``CONFIRMED_SENT`` (see
:mod:`qualification.semantic_session`'s own docstring for the full three-way
state). A mechanically-confirmed pre-send refusal
(``CONFIRMED_NOT_SENT``) keeps ``semantic_prompts_sent`` at ``0`` and is a
pre-prompt infrastructure refusal. Neither a raised adapter exception, a
malformed/mismatched adapter result, nor an adapter-reported
``SEND_STATE_INDETERMINATE`` is EVER treated as proof of either state --
each becomes ``SEND_STATE_INDETERMINATE``, for which
``semantic_prompts_sent`` is ``None`` (never coerced to 0 or 1), no primary
qualification record is built (the frozen ``qualification.records``/
``qualification.i2_cleanup`` schemas have no slot for an unestablished send
fact, and this module invents none for them), the candidate is never scored,
and there is never a retry -- see :class:`SemanticTaskAttemptResult` and
:func:`run_semantic_task_attempt`'s ``SEMANTIC_PROMPT_DISPATCH`` section for
the exact mechanics. Once ``CONFIRMED_SENT`` is established,
``semantic_prompts_sent`` stays ``1`` for the remainder of this attempt,
permanently, regardless of what happens next.

Truthful claim scope
---------------------

Identical to :mod:`qualification.i2b_controller`: teardown truthfulness is
bounded to AIDO's own direct child and the broker's own lifecycle state.
Nothing here claims a descendant process was terminated, that Pi/provider
inference stopped, or that GPU work stopped. Controlled invocation is not
sandboxed execution -- the launched runtime and the verification subprocess
are both repository-controlled code, not confined.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import Enum
from typing import Any, Callable, Mapping, Sequence

from ar2.observation import (
    NO_CHANGE_OBSERVED,
    UNEXPECTED_CHANGE,
    UNEXPECTED_UNTRACKED,
    classify as observe_and_classify,
    observe_repository,
)
from ar2.verification import VerificationOutcome, run_verification

from .corpus import QualificationTask
from .fixtures import BaselineCheck, validate_baseline
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
from .i2b_controller import (
    CategoryBFailureCode,
    CompatibilityFacts,
    ResourceClosureState,
    RuntimeTeardownStatus,
    BrokerShutdownStatus,
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
    mint_qualification_run_workspace,
)
from .outcomes import AutonomousClassification, DiagnosticSubclassification, OutcomeClassification, RunFacts, classify_outcome
from .records import CANDIDATE_MODEL_IDS, build_qualification_record, emit_or_refuse
from .report_accuracy import ClaimComparison, ObservedFacts, ReportClaims, bucket_report_accuracy, compare_report
from .safety import ArtifactSafetyContext, qualification_scrub_check
from .scope import RefusalEvent, ScopeResult, attribute_protocol_anomaly, build_scope_result, has_hard_disqualifier
from .semantic_session import (
    BrokerActivityObservation,
    FinalReportClaimsObservation,
    SemanticPromptDispatchState,
    SemanticPromptRequest,
    SemanticTurnObservation,
    require_dispatch_matches_request,
)
from .semantic_workspace import SemanticTaskWorkspace, SemanticWorkspaceError, populate_semantic_task_workspace
from .validity import RunValidity, ValidityResult, resolve_run_validity

#: This attempt sends at most one semantic prompt, ever. No name in this
#: module is ever bound to any other value for the attempted count.
MAX_SEMANTIC_PROMPTS_PER_ATTEMPT: int = 1

_STATUS_NOT_REACHED = "NOT_REACHED"
_STATUS_PASSED = "PASSED"
_STATUS_NOT_REQUIRED = "NOT_REQUIRED"


class SemanticGateName(str, Enum):
    """Every stage this controller gates, in exactly its evaluation order."""

    RUN_CORRELATION = "run_correlation"
    WORKSPACE_AUTHORITY = "workspace_authority"
    WORKSPACE_BASELINE = "workspace_baseline"
    ROUTE_DESCRIPTOR = "route_descriptor"
    NON_SECRET_PREFLIGHT = "non_secret_preflight"
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
    # -- post-prompt --
    SEMANTIC_PROMPT_DISPATCH = "semantic_prompt_dispatch"
    TURN_COMPLETION = "turn_completion"
    BROKER_ACTIVITY = "broker_activity"
    REPOSITORY_OBSERVATION = "repository_observation"
    AUTHORITATIVE_VERIFICATION = "authoritative_verification"
    FINAL_REPORT_CLAIMS = "final_report_claims"
    # -- lifecycle closure --
    RUNTIME_TEARDOWN = "runtime_teardown"
    BROKER_SHUTDOWN = "broker_shutdown"
    GENERATED_CONFIG_CLEANUP = "generated_config_cleanup"
    EVIDENCE_SAFETY = "evidence_safety"


#: The gates that establish the SAME 13 compatibility facts Category-B
#: establishes (plus the new, non-secret WORKSPACE_BASELINE gate, which is a
#: fixture-integrity check, never counted among the 13). Every one must be
#: ``PASSED`` before the one semantic prompt may be dispatched.
PRE_PROMPT_GATES: tuple[SemanticGateName, ...] = (
    SemanticGateName.RUN_CORRELATION,
    SemanticGateName.WORKSPACE_AUTHORITY,
    SemanticGateName.WORKSPACE_BASELINE,
    SemanticGateName.ROUTE_DESCRIPTOR,
    SemanticGateName.NON_SECRET_PREFLIGHT,
    SemanticGateName.CONNECTION_VALUES,
    SemanticGateName.SECRET_CONTEXT,
    SemanticGateName.PI_CONFIG_GENERATION,
    SemanticGateName.IDENTITY_BINDING,
    SemanticGateName.CHILD_ENVIRONMENT,
    SemanticGateName.BROKER_SESSION,
    SemanticGateName.BROKER_READY,
    SemanticGateName.RUNTIME_LAUNCH,
    SemanticGateName.PI_VERSION_OBSERVED,
    SemanticGateName.RPC_LAUNCH_SHAPE,
    SemanticGateName.REQUIRED_LAUNCH_FLAGS,
    SemanticGateName.LF_JSONL_CORRELATION,
    SemanticGateName.GET_COMMANDS,
    SemanticGateName.H1_EXTENSION_IDENTITY,
    SemanticGateName.EXTENSION_COMMAND_NAMESPACE,
    SemanticGateName.GET_STATE,
    SemanticGateName.H2_PROVIDER_MODEL_IDENTITY,
    SemanticGateName.PROTOCOL_INTEGRITY,
    SemanticGateName.ROUTE_CHECK,
)

POST_PROMPT_GATES: tuple[SemanticGateName, ...] = (
    SemanticGateName.SEMANTIC_PROMPT_DISPATCH,
    SemanticGateName.TURN_COMPLETION,
    SemanticGateName.BROKER_ACTIVITY,
    SemanticGateName.REPOSITORY_OBSERVATION,
    SemanticGateName.AUTHORITATIVE_VERIFICATION,
    SemanticGateName.FINAL_REPORT_CLAIMS,
)

CLOSURE_GATES: tuple[SemanticGateName, ...] = (
    SemanticGateName.RUNTIME_TEARDOWN,
    SemanticGateName.BROKER_SHUTDOWN,
    SemanticGateName.GENERATED_CONFIG_CLEANUP,
    SemanticGateName.EVIDENCE_SAFETY,
)

#: The one gate at which a credential value is read. Load-bearing: a
#: source-level test asserts CONNECTION_VALUES' position in ``PRE_PROMPT_GATES``
#: is strictly greater than RUN_CORRELATION/WORKSPACE_AUTHORITY/
#: WORKSPACE_BASELINE/ROUTE_DESCRIPTOR/NON_SECRET_PREFLIGHT.
CREDENTIAL_READ_GATE: SemanticGateName = SemanticGateName.CONNECTION_VALUES


class SemanticFailureCode(str, Enum):
    """Bounded failure codes for the gates :mod:`qualification.i2b_controller`
    has no equivalent of. Never free-form prose. Every gate this module
    shares with Category-B reuses :class:`~qualification.i2b_controller.CategoryBFailureCode`
    directly rather than redeclaring its ~40 existing members.
    """

    WORKSPACE_POPULATION_FAILED = "WORKSPACE_POPULATION_FAILED"
    WORKSPACE_BASELINE_INVALID = "WORKSPACE_BASELINE_INVALID"
    SEMANTIC_PROMPT_DISPATCH_FAILED = "SEMANTIC_PROMPT_DISPATCH_FAILED"
    #: A returned, well-typed dispatch observation mechanically established
    #: CONFIRMED_NOT_SENT (5F3B-Q1-PRE1-FU1). A pre-prompt refusal --
    #: `semantic_prompts_sent` stays 0.
    SEMANTIC_PROMPT_CONFIRMED_NOT_SENT = "SEMANTIC_PROMPT_CONFIRMED_NOT_SENT"
    #: Dispatch was attempted but AIDO cannot mechanically establish whether
    #: it was sent (5F3B-Q1-PRE1-FU1). Never `semantic_prompts_sent` 0 or 1.
    SEMANTIC_PROMPT_SEND_STATE_INDETERMINATE = "SEMANTIC_PROMPT_SEND_STATE_INDETERMINATE"
    TURN_DID_NOT_TERMINATE = "TURN_DID_NOT_TERMINATE"
    BROKER_ACTIVITY_COLLECTION_FAILED = "BROKER_ACTIVITY_COLLECTION_FAILED"
    REPOSITORY_OBSERVATION_FAILED = "REPOSITORY_OBSERVATION_FAILED"
    VERIFICATION_EXECUTION_FAILED = "VERIFICATION_EXECUTION_FAILED"
    FINAL_REPORT_CLAIMS_COLLECTION_FAILED = "FINAL_REPORT_CLAIMS_COLLECTION_FAILED"
    MALFORMED_ADAPTER_RESULT = "MALFORMED_ADAPTER_RESULT"
    ADAPTER_RAISED = "ADAPTER_RAISED"
    #: A cleanup-verification failure occurred while this run's dispatch
    #: send-state was SEND_STATE_INDETERMINATE (5F3B-Q1-PRE1-FU1). The frozen
    #: `i2_cleanup.classify_cleanup_failure` has no shape for an
    #: unestablished `semantic_prompts_sent` and is never called for this
    #: case -- see `SemanticCleanupStatus`.
    GENERATED_CONFIG_CLEANUP_UNVERIFIED_INDETERMINATE_DISPATCH = (
        "GENERATED_CONFIG_CLEANUP_UNVERIFIED_INDETERMINATE_DISPATCH"
    )


#: Either failure-code family may appear in a result. Both are exact-value
#: ``str`` enums; a gate-status text is always ``FAILED:<member.value>`` for
#: exactly one of them, never a hand-built string.
FailureCode = CategoryBFailureCode | SemanticFailureCode


class SemanticControllerInputError(ValueError):
    """An AIDO-supplied controller argument is unusable. Refused before ANYTHING.

    These are AIDO's OWN arguments (``candidate``, ``task``, ``node_executable``,
    the workspace inputs), never adapter or observation data. Refusing here
    happens before the run correlation id is minted and therefore long before
    any connection value could be read.
    """


class SemanticSafetyContextError(Exception):
    """The run's full artifact safety context could not be PROVEN complete."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"semantic controller safety context refused: {reason_code}")
        self.reason_code = reason_code


def _require_category_a_cleanup_failure_shape(
    classification: CleanupFailureClassification, *, semantic_prompts_sent: int
) -> None:
    """The semantic-run analogue of ``i2b_controller._require_category_b_cleanup_failure_shape``.

    Compares against a FRESH call to the same frozen, reused
    ``classify_cleanup_failure`` -- parameterized by THIS run's actual
    ``semantic_prompts_sent`` rather than Category-B's hard-coded ``0`` --
    so this check can never itself drift from what that function returns.
    """
    reference = classify_cleanup_failure(semantic_prompts_sent=semantic_prompts_sent)
    if (
        type(classification.semantic_prompts_sent) is not int
        or classification.semantic_prompts_sent != reference.semantic_prompts_sent
    ):
        raise ValueError(
            "SemanticCleanupStatus.classification.semantic_prompts_sent must equal "
            f"this run's own semantic_prompts_sent ({semantic_prompts_sent!r})"
        )
    if classification.autonomous_classification is not reference.autonomous_classification:
        raise ValueError(
            "SemanticCleanupStatus.classification.autonomous_classification must "
            "equal classify_cleanup_failure(...)'s own value for this run's "
            "semantic_prompts_sent"
        )
    if classification.run_validity is not reference.run_validity:
        raise ValueError(
            "SemanticCleanupStatus.classification.run_validity must equal "
            "classify_cleanup_failure(...)'s own value for this run's "
            "semantic_prompts_sent"
        )
    require_exact_bool(
        "SemanticCleanupStatus.classification.scoring_eligible", classification.scoring_eligible
    )
    if classification.scoring_eligible != reference.scoring_eligible:
        raise ValueError(
            "SemanticCleanupStatus.classification.scoring_eligible must equal "
            "classify_cleanup_failure(...)'s own value for this run's "
            "semantic_prompts_sent"
        )


@dataclass(frozen=True)
class SemanticCleanupStatus:
    """Whether generated-config cleanup was attempted, and its phase-aware result.

    The semantic-run analogue of
    :class:`qualification.i2b_controller.CleanupStatus`, parameterized by
    this run's ACTUAL ``semantic_prompts_sent`` (0 for a pre-prompt refusal,
    1 for any run that dispatched its one prompt, ``None`` for a run whose
    dispatch send-state was mechanically ``SEND_STATE_INDETERMINATE`` --
    5F3B-Q1-PRE1-FU1) rather than Category-B's structural ``0``. See the
    module docstring's "one genuinely new frozen incompatibility" note for
    why ``CleanupStatus`` itself cannot be reused here.

    **The ``None`` (indeterminate-dispatch) case never calls the frozen
    ``i2_cleanup.classify_cleanup_failure``.** That function's own contract
    (I2A Sec. 16/18) only has a shape for ``semantic_prompts_sent in (0, 1)``
    -- calling it with an unestablished fact would force a lie (that dispatch
    was confirmed 0 or 1) into a frozen classifier this phase must not
    silently extend or weaken. A cleanup failure under an indeterminate
    dispatch therefore carries ``classification = None`` -- an honest gap,
    not a forced/repaired classification.
    """

    attempted: bool
    scrub_verified: bool | None
    classification: CleanupFailureClassification | None
    semantic_prompts_sent: int | None

    def __post_init__(self) -> None:
        require_exact_bool("SemanticCleanupStatus.attempted", self.attempted)
        if self.semantic_prompts_sent is not None and (
            type(self.semantic_prompts_sent) is not int
            or self.semantic_prompts_sent not in (0, 1)
        ):
            raise ValueError(
                "SemanticCleanupStatus.semantic_prompts_sent must be 0, 1, or None "
                "(an indeterminate dispatch send-state)"
            )
        if not self.attempted:
            if self.scrub_verified is not None or self.classification is not None:
                raise ValueError("SemanticCleanupStatus: attempted=False must carry no other field")
            return
        if self.scrub_verified is None:
            raise ValueError("SemanticCleanupStatus: attempted=True requires scrub_verified")
        require_exact_bool("SemanticCleanupStatus.scrub_verified", self.scrub_verified)
        if self.scrub_verified and self.classification is not None:
            raise ValueError(
                "SemanticCleanupStatus: a verified cleanup must not carry a classification"
            )
        if not self.scrub_verified:
            if self.semantic_prompts_sent is None:
                if self.classification is not None:
                    raise ValueError(
                        "SemanticCleanupStatus: an indeterminate-dispatch cleanup "
                        "failure must carry classification = None -- "
                        "classify_cleanup_failure has no shape for an unestablished "
                        "semantic_prompts_sent fact and is never forced to produce one"
                    )
            elif self.classification is None:
                raise ValueError(
                    "SemanticCleanupStatus: a failed/unverified cleanup requires a "
                    "classification"
                )
        if self.classification is not None:
            if type(self.classification) is not CleanupFailureClassification:
                raise ValueError(
                    "SemanticCleanupStatus.classification must be None or exactly a "
                    "CleanupFailureClassification"
                )
            _require_category_a_cleanup_failure_shape(
                self.classification, semantic_prompts_sent=self.semantic_prompts_sent
            )

    @property
    def closure_satisfied(self) -> bool:
        if not self.attempted:
            return True
        return self.scrub_verified

    @property
    def status_text(self) -> str:
        if not self.attempted:
            return _STATUS_NOT_REQUIRED
        if self.scrub_verified:
            return "VERIFIED_REMOVED"
        if self.semantic_prompts_sent is None:
            return (
                "FAILED:"
                f"{SemanticFailureCode.GENERATED_CONFIG_CLEANUP_UNVERIFIED_INDETERMINATE_DISPATCH.value}"
            )
        return f"FAILED:{CategoryBFailureCode.GENERATED_CONFIG_CLEANUP_UNVERIFIED.value}"


def _mint_run_correlation_id() -> str:
    import secrets

    try:
        return "sem-" + secrets.token_hex(16)
    except Exception as exc:  # pragma: no cover - stdlib secrets essentially never fails
        raise ObservationError("RUN_CORRELATION_UNAVAILABLE") from exc


def _close_runtime(
    shutdown_runtime: Callable[[RuntimeSession], RuntimeShutdownObservation],
    session: RuntimeSession | None,
    *,
    run_id: str,
) -> RuntimeTeardownStatus:
    """Close AIDO's own runtime session, if one was ever handed over.

    Mirrors :mod:`qualification.i2b_controller`'s own closure discipline:
    ``NOT_REQUIRED`` for nothing to close; the shutdown adapter is NEVER
    CALLED for a session this run cannot prove is its own
    (``SHUTDOWN_REFUSED_FOREIGN_SESSION`` -- possession is not authority);
    an adapter that raises, returns the wrong type, or returns a mismatched
    session id is ``SHUTDOWN_FAILED``; only a genuinely-returned, matching,
    ``True`` postcondition is ``CLOSED_BY_ORCHESTRATOR``.
    """
    if session is None:
        return RuntimeTeardownStatus(state=ResourceClosureState.NOT_REQUIRED)
    if session.run_id != run_id:
        return RuntimeTeardownStatus(
            state=ResourceClosureState.SHUTDOWN_REFUSED_FOREIGN_SESSION,
            failure_code=CategoryBFailureCode.RUNTIME_SHUTDOWN_REFUSED_FOREIGN_SESSION,
        )
    try:
        observation = shutdown_runtime(session)
    except Exception:
        return RuntimeTeardownStatus(
            state=ResourceClosureState.SHUTDOWN_FAILED,
            failure_code=CategoryBFailureCode.RUNTIME_TEARDOWN_FAILED,
        )
    if type(observation) is not RuntimeShutdownObservation:
        return RuntimeTeardownStatus(
            state=ResourceClosureState.SHUTDOWN_FAILED,
            failure_code=CategoryBFailureCode.RUNTIME_TEARDOWN_FAILED,
        )
    if observation.runtime_session_id != session.runtime_session_id:
        return RuntimeTeardownStatus(
            state=ResourceClosureState.SHUTDOWN_FAILED,
            failure_code=CategoryBFailureCode.RUNTIME_SESSION_MISMATCH,
        )
    if (
        observation.shutdown_call_returned
        and observation.orchestrator_direct_child_reported_exit
    ):
        return RuntimeTeardownStatus(state=ResourceClosureState.CLOSED_BY_ORCHESTRATOR)
    return RuntimeTeardownStatus(
        state=ResourceClosureState.SHUTDOWN_FAILED,
        failure_code=CategoryBFailureCode.RUNTIME_TEARDOWN_FAILED,
    )


def _close_broker(
    shutdown_broker: Callable[[BrokerSession], BrokerShutdownObservation],
    session: BrokerSession | None,
    *,
    run_id: str,
) -> BrokerShutdownStatus:
    """Close AIDO's own broker session, if one was ever created. See ``_close_runtime``."""
    if session is None:
        return BrokerShutdownStatus(state=ResourceClosureState.NOT_REQUIRED)
    if session.run_id != run_id:
        return BrokerShutdownStatus(
            state=ResourceClosureState.SHUTDOWN_REFUSED_FOREIGN_SESSION,
            failure_code=CategoryBFailureCode.BROKER_SHUTDOWN_REFUSED_FOREIGN_SESSION,
        )
    try:
        observation = shutdown_broker(session)
    except Exception:
        return BrokerShutdownStatus(
            state=ResourceClosureState.SHUTDOWN_FAILED,
            failure_code=CategoryBFailureCode.BROKER_SHUTDOWN_INCOMPLETE,
        )
    if type(observation) is not BrokerShutdownObservation:
        return BrokerShutdownStatus(
            state=ResourceClosureState.SHUTDOWN_FAILED,
            failure_code=CategoryBFailureCode.BROKER_SHUTDOWN_INCOMPLETE,
        )
    if observation.session_id != session.session_id:
        return BrokerShutdownStatus(
            state=ResourceClosureState.SHUTDOWN_FAILED,
            failure_code=CategoryBFailureCode.BROKER_SESSION_MISMATCH,
        )
    if observation.reached_closed:
        return BrokerShutdownStatus(state=ResourceClosureState.CLOSED_BY_ORCHESTRATOR)
    return BrokerShutdownStatus(
        state=ResourceClosureState.SHUTDOWN_FAILED,
        failure_code=CategoryBFailureCode.BROKER_SHUTDOWN_INCOMPLETE,
    )


def _cleanup_classification_for(
    semantic_prompts_sent: int | None,
) -> CleanupFailureClassification | None:
    """The frozen classifier's result, or ``None`` when this run's dispatch
    send-state is unestablished (5F3B-Q1-PRE1-FU1) -- ``classify_cleanup_failure``
    is NEVER called with anything but a genuinely-known 0/1, so it can never
    be forced to lie about an indeterminate fact.
    """
    if semantic_prompts_sent is None:
        return None
    return classify_cleanup_failure(semantic_prompts_sent=semantic_prompts_sent)


def _attempt_cleanup(
    generated_config: GeneratedQualificationConfig | None, *, semantic_prompts_sent: int | None
) -> SemanticCleanupStatus:
    if generated_config is None:
        return SemanticCleanupStatus(
            attempted=False,
            scrub_verified=None,
            classification=None,
            semantic_prompts_sent=semantic_prompts_sent,
        )
    try:
        result = scrub_generated_qualification_config(generated_config)
    except (QualificationPiConfigCleanupError, CleanupAuthorityError):
        return SemanticCleanupStatus(
            attempted=True,
            scrub_verified=False,
            classification=_cleanup_classification_for(semantic_prompts_sent),
            semantic_prompts_sent=semantic_prompts_sent,
        )
    if result.scrub_verified:
        return SemanticCleanupStatus(
            attempted=True,
            scrub_verified=True,
            classification=None,
            semantic_prompts_sent=semantic_prompts_sent,
        )
    return SemanticCleanupStatus(
        attempted=True,
        scrub_verified=False,
        classification=_cleanup_classification_for(semantic_prompts_sent),
        semantic_prompts_sent=semantic_prompts_sent,
    )


def build_run_safety_context(
    *,
    secret_context: QualificationRouteSecretContext | None,
    broker_session: BrokerSession | None,
    run_workspace: QualificationRunWorkspace | None,
    route_descriptor: RouteDescriptor | None,
) -> ArtifactSafetyContext:
    """Build the run's FULL artifact safety context from whatever it actually has.

    Mirrors ``qualification.i2b_controller.build_run_safety_context`` exactly:
    a run that failed before some value existed still declares whatever it
    does have, rather than falling back to an empty context. ``bearer_token``
    is always ``None`` as a DERIVED absence -- this route's credential
    mechanism (``models_json_env_interpolation``) mints no separate bearer
    value.
    """
    if secret_context is None:
        return ArtifactSafetyContext.none_declared()
    return secret_context.to_safety_context(
        broker_token=broker_session.broker_token if broker_session is not None else None,
        pipe_name=broker_session.pipe_name if broker_session is not None else None,
        capability_id=broker_session.capability_id if broker_session is not None else None,
        workspace_absolute_path=(
            run_workspace.experiment_root if run_workspace is not None else None
        ),
    )


def _project_verification(outcome: VerificationOutcome | None) -> dict[str, Any]:
    """A bounded projection of ``VerificationOutcome``. Never raw output text.

    ``output_text``/``failed_node_ids`` node text can carry arbitrary
    subprocess output; only the fixed, bounded ``counts`` summary and the
    pass/fail/return-code facts are retained here, matching the discipline
    ``i2_cleanup.prepare_diagnostic_text_for_retention`` already applies to
    any OTHER raw diagnostic text in this package.
    """
    if outcome is None:
        return {"attempted": False}
    return {
        "attempted": True,
        "started": outcome.started,
        "completed": outcome.completed,
        "timed_out": outcome.timed_out,
        "passed": outcome.passed,
        "return_code": outcome.return_code,
        "counts": dict(outcome.counts),
        "orchestrator_direct_child_killed": outcome.direct_child_killed,
    }


def _project_scope_result(scope_result: ScopeResult | None) -> dict[str, Any]:
    if scope_result is None:
        return {"attempted": False}
    return {
        "attempted": True,
        "expected_changed_paths": sorted(scope_result.expected_changed_paths),
        "observed_changed_paths": sorted(scope_result.observed_changed_paths),
        "unexpected_changed_paths": sorted(scope_result.unexpected_changed_paths),
        "missing_expected_changed_paths": sorted(scope_result.missing_expected_changed_paths),
        "protected_write_attempts": scope_result.protected_write_attempts,
        "third_file_attempts": scope_result.third_file_attempts,
        "hard_refusal_count": scope_result.hard_refusal_count,
        "soft_refusal_count": scope_result.soft_refusal_count,
        "refusal_categories": list(scope_result.refusal_categories),
    }


def _project_report_accuracy(comparisons: tuple[ClaimComparison, ...]) -> dict[str, Any]:
    if not comparisons:
        return {"attempted": False}
    bucket = bucket_report_accuracy(comparisons)
    return {
        "attempted": True,
        "bucket": bucket.value,
        "comparisons": [
            {"claim": c.claim, "verdict": c.verdict.value, "detail": c.detail}
            for c in comparisons
        ],
    }


class _GateFailure(Exception):
    """Internal control-flow signal only. Never escapes :func:`run_semantic_task_attempt`."""

    def __init__(self, gate: SemanticGateName, code: FailureCode) -> None:
        super().__init__(f"{gate.value}: {code.value}")
        self.gate = gate
        self.code = code


class _DispatchIndeterminate(Exception):
    """Internal control-flow signal only (5F3B-Q1-PRE1-FU1). Never a
    ``_GateFailure`` -- there is no established failure code, because there
    is no established fact of either FAILURE or SUCCESS to attribute. Caught
    SEPARATELY from ``_GateFailure``/the generic exception handler in
    :func:`run_semantic_task_attempt`, so it can never be folded into
    ``infrastructure_refusal`` (which would falsely claim CONFIRMED_NOT_SENT)
    or a genuine post-prompt contamination (which would falsely claim
    CONFIRMED_SENT). Never escapes that function.
    """


def _invoke(
    gate: SemanticGateName,
    fn: Callable[[], Any],
    *,
    expected_type: type,
    raised_code: FailureCode,
    malformed_code: FailureCode,
) -> Any:
    """Call one injected adapter; reduce every failure mode to one bounded gate failure.

    Distinguishes an adapter that RAISED from one that returned the wrong
    type -- the same distinction ``qualification.i2b_controller``'s own
    (private) ``_invoke`` makes -- so a malformed adapter result can never be
    silently treated as a pass, and no adapter exception text is ever
    retained.
    """
    try:
        result = fn()
    except Exception:
        raise _GateFailure(gate, raised_code) from None
    if type(result) is not expected_type:
        raise _GateFailure(gate, malformed_code)
    return result


@dataclass(frozen=True)
class SemanticTaskAttemptResult:
    """The controller's one, complete, truthful result for ONE task attempt.

    This is a diagnostic/audit projection of what happened; it is NOT the
    retained evidence artifact (that is ``qualification_record``, built and
    emitted through the SAME ``qualification.records`` /
    ``qualification.safety`` choke point every other primary record in this
    package uses) and it is deliberately less exhaustively invariant-checked
    than ``qualification.i2b_controller.CategoryBControllerResult`` -- see
    this module's own docstring for the honest scope statement. The fields
    that matter for hard-bar/ranking purposes are exactly the ones
    ``qualification.records.build_qualification_record`` re-validates from
    scratch when the record is built, so an internally inconsistent result
    here cannot silently become a valid emitted record.
    """

    candidate: str
    model_id: str
    task_id: str
    task_revision: str
    #: ``None`` iff ``dispatch_state`` is ``SEND_STATE_INDETERMINATE``
    #: (5F3B-Q1-PRE1-FU1) -- never coerced to 0 or 1 for an unestablished fact.
    semantic_prompts_sent: int | None
    #: The mechanically-established send/no-send fact for this attempt's ONE
    #: dispatch (5F3B-Q1-PRE1-FU1). ``CONFIRMED_NOT_SENT`` by default for any
    #: attempt that never reached the dispatch gate at all -- structurally
    #: the strongest form of "not sent" (never even attempted).
    dispatch_state: SemanticPromptDispatchState
    infrastructure_refusal: bool
    gate_statuses: Mapping[str, str]
    failed_gate: SemanticGateName | None
    failure_code: FailureCode | None
    facts: CompatibilityFacts
    observed_pi_version: str | None
    run_validity: RunValidity | None
    scoring_eligible: bool
    autonomous_classification: AutonomousClassification | None
    diagnostic_subclassification: DiagnosticSubclassification | None
    scope_result: ScopeResult | None
    report_accuracy_comparisons: tuple[ClaimComparison, ...]
    verification_passed: bool | None
    expected_changed_paths_satisfied: bool | None
    head_unchanged: bool | None
    index_clean: bool | None
    protected_witness_untouched: bool | None
    no_unexpected_untracked_or_create_delete_rename: bool | None
    broker_git_cross_check_agrees: bool | None
    runtime_teardown: RuntimeTeardownStatus
    broker_shutdown: BrokerShutdownStatus
    cleanup: SemanticCleanupStatus
    qualification_record: dict[str, Any] | None

    def __post_init__(self) -> None:
        if type(self.dispatch_state) is not SemanticPromptDispatchState:
            raise ValueError(
                "SemanticTaskAttemptResult.dispatch_state must be exactly a "
                "SemanticPromptDispatchState"
            )
        indeterminate = self.dispatch_state is SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
        if indeterminate:
            if self.semantic_prompts_sent is not None:
                raise ValueError(
                    "SemanticTaskAttemptResult: SEND_STATE_INDETERMINATE requires "
                    "semantic_prompts_sent = None -- it is never coerced to 0 or 1"
                )
        else:
            if type(self.semantic_prompts_sent) is not int or self.semantic_prompts_sent not in (
                0,
                1,
            ):
                raise ValueError(
                    "SemanticTaskAttemptResult.semantic_prompts_sent must be 0 or 1 "
                    "unless dispatch_state is SEND_STATE_INDETERMINATE"
                )
            expected_sent = (
                1 if self.dispatch_state is SemanticPromptDispatchState.CONFIRMED_SENT else 0
            )
            if self.semantic_prompts_sent != expected_sent:
                raise ValueError(
                    "SemanticTaskAttemptResult.semantic_prompts_sent disagrees with its "
                    "own dispatch_state"
                )
        require_exact_bool(
            "SemanticTaskAttemptResult.infrastructure_refusal", self.infrastructure_refusal
        )
        if self.infrastructure_refusal and self.semantic_prompts_sent != 0:
            raise ValueError(
                "SemanticTaskAttemptResult: infrastructure_refusal requires "
                "semantic_prompts_sent == 0"
            )
        if indeterminate:
            if self.infrastructure_refusal:
                raise ValueError(
                    "SemanticTaskAttemptResult: SEND_STATE_INDETERMINATE is never an "
                    "infrastructure_refusal -- that would falsely claim "
                    "CONFIRMED_NOT_SENT for a fact this run could not mechanically "
                    "establish"
                )
            if (
                self.run_validity is not None
                or self.scoring_eligible
                or self.autonomous_classification is not None
                or self.qualification_record is not None
            ):
                raise ValueError(
                    "SemanticTaskAttemptResult: SEND_STATE_INDETERMINATE must carry no "
                    "run_validity, must not be scoring_eligible, must carry no "
                    "autonomous_classification, and must emit no qualification_record"
                )
        if type(self.facts) is not CompatibilityFacts:
            raise ValueError("SemanticTaskAttemptResult.facts must be a CompatibilityFacts")
        if type(self.runtime_teardown) is not RuntimeTeardownStatus:
            raise ValueError(
                "SemanticTaskAttemptResult.runtime_teardown must be a RuntimeTeardownStatus"
            )
        if type(self.broker_shutdown) is not BrokerShutdownStatus:
            raise ValueError(
                "SemanticTaskAttemptResult.broker_shutdown must be a BrokerShutdownStatus"
            )
        if type(self.cleanup) is not SemanticCleanupStatus:
            raise ValueError(
                "SemanticTaskAttemptResult.cleanup must be a SemanticCleanupStatus"
            )
        if self.cleanup.semantic_prompts_sent != self.semantic_prompts_sent:
            raise ValueError(
                "SemanticTaskAttemptResult.cleanup.semantic_prompts_sent disagrees "
                "with this result's own semantic_prompts_sent"
            )


def run_semantic_task_attempt(
    *,
    candidate: str,
    task: QualificationTask,
    ambient_environ: Mapping[str, str],
    node_executable: str,
    git_executable: str,
    python_executable: str,
    non_secret_gates: Sequence[Callable[[], PreflightGateResult]],
    read_connection: Callable[[], ConnectionValues],
    create_broker: Callable[[BrokerCreationRequest], BrokerCreationObservation],
    launch_runtime: Callable[[RuntimeLaunchRequest], RuntimeLaunchObservation],
    get_commands: Callable[[RuntimeSession], GetCommandsObservation],
    get_state: Callable[[RuntimeSession], GetStateObservation],
    observe_protocol: Callable[[RuntimeSession], ProtocolObservation],
    route_checker: Callable[..., Any],
    send_semantic_prompt: Callable[[SemanticPromptRequest], SemanticTurnObservation],
    collect_broker_activity: Callable[[RuntimeSession], BrokerActivityObservation],
    collect_final_report_claims: Callable[[RuntimeSession], FinalReportClaimsObservation],
    shutdown_runtime: Callable[[RuntimeSession], RuntimeShutdownObservation],
    shutdown_broker: Callable[[BrokerSession], BrokerShutdownObservation],
    evidence_path: str,
) -> SemanticTaskAttemptResult:
    """Drive ONE candidate's ONE task attempt: compatibility, then the ONE
    semantic prompt, then post-turn observation, then closure. OFFLINE
    WIRING ONLY -- every live dependency above is REQUIRED and INJECTED.

    **Fresh everything, every call.** This function mints its own run
    correlation id and its own :class:`~qualification.i2b_workspace.QualificationRunWorkspace`
    (via the unmodified, no-argument ``mint_qualification_run_workspace()``)
    on every invocation -- there is no parameter through which a caller could
    supply, reuse, or substitute a workspace, a broker session, or a runtime
    session from a different call. Two calls to this function share no
    state whatsoever, satisfying the design's "fresh Pi/runtime, fresh
    broker/session/capability, no state carried from another task" rule by
    construction, not by caller discipline.
    """
    if candidate not in CANDIDATE_MODEL_IDS:
        raise SemanticControllerInputError(
            f"unknown candidate {candidate!r}; declared: {sorted(CANDIDATE_MODEL_IDS)}"
        )
    from .corpus import TASKS_BY_ID

    if TASKS_BY_ID.get(task.task_id) is not task:
        raise SemanticControllerInputError(
            "task must be exactly one of the frozen qualification.corpus tasks; a "
            "caller-constructed or substituted QualificationTask is refused"
        )
    for name, value in (
        ("node_executable", node_executable),
        ("git_executable", git_executable),
        ("python_executable", python_executable),
        ("evidence_path", evidence_path),
    ):
        if not isinstance(value, str) or not value.strip():
            raise SemanticControllerInputError(f"{name} must be a non-blank str")

    model_id = CANDIDATE_MODEL_IDS[candidate]

    gate_statuses: dict[str, str] = {
        gate.value: _STATUS_NOT_REACHED
        for gate in (*PRE_PROMPT_GATES, *POST_PROMPT_GATES, *CLOSURE_GATES)
    }

    def _pass(gate: SemanticGateName) -> None:
        gate_statuses[gate.value] = _STATUS_PASSED

    def _fail_status(gate: SemanticGateName, code: FailureCode) -> None:
        gate_statuses[gate.value] = f"FAILED:{code.value}"

    run_id: str | None = None
    run_workspace: QualificationRunWorkspace | None = None
    task_workspace: SemanticTaskWorkspace | None = None
    route_descriptor: RouteDescriptor | None = None
    connection: ConnectionValues | None = None
    secret_context: QualificationRouteSecretContext | None = None
    generated_config: GeneratedQualificationConfig | None = None
    broker_session: BrokerSession | None = None
    runtime_session: RuntimeSession | None = None
    facts_kwargs: dict[str, bool] = {f.name: False for f in fields(CompatibilityFacts)}
    observed_pi_version: str | None = None
    semantic_prompts_sent: int | None = 0
    #: CONFIRMED_NOT_SENT by default: structurally, any attempt that never
    #: reaches the SEMANTIC_PROMPT_DISPATCH gate has mechanically never sent
    #: the command (5F3B-Q1-PRE1-FU1).
    dispatch_state: SemanticPromptDispatchState = SemanticPromptDispatchState.CONFIRMED_NOT_SENT
    dispatch_indeterminate = False
    turn_observation: SemanticTurnObservation | None = None
    broker_activity: BrokerActivityObservation | None = None
    classification = None
    verification_outcome: VerificationOutcome | None = None
    report_claims: ReportClaims | None = None
    failed_gate: SemanticGateName | None = None
    failure_code: FailureCode | None = None
    infrastructure_refusal = False
    # Tracks which gate is executing so an exception this function did not
    # anticipate (one not raised as a _GateFailure) can still be attributed
    # to the right stage and, more importantly, still let CLOSURE run --
    # see the `except Exception` fallback below.
    _current_gate: SemanticGateName = SemanticGateName.RUN_CORRELATION

    try:
        # -- RUN_CORRELATION --
        _current_gate = SemanticGateName.RUN_CORRELATION
        run_id = _mint_run_correlation_id()
        _pass(SemanticGateName.RUN_CORRELATION)

        # -- WORKSPACE_AUTHORITY (mint + populate) --
        _current_gate = SemanticGateName.WORKSPACE_AUTHORITY
        try:
            run_workspace = mint_qualification_run_workspace()
            claim_run_workspace(run_workspace, run_id=run_id)
            task_workspace = populate_semantic_task_workspace(
                run_workspace, task, git_executable=git_executable
            )
        except (WorkspaceAuthorityError, SemanticWorkspaceError):
            raise _GateFailure(
                SemanticGateName.WORKSPACE_AUTHORITY,
                SemanticFailureCode.WORKSPACE_POPULATION_FAILED,
            ) from None
        _pass(SemanticGateName.WORKSPACE_AUTHORITY)

        # -- WORKSPACE_BASELINE (fixture-integrity check, never one of the 13) --
        _current_gate = SemanticGateName.WORKSPACE_BASELINE
        try:
            baseline_outcome = run_verification(
                python_executable=python_executable,
                workspace_root=task_workspace.repo_root,
                args=task.case.verification_args,
            )
        except Exception:
            raise _GateFailure(
                SemanticGateName.WORKSPACE_BASELINE,
                SemanticFailureCode.WORKSPACE_BASELINE_INVALID,
            ) from None
        baseline_check: BaselineCheck = validate_baseline(task, baseline_outcome)
        if not baseline_check.matches:
            raise _GateFailure(
                SemanticGateName.WORKSPACE_BASELINE,
                SemanticFailureCode.WORKSPACE_BASELINE_INVALID,
            )
        _pass(SemanticGateName.WORKSPACE_BASELINE)

        # -- ROUTE_DESCRIPTOR --
        _current_gate = SemanticGateName.ROUTE_DESCRIPTOR
        try:
            route_descriptor = route_descriptor_for_candidate(candidate)
        except RouteDescriptorError:
            raise _GateFailure(
                SemanticGateName.ROUTE_DESCRIPTOR, CategoryBFailureCode.ROUTE_DESCRIPTOR_INVALID
            ) from None
        _pass(SemanticGateName.ROUTE_DESCRIPTOR)

        # -- NON_SECRET_PREFLIGHT / CONNECTION_VALUES (credential boundary) --
        _current_gate = SemanticGateName.NON_SECRET_PREFLIGHT
        try:
            connection = resolve_connection_after_preflight(
                non_secret_gates=non_secret_gates, read_connection=read_connection
            )
        except InfrastructureRefusal as exc:
            if exc.failure_code in (
                "CONNECTION_VALUE_MISSING_OR_BLANK",
                "CONNECTION_VALUE_INVALID",
            ):
                raise _GateFailure(
                    SemanticGateName.CONNECTION_VALUES,
                    CategoryBFailureCode.CONNECTION_VALUES_UNAVAILABLE,
                ) from None
            raise _GateFailure(
                SemanticGateName.NON_SECRET_PREFLIGHT,
                CategoryBFailureCode.NON_SECRET_PREFLIGHT_GATE_FAILED,
            ) from None
        _pass(SemanticGateName.NON_SECRET_PREFLIGHT)
        _pass(SemanticGateName.CONNECTION_VALUES)

        # -- SECRET_CONTEXT --
        _current_gate = SemanticGateName.SECRET_CONTEXT
        try:
            secret_context = build_secret_context(
                base_url=connection.base_url,
                api_key=connection.api_key,
                model_id=route_descriptor.model_id,
            )
        except (SecretContextError, InvalidBaseUrlError):
            raise _GateFailure(
                SemanticGateName.SECRET_CONTEXT,
                CategoryBFailureCode.SECRET_CONTEXT_CONSTRUCTION_FAILED,
            ) from None
        _pass(SemanticGateName.SECRET_CONTEXT)

        # -- PI_CONFIG_GENERATION --
        _current_gate = SemanticGateName.PI_CONFIG_GENERATION
        try:
            generated_config = write_qualification_pi_config(
                run_workspace.experiment_root,
                model_id=route_descriptor.model_id,
                base_url=connection.base_url,
            )
        except QualificationPiConfigError:
            raise _GateFailure(
                SemanticGateName.PI_CONFIG_GENERATION,
                CategoryBFailureCode.PI_CONFIG_GENERATION_FAILED,
            ) from None
        _pass(SemanticGateName.PI_CONFIG_GENERATION)

        # -- IDENTITY_BINDING --
        _current_gate = SemanticGateName.IDENTITY_BINDING
        try:
            verify_i2_identity_binding(
                generated_config=generated_config,
                secret_context=secret_context,
                route_descriptor=route_descriptor,
            )
        except I2IdentityBindingError:
            raise _GateFailure(
                SemanticGateName.IDENTITY_BINDING, CategoryBFailureCode.IDENTITY_BINDING_MISMATCH
            ) from None
        _pass(SemanticGateName.IDENTITY_BINDING)

        # -- CHILD_ENVIRONMENT --
        _current_gate = SemanticGateName.CHILD_ENVIRONMENT
        try:
            launch_environment = build_child_environment(
                ambient_environ=ambient_environ,
                node_executable=node_executable,
                generated_config=generated_config,
                secret_context=secret_context,
                git_executable=git_executable,
            )
        except EnvironmentPolicyError:
            raise _GateFailure(
                SemanticGateName.CHILD_ENVIRONMENT,
                CategoryBFailureCode.CHILD_ENVIRONMENT_BUILD_FAILED,
            ) from None
        _pass(SemanticGateName.CHILD_ENVIRONMENT)

        # -- BROKER_SESSION / BROKER_READY --
        _current_gate = SemanticGateName.BROKER_SESSION
        broker_observation = _invoke(
            SemanticGateName.BROKER_SESSION,
            lambda: create_broker(BrokerCreationRequest(run_id=run_id, workspace=run_workspace)),
            expected_type=BrokerCreationObservation,
            raised_code=CategoryBFailureCode.ADAPTER_RAISED,
            malformed_code=CategoryBFailureCode.MALFORMED_ADAPTER_RESULT,
        )
        if broker_observation.session is None or broker_observation.session.run_id != run_id:
            raise _GateFailure(
                SemanticGateName.BROKER_SESSION, CategoryBFailureCode.BROKER_CREATION_FAILED
            )
        broker_session = broker_observation.session
        _pass(SemanticGateName.BROKER_SESSION)
        if not broker_session.reached_ready:
            raise _GateFailure(
                SemanticGateName.BROKER_READY, CategoryBFailureCode.BROKER_NOT_READY
            )
        _pass(SemanticGateName.BROKER_READY)
        facts_kwargs["broker_reached_required_ready_state"] = True

        # -- RUNTIME_LAUNCH (+ 4 independent launch facts from ONE observation) --
        _current_gate = SemanticGateName.RUNTIME_LAUNCH
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
            raise _GateFailure(
                SemanticGateName.RUNTIME_LAUNCH,
                CategoryBFailureCode.RUNTIME_LAUNCH_REQUEST_UNCONSTRUCTIBLE,
            ) from None
        launch_observation = _invoke(
            SemanticGateName.RUNTIME_LAUNCH,
            lambda: launch_runtime(launch_request),
            expected_type=RuntimeLaunchObservation,
            raised_code=CategoryBFailureCode.ADAPTER_RAISED,
            malformed_code=CategoryBFailureCode.MALFORMED_ADAPTER_RESULT,
        )
        facts_kwargs["pi_version_observed"] = launch_observation.pi_version_observed
        observed_pi_version = launch_observation.observed_pi_version
        facts_kwargs["rpc_launch_shape_valid"] = launch_observation.launch_shape_valid
        facts_kwargs["required_launch_flags_accepted"] = launch_observation.required_flags_accepted
        facts_kwargs["lf_jsonl_correlation_succeeded"] = (
            launch_observation.lf_jsonl_correlation_succeeded
        )
        if launch_observation.session is None or launch_observation.session.run_id != run_id:
            raise _GateFailure(
                SemanticGateName.RUNTIME_LAUNCH, CategoryBFailureCode.RUNTIME_LAUNCH_FAILED
            )
        if launch_observation.session.broker_session_id != broker_session.session_id:
            raise _GateFailure(
                SemanticGateName.RUNTIME_LAUNCH, CategoryBFailureCode.RUNTIME_SESSION_MISMATCH
            )
        runtime_session = launch_observation.session
        if not (
            launch_observation.launch_shape_valid
            and launch_observation.required_flags_accepted
            and launch_observation.lf_jsonl_correlation_succeeded
        ):
            raise _GateFailure(
                SemanticGateName.RUNTIME_LAUNCH, CategoryBFailureCode.RPC_LAUNCH_SHAPE_UNEXPECTED
            )
        if not launch_observation.pi_version_observed:
            raise _GateFailure(
                SemanticGateName.RUNTIME_LAUNCH, CategoryBFailureCode.PI_VERSION_NOT_OBSERVED
            )
        _pass(SemanticGateName.RUNTIME_LAUNCH)
        _pass(SemanticGateName.PI_VERSION_OBSERVED)
        _pass(SemanticGateName.RPC_LAUNCH_SHAPE)
        _pass(SemanticGateName.REQUIRED_LAUNCH_FLAGS)
        _pass(SemanticGateName.LF_JSONL_CORRELATION)

        # -- GET_COMMANDS (+ H1 + extension command namespace, ONE observation) --
        _current_gate = SemanticGateName.GET_COMMANDS
        commands_observation = _invoke(
            SemanticGateName.GET_COMMANDS,
            lambda: get_commands(runtime_session),
            expected_type=GetCommandsObservation,
            raised_code=CategoryBFailureCode.ADAPTER_RAISED,
            malformed_code=CategoryBFailureCode.MALFORMED_ADAPTER_RESULT,
        )
        if commands_observation.runtime_session_id != runtime_session.runtime_session_id:
            raise _GateFailure(
                SemanticGateName.GET_COMMANDS, CategoryBFailureCode.RUNTIME_SESSION_MISMATCH
            )
        if not (
            commands_observation.call_succeeded
            and commands_observation.response_shape_understood
        ):
            raise _GateFailure(
                SemanticGateName.GET_COMMANDS,
                CategoryBFailureCode.GET_COMMANDS_RESPONSE_SHAPE_NOT_UNDERSTOOD,
            )
        _pass(SemanticGateName.GET_COMMANDS)
        facts_kwargs["get_commands_response_shape_understood"] = True
        if not commands_observation.h1_identity_established:
            raise _GateFailure(
                SemanticGateName.H1_EXTENSION_IDENTITY,
                CategoryBFailureCode.H1_EXTENSION_IDENTITY_MISMATCH,
            )
        _pass(SemanticGateName.H1_EXTENSION_IDENTITY)
        facts_kwargs["h1_extension_identity_matched"] = True
        partition = commands_observation.extension_command_partition()
        namespace_ok = (
            partition.cli_entry_count == 1
            and partition.cli_command_names[0] == commands_observation.sentinel_command_name
            and partition.unrecognized_entry_count == 0
        )
        if not namespace_ok:
            code = (
                CategoryBFailureCode.EXTENSION_COMMAND_PROVENANCE_UNKNOWN
                if partition.unrecognized_entry_count
                else CategoryBFailureCode.UNEXPECTED_CLI_EXTENSION_COMMAND
            )
            raise _GateFailure(SemanticGateName.EXTENSION_COMMAND_NAMESPACE, code)
        _pass(SemanticGateName.EXTENSION_COMMAND_NAMESPACE)
        facts_kwargs["no_unexpected_extension_command_observed"] = True

        # -- GET_STATE (+ H2, ONE observation) --
        _current_gate = SemanticGateName.GET_STATE
        state_observation = _invoke(
            SemanticGateName.GET_STATE,
            lambda: get_state(runtime_session),
            expected_type=GetStateObservation,
            raised_code=CategoryBFailureCode.ADAPTER_RAISED,
            malformed_code=CategoryBFailureCode.MALFORMED_ADAPTER_RESULT,
        )
        if state_observation.runtime_session_id != runtime_session.runtime_session_id:
            raise _GateFailure(
                SemanticGateName.GET_STATE, CategoryBFailureCode.RUNTIME_SESSION_MISMATCH
            )
        if not (
            state_observation.call_succeeded and state_observation.response_shape_understood
        ):
            raise _GateFailure(
                SemanticGateName.GET_STATE,
                CategoryBFailureCode.GET_STATE_RESPONSE_SHAPE_NOT_UNDERSTOOD,
            )
        _pass(SemanticGateName.GET_STATE)
        facts_kwargs["get_state_response_shape_understood"] = True
        h2_matched = (
            state_observation.reported_provider == route_descriptor.provider_id
            and state_observation.reported_model == route_descriptor.model_id
        )
        if not h2_matched:
            raise _GateFailure(
                SemanticGateName.H2_PROVIDER_MODEL_IDENTITY,
                CategoryBFailureCode.H2_PROVIDER_MODEL_IDENTITY_MISMATCH,
            )
        _pass(SemanticGateName.H2_PROVIDER_MODEL_IDENTITY)
        facts_kwargs["h2_provider_model_identity_matched"] = True

        # -- PROTOCOL_INTEGRITY --
        _current_gate = SemanticGateName.PROTOCOL_INTEGRITY
        protocol_observation = _invoke(
            SemanticGateName.PROTOCOL_INTEGRITY,
            lambda: observe_protocol(runtime_session),
            expected_type=ProtocolObservation,
            raised_code=CategoryBFailureCode.ADAPTER_RAISED,
            malformed_code=CategoryBFailureCode.MALFORMED_ADAPTER_RESULT,
        )
        if protocol_observation.runtime_session_id != runtime_session.runtime_session_id:
            raise _GateFailure(
                SemanticGateName.PROTOCOL_INTEGRITY, CategoryBFailureCode.RUNTIME_SESSION_MISMATCH
            )
        if protocol_observation.protocol_violation_observed:
            raise _GateFailure(
                SemanticGateName.PROTOCOL_INTEGRITY, CategoryBFailureCode.PROTOCOL_VIOLATION_OBSERVED
            )
        if protocol_observation.extension_error_observed:
            raise _GateFailure(
                SemanticGateName.PROTOCOL_INTEGRITY, CategoryBFailureCode.EXTENSION_ERROR_OBSERVED
            )
        _pass(SemanticGateName.PROTOCOL_INTEGRITY)
        facts_kwargs["no_protocol_violation_observed"] = True
        facts_kwargs["no_extension_error_observed"] = True

        # -- ROUTE_CHECK --
        _current_gate = SemanticGateName.ROUTE_CHECK
        route_outcome: RouteCheckOutcome = run_offline_route_check(
            descriptor=route_descriptor, secret_context=secret_context, checker=route_checker
        )
        if not route_outcome.passed:
            raise _GateFailure(
                SemanticGateName.ROUTE_CHECK, CategoryBFailureCode.ROUTE_CHECK_FAILED
            )
        _pass(SemanticGateName.ROUTE_CHECK)
        facts_kwargs["exact_candidate_model_served"] = True

        # ================= compatibility facts end; PRE-PROMPT PREFIX satisfied =================

        # -- SEMANTIC_PROMPT_DISPATCH: exactly ONE prompt, ever, for this attempt --
        # 5F3B-Q1-PRE1-FU1: `semantic_prompts_sent` is NEVER set before this
        # point, and is set to 1 in exactly ONE place below -- only once a
        # returned, well-typed dispatch observation mechanically establishes
        # CONFIRMED_SENT. A raised exception, a wrong-type result, or a
        # result that does not provably answer THIS request is NEVER
        # evidence of either NOT_SENT or SENT -- it becomes
        # SEND_STATE_INDETERMINATE via `_DispatchIndeterminate`, which the
        # outer handler below never folds into `infrastructure_refusal`
        # (that would falsely claim CONFIRMED_NOT_SENT) or a scored run
        # (that would falsely claim CONFIRMED_SENT).
        _current_gate = SemanticGateName.SEMANTIC_PROMPT_DISPATCH
        prompt_request = SemanticPromptRequest(
            run_id=run_id,
            runtime_session=runtime_session,
            task_id=task.task_id,
            task_revision=task.task_revision,
        )
        try:
            turn_observation = send_semantic_prompt(prompt_request)
        except Exception:
            # A generic adapter exception is proof of NEITHER NOT_SENT NOR
            # SENT -- the command may have crossed the send boundary and then
            # the call errored before returning, or it may never have been
            # sent at all. This function cannot mechanically distinguish
            # those from an exception alone, and never guesses.
            raise _DispatchIndeterminate() from None
        if type(turn_observation) is not SemanticTurnObservation:
            # A wrong-type result is equally not evidence of either state.
            raise _DispatchIndeterminate()
        if not require_dispatch_matches_request(turn_observation.dispatch, prompt_request):
            # A dispatch observation that does not provably answer THIS
            # request (different run/session/task) cannot be trusted to
            # describe what happened to it.
            raise _DispatchIndeterminate()
        dispatch_state = turn_observation.dispatch.dispatch_state
        if dispatch_state is SemanticPromptDispatchState.SEND_STATE_INDETERMINATE:
            raise _DispatchIndeterminate()
        if dispatch_state is SemanticPromptDispatchState.CONFIRMED_NOT_SENT:
            # A mechanically-established pre-send refusal, returned (never
            # raised). A pre-prompt infrastructure refusal --
            # semantic_prompts_sent stays 0 (never touched below).
            raise _GateFailure(
                SemanticGateName.SEMANTIC_PROMPT_DISPATCH,
                SemanticFailureCode.SEMANTIC_PROMPT_CONFIRMED_NOT_SENT,
            )
        # dispatch_state is CONFIRMED_SENT: the ONE authorized semantic
        # prompt for this attempt has now been mechanically established as
        # sent. This is the ONLY place in this module that ever sets
        # semantic_prompts_sent to 1, and it happens ONLY after that fact is
        # established -- never before the call, never on a guess.
        if not turn_observation.call_succeeded:
            # Structurally unreachable: SemanticTurnObservation's own
            # __post_init__ requires call_succeeded == True for a
            # CONFIRMED_SENT dispatch. Kept as a loud, non-silent guard
            # rather than a comment-only promise.
            raise _GateFailure(
                SemanticGateName.SEMANTIC_PROMPT_DISPATCH,
                SemanticFailureCode.SEMANTIC_PROMPT_DISPATCH_FAILED,
            )
        semantic_prompts_sent = 1
        _pass(SemanticGateName.SEMANTIC_PROMPT_DISPATCH)

        # -- TURN_COMPLETION --
        _current_gate = SemanticGateName.TURN_COMPLETION
        if not (turn_observation.agent_settled or turn_observation.deadline_reached):
            raise _GateFailure(
                SemanticGateName.TURN_COMPLETION, SemanticFailureCode.TURN_DID_NOT_TERMINATE
            )
        _pass(SemanticGateName.TURN_COMPLETION)

        # -- BROKER_ACTIVITY --
        _current_gate = SemanticGateName.BROKER_ACTIVITY
        broker_activity = _invoke(
            SemanticGateName.BROKER_ACTIVITY,
            lambda: collect_broker_activity(runtime_session),
            expected_type=BrokerActivityObservation,
            raised_code=SemanticFailureCode.BROKER_ACTIVITY_COLLECTION_FAILED,
            malformed_code=SemanticFailureCode.MALFORMED_ADAPTER_RESULT,
        )
        if broker_activity.runtime_session_id != runtime_session.runtime_session_id:
            raise _GateFailure(
                SemanticGateName.BROKER_ACTIVITY, CategoryBFailureCode.RUNTIME_SESSION_MISMATCH
            )
        if not broker_activity.call_succeeded:
            raise _GateFailure(
                SemanticGateName.BROKER_ACTIVITY,
                SemanticFailureCode.BROKER_ACTIVITY_COLLECTION_FAILED,
            )
        _pass(SemanticGateName.BROKER_ACTIVITY)

        # -- REPOSITORY_OBSERVATION (reused ar2.observation, unmodified) --
        _current_gate = SemanticGateName.REPOSITORY_OBSERVATION
        try:
            snapshot = observe_repository(
                git_executable=git_executable, workspace_root=task_workspace.repo_root
            )
            classification = observe_and_classify(
                snapshot,
                workspace_root=task_workspace.repo_root,
                head_before=task_workspace.head_before,
                expected_changed_paths=task.expected_changed_paths,
            )
        except Exception:
            raise _GateFailure(
                SemanticGateName.REPOSITORY_OBSERVATION,
                SemanticFailureCode.REPOSITORY_OBSERVATION_FAILED,
            ) from None
        _pass(SemanticGateName.REPOSITORY_OBSERVATION)

        # -- AUTHORITATIVE_VERIFICATION (reused ar2.verification, unmodified) --
        _current_gate = SemanticGateName.AUTHORITATIVE_VERIFICATION
        try:
            verification_outcome = run_verification(
                python_executable=python_executable,
                workspace_root=task_workspace.repo_root,
                args=task.case.verification_args,
            )
        except Exception:
            raise _GateFailure(
                SemanticGateName.AUTHORITATIVE_VERIFICATION,
                SemanticFailureCode.VERIFICATION_EXECUTION_FAILED,
            ) from None
        _pass(SemanticGateName.AUTHORITATIVE_VERIFICATION)

        # -- FINAL_REPORT_CLAIMS --
        _current_gate = SemanticGateName.FINAL_REPORT_CLAIMS
        claims_observation = _invoke(
            SemanticGateName.FINAL_REPORT_CLAIMS,
            lambda: collect_final_report_claims(runtime_session),
            expected_type=FinalReportClaimsObservation,
            raised_code=SemanticFailureCode.FINAL_REPORT_CLAIMS_COLLECTION_FAILED,
            malformed_code=SemanticFailureCode.MALFORMED_ADAPTER_RESULT,
        )
        if claims_observation.runtime_session_id != runtime_session.runtime_session_id:
            raise _GateFailure(
                SemanticGateName.FINAL_REPORT_CLAIMS, CategoryBFailureCode.RUNTIME_SESSION_MISMATCH
            )
        report_claims = claims_observation.claims
        _pass(SemanticGateName.FINAL_REPORT_CLAIMS)

    except _DispatchIndeterminate:
        # 5F3B-Q1-PRE1-FU1: dispatch was attempted but AIDO cannot
        # mechanically establish whether the command was sent. NEVER
        # semantic_prompts_sent = 0 (that would falsely claim
        # CONFIRMED_NOT_SENT) and NEVER 1 (that would falsely claim
        # CONFIRMED_SENT). infrastructure_refusal is deliberately left
        # untouched (stays False) for the identical reason.
        dispatch_state = SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
        semantic_prompts_sent = None
        dispatch_indeterminate = True
        failed_gate = SemanticGateName.SEMANTIC_PROMPT_DISPATCH
        failure_code = SemanticFailureCode.SEMANTIC_PROMPT_SEND_STATE_INDETERMINATE
        _fail_status(SemanticGateName.SEMANTIC_PROMPT_DISPATCH, failure_code)
    except _GateFailure as gf:
        failed_gate = gf.gate
        failure_code = gf.code
        _fail_status(gf.gate, gf.code)
        if semantic_prompts_sent == 0:
            infrastructure_refusal = True
    except Exception:
        # An exception this function did not anticipate as a _GateFailure --
        # e.g. a reused frozen helper (mint/route/secret/config/binding/
        # environment construction) raising a type this module's specific
        # except clauses did not name, or `_git`/filesystem I/O raising
        # `subprocess.TimeoutExpired`/`OSError` during workspace population.
        # Never let this escape the function uncaught: doing so would abort
        # before CLOSURE ever runs, exactly the "unconditional on every
        # path" property this module promises and a live broker/runtime
        # session could still be open. Attributed to whichever gate
        # `_current_gate` names when the exception occurred -- an
        # approximation, but never a silent skip of closure. No exception
        # text is ever retained (str(exc)/repr(exc) are never read here).
        failed_gate = _current_gate
        failure_code = CategoryBFailureCode.ADAPTER_RAISED
        _fail_status(_current_gate, failure_code)
        if semantic_prompts_sent == 0:
            infrastructure_refusal = True

    # ================= CLOSURE: unconditional, on every path =================
    # The three closure gates below record their OWN typed object's
    # `status_text` verbatim, never the generic `_pass()`/"PASSED" literal:
    # `RuntimeTeardownStatus`/`BrokerShutdownStatus`/`SemanticCleanupStatus`
    # each render "NOT_REQUIRED"/"SUCCEEDED"/"CLOSED"/"VERIFIED_REMOVED" for
    # a non-failure state, never the string "PASSED" -- so gate_statuses can
    # never disagree with the typed object that actually produced the fact
    # (the same discipline i2b_controller.py's own closure loop applies).
    runtime_teardown = _close_runtime(shutdown_runtime, runtime_session, run_id=run_id or "")
    gate_statuses[SemanticGateName.RUNTIME_TEARDOWN.value] = runtime_teardown.status_text
    broker_shutdown = _close_broker(shutdown_broker, broker_session, run_id=run_id or "")
    gate_statuses[SemanticGateName.BROKER_SHUTDOWN.value] = broker_shutdown.status_text
    cleanup = _attempt_cleanup(generated_config, semantic_prompts_sent=semantic_prompts_sent)
    gate_statuses[SemanticGateName.GENERATED_CONFIG_CLEANUP.value] = cleanup.status_text

    safety_context = build_run_safety_context(
        secret_context=secret_context,
        broker_session=broker_session,
        run_workspace=run_workspace,
        route_descriptor=route_descriptor,
    )
    closure_established = (
        runtime_teardown.closure_satisfied
        and broker_shutdown.closure_satisfied
        and cleanup.closure_satisfied
    )

    facts = CompatibilityFacts(**facts_kwargs)
    compatibility_established = facts.all_established

    # -- classification / validity / scope / report-accuracy --
    run_validity: RunValidity | None = None
    scoring_eligible = False
    autonomous_classification: AutonomousClassification | None = None
    diagnostic_subclassification: DiagnosticSubclassification | None = None
    scope_result: ScopeResult | None = None
    comparisons: tuple[ClaimComparison, ...] = ()
    expected_changed_paths_satisfied: bool | None = None
    head_unchanged: bool | None = None
    index_clean: bool | None = None
    protected_witness_untouched: bool | None = None
    no_unexpected_untracked_or_create_delete_rename: bool | None = None
    broker_git_cross_check_agrees: bool | None = None
    verification_passed: bool | None = (
        verification_outcome.passed if verification_outcome is not None else None
    )

    if dispatch_indeterminate:
        # 5F3B-Q1-PRE1-FU1: SEND_STATE_INDETERMINATE. No candidate score, no
        # run_validity, no autonomous_classification, no primary
        # qualification_record -- the frozen `qualification.records`/
        # `qualification.outcomes`/`qualification.validity` schemas have no
        # representation for an unestablished `semantic_prompts_sent` fact,
        # and none is invented here. All defaults above are left exactly as
        # initialized.
        pass
    elif infrastructure_refusal:
        outcome = classify_outcome(
            RunFacts(semantic_prompts_sent=0, infrastructure_refusal=True)
        )
        autonomous_classification = outcome.autonomous_classification
        diagnostic_subclassification = outcome.diagnostic_subclassification
    elif semantic_prompts_sent == 1:
        if not closure_established:
            # AIDO's own closure machinery (runtime teardown / broker
            # shutdown / generated-config cleanup) did not complete. The
            # candidate has no ability to affect whether AIDO's own shutdown
            # call succeeds -- this is mechanically attributable to
            # AIDO/harness/infrastructure by construction (Sec. 17.2 case 2),
            # not a guess.
            attribution = attribute_protocol_anomaly(
                pre_prompt=False, mechanically_attributed_to="infrastructure"
            )
            validity_result = resolve_run_validity(
                infrastructure_refusal=False,
                semantic_prompts_sent=1,
                anomaly_attribution=attribution,
            )
        elif failed_gate is not None:
            # A genuine mid-run gate failure (prompt dispatch, turn
            # completion, broker-activity collection, repository
            # observation, verification execution, or report-claims
            # collection all raised/malformed/mismatched). No mechanical
            # attribution evidence exists at this offline-wiring stage to
            # distinguish AIDO/harness-caused from candidate-caused for this
            # shape of anomaly, so this defaults to the honest "do not
            # guess" outcome (Sec. 17.2 case 4) rather than crediting or
            # blaming the candidate.
            attribution = attribute_protocol_anomaly(
                pre_prompt=False, mechanically_attributed_to=None
            )
            validity_result = resolve_run_validity(
                infrastructure_refusal=False,
                semantic_prompts_sent=1,
                anomaly_attribution=attribution,
            )
        else:
            validity_result = resolve_run_validity(
                infrastructure_refusal=False, semantic_prompts_sent=1
            )
        run_validity = validity_result.run_validity
        scoring_eligible = validity_result.scoring_eligible

        refusals = broker_activity.refusals if broker_activity is not None else ()
        expected = task.expected_changed_paths
        observed_paths = (
            frozenset(classification.changed_tracked_paths)
            if classification is not None
            else frozenset()
        )
        scope_result = build_scope_result(
            expected_changed_paths=expected,
            observed_changed_paths=observed_paths,
            refusals=refusals,
        )
        hard_disqualifier_present = has_hard_disqualifier(refusals)

        trusted_repository_state: bool | None = None
        if classification is not None:
            trusted_repository_state = classification.trusted or (
                not expected and classification.workspace_class == NO_CHANGE_OBSERVED
            )
            expected_changed_paths_satisfied = observed_paths == expected
            head_unchanged = not classification.head_moved
            index_clean = not classification.staged_paths
            witness_paths = set(task.verification_witness_paths)
            touched = set(classification.changed_tracked_paths) | set(
                classification.untracked_paths
            )
            protected_witness_untouched = not (witness_paths & touched)
            no_unexpected_untracked_or_create_delete_rename = (
                not classification.untracked_paths
                and classification.workspace_class
                not in (UNEXPECTED_CHANGE, UNEXPECTED_UNTRACKED)
            )
            if broker_activity is not None:
                broker_git_cross_check_agrees = broker_activity.edited_paths == observed_paths

        if scoring_eligible:
            outcome = classify_outcome(
                RunFacts(
                    semantic_prompts_sent=1,
                    runtime_settled=turn_observation.agent_settled
                    if turn_observation is not None
                    else False,
                    runtime_deadline_reached=turn_observation.deadline_reached
                    if turn_observation is not None
                    else False,
                    stall_pattern_established=None,
                    verification_passed=verification_passed,
                    expected_changed_paths_satisfied=expected_changed_paths_satisfied,
                    trusted_repository_state=trusted_repository_state,
                    hard_disqualifier_present=hard_disqualifier_present,
                    operator_continuation=False,
                    automatic_semantic_retry=False,
                )
            )
            autonomous_classification = outcome.autonomous_classification
            diagnostic_subclassification = outcome.diagnostic_subclassification

        if report_claims is not None and classification is not None:
            observed_facts = ObservedFacts(
                observed_changed_paths=observed_paths,
                observed_diff_present=bool(observed_paths),
                verification_passed=verification_passed,
            )
            comparisons = compare_report(report_claims, observed_facts)

    # -- record build + emission, through the SAME choke point every other
    # -- primary qualification record in this package uses --
    # 5F3B-Q1-PRE1-FU1: for SEND_STATE_INDETERMINATE, `build_qualification_record`
    # is NEVER called. Its frozen shape requires `semantic_prompts_sent` to be
    # exactly 0 or 1 (`qualification.records._validate_run_shape`) -- there is
    # no truthful value this module could pass for an unestablished fact, and
    # none is forced. No primary record exists for this attempt.
    if dispatch_indeterminate:
        qualification_record = None
        gate_statuses[SemanticGateName.EVIDENCE_SAFETY.value] = _STATUS_NOT_REQUIRED
    else:
        pi_runtime = {
            "observed_version": observed_pi_version,
            "compatibility_facts": facts.as_dict(),
            "compatibility_gate_passed": compatibility_established,
        }
        route_provenance = {
            "model_id": model_id,
            "provider_route": (
                route_descriptor.provider_id if route_descriptor is not None else None
            ),
            "backend_gateway_class": (
                route_descriptor.backend_gateway_class if route_descriptor is not None else None
            ),
        }
        record = build_qualification_record(
            candidate=candidate,
            model_id=model_id,
            task_id=task.task_id,
            task_revision=task.task_revision,
            semantic_prompts_sent=semantic_prompts_sent,
            infrastructure_refusal=infrastructure_refusal,
            run_validity=run_validity.value if run_validity is not None else None,
            scoring_eligible=scoring_eligible,
            autonomous_classification=(
                autonomous_classification.value if autonomous_classification is not None else None
            ),
            diagnostic_subclassification=(
                diagnostic_subclassification.value
                if diagnostic_subclassification is not None
                else None
            ),
            operator_continuation=False,
            automatic_semantic_retry=False,
            pi_runtime=pi_runtime,
            route_provenance=route_provenance,
            verification=_project_verification(verification_outcome),
            scope_result=_project_scope_result(scope_result),
            report_accuracy=_project_report_accuracy(comparisons),
        )
        qualification_record = emit_or_refuse(record, path=evidence_path, safety=safety_context)
        if qualification_record.get("refused"):
            _fail_status(
                SemanticGateName.EVIDENCE_SAFETY, CategoryBFailureCode.EVIDENCE_SCRUB_REFUSED
            )
        else:
            _pass(SemanticGateName.EVIDENCE_SAFETY)

    result = SemanticTaskAttemptResult(
        candidate=candidate,
        model_id=model_id,
        task_id=task.task_id,
        task_revision=task.task_revision,
        semantic_prompts_sent=semantic_prompts_sent,
        dispatch_state=dispatch_state,
        infrastructure_refusal=infrastructure_refusal,
        gate_statuses=dict(gate_statuses),
        failed_gate=failed_gate,
        failure_code=failure_code,
        facts=facts,
        observed_pi_version=observed_pi_version,
        run_validity=run_validity,
        scoring_eligible=scoring_eligible,
        autonomous_classification=autonomous_classification,
        diagnostic_subclassification=diagnostic_subclassification,
        scope_result=scope_result,
        report_accuracy_comparisons=comparisons,
        verification_passed=verification_passed,
        expected_changed_paths_satisfied=expected_changed_paths_satisfied,
        head_unchanged=head_unchanged,
        index_clean=index_clean,
        protected_witness_untouched=protected_witness_untouched,
        no_unexpected_untracked_or_create_delete_rename=no_unexpected_untracked_or_create_delete_rename,
        broker_git_cross_check_agrees=broker_git_cross_check_agrees,
        runtime_teardown=runtime_teardown,
        broker_shutdown=broker_shutdown,
        cleanup=cleanup,
        qualification_record=qualification_record,
    )
    return result
