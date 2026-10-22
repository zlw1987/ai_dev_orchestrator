"""DL-1 — offline dual-loop control-plane foundation.

Typed contracts and runs (:mod:`.models`), AIDO issuance of Step Contracts
(:mod:`.contracts`), the deterministic transition validator
(:mod:`.transitions`), SQLite persistence and recovery (:mod:`.store`), and
injected role ports (:mod:`.ports`), and the DL-2 offline single-Step inner loop
(:mod:`.inner_loop`).

Offline only. Nothing here calls a model, launches a process, opens a socket,
reads an environment variable, or touches a target workspace, and no CLI
command reaches it. The outer loop (DL-3) is not implemented; see
``docs/DL1_CONTROL_PLANE_FOUNDATION.md`` and ``docs/DL2_OFFLINE_INNER_LOOP.md``.
"""

from ai_dev_orchestrator.control_plane.contracts import (
    ContractRefusedError,
    issue_step_contract,
    validate_step_contract,
)
from ai_dev_orchestrator.control_plane.inner_loop import (
    InnerLoopInputError,
    InnerLoopOutcome,
    InnerLoopStop,
    RoleDispatch,
    StepInnerLoop,
)
from ai_dev_orchestrator.control_plane.models import (
    ExecutionPlan,
    HumanStepAcceptance,
    ImplementationReport,
    PlannedStep,
    PlannerDecision,
    PlannerRecommendation,
    ProjectContract,
    ProjectContractApproval,
    ProjectContractContent,
    ProjectRun,
    ProjectState,
    ReviewProposal,
    StepContract,
    StepContractProposal,
    StepRun,
    StepState,
    TestProposal,
    VerificationObservation,
)
from ai_dev_orchestrator.control_plane.ports import (
    ImplementerPort,
    PlannerPort,
    ReviewerPort,
    RolePorts,
    TesterPort,
    VerifierPort,
)
from ai_dev_orchestrator.control_plane.store import (
    AppliedTransition,
    ControlPlaneStore,
    RecordNotFoundError,
    RecoveryReport,
    RecoveryRequiredError,
    StateUntrustedError,
    StoreError,
    StoreLockedError,
    TransitionRecord,
    UnverifiedRunRow,
    new_request_id,
)
from ai_dev_orchestrator.control_plane.transitions import (
    ProjectEvent,
    ProjectTransitionRequest,
    RefusalCode,
    StepEvent,
    StepTransitionRequest,
    TransitionRefused,
    decide_project_transition,
    decide_step_transition,
)

__all__ = [
    "AppliedTransition",
    "ContractRefusedError",
    "ControlPlaneStore",
    "ExecutionPlan",
    "HumanStepAcceptance",
    "ImplementationReport",
    "ImplementerPort",
    "InnerLoopInputError",
    "InnerLoopOutcome",
    "InnerLoopStop",
    "PlannedStep",
    "PlannerDecision",
    "PlannerPort",
    "PlannerRecommendation",
    "ProjectContract",
    "ProjectContractApproval",
    "ProjectContractContent",
    "ProjectEvent",
    "ProjectRun",
    "ProjectState",
    "ProjectTransitionRequest",
    "RecordNotFoundError",
    "RecoveryReport",
    "RecoveryRequiredError",
    "RefusalCode",
    "ReviewProposal",
    "ReviewerPort",
    "RoleDispatch",
    "RolePorts",
    "StateUntrustedError",
    "StepContract",
    "StepContractProposal",
    "StepEvent",
    "StepInnerLoop",
    "StepRun",
    "StepState",
    "StepTransitionRequest",
    "StoreError",
    "StoreLockedError",
    "TestProposal",
    "TesterPort",
    "TransitionRecord",
    "TransitionRefused",
    "UnverifiedRunRow",
    "VerificationObservation",
    "VerifierPort",
    "decide_project_transition",
    "decide_step_transition",
    "issue_step_contract",
    "new_request_id",
    "validate_step_contract",
]
