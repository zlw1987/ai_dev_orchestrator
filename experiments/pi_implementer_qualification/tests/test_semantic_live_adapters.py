"""5F3B-LIVE1-I1 -- offline regression suite for ``qualification.semantic_live_adapters``.

**OFFLINE ONLY.** No test in this module launches a real Node/Pi process,
opens a real broker pipe, opens a socket, contacts B300, reads a real
credential, sends a real semantic prompt, or calls a model. Every live
primitive (``ar2.supervisor.PiRpcSupervisor``, a broker
``BrokerRequestHandler``, ``qualification.i2b_live_adapters.resolve_pi_identity``'s
one real subprocess probe, and the composed
``qualification.i2b_live_adapters.LiveCategoryBAdapters`` instance) is
replaced by a synthetic double that implements exactly the public surface
:mod:`qualification.semantic_live_adapters` actually calls.

This suite covers the FU4A Sec. 16 offline regression matrix for
``LIVE1-I1``, restricted to the surface this phase actually owns: the four
semantic ports, activation/one-shot lifecycle, task-local ownership, the two
private ``_base`` reads, and candidate blindness. The deeper C1 (capability
issuance), C2 (refusal projection) and C4 (record schema) mechanics are
proved by their own already-accepted suites and are only exercised here
through their frozen public entry points.
"""

from __future__ import annotations

import ast
import inspect
import io
import json
from dataclasses import dataclass, fields
from types import SimpleNamespace

import pytest

from ar2.broker import BrokerDiagnostics
from ar2.capability import ConsumedBudgets, RunState
from ar2.protocol import ReasoningDropStats, RecordStreamReader, decode_record
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
    RuntimeActivity,
)

import qualification.semantic_live_adapters as sla
from qualification.corpus import IQ1_TASK, IQ2_TASK, TASKS_BY_ID
from qualification.i2b_live_adapters import LiveCategoryBAdapters, _LiveBrokerRecord, _LiveRuntimeRecord
from qualification.i2b_session import RuntimeSession
from qualification.i2b_workspace import discard_semantic_capability_grants
from qualification.records import CANDIDATE_MODEL_IDS
from qualification.scope import RefusalEvent
from qualification.semantic_session import (
    SemanticDispatchEvidenceCode,
    SemanticPromptDispatchObservation,
    SemanticPromptDispatchState,
    SemanticPromptRequest,
    SemanticTurnObservation,
    SemanticTurnOutcome,
    SemanticTurnRequest,
    require_dispatch_matches_request,
)

_SOURCE_PATH = "qualification/semantic_live_adapters.py"
with open(_SOURCE_PATH, "r", encoding="utf-8") as _f:
    _SOURCE_TEXT = _f.read()
_SOURCE_AST = ast.parse(_SOURCE_TEXT)


@pytest.fixture(autouse=True)
def _no_leaked_semantic_grants():
    yield
    discard_semantic_capability_grants()


# ===========================================================================
# Fakes
# ===========================================================================


class _FakeSupervisor:
    """A minimal double for ``ar2.supervisor.PiRpcSupervisor``'s public
    surface -- exactly what :mod:`qualification.semantic_live_adapters`
    consumes and nothing more. No real process, no real pipe.
    """

    def __init__(self) -> None:
        self.activity = SimpleNamespace(
            event_type_counts={},
            responses={},
            unmatched_response_ids=[],
            agent_end_count=0,
            agent_end_will_retry_count=0,
            settled=False,
        )
        self.process = SimpleNamespace(poll=lambda: None)
        self.stdin_write_error: str | None = None
        self.sent: list[dict] = []
        self.send_calls = 0
        self.send_raises: Exception | None = None
        self._records_ingested = 0
        self._sanitized_events: list[dict] = []
        # -- await_response knobs --
        self.await_response_outcome = RUNTIME_DEADLINE_EXPIRED
        self.await_response_response: dict | None = None
        #: Simulates records absorbed DURING the wait -- applied as a side
        #: effect of the call, exactly like the real supervisor's `_wait`
        #: drains records as they arrive.
        self.await_response_bump_counts: dict[str, int] = {}
        self.await_response_bump_records: list[dict] = []
        self.await_response_bump_unmatched = 0
        self.await_response_calls: list[tuple[str, float]] = []
        # -- await_settled knobs --
        self.await_settled_outcome = RUNTIME_DEADLINE_EXPIRED
        self.await_settled_bump_agent_end = 0
        self.await_settled_calls = 0

    def send_command(self, command: dict) -> None:
        self.send_calls += 1
        if self.send_raises is not None:
            raise self.send_raises
        self.sent.append(command)

    def await_response(self, command_id: str, *, timeout_seconds: float):
        self.await_response_calls.append((command_id, timeout_seconds))
        for kind, delta in self.await_response_bump_counts.items():
            self.activity.event_type_counts[kind] = (
                self.activity.event_type_counts.get(kind, 0) + delta
            )
        self._sanitized_events.extend(self.await_response_bump_records)
        self.activity.unmatched_response_ids.extend(
            ["<no-id>"] * self.await_response_bump_unmatched
        )
        if self.await_response_response is not None:
            self.activity.responses[self.await_response_response.get("id", command_id)] = (
                self.await_response_response
            )
        return self.await_response_outcome, self.await_response_response

    def await_settled(self, *, timeout_seconds: float) -> str:
        self.await_settled_calls += 1
        self.activity.agent_end_count += self.await_settled_bump_agent_end
        return self.await_settled_outcome

    def stdout_state(self) -> dict:
        return {"records_ingested": self._records_ingested}

    def sanitized_events(self) -> list[dict]:
        return list(self._sanitized_events)


def _fake_supervisor_with_prior_handshake() -> _FakeSupervisor:
    """A supervisor that has already completed the frozen h1/h2 handshake --
    satisfies dispatch precondition P6 for every "happy path" test."""
    supervisor = _FakeSupervisor()
    supervisor.activity.responses["h1"] = {
        "id": "h1",
        "type": "response",
        "command": "get_commands",
        "success": True,
    }
    supervisor.activity.responses["h2"] = {
        "id": "h2",
        "type": "response",
        "command": "get_state",
        "success": True,
    }
    return supervisor


class _FakeBase:
    """A duck-typed double for ``LiveCategoryBAdapters``'s delegated
    surface, used ONLY to test ``LiveSemanticAdapters``'s OWN delegation and
    binding logic in isolation. Never a real broker/runtime resource.
    """

    def __init__(self) -> None:
        self._brokers: dict[str, _LiveBrokerRecord] = {}
        self._runtimes: dict[str, _LiveRuntimeRecord] = {}
        self.read_connection_calls = 0
        self.read_connection_result = "connection-values-sentinel"
        self.create_broker_calls: list[object] = []
        self.create_broker_result: object = None
        self.launch_runtime_calls: list[object] = []
        self.launch_runtime_result: object = None
        self.get_commands_calls: list[object] = []
        self.get_state_calls: list[object] = []
        self.observe_protocol_calls: list[object] = []
        self.shutdown_runtime_calls: list[object] = []
        self.shutdown_broker_calls: list[object] = []
        self.consumed_connection_values_calls = 0
        self.launch_diagnostics_calls = 0

    def read_connection(self):
        self.read_connection_calls += 1
        return self.read_connection_result

    def create_broker(self, request):
        self.create_broker_calls.append(request)
        return self.create_broker_result

    def launch_runtime(self, request):
        self.launch_runtime_calls.append(request)
        return self.launch_runtime_result

    def get_commands(self, session):
        self.get_commands_calls.append(session)
        return "get-commands-sentinel"

    def get_state(self, session):
        self.get_state_calls.append(session)
        return "get-state-sentinel"

    def observe_protocol(self, session):
        self.observe_protocol_calls.append(session)
        return "observe-protocol-sentinel"

    def shutdown_runtime(self, session):
        self.shutdown_runtime_calls.append(session)
        return "shutdown-runtime-sentinel"

    def shutdown_broker(self, session):
        self.shutdown_broker_calls.append(session)
        return "shutdown-broker-sentinel"

    def consumed_connection_values(self):
        self.consumed_connection_values_calls += 1
        return "connection-values-sentinel"

    def launch_diagnostics(self):
        self.launch_diagnostics_calls += 1
        return {}


def _environ_reader(name, default=None):
    return default


def _runtime_session(
    *, run_id="run-1", broker_session_id="brk-1", runtime_session_id="rt-1"
) -> RuntimeSession:
    return RuntimeSession(
        run_id=run_id, broker_session_id=broker_session_id, runtime_session_id=runtime_session_id
    )


def _adapter_with_transport(
    *,
    task=IQ1_TASK,
    supervisor: _FakeSupervisor | None = None,
    broker_handler=None,
    run_id="run-1",
    broker_session_id="brk-1",
    runtime_session_id="rt-1",
):
    """A ``LiveSemanticAdapters`` whose own live semantic transport is
    injected directly -- the four semantic ports never read ``self._base``,
    so this exercises their real production logic without going through
    activation at all.
    """
    adapters = sla.LiveSemanticAdapters(task=task, environ_reader=_environ_reader)
    supervisor = supervisor or _fake_supervisor_with_prior_handshake()
    adapters._transport = sla._LiveSemanticTransport(
        run_id=run_id,
        broker_session_id=broker_session_id,
        runtime_session_id=runtime_session_id,
        supervisor=supervisor,
        broker_handler=broker_handler,
        task_id=task.task_id,
        task_revision=task.task_revision,
    )
    session = _runtime_session(
        run_id=run_id, broker_session_id=broker_session_id, runtime_session_id=runtime_session_id
    )
    return adapters, session, supervisor


def _prompt_request(*, task=IQ1_TASK, session: RuntimeSession, task_revision: str | None = None):
    return SemanticPromptRequest(
        run_id=session.run_id,
        runtime_session=session,
        task_id=task.task_id,
        task_revision=task_revision if task_revision is not None else task.task_revision,
    )


def _dispatch(adapters, session, *, task=IQ1_TASK, task_revision=None):
    request = _prompt_request(task=task, session=session, task_revision=task_revision)
    return adapters.dispatch_semantic_prompt(request), request


def _confirmed_sent(adapters, session, *, task=IQ1_TASK):
    """Drive one successful dispatch, returning (observation, request)."""
    supervisor = adapters._transport.supervisor
    supervisor.await_response_outcome = RUNTIME_RESPONSE_RECEIVED
    supervisor.await_response_response = {
        "id": "s1",
        "type": "response",
        "command": "prompt",
        "success": True,
    }
    observation, request = _dispatch(adapters, session, task=task)
    assert observation.dispatch_state is SemanticPromptDispatchState.CONFIRMED_SENT
    return observation, request


# ===========================================================================
# Section A -- Phase 1 dispatch algorithm
# ===========================================================================


def test_dispatch_success_true_is_confirmed_sent():
    adapters, session, supervisor = _adapter_with_transport()
    observation, request = _confirmed_sent(adapters, session)
    assert observation.dispatch_evidence_code is (
        SemanticDispatchEvidenceCode.PROMPT_RESPONSE_ACCEPTED
    )
    assert require_dispatch_matches_request(observation, request)
    assert supervisor.send_calls == 1


def test_dispatch_success_false_is_confirmed_not_sent():
    adapters, session, supervisor = _adapter_with_transport()
    supervisor.await_response_outcome = RUNTIME_RESPONSE_RECEIVED
    supervisor.await_response_response = {
        "id": "s1",
        "type": "response",
        "command": "prompt",
        "success": False,
    }
    observation, request = _dispatch(adapters, session)
    assert observation.dispatch_state is SemanticPromptDispatchState.CONFIRMED_NOT_SENT
    assert observation.dispatch_evidence_code is (
        SemanticDispatchEvidenceCode.PROMPT_RESPONSE_REFUSED
    )
    assert require_dispatch_matches_request(observation, request)


def test_dispatch_write_failure_is_indeterminate():
    adapters, session, supervisor = _adapter_with_transport()
    supervisor.send_raises = OSError("synthetic stdin failure")
    observation, request = _dispatch(adapters, session)
    assert observation.dispatch_state is SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
    assert observation.dispatch_evidence_code is (
        SemanticDispatchEvidenceCode.WRITE_FAILED_TRANSMISSION_UNKNOWN
    )
    assert require_dispatch_matches_request(observation, request)


def test_dispatch_deadline_with_no_response_is_indeterminate():
    adapters, session, supervisor = _adapter_with_transport()
    supervisor.await_response_outcome = RUNTIME_DEADLINE_EXPIRED
    observation, _ = _dispatch(adapters, session)
    assert observation.dispatch_state is SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
    assert observation.dispatch_evidence_code is (
        SemanticDispatchEvidenceCode.NO_CORRELATED_RESPONSE_DEADLINE
    )


@pytest.mark.parametrize(
    "outcome",
    [
        RUNTIME_PROTOCOL_VIOLATION,
        RUNTIME_OUTPUT_CAP_EXCEEDED,
        RUNTIME_EVENT_CAP_EXCEEDED,
        RUNTIME_READ_ERROR,
        RUNTIME_EXITED_EARLY,
    ],
)
def test_dispatch_stream_terminal_before_ack_is_indeterminate(outcome):
    adapters, session, supervisor = _adapter_with_transport()
    supervisor.await_response_outcome = outcome
    observation, _ = _dispatch(adapters, session)
    assert observation.dispatch_state is SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
    assert observation.dispatch_evidence_code is (
        SemanticDispatchEvidenceCode.NO_CORRELATED_RESPONSE_STREAM_TERMINAL
    )


def test_dispatch_foreign_id_response_never_establishes_a_send():
    """Matrix case 6. A response carrying a foreign id can never occur from
    the REAL supervisor's own ``await_response`` (its dict lookup makes the
    returned record's id equal the requested command id by construction),
    so this is adversarial: it proves the adapter's own explicit id check is
    load-bearing, not merely redundant with the real class's behaviour.
    """
    adapters, session, supervisor = _adapter_with_transport()
    supervisor.await_response_outcome = RUNTIME_RESPONSE_RECEIVED
    supervisor.await_response_response = {
        "id": "h9",
        "type": "response",
        "command": "prompt",
        "success": True,
    }
    with pytest.raises(sla.LiveSemanticAdapterError):
        _dispatch(adapters, session)


class _ForgedEqSessionIdStr(str):
    """A ``str`` subclass reproducing FU1 BLOCKER 1's exact adversarial
    shape: genuinely different bounded content, but ``__eq__``/``__ne__``
    unconditionally claim equality with whatever they are compared against.
    Reachable ONLY through ``RuntimeSession``'s normal PUBLIC constructor --
    ``_require_pattern`` validates with ``isinstance(value, str)``, which a
    subclass with valid character content satisfies.
    """

    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    def __hash__(self):
        return str.__hash__(self)


def _assert_forgery_mechanically_works(forged: str, real: str) -> None:
    """Prove ordinary Python equality is actually fooled, and that the
    forged value's REAL underlying content differs from what it claims to
    equal -- both required so the regression below is not vacuous."""
    assert forged == real
    assert not (forged != real)
    assert str.__eq__(forged, real) is False


def _forged_runtime_session(
    *,
    forge_run_id: bool = False,
    forge_broker_session_id: bool = False,
    forge_runtime_session_id: bool = False,
    run_id: str = "run-1",
    broker_session_id: str = "brk-1",
    runtime_session_id: str = "rt-1",
) -> RuntimeSession:
    kwargs = dict(
        run_id=run_id, broker_session_id=broker_session_id, runtime_session_id=runtime_session_id
    )
    if forge_run_id:
        kwargs["run_id"] = _ForgedEqSessionIdStr("run-FORGED-not-the-real-one")
    if forge_broker_session_id:
        kwargs["broker_session_id"] = _ForgedEqSessionIdStr("brk-FORGED-not-the-real-one")
    if forge_runtime_session_id:
        kwargs["runtime_session_id"] = _ForgedEqSessionIdStr("rt-FORGED-not-the-real-one")
    return RuntimeSession(**kwargs)  # the NORMAL PUBLIC constructor


@pytest.mark.parametrize(
    "forge_run_id,forge_broker,forge_runtime",
    [
        (True, False, False),
        (False, True, False),
        (False, False, True),
        (True, True, True),
    ],
    ids=["run_id", "broker_session_id", "runtime_session_id", "all_three"],
)
def test_blocker1_transport_for_session_rejects_str_subclass_equality_forging(
    forge_run_id, forge_broker, forge_runtime
):
    """FU1 BLOCKER 1. A publicly-constructed, exact-type ``RuntimeSession``
    whose id field(s) are ``str`` subclasses forging equality with this
    transport's own stored ids must never be accepted: ``type(x) is str`` is
    required for every id field BEFORE any comparison runs.
    """
    adapters, real_session, supervisor = _adapter_with_transport(
        run_id="run-1", broker_session_id="brk-1", runtime_session_id="rt-1"
    )
    forged = _forged_runtime_session(
        forge_run_id=forge_run_id,
        forge_broker_session_id=forge_broker,
        forge_runtime_session_id=forge_runtime,
    )
    if forge_run_id:
        _assert_forgery_mechanically_works(forged.run_id, "run-1")
    if forge_broker:
        _assert_forgery_mechanically_works(forged.broker_session_id, "brk-1")
    if forge_runtime:
        _assert_forgery_mechanically_works(forged.runtime_session_id, "rt-1")

    # The central answer this BLOCKER requires: NO.
    assert adapters._transport_for_session(forged) is None


def test_blocker1_ordinary_foreign_session_still_refuses():
    """Control: the pre-existing ordinary-foreign-session refusal (no
    forgery involved) is preserved unchanged."""
    adapters, real_session, supervisor = _adapter_with_transport(
        run_id="run-1", broker_session_id="brk-1", runtime_session_id="rt-1"
    )
    ordinary_foreign = _runtime_session(runtime_session_id="rt-ordinary-foreign")
    assert adapters._transport_for_session(ordinary_foreign) is None


def test_blocker1_the_same_real_session_is_still_accepted():
    """Control: the transport's OWN genuine session must still be accepted
    -- the hardening must not be so strict it refuses legitimate traffic."""
    adapters, real_session, supervisor = _adapter_with_transport(
        run_id="run-1", broker_session_id="brk-1", runtime_session_id="rt-1"
    )
    assert adapters._transport_for_session(real_session) is adapters._transport


class _ExplodingBrokerHandler:
    """Raises on ANY attribute access -- proves a foreign/forged session
    never reaches broker-handler consumption at all."""

    def __getattr__(self, name):
        raise AssertionError(
            f"broker handler attribute {name!r} was accessed for a session "
            "that should have been refused before any consumption"
        )


@pytest.mark.parametrize(
    "forge_run_id,forge_broker,forge_runtime",
    [
        (True, False, False),
        (False, True, False),
        (False, False, True),
        (True, True, True),
    ],
    ids=["run_id", "broker_session_id", "runtime_session_id", "all_three"],
)
def test_blocker1_forged_session_cannot_reach_any_public_semantic_port(
    forge_run_id, forge_broker, forge_runtime
):
    """The forgery must be refused through the PUBLIC ports themselves --
    dispatch_semantic_prompt, collect_broker_activity,
    collect_final_report_claims, shutdown_runtime -- not merely through the
    private helper. No supervisor send/wait and no broker-handler attribute
    is ever touched.
    """
    adapters, real_session, supervisor = _adapter_with_transport(
        broker_handler=_ExplodingBrokerHandler(),
        run_id="run-1",
        broker_session_id="brk-1",
        runtime_session_id="rt-1",
    )
    forged = _forged_runtime_session(
        forge_run_id=forge_run_id,
        forge_broker_session_id=forge_broker,
        forge_runtime_session_id=forge_runtime,
    )

    # dispatch_semantic_prompt, via the public SemanticPromptRequest constructor.
    request = SemanticPromptRequest(
        run_id="run-1",
        runtime_session=forged,
        task_id=IQ1_TASK.task_id,
        task_revision=IQ1_TASK.task_revision,
    )
    observation = adapters.dispatch_semantic_prompt(request)
    assert observation.dispatch_state is SemanticPromptDispatchState.CONFIRMED_NOT_SENT
    assert observation.dispatch_evidence_code is (
        SemanticDispatchEvidenceCode.GATE_REFUSED_BEFORE_WRITE
    )
    assert supervisor.send_calls == 0
    assert supervisor.await_response_calls == []

    # collect_broker_activity / collect_final_report_claims take the session directly.
    with pytest.raises(sla.LiveSemanticAdapterError):
        adapters.collect_broker_activity(forged)
    with pytest.raises(sla.LiveSemanticAdapterError):
        adapters.collect_final_report_claims(forged)

    # shutdown_runtime requires activation; supply a base that would explode
    # if ever reached, proving the session check happens first.
    class _ExplodingBase:
        def shutdown_runtime(self, session):
            raise AssertionError("shutdown_runtime must not be reached for a forged session")

    adapters._base = _ExplodingBase()
    with pytest.raises(sla.LiveSemanticAdapterError):
        adapters.shutdown_runtime(forged)

    # The real session, by contrast, is still usable afterward.
    assert adapters._transport_for_session(real_session) is adapters._transport


# ===========================================================================
# Case 45 -- Pi 0.84.4 seam-shape drift guard
# ===========================================================================


def _serialize_json_line(value: dict) -> bytes:
    """The Python equivalent of Pi's own ``dist/modes/rpc/jsonl.js``
    ``serializeJsonLine``: one JSON value, LF-terminated, ``ensure_ascii=False``
    so a genuine non-ASCII byte sequence is actually emitted on the wire."""
    return (json.dumps(value, ensure_ascii=False) + "\n").encode("utf-8")


def test_case45_prompt_response_and_id_less_parse_arms_match_the_frozen_pi_seam():
    """Matrix case 45. Source-level drift guard for the exact Pi 0.84.4
    wire arms LIVE1's dispatch classification depends on (design Sec.
    2.1/2.3, ``RpcResponse``'s ``prompt`` success arm, its shared
    ``success:false`` arm, and the id-less ``parse`` failure arm from
    ``rpc-mode.js``'s ``handleInputLine`` ``catch (parseError)``):

        success arm    {id?; type:"response"; command:"prompt"; success:true}
        refused arm    {id?; type:"response"; command:string; success:false; error:string}
        parse arm      {type:"response"; command:"parse"; success:false; error:string}
                       -- NO "id" key at all (JSON.stringify drops `undefined`)

    This feeds REALISTIC Pi-serialized bytes for all three arms through the
    FROZEN ``ar2.protocol`` parser (``decode_record``/``RecordStreamReader``)
    and the FROZEN ``PiRpcSupervisor._absorb``, then asserts the resulting
    ``activity`` state is EXACTLY the shape
    :meth:`~qualification.semantic_live_adapters.LiveSemanticAdapters._classify_dispatch`
    and :meth:`~qualification.semantic_live_adapters.LiveSemanticAdapters._unparseable_refusal_established`
    depend on. No Pi process is launched -- these are bytes constructed to
    match the documented wire shape, not a live capture.
    """
    success_arm = {"id": "s1", "type": "response", "command": "prompt", "success": True}
    refused_arm = {
        "id": "s1",
        "type": "response",
        "command": "prompt",
        "success": False,
        "error": "refused",
    }
    # id-less: exactly what `error(undefined, "parse", ...)` + JSON.stringify
    # produces -- the "id" key is ABSENT, never present-and-null.
    parse_arm = {"type": "response", "command": "parse", "success": False, "error": "bad json"}
    assert "id" not in parse_arm

    for arm in (success_arm, refused_arm, parse_arm):
        wire_bytes = _serialize_json_line(arm)
        # 1) the frozen parser decodes it back to the exact same dict.
        assert decode_record(wire_bytes.rstrip(b"\n")) == arm
        # 2) a full frozen RecordStreamReader accepts the byte stream with
        #    no protocol violation -- the exact LF-framed shape both jsonl.js
        #    and ar2.protocol document.
        reader = RecordStreamReader(
            io.BytesIO(wire_bytes), max_bytes=1 << 16, max_records=10, stats=ReasoningDropStats()
        )
        reader.start()
        reader.finished.wait(timeout=5.0)
        assert reader.protocol_violation is None
        assert reader.record_count() == 1

    # 3) the frozen PiRpcSupervisor._absorb ingests each arm into EXACTLY
    #    the fields LIVE1's dispatch classification reads.
    minimal_self = SimpleNamespace(activity=RuntimeActivity())
    PiRpcSupervisor._absorb(minimal_self, success_arm)
    assert minimal_self.activity.responses["s1"] == success_arm
    assert minimal_self.activity.responses["s1"]["command"] == "prompt"
    assert minimal_self.activity.responses["s1"]["success"] is True
    assert minimal_self.activity.unmatched_response_ids == []

    minimal_self = SimpleNamespace(activity=RuntimeActivity())
    PiRpcSupervisor._absorb(minimal_self, refused_arm)
    assert minimal_self.activity.responses["s1"]["success"] is False

    minimal_self = SimpleNamespace(activity=RuntimeActivity())
    PiRpcSupervisor._absorb(minimal_self, parse_arm)
    # id-less -> NEVER lands in `responses` (no str id to key on) -- it
    # becomes exactly one unmatched-response marker, which is what
    # `_unparseable_refusal_established`'s U4 check depends on.
    assert minimal_self.activity.responses == {}
    assert minimal_self.activity.unmatched_response_ids == ["<no-id>"]

    # 4) end-to-end: feed the REAL decoded/absorbed activity state through
    #    THIS adapter's own classification and prove it reaches exactly the
    #    evidence codes the design assigns to each arm.
    adapters, session, supervisor = _adapter_with_transport()
    supervisor.await_response_outcome = RUNTIME_RESPONSE_RECEIVED
    supervisor.await_response_response = decode_record(
        _serialize_json_line(success_arm).rstrip(b"\n")
    )
    observation, _ = _dispatch(adapters, session)
    assert observation.dispatch_state is SemanticPromptDispatchState.CONFIRMED_SENT
    assert observation.dispatch_evidence_code is (
        SemanticDispatchEvidenceCode.PROMPT_RESPONSE_ACCEPTED
    )

    adapters, session, supervisor = _adapter_with_transport()
    supervisor.await_response_outcome = RUNTIME_RESPONSE_RECEIVED
    supervisor.await_response_response = decode_record(
        _serialize_json_line(refused_arm).rstrip(b"\n")
    )
    observation, _ = _dispatch(adapters, session)
    assert observation.dispatch_state is SemanticPromptDispatchState.CONFIRMED_NOT_SENT
    assert observation.dispatch_evidence_code is (
        SemanticDispatchEvidenceCode.PROMPT_RESPONSE_REFUSED
    )

    adapters, session, supervisor = _adapter_with_transport()
    decoded_parse = decode_record(_serialize_json_line(parse_arm).rstrip(b"\n"))
    supervisor.await_response_outcome = RUNTIME_DEADLINE_EXPIRED
    supervisor.await_response_bump_unmatched = 1
    supervisor.await_response_bump_records = [decoded_parse]
    observation, _ = _dispatch(adapters, session)
    assert observation.dispatch_state is SemanticPromptDispatchState.CONFIRMED_NOT_SENT
    assert observation.dispatch_evidence_code is (
        SemanticDispatchEvidenceCode.COMMAND_UNPARSEABLE_REFUSED
    )


def test_dispatch_foreign_runtime_session_refuses_before_any_write():
    """Matrix cases 7 and 25. A request naming a session this adapter did
    not mint is refused via P1, mechanically true (bound to the request's
    own identity, matching ``require_dispatch_matches_request``), and no
    supervisor method is ever called.
    """
    adapters, session, supervisor = _adapter_with_transport()
    foreign_session = _runtime_session(runtime_session_id="rt-someone-else")
    request = _prompt_request(session=foreign_session)
    observation = adapters.dispatch_semantic_prompt(request)
    assert observation.dispatch_state is SemanticPromptDispatchState.CONFIRMED_NOT_SENT
    assert observation.dispatch_evidence_code is (
        SemanticDispatchEvidenceCode.GATE_REFUSED_BEFORE_WRITE
    )
    assert require_dispatch_matches_request(observation, request)
    assert supervisor.send_calls == 0
    assert supervisor.await_response_calls == []


def test_dispatch_str_subclass_forged_task_revision_cannot_bypass_p3():
    """Adversarial: a ``str`` subclass overriding ``__eq__``/``__ne__`` to
    force "equal" must never bypass the task-revision bind. Python gives a
    subclass's own reflected ``__eq__`` priority over a plain ``str``'s, so
    a naive ``!=`` comparison alone would be fooled; the exact-``type(x) is
    str`` check in ``_task_identity_binds`` closes this before any
    comparison runs.
    """

    class _ForgedEqStr(str):
        def __eq__(self, other):
            return True

        def __ne__(self, other):
            return False

        def __hash__(self):
            return str.__hash__(self)

    adapters, session, supervisor = _adapter_with_transport()
    forged_revision = _ForgedEqStr("totally-not-the-real-revision")
    request = SemanticPromptRequest(
        run_id=session.run_id,
        runtime_session=session,
        task_id=IQ1_TASK.task_id,
        task_revision=forged_revision,
    )
    observation = adapters.dispatch_semantic_prompt(request)
    assert observation.dispatch_state is SemanticPromptDispatchState.CONFIRMED_NOT_SENT
    assert observation.dispatch_evidence_code is (
        SemanticDispatchEvidenceCode.GATE_REFUSED_BEFORE_WRITE
    )
    assert supervisor.send_calls == 0


def test_dispatch_str_subclass_forged_task_id_cannot_bypass_p3():
    class _ForgedEqStr(str):
        def __eq__(self, other):
            return True

        def __ne__(self, other):
            return False

        def __hash__(self):
            return str.__hash__(self)

    adapters, session, supervisor = _adapter_with_transport()
    forged_task_id = _ForgedEqStr(IQ1_TASK.task_id)
    request = SemanticPromptRequest(
        run_id=session.run_id,
        runtime_session=session,
        task_id=forged_task_id,
        task_revision=IQ1_TASK.task_revision,
    )
    observation = adapters.dispatch_semantic_prompt(request)
    assert observation.dispatch_state is SemanticPromptDispatchState.CONFIRMED_NOT_SENT
    assert supervisor.send_calls == 0


def test_dispatch_wrong_task_revision_refuses_before_write():
    adapters, session, supervisor = _adapter_with_transport()
    observation, request = _dispatch(adapters, session, task_revision="not-the-real-revision")
    assert observation.dispatch_state is SemanticPromptDispatchState.CONFIRMED_NOT_SENT
    assert observation.dispatch_evidence_code is (
        SemanticDispatchEvidenceCode.GATE_REFUSED_BEFORE_WRITE
    )
    assert supervisor.send_calls == 0


def test_dispatch_exact_frozen_task_prompt_no_caller_substitution():
    """Matrix case 17. There is no ``prompt``/``message``/``text`` parameter
    anywhere on the public surface, and the transmitted text is exactly
    ``task.prompt``.
    """
    signature = inspect.signature(sla.LiveSemanticAdapters.dispatch_semantic_prompt)
    assert set(signature.parameters) == {"self", "request"}
    signature = inspect.signature(sla.LiveSemanticAdapters.__init__)
    assert set(signature.parameters) == {"self", "task", "environ_reader"}

    adapters, session, supervisor = _adapter_with_transport()
    _confirmed_sent(adapters, session)
    assert len(supervisor.sent) == 1
    assert supervisor.sent[0]["message"] == IQ1_TASK.prompt


def test_dispatch_exactly_one_prompt_command_dict_has_exactly_three_keys():
    """Matrix cases 19, 21, 39: one write, keys exactly {id, type, message},
    no maxTokens/max_tokens/images/streamingBehavior/thinkingLevel."""
    adapters, session, supervisor = _adapter_with_transport()
    _confirmed_sent(adapters, session)
    assert len(supervisor.sent) == 1
    command = supervisor.sent[0]
    assert set(command.keys()) == {"id", "type", "message"}
    assert command["type"] == "prompt"
    assert command["id"] == "s1"


def test_dispatch_is_one_shot_per_transport():
    """P2 (matrix case 20's "no continuation" partner): a second dispatch on
    the SAME transport, after either a determinate or indeterminate first
    dispatch, is refused before any second write.
    """
    adapters, session, supervisor = _adapter_with_transport()
    _confirmed_sent(adapters, session)
    assert supervisor.send_calls == 1

    second_observation, _ = _dispatch(adapters, session)
    assert second_observation.dispatch_state is SemanticPromptDispatchState.CONFIRMED_NOT_SENT
    assert second_observation.dispatch_evidence_code is (
        SemanticDispatchEvidenceCode.GATE_REFUSED_BEFORE_WRITE
    )
    assert supervisor.send_calls == 1  # unchanged: no second write


def test_dispatch_no_second_send_command_call_site_in_source():
    """Matrix case 20. AST: exactly one ``.send_command(`` call in the whole
    production module."""
    calls = [
        node
        for node in ast.walk(_SOURCE_AST)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "send_command"
    ]
    assert len(calls) == 1


def test_dispatch_s1_unused_before_write_h1_h2_never_reused():
    """Matrix case 31."""
    adapters, session, supervisor = _adapter_with_transport()
    supervisor.activity.responses["s1"] = {
        "id": "s1",
        "type": "response",
        "command": "prompt",
        "success": True,
    }
    observation, _ = _dispatch(adapters, session)
    assert observation.dispatch_state is SemanticPromptDispatchState.CONFIRMED_NOT_SENT
    assert observation.dispatch_evidence_code is (
        SemanticDispatchEvidenceCode.GATE_REFUSED_BEFORE_WRITE
    )
    assert supervisor.send_calls == 0


def test_dispatch_missing_h1_or_h2_refuses_before_write():
    adapters, session, supervisor = _adapter_with_transport(supervisor=_FakeSupervisor())
    observation, _ = _dispatch(adapters, session)
    assert observation.dispatch_state is SemanticPromptDispatchState.CONFIRMED_NOT_SENT
    assert supervisor.send_calls == 0


def test_dispatch_no_live_child_refuses_before_write():
    adapters, session, supervisor = _adapter_with_transport()
    supervisor.process = SimpleNamespace(poll=lambda: 0)  # already exited
    observation, _ = _dispatch(adapters, session)
    assert observation.dispatch_state is SemanticPromptDispatchState.CONFIRMED_NOT_SENT
    assert supervisor.send_calls == 0


def test_dispatch_parse_response_before_baseline_does_not_establish_unparseable():
    """Matrix case 32. A parse response present BEFORE the baseline (i.e.
    already reflected in the baseline's own counters) never retroactively
    establishes COMMAND_UNPARSEABLE_REFUSED for THIS dispatch."""
    adapters, session, supervisor = _adapter_with_transport()
    # Already present before dispatch -- part of the baseline itself.
    supervisor._sanitized_events.append(
        {"type": "response", "command": "parse", "success": False}
    )
    supervisor.activity.unmatched_response_ids.append("<no-id>")
    supervisor._records_ingested = 1
    # No NEW growth during the wait; outcome is an ordinary deadline.
    supervisor.await_response_outcome = RUNTIME_DEADLINE_EXPIRED
    observation, _ = _dispatch(adapters, session)
    assert observation.dispatch_evidence_code is (
        SemanticDispatchEvidenceCode.NO_CORRELATED_RESPONSE_DEADLINE
    )


def test_dispatch_unparseable_command_refused():
    adapters, session, supervisor = _adapter_with_transport()
    supervisor.await_response_outcome = RUNTIME_DEADLINE_EXPIRED
    supervisor.await_response_bump_unmatched = 1
    supervisor.await_response_bump_records = [
        {"type": "response", "command": "parse", "success": False}
    ]
    observation, _ = _dispatch(adapters, session)
    assert observation.dispatch_state is SemanticPromptDispatchState.CONFIRMED_NOT_SENT
    assert observation.dispatch_evidence_code is (
        SemanticDispatchEvidenceCode.COMMAND_UNPARSEABLE_REFUSED
    )


def test_dispatch_success_false_with_agent_activity_is_a_contradiction():
    """Matrix case 33."""
    adapters, session, supervisor = _adapter_with_transport()
    supervisor.await_response_outcome = RUNTIME_RESPONSE_RECEIVED
    supervisor.await_response_response = {
        "id": "s1",
        "type": "response",
        "command": "prompt",
        "success": False,
    }
    supervisor.await_response_bump_counts = {"agent_start": 1}
    with pytest.raises(sla.LiveSemanticAdapterError):
        _dispatch(adapters, session)


@pytest.mark.parametrize("malformed_success", ["true", 1, 0])
def test_dispatch_non_bool_success_is_never_determinate_from_the_body(malformed_success):
    """Matrix case 34, non-missing half."""
    adapters, session, supervisor = _adapter_with_transport()
    supervisor.await_response_outcome = RUNTIME_RESPONSE_RECEIVED
    supervisor.await_response_response = {
        "id": "s1",
        "type": "response",
        "command": "prompt",
        "success": malformed_success,
    }
    # A malformed `success` never satisfies branch A's `type(success) is
    # bool` check, so it falls through to B..E exactly like a missing key
    # does; with zero agent-loop delta and no unparseable evidence,
    # RUNTIME_RESPONSE_RECEIVED matches neither D's deadline nor its
    # stream-terminal set, so it fails closed to E (raise) rather than ever
    # being read as CONFIRMED_SENT/CONFIRMED_NOT_SENT.
    with pytest.raises(sla.LiveSemanticAdapterError):
        _dispatch(adapters, session)


def test_dispatch_missing_success_key_is_never_determinate():
    adapters, session, supervisor = _adapter_with_transport()
    supervisor.await_response_outcome = RUNTIME_RESPONSE_RECEIVED
    supervisor.await_response_response = {"id": "s1", "type": "response", "command": "prompt"}
    with pytest.raises(sla.LiveSemanticAdapterError):
        # Falls through to fail-closed E, exactly like the foreign-id case.
        _dispatch(adapters, session)


def test_dispatch_agent_run_observed_when_correlated_response_missed():
    adapters, session, supervisor = _adapter_with_transport()
    supervisor.await_response_outcome = RUNTIME_DEADLINE_EXPIRED
    supervisor.await_response_bump_counts = {"agent_start": 1}
    observation, request = _dispatch(adapters, session)
    assert observation.dispatch_state is SemanticPromptDispatchState.CONFIRMED_SENT
    assert observation.dispatch_evidence_code is SemanticDispatchEvidenceCode.AGENT_RUN_OBSERVED
    assert require_dispatch_matches_request(observation, request)


def test_dispatch_never_writes_while_a_wait_is_outstanding():
    """Matrix case 43: this adapter never issues a second command while an
    earlier wait is outstanding -- proved structurally, because there is
    exactly one ``send_command`` call site (case 20) and dispatch is
    one-shot per transport (P2)."""
    calls = [
        node
        for node in ast.walk(_SOURCE_AST)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "send_command"
    ]
    assert len(calls) == 1


# ===========================================================================
# Section B -- Phase 2 turn observation
# ===========================================================================


def _turn_request(adapters, session, dispatch_observation, *, task=IQ1_TASK):
    return SemanticTurnRequest(
        run_id=session.run_id,
        runtime_session=session,
        task_id=task.task_id,
        task_revision=task.task_revision,
        dispatch=dispatch_observation,
    )


def test_turn_settled():
    adapters, session, supervisor = _adapter_with_transport()
    dispatch_observation, _ = _confirmed_sent(adapters, session)
    supervisor.await_settled_outcome = RUNTIME_SETTLED
    request = _turn_request(adapters, session, dispatch_observation)
    observation = adapters.observe_semantic_turn(request)
    assert type(observation) is SemanticTurnObservation
    assert observation.turn_outcome is SemanticTurnOutcome.SETTLED
    assert observation.agent_end_observed is False


def test_turn_agent_end_alone_never_settles():
    adapters, session, supervisor = _adapter_with_transport()
    dispatch_observation, _ = _confirmed_sent(adapters, session)
    supervisor.await_settled_outcome = RUNTIME_DEADLINE_EXPIRED
    supervisor.await_settled_bump_agent_end = 1
    observation = adapters.observe_semantic_turn(_turn_request(adapters, session, dispatch_observation))
    assert observation.turn_outcome is SemanticTurnOutcome.DEADLINE_REACHED
    assert observation.agent_end_observed is True


def test_turn_repeated_agent_end_including_will_retry_never_settles():
    adapters, session, supervisor = _adapter_with_transport()
    dispatch_observation, _ = _confirmed_sent(adapters, session)
    supervisor.await_settled_outcome = RUNTIME_DEADLINE_EXPIRED
    supervisor.await_settled_bump_agent_end = 3
    observation = adapters.observe_semantic_turn(_turn_request(adapters, session, dispatch_observation))
    assert observation.turn_outcome is not SemanticTurnOutcome.SETTLED
    assert observation.agent_end_observed is True


def test_turn_settled_buffered_during_phase_one_requires_no_extra_wait():
    """Matrix cases 8/35. The frozen ``PiRpcSupervisor`` itself guarantees a
    record absorbed during phase 1's wait is already reflected in
    ``activity.settled`` before phase 2 ever calls ``await_settled`` (design
    Sec. 4.1) -- that buffering mechanic is frozen AR2 behaviour and is not
    re-proved here. What THIS adapter must do is simply trust and forward
    ``await_settled``'s own return value without adding a second wait, which
    this asserts via the call count.
    """
    adapters, session, supervisor = _adapter_with_transport()
    dispatch_observation, _ = _confirmed_sent(adapters, session)
    supervisor.await_settled_outcome = RUNTIME_SETTLED
    observation = adapters.observe_semantic_turn(_turn_request(adapters, session, dispatch_observation))
    assert observation.turn_outcome is SemanticTurnOutcome.SETTLED
    assert supervisor.await_settled_calls == 1


def test_turn_deadline_reached():
    adapters, session, supervisor = _adapter_with_transport()
    dispatch_observation, _ = _confirmed_sent(adapters, session)
    supervisor.await_settled_outcome = RUNTIME_DEADLINE_EXPIRED
    observation = adapters.observe_semantic_turn(_turn_request(adapters, session, dispatch_observation))
    assert observation.turn_outcome is SemanticTurnOutcome.DEADLINE_REACHED
    # Matrix cases 12/13: the send fact itself lives entirely in phase 1's
    # own object, which SemanticTurnObservation cannot carry or contradict.
    assert not hasattr(observation, "dispatch_state")
    assert dispatch_observation.dispatch_state is SemanticPromptDispatchState.CONFIRMED_SENT


@pytest.mark.parametrize(
    "outcome",
    [
        RUNTIME_PROTOCOL_VIOLATION,
        RUNTIME_OUTPUT_CAP_EXCEEDED,
        RUNTIME_EVENT_CAP_EXCEEDED,
        RUNTIME_READ_ERROR,
        RUNTIME_EXITED_EARLY,
        "some_unrecognized_outcome",
    ],
)
def test_turn_stream_failures_and_unrecognized_outcomes_fail_closed(outcome):
    adapters, session, supervisor = _adapter_with_transport()
    dispatch_observation, _ = _confirmed_sent(adapters, session)
    supervisor.await_settled_outcome = outcome
    observation = adapters.observe_semantic_turn(_turn_request(adapters, session, dispatch_observation))
    assert observation.turn_outcome is SemanticTurnOutcome.OBSERVATION_FAILED
    # A failed observation never contests the already-established send fact.
    assert dispatch_observation.dispatch_state is SemanticPromptDispatchState.CONFIRMED_SENT


def test_turn_precondition_failures_raise():
    adapters, session, supervisor = _adapter_with_transport()
    dispatch_observation, _ = _confirmed_sent(adapters, session)

    # T1: a foreign session, paired with its own self-consistent
    # CONFIRMED_SENT dispatch (never this adapter's own transport, which is
    # exactly what the frozen SemanticTurnRequest.__post_init__ would
    # otherwise refuse to even construct).
    foreign_session = _runtime_session(runtime_session_id="rt-foreign")
    foreign_dispatch = SemanticPromptDispatchObservation(
        run_id=foreign_session.run_id,
        runtime_session_id=foreign_session.runtime_session_id,
        task_id=IQ1_TASK.task_id,
        task_revision=IQ1_TASK.task_revision,
        dispatch_state=SemanticPromptDispatchState.CONFIRMED_SENT,
        dispatch_evidence_code=SemanticDispatchEvidenceCode.PROMPT_RESPONSE_ACCEPTED,
    )
    foreign_request = SemanticTurnRequest(
        run_id=foreign_session.run_id,
        runtime_session=foreign_session,
        task_id=IQ1_TASK.task_id,
        task_revision=IQ1_TASK.task_revision,
        dispatch=foreign_dispatch,
    )
    with pytest.raises(sla.LiveSemanticAdapterError):
        adapters.observe_semantic_turn(foreign_request)

    # T2: one observation per transport, ever.
    supervisor.await_settled_outcome = RUNTIME_SETTLED
    adapters.observe_semantic_turn(_turn_request(adapters, session, dispatch_observation))
    with pytest.raises(sla.LiveSemanticAdapterError):
        adapters.observe_semantic_turn(_turn_request(adapters, session, dispatch_observation))


def test_turn_dispatch_object_must_be_the_exact_one_this_adapter_returned():
    """T3: identity, not equality."""
    adapters, session, supervisor = _adapter_with_transport()
    dispatch_observation, _ = _confirmed_sent(adapters, session)
    from dataclasses import replace

    copied = replace(dispatch_observation)
    request = SemanticTurnRequest(
        run_id=session.run_id,
        runtime_session=session,
        task_id=IQ1_TASK.task_id,
        task_revision=IQ1_TASK.task_revision,
        dispatch=copied,
    )
    with pytest.raises(sla.LiveSemanticAdapterError):
        adapters.observe_semantic_turn(request)


def test_turn_str_subclass_forged_task_revision_cannot_bypass_t4():
    """Adversarial: T4 shares ``_task_identity_binds`` with P3 (BLOCKER 1
    style hardening). Constructing a forged ``SemanticTurnRequest`` is
    possible through the public constructor ONLY because the forged
    subclass's ``__ne__`` also fools the FROZEN type's own
    ``dispatch.task_revision != self.task_revision`` consistency check --
    which is exactly why this adapter's own exact-type check must not rely
    on the frozen type to have already caught it.
    """
    adapters, session, supervisor = _adapter_with_transport()
    dispatch_observation, _ = _confirmed_sent(adapters, session)

    class _ForgedEqStr(str):
        def __eq__(self, other):
            return True

        def __ne__(self, other):
            return False

        def __hash__(self):
            return str.__hash__(self)

    forged_revision = _ForgedEqStr("totally-not-the-real-revision")
    _assert_forgery_mechanically_works(forged_revision, IQ1_TASK.task_revision)

    request = SemanticTurnRequest(
        run_id=session.run_id,
        runtime_session=session,
        task_id=IQ1_TASK.task_id,
        task_revision=forged_revision,
        dispatch=dispatch_observation,
    )
    with pytest.raises(sla.LiveSemanticAdapterError):
        adapters.observe_semantic_turn(request)


def test_turn_task_identity_must_bind_to_this_adapters_own_task():
    adapters, session, supervisor = _adapter_with_transport(task=IQ1_TASK)
    dispatch_observation, _ = _confirmed_sent(adapters, session, task=IQ1_TASK)
    with pytest.raises(sla.LiveSemanticAdapterError):
        # A SemanticTurnRequest with IQ2's identity cannot even be
        # constructed against IQ1's CONFIRMED_SENT dispatch (frozen
        # __post_init__ refuses the mismatch already), so this proves the
        # defence-in-depth check is unreachable in a way that still fails
        # closed rather than silently succeeding.
        from qualification.semantic_session import ObservationError

        try:
            request = SemanticTurnRequest(
                run_id=session.run_id,
                runtime_session=session,
                task_id=IQ2_TASK.task_id,
                task_revision=IQ2_TASK.task_revision,
                dispatch=dispatch_observation,
            )
        except ObservationError:
            raise sla.LiveSemanticAdapterError("frozen type refused the mismatch") from None
        adapters.observe_semantic_turn(request)


# ===========================================================================
# Section C -- broker activity
# ===========================================================================


def _fake_handler(*, read_ops=0, edit_ops=0, mutated_paths=(), refusal_reasons=()):
    return SimpleNamespace(
        run_state=SimpleNamespace(
            consumed=SimpleNamespace(read_operations=read_ops, edit_operations=edit_ops),
            mutated_paths=list(mutated_paths),
        ),
        diagnostics=SimpleNamespace(refusal_reasons=list(refusal_reasons)),
    )


def test_broker_activity_bounded_same_run_counts():
    handler = _fake_handler(read_ops=3, edit_ops=1, mutated_paths=["money/rounding.py"])
    adapters, session, _ = _adapter_with_transport(broker_handler=handler)
    observation = adapters.collect_broker_activity(session)
    assert observation.call_succeeded is True
    assert observation.read_operation_count == 3
    assert observation.edit_operation_count == 1
    assert observation.edited_paths == frozenset({"money/rounding.py"})
    assert observation.refusals == ()


def test_broker_activity_foreign_session_refuses():
    handler = _fake_handler()
    adapters, session, _ = _adapter_with_transport(broker_handler=handler)
    foreign = _runtime_session(runtime_session_id="rt-foreign")
    with pytest.raises(sla.LiveSemanticAdapterError):
        adapters.collect_broker_activity(foreign)


def test_broker_activity_is_one_shot():
    handler = _fake_handler()
    adapters, session, _ = _adapter_with_transport(broker_handler=handler)
    adapters.collect_broker_activity(session)
    with pytest.raises(sla.LiveSemanticAdapterError):
        adapters.collect_broker_activity(session)


def test_broker_activity_colon_embedded_reason_is_preserved_intact_before_projection():
    """Matrix case 36. ``entry.split(':', 2)`` must not truncate a dynamic
    ``internal_reason`` that itself embeds a colon. A naive ``split(':')``
    (no maxsplit) would raise ``ValueError`` unpacking 4 parts into 3 names,
    which this module's own fail-closed handling would turn into
    ``call_succeeded=False`` -- so asserting ``call_succeeded is True`` here
    positively distinguishes the correct ``maxsplit=2`` behaviour from that
    bug.
    """
    handler = _fake_handler(
        refusal_reasons=["edit_file:refused:unsafe_lexical_form:CanonicalPathError"]
    )
    adapters, session, _ = _adapter_with_transport(broker_handler=handler)
    observation = adapters.collect_broker_activity(session)
    assert observation.call_succeeded is True
    assert len(observation.refusals) == 1
    assert observation.refusals[0].reason_code == "unrecognized_broker_reason"
    assert observation.refusals[0].path is None


def test_broker_activity_budget_exhausted_is_third_distinct_file():
    """Matrix case 37, pinned to ``max_changed_files_per_run == 2``."""
    from ar2.capability import CapDefinitions

    assert CapDefinitions().max_changed_files_per_run == 2
    handler = _fake_handler(
        refusal_reasons=["edit_file:budget_exhausted:changed_file_budget_exhausted"]
    )
    adapters, session, _ = _adapter_with_transport(broker_handler=handler)
    observation = adapters.collect_broker_activity(session)
    assert observation.refusals[0].reason_code == "changed_file_budget_exhausted"
    assert observation.refusals[0].is_third_distinct_implementation_file is True


def test_broker_activity_no_raw_diagnostic_leaks_into_evidence():
    handler = _fake_handler(
        refusal_reasons=["edit_file:refused:path_policy:/absolute/secret/path"]
    )
    adapters, session, _ = _adapter_with_transport(broker_handler=handler)
    observation = adapters.collect_broker_activity(session)
    for refusal in observation.refusals:
        assert "/absolute/secret/path" not in refusal.reason_code
        assert "path_policy" not in refusal.reason_code


def test_broker_activity_count_above_cap_fails_closed_never_clamped():
    """Matrix case 38."""
    handler = _fake_handler(read_ops=999)
    adapters, session, _ = _adapter_with_transport(broker_handler=handler)
    observation = adapters.collect_broker_activity(session)
    assert observation.call_succeeded is False
    assert observation.read_operation_count == 0
    assert observation.refusals == ()


def test_broker_activity_no_handler_bound_fails_closed():
    adapters, session, _ = _adapter_with_transport(broker_handler=None)
    observation = adapters.collect_broker_activity(session)
    assert observation.call_succeeded is False


# ===========================================================================
# Section D -- final report claims
# ===========================================================================


def test_final_report_claims_returns_none_and_is_one_shot():
    """Matrix case 16."""
    adapters, session, _ = _adapter_with_transport()
    assert adapters.collect_final_report_claims(session) is None
    with pytest.raises(sla.LiveSemanticAdapterError):
        adapters.collect_final_report_claims(session)


def test_final_report_claims_foreign_session_refuses():
    adapters, session, _ = _adapter_with_transport()
    foreign = _runtime_session(runtime_session_id="rt-foreign")
    with pytest.raises(sla.LiveSemanticAdapterError):
        adapters.collect_final_report_claims(foreign)


def test_final_report_claims_never_scores_a_prompt_command():
    """No prohibited semantic command literal (Sec. 17 of the prompt) ever
    appears anywhere in this module's production source."""
    for literal in (
        "steer",
        "follow_up",
        "abort",
        "abort_retry",
        "clear_queue",
        "bash",
        "compact",
        "set_model",
        "new_session",
    ):
        assert f'"{literal}"' not in _SOURCE_TEXT
        assert f"'{literal}'" not in _SOURCE_TEXT


# ===========================================================================
# Section E -- activation, composition, task-local ownership
# ===========================================================================


def test_construction_is_inert(monkeypatch):
    """Zero probe, zero grant, zero base, zero transport at construction."""
    probe_calls = []
    monkeypatch.setattr(sla, "resolve_pi_identity", lambda: probe_calls.append(1))
    grant_calls = []
    monkeypatch.setattr(
        sla,
        "grant_semantic_capability_issuance",
        lambda task: grant_calls.append(task),
    )

    adapters = sla.LiveSemanticAdapters(task=IQ1_TASK, environ_reader=_environ_reader)

    assert probe_calls == []
    assert grant_calls == []
    assert adapters._base is None
    assert adapters._transport is None


def test_construction_refuses_a_foreign_task():
    from dataclasses import replace

    foreign_task = replace(IQ1_TASK)
    with pytest.raises(sla.LiveSemanticAdapterError):
        sla.LiveSemanticAdapters(task=foreign_task, environ_reader=_environ_reader)


def test_activation_probes_identity_grants_capability_and_delegates(monkeypatch):
    probe_calls = []
    grant_calls = []
    build_calls = []
    fake_base = _FakeBase()
    fake_identity = object()
    fake_grant = object()

    def fake_resolve_pi_identity():
        probe_calls.append(1)
        return fake_identity

    def fake_grant_issuance(task):
        grant_calls.append(task)
        return fake_grant

    def fake_build(*, environ_reader, runtime_identity, capability_grant):
        build_calls.append((runtime_identity, capability_grant))
        assert runtime_identity is fake_identity
        assert capability_grant is fake_grant
        return fake_base

    monkeypatch.setattr(sla, "resolve_pi_identity", fake_resolve_pi_identity)
    monkeypatch.setattr(sla, "grant_semantic_capability_issuance", fake_grant_issuance)
    monkeypatch.setattr(sla, "build_semantic_task_live_adapters", fake_build)

    adapters = sla.LiveSemanticAdapters(task=IQ1_TASK, environ_reader=_environ_reader)
    result = adapters.read_connection()

    assert result == "connection-values-sentinel"
    assert fake_base.read_connection_calls == 1
    assert len(probe_calls) == 1
    assert len(grant_calls) == 1
    assert grant_calls[0] is IQ1_TASK
    assert len(build_calls) == 1
    assert adapters._base is fake_base


def test_activation_is_one_shot_and_a_second_call_issues_no_second_probe(monkeypatch):
    """Matrix case 55."""
    probe_calls = []
    monkeypatch.setattr(
        sla, "resolve_pi_identity", lambda: probe_calls.append(1) or object()
    )
    monkeypatch.setattr(sla, "build_semantic_task_live_adapters", lambda **kw: _FakeBase())

    adapters = sla.LiveSemanticAdapters(task=IQ1_TASK, environ_reader=_environ_reader)
    adapters.read_connection()
    assert len(probe_calls) == 1

    with pytest.raises(sla.LiveSemanticAdapterError):
        adapters.read_connection()
    assert len(probe_calls) == 1


def test_a_failed_activation_still_refuses_a_second_call_with_no_second_probe(monkeypatch):
    """A2/A4: a raised activation still leaves the adapter permanently
    activated, so a retry never issues a second probe."""
    probe_calls = []

    def fake_resolve_pi_identity():
        probe_calls.append(1)
        raise RuntimeError("synthetic identity failure")

    monkeypatch.setattr(sla, "resolve_pi_identity", fake_resolve_pi_identity)

    adapters = sla.LiveSemanticAdapters(task=IQ1_TASK, environ_reader=_environ_reader)
    with pytest.raises(RuntimeError):
        adapters.read_connection()
    assert len(probe_calls) == 1

    with pytest.raises(sla.LiveSemanticAdapterError):
        adapters.read_connection()
    assert len(probe_calls) == 1


_DELEGATED_PORT_CALLS = {
    "create_broker": lambda adapters: adapters.create_broker(SimpleNamespace(run_id="run-1")),
    "shutdown_broker": lambda adapters: adapters.shutdown_broker(SimpleNamespace()),
    "launch_runtime": lambda adapters: adapters.launch_runtime(SimpleNamespace()),
    "get_commands": lambda adapters: adapters.get_commands(SimpleNamespace()),
    "get_state": lambda adapters: adapters.get_state(SimpleNamespace()),
    "observe_protocol": lambda adapters: adapters.observe_protocol(SimpleNamespace()),
    "shutdown_runtime": lambda adapters: adapters.shutdown_runtime(SimpleNamespace()),
    "consumed_connection_values": lambda adapters: adapters.consumed_connection_values(),
    "launch_diagnostics": lambda adapters: adapters.launch_diagnostics(),
    "base_for_route_authority": lambda adapters: adapters.base_for_route_authority(),
}


@pytest.mark.parametrize("port_name", sorted(_DELEGATED_PORT_CALLS))
def test_every_non_read_connection_port_refuses_pre_activation(port_name, monkeypatch):
    """Matrix case 50, for every DELEGATED port. The four semantic ports are
    covered separately (they refuse via "no transport", which is the only
    state reachable before activation)."""
    probe_calls = []
    monkeypatch.setattr(
        sla, "resolve_pi_identity", lambda: probe_calls.append(1) or object()
    )
    adapters = sla.LiveSemanticAdapters(task=IQ1_TASK, environ_reader=_environ_reader)
    with pytest.raises(sla.LiveSemanticAdapterError):
        _DELEGATED_PORT_CALLS[port_name](adapters)
    assert probe_calls == []


@pytest.mark.parametrize(
    "port_name,call",
    [
        ("dispatch_semantic_prompt", lambda a: a.dispatch_semantic_prompt(
            _prompt_request(session=_runtime_session())
        )),
        ("observe_semantic_turn", lambda a: a.observe_semantic_turn(
            SemanticTurnRequest(
                run_id="run-1",
                runtime_session=_runtime_session(),
                task_id=IQ1_TASK.task_id,
                task_revision=IQ1_TASK.task_revision,
                dispatch=SemanticPromptDispatchObservation(
                    run_id="run-1",
                    runtime_session_id="rt-1",
                    task_id=IQ1_TASK.task_id,
                    task_revision=IQ1_TASK.task_revision,
                    dispatch_state=SemanticPromptDispatchState.CONFIRMED_SENT,
                    dispatch_evidence_code=SemanticDispatchEvidenceCode.PROMPT_RESPONSE_ACCEPTED,
                ),
            )
        )),
        ("collect_broker_activity", lambda a: a.collect_broker_activity(_runtime_session())),
        (
            "collect_final_report_claims",
            lambda a: a.collect_final_report_claims(_runtime_session()),
        ),
    ],
)
def test_every_semantic_port_refuses_when_no_transport_exists(port_name, call, monkeypatch):
    probe_calls = []
    monkeypatch.setattr(
        sla, "resolve_pi_identity", lambda: probe_calls.append(1) or object()
    )
    adapters = sla.LiveSemanticAdapters(task=IQ1_TASK, environ_reader=_environ_reader)
    # dispatch_semantic_prompt is well-typed and returns rather than raises,
    # so it is checked for the CONFIRMED_NOT_SENT/GATE_REFUSED_BEFORE_WRITE
    # shape instead of an exception.
    if port_name == "dispatch_semantic_prompt":
        observation = call(adapters)
        assert observation.dispatch_state is SemanticPromptDispatchState.CONFIRMED_NOT_SENT
    else:
        with pytest.raises(sla.LiveSemanticAdapterError):
            call(adapters)
    assert probe_calls == []


def test_second_read_connection_refuses_and_no_port_activates_lazily(monkeypatch):
    probe_calls = []
    monkeypatch.setattr(
        sla, "resolve_pi_identity", lambda: probe_calls.append(1) or object()
    )
    monkeypatch.setattr(sla, "build_semantic_task_live_adapters", lambda **kw: _FakeBase())
    adapters = sla.LiveSemanticAdapters(task=IQ1_TASK, environ_reader=_environ_reader)

    with pytest.raises(sla.LiveSemanticAdapterError):
        adapters.get_commands(SimpleNamespace())
    assert probe_calls == []

    adapters.read_connection()
    assert len(probe_calls) == 1


def test_preflight_refusal_style_construction_causes_zero_live_activity(monkeypatch):
    """Matrix case: preflight refusal causes zero Pi/Node/credential/broker/
    runtime/network/semantic activity. Simulated here at the adapter level:
    if the controller's own Category-A gates refuse, ``read_connection`` is
    NEVER called at all, so no probe, no grant, and no base/transport of
    any kind is ever created -- proved by simply never invoking it."""
    probe_calls = []
    grant_calls = []
    monkeypatch.setattr(
        sla, "resolve_pi_identity", lambda: probe_calls.append(1) or object()
    )
    monkeypatch.setattr(
        sla,
        "grant_semantic_capability_issuance",
        lambda task: grant_calls.append(task) or object(),
    )
    adapters = sla.LiveSemanticAdapters(task=IQ1_TASK, environ_reader=_environ_reader)
    assert probe_calls == []
    assert grant_calls == []
    assert adapters._base is None
    assert adapters._transport is None


def test_create_broker_binds_broker_handler_via_the_one_base_brokers_read():
    adapters = sla.LiveSemanticAdapters(task=IQ1_TASK, environ_reader=_environ_reader)
    fake_base = _FakeBase()
    adapters._base = fake_base

    handler = object()
    session = SimpleNamespace(session_id="brk-1")
    fake_base._brokers["brk-1"] = _LiveBrokerRecord(
        server=object(), handler=handler, run_id="run-1", session=session
    )
    fake_base.create_broker_result = SimpleNamespace(session=session)

    request = SimpleNamespace(run_id="run-1")
    observation = adapters.create_broker(request)
    assert observation is fake_base.create_broker_result
    assert adapters._pending_broker_handler is handler


def test_create_broker_refuses_a_mismatched_returned_session():
    adapters = sla.LiveSemanticAdapters(task=IQ1_TASK, environ_reader=_environ_reader)
    fake_base = _FakeBase()
    adapters._base = fake_base

    session = SimpleNamespace(session_id="brk-1")
    # Registry disagrees with the returned observation's run_id.
    fake_base._brokers["brk-1"] = _LiveBrokerRecord(
        server=object(), handler=object(), run_id="run-DIFFERENT", session=session
    )
    fake_base.create_broker_result = SimpleNamespace(session=session)
    request = SimpleNamespace(run_id="run-1")
    with pytest.raises(sla.LiveSemanticAdapterError):
        adapters.create_broker(request)


def test_launch_runtime_binds_transport_via_the_one_base_runtimes_read():
    adapters = sla.LiveSemanticAdapters(task=IQ1_TASK, environ_reader=_environ_reader)
    fake_base = _FakeBase()
    adapters._base = fake_base
    adapters._pending_broker_handler = object()

    supervisor = _FakeSupervisor()
    session = _runtime_session()
    fake_base._runtimes[session.runtime_session_id] = _LiveRuntimeRecord(
        supervisor=supervisor,
        run_id=session.run_id,
        broker_session_id=session.broker_session_id,
        extension_dir="synthetic",
        extension_entry="synthetic",
    )
    fake_base.launch_runtime_result = SimpleNamespace(session=session)

    observation = adapters.launch_runtime(SimpleNamespace())
    assert observation is fake_base.launch_runtime_result
    assert adapters._transport is not None
    assert adapters._transport.supervisor is supervisor
    assert adapters._transport.broker_handler is adapters._pending_broker_handler


def test_launch_runtime_refuses_a_second_transport():
    adapters = sla.LiveSemanticAdapters(task=IQ1_TASK, environ_reader=_environ_reader)
    fake_base = _FakeBase()
    adapters._base = fake_base
    adapters._pending_broker_handler = object()

    session = _runtime_session()
    fake_base._runtimes[session.runtime_session_id] = _LiveRuntimeRecord(
        supervisor=_FakeSupervisor(),
        run_id=session.run_id,
        broker_session_id=session.broker_session_id,
        extension_dir="synthetic",
        extension_entry="synthetic",
    )
    fake_base.launch_runtime_result = SimpleNamespace(session=session)
    adapters.launch_runtime(SimpleNamespace())

    with pytest.raises(sla.LiveSemanticAdapterError):
        adapters.launch_runtime(SimpleNamespace())


def test_launch_runtime_partial_failure_session_none_binds_no_transport():
    """A partial/failed launch (``observation.session is None``) leaves
    this adapter's own transport untouched -- the creator-retained-partial-
    resource contract stays entirely the base adapter's, and this layer
    adds no transport for a resource that was never handed over."""
    adapters = sla.LiveSemanticAdapters(task=IQ1_TASK, environ_reader=_environ_reader)
    fake_base = _FakeBase()
    adapters._base = fake_base
    adapters._pending_broker_handler = object()
    fake_base.launch_runtime_result = SimpleNamespace(session=None)

    observation = adapters.launch_runtime(SimpleNamespace())
    assert observation is fake_base.launch_runtime_result
    assert adapters._transport is None


def test_create_broker_refuses_a_session_with_no_registry_entry_at_all():
    """A session naming a broker record this base never minted at all
    (never merely one with a mismatched field) is refused identically."""
    adapters = sla.LiveSemanticAdapters(task=IQ1_TASK, environ_reader=_environ_reader)
    fake_base = _FakeBase()
    adapters._base = fake_base
    session = SimpleNamespace(session_id="brk-never-minted")
    fake_base.create_broker_result = SimpleNamespace(session=session)
    with pytest.raises(sla.LiveSemanticAdapterError):
        adapters.create_broker(SimpleNamespace(run_id="run-1"))


def test_broker_activity_malformed_diagnostic_entry_fails_closed():
    """A refusal-reasons entry with fewer than two colons is malformed and
    is never guessed into a shape; the call fails closed."""
    handler = _fake_handler(refusal_reasons=["not-a-well-formed-entry"])
    adapters, session, _ = _adapter_with_transport(broker_handler=handler)
    observation = adapters.collect_broker_activity(session)
    assert observation.call_succeeded is False
    assert observation.refusals == ()


def test_launch_runtime_refuses_without_a_prior_broker_handler():
    adapters = sla.LiveSemanticAdapters(task=IQ1_TASK, environ_reader=_environ_reader)
    fake_base = _FakeBase()
    adapters._base = fake_base
    session = _runtime_session()
    fake_base._runtimes[session.runtime_session_id] = _LiveRuntimeRecord(
        supervisor=_FakeSupervisor(),
        run_id=session.run_id,
        broker_session_id=session.broker_session_id,
        extension_dir="synthetic",
        extension_entry="synthetic",
    )
    fake_base.launch_runtime_result = SimpleNamespace(session=session)
    with pytest.raises(sla.LiveSemanticAdapterError):
        adapters.launch_runtime(SimpleNamespace())


def test_shutdown_runtime_retires_only_its_own_transport():
    """Matrix case 24."""
    handler1 = _fake_handler()
    handler2 = _fake_handler()
    adapters1, session1, supervisor1 = _adapter_with_transport(
        broker_handler=handler1, run_id="run-1", runtime_session_id="rt-1"
    )
    adapters2, session2, supervisor2 = _adapter_with_transport(
        broker_handler=handler2, run_id="run-2", runtime_session_id="rt-2"
    )
    adapters1._base = _FakeBase()
    adapters2._base = _FakeBase()

    adapters1.shutdown_runtime(session1)
    assert adapters1._transport.retired is True
    assert adapters2._transport.retired is False


def test_post_teardown_retired_transport_refuses_every_further_port():
    """Adversarial: after a successful ``shutdown_runtime``, the SAME real
    session must be refused by every semantic/session-consuming port --
    ``retired`` is terminal, not merely advisory."""
    handler = _fake_handler(read_ops=1)
    adapters, session, supervisor = _adapter_with_transport(broker_handler=handler)
    adapters._base = _FakeBase()

    adapters.shutdown_runtime(session)
    assert adapters._transport.retired is True

    assert adapters._transport_for_session(session) is None
    with pytest.raises(sla.LiveSemanticAdapterError):
        adapters.collect_broker_activity(session)
    with pytest.raises(sla.LiveSemanticAdapterError):
        adapters.collect_final_report_claims(session)
    # A second shutdown_runtime on the now-retired transport is refused too.
    with pytest.raises(sla.LiveSemanticAdapterError):
        adapters.shutdown_runtime(session)
    observation = adapters.dispatch_semantic_prompt(
        _prompt_request(session=session)
    )
    assert observation.dispatch_state is SemanticPromptDispatchState.CONFIRMED_NOT_SENT
    assert supervisor.send_calls == 0


def test_shutdown_runtime_refuses_a_foreign_session():
    adapters, session, _ = _adapter_with_transport()
    adapters._base = _FakeBase()
    foreign = _runtime_session(runtime_session_id="rt-foreign")
    with pytest.raises(sla.LiveSemanticAdapterError):
        adapters.shutdown_runtime(foreign)


def test_fresh_adapter_and_transport_per_task_no_shared_state():
    """Matrix cases 22, 23."""
    handler_a = _fake_handler(read_ops=1)
    handler_b = _fake_handler(read_ops=2)
    adapters_a, session_a, supervisor_a = _adapter_with_transport(
        task=IQ1_TASK, broker_handler=handler_a, run_id="run-a", runtime_session_id="rt-a"
    )
    adapters_b, session_b, supervisor_b = _adapter_with_transport(
        task=IQ2_TASK, broker_handler=handler_b, run_id="run-b", runtime_session_id="rt-b"
    )
    assert adapters_a is not adapters_b
    assert adapters_a._transport is not adapters_b._transport
    assert supervisor_a is not supervisor_b

    supervisor_a._sanitized_events.append({"type": "message_end"})
    assert supervisor_b.sanitized_events() == []

    activity_a = adapters_a.collect_broker_activity(session_a)
    activity_b = adapters_b.collect_broker_activity(session_b)
    assert activity_a.read_operation_count == 1
    assert activity_b.read_operation_count == 2


def test_base_for_route_authority_raises_when_unactivated():
    adapters = sla.LiveSemanticAdapters(task=IQ1_TASK, environ_reader=_environ_reader)
    with pytest.raises(sla.LiveSemanticAdapterError):
        adapters.base_for_route_authority()


def test_base_for_route_authority_returns_the_activated_base_unmodified(monkeypatch):
    fake_base = _FakeBase()
    monkeypatch.setattr(sla, "resolve_pi_identity", lambda: object())
    monkeypatch.setattr(sla, "build_semantic_task_live_adapters", lambda **kw: fake_base)
    adapters = sla.LiveSemanticAdapters(task=IQ1_TASK, environ_reader=_environ_reader)
    adapters.read_connection()
    assert adapters.base_for_route_authority() is fake_base


def test_composition_not_subclassing():
    """Matrix cases 29, 41."""
    assert not issubclass(sla.LiveSemanticAdapters, LiveCategoryBAdapters)
    assert not isinstance(
        sla.LiveSemanticAdapters(task=IQ1_TASK, environ_reader=_environ_reader),
        LiveCategoryBAdapters,
    )


def test_exactly_two_private_base_reads_in_source():
    """Matrix case 42: AST count of ``self._base._brokers``/``self._base._runtimes``
    style private-attribute reads."""
    reads = 0
    for node in ast.walk(_SOURCE_AST):
        if (
            isinstance(node, ast.Attribute)
            and node.attr in ("_brokers", "_runtimes")
            and isinstance(node.value, ast.Name)
            and node.value.id == "base"
        ):
            reads += 1
    assert reads == 2


def test_no_competing_observation_schema_is_declared():
    """Matrix case 30: AST -- no class named *DispatchObservation /
    *TurnObservation / *ActivityObservation / *ReportClaims* is defined in
    the new module."""
    forbidden_suffixes = (
        "DispatchObservation",
        "TurnObservation",
        "ActivityObservation",
        "ReportClaims",
    )
    for node in ast.walk(_SOURCE_AST):
        if isinstance(node, ast.ClassDef):
            assert not any(node.name.endswith(suffix) for suffix in forbidden_suffixes), node.name


def test_no_candidate_identity_anywhere_in_the_adapter_module():
    """Matrix case 41 (15.3.1): no string literal "A"/"B", no reference to
    CANDIDATE_MODEL_IDS, no candidate/model/model_id/provider parameter."""
    for node in ast.walk(_SOURCE_AST):
        if isinstance(node, ast.Constant) and node.value in ("A", "B"):
            pytest.fail(f"candidate literal {node.value!r} found in semantic_live_adapters.py")
        if isinstance(node, ast.Name) and node.id == "CANDIDATE_MODEL_IDS":
            pytest.fail("CANDIDATE_MODEL_IDS referenced in semantic_live_adapters.py")
    for node in ast.walk(_SOURCE_AST):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names = {arg.arg for arg in node.args.args + node.args.kwonlyargs}
            for forbidden in ("candidate", "model", "model_id", "provider"):
                assert forbidden not in names, f"{node.name} accepts {forbidden!r}"


def test_live_semantic_adapters_constructor_has_no_forbidden_parameter():
    """Matrix case 54."""
    signature = inspect.signature(sla.LiveSemanticAdapters.__init__)
    forbidden = {
        "candidate",
        "model",
        "model_id",
        "provider",
        "runtime_identity",
        "capability_source",
        "capability_factory",
        "sed",
        "domain",
        "git_executable",
    }
    assert forbidden.isdisjoint(signature.parameters)


def test_source_drift_guards_on_frozen_surfaces():
    """Matrix case 40."""
    for attr in (
        "send_command",
        "await_response",
        "await_settled",
        "stdout_state",
        "sanitized_events",
        "shutdown",
        "activity",
        "process",
        "stdin_write_error",
    ):
        assert hasattr(PiRpcSupervisor, attr) or attr in (
            "activity",
            "process",
            "stdin_write_error",
        )
    for attr in (
        "settled",
        "agent_end_count",
        "agent_end_will_retry_count",
        "event_type_counts",
        "responses",
        "unmatched_response_ids",
        "final_assistant_text",
    ):
        assert attr in {f.name for f in fields(RuntimeActivity)}
    for attr in ("consumed", "mutated_paths"):
        assert attr in {f.name for f in fields(RunState)}
    for attr in ("read_operations", "edit_operations"):
        assert attr in {f.name for f in fields(ConsumedBudgets)}
    assert "refusal_reasons" in {f.name for f in fields(BrokerDiagnostics)}
    assert "handler" in {f.name for f in fields(_LiveBrokerRecord)}
    assert "supervisor" in {f.name for f in fields(_LiveRuntimeRecord)}


# ===========================================================================
# Section F -- A/B fairness
# ===========================================================================


def test_differential_dispatch_trace_is_identical_across_candidates():
    """Matrix case 26 (adapter half). Candidate identity never reaches
    ``LiveSemanticAdapters``, so driving the SAME transport twice with the
    ONLY externally-visible difference being the candidate label used to
    name the test produces byte-identical prompt command dicts.
    """
    traces = {}
    for label in ("A", "B"):
        adapters, session, supervisor = _adapter_with_transport()
        _confirmed_sent(adapters, session)
        traces[label] = supervisor.sent
    assert traces["A"] == traces["B"]
