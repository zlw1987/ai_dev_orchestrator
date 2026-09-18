"""Pi-specific RPC process supervision for AR2.

Deliberately Pi-specific. There is no generic runtime interface here and none
may be added (AR0 section 17.3, reinforced by AR0-FU1: B-fixed is Pi-seam
specific and would generalize badly).

Vocabulary discipline (AR0 section 13.2): the reviewer's RS1 terms
(``review_stalled``, ``RETRY_ELIGIBLE_OUTCOMES``, ``stall_source``) are NOT
reused. The runtime stage has its own outcome names.

Bounds discipline: process/time/output bounds are NOT token limits, and the two
must never be conflated. AIDO requests no model output-token ceiling anywhere.

Honesty discipline for termination::

    AIDO wait ended  !=  Pi stopped  !=  tool children stopped
                     !=  provider request cancelled
                     !=  backend inference stopped

CFG1-L16-FU2 (design ``PHASE_5F3B_HARNESS_CFG1_L16_FU2_RUNTIME_CAPABILITY_
OBSERVATION_DESIGN.md``, revision R2) adds, and adds only:

- **Single-use launch authority** (Sec. 5.6.1). ``launch()`` may acquire
  runtime-creation authority exactly once per supervisor INSTANCE; a repeated
  launch, a launch after a failed launch and a launch after retirement all
  refuse with one fixed text BEFORE any process, reader, thread or pipe exists.
- **Child-resource ownership** (Sec. 5.6.2). The one object returned by the one
  child-creation site is bound, by identity, into exactly one private,
  write-once role -- the runtime-child or the orphan-child -- together with the
  three pipe handles captured from that exact child. Every write, poll, wait,
  signal and close takes its target from that binding and verifies it first.
- **``process`` is a read-only observation** derived on each read from the
  runtime-child binding. Assignment and deletion refuse. It is NOT operational
  authority for this class; other AIDO components read it as an input to their
  own lifecycle and dispatch decisions, which is exactly why it is read-only.
- **An OPEN/RETIRED lifecycle** with retirement as ``shutdown()``'s first step,
  and one lifecycle serialization (distinct from the reader lock; always taken
  FIRST) ordering launch commit, launch install/orphan, the probe's
  eligibility->arm->write-commit, the write-state update, consumption and
  retirement. Neither lock is ever held across child creation, a pipe write, or
  a wait on Pi.
- **One parameterless, one-shot runtime capability probe**
  (:meth:`PiRpcSupervisor.probe_runtime_capabilities`), returning exactly one
  ``bool`` and three closed ``str`` literals and nothing else (Sec. 5.3).
"""

from __future__ import annotations

import json
import secrets
import subprocess  # noqa: S404 - pinned absolute argv, shell=False
import threading
import time
from dataclasses import dataclass, field
from typing import IO, Any

from .protocol import (
    BoundedStreamReader,
    ReasoningDropStats,
    RecordStreamReader,
)
from .runtime_probe import (
    PROBE_COMMAND_TYPE,
    SLOT_ARMED,
    SLOT_POISONED,
    SLOT_RESOLVED,
    SLOT_UNARMED,
    ProbeSlot,
)

# Runtime-stage outcomes. Disjoint from the reviewer's RS1 vocabulary.
RUNTIME_SETTLED = "runtime_settled"
RUNTIME_DEADLINE_EXPIRED = "runtime_deadline_expired"
RUNTIME_PROTOCOL_VIOLATION = "runtime_protocol_violation"
RUNTIME_LAUNCH_FAILED = "runtime_launch_failed"
RUNTIME_EXITED_EARLY = "runtime_exited_early"
RUNTIME_OUTPUT_CAP_EXCEEDED = "runtime_output_cap_exceeded"
RUNTIME_EVENT_CAP_EXCEEDED = "runtime_event_cap_exceeded"
RUNTIME_RESPONSE_RECEIVED = "runtime_response_received"
RUNTIME_READ_ERROR = "runtime_read_error"

# Windows: keep the child off the console.
_CREATE_NO_WINDOW = 0x08000000

# -- fixed refusal texts. Nothing is ever formatted into them. ---------------

LAUNCH_REFUSED = "supervisor error: launch refused: this supervisor's launch authority is spent or retired"
PROBE_REFUSED = "supervisor error: runtime capability probe refused"
PROBE_FAILED = "supervisor error: runtime capability probe failed"
CHILD_BINDING_UNVERIFIED = "supervisor error: child ownership binding failed verification"
CLONE_REFUSED = "supervisor error: a supervisor instance cannot be copied or pickled"
EXPECTATIONS_INVALID = (
    "supervisor error: runtime identity expectations must both be absent or both "
    "be non-empty exact str"
)

# -- supervisor state literals (Sec. 5.6.1). Per INSTANCE, never module state. -

_LAUNCH_UNUSED = "UNUSED"
_LAUNCH_COMMITTED = "COMMITTED"
_LAUNCH_INSTALLED = "INSTALLED"
_LAUNCH_FAILED = "FAILED"

_LIFECYCLE_OPEN = "OPEN"
_LIFECYCLE_RETIRED = "RETIRED"

_WRITE_NONE = "WRITE_NONE"
_WRITE_COMMITTED = "WRITE_COMMITTED"
_WRITE_DONE = "WRITE_DONE"
_WRITE_FAILED = "WRITE_FAILED"

_ROLE_RUNTIME = "runtime-child"
_ROLE_ORPHAN = "orphan-child"


@dataclass(frozen=True)
class RunBounds:
    """Four independent kinds of bound. NONE of them is a token limit."""

    startup_deadline_seconds: float = 60.0
    turn_deadline_seconds: float = 900.0
    shutdown_deadline_seconds: float = 20.0
    max_stdout_bytes: int = 32 * 1024 * 1024
    max_stderr_bytes: int = 1 * 1024 * 1024
    max_events: int = 200_000
    direct_child_reap_grace_seconds: float = 5.0

    def as_dict(self) -> dict[str, float | int]:
        return {
            "startup_deadline_seconds": self.startup_deadline_seconds,
            "turn_deadline_seconds": self.turn_deadline_seconds,
            "shutdown_deadline_seconds": self.shutdown_deadline_seconds,
            "max_stdout_bytes": self.max_stdout_bytes,
            "max_stderr_bytes": self.max_stderr_bytes,
            "max_events": self.max_events,
            "direct_child_reap_grace_seconds": self.direct_child_reap_grace_seconds,
        }


class PiSupervisorError(Exception):
    """The supervised runtime could not be launched or driven."""


@dataclass
class RuntimeActivity:
    """Everything AIDO OBSERVED ON THE WIRE. All of it is an untrusted claim.

    Every field here is runtime-reported. None of it is repository authority.
    """

    event_type_counts: dict[str, int] = field(default_factory=dict)
    tool_calls: dict[str, dict[str, Any]] = field(default_factory=dict)
    agent_end_count: int = 0
    agent_end_will_retry_count: int = 0
    settled: bool = False
    auto_retry_events: int = 0
    compaction_events: int = 0
    extension_errors: list[str] = field(default_factory=list)
    final_assistant_text: str = ""
    last_usage: dict[str, Any] | None = None
    responses: dict[str, dict[str, Any]] = field(default_factory=dict)
    unmatched_response_ids: list[str] = field(default_factory=list)

    def tool_call_summary(self) -> dict[str, Any]:
        by_name: dict[str, int] = {}
        errors: dict[str, int] = {}
        for call in self.tool_calls.values():
            name = str(call.get("toolName", "unknown"))
            by_name[name] = by_name.get(name, 0) + 1
            if call.get("isError"):
                errors[name] = errors.get(name, 0) + 1
        return {
            "distinct_tool_call_ids": len(self.tool_calls),
            "calls_by_tool_name": by_name,
            "error_results_by_tool_name": errors,
        }

    def usage_for_record(self) -> dict[str, Any]:
        """Report usage as UNKNOWN when the provider reported none. Never zero."""
        if not self.last_usage:
            return {"reported": False, "note": "provider reported no usage; unknown, not zero"}
        total = self.last_usage.get("totalTokens")
        if not total:
            return {
                "reported": False,
                "note": "provider-reported usage was absent or zero; recorded as unknown",
            }
        return {
            "reported": True,
            "input": self.last_usage.get("input"),
            "output": self.last_usage.get("output"),
            "totalTokens": total,
        }


def _text_from_message(message: Any) -> str:
    """Extract only plain text blocks from an ASSISTANT message.

    FU-D: only a message explicitly identified as ``role == "assistant"`` may
    contribute to ``final_assistant_text``. A ``message_end`` or ``turn_end``
    event can carry a user message, a tool message, a system message, a message
    with a missing role, or an unknown role, and prior to this check
    ``_text_from_message`` extracted text from ANY of them.

    That defect is exactly what AR2's R1-a run record demonstrates: its stored
    ``final_assistant_text`` field is the USER/TASK PROMPT, not anything the
    model said, while ``FINDINGS.md`` correctly describes the actual assistant
    response as empty (zero tool calls, zero usage, 0.382 s to settle). The
    historical record is NOT rewritten -- see ``FINDINGS.md`` FU-D note -- but
    every future run collects this field correctly.

    Reasoning was already dropped upstream, before this function ever sees the
    record.
    """
    if not isinstance(message, dict):
        return ""
    if message.get("role") != "assistant":
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = [
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    return "\n".join(part for part in parts if part)


@dataclass(frozen=True, eq=False, slots=True)
class _ChildBinding:
    """AIDO-private child ownership (Sec. 5.6.2). Created only at L3 (or unwinding).

    Holds the one object the one child-creation site returned, the three pipe
    handles captured from THAT object at bind time, the role, and the owning
    supervisor. Capturing the pipes is what makes a later assignment to the
    exposed child's ``.stdin``/``.stdout``/``.stderr`` inert. No API accepts a
    binding, a child or a pipe as input. ``eq=False``: identity is the only
    equality there is.
    """

    child: Any
    stdin: IO[bytes] | None
    stdout: IO[bytes] | None
    stderr: IO[bytes] | None
    role: str
    owner: Any


def _capture_child(child: Any, *, role: str, owner: Any) -> _ChildBinding:
    return _ChildBinding(
        child=child,
        stdin=child.stdin,
        stdout=child.stdout,
        stderr=child.stderr,
        role=role,
        owner=owner,
    )


def _write_frame(stream: IO[bytes], payload: bytes) -> None:
    """Write one LF-terminated frame and flush. The single stdin write routine."""
    stream.write(payload)
    stream.flush()


class PiRpcSupervisor:
    """One launch, bounded, with AIDO's own monotonic deadlines."""

    def __init__(
        self,
        *,
        argv: tuple[str, ...],
        cwd: str,
        environment: dict[str, str],
        bounds: RunBounds,
        expected_provider: str | None = None,
        expected_model: str | None = None,
    ) -> None:
        # Sec. 5.2: optional, exact, bound ONCE here. Both absent (every AR2,
        # AR2-O1 and qualification construction) makes the probe unavailable.
        # ``type(x) is str`` refuses str subclasses; there is no setter, no
        # public name, and no later path that rebinds them.
        if expected_provider is None and expected_model is None:
            pass
        elif not (
            type(expected_provider) is str
            and type(expected_model) is str
            and len(expected_provider) > 0
            and len(expected_model) > 0
        ):
            raise PiSupervisorError(EXPECTATIONS_INVALID)
        self._expected_provider = expected_provider
        self._expected_model = expected_model

        self.argv = argv
        self.cwd = cwd
        self.environment = environment
        self.bounds = bounds
        self.reasoning_stats = ReasoningDropStats()
        self.activity = RuntimeActivity()
        self._stdout: RecordStreamReader | None = None
        self._stderr: BoundedStreamReader | None = None
        self._consumed = 0
        self.commands_sent: list[str] = []
        self.stdin_write_error: str | None = None
        self.termination: dict[str, Any] = {}
        #: The launching call's record of an orphan child's teardown (Sec.
        #: 5.6.1). Diagnostic only; never consulted as authority.
        self.orphan_termination: dict[str, Any] = {}

        # Sec. 5.6: the lifecycle serialization. Distinct from the reader lock
        # and ALWAYS acquired first. The reader thread never takes it.
        self._lifecycle_cond = threading.Condition(threading.Lock())
        self._launch_authority = _LAUNCH_UNUSED
        self._lifecycle = _LIFECYCLE_OPEN
        self._write_state = _WRITE_NONE

        # Sec. 5.6.2: the two write-once ownership roles. Never public.
        self._runtime_child: _ChildBinding | None = None
        self._orphan_child: _ChildBinding | None = None

        # Sec. 5.3: the one probe slot, bound to the one stdout reader as the
        # LAST install step; ``_slot_reader`` records that binding.
        self._probe_slot = ProbeSlot()
        self._slot_reader: RecordStreamReader | None = None

    # -- no second lineage by cloning (Sec. 5.6.1 "not an id") --------------
    #
    # ``copy.copy``/``copy.deepcopy``/``pickle`` would otherwise build a SECOND
    # instance whose state carries this one's launch authority -- an unlaunched
    # copy would pass L1 again while SHARING this instance's probe slot and
    # lifecycle serialization. Launch state never moves between instances, so
    # every cloning path refuses, before anything is created.

    def __copy__(self) -> "PiRpcSupervisor":
        raise PiSupervisorError(CLONE_REFUSED)

    def __deepcopy__(self, memo: Any) -> "PiRpcSupervisor":
        raise PiSupervisorError(CLONE_REFUSED)

    def __reduce_ex__(self, protocol: Any) -> Any:
        raise PiSupervisorError(CLONE_REFUSED)

    def __reduce__(self) -> Any:
        raise PiSupervisorError(CLONE_REFUSED)

    # -- the compatibility observation (Sec. 5.6.2 contract) ----------------

    @property
    def process(self) -> Any:
        """READ-ONLY. The genuine runtime child, or ``None``. Never authority here.

        Derived on every read from the private runtime-child binding: ``None``
        until that binding is made (and forever in an orphan-only lineage), then
        exactly that genuine child for the rest of the instance's life,
        including after a partial install failure and after ``shutdown()``.
        There is no setter and no deleter, so assignment and deletion refuse,
        and as a data descriptor it cannot be shadowed by the instance
        namespace. No ``PiRpcSupervisor`` operation takes a target from it.
        """
        binding = self._runtime_child
        return None if binding is None else binding.child

    # -- ownership verification (Sec. 5.6.2 "verification at consumption") --

    def _verified_binding(self, role: str) -> _ChildBinding | None:
        """The binding a consumption of ``role`` may act on, or ``None`` if empty.

        Fails CLOSED -- raising one fixed text, acting on nothing -- unless the
        binding is a genuine ``_ChildBinding`` of exactly that role, owned by
        THIS instance, with the other role's binding empty. Only a private
        rebinding can make this raise; no supported API can.
        """
        if role == _ROLE_RUNTIME:
            binding, other = self._runtime_child, self._orphan_child
        else:
            binding, other = self._orphan_child, self._runtime_child
        if binding is None:
            if other is not None and (
                type(other) is not _ChildBinding or other.owner is not self
            ):
                raise PiSupervisorError(CHILD_BINDING_UNVERIFIED)
            return None
        if (
            type(binding) is not _ChildBinding
            or binding.role != role
            or binding.owner is not self
            or other is not None
        ):
            raise PiSupervisorError(CHILD_BINDING_UNVERIFIED)
        return binding

    # -- lifecycle ---------------------------------------------------------

    def launch(self) -> None:
        # L1 -- commit launch authority. The linearization point; single-use.
        with self._lifecycle_cond:
            if (
                self._lifecycle != _LIFECYCLE_OPEN
                or self._launch_authority != _LAUNCH_UNUSED
            ):
                raise PiSupervisorError(LAUNCH_REFUSED)
            self._launch_authority = _LAUNCH_COMMITTED

        child: Any = None
        orphan: _ChildBinding | None = None
        try:
            # L2 -- create the child, holding NO lock. The module's only
            # child-creation site; its return value lives in a local only.
            try:
                child = subprocess.Popen(  # noqa: S603 - pinned argv, shell=False
                    list(self.argv),
                    cwd=self.cwd,
                    env=self.environment,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=False,
                    creationflags=_CREATE_NO_WINDOW,
                )
            except OSError as exc:
                raise PiSupervisorError(f"{RUNTIME_LAUNCH_FAILED}: {exc}") from exc

            # L3 -- bind, then install or orphan, atomically.
            orphan = self._bind_install_or_orphan(child)
        except BaseException:
            # No stranded COMMITTED and no unattributed child, whatever raised.
            unwound = self._unwind_failed_launch(child)
            if unwound is not None:
                try:
                    self._teardown_orphan(unwound, child)
                except Exception:  # noqa: BLE001 - never masks the original failure
                    pass
            raise

        if orphan is not None:
            # Retirement was ordered after L1 and before L3: the child was
            # never installed and never ACTIVE. THIS call owns and tears it down.
            self._teardown_orphan(orphan, child)
            raise PiSupervisorError(LAUNCH_REFUSED)

    def _bind_install_or_orphan(self, child: Any) -> _ChildBinding | None:
        """L3. One lifecycle section. Returns the orphan binding, or ``None`` if installed."""
        with self._lifecycle_cond:
            if self._lifecycle != _LIFECYCLE_OPEN:
                self._orphan_child = _capture_child(child, role=_ROLE_ORPHAN, owner=self)
                self._launch_authority = _LAUNCH_FAILED
                return self._orphan_child

            self._runtime_child = _capture_child(child, role=_ROLE_RUNTIME, owner=self)
            try:
                binding = self._verified_binding(_ROLE_RUNTIME)
                assert binding is not None
                assert binding.stdout is not None
                assert binding.stderr is not None
                self._stdout = RecordStreamReader(
                    binding.stdout,
                    max_bytes=self.bounds.max_stdout_bytes,
                    max_records=self.bounds.max_events,
                    stats=self.reasoning_stats,
                )
                self._stderr = BoundedStreamReader(
                    binding.stderr,
                    max_bytes=self.bounds.max_stderr_bytes,
                    name="ar2-pi-stderr",
                )
                self._stdout.start()
                self._stderr.start()
                # LAST: only a completely installed lineage has a slot any
                # reader thread can reach. Reader lock nested inside L.
                self._stdout._bind_probe_slot(self._probe_slot)
                self._slot_reader = self._stdout
                self._launch_authority = _LAUNCH_INSTALLED
            except BaseException:
                # Never ACTIVE. The runtime-child binding STAYS, so ``process``
                # still shows the child and ``shutdown()`` owns its teardown.
                self._launch_authority = _LAUNCH_FAILED
                raise
            return None

    def _unwind_failed_launch(self, child: Any) -> _ChildBinding | None:
        """Any exception after L1: FAILED, and a created-but-unbound child becomes an orphan."""
        with self._lifecycle_cond:
            if self._launch_authority == _LAUNCH_COMMITTED:
                self._launch_authority = _LAUNCH_FAILED
            if child is None:
                return None
            if self._runtime_child is not None or self._orphan_child is not None:
                return None  # already bound; that role stands
            self._orphan_child = _capture_child(child, role=_ROLE_ORPHAN, owner=self)
            return self._orphan_child

    def _teardown_orphan(self, orphan: _ChildBinding, created: Any) -> None:
        """The launching call's own teardown of the one orphan child it created.

        Consumes ONLY the orphan-child binding, verified against the object the
        creation site returned to this very call. Same rungs, bounds and claim
        scope as ``shutdown()``; the outcome is recorded in
        ``orphan_termination`` and never claimed as more than it observed.
        """
        try:
            binding = self._verified_binding(_ROLE_ORPHAN)
            if binding is None or binding is not orphan or binding.child is not created:
                raise PiSupervisorError(CHILD_BINDING_UNVERIFIED)
        except PiSupervisorError:
            self.orphan_termination = {
                "rung_reached": "none",
                "verification_failed": True,
                "claim_scope": "AIDO issued no action to an unverified orphan binding.",
            }
            return
        record: dict[str, Any] = {
            "rung_reached": "none",
            "stdin_closed": False,
            "exit_status_observed": None,
            "direct_child_terminate_sent": False,
            "direct_child_kill_sent": False,
        }
        try:
            if binding.stdin is not None:
                try:
                    binding.stdin.close()
                    record["stdin_closed"] = True
                    record["rung_reached"] = "stdin_closed"
                except OSError:  # pragma: no cover - platform dependent
                    record["stdin_close_error"] = True
            self._direct_child_ladder(binding, record)
        except Exception:  # noqa: BLE001 - recorded truthfully, never as termination
            record["teardown_raised"] = True
        finally:
            for pipe in (binding.stdout, binding.stderr):
                if pipe is not None:
                    try:
                        pipe.close()
                    except OSError:  # pragma: no cover - platform dependent
                        pass
            record["claim_scope"] = (
                "AIDO signalled only the DIRECT orphan child it created and never "
                "installed. This is not a claim that any descendant process was "
                "terminated."
            )
            self.orphan_termination = record

    def _direct_child_ladder(self, binding: _ChildBinding, record: dict[str, Any]) -> None:
        """The shipped wait -> terminate -> wait -> kill -> wait rungs. Direct child only."""
        try:
            code = binding.child.wait(timeout=self.bounds.shutdown_deadline_seconds)
            record["exit_status_observed"] = code
            record["rung_reached"] = "exited_after_stdin_close"
        except subprocess.TimeoutExpired:
            record["rung_reached"] = "shutdown_deadline_expired"
            binding.child.terminate()
            record["direct_child_terminate_sent"] = True
            try:
                code = binding.child.wait(
                    timeout=self.bounds.direct_child_reap_grace_seconds
                )
                record["exit_status_observed"] = code
                record["rung_reached"] = "exited_after_terminate"
            except subprocess.TimeoutExpired:
                binding.child.kill()
                record["direct_child_kill_sent"] = True
                try:
                    code = binding.child.wait(
                        timeout=self.bounds.direct_child_reap_grace_seconds
                    )
                    record["exit_status_observed"] = code
                    record["rung_reached"] = "exited_after_kill"
                except subprocess.TimeoutExpired:
                    record["rung_reached"] = "gave_up_waiting"

    def send_command(self, command: dict[str, Any]) -> None:
        """Write one JSONL command. stdin is binary and LF-terminated."""
        binding = self._verified_binding(_ROLE_RUNTIME)
        if binding is None or binding.stdin is None:
            raise PiSupervisorError("supervisor error: no live process stdin")
        payload = json.dumps(command, ensure_ascii=True).encode("utf-8") + b"\n"
        try:
            _write_frame(binding.stdin, payload)
        except OSError as exc:
            self.stdin_write_error = f"{type(exc).__name__}: {exc}"
            raise PiSupervisorError(f"supervisor error: stdin write failed: {exc}") from exc
        self.commands_sent.append(str(command.get("type")))

    # -- the one bounded runtime capability probe (Sec. 5.3) ----------------

    def probe_runtime_capabilities(self) -> tuple[bool, str, str, str]:
        """ONE ``get_state``, correlated, reduced BEFORE publication. No parameters.

        Returns exactly ``(h2_matched, model_reasoning, compat_shape,
        thinking_level)``: one ``bool`` and three closed ``str`` literals. No
        id, mapping, record, ``data``, model subtree or raw value is returned or
        retained. One use per supervisor lifetime; arm, write, wait and consume
        all happen inside this one call, so no redeemable authority ever exists.

        The facts remain RUNTIME CLAIMS (Sec. 5.7). Every refusal or failure
        raises one of two fixed texts and never formats anything into them.
        """
        slot = self._probe_slot
        returned = False
        committed = False
        try:
            # Steps 1-3: eligibility, mint, arm and write-commit -- ONE
            # lifecycle section, so retirement is totally ordered against it.
            with self._lifecycle_cond:
                if (
                    self._launch_authority != _LAUNCH_INSTALLED
                    or self._lifecycle != _LIFECYCLE_OPEN
                    or self._expected_provider is None
                    or self._expected_model is None
                    or self._write_state != _WRITE_NONE
                ):
                    raise PiSupervisorError(PROBE_REFUSED)
                reader = self._slot_reader
                binding = self._verified_binding(_ROLE_RUNTIME)
                if reader is None or binding is None or binding.stdin is None:
                    raise PiSupervisorError(PROBE_REFUSED)
                probe_id = secrets.token_hex(16)
                if probe_id in self.activity.responses:
                    raise PiSupervisorError(PROBE_REFUSED)
                with reader._condition:
                    if slot.state != SLOT_UNARMED:
                        raise PiSupervisorError(PROBE_REFUSED)
                    slot.arm(probe_id, self._expected_provider, self._expected_model)
                self._write_state = _WRITE_COMMITTED
                committed = True
                target = binding.stdin

            # Step 4: the write, holding NEITHER lock.
            payload = (
                json.dumps(
                    {"id": probe_id, "type": PROBE_COMMAND_TYPE}, ensure_ascii=True
                ).encode("utf-8")
                + b"\n"
            )
            try:
                _write_frame(target, payload)
            except BaseException as exc:
                self._settle_write(_WRITE_FAILED)
                if not isinstance(exc, Exception):
                    raise
                raise PiSupervisorError(PROBE_FAILED) from None
            self._settle_write(_WRITE_DONE)
            self.commands_sent.append(PROBE_COMMAND_TYPE)

            # Step 5: the existing monotonic wait, holding NEITHER lock.
            deadline = time.monotonic() + self.bounds.startup_deadline_seconds
            self._wait(deadline, lambda: self._probe_wait_over(reader))

            # Step 6: consume -- ONE lifecycle section, reader lock nested.
            with self._lifecycle_cond:
                with reader._condition:
                    if self._lifecycle != _LIFECYCLE_OPEN:
                        slot.retire()
                        raise PiSupervisorError(PROBE_FAILED)
                    if slot.state not in (SLOT_ARMED, SLOT_RESOLVED, SLOT_POISONED):
                        raise PiSupervisorError(PROBE_FAILED)
                    facts = slot.consume()
            if facts is None:
                raise PiSupervisorError(PROBE_FAILED)
            returned = True
            return facts
        finally:
            # Step 7: every non-return exit leaves the slot RETIRED (unless
            # CONSUMED) and the write state out of WRITE_COMMITTED.
            if not returned:
                self._finalize_failed_probe(committed)

    def _settle_write(self, outcome: str) -> None:
        """Step 4's write-state update. On failure the slot is RETIRED too."""
        with self._lifecycle_cond:
            if self._write_state == _WRITE_COMMITTED:
                self._write_state = outcome
            if outcome == _WRITE_FAILED:
                self._retire_slot_locked()
            self._lifecycle_cond.notify_all()

    def _finalize_failed_probe(self, committed: bool) -> None:
        with self._lifecycle_cond:
            if committed and self._write_state == _WRITE_COMMITTED:
                self._write_state = _WRITE_FAILED
            if committed:
                self._retire_slot_locked()
            self._lifecycle_cond.notify_all()

    def _retire_slot_locked(self) -> None:
        """Slot -> RETIRED unless CONSUMED. Caller holds the lifecycle serialization."""
        reader = self._slot_reader
        if reader is None:
            self._probe_slot.retire()
            return
        with reader._condition:
            self._probe_slot.retire()

    def _probe_wait_over(self, reader: RecordStreamReader) -> bool:
        if self._lifecycle != _LIFECYCLE_OPEN:
            return True
        with reader._condition:
            return self._probe_slot.state != SLOT_ARMED

    # -- ingestion ---------------------------------------------------------

    def _absorb(self, record: dict[str, Any]) -> None:
        kind = record.get("type")
        if not isinstance(kind, str):
            return
        self.activity.event_type_counts[kind] = (
            self.activity.event_type_counts.get(kind, 0) + 1
        )

        if kind == "response":
            identifier = record.get("id")
            if isinstance(identifier, str):
                self.activity.responses[identifier] = record
            else:
                self.activity.unmatched_response_ids.append("<no-id>")
            return

        if kind == "agent_end":
            self.activity.agent_end_count += 1
            if record.get("willRetry"):
                self.activity.agent_end_will_retry_count += 1
            return

        if kind == "agent_settled":
            self.activity.settled = True
            return

        if kind in ("auto_retry_start", "auto_retry_end"):
            self.activity.auto_retry_events += 1
            return

        if kind in ("compaction_start", "compaction_end"):
            self.activity.compaction_events += 1
            return

        if kind == "extension_error":
            message = record.get("error") or record.get("message") or "extension_error"
            self.activity.extension_errors.append(str(message)[:500])
            return

        if kind == "tool_execution_start":
            call_id = str(record.get("toolCallId", ""))
            self.activity.tool_calls.setdefault(call_id, {})["toolName"] = record.get(
                "toolName"
            )
            return

        if kind == "tool_execution_end":
            call_id = str(record.get("toolCallId", ""))
            entry = self.activity.tool_calls.setdefault(call_id, {})
            entry["toolName"] = record.get("toolName", entry.get("toolName"))
            entry["isError"] = bool(record.get("isError"))
            return

        if kind == "message_update":
            usage = record.get("usage")
            if isinstance(usage, dict):
                self.activity.last_usage = usage
            return

        if kind in ("message_end", "turn_end"):
            text = _text_from_message(record.get("message"))
            if text:
                self.activity.final_assistant_text = text
            message = record.get("message")
            if isinstance(message, dict) and isinstance(message.get("usage"), dict):
                self.activity.last_usage = message["usage"]
            return

    def _drain(self) -> None:
        assert self._stdout is not None
        new = self._stdout.records_since(self._consumed)
        for record in new:
            self._absorb(record)
        self._consumed += len(new)

    def _terminal_stream_outcome(self) -> str | None:
        assert self._stdout is not None
        if self._stdout.protocol_violation:
            return RUNTIME_PROTOCOL_VIOLATION
        if self._stdout.byte_cap_exceeded:
            return RUNTIME_OUTPUT_CAP_EXCEEDED
        if self._stdout.record_cap_exceeded:
            return RUNTIME_EVENT_CAP_EXCEEDED
        if self._stdout.read_error:
            return RUNTIME_READ_ERROR
        return None

    def _wait(self, deadline: float, satisfied) -> str:
        """Consume records until ``satisfied()``, a terminal condition, or the deadline."""
        assert self._stdout is not None
        while True:
            self._drain()
            terminal = self._terminal_stream_outcome()
            if terminal is not None:
                return terminal
            if satisfied():
                return RUNTIME_RESPONSE_RECEIVED
            binding = self._verified_binding(_ROLE_RUNTIME)
            if binding is not None and binding.child.poll() is not None:
                # Give the reader one last chance to publish buffered records.
                self._stdout.finished.wait(timeout=1.0)
                self._drain()
                if satisfied():
                    return RUNTIME_RESPONSE_RECEIVED
                terminal = self._terminal_stream_outcome()
                return terminal if terminal is not None else RUNTIME_EXITED_EARLY
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return RUNTIME_DEADLINE_EXPIRED
            self._stdout.wait_for_more(self._consumed, min(remaining, 0.25))

    # -- public waits ------------------------------------------------------

    def await_response(self, command_id: str, *, timeout_seconds: float) -> tuple[str, dict[str, Any] | None]:
        """Wait for the response echoing ``command_id``. Correlation is by RPC id."""
        deadline = time.monotonic() + timeout_seconds
        outcome = self._wait(
            deadline, lambda: command_id in self.activity.responses
        )
        return outcome, self.activity.responses.get(command_id)

    def await_settled(self, *, timeout_seconds: float) -> str:
        """Wait for ``agent_settled``.

        ``agent_end`` is explicitly NOT the completion signal, and an
        ``agent_end`` carrying ``willRetry`` means the run is still going.
        """
        deadline = time.monotonic() + timeout_seconds
        outcome = self._wait(deadline, lambda: self.activity.settled)
        if outcome == RUNTIME_RESPONSE_RECEIVED:
            return RUNTIME_SETTLED
        return outcome

    # -- termination -------------------------------------------------------

    def _retire(self) -> _ChildBinding | None:
        """Retirement: ``shutdown()``'s FIRST action. One lifecycle section.

        Lifecycle -> RETIRED (permanently, in any launch state -- a
        never-launched supervisor becomes unlaunchable), the slot -> RETIRED
        unless CONSUMED, and the runtime-child binding is read HERE, in the same
        total order as L3. Changes no binding. Idempotent and monotonic.
        """
        with self._lifecycle_cond:
            self._lifecycle = _LIFECYCLE_RETIRED
            self._retire_slot_locked()
            self._lifecycle_cond.notify_all()
            return self._verified_binding(_ROLE_RUNTIME)

    def _probe_write_settled(self, timeout: float) -> bool:
        """Wait (bounded) until no committed probe write is in flight."""
        with self._lifecycle_cond:
            return self._lifecycle_cond.wait_for(
                lambda: self._write_state != _WRITE_COMMITTED, timeout=timeout
            )

    def shutdown(self) -> dict[str, Any]:
        """The termination ladder, recorded exactly as observed.

        Rung 1 is closing Pi's stdin, which is the only documented in-protocol
        shutdown trigger and the only one that runs Pi's own cleanup. Escalation
        happens only after that wait expires.

        What may be claimed: AIDO stopped waiting; AIDO closed stdin; AIDO sent
        terminate/kill to the DIRECT child; AIDO observed (or did not observe)
        that child's exit status. What may NEVER be claimed: that inference
        stopped, that GPU work stopped, that the provider request was cancelled,
        that all descendants died, or that Pi's cleanup definitely killed
        everything.

        CFG1-L16-FU2: retirement is the first action. Every rung targets the
        runtime-child binding and its CAPTURED stdin, never ``process``. stdin
        is never closed while a committed probe write is in flight; if that
        write is still in flight at ``shutdown_deadline_seconds`` the ladder
        proceeds straight to the direct-child terminate/kill rungs and stdin is
        left unclosed unless the write settles, which is recorded truthfully.
        """
        binding = self._retire()
        record: dict[str, Any] = {
            "rung_reached": "none",
            "stdin_closed": False,
            "exit_status_observed": None,
            "direct_child_terminate_sent": False,
            "direct_child_kill_sent": False,
        }
        if binding is None:
            return record

        if self._probe_write_settled(self.bounds.shutdown_deadline_seconds):
            if binding.stdin is not None:
                try:
                    binding.stdin.close()
                    record["stdin_closed"] = True
                    record["rung_reached"] = "stdin_closed"
                except OSError as exc:  # pragma: no cover - platform dependent
                    record["stdin_close_error"] = f"{type(exc).__name__}: {exc}"
            self._direct_child_ladder(binding, record)
        else:
            self._in_flight_write_ladder(binding, record)

        self._drain()
        record["claim_scope"] = (
            "AIDO stopped waiting and signalled only the DIRECT child. This is "
            "not a claim that inference stopped, that the provider request was "
            "cancelled, that GPU work stopped, or that any descendant process "
            "was terminated."
        )
        self.termination = record
        return record

    def _in_flight_write_ladder(self, binding: _ChildBinding, record: dict[str, Any]) -> None:
        """A committed probe write is still in flight at the shutdown deadline.

        stdin is NOT closed concurrently with it. The existing direct-child
        rungs run (they never touch stdin), and after each one the write state
        is re-checked without any added wait; stdin is closed only once the
        write has left ``WRITE_COMMITTED``.
        """
        record["rung_reached"] = "shutdown_deadline_expired"
        record["stdin_close_deferred_for_in_flight_probe_write"] = True
        binding.child.terminate()
        record["direct_child_terminate_sent"] = True
        try:
            code = binding.child.wait(timeout=self.bounds.direct_child_reap_grace_seconds)
            record["exit_status_observed"] = code
            record["rung_reached"] = "exited_after_terminate"
        except subprocess.TimeoutExpired:
            self._close_stdin_if_write_settled(binding, record)
            binding.child.kill()
            record["direct_child_kill_sent"] = True
            try:
                code = binding.child.wait(
                    timeout=self.bounds.direct_child_reap_grace_seconds
                )
                record["exit_status_observed"] = code
                record["rung_reached"] = "exited_after_kill"
            except subprocess.TimeoutExpired:
                record["rung_reached"] = "gave_up_waiting"
        self._close_stdin_if_write_settled(binding, record)

    def _close_stdin_if_write_settled(self, binding: _ChildBinding, record: dict[str, Any]) -> None:
        if record["stdin_closed"] or binding.stdin is None:
            return
        with self._lifecycle_cond:
            if self._write_state == _WRITE_COMMITTED:
                return
        try:
            binding.stdin.close()
            record["stdin_closed"] = True
        except OSError as exc:  # pragma: no cover - platform dependent
            record["stdin_close_error"] = f"{type(exc).__name__}: {exc}"

    # -- evidence ----------------------------------------------------------

    def stderr_snapshot(self) -> dict[str, Any]:
        if self._stderr is None:
            return {"captured": False}
        data, state = self._stderr.snapshot()
        text = data.decode("utf-8", "replace")
        return {
            "captured": True,
            "bytes_seen": state.bytes_seen,
            "bytes_retained": state.bytes_retained,
            "cap_exceeded": state.cap_exceeded,
            "eof": state.eof,
            "read_error": state.error,
            "text_tail": text[-4000:],
        }

    def stdout_state(self) -> dict[str, Any]:
        assert self._stdout is not None
        return {
            "bytes_seen": self._stdout.bytes_seen,
            "records_ingested": self._stdout.record_count(),
            "byte_cap_exceeded": self._stdout.byte_cap_exceeded,
            "event_cap_exceeded": self._stdout.record_cap_exceeded,
            "protocol_violation": self._stdout.protocol_violation,
            "read_error": self._stdout.read_error,
            "eof": self._stdout.eof,
        }

    def sanitized_events(self) -> list[dict[str, Any]]:
        assert self._stdout is not None
        return self._stdout.all_records()
