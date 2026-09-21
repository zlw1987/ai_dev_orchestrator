"""CFG1-L16-FU2 -- lifecycle (L), write-versus-retirement (W) and launch
authority (S) rows, against the REAL supervisor and a synthetic peer.

Barriers, owner-tracking locks, counting wrappers around child creation and
reader construction, and a check-then-write probe VARIANT are test-only
instrumentation. None of them is, or may become, a production parameter.
"""

from __future__ import annotations

import ast
import inspect
import itertools
import subprocess
import textwrap
import threading
import time
from pathlib import Path

import pytest

from ar2 import protocol as protocol_module
from ar2 import supervisor as supervisor_module
from ar2.protocol import BoundedStreamReader, RecordStreamReader
from ar2.supervisor import (
    LAUNCH_REFUSED,
    PROBE_FAILED,
    PROBE_REFUSED,
    PiRpcSupervisor,
    PiSupervisorError,
    RunBounds,
)

from probe_support import (
    FAST_BOUNDS,
    close,
    frame,
    get_state_frame,
    instrument_lifecycle_lock,
    instrumented_reader_class,
    join_readers,
    make_peer,
    make_supervisor,
    reap_raw_child,
    respond_config,
    run_in_thread,
)

GOOD = get_state_frame()
FACTS = (True, "TRUE", "ABSENT", "medium")


def _wait_until(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


def _probe_frames(peer):
    return [command for command in peer.captured_commands() if command.get("type") == "get_state"]


def _payload_bytes(peer) -> bytes:
    return peer.captured().replace(b"<EOF>", b"")


# ---------------------------------------------------------------------------
# 11.3 lifecycle and retirement rows
# ---------------------------------------------------------------------------


def test_l01_resolved_then_shutdown_before_consumption_raises(tmp_path):
    peer = make_peer(tmp_path, **respond_config([GOOD]))
    supervisor = make_supervisor(peer)
    supervisor.launch()
    resolved, go = threading.Event(), threading.Event()
    real = supervisor._probe_wait_over

    def _held(reader):
        done = real(reader)
        if done and supervisor._probe_slot.state == "RESOLVED":
            resolved.set()
            go.wait(5)
        return done

    supervisor._probe_wait_over = _held
    thread, box = run_in_thread(supervisor.probe_runtime_capabilities)
    try:
        assert resolved.wait(5)
        supervisor.shutdown()
    finally:
        go.set()
        thread.join(5)
        close(supervisor)
    assert "result" not in box
    assert isinstance(box["error"], PiSupervisorError) and str(box["error"]) == PROBE_FAILED
    assert supervisor._probe_slot.state == "RETIRED"


def test_l02_consumed_then_shutdown_there_is_no_redemption(tmp_path):
    peer = make_peer(tmp_path, **respond_config([GOOD]))
    supervisor = make_supervisor(peer)
    supervisor.launch()
    try:
        assert supervisor.probe_runtime_capabilities() == FACTS
    finally:
        close(supervisor)
    for name, member in inspect.getmembers(PiRpcSupervisor, predicate=inspect.isfunction):
        for parameter in inspect.signature(member).parameters:
            for fragment in ("fact", "observation", "result", "token", "redeem", "literal"):
                assert fragment not in parameter.lower(), (name, parameter)
    assert not [name for name in dir(PiRpcSupervisor) if "redeem" in name]
    with pytest.raises(PiSupervisorError) as raised:
        supervisor.probe_runtime_capabilities()
    assert str(raised.value) == PROBE_REFUSED


def test_l03_shutdown_racing_consumption_never_returns_facts_after_retirement(tmp_path):
    outcomes = {"facts": 0, "raised": 0}
    for iteration in range(12):
        log: list = []
        peer = make_peer(tmp_path, f"l03_{iteration}", **respond_config([GOOD]))
        supervisor = make_supervisor(peer)
        instrument_lifecycle_lock(supervisor, log)
        supervisor.launch()
        barrier = threading.Barrier(2, timeout=5)
        real = supervisor._probe_wait_over

        def _held(reader, real=real, barrier=barrier, supervisor=supervisor):
            done = real(reader)
            if done and supervisor._probe_slot.state == "RESOLVED":
                try:
                    barrier.wait()
                except threading.BrokenBarrierError:
                    pass
            return done

        supervisor._probe_wait_over = _held

        def _shutdown(barrier=barrier, supervisor=supervisor):
            barrier.wait()
            return supervisor.shutdown()

        probe_thread, probe_box = run_in_thread(supervisor.probe_runtime_capabilities, name="probe-worker")
        shut_thread, _shut_box = run_in_thread(_shutdown, name="shutdown-worker")
        probe_thread.join(10)
        shut_thread.join(10)
        close(supervisor)

        probe_sequences = [entry[0] for entry in log if entry[2] == "probe-worker"]
        shutdown_sequences = [entry[0] for entry in log if entry[2] == "shutdown-worker"]
        if "result" in probe_box:
            outcomes["facts"] += 1
            assert probe_box["result"] == FACTS
            # The consume section was ordered BEFORE retirement.
            assert max(probe_sequences) < min(shutdown_sequences)
            assert supervisor._probe_slot.state == "CONSUMED"
        else:
            outcomes["raised"] += 1
            assert isinstance(probe_box["error"], PiSupervisorError)
            assert supervisor._probe_slot.state == "RETIRED"
    assert outcomes["facts"] + outcomes["raised"] == 12


def test_l04_repeated_shutdown_is_idempotent_and_monotonic(tmp_path):
    peer = make_peer(tmp_path, **respond_config([GOOD]))
    supervisor = make_supervisor(peer)
    supervisor.launch()
    assert supervisor.probe_runtime_capabilities() == FACTS
    first = supervisor.shutdown()
    second = supervisor.shutdown()
    join_readers(supervisor)
    assert first["exit_status_observed"] is not None
    assert second["exit_status_observed"] == first["exit_status_observed"]
    assert supervisor._lifecycle == "RETIRED"
    assert supervisor._probe_slot.state == "CONSUMED"
    with pytest.raises(PiSupervisorError):
        supervisor.probe_runtime_capabilities()


def test_l05_a_second_probe_writes_nothing(tmp_path):
    peer = make_peer(tmp_path, **respond_config([GOOD]))
    supervisor = make_supervisor(peer)
    supervisor.launch()
    try:
        assert supervisor.probe_runtime_capabilities() == FACTS
        with pytest.raises(PiSupervisorError) as raised:
            supervisor.probe_runtime_capabilities()
        assert str(raised.value) == PROBE_REFUSED
        time.sleep(0.3)
    finally:
        close(supervisor)
    assert len(_probe_frames(peer)) == 1
    assert supervisor.commands_sent == ["get_state"]


def test_l05_a_concurrent_second_probe_is_refused_without_disturbing_the_first(tmp_path):
    """Implementation-derived: a refused call must not retire a slot it never armed."""
    peer = make_peer(tmp_path, **respond_config([{"sleep": 0.8}, GOOD], respond_async=True))
    supervisor = make_supervisor(peer)
    supervisor.launch()
    thread, box = run_in_thread(supervisor.probe_runtime_capabilities)
    try:
        assert _wait_until(lambda: supervisor._probe_slot.state == "ARMED")
        with pytest.raises(PiSupervisorError) as raised:
            supervisor.probe_runtime_capabilities()
        assert str(raised.value) == PROBE_REFUSED
        assert supervisor._probe_slot.state == "ARMED"  # the loser changed nothing
        thread.join(10)
    finally:
        close(supervisor)
    assert box["result"] == FACTS
    assert len(_probe_frames(peer)) == 1


def test_l06_never_launched_or_retired_supervisors_are_refused(tmp_path):
    peer = make_peer(tmp_path, **respond_config([GOOD]))
    never = make_supervisor(peer)
    with pytest.raises(PiSupervisorError) as raised:
        never.probe_runtime_capabilities()
    assert str(raised.value) == PROBE_REFUSED

    retired = make_supervisor(peer)
    retired.launch()
    close(retired)
    with pytest.raises(PiSupervisorError):
        retired.probe_runtime_capabilities()
    assert _probe_frames(peer) == []


def test_l08_probe_before_launch_after_failed_launch_and_without_expectations(tmp_path):
    peer = make_peer(tmp_path, **respond_config([GOOD]))
    supervisor = make_supervisor(peer)
    with pytest.raises(PiSupervisorError):
        supervisor.probe_runtime_capabilities()
    assert supervisor._probe_slot.state == "UNARMED"
    assert supervisor._write_state == "WRITE_NONE"

    failed = PiRpcSupervisor(
        argv=(str(tmp_path / "no-such-executable.exe"),), cwd=str(tmp_path),
        environment={}, bounds=FAST_BOUNDS, expected_provider="p", expected_model="m",
    )
    with pytest.raises(PiSupervisorError):
        failed.launch()
    with pytest.raises(PiSupervisorError):
        failed.probe_runtime_capabilities()

    bare = make_supervisor(peer, expectations=False)
    bare.launch()
    try:
        with pytest.raises(PiSupervisorError) as raised:
            bare.probe_runtime_capabilities()
        assert str(raised.value) == PROBE_REFUSED
        time.sleep(0.3)
    finally:
        close(bare)
    assert _probe_frames(peer) == []


def test_l09_a_real_stdin_write_failure_after_arming_retires_the_slot(tmp_path):
    peer = make_peer(tmp_path, mode="close_stdin", max_lifetime=20)
    supervisor = make_supervisor(peer, bounds=RunBounds(
        startup_deadline_seconds=2.0, shutdown_deadline_seconds=1.0,
        direct_child_reap_grace_seconds=1.0))
    supervisor.launch()
    time.sleep(0.5)  # let the peer close its read end
    try:
        with pytest.raises(PiSupervisorError) as raised:
            supervisor.probe_runtime_capabilities()
    finally:
        close(supervisor)
    assert str(raised.value) == PROBE_FAILED
    assert supervisor._write_state == "WRITE_FAILED"
    assert supervisor._probe_slot.state == "RETIRED"
    assert supervisor.commands_sent == []


def test_l09_a_late_matching_frame_after_a_failed_write_yields_nothing(tmp_path, monkeypatch):
    classified = []
    real_raw = protocol_module.classify_correlated_raw_record
    monkeypatch.setattr(
        protocol_module, "classify_correlated_raw_record",
        lambda record: classified.append(1) or real_raw(record),
    )
    real_write = supervisor_module._write_frame

    def _deliver_then_fail(stream, payload):
        real_write(stream, payload)  # the peer DOES receive the id...
        raise OSError("injected failure after delivery")  # ...but AIDO sees a failure

    monkeypatch.setattr(supervisor_module, "_write_frame", _deliver_then_fail)
    peer = make_peer(tmp_path, **respond_config([{"sleep": 0.3}, GOOD], respond_async=True))
    supervisor = make_supervisor(peer)
    supervisor.launch()
    try:
        with pytest.raises(PiSupervisorError):
            supervisor.probe_runtime_capabilities()
        assert supervisor._probe_slot.state == "RETIRED"
        assert _wait_until(lambda: supervisor._stdout.record_count() >= 1)
    finally:
        monkeypatch.setattr(supervisor_module, "_write_frame", real_write)
        close(supervisor)
    assert classified == []  # RETIRED: no matching at all
    assert supervisor._probe_slot.state == "RETIRED"


def test_l10_an_exception_inside_the_call_after_arming_retires_the_slot(tmp_path):
    peer = make_peer(tmp_path, **respond_config([GOOD]))
    supervisor = make_supervisor(peer)
    supervisor.launch()

    def _raising_wait(deadline, satisfied):
        raise RuntimeError("injected failure inside the wait")

    supervisor._wait = _raising_wait
    try:
        with pytest.raises(RuntimeError):
            supervisor.probe_runtime_capabilities()
        assert supervisor._probe_slot.state == "RETIRED"
        assert supervisor._write_state == "WRITE_DONE"
        with pytest.raises(PiSupervisorError):
            supervisor.probe_runtime_capabilities()
    finally:
        del supervisor._wait
        close(supervisor)


def test_l11_retirement_racing_resolution_discards_the_facts(tmp_path, monkeypatch):
    in_reduce, go = threading.Event(), threading.Event()
    real_reduce = protocol_module.reduce_sanitized_get_state

    def _held_reduce(*args, **kwargs):
        in_reduce.set()
        go.wait(5)
        return real_reduce(*args, **kwargs)

    monkeypatch.setattr(protocol_module, "reduce_sanitized_get_state", _held_reduce)
    peer = make_peer(tmp_path, **respond_config([GOOD]))
    supervisor = make_supervisor(peer)
    supervisor.launch()
    thread, box = run_in_thread(supervisor.probe_runtime_capabilities)
    try:
        assert in_reduce.wait(5)
        supervisor.shutdown()  # retirement linearizes before (f)
        go.set()
        thread.join(5)
    finally:
        go.set()
        close(supervisor)
    assert isinstance(box.get("error"), PiSupervisorError)
    slot = supervisor._probe_slot
    assert slot.state == "RETIRED"
    assert (slot.h2, slot.capability_flag, slot.compat, slot.thinking_level) == (None, None, None, None)
    published = [r for r in supervisor.sanitized_events() if r.get("command") == "get_state"]
    assert len(published) == 1  # still published as today


# ---------------------------------------------------------------------------
# 11.3a write-versus-retirement rows
# ---------------------------------------------------------------------------


def _write_race_harness(tmp_path, name, monkeypatch, *, probe_callable=None, trigger="at_write"):
    """Run one probe-versus-shutdown interleaving. Returns the oracle inputs."""
    peer = make_peer(tmp_path, name, **respond_config([GOOD]))
    supervisor = make_supervisor(peer)
    supervisor.launch()
    at_write, retired, written = threading.Event(), threading.Event(), threading.Event()
    snapshot: dict = {}
    real_write = supervisor_module._write_frame

    def _hooked_write(stream, payload):
        if b'"get_state"' in payload:
            at_write.set()
            retired.wait(3)
            try:
                return real_write(stream, payload)
            finally:
                written.set()
        return real_write(stream, payload)

    monkeypatch.setattr(supervisor_module, "_write_frame", _hooked_write)
    real_retire = supervisor._retire

    def _recording_retire():
        result = real_retire()
        snapshot["write_state_at_retirement"] = supervisor._write_state
        snapshot["slot_state_at_retirement"] = supervisor._probe_slot.state
        retired.set()
        return result

    supervisor._retire = _recording_retire
    real_settled = supervisor._probe_write_settled

    def _held_settled(timeout):
        written.wait(1.0)  # give an in-flight write the chance to land first
        return real_settled(timeout)

    supervisor._probe_write_settled = _held_settled

    def _shutdown():
        if trigger == "at_write":
            at_write.wait(3)
        return supervisor.shutdown()

    probe = probe_callable(supervisor) if probe_callable else supervisor.probe_runtime_capabilities
    probe_thread, probe_box = run_in_thread(probe, name="probe-worker")
    shut_thread, shut_box = run_in_thread(_shutdown, name="shutdown-worker")
    probe_thread.join(10)
    shut_thread.join(10)
    monkeypatch.setattr(supervisor_module, "_write_frame", real_write)
    close(supervisor)
    peer.wait_for_eof(5)
    return supervisor, peer, snapshot, probe_box


def _write_oracle(peer, snapshot):
    """(2) of the W-rows: probe bytes may exist only if the commit preceded retirement."""
    payload = _payload_bytes(peer)
    assert payload == b"" or payload.endswith(b"\n"), payload  # never a partial frame
    received = [line for line in payload.splitlines() if b'"get_state"' in line]
    if received:
        assert snapshot["write_state_at_retirement"] != "WRITE_NONE", (
            "probe bytes reached stdin although retirement linearized before any commit"
        )
    return bool(received)


def _check_then_write_variant(supervisor):
    """TEST-ONLY defect: eligibility checked OUTSIDE the serialization, then a write."""

    def _probe():
        with supervisor._lifecycle_cond:
            eligible = supervisor._launch_authority == "INSTALLED" and supervisor._lifecycle == "OPEN"
        if not eligible:
            raise PiSupervisorError(PROBE_REFUSED)
        payload = b'{"id": "check-then-write", "type": "get_state"}\n'
        supervisor_module._write_frame(supervisor._runtime_child.stdin, payload)
        raise PiSupervisorError(PROBE_FAILED)

    return _probe


def test_w01_retirement_can_never_fall_between_the_check_and_the_write(tmp_path, monkeypatch):
    for iteration in range(4):
        trigger = "at_write" if iteration % 2 == 0 else "immediately"
        supervisor, peer, snapshot, box = _write_race_harness(
            tmp_path, f"w01_{iteration}", monkeypatch, trigger=trigger
        )
        received = _write_oracle(peer, snapshot)
        assert "result" not in box or snapshot["slot_state_at_retirement"] == "CONSUMED"
        if received:
            # commit-first: the complete frame arrived, then EOF
            assert peer.saw_eof()
            assert supervisor._probe_slot.state in ("RETIRED", "CONSUMED")
        else:
            assert supervisor._probe_slot.state == "RETIRED"
            assert supervisor._probe_slot.expected_id is None

    # The same row DETECTS the check-then-write defect.
    _supervisor, peer, snapshot, _box = _write_race_harness(
        tmp_path, "w01_variant", monkeypatch, probe_callable=_check_then_write_variant
    )
    with pytest.raises(AssertionError, match="retirement linearized before any commit"):
        _write_oracle(peer, snapshot)


def test_w02_shutdown_racing_the_write_is_always_one_of_two_orders(tmp_path, monkeypatch):
    seen = set()
    for iteration in range(10):
        peer = make_peer(tmp_path, f"w02_{iteration}", **respond_config([GOOD]))
        supervisor = make_supervisor(peer)
        supervisor.launch()
        snapshot: dict = {}
        real_retire = supervisor._retire

        def _recording_retire(real_retire=real_retire, supervisor=supervisor, snapshot=snapshot):
            result = real_retire()
            snapshot["write_state_at_retirement"] = supervisor._write_state
            snapshot["slot_state_at_retirement"] = supervisor._probe_slot.state
            return result

        supervisor._retire = _recording_retire
        barrier = threading.Barrier(2, timeout=5)

        def _probe(barrier=barrier, supervisor=supervisor):
            barrier.wait()
            return supervisor.probe_runtime_capabilities()

        def _shutdown(barrier=barrier, supervisor=supervisor):
            barrier.wait()
            return supervisor.shutdown()

        probe_thread, probe_box = run_in_thread(_probe)
        shut_thread, _ = run_in_thread(_shutdown)
        probe_thread.join(10)
        shut_thread.join(10)
        close(supervisor)
        peer.wait_for_eof(5)
        received = _write_oracle(peer, snapshot)
        if "result" in probe_box:
            assert snapshot["slot_state_at_retirement"] == "CONSUMED"
            seen.add("consumed-first")
        elif received:
            seen.add("commit-first")
        else:
            assert snapshot["write_state_at_retirement"] == "WRITE_NONE"
            seen.add("retirement-first")
        assert peer.saw_eof()
    assert seen  # every iteration landed in one of the admissible orders


def test_w03_a_committed_write_completes_before_stdin_is_closed(tmp_path, monkeypatch):
    peer = make_peer(tmp_path, **respond_config([GOOD]))
    supervisor = make_supervisor(peer)
    supervisor.launch()
    at_write, release = threading.Event(), threading.Event()
    real_write = supervisor_module._write_frame

    def _held_write(stream, payload):
        at_write.set()
        release.wait(5)
        return real_write(stream, payload)

    monkeypatch.setattr(supervisor_module, "_write_frame", _held_write)
    probe_thread, probe_box = run_in_thread(supervisor.probe_runtime_capabilities)
    try:
        assert at_write.wait(5)
        assert supervisor._write_state == "WRITE_COMMITTED"
        shut_thread, shut_box = run_in_thread(supervisor.shutdown, name="shutdown-worker")
        assert _wait_until(lambda: supervisor._lifecycle == "RETIRED")
        time.sleep(0.5)
        assert shut_thread.is_alive()  # waiting for the write state to settle
        assert not peer.saw_eof()  # stdin NOT closed during the committed write
        release.set()
        probe_thread.join(10)
        shut_thread.join(10)
    finally:
        release.set()
        monkeypatch.setattr(supervisor_module, "_write_frame", real_write)
        close(supervisor)
    assert peer.wait_for_eof(5)
    assert len(_probe_frames(peer)) == 1  # the complete frame, THEN EOF
    assert _payload_bytes(peer).endswith(b"\n")
    assert isinstance(probe_box.get("error"), PiSupervisorError)
    assert supervisor._probe_slot.state == "RETIRED"
    assert shut_box["result"]["stdin_closed"] is True


def test_w04_retirement_committed_first_means_zero_probe_bytes(tmp_path):
    peer = make_peer(tmp_path, **respond_config([GOOD]))
    supervisor = make_supervisor(peer)
    supervisor.launch()
    close(supervisor)
    with pytest.raises(PiSupervisorError) as raised:
        supervisor.probe_runtime_capabilities()
    assert str(raised.value) == PROBE_REFUSED
    assert peer.wait_for_eof(5)
    assert _payload_bytes(peer) == b""
    assert supervisor._write_state == "WRITE_NONE"
    assert supervisor._probe_slot.state == "RETIRED"
    assert supervisor._probe_slot.expected_id is None
    assert "get_state" not in supervisor.commands_sent


#: The termination record's frozen keys (R2 Sec. 5.6: "`stdin_closed: False`
#: already exists in the termination record"). The in-flight-write branch
#: expresses itself ONLY through these; a new key for it is unauthorized.
_FROZEN_TERMINATION_KEYS = frozenset(
    {
        "rung_reached",
        "stdin_closed",
        "exit_status_observed",
        "direct_child_terminate_sent",
        "direct_child_kill_sent",
        "stdin_close_error",
        "claim_scope",
    }
)


def _assert_frozen_termination_record(record: dict) -> None:
    extra = set(record) - _FROZEN_TERMINATION_KEYS
    assert not extra, f"unauthorized termination-record field(s): {sorted(extra)}"


def _assert_stdin_closed_is_truthful(record: dict, genuine_stdin) -> None:
    """``stdin_closed`` means the close call RETURNED without error -- nothing more.

    Checked against the genuine handle, not against the record itself.
    """
    if record["stdin_closed"] is True:
        assert genuine_stdin.closed is True
        assert "stdin_close_error" not in record
    else:
        # either no close was ever attempted (the handle is still open), or an
        # attempt was made and failed, which the shipped key
        # ``stdin_close_error`` records.
        assert "stdin_close_error" in record or genuine_stdin.closed is False


class _ShutdownObserver:
    """Test-side, MECHANICAL observation of what the REAL shutdown ladder did.

    Wraps the supervisor's existing private methods and the genuine child's
    ``terminate``/``kill`` so every call is logged, in order, together with the
    write state and the genuine stdin's ``closed`` flag at that instant. It
    adds nothing to the ladder, reads no new production field, and never
    becomes a production parameter.

    Events:
      ``("settled_wait", returned, seconds)``  the bounded wait for the write;
      ``("terminate"|"kill", write_state, stdin_closed)``  taken just BEFORE
          the signal, so they show whether stdin was untouched at that moment;
      ``("close_call", state_before, state_after, closed_before, attempted)``
          one call of ``_close_stdin_if_write_settled``; ``attempted`` is true
          when the call changed ``stdin_closed`` or ``stdin_close_error``.
    """

    def __init__(self, supervisor, genuine_stdin, *, before_close=None):
        self.events: list[tuple] = []
        real_settled = supervisor._probe_write_settled
        real_close = supervisor._close_stdin_if_write_settled
        child = supervisor.process
        real_terminate, real_kill = child.terminate, child.kill

        def _settled(timeout):
            started = time.monotonic()
            result = real_settled(timeout)
            self.events.append(("settled_wait", result, time.monotonic() - started))
            return result

        def _terminate():
            self.events.append(("terminate", supervisor._write_state, genuine_stdin.closed))
            return real_terminate()

        def _kill():
            self.events.append(("kill", supervisor._write_state, genuine_stdin.closed))
            return real_kill()

        def _close(binding, record):
            if before_close is not None:
                before_close()
            was_closed = record["stdin_closed"]
            had_error = "stdin_close_error" in record
            state_before = supervisor._write_state
            closed_before = genuine_stdin.closed
            real_close(binding, record)
            attempted = (record["stdin_closed"] and not was_closed) or (
                "stdin_close_error" in record and not had_error
            )
            self.events.append(
                ("close_call", state_before, supervisor._write_state, closed_before, bool(attempted))
            )

        supervisor._probe_write_settled = _settled
        supervisor._close_stdin_if_write_settled = _close
        child.terminate = _terminate
        child.kill = _kill

    def kinds(self) -> list[str]:
        return [event[0] for event in self.events]

    def close_calls(self) -> list[tuple]:
        return [event for event in self.events if event[0] == "close_call"]


def test_w05_write_failure_concurrent_with_shutdown_releases_the_waiter(tmp_path, monkeypatch):
    bounds = RunBounds(startup_deadline_seconds=2.0, shutdown_deadline_seconds=1.5,
                       direct_child_reap_grace_seconds=1.0)
    peer = make_peer(tmp_path, mode="close_stdin", max_lifetime=20)
    supervisor = make_supervisor(peer, bounds=bounds)
    supervisor.launch()
    time.sleep(0.5)
    observer = _ShutdownObserver(supervisor, supervisor.process.stdin)
    at_write, shutdown_waiting = threading.Event(), threading.Event()
    real_write = supervisor_module._write_frame

    def _held_write(stream, payload):
        at_write.set()
        shutdown_waiting.wait(5)
        time.sleep(0.1)
        return real_write(stream, payload)

    monkeypatch.setattr(supervisor_module, "_write_frame", _held_write)
    real_settled = supervisor._probe_write_settled

    def _signalling_settled(timeout):
        shutdown_waiting.set()
        return real_settled(timeout)

    supervisor._probe_write_settled = _signalling_settled
    probe_thread, probe_box = run_in_thread(supervisor.probe_runtime_capabilities)
    try:
        assert at_write.wait(5)
        started = time.monotonic()
        shut_thread, shut_box = run_in_thread(supervisor.shutdown)
        probe_thread.join(10)
        shut_thread.join(15)
    finally:
        monkeypatch.setattr(supervisor_module, "_write_frame", real_write)
        close(supervisor)
    assert isinstance(probe_box.get("error"), PiSupervisorError)
    assert supervisor._write_state == "WRITE_FAILED"
    assert supervisor._probe_slot.state == "RETIRED"
    record = shut_box["result"]
    _assert_frozen_termination_record(record)
    # The waiter was released EARLY, by the write leaving WRITE_COMMITTED -- not
    # by the shutdown deadline -- so the in-flight ladder never ran:
    # (the test's own ``finally: close()`` is a second, idempotent shutdown, so
    # the first wait is the concurrent one and any later wait is that repeat.)
    waits = [event for event in observer.events if event[0] == "settled_wait"]
    assert waits and all(event[1] is True for event in waits)
    assert waits[0][2] < bounds.shutdown_deadline_seconds
    assert observer.close_calls() == []
    # ...and the direct-child rung ran only AFTER the write had settled:
    assert [event[1] for event in observer.events if event[0] == "terminate"] == ["WRITE_FAILED"]
    assert record["exit_status_observed"] is not None
    assert time.monotonic() - started < 10


def test_w06_a_write_that_never_finishes_never_overlaps_a_stdin_close(tmp_path):
    """A REAL full pipe holds a committed probe write in flight through shutdown.

    The oracle is the existing frozen termination record plus DIRECT mechanical
    observations of the real ladder -- never a field added for the purpose. Which
    side of the race the final close check lands on (the write may fail a moment
    after the child dies) is genuinely nondeterministic here, so this row asserts
    only what holds on both sides; W-06b and W-06c pin each side exactly.
    """
    bounds = RunBounds(startup_deadline_seconds=2.0, shutdown_deadline_seconds=1.5,
                       direct_child_reap_grace_seconds=1.0)
    peer = make_peer(tmp_path, mode="no_read", max_lifetime=30)
    supervisor = make_supervisor(peer, bounds=bounds)
    supervisor.launch()
    genuine_stdin = supervisor.process.stdin

    def _fill():
        try:
            genuine_stdin.write(b"x" * (8 * 1024 * 1024))
            genuine_stdin.flush()
        except (OSError, ValueError):
            pass

    filler = threading.Thread(target=_fill, name="fu2-filler", daemon=True)
    filler.start()
    time.sleep(0.5)
    observer = _ShutdownObserver(supervisor, genuine_stdin)
    probe_thread, probe_box = run_in_thread(supervisor.probe_runtime_capabilities)
    assert _wait_until(lambda: supervisor._write_state == "WRITE_COMMITTED")
    time.sleep(0.2)
    started = time.monotonic()
    record = supervisor.shutdown()
    elapsed = time.monotonic() - started
    probe_thread.join(10)
    filler.join(10)
    join_readers(supervisor)

    # the shutdown deadline stays a bound
    bound = bounds.shutdown_deadline_seconds + 2 * bounds.direct_child_reap_grace_seconds + 2.0
    assert elapsed < bound, elapsed
    _assert_frozen_termination_record(record)

    # the bounded wait ran to (about) the deadline and reported "still in flight"
    kinds = observer.kinds()
    assert kinds[0] == "settled_wait"
    _, settled, waited = observer.events[0]
    assert settled is False
    assert bounds.shutdown_deadline_seconds - 0.25 <= waited < bounds.shutdown_deadline_seconds + 1.0

    # the direct-child rung proceeded with the write STILL committed and stdin UNTOUCHED
    terminates = [event for event in observer.events if event[0] == "terminate"]
    assert len(terminates) == 1
    assert terminates[0][1] == "WRITE_COMMITTED" and terminates[0][2] is False
    assert kinds.index("settled_wait") < kinds.index("terminate")
    assert record["direct_child_terminate_sent"] is True
    assert record["exit_status_observed"] is not None
    assert record["rung_reached"] in ("exited_after_terminate", "exited_after_kill")

    # no stdin close was ever ATTEMPTED while the write was still committed, and
    # none before the first signal
    for position, event in enumerate(observer.events):
        if event[0] != "close_call":
            continue
        _, _state_before, state_after, _closed_before, attempted = event
        assert position > kinds.index("terminate")
        assert not (attempted and state_after == "WRITE_COMMITTED")

    _assert_stdin_closed_is_truthful(record, genuine_stdin)
    assert "result" not in probe_box
    assert isinstance(probe_box.get("error"), PiSupervisorError)


def _held_write_supervisor(tmp_path, monkeypatch, *, before_close_factory=None):
    """A real supervisor whose committed probe write is HELD and touches no pipe.

    The held write returns without writing, so no byte is ever buffered and a
    later stdin close has nothing to flush: ``stdin_closed`` then reports the
    close itself rather than a flush error. Returns everything the row needs.
    """
    bounds = RunBounds(startup_deadline_seconds=2.0, shutdown_deadline_seconds=1.5,
                       direct_child_reap_grace_seconds=1.0)
    peer = make_peer(tmp_path, mode="no_read", max_lifetime=30)
    supervisor = make_supervisor(peer, bounds=bounds)
    supervisor.launch()
    genuine_stdin = supervisor.process.stdin
    at_write, release = threading.Event(), threading.Event()
    real_write = supervisor_module._write_frame

    def _held_write(stream, payload):
        at_write.set()
        release.wait(30)

    monkeypatch.setattr(supervisor_module, "_write_frame", _held_write)
    before_close = before_close_factory(supervisor, release) if before_close_factory else None
    observer = _ShutdownObserver(supervisor, genuine_stdin, before_close=before_close)
    probe_thread, probe_box = run_in_thread(supervisor.probe_runtime_capabilities)
    return {
        "bounds": bounds, "supervisor": supervisor, "stdin": genuine_stdin,
        "observer": observer, "at_write": at_write, "release": release,
        "probe_thread": probe_thread, "probe_box": probe_box, "real_write": real_write,
    }


def _finish_held_write(rig, monkeypatch):
    rig["release"].set()
    rig["probe_thread"].join(10)
    monkeypatch.setattr(supervisor_module, "_write_frame", rig["real_write"])
    join_readers(rig["supervisor"])
    try:
        rig["stdin"].close()  # test cleanup only, after every assertion
    except (OSError, ValueError):
        pass


def test_w06b_a_committed_write_that_never_settles_leaves_stdin_unclosed_and_says_so(
    tmp_path, monkeypatch
):
    rig = _held_write_supervisor(tmp_path, monkeypatch)
    supervisor, observer, stdin, bounds = (
        rig["supervisor"], rig["observer"], rig["stdin"], rig["bounds"])
    try:
        assert rig["at_write"].wait(5)
        assert supervisor._write_state == "WRITE_COMMITTED"
        started = time.monotonic()
        record = supervisor.shutdown()
        elapsed = time.monotonic() - started

        # still in flight after the whole ladder: direct, mechanical observations
        assert supervisor._write_state == "WRITE_COMMITTED"
        assert stdin.closed is False
        assert elapsed < bounds.shutdown_deadline_seconds + 2 * bounds.direct_child_reap_grace_seconds + 2.0
        _assert_frozen_termination_record(record)
        assert record["stdin_closed"] is False          # the truth
        assert "stdin_close_error" not in record        # ...because no close was ever attempted
        assert record["direct_child_terminate_sent"] is True
        assert record["exit_status_observed"] is not None
        assert record["rung_reached"] in ("exited_after_terminate", "exited_after_kill")
        _assert_stdin_closed_is_truthful(record, stdin)

        kinds = observer.kinds()
        assert kinds[0] == "settled_wait" and observer.events[0][1] is False
        assert (bounds.shutdown_deadline_seconds - 0.25
                <= observer.events[0][2] < bounds.shutdown_deadline_seconds + 1.0)
        terminate = next(event for event in observer.events if event[0] == "terminate")
        assert terminate[1:] == ("WRITE_COMMITTED", False)   # signalled with stdin untouched
        # every close check that ran saw the write still committed and did NOT close
        assert observer.close_calls()
        for _, before, after, closed_before, attempted in observer.close_calls():
            assert before == after == "WRITE_COMMITTED"
            assert closed_before is False and attempted is False
    finally:
        _finish_held_write(rig, monkeypatch)
    assert isinstance(rig["probe_box"].get("error"), PiSupervisorError)


def test_w06c_a_write_that_settles_between_rungs_lets_stdin_close_after_it_and_says_so(
    tmp_path, monkeypatch
):
    def _factory(supervisor, release):
        def _settle_then_continue():
            # runs BEFORE the ladder's first close check: the write completes
            # first, and only then may stdin be closed
            release.set()
            assert _wait_until(lambda: supervisor._write_state != "WRITE_COMMITTED")
        return _settle_then_continue

    rig = _held_write_supervisor(tmp_path, monkeypatch, before_close_factory=_factory)
    supervisor, observer, stdin = rig["supervisor"], rig["observer"], rig["stdin"]
    try:
        assert rig["at_write"].wait(5)
        record = supervisor.shutdown()
        rig["probe_thread"].join(10)

        _assert_frozen_termination_record(record)
        kinds = observer.kinds()
        assert kinds[0] == "settled_wait" and observer.events[0][1] is False
        terminate = next(event for event in observer.events if event[0] == "terminate")
        assert terminate[1:] == ("WRITE_COMMITTED", False)   # signalled first, stdin untouched
        calls = observer.close_calls()
        assert calls and kinds.index("terminate") < kinds.index("close_call")
        first = calls[0]
        assert first[1] != "WRITE_COMMITTED"                 # closed only AFTER the write settled
        assert first[3] is False and first[4] is True
        assert record["stdin_closed"] is True                # the truth
        assert "stdin_close_error" not in record
        assert stdin.closed is True
        _assert_stdin_closed_is_truthful(record, stdin)
    finally:
        _finish_held_write(rig, monkeypatch)


def _shutdown_path_functions():
    return {
        name: ast.parse(textwrap.dedent(inspect.getsource(getattr(PiRpcSupervisor, name)))).body[0]
        for name in ("shutdown", "_in_flight_write_ladder", "_close_stdin_if_write_settled",
                     "_direct_child_ladder")
    }


def test_w09_the_in_flight_branch_adds_no_termination_field_and_no_side_channel(tmp_path):
    # runtime: the never-launched and the ordinary ladder records carry only frozen keys
    never = make_supervisor(make_peer(tmp_path, "never"))
    _assert_frozen_termination_record(never.shutdown())
    peer = make_peer(tmp_path, "ordinary", **respond_config([GOOD]))
    supervisor = make_supervisor(peer)
    supervisor.launch()
    _assert_frozen_termination_record(close(supervisor))

    # source: every key ANY shutdown-path function writes into the record is frozen,
    # nothing else mutates it, and no attribute other than the existing
    # ``termination`` is stored (a side channel would have to live somewhere)
    written: set[str] = set()
    for name, function in _shutdown_path_functions().items():
        for node in ast.walk(function):
            if (isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store)
                    and isinstance(node.value, ast.Name) and node.value.id == "record"):
                assert isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str), name
                written.add(node.slice.value)
            if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "record":
                assert isinstance(node.value, ast.Dict), name
                for key in node.value.keys:
                    assert isinstance(key, ast.Constant), name
                    written.add(key.value)
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == "record"):
                raise AssertionError(f"{name}: record.{node.func.attr}() mutates the record indirectly")
            if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
                target = node.value.id if isinstance(node.value, ast.Name) else None
                if target == "self":
                    assert name == "shutdown" and node.attr == "termination", (name, node.attr)
    assert written <= _FROZEN_TERMINATION_KEYS, sorted(written - _FROZEN_TERMINATION_KEYS)
    assert "stdin_closed" in written and "rung_reached" in written


def test_w07_the_reader_keeps_publishing_during_a_committed_write(tmp_path, monkeypatch):
    log: list = []
    readers: list = []
    monkeypatch.setattr(supervisor_module, "RecordStreamReader", instrumented_reader_class(log, readers))
    peer = make_peer(
        tmp_path, flood={"count": 600, "interval": 0.002}, **respond_config([GOOD])
    )
    supervisor = make_supervisor(peer)
    instrument_lifecycle_lock(supervisor, log)
    supervisor.launch()
    during = {}
    real_write = supervisor_module._write_frame

    def _observed_write(stream, payload):
        during["lifecycle_held"] = supervisor._lifecycle_cond._lock.held_by_current_thread()
        during["reader_held"] = readers[0]._lock.held_by_current_thread()
        during["before"] = supervisor._stdout.record_count()
        time.sleep(0.4)
        during["after"] = supervisor._stdout.record_count()
        return real_write(stream, payload)

    monkeypatch.setattr(supervisor_module, "_write_frame", _observed_write)
    try:
        time.sleep(0.05)
        facts = supervisor.probe_runtime_capabilities()
    finally:
        monkeypatch.setattr(supervisor_module, "_write_frame", real_write)
        close(supervisor)
    assert facts == FACTS
    assert during["lifecycle_held"] is False and during["reader_held"] is False
    assert during["after"] > during["before"]


def test_w08_lock_order_including_the_launch_sections(tmp_path, monkeypatch):
    log: list = []
    monkeypatch.setattr(supervisor_module, "RecordStreamReader", instrumented_reader_class(log))
    peer = make_peer(tmp_path, **respond_config(
        [GOOD], responses={"get_commands": [frame({"type": "response", "id": "__ID__",
                                                      "command": "get_commands", "success": True})]}))
    supervisor = make_supervisor(peer)
    instrument_lifecycle_lock(supervisor, log)
    supervisor.launch()
    try:
        with pytest.raises(PiSupervisorError):
            supervisor.launch()
        supervisor.send_command({"id": "h1", "type": "get_commands"})
        supervisor.await_response("h1", timeout_seconds=4)
        assert supervisor.probe_runtime_capabilities() == FACTS
    finally:
        close(supervisor)
    lifecycle_entries = [entry for entry in log if entry[1] == "lifecycle"]
    reader_entries = [entry for entry in log if entry[1] == "reader"]
    assert lifecycle_entries and reader_entries
    assert not [entry for entry in lifecycle_entries if entry[2] == "ar2-pi-stdout"]
    assert not [entry for entry in lifecycle_entries if "reader" in entry[3]]
    # the nesting that does occur is always lifecycle -> reader
    assert [entry for entry in reader_entries if "lifecycle" in entry[3]]


# ---------------------------------------------------------------------------
# 11.3b launch-authority rows
# ---------------------------------------------------------------------------


@pytest.fixture()
def counting(monkeypatch):
    """Counting wrappers around child creation and reader construction (tests only)."""
    state: dict = {"popen": 0, "children": [], "stdout_readers": [], "stderr_readers": [],
                   "hook": None, "raise_in": None, "held_locks": []}
    real_popen = subprocess.Popen

    def _popen(*args, **kwargs):
        state["popen"] += 1
        if state["hook"] is not None:
            state["hook"]("before", None)
        child = real_popen(*args, **kwargs)
        state["children"].append(child)
        if state["hook"] is not None:
            state["hook"]("after", child)
        return child

    class _Stdout(RecordStreamReader):
        def __init__(self, *args, **kwargs):
            if state["raise_in"] == "stdout_init":
                raise RuntimeError("injected reader construction failure")
            super().__init__(*args, **kwargs)
            state["stdout_readers"].append(self)

    class _Stderr(BoundedStreamReader):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            state["stderr_readers"].append(self)

        def start(self):
            if state["raise_in"] == "stderr_start":
                raise RuntimeError("injected reader start failure")
            super().start()

    monkeypatch.setattr(supervisor_module.subprocess, "Popen", _popen)
    monkeypatch.setattr(supervisor_module, "RecordStreamReader", _Stdout)
    monkeypatch.setattr(supervisor_module, "BoundedStreamReader", _Stderr)
    yield state
    for child in state["children"]:
        reap_raw_child(child)


def _identity_snapshot(supervisor):
    binding = supervisor._runtime_child
    return {
        "process": supervisor.process,
        "_stdout": supervisor._stdout,
        "_stderr": supervisor._stderr,
        "stdout_thread": supervisor._stdout._thread if supervisor._stdout else None,
        "stderr_thread": supervisor._stderr._thread if supervisor._stderr else None,
        "slot": supervisor._probe_slot,
        "slot_state": supervisor._probe_slot.state,
        "slot_reader": supervisor._slot_reader,
        "expected": (supervisor._expected_provider, supervisor._expected_model),
        "runtime_child": binding,
        "orphan_child": supervisor._orphan_child,
        "binding_parts": None if binding is None else (
            binding.child, binding.stdin, binding.stdout, binding.stderr, binding.role, binding.owner),
    }


def _assert_identical(before, after):
    for key, value in before.items():
        if key in ("slot_state", "expected", "binding_parts") and value is not None:
            assert after[key] == value, key
            if key == "binding_parts":
                assert all(a is b for a, b in zip(after[key], value)), key
        else:
            assert after[key] is value, key


def _refused_launch(supervisor):
    with pytest.raises(PiSupervisorError) as raised:
        supervisor.launch()
    assert str(raised.value) == LAUNCH_REFUSED


def test_s01_s08_c09_a_second_launch_refuses_before_creation(tmp_path, counting):
    peer = make_peer(tmp_path, **respond_config([GOOD]))
    supervisor = make_supervisor(peer)
    supervisor.launch()
    try:
        before = _identity_snapshot(supervisor)
        _refused_launch(supervisor)
        assert counting["popen"] == 1
        assert len(counting["stdout_readers"]) == 1 and len(counting["stderr_readers"]) == 1
        _assert_identical(before, _identity_snapshot(supervisor))
        assert supervisor.probe_runtime_capabilities() == FACTS
    finally:
        close(supervisor)


def test_s02_launch_after_shutdown_refuses(tmp_path, counting):
    peer = make_peer(tmp_path, **respond_config([GOOD]))
    supervisor = make_supervisor(peer)
    supervisor.launch()
    close(supervisor)
    before = _identity_snapshot(supervisor)
    _refused_launch(supervisor)
    assert counting["popen"] == 1
    _assert_identical(before, _identity_snapshot(supervisor))
    assert supervisor._lifecycle == "RETIRED"
    with pytest.raises(PiSupervisorError):
        supervisor.probe_runtime_capabilities()


class _InjectedBaseException(BaseException):
    pass


def test_s03_i_popen_oserror_is_terminal(tmp_path, counting):
    supervisor = PiRpcSupervisor(
        argv=(str(tmp_path / "missing.exe"),), cwd=str(tmp_path), environment={},
        bounds=FAST_BOUNDS, expected_provider="p", expected_model="m",
    )
    with pytest.raises(PiSupervisorError):
        supervisor.launch()
    assert supervisor._launch_authority == "FAILED"
    assert supervisor.process is None
    before = _identity_snapshot(supervisor)
    _refused_launch(supervisor)
    assert counting["popen"] == 1
    _assert_identical(before, _identity_snapshot(supervisor))


@pytest.mark.parametrize("where", ["stderr_start", "stdout_init"])
def test_s03_ii_c14_install_failure_keeps_the_runtime_child_for_shutdown(tmp_path, counting, where):
    counting["raise_in"] = where
    peer = make_peer(tmp_path, **respond_config([GOOD]))
    supervisor = make_supervisor(peer)
    with pytest.raises(RuntimeError):
        supervisor.launch()
    child = counting["children"][0]
    assert supervisor.process is child
    assert supervisor._launch_authority == "FAILED"
    assert supervisor._slot_reader is None  # the slot was never bound
    before = _identity_snapshot(supervisor)
    counting["raise_in"] = None
    _refused_launch(supervisor)
    assert counting["popen"] == 1
    _assert_identical(before, _identity_snapshot(supervisor))
    with pytest.raises(PiSupervisorError):
        supervisor.probe_runtime_capabilities()
    # the CFG1 L14 / L21 and qualification partial-launch decisions see the child
    assert getattr(supervisor, "process", None) is not None
    if where == "stderr_start":
        record = supervisor.shutdown()
        assert record["exit_status_observed"] is not None
    else:
        # F-7 (pre-existing, recorded, NOT closed): the ladder runs and reaps the
        # child, then ``_drain`` asserts because no stdout reader exists.
        with pytest.raises(AssertionError):
            supervisor.shutdown()
    join_readers(supervisor)
    assert child.poll() is not None
    assert _probe_frames(peer) == []
    assert supervisor.process is child


def test_s03_iii_a_base_exception_before_creation_is_terminal(tmp_path, counting):
    def _hook(when, child):
        if when == "before":
            raise _InjectedBaseException()

    counting["hook"] = _hook
    peer = make_peer(tmp_path, **respond_config([GOOD]))
    supervisor = make_supervisor(peer)
    with pytest.raises(_InjectedBaseException):
        supervisor.launch()
    counting["hook"] = None
    assert supervisor._launch_authority == "FAILED"
    assert supervisor.process is None and supervisor._orphan_child is None
    _refused_launch(supervisor)
    assert counting["children"] == []


def test_s03_iv_a_base_exception_after_creation_takes_the_orphan_rule(tmp_path, counting):
    peer = make_peer(tmp_path, **respond_config([GOOD]))
    supervisor = make_supervisor(peer)

    def _raising_l3(child):
        raise _InjectedBaseException()

    supervisor._bind_install_or_orphan = _raising_l3
    with pytest.raises(_InjectedBaseException):
        supervisor.launch()
    child = counting["children"][0]
    assert supervisor._launch_authority == "FAILED"
    assert supervisor.process is None
    assert supervisor._orphan_child is not None and supervisor._orphan_child.child is child
    assert supervisor._orphan_child.role == "orphan-child"
    assert counting["stdout_readers"] == [] and counting["stderr_readers"] == []
    assert supervisor.orphan_termination["exit_status_observed"] is not None
    assert child.poll() is not None
    assert peer.wait_for_eof(5)
    _refused_launch(supervisor)
    assert counting["popen"] == 1


def test_s04_two_concurrent_launches_create_at_most_one_child(tmp_path, counting):
    peer = make_peer(tmp_path, **respond_config([GOOD]))
    supervisor = make_supervisor(peer)
    barrier = threading.Barrier(2, timeout=5)

    def _launch():
        barrier.wait()
        supervisor.launch()
        return "launched"

    first, first_box = run_in_thread(_launch)
    second, second_box = run_in_thread(_launch)
    first.join(10)
    second.join(10)
    try:
        boxes = [first_box, second_box]
        assert sorted("result" in box for box in boxes) == [False, True]
        (loser,) = [box for box in boxes if "error" in box]
        assert isinstance(loser["error"], PiSupervisorError)
        assert str(loser["error"]) == LAUNCH_REFUSED
        assert counting["popen"] == 1
        assert len(counting["stdout_readers"]) == 1 and len(counting["stderr_readers"]) == 1
        assert supervisor.probe_runtime_capabilities() == FACTS
    finally:
        close(supervisor)


def test_s05_retirement_first_means_zero_creation_forever(tmp_path, counting):
    peer = make_peer(tmp_path, **respond_config([GOOD]))
    supervisor = make_supervisor(peer)
    record = supervisor.shutdown()
    assert record["rung_reached"] == "none"
    before = _identity_snapshot(supervisor)
    _refused_launch(supervisor)
    _refused_launch(supervisor)
    assert counting["popen"] == 0
    assert counting["stdout_readers"] == [] and counting["stderr_readers"] == []
    _assert_identical(before, _identity_snapshot(supervisor))
    assert supervisor.process is None
    assert supervisor._lifecycle == "RETIRED"
    with pytest.raises(PiSupervisorError):
        supervisor.probe_runtime_capabilities()


def test_s06_a_launch_committed_then_l3_before_retirement(tmp_path, counting):
    peer = make_peer(tmp_path, **respond_config([GOOD]))
    supervisor = make_supervisor(peer)
    supervisor.launch()
    record = close(supervisor)
    assert counting["popen"] == 1
    assert record["exit_status_observed"] is not None
    assert supervisor._orphan_child is None


def test_s06_b_retirement_between_l1_and_l3_makes_an_attributed_orphan(tmp_path, counting):
    created, go = threading.Event(), threading.Event()

    def _hook(when, child):
        if when == "after":
            created.set()
            go.wait(5)

    counting["hook"] = _hook
    peer = make_peer(tmp_path, **respond_config([GOOD]))
    supervisor = make_supervisor(peer)
    thread, box = run_in_thread(supervisor.launch)
    try:
        assert created.wait(5)
        assert supervisor.process is None  # mid-launch, before L3
        record = supervisor.shutdown()
        assert record["rung_reached"] == "none"  # shutdown saw an EMPTY runtime binding
        go.set()
        thread.join(15)
    finally:
        go.set()
    child = counting["children"][0]
    assert isinstance(box.get("error"), PiSupervisorError)
    assert str(box["error"]) == LAUNCH_REFUSED
    assert supervisor.process is None
    assert supervisor._runtime_child is None
    assert supervisor._orphan_child.child is child
    assert counting["stdout_readers"] == [] and counting["stderr_readers"] == []
    assert supervisor._slot_reader is None
    assert supervisor._launch_authority == "FAILED"
    orphan = supervisor.orphan_termination
    assert orphan["exit_status_observed"] is not None
    assert "DIRECT orphan child" in orphan["claim_scope"]
    assert child.poll() is not None
    assert peer.wait_for_eof(5)
    with pytest.raises(PiSupervisorError):
        supervisor.probe_runtime_capabilities()
    assert _probe_frames(peer) == []
    assert supervisor.termination == {}  # shutdown's own record says nothing of the orphan


_ORDER = {"UNUSED": 0, "COMMITTED": 1, "INSTALLED": 2, "FAILED": 2}


@pytest.mark.parametrize("inject", [None, "stderr_start"])
def test_s07_no_sequence_of_operations_ever_resets_launch_or_lifecycle(tmp_path, counting, inject):
    operations = ("launch", "shutdown", "probe")
    for length in range(1, 5):
        for index, sequence in enumerate(itertools.product(operations, repeat=length)):
            counting["popen"] = 0
            counting["raise_in"] = inject
            peer = make_peer(tmp_path, f"s07_{inject}_{length}_{index}", **respond_config([GOOD]))
            supervisor = make_supervisor(peer)
            history = [(supervisor._launch_authority, supervisor._lifecycle)]
            try:
                for operation in sequence:
                    try:
                        if operation == "launch":
                            supervisor.launch()
                        elif operation == "shutdown":
                            supervisor.shutdown()
                        else:
                            supervisor.probe_runtime_capabilities()
                    except (PiSupervisorError, RuntimeError, AssertionError):
                        pass
                    history.append((supervisor._launch_authority, supervisor._lifecycle))
            finally:
                counting["raise_in"] = None
                close(supervisor)
            assert counting["popen"] <= 1, sequence
            for (authority_a, life_a), (authority_b, life_b) in zip(history, history[1:]):
                assert _ORDER[authority_b] >= _ORDER[authority_a], sequence
                if authority_a in ("INSTALLED", "FAILED"):
                    assert authority_b == authority_a, sequence
                assert not (life_a == "RETIRED" and life_b == "OPEN"), sequence
            retired_seen = False
            for authority, life in history:
                retired_seen = retired_seen or life == "RETIRED"
                if retired_seen:
                    assert not (authority == "INSTALLED" and life == "OPEN"), sequence


def test_s07_only_the_enumerated_sections_write_launch_or_lifecycle_state():
    tree = ast.parse(Path(supervisor_module.__file__).read_text(encoding="utf-8"))
    writers: dict[str, set] = {"_launch_authority": set(), "_lifecycle": set()}
    values: dict[str, set] = {"_launch_authority": set(), "_lifecycle": set()}
    for function in ast.walk(tree):
        if not isinstance(function, ast.FunctionDef):
            continue
        for node in ast.walk(function):
            if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if (isinstance(target, ast.Attribute) and target.attr in writers
                            and isinstance(target.value, ast.Name) and target.value.id == "self"):
                        writers[target.attr].add(function.name)
                        values[target.attr].add((function.name, ast.unparse(node.value)))
    assert writers["_launch_authority"] == {
        "__init__", "launch", "_bind_install_or_orphan", "_unwind_failed_launch"}
    assert writers["_lifecycle"] == {"__init__", "_retire"}
    assert {value for name, value in values["_launch_authority"] if value == "_LAUNCH_UNUSED"} == {"_LAUNCH_UNUSED"}
    assert [name for name, value in values["_launch_authority"] if value == "_LAUNCH_UNUSED"] == ["__init__"]
    assert values["_lifecycle"] == {("__init__", "_LIFECYCLE_OPEN"), ("_retire", "_LIFECYCLE_RETIRED")}
    assert ("launch", "_LAUNCH_COMMITTED") in values["_launch_authority"]
    assert {value for name, value in values["_launch_authority"] if name != "__init__"} <= {
        "_LAUNCH_COMMITTED", "_LAUNCH_INSTALLED", "_LAUNCH_FAILED"}


def test_s09_the_guard_is_per_instance(tmp_path, counting):
    peer_a = make_peer(tmp_path, "a", **respond_config([GOOD]))
    peer_b = make_peer(tmp_path, "b", **respond_config([GOOD]))
    first, second = make_supervisor(peer_a), make_supervisor(peer_b)
    first.launch()
    try:
        _refused_launch(first)
        second.launch()
        assert second.probe_runtime_capabilities() == FACTS
        assert first.probe_runtime_capabilities() == FACTS
    finally:
        close(first)
        close(second)
    assert counting["popen"] == 2
    for name in ("_launch_authority", "_lifecycle", "_write_state", "_runtime_child", "_orphan_child"):
        assert name in vars(first)
        assert name not in vars(PiRpcSupervisor)
        assert name not in vars(supervisor_module)


@pytest.mark.parametrize("launched", [False, True])
def test_s09_no_copy_or_pickle_can_carry_launch_state_to_another_instance(tmp_path, counting, launched):
    """Adversarial self-review finding (CFG1-L16-FU2 IMPL).

    ``copy.copy`` / ``copy.deepcopy`` / ``pickle`` would build a SECOND instance
    whose ``__dict__`` carries this one's launch authority -- an unlaunched copy
    would be launchable again while SHARING the original's probe slot and
    lifecycle serialization. Sec. 5.6.1: "nothing carries launch state from one
    instance to another". Every such path must refuse, before anything exists.
    """
    import copy
    import pickle

    peer = make_peer(tmp_path, **respond_config([GOOD]))
    supervisor = make_supervisor(peer)
    if launched:
        supervisor.launch()
    try:
        for clone in (copy.copy, copy.deepcopy, pickle.dumps,
                      lambda s: s.__reduce_ex__(4), lambda s: s.__reduce__()):
            with pytest.raises(PiSupervisorError):
                clone(supervisor)
        assert counting["popen"] == (1 if launched else 0)
        if launched:
            assert supervisor.probe_runtime_capabilities() == FACTS
    finally:
        close(supervisor)


def test_s10_no_lock_is_held_at_creation_and_refusals_carry_nothing(tmp_path, counting):
    peer = make_peer(tmp_path, **respond_config([{"sleep": 1.0}, GOOD], respond_async=True))
    supervisor = make_supervisor(peer)
    held_at_creation = []

    def _hook(when, child):
        if when == "before":
            held_at_creation.append(supervisor._lifecycle_cond._lock.locked())

    counting["hook"] = _hook
    supervisor.launch()
    counting["hook"] = None
    assert held_at_creation == [False]
    messages = []
    thread, box = run_in_thread(supervisor.probe_runtime_capabilities)
    try:
        assert _wait_until(lambda: supervisor._probe_slot.state == "ARMED")
        slot = supervisor._probe_slot
        with pytest.raises(PiSupervisorError) as raised:
            supervisor.launch()  # refused while a probe is ARMED on the first lineage
        messages.append(str(raised.value))
        assert supervisor._probe_slot is slot and slot.state == "ARMED"
        thread.join(10)
    finally:
        close(supervisor)
    assert box["result"] == FACTS
    with pytest.raises(PiSupervisorError) as raised:
        supervisor.launch()
    messages.append(str(raised.value))
    for message in messages:
        assert message == LAUNCH_REFUSED
        for fragment in (str(tmp_path), peer.argv[0], peer.argv[1], "PATH", "SystemRoot"):
            assert fragment not in message
