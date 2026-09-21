"""Test-only support for the CFG1-L16-FU2 probe, lifecycle and ownership rows.

Everything here is SYNTHETIC and LOCAL:

- the "Pi" is a Python script written under ``tmp_path`` and launched with a
  pinned absolute argv (``sys.executable`` + that script), never the real Pi;
- it reads JSONL commands from its stdin, records EVERY byte it receives in a
  capture file, and answers with scripted JSONL frames on stdout;
- no network, no socket, no model, no credential, no endpoint.

The instrumentation classes (owner-tracking locks, counting readers) are
test-only and never become production parameters.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path
from typing import Any

from ar2.protocol import REASONING_KEYS, contains_reasoning
from ar2.supervisor import PiRpcSupervisor, RunBounds

EXPECTED_PROVIDER = "synthetic-provider"
EXPECTED_MODEL = "qwen-synthetic-1"
SYNTHETIC_BASE_URL = "http://fu2-peer.invalid/v1"
SYNTHETIC_SESSION_FILE = "C:/fu2-synthetic/session-file.jsonl"
ID_PLACEHOLDER = "__ID__"

FAST_BOUNDS = RunBounds(
    startup_deadline_seconds=4.0,
    turn_deadline_seconds=5.0,
    shutdown_deadline_seconds=3.0,
    direct_child_reap_grace_seconds=1.5,
)

#: The BASE interpreter, never a venv redirector. On Windows a venv's
#: ``python.exe`` is a launcher process that holds the child's pipe handles too,
#: so a peer that closed its stdin would not actually break the pipe, and
#: terminating the launcher would not terminate the peer itself.
PEER_INTERPRETER = getattr(sys, "_base_executable", None) or sys.executable

PEER_SOURCE = r'''
"""Synthetic stand-in for a Pi RPC process. Test-only. Never the real Pi."""
import json
import os
import sys
import threading
import time

cfg = json.load(open(sys.argv[1], encoding="utf-8"))
out = sys.stdout.buffer
out_lock = threading.Lock()
capture_path = cfg.get("capture_path")
max_lifetime = float(cfg.get("max_lifetime", 60.0))


def _watchdog():
    time.sleep(max_lifetime)
    os._exit(97)


threading.Thread(target=_watchdog, daemon=True).start()


def capture(data):
    if capture_path:
        with open(capture_path, "ab") as handle:
            handle.write(data)


def emit(lines, command_id=None):
    for line in lines:
        if isinstance(line, dict):
            delay = float(line.get("sleep", 0))
            time.sleep(delay)
            continue
        text = line if command_id is None else line.replace("__ID__", command_id)
        with out_lock:
            out.write(text.encode("utf-8") + b"\n")
            out.flush()


def flood(spec):
    for index in range(int(spec.get("count", 0))):
        emit([json.dumps({"type": "flood_event", "index": index})])
        time.sleep(float(spec.get("interval", 0.001)))


emit(cfg.get("startup_frames", []))
if cfg.get("flood"):
    threading.Thread(target=flood, args=(cfg["flood"],), daemon=True).start()

mode = cfg.get("mode", "respond")
if mode == "close_stdin":
    os.close(0)
    time.sleep(max_lifetime)
    sys.exit(0)
if mode == "no_read":
    time.sleep(max_lifetime)
    sys.exit(0)

responses = cfg.get("responses", {})
while True:
    line = sys.stdin.buffer.readline()
    if not line:
        capture(b"<EOF>")
        if mode == "ignore_eof":
            time.sleep(max_lifetime)
        time.sleep(float(cfg.get("linger_after_eof", 0)))
        sys.exit(int(cfg.get("exit_code", 0)))
    capture(line)
    try:
        command = json.loads(line.decode("utf-8").rstrip("\r\n"))
    except Exception:
        continue
    kind = command.get("type")
    if kind == "exit_now":
        sys.exit(0)
    command_id = command.get("id")
    frames = responses.get(kind)
    if frames is None:
        continue
    if cfg.get("respond_async"):
        threading.Thread(
            target=emit, args=(frames, command_id if isinstance(command_id, str) else ""),
            daemon=True,
        ).start()
    else:
        emit(frames, command_id if isinstance(command_id, str) else "")
'''


def frame(obj: Any) -> str:
    return json.dumps(obj)


def state_data(
    *,
    reasoning: Any = True,
    include_reasoning: bool = True,
    provider: str = EXPECTED_PROVIDER,
    model_id: str = EXPECTED_MODEL,
    compat: Any = None,
    include_compat: bool = False,
    thinking: Any = "medium",
    include_thinking: bool = True,
) -> dict:
    """A ``get_state`` ``data`` object shaped as installed Pi 0.85.1 emits it."""
    model: dict[str, Any] = {
        "id": model_id,
        "name": model_id,
        "api": "openai-completions",
        "provider": provider,
        "baseUrl": SYNTHETIC_BASE_URL,
        "input": ["text"],
        "contextWindow": 128000,
        "maxTokens": 16384,
    }
    if include_reasoning:
        model["reasoning"] = reasoning
    if include_compat:
        model["compat"] = compat
    data: dict[str, Any] = {
        "model": model,
        "isStreaming": False,
        "sessionFile": SYNTHETIC_SESSION_FILE,
        "sessionId": "synthetic-session-id",
        "messageCount": 0,
    }
    if include_thinking:
        data["thinkingLevel"] = thinking
    return data


def get_state_frame(
    data: Any = None,
    *,
    success: Any = True,
    include_success: bool = True,
    command: Any = "get_state",
    include_command: bool = True,
    response_id: Any = ID_PLACEHOLDER,
    include_data: bool = True,
) -> str:
    """One ``get_state`` response frame; ``__ID__`` is replaced by the peer."""
    payload: dict[str, Any] = {"type": "response"}
    if response_id is not None:
        payload["id"] = response_id
    if include_command:
        payload["command"] = command
    if include_success:
        payload["success"] = success
    if include_data:
        payload["data"] = state_data() if data is None else data
    return frame(payload)


class Peer:
    """One synthetic peer's argv plus its capture files."""

    def __init__(self, tmp_path: Path, name: str, config: dict) -> None:
        script = tmp_path / "fu2_peer.py"
        if not script.exists():
            script.write_text(PEER_SOURCE, encoding="utf-8")
        self.capture_path = tmp_path / f"{name}_stdin_capture.bin"
        config = dict(config)
        config.setdefault("capture_path", str(self.capture_path))
        config_path = tmp_path / f"{name}_config.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        self.argv = (PEER_INTERPRETER, str(script), str(config_path))

    def captured(self) -> bytes:
        try:
            return self.capture_path.read_bytes()
        except FileNotFoundError:
            return b""

    def captured_commands(self) -> list[dict]:
        commands = []
        for line in self.captured().replace(b"<EOF>", b"").splitlines():
            if line.strip():
                commands.append(json.loads(line.decode("utf-8")))
        return commands

    def saw_eof(self) -> bool:
        return self.captured().endswith(b"<EOF>")

    def wait_for_eof(self, timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.saw_eof():
                return True
            time.sleep(0.02)
        return self.saw_eof()


def make_peer(tmp_path: Path, name: str = "peer", **config: Any) -> Peer:
    return Peer(tmp_path, name, config)


def respond_config(get_state_frames: list, **extra: Any) -> dict:
    responses = dict(extra.pop("responses", {}))
    responses["get_state"] = get_state_frames
    return {"responses": responses, **extra}


def make_supervisor(
    peer: Peer,
    *,
    expectations: bool = True,
    bounds: RunBounds = FAST_BOUNDS,
    provider: str = EXPECTED_PROVIDER,
    model: str = EXPECTED_MODEL,
) -> PiRpcSupervisor:
    kwargs: dict[str, Any] = {}
    if expectations:
        kwargs = {"expected_provider": provider, "expected_model": model}
    return PiRpcSupervisor(
        argv=peer.argv,
        cwd=str(Path(peer.argv[1]).parent),
        environment=_minimal_environment(),
        bounds=bounds,
        **kwargs,
    )


def _minimal_environment() -> dict[str, str]:
    import os

    environment = {}
    for name in ("SystemRoot", "SystemDrive", "TEMP", "TMP", "PATH"):
        if name in os.environ:
            environment[name] = os.environ[name]
    return environment


def join_readers(supervisor: PiRpcSupervisor, timeout: float = 10.0) -> None:
    """Test-side join of the two reader threads, so no ``ar2-`` thread leaks."""
    for reader in (supervisor._stdout, supervisor._stderr):
        if reader is not None and reader._thread.is_alive():
            reader._thread.join(timeout)


def close(supervisor: PiRpcSupervisor) -> dict:
    """Shut down (tolerating F-7) and join the reader threads."""
    record: dict = {}
    try:
        record = supervisor.shutdown()
    except AssertionError:
        # F-7 (pre-existing, recorded, not closed): ``_drain`` asserts after a
        # partial-launch ladder. The ladder itself already ran.
        pass
    join_readers(supervisor)
    return record


def reap_raw_child(child: Any) -> None:
    """Test-side cleanup of a child the supervisor deliberately left alone."""
    if child is None:
        return
    try:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=10)
    except Exception:  # noqa: BLE001 - best effort test cleanup
        pass
    for pipe in (child.stdin, child.stdout, child.stderr):
        try:
            if pipe is not None:
                pipe.close()
        except Exception:  # noqa: BLE001
            pass


def count_reasoning_keys(value: Any) -> int:
    if isinstance(value, dict):
        total = 0
        for key, item in value.items():
            if key in REASONING_KEYS:
                total += 1
                continue
            total += count_reasoning_keys(item)
        return total
    if isinstance(value, list):
        return sum(count_reasoning_keys(item) for item in value)
    return 0


def leak_check(supervisor: PiRpcSupervisor, facts: Any, sentinels: list[str]) -> None:
    """Design Sec. 11 leak check over every AIDO-held surface."""
    slot = supervisor._probe_slot
    surfaces = {
        "events": supervisor.sanitized_events() if supervisor._stdout is not None else [],
        "responses": supervisor.activity.responses,
        "facts": list(facts) if isinstance(facts, tuple) else facts,
        "slot": {name: getattr(slot, name) for name in type(slot).__slots__},
        "read_error": supervisor._stdout.read_error if supervisor._stdout else None,
        "protocol_violation": (
            supervisor._stdout.protocol_violation if supervisor._stdout else None
        ),
        "termination": supervisor.termination,
        "orphan_termination": supervisor.orphan_termination,
        "stdin_write_error": supervisor.stdin_write_error,
    }
    serialized = json.dumps(surfaces, default=repr)
    for sentinel in sentinels:
        assert sentinel not in serialized, sentinel
    for name in ("events", "responses", "facts", "slot"):
        assert contains_reasoning(surfaces[name]) is False, name


class OwnerTrackingLock:
    """A non-reentrant lock that records every acquisition (tests only).

    ``log`` entries are ``(sequence, lock_name, thread_name, other_locks_held)``.
    """

    _sequence = 0
    _sequence_lock = threading.Lock()
    _held: dict[int, list[str]] = {}

    def __init__(self, name: str, log: list) -> None:
        self._lock = threading.Lock()
        self._name = name
        self._log = log
        self.owner: int | None = None

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        acquired = self._lock.acquire(blocking, timeout)
        if acquired:
            ident = threading.get_ident()
            self.owner = ident
            with OwnerTrackingLock._sequence_lock:
                OwnerTrackingLock._sequence += 1
                sequence = OwnerTrackingLock._sequence
                held = OwnerTrackingLock._held.setdefault(ident, [])
                self._log.append(
                    (sequence, self._name, threading.current_thread().name, tuple(held))
                )
                held.append(self._name)
        return acquired

    def release(self) -> None:
        ident = threading.get_ident()
        with OwnerTrackingLock._sequence_lock:
            held = OwnerTrackingLock._held.get(ident, [])
            if self._name in held:
                held.remove(self._name)
        self.owner = None
        self._lock.release()

    def locked(self) -> bool:
        return self._lock.locked()

    def _is_owned(self) -> bool:
        return self.owner == threading.get_ident()

    def held_by_current_thread(self) -> bool:
        return self.owner == threading.get_ident()

    __enter__ = acquire

    def __exit__(self, *exc: Any) -> None:
        self.release()


def instrument_lifecycle_lock(supervisor: PiRpcSupervisor, log: list) -> OwnerTrackingLock:
    lock = OwnerTrackingLock("lifecycle", log)
    supervisor._lifecycle_cond = threading.Condition(lock)
    return lock


def instrumented_reader_class(log: list, registry: list | None = None):
    """A ``RecordStreamReader`` subclass whose lock records acquisitions."""
    from ar2.protocol import RecordStreamReader

    class _InstrumentedReader(RecordStreamReader):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._lock = OwnerTrackingLock("reader", log)
            self._condition = threading.Condition(self._lock)
            if registry is not None:
                registry.append(self)

    return _InstrumentedReader


class Recorder:
    """A process-like substitute that records EVERY access (C-rows)."""

    def __init__(self, log: list, name: str = "substitute") -> None:
        object.__setattr__(self, "_log", log)
        object.__setattr__(self, "_name", name)

    def __getattr__(self, attr: str) -> Any:
        self._log.append((self._name, attr))
        if attr in ("stdin", "stdout", "stderr"):
            return Recorder(self._log, f"{self._name}.{attr}")
        return lambda *args, **kwargs: self._log.append((self._name, attr, "called"))

    def __setattr__(self, attr: str, value: Any) -> None:
        self._log.append((self._name, "set", attr))


def run_in_thread(target, *args: Any, name: str = "fu2-test-worker") -> tuple[threading.Thread, dict]:
    """Run ``target`` in a non-``ar2-`` thread; result or exception lands in the dict."""
    box: dict = {}

    def _runner() -> None:
        try:
            box["result"] = target(*args)
        except BaseException as exc:  # noqa: BLE001 - reported to the test
            box["error"] = exc

    thread = threading.Thread(target=_runner, name=name, daemon=True)
    thread.start()
    return thread, box
