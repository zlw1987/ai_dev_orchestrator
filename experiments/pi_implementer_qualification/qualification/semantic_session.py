"""5F3B-Q1-PRE1 / -FU1 / -FU2 -- bounded value objects for the ONE
semantic-prompt dispatch and the ONE semantic turn that may follow it.

**OFFLINE ONLY. This module launches nothing, opens no socket, calls no
model, and reads no credential.** It defines value objects only, in exactly
the style :mod:`qualification.i2b_session` already established: frozen
dataclasses, ``__post_init__`` validation, bounded/charset-limited fields, no
raw runtime text retained.

**5F3B-Q1-PRE1-FU1 -- prompt dispatch is now an observed fact, not an
inference.** Independent review reproduced a defect in the ORIGINAL PRE1
controller (:mod:`qualification.semantic_controller`, fixed in this same
follow-up): ``semantic_prompts_sent = 1`` was assigned immediately BEFORE the
prompt-dispatch adapter was even called, so ANY dispatch-gate failure --
including one mechanically established as never having been sent -- was
recorded as though the one authorized prompt had been spent. Fixing this
required the send/no-send fact itself to become a typed, bounded value the
controller reads rather than infers from having merely called a Python
function:

- :class:`SemanticPromptDispatchState` -- exactly three values.
  ``CONFIRMED_SENT``/``CONFIRMED_NOT_SENT`` may be asserted ONLY by a
  normally-RETURNED, well-typed :class:`SemanticPromptDispatchObservation`;
  neither a raised exception nor a malformed/mismatched result may ever
  produce either of them -- both collapse to ``SEND_STATE_INDETERMINATE``,
  which the controller never maps to ``semantic_prompts_sent`` 0 or 1 (see
  that module's docstring for the full accounting of why the frozen
  ``qualification.records``/``qualification.i2_cleanup`` schemas have no slot
  for an unestablished send fact, and why none is invented for them).
- :class:`SemanticPromptDispatchObservation` -- the ONE typed fact,
  provenance-bound to the exact ``run_id``/``runtime_session_id``/``task_id``/
  ``task_revision`` it answers, via :func:`require_dispatch_matches_request`.
  There is no seam here for an acknowledgement a real future Pi/RPC channel
  does not provide -- CONFIRMED_SENT/CONFIRMED_NOT_SENT are reserved for
  whatever a live adapter's OWN real seam can mechanically establish, not
  invented by this module.

**5F3B-Q1-PRE1-FU2 -- dispatch and turn observation are now TWO phases.**
Independent review established, from Pi 0.84.4's own source, that FU1's
single whole-turn observation is not faithful to the real seam
(``docs/PHASE_5F3B_Q1_PRE1_DESIGN_FU1_SEMANTIC_DISPATCH_AUTHORITY.md``
Sec. 1-2). Pi emits a correlated ``prompt`` response STRICTLY BEFORE agent
start and before any provider inference, so the send fact is established
long before turn completion is. FU1 embedded the dispatch fact INSIDE the
whole-turn observation, which left every reachable post-acknowledgement
failure -- protocol violation, output cap, event cap, read error, early
child exit, a phase-2 adapter bug -- with only two options, both wrong:
fabricate ``deadline_reached``, or raise and thereby ERASE an
already-established ``CONFIRMED_SENT``. This module now splits them:

- PHASE 1 :class:`SemanticPromptDispatchObservation` -- the send fact,
  alone, carrying a bounded :class:`SemanticDispatchEvidenceCode` naming
  WHICH mechanical fact established it. Once ``CONFIRMED_SENT``, that fact
  is write-once for the attempt.
- PHASE 2 :class:`SemanticTurnRequest` -> :class:`SemanticTurnObservation`
  -- entered ONLY after ``CONFIRMED_SENT`` (structurally: a turn request
  cannot even be constructed otherwise), reporting a THREE-valued
  :class:`SemanticTurnOutcome` (``SETTLED`` / ``DEADLINE_REACHED`` /
  ``OBSERVATION_FAILED``). It carries no dispatch object and no
  ``call_succeeded`` flag, so there is no field through which a phase-2
  outcome could rewrite a phase-1 truth.

Why this module exists
-----------------------

:mod:`qualification.i2b_controller` proves Category-B compatibility and then
tears the runtime and broker down, unconditionally, before it ever returns --
that is correct for Category-B, which sends zero prompts and therefore has
nothing further to do with a live session. A **semantic** task run needs the
opposite: the compatibility facts must be established, and the SAME runtime
session must then be used to send exactly one prompt and observe its turn to
completion, before any teardown happens. :mod:`qualification.i2b_session`'s
own types (:class:`~qualification.i2b_session.RuntimeSession`,
:class:`~qualification.i2b_session.BrokerSession`, and friends) already
express every fact needed to *reach* that point; this module adds only the
narrow, ADDITIONAL facts a semantic turn needs once a runtime session already
exists -- it does not redefine anything :mod:`qualification.i2b_session`
already owns, and it imports those types rather than reinventing them.

Every object here is what a FUTURE live adapter would need to construct.
Nothing here launches Pi, sends a prompt, or reads model output -- this
phase (5F3B-Q1-PRE1) is offline implementation only, and every function that
would perform one of those things is an INJECTED callable at the controller
boundary, exactly like :mod:`qualification.i2b_controller`'s own adapters.

Claim scope, exactly like the rest of this package
----------------------------------------------------

:class:`SemanticTurnObservation` reports only what AIDO's own wait for
runtime-turn completion observed: ``SETTLED`` (the runtime reported
``agent_settled`` -- Pi's own turn-completion signal, per the frozen AR2
supervisor's ``await_settled``/``activity.settled`` semantics, **not** the
task succeeding), ``DEADLINE_REACHED`` (AIDO's own configured turn deadline
elapsed first), or ``OBSERVATION_FAILED`` (the turn became unobservable to
AIDO), plus the independent ``agent_end_observed`` fact, which never by
itself means completion. Every one of the three says only that AIDO stopped
being able to establish completion: none claims Pi stopped, that the
underlying request was cancelled, that backend inference stopped, or that a
descendant process was terminated. Nothing here carries reasoning-bearing
content -- there is no field that could hold it.

:class:`BrokerActivityObservation` reports the run's own accumulated
read/edit operation counts and refusal events, exactly as
:mod:`qualification.i2b_session`'s ``BrokerCreationObservation``/
``RuntimeLaunchObservation`` already report resource-lifecycle facts:
AIDO-derived counts of AIDO's own accepted/refused operations, never a claim
about what the model "intended". Refusal events are carried as
:class:`~qualification.scope.RefusalEvent` -- the identical frozen type
:mod:`qualification.scope` already consumes for Sec. 17 refusal attribution
-- so there is no second, drifting refusal-event shape anywhere in this
package.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from .i2b_session import (
    _ID_PATTERN,
    ObservationError,
    RuntimeSession,
    _require_pattern,
    require_exact_bool,
)
from .report_accuracy import ReportClaims
from .scope import RefusalEvent

#: A bounded task identifier (``IQ-1``, ``IQ-2``, ``IQ-3``). Never a free
#: string -- this travels into evidence, so it is charset/length bounded like
#: every other retained identifier in this package.
_TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,32}$")

#: An upper bound on how many refusal events one turn may report. A real
#: qualification task's budget is 16 edit operations + 32 read operations
#: (Sec. 3 of the design), so this only refuses an unbounded/malformed
#: adapter-supplied list rather than holding one in memory.
_MAX_REFUSAL_EVENTS = 256

#: Upper bounds on the AIDO-owned operation counters, matching the accepted
#: capability caps this package's corpus is built against (``ar2.capability``
#: ``MAX_READ_OPERATIONS_PER_RUN`` / ``MAX_EDIT_OPERATIONS_PER_RUN``). A
#: reported count above these is refused outright: it cannot be a truthful
#: report of THIS run's own budget-limited activity.
_MAX_READ_OPERATIONS = 32
_MAX_EDIT_OPERATIONS = 16


def _require_task_id(field_name: str, value: object) -> str:
    if not isinstance(value, str) or not _TASK_ID_PATTERN.fullmatch(value):
        raise ObservationError(
            f"{field_name} must be a bounded task id; arbitrary text is refused"
        )
    return value


def _require_bounded_count(field_name: str, value: object, *, maximum: int) -> int:
    if type(value) is not int or isinstance(value, bool):
        raise ObservationError(f"{field_name} must be exactly an int")
    if value < 0 or value > maximum:
        raise ObservationError(f"{field_name} must be in [0, {maximum}]")
    return value


@dataclass(frozen=True)
class SemanticPromptRequest:
    """What AIDO hands its prompt-dispatch adapter. AIDO-authored only.

    **There is no free-text ``prompt`` parameter anywhere in this module.**
    ``task_id``/``task_revision`` name the frozen
    :class:`~qualification.corpus.QualificationTask` this request carries;
    the adapter is trusted to send exactly ``task.prompt`` (the frozen
    corpus's own wording) and nothing an AIDO caller could substitute at this
    boundary -- a live adapter's own contract, not something this value
    object can enforce by itself, exactly as
    :class:`~qualification.i2b_session.RuntimeLaunchRequest` cannot itself
    prove the argv a future live adapter builds is correct. What THIS object
    prevents is different callers of the controller silently disagreeing
    about *which* task's prompt this dispatch is for.

    ``runtime_session`` binds this request to the one already-launched,
    already-compatibility-proven runtime -- there is no way to construct one
    of these before a runtime session exists.
    """

    run_id: str
    runtime_session: RuntimeSession
    task_id: str
    task_revision: str

    def __post_init__(self) -> None:
        _require_pattern("SemanticPromptRequest.run_id", self.run_id, _ID_PATTERN)
        if type(self.runtime_session) is not RuntimeSession:
            raise ObservationError(
                "SemanticPromptRequest.runtime_session must be a RuntimeSession"
            )
        if self.runtime_session.run_id != self.run_id:
            raise ObservationError(
                "SemanticPromptRequest: the runtime session belongs to a different run"
            )
        _require_task_id("SemanticPromptRequest.task_id", self.task_id)
        if not isinstance(self.task_revision, str) or not self.task_revision:
            raise ObservationError("SemanticPromptRequest.task_revision must be non-blank")


class SemanticPromptDispatchState(str, Enum):
    """The mechanically-established send/no-send fact for ONE dispatch attempt.

    ``CONFIRMED_SENT`` and ``CONFIRMED_NOT_SENT`` may be asserted ONLY by a
    normally-returned, well-typed :class:`SemanticPromptDispatchObservation`
    -- never inferred from a raised exception, a malformed adapter result, or
    the mere fact that the adapter function was called.
    """

    #: The one authorized semantic command was mechanically established as
    #: accepted/sent. Only after this exists may the semantic turn proceed.
    CONFIRMED_SENT = "CONFIRMED_SENT"
    #: The semantic command was mechanically established as NOT having been
    #: accepted/sent -- a genuine pre-send refusal, structurally
    #: indistinguishable in effect from never having reached this gate at
    #: all. Remains a pre-prompt infrastructure refusal.
    CONFIRMED_NOT_SENT = "CONFIRMED_NOT_SENT"
    #: Dispatch was attempted but AIDO cannot mechanically establish whether
    #: the command crossed the send boundary. Never mapped to 0 or 1, never
    #: scored, never retried.
    SEND_STATE_INDETERMINATE = "SEND_STATE_INDETERMINATE"


class SemanticDispatchEvidenceCode(str, Enum):
    """WHICH mechanical fact established a :class:`SemanticPromptDispatchState`.

    5F3B-Q1-PRE1-DESIGN-FU1 Sec. 2.3. A **closed, declared** vocabulary --
    never raw runtime text, never a supervisor outcome string retained
    verbatim, never free-form prose. It mirrors the accepted
    ``LaunchDiagnostic.required_flags_code`` discipline, and like the
    accepted reviewer supervisor's ``stall_source`` it is **audit-only**:
    nothing in this package branches on it.

    Each member maps to EXACTLY ONE :class:`SemanticPromptDispatchState`
    (:data:`DISPATCH_EVIDENCE_CODE_STATES`), and
    :class:`SemanticPromptDispatchObservation` refuses any pairing that
    disagrees -- so an evidence code can never be attached to a state it
    does not actually establish.
    """

    # -- CONFIRMED_NOT_SENT ------------------------------------------------
    #: AIDO's own dispatch gate refused; the write was never entered.
    GATE_REFUSED_BEFORE_WRITE = "GATE_REFUSED_BEFORE_WRITE"
    #: A correlated prompt response reporting success false. Sec. 1.5:
    #: nothing reached the agent loop.
    PROMPT_RESPONSE_REFUSED = "PROMPT_RESPONSE_REFUSED"
    #: An uncorrelated parse-failure response observed in the dispatch
    #: window with no prompt response for AIDO's id. Admissible ONLY under
    #: Sec. 2.5's single-writer rule.
    COMMAND_UNPARSEABLE_REFUSED = "COMMAND_UNPARSEABLE_REFUSED"
    # -- CONFIRMED_SENT ----------------------------------------------------
    #: A correlated prompt response reporting success true, for AIDO's id.
    PROMPT_RESPONSE_ACCEPTED = "PROMPT_RESPONSE_ACCEPTED"
    #: An agent-run record observed for this session after dispatch, when the
    #: correlated response itself was missed. Sec. 1.6 makes this
    #: independently sufficient.
    AGENT_RUN_OBSERVED = "AGENT_RUN_OBSERVED"
    # -- SEND_STATE_INDETERMINATE ------------------------------------------
    #: The write/flush raised. Sec. 1.7: a failed write is not proof of
    #: not-sent, and a successful one is not proof of sent.
    WRITE_FAILED_TRANSMISSION_UNKNOWN = "WRITE_FAILED_TRANSMISSION_UNKNOWN"
    #: AIDO's own dispatch deadline elapsed with no correlated response.
    NO_CORRELATED_RESPONSE_DEADLINE = "NO_CORRELATED_RESPONSE_DEADLINE"
    #: The record stream terminated (protocol violation / output cap / event
    #: cap / read error / early exit) before any acknowledgement.
    NO_CORRELATED_RESPONSE_STREAM_TERMINAL = "NO_CORRELATED_RESPONSE_STREAM_TERMINAL"
    #: The phase-1 adapter raised.
    ADAPTER_RAISED = "ADAPTER_RAISED"
    #: The phase-1 adapter returned the wrong type, or an observation that
    #: does not provably answer THIS request.
    OBSERVATION_MALFORMED_OR_FOREIGN = "OBSERVATION_MALFORMED_OR_FOREIGN"


#: The one authoritative code -> state mapping (Sec. 2.3's table). A
#: read-only proxy over a private copy: a caller cannot add, remove, or
#: repoint an entry and thereby make a code establish a different state.
DISPATCH_EVIDENCE_CODE_STATES: Mapping[
    SemanticDispatchEvidenceCode, SemanticPromptDispatchState
] = MappingProxyType(
    {
        SemanticDispatchEvidenceCode.GATE_REFUSED_BEFORE_WRITE: (
            SemanticPromptDispatchState.CONFIRMED_NOT_SENT
        ),
        SemanticDispatchEvidenceCode.PROMPT_RESPONSE_REFUSED: (
            SemanticPromptDispatchState.CONFIRMED_NOT_SENT
        ),
        SemanticDispatchEvidenceCode.COMMAND_UNPARSEABLE_REFUSED: (
            SemanticPromptDispatchState.CONFIRMED_NOT_SENT
        ),
        SemanticDispatchEvidenceCode.PROMPT_RESPONSE_ACCEPTED: (
            SemanticPromptDispatchState.CONFIRMED_SENT
        ),
        SemanticDispatchEvidenceCode.AGENT_RUN_OBSERVED: (
            SemanticPromptDispatchState.CONFIRMED_SENT
        ),
        SemanticDispatchEvidenceCode.WRITE_FAILED_TRANSMISSION_UNKNOWN: (
            SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
        ),
        SemanticDispatchEvidenceCode.NO_CORRELATED_RESPONSE_DEADLINE: (
            SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
        ),
        SemanticDispatchEvidenceCode.NO_CORRELATED_RESPONSE_STREAM_TERMINAL: (
            SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
        ),
        SemanticDispatchEvidenceCode.ADAPTER_RAISED: (
            SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
        ),
        SemanticDispatchEvidenceCode.OBSERVATION_MALFORMED_OR_FOREIGN: (
            SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
        ),
    }
)


@dataclass(frozen=True)
class SemanticPromptDispatchObservation:
    """PHASE 1's ONE typed, provenance-bound fact: was the command sent?

    **This is the whole of phase 1's output.** 5F3B-Q1-PRE1-FU2 separated it
    from the turn observation entirely (DESIGN-FU1 Sec. 2.2): the real Pi
    0.84.4 seam emits a correlated prompt-response acknowledgement STRICTLY
    BEFORE agent start and before any provider inference, so the send fact
    exists long before turn completion does. Embedding it inside a
    whole-turn observation -- FU1's shape -- meant a post-acknowledgement
    read failure could only be represented by fabricating a deadline or by
    ERASING an already-established ``CONFIRMED_SENT``. Neither is truthful,
    and both are now structurally impossible: phase 2
    (:class:`SemanticTurnObservation`) cannot carry, contradict, or rewrite
    this object.

    Bound to the exact ``run_id``/``runtime_session_id``/``task_id``/
    ``task_revision`` it answers -- a caller must use
    :func:`require_dispatch_matches_request` to prove this observation
    actually answers a given :class:`SemanticPromptRequest` before trusting
    it (adversarial: a dispatch observation minted for a different
    run/session/task can never be silently accepted as this request's own
    answer).

    ``dispatch_evidence_code`` is REQUIRED and has no default: a live
    adapter must state WHICH mechanical fact established the state, and the
    pairing is re-checked here against :data:`DISPATCH_EVIDENCE_CODE_STATES`.
    There is no seam here for an acknowledgement a real Pi/RPC channel does
    not provide -- ``CONFIRMED_SENT``/``CONFIRMED_NOT_SENT`` are reserved for
    facts that seam can actually prove, never invented here.
    """

    run_id: str
    runtime_session_id: str
    task_id: str
    task_revision: str
    dispatch_state: SemanticPromptDispatchState
    dispatch_evidence_code: SemanticDispatchEvidenceCode

    def __post_init__(self) -> None:
        _require_pattern(
            "SemanticPromptDispatchObservation.run_id", self.run_id, _ID_PATTERN
        )
        _require_pattern(
            "SemanticPromptDispatchObservation.runtime_session_id",
            self.runtime_session_id,
            _ID_PATTERN,
        )
        _require_task_id("SemanticPromptDispatchObservation.task_id", self.task_id)
        if not isinstance(self.task_revision, str) or not self.task_revision:
            raise ObservationError(
                "SemanticPromptDispatchObservation.task_revision must be non-blank"
            )
        if type(self.dispatch_state) is not SemanticPromptDispatchState:
            raise ObservationError(
                "SemanticPromptDispatchObservation.dispatch_state must be exactly a "
                "SemanticPromptDispatchState"
            )
        if type(self.dispatch_evidence_code) is not SemanticDispatchEvidenceCode:
            raise ObservationError(
                "SemanticPromptDispatchObservation.dispatch_evidence_code must be "
                "exactly a SemanticDispatchEvidenceCode -- never raw runtime text"
            )
        established = DISPATCH_EVIDENCE_CODE_STATES[self.dispatch_evidence_code]
        if established is not self.dispatch_state:
            raise ObservationError(
                "SemanticPromptDispatchObservation: dispatch_evidence_code "
                f"{self.dispatch_evidence_code.value!r} establishes "
                f"{established.value!r}, not {self.dispatch_state.value!r} -- an "
                "evidence code may never be attached to a state it does not establish"
            )


def require_dispatch_matches_request(
    observation: SemanticPromptDispatchObservation, request: SemanticPromptRequest
) -> bool:
    """Whether ``observation`` truthfully answers exactly ``request``.

    Same run, same runtime session, same task identity/revision. A dispatch
    observation that does not match cannot be trusted to describe what
    happened to THIS request -- it may be stale, foreign, or substituted.
    """
    if type(observation) is not SemanticPromptDispatchObservation:
        return False
    return (
        observation.run_id == request.run_id
        and observation.runtime_session_id == request.runtime_session.runtime_session_id
        and observation.task_id == request.task_id
        and observation.task_revision == request.task_revision
    )


@dataclass(frozen=True)
class SemanticTurnRequest:
    """What AIDO hands its PHASE 2 turn-observation adapter.

    Carries the phase-1 :class:`SemanticPromptDispatchObservation` as an
    INPUT, so phase 2 structurally cannot rewrite, contradict, or re-report
    the send fact -- it can only describe what AIDO's own wait for turn
    completion observed afterwards.

    Constructing one REQUIRES a ``CONFIRMED_SENT`` dispatch that provably
    answers this same run/session/task. That is the type-level half of
    DESIGN-FU1 Sec. 2.2's "phase 2 is entered ONLY when phase 1 returned
    CONFIRMED_SENT"; the controller enforces the control-flow half.
    """

    run_id: str
    runtime_session: RuntimeSession
    task_id: str
    task_revision: str
    dispatch: SemanticPromptDispatchObservation

    def __post_init__(self) -> None:
        _require_pattern("SemanticTurnRequest.run_id", self.run_id, _ID_PATTERN)
        if type(self.runtime_session) is not RuntimeSession:
            raise ObservationError(
                "SemanticTurnRequest.runtime_session must be a RuntimeSession"
            )
        if self.runtime_session.run_id != self.run_id:
            raise ObservationError(
                "SemanticTurnRequest: the runtime session belongs to a different run"
            )
        _require_task_id("SemanticTurnRequest.task_id", self.task_id)
        if not isinstance(self.task_revision, str) or not self.task_revision:
            raise ObservationError("SemanticTurnRequest.task_revision must be non-blank")
        if type(self.dispatch) is not SemanticPromptDispatchObservation:
            raise ObservationError(
                "SemanticTurnRequest.dispatch must be exactly a "
                "SemanticPromptDispatchObservation"
            )
        if self.dispatch.dispatch_state is not SemanticPromptDispatchState.CONFIRMED_SENT:
            raise ObservationError(
                "SemanticTurnRequest: a semantic turn may only be observed after the "
                "dispatch was mechanically established as CONFIRMED_SENT"
            )
        if (
            self.dispatch.run_id != self.run_id
            or self.dispatch.runtime_session_id != self.runtime_session.runtime_session_id
            or self.dispatch.task_id != self.task_id
            or self.dispatch.task_revision != self.task_revision
        ):
            raise ObservationError(
                "SemanticTurnRequest: the dispatch observation answers a different "
                "run/session/task"
            )


class SemanticTurnOutcome(str, Enum):
    """PHASE 2's bounded terminal outcome. Exactly three values.

    ``OBSERVATION_FAILED`` is the third terminal state FU1's two-valued
    shape denied (DESIGN-FU1 Sec. 1.10 / Sec. 2.2). It is what makes "the
    acknowledgement arrived, and then AIDO's own view of the turn broke"
    representable WITHOUT either fabricating a deadline or erasing an
    already-established ``CONFIRMED_SENT``.
    """

    #: The runtime reported ``agent_settled`` -- Pi's own turn-completion
    #: signal, never a claim that the task succeeded.
    SETTLED = "SETTLED"
    #: AIDO's OWN configured turn deadline elapsed first. Never a claim that
    #: the underlying request was cancelled or that backend inference
    #: stopped.
    DEADLINE_REACHED = "DEADLINE_REACHED"
    #: The turn became unobservable to AIDO -- protocol violation, output
    #: cap, event cap, read error, early child exit, or a raised/malformed
    #: phase-2 adapter result. AIDO stopped being able to watch; nothing
    #: here claims Pi stopped.
    OBSERVATION_FAILED = "OBSERVATION_FAILED"


@dataclass(frozen=True)
class SemanticTurnObservation:
    """ONE correlated observation of the semantic turn's terminal state.

    **It no longer carries the dispatch fact at all** (5F3B-Q1-PRE1-FU2).
    Phase 1 owns that, permanently; this object describes only what AIDO's
    own wait observed afterwards, and there is no field here through which a
    phase-2 result could contradict or erase ``semantic_prompts_sent = 1``.

    ``agent_end_observed`` stays an INDEPENDENT, non-completion fact,
    exactly mirroring the frozen AR2 supervisor's own distinction
    (``ar2.supervisor.PiRpcSupervisor._absorb``) and Pi's own emission sites:
    ``agent_end`` may carry ``willRetry`` and is emitted once per loop
    iteration, while ``agent_settled`` has exactly one emission site
    (``_runAgentPrompt``'s ``finally``). An ``agent_end`` therefore never by
    itself upgrades an outcome to ``SETTLED``.
    """

    runtime_session_id: str
    turn_outcome: SemanticTurnOutcome
    agent_end_observed: bool = False

    def __post_init__(self) -> None:
        _require_pattern(
            "SemanticTurnObservation.runtime_session_id",
            self.runtime_session_id,
            _ID_PATTERN,
        )
        if type(self.turn_outcome) is not SemanticTurnOutcome:
            raise ObservationError(
                "SemanticTurnObservation.turn_outcome must be exactly a "
                "SemanticTurnOutcome"
            )
        require_exact_bool(
            "SemanticTurnObservation.agent_end_observed", self.agent_end_observed
        )

    @property
    def agent_settled(self) -> bool:
        """Derived, read-only: Pi reported its own turn-completion signal."""
        return self.turn_outcome is SemanticTurnOutcome.SETTLED

    @property
    def deadline_reached(self) -> bool:
        """Derived, read-only: AIDO's own turn deadline elapsed first."""
        return self.turn_outcome is SemanticTurnOutcome.DEADLINE_REACHED

    @property
    def observation_failed(self) -> bool:
        """Derived, read-only: the turn became unobservable to AIDO."""
        return self.turn_outcome is SemanticTurnOutcome.OBSERVATION_FAILED


def require_turn_matches_request(
    observation: SemanticTurnObservation, request: SemanticTurnRequest
) -> bool:
    """Whether ``observation`` truthfully answers exactly ``request``'s turn.

    Exact type (a subclass is refused, exactly as for phase 1) and the same
    runtime session the dispatch was acknowledged on.
    """
    if type(observation) is not SemanticTurnObservation:
        return False
    return observation.runtime_session_id == request.runtime_session.runtime_session_id


@dataclass(frozen=True)
class BrokerActivityObservation:
    """The run's own accumulated read/edit activity and refusal events.

    AIDO-derived, from the SAME broker capability the runtime session was
    launched against -- never a claim about the model's intent. Refusal
    events are :class:`~qualification.scope.RefusalEvent` instances, the
    identical frozen type Sec. 17 scope attribution already consumes, so a
    caller building :func:`~qualification.scope.build_scope_result` input
    from this object never has to translate between two refusal-event
    shapes.

    ``edited_paths`` is the broker's OWN accounting of which distinct
    repository-relative paths it accepted an edit operation for -- never
    inferred from Git. This is what makes H-8 ("broker/Git cross-check
    agrees in both directions") checkable at all: AIDO compares this set
    against the independently Git-observed changed-path set, and a
    disagreement in either direction is exactly the anomaly the design
    requires be caught.
    """

    runtime_session_id: str
    call_succeeded: bool
    read_operation_count: int = 0
    edit_operation_count: int = 0
    edited_paths: frozenset[str] = field(default_factory=frozenset)
    refusals: tuple[RefusalEvent, ...] = ()

    def __post_init__(self) -> None:
        _require_pattern(
            "BrokerActivityObservation.runtime_session_id",
            self.runtime_session_id,
            _ID_PATTERN,
        )
        require_exact_bool(
            "BrokerActivityObservation.call_succeeded", self.call_succeeded
        )
        _require_bounded_count(
            "BrokerActivityObservation.read_operation_count",
            self.read_operation_count,
            maximum=_MAX_READ_OPERATIONS,
        )
        _require_bounded_count(
            "BrokerActivityObservation.edit_operation_count",
            self.edit_operation_count,
            maximum=_MAX_EDIT_OPERATIONS,
        )
        if not isinstance(self.edited_paths, frozenset) or not all(
            isinstance(entry, str) for entry in self.edited_paths
        ):
            raise ObservationError(
                "BrokerActivityObservation.edited_paths must be a frozenset of str"
            )
        if len(self.edited_paths) > _MAX_EDIT_OPERATIONS:
            raise ObservationError(
                "BrokerActivityObservation.edited_paths exceeds the bounded "
                "per-run changed-file budget"
            )
        if not isinstance(self.refusals, tuple) or not all(
            type(entry) is RefusalEvent for entry in self.refusals
        ):
            raise ObservationError(
                "BrokerActivityObservation.refusals must be a tuple of RefusalEvent"
            )
        if len(self.refusals) > _MAX_REFUSAL_EVENTS:
            raise ObservationError(
                "BrokerActivityObservation.refusals exceeds the bounded event count"
            )
        if not self.call_succeeded and (
            self.read_operation_count
            or self.edit_operation_count
            or self.edited_paths
            or self.refusals
        ):
            raise ObservationError(
                "BrokerActivityObservation: a failed call cannot also report observed "
                "activity"
            )


@dataclass(frozen=True)
class FinalReportClaimsObservation:
    """A bounded wrapper binding one :class:`~qualification.report_accuracy.ReportClaims`
    to the runtime session it was extracted from.

    The extraction itself -- turning the model's final assistant text into
    bounded structured claims -- is NOT this module's business and is not
    implemented here: it is exactly the kind of live, runtime-specific logic
    a future live-adapter phase supplies, injected at the controller boundary
    like every other live fact in this package. This wrapper only proves
    which runtime session a given ``ReportClaims`` came from; it never
    retains the raw text the claims were derived from.
    """

    runtime_session_id: str
    claims: ReportClaims

    def __post_init__(self) -> None:
        _require_pattern(
            "FinalReportClaimsObservation.runtime_session_id",
            self.runtime_session_id,
            _ID_PATTERN,
        )
        if type(self.claims) is not ReportClaims:
            raise ObservationError(
                "FinalReportClaimsObservation.claims must be exactly a ReportClaims"
            )
