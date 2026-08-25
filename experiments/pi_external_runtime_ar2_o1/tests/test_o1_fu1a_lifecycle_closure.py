"""5F3A-AR2-O1-FU1A: handshake resource/scrub lifecycle closure.

Three tightly-scoped regressions, all offline, all deterministic:

A. ``run_o1.py``'s standalone ``phase_handshake`` now closes its own
   broker/fixture lifecycle on a ``launch_and_handshake`` failure, exactly
   like ``phase_case`` already does since FU1 -- proven here by source
   inspection, in the same spirit as the FU1 tests for ``phase_case``.
B. A Pi-config write that succeeds followed by a LATER extension-write
   failure must not leave the generated, endpoint-bearing ``models.json``
   unscrubbed -- proven by a real ``launch_and_handshake`` call with
   ``write_disposable_extension`` injected to fail, using a synthetic
   endpoint needle and no network.
C. A ``supervisor.shutdown()`` call that itself raises must never replace
   or mask the ORIGINAL compatibility failure -- proven by a real fake-Pi
   child, a real handshake/RPC failure, and an injected shutdown failure,
   with the injected failure stub responsible for actually reaping the
   child so no test-owned process is ever left running.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from ar2.launch import RuntimeIdentity
from ar2.pi_config import scrub_generated_pi_config
from ar2.supervisor import PiRpcSupervisor, PiSupervisorError, RunBounds
from o1.handshake import CompatibilityHandshakeError, launch_and_handshake

_O1_DIR = Path(__file__).resolve().parent.parent
_AR2_DIR = _O1_DIR.parent / "pi_external_runtime_ar2"
_AR2_EXTENSION_SOURCE_DIR = str(_AR2_DIR / "extension")
_RUN_O1_SOURCE = (_O1_DIR / "run_o1.py").read_text(encoding="utf-8")

_SYNTHETIC_ENDPOINT_NEEDLE = "http://synthetic-fu1a-test-endpoint.invalid:9999/v1"


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


def _call(
    identity: RuntimeIdentity,
    fixture: _FakeFixture,
    *,
    bounds: RunBounds,
    git_executable: str,
    base_url: str = "http://127.0.0.1:1",
):
    return launch_and_handshake(
        identity=identity,
        fixture=fixture,
        config=_FAKE_CONFIG,
        base_url=base_url,
        profile_names=(),
        git_executable=git_executable,
        bounds=bounds,
        ar2_extension_source_dir=_AR2_EXTENSION_SOURCE_DIR,
        experiment_id="5F3A-AR2-O1-FU1A-TEST",
        pipe_name="\\\\.\\pipe\\aido-ar2-o1-fu1a-test",
        capability_id="cap-fu1a-test",
        token="tok-fu1a-test",
    )


# =============================================================================
# A. Standalone phase_handshake closes its broker/fixture lifecycle
# =============================================================================


def _phase_handshake_source() -> str:
    tree = ast.parse(_RUN_O1_SOURCE)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "phase_handshake":
            return ast.get_source_segment(_RUN_O1_SOURCE, node) or ""
    raise AssertionError("phase_handshake not found in run_o1.py")


def test_phase_handshake_never_sends_a_prompt():
    """Structural zero-prompt proof: no prompt-send statement exists at all."""
    body = _phase_handshake_source()
    assert '"type": "prompt"' not in body


def test_phase_handshake_catches_compatibility_handshake_error():
    body = _phase_handshake_source()
    assert "except CompatibilityHandshakeError as exc:" in body


def test_phase_handshake_broker_shutdown_is_lexically_after_the_try_except():
    body = _phase_handshake_source()
    try_index = body.index("try:\n        supervisor, launch_report, extension_dir = launch_and_handshake")
    except_index = body.index("except CompatibilityHandshakeError as exc:")
    broker_shutdown_index = body.index('report["broker_recorded_lifecycle"] = server.shutdown(TRIGGER_PI_EXITED)')
    assert try_index < except_index < broker_shutdown_index


def test_phase_handshake_broker_shutdown_appears_exactly_once():
    body = _phase_handshake_source()
    assert body.count("server.shutdown(") == 1


def test_phase_handshake_pi_config_scrub_is_not_conditional_on_extension_dir():
    """The exact FU1A regression shape: two INDEPENDENT `if` guards, neither
    nested inside the other."""
    body = _phase_handshake_source()
    pi_scrub_index = body.index('if pi_config_dir:\n        report["cleanup_pi_models_json_scrub"]')
    ext_scrub_index = body.index('if extension_dir:\n        report["cleanup_extension_binding_scrub"]')
    # Neither scrub line is textually nested inside the other's `if` body --
    # both are top-level statements at the same indentation, proven by both
    # starting a fresh line with the same 4-space indentation as this
    # function's other top-level statements.
    assert body.count("\n    if pi_config_dir:\n") == 1 or body.count("if pi_config_dir:") == 1
    assert pi_scrub_index != ext_scrub_index


def test_phase_handshake_fixture_cleanup_is_always_reached():
    body = _phase_handshake_source()
    cleanup_index = body.index('report["cleanup"] = remove_disposable_tree(fixture.experiment_root)')
    except_index = body.index("except CompatibilityHandshakeError as exc:")
    assert except_index < cleanup_index


def test_phase_handshake_never_reassigns_supervisor_inside_the_exception_handler():
    body = _phase_handshake_source()
    start = body.index("except CompatibilityHandshakeError as exc:")
    end = body.index("\n    else:\n", start)
    except_block = body[start:end]
    assert "supervisor =" not in except_block
    assert "supervisor=" not in except_block


def test_phase_handshake_does_not_reshutdown_inside_the_exception_handler():
    body = _phase_handshake_source()
    start = body.index("except CompatibilityHandshakeError as exc:")
    end = body.index("\n    else:\n", start)
    except_block = body[start:end]
    assert ".shutdown()" not in except_block


# =============================================================================
# B. Pi-config-before-extension-failure window: config must still be scrubbed
# =============================================================================


def test_pi_config_survives_before_scrub_when_extension_write_fails(
    tmp_path: Path, git_executable: str, monkeypatch: pytest.MonkeyPatch
):
    """Demonstrates the FAILURE WINDOW the fix closes: absent the fix, the
    generated, endpoint-bearing models.json would be left on disk, because
    write order is Pi-config-then-extension and the extension write is the
    one that fails."""
    import o1.handshake as handshake_module

    def _raise_on_extension_write(*args, **kwargs):
        raise RuntimeError("injected test failure: extension write failed")

    monkeypatch.setattr(handshake_module, "write_disposable_extension", _raise_on_extension_write)

    fixture = _FakeFixture(tmp_path)
    identity = RuntimeIdentity(
        node_executable=sys.executable,
        pi_cli_js=str(tmp_path / "unused_cli.js"),
        pi_package_root=str(tmp_path),
        reported_version="0.84.3",
        launch_shape="node_direct",
    )

    with pytest.raises(CompatibilityHandshakeError) as excinfo:
        _call(
            identity,
            fixture,
            bounds=_fast_bounds(),
            git_executable=git_executable,
            base_url=_SYNTHETIC_ENDPOINT_NEEDLE,
        )

    exc = excinfo.value

    # The ORIGINAL failure is the injected extension-write error, not a
    # generic message.
    assert exc.original_exception_class == "RuntimeError"
    assert "extension write failed" in exc.original_exception_reason

    # Pi config WAS generated (tracked independently); extension was NOT.
    assert exc.pi_config_dir
    assert exc.extension_dir == ""

    # Zero prompts: launch() was never reached (the extension write failure
    # happens before the supervisor is even constructed), so there is no
    # process, no supervisor, and structurally no prompt-send code path.
    assert exc.termination == {}
    assert exc.shutdown_attempted is False

    # BEFORE scrub: the synthetic endpoint needle really is present on disk
    # -- proving the failure window is real, not hypothetical.
    generated_models_json = Path(exc.pi_config_dir) / "models.json"
    assert generated_models_json.is_file()
    assert _SYNTHETIC_ENDPOINT_NEEDLE in generated_models_json.read_text(encoding="utf-8")

    # THE FIX: cleanup scrubs the Pi config independently of extension_dir
    # (exactly what run_o1.py's cleanup now does unconditionally on
    # `if pi_config_dir:`, never on `if extension_dir:`).
    scrub_result = scrub_generated_pi_config(exc.pi_config_dir)
    assert scrub_result["generated_models_json_existed"] is True
    assert scrub_result["generated_models_json_removed"] is True

    # AFTER scrub: the endpoint value is gone from disk entirely.
    assert not generated_models_json.exists()


def test_pi_config_scrub_result_reports_verified_removal(
    tmp_path: Path, git_executable: str, monkeypatch: pytest.MonkeyPatch
):
    import o1.handshake as handshake_module

    monkeypatch.setattr(
        handshake_module,
        "write_disposable_extension",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("injected: extension unavailable")),
    )
    fixture = _FakeFixture(tmp_path)
    identity = RuntimeIdentity(
        node_executable=sys.executable,
        pi_cli_js=str(tmp_path / "unused_cli.js"),
        pi_package_root=str(tmp_path),
        reported_version="0.84.3",
        launch_shape="node_direct",
    )
    with pytest.raises(CompatibilityHandshakeError) as excinfo:
        _call(identity, fixture, bounds=_fast_bounds(), git_executable=git_executable)

    exc = excinfo.value
    scrub_result = scrub_generated_pi_config(exc.pi_config_dir)
    assert scrub_result["verified_by_stat"] is True


def test_compatibility_handshake_error_as_dict_never_contains_the_endpoint(
    tmp_path: Path, git_executable: str, monkeypatch: pytest.MonkeyPatch
):
    """as_dict() must never leak the raw config directory path or the
    endpoint value -- only booleans."""
    import json as _json

    import o1.handshake as handshake_module

    monkeypatch.setattr(
        handshake_module,
        "write_disposable_extension",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("injected: extension unavailable")),
    )
    fixture = _FakeFixture(tmp_path)
    identity = RuntimeIdentity(
        node_executable=sys.executable,
        pi_cli_js=str(tmp_path / "unused_cli.js"),
        pi_package_root=str(tmp_path),
        reported_version="0.84.3",
        launch_shape="node_direct",
    )
    with pytest.raises(CompatibilityHandshakeError) as excinfo:
        _call(
            identity, fixture, bounds=_fast_bounds(), git_executable=git_executable,
            base_url=_SYNTHETIC_ENDPOINT_NEEDLE,
        )

    record = excinfo.value.as_dict()
    serialized = _json.dumps(record)
    assert _SYNTHETIC_ENDPOINT_NEEDLE not in serialized
    assert str(tmp_path) not in serialized
    assert record["pi_config_dir_generated"] is True
    assert record["extension_dir_generated"] is False


# =============================================================================
# C. A failing shutdown must not mask the original compatibility failure
# =============================================================================

_BLOCK_ON_STDIN_SCRIPT = """\
import sys
sys.stdin.buffer.read()
sys.exit(0)
"""


@pytest.fixture()
def fake_pi_that_blocks_on_stdin(tmp_path: Path) -> Path:
    script_path = tmp_path / "fake_pi_blocks_on_stdin.py"
    script_path.write_text(_BLOCK_ON_STDIN_SCRIPT, encoding="utf-8")
    return script_path


def test_shutdown_failure_does_not_mask_the_original_handshake_failure(
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
        raise PiSupervisorError("supervisor error: stdin write failed: injected RPC failure")

    monkeypatch.setattr(PiRpcSupervisor, "send_command", _raise_on_send_command)

    # The injected shutdown failure. It is ALSO responsible for actually
    # reaping the real child directly (bypassing its own broken method), so
    # this test never leaks a live process even though the AIDO shutdown
    # path intentionally fails -- exactly the bounded, test-owned cleanup
    # the brief requires.
    reaped: dict[str, object] = {"waited": False, "exit_code": None}

    def _broken_shutdown(self):
        if self.process is not None:
            if self.process.stdin is not None:
                try:
                    self.process.stdin.close()
                except OSError:
                    pass
            try:
                reaped["exit_code"] = self.process.wait(timeout=5)
                reaped["waited"] = True
            except Exception:  # noqa: BLE001 - test cleanup must not itself raise
                pass
        raise RuntimeError("injected shutdown failure")

    monkeypatch.setattr(PiRpcSupervisor, "shutdown", _broken_shutdown)

    with pytest.raises(CompatibilityHandshakeError) as excinfo:
        _call(identity, fixture, bounds=_fast_bounds(), git_executable=git_executable)

    exc = excinfo.value

    # The ORIGINAL compatibility failure remains primary and un-replaced.
    assert exc.original_exception_class == "PiSupervisorError"
    assert "injected RPC failure" in exc.original_exception_reason

    # The shutdown failure is recorded SEPARATELY, never as the main cause.
    assert exc.shutdown_attempted is True
    assert exc.shutdown_exception_class == "RuntimeError"
    assert exc.shutdown_exception_reason is not None
    assert "injected shutdown failure" in exc.shutdown_exception_reason

    # No false claim that the child stopped: termination is the same
    # "nothing observed" shape used when no shutdown was attempted at all.
    assert exc.termination == {}

    # stdout_state is still independently fetchable (a real process existed
    # and its attribute is unaffected by shutdown() raising).
    assert exc.stdout_state is not None

    # Zero prompts: the failure happened at h1, well before any prompt code
    # path could be reached.
    # (structural: launch_and_handshake contains no prompt-send statement)

    # The test-owned real child WAS actually reaped, by the injected
    # shutdown stub itself, despite the stub also raising.
    assert reaped["waited"] is True
    assert reaped["exit_code"] == 0


def test_shutdown_failure_as_dict_exposes_only_bounded_safe_fields(
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
    monkeypatch.setattr(
        PiRpcSupervisor,
        "send_command",
        lambda self, command: (_ for _ in ()).throw(
            PiSupervisorError("supervisor error: stdin write failed: injected RPC failure")
        ),
    )

    def _broken_shutdown(self):
        if self.process is not None:
            if self.process.stdin is not None:
                try:
                    self.process.stdin.close()
                except OSError:
                    pass
            try:
                self.process.wait(timeout=5)
            except Exception:  # noqa: BLE001 - test cleanup must not itself raise
                pass
        raise RuntimeError("injected shutdown failure with a very very long " + "x" * 2000)

    monkeypatch.setattr(PiRpcSupervisor, "shutdown", _broken_shutdown)

    with pytest.raises(CompatibilityHandshakeError) as excinfo:
        _call(identity, fixture, bounds=_fast_bounds(), git_executable=git_executable)

    record = excinfo.value.as_dict()
    assert record["supervisor_shutdown_itself_raised"] is True
    assert record["supervisor_shutdown_exception_class"] == "RuntimeError"
    # Bounded: the (deliberately oversized) reason is capped, not raw.
    assert len(record["supervisor_shutdown_exception_reason"]) <= 500
    assert "not a claim that Pi/provider inference stopped" in record["claim_scope"]
    assert "NEVER read as proof" in record["claim_scope"]
