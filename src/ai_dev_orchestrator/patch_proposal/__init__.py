"""Typed patch **proposal** artifact models and a strict parser (Phase 5E0).

Phase 5E0 types the artifact shape §13's "Phase 5E — patch proposal artifact
only" would eventually produce, in
[PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md](../../../docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md)
— :class:`PatchProposalChange`, :class:`PatchProposalProvenance`, and the
:class:`PatchProposalArtifact` wrapper around an **untouched**
``ApprovedL1PlanArtifact`` snapshot — plus
:func:`parse_patch_proposal_artifact`, a pure strict-JSON parser for text it is
handed.

**This is not patch generation.** There is no generator here. The artifact
carries **no unified diff**, no patch, no edit script, no command, and no file
content — only prose describing what a human should do to paths the approved
plan already named. Producing a proposal is Phase 5E1, which is proposed and not
authorized.

**Library only, wired into nothing.** Importing this package adds no command and
no option, performs no file read, no workspace path check, no patch generation,
no file edit, no command execution, no GitHub fetch or write, and no model,
network, or environment access. It writes no approved-plan artifact and stamps
no approval.

**L2 is still not built**, and nothing here can invoke it. A parsed proposal is
data describing suggested work — never permission to do it.
"""

from ai_dev_orchestrator.patch_proposal.models import (
    PATCH_PROPOSAL_MODE,
    PATCH_PROPOSAL_SCHEMA_VERSION,
    PatchProposalArtifact,
    PatchProposalChange,
    PatchProposalError,
    PatchProposalParseError,
    PatchProposalProvenance,
    PatchProposalValidationError,
    parse_patch_proposal_artifact,
)

__all__ = [
    "PATCH_PROPOSAL_MODE",
    "PATCH_PROPOSAL_SCHEMA_VERSION",
    "PatchProposalArtifact",
    "PatchProposalChange",
    "PatchProposalError",
    "PatchProposalParseError",
    "PatchProposalProvenance",
    "PatchProposalValidationError",
    "parse_patch_proposal_artifact",
]
