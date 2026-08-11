"""Unified **diff proposal** artifact models and a strict parser (Phase 5E2).

Phase 5E0 typed a patch proposal that carried **prose only** — no diff — because
carrying one meant reading file contents, which was unauthorized then. Phase 5D2
has since shipped bounded, redacted content reads behind their own project-level
opt-in and two explicit flags. Phase 5E2 is the next inert step: it lets a
unified-diff-shaped artifact **exist as data** and be validated, so a future
producer has a schema to be checked against.

This package is **library only**. It contains
:class:`~ai_dev_orchestrator.diff_proposal.models.DiffProposalFileChange`,
:class:`~ai_dev_orchestrator.diff_proposal.models.DiffProposalProvenance`, the
:class:`~ai_dev_orchestrator.diff_proposal.models.DiffProposalArtifact` wrapper
around an **untouched** ``ApprovedL1PlanArtifact`` snapshot (and, optionally, an
untouched Phase 5E0 ``PatchProposalArtifact`` snapshot), and
:func:`~ai_dev_orchestrator.diff_proposal.models.parse_diff_proposal_artifact`,
a pure strict-JSON parser for text it is handed.

**Phase 5E2 does not generate a diff.** There is no generator here. It does not
apply a diff, modify one, edit a file, run a command, read workspace contents,
list a directory, or call a model. The ``unified_diff`` field may contain source
lines as diff context — that is what a diff is, and it is allowed as **data** —
but nothing here produced that text, read a file to obtain it, or sends it
anywhere. Whether a diff would apply is never checked and no patch tooling is
invoked.

**Importing this package adds no command and no option**, performs no file read,
no workspace access, no file edit, no command execution, no GitHub fetch or
write, and no model, network, or environment access. Nothing here writes an
artifact file, and nothing stamps an approval.

Phase 5E3 — a separately gated **producer** of this artifact — remains proposed
and not authorized. **L2 is still not built**, and nothing here can invoke it. A
parsed diff proposal is data describing suggested work — never permission to do
it.
"""

from ai_dev_orchestrator.diff_proposal.models import (
    DIFF_PROPOSAL_MODE,
    DIFF_PROPOSAL_SCHEMA_VERSION,
    DiffProposalArtifact,
    DiffProposalError,
    DiffProposalFileChange,
    DiffProposalParseError,
    DiffProposalProvenance,
    DiffProposalValidationError,
    parse_diff_proposal_artifact,
)

__all__ = [
    "DIFF_PROPOSAL_MODE",
    "DIFF_PROPOSAL_SCHEMA_VERSION",
    "DiffProposalArtifact",
    "DiffProposalError",
    "DiffProposalFileChange",
    "DiffProposalParseError",
    "DiffProposalProvenance",
    "DiffProposalValidationError",
    "parse_diff_proposal_artifact",
]
