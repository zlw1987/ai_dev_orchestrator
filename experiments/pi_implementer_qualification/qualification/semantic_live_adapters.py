"""5F3B-LIVE1-I1 -- the live semantic adapter for ONE Pi qualification task.

**THIS MODULE PERFORMS REAL, LIVE ACTIVITY**, exactly the same class of
activity :mod:`qualification.i2b_live_adapters` already performs for
Category-B, plus exactly one additional thing neither that module nor any
other module in this package has ever done: it sends **one real semantic
prompt** to a live Pi runtime and observes its turn to completion. It is the
first runtime capability in this repository that deliberately transmits
source-derived task prose to a model-backed agent loop.

Composition, never subclassing or reimplementation
-----------------------------------------------------

:class:`LiveSemanticAdapters` **is not** a subclass of
:class:`~qualification.i2b_live_adapters.LiveCategoryBAdapters` and does not
reimplement any of its thirteen zero-prompt ports. It holds one **as a
private member**, activated post-gate (below), and delegates every
Category-A-era port to it verbatim. Two frozen facts force this shape
(design Sec. 11.1):

1. ``tests/test_i2b_live_adapters.py::test_no_prompt_command_type_is_ever_constructed``
   asserts the string ``"prompt"`` appears in no string literal anywhere in
   :mod:`qualification.i2b_live_adapters` -- so the one ``"prompt"`` RPC
   command this module constructs (Sec. 6 below) cannot live there.
2. ``AuthenticatedB300RouteObserver.__init__`` requires
   ``type(adapters) is LiveCategoryBAdapters`` exactly -- so this class
   cannot be a subclass, or the frozen route-check gate would refuse it.

This module therefore declares exactly the four frozen semantic ports on top
of the delegated base, and nothing else:

    dispatch_semantic_prompt(request)   -> SemanticPromptDispatchObservation
    observe_semantic_turn(request)      -> SemanticTurnObservation
    collect_broker_activity(session)    -> BrokerActivityObservation
    collect_final_report_claims(session) -> FinalReportClaimsObservation | None

Every one of those four types is imported from the frozen
:mod:`qualification.semantic_session` -- this module declares no competing
observation/request/result schema of its own.

Inert construction, one-shot post-gate activation
-----------------------------------------------------

Constructing an instance performs zero subprocess launches, zero
``--version`` probes, zero credential reads, zero broker/runtime/pipe
creation, zero network contact, and zero semantic dispatch: it binds the
frozen :class:`~qualification.corpus.QualificationTask` object and an
``environ_reader`` callable, nothing else. Activation happens in exactly one
place -- :meth:`LiveSemanticAdapters.read_connection`, which the frozen
controller calls first, after all eight of a task's own Category-A
non-secret preflight gates have already passed
(:func:`qualification.i2_credentials.resolve_connection_after_preflight`'s
own frozen contract). Activation is one-shot: a second
``read_connection()`` call refuses without a second identity probe. Every
other port refuses on an unactivated adapter and never lazily activates one.

Activation binds the **runtime identity only** -- one
:func:`~qualification.i2b_live_adapters.resolve_pi_identity` probe, and the
one :func:`~qualification.i2b_workspace.grant_semantic_capability_issuance`
authorization to this task's later, single, semantic broker-capability
issuance. Neither touches a workspace, a run id, a credential, or the
filesystem: the grant is an opaque, module-private-keyed token minted by
:mod:`qualification.i2b_workspace` and carries no authority fact of its own
(design Sec. 2.6.4a EVENT 1). The genuine capability issuance -- the second,
separate authority event -- happens later and elsewhere, inside
:func:`~qualification.i2b_live_adapters.LiveCategoryBAdapters.create_broker`
(via :func:`~qualification.i2b_workspace.build_semantic_task_live_adapters`,
already-accepted 5F3B-LIVE1-C1 machinery this module only *consumes*), at
the first adapter call that carries both the run id and the exact verified
workspace (design Sec. 2.6.4a EVENT 2). This module never derives a
manifest, resolves a Git executable, mints a
:class:`~ar2.capability.StaticEligibilityDomain`, or touches
``ar2.capability``/``ar2.observation`` directly -- all of that is C1's own,
already-accepted, unmodified machinery.

Task-local ownership, and candidate blindness
-----------------------------------------------

One instance is bound to exactly one frozen task, holds at most one live
semantic transport (:class:`_LiveSemanticTransport`), and is looked up by
the frozen ``RuntimeSession``'s three ids together -- never by
``runtime_session_id`` alone -- on every port that consumes one. There is no
process-global registry: the transport hangs off the adapter instance, which
is unreachable once the owning task attempt returns.

**This class receives no ``candidate``, ``model``, ``model_id``, ``provider``,
or ``route`` parameter, anywhere, and contains no candidate-specific branch.**
Candidate identity stays in the runner and reaches only the frozen
candidate-aware consumers (``run_primary_sweep``,
``build_authenticated_route_checker``); it never reaches this module or the
task prompt it transmits.

Prompt authority
------------------

The transmitted text is always exactly ``self._task.prompt`` -- the frozen
corpus's own wording, read at the one write site inside
:meth:`dispatch_semantic_prompt`. There is no ``prompt``/``message``/
``text``/``instruction``/``prefix``/``suffix``/``preamble``/``system``/
``template`` parameter anywhere on this module's public surface, and the RPC
command dict has exactly three keys: ``id``, ``type``, ``message``. No
``maxTokens``/``max_tokens``/``images``/``streamingBehavior``/
``thinkingLevel`` is ever sent -- the frozen unlimited-output policy is
preserved by omission.

Stream ownership
-------------------

The one ``ar2.supervisor.PiRpcSupervisor`` bound to this task's transport
remains the sole reader of Pi's RPC record stream. This module adds no
second stdout reader, JSONL parser, or record buffer: it consumes only the
supervisor's already-bounded public surfaces (``send_command``,
``await_response``, ``await_settled``, ``stdout_state``, ``sanitized_events``,
``activity``, ``process``, ``stdin_write_error``). No raw Pi record, no
``error`` string, no assistant text, and no reasoning content is ever
retained here -- only booleans, small bounded integers, and declared enum
members.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ar2.capability import CapDefinitions
from ar2.supervisor import (
    RUNTIME_DEADLINE_EXPIRED,
    RUNTIME_EVENT_CAP_EXCEEDED,
    RUNTIME_EXITED_EARLY,
    RUNTIME_OUTPUT_CAP_EXCEEDED,
    RUNTIME_PROTOCOL_VIOLATION,
    RUNTIME_READ_ERROR,
    RUNTIME_RESPONSE_RECEIVED,
    RUNTIME_SETTLED,
    PiRpcSupervisor,
    RunBounds,
)

from .corpus import QualificationTask, TASKS_BY_ID
from .i2b_live_adapters import (
    IssuedRuntimeIdentity,
    LiveCategoryBAdapters,
    build_semantic_task_live_adapters,
    resolve_pi_identity,
)
from .i2b_session import (
    BrokerCreationObservation,
    BrokerCreationRequest,
    BrokerShutdownObservation,
    BrokerSession,
    GetCommandsObservation,
    GetStateObservation,
    ProtocolObservation,
    RuntimeLaunchObservation,
    RuntimeLaunchRequest,
    RuntimeSession,
    RuntimeShutdownObservation,
)
from .i2b_workspace import grant_semantic_capability_issuance
from .refusal_projection import project_broker_refusal_reason
from .runtime_activity import project_runtime_tool_activity
from .scope import BUDGET_EXHAUSTED_REASON_CODE, RefusalEvent
from .semantic_session import (
    BrokerActivityObservation,
    FinalReportClaimsObservation,
    SemanticDispatchEvidenceCode,
    SemanticPromptDispatchObservation,
    SemanticPromptDispatchState,
    SemanticPromptRequest,
    SemanticTurnObservation,
    SemanticTurnOutcome,
    SemanticTurnRequest,
)

__all__ = ("LiveSemanticAdapterError", "LiveSemanticAdapters")


class LiveSemanticAdapterError(RuntimeError):
    """A live semantic adapter port could not complete its call. Fails closed.

    Deliberately a bare, literal-string exception, in the exact lineage of
    :class:`qualification.i2b_live_adapters.LiveAdapterError`: every message
    here is a fixed sentence naming no runtime value (no path, no id, no
    credential, no raw RPC body, no prompt text). The frozen controller
    reduces any exception raised from an injected adapter to a bounded
    failure code and never reads this message.
    """


#: The frozen record-stream event kinds one agent turn can produce. Design
#: Sec. 7.4/7.5. A positive delta across ANY of these, observed strictly
#: after this dispatch's own write, mechanically proves an agent loop ran on
#: THIS session as a consequence of THIS write -- AIDO is the only writer to
#: this child's stdin (Sec. 7.2), and it has issued exactly two prior
#: commands (``h1``, ``h2``), neither of which is a ``prompt``.
_AGENT_LOOP_EVENT_TYPES: tuple[str, ...] = (
    "agent_start",
    "turn_start",
    "message_start",
    "message_end",
    "turn_end",
    "tool_execution_start",
    "tool_execution_end",
    "agent_end",
    "agent_settled",
)

#: The fixed, deterministic RPC id for the ONE semantic prompt command this
#: module will ever write for one task attempt. AIDO issues exactly three
#: commands on a semantic task's child stdin -- ``h1`` (get_commands, inside
#: launch_runtime), ``h2`` (get_state), and this one -- so a fixed literal is
#: unambiguous by construction (design Sec. 7.2).
_PROMPT_COMMAND_ID = "s1"

#: The two prior command ids a semantic dispatch's own precondition P6
#: requires to have already produced a correlated response -- the
#: single-writer, one-command-in-flight-at-a-time discipline Sec. 7.6.1's
#: U1/U2 depend on.
_PRIOR_COMMAND_IDS: tuple[str, ...] = ("h1", "h2")

#: ``await_response``'s recognized outcome domain reachable BEFORE an
#: acknowledgement (design Sec. 7.5 D). Anything outside this set is
#: unrecognized and fails closed (branch E) rather than being guessed.
_STREAM_TERMINAL_BEFORE_ACK: frozenset[str] = frozenset(
    {
        RUNTIME_PROTOCOL_VIOLATION,
        RUNTIME_OUTPUT_CAP_EXCEEDED,
        RUNTIME_EVENT_CAP_EXCEEDED,
        RUNTIME_READ_ERROR,
        RUNTIME_EXITED_EARLY,
    }
)

#: ``await_settled``'s recognized outcome domain (design Sec. 8.2 S3), mapped
#: through a POSITIVE allowlist -- never a negative one. Anything outside
#: this set fails closed to ``OBSERVATION_FAILED`` exactly like a recognized
#: stream-terminal outcome does.
_RECOGNIZED_TURN_WAIT_OUTCOMES: frozenset[str] = frozenset(
    {
        RUNTIME_SETTLED,
        RUNTIME_DEADLINE_EXPIRED,
        RUNTIME_PROTOCOL_VIOLATION,
        RUNTIME_OUTPUT_CAP_EXCEEDED,
        RUNTIME_EVENT_CAP_EXCEEDED,
        RUNTIME_READ_ERROR,
        RUNTIME_EXITED_EARLY,
    }
)

#: Both waits reuse the frozen ``ar2.supervisor.RunBounds`` defaults --
#: exactly the bound Category-B already uses for its own startup/turn waits
#: (design Sec. 5). No new timeout policy is introduced here.
_DEFAULT_BOUNDS = RunBounds()

#: Mirrors ``qualification.semantic_session``'s own operation-count caps, so
#: a broker count above the bound fails this module's OWN construction
#: closed (``call_succeeded=False``) rather than letting
#: ``BrokerActivityObservation.__post_init__`` raise and be reduced to a
#: generic ``ADAPTER_RAISED`` further up (design matrix case 38: "never
#: clamped").
_MAX_READ_OPERATIONS = 32
_MAX_EDIT_OPERATIONS = 16
_MAX_REFUSAL_EVENTS = 256

# Design Sec. 9.3: ``changed_file_budget_exhausted`` is a hard disqualifier
# only for a refusal of a THIRD distinct implementation-file attempt, which
# is reachable only because ``MAX_CHANGED_FILES_PER_RUN == 2``. Pinned here
# so a future cap change breaks this module's own test suite loudly instead
# of silently mis-attributing a hard disqualifier.
assert CapDefinitions().max_changed_files_per_run == 2, (
    "qualification.semantic_live_adapters: the frozen budget-exhaustion "
    "hard-disqualifier derivation assumes max_changed_files_per_run == 2"
)


@dataclass(frozen=True)
class _DispatchBaseline:
    """The correlation state captured immediately before the ONE write.

    Design Sec. 7.4. Exists so "an agent run was observed" and "a parse
    failure was observed" are always DELTAS since this dispatch, never
    absolute counts an earlier phase (or an earlier task's leaked state --
    structurally impossible here, see the module docstring) could have
    produced.
    """

    records_ingested: int
    agent_loop_event_counts: dict[str, int]
    unmatched_response_ids: int
    agent_end_count: int
    settled: bool
    #: 5F3B-HARNESS-OBS1 Sec. 5.2. ``activity.tool_calls`` is a dict keyed by
    #: CALL ID, not a monotonic counter, so a per-dispatch delta-of-count
    #: cannot correlate its entries: a key present before this dispatch would
    #: silently persist and be miscounted as this attempt's own activity. This
    #: frozen pre-send snapshot makes the exclusion MECHANICAL -- the
    #: projection retains only entries whose key is absent from it -- rather
    #: than relying on the "one adapter owns one transport" invariant holding.
    pre_dispatch_tool_call_ids: frozenset[str] = frozenset()

    @staticmethod
    def capture(supervisor: PiRpcSupervisor) -> "_DispatchBaseline":
        state = supervisor.stdout_state()
        activity = supervisor.activity
        return _DispatchBaseline(
            records_ingested=state["records_ingested"],
            agent_loop_event_counts={
                kind: activity.event_type_counts.get(kind, 0)
                for kind in _AGENT_LOOP_EVENT_TYPES
            },
            unmatched_response_ids=len(activity.unmatched_response_ids),
            agent_end_count=activity.agent_end_count,
            settled=activity.settled,
            # Captured at the SAME pre-send instant as every other baseline
            # field -- `capture` itself runs strictly before `send_command`.
            pre_dispatch_tool_call_ids=frozenset(activity.tool_calls.keys()),
        )


@dataclass
class _LiveSemanticTransport:
    """The ONE live semantic transport a single task-local adapter may own.

    Design Sec. 3.2. Adapter-private, never placed on a frozen PRE1 value
    object (:class:`~qualification.i2b_session.RuntimeSession` and friends
    stay exactly correlation identifiers). Bound to one
    :class:`~ar2.supervisor.PiRpcSupervisor` and one
    :class:`~ar2.broker.BrokerRequestHandler`, neither ever re-created for
    this transport's lifetime.
    """

    run_id: str
    broker_session_id: str
    runtime_session_id: str
    supervisor: PiRpcSupervisor
    broker_handler: Any
    task_id: str
    task_revision: str
    baseline: _DispatchBaseline | None = field(default=None)
    prompt_command_id: str | None = field(default=None)
    dispatch_observation: SemanticPromptDispatchObservation | None = field(default=None)
    dispatch_completed: bool = field(default=False)
    turn_observed: bool = field(default=False)
    broker_activity_collected: bool = field(default=False)
    report_claims_collected: bool = field(default=False)
    retired: bool = field(default=False)


class LiveSemanticAdapters:
    """One task's live semantic adapter: the delegated Category-B base plus
    the four frozen semantic ports.

    See the module docstring for the full activation, ownership, and
    candidate-blindness contract. This class's constructor accepts exactly
    ``task`` and ``environ_reader`` -- no ``candidate``, ``model``,
    ``model_id``, ``provider``, ``runtime_identity``, ``git_executable``,
    ``capability_source``, ``capability_factory``, ``sed``, or ``domain``
    parameter exists anywhere on it.
    """

    def __init__(self, *, task: QualificationTask, environ_reader: Any) -> None:
        if type(task) is not QualificationTask or TASKS_BY_ID.get(task.task_id) is not task:
            raise LiveSemanticAdapterError(
                "live semantic adapter refused: task must be exactly one of the "
                "frozen qualification.corpus tasks"
            )
        self._task = task
        self._environ_reader = environ_reader
        self._activated = False
        self._base: LiveCategoryBAdapters | None = None
        self._pending_broker_handler: Any = None
        self._transport: _LiveSemanticTransport | None = None

    # -- activation -----------------------------------------------------

    def read_connection(self) -> Any:
        """The ONE activation trigger (design Sec. 12.2A.2/.3).

        Called by the frozen controller exactly once, and only after every
        one of this task's eight Category-A non-secret gates has already
        passed. Binds the RUNTIME IDENTITY (one ``--version`` probe, via
        :func:`~qualification.i2b_live_adapters.resolve_pi_identity`) and
        authorizes this task's ONE future semantic capability issuance (via
        :func:`~qualification.i2b_workspace.grant_semantic_capability_issuance`)
        -- neither touches a workspace, a run id, or a credential. It then
        delegates the ONE credential read to the freshly composed base
        adapter's own ``read_connection``.

        Marks this instance activated BEFORE either operation runs, so a
        raised :class:`~ar2.launch.LaunchIdentityError` or a bounded
        :class:`~qualification.i2b_live_adapters.LiveAdapterError` from
        construction below still leaves a SECOND call refusing outright,
        with no second identity probe and no second grant.

        **5F3B-LIVE1-I1-FU1 ordering.** The identity probe runs BEFORE the
        C1 capability grant is minted -- matching FU4A's identity-first
        activation order and avoiding minting an otherwise-unused,
        unrevocable grant when the probe itself fails. The grant carries no
        workspace/run authority of its own (design Sec. 2.6.4a EVENT 1) and
        this reordering changes only WHEN it is minted, never what it
        authorizes; C1's public API (`grant_semantic_capability_issuance`,
        `build_semantic_task_live_adapters`) is unchanged and unmodified.
        """
        if self._activated:
            raise LiveSemanticAdapterError(
                "read_connection refused: this adapter has already been "
                "activated once"
            )
        self._activated = True
        identity: IssuedRuntimeIdentity = resolve_pi_identity()
        grant = grant_semantic_capability_issuance(self._task)
        base = build_semantic_task_live_adapters(
            environ_reader=self._environ_reader,
            runtime_identity=identity,
            capability_grant=grant,
        )
        self._base = base
        return base.read_connection()

    def _require_activated(self) -> LiveCategoryBAdapters:
        if self._base is None:
            raise LiveSemanticAdapterError(
                "port refused: this adapter has not been activated via "
                "read_connection"
            )
        return self._base

    def base_for_route_authority(self) -> LiveCategoryBAdapters:
        """The ONE accessor the runner's route-checker binder may use.

        Raises when unactivated rather than activating -- the route checker
        must never trigger activation itself (design Sec. 12.2A.4 R3).
        Returns the composed, exact-type ``LiveCategoryBAdapters`` so the
        frozen ``AuthenticatedB300RouteObserver``'s ``type(adapters) is
        LiveCategoryBAdapters`` check passes unweakened.
        """
        return self._require_activated()

    # -- delegated zero-prompt ports --------------------------------------

    def create_broker(self, request: BrokerCreationRequest) -> BrokerCreationObservation:
        """Delegate broker creation; bind THIS task's broker handler.

        This is the design's EVENT 2 (design Sec. 2.6.4a): the first
        adapter call carrying both ``request.run_id`` and the exact
        ``request.workspace``, which is why the already-accepted C1
        capability issuance happens inside the delegated
        ``self._base.create_broker`` and not here. This method's own job is
        narrower: bind the resulting
        :class:`~ar2.broker.BrokerRequestHandler` -- the ONE private read of
        the base adapter's own ``_brokers`` registry (design Sec. 11.3 READ
        1) -- so :meth:`collect_broker_activity` can later read the SAME
        run's own accumulated broker state.
        """
        base = self._require_activated()
        observation = base.create_broker(request)
        if observation.session is not None:
            record = base._brokers.get(observation.session.session_id)  # READ 1
            if (
                record is None
                or record.run_id != request.run_id
                or record.session is not observation.session
            ):
                raise LiveSemanticAdapterError(
                    "create_broker refused: the returned broker session does "
                    "not match this adapter's own minted record"
                )
            self._pending_broker_handler = record.handler
        return observation

    def shutdown_broker(self, session: BrokerSession) -> BrokerShutdownObservation:
        return self._require_activated().shutdown_broker(session)

    def launch_runtime(self, request: RuntimeLaunchRequest) -> RuntimeLaunchObservation:
        """Delegate runtime launch; mint THIS task's ONE live transport.

        The ONE private read of the base adapter's own ``_runtimes``
        registry (design Sec. 11.3 READ 2), binding the
        :class:`~ar2.supervisor.PiRpcSupervisor` this task's four semantic
        ports will use for the remainder of the attempt. Refuses a second
        transport for this adapter instance (design Sec. 3.2 rule 2).
        """
        base = self._require_activated()
        observation = base.launch_runtime(request)
        if observation.session is not None:
            record = base._runtimes.get(observation.session.runtime_session_id)  # READ 2
            if (
                record is None
                or record.run_id != observation.session.run_id
                or record.broker_session_id != observation.session.broker_session_id
            ):
                raise LiveSemanticAdapterError(
                    "launch_runtime refused: the returned runtime session "
                    "does not match this adapter's own minted record"
                )
            if self._transport is not None:
                raise LiveSemanticAdapterError(
                    "launch_runtime refused: this adapter already owns a "
                    "live semantic transport"
                )
            if self._pending_broker_handler is None:
                raise LiveSemanticAdapterError(
                    "launch_runtime refused: no broker handler was bound by "
                    "a prior create_broker call on this adapter"
                )
            self._transport = _LiveSemanticTransport(
                run_id=observation.session.run_id,
                broker_session_id=observation.session.broker_session_id,
                runtime_session_id=observation.session.runtime_session_id,
                supervisor=record.supervisor,
                broker_handler=self._pending_broker_handler,
                task_id=self._task.task_id,
                task_revision=self._task.task_revision,
            )
        return observation

    def get_commands(self, session: RuntimeSession) -> GetCommandsObservation:
        return self._require_activated().get_commands(session)

    def get_state(self, session: RuntimeSession) -> GetStateObservation:
        return self._require_activated().get_state(session)

    def observe_protocol(self, session: RuntimeSession) -> ProtocolObservation:
        return self._require_activated().observe_protocol(session)

    def consumed_connection_values(self) -> Any:
        return self._require_activated().consumed_connection_values()

    def launch_diagnostics(self) -> dict[str, dict[str, str]]:
        return self._require_activated().launch_diagnostics()

    def shutdown_runtime(self, session: RuntimeSession) -> RuntimeShutdownObservation:
        """Delegate runtime teardown; retire THIS task's transport afterwards.

        Retirement (``transport.retired = True``) happens strictly AFTER
        the delegated, frozen teardown call returns -- never before, and
        never in place of it. Retirement is adapter-private bookkeeping: it
        is never folded into, or allowed to contradict, the frozen
        :class:`~qualification.i2b_session.RuntimeShutdownObservation` the
        controller reads (design Sec. 13.2).
        """
        base = self._require_activated()
        transport = self._transport_for_session(session)
        if transport is None:
            raise LiveSemanticAdapterError(
                "shutdown_runtime refused: this session does not belong to "
                "this adapter's own live semantic transport"
            )
        observation = base.shutdown_runtime(session)
        transport.retired = True
        return observation

    # -- same-run transport binding ---------------------------------------

    def _transport_for_session(self, session: Any) -> _LiveSemanticTransport | None:
        """The task-local transport, iff ``session`` is mechanically proved
        to be exactly the one this adapter itself minted -- all three ids
        together, never ``runtime_session_id`` alone (design Sec. 3.2 rule
        3). A foreign, stale, or retired session returns ``None`` rather
        than raising, so every caller decides its own failure mode.

        **5F3B-LIVE1-I1-FU1 BLOCKER 1.** ``type(session) is RuntimeSession``
        alone is not enough: the frozen public ``RuntimeSession`` constructor
        validates each id field with ``isinstance(value, str)``
        (``i2b_session._require_pattern``), so a supported caller can build
        an exact ``RuntimeSession`` whose id fields are ``str`` SUBCLASSES
        with a forged ``__eq__``/``__ne__`` -- Python gives a subclass's own
        reflected comparison priority over a plain ``str``'s, so ordinary
        ``!=`` can be fooled into reporting "equal" for genuinely different
        underlying content. Each of the three id fields is therefore
        required to be EXACTLY ``type(...) is str`` before it ever
        participates in a comparison -- never ``isinstance``, never
        ``str(value)``, and never a comparison evaluated first. A malformed
        (non-exact-``str``) identity is unconditionally foreign.
        """
        transport = self._transport
        if transport is None or transport.retired or type(session) is not RuntimeSession:
            return None
        if (
            type(session.run_id) is not str
            or type(session.broker_session_id) is not str
            or type(session.runtime_session_id) is not str
        ):
            return None
        if (
            session.run_id != transport.run_id
            or session.broker_session_id != transport.broker_session_id
            or session.runtime_session_id != transport.runtime_session_id
        ):
            return None
        return transport

    def _task_identity_binds(self, task_id: Any, task_revision: Any) -> bool:
        """Whether ``(task_id, task_revision)`` provably bind to this
        adapter's own frozen task -- exact-type ``str`` first, THEN the
        trusted-dict-identity lookup, THEN direct equality.

        The exact-type check closes an adversarial seam a bare ``isinstance``
        check (which the frozen ``SemanticPromptRequest``/``SemanticTurnRequest``
        themselves use) does not: a ``str`` SUBCLASS may override ``__eq__``/
        ``__ne__`` to force an unrelated value to compare as "equal", and
        Python gives a subclass's own reflected ``__eq__`` priority over a
        plain ``str``'s. Requiring ``type(x) is str`` for both fields BEFORE
        any comparison removes that seam entirely, for both this equality
        check and the dict lookup below.
        """
        if type(task_id) is not str or type(task_revision) is not str:
            return False
        if TASKS_BY_ID.get(task_id) is not self._task:
            return False
        return task_id == self._task.task_id and task_revision == self._task.task_revision

    # -- PHASE 1: semantic prompt dispatch (design Sec. 7) -----------------

    def _pre_write_refusal(
        self,
        request: SemanticPromptRequest,
        code: SemanticDispatchEvidenceCode = SemanticDispatchEvidenceCode.GATE_REFUSED_BEFORE_WRITE,
    ) -> SemanticPromptDispatchObservation:
        """A precondition (P1..P8) failed BEFORE ``send_command`` was ever
        entered -- mechanically ``CONFIRMED_NOT_SENT``, bound to the
        REQUEST's own identity (there may be no transport at all for P1).
        """
        return SemanticPromptDispatchObservation(
            run_id=request.run_id,
            runtime_session_id=request.runtime_session.runtime_session_id,
            task_id=request.task_id,
            task_revision=request.task_revision,
            dispatch_state=SemanticPromptDispatchState.CONFIRMED_NOT_SENT,
            dispatch_evidence_code=code,
        )

    def _observation_for_transport(
        self,
        transport: _LiveSemanticTransport,
        state: SemanticPromptDispatchState,
        code: SemanticDispatchEvidenceCode,
    ) -> SemanticPromptDispatchObservation:
        return SemanticPromptDispatchObservation(
            run_id=transport.run_id,
            runtime_session_id=transport.runtime_session_id,
            task_id=transport.task_id,
            task_revision=transport.task_revision,
            dispatch_state=state,
            dispatch_evidence_code=code,
        )

    def dispatch_semantic_prompt(
        self, request: SemanticPromptRequest
    ) -> SemanticPromptDispatchObservation:
        """Design Sec. 7.5's dispatch algorithm, exactly.

        Every precondition failure (P1..P8) RETURNS ``CONFIRMED_NOT_SENT`` /
        ``GATE_REFUSED_BEFORE_WRITE`` -- mechanically true, because
        ``send_command`` was never entered. Only a genuinely contradictory
        or unrecognized post-write supervisor state RAISES
        :class:`LiveSemanticAdapterError`, which the frozen controller
        reduces to ``SEND_STATE_INDETERMINATE`` / ``ADAPTER_RAISED``.
        """
        transport = self._transport_for_session(request.runtime_session)
        if transport is None:  # P1
            return self._pre_write_refusal(request)
        if transport.dispatch_completed:  # P2: one dispatch per transport, ever
            return self._pre_write_refusal(request)
        if not self._task_identity_binds(request.task_id, request.task_revision):  # P3
            return self._pre_write_refusal(request)
        if self._task.prompt.startswith("/"):  # P4
            return self._pre_write_refusal(request)
        supervisor = transport.supervisor
        if supervisor.stdin_write_error is not None:  # P5
            return self._pre_write_refusal(request)
        responses = supervisor.activity.responses
        if any(command_id not in responses for command_id in _PRIOR_COMMAND_IDS):  # P6
            return self._pre_write_refusal(request)
        if _PROMPT_COMMAND_ID in responses:  # P7
            return self._pre_write_refusal(request)
        if supervisor.process is None or supervisor.process.poll() is not None:  # P8
            return self._pre_write_refusal(request)

        baseline = _DispatchBaseline.capture(supervisor)
        transport.baseline = baseline
        transport.prompt_command_id = _PROMPT_COMMAND_ID
        # D2: mark BEFORE the write. A raised write must never leave this
        # port re-enterable for a second attempt at the one authorized send.
        transport.dispatch_completed = True

        try:
            supervisor.send_command(
                {
                    "id": _PROMPT_COMMAND_ID,
                    "type": "prompt",
                    "message": self._task.prompt,
                }
            )
        except Exception:
            observation = self._observation_for_transport(
                transport,
                SemanticPromptDispatchState.SEND_STATE_INDETERMINATE,
                SemanticDispatchEvidenceCode.WRITE_FAILED_TRANSMISSION_UNKNOWN,
            )
            transport.dispatch_observation = observation
            return observation

        outcome, response = supervisor.await_response(
            _PROMPT_COMMAND_ID, timeout_seconds=_DEFAULT_BOUNDS.startup_deadline_seconds
        )
        observation = self._classify_dispatch(transport, baseline, outcome, response)
        transport.dispatch_observation = observation
        return observation

    def _classify_dispatch(
        self,
        transport: _LiveSemanticTransport,
        baseline: _DispatchBaseline,
        outcome: str,
        response: dict[str, Any] | None,
    ) -> SemanticPromptDispatchObservation:
        supervisor = transport.supervisor
        current_counts = {
            kind: supervisor.activity.event_type_counts.get(kind, 0)
            for kind in _AGENT_LOOP_EVENT_TYPES
        }
        agent_loop_delta = sum(
            current_counts[kind] - baseline.agent_loop_event_counts[kind]
            for kind in _AGENT_LOOP_EVENT_TYPES
        )

        # A. CORRELATED RESPONSE PRESENT.
        if (
            outcome == RUNTIME_RESPONSE_RECEIVED
            and isinstance(response, dict)
            and response.get("type") == "response"
            and response.get("command") == "prompt"
            and response.get("id") == transport.prompt_command_id
        ):
            success = response.get("success")
            if type(success) is bool and success is True:
                return self._observation_for_transport(
                    transport,
                    SemanticPromptDispatchState.CONFIRMED_SENT,
                    SemanticDispatchEvidenceCode.PROMPT_RESPONSE_ACCEPTED,
                )
            if type(success) is bool and success is False:
                if agent_loop_delta > 0:
                    # A CONTRADICTION: the runtime claims nothing was
                    # accepted, yet an agent loop ran on this session after
                    # this write. Never resolved by guessing either way.
                    raise LiveSemanticAdapterError(
                        "dispatch refused: a success:false prompt response "
                        "coexists with observed agent-loop activity for "
                        "this dispatch"
                    )
                return self._observation_for_transport(
                    transport,
                    SemanticPromptDispatchState.CONFIRMED_NOT_SENT,
                    SemanticDispatchEvidenceCode.PROMPT_RESPONSE_REFUSED,
                )
            # missing/non-bool `success`: never a determinate state from a
            # malformed body -- fall through to B..E.

        # B. AGENT RUN OBSERVED (the correlated response was missed).
        if agent_loop_delta > 0:
            return self._observation_for_transport(
                transport,
                SemanticPromptDispatchState.CONFIRMED_SENT,
                SemanticDispatchEvidenceCode.AGENT_RUN_OBSERVED,
            )

        # C. UNPARSEABLE COMMAND REFUSED (design Sec. 7.6, all six
        # conditions U1..U6; U1/U2 are structural invariants of this
        # module's own single-writer, one-command-at-a-time discipline and
        # are not re-checked here as a runtime condition).
        if self._unparseable_refusal_established(transport, baseline, agent_loop_delta):
            return self._observation_for_transport(
                transport,
                SemanticPromptDispatchState.CONFIRMED_NOT_SENT,
                SemanticDispatchEvidenceCode.COMMAND_UNPARSEABLE_REFUSED,
            )

        # D. NO CORRELATED RESPONSE.
        if outcome == RUNTIME_DEADLINE_EXPIRED:
            return self._observation_for_transport(
                transport,
                SemanticPromptDispatchState.SEND_STATE_INDETERMINATE,
                SemanticDispatchEvidenceCode.NO_CORRELATED_RESPONSE_DEADLINE,
            )
        if outcome in _STREAM_TERMINAL_BEFORE_ACK:
            return self._observation_for_transport(
                transport,
                SemanticPromptDispatchState.SEND_STATE_INDETERMINATE,
                SemanticDispatchEvidenceCode.NO_CORRELATED_RESPONSE_STREAM_TERMINAL,
            )

        # E. UNRECOGNIZED SUPERVISOR OUTCOME -- fail closed, never guessed.
        raise LiveSemanticAdapterError(
            "dispatch refused: an unrecognized supervisor wait outcome is "
            "never mapped to a determinate or indeterminate send fact"
        )

    def _unparseable_refusal_established(
        self,
        transport: _LiveSemanticTransport,
        baseline: _DispatchBaseline,
        agent_loop_delta: int,
    ) -> bool:
        """Design Sec. 7.6.1's U4/U5/U6 -- U1/U2/U3 are structural (see
        :meth:`_classify_dispatch`'s own note) and are not runtime checks.
        """
        supervisor = transport.supervisor
        if transport.prompt_command_id in supervisor.activity.responses:  # U5 fails
            return False
        if agent_loop_delta != 0:  # U6 fails
            return False
        if len(supervisor.activity.unmatched_response_ids) <= baseline.unmatched_response_ids:
            return False
        for record in supervisor.sanitized_events()[baseline.records_ingested :]:
            if (
                isinstance(record, dict)
                and record.get("type") == "response"
                and record.get("command") == "parse"
                and type(record.get("success")) is bool
                and record.get("success") is False
                and "id" not in record
            ):
                return True
        return False

    # -- PHASE 2: semantic turn observation (design Sec. 8) ----------------

    def observe_semantic_turn(self, request: SemanticTurnRequest) -> SemanticTurnObservation:
        """Design Sec. 8.2's turn algorithm.

        Every precondition failure RAISES -- unlike phase 1, this port does
        not mint a substitute observation for a session it does not own; the
        frozen controller itself synthesises the truthful
        ``OBSERVATION_FAILED`` record, which leaves
        ``semantic_prompts_sent = 1`` untouched (design Sec. 8.1).
        """
        transport = self._transport_for_session(request.runtime_session)
        if transport is None:  # T1
            raise LiveSemanticAdapterError(
                "observe_semantic_turn refused: this request does not "
                "belong to this adapter's own live semantic transport"
            )
        if transport.turn_observed:  # T2
            raise LiveSemanticAdapterError(
                "observe_semantic_turn refused: this transport's turn was "
                "already observed once"
            )
        if request.dispatch is not transport.dispatch_observation:  # T3 (identity)
            raise LiveSemanticAdapterError(
                "observe_semantic_turn refused: request.dispatch is not the "
                "exact object this adapter returned from phase 1"
            )
        if not self._task_identity_binds(request.task_id, request.task_revision):  # T4
            raise LiveSemanticAdapterError(
                "observe_semantic_turn refused: task identity/revision does "
                "not bind to this adapter's own frozen task"
            )

        supervisor = transport.supervisor
        outcome = supervisor.await_settled(timeout_seconds=_DEFAULT_BOUNDS.turn_deadline_seconds)
        agent_end_observed = supervisor.activity.agent_end_count > 0

        if outcome not in _RECOGNIZED_TURN_WAIT_OUTCOMES:
            # Fail closed exactly like an unrecognized dispatch-wait
            # outcome: never guessed into SETTLED or DEADLINE_REACHED.
            turn_outcome = SemanticTurnOutcome.OBSERVATION_FAILED
        elif outcome == RUNTIME_SETTLED:
            turn_outcome = SemanticTurnOutcome.SETTLED
        elif outcome == RUNTIME_DEADLINE_EXPIRED:
            turn_outcome = SemanticTurnOutcome.DEADLINE_REACHED
        else:
            turn_outcome = SemanticTurnOutcome.OBSERVATION_FAILED

        # 5F3B-HARNESS-OBS1 Sec. 4.2/5.2/5.3 -- the runtime-activity snapshot is
        # projected HERE, at the exact point this port already reads
        # `supervisor.activity` for its own `agent_end_observed`, and rides out
        # in this ONE already-existing return statement. No new port, no new
        # TaskAdapterBundle member, no new gate, and no new call the controller
        # must make. The projection is into plain ints/bools on a frozen
        # dataclass BEFORE this call even returns, so a later mutation of
        # `activity.tool_calls` cannot reach the returned observation.
        #
        # `transport.baseline` is always present here in practice (phase 2 is
        # entered only after a CONFIRMED_SENT phase 1, which sets it), but
        # without a baseline there is no correlation to THIS dispatch at all --
        # so no correlated fact is invented, and `tool_activity` stays None.
        tool_activity = (
            project_runtime_tool_activity(
                supervisor.activity, transport.baseline, turn_outcome=turn_outcome
            )
            if transport.baseline is not None
            else None
        )

        transport.turn_observed = True
        return SemanticTurnObservation(
            runtime_session_id=transport.runtime_session_id,
            turn_outcome=turn_outcome,
            agent_end_observed=agent_end_observed,
            tool_activity=tool_activity,
        )

    # -- broker activity (design Sec. 9) -----------------------------------

    def collect_broker_activity(self, session: RuntimeSession) -> BrokerActivityObservation:
        """Design Sec. 9.1/9.3's broker-activity derivation.

        Reads only this task's OWN broker handler, bound at
        :meth:`create_broker` time for the SAME run. Every refusal diagnostic
        is reduced through the ONE frozen C2 projection boundary
        (:func:`~qualification.refusal_projection.project_broker_refusal_reason`)
        -- the raw AR2 ``internal_reason`` never reaches
        :class:`~qualification.scope.RefusalEvent.reason_code`.
        """
        transport = self._transport_for_session(session)
        if transport is None:
            raise LiveSemanticAdapterError(
                "collect_broker_activity refused: this session does not "
                "belong to this adapter's own live semantic transport"
            )
        if transport.broker_activity_collected:
            raise LiveSemanticAdapterError(
                "collect_broker_activity refused: broker activity for this "
                "transport was already collected once"
            )
        transport.broker_activity_collected = True

        handler = transport.broker_handler
        if handler is None:
            return BrokerActivityObservation(
                runtime_session_id=transport.runtime_session_id, call_succeeded=False
            )

        consumed = handler.run_state.consumed
        read_count = consumed.read_operations
        edit_count = consumed.edit_operations
        edited_paths = frozenset(handler.run_state.mutated_paths)

        refusals: list[RefusalEvent] = []
        for entry in handler.diagnostics.refusal_reasons:
            parts = entry.split(":", 2)
            if len(parts) != 3:
                # A malformed diagnostic entry proves nothing truthful about
                # this run's activity; fail closed rather than guess a shape.
                return BrokerActivityObservation(
                    runtime_session_id=transport.runtime_session_id, call_succeeded=False
                )
            _operation, error_code, internal_reason = parts
            normalized = project_broker_refusal_reason(
                error_code=error_code, internal_reason=internal_reason
            )
            refusals.append(
                RefusalEvent(
                    reason_code=normalized,
                    path=None,
                    is_third_distinct_implementation_file=(
                        normalized == BUDGET_EXHAUSTED_REASON_CODE
                    ),
                    self_corrected=False,
                )
            )

        if (
            read_count > _MAX_READ_OPERATIONS
            or edit_count > _MAX_EDIT_OPERATIONS
            or len(edited_paths) > _MAX_EDIT_OPERATIONS
            or len(refusals) > _MAX_REFUSAL_EVENTS
        ):
            # Design matrix case 38: a broker count above a frozen
            # BrokerActivityObservation cap fails closed; it is never
            # clamped/truncated to fit.
            return BrokerActivityObservation(
                runtime_session_id=transport.runtime_session_id, call_succeeded=False
            )

        return BrokerActivityObservation(
            runtime_session_id=transport.runtime_session_id,
            call_succeeded=True,
            read_operation_count=read_count,
            edit_operation_count=edit_count,
            edited_paths=edited_paths,
            refusals=tuple(refusals),
        )

    # -- final report claims (design Sec. 10) -------------------------------

    def collect_final_report_claims(
        self, session: RuntimeSession
    ) -> FinalReportClaimsObservation | None:
        """Design Sec. 10.3: R1 bind, R2 one-shot, R3 return ``None``.

        No structured, machine-readable self-report channel exists in the
        Pi seam (design Sec. 10.2), so this module extracts none: returning
        ``None`` here makes the frozen controller record
        ``ReportAvailability.UNAVAILABLE`` -- non-gating, and truthful --
        rather than fabricating an all-``UNKNOWN`` ``ReportClaims`` that
        would read as an accurate self-report.
        """
        transport = self._transport_for_session(session)
        if transport is None:  # R1
            raise LiveSemanticAdapterError(
                "collect_final_report_claims refused: this session does not "
                "belong to this adapter's own live semantic transport"
            )
        if transport.report_claims_collected:  # R2
            raise LiveSemanticAdapterError(
                "collect_final_report_claims refused: this transport's "
                "final report claims were already collected once"
            )
        transport.report_claims_collected = True
        return None  # R3
