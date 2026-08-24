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
"""

from __future__ import annotations

import json
import subprocess  # noqa: S404 - pinned absolute argv, shell=False
import time
from dataclasses import dataclass, field
from typing import Any

from .protocol import (
    BoundedStreamReader,
    ReasoningDropStats,
    RecordStreamReader,
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


class PiRpcSupervisor:
    """One launch, bounded, with AIDO's own monotonic deadlines."""

    def __init__(
        self,
        *,
        argv: tuple[str, ...],
        cwd: str,
        environment: dict[str, str],
        bounds: RunBounds,
    ) -> None:
        self.argv = argv
        self.cwd = cwd
        self.environment = environment
        self.bounds = bounds
        self.reasoning_stats = ReasoningDropStats()
        self.activity = RuntimeActivity()
        self.process: subprocess.Popen[bytes] | None = None
        self._stdout: RecordStreamReader | None = None
        self._stderr: BoundedStreamReader | None = None
        self._consumed = 0
        self.commands_sent: list[str] = []
        self.stdin_write_error: str | None = None
        self.termination: dict[str, Any] = {}

    # -- lifecycle ---------------------------------------------------------

    def launch(self) -> None:
        try:
            self.process = subprocess.Popen(  # noqa: S603 - pinned argv, shell=False
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

        assert self.process.stdout is not None
        assert self.process.stderr is not None
        self._stdout = RecordStreamReader(
            self.process.stdout,
            max_bytes=self.bounds.max_stdout_bytes,
            max_records=self.bounds.max_events,
            stats=self.reasoning_stats,
        )
        self._stderr = BoundedStreamReader(
            self.process.stderr,
            max_bytes=self.bounds.max_stderr_bytes,
            name="ar2-pi-stderr",
        )
        self._stdout.start()
        self._stderr.start()

    def send_command(self, command: dict[str, Any]) -> None:
        """Write one JSONL command. stdin is binary and LF-terminated."""
        if self.process is None or self.process.stdin is None:
            raise PiSupervisorError("supervisor error: no live process stdin")
        payload = json.dumps(command, ensure_ascii=True).encode("utf-8") + b"\n"
        try:
            self.process.stdin.write(payload)
            self.process.stdin.flush()
        except OSError as exc:
            self.stdin_write_error = f"{type(exc).__name__}: {exc}"
            raise PiSupervisorError(f"supervisor error: stdin write failed: {exc}") from exc
        self.commands_sent.append(str(command.get("type")))

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
            if self.process is not None and self.process.poll() is not None:
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
        """
        record: dict[str, Any] = {
            "rung_reached": "none",
            "stdin_closed": False,
            "exit_status_observed": None,
            "direct_child_terminate_sent": False,
            "direct_child_kill_sent": False,
        }
        if self.process is None:
            return record

        if self.process.stdin is not None:
            try:
                self.process.stdin.close()
                record["stdin_closed"] = True
                record["rung_reached"] = "stdin_closed"
            except OSError as exc:  # pragma: no cover - platform dependent
                record["stdin_close_error"] = f"{type(exc).__name__}: {exc}"

        try:
            code = self.process.wait(timeout=self.bounds.shutdown_deadline_seconds)
            record["exit_status_observed"] = code
            record["rung_reached"] = "exited_after_stdin_close"
        except subprocess.TimeoutExpired:
            record["rung_reached"] = "shutdown_deadline_expired"
            self.process.terminate()
            record["direct_child_terminate_sent"] = True
            try:
                code = self.process.wait(
                    timeout=self.bounds.direct_child_reap_grace_seconds
                )
                record["exit_status_observed"] = code
                record["rung_reached"] = "exited_after_terminate"
            except subprocess.TimeoutExpired:
                self.process.kill()
                record["direct_child_kill_sent"] = True
                try:
                    code = self.process.wait(
                        timeout=self.bounds.direct_child_reap_grace_seconds
                    )
                    record["exit_status_observed"] = code
                    record["rung_reached"] = "exited_after_kill"
                except subprocess.TimeoutExpired:
                    record["rung_reached"] = "gave_up_waiting"

        self._drain()
        record["claim_scope"] = (
            "AIDO stopped waiting and signalled only the DIRECT child. This is "
            "not a claim that inference stopped, that the provider request was "
            "cancelled, that GPU work stopped, or that any descendant process "
            "was terminated."
        )
        self.termination = record
        return record

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
