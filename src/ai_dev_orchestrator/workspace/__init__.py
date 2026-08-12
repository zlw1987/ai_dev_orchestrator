"""Workspace policy package.

Phase 1 contributed the pure, lexical path policy. Phase 5D0 added the
**library-only** canonical path guard — the on-disk second gate designed in
§6.4 of ``docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md``. Phase 5F2B added its
create-aware write-target counterpart from §26.3, which is **also library
only**: it has no caller, and it writes nothing and creates nothing.
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
from ai_dev_orchestrator.workspace.path_policy import (
    PathClassification,
    PathDecision,
    PathPolicy,
    PathPolicyError,
)

__all__ = [
    "CanonicalPathAmbiguityError",
    "CanonicalPathContainmentError",
    "CanonicalPathError",
    "CanonicalPathInputError",
    "CanonicalPathResolutionError",
    "CanonicalPathSymlinkError",
    "CanonicalPathWriteTargetError",
    "CanonicalWorkspacePath",
    "CanonicalWriteTarget",
    "PathClassification",
    "PathDecision",
    "PathPolicy",
    "PathPolicyError",
    "canonicalize_existing_path_under_workspace",
    "canonicalize_write_target_under_workspace",
]
