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

from pi_harness_cfg1.run_executor import Cfg1RunPorts

SYNTHETIC_BASE_URL = "https://cfg1-doubles.invalid/v1"
SYNTHETIC_CREDENTIAL = "cfg1-synthetic-key"


# ---------------------------------------------------------------------------
# FU1 (AMEND1 AMD-1): the static Pi identity proof runs its GENUINE leaves over
# a SYNTHETIC on-disk Pi tree with a TEST-OWNED pin table. Nothing here is Node
# or Pi: ``node.exe`` is an inert byte string that is never executed, ``pi.cmd``
# is never read, and the 20 "seam" files are synthetic bytes whose digests the
# test itself pins (Test AC's "test-owned pin table").
# ---------------------------------------------------------------------------

import hashlib
import os
import tempfile

from pi_harness_cfg1.preflight import PINNED_PI_SEAM_DIGESTS as _REAL_PINNED_TABLE

SYNTHETIC_NODE_BYTES = b"synthetic node image -- never executed by the CFG1 suite\n"
SYNTHETIC_PI_CMD_BYTES = b"@rem synthetic anchor -- never read, never executed\r\n"


def synthetic_seam_bytes(relative: str) -> bytes:
    """Deterministic synthetic bytes for one pinned seam key."""
    return b"synthetic cfg1 seam file: " + relative.encode("ascii") + b"\n"


@dataclass
class SyntheticPiTree:
    """One synthetic Pi installation on disk. Paths are real, bytes are not Pi."""

    base: str
    node_dir: str
    npm_dir: str
    node_exe: str
    pi_cmd: str
    package_root: str
    pin_table: dict

    @property
    def path_value(self) -> str:
        return f"{self.node_dir};{self.npm_dir}"

    def seam_path(self, relative: str) -> str:
        return os.path.join(self.package_root, *relative.split("/"))


def build_synthetic_pi_tree(base: str) -> SyntheticPiTree:
    """Create the synthetic tree under ``base`` (which must already exist)."""
    node_dir = os.path.join(base, "nodejs")
    npm_dir = os.path.join(base, "npm")
    package_root = os.path.join(npm_dir, "node_modules", "@earendil-works", "pi-coding-agent")
    os.makedirs(node_dir)
    os.makedirs(package_root)
    node_exe = os.path.join(node_dir, "node.exe")
    pi_cmd = os.path.join(npm_dir, "pi.cmd")
    with open(node_exe, "wb") as handle:
        handle.write(SYNTHETIC_NODE_BYTES)
    with open(pi_cmd, "wb") as handle:
        handle.write(SYNTHETIC_PI_CMD_BYTES)
    table = {}
    for relative in sorted(_REAL_PINNED_TABLE):
        target = os.path.join(package_root, *relative.split("/"))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        data = synthetic_seam_bytes(relative)
        with open(target, "wb") as handle:
            handle.write(data)
        table[relative] = hashlib.sha256(data).hexdigest()
    return SyntheticPiTree(
        base=base,
        node_dir=node_dir,
        npm_dir=npm_dir,
        node_exe=node_exe,
        pi_cmd=pi_cmd,
        package_root=package_root,
        pin_table=table,
    )


_SESSION_TREE: SyntheticPiTree | None = None


def session_synthetic_pi_tree() -> SyntheticPiTree:
    """ONE shared synthetic tree for the doubled executor ports.

    Created lazily under the system temporary directory (never inside the
    checkout) and never mutated by the doubles; a test that needs to mutate a
    Pi tree builds its own under ``tmp_path``.
    """
    global _SESSION_TREE
    if _SESSION_TREE is None:
        import atexit
        import shutil

        base = tempfile.mkdtemp(prefix="cfg1_fu1_synthetic_pi_")
        atexit.register(shutil.rmtree, base, True)
        _SESSION_TREE = build_synthetic_pi_tree(base)
    return _SESSION_TREE


def use_test_owned_pin_table(monkeypatch, table: dict) -> None:
    """Point the static proof at a TEST-OWNED 20-entry pin table."""
    from pi_harness_cfg1 import pi_identity

    assert len(table) == 20 and set(table) == set(_REAL_PINNED_TABLE)
    monkeypatch.setattr(pi_identity, "PINNED_PI_SEAM_DIGESTS", dict(table))


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


def probe_facts_for_arm(arm_id: str) -> tuple[bool, str, str, str]:
    """The four L16 facts a runtime that loaded ``arm_id``'s declared shape reports."""
    from pi_harness_cfg1.arms import ARM_SHAPE

    return True, "TRUE", ARM_SHAPE[arm_id], "medium"


class FakeSupervisor:
    """A Pi RPC supervisor that launches nothing. Never a real process.

    CFG1-L16-FU2 (Sec. 12.2): its ``probe_runtime_capabilities()`` returns
    SCRIPTED scalars. It exists so the rest of the state machine can be driven
    offline, and so CFG1's own L16 type-check and refusal mapping can be
    asserted. It proves nothing about the receive boundary: every row about
    that drives the REAL supervisor over a synthetic peer instead.
    """

    def __init__(
        self,
        *,
        launch_error: Exception | None = None,
        prompt_response: dict | None = None,
        send_error: Exception | None = None,
        wait_outcome: str = "runtime_settled",
        events: list | None = None,
        probe_facts: Any = None,
        probe_error: Exception | None = None,
    ) -> None:
        self.activity = FakeActivity()
        self.process = None
        self.commands_sent: list[str] = []
        self.shutdown_calls = 0
        #: A tuple, or a zero-argument callable producing one. ``None`` means
        #: "the arm the run's config generator recorded" (build_doubled_ports).
        self.probe_facts = probe_facts
        self.probe_calls = 0
        self._probe_error = probe_error
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

    def probe_runtime_capabilities(self):
        self.probe_calls += 1
        if self._probe_error is not None:
            raise self._probe_error
        facts = self.probe_facts
        if callable(facts):
            facts = facts()
        if facts is None:
            facts = probe_facts_for_arm("Q")
        return facts

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

    CFG1-L16-FU2: there is no H2 port any more. ``overrides`` may instead
    carry ``probe_facts`` (and ``probe_error``) -- TEST-DOUBLE configuration,
    never a port -- scripting what any :class:`FakeSupervisor` the run builds
    returns from its probe. Absent both, the facts are those of a runtime that
    loaded the arm the doubled config generator recorded.
    """
    from pi_harness_cfg1 import run_workspace
    from pi_harness_cfg1.cfg1_extension import write_cfg1_extension
    from pi_harness_cfg1.cfg1_pi_config import write_cfg1_pi_config
    from pi_harness_cfg1.pi_identity import genuine_pi_proof_leaves
    from pi_harness_cfg1.environment import build_cfg1_child_environment

    overrides = dict(overrides or {})
    scripted_facts = overrides.pop("probe_facts", None)
    scripted_error = overrides.pop("probe_error", None)
    made: dict[str, Any] = {}

    def _script_probe(supervisor):
        if isinstance(supervisor, FakeSupervisor) and supervisor.probe_facts is None:
            if scripted_facts is not None:
                supervisor.probe_facts = scripted_facts
            else:
                supervisor.probe_facts = lambda: probe_facts_for_arm(
                    made.get("arm_id", arm_id)
                )
            if scripted_error is not None:
                supervisor._probe_error = scripted_error
        return supervisor

    def _write_extension(*, workspace, broker):
        # FU1: the GENUINE CFG1 transactional writer (R6 AM-9/AM-14), over the
        # real, pinned in-repository AR2 extension sources. It returns only an
        # extension issuance token; L14/L15 re-verify it and L24 consumes it.
        return write_cfg1_extension(
            workspace,
            pipe_name=broker.pipe_name,
            capability_id=broker.capability_id,
            token=broker.token,
        )

    def _build_supervisor(*, identity, extension, environment, workspace_root):
        supervisor = made.get("supervisor") or FakeSupervisor()
        made["supervisor"] = supervisor
        return supervisor

    def _build_broker(*, capability):
        broker = made.get("broker") or FakeBroker()
        made["broker"] = broker
        return broker

    def _mint_workspace(*, git_executable):
        workspace, built = run_workspace.mint_cfg1_run_workspace(
            git_executable=git_executable
        )
        made["workspace"] = workspace
        return workspace, built

    def _write_config(*, workspace, arm_id, base_url):
        made["arm_id"] = arm_id
        return write_cfg1_pi_config(workspace, arm_id=arm_id, base_url=base_url)

    defaults: dict[str, Any] = {
        "ambient_environ": {
            "SystemRoot": r"C:\Windows",
            "PATH": session_synthetic_pi_tree().path_value,
        },
        "git_executable": lambda: git_executable,
        "pi_proof_leaves": genuine_pi_proof_leaves(),
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
    }
    defaults.update(overrides)
    builder = defaults["build_supervisor"]
    defaults["build_supervisor"] = lambda **kwargs: _script_probe(builder(**kwargs))
    return Cfg1RunPorts(**defaults), made


def seam_digests_all_match(monkeypatch) -> None:
    """Make the static seam proof pass for the doubled ports' synthetic tree.

    FU1: the proof itself is the GENUINE static P (and the genuine L14
    re-proof); only its pin TABLE is test-owned, matching the synthetic tree's
    synthetic bytes. Nothing executes: the tree's ``node.exe`` is never run.
    """
    use_test_owned_pin_table(monkeypatch, session_synthetic_pi_tree().pin_table)


class StaticIdentityShape:
    """A TEST-ONLY object with exactly the five AMEND1 Sec. 10 attributes.

    The genuine :class:`pi_harness_cfg1.pi_identity.Cfg1PiIdentity` can be
    produced only by a passing P; tests that exercise a port which merely
    CONSUMES the identity shape (e.g. the genuine supervisor builder's argv)
    use this instead. ``__slots__`` and no ``__getattr__``: reading any other
    attribute raises (Test AG's discipline).
    """

    __slots__ = (
        "node_executable",
        "pi_cli_js",
        "pi_package_root",
        "node_identity",
        "package_root_identity",
    )

    def __init__(
        self,
        *,
        node_executable: str = r"C:\cfg1-synthetic\nodejs\node.exe",
        pi_cli_js: str = r"C:\cfg1-synthetic\pi\dist\cli.js",
        pi_package_root: str = r"C:\cfg1-synthetic\pi",
        node_identity: tuple = (1, 2),
        package_root_identity: tuple = (1, 3),
    ) -> None:
        self.node_executable = node_executable
        self.pi_cli_js = pi_cli_js
        self.pi_package_root = pi_package_root
        self.node_identity = node_identity
        self.package_root_identity = package_root_identity
