"""Patch **proposal** artifact models, a strict parser, and a generator.

Phase 5E0 typed the artifact shape §13's "Phase 5E — patch proposal artifact
only" would eventually produce, in
[PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md](../../../docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md)
— :class:`PatchProposalChange`, :class:`PatchProposalProvenance`, and the
:class:`PatchProposalArtifact` wrapper around an **untouched**
``ApprovedL1PlanArtifact`` snapshot — plus
:func:`parse_patch_proposal_artifact`, a pure strict-JSON parser for text it is
handed.

Phase 5E1 adds the one thing 5E0 deliberately withheld: a **deterministic,
offline producer**, :func:`build_deterministic_patch_proposal`. It is a pure
function over two already-loaded objects — an approved plan and a project config
— that restates the plan's own ``files_likely_to_change`` list as one prose
change each.

**Still not a diff.** The artifact carries **no unified diff**, no patch, no
edit script, no command, no command output, and no file content — only prose
describing what a human should do to paths the approved plan already named.
Reading file contents (Phase 5D2) and carrying a real diff (Phase 5E2) remain
proposed and not authorized.

**Importing this package still adds no command and no option**, performs no file
read, no workspace access, no patch generation on import, no file edit, no
command execution, no GitHub fetch or write, and no model, network, or
environment access. Nothing here writes an artifact file, and nothing stamps an
approval.

**L2 is still not built**, and nothing here can invoke it. A generated or parsed
proposal is data describing suggested work — never permission to do it.
"""

from ai_dev_orchestrator.patch_proposal.generator import (
    PatchProposalGenerationError,
    build_deterministic_patch_proposal,
)
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
    "PatchProposalGenerationError",
    "PatchProposalParseError",
    "PatchProposalProvenance",
    "PatchProposalValidationError",
    "build_deterministic_patch_proposal",
    "parse_patch_proposal_artifact",
]
