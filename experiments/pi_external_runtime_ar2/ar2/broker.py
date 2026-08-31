"""The AIDO-owned Python broker: request authority + named-pipe lifecycle.

Two classes, deliberately separable:

- :class:`BrokerRequestHandler` -- the authority. Validates one frame, checks the
  per-run binding, enforces id uniqueness and the single-flight slot, evaluates
  the fixed dynamic preconditions against AIDO-owned run state, and dispatches to
  :mod:`ar2.operations`. It touches no pipe, which is why the offline suite can
  drive it directly.
- :class:`BrokerServer` -- the FU1 section 7 lifecycle. One in-process daemon
  thread, **overlapped** Windows named-pipe I/O, an explicit shutdown event, and
  a bounded, observed teardown.

    CREATED -> READY -> SERVING -> DRAINING -> CLOSED
                                           \\-> TEARDOWN_INCOMPLETE

**No synchronous blocking pipe I/O anywhere on the protocol path.** FU1 measured
that a controller-side ``CloseHandle`` with a synchronous ``ConnectNamedPipe``
pending did not return in ~19 s -- the obvious teardown lever blocks the
orchestrator. Overlapped operations are cancellable from any thread and reapable
in microseconds.

Ownership rule, which is what makes the shutdown sequence safe. It is a
**partition on two monotonic facts** -- ``pipe_resource_created`` and whether
``Thread.start()`` itself returned without raising -- not a single blanket
statement, because 5F3B-I2B-L1-D1 added a partial-start lifecycle in which no
worker exists to own anything:

    **A. Worker successfully started** (``Thread.start()`` returned without
    raising). From that point on, the broker thread owns pipe/event teardown.
    Controller-side shutdown only signals the shutdown event; it never calls
    ``CloseHandle`` on the worker-owned pipe or event, never releases an
    ``Overlapped`` buffer, never kills a thread, never calls
    ``TerminateThread``, never sleeps and assumes, and never claims completion
    it did not observe. Its ONE escalation lever is ``Overlapped.cancel()`` on
    the worker's pending operation. The worker closes its own handles only
    after that pending overlapped operation has been safely reaped. (See the
    truthfulness limit below for the one case this can leave incomplete.)

    **B. No worker successfully started, but a pipe resource was created**
    (``pipe_resource_created`` is True and ``Thread.start()`` never returned
    successfully -- i.e. it was never called, or it raised). There is no
    worker to own teardown, so ownership never left the creator.
    ``BrokerServer.shutdown()`` then runs on the caller/controller thread and
    directly closes ONLY the pipe and shutdown-event handles that
    ``BrokerServer`` itself created in this ``start()`` call. Raw handles are
    never exposed to the caller. ``CLOSED`` is claimed only once every
    actually-created handle close has succeeded. This is a narrow exception
    for resources nothing else owns -- it is not permission for the
    controller to close handles belonging to a running worker.

    **C. Nothing created** (``pipe_resource_created`` is False). No broker OS
    resource was ever created, so ``shutdown()`` performs no handle cleanup.

Truthfulness limit that must never be softened:

    Overlapped cancellation bounds NAMED-PIPE I/O. It does **not** prove that a
    synchronous local filesystem call -- ``stat``, ``open``, ``read``, ``write``,
    ``fstat`` -- can be cancelled from the controller. If teardown occurs while
    the broker thread is inside a filesystem operation and the worker does not
    terminate within the broker deadline, the outcome is
    ``TEARDOWN_INCOMPLETE``. AIDO does not claim hard cancellation or guaranteed
    thread termination, and it does **not** switch to a child-process broker
    merely to remove this residual (FU1 section 8).
"""

from __future__ import annotations

import hmac
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from . import winpipe
from .capability import (
    EDIT_FILE,
    READ_FILE,
    RunState,
    StaticEligibilityDomain,
    TERMINAL_INTERNAL,
    TERMINAL_PROTOCOL,
    TERMINAL_UNAUTHORIZED,
)
from .operations import perform_edit, perform_read
from .wire import (
    ERR_INTERNAL_ERROR,
    ERR_PROTOCOL_ERROR,
    ERR_UNAUTHORIZED,
    MAX_REQUEST_FRAME_BYTES,
    OP_EDIT_FILE,
    OP_READ_FILE,
    TERMINAL_ERROR_CODES,
    WireProtocolError,
    error_frame,
    parse_request_frame,
    response_is_host_safe,
    success_frame,
)

# -- deadlines. Kept strictly separate from the Pi runtime/semantic deadlines --
IPC_FRAME_DEADLINE_SECONDS = 30.0
BROKER_SHUTDOWN_ACK_GRACE_SECONDS = 2.0
BROKER_TEARDOWN_DEADLINE_SECONDS = 5.0
BROKER_IDLE_WAIT_SLICE_MS = 250
BROKER_REAP_WAIT_MS = 2000
BROKER_READY_DEADLINE_SECONDS = 5.0

STATE_CREATED = "CREATED"
STATE_READY = "READY"
STATE_SERVING = "SERVING"
STATE_DRAINING = "DRAINING"
STATE_CLOSED = "CLOSED"
STATE_TEARDOWN_INCOMPLETE = "TEARDOWN_INCOMPLETE"

TRIGGER_RUNTIME_SETTLED = "runtime_settled"
TRIGGER_PI_EXITED = "pi_exited"
TRIGGER_RUNTIME_DEADLINE = "runtime_deadline_expired"
TRIGGER_PROTOCOL_TERMINAL = "protocol_terminal"
TRIGGER_UNAUTHORIZED_FRAME = "unauthorized_frame"
TRIGGER_AIDO_TEARDOWN = "aido_teardown"


# -- per-run binding -----------------------------------------------------------


@dataclass(frozen=True)
class BrokerBinding:
    """The per-run capability id and 256-bit token.

    Both are generated by AIDO. They do **not** come from the model, the prompt,
    the project config, or the operator-local experiment config. They are
    delivered only through the generated, disposable extension configuration;
    they never enter a model prompt, are never logged, printed, or persisted, and
    the token value is added to the artifact scrub denylist.

    This is an **integrity and attribution control, not OS isolation** against a
    same-user adversary: that adversary can read the generated config, or the
    disposable repository, without the broker at all (AR2D section 10.4).
    """

    capability_id: str
    token: str

    @classmethod
    def mint(cls, capability_id: str) -> "BrokerBinding":
        return cls(capability_id=capability_id, token=secrets.token_urlsafe(32))

    def matches(self, capability_id: str, token: str) -> bool:
        """Constant-time comparison for both halves. Never short-circuits."""
        capability_ok = hmac.compare_digest(
            self.capability_id.encode("utf-8"), capability_id.encode("utf-8")
        )
        token_ok = hmac.compare_digest(
            self.token.encode("utf-8"), token.encode("utf-8")
        )
        return capability_ok and token_ok


# -- the authority -------------------------------------------------------------


@dataclass
class BrokerDiagnostics:
    """``broker_recorded_*`` -- AIDO-authored, and DIAGNOSTIC ONLY.

    A broker log is **not** repository truth, even though AIDO wrote it. It
    records the operations AIDO performed *through the broker*; it cannot see a
    write that happened another way, it does not know what the filesystem did
    afterwards, and it is a record of intent and return value, not of final
    state.
    """

    accepted: dict[str, int] = field(default_factory=dict)
    refused: dict[str, int] = field(default_factory=dict)
    refusal_reasons: list[str] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)
    frames_received: int = 0
    frames_written: int = 0
    unsafe_response_frames_suppressed: int = 0

    def accept(self, operation: str) -> None:
        self.accepted[operation] = self.accepted.get(operation, 0) + 1

    def refuse(self, operation: str, code: str, reason: str) -> None:
        key = f"{operation}:{code}"
        self.refused[key] = self.refused.get(key, 0) + 1
        self.refusal_reasons.append(f"{operation}:{code}:{reason}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "trust": "AIDO-authored, DIAGNOSTIC ONLY -- never repository truth",
            "frames_received": self.frames_received,
            "frames_written": self.frames_written,
            "accepted_operations": dict(sorted(self.accepted.items())),
            "refused_operations": dict(sorted(self.refused.items())),
            "refusal_reason_codes": list(self.refusal_reasons),
            "anomalies": list(self.anomalies),
            "unsafe_response_frames_suppressed": self.unsafe_response_frames_suppressed,
        }


@dataclass(frozen=True)
class HandledFrame:
    """One handled request frame: the bytes to write back, and whether it ends it."""

    response: bytes
    terminal: bool
    terminal_flag: str | None


class BrokerRequestHandler:
    """The ONE authority. Re-decides every request from scratch, caching nothing."""

    def __init__(
        self,
        *,
        sed: StaticEligibilityDomain,
        run_state: RunState,
        binding: BrokerBinding,
        diagnostics: BrokerDiagnostics | None = None,
    ) -> None:
        self.sed = sed
        self.run_state = run_state
        self.binding = binding
        self.diagnostics = diagnostics or BrokerDiagnostics()
        self._forbidden_response_values = (binding.token, binding.capability_id)

    # -- frame handling ---------------------------------------------------

    def handle_frame(self, raw: bytes) -> HandledFrame:
        self.diagnostics.frames_received += 1
        try:
            request = parse_request_frame(raw)
        except WireProtocolError as exc:
            self.diagnostics.refuse("unknown", ERR_PROTOCOL_ERROR, str(exc))
            self.run_state.mark_terminal(TERMINAL_PROTOCOL)
            return self._terminal(
                "0", ERR_PROTOCOL_ERROR, "malformed_request", TERMINAL_PROTOCOL
            )

        if not self.binding.matches(request.capability_id, request.token):
            self.diagnostics.refuse(request.operation, ERR_UNAUTHORIZED, "binding_mismatch")
            self.diagnostics.anomalies.append(
                "a frame reached the broker carrying a capability id or token that "
                "does not match this run's AIDO-generated binding"
            )
            self.run_state.mark_terminal(TERMINAL_UNAUTHORIZED)
            return self._terminal(
                request.request_id, ERR_UNAUTHORIZED, "binding_mismatch", TERMINAL_UNAUTHORIZED
            )

        if self.run_state.terminal:
            self.diagnostics.refuse(request.operation, ERR_PROTOCOL_ERROR, "already_terminal")
            return self._terminal(
                request.request_id, ERR_PROTOCOL_ERROR, "capability_terminal", TERMINAL_PROTOCOL
            )

        if request.request_id in self.run_state.seen_request_ids:
            self.diagnostics.refuse(request.operation, ERR_PROTOCOL_ERROR, "duplicate_request_id")
            self.run_state.mark_terminal(TERMINAL_PROTOCOL)
            return self._terminal(
                request.request_id, ERR_PROTOCOL_ERROR, "duplicate_request_id", TERMINAL_PROTOCOL
            )
        self.run_state.seen_request_ids.add(request.request_id)

        if self.run_state.in_flight:
            self.diagnostics.refuse(request.operation, ERR_PROTOCOL_ERROR, "concurrent_request")
            self.run_state.mark_terminal(TERMINAL_PROTOCOL)
            return self._terminal(
                request.request_id, ERR_PROTOCOL_ERROR, "concurrent_request", TERMINAL_PROTOCOL
            )

        self.run_state.in_flight = True
        try:
            if request.operation == OP_READ_FILE:
                outcome = perform_read(self.sed, self.run_state, request.path_candidate)
            elif request.operation == OP_EDIT_FILE:
                outcome = perform_edit(
                    self.sed,
                    self.run_state,
                    request.path_candidate,
                    base_sha256=request.base_sha256 or "",
                    old_text=request.old_text or "",
                    new_text=request.new_text or "",
                )
            else:  # pragma: no cover - parse_request_frame already refused it
                self.run_state.mark_terminal(TERMINAL_PROTOCOL)
                return self._terminal(
                    request.request_id, ERR_PROTOCOL_ERROR, "unsupported_operation",
                    TERMINAL_PROTOCOL,
                )
        except Exception as exc:  # noqa: BLE001 - the broker refuses to guess
            self.diagnostics.refuse(
                request.operation, ERR_INTERNAL_ERROR, type(exc).__name__
            )
            self.run_state.mark_terminal(TERMINAL_INTERNAL)
            return self._terminal(
                request.request_id, ERR_INTERNAL_ERROR, "broker_failure", TERMINAL_INTERNAL
            )
        finally:
            self.run_state.in_flight = False

        if outcome.ok:
            self.diagnostics.accept(request.operation)
            frame = success_frame(request.request_id, outcome.result or {})
        else:
            self.diagnostics.refuse(
                request.operation, outcome.code or ERR_INTERNAL_ERROR, outcome.internal_reason
            )
            frame = error_frame(
                request.request_id, outcome.code or ERR_INTERNAL_ERROR, outcome.detail
            )
            if outcome.code in TERMINAL_ERROR_CODES:
                self.run_state.mark_terminal(TERMINAL_INTERNAL)
                return HandledFrame(
                    response=self._safe(frame, request.request_id),
                    terminal=True,
                    terminal_flag=TERMINAL_INTERNAL,
                )

        return HandledFrame(
            response=self._safe(frame, request.request_id), terminal=False, terminal_flag=None
        )

    # -- helpers ----------------------------------------------------------

    def _terminal(self, request_id: str, code: str, detail: str, flag: str) -> HandledFrame:
        return HandledFrame(
            response=self._safe(error_frame(request_id, code, detail), request_id),
            terminal=True,
            terminal_flag=flag,
        )

    def _safe(self, frame: bytes, request_id: str) -> bytes:
        """Final backstop: never write a frame carrying a host detail or a secret."""
        forbidden = (*self._forbidden_response_values, self.sed.canonical_root)
        if response_is_host_safe(frame, forbidden_values=forbidden):
            return frame
        self.diagnostics.unsafe_response_frames_suppressed += 1
        self.diagnostics.anomalies.append(
            "a response frame did not pass the host-detail self-check and was "
            "replaced by a bounded internal_error"
        )
        return error_frame(request_id, ERR_INTERNAL_ERROR, "broker_failure")


# -- the lifecycle -------------------------------------------------------------


@dataclass
class BrokerTestHooks:
    """Offline-only injection points. Never used by the live harness."""

    block_worker_before_ready: threading.Event | None = None
    block_worker_before_teardown: threading.Event | None = None
    reap_wait_ms_override: int | None = None
    skip_worker_teardown: bool = False
    # Forces every reap to report "not reaped", which drives the FU1 section 7.5
    # fail-closed branch deterministically. Synthetic injection for the offline
    # suite; the live harness never sets it.
    force_reap_failure: bool = False


class BrokerServer:
    """One per-run pipe instance, one daemon thread, overlapped I/O throughout."""

    def __init__(
        self,
        handler: BrokerRequestHandler,
        *,
        ipc_frame_deadline_seconds: float = IPC_FRAME_DEADLINE_SECONDS,
        shutdown_ack_grace_seconds: float = BROKER_SHUTDOWN_ACK_GRACE_SECONDS,
        teardown_deadline_seconds: float = BROKER_TEARDOWN_DEADLINE_SECONDS,
        idle_wait_slice_ms: int = BROKER_IDLE_WAIT_SLICE_MS,
        hooks: BrokerTestHooks | None = None,
        on_terminal: Callable[[str], None] | None = None,
    ) -> None:
        self.handler = handler
        self.ipc_frame_deadline_seconds = ipc_frame_deadline_seconds
        self.shutdown_ack_grace_seconds = shutdown_ack_grace_seconds
        self.teardown_deadline_seconds = teardown_deadline_seconds
        self.idle_wait_slice_ms = idle_wait_slice_ms
        self.hooks = hooks or BrokerTestHooks()
        self.on_terminal = on_terminal

        self._lock = threading.Lock()
        self._state = STATE_CREATED
        self._ready = threading.Event()
        self._closed_by_worker = threading.Event()
        self._thread: threading.Thread | None = None

        self._security = winpipe.build_current_user_security_attributes()
        self.pipe_name = winpipe.random_pipe_name()
        self._pipe_handle: int | None = None
        self._shutdown_event: int | None = None

        self._pending: Any = None
        self._pending_kind: str | None = None
        self._start_called = False

        # -- 5F3B-I2B-L1-D1: partial-start facts, both monotonic -----------
        # ``_pipe_resource_created`` becomes True ONLY immediately after
        # ``create_first_instance_pipe`` returns successfully; it never means
        # "attempted" and it never resets to False, not even after the handle
        # is later closed. ``_worker_thread_started`` becomes True ONLY
        # immediately after ``Thread.start()`` returns without raising --
        # ``self._thread is not None`` alone does NOT mean the worker started
        # (``Thread.start()`` itself can raise, e.g. "can't start new
        # thread"), and ``Thread.join()`` on a thread that never started
        # raises ``RuntimeError``. Kept private: shutdown() is the only
        # caller that needs it.
        self._pipe_resource_created = False
        self._worker_thread_started = False
        self._partial_start_no_worker = False

        self.overlapped_started = 0
        self.overlapped_reaped = 0
        self.handles_closed = False
        self.shutdown_trigger: str | None = None
        self.rung_reached = "none"
        self.controller_cancel_escalation_used = False
        self.worker_termination_observed = False
        self.teardown_elapsed_seconds: float | None = None
        self.client_connected = False
        self.worker_error: str | None = None

    # -- state ------------------------------------------------------------

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def _set_state(self, value: str) -> None:
        with self._lock:
            self._state = value
        self.handler.run_state.lifecycle_state = value

    @property
    def pipe_resource_created(self) -> bool:
        """Monotonic fact: the first-instance pipe was successfully created at
        least once for this run's ``start()`` call.

        True ONLY immediately after ``winpipe.create_first_instance_pipe``
        returns. It never means "creation was attempted" or "a resource might
        exist", and a failure raised by that call before returning leaves this
        False. It never resets to False afterwards -- not even once
        ``shutdown()`` has closed the handle -- because it records that the
        resource WAS created, not that it currently exists. Non-authority-
        bearing: it grants no access and hands back no handle.
        """
        return self._pipe_resource_created

    # -- start ------------------------------------------------------------

    def start(self, *, ready_deadline_seconds: float = BROKER_READY_DEADLINE_SECONDS) -> None:
        """Create the pipe and reach ``READY`` before the runtime is launched.

        A tool call that arrives before the server exists must be impossible, not
        merely unlikely, so this returns only once the worker has issued its
        first overlapped ``ConnectNamedPipe``.
        """
        # FU1A: a released security descriptor and a per-run pipe name must
        # never be reused. One BrokerServer is good for exactly one run; a
        # second start() call -- even after a full CLOSED teardown -- is
        # refused rather than silently re-creating a new pipe under an old
        # instance's bookkeeping.
        if self._start_called:
            raise winpipe.WindowsPipeError(
                "pipe error: this broker has already been started; start() may "
                "be called at most once per instance"
            )
        self._start_called = True

        # FU-F: the security descriptor is released right after the ONE call
        # that needs it, on EVERY outcome -- success, a pipe-creation failure
        # that raises, or a later partial-start failure (which happens after
        # this finally has already run). ``release()`` is idempotent, so this
        # can never double-free even if something else already released it.
        try:
            self._pipe_handle = winpipe.create_first_instance_pipe(
                self.pipe_name, self._security
            )
        finally:
            self._security.release()
        # The pipe now genuinely exists as an OS resource. Recorded before
        # anything else in start() can raise, so a later failure in this same
        # call (shutdown-event creation, Thread construction, Thread.start())
        # can never leave this fact incorrectly False.
        self._pipe_resource_created = True
        self._shutdown_event = winpipe.create_shutdown_event()
        self._thread = threading.Thread(target=self._serve, name="ar2-broker", daemon=True)
        self._thread.start()
        # Thread.start() returned without raising: the worker genuinely
        # started. self._thread being non-None is NOT this fact -- Thread()
        # construction can leave self._thread assigned while .start() itself
        # still fails.
        self._worker_thread_started = True
        if not self._ready.wait(timeout=ready_deadline_seconds):
            raise winpipe.WindowsPipeError(
                "pipe error: the broker did not reach READY within its deadline; "
                "no runtime is launched"
            )

    # -- worker -----------------------------------------------------------

    def _track(self, overlapped, kind: str) -> None:
        with self._lock:
            self._pending = overlapped
            self._pending_kind = kind
            self.overlapped_started += 1

    def _untrack_reaped(self) -> None:
        with self._lock:
            self._pending = None
            self._pending_kind = None
            self.overlapped_reaped += 1

    def _shutdown_signalled(self) -> bool:
        handle = self._shutdown_event
        if handle is None:
            return False
        return winpipe.wait_any([handle], 0) == winpipe.WAIT_OBJECT_0

    def _wait_operation(self, overlapped, deadline: float | None) -> str:
        """Bounded wait co-waiting the shutdown event. Never waits indefinitely."""
        assert self._shutdown_event is not None
        while True:
            rc = winpipe.wait_any(
                [overlapped.event, self._shutdown_event], self.idle_wait_slice_ms
            )
            if rc == winpipe.WAIT_OBJECT_0:
                return "completed"
            if rc == winpipe.WAIT_OBJECT_0 + 1:
                return "shutdown"
            if deadline is not None and time.monotonic() >= deadline:
                return "deadline"

    def _reap(self, overlapped) -> winpipe.ReapResult:
        if self.hooks.force_reap_failure:
            return winpipe.ReapResult(
                reaped=False, transferred=0, error_code=None, aborted=False,
                broken_pipe=False,
            )
        timeout = (
            self.hooks.reap_wait_ms_override
            if self.hooks.reap_wait_ms_override is not None
            else BROKER_REAP_WAIT_MS
        )
        result = winpipe.reap_overlapped(overlapped, timeout)
        if result.reaped:
            self._untrack_reaped()
        return result

    @property
    def pending_unreaped(self) -> int:
        """Derived, never incremented: started minus reaped, at this instant."""
        with self._lock:
            return self.overlapped_started - self.overlapped_reaped

    def _serve(self) -> None:
        try:
            self._serve_body()
        except Exception as exc:  # noqa: BLE001 - the worker never raises upward
            self.worker_error = f"{type(exc).__name__}: {exc}"
        finally:
            if not self.hooks.skip_worker_teardown:
                self._teardown_self()

    def _serve_body(self) -> None:
        assert self._pipe_handle is not None
        gate = self.hooks.block_worker_before_ready
        if gate is not None:
            gate.wait()
        connect = winpipe.connect_overlapped(self._pipe_handle)
        self._track(connect, "connect")
        self._set_state(STATE_READY)
        self._ready.set()

        outcome = self._wait_operation(connect, None)
        if outcome != "completed":
            self._reap_after(connect, outcome)
            self._set_state(STATE_DRAINING)
            return
        reap = self._reap(connect)
        if not reap.reaped or reap.aborted:
            self._set_state(STATE_DRAINING)
            return

        self.client_connected = True
        self._set_state(STATE_SERVING)

        buffer = b""
        frame_deadline: float | None = None
        while True:
            if self._shutdown_signalled():
                self._set_state(STATE_DRAINING)
                return

            newline = buffer.find(b"\n")
            if newline >= 0:
                raw, buffer = buffer[:newline], buffer[newline + 1:]
                frame_deadline = (
                    time.monotonic() + self.ipc_frame_deadline_seconds if buffer else None
                )
                if raw.endswith(b"\r"):
                    raw = raw[:-1]
                handled = self.handler.handle_frame(raw)
                if not self._write_frame(handled.response):
                    self._set_state(STATE_DRAINING)
                    return
                if handled.terminal:
                    if self.on_terminal is not None and handled.terminal_flag:
                        self.on_terminal(handled.terminal_flag)
                    self._set_state(STATE_DRAINING)
                    return
                continue

            if len(buffer) > MAX_REQUEST_FRAME_BYTES:
                self.handler.run_state.mark_terminal(TERMINAL_PROTOCOL)
                self.handler.diagnostics.refuse(
                    "unknown", ERR_PROTOCOL_ERROR, "unterminated_frame_over_cap"
                )
                self._write_frame(error_frame("0", ERR_PROTOCOL_ERROR, "frame_over_cap"))
                self._set_state(STATE_DRAINING)
                return

            try:
                read, _err = winpipe.read_overlapped(self._pipe_handle, 65536)
            except OSError:
                # The client's handle closed. The design's fail-closed direction:
                # the connection ends, and nothing is retried or repaired.
                self._set_state(STATE_DRAINING)
                return
            self._track(read, "read")
            deadline = frame_deadline if buffer else None
            outcome = self._wait_operation(read, deadline)
            if outcome != "completed":
                self._reap_after(read, outcome)
                self._set_state(STATE_DRAINING)
                return
            reap = self._reap(read)
            if not reap.reaped or reap.aborted or reap.broken_pipe or reap.transferred == 0:
                self._set_state(STATE_DRAINING)
                return
            chunk = winpipe.overlapped_buffer(read, reap.transferred)
            if not buffer and frame_deadline is None:
                frame_deadline = time.monotonic() + self.ipc_frame_deadline_seconds
            buffer += chunk

    def _reap_after(self, overlapped, outcome: str) -> None:
        """Cancel and reap an operation the wait abandoned. Always bounded."""
        if outcome == "deadline":
            self.handler.run_state.mark_terminal(TERMINAL_PROTOCOL)
            self.handler.diagnostics.refuse(
                "unknown", ERR_PROTOCOL_ERROR, "ipc_frame_deadline_expired"
            )
        try:
            overlapped.cancel()
        except OSError:
            pass
        self._reap(overlapped)

    def _write_frame(self, payload: bytes) -> bool:
        assert self._pipe_handle is not None
        deadline = time.monotonic() + self.ipc_frame_deadline_seconds
        remaining = payload
        while remaining:
            try:
                write, _err = winpipe.write_overlapped(self._pipe_handle, remaining)
            except OSError:
                return False
            self._track(write, "write")
            outcome = self._wait_operation(write, deadline)
            if outcome != "completed":
                self._reap_after(write, outcome)
                return False
            reap = self._reap(write)
            if not reap.reaped or reap.aborted or reap.broken_pipe:
                return False
            if reap.transferred <= 0:
                return False
            remaining = remaining[reap.transferred:]
        self.handler.diagnostics.frames_written += 1
        return True

    def _teardown_self(self) -> None:
        """b1..b5: the broker thread cancels, reaps and closes its OWN handles."""
        blocker = self.hooks.block_worker_before_teardown
        if blocker is not None:
            blocker.wait()

        self._set_state(STATE_DRAINING)
        with self._lock:
            pending = self._pending
        if pending is not None:
            try:
                pending.cancel()
            except OSError:
                pass
            reap = self._reap(pending)
            if not reap.reaped:
                # FU1 section 7.5: do NOT close the handle and do NOT release the
                # Overlapped object. A kernel write into a released buffer is
                # strictly worse than a leaked handle in a short-lived process.
                self._set_state(STATE_TEARDOWN_INCOMPLETE)
                self._closed_by_worker.set()
                return

        if self._pipe_handle is not None:
            winpipe.close_handle(self._pipe_handle)
            self._pipe_handle = None
        if self._shutdown_event is not None:
            winpipe.close_handle(self._shutdown_event)
            self._shutdown_event = None
        self.handles_closed = True
        self._set_state(STATE_CLOSED)
        self._closed_by_worker.set()

    # -- controller-side shutdown -----------------------------------------

    def _shutdown_no_worker_started(self) -> None:
        """5F3B-I2B-L1-D1 states B/C/D: an OS resource exists but no worker
        thread is running, so no worker will ever call ``_teardown_self``.

        This runs on the CONTROLLER thread (there is no worker to own it),
        closes only the handles BrokerServer itself created in this partial
        start, and never touches ``self._thread`` -- joining a thread whose
        ``.start()`` itself raised is unsafe (see ``shutdown``'s docstring).
        The caller is never handed a handle and never closes one itself.
        """
        self._partial_start_no_worker = True
        self.rung_reached = "N1"

        closed_cleanly = True
        if self._pipe_handle is not None:
            try:
                winpipe.close_handle(self._pipe_handle)
            except OSError:
                closed_cleanly = False
            else:
                self._pipe_handle = None
        if self._shutdown_event is not None:
            try:
                winpipe.close_handle(self._shutdown_event)
            except OSError:
                closed_cleanly = False
            else:
                self._shutdown_event = None

        if closed_cleanly:
            # True whether this call actually closed a handle just now, or
            # found nothing left to close because a prior call already did --
            # idempotent, never a double CloseHandle on the same value.
            self.handles_closed = True
            self._set_state(STATE_CLOSED)
        else:
            # Never claim CLOSED, and never hide the failure. The exact same
            # bounded vocabulary the worker-owned path uses for a failed
            # close (FU1 section 7.5).
            self._set_state(STATE_TEARDOWN_INCOMPLETE)
        self.rung_reached = "N2"

    def shutdown(self, trigger: str) -> dict[str, Any]:
        """The FU1 section 7.4 sequence, executed and RECORDED exactly as observed.

        5F3B-I2B-L1-D1: this now branches on the two partial-start facts
        recorded by ``start()``, not merely on ``self._thread is None``. That
        single check used to treat "nothing was ever created" (state A) and
        "a resource WAS created but no worker thread is running" (states
        B/C/D) identically -- an immediate no-op return -- which silently
        leaked the pipe and/or shutdown-event handle in B/C, and would have
        called ``Thread.join()`` on an unstarted thread in D (CPython raises
        ``RuntimeError: cannot join thread before it is started`` there).
        """
        started = time.monotonic()
        self.shutdown_trigger = trigger
        self.rung_reached = "B0"

        # FU-F backstop: idempotent, so this is a no-op if start() already
        # released it. It only does real work if start() was never called at
        # all (nothing else would ever release the descriptor in that case).
        self._security.release()

        if not self._pipe_resource_created:
            # A: start() was never called, or its first call
            # (create_first_instance_pipe) failed before returning. Nothing
            # was ever created, so there is nothing to close. Unchanged from
            # the pre-existing "shutdown before start" semantics.
            self.rung_reached = "B0"
            self.teardown_elapsed_seconds = 0.0
            return self.lifecycle_record()

        if not self._worker_thread_started:
            # B/C/D: an OS resource was created (the pipe, and possibly the
            # shutdown event too) but no worker thread is running to call
            # _teardown_self. BrokerServer's OWN shutdown path must close
            # only what it created here -- the caller never touches these
            # handles -- and must NEVER join self._thread, started or not.
            self._shutdown_no_worker_started()
            self.teardown_elapsed_seconds = round(time.monotonic() - started, 4)
            return self.lifecycle_record()

        # _worker_thread_started implies self._thread is not None and
        # Thread.start() returned without raising, so join() below is safe.
        if self._shutdown_event is not None:
            winpipe.set_event(self._shutdown_event)
        self.rung_reached = "B1"

        acknowledged = self._closed_by_worker.wait(timeout=self.shutdown_ack_grace_seconds)
        self.rung_reached = "B2"

        if not acknowledged:
            with self._lock:
                pending = self._pending
            if pending is not None:
                # The controller's ONE escalation lever. Safe cross-thread, and
                # idempotent on an already completed operation. The controller
                # still does NOT close any handle.
                try:
                    pending.cancel()
                    self.controller_cancel_escalation_used = True
                except OSError:
                    pass
            self.rung_reached = "B3"

        assert self._thread is not None  # guaranteed by _worker_thread_started
        self._thread.join(timeout=self.teardown_deadline_seconds)
        self.rung_reached = "B4"
        self.worker_termination_observed = not self._thread.is_alive()
        if self.worker_termination_observed and self.state == STATE_CLOSED:
            self.rung_reached = "B5"
        else:
            self._set_state(STATE_TEARDOWN_INCOMPLETE)
            self.rung_reached = "B5"

        self.teardown_elapsed_seconds = round(time.monotonic() - started, 4)
        return self.lifecycle_record()

    # -- evidence ---------------------------------------------------------

    def lifecycle_record(self) -> dict[str, Any]:
        """``broker_recorded_lifecycle``. Facts about AIDO's OWN thread and handles."""
        state = self.state
        closed = state == STATE_CLOSED
        record: dict[str, Any] = {
            "state_reached": state,
            "shutdown_trigger": self.shutdown_trigger,
            "rung_reached": self.rung_reached,
            "controller_cancel_escalation_used": self.controller_cancel_escalation_used,
            "overlapped_operations_started": self.overlapped_started,
            "overlapped_operations_reaped": self.overlapped_reaped,
            "pending_operations_unreaped": self.pending_unreaped,
            "handles_closed": self.handles_closed,
            "worker_termination_observed": self.worker_termination_observed,
            "teardown_elapsed_seconds": self.teardown_elapsed_seconds,
            "teardown_outcome": "closed_observed" if closed else "teardown_incomplete",
            "client_connected": self.client_connected,
            "worker_error": self.worker_error,
            "pipe_name_recorded": False,
            "deadlines": {
                "ipc_frame_deadline_seconds": self.ipc_frame_deadline_seconds,
                "broker_shutdown_ack_grace_seconds": self.shutdown_ack_grace_seconds,
                "broker_teardown_deadline_seconds": self.teardown_deadline_seconds,
                "note": (
                    "Broker deadlines are separate from the Pi runtime/semantic "
                    "deadlines. They authorize no additional model call, no retry, "
                    "no relaunch, no provider fallback, and no runtime fallback, "
                    "and they do not change token policy."
                ),
            },
        }
        if closed and self._partial_start_no_worker:
            # 5F3B-I2B-L1-D1 states B/C/D: no worker ever ran, so the worker-
            # thread claims below would be false. BrokerServer's own
            # shutdown path closed only what it created directly.
            record["claims_permitted"] = [
                "no broker worker thread ever started for this run",
                "every OS resource this partial start actually created (the "
                "pipe handle, and the shutdown-event handle if it was also "
                "created) was closed by BrokerServer's own shutdown path, "
                "directly, on the controller thread",
                "the pipe name no longer resolves for a new client",
                "AIDO performed no broker-mediated filesystem operation on the "
                "delegated root, because no worker ever served a request",
            ]
            record["claims_forbidden"] = [
                "a broker worker thread was observed to terminate -- none ever "
                "started, so there was nothing to join or observe",
                "nothing about Pi, Node, the model, the provider, or GPU occupancy "
                "-- AIDO's broker closing is not Pi stopping",
                "not 'sandboxed', 'isolated', 'OS-confined', or 'no host file "
                "outside the workspace was touched'",
            ]
        elif closed:
            record["claims_permitted"] = [
                "the broker thread was OBSERVED to terminate (join returned and "
                "is_alive() was false)",
                "every overlapped operation the broker started was reaped before "
                "its handle was closed; started and reaped counts are equal",
                "the pipe handle and the shutdown-event handle were closed, and "
                "the pipe name no longer resolves for a new client",
                "AIDO performed no further broker-mediated filesystem operation "
                "on the delegated root after teardown",
            ]
            record["claims_forbidden"] = [
                "nothing about Pi, Node, the model, the provider, or GPU occupancy "
                "-- AIDO's broker closing is not Pi stopping",
                "not 'sandboxed', 'isolated', 'OS-confined', or 'no host file "
                "outside the workspace was touched'",
                "not 'no process holds a handle to the pipe' -- the client's "
                "handle is the client's",
            ]
        elif self._partial_start_no_worker:
            record["residual_statement"] = (
                "No broker worker thread ever started for this run. "
                "BrokerServer's own shutdown path attempted to close the pipe "
                "handle and/or the shutdown-event handle it created directly, "
                "on the controller thread, and at least one CloseHandle call "
                "did not succeed. The unclosed handle may still exist and the "
                "pipe name may still resolve for a new client."
            )
            record["claims_forbidden"] = [
                "a broker worker thread was ever started, terminated, stopped, "
                "killed, cancelled or cleaned up",
                "every handle this partial start created was released, or the "
                "pipe name is retired",
                "the capability was revoked -- it was REQUESTED to be withdrawn",
                "clean_expected, or any clean classification resting on a "
                "teardown that did not complete",
            ]
        else:
            record["residual_statement"] = (
                "AIDO stopped waiting for its broker thread at its own deadline. "
                "AIDO did not observe the thread terminate. The thread may still "
                "hold the pipe handle and the per-run capability state, and a "
                "pending overlapped operation may still complete. The handle was "
                "deliberately NOT closed and the Overlapped object was "
                "deliberately NOT released, because completing a cancelled "
                "operation into a released buffer is worse than leaking a handle."
            )
            record["claims_forbidden"] = [
                "the broker was terminated, stopped, killed, cancelled or cleaned up",
                "handles were released, the pipe is closed, or the name is retired",
                "no further broker-mediated read or write can occur",
                "the capability was revoked -- it was REQUESTED to be withdrawn",
                "clean_expected, or any clean classification resting on a teardown "
                "that did not complete",
            ]
        record["filesystem_io_limitation"] = (
            "Overlapped cancellation bounds NAMED-PIPE I/O. It does not prove that "
            "a synchronous local filesystem call (stat, open, read, write, fstat) "
            "can be cancelled from the controller. If teardown occurs while the "
            "broker thread is inside a filesystem operation and the worker does "
            "not terminate within the broker deadline, the outcome is "
            "TEARDOWN_INCOMPLETE. No hard cancellation or guaranteed thread "
            "termination is claimed."
        )
        record["chain"] = (
            "AIDO wait ended != broker thread stopped != pending I/O completed "
            "!= handle released != capability provably withdrawn"
        )
        return record

    def security_shape(self) -> dict[str, Any]:
        """A recordable description of the pipe's creation shape. No name, no SID."""
        return {
            "transport": "windows_named_pipe",
            "per_run_random_name_bits": 128,
            "pipe_name_recorded": False,
            "first_pipe_instance": True,
            "overlapped": True,
            "reject_remote_clients": True,
            "max_instances": 1,
            "byte_mode": True,
            "framing": "strict LF-terminated JSONL",
            "single_client": True,
            "single_flight": True,
            **self._security.describe(),
        }

    # -- test-only -------------------------------------------------------

    def _test_only_complete_leaked_teardown(self) -> None:
        """Release a deliberately leaked handle AFTER a TEARDOWN_INCOMPLETE test.

        Offline-suite hygiene only, so a green run leaves no AR2-owned handle or
        thread behind. It is NOT a teardown rung, it is never called by the live
        harness, and it changes nothing that was already recorded.
        """
        with self._lock:
            pending = self._pending
        if pending is not None:
            try:
                pending.cancel()
            except OSError:
                pass
            winpipe.reap_overlapped(pending, BROKER_REAP_WAIT_MS)
            with self._lock:
                self._pending = None
        if self._pipe_handle is not None:
            winpipe.close_handle(self._pipe_handle)
            self._pipe_handle = None
        if self._shutdown_event is not None:
            winpipe.close_handle(self._shutdown_event)
            self._shutdown_event = None
