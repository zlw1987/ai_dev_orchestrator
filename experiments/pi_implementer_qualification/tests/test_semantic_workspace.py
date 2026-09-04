"""Offline tests for :mod:`qualification.semantic_workspace` (5F3B-Q1-PRE1).

The only subprocess activity here is local ``git`` -- the same fixture-
construction surface the rest of this package's offline suite already uses.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from qualification.corpus import IQ1_TASK, IQ2_TASK
from qualification.i2b_workspace import (
    QualificationRunWorkspace,
    claim_run_workspace,
    mint_qualification_run_workspace,
    remove_run_workspace,
)
from qualification.semantic_workspace import (
    SemanticTaskWorkspace,
    SemanticWorkspaceError,
    populate_semantic_task_workspace,
)


@pytest.fixture(scope="module")
def git_executable() -> str:
    """AIDO's OWN accepted Git resolution (5F3B-LIVE1-C1-P12a).

    The semantic attempt's fixture-population checkpoint requires EXACT
    STRING EQUALITY with ``resolve_git_executable``'s return value, so this
    fixture must BE that value -- never another spelling of the same target.
    """
    from ai_dev_orchestrator.workspace.git_adapter import resolve_git_executable

    exe = shutil.which("git")
    assert exe, "git must be on PATH to build synthetic fixtures"
    return resolve_git_executable(workspace_root=str(Path(__file__).resolve().parents[1]))


def test_populate_produces_a_valid_task_workspace(git_executable: str) -> None:
    ws = mint_qualification_run_workspace()
    try:
        built = populate_semantic_task_workspace(ws, IQ1_TASK, git_executable=git_executable)
        assert type(built) is SemanticTaskWorkspace
        assert built.task_id == "IQ-1"
        assert built.head_before
        assert "money/rounding.py" in built.tracked_paths
        assert built.repo_root == ws.workspace_root
    finally:
        remove_run_workspace(ws)


def test_populate_refuses_a_non_empty_workspace(git_executable: str) -> None:
    ws = mint_qualification_run_workspace()
    try:
        populate_semantic_task_workspace(ws, IQ1_TASK, git_executable=git_executable)
        with pytest.raises(SemanticWorkspaceError):
            populate_semantic_task_workspace(ws, IQ2_TASK, git_executable=git_executable)
    finally:
        remove_run_workspace(ws)


def test_populate_refuses_a_workspace_not_minted_by_this_package(git_executable: str) -> None:
    class _Forged:
        workspace_root = "C:\\nonexistent"
        experiment_root = "C:\\nonexistent"
        run_workspace_nonce = "forged"

    with pytest.raises(SemanticWorkspaceError):
        populate_semantic_task_workspace(_Forged(), IQ1_TASK, git_executable=git_executable)  # type: ignore[arg-type]


def test_semantic_task_workspace_is_valid_by_construction(git_executable: str) -> None:
    ws = mint_qualification_run_workspace()
    try:
        built = populate_semantic_task_workspace(ws, IQ1_TASK, git_executable=git_executable)
        with pytest.raises(SemanticWorkspaceError):
            SemanticTaskWorkspace(
                workspace=built.workspace,
                task_id="",
                task_revision=built.task_revision,
                head_before=built.head_before,
                tracked_paths=built.tracked_paths,
            )
    finally:
        remove_run_workspace(ws)
