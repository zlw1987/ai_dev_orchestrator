"""5F3A-AR2-O1-FU1: the exceptional compatibility-failure lifecycle is closed.

Proves, injecting failures at the two representative points named in the
brief -- Pi launch failure after broker READY, and handshake/RPC failure
after Pi process creation -- WITHOUT any real Pi, model, or network call:

- ``o1.handshake.launch_and_handshake`` NEVER lets a raw exception escape
  uncaught: any failure is wrapped in :class:`CompatibilityHandshakeError`,
  which carries the exact original exception class/reason (never a generic
  "compatibility failed"), a truthful bounded-shutdown attempt record, and
  (when a real process existed) its stdout state at the moment of failure;
- a fake Pi child that WAS actually launched is reaped through AR2's own,
  UNMODIFIED ``PiRpcSupervisor.shutdown()`` semantics -- proven by an actual
  live subprocess, not merely asserted;
- no thread survives (the autouse ``_no_leaked_ar2_threads`` fixture in
  ``conftest.py`` enforces this for every test in this module, exactly as
  for every other test in this suite);
- ``run_o1.py``'s ``phase_case`` catches exactly this one exception type,
  never reassigns ``supervisor`` to anything but ``None`` inside that catch,
  and always reaches broker shutdown afterward -- so zero semantic prompts
  is a structural guarantee, not a runtime coincidence.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from ar2.launch import RuntimeIdentity
from ar2.supervisor import PiRpcSupervisor, PiSupervisorError, RunBounds
from o1.handshake import CompatibilityHandshakeError, launch_and_handshake

_O1_DIR = Path(__file__).resolve().parent.parent
_AR2_DIR = _O1_DIR.parent / "pi_external_runtime_ar2"
_AR2_EXTENSION_SOURCE_DIR = str(_AR2_DIR / "extension")
_RUN_O1_SOURCE = (_O1_DIR / "run_o1.py").read_text(encoding="utf-8")


class _FakeFixture:
    """Just enough of ``ar2.fixtures.BuiltFixture`` for launch_and_handshake."""

    def __init__(self, tmp_path: Path):
        self.experiment_root = str(tmp_path)
        repo_root = tmp_path / "repo"
        repo_root.mkdir(exist_ok=True)
        self.repo_root = str(repo_root)


_FAKE_CONFIG = {"provider_id": "aido-ar2-qwen36-direct-vllm", "model_id": "Qwen3.6-27B-262K"}


def _fast_bounds() -> RunBounds:
    return RunBounds(
        startup_deadline_seconds=5.0,
        turn_deadline_seconds=5.0,
        shutdown_deadline_seconds=3.0,
        direct_child_reap_grace_seconds=1.0,
    )


def _call(identity: RuntimeIdentity, fixture: _FakeFixture, *, bounds: RunBounds, git_executable: str):
    return launch_and_handshake(
        identity=identity,
        fixture=fixture,
        config=_FAKE_CONFIG,
        base_url="http://127.0.0.1:1",
        profile_names=(),
        git_executable=git_executable,
        bounds=bounds,
        ar2_extension_source_dir=_AR2_EXTENSION_SOURCE_DIR,
        experiment_id="5F3A-AR2-O1-FU1-TEST",
        pipe_name="\\\\.\\pipe\\aido-ar2-o1-fu1-test",
        capability_id="cap-fu1-test",
        token="tok-fu1-test",
    )


# -- injected failure 1: Pi launch failure after broker READY ---------------


def test_pi_launch_failure_raises_compatibility_handshake_error(tmp_path: Path, git_executable: str):
    fixture = _FakeFixture(tmp_path)
    nonexistent_node = tmp_path / "does_not_exist" / "node.exe"
    identity = RuntimeIdentity(
        node_executable=str(nonexistent_node),
        pi_cli_js=str(tmp_path / "does_not_exist" / "cli.js"),
        pi_package_root=str(tmp_path),
        reported_version="0.84.3",
        launch_shape="node_direct",
    )

    with pytest.raises(CompatibilityHandshakeError) as excinfo:
        _call(identity, fixture, bounds=_fast_bounds(), git_executable=git_executable)

    exc = excinfo.value
    assert isinstance(exc, PiSupervisorError)  # caught by main()'s existing except tuple, unchanged
    assert exc.original_exception_class == "PiSupervisorError"
    assert "launch" in exc.original_exception_reason.lower()


def test_pi_launch_failure_never_claims_a_process_existed(tmp_path: Path, git_executable: str):
    fixture = _FakeFixture(tmp_path)
    identity = RuntimeIdentity(
        node_executable=str(tmp_path / "does_not_exist" / "node.exe"),
        pi_cli_js=str(tmp_path / "does_not_exist" / "cli.js"),
        pi_package_root=str(tmp_path),
        reported_version="0.84.3",
        launch_shape="node_direct",
    )
    with pytest.raises(CompatibilityHandshakeError) as excinfo:
        _call(identity, fixture, bounds=_fast_bounds(), git_executable=git_executable)

    exc = excinfo.value
    # A bounded shutdown WAS attempted (AR2's shutdown() is process-None-safe
    # and was called), but it truthfully reports there was nothing to reap.
    assert exc.termination.get("rung_reached") == "none"
    assert exc.termination.get("exit_status_observed") is None
    assert exc.termination.get("direct_child_terminate_sent") is False
    assert exc.termination.get("direct_child_kill_sent") is False
    # stdout_state is never fetched for a process that never launched --
    # AR2's own stdout_state() would itself raise AssertionError for that.
    assert exc.stdout_state is None


def test_pi_launch_failure_as_dict_never_claims_inference_stopped(tmp_path: Path, git_executable: str):
    fixture = _FakeFixture(tmp_path)
    identity = RuntimeIdentity(
        node_executable=str(tmp_path / "does_not_exist" / "node.exe"),
        pi_cli_js=str(tmp_path / "does_not_exist" / "cli.js"),
        pi_package_root=str(tmp_path),
        reported_version="0.84.3",
        launch_shape="node_direct",
    )
    with pytest.raises(CompatibilityHandshakeError) as excinfo:
        _call(identity, fixture, bounds=_fast_bounds(), git_executable=git_executable)

    record = excinfo.value.as_dict()
    assert record["original_exception_class"] == "PiSupervisorError"
    claim = record["claim_scope"]
    assert "not a claim that Pi/provider inference stopped" in claim
    assert "No thread was killed" in claim
    assert "no fallback" in claim.lower()


# -- injected failure 2: handshake/RPC failure after Pi process creation ----

_BLOCK_ON_STDIN_SCRIPT = """\
import sys
sys.stdin.buffer.read()
sys.exit(0)
"""


@pytest.fixture()
def fake_pi_that_blocks_on_stdin(tmp_path: Path) -> Path:
    """A REAL child process: blocks reading stdin, exits 0 on EOF.

    Used to prove a genuinely-launched fake Pi child is reaped through AR2's
    own, unmodified termination ladder when a later step fails -- not merely
    asserted without ever launching anything.
    """
    script_path = tmp_path / "fake_pi_blocks_on_stdin.py"
    script_path.write_text(_BLOCK_ON_STDIN_SCRIPT, encoding="utf-8")
    return script_path


def test_handshake_rpc_failure_after_real_process_creation_reaps_the_child(
    tmp_path: Path, git_executable: str, fake_pi_that_blocks_on_stdin: Path, monkeypatch: pytest.MonkeyPatch
):
    fixture = _FakeFixture(tmp_path)
    identity = RuntimeIdentity(
        node_executable=sys.executable,
        pi_cli_js=str(fake_pi_that_blocks_on_stdin),
        pi_package_root=str(tmp_path),
        reported_version="0.84.3",
        launch_shape="node_direct",
    )

    def _raise_on_send_command(self, command):  # noqa: ANN001 - test double signature
        raise PiSupervisorError("supervisor error: stdin write failed: injected test failure")

    monkeypatch.setattr(PiRpcSupervisor, "send_command", _raise_on_send_command)

    with pytest.raises(CompatibilityHandshakeError) as excinfo:
        _call(identity, fixture, bounds=_fast_bounds(), git_executable=git_executable)

    exc = excinfo.value
    assert exc.original_exception_class == "PiSupervisorError"
    assert "injected test failure" in exc.original_exception_reason

    # A REAL process existed (launch() succeeded) and was REAPED through
    # AR2's own unmodified shutdown() -- closing stdin let the script see
    # EOF and exit cleanly, which is the FIRST rung, not an escalation.
    assert exc.termination.get("rung_reached") == "exited_after_stdin_close"
    assert exc.termination.get("exit_status_observed") == 0
    assert exc.termination.get("direct_child_terminate_sent") is False
    assert exc.termination.get("direct_child_kill_sent") is False

    # A real process existed, so stdout_state() (AR2's own) was fetchable.
    assert exc.stdout_state is not None
    assert isinstance(exc.stdout_state.get("bytes_seen"), int)

    # The extension WAS written before the injected failure, so the caller
    # (phase_case) still has an extension_dir to scrub during cleanup.
    assert exc.extension_dir
    assert Path(exc.extension_dir).exists()


def test_handshake_rpc_failure_partial_report_has_no_handshake_results(
    tmp_path: Path, git_executable: str, fake_pi_that_blocks_on_stdin: Path, monkeypatch: pytest.MonkeyPatch
):
    """The failure happened before H1 ever got a response -- the partial
    report must not claim a handshake result that never occurred."""
    fixture = _FakeFixture(tmp_path)
    identity = RuntimeIdentity(
        node_executable=sys.executable,
        pi_cli_js=str(fake_pi_that_blocks_on_stdin),
        pi_package_root=str(tmp_path),
        reported_version="0.84.3",
        launch_shape="node_direct",
    )
    monkeypatch.setattr(
        PiRpcSupervisor,
        "send_command",
        lambda self, command: (_ for _ in ()).throw(
            PiSupervisorError("supervisor error: stdin write failed: injected test failure")
        ),
    )
    with pytest.raises(CompatibilityHandshakeError) as excinfo:
        _call(identity, fixture, bounds=_fast_bounds(), git_executable=git_executable)

    partial = excinfo.value.partial_report
    assert "handshake_extension" not in partial
    assert "handshake_model" not in partial
    # But the pre-launch report (config/argv description) WAS populated.
    assert "generated_pi_config" in partial
    assert "launch_flags" in partial


# -- CompatibilityHandshakeError is a PiSupervisorError, unconditionally ----


def test_compatibility_handshake_error_is_always_a_pi_supervisor_error():
    assert issubclass(CompatibilityHandshakeError, PiSupervisorError)


# -- zero-prompt structural guarantee in run_o1.py's phase_case -------------


def _phase_case_source() -> str:
    tree = ast.parse(_RUN_O1_SOURCE)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "phase_case":
            return ast.get_source_segment(_RUN_O1_SOURCE, node) or ""
    raise AssertionError("phase_case not found in run_o1.py")


def _except_compatibility_handshake_block(body: str) -> str:
    marker = "except CompatibilityHandshakeError as exc:"
    start = body.index(marker)
    # The except block ends at the next line with the same or shallower
    # indentation as the surrounding `try:`; the next `else:` at the same
    # depth is that boundary here.
    end = body.index("\n        else:\n", start)
    return body[start:end]


def test_phase_case_catches_compatibility_handshake_error():
    body = _phase_case_source()
    assert "except CompatibilityHandshakeError as exc:" in body


def test_phase_case_never_reassigns_supervisor_inside_the_exception_handler():
    body = _phase_case_source()
    except_block = _except_compatibility_handshake_block(body)
    assert "supervisor =" not in except_block
    assert "supervisor=" not in except_block


def test_phase_case_does_not_reshutdown_inside_the_exception_handler():
    """launch_and_handshake already attempted the bounded shutdown; phase_case
    must not call supervisor.shutdown() a second time from the handler."""
    body = _phase_case_source()
    except_block = _except_compatibility_handshake_block(body)
    assert ".shutdown()" not in except_block


def test_phase_case_broker_shutdown_is_lexically_after_the_handshake_try_except():
    body = _phase_case_source()
    try_index = body.index("try:\n            supervisor, launch_report, extension_dir = launch_and_handshake")
    except_index = body.index("except CompatibilityHandshakeError as exc:")
    broker_shutdown_index = body.index("lifecycle = server.shutdown(shutdown_trigger)")
    assert try_index < except_index < broker_shutdown_index


def test_phase_case_prompt_send_still_unreachable_after_a_caught_exception():
    """Zero prompts on a compatibility-handshake exception: the prompt guard
    still requires `supervisor is not None`, and the exception handler never
    sets it to anything but leaves it None."""
    body = _phase_case_source()
    guard_index = body.index("if gate_all_passed and supervisor is not None:")
    prompt_index = body.index('"type": "prompt"')
    except_index = body.index("except CompatibilityHandshakeError as exc:")
    assert except_index < guard_index < prompt_index
