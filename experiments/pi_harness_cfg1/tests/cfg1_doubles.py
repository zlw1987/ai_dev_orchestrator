"""Synthetic doubles for every live CFG1 resource. Test-only scaffolding.

No Pi process, no named pipe, no socket, no model, no credential. The ONE
genuine resource these doubles keep is the run workspace: its ownership is
never a port (Sec. 17's "never, by construction" list), so a double standing in
for the claim, the re-proof, or the removal could authorize deleting a tree
CFG1 never created -- which is exactly the class of event the registry exists
to prevent. Every workspace here is a real, freshly-minted disposable
repository under an ``ar2``-created root, exactly as the design requires.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pi_harness_cfg1.identity import PINNED_PI_VERSION
from pi_harness_cfg1.run_executor import Cfg1RunPorts

SYNTHETIC_BASE_URL = "https://cfg1-doubles.invalid/v1"
SYNTHETIC_CREDENTIAL = "cfg1-synthetic-key"


@dataclass
class FakeRuntimeIdentity:
    node_executable: str = r"C:\Program Files\nodejs\node.exe"
    pi_cli_js: str = r"C:\pi\dist\cli.js"
    pi_package_root: str = r"C:\pi"
    reported_version: str = PINNED_PI_VERSION
    launch_shape: str = "node_direct"


@dataclass
class FakeRouteObservation:
    reachable: bool = True
    configured_model_served: bool = True


@dataclass
class FakeHandshake:
    matched: bool = True


@dataclass
class FakeRepositorySnapshot:
    head: str = "0" * 40
    changed_tracked_paths: tuple[str, ...] = ()
    untracked_path_count: int = 0
    staged_path_count: int = 0


@dataclass
class FakeVerificationOutcome:
    started: bool = True
    completed: bool = True
    timed_out: bool = False
    output_limit_exceeded: bool = False
    return_code: int = 1
    passed: bool = False
    counts: dict = field(default_factory=lambda: {"passed": 0, "failed": 1, "error": 0})


@dataclass
class FakeExtension:
    """Mirrors the frozen generated layout, including ``ar2_config.ts``.

    The frozen scrubber removes that exact filename from ``extension_dir``, so
    a double that named the token file anything else would make L24 look
    verified while leaving the token on disk.
    """

    entry_path: str
    extension_dir: str


class FakeActivity:
    def __init__(self) -> None:
        self.event_type_counts: dict[str, int] = {}
        self.tool_calls: dict[str, dict] = {}
        self.unmatched_response_ids: list[str] = []
        self.agent_end_count = 0
        self.settled = True
        self.auto_retry_events = 0
        self.extension_errors: list[str] = []


class FakeBroker:
    """A broker that owns no OS resource at all. ``start`` may be made to fail."""

    def __init__(self, *, start_error: Exception | None = None) -> None:
        self.token = "synthetic-broker-token-0f2a"
        self.pipe_name = r"\\.\pipe\cfg1-synthetic-0f2a"
        self.capability_id = "synthetic-capability-0f2a"
        self.started = False
        self.shutdown_calls = 0
        self._start_error = start_error
        self.counts = {
            "read_operations": 0,
            "edit_operations": 0,
            "edited_paths": 0,
            "refusals": 0,
        }
        self.lifecycle = {
            "state_reached": "CLOSED",
            "pending_operations_unreaped": 0,
            "worker_termination_observed": True,
        }

    def start(self) -> None:
        if self._start_error is not None:
            raise self._start_error
        self.started = True

    def diagnostics_counts(self) -> dict:
        return dict(self.counts)

    def shutdown_for_cfg1(self) -> dict:
        self.shutdown_calls += 1
        return dict(self.lifecycle)


class FakeSupervisor:
    """A Pi RPC supervisor that launches nothing. Never a real process."""

    def __init__(
        self,
        *,
        launch_error: Exception | None = None,
        prompt_response: dict | None = None,
        send_error: Exception | None = None,
        wait_outcome: str = "runtime_settled",
        events: list | None = None,
    ) -> None:
        self.activity = FakeActivity()
        self.process = None
        self.commands_sent: list[str] = []
        self.shutdown_calls = 0
        self._launch_error = launch_error
        self._prompt_response = (
            {"type": "response", "command": "prompt", "success": True}
            if prompt_response is None
            else prompt_response
        )
        self._send_error = send_error
        self._wait_outcome = wait_outcome
        self._events = events if events is not None else [
            {"type": "message_end", "message": {"stopReason": "stop"}}
        ]

    def launch(self) -> None:
        if self._launch_error is not None:
            raise self._launch_error
        self.process = object()

    def send_command(self, command: dict) -> None:
        if self._send_error is not None:
            raise self._send_error
        self.commands_sent.append(str(command.get("type")))

    def await_response(self, command_id: str, *, timeout_seconds: float):
        if self._prompt_response is None:
            return "runtime_deadline_expired", None
        return "runtime_response_received", dict(self._prompt_response)

    def await_settled(self, *, timeout_seconds: float) -> str:
        return self._wait_outcome

    def shutdown(self) -> dict:
        self.shutdown_calls += 1
        return {"exit_status_observed": 0, "stdin_closed": True}

    def stdout_state(self) -> dict:
        return {"records_ingested": len(self._events), "eof": True}

    def stderr_snapshot(self) -> dict:
        return {"captured": True, "eof": True}

    def sanitized_events(self) -> list:
        return list(self._events)


def get_state_document(arm_id: str, *, thinking_level: str = "medium") -> dict:
    """A ``get_state`` response shaped exactly as the installed Pi 0.85.1 emits.

    Includes ``baseUrl`` deliberately: the real composed model object carries
    it, and the projection must read past it and retain only the three bounded
    literals. A fixture that omitted it would not exercise that.
    """
    from pi_harness_cfg1.arms import ARM_COMPAT

    model: dict[str, Any] = {
        "id": "qwen3-coder-next",
        "name": "qwen3-coder-next",
        "api": "openai-completions",
        "provider": "b300_pi_qualification",
        "baseUrl": SYNTHETIC_BASE_URL,
        "reasoning": True,
        "input": ["text"],
        "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
        "contextWindow": 128000,
        "maxTokens": 16384,
    }
    compat = ARM_COMPAT[arm_id]
    if compat is not None:
        model["compat"] = dict(compat)
    return {
        "model": model,
        "thinkingLevel": thinking_level,
        "isStreaming": False,
        "isCompacting": False,
        "messageCount": 0,
        "pendingMessageCount": 0,
    }


def build_doubled_ports(
    *,
    git_executable: str,
    arm_id: str = "Q",
    overrides: dict | None = None,
) -> tuple[Cfg1RunPorts, dict]:
    """Every port doubled, with one optional override per port name.

    Returns ``(ports, made)``. ``made`` collects the doubles a test may want to
    inspect afterwards -- the frozen ports dataclass is deliberately not
    widened to carry test state, and is not hashable anyway (its
    ``ambient_environ`` field is a dict).
    """
    from pi_harness_cfg1 import run_workspace
    from pi_harness_cfg1.cfg1_pi_config import write_cfg1_pi_config
    from pi_harness_cfg1.environment import build_cfg1_child_environment

    overrides = overrides or {}
    made: dict[str, Any] = {}

    def _write_extension(*, owned_root: str, broker):
        directory = Path(owned_root) / "pi_extension"
        directory.mkdir(parents=False, exist_ok=False)
        entry = directory / "index.ts"
        config = directory / "ar2_config.ts"
        entry.write_text("// synthetic extension entry\n", encoding="utf-8")
        config.write_text(
            f'export const TOKEN = "{broker.token}";\n', encoding="utf-8"
        )
        return FakeExtension(entry_path=str(entry), extension_dir=str(directory))

    def _build_supervisor(*, identity, extension, environment, workspace_root):
        supervisor = made.get("supervisor") or FakeSupervisor()
        made["supervisor"] = supervisor
        return supervisor

    def _build_broker(*, capability):
        broker = made.get("broker") or FakeBroker()
        made["broker"] = broker
        return broker

    def _evaluate_model_identity(*, supervisor):
        # The arm the doubled config generator recorded, or the declared
        # default when a test overrode ``write_config`` with its own.
        return FakeHandshake(), get_state_document(made.get("arm_id", arm_id))

    def _mint_workspace(*, git_executable):
        workspace, built = run_workspace.mint_cfg1_run_workspace(
            git_executable=git_executable
        )
        made["workspace"] = workspace
        return workspace, built

    def _write_config(*, owned_root, arm_id, base_url):
        made["arm_id"] = arm_id
        return write_cfg1_pi_config(owned_root, arm_id=arm_id, base_url=base_url)

    defaults: dict[str, Any] = {
        "ambient_environ": {"SystemRoot": r"C:\Windows", "PATH": r"C:\decoy"},
        "git_executable": lambda: git_executable,
        "resolve_runtime_identity": lambda: FakeRuntimeIdentity(),
        "mint_workspace": _mint_workspace,
        "observe_repository": lambda *, workspace_root: FakeRepositorySnapshot(),
        "run_verification": lambda *, workspace_root, args: FakeVerificationOutcome(),
        "read_connection": lambda: (SYNTHETIC_BASE_URL, SYNTHETIC_CREDENTIAL),
        "observe_route": lambda *, base_url, api_key, model_id: FakeRouteObservation(),
        "mint_capability": lambda *, workspace, git_executable: object(),
        "write_config": _write_config,
        "write_extension": _write_extension,
        "build_environment": build_cfg1_child_environment,
        "build_broker": _build_broker,
        "build_supervisor": _build_supervisor,
        "evaluate_extension_identity": lambda *, supervisor, extension: FakeHandshake(),
        "evaluate_model_identity": _evaluate_model_identity,
    }
    defaults.update(overrides)
    return Cfg1RunPorts(**defaults), made


def seam_digests_all_match(monkeypatch) -> None:
    """Make the pinned seam-digest check pass for a synthetic Pi package root."""
    from pi_harness_cfg1 import run_executor

    monkeypatch.setattr(
        run_executor, "verify_pi_seam_digests", lambda root: (True, ())
    )
