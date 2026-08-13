"""Workspace policy package.

Phase 1 contributed the pure, lexical path policy. Phase 5D0 added the
**library-only** canonical path guard — the on-disk second gate designed in
§6.4 of ``docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md``. Phase 5F2B added its
create-aware write-target counterpart from §26.3, which is **also library
only**: it writes nothing and creates nothing.

Phase 5F2C added :mod:`ai_dev_orchestrator.workspace.git_adapter`, a **fixed**
Git inspection adapter, corrected by 5F2C-FU1. It is not command execution: the
executable is resolved to one **absolute path** and pinned for the run (never the
bare name ``"git"``, and refused if it lives inside the target workspace), every
argv is assembled there from a closed set of constants, ``shell=False`` always,
the environment is a minimal allowlist rather than a copy of this process's,
output is bounded during capture, and the only variable component in the whole
module is one already-validated repo-relative path passed after ``--``. Every
operation in the set is read-only — there is no ``add``, ``commit``,
``checkout``, ``restore``, ``reset``, ``branch``, ``fetch`` or ``push``, and no
network operation of any kind. A repository whose effective Git configuration
could make Git execute a program is **refused** before any content-reading
operation runs.

That adapter is AIDO-owned repository *inspection*. Phase 5F2D's controlled
verification — :mod:`ai_dev_orchestrator.verification` — is a deliberately
separate thing: explicitly authorized execution of **repository-controlled**
code. The two are not blurred together, and neither module is a general process
executor.
"""

from ai_dev_orchestrator.workspace.canonical import (
    CanonicalPathAmbiguityError,
    CanonicalPathContainmentError,
    CanonicalPathError,
    CanonicalPathInputError,
    CanonicalPathResolutionError,
    CanonicalPathSymlinkError,
    CanonicalPathWriteTargetError,
    CanonicalWorkspacePath,
    CanonicalWriteTarget,
    canonicalize_existing_path_under_workspace,
    canonicalize_write_target_under_workspace,
)
from ai_dev_orchestrator.workspace.git_adapter import (
    CONTENT_READING_OPERATIONS,
    FIXED_GIT_OPERATIONS,
    GitAdapterError,
    GitExecutableError,
    GitIndexEntry,
    GitOperationNotAllowedError,
    GitResult,
    build_git_argv,
    find_unsupported_config_keys,
    ordered_preflight_operations,
    parse_config_name_only,
    parse_config_scoped_name_only,
    parse_ls_files_stage,
    parse_ls_files_verbose,
    parse_status_porcelain,
    resolve_git_executable,
    run_fixed_git_operation,
    status_record_path,
)
from ai_dev_orchestrator.workspace.path_policy import (
    PathClassification,
    PathDecision,
    PathPolicy,
    PathPolicyError,
)

__all__ = [
    "CONTENT_READING_OPERATIONS",
    "FIXED_GIT_OPERATIONS",
    "CanonicalPathAmbiguityError",
    "CanonicalPathContainmentError",
    "CanonicalPathError",
    "CanonicalPathInputError",
    "CanonicalPathResolutionError",
    "CanonicalPathSymlinkError",
    "CanonicalPathWriteTargetError",
    "CanonicalWorkspacePath",
    "CanonicalWriteTarget",
    "GitAdapterError",
    "GitExecutableError",
    "GitIndexEntry",
    "GitOperationNotAllowedError",
    "GitResult",
    "PathClassification",
    "PathDecision",
    "PathPolicy",
    "PathPolicyError",
    "build_git_argv",
    "canonicalize_existing_path_under_workspace",
    "canonicalize_write_target_under_workspace",
    "find_unsupported_config_keys",
    "ordered_preflight_operations",
    "parse_config_name_only",
    "parse_config_scoped_name_only",
    "parse_ls_files_stage",
    "parse_ls_files_verbose",
    "parse_status_porcelain",
    "resolve_git_executable",
    "run_fixed_git_operation",
    "status_record_path",
]
