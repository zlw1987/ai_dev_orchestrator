"""Shared fixtures for the O1 offline suite.

Rules this suite obeys, without exception (same rules as AR2's own suite):

- NO network, NO socket, NO model call, NO API key needed.
- Every repository is synthetic, created under a FRESH root via AR2's own
  ``ar2.fixtures.create_disposable_experiment_root`` / ``build_case_repository``
  (system temp, never under a caller-chosen or pre-existing directory).
- The real Pi binary is never launched by a test.
- A green suite must leave no AR2-owned background thread alive; the
  ``ar2-`` thread-name prefix is unchanged from AR2 (``ar2/supervisor.py``
  names its stderr-reader thread ``ar2-pi-stderr`` regardless of which
  experiment invokes it), so the SAME leak check applies here unmodified.

This suite imports ``ar2`` (from the sibling, frozen
``experiments/pi_external_runtime_ar2/`` directory) and ``o1`` (this
directory's own package). Nothing under ``ar2`` is modified by anything here.
"""

from __future__ import annotations

import os
import shutil
import sys
import threading
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_O1_DIR = _HERE.parent
_AR2_DIR = _O1_DIR.parent / "pi_external_runtime_ar2"
_REPO_SRC = _O1_DIR.parents[1] / "src"

for path in (str(_REPO_SRC), str(_AR2_DIR), str(_O1_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)


@pytest.fixture(scope="session")
def git_executable() -> str:
    found = shutil.which("git")
    if not found:  # pragma: no cover - environment dependent
        pytest.skip("git is not available")
    return os.path.realpath(found)


@pytest.fixture()
def o1_repo(git_executable: str):
    """The built O1 fixture under a FRESH AIDO-created root. Synthetic, disposable."""
    from ar2.fixtures import build_case_repository, remove_disposable_tree
    from o1.fixture import O1_CASE

    built = build_case_repository(O1_CASE, git_executable=git_executable)
    yield built
    remove_disposable_tree(built.experiment_root)


def tracked_manifest(git_executable: str, repo_root: str) -> tuple[str, ...]:
    from ai_dev_orchestrator.workspace.git_adapter import (
        parse_ls_files_stage,
        run_fixed_git_operation,
    )

    result = run_fixed_git_operation(
        "ls_files_stage", git_executable=git_executable, workspace_root=repo_root
    )
    return tuple(sorted(entry.path for entry in parse_ls_files_stage(result.stdout)))


def mint_for_o1(git_executable: str, built_fixture):
    """Mint the SED for the built O1 fixture, using AR2's unmodified mint_capability."""
    from ar2.capability import CapDefinitions, mint_capability
    from o1.fixture import O1_CASE

    return mint_capability(
        authority=built_fixture.authority,
        tracked_manifest=tracked_manifest(git_executable, built_fixture.repo_root),
        protected_patterns=O1_CASE.protected_patterns,
        verification_witness_paths=O1_CASE.verification_witness_paths,
        caps=CapDefinitions(),
    )


def ar2_threads() -> list[str]:
    return [
        thread.name
        for thread in threading.enumerate()
        if thread.name.startswith("ar2-") and thread.is_alive()
    ]


@pytest.fixture(autouse=True)
def _no_leaked_ar2_threads():
    yield
    leaked = ar2_threads()
    assert not leaked, f"AR2-owned threads are still alive after the test: {leaked}"


def pytest_sessionfinish(session, exitstatus):
    survivors = ar2_threads()
    alive = sorted(t.name for t in threading.enumerate() if t.is_alive())
    print(
        "\n[ar2-o1] session finish: ar2-owned threads still alive = "
        f"{survivors or 'none'}; all live threads = {alive}"
    )
    if survivors:  # pragma: no cover - a failure path by construction
        session.exitstatus = 1
        raise RuntimeError(f"AR2-owned threads survived the O1 suite: {survivors}")
