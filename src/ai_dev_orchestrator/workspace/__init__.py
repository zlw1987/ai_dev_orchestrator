"""Workspace policy package.

Phase 1 contributed the pure, lexical path policy. Phase 5D0 added the
**library-only** canonical path guard — the on-disk second gate designed in
§6.4 of ``docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md``. Neither is wired
into any command, and no shipped code path reads a target workspace.
"""

from ai_dev_orchestrator.workspace.canonical import (
    CanonicalPathAmbiguityError,
    CanonicalPathContainmentError,
    CanonicalPathError,
    CanonicalPathInputError,
    CanonicalPathResolutionError,
    CanonicalPathSymlinkError,
    CanonicalWorkspacePath,
    canonicalize_existing_path_under_workspace,
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
    "CanonicalWorkspacePath",
    "PathClassification",
    "PathDecision",
    "PathPolicy",
    "PathPolicyError",
    "canonicalize_existing_path_under_workspace",
]
