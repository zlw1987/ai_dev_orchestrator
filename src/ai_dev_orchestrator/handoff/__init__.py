"""Typed approved-plan handoff models and a strict parser (Phase 5B).

Phase 5B types §3 of
[PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md](../../../docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md)
— :class:`PlanApproval`, :class:`L1PlanProvenance`, and the
:class:`ApprovedL1PlanArtifact` wrapper around an **untouched** ``L1Plan``
snapshot — plus :func:`parse_approved_l1_plan_artifact`, a pure strict-JSON
parser for text it is handed.

**Library only, wired into nothing.** Importing this package adds no command and
no option, performs no file read, no workspace path check, no command execution,
no GitHub fetch or write, and no model, network, or environment access. There is
no artifact loader: reading an approved plan from disk, and every form of acting
on one, belong to later phases that are not authorized.

**L2 is still not built**, and nothing here can invoke it. A parsed artifact is
data describing an approval — never permission to do anything.
"""

from ai_dev_orchestrator.handoff.models import (
    REQUIRED_APPROVAL_TEXT,
    ApprovedL1PlanArtifact,
    ApprovedPlanError,
    ApprovedPlanParseError,
    ApprovedPlanValidationError,
    L1PlanProvenance,
    PlanApproval,
    parse_approved_l1_plan_artifact,
)

__all__ = [
    "REQUIRED_APPROVAL_TEXT",
    "ApprovedL1PlanArtifact",
    "ApprovedPlanError",
    "ApprovedPlanParseError",
    "ApprovedPlanValidationError",
    "L1PlanProvenance",
    "PlanApproval",
    "parse_approved_l1_plan_artifact",
]
