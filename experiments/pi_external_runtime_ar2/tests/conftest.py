"""Shared fixtures for the AR2 offline suite.

Rules this suite obeys, without exception:

- NO network, NO socket, NO model call, NO API key needed.
- Every repository is synthetic, created under a FRESH root AIDO's own
  ``ar2.fixtures.create_disposable_experiment_root`` mints (system temp, never
  under a caller-chosen or pre-existing directory -- 5F3A-AR2-FU1A).
- The "Pi process" is a synthetic JSONL-emitting Python script under ``tmp_path``.
  The real Pi binary is never launched by a test.
- Local Windows named pipes ARE used, because that is the mechanism under test.
  Every pipe handle is closed and every thread is joined before the suite exits.

A green suite must leave no AR2-owned background process, task or thread that is
still expected to be doing work. :func:`assert_no_ar2_threads` is the check, and
the session-scoped autouse fixture at the bottom enforces it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_EXPERIMENT_DIR = _HERE.parent
_REPO_SRC = _EXPERIMENT_DIR.parents[1] / "src"

for path in (str(_REPO_SRC), str(_EXPERIMENT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)


FAKE_PI_SOURCE = '''\
"""Synthetic stand-in for a Pi RPC process. Test-only. Emits JSONL on stdout."""
import json
import sys
import time

script = json.load(open(sys.argv[1], encoding="utf-8"))
out = sys.stdout.buffer


def emit_chunks(chunks):
    for chunk in chunks:
        out.write(chunk.encode("utf-8"))
        out.flush()


emit_chunks(script.get("startup_chunks", []))
if script.get("exit_immediately"):
    sys.exit(script.get("exit_code", 0))

responses = script.get("responses", {})
log_path = script.get("command_log")
while True:
    line = sys.stdin.buffer.readline()
    if not line:
        sys.exit(script.get("exit_code", 0))
    try:
        command = json.loads(line.decode("utf-8").rstrip("\\r\\n"))
    except Exception:
        continue
    kind = command.get("type")
    if log_path:
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(str(kind) + "\\n")
    entry = responses.get(kind)
    if entry is not None:
        payload = {
            "type": "response",
            "command": kind,
            "success": entry.get("success", True),
        }
        if command.get("id") is not None:
            payload["id"] = command["id"]
        if "data" in entry:
            payload["data"] = entry["data"]
        out.write((json.dumps(payload) + "\\n").encode("utf-8"))
        out.flush()
    if kind == "prompt":
        emit_chunks(script.get("prompt_chunks", []))
'''


@pytest.fixture()
def fake_pi(tmp_path: Path):
    """A factory that builds argv for a synthetic Pi process. Never the real Pi."""
    script_path = tmp_path / "fake_pi.py"
    script_path.write_text(FAKE_PI_SOURCE, encoding="utf-8")
    counter = {"n": 0}

    def _build(script: dict) -> tuple[str, ...]:
        counter["n"] += 1
        config_path = tmp_path / f"fake_pi_script_{counter['n']}.json"
        config_path.write_text(json.dumps(script), encoding="utf-8")
        return (sys.executable, str(script_path), str(config_path))

    return _build


@pytest.fixture(scope="session")
def git_executable() -> str:
    found = shutil.which("git")
    if not found:  # pragma: no cover - environment dependent
        pytest.skip("git is not available")
    return os.path.realpath(found)


@pytest.fixture(scope="session")
def node_executable() -> str:
    found = shutil.which("node")
    if not found:  # pragma: no cover - environment dependent
        pytest.skip("node is not available")
    return os.path.realpath(found)


@pytest.fixture()
def r1_repo(git_executable: str):
    """A built R1 fixture under a FRESH AIDO-created root. Synthetic, disposable.

    The root now lives under the system temp directory (never under pytest's
    own ``tmp_path``, since authority may only originate from
    ``create_disposable_experiment_root`` -- FU1A), so this fixture cleans up
    after itself explicitly rather than relying on pytest's ``tmp_path`` reaper.
    """
    from ar2.fixtures import R1, build_case_repository, remove_disposable_tree

    built = build_case_repository(R1, git_executable=git_executable)
    yield built
    remove_disposable_tree(built.experiment_root)


@pytest.fixture()
def r2_repo(git_executable: str):
    from ar2.fixtures import R2, build_case_repository, remove_disposable_tree

    built = build_case_repository(R2, git_executable=git_executable)
    yield built
    remove_disposable_tree(built.experiment_root)


def tracked_manifest(git_executable: str, repo_root: str) -> tuple[str, ...]:
    """The mint-time manifest, from the ACCEPTED fixed ``ls_files_stage`` operation."""
    from ai_dev_orchestrator.workspace.git_adapter import (
        parse_ls_files_stage,
        run_fixed_git_operation,
    )

    result = run_fixed_git_operation(
        "ls_files_stage", git_executable=git_executable, workspace_root=repo_root
    )
    return tuple(sorted(entry.path for entry in parse_ls_files_stage(result.stdout)))


def mint_for(case, git_executable: str, built_fixture):
    """Mint the SED for one built case fixture.

    5F3A-AR2-FU1A: consumes ``built_fixture.authority`` -- produced ONCE, at
    creation time, by ``create_disposable_experiment_root`` /
    ``build_case_repository`` / ``build_synthetic_repository`` -- rather than
    reconstructing or retroactively stamping authority from a bare path. There
    is no function anywhere in this experiment, production or test, that can
    convert an arbitrary pre-existing directory into an authorized one.
    """
    from ar2.capability import CapDefinitions, mint_capability

    return mint_capability(
        authority=built_fixture.authority,
        tracked_manifest=tracked_manifest(git_executable, built_fixture.repo_root),
        protected_patterns=case.protected_patterns,
        verification_witness_paths=case.verification_witness_paths,
        caps=CapDefinitions(),
    )


@pytest.fixture()
def custom_repo(git_executable: str):
    """Factory fixture: ``custom_repo(files, case_id="test") -> BuiltFixture``.

    THE sanctioned way for a test to get a CUSTOM synthetic repository -- a
    shape R1-R4 does not cover. It creates a FRESH, authorized synthetic
    experiment root first (exactly like the case builders), then places
    ``files`` inside that OWNED root and commits them. Every root it builds is
    removed when the test ends.

    There is no ``stamp_this_existing_directory_as_disposable()`` under any
    name here or anywhere else in this experiment (5F3A-AR2-FU1A). A test that
    already built a repository some other way (e.g. by hand with
    ``subprocess``) cannot retroactively authorize it -- it must be built
    through this fixture, or through ``build_case_repository``, from the start.
    """
    from ar2.fixtures import build_synthetic_repository, remove_disposable_tree

    built_roots: list[str] = []

    def _build(files: dict[str, "str | bytes"], *, case_id: str = "test"):
        built = build_synthetic_repository(files, case_id=case_id, git_executable=git_executable)
        built_roots.append(built.experiment_root)
        return built

    yield _build
    for root in built_roots:
        remove_disposable_tree(root)


def run_git(git_exe: str, args: list[str], cwd: str) -> str:
    """Test-only mutation helper for building adversarial repository states."""
    completed = subprocess.run(
        [git_exe, "-c", "user.name=T", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd,
        capture_output=True,
        check=True,
    )
    return completed.stdout.decode("utf-8", "replace")


def ar2_threads() -> list[str]:
    """Names of live threads this experiment owns."""
    return [
        thread.name
        for thread in threading.enumerate()
        if thread.name.startswith("ar2-") and thread.is_alive()
    ]


@pytest.fixture(autouse=True)
def _no_leaked_ar2_threads():
    """Every test must join or terminate every AR2 worker it started."""
    yield
    leaked = ar2_threads()
    assert not leaked, f"AR2-owned threads are still alive after the test: {leaked}"


def pytest_sessionfinish(session, exitstatus):
    """Session-level proof that a green suite leaves no AR2 worker running.

    Printed unconditionally so the fact is evidence rather than an assumption,
    and turned into a failure if anything AR2 owns is still alive.
    """
    survivors = ar2_threads()
    alive = sorted(t.name for t in threading.enumerate() if t.is_alive())
    print(
        "\n[ar2] session finish: ar2-owned threads still alive = "
        f"{survivors or 'none'}; all live threads = {alive}"
    )
    if survivors:  # pragma: no cover - a failure path by construction
        session.exitstatus = 1
        raise RuntimeError(f"AR2-owned threads survived the suite: {survivors}")
