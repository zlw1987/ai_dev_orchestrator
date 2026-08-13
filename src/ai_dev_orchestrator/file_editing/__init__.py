"""File-edit **write gate** models, a strict parser, and a dry-run preview.

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

Phase 5F1 adds the first consumer of that approval:
:func:`build_file_edit_preview`, a pure function that validates one approved
diff proposal against a project config and the **lexical** Phase 1 write policy
and returns a :class:`FileEditPreviewReport` describing what a future write
phase *would be allowed to attempt*. It is a description of a hypothetical, and
it is **not file editing**: nothing is applied, no apply-cleanliness is checked,
no command is run, and the target workspace is never read, listed, stat'd,
resolved, or canonicalized.

Phase 5F2C adds the **controlled single-file writer** — the first code in this
repository that writes a byte into a target project workspace.
:func:`apply_approved_file_edit` transforms one existing tracked ordinary UTF-8
file from one exact approved pre-image into one exact approved post-image inside
one clean supported Windows Git repository, proves the postcondition, and leaves
the change uncommitted for human review. Everything outside that narrow domain
fails closed: no ``create``, no delete, no rename, no multi-file write, no
protected path, no fuzzy patching, no project verification command, no model
call, no network call, no GitHub access, no branch, no commit, no push, no PR,
and no rollback or journal framework. :mod:`~ai_dev_orchestrator.file_editing.
diff_apply` applies the approved diff **exactly or not at all**.

**Importing this package still performs no file read, no workspace access, and
no write**, and nothing here stamps an approval. Phase 5F2D (controlled
verification) and Phase 5F2E (reviewer integration) remain unauthorized, so the
complete L2 loop is still not built.
"""

from ai_dev_orchestrator.file_editing.diff_apply import (
    StrictDiffApplyError,
    apply_strict_unified_diff,
)
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
from ai_dev_orchestrator.file_editing.preview import (
    FILE_EDIT_PREVIEW_CANDIDATE_SOURCE,
    FILE_EDIT_PREVIEW_MODE,
    FILE_EDIT_PREVIEW_SCHEMA_VERSION,
    FileEditPreviewApprovedDiff,
    FileEditPreviewBlock,
    FileEditPreviewChange,
    FileEditPreviewChecksNotPerformed,
    FileEditPreviewChecksPerformed,
    FileEditPreviewDiffStats,
    FileEditPreviewError,
    FileEditPreviewProject,
    FileEditPreviewReport,
    FileEditPreviewWorkspacePolicy,
    build_file_edit_preview,
)
from ai_dev_orchestrator.file_editing.writer import (
    NEXT_STEP_REQUIRES_HUMAN_REVIEW,
    SINGLE_WRITER_CONTRACT,
    WORKSPACE_WRITE_MODE,
    WORKSPACE_WRITE_SCHEMA_VERSION,
    WorkspaceWriteChecks,
    WorkspaceWriteError,
    WorkspaceWriteExclusions,
    WorkspaceWriteGitBlock,
    WorkspaceWriteIndeterminateError,
    WorkspaceWriteOperationalFiles,
    WorkspaceWriteRefusedError,
    WorkspaceWriteReport,
    WorkspaceWriteTarget,
    apply_approved_file_edit,
)

__all__ = [
    "APPROVED_DIFF_PROPOSAL_MODE",
    "APPROVED_DIFF_PROPOSAL_SCHEMA_VERSION",
    "NEXT_STEP_REQUIRES_HUMAN_REVIEW",
    "SINGLE_WRITER_CONTRACT",
    "WORKSPACE_WRITE_MODE",
    "WORKSPACE_WRITE_SCHEMA_VERSION",
    "FILE_EDIT_PREVIEW_CANDIDATE_SOURCE",
    "FILE_EDIT_PREVIEW_MODE",
    "FILE_EDIT_PREVIEW_SCHEMA_VERSION",
    "REQUIRED_DIFF_EDIT_APPROVAL_TEXT",
    "ApprovedDiffProposalArtifact",
    "DiffEditApproval",
    "FileEditPreviewApprovedDiff",
    "FileEditPreviewBlock",
    "FileEditPreviewChange",
    "FileEditPreviewChecksNotPerformed",
    "FileEditPreviewChecksPerformed",
    "FileEditPreviewDiffStats",
    "FileEditPreviewError",
    "FileEditPreviewProject",
    "FileEditPreviewReport",
    "FileEditPreviewWorkspacePolicy",
    "FileEditingApprovalError",
    "FileEditingApprovalParseError",
    "FileEditingApprovalValidationError",
    "StrictDiffApplyError",
    "WorkspaceWriteChecks",
    "WorkspaceWriteError",
    "WorkspaceWriteExclusions",
    "WorkspaceWriteGitBlock",
    "WorkspaceWriteIndeterminateError",
    "WorkspaceWriteOperationalFiles",
    "WorkspaceWriteRefusedError",
    "WorkspaceWriteReport",
    "WorkspaceWriteTarget",
    "apply_approved_file_edit",
    "apply_strict_unified_diff",
    "build_file_edit_preview",
    "parse_approved_diff_proposal_artifact",
]
