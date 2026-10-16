"""AIDO-observed workspace state for the live supervised path (ALPHA-P1B, D-6 / R-1).

D-6 requires the workspace and source state to be **independently verifiable at
the live consumption boundary**; an operator's clean-clone claim is not enough.
This module observes it with the **5F2C writer's exact read-only Git
preflight**, unchanged and imported rather than copied, so the source state a
proposal is built from is exactly the state the writer will later require:

- the Git worktree top level is exactly the canonical workspace root;
- no execution-capable or indirecting Git configuration is in effect (the
  filter gate runs before anything reads working-tree content);
- the index is simple and submodule-free, and holds the target once as an
  ordinary file blob;
- the working tree is **wholly clean**.

It then reads the exact HEAD object id with the fixed ``rev_parse_head``
operation. No Git operation is added to the fixed read-only set, nothing is
written, and the adapter's minimal child environment (no ``AIDO_*`` value)
is unchanged.

What it does not prove: Git-ignored files, anything outside the repository,
remote state, or an atomic snapshot. The live path brackets the in-process
read with two observations; it does not lock the tree.
"""

from __future__ import annotations

import re

from ai_dev_orchestrator.models import ProjectConfig
from ai_dev_orchestrator.supervised_implementer.models import SupervisedImplementerRefused

_OBJECT_ID = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")


def _refuse(category: str, message: str) -> SupervisedImplementerRefused:
    return SupervisedImplementerRefused(category, message)


def observe_clean_workspace_head(project: ProjectConfig, target_path: str) -> str:
    """Return the HEAD object id of a wholly clean workspace, or refuse.

    ``target_path`` must already have passed the P1A target checks.
    """
    from ai_dev_orchestrator.file_editing.writer import (
        WorkspaceWriteRefusedError,
        _run_git_preflight,
    )
    from ai_dev_orchestrator.workspace import (
        CanonicalPathError,
        GitAdapterError,
        canonicalize_write_target_under_workspace,
        resolve_git_executable,
        run_fixed_git_operation,
    )

    try:
        target = canonicalize_write_target_under_workspace(
            project.repo.workspace_path,
            target_path,
            change_type="modify",
            allow_symlinks=False,
        )
    except CanonicalPathError as exc:
        raise _refuse(
            "workspace_target_unresolvable",
            f"the target could not be proved to be an existing file inside the "
            f"workspace ({type(exc).__name__}). Nothing was sent.",
        ) from None
    workspace_root = target.resolved_workspace_root
    relative = target.relative_destination.replace("\\", "/")
    if relative != target_path:
        raise _refuse(
            "target_canonical_mismatch",
            f"{target_path!r} resolves to a different relative spelling on disk. "
            "Nothing was sent.",
        )
    try:
        git_executable = resolve_git_executable(workspace_root=workspace_root)
        _run_git_preflight(workspace_root, relative, git_executable=git_executable)
        head = run_fixed_git_operation(
            "rev_parse_head", git_executable=git_executable, workspace_root=workspace_root
        ).stdout.strip()
    except WorkspaceWriteRefusedError as exc:
        detail = str(exc).replace(" Nothing was written.", "")
        raise _refuse(
            "workspace_git_state_untrusted",
            f"AIDO could not prove a wholly clean, supported Git workspace: {detail} "
            "Nothing was sent.",
        ) from None
    except GitAdapterError as exc:
        raise _refuse(
            "workspace_git_state_untrusted",
            f"AIDO's read-only Git inspection failed ({type(exc).__name__}). "
            "Nothing was sent.",
        ) from None
    if not _OBJECT_ID.fullmatch(head):
        raise _refuse(
            "workspace_git_state_untrusted",
            "the workspace has no resolvable HEAD commit to bind. Nothing was sent.",
        )
    return head
