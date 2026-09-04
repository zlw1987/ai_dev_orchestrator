"""Shared fixtures for the 5F3B-I1 offline suite.

Rules this suite obeys, without exception (the same rules AR2/O1 obey):

- NO network, NO socket, NO model call, NO API key needed, NO Pi launch.
- Every repository is synthetic, created under a FRESH root via AR2's own
  ``ar2.fixtures.create_disposable_experiment_root`` / ``build_case_repository``
  (system temp, never under a caller-chosen or pre-existing directory, and
  never under ``C:\\dev\\ai_dev_orchestrator`` or any sibling of it).
- The real Pi binary is never launched, and no broker/supervisor/handshake
  code from AR2 is invoked at all -- this package has no live runtime
  integration to exercise offline. Every "model run" this suite classifies
  is a plain Python fact structure fed to a pure policy function.
- A green suite leaves no thread or process behind (checked below).

This suite imports ``ar2`` (from the sibling, frozen
``experiments/pi_external_runtime_ar2/`` directory), the production
``ai_dev_orchestrator`` package (from ``src/``, read-only fixed Git
operations only), and ``qualification`` (this package). Nothing under
``ar2`` or ``src`` is modified by anything here.
"""

from __future__ import annotations

import shutil
import sys
import threading
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_PACKAGE_DIR = _HERE.parent
_AR2_DIR = _PACKAGE_DIR.parent / "pi_external_runtime_ar2"
_REPO_SRC = _PACKAGE_DIR.parents[1] / "src"

for _path in (str(_REPO_SRC), str(_AR2_DIR), str(_PACKAGE_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)


@pytest.fixture(scope="session")
def git_executable() -> str:
    """AIDO's OWN accepted Git resolution -- never a re-spelling of it.

    5F3B-LIVE1-C1-P12a. This used to return ``os.path.realpath(shutil.which(
    "git"))``. That is the same TARGET as
    ``ai_dev_orchestrator.workspace.git_adapter.resolve_git_executable``
    returns, but not necessarily the same STRING: on Windows ``realpath``
    normalises the extension's case, so the fixture handed the semantic
    attempt ``...\\git.exe`` while the accepted resolver returns
    ``...\\git.EXE``.

    The C1 fixture-population checkpoint requires EXACT STRING EQUALITY with
    the resolver's return value, deliberately -- an alias-tolerant comparison
    would let a DIFFERENT SPELLING reach the frozen controller's later
    consumers. So the suite is corrected to use the trusted resolution
    itself rather than the checkpoint being weakened to accept an alias.
    """
    from ai_dev_orchestrator.workspace.git_adapter import (
        GitExecutableError,
        resolve_git_executable,
    )

    if not shutil.which("git"):  # pragma: no cover - environment dependent
        pytest.skip("git is not available")
    try:
        return resolve_git_executable(workspace_root=str(_PACKAGE_DIR))
    except GitExecutableError:  # pragma: no cover - environment dependent
        pytest.skip("git could not be resolved by AIDO's own resolver")


def observed_changed_paths(*, git_executable: str, repo_root: str) -> frozenset[str]:
    """The Git-observed changed-path set, via the production fixed adapter."""
    from ai_dev_orchestrator.workspace.git_adapter import (
        parse_status_porcelain,
        run_fixed_git_operation,
        status_record_path,
    )

    result = run_fixed_git_operation(
        "status_porcelain", git_executable=git_executable, workspace_root=repo_root
    )
    records = parse_status_porcelain(result.stdout)
    return frozenset(status_record_path(record) for record in records)


def tracked_manifest(*, git_executable: str, repo_root: str) -> tuple[str, ...]:
    """The tracked-path set, via the production fixed adapter's ls-files-stage."""
    from ai_dev_orchestrator.workspace.git_adapter import (
        parse_ls_files_stage,
        run_fixed_git_operation,
    )

    result = run_fixed_git_operation(
        "ls_files_stage", git_executable=git_executable, workspace_root=repo_root
    )
    return tuple(sorted(entry.path for entry in parse_ls_files_stage(result.stdout)))


def rev_parse_head(*, git_executable: str, repo_root: str) -> str:
    from ai_dev_orchestrator.workspace.git_adapter import run_fixed_git_operation

    result = run_fixed_git_operation(
        "rev_parse_head", git_executable=git_executable, workspace_root=repo_root
    )
    return result.stdout.strip()


def _qualification_threads() -> list[str]:
    # This package spawns no threads of its own (no broker, no supervisor,
    # no Pi process). Any AR2-prefixed thread would mean a test accidentally
    # exercised live-runtime machinery this package must never touch.
    return [
        thread.name
        for thread in threading.enumerate()
        if thread.name.startswith("ar2-") and thread.is_alive()
    ]


@pytest.fixture(autouse=True)
def _no_leaked_threads():
    yield
    leaked = _qualification_threads()
    assert not leaked, f"unexpected AR2-owned threads still alive after the test: {leaked}"


def pytest_sessionfinish(session, exitstatus):
    survivors = _qualification_threads()
    if survivors:  # pragma: no cover - a failure path by construction
        session.exitstatus = 1
        raise RuntimeError(
            f"unexpected AR2-owned threads survived the 5F3B-I1 offline suite: {survivors}"
        )
