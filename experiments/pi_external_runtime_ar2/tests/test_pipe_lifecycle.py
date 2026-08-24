"""NAMED-PIPE LIFECYCLE, and the truthfulness rules that go with it.

These tests DO open local Windows named pipes: that is the mechanism under test,
and FU1's whole D2 correction rests on measured behaviour rather than assumption.
No socket, no network, no model, and no real Pi process is involved.

Every test joins or completes every worker it starts. The session-wide autouse
fixture in ``conftest.py`` fails any test that leaves an AR2-owned thread alive.

The claim boundary this file exists to hold:

    AIDO wait ended  !=  broker thread stopped  !=  pending I/O completed
                     !=  handle released        !=  capability provably withdrawn
"""

from __future__ import annotations

import _winapi
import ast
import inspect
import json
import threading
import time

import pytest

from ar2 import broker as broker_module
from ar2 import winpipe
from ar2.broker import (
    STATE_CLOSED,
    STATE_CREATED,
    STATE_READY,
    STATE_TEARDOWN_INCOMPLETE,
    TRIGGER_AIDO_TEARDOWN,
    BrokerBinding,
    BrokerDiagnostics,
    BrokerRequestHandler,
    BrokerServer,
    BrokerTestHooks,
)
from ar2.capability import RunState
from ar2.fixtures import R1
from ar2.wire import PROTOCOL_VERSION

from conftest import mint_for

pytestmark = pytest.mark.timeout if False else []


def build_server(r1_repo, git_executable, **kwargs):
    sed = mint_for(R1, git_executable, r1_repo)
    binding = BrokerBinding.mint(sed.capability_id)
    handler = BrokerRequestHandler(
        sed=sed,
        run_state=RunState(caps=sed.caps),
        binding=binding,
        diagnostics=BrokerDiagnostics(),
    )
    return BrokerServer(handler, **kwargs), binding


class PipeClient:
    """A minimal synchronous local client. Test-only; AIDO never uses this."""

    def __init__(self, name: str) -> None:
        self.handle = winpipe.connect_client(name)
        self._buffer = b""

    def send(self, payload: dict) -> None:
        _winapi.WriteFile(self.handle, json.dumps(payload).encode("utf-8") + b"\n")

    def receive(self, timeout_seconds: float = 5.0) -> dict:
        deadline = time.monotonic() + timeout_seconds
        while b"\n" not in self._buffer:
            if time.monotonic() > deadline:
                raise TimeoutError("no framed response arrived")
            chunk, _err = _winapi.ReadFile(self.handle, 65536)
            self._buffer += chunk
        line, _, self._buffer = self._buffer.partition(b"\n")
        return json.loads(line.decode("utf-8"))

    def close(self) -> None:
        try:
            _winapi.CloseHandle(self.handle)
        except OSError:
            pass


# -- creation shape ------------------------------------------------------------


def test_the_security_descriptor_is_current_user_scoped():
    security = winpipe.build_current_user_security_attributes()
    try:
        described = security.describe()
        assert described["security_descriptor_built"] is True
        assert described["dacl_protected"] is True
        assert described["ace_count"] == 1
        assert described["grants_current_user_only"] is True
        assert described["inherit_handle"] is False
        assert security.sddl.startswith("D:P(A;;GA;;;S-1-")
        assert isinstance(security.address, int) and security.address != 0
    finally:
        security.release()


def test_a_first_pipe_instance_collision_fails_closed():
    security = winpipe.build_current_user_security_attributes()
    try:
        name = winpipe.random_pipe_name()
        handle = winpipe.create_first_instance_pipe(name, security)
        try:
            with pytest.raises(winpipe.WindowsPipeError, match="refuses to start"):
                winpipe.create_first_instance_pipe(name, security)
        finally:
            winpipe.close_handle(handle)
    finally:
        security.release()


def test_the_pipe_name_is_unpredictable_and_per_run():
    names = {winpipe.random_pipe_name() for _ in range(16)}
    assert len(names) == 16
    for name in names:
        assert name.startswith("\\\\.\\pipe\\aido-ar2-")
        assert len(name.rsplit("-", 1)[-1]) == 32  # 128 bits of hex


def test_the_recorded_security_shape_carries_no_name_or_sid(r1_repo, git_executable):
    server, _binding = build_server(r1_repo, git_executable)
    shape = server.security_shape()
    serialized = json.dumps(shape)
    assert shape["pipe_name_recorded"] is False
    assert server.pipe_name not in serialized
    assert "S-1-5" not in serialized
    assert shape["first_pipe_instance"] is True
    assert shape["overlapped"] is True
    assert shape["reject_remote_clients"] is True
    assert shape["max_instances"] == 1


# -- READY before the runtime --------------------------------------------------


def test_the_broker_reaches_ready_before_any_runtime_launch(r1_repo, git_executable):
    server, _binding = build_server(r1_repo, git_executable)
    assert server.state == STATE_CREATED
    server.start()
    try:
        assert server.state == STATE_READY
        assert server.overlapped_started >= 1  # the first ConnectNamedPipe is issued
        # A client CAN connect at this point, which is the property that makes
        # "a tool call before the server exists" impossible rather than unlikely.
        client = PipeClient(server.pipe_name)
        client.close()
    finally:
        server.shutdown(TRIGGER_AIDO_TEARDOWN)


def test_start_raises_rather_than_returning_a_broker_that_is_not_ready(
    r1_repo, git_executable
):
    """A broker that has not reached READY is a refusal, never a launched runtime."""
    gate = threading.Event()
    server, _binding = build_server(
        r1_repo, git_executable, hooks=BrokerTestHooks(block_worker_before_ready=gate)
    )
    with pytest.raises(winpipe.WindowsPipeError, match="no runtime is launched"):
        server.start(ready_deadline_seconds=0.2)
    assert server.state != STATE_READY
    # Suite hygiene: release the worker, let it reach READY, then tear down normally.
    gate.set()
    deadline = time.monotonic() + 5.0
    while server.state == STATE_CREATED and time.monotonic() < deadline:
        time.sleep(0.02)
    lifecycle = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    assert lifecycle["worker_termination_observed"] is True


# -- a real round trip ---------------------------------------------------------


def test_one_real_lf_framed_round_trip_over_the_pipe(r1_repo, git_executable):
    server, binding = build_server(r1_repo, git_executable)
    server.start()
    client = PipeClient(server.pipe_name)
    try:
        client.send(
            {
                "v": PROTOCOL_VERSION,
                "id": "r1",
                "cap": binding.capability_id,
                "tok": binding.token,
                "op": "read_file",
                "path_candidate": "calc.py",
            }
        )
        response = client.receive()
        assert response["ok"] is True
        assert response["id"] == "r1"
        assert "return value < limit" in response["result"]["text"]
        assert len(response["result"]["sha256"]) == 64
    finally:
        client.close()
        lifecycle = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    assert lifecycle["state_reached"] == STATE_CLOSED
    assert server.handler.diagnostics.frames_received == 1
    assert server.handler.diagnostics.frames_written == 1


def test_an_edit_round_trip_requires_the_read_receipt(r1_repo, git_executable):
    server, binding = build_server(r1_repo, git_executable)
    server.start()
    client = PipeClient(server.pipe_name)
    try:
        base = {
            "v": PROTOCOL_VERSION,
            "cap": binding.capability_id,
            "tok": binding.token,
        }
        client.send({**base, "id": "e1", "op": "edit_file", "path_candidate": "calc.py",
                     "base_sha256": "0" * 64, "old_text": "a", "new_text": "b"})
        refused = client.receive()
        assert refused["ok"] is False and refused["error"]["code"] == "refused"

        client.send({**base, "id": "r1", "op": "read_file", "path_candidate": "calc.py"})
        read = client.receive()
        client.send({**base, "id": "e2", "op": "edit_file", "path_candidate": "calc.py",
                     "base_sha256": read["result"]["sha256"],
                     "old_text": "return value < limit",
                     "new_text": "return value <= limit"})
        applied = client.receive()
        assert applied["ok"] is True
        assert applied["result"]["applied"] is True
    finally:
        client.close()
        server.shutdown(TRIGGER_AIDO_TEARDOWN)


# -- cancellation and reap -----------------------------------------------------


def test_shutdown_event_wakes_a_pending_connect_and_it_is_cancelled_and_reaped(
    r1_repo, git_executable
):
    server, _binding = build_server(r1_repo, git_executable)
    server.start()
    # No client ever connects, so ConnectNamedPipe is genuinely pending.
    lifecycle = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    assert lifecycle["state_reached"] == STATE_CLOSED
    assert lifecycle["shutdown_trigger"] == TRIGGER_AIDO_TEARDOWN
    assert lifecycle["overlapped_operations_started"] >= 1
    assert (
        lifecycle["overlapped_operations_reaped"]
        == lifecycle["overlapped_operations_started"]
    )
    assert lifecycle["pending_operations_unreaped"] == 0
    assert lifecycle["handles_closed"] is True
    assert lifecycle["worker_termination_observed"] is True
    assert lifecycle["teardown_outcome"] == "closed_observed"
    assert lifecycle["client_connected"] is False


def test_a_pending_read_is_cancelled_and_reaped_at_shutdown(r1_repo, git_executable):
    server, _binding = build_server(r1_repo, git_executable)
    server.start()
    client = PipeClient(server.pipe_name)
    try:
        # Connected but silent: the broker's overlapped ReadFile is pending.
        time.sleep(0.2)
        lifecycle = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    finally:
        client.close()
    assert lifecycle["client_connected"] is True
    assert lifecycle["state_reached"] == STATE_CLOSED
    assert (
        lifecycle["overlapped_operations_reaped"]
        == lifecycle["overlapped_operations_started"]
    )
    assert lifecycle["pending_operations_unreaped"] == 0


def test_client_death_unblocks_the_pending_read_by_itself(r1_repo, git_executable):
    server, _binding = build_server(r1_repo, git_executable)
    server.start()
    client = PipeClient(server.pipe_name)
    time.sleep(0.2)
    client.close()
    # No shutdown yet: the worker should end its serve loop on the broken pipe.
    deadline = time.monotonic() + 5.0
    while server.state not in ("DRAINING", STATE_CLOSED) and time.monotonic() < deadline:
        time.sleep(0.05)
    lifecycle = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    assert lifecycle["state_reached"] == STATE_CLOSED
    assert lifecycle["worker_termination_observed"] is True


def test_a_stalled_write_is_cancellable(r1_repo, git_executable):
    """A client that connects and never reads can stall a write once the buffer fills."""
    from ar2.capability import CapDefinitions, mint_capability

    # A response larger than the 64 KiB pipe buffer forces the stall.
    big = "q = 1  # padding to exceed the pipe buffer\n" * 3000
    target = r1_repo.repo_root + "\\big.py"
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(big)
    sed = mint_capability(
        authority=r1_repo.authority,
        tracked_manifest=("big.py", "calc.py", "test_calc.py"),
        protected_patterns=R1.protected_patterns,
        verification_witness_paths=R1.verification_witness_paths,
    )
    binding = BrokerBinding.mint(sed.capability_id)
    handler = BrokerRequestHandler(
        sed=sed, run_state=RunState(caps=sed.caps), binding=binding,
        diagnostics=BrokerDiagnostics(),
    )
    server = BrokerServer(handler, shutdown_ack_grace_seconds=1.0)
    server.start()
    handle = winpipe.connect_client(server.pipe_name)
    try:
        _winapi.WriteFile(
            handle,
            json.dumps(
                {
                    "v": PROTOCOL_VERSION, "id": "big", "cap": binding.capability_id,
                    "tok": binding.token, "op": "read_file", "path_candidate": "big.py",
                }
            ).encode("utf-8")
            + b"\n",
        )
        # Deliberately never read the response, so the broker's write stalls.
        time.sleep(0.5)
        lifecycle = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    finally:
        try:
            _winapi.CloseHandle(handle)
        except OSError:
            pass
    assert lifecycle["state_reached"] == STATE_CLOSED
    assert lifecycle["worker_termination_observed"] is True
    assert lifecycle["pending_operations_unreaped"] == 0


def test_a_repeated_or_late_cancel_is_safe(r1_repo, git_executable):
    """``Overlapped.cancel()`` is safe cross-thread and on an already completed op."""
    security = winpipe.build_current_user_security_attributes()
    try:
        name = winpipe.random_pipe_name()
        handle = winpipe.create_first_instance_pipe(name, security)
        try:
            overlapped = winpipe.connect_overlapped(handle)
            overlapped.cancel()
            result = winpipe.reap_overlapped(overlapped, 2000)
            assert result.reaped is True
            assert result.aborted is True
            # Late and repeated cancels do not raise.
            overlapped.cancel()
            overlapped.cancel()
        finally:
            winpipe.close_handle(handle)
    finally:
        security.release()


def test_the_pipe_name_is_retired_after_close(r1_repo, git_executable):
    server, _binding = build_server(r1_repo, git_executable)
    server.start()
    name = server.pipe_name
    lifecycle = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    assert lifecycle["handles_closed"] is True
    with pytest.raises(OSError) as info:
        winpipe.connect_client(name)
    assert info.value.winerror == winpipe.ERROR_FILE_NOT_FOUND


# -- TEARDOWN_INCOMPLETE -------------------------------------------------------


def test_a_failed_reap_records_teardown_incomplete_and_leaks_deliberately(
    r1_repo, git_executable
):
    """FU1 section 7.5: a kernel write into a released buffer is worse than a leak."""
    server, _binding = build_server(
        r1_repo,
        git_executable,
        hooks=BrokerTestHooks(force_reap_failure=True),
        shutdown_ack_grace_seconds=0.3,
        teardown_deadline_seconds=1.0,
    )
    server.start()
    lifecycle = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    try:
        assert lifecycle["state_reached"] == STATE_TEARDOWN_INCOMPLETE
        assert lifecycle["teardown_outcome"] == "teardown_incomplete"
        assert lifecycle["pending_operations_unreaped"] >= 1
        assert lifecycle["handles_closed"] is False
        assert "claims_permitted" not in lifecycle
        assert "residual_statement" in lifecycle
        forbidden = " ".join(lifecycle["claims_forbidden"]).lower()
        for phrase in ("terminated", "handles were released", "capability was revoked",
                       "clean_expected"):
            assert phrase in forbidden
    finally:
        server._test_only_complete_leaked_teardown()


def test_a_worker_that_does_not_terminate_records_teardown_incomplete(
    r1_repo, git_executable
):
    """A worker stuck past the broker deadline is recorded, never claimed away.

    The block stands in for the one residual overlapped cancellation cannot cover:
    a worker inside a synchronous local filesystem call.
    """
    blocker = threading.Event()
    server, _binding = build_server(
        r1_repo,
        git_executable,
        hooks=BrokerTestHooks(block_worker_before_teardown=blocker),
        shutdown_ack_grace_seconds=0.2,
        teardown_deadline_seconds=0.4,
    )
    server.start()
    lifecycle = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    try:
        assert lifecycle["state_reached"] == STATE_TEARDOWN_INCOMPLETE
        assert lifecycle["worker_termination_observed"] is False
        assert lifecycle["teardown_outcome"] == "teardown_incomplete"
        assert lifecycle["controller_cancel_escalation_used"] in (True, False)
        assert "AIDO stopped waiting" in lifecycle["residual_statement"]
        assert "did not observe the thread terminate" in lifecycle["residual_statement"]
    finally:
        # Suite hygiene: release the worker and OBSERVE it finish.
        blocker.set()
        if server._thread is not None:
            server._thread.join(timeout=5.0)
            assert server._thread.is_alive() is False
        server._test_only_complete_leaked_teardown()


def test_teardown_incomplete_forbids_a_clean_classification(r1_repo, git_executable):
    server, _binding = build_server(
        r1_repo,
        git_executable,
        hooks=BrokerTestHooks(force_reap_failure=True),
        shutdown_ack_grace_seconds=0.2,
        teardown_deadline_seconds=0.4,
    )
    server.start()
    lifecycle = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    try:
        assert lifecycle["state_reached"] != STATE_CLOSED
        # The harness gates the clean classification on exactly this.
        teardown_closed = lifecycle["state_reached"] == STATE_CLOSED
        assert teardown_closed is False
    finally:
        server._test_only_complete_leaked_teardown()


# -- ownership and claim rules -------------------------------------------------


def test_the_controller_never_closes_a_handle_or_kills_a_thread():
    """Asserted against the AST of ``BrokerServer.shutdown`` itself."""
    tree = ast.parse(inspect.getsource(broker_module))
    shutdown_node = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "shutdown"
    )
    called: list[str] = []
    for node in ast.walk(shutdown_node):
        if isinstance(node, ast.Call):
            func = node.func
            called.append(func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", ""))
    for banned in ("close_handle", "CloseHandle", "TerminateThread", "sleep", "_stop"):
        assert banned not in called, f"the controller must never call {banned}"
    # Its ONE escalation lever, and a bounded join.
    assert "cancel" in called
    assert "join" in called
    assert "set_event" in called


def test_no_synchronous_blocking_pipe_call_is_used_on_the_protocol_path():
    """Overlapped everywhere: FU1 measured that a synchronous design has no honest teardown.

    Asserted against the module's CODE via the AST, so the prose explaining what
    was rejected cannot trip the check.
    """
    tree = ast.parse(inspect.getsource(broker_module))
    banned_calls = {
        "ConnectNamedPipe", "ReadFile", "WriteFile", "CancelSynchronousIo",
        "CancelIoEx", "TerminateThread", "ThreadPoolExecutor", "Pool", "Process",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            assert name not in banned_calls, f"broker.py must not call {name}"
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = getattr(node, "module", None) or ""
            names = [alias.name for alias in node.names]
            for banned_module in ("multiprocessing", "asyncio", "concurrent"):
                assert not module.startswith(banned_module)
                assert not any(n.startswith(banned_module) for n in names)
    winpipe_source = inspect.getsource(winpipe)
    # winpipe issues them, and ONLY in overlapped form.
    assert "overlapped=True" in winpipe_source
    assert "_winapi.ReadFile(pipe_handle, size, True)" in winpipe_source
    assert "_winapi.WriteFile(pipe_handle, payload, True)" in winpipe_source


def test_only_one_daemon_worker_thread_exists_per_broker(r1_repo, git_executable):
    server, _binding = build_server(r1_repo, git_executable)
    server.start()
    try:
        live = [t for t in threading.enumerate() if t.name == "ar2-broker" and t.is_alive()]
        assert len(live) == 1
        assert live[0].daemon is True
    finally:
        server.shutdown(TRIGGER_AIDO_TEARDOWN)
    assert not [t for t in threading.enumerate() if t.name == "ar2-broker" and t.is_alive()]


def test_the_broker_deadlines_are_separate_from_the_runtime_deadlines(
    r1_repo, git_executable
):
    server, _binding = build_server(r1_repo, git_executable)
    server.start()
    lifecycle = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    deadlines = lifecycle["deadlines"]
    assert deadlines["ipc_frame_deadline_seconds"] == 30.0
    assert deadlines["broker_shutdown_ack_grace_seconds"] == 2.0
    assert deadlines["broker_teardown_deadline_seconds"] == 5.0
    note = deadlines["note"].lower()
    assert "no additional model call" in note
    assert "no retry" in note
    assert "token policy" in note


def test_the_closed_record_states_only_observed_facts(r1_repo, git_executable):
    server, _binding = build_server(r1_repo, git_executable)
    server.start()
    lifecycle = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    permitted = " ".join(lifecycle["claims_permitted"]).lower()
    forbidden = " ".join(lifecycle["claims_forbidden"]).lower()
    assert "observed to terminate" in permitted
    assert "reaped" in permitted
    assert "pi" in forbidden and "gpu occupancy" in forbidden
    assert "sandboxed" in forbidden
    assert "no process holds a handle to the pipe" in forbidden
    chain = lifecycle["chain"]
    assert "AIDO wait ended" in chain and "capability provably withdrawn" in chain


def test_the_filesystem_io_limitation_is_stated_on_every_lifecycle_record(
    r1_repo, git_executable
):
    """Overlapped cancellation bounds pipe I/O. It says nothing about stat/open/read."""
    server, _binding = build_server(r1_repo, git_executable)
    server.start()
    lifecycle = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    text = lifecycle["filesystem_io_limitation"]
    assert "NAMED-PIPE I/O" in text
    assert "does not prove" in text
    assert "TEARDOWN_INCOMPLETE" in text
    assert "No hard cancellation or guaranteed thread termination is claimed" in text
    lowered = text.lower()
    assert "cancels filesystem calls" not in lowered
    assert "guaranteed" in lowered  # only inside the negation asserted above


# -- FU-F: the security descriptor allocation is released exactly once --------
#
# ConvertStringSecurityDescriptorToSecurityDescriptorW allocates memory that
# UserScopedSecurityAttributes._descriptor previously never freed -- a per-run
# LocalAlloc leak. It only needs to remain valid through the ONE
# CreateNamedPipe call that consumes it.


def test_a_fresh_security_attributes_object_starts_unreleased():
    security = winpipe.build_current_user_security_attributes()
    try:
        assert security.released is False
    finally:
        security.release()


def test_release_is_idempotent_and_never_double_frees():
    """Calling release() twice must not raise and must not corrupt anything."""
    security = winpipe.build_current_user_security_attributes()
    security.release()
    assert security.released is True
    security.release()  # must not raise, must not double-free
    security.release()
    assert security.released is True


def test_start_releases_the_descriptor_after_successful_pipe_creation(
    r1_repo, git_executable
):
    server, _binding = build_server(r1_repo, git_executable)
    assert server._security.released is False
    server.start()
    try:
        assert server._security.released is True
    finally:
        server.shutdown(TRIGGER_AIDO_TEARDOWN)


def test_start_releases_the_descriptor_even_when_pipe_creation_fails(
    r1_repo, git_executable
):
    """A pipe-creation FAILURE must release too, not only the success path."""
    server, _binding = build_server(r1_repo, git_executable)
    # Force create_first_instance_pipe to fail deterministically, without a
    # real name collision: swap in a callable that raises.
    original = winpipe.create_first_instance_pipe

    def always_fails(name, security):
        raise winpipe.WindowsPipeError("synthetic pipe-creation failure for FU-F")

    winpipe.create_first_instance_pipe = always_fails
    try:
        with pytest.raises(winpipe.WindowsPipeError, match="synthetic pipe-creation failure"):
            server.start()
        assert server._security.released is True
    finally:
        winpipe.create_first_instance_pipe = original
        # Suite hygiene: nothing was actually created, so there is no worker or
        # handle to tear down.


def test_shutdown_releases_the_descriptor_even_if_start_was_never_called(
    r1_repo, git_executable
):
    """The backstop: a BrokerServer that is torn down without ever starting
    must not leak the descriptor construction allocated in __init__."""
    server, _binding = build_server(r1_repo, git_executable)
    assert server._security.released is False
    lifecycle = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    assert server._security.released is True
    assert lifecycle["rung_reached"] == "B0"


def test_security_shape_remains_readable_after_release(r1_repo, git_executable):
    """describe() is string-only and must stay safe to call after release()."""
    server, _binding = build_server(r1_repo, git_executable)
    server.start()
    try:
        shape_after_start = server.security_shape()
        assert shape_after_start["security_descriptor_built"] is True
        assert shape_after_start["dacl_protected"] is True
    finally:
        lifecycle = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    # Reading it again after full teardown (release already happened twice by
    # now, both idempotently) must still work.
    shape_after_shutdown = server.security_shape()
    assert shape_after_shutdown["security_descriptor_built"] is True
    assert lifecycle["state_reached"] == STATE_CLOSED


# -- FU1A: released-address reuse and a second start() both fail closed -------


def test_address_after_release_fails_closed():
    security = winpipe.build_current_user_security_attributes()
    security.release()
    with pytest.raises(winpipe.WindowsPipeError, match="already released"):
        _ = security.address


def test_a_second_broker_start_call_fails_closed(r1_repo, git_executable):
    """One BrokerServer is good for exactly one run -- even after CLOSED."""
    server, _binding = build_server(r1_repo, git_executable)
    server.start()
    lifecycle = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    assert lifecycle["state_reached"] == STATE_CLOSED
    with pytest.raises(winpipe.WindowsPipeError, match="already been started"):
        server.start()


def test_a_second_start_call_while_still_serving_also_fails_closed(
    r1_repo, git_executable
):
    server, _binding = build_server(r1_repo, git_executable)
    server.start()
    try:
        with pytest.raises(winpipe.WindowsPipeError, match="already been started"):
            server.start()
    finally:
        server.shutdown(TRIGGER_AIDO_TEARDOWN)
