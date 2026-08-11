"""File-edit **write gate** models and a strict parser (Phase 5F0).

Phase 5F0 types the explicit human approval that any future file-editing phase
would have to be handed before writing a single byte into a target workspace:
:class:`DiffEditApproval`, the
:class:`ApprovedDiffProposalArtifact` wrapper around an **untouched** Phase 5E2
``DiffProposalArtifact`` snapshot, and
:func:`parse_approved_diff_proposal_artifact`, a pure strict-JSON parser for
text it is handed.

This is a **second, separate** approval. Phase 5B's approval covers an *L1
plan*; this one covers the *concrete diff* generated from it, which the human
had not seen when they approved the plan. It is never inferred from the wrapped
plan approval, from a diff proposal existing or parsing, from
``requires_human_review``, from a file being present, from issue prose or an
``Automation Authorization`` heading, or from model output.

**Library only, wired into nothing.** Importing this package adds no command and
no option, performs no file read, no workspace access, no file edit, no diff
application, no apply-cleanliness check, no command execution, no GitHub fetch
or write, and no model, network, or environment access. There is no artifact
loader and no artifact writer, and nothing here stamps an approval.

**L2 is still not built**, and nothing here can invoke it. A parsed artifact is
data describing an approval — never permission to do anything, and specifically
never proof that a diff applies or authorization to commit, push, or open a PR.
"""

from ai_dev_orchestrator.file_editing.models import (
    APPROVED_DIFF_PROPOSAL_MODE,
    APPROVED_DIFF_PROPOSAL_SCHEMA_VERSION,
    REQUIRED_DIFF_EDIT_APPROVAL_TEXT,
    ApprovedDiffProposalArtifact,
    DiffEditApproval,
    FileEditingApprovalError,
    FileEditingApprovalParseError,
    FileEditingApprovalValidationError,
    parse_approved_diff_proposal_artifact,
)

__all__ = [
    "APPROVED_DIFF_PROPOSAL_MODE",
    "APPROVED_DIFF_PROPOSAL_SCHEMA_VERSION",
    "REQUIRED_DIFF_EDIT_APPROVAL_TEXT",
    "ApprovedDiffProposalArtifact",
    "DiffEditApproval",
    "FileEditingApprovalError",
    "FileEditingApprovalParseError",
    "FileEditingApprovalValidationError",
    "parse_approved_diff_proposal_artifact",
]
