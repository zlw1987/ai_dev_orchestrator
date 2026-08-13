"""Phase 5F2D tests: the one controlled verification execution.

This module is the only place in the repository that launches a program the
*project* chose, so these tests pin down exactly what is controlled about that
launch — and, just as importantly, that the module offers no way to launch
anything else.

Every process started here is a small synthetic Python script written under
pytest's ``tmp_path``. **No real target project executable is used.**
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

from ai_dev_orchestrator.verification import runner as runner_module
from ai_dev_orchestrator.verification.runner import (
    FORBIDDEN_ENV_NAME_FRAGMENTS,
    INHERITED_ENV_NAMES,
    VerificationExecutableError,
    VerificationLaunchError,
    build_verification_argv,
    build_verification_environment,
    decode_verification_output,
    run_configured_verification,
    validate_verification_executable,
)


def _script(tmp_path: Path, name: str, body: str) -> Path:
    """Write one synthetic verification program **outside** any repository."""
    scripts = tmp_path / "scripts"
    scripts.mkdir(exist_ok=True)
    path = scripts / name
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir(exist_ok=True)
    return workspace


def _run(tmp_path: Path, script: Path, *, timeout=30, cap=200_000, extra=()):
    return run_configured_verification(
        executable=sys.executable,
        args=[str(script), *extra],
        cwd=str(_workspace(tmp_path)),
        timeout_seconds=timeout,
        max_output_bytes=cap,
    )


# =============================================================================
# 1. Executable authority
# =============================================================================


def test_an_unconfigured_executable_is_refused(tmp_path):
    with pytest.raises(VerificationExecutableError) as excinfo:
        validate_verification_executable(None, workspace_root=str(_workspace(tmp_path)))

    assert "no default executable" in str(excinfo.value)
    assert "PATH" in str(excinfo.value)


@pytest.mark.parametrize("value", ["", "   "])
def test_a_blank_executable_is_refused(tmp_path, value):
    with pytest.raises(VerificationExecutableError):
        validate_verification_executable(
            value, workspace_root=str(_workspace(tmp_path))
        )


@pytest.mark.parametrize("value", ["python", "python.exe", "./python", "..\\python"])
def test_a_relative_executable_is_refused_and_no_path_lookup_happens(tmp_path, value):
    with pytest.raises(VerificationExecutableError) as excinfo:
        validate_verification_executable(
            value, workspace_root=str(_workspace(tmp_path))
        )

    assert "absolute path" in str(excinfo.value)


def test_a_missing_executable_is_refused(tmp_path):
    missing = tmp_path / "nowhere" / "python.exe"

    with pytest.raises(VerificationExecutableError) as excinfo:
        validate_verification_executable(
            str(missing), workspace_root=str(_workspace(tmp_path))
        )

    assert "does not exist" in str(excinfo.value)


def test_a_directory_executable_is_refused(tmp_path):
    directory = tmp_path / "a_directory"
    directory.mkdir()

    with pytest.raises(VerificationExecutableError) as excinfo:
        validate_verification_executable(
            str(directory), workspace_root=str(_workspace(tmp_path))
        )

    assert "not a regular file" in str(excinfo.value)


def test_an_executable_inside_the_target_workspace_is_refused(tmp_path):
    workspace = _workspace(tmp_path)
    inside = workspace / ".venv" / "Scripts"
    inside.mkdir(parents=True)
    candidate = inside / "python.exe"
    candidate.write_bytes(b"not really a program")

    with pytest.raises(VerificationExecutableError) as excinfo:
        validate_verification_executable(
            str(candidate), workspace_root=str(workspace)
        )

    assert "inside the target workspace" in str(excinfo.value)


def test_the_workspace_root_itself_is_refused_as_an_executable(tmp_path):
    workspace = _workspace(tmp_path)

    with pytest.raises(VerificationExecutableError):
        validate_verification_executable(
            str(workspace), workspace_root=str(workspace)
        )


def test_an_executable_outside_the_workspace_is_accepted(tmp_path):
    resolved = validate_verification_executable(
        sys.executable, workspace_root=str(_workspace(tmp_path))
    )

    assert os.path.isabs(resolved)
    assert os.path.isfile(resolved)


def test_a_nul_byte_in_the_executable_is_refused(tmp_path):
    with pytest.raises(VerificationExecutableError):
        validate_verification_executable(
            "C:\\tools\\py\x00thon.exe", workspace_root=str(_workspace(tmp_path))
        )


# =============================================================================
# 2. Argv authority
# =============================================================================


def test_the_argv_is_exactly_the_executable_then_the_configured_args():
    argv = build_verification_argv("C:\\tools\\python.exe", ["-m", "pytest", "-q"])

    assert argv == ("C:\\tools\\python.exe", "-m", "pytest", "-q")


def test_args_are_used_verbatim_and_shell_metacharacters_are_not_interpreted():
    hostile = "a && b | c > d ; rm -rf / $(whoami) `id` %PATH%"
    argv = build_verification_argv("C:\\tools\\python.exe", [hostile])

    # One argument in, one argument out. Nothing split, quoted, or expanded.
    assert argv == ("C:\\tools\\python.exe", hostile)


def test_an_empty_arg_list_is_a_bare_executable_invocation():
    assert build_verification_argv("C:\\tools\\python.exe", []) == (
        "C:\\tools\\python.exe",
    )


def test_a_nul_byte_in_an_arg_is_refused():
    with pytest.raises(VerificationExecutableError):
        build_verification_argv("C:\\tools\\python.exe", ["-m", "pyt\x00est"])


def test_a_non_string_arg_is_refused():
    with pytest.raises(VerificationExecutableError):
        build_verification_argv("C:\\tools\\python.exe", [7])


def test_the_module_exposes_no_general_command_runner():
    """There is no public 'run whatever you like' entry point here."""
    public = {name for name in dir(runner_module) if not name.startswith("_")}

    for forbidden in ("run", "run_command", "execute", "call", "check_output", "spawn"):
        assert forbidden not in public, forbidden

    source = Path(runner_module.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "shell=True",
        "subprocess.run(",
        "subprocess.call(",
        "check_output",
        "os.system",
        "os.popen",
        "shlex",
        "shutil.which",
    ):
        assert forbidden not in source, forbidden


# =============================================================================
# 3. Environment
# =============================================================================


def test_the_child_environment_is_an_allowlist_not_os_environ(monkeypatch):
    monkeypatch.setenv("AIDO_LITELLM_API_KEY", "sk-should-never-be-forwarded")
    monkeypatch.setenv("AIDO_LITELLM_BASE_URL", "http://internal.invalid/v1")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_should_never_be_forwarded")
    monkeypatch.setenv("SOME_DATABASE_PASSWORD", "hunter2")
    monkeypatch.setenv("MY_CLOUD_SECRET", "value")

    environment = build_verification_environment()

    assert set(environment) <= set(INHERITED_ENV_NAMES)
    for name in (
        "AIDO_LITELLM_API_KEY",
        "AIDO_LITELLM_BASE_URL",
        "GITHUB_TOKEN",
        "SOME_DATABASE_PASSWORD",
        "MY_CLOUD_SECRET",
    ):
        assert name not in environment


def test_no_forbidden_fragment_survives_the_allowlist(monkeypatch):
    # Even if a name somehow appeared in both lists, the second pass drops it.
    monkeypatch.setattr(
        runner_module, "INHERITED_ENV_NAMES", ("PATH", "GITHUB_TOKEN", "AIDO_X")
    )
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_x")
    monkeypatch.setenv("AIDO_X", "y")

    environment = build_verification_environment()

    assert "GITHUB_TOKEN" not in environment
    assert "AIDO_X" not in environment
    for name in environment:
        assert not any(
            fragment in name.upper() for fragment in FORBIDDEN_ENV_NAME_FRAGMENTS
        )


def test_git_environment_variables_are_never_forwarded(monkeypatch):
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_CONFIG"):
        monkeypatch.setenv(name, "anything")

    environment = build_verification_environment()

    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_CONFIG"):
        assert name not in environment


def test_the_child_actually_sees_only_the_minimal_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("AIDO_LITELLM_API_KEY", "sk-never-forwarded-abcdefgh")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_never_forwarded")

    script = _script(
        tmp_path,
        "dump_env.py",
        """
        import os, sys
        for name in sorted(os.environ):
            sys.stdout.write(name + "\\n")
        """,
    )

    execution = _run(tmp_path, script)
    names = set(execution.output_bytes.decode("utf-8").split())

    assert "AIDO_LITELLM_API_KEY" not in names
    assert "GITHUB_TOKEN" not in names
    assert execution.return_code == 0


# =============================================================================
# 4. Invocation properties
# =============================================================================


def test_the_child_runs_in_the_given_working_directory(tmp_path):
    script = _script(
        tmp_path,
        "print_cwd.py",
        """
        import os, sys
        sys.stdout.write(os.getcwd())
        """,
    )

    execution = _run(tmp_path, script)

    assert os.path.normcase(
        os.path.realpath(execution.output_bytes.decode("utf-8").strip())
    ) == os.path.normcase(os.path.realpath(str(_workspace(tmp_path))))


def test_stdin_is_devnull_so_a_prompting_process_gets_eof(tmp_path):
    script = _script(
        tmp_path,
        "read_stdin.py",
        """
        import sys
        data = sys.stdin.read()
        sys.stdout.write("read %d bytes" % len(data))
        """,
    )

    execution = _run(tmp_path, script, timeout=20)

    assert execution.completed is True
    assert b"read 0 bytes" in execution.output_bytes


def test_stdout_and_stderr_arrive_through_the_one_combined_stream(tmp_path):
    script = _script(
        tmp_path,
        "both_streams.py",
        """
        import sys
        sys.stdout.write("FROM-STDOUT\\n")
        sys.stdout.flush()
        sys.stderr.write("FROM-STDERR\\n")
        sys.stderr.flush()
        """,
    )

    execution = _run(tmp_path, script)
    text = execution.output_bytes.decode("utf-8")

    assert "FROM-STDOUT" in text
    assert "FROM-STDERR" in text


def test_no_shell_is_spawned(tmp_path, monkeypatch):
    seen = {}
    real_popen = subprocess.Popen

    def recording(argv, **kwargs):
        seen.update(kwargs)
        seen["argv"] = argv
        return real_popen(argv, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", recording)

    script = _script(tmp_path, "ok.py", "import sys\nsys.stdout.write('ok')\n")
    _run(tmp_path, script)

    assert seen["shell"] is False
    assert seen["stdin"] is subprocess.DEVNULL
    assert seen["stderr"] is subprocess.STDOUT
    assert isinstance(seen["argv"], tuple)


def test_exactly_one_child_is_started_and_nothing_is_retried(tmp_path, monkeypatch):
    starts = []
    real_popen = subprocess.Popen

    def counting(argv, **kwargs):
        starts.append(argv)
        return real_popen(argv, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", counting)

    script = _script(tmp_path, "fail.py", "import sys\nsys.exit(7)\n")
    execution = _run(tmp_path, script)

    assert len(starts) == 1
    assert execution.return_code == 7
    assert execution.passed is False


def test_a_launch_failure_is_reported_as_such(tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("cannot start")

    monkeypatch.setattr(subprocess, "Popen", boom)

    with pytest.raises(VerificationLaunchError):
        run_configured_verification(
            executable=sys.executable,
            args=["-c", "pass"],
            cwd=str(_workspace(tmp_path)),
            timeout_seconds=10,
            max_output_bytes=1000,
        )


# =============================================================================
# 5. Outcomes and bounds
# =============================================================================


def test_return_code_zero_passes(tmp_path):
    script = _script(tmp_path, "pass.py", "import sys\nsys.stdout.write('all good')\n")

    execution = _run(tmp_path, script)

    assert execution.return_code == 0
    assert execution.completed is True
    assert execution.passed is True
    assert execution.output_complete is True


def test_a_nonzero_return_code_is_a_valid_outcome_not_an_exception(tmp_path):
    script = _script(
        tmp_path,
        "fail.py",
        """
        import sys
        sys.stdout.write("1 failed, 3 passed\\n")
        sys.exit(1)
        """,
    )

    execution = _run(tmp_path, script)

    assert execution.return_code == 1
    assert execution.completed is True
    assert execution.passed is False
    assert b"1 failed" in execution.output_bytes


def test_a_timeout_kills_the_child_and_reports_no_return_code(tmp_path):
    script = _script(
        tmp_path,
        "hang.py",
        """
        import time
        time.sleep(120)
        """,
    )

    execution = _run(tmp_path, script, timeout=1)

    assert execution.timed_out is True
    assert execution.completed is False
    assert execution.return_code is None
    assert execution.passed is False


def test_output_overflow_kills_the_child_and_marks_the_output_incomplete(tmp_path):
    script = _script(
        tmp_path,
        "flood.py",
        """
        import sys
        chunk = "x" * 4096
        for _ in range(4000):
            sys.stdout.write(chunk)
        """,
    )

    execution = _run(tmp_path, script, cap=5_000)

    assert execution.output_limit_exceeded is True
    assert execution.completed is False
    assert execution.return_code is None
    assert execution.passed is False
    assert execution.output_complete is False
    # Since FU2 the retained output is exactly the cap: the over-limit bytes of
    # the read that tripped it are dropped rather than held.
    assert len(execution.output_bytes) == 5_000


# -----------------------------------------------------------------------------
# Phase 5F2D-FU2: the cap is enforced when it is passed, not when a buffer fills
# -----------------------------------------------------------------------------
#
# The reader used `stream.read(64 * 1024)` and tested the cap only after that
# call returned. `BufferedReader.read(n)` blocks until it has n bytes or reaches
# EOF, so a child that emitted MORE than the cap and then stopped writing was not
# detected — the read sat waiting for a 64 KiB buffer that would never fill.
# Measured directly against a real Windows pipe with a child that wrote 5001
# bytes and slept 30s: read(65536) returned after 30.1s (only once the child
# exited), read1(5001) returned after 0.078s.
#
# The existing flood regression does not catch this: it writes megabytes, so the
# 64 KiB request fills immediately. This is a different failure shape.


def test_output_just_past_the_cap_is_detected_without_waiting_for_the_timeout(
    tmp_path,
):
    """The FU2 regression: cap + 1 bytes, flushed, then a long hang."""
    cap = 5_000
    body = """
        import sys, time
        sys.stdout.buffer.write(b"z" * 5001)
        sys.stdout.buffer.flush()
        # Far longer than the configured timeout, and longer than this test may
        # take. The runner must not wait for it.
        time.sleep(120)
    """
    script = _script(tmp_path, "just_past_cap.py", body)

    configured_timeout = 20
    started = time.monotonic()
    execution = _run(tmp_path, script, timeout=configured_timeout, cap=cap)
    elapsed = time.monotonic() - started

    # Returned because of the cap, not because the timeout eventually fired.
    assert elapsed < 10.0, elapsed
    assert execution.output_limit_exceeded is True
    assert execution.timed_out is False
    assert execution.completed is False
    assert execution.passed is False
    assert execution.return_code is None
    assert execution.output_complete is False

    # The over-limit byte is never retained.
    assert len(execution.output_bytes) <= cap


def test_the_cap_is_exact_and_the_over_limit_bytes_are_dropped(tmp_path):
    cap = 5_000
    body = """
        import sys, time
        sys.stdout.buffer.write(b"z" * 5001)
        sys.stdout.buffer.flush()
        time.sleep(120)
    """
    script = _script(tmp_path, "just_past_cap2.py", body)

    execution = _run(tmp_path, script, timeout=20, cap=cap)

    assert execution.output_limit_exceeded is True
    # Exactly the cap is kept: not the whole over-limit read, and not a whole
    # discarded chunk either.
    assert len(execution.output_bytes) == cap
    assert execution.output_bytes == b"z" * cap


def test_output_exactly_at_the_cap_is_not_an_overflow(tmp_path):
    """The boundary is `> cap`, not `>= cap`."""
    cap = 5_000
    body = """
        import sys
        sys.stdout.buffer.write(b"z" * 5000)
        sys.stdout.buffer.flush()
    """
    script = _script(tmp_path, "exactly_cap.py", body)

    execution = _run(tmp_path, script, timeout=20, cap=cap)

    assert execution.output_limit_exceeded is False
    assert execution.timed_out is False
    assert execution.completed is True
    assert execution.output_complete is True
    assert execution.return_code == 0
    assert len(execution.output_bytes) == cap


def test_an_overflow_kill_is_reported_as_a_kill(tmp_path):
    """`direct_child_killed` means AIDO killed the direct child — from any bound.

    The overflow kill happens on the reader thread; the field used to be
    populated only from the main thread's timeout branch, so an ordinary
    `output_limit_exceeded` run reported `direct_child_killed: false` while
    having actually killed the child.
    """
    cap = 5_000
    body = """
        import sys, time
        sys.stdout.buffer.write(b"z" * 5001)
        sys.stdout.buffer.flush()
        time.sleep(120)
    """
    script = _script(tmp_path, "overflow_then_hang.py", body)

    execution = _run(tmp_path, script, timeout=20, cap=cap)

    assert execution.output_limit_exceeded is True
    assert execution.timed_out is False
    # The child was sleeping for 120s, so it was certainly still alive and the
    # kill certainly happened.
    assert execution.direct_child_killed is True


def test_a_child_that_exited_on_its_own_is_not_reported_as_killed(tmp_path):
    """The field stays honest in the other direction too."""
    script = _script(tmp_path, "quick_pass.py", "import sys\nsys.stdout.write('ok')\n")

    execution = _run(tmp_path, script)

    assert execution.completed is True
    assert execution.timed_out is False
    assert execution.output_limit_exceeded is False
    assert execution.direct_child_killed is False


def test_snapshot_can_never_observe_an_overflow_without_its_kill():
    """Deterministic atomicity proof: the kill and its record are one section.

    The kill used to run *outside* the reader's lock, publishing ``_killed``
    afterwards. That left a real window — reader kills, main thread times out,
    the main thread's own kill finds the child already dead and returns
    ``False``, and a ``snapshot`` taken before the reader published reported
    ``direct_child_killed: false`` for a run in which AIDO really did kill.

    Forcing that window here with a process whose ``kill()`` blocks: while the
    kill is in flight the reader must be holding the lock, so ``snapshot`` cannot
    complete at all — which is exactly what makes the split state unobservable.
    """
    kill_entered = threading.Event()
    release_kill = threading.Event()

    class _PausingStream:
        def __init__(self, payload: bytes) -> None:
            self._payload = payload
            self._sent = False

        def read1(self, size: int) -> bytes:
            if self._sent:
                return b""
            self._sent = True
            return self._payload[:size]

        def close(self) -> None:
            pass

    class _PausingProcess:
        def __init__(self) -> None:
            self.stdout = _PausingStream(b"x" * 11)
            self._alive = True
            self.kill_calls = 0

        def poll(self):
            return None if self._alive else 0

        def kill(self) -> None:
            self.kill_calls += 1
            self._alive = False
            kill_entered.set()
            # Stay inside kill(), and therefore inside the reader's critical
            # section, until this test releases it.
            assert release_kill.wait(10)

    process = _PausingProcess()
    reader = runner_module._BoundedOutputReader(process, max_output_bytes=10)
    reader.start()

    assert kill_entered.wait(10), "the reader never reached its overflow kill"

    captured: list = []
    watcher = threading.Thread(
        target=lambda: captured.append(reader.snapshot()), daemon=True
    )
    watcher.start()
    watcher.join(0.5)
    assert watcher.is_alive(), "snapshot() observed the reader mid-kill"
    assert captured == []

    release_kill.set()
    watcher.join(10)
    assert not watcher.is_alive()

    output, overflowed, killed = captured[0]
    assert output == b"x" * 10
    assert overflowed is True
    assert killed is True
    assert process.kill_calls == 1

    assert reader.finished.wait(10)


def test_a_reader_kill_is_never_lost_when_the_timeout_also_fires(
    tmp_path, monkeypatch
):
    """The full reported race, forced end to end against a real child process.

    The reader's overflow kill is held well past the configured deadline, so the
    main thread times out and its own kill finds the child already dead and
    returns ``False``. The invocation must still report that AIDO killed the
    direct child, because it did.
    """
    cap = 5_000
    body = """
        import sys, time
        sys.stdout.buffer.write(b"z" * 5001)
        sys.stdout.buffer.flush()
        time.sleep(120)
    """
    script = _script(tmp_path, "overflow_race.py", body)

    real_kill = runner_module._kill_quietly
    reader_killed = threading.Event()

    def instrumented(process):
        result = real_kill(process)
        if result and not reader_killed.is_set():
            # This is the reader's overflow kill. Hold here past the configured
            # deadline so the timeout branch runs while it is still in flight.
            reader_killed.set()
            time.sleep(2.0)
        return result

    monkeypatch.setattr(runner_module, "_kill_quietly", instrumented)

    execution = _run(tmp_path, script, timeout=1, cap=cap)

    # A kill really was sent by the reader...
    assert reader_killed.is_set()
    # ...the overlap really happened...
    assert execution.output_limit_exceeded is True
    assert execution.timed_out is True
    # ...and the result says so. Before the fix this was False.
    assert execution.direct_child_killed is True

    # Nothing else moved: still one launch, still the exact cap, still no retry.
    assert execution.completed is False
    assert execution.passed is False
    assert execution.return_code is None
    assert len(execution.output_bytes) == cap


def test_an_overflow_kill_does_not_claim_descendants_were_killed(tmp_path):
    """One kill, to the direct child. Nothing is said about a process tree."""
    cap = 5_000
    body = """
        import sys, time
        sys.stdout.buffer.write(b"z" * 5001)
        sys.stdout.buffer.flush()
        time.sleep(120)
    """
    script = _script(tmp_path, "overflow_then_hang2.py", body)

    execution = _run(tmp_path, script, timeout=20, cap=cap)

    assert execution.direct_child_killed is True
    # There is no descendant-facing field on the execution record at all.
    assert not hasattr(execution, "descendants_killed")
    assert not hasattr(execution, "process_tree_terminated")


def test_the_cap_regression_starts_one_process_and_never_retries(tmp_path):
    cap = 5_000
    body = """
        import sys, time
        sys.stdout.buffer.write(b"z" * 5001)
        sys.stdout.buffer.flush()
        time.sleep(120)
    """
    script = _script(tmp_path, "just_past_cap3.py", body)

    starts: list[tuple] = []
    real_popen = subprocess.Popen

    def counting(argv, **kwargs):
        starts.append(tuple(argv))
        return real_popen(argv, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(subprocess, "Popen", counting)
        execution = _run(tmp_path, script, timeout=20, cap=cap)

    assert len(starts) == 1
    assert execution.output_limit_exceeded is True


def test_the_reader_never_waits_for_a_fixed_size_buffer_to_fill():
    """The strategy is a bounded one-read request, not a fixed-size fill.

    Asserted against the **read loop's own code**, not the module text: the
    class docstring quotes the old `read(64 * 1024)` call and names the
    frameworks that were not adopted, so a whole-file scan would be measuring
    the documentation rather than the implementation.
    """
    import inspect

    body = inspect.getsource(runner_module._BoundedOutputReader._run)

    # Exactly one read primitive, and it is the one-underlying-read kind.
    assert ".read1(" in body
    assert ".read(" not in body.replace(".read1(", "")
    # Bounded by the remaining allowance plus a single sentinel byte.
    assert "remaining + 1" in body
    assert "_MAX_READ_REQUEST_BYTES" in body
    # The old fixed-size chunk constant is gone from the module entirely.
    assert not hasattr(runner_module, "_READ_CHUNK_BYTES")


def test_no_streaming_or_polling_framework_was_adopted():
    """Checked against imports, not prose — the docstring names these to deny them."""
    import ast

    tree = ast.parse(Path(runner_module.__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    for forbidden in ("asyncio", "selectors", "select", "fcntl", "msvcrt", "psutil"):
        assert forbidden not in imported, forbidden

    body = inspect_source_of_reader()
    for forbidden in ("O_NONBLOCK", "setblocking", "poll(", "epoll"):
        assert forbidden not in body, forbidden


def inspect_source_of_reader() -> str:
    import inspect

    return inspect.getsource(runner_module._BoundedOutputReader._run)


def test_a_run_that_exits_zero_after_a_timeout_kill_still_does_not_pass(tmp_path):
    """`passed` requires finishing on its own terms, not merely a zero status."""
    script = _script(tmp_path, "hang2.py", "import time\ntime.sleep(120)\n")

    execution = _run(tmp_path, script, timeout=1)

    assert execution.passed is False


# =============================================================================
# 5b. Phase 5F2D-FU1: the timeout bounds AIDO's wait, not the child's life
# =============================================================================
#
# The original 5F2D runner read the pipe on the main thread and relied on a
# `threading.Timer` that killed the direct child at the deadline. That is not a
# bound: the direct child is explicitly permitted to spawn descendants, and a
# descendant launched with inherited standard handles holds the WRITE end of the
# same pipe. Killing or exiting the direct parent does not close the descendant's
# handle, so the main thread stayed blocked in `read()` until the descendant let
# go. Measured against the old algorithm: a 0.5s timeout with a ~4s descendant
# returned after ~4s.
#
# These tests exercise the real Windows process/pipe semantics the product uses.
# Nothing here is monkeypatched.


# The descendant holds the inherited pipe until a sentinel file appears, up to a
# hard cap far longer than any timeout under test. It signals its own exit so the
# test can join it rather than leaving a stray process behind.
_DESCENDANT_BODY = """
    import os, sys, time
    stop = sys.argv[1]
    done = sys.argv[2]
    deadline = time.time() + 60
    while time.time() < deadline:
        if os.path.exists(stop):
            break
        time.sleep(0.05)
    sys.stdout.write("DESCENDANT-EXITING\\n")
    sys.stdout.flush()
    open(done, "w", encoding="utf-8").write("done")
"""

# The direct verification child spawns that descendant with INHERITED standard
# handles (stdout=None is inheritance), then exits immediately itself.
_PARENT_SPAWNS_DESCENDANT_BODY = """
    import subprocess, sys
    subprocess.Popen([sys.executable, sys.argv[1], sys.argv[2], sys.argv[3]])
    sys.stdout.write("PARENT-EXITING\\n")
    sys.stdout.flush()
    sys.exit(0)
"""


def _join_descendant(stop: Path, done: Path) -> None:
    """Release the synthetic descendant and wait for it, so pytest stays clean."""
    stop.write_text("stop", encoding="utf-8")
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if done.exists():
            return
        time.sleep(0.05)
    raise AssertionError("the synthetic descendant did not exit during cleanup")


def test_a_descendant_holding_the_inherited_pipe_cannot_block_aido_past_the_deadline(
    tmp_path,
):
    """The FU1 regression. A real descendant, a real inherited pipe, real timing."""
    stop = tmp_path / "stop.txt"
    done = tmp_path / "descendant_done.txt"
    descendant = _script(tmp_path, "descendant.py", _DESCENDANT_BODY)
    parent = _script(tmp_path, "spawns_descendant.py", _PARENT_SPAWNS_DESCENDANT_BODY)

    timeout_seconds = 1
    started = time.monotonic()
    try:
        execution = _run(
            tmp_path,
            parent,
            timeout=timeout_seconds,
            extra=(str(descendant), str(stop), str(done)),
        )
        elapsed = time.monotonic() - started

        # The descendant is still alive and still holds the pipe. Before FU1 this
        # returned only when the descendant let go, tens of seconds later.
        assert not done.exists(), "the descendant exited early; the test is not valid"
        assert elapsed < timeout_seconds + 4.0, elapsed

        assert execution.timed_out is True
        assert execution.completed is False
        assert execution.passed is False
        assert execution.return_code is None
        assert execution.output_complete is False
    finally:
        _join_descendant(stop, done)


def test_that_regression_starts_exactly_one_process_and_never_retries(tmp_path):
    stop = tmp_path / "stop.txt"
    done = tmp_path / "descendant_done.txt"
    descendant = _script(tmp_path, "descendant.py", _DESCENDANT_BODY)
    parent = _script(tmp_path, "spawns_descendant.py", _PARENT_SPAWNS_DESCENDANT_BODY)

    starts: list[tuple] = []
    real_popen = subprocess.Popen

    def counting(argv, **kwargs):
        starts.append(tuple(argv))
        return real_popen(argv, **kwargs)

    try:
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(subprocess, "Popen", counting)
            execution = _run(
                tmp_path,
                parent,
                timeout=1,
                extra=(str(descendant), str(stop), str(done)),
            )

        # AIDO launched the configured command once. The second process in
        # existence was started by the child itself, not by AIDO.
        assert len(starts) == 1
        assert execution.timed_out is True
    finally:
        _join_descendant(stop, done)


def test_a_timeout_kills_the_direct_child_and_claims_nothing_about_descendants(
    tmp_path,
):
    stop = tmp_path / "stop.txt"
    done = tmp_path / "descendant_done.txt"
    descendant = _script(tmp_path, "descendant.py", _DESCENDANT_BODY)
    parent = _script(tmp_path, "spawns_descendant.py", _PARENT_SPAWNS_DESCENDANT_BODY)

    try:
        execution = _run(
            tmp_path,
            parent,
            timeout=1,
            extra=(str(descendant), str(stop), str(done)),
        )

        # The descendant is demonstrably still running: the runner made no claim
        # to have stopped it, and did not.
        assert done.exists() is False
        assert execution.timed_out is True
        # The field records exactly what was done — one kill, to the direct
        # child — and nothing about the process tree.
        assert isinstance(execution.direct_child_killed, bool)
    finally:
        _join_descendant(stop, done)


def test_the_wait_bound_contract_names_the_reap_grace_explicitly():
    """FU2: the configured timeout is not the whole worst-case wait, and says so."""
    assert runner_module.DIRECT_CHILD_REAP_GRACE_SECONDS > 0

    policy = runner_module.WAIT_BOUND_POLICY
    assert "configured timeout bounds the execution" in policy
    assert "reap grace" in policy
    assert "never waits for descendants" in policy
    # The grace applies to the direct child's handle only.
    source = Path(runner_module.__file__).read_text(encoding="utf-8")
    assert "process.wait(timeout=DIRECT_CHILD_REAP_GRACE_SECONDS)" in source


def test_the_abandoned_reader_lifetime_is_documented_as_unbounded():
    """FU2: 'a bounded, known cost' overstated it, and the claim is corrected.

    The old phrase is still quoted in the docstring as history — that is
    deliberate — so what is asserted is the corrected *current* statement.
    """
    doc = runner_module._BoundedOutputReader.__doc__ or ""

    assert "abandoned reader's own lifetime is not bounded" in doc.lower()
    assert "residual limitation" in doc
    assert "indefinitely" in doc
    # And the correction is attributed rather than silently applied.
    assert "conflated" in doc


def test_the_runner_never_enumerates_or_manages_a_process_tree():
    """No process-tree framework was added, only a bounded wait."""
    source = Path(runner_module.__file__).read_text(encoding="utf-8")

    for forbidden in (
        "taskkill",
        "TerminateJobObject",
        "CREATE_NEW_PROCESS_GROUP",
        "psutil",
        "os.killpg",
        "setsid",
        "start_new_session",
        "job object",
        "children(",
    ):
        assert forbidden not in source, forbidden

    # The bounded reader is private: there is no public supervisor.
    assert not hasattr(runner_module, "BoundedOutputReader")
    assert "_BoundedOutputReader" not in runner_module.__all__ if hasattr(
        runner_module, "__all__"
    ) else True


# =============================================================================
# 6. Decoding
# =============================================================================


def test_output_is_decoded_for_humans_and_never_refused(tmp_path):
    text, replaced = decode_verification_output(b"ok \xff\xfe not utf-8")

    assert "ok" in text
    assert replaced is True


def test_clean_utf8_decodes_without_replacement():
    text, replaced = decode_verification_output("héllo".encode("utf-8"))

    assert text == "héllo"
    assert replaced is False
