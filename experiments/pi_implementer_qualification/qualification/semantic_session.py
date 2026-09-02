"""5F3B-Q1-PRE1 / 5F3B-Q1-PRE1-FU1 -- bounded value objects for the ONE
semantic-prompt turn.

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
- :class:`SemanticTurnObservation` now EMBEDS a
  :class:`SemanticPromptDispatchObservation` and enforces, at construction,
  that only a ``CONFIRMED_SENT`` dispatch may also report ``call_succeeded``
  or any turn-completion fact -- a ``CONFIRMED_NOT_SENT`` or
  ``SEND_STATE_INDETERMINATE`` observation structurally cannot smuggle in a
  turn-completion claim.

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
runtime-turn completion observed: whether the runtime reported
``agent_settled`` (Pi's own turn-completion signal, per the frozen AR2
supervisor's ``await_settled``/``activity.settled`` semantics -- **not** the
task succeeding), whether an ``agent_end`` was separately observed (which
never by itself means completion), and whether AIDO's own configured turn
deadline was reached before settlement. It never claims backend inference
stopped, never claims a descendant process was terminated, and never carries
reasoning-bearing content -- there is no field here that could hold it.

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


@dataclass(frozen=True)
class SemanticPromptDispatchObservation:
    """The ONE typed, provenance-bound fact about whether a semantic command
    was sent.

    Bound to the exact ``run_id``/``runtime_session_id``/``task_id``/
    ``task_revision`` it answers -- a caller must use
    :func:`require_dispatch_matches_request` to prove this observation
    actually answers a given :class:`SemanticPromptRequest` before trusting
    it (5F3B-Q1-PRE1-FU1 adversarial: a dispatch observation minted for a
    different run/session/task can never be silently accepted as this
    request's own answer).

    There is no seam here for an acknowledgement a real future Pi/RPC channel
    does not provide: a live adapter must derive ``dispatch_state`` from
    whatever ITS OWN real seam mechanically establishes, and
    ``CONFIRMED_SENT``/``CONFIRMED_NOT_SENT`` are reserved for facts that seam
    can actually prove -- never invented here.
    """

    run_id: str
    runtime_session_id: str
    task_id: str
    task_revision: str
    dispatch_state: SemanticPromptDispatchState

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
class SemanticTurnObservation:
    """ONE correlated observation of the semantic turn's completion state.

    ``dispatch`` is the mechanically-established send/no-send fact (5F3B-Q1-
    PRE1-FU1) -- see :class:`SemanticPromptDispatchObservation`. Only a
    ``CONFIRMED_SENT`` dispatch may also report ``call_succeeded`` or any
    turn-completion fact; a ``CONFIRMED_NOT_SENT``/``SEND_STATE_INDETERMINATE``
    dispatch structurally cannot carry one.

    ``agent_settled`` and ``agent_end_observed`` are two INDEPENDENT facts,
    exactly mirroring the frozen AR2 supervisor's own distinction
    (``ar2.supervisor.PiRpcSupervisor._absorb``): an ``agent_end`` is never
    by itself completion (it may carry ``willRetry``), and only
    ``agent_settled`` sets the runtime's own turn-completion signal.
    ``deadline_reached`` records whether AIDO's own configured turn deadline
    (the accepted ``RunBounds.turn_deadline_seconds``) elapsed before
    settlement -- never a claim that the underlying request was cancelled or
    that backend inference stopped.

    **Exactly one of ``agent_settled`` or ``deadline_reached`` may be true**
    for a call that succeeded; a turn that neither settled nor reached its
    deadline is not yet a terminal observation at all, and this object
    cannot represent it as one.
    """

    runtime_session_id: str
    dispatch: SemanticPromptDispatchObservation
    call_succeeded: bool
    agent_settled: bool = False
    agent_end_observed: bool = False
    deadline_reached: bool = False

    def __post_init__(self) -> None:
        _require_pattern(
            "SemanticTurnObservation.runtime_session_id", self.runtime_session_id, _ID_PATTERN
        )
        if type(self.dispatch) is not SemanticPromptDispatchObservation:
            raise ObservationError(
                "SemanticTurnObservation.dispatch must be exactly a "
                "SemanticPromptDispatchObservation"
            )
        if self.dispatch.runtime_session_id != self.runtime_session_id:
            raise ObservationError(
                "SemanticTurnObservation: the dispatch observation belongs to a "
                "different runtime session"
            )
        require_exact_bool("SemanticTurnObservation.call_succeeded", self.call_succeeded)
        require_exact_bool("SemanticTurnObservation.agent_settled", self.agent_settled)
        require_exact_bool(
            "SemanticTurnObservation.agent_end_observed", self.agent_end_observed
        )
        require_exact_bool("SemanticTurnObservation.deadline_reached", self.deadline_reached)

        if self.dispatch.dispatch_state is not SemanticPromptDispatchState.CONFIRMED_SENT:
            if self.call_succeeded or self.agent_settled or self.agent_end_observed or self.deadline_reached:
                raise ObservationError(
                    "SemanticTurnObservation: only a CONFIRMED_SENT dispatch may report "
                    "call_succeeded or any turn-completion fact"
                )
            return
        if not self.call_succeeded:
            raise ObservationError(
                "SemanticTurnObservation: a CONFIRMED_SENT dispatch requires "
                "call_succeeded == True"
            )
        if self.agent_settled and self.deadline_reached:
            raise ObservationError(
                "SemanticTurnObservation: a turn cannot both settle and reach the "
                "deadline -- these are mutually exclusive terminal facts"
            )
        if not self.agent_settled and not self.deadline_reached:
            raise ObservationError(
                "SemanticTurnObservation: a successful call must report either "
                "agent_settled or deadline_reached -- there is no third terminal state"
            )


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
