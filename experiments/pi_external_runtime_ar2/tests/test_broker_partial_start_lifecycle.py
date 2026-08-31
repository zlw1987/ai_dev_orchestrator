"""5F3B-I2B-L1-D1: AR2 broker partial-start lifecycle surface closure.

Independent review found that ``BrokerServer.start()``'s public state stays
``CREATED`` until the worker reaches ``READY``, so after ``start()`` raises the
public surface could not distinguish which of five points failed:

    A. create_first_instance_pipe itself failed -- no pipe resource created
    B. pipe created, create_shutdown_event failed
    C. pipe + event created, Thread construction failed
    D. Thread object assigned, but Thread.start() itself failed
    E. worker started, but READY was never reached before the deadline

and the old ``shutdown()`` returned immediately whenever ``self._thread is
None`` -- leaking the pipe/event handle in B and C, and (had ``self._thread``
been non-None with a never-started worker, state D) it would have called
``Thread.join()`` on a thread that was never started, which CPython raises
``RuntimeError`` for.

This file exercises exactly those five points, deterministically, by
monkeypatching the narrow primitives ``BrokerServer.start()`` calls --
``winpipe.create_first_instance_pipe``, ``winpipe.create_shutdown_event``,
``threading.Thread`` construction, and ``threading.Thread.start`` -- never by
racing real OS timing.

No network, no socket, no model, no real Pi process -- consistent with the
rest of this offline suite.
"""

from __future__ import annotations

import threading

import pytest

from ar2 import broker as broker_module
from ar2 import winpipe
from ar2.broker import (
    STATE_CLOSED,
    STATE_CREATED,
    STATE_TEARDOWN_INCOMPLETE,
    TRIGGER_AIDO_TEARDOWN,
    BrokerTestHooks,
)

from test_pipe_lifecycle import PipeClient, build_server


# -- A: create_first_instance_pipe itself fails --------------------------------


def test_pipe_creation_failure_leaves_the_resource_created_fact_false(
    r1_repo, git_executable
):
    server, _binding = build_server(r1_repo, git_executable)
    original = winpipe.create_first_instance_pipe

    def always_fails(name, security):
        raise winpipe.WindowsPipeError("synthetic D1-A pipe-creation failure")

    winpipe.create_first_instance_pipe = always_fails
    try:
        with pytest.raises(winpipe.WindowsPipeError, match="synthetic D1-A"):
            server.start()
    finally:
        winpipe.create_first_instance_pipe = original

    assert server.pipe_resource_created is False
    assert server.state == STATE_CREATED

    # Unchanged "shutdown before start" semantics: nothing was created, so
    # there is nothing to close, and the pre-existing rung is preserved.
    lifecycle = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    assert lifecycle["rung_reached"] == "B0"
    assert lifecycle["handles_closed"] is False
    assert not [t for t in threading.enumerate() if t.name == "ar2-broker"]

    # Idempotent: a second shutdown() call is safe too.
    server.shutdown(TRIGGER_AIDO_TEARDOWN)


# -- B: pipe succeeds, create_shutdown_event fails ------------------------------


def test_shutdown_event_failure_still_closes_the_created_pipe(r1_repo, git_executable):
    server, _binding = build_server(r1_repo, git_executable)
    pipe_name = server.pipe_name
    original = winpipe.create_shutdown_event

    def always_fails():
        raise winpipe.WindowsPipeError("synthetic D1-B shutdown-event failure")

    winpipe.create_shutdown_event = always_fails
    try:
        with pytest.raises(winpipe.WindowsPipeError, match="synthetic D1-B"):
            server.start()
    finally:
        winpipe.create_shutdown_event = original

    assert server.pipe_resource_created is True
    assert server.state == STATE_CREATED  # the worker never ran to advance it

    lifecycle = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    assert lifecycle["state_reached"] == STATE_CLOSED
    assert lifecycle["handles_closed"] is True
    assert lifecycle["rung_reached"] == "N2"
    assert "no broker worker thread ever started" in " ".join(
        lifecycle["claims_permitted"]
    )
    forbidden = " ".join(lifecycle["claims_forbidden"]).lower()
    assert "observed to terminate" in forbidden

    # The pipe name genuinely no longer resolves for a new client.
    with pytest.raises(OSError) as info:
        winpipe.connect_client(pipe_name)
    assert info.value.winerror == winpipe.ERROR_FILE_NOT_FOUND

    assert not [t for t in threading.enumerate() if t.name == "ar2-broker"]

    # Idempotent repeat.
    repeat = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    assert repeat["state_reached"] == STATE_CLOSED


# -- C: pipe + event succeed, Thread construction fails -------------------------


def test_thread_construction_failure_closes_pipe_and_event(r1_repo, git_executable):
    server, _binding = build_server(r1_repo, git_executable)
    pipe_name = server.pipe_name
    original_thread_cls = broker_module.threading.Thread

    def failing_ctor(*args, **kwargs):
        raise RuntimeError("synthetic D1-C Thread construction failure")

    broker_module.threading.Thread = failing_ctor
    try:
        with pytest.raises(RuntimeError, match="synthetic D1-C"):
            server.start()
    finally:
        broker_module.threading.Thread = original_thread_cls

    assert server.pipe_resource_created is True
    assert server._thread is None  # construction itself never returned an object

    lifecycle = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    assert lifecycle["state_reached"] == STATE_CLOSED
    assert lifecycle["handles_closed"] is True

    with pytest.raises(OSError) as info:
        winpipe.connect_client(pipe_name)
    assert info.value.winerror == winpipe.ERROR_FILE_NOT_FOUND

    assert not [t for t in threading.enumerate() if t.name == "ar2-broker"]


# -- D: Thread object assigned, but Thread.start() itself fails -----------------


def test_thread_start_failure_does_not_join_an_unstarted_thread(
    r1_repo, git_executable
):
    """The exact defect: an unconditional join() on this thread object raises
    RuntimeError. shutdown() must never attempt it."""
    server, _binding = build_server(r1_repo, git_executable)
    pipe_name = server.pipe_name
    original_start = threading.Thread.start

    def failing_start(self):
        raise RuntimeError("synthetic D1-D Thread.start failure")

    threading.Thread.start = failing_start
    try:
        with pytest.raises(RuntimeError, match="synthetic D1-D"):
            server.start()
    finally:
        threading.Thread.start = original_start

    assert server.pipe_resource_created is True
    assert server._thread is not None  # the Thread OBJECT was assigned
    assert server._worker_thread_started is False  # but it never actually started
    with pytest.raises(RuntimeError, match="cannot join thread before it is started"):
        server._thread.join(timeout=0.01)  # proves the raw hazard this guards against

    # shutdown() must not raise, must not attempt that join, and must close
    # the handles this partial start actually created.
    lifecycle = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    assert lifecycle["state_reached"] == STATE_CLOSED
    assert lifecycle["handles_closed"] is True

    with pytest.raises(OSError) as info:
        winpipe.connect_client(pipe_name)
    assert info.value.winerror == winpipe.ERROR_FILE_NOT_FOUND

    # The never-started Thread object holds no OS thread resource to leak.
    assert not [t for t in threading.enumerate() if t.name == "ar2-broker"]

    # Idempotent repeat: no exception, no double close.
    repeat = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    assert repeat["state_reached"] == STATE_CLOSED


# -- E: worker started, READY deadline expired -----------------------------------


def test_ready_deadline_expiry_keeps_the_existing_worker_owned_ladder(
    r1_repo, git_executable
):
    """State E is NOT a partial-start-no-worker case: a real worker is running,
    so the pre-existing worker-owned teardown/cancel/reap ladder must still be
    the one that answers, unchanged."""
    gate = threading.Event()
    server, _binding = build_server(
        r1_repo, git_executable, hooks=BrokerTestHooks(block_worker_before_ready=gate)
    )
    with pytest.raises(winpipe.WindowsPipeError, match="no runtime is launched"):
        server.start(ready_deadline_seconds=0.2)

    assert server.pipe_resource_created is True
    assert server._worker_thread_started is True  # Thread.start() DID succeed
    assert server.state != STATE_CLOSED

    gate.set()  # release the worker so it can proceed to teardown
    lifecycle = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    assert lifecycle["worker_termination_observed"] is True
    assert lifecycle["rung_reached"] == "B5"  # the worker ladder's rung, not "N2"
    assert not [t for t in threading.enumerate() if t.name == "ar2-broker"]


# -- partial-start handle close itself fails: no false CLOSED -------------------


def test_a_failed_handle_close_in_partial_start_never_claims_closed(
    r1_repo, git_executable
):
    server, _binding = build_server(r1_repo, git_executable)
    pipe_name = server.pipe_name
    original_event_ctor = winpipe.create_shutdown_event

    def event_fails():
        raise winpipe.WindowsPipeError("synthetic D1 shutdown-event failure")

    winpipe.create_shutdown_event = event_fails
    try:
        with pytest.raises(winpipe.WindowsPipeError, match="synthetic D1"):
            server.start()
    finally:
        winpipe.create_shutdown_event = original_event_ctor

    assert server.pipe_resource_created is True

    original_close = winpipe.close_handle

    def close_fails(handle):
        raise OSError("synthetic D1 CloseHandle failure")

    winpipe.close_handle = close_fails
    try:
        lifecycle = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    finally:
        winpipe.close_handle = original_close

    assert lifecycle["state_reached"] != STATE_CLOSED
    assert lifecycle["state_reached"] == STATE_TEARDOWN_INCOMPLETE
    assert lifecycle["handles_closed"] is False
    assert "claims_permitted" not in lifecycle
    assert "residual_statement" in lifecycle
    assert "no broker worker thread ever started" in lifecycle["residual_statement"].lower()
    # The primary start() exception is never hidden behind this later failure:
    # the caller already observed it via pytest.raises above.

    # Hygiene: now let the real close_handle succeed, proving the retry path
    # is idempotent and actually reaches CLOSED once the transient failure
    # clears -- no forced-leak escape hatch needed for this new path.
    recovered = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    assert recovered["state_reached"] == STATE_CLOSED
    assert recovered["handles_closed"] is True
    with pytest.raises(OSError) as info:
        winpipe.connect_client(pipe_name)
    assert info.value.winerror == winpipe.ERROR_FILE_NOT_FOUND


# -- shutdown before start: unchanged ---------------------------------------------


def test_shutdown_before_start_is_still_the_original_no_op(r1_repo, git_executable):
    server, _binding = build_server(r1_repo, git_executable)
    assert server.pipe_resource_created is False
    lifecycle = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    assert lifecycle["rung_reached"] == "B0"
    assert lifecycle["handles_closed"] is False
    assert lifecycle["teardown_elapsed_seconds"] == 0.0
    assert server._security.released is True


# -- normal READY -> use -> shutdown is untouched by any of this -----------------


def test_normal_lifecycle_is_unaffected_by_the_partial_start_surface(
    r1_repo, git_executable
):
    server, binding = build_server(r1_repo, git_executable)
    server.start()
    try:
        assert server.pipe_resource_created is True
        assert server._worker_thread_started is True
        client = PipeClient(server.pipe_name)
        client.close()
    finally:
        lifecycle = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    assert lifecycle["state_reached"] == STATE_CLOSED
    assert lifecycle["rung_reached"] == "B5"
    assert "the broker thread was OBSERVED to terminate" in " ".join(
        lifecycle["claims_permitted"]
    )
