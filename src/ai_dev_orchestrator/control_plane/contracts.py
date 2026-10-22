"""DL-1 — AIDO issuance of Step Contracts from Planner proposals.

The Planner does not issue a Step Contract; it proposes one (roadmap §23.1).
:func:`issue_step_contract` is where a proposal becomes a contract, and
:func:`validate_step_contract` is the single statement of the rules a contract
must satisfy against its Project Contract and Execution Plan. The store calls
the validator again before persisting any contract, so a contract built by hand
gets no further than one built here.

Rules, all refusals and none of them repairs:

- the contract binds exactly the given Project Contract and Execution Plan, by
  digest, project id and plan version;
- the step exists in that plan, and the objective and dependencies are the
  plan's, verbatim (the plan is AIDO's layer, not the Planner's);
- every Project Contract protected invariant is carried. A proposal that drops
  one is refused rather than having it added back, so an omission surfaces;
- the policy fields come from AIDO's caller, never from the proposal.
"""

from __future__ import annotations

from ai_dev_orchestrator.control_plane.models import (
    STEP_CONTRACT_SCHEMA_VERSION,
    VERIFICATION_AUTHORITY_PROJECT_CONFIG,
    ExecutionPlan,
    ProjectContract,
    StepContract,
    StepContractProposal,
)


class ContractRefusedError(Exception):
    """A contract or proposal failed an AIDO binding rule. Nothing was issued."""


def validate_plan_against_contract(plan: ExecutionPlan, project_contract: ProjectContract) -> None:
    """Refuse a plan that does not bind this Project Contract exactly."""
    if plan.project_id != project_contract.project_id:
        raise ContractRefusedError("execution plan project_id does not match the project contract.")
    if plan.project_contract_sha256 != project_contract.sha256:
        raise ContractRefusedError(
            "execution plan binds a different project contract digest."
        )


def validate_step_contract(
    contract: StepContract,
    *,
    project_contract: ProjectContract,
    execution_plan: ExecutionPlan,
) -> None:
    """Refuse a step contract that does not satisfy every issuance rule."""
    validate_plan_against_contract(execution_plan, project_contract)
    if contract.project_id != project_contract.project_id:
        raise ContractRefusedError("step contract project_id does not match the project contract.")
    if contract.project_contract_sha256 != project_contract.sha256:
        raise ContractRefusedError("step contract binds a different project contract digest.")
    if contract.execution_plan_sha256 != execution_plan.sha256:
        raise ContractRefusedError("step contract binds a different execution plan digest.")
    if contract.execution_plan_version != execution_plan.plan_version:
        raise ContractRefusedError("step contract binds a different execution plan version.")
    planned = execution_plan.step(contract.step_id)
    if planned is None:
        raise ContractRefusedError("step contract names a step that is not in the execution plan.")
    if contract.objective != planned.objective:
        raise ContractRefusedError("step contract objective differs from the execution plan.")
    if contract.depends_on != planned.depends_on:
        raise ContractRefusedError("step contract dependencies differ from the execution plan.")
    missing = [
        invariant
        for invariant in project_contract.content.protected_invariants
        if invariant not in contract.protected_invariants
    ]
    if missing:
        raise ContractRefusedError(
            f"step contract omits {len(missing)} project protected invariant(s); "
            "a step may add invariants but never drop one."
        )


def issue_step_contract(
    proposal: StepContractProposal,
    *,
    project_contract: ProjectContract,
    execution_plan: ExecutionPlan,
    review_required: bool,
    human_acceptance_required: bool,
    max_attempts: int,
    step_contract_version: int = 1,
    supersedes_sha256: str | None = None,
) -> StepContract:
    """Turn a validated Planner proposal into an AIDO-issued Step Contract.

    Pure: it reads and writes nothing. The policy arguments are AIDO's; they
    are keyword-only and have no defaults, so none is inherited by omission.
    """
    planned = execution_plan.step(proposal.step_id)
    if planned is None:
        raise ContractRefusedError("proposal names a step that is not in the execution plan.")
    contract = StepContract(
        schema_version=STEP_CONTRACT_SCHEMA_VERSION,
        project_id=project_contract.project_id,
        project_contract_sha256=project_contract.sha256,
        execution_plan_sha256=execution_plan.sha256,
        execution_plan_version=execution_plan.plan_version,
        step_id=planned.step_id,
        step_contract_version=step_contract_version,
        supersedes_sha256=supersedes_sha256,
        objective=planned.objective,
        depends_on=planned.depends_on,
        requirements=proposal.requirements,
        protected_invariants=proposal.protected_invariants,
        verification_authority=VERIFICATION_AUTHORITY_PROJECT_CONFIG,
        review_required=review_required,
        human_acceptance_required=human_acceptance_required,
        max_attempts=max_attempts,
    )
    validate_step_contract(
        contract, project_contract=project_contract, execution_plan=execution_plan
    )
    return contract
