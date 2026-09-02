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
      -> PHASE 1: ONE semantic prompt dispatched   (injected)
           -> CONFIRMED_SENT / CONFIRMED_NOT_SENT / SEND_STATE_INDETERMINATE
      -> PHASE 2: turn completion observed         (injected; ONLY after
           CONFIRMED_SENT) -> SETTLED / DEADLINE_REACHED / OBSERVATION_FAILED
      -> broker activity collected         (injected)
      -> repository observed               (reused ar2.observation, unmodified)
      -> authoritative verification        (reused ar2.verification, unmodified)
      -> final report claims collected     (injected; OPTIONAL, NEVER GATING)
      -- post-turn facts end here --
      -> runtime teardown                  (frozen O1 order: runtime first)
      -> broker shutdown                   (frozen O1 order: broker second)
      -> generated-config cleanup          (reused i2_cleanup, unmodified)
      -> semantic workspace removal + verification   (reused i2b_workspace)
      -> retained-evidence safety gate     (reused qualification.safety)

Exactly ONE semantic prompt, in TWO observation phases
-------------------------------------------------------

:data:`MAX_SEMANTIC_PROMPTS_PER_ATTEMPT` is a module constant ``1``. This
module defines no retry, no continuation, and no second call to the dispatch
adapter for any reason -- not a stall, not a wrong result, not an adapter
error. There is exactly one call site for ``dispatch_semantic_prompt`` and
exactly one for ``observe_semantic_turn``, and the second is reachable only
after the first established ``CONFIRMED_SENT``.

**5F3B-Q1-PRE1-FU2 -- dispatch authority is separate from turn completion.**
Independent review established, from Pi 0.84.4's own source, that FU1's
single whole-turn adapter is not faithful to the real seam: Pi emits a
correlated ``prompt`` response after preflight and STRICTLY BEFORE agent
start and any provider inference, so the send fact exists long before turn
completion does. Every reachable post-acknowledgement failure --
``RUNTIME_PROTOCOL_VIOLATION``, ``RUNTIME_OUTPUT_CAP_EXCEEDED``,
``RUNTIME_EVENT_CAP_EXCEEDED``, ``RUNTIME_READ_ERROR``,
``RUNTIME_EXITED_EARLY``, or a phase-2 adapter bug -- left FU1's live adapter
exactly two options, both wrong: fabricate ``deadline_reached``, or raise and
have the controller ERASE an already-established ``CONFIRMED_SENT`` into
``SEND_STATE_INDETERMINATE``. The second is the fairness-critical one: it
converts a KNOWN SPENT prompt into an UNKNOWN one.

So the send fact and the turn fact are now two adapters and two types:

.. code-block:: text

    PHASE 1  dispatch_semantic_prompt(SemanticPromptRequest)
               -> SemanticPromptDispatchObservation
             CONFIRMED_NOT_SENT | CONFIRMED_SENT | SEND_STATE_INDETERMINATE
                  |
                  v
             PROMPT-COUNT TRUTH FIXED HERE, ONCE, AND NEVER REWRITTEN
                  |
                  v  (only for CONFIRMED_SENT)
    PHASE 2  observe_semantic_turn(SemanticTurnRequest)
               -> SemanticTurnObservation
             SETTLED | DEADLINE_REACHED | OBSERVATION_FAILED

Invariant I-1 (monotonicity), mechanically: ``_DispatchIndeterminate`` is
raised from inside the phase-1 block and NOWHERE ELSE, and
``semantic_prompts_sent = 1`` dominates every statement that follows it. No
phase-2 outcome, no broker/repository/verification/report-claims failure, no
runtime-teardown, broker-shutdown, generated-config-cleanup, **workspace
removal** (Sec. 9.1.6) or evidence-emission failure can move it back to
``SEND_STATE_INDETERMINATE`` or to ``0``.

Invariant I-2 (no send by convention): calling the adapter establishes
nothing. ``CONFIRMED_SENT``/``CONFIRMED_NOT_SENT`` may be produced ONLY by a
returned, well-typed, provenance-matched observation carrying a bounded
evidence code -- never by an exception, and never by having called a Python
function.

Exactly ONE retained artifact per invoked attempt
--------------------------------------------------

Sec. 3.F. A determinate send state emits the frozen
``pi-implementer-qualification.v1`` primary record; an indeterminate one
emits the sibling ``pi-implementer-qualification-attempt.v1``
(:mod:`qualification.semantic_attempt`) through the SAME
``safety.emit_evidence_or_refuse`` choke point. Never zero -- which is what
FU1 left behind for the one outcome where AIDO cannot prove whether the
candidate's single authorized prompt was spent -- and never two.

**5F3B-Q1-PRE1-FU1 -- ``semantic_prompts_sent`` is truth, not timing.**
(Retained for provenance; FU2 above supersedes its single-adapter shape.)
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

import hashlib
import json
import secrets
from dataclasses import dataclass, field, fields
from enum import Enum
from types import MappingProxyType
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
    remove_run_workspace,
)
from .outcomes import AutonomousClassification, DiagnosticSubclassification, OutcomeClassification, RunFacts, classify_outcome
from .records import CANDIDATE_MODEL_IDS, build_qualification_record, emit_or_refuse
from .report_accuracy import ClaimComparison, ObservedFacts, ReportClaims, bucket_report_accuracy, compare_report
from .safety import ArtifactSafetyContext, qualification_scrub_check
from .semantic_attempt import (
    CLASSIFICATION_UNAVAILABLE_REASON,
    build_attempt_record,
    emit_attempt_or_refuse,
)
from .scope import RefusalEvent, ScopeResult, attribute_protocol_anomaly, build_scope_result, has_hard_disqualifier
from .semantic_session import (
    DISPATCH_EVIDENCE_CODE_STATES,
    BrokerActivityObservation,
    FinalReportClaimsObservation,
    SemanticDispatchEvidenceCode,
    SemanticPromptDispatchObservation,
    SemanticPromptDispatchState,
    SemanticPromptRequest,
    SemanticTurnObservation,
    SemanticTurnOutcome,
    SemanticTurnRequest,
    require_dispatch_matches_request,
    require_turn_matches_request,
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
    #: 5F3B-Q1-PRE1-FU2 / DESIGN-FU1 Sec. 9.1: the attempt OWNS its
    #: workspace from the instant mint returns, and every terminal path
    #: after mint attempts removal exactly once -- AFTER runtime teardown
    #: and broker shutdown (whose cwd/capability scope are bound to that
    #: tree) and AFTER the authority-scoped generated-config scrub, but
    #: strictly BEFORE any evidence is constructed or emitted.
    SEMANTIC_WORKSPACE_REMOVAL = "semantic_workspace_removal"
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

#: 5F3B-Q1-PRE1-FU2 / DESIGN-FU1 Sec. 9.3: the model's own final assistant
#: report is **OPTIONAL, UNTRUSTED** evidence and is NOT a qualification
#: gate. Its unavailability -- an adapter exception, a wrong-type return, a
#: foreign-session observation, or claims that fail bounded parsing -- must
#: never route through the shared ``_GateFailure``/``failed_gate`` machinery
#: that genuinely gating post-prompt facts use, because that path feeds
#: ``attribute_protocol_anomaly`` and would turn a fully-verified,
#: fully-closed run into ``ATTRIBUTION_UNDETERMINED`` and unscorable. The
#: authority hierarchy is repository observation, authoritative
#: verification, broker/Git cross-check and scope/refusal facts FIRST; the
#: model's self-report is never promoted to implementation authority by a
#: collection failure any more than by its content.
NON_GATING_POST_PROMPT_GATES: tuple[SemanticGateName, ...] = (
    SemanticGateName.FINAL_REPORT_CLAIMS,
)

#: The post-prompt gates whose failure MAY set ``failed_gate``.
GATING_POST_PROMPT_GATES: tuple[SemanticGateName, ...] = tuple(
    gate for gate in POST_PROMPT_GATES if gate not in NON_GATING_POST_PROMPT_GATES
)

#: The FROZEN closure order (DESIGN-FU1 Sec. 9.1.3), which is also the
#: order this tuple declares and the order the controller executes:
#: runtime teardown -> broker shutdown -> generated-config cleanup ->
#: semantic workspace removal + verification -> retained-evidence
#: construction/scrub/emission.
CLOSURE_GATES: tuple[SemanticGateName, ...] = (
    SemanticGateName.RUNTIME_TEARDOWN,
    SemanticGateName.BROKER_SHUTDOWN,
    SemanticGateName.GENERATED_CONFIG_CLEANUP,
    SemanticGateName.SEMANTIC_WORKSPACE_REMOVAL,
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
    #: 5F3B-Q1-PRE1-FU2: PHASE 2 reported ``OBSERVATION_FAILED`` -- the
    #: turn became unobservable to AIDO (protocol violation, output cap,
    #: event cap, read error, early child exit, or a raised/malformed
    #: phase-2 adapter result). This NEVER contests the already-established
    #: ``CONFIRMED_SENT`` / ``semantic_prompts_sent = 1``, and it is never
    #: reported as a deadline: AIDO stopped being able to watch, which is
    #: not a claim that Pi stopped or that inference stopped. It replaces
    #: FU1's ``TURN_DID_NOT_TERMINATE``, which existed only because the old
    #: two-valued turn type could not represent this reachable state.
    TURN_OBSERVATION_FAILED = "TURN_OBSERVATION_FAILED"
    BROKER_ACTIVITY_COLLECTION_FAILED = "BROKER_ACTIVITY_COLLECTION_FAILED"
    REPOSITORY_OBSERVATION_FAILED = "REPOSITORY_OBSERVATION_FAILED"
    VERIFICATION_EXECUTION_FAILED = "VERIFICATION_EXECUTION_FAILED"
    # 5F3B-Q1-PRE1-FU2 removed FINAL_REPORT_CLAIMS_COLLECTION_FAILED. There
    # is deliberately no bounded FAILURE code for the final-report gate any
    # more: DESIGN-FU1 Sec. 9.3 makes report availability a non-gating,
    # descriptive `ReportAvailability` fact, and leaving a failure code in
    # this enum is exactly the seam through which it would be re-wired into
    # `failed_gate` -> `attribute_protocol_anomaly` -> ATTRIBUTION_UNDETERMINED.
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
    #: 5F3B-Q1-PRE1-FU2 / DESIGN-FU1 Sec. 9.1.4: the semantic workspace's
    #: removal was attempted and NOT proven. "Not proven" is the strict
    #: frozen predicate, never truthiness and never absence-of-exception.
    SEMANTIC_WORKSPACE_REMOVAL_UNVERIFIED = "SEMANTIC_WORKSPACE_REMOVAL_UNVERIFIED"
    #: The same removal failure, under a dispatch send state that was
    #: mechanically indeterminate. No 0/1 cleanup classifier is fabricated
    #: for workspace removal any more than for the generated-config scrub.
    SEMANTIC_WORKSPACE_REMOVAL_UNVERIFIED_INDETERMINATE_DISPATCH = (
        "SEMANTIC_WORKSPACE_REMOVAL_UNVERIFIED_INDETERMINATE_DISPATCH"
    )


#: Either failure-code family may appear in a result. Both are exact-value
#: ``str`` enums; a gate-status text is always ``FAILED:<member.value>`` for
#: exactly one of them, never a hand-built string.
FailureCode = CategoryBFailureCode | SemanticFailureCode


# ===========================================================================
# 5F3B-Q1-PRE1-FU2 / DESIGN-FU1 Sec. 9.4 -- DEEP in-memory immutability
# ===========================================================================
# ``@dataclass(frozen=True)`` only refuses reassigning the FIELD; it never
# refuses MUTATING the object the field refers to. A frozen result whose
# ``gate_statuses`` is a plain ``dict``, or whose record projection holds a
# live reference to a nested mutable ``list``, is therefore NOT immutable in
# the sense classification, the hard bar, ranking, evidence generation and
# audit all depend on -- a caller could rewrite a validated gate outcome, or
# flip the ``refused`` flag the sweep derives ``artifact_scrub_passed`` from,
# after every validation had already run.
#
# Two rules make the helpers below sufficient rather than decorative:
#
# 1. **Copy BEFORE wrapping.** ``MappingProxyType`` is a live VIEW: it keeps
#    reflecting mutations of the dict it wraps. Wrapping a caller-supplied
#    dict would leave the caller holding a mutation handle. Every helper here
#    builds a fresh container and wraps THAT, and the fresh container is a
#    throwaway the constructing scope never retains.
# 2. **Recurse.** A proxy over a dict whose values are lists is still
#    mutable one level down, so nested lists/tuples become tuples, sets
#    become frozensets, and nested mappings become proxies over their own
#    fresh copies.
#
# This is in-memory immutability ONLY. Disk-artifact immutability is the
# separate, already-accepted ``safety.write_evidence_exclusively``
# ``O_CREAT | O_EXCL`` property, and satisfying one has never satisfied the
# other -- this whole section exists precisely because the first was already
# true while the second was not.


def freeze_value(value: Any) -> Any:
    """Recursively project ``value`` onto an immutable equivalent."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze_value(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(freeze_value(item) for item in value)
    return value


def freeze_mapping(mapping: Mapping[Any, Any]) -> Mapping[Any, Any]:
    """A read-only proxy over a fresh, recursively-immutable COPY of ``mapping``.

    The backing dict is created here and never returned, stored, or otherwise
    reachable, so no supported caller holds a handle that could mutate what
    the proxy shows.
    """
    return MappingProxyType({key: freeze_value(item) for key, item in mapping.items()})


#: 5F3B-Q1-PRE1-FU2A-FU1A-FU1: byte length of the per-attempt authority token
#: minted once per :func:`run_semantic_task_attempt` invocation -- same
#: length as ``i2_pi_config``'s own ``_AUTHORITY_TOKEN_BYTES`` precedent.
_ATTEMPT_AUTHORITY_TOKEN_BYTES = 16


# ===========================================================================
# 5F3B-Q1-PRE1-FINAL-CLOSURE: ONE-SHOT attempt-authority ISSUANCE REGISTRY
# ===========================================================================
# 5F3B-Q1-PRE1-FU2A-FU1A-FU1-FU1 first closed the "borrow a genuine,
# internally-self-consistent evidence bundle from a DIFFERENT attempt"
# replay by binding each token to a fingerprint of the facts OUTSIDE that
# bundle (gate chronology, dispatch outcome, run validity, scoring
# eligibility, classification, verification). Independent review then
# reproduced a STRONGER replay: the fingerprint itself is derived entirely
# from caller-replaceable `SemanticTaskAttemptResult` fields, so a
# `replace()` call that ALSO copies the foreign attempt's own
# `gate_statuses` (or, for two otherwise-identical correct attempts,
# whatever OTHER fingerprinted field happens to differ) reconstructs a
# fingerprint that matches the foreign token's registered one -- because
# nothing stops the SAME facts from simply being copied alongside the
# bundle. Adding more fields to the fingerprint only enlarges the set that a
# `replace()` call can copy; it does not close the seam.
#
# The actual fix: `SemanticTaskAttemptResult` construction now consumes a
# ONE-SHOT issuance, mirroring `qualification.i2_issuance`'s own
# register/finalize/one-shot precedent (a token already finalized there
# refuses a SECOND finalization; here, a token already consumed refuses a
# SECOND consumption, full stop):
#
#     `run_semantic_task_attempt` REGISTERS one PENDING (token, fingerprint)
#     pair -- ONCE, immediately before constructing its own genuine
#     `SemanticTaskAttemptResult`.
#
#     `SemanticTaskAttemptResult.__post_init__`, after every other
#     invariant already holds, ATOMICALLY requires-and-consumes that pending
#     issuance: the token must currently be pending, the re-derived
#     fingerprint must match what was registered, and -- regardless of
#     whether the match succeeds -- the entry is deleted as part of the SAME
#     step. A token can therefore back AT MOST ONE `SemanticTaskAttemptResult`
#     construction, ever, successful or not.
#
# **This makes `SemanticTaskAttemptResult` a valid-by-construction,
# one-shot authority object, not a freely reconstructible DTO.** After the
# genuine controller-created result has consumed its issuance, NO later
# `dataclasses.replace(genuine_result, ...)` can ever construct another
# authority-bearing instance from it -- including one that touches only an
# "unrelated" field, and including one that faithfully copies the ENTIRE
# caller-visible field set of a DIFFERENT genuine result. That is
# intentional: it is no longer possible to distinguish "copies the whole
# foreign result" from "copies the whole foreign result plus grafts it onto
# different other facts" by inspecting fields alone, so the only sound
# boundary is that the issuance itself is single-use.
#
# **EPHEMERAL PROCESS MEMORY ONLY** -- exactly like `i2_issuance._REGISTRY`:
# a plain module-level ``dict``, never written to disk, never an evidence
# field, carries no claim of surviving a process restart. This is NOT a
# generic provenance framework: there is no public mutation API, no path or
# directory concept, and the ONE fingerprinted field set is fixed and named,
# not caller-configurable.
_PENDING_ATTEMPT_AUTHORITY: dict[str, str] = {}


def _register_attempt_authority(token: str, fingerprint: str) -> None:
    """Register ONE pending issuance. Package-internal only -- called
    EXACTLY ONCE per genuine attempt, by :func:`run_semantic_task_attempt`
    itself, immediately before it constructs its own
    :class:`SemanticTaskAttemptResult`. Not part of any supported public
    API.
    """
    if token in _PENDING_ATTEMPT_AUTHORITY:
        raise ValueError(
            "attempt authority token already registered -- a fresh, random "
            "token must never collide"
        )
    _PENDING_ATTEMPT_AUTHORITY[token] = fingerprint


def _consume_pending_attempt_authority(token: str, fingerprint: str) -> None:
    """Atomically require-and-consume ONE pending attempt-authority issuance.

    Package-internal only -- called EXACTLY ONCE per
    :class:`SemanticTaskAttemptResult` construction, from its own
    ``__post_init__``, after every other invariant already holds.

    Raises :class:`ValueError` unless ``token`` is CURRENTLY a pending
    (unconsumed) issuance whose registered fingerprint equals ``fingerprint``
    exactly. The entry is deleted as part of THIS SAME call regardless of
    whether the match succeeds -- a token is consumed by exactly one
    construction attempt, successful or not, so a failed/mismatched
    construction can never leave a consumed issuance reusable, and a
    genuinely successful one leaves no registry entry behind at all.
    """
    registered = _PENDING_ATTEMPT_AUTHORITY.pop(token, None)
    if registered is None:
        raise ValueError(
            "SemanticTaskAttemptResult: no pending attempt authority for this "
            "identity_provenance.attempt_authority_token -- it was never issued, "
            "or it has already been consumed by an earlier construction. A "
            "SemanticTaskAttemptResult is a one-shot, valid-by-construction "
            "authority object: its issuance can back at most ONE construction, "
            "ever, including a dataclasses.replace() that touches only an "
            "unrelated field"
        )
    if registered != fingerprint:
        raise ValueError(
            "SemanticTaskAttemptResult: this result's own facts disagree with "
            "the fingerprint its identity_provenance.attempt_authority_token was "
            "genuinely issued for -- an evidence bundle borrowed from a "
            "DIFFERENT attempt, even when every object in it is genuine and "
            "internally self-consistent, cannot authorize a different attempt's "
            "own facts. The token is now consumed regardless: this same "
            "mismatched attempt can never be retried into a match"
        )


def _authorized_facts_fingerprint(
    *,
    gate_statuses: Mapping[str, str],
    dispatch_state: SemanticPromptDispatchState,
    semantic_prompts_sent: int | None,
    run_validity: RunValidity | None,
    scoring_eligible: bool,
    autonomous_classification: AutonomousClassification | None,
    diagnostic_subclassification: DiagnosticSubclassification | None,
    verification_passed: bool | None,
) -> str:
    """A deterministic SHA-256 fingerprint of exactly the facts THIS
    attempt's authority is issued for -- everything meaningfully OUTSIDE the
    ``identity_provenance``/``evidence_emission``/``qualification_record``/
    ``attempt_record`` bundle itself, so it can never be satisfied merely by
    that bundle's own internal consistency. ``gate_statuses`` alone already
    guarantees divergence between a scrub-refused attempt and a successful
    one -- ``gate_statuses[EVIDENCE_SAFETY]`` is set to a materially
    different literal status for each (see ``_fail_status``/``_pass`` at the
    ``EVIDENCE_SAFETY`` gate below) -- but the full set is included so a
    borrowed bundle cannot be reattached to a result whose OUTCOME differs in
    any of these dimensions either.

    Genuine construction always passes real enum members here, but this
    function is also reachable from ``SemanticTaskAttemptResult.__post_init__``
    BEFORE that field's own type is otherwise validated in the general
    (non-``SEND_STATE_INDETERMINATE``) case -- so a malformed/forged
    ``run_validity``/``autonomous_classification``/``diagnostic_subclassification``
    (e.g. a plain string substituted via ``replace()``) must never crash this
    function; :func:`_safe_enum_value` renders it as a value that simply
    cannot equal any GENUINE enum's own ``.value``, which is exactly the
    correct (divergent, never falsely-matching) outcome.
    """

    def _safe_enum_value(value: object) -> object:
        if value is None:
            return None
        rendered = getattr(value, "value", None)
        if isinstance(rendered, (str, int, float, bool)):
            return rendered
        return repr(value)

    canonical = json.dumps(
        {
            "gate_statuses": dict(gate_statuses),
            "dispatch_state": _safe_enum_value(dispatch_state),
            "semantic_prompts_sent": semantic_prompts_sent,
            "run_validity": _safe_enum_value(run_validity),
            "scoring_eligible": scoring_eligible,
            "autonomous_classification": _safe_enum_value(autonomous_classification),
            "diagnostic_subclassification": _safe_enum_value(diagnostic_subclassification),
            "verification_passed": verification_passed,
        },
        sort_keys=True,
        default=repr,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _require_evidence_emission_field_shape(
    *,
    emitted: object,
    refused: object,
    path: object,
    scrub_checked: object,
    clean: object,
    findings: object,
    attempt_authority_token: object = None,
) -> None:
    """The full field-shape contract EVERY :class:`EvidenceEmission` instance
    must satisfy, genuine or not. Shared by the public constructor's
    ``__post_init__`` AND the one genuine, bypass-minted success path inside
    :func:`run_semantic_task_attempt`, so neither can drift from the other.

    ``attempt_authority_token`` is ``None`` for every instance built through
    the class's own public constructor (5F3B-Q1-PRE1-FU2A-FU1A-FU1) -- only
    ``run_semantic_task_attempt``'s internal minting bypass ever sets a real
    one, so a ``None`` value here can never satisfy the pairing check in
    ``SemanticTaskAttemptResult.__post_init__``.
    """
    require_exact_bool("EvidenceEmission.emitted", emitted)
    require_exact_bool("EvidenceEmission.refused", refused)
    require_exact_bool("EvidenceEmission.scrub_checked", scrub_checked)
    require_exact_bool("EvidenceEmission.clean", clean)
    if attempt_authority_token is not None and (
        not isinstance(attempt_authority_token, str) or not attempt_authority_token
    ):
        raise ValueError(
            "EvidenceEmission.attempt_authority_token must be None or a non-blank str"
        )
    if not isinstance(path, str) or not path:
        raise ValueError("EvidenceEmission.path must be a non-blank str")
    if not isinstance(findings, tuple) or not all(
        isinstance(entry, str) for entry in findings
    ):
        raise ValueError("EvidenceEmission.findings must be a tuple of str")
    if refused == clean:
        raise ValueError(
            "EvidenceEmission: a refused emission is exactly an unclean scrub, "
            "and a clean scrub is exactly a non-refused emission"
        )
    # 5F3B-Q1-PRE1-FU2A: both of `emit_evidence_or_refuse`'s own return
    # shapes always carry `emitted=True` and `scrub_checked=True` -- it
    # never returns any other combination (a write failure raises instead of
    # returning). Neither field is EVER genuinely False.
    if not emitted:
        raise ValueError(
            "EvidenceEmission.emitted must be True -- a real evidence emission "
            "always completed a write attempt; False can never describe a "
            "genuine outcome"
        )
    if not scrub_checked:
        raise ValueError(
            "EvidenceEmission.scrub_checked must be True -- a real evidence "
            "emission is always scrub-checked before either branch returns"
        )
    if refused is False and findings:
        raise ValueError(
            "EvidenceEmission: a non-refused (successful) emission must carry "
            "no scrub findings"
        )


@dataclass(frozen=True)
class EvidenceEmission:
    """The NARROW typed projection of one evidence-emission outcome.

    DESIGN-FU1 Sec. 9.4.2 names this the preferred shape over re-exposing
    ``safety.emit_evidence_or_refuse``'s raw return object by reference: the
    ON-DISK artifact is the actual evidence, and this is only the bounded
    in-memory statement of what happened to it. ``findings`` is a tuple of
    bounded finding CODES -- never a needle, never a value, and never a
    mutable list.

    This is the field the sweep's hard-bar projection reads for H-14
    (``artifact_scrub_passed``); it cannot be mutated after construction, so
    that fact can no longer drift from the immutable file it describes.

    5F3B-Q1-PRE1-FU2A-FU1A -- **the public constructor can NEVER produce a
    successful (``refused=False``) instance, under ANY arguments.**
    Independent review proved the FU2A-FU1 ``_issuance`` sentinel field
    still forgeable: ``EvidenceEmission(..., refused=False, ...,
    _issuance=object())`` satisfied the old ``self._issuance is not None``
    check, because ANY non-``None`` object -- not one specific, unobtainable
    value -- passed it. There is no field, sentinel, or token value left to
    steal: ``__post_init__`` below refuses ``refused=False``
    UNCONDITIONALLY, for every call that reaches it through this class's own
    ``__init__``.

    The ONE genuine success instance is minted a completely DIFFERENT way,
    by a function nested inside :func:`run_semantic_task_attempt` (never a
    module attribute, never importable): via ``object.__new__(EvidenceEmission)``
    plus ``object.__setattr__`` for each field, which bypasses ``__init__``/
    ``__post_init__`` entirely -- the identical technique this package's own
    frozen dataclasses already use internally (e.g. deep-immutability
    freezing) to populate a frozen instance without going through its public
    constructor. That bypass path still runs the FULL field-shape contract
    (:func:`_require_evidence_emission_field_shape`, shared with
    ``__post_init__``) before minting, so it can never mint a malformed
    instance either -- only the "``refused=False`` is unconditionally
    refused" rule is specific to the public path.

    5F3B-Q1-PRE1-FU2A-FU1A-FU1 -- **``attempt_authority_token`` binds a
    genuine instance to the ONE attempt it was minted for.** Independent
    review proved that unforgeability as a class instance was not enough: a
    caller cannot construct a NEW successful ``EvidenceEmission``, but it did
    not need to -- it could REPLAY a genuine successful instance minted for a
    DIFFERENT attempt (a different run, task, or candidate) by attaching it
    to a result whose own ``path``/``refused`` projection was forged to
    match. ``attempt_authority_token`` is a fresh, random, per-attempt value
    minted once inside :func:`run_semantic_task_attempt` and threaded into
    BOTH this instance and that SAME call's ``identity_provenance``
    (:class:`_AttemptIdentityProvenance`); ``SemanticTaskAttemptResult.__post_init__``
    requires the two tokens to agree exactly. A replayed emission from
    another attempt carries a DIFFERENT token (freshly, randomly minted per
    call), so the pairing disagrees and construction is refused -- even
    though the emission and the projection it is attached to agree with each
    other. ``None`` on the public path (5F3B-Q1-PRE1-FU2A-FU1A-FU1's own
    ``_require_evidence_emission_field_shape`` change): only the internal
    minting bypass ever sets a real token, so a caller-built instance can
    never satisfy the pairing check.
    """

    emitted: bool
    refused: bool
    path: str
    scrub_checked: bool
    clean: bool
    findings: tuple[str, ...]
    attempt_authority_token: str | None = None

    def __post_init__(self) -> None:
        _require_evidence_emission_field_shape(
            emitted=self.emitted,
            refused=self.refused,
            path=self.path,
            scrub_checked=self.scrub_checked,
            clean=self.clean,
            findings=self.findings,
            attempt_authority_token=self.attempt_authority_token,
        )
        if self.refused is False:
            raise ValueError(
                "EvidenceEmission: its own public constructor can NEVER produce a "
                "successful (refused=False) instance, under any arguments -- H-14 "
                "success requires a real emit/scrub/write, established only "
                "through run_semantic_task_attempt's own internal, unimportable "
                "minting path"
            )


class ReportAvailability(str, Enum):
    """Whether the model's OPTIONAL, UNTRUSTED final report could be used.

    DESIGN-FU1 Sec. 9.3.3. A closed three-value classification that is
    **orthogonal to ``failed_gate``**: none of these values may change
    repository truth, verification truth, scope truth, ``run_validity``,
    ``scoring_eligible``, or any of the hard bar's H-1..H-9 conjunctive
    checks. Their ONLY effect is whether report accuracy is evaluable at
    all.
    """

    #: A well-typed, session-matched observation whose claims were compared.
    AVAILABLE = "AVAILABLE"
    #: The harness could not collect it -- the adapter raised, or returned
    #: the wrong type.
    UNAVAILABLE = "UNAVAILABLE"
    #: A well-typed observation that is nonetheless unusable -- it answers a
    #: foreign session, or its claims failed bounded parsing/comparison.
    MALFORMED = "MALFORMED"


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


#: DESIGN-FU1 Sec. 9.1.5: the ONE fixed reason recorded wherever a frozen
#: 0/1 classifier could not truthfully be called for this attempt. Imported
#: from the attempt-artifact module so the controller and the artifact can
#: never drift into two wordings for the identical honest gap.
WORKSPACE_REMOVAL_CLASSIFICATION_UNAVAILABLE_REASON = CLASSIFICATION_UNAVAILABLE_REASON


def workspace_removal_succeeded(result: object) -> bool:
    """Strict, fail-CLOSED validation of the frozen
    ``ar2.fixtures.remove_disposable_tree`` return shape, as returned
    unmodified by ``i2b_workspace.remove_run_workspace``.

    **This is the identical predicate ``run_i2b_live._workspace_removal_succeeded``
    already applies to Category-B's own outer cleanup** (DESIGN-FU1
    Sec. 9.1.4 freezes it verbatim, because it is the same frozen return
    shape, not a new one). A normal return does NOT mean removal succeeded:
    the frozen contract can return, without raising,
    ``{"removed": False, "residual_file_count": N, "verified": True}`` --
    where ``verified=True`` means only that the postcondition was inspected
    truthfully, never that removal happened.

    The ONLY shape accepted as success is the frozen success shape exactly::

        {"removed": True, "residual_file_count": 0, "verified": True}

    Every other shape fails CLOSED: a non-dict, a missing key, ``removed``
    or ``verified`` not exactly the ``True`` singleton (a truthy non-bool
    like the string ``"true"`` is rejected), or ``residual_file_count`` not
    exactly the ``int`` ``0``. ``bool`` is deliberately excluded even though
    it is an ``int`` subclass, since ``type(x) is int`` is ``False`` for a
    ``bool``. No ``bool(result)``, no ``.get(...)`` default substitution,
    and no reliance on a field's absence to mean success.
    """
    if type(result) is not dict:
        return False
    if not {"removed", "residual_file_count", "verified"} <= result.keys():
        return False
    if result["removed"] is not True:
        return False
    if result["verified"] is not True:
        return False
    residual = result["residual_file_count"]
    if type(residual) is not int or residual != 0:
        return False
    return True


def _bounded_removal_facts(result: object) -> dict[str, Any]:
    """A bounded projection of a removal result. Never raw adapter text.

    The frozen success/failure dicts carry no path, token or output text --
    only two bools and one int -- so those three values are retained
    verbatim. Anything else about the returned object is reduced to the
    single bool ``result_shape_recognized``: a malformed result must never
    be able to inject arbitrary content into a retained artifact.
    """

    def _exact_bool(value: object) -> bool | None:
        return value if type(value) is bool else None

    def _exact_int(value: object) -> int | None:
        return value if type(value) is int else None

    if type(result) is not dict:
        return {
            "result_shape_recognized": False,
            "removed": None,
            "residual_file_count": None,
            "verified": None,
        }
    return {
        "result_shape_recognized": (
            {"removed", "residual_file_count", "verified"} <= result.keys()
        ),
        "removed": _exact_bool(result.get("removed")),
        "residual_file_count": _exact_int(result.get("residual_file_count")),
        "verified": _exact_bool(result.get("verified")),
    }


@dataclass(frozen=True)
class SemanticWorkspaceRemovalStatus:
    """Whether this attempt's OWN semantic workspace was removed, and proven so.

    DESIGN-FU1 Sec. 9.1. The attempt owns its
    :class:`~qualification.i2b_workspace.QualificationRunWorkspace` from the
    instant ``mint_qualification_run_workspace()`` returns inside its own
    call to :func:`run_semantic_task_attempt`; ownership implies exactly one
    obligation, which is that this attempt and no other code removes it.
    Before FU2, the controller never called removal at all, so every
    attempt -- pass, fail, or indeterminate -- left its disposable Git
    fixture tree on disk indefinitely.

    ``verified`` is the strict :func:`workspace_removal_succeeded`
    predicate, never truthiness and never "the call did not raise". A raised
    ``remove_run_workspace`` is ``attempted=True, verified=False`` --
    reported, never swallowed, and never allowed to skip the evidence
    construction that follows it.

    ``classification_unavailable_reason`` mirrors
    :class:`SemanticCleanupStatus`'s own honest gap exactly: when this
    attempt's dispatch send state was mechanically indeterminate, no 0/1
    classification is fabricated for a removal failure either.
    """

    attempted: bool
    verified: bool
    facts: Mapping[str, Any] | None
    semantic_prompts_sent: int | None
    classification_unavailable_reason: str | None

    def __post_init__(self) -> None:
        require_exact_bool("SemanticWorkspaceRemovalStatus.attempted", self.attempted)
        require_exact_bool("SemanticWorkspaceRemovalStatus.verified", self.verified)
        if self.semantic_prompts_sent is not None and (
            type(self.semantic_prompts_sent) is not int
            or self.semantic_prompts_sent not in (0, 1)
        ):
            raise ValueError(
                "SemanticWorkspaceRemovalStatus.semantic_prompts_sent must be 0, 1, "
                "or None (an indeterminate dispatch send-state)"
            )
        if not self.attempted:
            if self.verified or self.facts is not None:
                raise ValueError(
                    "SemanticWorkspaceRemovalStatus: attempted=False carries no "
                    "removal facts and is never 'verified'"
                )
            if self.classification_unavailable_reason is not None:
                raise ValueError(
                    "SemanticWorkspaceRemovalStatus: attempted=False carries no "
                    "unavailable-classification reason"
                )
            return
        if self.verified:
            if self.classification_unavailable_reason is not None:
                raise ValueError(
                    "SemanticWorkspaceRemovalStatus: a verified removal carries no "
                    "unavailable-classification reason"
                )
        elif self.semantic_prompts_sent is None:
            if (
                self.classification_unavailable_reason
                != WORKSPACE_REMOVAL_CLASSIFICATION_UNAVAILABLE_REASON
            ):
                raise ValueError(
                    "SemanticWorkspaceRemovalStatus: a removal failure under an "
                    "indeterminate dispatch must record the fixed unavailable-"
                    "classification reason, never a fabricated classification"
                )
        elif self.classification_unavailable_reason is not None:
            raise ValueError(
                "SemanticWorkspaceRemovalStatus: a determinate dispatch state has no "
                "unavailable-classification reason"
            )
        if self.facts is not None and not isinstance(self.facts, Mapping):
            raise ValueError(
                "SemanticWorkspaceRemovalStatus.facts must be a Mapping or None"
            )
        if self.facts is not None:
            object.__setattr__(self, "facts", freeze_mapping(self.facts))

    @property
    def closure_satisfied(self) -> bool:
        """Nothing to remove is satisfied; an unproven removal never is."""
        if not self.attempted:
            return True
        return self.verified

    @property
    def status_text(self) -> str:
        if not self.attempted:
            return _STATUS_NOT_REQUIRED
        if self.verified:
            return "VERIFIED_REMOVED"
        if self.semantic_prompts_sent is None:
            return (
                "FAILED:"
                f"{SemanticFailureCode.SEMANTIC_WORKSPACE_REMOVAL_UNVERIFIED_INDETERMINATE_DISPATCH.value}"
            )
        return f"FAILED:{SemanticFailureCode.SEMANTIC_WORKSPACE_REMOVAL_UNVERIFIED.value}"


def _remove_semantic_workspace(
    run_workspace: QualificationRunWorkspace | None,
    *,
    semantic_prompts_sent: int | None,
) -> SemanticWorkspaceRemovalStatus:
    """Remove this attempt's own workspace, exactly once, and PROVE it.

    Delegates to the frozen, unmodified
    :func:`qualification.i2b_workspace.remove_run_workspace` -- itself a
    pass-through to the frozen ``ar2.fixtures.remove_disposable_tree``. This
    function adds only the two things Sec. 9.1.4 requires and the frozen
    helper deliberately does not do for its caller: the strict acceptance
    predicate, and the ``try``/``except Exception`` that turns a raised
    removal into a recorded ``attempted=True, verified=False`` rather than
    an escape that would skip evidence construction entirely.
    """
    unavailable = (
        WORKSPACE_REMOVAL_CLASSIFICATION_UNAVAILABLE_REASON
        if semantic_prompts_sent is None
        else None
    )
    if run_workspace is None:
        return SemanticWorkspaceRemovalStatus(
            attempted=False,
            verified=False,
            facts=None,
            semantic_prompts_sent=semantic_prompts_sent,
            classification_unavailable_reason=None,
        )
    try:
        result = remove_run_workspace(run_workspace)
    except Exception:  # noqa: BLE001 - reported truthfully, never swallowed
        return SemanticWorkspaceRemovalStatus(
            attempted=True,
            verified=False,
            facts=_bounded_removal_facts(None),
            semantic_prompts_sent=semantic_prompts_sent,
            classification_unavailable_reason=unavailable,
        )
    verified = workspace_removal_succeeded(result)
    return SemanticWorkspaceRemovalStatus(
        attempted=True,
        verified=verified,
        facts=_bounded_removal_facts(result),
        semantic_prompts_sent=semantic_prompts_sent,
        classification_unavailable_reason=None if verified else unavailable,
    )


def build_run_safety_context(
    *,
    secret_context: QualificationRouteSecretContext | None,
    broker_session: BrokerSession | None,
    run_workspace: QualificationRunWorkspace | None,
    route_descriptor: RouteDescriptor | None,
) -> ArtifactSafetyContext:
    """Build the run's FULL artifact safety context, FIELD-INDEPENDENTLY.

    **5F3B-Q1-PRE1-FU2 / DESIGN-FU1 Sec. 9.2.** The pre-FU2 version returned
    ``ArtifactSafetyContext.none_declared()`` whenever ``secret_context`` was
    ``None``, which happened to be correct only because
    ``run_semantic_task_attempt``'s linear gate order puts ``SECRET_CONTEXT``
    strictly before ``BROKER_SESSION``. That made its correctness a fact
    about CALLER CONTROL FLOW rather than about the function -- and a real,
    already-minted workspace needle was droppable even today, since
    ``WORKSPACE_AUTHORITY`` runs strictly BEFORE ``SECRET_CONTEXT``. A
    future refactor, a caught-and-recovered secret-context failure, or a
    second call site would silently reintroduce the exact I2B-FU1 defect
    this rule exists to close.

    The frozen rule, restated as the per-field rule this function now
    implements -- the presence or absence of ANY one field's source object
    never gates whether ANOTHER field's source object is consulted:

    ===========================  ==========================================
    ``workspace_absolute_path``  whenever ``run_workspace is not None``
    ``broker_token``             whenever ``broker_session is not None``
    ``pipe_name``                whenever ``broker_session is not None``
    ``capability_id``            whenever ``broker_session is not None``
    ``endpoint_host``            whenever ``secret_context is not None``
    ``api_key``                  whenever ``secret_context is not None``
    ``bearer_token``             DERIVED -- see below
    ===========================  ==========================================

    **The workspace needle is the EXPERIMENT ROOT, deliberately** -- the
    identical reasoning ``i2b_controller.build_run_safety_context`` already
    records: the repository root and the generated-config directory both sit
    strictly beneath it, and ``ar2.record.scrub_check`` matches substrings,
    so the enclosing root is a strictly stronger needle drawn from the same
    one verified workspace identity.

    **``bearer_token`` is DERIVED, not defaulted.** This route's frozen
    credential mechanism is
    ``i2_route.CREDENTIAL_MECHANISM == "models_json_env_interpolation"``: the
    credential travels as the generated ``models.json`` env interpolation of
    the one child carrier, and no separate bearer value is ever minted. The
    previously-unused ``route_descriptor`` parameter now has exactly this
    job -- it is asserted, and an unexpected mechanism REFUSES safety-context
    construction (:class:`SemanticSafetyContextError`) rather than silently
    defaulting ``bearer_token`` to ``None``. ``RouteDescriptor.__post_init__``
    already refuses any other mechanism at construction, so this is currently
    unreachable in practice; the contract exists so it stays refused, not
    silently accepted, the day a second mechanism is added.

    ``ArtifactSafetyContext.none_declared()`` is returned ONLY for the true
    all-absent case -- never while any of ``secret_context``,
    ``broker_session`` or ``run_workspace`` is non-``None``.
    """
    if route_descriptor is not None:
        if type(route_descriptor) is not RouteDescriptor:
            raise SemanticSafetyContextError("ROUTE_DESCRIPTOR_TYPE_UNEXPECTED")
        if route_descriptor.credential_mechanism != CREDENTIAL_MECHANISM:
            raise SemanticSafetyContextError("UNEXPECTED_CREDENTIAL_MECHANISM")

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
    if broker_session is None and run_workspace is None:
        return ArtifactSafetyContext.none_declared()
    return ArtifactSafetyContext(
        endpoint_host=None,
        api_key=None,
        bearer_token=None,
        broker_token=broker_token,
        pipe_name=pipe_name,
        capability_id=capability_id,
        workspace_absolute_path=workspace_absolute_path,
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


def _project_report_accuracy(
    comparisons: tuple[ClaimComparison, ...],
    *,
    availability: "ReportAvailability | None",
) -> dict[str, Any]:
    """A bounded projection of the OPTIONAL, UNTRUSTED report layer.

    DESIGN-FU1 Sec. 9.3.3: an ``UNAVAILABLE``/``MALFORMED`` report is
    recorded here as a purely DESCRIPTIVE not-evaluable fact -- it is never
    scored, never fed to the hard bar (``report_accuracy`` is not one of the
    H-1..H-9 checks, and this contract keeps it that way), and never allowed
    to change ``run_validity`` or ``scoring_eligible``. The bounded
    ``reason`` distinguishes "the harness could not collect it" from "the
    model produced nothing usable", which the pre-FU2 ``{"attempted": False}``
    shape could not say at all.
    """
    if availability is None:
        # Collection was never reached (a pre-prompt refusal, or a failure
        # before the post-turn gates). "AIDO never asked" is a different
        # fact from "AIDO asked and got nothing usable", and this shape --
        # the pre-FU2 one -- is the truthful one for it.
        return {"attempted": False}
    if availability is not ReportAvailability.AVAILABLE:
        return {
            "attempted": True,
            "available": False,
            "reason": availability.value,
        }
    if not comparisons:
        return {"attempted": False}
    bucket = bucket_report_accuracy(comparisons)
    return {
        "attempted": True,
        "available": True,
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

    **5F3B-Q1-PRE1-FU2 (invariant I-1).** This signal is now raised from
    inside the PHASE 1 block and NOWHERE ELSE. That is the mechanical half
    of monotonicity: once phase 1 establishes ``CONFIRMED_SENT``, no phase-2
    outcome, no broker/repository/verification/report failure, and no
    closure failure can reach this handler, so none of them can move
    ``semantic_prompts_sent`` back off ``1``. It carries the bounded
    :class:`~qualification.semantic_session.SemanticDispatchEvidenceCode`
    that establishes WHICH mechanical fact left the send state unknown.
    """

    def __init__(self, evidence_code: SemanticDispatchEvidenceCode) -> None:
        super().__init__(evidence_code.value)
        self.evidence_code = evidence_code


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
class _AttemptIdentityProvenance:
    """An unforgeable proof of WHICH candidate/task this attempt's identity
    actually is -- never constructible through its own public constructor.

    5F3B-Q1-PRE1-FU2A-FU1A. Independent review proved FU2A-FU1's identity
    check -- comparing ``self.candidate``/etc. against a plain string copy
    embedded in ``qualification_record``/``attempt_record`` -- insufficient:
    both copies are ordinary caller-editable dataclass/dict fields, so a
    caller can relabel BOTH together
    (``replace(result, candidate="B", ..., qualification_record=forged)``)
    and the two agree with each other while both lying.

    The fix is the SAME pattern already accepted for :class:`EvidenceEmission`'s
    own success state, applied to identity instead: this type's
    ``__post_init__`` unconditionally refuses ANY construction attempt
    through its own public constructor, so a caller can never build a NEW
    instance of this type at all, forged or otherwise. The ONE genuine
    instance -- proving the actual candidate/model/task/revision this
    attempt was minted for -- is created by a function nested inside
    :func:`run_semantic_task_attempt`, bypassing ``__init__``/``__post_init__``
    via ``object.__new__``, from the SAME trusted local variables used to
    build the attempt itself.

    ``SemanticTaskAttemptResult.__post_init__`` requires
    ``self.identity_provenance``'s own embedded fields to agree with
    ``self.candidate``/etc. A plain field-level relabel changes only the
    OUTER fields; ``dataclasses.replace()`` leaves ``identity_provenance``
    itself untouched (the SAME already-genuine instance, still naming the
    ORIGINAL candidate/task) unless the caller also overrides it -- and
    overriding it requires constructing a NEW instance of this type, which
    its own constructor unconditionally refuses.

    5F3B-Q1-PRE1-FU2A-FU1A-FU1 -- **``attempt_authority_token`` binds this
    instance to the ONE attempt it was minted for, not merely to the
    candidate/model/task/revision VALUE TUPLE it carries.** Independent
    review proved the FU2A-FU1A field-tuple check insufficient: a caller
    cannot forge a NEW ``_AttemptIdentityProvenance``, but it did not need
    to -- it could take a GENUINE instance minted for a DIFFERENT result
    (another run of the same candidate/task, another task, or another
    candidate) and attach it to a result whose OUTER
    candidate/model_id/task_id/task_revision were relabelled to match that
    instance's own tuple. Two genuine instances of the same
    candidate/task pair (e.g. two separate runs of Candidate B on IQ-1)
    carry EQUAL field values but are minted by DIFFERENT calls, so a
    value-tuple check alone cannot tell them apart. ``attempt_authority_token``
    is a fresh, random value minted once per :func:`run_semantic_task_attempt`
    call and shared with that SAME call's ``evidence_emission``
    (:class:`EvidenceEmission`); ``SemanticTaskAttemptResult.__post_init__``
    requires the two tokens to agree exactly whenever an evidence emission
    is present, so a provenance instance minted for one attempt can never
    back a different attempt's retained evidence.
    """

    candidate: str
    model_id: str
    task_id: str
    task_revision: str
    attempt_authority_token: str

    def __post_init__(self) -> None:
        raise ValueError(
            "_AttemptIdentityProvenance can never be constructed through its own "
            "public constructor, under any arguments -- it is minted only by "
            "run_semantic_task_attempt's own internal, unimportable bypass"
        )


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
    #: 5F3B-Q1-PRE1-FU2A-FU1A. An unforgeable proof of WHICH
    #: candidate/model/task/revision this attempt's identity actually is,
    #: minted only by ``run_semantic_task_attempt``'s own internal bypass --
    #: see :class:`_AttemptIdentityProvenance`'s own docstring for why a
    #: plain string comparison (FU2A-FU1's own fix) was insufficient.
    identity_provenance: _AttemptIdentityProvenance
    #: ``None`` iff ``dispatch_state`` is ``SEND_STATE_INDETERMINATE``
    #: (5F3B-Q1-PRE1-FU1) -- never coerced to 0 or 1 for an unestablished fact.
    semantic_prompts_sent: int | None
    #: The mechanically-established send/no-send fact for this attempt's ONE
    #: dispatch (5F3B-Q1-PRE1-FU1). ``CONFIRMED_NOT_SENT`` by default for any
    #: attempt that never reached the dispatch gate at all -- structurally
    #: the strongest form of "not sent" (never even attempted).
    dispatch_state: SemanticPromptDispatchState
    #: WHICH mechanical fact established ``dispatch_state`` (DESIGN-FU1
    #: Sec. 2.3). Audit-only: nothing branches on it.
    dispatch_evidence_code: SemanticDispatchEvidenceCode
    #: Whether PHASE 1 was actually entered -- i.e. the dispatch adapter was
    #: invoked. This, not a guessed prompt count, is what the sweep's
    #: ``semantic_dispatch_attempts`` budget counts (DESIGN-FU1 Sec. 4).
    semantic_dispatch_attempted: bool
    #: PHASE 2's three-valued terminal outcome, or ``None`` when phase 2 was
    #: never entered (which is every non-``CONFIRMED_SENT`` dispatch).
    turn_outcome: SemanticTurnOutcome | None
    #: An INDEPENDENT, non-completion fact. Never upgrades an outcome.
    agent_end_observed: bool
    #: The bounded availability of the OPTIONAL, UNTRUSTED final report, or
    #: ``None`` when collection was never reached at all (a pre-prompt
    #: refusal, or any failure before the post-turn gates). Never gating
    #: (DESIGN-FU1 Sec. 9.3). ``None`` and ``UNAVAILABLE`` are deliberately
    #: distinct: "AIDO never asked" is not "AIDO asked and got nothing".
    report_availability: ReportAvailability | None
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
    #: This attempt's OWN workspace-removal truth (DESIGN-FU1 Sec. 9.1),
    #: established BEFORE any evidence was constructed or emitted.
    workspace_removal: SemanticWorkspaceRemovalStatus
    #: An immutable projection of the primary-record emission outcome, or
    #: ``None`` for an indeterminate dispatch (which emits the sibling
    #: attempt artifact instead). Deeply frozen -- see Sec. 9.4.
    qualification_record: Mapping[str, Any] | None
    #: The same, for the ``pi-implementer-qualification-attempt.v1``
    #: artifact. Exactly one of these two is non-``None`` for any INVOKED
    #: attempt whose safety context was provable (Sec. 3.F).
    attempt_record: Mapping[str, Any] | None
    #: The NARROW typed projection of whichever of the two was emitted --
    #: this is what the hard bar's ``artifact_scrub_passed`` reads.
    evidence_emission: EvidenceEmission | None

    def __post_init__(self) -> None:
        # 5F3B-Q1-PRE1-FU2A: mechanically bind identity BEFORE anything else
        # is checked. Independent review reproduced a "result identity
        # substitution" bypass: `dataclasses.replace` (or direct
        # construction) could relabel a genuine A run's facts as Candidate
        # B's, mismatch candidate/model, or attach a task_revision that
        # merely shares a task's prefix rather than being that frozen
        # task's own exact revision. None of that was previously refused
        # here -- only `PrimarySweepResult`'s OWN `task_id` key check caught
        # a narrower slice of it.
        from .corpus import TASKS_BY_ID

        if self.candidate not in CANDIDATE_MODEL_IDS:
            raise ValueError(
                f"SemanticTaskAttemptResult.candidate must be one of "
                f"{sorted(CANDIDATE_MODEL_IDS)}; got {self.candidate!r}"
            )
        if self.model_id != CANDIDATE_MODEL_IDS[self.candidate]:
            raise ValueError(
                "SemanticTaskAttemptResult.model_id does not match "
                f"candidate {self.candidate!r}'s frozen pairing "
                f"{CANDIDATE_MODEL_IDS[self.candidate]!r} -- a cross-candidate "
                "relabelling is refused"
            )
        frozen_task = TASKS_BY_ID.get(self.task_id)
        if frozen_task is None:
            raise ValueError(
                f"SemanticTaskAttemptResult.task_id {self.task_id!r} is not one of "
                "the frozen qualification.corpus tasks"
            )
        if self.task_revision != frozen_task.task_revision:
            raise ValueError(
                "SemanticTaskAttemptResult.task_revision does not equal task "
                f"{self.task_id!r}'s own frozen revision -- a revision that merely "
                "shares the task's id prefix is refused, never accepted as "
                "equivalent"
            )
        # 5F3B-Q1-PRE1-FU2A-FU1A: bind identity to MECHANICALLY ISSUED
        # provenance, not merely to a second caller-editable copy. Independent
        # review proved the FU2A-FU1 fix (comparing against a plain string
        # embedded in qualification_record/attempt_record) insufficient: a
        # caller can relabel BOTH the top-level fields AND that embedded copy
        # together, consistently. `identity_provenance` can only ever be a
        # genuine `_AttemptIdentityProvenance` -- its own constructor
        # unconditionally refuses construction, so a caller cannot mint a
        # matching forged one no matter what they change here.
        if type(self.identity_provenance) is not _AttemptIdentityProvenance:
            raise ValueError(
                "SemanticTaskAttemptResult.identity_provenance must be exactly a "
                "genuine _AttemptIdentityProvenance"
            )
        if (
            self.identity_provenance.candidate,
            self.identity_provenance.model_id,
            self.identity_provenance.task_id,
            self.identity_provenance.task_revision,
        ) != (self.candidate, self.model_id, self.task_id, self.task_revision):
            raise ValueError(
                "SemanticTaskAttemptResult: this result's own "
                "candidate/model_id/task_id/task_revision disagrees with the "
                "mechanically issued identity_provenance it was minted with -- a "
                "post-construction identity relabel is refused, even when the "
                "artifact projection is relabelled to match"
            )
        # 5F3B-Q1-PRE1-FU2A-FU1A-FU1: bind identity_provenance to THIS
        # attempt's own retained evidence, not merely to the candidate/
        # model/task/revision VALUE TUPLE it carries. Independent review
        # reproduced two supported replays that the tuple check alone could
        # not catch, because both sides of each replay are GENUINE objects
        # that agree with each other:
        #   (a) a genuine successful EvidenceEmission minted for a DIFFERENT
        #       attempt, attached to a result whose own path/refused
        #       projection was forged to match it -- H-14 authority replay;
        #   (b) a genuine _AttemptIdentityProvenance minted for a DIFFERENT
        #       result (another run of the same candidate/task, another
        #       task, or another candidate), attached to a result whose
        #       outer candidate/model_id/task_id/task_revision were
        #       relabelled to match its tuple -- identity provenance replay.
        # `attempt_authority_token` is a fresh, random value minted exactly
        # once per `run_semantic_task_attempt` call and shared between that
        # SAME call's `identity_provenance` and `evidence_emission`. Neither
        # value can be forged (both types unconditionally refuse public
        # construction of a genuine/successful instance), so the only way to
        # make the tokens agree is to use the identity_provenance and the
        # evidence_emission this SAME call actually minted together -- a
        # replay from any other call mints a DIFFERENT random token and the
        # pairing disagrees, even when every other check above passes.
        if (
            not isinstance(self.identity_provenance.attempt_authority_token, str)
            or not self.identity_provenance.attempt_authority_token
        ):
            raise ValueError(
                "SemanticTaskAttemptResult.identity_provenance.attempt_authority_token "
                "must be a non-blank str -- a genuinely minted provenance always "
                "carries one"
            )
        if self.evidence_emission is not None and (
            self.evidence_emission.attempt_authority_token
            != self.identity_provenance.attempt_authority_token
        ):
            raise ValueError(
                "SemanticTaskAttemptResult: evidence_emission.attempt_authority_token "
                "disagrees with identity_provenance.attempt_authority_token -- this "
                "evidence emission was not minted for this attempt's own identity, "
                "even though its path/refused projection agrees"
            )
        if type(self.dispatch_state) is not SemanticPromptDispatchState:
            raise ValueError(
                "SemanticTaskAttemptResult.dispatch_state must be exactly a "
                "SemanticPromptDispatchState"
            )
        if type(self.dispatch_evidence_code) is not SemanticDispatchEvidenceCode:
            raise ValueError(
                "SemanticTaskAttemptResult.dispatch_evidence_code must be exactly a "
                "SemanticDispatchEvidenceCode"
            )
        if (
            DISPATCH_EVIDENCE_CODE_STATES[self.dispatch_evidence_code]
            is not self.dispatch_state
        ):
            raise ValueError(
                "SemanticTaskAttemptResult: dispatch_evidence_code establishes a "
                "different dispatch_state than this result reports"
            )
        require_exact_bool(
            "SemanticTaskAttemptResult.semantic_dispatch_attempted",
            self.semantic_dispatch_attempted,
        )
        require_exact_bool(
            "SemanticTaskAttemptResult.agent_end_observed", self.agent_end_observed
        )
        # 5F3B-Q1-PRE1-FU2A-FU1: `scoring_eligible` is a hard-bar authority
        # fact (`_is_scorable` in `hard_bar.py` reads it directly) and must
        # therefore be exact bool, never truthiness -- `replace(result,
        # scoring_eligible="yes")` must fail HERE, before this result could
        # ever reach `_task_hard_bar_facts`.
        require_exact_bool("SemanticTaskAttemptResult.scoring_eligible", self.scoring_eligible)
        if self.report_availability is not None and (
            type(self.report_availability) is not ReportAvailability
        ):
            raise ValueError(
                "SemanticTaskAttemptResult.report_availability must be None or "
                "exactly a ReportAvailability"
            )
        # 5F3B-Q1-PRE1-FU2A: every optional-bool fact classification, the
        # hard bar and audit consume must be EXACT bool when present -- never
        # a truthy non-bool. Independent review reproduced
        # `dataclasses.replace(result, verification_passed="false")` reaching
        # `qualification.semantic_sweep._task_hard_bar_facts` unrefused,
        # where `bool("false")` silently became `True`. Refusing the
        # malformed fact HERE, at construction, is what makes it safe for
        # that projection to stop coercing at all.
        for _field_name in (
            "verification_passed",
            "expected_changed_paths_satisfied",
            "head_unchanged",
            "index_clean",
            "protected_witness_untouched",
            "no_unexpected_untracked_or_create_delete_rename",
            "broker_git_cross_check_agrees",
        ):
            _value = getattr(self, _field_name)
            if _value is not None and type(_value) is not bool:
                raise ValueError(
                    f"SemanticTaskAttemptResult.{_field_name} must be None or "
                    "exactly a bool -- a truthy non-bool (e.g. the string "
                    "'false') is refused, never coerced"
                )
        indeterminate = self.dispatch_state is SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
        confirmed_sent = self.dispatch_state is SemanticPromptDispatchState.CONFIRMED_SENT
        if self.turn_outcome is not None:
            if type(self.turn_outcome) is not SemanticTurnOutcome:
                raise ValueError(
                    "SemanticTaskAttemptResult.turn_outcome must be None or exactly a "
                    "SemanticTurnOutcome"
                )
            if not confirmed_sent:
                raise ValueError(
                    "SemanticTaskAttemptResult: a turn outcome exists only after the "
                    "dispatch was mechanically established as CONFIRMED_SENT -- phase 2 "
                    "is never entered otherwise"
                )
        if self.agent_end_observed and not confirmed_sent:
            raise ValueError(
                "SemanticTaskAttemptResult: an agent_end can only have been observed "
                "for a turn that was actually dispatched"
            )
        if not self.semantic_dispatch_attempted and (
            confirmed_sent
            or indeterminate
            or self.dispatch_evidence_code
            is not SemanticDispatchEvidenceCode.GATE_REFUSED_BEFORE_WRITE
        ):
            raise ValueError(
                "SemanticTaskAttemptResult: a dispatch state other than a gate refusal "
                "before the write requires that phase 1 was actually entered"
            )
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
        elif self.attempt_record is not None:
            raise ValueError(
                "SemanticTaskAttemptResult: the attempt-level artifact exists ONLY for "
                "a SEND_STATE_INDETERMINATE dispatch -- a determinate attempt emits a "
                "primary qualification record instead, never both"
            )
        if self.qualification_record is not None and self.attempt_record is not None:
            raise ValueError(
                "SemanticTaskAttemptResult: exactly one retained artifact per invoked "
                "attempt -- never both a primary record and an attempt artifact"
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
        if not isinstance(self.report_accuracy_comparisons, tuple) or not all(
            type(entry) is ClaimComparison for entry in self.report_accuracy_comparisons
        ):
            raise ValueError(
                "SemanticTaskAttemptResult.report_accuracy_comparisons must be a "
                "tuple of ClaimComparison -- never a mutable list a caller could "
                "still be holding"
            )
        if (
            self.report_accuracy_comparisons
            and self.report_availability is not ReportAvailability.AVAILABLE
        ):
            raise ValueError(
                "SemanticTaskAttemptResult: report comparisons exist only for an "
                "AVAILABLE report -- an unavailable or malformed report is not "
                "evaluable, and cannot carry a comparison"
            )
        if type(self.workspace_removal) is not SemanticWorkspaceRemovalStatus:
            raise ValueError(
                "SemanticTaskAttemptResult.workspace_removal must be a "
                "SemanticWorkspaceRemovalStatus"
            )
        if self.workspace_removal.semantic_prompts_sent != self.semantic_prompts_sent:
            raise ValueError(
                "SemanticTaskAttemptResult.workspace_removal.semantic_prompts_sent "
                "disagrees with this result's own semantic_prompts_sent"
            )
        if self.evidence_emission is not None:
            if type(self.evidence_emission) is not EvidenceEmission:
                raise ValueError(
                    "SemanticTaskAttemptResult.evidence_emission must be None or "
                    "exactly an EvidenceEmission"
                )
            projection = (
                self.qualification_record
                if self.qualification_record is not None
                else self.attempt_record
            )
            if projection is None:
                raise ValueError(
                    "SemanticTaskAttemptResult: an evidence_emission requires the "
                    "artifact projection it describes"
                )
            # 5F3B-Q1-PRE1-FU2A: exact type, never coerced. `bool(...)`/
            # `str(...)` would let a malformed projection value (e.g. the
            # string "false", which is truthy) silently pass as agreement
            # with a genuine bool/str fact -- a malformed projection is an
            # integrity failure, not a value to normalize.
            projected_refused = projection.get("refused")
            projected_path = projection.get("path")
            if type(projected_refused) is not bool or type(projected_path) is not str:
                raise ValueError(
                    "SemanticTaskAttemptResult: the artifact projection's own "
                    "'refused'/'path' fields must be exactly bool/str -- a "
                    "malformed projection is refused, never coerced into a "
                    "plausible fact"
                )
            if (
                projected_refused is not self.evidence_emission.refused
                or projected_path != self.evidence_emission.path
            ):
                raise ValueError(
                    "SemanticTaskAttemptResult: evidence_emission disagrees with the "
                    "artifact projection it is supposed to describe"
                )
            # 5F3B-Q1-PRE1-FU2A-FU1: bind identity to the PROVENANCE that
            # actually produced this attempt, not merely to an internally
            # self-consistent pair. `run_semantic_task_attempt` embeds this
            # attempt's candidate/model/task identity into `qualification_record`/
            # `attempt_record` from the SAME trusted local variables it uses
            # to build `self.candidate`/etc -- so genuine construction always
            # agrees. `dataclasses.replace(result, candidate="B",
            # model_id=CANDIDATE_MODEL_IDS["B"])` (or an equivalent
            # simultaneous task_id/task_revision relabel) only overrides the
            # TOP-LEVEL field; the embedded copy inside the immutable
            # projection is untouched and still names the genuine identity,
            # so the two disagree and this is refused.
            for _field_name, _projected_key in (
                ("candidate", "candidate"),
                ("model_id", "model_id"),
                ("task_id", "task_id"),
                ("task_revision", "task_revision"),
            ):
                _projected_value = projection.get(_projected_key)
                if type(_projected_value) is not str:
                    raise ValueError(
                        f"SemanticTaskAttemptResult: the artifact projection's own "
                        f"{_projected_key!r} must be exactly a str"
                    )
                if _projected_value != getattr(self, _field_name):
                    raise ValueError(
                        "SemanticTaskAttemptResult: this result's "
                        f"{_field_name}={getattr(self, _field_name)!r} disagrees with "
                        f"the identity ({_projected_value!r}) embedded in its own "
                        "retained artifact projection at construction time -- a "
                        "post-construction identity relabel is refused"
                    )
        elif self.qualification_record is not None or self.attempt_record is not None:
            raise ValueError(
                "SemanticTaskAttemptResult: a retained artifact requires its narrow "
                "typed evidence_emission projection"
            )
        # 5F3B-Q1-PRE1-FINAL-CLOSURE: consume THIS construction's ONE-SHOT
        # issuance. Independent review proved the fingerprint-equality-only
        # check (FU2A-FU1A-FU1-FU1) still insufficient: the fingerprint is
        # itself derived entirely from caller-replaceable fields, so a
        # `replace()` call that ALSO copies the foreign attempt's
        # `gate_statuses` (or whatever other fingerprinted field happens to
        # differ) reconstructs a fingerprint that matches the foreign
        # token's registered one. Enlarging the fingerprinted field set only
        # enlarges the set `replace()` can copy alongside it -- it cannot
        # close this. The actual fix: `identity_provenance.attempt_authority_token`
        # now authorizes AT MOST ONE `SemanticTaskAttemptResult` construction,
        # ever. `_consume_pending_attempt_authority` requires the token to be
        # CURRENTLY pending and the re-derived fingerprint to match, and
        # deletes the pending entry as part of that SAME atomic step
        # regardless of outcome -- so this call, successful or not, is the
        # LAST time this token can ever authorize a construction. A borrowed
        # bundle's token was already consumed by the FOREIGN attempt's own
        # genuine construction, so it is never even pending here.
        _authorized_facts_fingerprint_value = _authorized_facts_fingerprint(
            gate_statuses=self.gate_statuses,
            dispatch_state=self.dispatch_state,
            semantic_prompts_sent=self.semantic_prompts_sent,
            run_validity=self.run_validity,
            scoring_eligible=self.scoring_eligible,
            autonomous_classification=self.autonomous_classification,
            diagnostic_subclassification=self.diagnostic_subclassification,
            verification_passed=self.verification_passed,
        )
        _consume_pending_attempt_authority(
            self.identity_provenance.attempt_authority_token,
            _authorized_facts_fingerprint_value,
        )
        # -- DESIGN-FU1 Sec. 9.4: deep immutability, COPY BEFORE WRAPPING --
        # Every publicly reachable container is replaced, here, by a
        # read-only proxy over a private, recursively-immutable copy. The
        # dict a caller passed in stays theirs and is no longer reachable
        # through this result, so mutating it afterwards cannot change what
        # classification, the hard bar, ranking, evidence or audit reads.
        object.__setattr__(self, "gate_statuses", freeze_mapping(self.gate_statuses))
        if self.qualification_record is not None:
            object.__setattr__(
                self, "qualification_record", freeze_mapping(self.qualification_record)
            )
        if self.attempt_record is not None:
            object.__setattr__(
                self, "attempt_record", freeze_mapping(self.attempt_record)
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
    dispatch_semantic_prompt: Callable[
        [SemanticPromptRequest], SemanticPromptDispatchObservation
    ],
    observe_semantic_turn: Callable[[SemanticTurnRequest], SemanticTurnObservation],
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
    #: The matching bounded evidence code. A gate refusal before the write
    #: is the structurally strongest form of "not sent" and is the only
    #: state reachable without entering phase 1 at all.
    dispatch_evidence_code: SemanticDispatchEvidenceCode = (
        SemanticDispatchEvidenceCode.GATE_REFUSED_BEFORE_WRITE
    )
    dispatch_indeterminate = False
    semantic_dispatch_attempted = False
    dispatch_observation: SemanticPromptDispatchObservation | None = None
    turn_observation: SemanticTurnObservation | None = None
    #: ``None`` until the FINAL_REPORT_CLAIMS gate is actually reached --
    #: a run that never asked for a report must never be recorded as having
    #: asked and been given nothing.
    report_availability: ReportAvailability | None = None
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

        # ============ PHASE 1: SEMANTIC_PROMPT_DISPATCH ============
        # Exactly ONE dispatch, ever, for this attempt.
        #
        # 5F3B-Q1-PRE1-FU2 / DESIGN-FU1 Sec. 2. Dispatch and turn
        # observation are now TWO adapter calls, because Pi 0.84.4's own
        # seam has an acknowledgement boundary STRICTLY EARLIER than turn
        # completion: the correlated prompt response is emitted after
        # preflight and BEFORE agent start and any provider inference. FU1
        # collapsed the two into one whole-turn adapter, which made every
        # reachable post-acknowledgement failure -- protocol violation,
        # output cap, event cap, read error, early child exit, a phase-2
        # adapter bug, a wrong-type or foreign phase-2 result -- either a
        # fabricated deadline or an ERASURE of an already-established
        # CONFIRMED_SENT. Both were wrong, and the erasure was wrong in the
        # direction that matters most for fairness: it converted a KNOWN
        # SPENT prompt into an UNKNOWN one.
        #
        # `semantic_prompts_sent` is NEVER set before this point, and is set
        # to 1 in exactly ONE place below -- only once a returned,
        # well-typed, provenance-matched dispatch observation mechanically
        # establishes CONFIRMED_SENT. Calling the adapter establishes
        # nothing (invariant I-2). A raised exception, a wrong-type result,
        # or a result that does not provably answer THIS request is evidence
        # of NEITHER state and becomes SEND_STATE_INDETERMINATE via
        # `_DispatchIndeterminate` -- which the outer handler never folds
        # into `infrastructure_refusal` (that would falsely claim
        # CONFIRMED_NOT_SENT) or into a scored run (that would falsely claim
        # CONFIRMED_SENT).
        _current_gate = SemanticGateName.SEMANTIC_PROMPT_DISPATCH
        prompt_request = SemanticPromptRequest(
            run_id=run_id,
            runtime_session=runtime_session,
            task_id=task.task_id,
            task_revision=task.task_revision,
        )
        semantic_dispatch_attempted = True
        try:
            dispatch_observation = dispatch_semantic_prompt(prompt_request)
        except Exception:
            # Sec. 1.7: a raised write/flush does not tell AIDO how many
            # bytes reached the pipe, and a raised adapter cannot be
            # distinguished from "raised after the command already crossed
            # the boundary". Never guessed either way.
            raise _DispatchIndeterminate(
                SemanticDispatchEvidenceCode.ADAPTER_RAISED
            ) from None
        if type(dispatch_observation) is not SemanticPromptDispatchObservation:
            # A wrong type (a subclass included -- this is an exact-type
            # check) is equally not evidence of either state.
            raise _DispatchIndeterminate(
                SemanticDispatchEvidenceCode.OBSERVATION_MALFORMED_OR_FOREIGN
            )
        if not require_dispatch_matches_request(dispatch_observation, prompt_request):
            # An observation that does not provably answer THIS request
            # (different run/session/task/revision) cannot be trusted to
            # describe what happened to it, however internally coherent it
            # is on its own terms.
            raise _DispatchIndeterminate(
                SemanticDispatchEvidenceCode.OBSERVATION_MALFORMED_OR_FOREIGN
            )
        dispatch_state = dispatch_observation.dispatch_state
        dispatch_evidence_code = dispatch_observation.dispatch_evidence_code
        if dispatch_state is SemanticPromptDispatchState.SEND_STATE_INDETERMINATE:
            # A live adapter's own real seam may itself report this -- a
            # RETURNED value, never an exception. Honored identically, with
            # the adapter's own bounded evidence code preserved.
            raise _DispatchIndeterminate(dispatch_evidence_code)
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
        # semantic_prompts_sent to 1, it happens ONLY after that fact is
        # established, and it dominates every statement that follows --
        # invariant I-1, extended by Sec. 9.1.6 to workspace removal.
        semantic_prompts_sent = 1
        _pass(SemanticGateName.SEMANTIC_PROMPT_DISPATCH)

        # ============ PHASE 2: TURN_COMPLETION ============
        # Entered ONLY after CONFIRMED_SENT -- and doubly so: this statement
        # is unreachable for the other two states (both raised above), and
        # `SemanticTurnRequest` itself refuses construction from a
        # non-CONFIRMED_SENT dispatch.
        #
        # NOTHING in this block may write `semantic_prompts_sent` or
        # `dispatch_state`. A phase-2 failure of ANY kind -- a raised
        # adapter, a wrong type, a foreign session, an unconstructible
        # request -- becomes the bounded terminal fact OBSERVATION_FAILED,
        # never a fabricated deadline and never an erasure.
        _current_gate = SemanticGateName.TURN_COMPLETION
        try:
            turn_request = SemanticTurnRequest(
                run_id=run_id,
                runtime_session=runtime_session,
                task_id=task.task_id,
                task_revision=task.task_revision,
                dispatch=dispatch_observation,
            )
            observed_turn = observe_semantic_turn(turn_request)
        except Exception:
            observed_turn = None
        else:
            if not require_turn_matches_request(observed_turn, turn_request):
                observed_turn = None
        if observed_turn is None:
            turn_observation = SemanticTurnObservation(
                runtime_session_id=runtime_session.runtime_session_id,
                turn_outcome=SemanticTurnOutcome.OBSERVATION_FAILED,
            )
        else:
            turn_observation = observed_turn
        if turn_observation.turn_outcome is SemanticTurnOutcome.OBSERVATION_FAILED:
            # AIDO stopped being able to watch the turn. This is NOT a claim
            # that Pi stopped, that the command was cancelled, or that
            # backend inference stopped -- and it is never reported as a
            # deadline, which is a different, genuinely observed fact.
            raise _GateFailure(
                SemanticGateName.TURN_COMPLETION,
                SemanticFailureCode.TURN_OBSERVATION_FAILED,
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

        # -- FINAL_REPORT_CLAIMS: OPTIONAL, UNTRUSTED, NEVER GATING --
        # 5F3B-Q1-PRE1-FU2 / DESIGN-FU1 Sec. 9.3. Before FU2 this ran
        # through the SAME `_invoke`/`_GateFailure` machinery as
        # BROKER_ACTIVITY, REPOSITORY_OBSERVATION and
        # AUTHORITATIVE_VERIFICATION -- so an adapter exception or a
        # malformed model report set `failed_gate`, which fed
        # `attribute_protocol_anomaly(..., mechanically_attributed_to=None)`
        # and made an otherwise-successful, fully-verified, fully-closed run
        # ATTRIBUTION_UNDETERMINED and unscorable. The model's own final
        # text (or the harness's failure to extract it) was on equal gating
        # footing with AIDO's own authoritative verification, which is never
        # correct.
        #
        # It is now a bounded, closed availability classification that
        # touches NOTHING else: not repository truth, not verification
        # truth, not scope truth, not `run_validity`, not
        # `scoring_eligible`, and not any of the hard bar's H-1..H-9 checks.
        # There is deliberately no `_GateFailure` raised anywhere below, and
        # no retry: a missing or bad self-report is not proof the one
        # authorized prompt needs reissuing.
        _current_gate = SemanticGateName.FINAL_REPORT_CLAIMS
        try:
            claims_observation = collect_final_report_claims(runtime_session)
        except Exception:
            claims_observation = None
        if type(claims_observation) is not FinalReportClaimsObservation:
            # The harness could not collect it: the adapter raised, or
            # returned something that is not a report observation at all.
            report_availability = ReportAvailability.UNAVAILABLE
        elif claims_observation.runtime_session_id != runtime_session.runtime_session_id:
            # Well-typed, but it answers a different runtime session, so it
            # is not usable as THIS run's self-report.
            report_availability = ReportAvailability.MALFORMED
        else:
            report_claims = claims_observation.claims
            report_availability = ReportAvailability.AVAILABLE
        gate_statuses[SemanticGateName.FINAL_REPORT_CLAIMS.value] = (
            _STATUS_PASSED
            if report_availability is ReportAvailability.AVAILABLE
            else f"NOT_EVALUABLE:{report_availability.value}"
        )

    except _DispatchIndeterminate as indeterminate_signal:
        # 5F3B-Q1-PRE1-FU1: dispatch was attempted but AIDO cannot
        # mechanically establish whether the command was sent. NEVER
        # semantic_prompts_sent = 0 (that would falsely claim
        # CONFIRMED_NOT_SENT) and NEVER 1 (that would falsely claim
        # CONFIRMED_SENT). infrastructure_refusal is deliberately left
        # untouched (stays False) for the identical reason.
        dispatch_state = SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
        dispatch_evidence_code = indeterminate_signal.evidence_code
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
    # The four closure gates below record their OWN typed object's
    # `status_text` verbatim, never the generic `_pass()`/"PASSED" literal:
    # `RuntimeTeardownStatus`/`BrokerShutdownStatus`/`SemanticCleanupStatus`/
    # `SemanticWorkspaceRemovalStatus` each render "NOT_REQUIRED"/
    # "SUCCEEDED"/"CLOSED"/"VERIFIED_REMOVED" for a non-failure state, never
    # the string "PASSED" -- so gate_statuses can never disagree with the
    # typed object that actually produced the fact (the same discipline
    # i2b_controller.py's own closure loop applies).
    runtime_teardown = _close_runtime(shutdown_runtime, runtime_session, run_id=run_id or "")
    gate_statuses[SemanticGateName.RUNTIME_TEARDOWN.value] = runtime_teardown.status_text
    broker_shutdown = _close_broker(shutdown_broker, broker_session, run_id=run_id or "")
    gate_statuses[SemanticGateName.BROKER_SHUTDOWN.value] = broker_shutdown.status_text
    cleanup = _attempt_cleanup(generated_config, semantic_prompts_sent=semantic_prompts_sent)
    gate_statuses[SemanticGateName.GENERATED_CONFIG_CLEANUP.value] = cleanup.status_text
    # 5F3B-Q1-PRE1-FU2 / DESIGN-FU1 Sec. 9.1.3 -- the frozen closure order.
    # Workspace removal comes AFTER runtime teardown and broker shutdown
    # (the runtime's cwd and the broker's capability scope are both bound to
    # this tree, so removing it out from under a still-open resource is the
    # same "cleanup racing a live resource" defect frozen O1's own ordering
    # exists to prevent) and AFTER the generated-config scrub (which
    # re-verifies that config's own creation-time issuance authority before
    # deleting anything; the generic, authority-blind tree remover would
    # otherwise silently absorb a config directory whose specific authority
    # was never re-checked). It comes strictly BEFORE evidence
    # construction/scrub/emission, so no record is ever sealed before
    # workspace-removal truth is known -- for every dispatch state.
    workspace_removal = _remove_semantic_workspace(
        run_workspace, semantic_prompts_sent=semantic_prompts_sent
    )
    gate_statuses[SemanticGateName.SEMANTIC_WORKSPACE_REMOVAL.value] = (
        workspace_removal.status_text
    )

    # The safety context is REFUSED, never defaulted, if this route ever
    # reports a credential mechanism other than the one frozen mechanism
    # (Sec. 9.2.2). Fail closed: nothing is written at all rather than an
    # artifact scrubbed against a context AIDO could not prove complete.
    safety_context: ArtifactSafetyContext | None
    try:
        safety_context = build_run_safety_context(
            secret_context=secret_context,
            broker_session=broker_session,
            run_workspace=run_workspace,
            route_descriptor=route_descriptor,
        )
    except SemanticSafetyContextError:
        safety_context = None
    closure_established = (
        runtime_teardown.closure_satisfied
        and broker_shutdown.closure_satisfied
        and cleanup.closure_satisfied
        # Sec. 9.1.5: an unverified removal of AIDO's OWN disposable tree
        # drives the same INFRASTRUCTURE_CONTAMINATED / not-scoring-eligible
        # path a teardown, shutdown or config-cleanup failure already does.
        # The candidate cannot influence whether AIDO's own tree removal
        # succeeds, so Sec. 17.2 case 2 is mechanical here.
        and workspace_removal.closure_satisfied
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
            try:
                comparisons = compare_report(report_claims, observed_facts)
            except Exception:  # noqa: BLE001 - Sec. 9.3.3: never gating
                # The claims were well-typed but could not be compared. That
                # is a fact about the REPORT LAYER alone: it downgrades
                # report accuracy to not-evaluable and changes nothing about
                # repository truth, verification truth, scope truth,
                # run_validity, scoring_eligible, or the hard bar.
                comparisons = ()
                report_availability = ReportAvailability.MALFORMED
                gate_statuses[SemanticGateName.FINAL_REPORT_CLAIMS.value] = (
                    f"NOT_EVALUABLE:{report_availability.value}"
                )

    # ================= RETAINED EVIDENCE: exactly ONE artifact =================
    # 5F3B-Q1-PRE1-FU2 / DESIGN-FU1 Sec. 3.F. Every INVOKED task attempt
    # leaves exactly one immutable retained artifact -- never zero, never
    # two -- through the SAME `qualification.safety.emit_evidence_or_refuse`
    # choke point (exclusive-create, scrub-checked, bounded refusal
    # fallback):
    #
    #     determinate send state   -> pi-implementer-qualification.v1
    #     indeterminate send state -> pi-implementer-qualification-attempt.v1
    #
    # Before FU2, an indeterminate dispatch wrote NOTHING at all and marked
    # EVIDENCE_SAFETY as NOT_REQUIRED -- so the one outcome in which AIDO
    # cannot prove whether the candidate's single authorized prompt was
    # spent was the one outcome that left nothing on disk.
    #
    # `build_qualification_record` is still NEVER called for an
    # indeterminate dispatch: its frozen shape requires
    # `semantic_prompts_sent` to be exactly 0 or 1, and there is no truthful
    # value to pass for an unestablished fact. `pi-implementer-qualification.v1`
    # is not widened; the sibling artifact OMITS the key entirely.
    qualification_record: Mapping[str, Any] | None = None
    attempt_record: Mapping[str, Any] | None = None
    evidence_emission: EvidenceEmission | None = None

    # 5F3B-Q1-PRE1-FU2A-FU1A-FU1: ONE fresh, random, per-attempt token,
    # minted exactly once per invocation of `run_semantic_task_attempt` and
    # never derived from `candidate`/`task`/anything guessable -- so a
    # replayed genuine identity_provenance/evidence_emission from a
    # DIFFERENT invocation carries a DIFFERENT token, no matter how closely
    # its other fields happen to match this attempt's own. See
    # `_AttemptIdentityProvenance`'s and `EvidenceEmission`'s own docstrings
    # for the exact replay this closes.
    _attempt_authority_token = secrets.token_hex(_ATTEMPT_AUTHORITY_TOKEN_BYTES)

    def _mint_identity_provenance(
        candidate_: str,
        model_id_: str,
        task_id_: str,
        task_revision_: str,
        attempt_authority_token_: str,
    ) -> _AttemptIdentityProvenance:
        """Mint one :class:`_AttemptIdentityProvenance`, bypassing its own
        ``__init__``/``__post_init__`` -- the ONLY way, anywhere in this
        package, that an instance of this type can ever be produced (its
        public constructor unconditionally refuses every call). Nested here:
        unreachable, uncallable, and unimportable from outside this one
        invocation of ``run_semantic_task_attempt``, and built from the SAME
        trusted local variables used to build this attempt's own
        ``candidate``/``model_id``/``task.task_id``/``task.task_revision``/
        this call's own ``_attempt_authority_token``.
        """
        instance = object.__new__(_AttemptIdentityProvenance)
        object.__setattr__(instance, "candidate", candidate_)
        object.__setattr__(instance, "model_id", model_id_)
        object.__setattr__(instance, "task_id", task_id_)
        object.__setattr__(instance, "task_revision", task_revision_)
        object.__setattr__(instance, "attempt_authority_token", attempt_authority_token_)
        return instance

    # Minted immediately: candidate/model_id/task identity are already known
    # and validated (SemanticControllerInputError above) before this point.
    identity_provenance = _mint_identity_provenance(
        candidate, model_id, task.task_id, task.task_revision, _attempt_authority_token
    )

    def _mint_evidence_emission(
        *,
        emitted: bool,
        refused: bool,
        path: str,
        scrub_checked: bool,
        clean: bool,
        findings: tuple[str, ...],
        attempt_authority_token: str,
    ) -> EvidenceEmission:
        """Mint one :class:`EvidenceEmission`, bypassing its own ``__init__``/
        ``__post_init__`` -- the ONLY way, anywhere in this package, that a
        ``refused=False`` (successful) instance can ever be produced.
        ``EvidenceEmission.__post_init__`` unconditionally refuses
        ``refused=False`` for every call that reaches it through the class's
        public constructor, so this bypass is not a convenience, it is the
        entire mechanism. Nested here (not a module attribute): unreachable,
        uncallable, and unimportable from outside this one invocation of
        ``run_semantic_task_attempt``. ``attempt_authority_token`` is always
        this SAME call's own ``_attempt_authority_token`` -- both emission
        paths (success and refused) below pass it, so
        ``SemanticTaskAttemptResult.__post_init__`` always finds it paired
        with this call's own ``identity_provenance``.
        """
        _require_evidence_emission_field_shape(
            emitted=emitted,
            refused=refused,
            path=path,
            scrub_checked=scrub_checked,
            clean=clean,
            findings=findings,
            attempt_authority_token=attempt_authority_token,
        )
        instance = object.__new__(EvidenceEmission)
        object.__setattr__(instance, "emitted", emitted)
        object.__setattr__(instance, "refused", refused)
        object.__setattr__(instance, "path", path)
        object.__setattr__(instance, "scrub_checked", scrub_checked)
        object.__setattr__(instance, "clean", clean)
        object.__setattr__(instance, "findings", findings)
        object.__setattr__(instance, "attempt_authority_token", attempt_authority_token)
        return instance

    def _project_emission(emission: Mapping[str, Any]) -> EvidenceEmission:
        """Project a REAL ``emit_or_refuse``/``emit_attempt_or_refuse`` return
        dict onto :class:`EvidenceEmission`.

        Deliberately NESTED, not a module attribute: the only two call sites
        below hand this ``emission`` straight from a same-statement call to
        the real, frozen emission choke point -- there is no reachable path
        by which a caller-fabricated ``Mapping`` could ever reach this
        function, because the function itself cannot be imported, referenced,
        or called from outside this one invocation of
        ``run_semantic_task_attempt``.
        """

        def _exact_bool(name: str, value: object) -> bool:
            # No truthiness anywhere in this projection: a truthy non-bool
            # (the string "true", a non-empty list) must never be read as
            # True for a fact the hard bar consumes.
            if type(value) is not bool:
                raise ValueError(f"evidence emission field {name!r} must be exactly a bool")
            return value

        scrub = emission.get("scrub")
        if not isinstance(scrub, Mapping):
            raise ValueError("evidence emission must carry its own scrub result")
        findings = scrub.get("findings")
        if not isinstance(findings, (list, tuple)):
            raise ValueError("evidence emission scrub must carry a findings sequence")
        # A malformed finding element is an integrity failure, never a value
        # to normalize -- `str(entry)` would silently turn e.g. an int or a
        # nested object into a plausible-looking finding code.
        if not all(type(entry) is str for entry in findings):
            raise ValueError(
                "evidence emission scrub findings must be exactly str entries -- a "
                "non-str finding is refused, never coerced"
            )
        path = emission.get("path")
        if not isinstance(path, str) or not path:
            raise ValueError("evidence emission must carry a non-blank path")
        return _mint_evidence_emission(
            emitted=_exact_bool("emitted", emission.get("emitted")),
            refused=_exact_bool("refused", emission.get("refused")),
            path=path,
            scrub_checked=_exact_bool("scrub_checked", scrub.get("scrub_checked")),
            clean=_exact_bool("clean", scrub.get("clean")),
            findings=tuple(findings),
            attempt_authority_token=_attempt_authority_token,
        )

    route_provenance = {
        "model_id": model_id,
        "provider_route": (
            route_descriptor.provider_id if route_descriptor is not None else None
        ),
        "backend_gateway_class": (
            route_descriptor.backend_gateway_class if route_descriptor is not None else None
        ),
    }

    if safety_context is None:
        # Unreachable through this package's public API -- `RouteDescriptor`
        # already refuses any other credential mechanism at construction --
        # and deliberately fail-closed rather than emitting an artifact
        # scrubbed against a context that could be missing a real needle.
        _fail_status(
            SemanticGateName.EVIDENCE_SAFETY,
            CategoryBFailureCode.SAFETY_CONTEXT_UNPROVABLE,
        )
    elif dispatch_indeterminate:
        attempt_payload = build_attempt_record(
            candidate=candidate,
            model_id=model_id,
            task_id=task.task_id,
            task_revision=task.task_revision,
            dispatch_evidence_code=dispatch_evidence_code,
            # EVIDENCE_SAFETY is omitted deliberately: an evidence body
            # cannot truthfully record the outcome of the gate that is about
            # to judge it, and recording it as NOT_REACHED would be a false
            # statement about a gate that always runs. Its outcome lives on
            # the controller result instead -- the identical discipline
            # `i2b_controller._build_evidence` already applies.
            gate_statuses={
                name: status
                for name, status in gate_statuses.items()
                if name != SemanticGateName.EVIDENCE_SAFETY.value
            },
            observed_pi_version=observed_pi_version,
            compatibility_facts=facts.as_dict(),
            compatibility_gate_passed=compatibility_established,
            route_provenance=route_provenance,
            closure={
                "runtime_teardown": runtime_teardown.status_text,
                "broker_shutdown": broker_shutdown.status_text,
                "generated_config_cleanup": {
                    "attempted": cleanup.attempted,
                    "scrub_verified": cleanup.scrub_verified,
                    "classification": None,
                },
                "semantic_workspace_removal": {
                    "attempted": workspace_removal.attempted,
                    "verified": workspace_removal.verified,
                    "facts": (
                        dict(workspace_removal.facts)
                        if workspace_removal.facts is not None
                        else None
                    ),
                },
                "closure_established": closure_established,
            },
        )
        emission = emit_attempt_or_refuse(
            attempt_payload, path=evidence_path, safety=safety_context
        )
        # 5F3B-Q1-PRE1-FU2A-FU1: embed this attempt's OWN identity, from the
        # SAME trusted local variables used to build `attempt_payload` and
        # the `SemanticTaskAttemptResult` below -- never re-derived from
        # `self` after construction. `SemanticTaskAttemptResult.__post_init__`
        # cross-checks its own `candidate`/`model_id`/`task_id`/
        # `task_revision` against these embedded copies, so
        # `dataclasses.replace(result, candidate="B", model_id=...)` can no
        # longer relabel identity: the embedded copy stays whatever this
        # attempt genuinely was.
        attempt_record = {
            **emission,
            "candidate": candidate,
            "model_id": model_id,
            "task_id": task.task_id,
            "task_revision": task.task_revision,
        }
        evidence_emission = _project_emission(emission)
        if evidence_emission.refused:
            _fail_status(
                SemanticGateName.EVIDENCE_SAFETY, CategoryBFailureCode.EVIDENCE_SCRUB_REFUSED
            )
        else:
            _pass(SemanticGateName.EVIDENCE_SAFETY)
    else:
        pi_runtime = {
            "observed_version": observed_pi_version,
            "compatibility_facts": facts.as_dict(),
            "compatibility_gate_passed": compatibility_established,
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
            report_accuracy=_project_report_accuracy(
                comparisons, availability=report_availability
            ),
        )
        emission = emit_or_refuse(record, path=evidence_path, safety=safety_context)
        # 5F3B-Q1-PRE1-FU2A-FU1: same identity-embedding as the attempt path
        # above, from the same trusted local variables used to build
        # `record` itself.
        qualification_record = {
            **emission,
            "candidate": candidate,
            "model_id": model_id,
            "task_id": task.task_id,
            "task_revision": task.task_revision,
        }
        evidence_emission = _project_emission(emission)
        if evidence_emission.refused:
            _fail_status(
                SemanticGateName.EVIDENCE_SAFETY, CategoryBFailureCode.EVIDENCE_SCRUB_REFUSED
            )
        else:
            _pass(SemanticGateName.EVIDENCE_SAFETY)

    # 5F3B-Q1-PRE1-FU2A-FU1A-FU1-FU1: register THIS attempt's own authority
    # fingerprint -- from the SAME trusted local variables about to be
    # passed into `SemanticTaskAttemptResult` below -- before constructing
    # it. See `_register_attempt_authority`'s own docstring for why this
    # closes the "borrow a genuine, internally-self-consistent evidence
    # bundle from a DIFFERENT attempt" replay the pairwise
    # `attempt_authority_token` equality check alone could not.
    _register_attempt_authority(
        _attempt_authority_token,
        _authorized_facts_fingerprint(
            gate_statuses=gate_statuses,
            dispatch_state=dispatch_state,
            semantic_prompts_sent=semantic_prompts_sent,
            run_validity=run_validity,
            scoring_eligible=scoring_eligible,
            autonomous_classification=autonomous_classification,
            diagnostic_subclassification=diagnostic_subclassification,
            verification_passed=verification_passed,
        ),
    )

    result = SemanticTaskAttemptResult(
        candidate=candidate,
        model_id=model_id,
        task_id=task.task_id,
        task_revision=task.task_revision,
        identity_provenance=identity_provenance,
        semantic_prompts_sent=semantic_prompts_sent,
        dispatch_state=dispatch_state,
        dispatch_evidence_code=dispatch_evidence_code,
        semantic_dispatch_attempted=semantic_dispatch_attempted,
        turn_outcome=(
            turn_observation.turn_outcome if turn_observation is not None else None
        ),
        agent_end_observed=(
            turn_observation.agent_end_observed if turn_observation is not None else False
        ),
        report_availability=report_availability,
        infrastructure_refusal=infrastructure_refusal,
        gate_statuses=gate_statuses,
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
        workspace_removal=workspace_removal,
        qualification_record=qualification_record,
        attempt_record=attempt_record,
        evidence_emission=evidence_emission,
    )
    return result
