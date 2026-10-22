"""DL-1 — injected role ports for the future inner and outer loops.

These are interfaces only. DL-1 ships **no implementation** of any of them:
the test suite injects fakes, and the only code in this package that calls a
port is the DL-2 offline inner loop (:mod:`.inner_loop`). Wiring
a real role (a model-backed Planner, a Pi Implementer, the 5F2D verifier, the
5F2E reviewer) is later, separately authorized work, and each such adapter
inherits that role's existing authority contract unchanged.

Every port returns a typed **proposal**. None returns a state, and none is
handed the store, so no role can persist anything or cause a transition: the
DL-2 inner loop passes a port's output into a
:class:`~ai_dev_orchestrator.control_plane.transitions.StepTransitionRequest`,
and the validator decides. The one exception in kind is :class:`VerifierPort`,
whose :class:`~ai_dev_orchestrator.control_plane.models.VerificationObservation`
the validator treats as an authoritative fact; only AIDO's own deterministic
verification may implement it, never a model.

There is deliberately no Tester-authority issuer and no port that accepts a
proposal back as authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ai_dev_orchestrator.control_plane.models import (
    ExecutionPlan,
    ImplementationReport,
    PlannerDecision,
    ProjectContract,
    ReviewProposal,
    StepContract,
    StepContractProposal,
    StepRun,
    TestProposal,
    VerificationObservation,
)


class PlannerPort(Protocol):
    def propose_step_contract(
        self, *, project_contract: ProjectContract, execution_plan: ExecutionPlan, step_id: str
    ) -> StepContractProposal: ...

    def decide_step(self, *, step_contract: StepContract, step_run: StepRun) -> PlannerDecision: ...


class TesterPort(Protocol):
    def propose_tests(
        self, *, step_contract: StepContract, attempt: int
    ) -> tuple[TestProposal, ...]: ...


class ImplementerPort(Protocol):
    def implement(self, *, step_contract: StepContract, attempt: int) -> ImplementationReport: ...


class VerifierPort(Protocol):
    def verify(self, *, step_contract: StepContract, attempt: int) -> VerificationObservation: ...


class ReviewerPort(Protocol):
    def review(self, *, step_contract: StepContract, attempt: int) -> ReviewProposal: ...


@dataclass(frozen=True)
class RolePorts:
    """The five injected roles a future loop is constructed with."""

    planner: PlannerPort
    tester: TesterPort
    implementer: ImplementerPort
    verifier: VerifierPort
    reviewer: ReviewerPort
