"""Unified **diff proposal** artifact models, parser, and generator (5E2/5E3).

Phase 5E0 typed a patch proposal that carried **prose only** — no diff — because
carrying one meant reading file contents, which was unauthorized then. Phase 5D2
has since shipped bounded, redacted content reads behind their own project-level
opt-in and two explicit flags. Phase 5E2 was the next inert step: it lets a
unified-diff-shaped artifact **exist as data** and be validated. Phase 5E3 adds
the producer that fills that schema in.

The **Phase 5E2 half** is
:class:`~ai_dev_orchestrator.diff_proposal.models.DiffProposalFileChange`,
:class:`~ai_dev_orchestrator.diff_proposal.models.DiffProposalProvenance`, the
:class:`~ai_dev_orchestrator.diff_proposal.models.DiffProposalArtifact` wrapper
around an **untouched** ``ApprovedL1PlanArtifact`` snapshot (and, optionally, an
untouched Phase 5E0 ``PatchProposalArtifact`` snapshot), and
:func:`~ai_dev_orchestrator.diff_proposal.models.parse_diff_proposal_artifact`,
a pure strict-JSON parser for text it is handed.

The **Phase 5E3 half** is
:func:`~ai_dev_orchestrator.diff_proposal.generator.build_deterministic_diff_proposal`
plus the two strict parsers for its inputs —
:func:`~ai_dev_orchestrator.diff_proposal.generator.parse_proposed_content_input`
and
:func:`~ai_dev_orchestrator.diff_proposal.generator.parse_workspace_content_packet`.
The generator is a **pure function over already-loaded objects**: an approved
plan, a project config, a Phase 5D2 ``l2-read-workspace-files`` packet, and a
proposed-content input. It runs ``difflib`` over strings it was handed.

**Phase 5E3 generates diff text and does nothing with it.** It does not apply a
diff, check whether one would apply, edit a file, write a file, run a command,
read a target workspace, list a directory, or call a model. Original file text
reaches it only inside the Phase 5D2 packet, as **data**; a path that packet
does not cover is a path whose diff simply cannot be generated, never a path to
go and read.

**Importing this package performs no file read, no workspace access, no file
edit, no command execution, no GitHub fetch or write, and no model, network, or
environment access.** Nothing here writes an artifact file, and nothing stamps
an approval — the Phase 5E3 CLI command prints to stdout only.

Phase 5F — the first phase that could **edit a file** — remains proposed and not
authorized. **L2 is still not built**, and nothing here can invoke it. A
generated diff proposal is data describing suggested work — never permission to
do it.
"""

from ai_dev_orchestrator.diff_proposal.generator import (
    MAX_PROPOSED_CONTENT_CHARS,
    PROPOSED_CONTENT_MODE,
    PROPOSED_CONTENT_SCHEMA_VERSION,
    DiffProposalGenerationError,
    DiffProposalInputParseError,
    DiffProposalInputValidationError,
    ProposedContentChange,
    ProposedContentInput,
    WorkspaceContentItem,
    WorkspaceContentPacket,
    build_deterministic_diff_proposal,
    parse_proposed_content_input,
    parse_workspace_content_packet,
)
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
    "MAX_PROPOSED_CONTENT_CHARS",
    "PROPOSED_CONTENT_MODE",
    "PROPOSED_CONTENT_SCHEMA_VERSION",
    "DiffProposalArtifact",
    "DiffProposalError",
    "DiffProposalFileChange",
    "DiffProposalGenerationError",
    "DiffProposalInputParseError",
    "DiffProposalInputValidationError",
    "DiffProposalParseError",
    "DiffProposalProvenance",
    "DiffProposalValidationError",
    "ProposedContentChange",
    "ProposedContentInput",
    "WorkspaceContentItem",
    "WorkspaceContentPacket",
    "build_deterministic_diff_proposal",
    "parse_diff_proposal_artifact",
    "parse_proposed_content_input",
    "parse_workspace_content_packet",
]
