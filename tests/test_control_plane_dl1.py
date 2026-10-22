"""DL-1 — offline dual-loop control-plane foundation.

Every test is offline and synthetic. The store is a SQLite file under pytest
``tmp_path``; contracts, plans and role outputs are synthetic; the five role
ports are in-test fakes. No model, no socket, no subprocess, no Pi or Node,
no target workspace, and no environment variable is used.

The suite covers, in order:

- creation and persistence of ProjectRun / StepRun, and store ownership;
- contract identity, approval binding and version chaining;
- valid transitions, including the full inner-loop path with fake ports;
- invalid, stale, out-of-order and mis-bound transitions;
- duplicate requests;
- interruption, restart and recovery;
- escalation to HUMAN_REQUIRED when persisted state cannot be trusted;
- FU1: recovery enforced as a per-session gate (B1), cross-object identity
  re-proven at consumption and recovery (B2), public reads that refuse unproven
  state (B3), replays answered only after that proof (B4), and caller models
  re-validated at the store boundary;
- that no role proposal can become authority on its own;
- static boundaries: imports, CLI reachability and vocabulary drift.
"""

from __future__ import annotations

import ast
import sqlite3
import typing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

import ai_dev_orchestrator.control_plane as cp
from ai_dev_orchestrator.control_plane import (
    ContractRefusedError,
    ControlPlaneStore,
    ExecutionPlan,
    HumanStepAcceptance,
    ImplementationReport,
    PlannedStep,
    PlannerDecision,
    PlannerRecommendation,
    ProjectContract,
    ProjectContractApproval,
    ProjectContractContent,
    ProjectEvent,
    ProjectState,
    ProjectTransitionRequest,
    RecordNotFoundError,
    RecoveryRequiredError,
    RefusalCode,
    ReviewProposal,
    RolePorts,
    StateUntrustedError,
    StepContractProposal,
    StepEvent,
    StepState,
    StepTransitionRequest,
    StoreError,
    StoreLockedError,
    TestProposal,
    TransitionRefused,
    UnverifiedRunRow,
    VerificationObservation,
    issue_step_contract,
    new_request_id,
)
from ai_dev_orchestrator.control_plane.models import (
    REQUIRED_PROJECT_CONTRACT_APPROVAL_TEXT,
    REQUIRED_STEP_ACCEPTANCE_APPROVAL_TEXT,
    ReviewVerdict,
    VerificationOutcome,
)

APPROVED_AT = datetime(2026, 10, 21, 9, 0, tzinfo=timezone.utc)
EVIDENCE = "e" * 64
INVARIANT = "No network access from the control plane."


# --- builders ---------------------------------------------------------------


def make_project_contract(**content_overrides) -> ProjectContract:
    content = ProjectContractContent(
        **{
            "schema_version": "project-contract.v1",
            "project_id": "synthetic-project",
            "goal": "Add a synthetic greeting helper.",
            "requirements": ("The helper returns a greeting.",),
            "protected_invariants": (INVARIANT,),
            "acceptance_criteria": ("A greeting test passes.",),
            "human_decision_boundaries": ("Any public API change.",),
            **content_overrides,
        }
    )
    approval = ProjectContractApproval(
        approved_by="synthetic-operator",
        approved_at=APPROVED_AT,
        approval_text=REQUIRED_PROJECT_CONTRACT_APPROVAL_TEXT,
        source="manual",
        contract_sha256=content.sha256,
    )
    return ProjectContract(content=content, approval=approval)


def make_plan(pc: ProjectContract, *, version: int = 1, supersedes: str | None = None,
              steps: tuple[PlannedStep, ...] | None = None) -> ExecutionPlan:
    return ExecutionPlan(
        schema_version="execution-plan.v1",
        project_id=pc.project_id,
        project_contract_sha256=pc.sha256,
        plan_version=version,
        supersedes_sha256=supersedes,
        steps=steps
        or (
            PlannedStep(step_id="step-a", objective="Write the helper."),
            PlannedStep(step_id="step-b", objective="Document it.", depends_on=("step-a",)),
        ),
    )


def make_proposal(step_id: str = "step-a", **overrides) -> StepContractProposal:
    return StepContractProposal(
        **{
            "step_id": step_id,
            "requirements": ("Return 'hello'.",),
            "protected_invariants": (INVARIANT,),
            **overrides,
        }
    )


def issue(pc, plan, step_id="step-a", *, review_required=True, human=False, max_attempts=2):
    return issue_step_contract(
        make_proposal(step_id),
        project_contract=pc,
        execution_plan=plan,
        review_required=review_required,
        human_acceptance_required=human,
        max_attempts=max_attempts,
    )


class FakeClock:
    def __init__(self) -> None:
        self.now = APPROVED_AT

    def __call__(self) -> datetime:
        self.now += timedelta(seconds=1)
        return self.now


def open_store(path: Path) -> ControlPlaneStore:
    return ControlPlaneStore.open(path, clock=FakeClock())


def tamper(db_path: Path, sql: str, params: tuple = ()) -> None:
    """Edit the database outside the store, as a bug or a person could."""
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA ignore_check_constraints = ON")
    connection.execute(sql, params)
    connection.commit()
    connection.close()


INDEPENDENT_STEPS = (
    PlannedStep(step_id="step-a", objective="Write the helper."),
    PlannedStep(step_id="step-b", objective="Write a second helper."),
)


class World:
    """One recorded project run with two step runs (b depends on a, unless
    ``independent``). Step a's policy is configurable; step b requires neither
    review nor human acceptance."""

    def __init__(self, db_path: Path, *, review_required=True, human=False, max_attempts=2,
                 independent=False):
        self.db_path = db_path
        self.store = open_store(db_path)
        self.pc = make_project_contract()
        self.plan = make_plan(self.pc, steps=INDEPENDENT_STEPS if independent else None)
        self.contract_a = issue(self.pc, self.plan, "step-a", review_required=review_required,
                                human=human, max_attempts=max_attempts)
        self.contract_b = issue(self.pc, self.plan, "step-b", review_required=False)
        self.store.record_project_contract(self.pc)
        self.store.record_execution_plan(self.plan)
        self.store.record_step_contract(self.contract_a)
        self.store.record_step_contract(self.contract_b)
        self.project = self.store.create_project_run(
            project_contract_sha256=self.pc.sha256, execution_plan_sha256=self.plan.sha256
        )
        self.a = self.store.create_step_run(
            project_run_id=self.project.project_run_id,
            step_contract_sha256=self.contract_a.sha256,
        ).step_run_id
        self.b = self.store.create_step_run(
            project_run_id=self.project.project_run_id,
            step_contract_sha256=self.contract_b.sha256,
        ).step_run_id

    def step(self, step_run_id=None):
        return self.store.get_step_run(step_run_id or self.a)

    def project_state(self) -> ProjectState:
        return self.store.get_project_run(self.project.project_run_id).state

    def contract(self, step_run_id=None):
        return self.store.get_step_contract(self.step(step_run_id).step_contract_sha256)

    def request(self, event: StepEvent, step_run_id=None, **payload) -> StepTransitionRequest:
        return StepTransitionRequest(
            request_id=new_request_id(),
            expected_state_version=self.step(step_run_id).state_version,
            event=event,
            **payload,
        )

    def apply(self, event: StepEvent, step_run_id=None, **payload):
        request = self.request(event, step_run_id, **payload)
        self.store.apply_step_transition(step_run_id or self.a, request)
        return self.step(step_run_id)

    def bound(self, step_run_id=None) -> dict:
        step = self.step(step_run_id)
        return {"step_contract_sha256": step.step_contract_sha256, "attempt": step.attempt}

    def implementation(self, step_run_id=None, **extra) -> ImplementationReport:
        return ImplementationReport(summary="Changed one file.", **self.bound(step_run_id), **extra)

    def verification(self, outcome: VerificationOutcome = "verified", step_run_id=None):
        return VerificationObservation(
            outcome=outcome, evidence_sha256=EVIDENCE, **self.bound(step_run_id)
        )

    def review(self, verdict: ReviewVerdict = "approve") -> ReviewProposal:
        return ReviewProposal(verdict=verdict, evidence_sha256=EVIDENCE, **self.bound())

    def decision(self, recommendation: PlannerRecommendation, step_run_id=None):
        return PlannerDecision(
            recommendation=recommendation,
            rationale="Synthetic rationale.",
            evidence_refs=("verification-result.v1:" + EVIDENCE[:8],),
            **self.bound(step_run_id),
        )

    def human(self) -> HumanStepAcceptance:
        return HumanStepAcceptance(
            approved_by="synthetic-operator",
            approved_at=APPROVED_AT,
            approval_text=REQUIRED_STEP_ACCEPTANCE_APPROVAL_TEXT,
            source="manual",
            **self.bound(),
        )

    def to_acceptance(self, outcome: VerificationOutcome = "verified",
                      verdict: ReviewVerdict | None = "approve", step_run_id=None):
        self.apply(StepEvent.MARK_READY, step_run_id)
        self.apply(StepEvent.BEGIN_ATTEMPT, step_run_id)
        self.apply(StepEvent.IMPLEMENTATION_RETURNED, step_run_id,
                   implementation=self.implementation(step_run_id))
        step = self.apply(StepEvent.VERIFICATION_OBSERVED, step_run_id,
                          verification=self.verification(outcome, step_run_id))
        if step.state is StepState.REVIEWING:
            step = self.apply(StepEvent.REVIEW_OBSERVED, step_run_id, review=self.review(verdict))
        return step

    def reopen(self) -> None:
        """A new store session on the same file. Nothing is recovered."""
        self.store.close()
        self.store = open_store(self.db_path)

    def restart_and_recover(self):
        self.reopen()
        return self.store.recover(self.project.project_run_id)

    def raw(self, step_run_id=None) -> dict:
        """The unproven step row, for asserting on state that cannot be proven."""
        return self.store.inspect_step_run(step_run_id or self.a).columns


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "aido-control-plane.sqlite3"


@pytest.fixture
def world(db_path: Path):
    instance = World(db_path)
    yield instance
    instance.store.close()


def refused(code: RefusalCode):
    return pytest.raises(TransitionRefused, match=code.value)


# --- creation, persistence, ownership ---------------------------------------


def test_project_and_step_runs_are_created_and_persisted(world: World) -> None:
    project = world.store.get_project_run(world.project.project_run_id)
    assert project.state is ProjectState.ACTIVE
    assert project.state_version == 0
    assert project.project_contract_sha256 == world.pc.sha256
    assert project.execution_plan_sha256 == world.plan.sha256
    steps = world.store.list_step_runs(project.project_run_id)
    assert [s.step_id for s in steps] == ["step-a", "step-b"]
    assert all(s.state is StepState.PLANNED and s.attempt == 0 for s in steps)

    world.reopen()
    with pytest.raises(RecoveryRequiredError):
        world.store.get_project_run(project.project_run_id)
    world.store.recover(project.project_run_id)
    assert world.store.get_project_run(project.project_run_id) == project
    assert world.store.list_step_runs(project.project_run_id) == steps


def test_store_path_must_be_absolute_with_an_existing_parent(tmp_path: Path) -> None:
    with pytest.raises(StoreError, match="absolute"):
        ControlPlaneStore.open("relative.sqlite3")
    with pytest.raises(StoreError, match="parent directory"):
        ControlPlaneStore.open(tmp_path / "missing" / "state.sqlite3")
    assert not (tmp_path / "missing").exists()


def test_a_second_owner_of_the_same_store_is_refused(world: World) -> None:
    with pytest.raises(StoreLockedError):
        ControlPlaneStore.open(world.db_path)
    world.store.close()
    ControlPlaneStore.open(world.db_path).close()
    world.store = open_store(world.db_path)


def test_a_file_that_is_not_this_store_is_untrusted(tmp_path: Path) -> None:
    garbage = tmp_path / "garbage.sqlite3"
    garbage.write_bytes(b"not a database at all" * 100)
    with pytest.raises(StateUntrustedError):
        ControlPlaneStore.open(garbage)

    foreign = tmp_path / "foreign.sqlite3"
    connection = sqlite3.connect(foreign)
    connection.execute("CREATE TABLE something_else (x INTEGER)")
    connection.commit()
    connection.close()
    with pytest.raises(StateUntrustedError, match="schema version"):
        ControlPlaneStore.open(foreign)


def test_a_store_with_another_schema_version_is_untrusted(db_path: Path) -> None:
    open_store(db_path).close()
    tamper(db_path, "UPDATE store_meta SET value = 'aido-control-plane-store.v0'")
    with pytest.raises(StateUntrustedError, match="schema version"):
        ControlPlaneStore.open(db_path)


# --- contract identity and versions -----------------------------------------


def test_contract_identity_is_the_content_digest() -> None:
    first = make_project_contract()
    assert first.sha256 == make_project_contract().sha256
    changed = make_project_contract(goal="A different goal.")
    assert changed.sha256 != first.sha256
    plan = make_plan(first)
    assert plan.sha256 != make_plan(changed).sha256
    contract = issue(first, plan)
    assert contract.sha256 != issue(first, plan, max_attempts=3).sha256


def test_project_approval_must_bind_the_exact_digest_and_phrase() -> None:
    content = make_project_contract().content
    good = {
        "approved_by": "synthetic-operator",
        "approved_at": APPROVED_AT,
        "approval_text": REQUIRED_PROJECT_CONTRACT_APPROVAL_TEXT,
        "source": "manual",
        "contract_sha256": content.sha256,
    }
    for bad in (
        {"approval_text": REQUIRED_PROJECT_CONTRACT_APPROVAL_TEXT.lower()},
        {"source": "model"},
        {"approved_at": APPROVED_AT.replace(tzinfo=None)},
        {"approved_by": "  "},
    ):
        with pytest.raises(ValidationError):
            ProjectContractApproval(**{**good, **bad})
    other = make_project_contract(goal="Another goal.").content
    approval = ProjectContractApproval(**{**good, "contract_sha256": other.sha256})
    with pytest.raises(ValidationError, match="different contract"):
        ProjectContract(content=content, approval=approval)


def test_a_plan_must_bind_a_recorded_matching_project_contract(db_path: Path) -> None:
    with open_store(db_path) as store:
        pc = make_project_contract()
        with pytest.raises(RecordNotFoundError):
            store.record_execution_plan(make_plan(pc))
        store.record_project_contract(pc)
        other = make_project_contract(project_id="other-project")
        store.record_project_contract(other)
        forged = make_plan(pc).model_copy(update={"project_id": "other-project"})
        with pytest.raises(ContractRefusedError, match="project_id"):
            store.record_execution_plan(forged)
        assert store.record_execution_plan(make_plan(pc)) == make_plan(pc).sha256


def test_plan_versions_must_chain(db_path: Path) -> None:
    with open_store(db_path) as store:
        pc = make_project_contract()
        store.record_project_contract(pc)
        v1 = make_plan(pc)
        store.record_execution_plan(v1)
        with pytest.raises(ValidationError, match="supersedes_sha256"):
            make_plan(pc, version=2)
        with pytest.raises(ValidationError, match="supersedes_sha256"):
            make_plan(pc, supersedes=v1.sha256)
        steps = (PlannedStep(step_id="step-a", objective="Write it differently."),)
        competing_v1 = make_plan(pc, steps=steps)
        with pytest.raises(ContractRefusedError, match="version 1"):
            store.record_execution_plan(competing_v1)
        v2 = make_plan(pc, version=2, supersedes=v1.sha256, steps=steps)
        store.record_execution_plan(v2)
        v3_skipping = make_plan(pc, version=3, supersedes=v1.sha256, steps=steps)
        with pytest.raises(ContractRefusedError, match="supersede"):
            store.record_execution_plan(v3_skipping)
        assert store.get_execution_plan(v2.sha256) == v2


def test_a_plan_may_depend_only_on_earlier_steps() -> None:
    pc = make_project_contract()
    for steps in (
        (PlannedStep(step_id="a", objective="x", depends_on=("b",)),
         PlannedStep(step_id="b", objective="y")),
        (PlannedStep(step_id="a", objective="x", depends_on=("a",)),),
        (PlannedStep(step_id="a", objective="x"), PlannedStep(step_id="a", objective="y")),
    ):
        with pytest.raises(ValidationError):
            make_plan(pc, steps=steps)


def test_issuance_copies_plan_fields_and_keeps_policy_with_aido() -> None:
    pc = make_project_contract()
    plan = make_plan(pc)
    contract = issue(pc, plan, "step-b", review_required=False, human=True, max_attempts=3)
    assert contract.objective == "Document it."
    assert contract.depends_on == ("step-a",)
    assert contract.execution_plan_sha256 == plan.sha256
    assert contract.project_contract_sha256 == pc.sha256
    assert contract.verification_authority == "project_config.controlled_verification"
    assert (contract.review_required, contract.human_acceptance_required) == (False, True)
    assert contract.max_attempts == 3
    with pytest.raises(ValidationError):
        issue(pc, plan, max_attempts=99)


def test_issuance_refuses_a_dropped_invariant_or_an_unknown_step() -> None:
    pc = make_project_contract()
    plan = make_plan(pc)
    with pytest.raises(ContractRefusedError, match="never drop"):
        issue_step_contract(
            make_proposal(protected_invariants=()), project_contract=pc, execution_plan=plan,
            review_required=True, human_acceptance_required=False, max_attempts=1,
        )
    with pytest.raises(ContractRefusedError, match="not in the execution plan"):
        issue(pc, plan, "step-z")


def test_the_store_reruns_issuance_rules_on_a_hand_built_contract(world: World) -> None:
    hand_built = world.contract_a.model_copy(update={"objective": "Something unplanned."})
    with pytest.raises(ContractRefusedError, match="objective"):
        world.store.record_step_contract(hand_built)
    dropped = world.contract_a.model_copy(update={"protected_invariants": ()})
    with pytest.raises(ContractRefusedError, match="never drop"):
        world.store.record_step_contract(dropped)
    assert world.store.record_step_contract(world.contract_a) == world.contract_a.sha256


def test_a_step_run_must_bind_its_project_runs_contract_and_plan(world: World) -> None:
    steps = (PlannedStep(step_id="step-a", objective="Write the helper."),)
    v2 = make_plan(world.pc, version=2, supersedes=world.plan.sha256, steps=steps)
    world.store.record_execution_plan(v2)
    under_v2 = issue(world.pc, v2, "step-a")
    world.store.record_step_contract(under_v2)
    with pytest.raises(ContractRefusedError, match="binds a different"):
        world.store.create_step_run(
            project_run_id=world.project.project_run_id, step_contract_sha256=under_v2.sha256
        )
    with pytest.raises(ContractRefusedError, match="already has a step run"):
        world.store.create_step_run(
            project_run_id=world.project.project_run_id,
            step_contract_sha256=world.contract_a.sha256,
        )


def test_a_tampered_stored_contract_is_untrusted(world: World) -> None:
    world.store.close()
    body = world.contract_a.model_dump_json().replace("Return 'hello'.", "Return 'bye'.")
    tamper(world.db_path, "UPDATE contracts SET body = ? WHERE sha256 = ?",
           (body, world.contract_a.sha256))
    world.store = open_store(world.db_path)
    with pytest.raises(StateUntrustedError, match="no longer hashes"):
        world.store.get_step_contract(world.contract_a.sha256)


# --- valid transitions --------------------------------------------------------


def test_the_full_step_path_completes_with_every_required_input(world: World) -> None:
    step = world.to_acceptance("verified", "approve")
    assert step.state is StepState.ACCEPTANCE
    assert (step.verification_outcome, step.review_verdict) == ("verified", "approve")
    step = world.apply(
        StepEvent.DECIDE_ACCEPTANCE,
        planner_decision=world.decision(PlannerRecommendation.RECOMMEND_STEP_ACCEPT),
    )
    assert step.state is StepState.COMPLETE
    assert step.attempt == 1
    log = world.store.transitions_for(world.a)
    assert [r.to_state for r in log] == [
        "READY", "EXECUTING", "VERIFYING", "REVIEWING", "ACCEPTANCE", "COMPLETE"
    ]
    assert [r.to_version for r in log] == [1, 2, 3, 4, 5, 6]
    assert log[-1].rule == "acceptance_authorized"
    assert world.project_state() is ProjectState.ACTIVE


def test_without_required_review_verification_goes_straight_to_acceptance(db_path) -> None:
    world = World(db_path, review_required=False)
    try:
        step = world.to_acceptance("verified", verdict=None)
        assert step.state is StepState.ACCEPTANCE
        assert step.review_verdict is None
        step = world.apply(
            StepEvent.DECIDE_ACCEPTANCE,
            planner_decision=world.decision(PlannerRecommendation.RECOMMEND_STEP_ACCEPT),
        )
        assert step.state is StepState.COMPLETE
    finally:
        world.store.close()


def test_a_step_is_ready_only_when_its_dependencies_are_complete(world: World) -> None:
    with refused(RefusalCode.DEPENDENCIES_INCOMPLETE):
        world.apply(StepEvent.MARK_READY, world.b)
    assert world.step(world.b).state is StepState.PLANNED
    world.to_acceptance()
    world.apply(StepEvent.DECIDE_ACCEPTANCE,
                planner_decision=world.decision(PlannerRecommendation.RECOMMEND_STEP_ACCEPT))
    assert world.apply(StepEvent.MARK_READY, world.b).state is StepState.READY


def test_a_required_human_acceptance_is_enforced(db_path: Path) -> None:
    world = World(db_path, human=True)
    try:
        world.to_acceptance()
        accept = world.decision(PlannerRecommendation.RECOMMEND_STEP_ACCEPT)
        with refused(RefusalCode.HUMAN_ACCEPTANCE_MISSING):
            world.apply(StepEvent.DECIDE_ACCEPTANCE, planner_decision=accept)
        assert world.step().state is StepState.ACCEPTANCE
        with pytest.raises(ValidationError):
            HumanStepAcceptance(**{**world.human().model_dump(), "approval_text": "ok"})
        step = world.apply(StepEvent.DECIDE_ACCEPTANCE, planner_decision=accept,
                           human_acceptance=world.human())
        assert step.state is StepState.COMPLETE
    finally:
        world.store.close()


def test_retry_is_bounded_by_the_contracts_attempt_budget(world: World) -> None:
    world.to_acceptance("verification-failed", verdict=None)
    retry = PlannerRecommendation.RECOMMEND_RETRY_IMPLEMENTATION
    assert world.apply(StepEvent.DECIDE_ACCEPTANCE,
                       planner_decision=world.decision(retry)).state is StepState.READY
    step = world.apply(StepEvent.BEGIN_ATTEMPT)
    assert (step.state, step.attempt, step.verification_outcome) == (
        StepState.EXECUTING, 2, None
    )
    world.apply(StepEvent.IMPLEMENTATION_RETURNED, implementation=world.implementation())
    world.apply(StepEvent.VERIFICATION_OBSERVED,
                verification=world.verification("verification-failed"))
    step = world.apply(StepEvent.DECIDE_ACCEPTANCE, planner_decision=world.decision(retry))
    assert step.state is StepState.FAILED
    assert world.store.transitions_for(world.a)[-1].rule == "attempt_budget_exhausted"


@pytest.mark.parametrize(
    ("outcome", "verdict", "rule"),
    [
        ("verification-failed", None, "accept_recommended_without_verified_outcome"),
        ("verified", "changes_requested", "accept_recommended_without_review_approval"),
        ("verified", "needs_human_review", "accept_recommended_without_review_approval"),
    ],
)
def test_an_accept_recommendation_against_the_facts_escalates(
    world: World, outcome, verdict, rule
) -> None:
    world.to_acceptance(outcome, verdict)
    step = world.apply(
        StepEvent.DECIDE_ACCEPTANCE,
        planner_decision=world.decision(PlannerRecommendation.RECOMMEND_STEP_ACCEPT),
    )
    assert step.state is StepState.HUMAN_REQUIRED
    assert world.store.transitions_for(world.a)[-1].rule == rule


@pytest.mark.parametrize(
    "recommendation",
    [
        PlannerRecommendation.RECOMMEND_RETRY_TEST,
        PlannerRecommendation.RECOMMEND_REPLAN,
        PlannerRecommendation.PLAN_CONFLICT,
        PlannerRecommendation.HUMAN_REQUIRED,
    ],
)
def test_recommendations_dl1_cannot_act_on_end_at_a_human(world: World, recommendation) -> None:
    world.to_acceptance()
    step = world.apply(StepEvent.DECIDE_ACCEPTANCE, planner_decision=world.decision(recommendation))
    assert step.state is StepState.HUMAN_REQUIRED
    assert world.project_state() is ProjectState.ACTIVE


def test_a_project_contract_conflict_escalates_the_project(world: World) -> None:
    world.to_acceptance()
    step = world.apply(
        StepEvent.DECIDE_ACCEPTANCE,
        planner_decision=world.decision(PlannerRecommendation.PROJECT_CONTRACT_CONFLICT),
    )
    assert step.state is StepState.HUMAN_REQUIRED
    assert world.project_state() is ProjectState.HUMAN_REQUIRED
    project_log = world.store.transitions_for(world.project.project_run_id)
    assert [(r.event, r.to_state) for r in project_log] == [("step_propagation", "HUMAN_REQUIRED")]


def test_an_untrusted_workspace_requires_recovery_and_is_never_resumed(world: World) -> None:
    step = world.to_acceptance("workspace-state-untrusted")
    assert step.state is StepState.RECOVERY_REQUIRED
    assert world.project_state() is ProjectState.RECOVERY_REQUIRED
    with refused(RefusalCode.TERMINAL_STATE):
        world.apply(StepEvent.BEGIN_ATTEMPT)
    with refused(RefusalCode.PROJECT_NOT_ACTIVE):
        world.apply(StepEvent.MARK_READY, world.b)


# --- invalid transitions -------------------------------------------------------


def test_out_of_order_events_are_refused_and_change_nothing(world: World) -> None:
    with refused(RefusalCode.OUT_OF_ORDER):
        world.apply(StepEvent.BEGIN_ATTEMPT)
    with refused(RefusalCode.OUT_OF_ORDER):
        world.apply(StepEvent.RECOVER_INTERRUPTED, reason="Not in flight.")
    early_report = ImplementationReport(
        summary="Too early.", step_contract_sha256=world.contract_a.sha256, attempt=1)
    with refused(RefusalCode.BINDING_MISMATCH):  # no attempt 1 exists yet
        world.apply(StepEvent.IMPLEMENTATION_RETURNED, implementation=early_report)
    assert world.store.transitions_for(world.a) == ()
    world.apply(StepEvent.MARK_READY)
    world.apply(StepEvent.BEGIN_ATTEMPT)
    with refused(RefusalCode.OUT_OF_ORDER):
        world.apply(StepEvent.REVIEW_OBSERVED, review=world.review())
    with refused(RefusalCode.OUT_OF_ORDER):
        world.apply(StepEvent.DECIDE_ACCEPTANCE,
                    planner_decision=world.decision(PlannerRecommendation.RECOMMEND_STEP_ACCEPT))
    assert world.step().state is StepState.EXECUTING
    assert len(world.store.transitions_for(world.a)) == 2


def test_a_stale_request_is_refused(world: World) -> None:
    stale = world.request(StepEvent.MARK_READY)
    world.apply(StepEvent.MARK_READY)
    with refused(RefusalCode.STALE_STATE_VERSION):
        world.store.apply_step_transition(world.a, stale.model_copy(
            update={"request_id": new_request_id()}))


def test_terminal_states_refuse_every_event(world: World) -> None:
    world.to_acceptance()
    world.apply(StepEvent.DECIDE_ACCEPTANCE,
                planner_decision=world.decision(PlannerRecommendation.RECOMMEND_STEP_ACCEPT))
    for event, payload in (
        (StepEvent.BEGIN_ATTEMPT, {}),
        (StepEvent.ESCALATE, {"reason": "late"}),
        (StepEvent.DECIDE_ACCEPTANCE, {"planner_decision": world.decision(
            PlannerRecommendation.RECOMMEND_RETRY_IMPLEMENTATION)}),
    ):
        with refused(RefusalCode.TERMINAL_STATE):
            world.apply(event, **payload)


def test_a_request_payload_must_match_its_event_exactly(world: World) -> None:
    base = {"request_id": new_request_id(), "expected_state_version": 0}
    with pytest.raises(ValidationError, match="requires verification"):
        StepTransitionRequest(**base, event=StepEvent.VERIFICATION_OBSERVED)
    with pytest.raises(ValidationError, match="does not accept"):
        StepTransitionRequest(**base, event=StepEvent.MARK_READY, reason="extra")
    acceptance = HumanStepAcceptance(
        approved_by="synthetic-operator", approved_at=APPROVED_AT,
        approval_text=REQUIRED_STEP_ACCEPTANCE_APPROVAL_TEXT, source="manual",
        step_contract_sha256=world.contract_a.sha256, attempt=1,
    )
    with pytest.raises(ValidationError, match="human_acceptance"):
        StepTransitionRequest(**base, event=StepEvent.ESCALATE, reason="x",
                              human_acceptance=acceptance)
    with pytest.raises(ValidationError):
        StepTransitionRequest(**{**base, "request_id": "not-hex"}, event=StepEvent.MARK_READY)


def test_a_role_output_bound_to_another_attempt_or_contract_is_refused(world: World) -> None:
    world.to_acceptance("verification-failed", verdict=None)
    from_attempt_1 = world.decision(PlannerRecommendation.RECOMMEND_RETRY_IMPLEMENTATION)
    world.apply(StepEvent.DECIDE_ACCEPTANCE, planner_decision=from_attempt_1)
    world.apply(StepEvent.BEGIN_ATTEMPT)
    world.apply(StepEvent.IMPLEMENTATION_RETURNED, implementation=world.implementation())
    stale_verification = VerificationObservation(
        outcome="verified", evidence_sha256=EVIDENCE,
        step_contract_sha256=world.contract_a.sha256, attempt=1,
    )
    with refused(RefusalCode.BINDING_MISMATCH):
        world.apply(StepEvent.VERIFICATION_OBSERVED, verification=stale_verification)
    other_contract = VerificationObservation(
        outcome="verified", evidence_sha256=EVIDENCE,
        step_contract_sha256=world.contract_b.sha256, attempt=2,
    )
    with refused(RefusalCode.BINDING_MISMATCH):
        world.apply(StepEvent.VERIFICATION_OBSERVED, verification=other_contract)
    assert world.step().state is StepState.VERIFYING


def test_a_non_active_project_freezes_step_progress(world: World) -> None:
    project = world.store.get_project_run(world.project.project_run_id)
    world.store.apply_project_transition(
        project.project_run_id,
        ProjectTransitionRequest(request_id=new_request_id(), expected_state_version=0,
                                 event=ProjectEvent.ESCALATE, reason="Operator stop."),
    )
    assert world.project_state() is ProjectState.HUMAN_REQUIRED
    with refused(RefusalCode.PROJECT_NOT_ACTIVE):
        world.apply(StepEvent.MARK_READY)
    assert world.apply(StepEvent.ESCALATE, reason="Project stopped.").state is (
        StepState.HUMAN_REQUIRED
    )
    with refused(RefusalCode.PROJECT_NOT_ACTIVE):
        world.store.create_step_run(project_run_id=project.project_run_id,
                                    step_contract_sha256=world.contract_a.sha256)


def test_project_completion_is_not_reachable_in_dl1(world: World) -> None:
    for step_run_id in (world.a, world.b):
        world.to_acceptance(step_run_id=step_run_id,
                            verdict="approve" if step_run_id == world.a else None)
        world.apply(StepEvent.DECIDE_ACCEPTANCE, step_run_id, planner_decision=world.decision(
            PlannerRecommendation.RECOMMEND_STEP_ACCEPT, step_run_id))
    assert {s.state for s in world.store.list_step_runs(world.project.project_run_id)} == {
        StepState.COMPLETE
    }
    with refused(RefusalCode.UNSUPPORTED_IN_DL1):
        world.store.apply_project_transition(
            world.project.project_run_id,
            ProjectTransitionRequest(request_id=new_request_id(), expected_state_version=0,
                                     event=ProjectEvent.REQUEST_COMPLETE, reason="All done."),
        )
    assert world.project_state() is ProjectState.ACTIVE


# --- duplicates ------------------------------------------------------------------


def test_an_identical_replay_returns_the_recorded_transition(world: World) -> None:
    request = world.request(StepEvent.MARK_READY)
    first = world.store.apply_step_transition(world.a, request)
    replay = world.store.apply_step_transition(world.a, request)
    assert (first.duplicate, replay.duplicate) == (False, True)
    assert replay.record == first.record
    assert world.step().state_version == 1
    assert len(world.store.transitions_for(world.a)) == 1
    world.apply(StepEvent.BEGIN_ATTEMPT)
    assert world.store.apply_step_transition(world.a, request).duplicate is True
    assert world.step().state is StepState.EXECUTING


def test_a_reused_request_id_for_different_content_is_refused(world: World) -> None:
    request = world.request(StepEvent.MARK_READY)
    world.store.apply_step_transition(world.a, request)
    different = StepTransitionRequest(request_id=request.request_id, expected_state_version=1,
                                      event=StepEvent.BEGIN_ATTEMPT)
    with refused(RefusalCode.DUPLICATE_REQUEST_CONFLICT):
        world.store.apply_step_transition(world.a, different)
    same_on_other_step = request.model_copy()
    with refused(RefusalCode.DUPLICATE_REQUEST_CONFLICT):
        world.store.apply_step_transition(world.b, same_on_other_step)
    assert world.step().state is StepState.READY


# --- interruption and recovery ---------------------------------------------------


def test_a_failure_inside_a_transition_rolls_everything_back(world: World, monkeypatch) -> None:
    world.apply(StepEvent.MARK_READY)

    def crash(*_args, **_kwargs):
        raise RuntimeError("simulated crash after the transition row was written")

    monkeypatch.setattr(world.store, "_update_step_row", crash)
    with pytest.raises(RuntimeError, match="simulated crash"):
        world.apply(StepEvent.BEGIN_ATTEMPT)
    monkeypatch.undo()
    step = world.step()
    assert (step.state, step.attempt, step.state_version) == (StepState.READY, 0, 1)
    assert len(world.store.transitions_for(world.a)) == 1


def test_a_failed_project_propagation_rolls_back_the_step_too(world: World, monkeypatch) -> None:
    world.to_acceptance()

    def crash(*_args, **_kwargs):
        raise RuntimeError("simulated crash during project propagation")

    monkeypatch.setattr(world.store, "_propagate", crash)
    with pytest.raises(RuntimeError, match="propagation"):
        world.apply(StepEvent.DECIDE_ACCEPTANCE, planner_decision=world.decision(
            PlannerRecommendation.PROJECT_CONTRACT_CONFLICT))
    monkeypatch.undo()
    assert world.step().state is StepState.ACCEPTANCE
    assert world.project_state() is ProjectState.ACTIVE


def test_an_uncommitted_write_does_not_survive_the_owner_dying(world: World) -> None:
    connection = world.store._conn
    connection.execute("BEGIN IMMEDIATE")
    connection.execute("UPDATE step_runs SET state = 'COMPLETE' WHERE step_run_id = ?",
                        (world.a,))
    connection.close()  # the owner dies before COMMIT
    world.store = open_store(world.db_path)
    assert world.store.recover(world.project.project_run_id).integrity_ok is True
    assert world.step().state is StepState.PLANNED


def test_a_committed_transition_survives_restart(world: World) -> None:
    world.apply(StepEvent.MARK_READY)
    applied = world.store.transitions_for(world.a)
    world.restart_and_recover()
    assert world.step().state is StepState.READY
    assert world.store.transitions_for(world.a) == applied


@pytest.mark.parametrize("stop_at", ["EXECUTING", "VERIFYING", "REVIEWING"])
def test_restart_moves_in_flight_steps_to_recovery_required(world: World, stop_at) -> None:
    world.apply(StepEvent.MARK_READY)
    world.apply(StepEvent.BEGIN_ATTEMPT)
    if stop_at in ("VERIFYING", "REVIEWING"):
        world.apply(StepEvent.IMPLEMENTATION_RETURNED, implementation=world.implementation())
    if stop_at == "REVIEWING":
        world.apply(StepEvent.VERIFICATION_OBSERVED, verification=world.verification())
    assert world.step().state.value == stop_at

    world.reopen()  # AIDO restarted; the external request's fate is unknown
    report = world.store.recover(world.project.project_run_id)
    assert report.integrity_ok is True
    assert report.recovered_step_run_ids == (world.a,)
    assert world.step().state is StepState.RECOVERY_REQUIRED
    assert world.step(world.b).state is StepState.PLANNED
    assert world.project_state() is ProjectState.RECOVERY_REQUIRED
    assert world.store.transitions_for(world.a)[-1].rule == "interrupted_external_effect_unproven"

    log = world.store.transitions_for(world.a)
    again = world.store.recover(world.project.project_run_id)
    assert again.recovered_step_run_ids == ()
    assert world.store.transitions_for(world.a) == log
    with refused(RefusalCode.TERMINAL_STATE):
        world.apply(StepEvent.IMPLEMENTATION_RETURNED, implementation=world.implementation())


def test_recovery_never_assumes_an_issued_request_succeeded(world: World) -> None:
    """The fake implementer returned, but AIDO died before recording it."""
    implementer = FakeImplementer()
    world.apply(StepEvent.MARK_READY)
    step = world.apply(StepEvent.BEGIN_ATTEMPT)
    implementer.implement(step_contract=world.contract(), attempt=step.attempt)
    assert implementer.calls == 1
    world.reopen()
    world.store.recover(world.project.project_run_id)
    assert world.step().state is StepState.RECOVERY_REQUIRED
    assert world.step().verification_outcome is None


def test_recovery_leaves_steps_without_a_pending_effect_alone(world: World) -> None:
    world.to_acceptance()
    world.apply(StepEvent.ESCALATE, world.b, reason="Synthetic stop.")
    log_before = world.store.transitions_for(world.a)
    world.reopen()
    report = world.store.recover(world.project.project_run_id)
    assert report.recovered_step_run_ids == ()
    assert report.project_state is ProjectState.ACTIVE
    assert world.step().state is StepState.ACCEPTANCE
    assert world.store.transitions_for(world.a) == log_before


# --- untrusted state ---------------------------------------------------------


def test_a_state_edited_outside_the_log_escalates_to_human_required(world: World) -> None:
    world.apply(StepEvent.MARK_READY)
    world.store.close()
    tamper(world.db_path,
           "UPDATE step_runs SET state = 'COMPLETE', state_version = 6 WHERE step_run_id = ?",
           (world.a,))
    world.store = open_store(world.db_path)
    with pytest.raises(StateUntrustedError, match="not explained"):
        world.apply(StepEvent.ESCALATE, reason="anything")
    with pytest.raises(StateUntrustedError):
        world.apply(StepEvent.MARK_READY, world.b)

    report = world.store.recover(world.project.project_run_id)
    assert report.integrity_ok is False
    assert any("not explained" in issue for issue in report.integrity_issues)
    assert set(report.escalated_step_run_ids) == {world.a, world.b}
    assert world.raw()["state"] == "HUMAN_REQUIRED"
    with pytest.raises(StateUntrustedError):  # its row is still unexplained
        world.step()
    assert world.step(world.b).state is StepState.HUMAN_REQUIRED
    assert world.project_state() is ProjectState.HUMAN_REQUIRED

    count = len(world.store.transitions_for(world.a))
    second = world.store.recover(world.project.project_run_id)
    assert second.integrity_ok is False and second.escalated_step_run_ids == ()
    assert len(world.store.transitions_for(world.a)) == count


def test_a_tampered_step_contract_escalates_on_recovery(world: World) -> None:
    world.store.close()
    body = world.contract_a.model_dump_json().replace("Write the helper.", "Delete the tests.")
    tamper(world.db_path, "UPDATE contracts SET body = ? WHERE sha256 = ?",
           (body, world.contract_a.sha256))
    world.store = open_store(world.db_path)
    with pytest.raises(StateUntrustedError):
        world.apply(StepEvent.MARK_READY)
    report = world.store.recover(world.project.project_run_id)
    assert report.integrity_ok is False
    assert world.project_state() is ProjectState.HUMAN_REQUIRED
    assert world.raw()["state"] == "HUMAN_REQUIRED"
    with pytest.raises(StateUntrustedError, match="no longer hashes"):
        world.step()


def test_an_unparseable_project_row_stops_without_writing(world: World) -> None:
    world.store.close()
    tamper(world.db_path, "UPDATE project_runs SET state = 'BOGUS'")
    world.store = open_store(world.db_path)
    with pytest.raises(StateUntrustedError):
        world.store.recover(world.project.project_run_id)
    assert world.store.transitions_for(world.project.project_run_id) == ()


# --- FU1: authority is re-proven at the consumption boundary ----------------------
#
# B1 recovery is a gate, B2 valid objects must also belong together, B3 public
# reads hand out only proven state, B4 a replay is answered only after the same
# proof. The helpers below build requests from the raw row, because a proven
# read is exactly what a reopened, unrecovered run must refuse.

_HAPPY_PATH = ("PLANNED", "READY", "EXECUTING", "VERIFYING", "REVIEWING", "ACCEPTANCE")


def happy_request(world: World, step_run_id=None) -> StepTransitionRequest:
    """The happy-path request that advances the step out of its raw state."""
    row = world.raw(step_run_id)
    bound = {"step_contract_sha256": row["step_contract_sha256"], "attempt": row["attempt"]}
    state = row["state"]
    if state == "PLANNED":
        event, payload = StepEvent.MARK_READY, {}
    elif state == "READY":
        event, payload = StepEvent.BEGIN_ATTEMPT, {}
    elif state == "EXECUTING":
        event = StepEvent.IMPLEMENTATION_RETURNED
        payload = {"implementation": ImplementationReport(summary="Changed one file.", **bound)}
    elif state == "VERIFYING":
        event = StepEvent.VERIFICATION_OBSERVED
        payload = {"verification": VerificationObservation(
            outcome="verified", evidence_sha256=EVIDENCE, **bound)}
    elif state == "REVIEWING":
        event = StepEvent.REVIEW_OBSERVED
        payload = {"review": ReviewProposal(verdict="approve", evidence_sha256=EVIDENCE, **bound)}
    elif state == "ACCEPTANCE":
        event = StepEvent.DECIDE_ACCEPTANCE
        payload = {"planner_decision": PlannerDecision(
            recommendation=PlannerRecommendation.RECOMMEND_STEP_ACCEPT,
            rationale="Synthetic rationale.", **bound)}
    else:
        raise AssertionError(f"no happy-path event leaves {state}")
    return StepTransitionRequest(request_id=new_request_id(),
                                 expected_state_version=row["state_version"],
                                 event=event, **payload)


def drive_to(world: World, stop_at: str, step_run_id=None) -> None:
    assert stop_at in _HAPPY_PATH
    while world.raw(step_run_id)["state"] != stop_at:
        world.store.apply_step_transition(step_run_id or world.a,
                                          happy_request(world, step_run_id))


def forge(world: World, sql: str, params: tuple = ()) -> None:
    """Close the store, edit the file outside it, and open a new session."""
    world.store.close()
    tamper(world.db_path, sql, params)
    world.store = open_store(world.db_path)


def raw_request(world: World, event: StepEvent, step_run_id=None, **payload):
    return StepTransitionRequest(request_id=new_request_id(),
                                 expected_state_version=world.raw(step_run_id)["state_version"],
                                 event=event, **payload)


# B1 — recovery is enforced, not a caller convention.


@pytest.mark.parametrize("stop_at", ["EXECUTING", "VERIFYING", "REVIEWING"])
def test_an_in_flight_step_cannot_be_advanced_after_reopen_without_recover(
    world: World, stop_at
) -> None:
    drive_to(world, stop_at)
    log = world.store.transitions_for(world.a)
    world.reopen()  # AIDO restarted; nobody called recover()

    resume = happy_request(world)
    with pytest.raises(RecoveryRequiredError):
        world.store.apply_step_transition(world.a, resume)
    for event in (StepEvent.ESCALATE, StepEvent.RECOVER_INTERRUPTED):
        with pytest.raises(RecoveryRequiredError):
            world.store.apply_step_transition(world.a, raw_request(
                world, event, reason="A caller's own recovery is not recovery."))
    for read in (lambda: world.store.get_step_run(world.a),
                 lambda: world.store.list_step_runs(world.project.project_run_id),
                 lambda: world.store.get_project_run(world.project.project_run_id)):
        with pytest.raises(RecoveryRequiredError):
            read()
    assert world.raw()["state"] == stop_at
    assert world.store.transitions_for(world.a) == log

    report = world.store.recover(world.project.project_run_id)
    assert (report.integrity_ok, report.recovered_step_run_ids) == (True, (world.a,))
    assert world.step().state is StepState.RECOVERY_REQUIRED
    resumed_late = resume.model_copy(update={"request_id": new_request_id(),
                                             "expected_state_version": world.raw()["state_version"]})
    with refused(RefusalCode.TERMINAL_STATE):  # COMPLETE stays unreachable
        world.store.apply_step_transition(world.a, resumed_late)


@pytest.mark.parametrize("stop_at", ["PLANNED", "READY", "ACCEPTANCE"])
def test_a_step_without_a_pending_effect_resumes_after_reopen_once_recovered(
    world: World, stop_at
) -> None:
    drive_to(world, stop_at)
    log = world.store.transitions_for(world.a)
    world.reopen()
    request = happy_request(world)
    with pytest.raises(RecoveryRequiredError):
        world.store.apply_step_transition(world.a, request)

    report = world.store.recover(world.project.project_run_id)
    assert (report.integrity_ok, report.recovered_step_run_ids, report.project_state) == (
        True, (), ProjectState.ACTIVE)
    assert world.store.transitions_for(world.a) == log
    applied = world.store.apply_step_transition(world.a, request)
    expected = {"PLANNED": "READY", "READY": "EXECUTING", "ACCEPTANCE": "COMPLETE"}[stop_at]
    assert (applied.duplicate, applied.current_state) == (False, expected)
    assert world.store.recover(world.project.project_run_id).recovered_step_run_ids == (
        (world.a,) if expected == "EXECUTING" else ()
    )


def test_a_recovery_that_fails_part_way_leaves_the_run_gated_and_unchanged(
    world: World, monkeypatch
) -> None:
    drive_to(world, "EXECUTING")
    log = world.store.transitions_for(world.a)
    world.reopen()

    def crash(*_args, **_kwargs):
        raise RuntimeError("simulated crash while recover() was writing")

    monkeypatch.setattr(world.store, "_write_step", crash)
    with pytest.raises(RuntimeError, match="simulated crash"):
        world.store.recover(world.project.project_run_id)
    monkeypatch.undo()
    with pytest.raises(RecoveryRequiredError):
        world.store.get_step_run(world.a)
    assert world.raw()["state"] == "EXECUTING"
    assert world.store.transitions_for(world.a) == log
    assert world.store.recover(world.project.project_run_id).recovered_step_run_ids == (world.a,)


def test_recovery_is_per_session_and_a_store_exists_only_through_open(
    world: World, tmp_path: Path
) -> None:
    world.apply(StepEvent.MARK_READY)
    world.restart_and_recover()
    assert world.step().state is StepState.READY
    world.reopen()  # the previous session's recover() does not carry over
    with pytest.raises(RecoveryRequiredError):
        world.store.get_step_run(world.a)
    with pytest.raises(RecoveryRequiredError):
        world.store.create_step_run(project_run_id=world.project.project_run_id,
                                    step_contract_sha256=world.contract_a.sha256)

    connection = sqlite3.connect(tmp_path / "unchecked.sqlite3")
    try:
        with pytest.raises(StoreError, match=r"ControlPlaneStore\.open"):
            ControlPlaneStore(connection, FakeClock())
    finally:
        connection.close()


# B2 — valid objects must also belong together.


def test_cross_step_contract_substitution_is_refused_without_recover(db_path: Path) -> None:
    world = World(db_path, human=True, independent=True)
    try:
        assert (world.contract_a.review_required, world.contract_a.human_acceptance_required) == (
            True, True)
        assert (world.contract_b.review_required, world.contract_b.human_acceptance_required) == (
            False, False)
        forge(world, "UPDATE step_runs SET step_contract_sha256 = ? WHERE step_run_id = ?",
              (world.contract_b.sha256, world.a))
        with pytest.raises(StateUntrustedError, match="contract binding"):
            world.store.apply_step_transition(world.a, happy_request(world))
        for read in (lambda: world.store.get_step_run(world.a),
                     lambda: world.store.list_step_runs(world.project.project_run_id)):
            with pytest.raises(StateUntrustedError, match="contract binding"):
                read()
        assert world.store.transitions_for(world.a) == ()
    finally:
        world.store.close()


def test_cross_step_contract_substitution_is_escalated_by_recover(db_path: Path) -> None:
    world = World(db_path, human=True, independent=True)
    try:
        drive_to(world, "READY")  # not in flight, so only the proof can catch it
        forge(world, "UPDATE step_runs SET step_contract_sha256 = ? WHERE step_run_id = ?",
              (world.contract_b.sha256, world.a))
        report = world.store.recover(world.project.project_run_id)
        assert report.integrity_ok is False
        assert any("another step's contract" in issue for issue in report.integrity_issues)
        assert world.a in report.escalated_step_run_ids
        assert world.raw()["state"] == "HUMAN_REQUIRED"
        assert world.project_state() is ProjectState.HUMAN_REQUIRED
        with pytest.raises(StateUntrustedError):
            world.store.apply_step_transition(world.a, raw_request(world, StepEvent.BEGIN_ATTEMPT))
    finally:
        world.store.close()


def test_a_step_cannot_be_rebound_to_a_weaker_version_of_its_own_contract(db_path) -> None:
    world = World(db_path, human=True)
    try:
        weaker = issue_step_contract(
            make_proposal("step-a"), project_contract=world.pc, execution_plan=world.plan,
            review_required=False, human_acceptance_required=False, max_attempts=2,
            step_contract_version=2, supersedes_sha256=world.contract_a.sha256,
        )
        world.store.record_step_contract(weaker)  # valid on its own, and same step and plan
        drive_to(world, "READY")
        forge(world, "UPDATE step_runs SET step_contract_sha256 = ? WHERE step_run_id = ?",
              (weaker.sha256, world.a))
        with pytest.raises(StateUntrustedError, match="contract binding"):
            world.store.get_step_run(world.a)
        report = world.store.recover(world.project.project_run_id)
        assert report.integrity_ok is False
        assert world.raw()["state"] == "HUMAN_REQUIRED"
    finally:
        world.store.close()


def test_a_consistent_swap_to_another_plan_version_is_refused(world: World) -> None:
    v2 = make_plan(world.pc, version=2, supersedes=world.plan.sha256)
    world.store.record_execution_plan(v2)
    a2 = issue(world.pc, v2, "step-a", review_required=False)
    b2 = issue(world.pc, v2, "step-b", review_required=False)
    world.store.record_step_contract(a2)
    world.store.record_step_contract(b2)
    world.store.close()
    tamper(world.db_path, "UPDATE project_runs SET execution_plan_sha256 = ?, "
           "execution_plan_version = 2", (v2.sha256,))
    tamper(world.db_path, "UPDATE step_runs SET step_contract_sha256 = ? WHERE step_run_id = ?",
           (a2.sha256, world.a))
    tamper(world.db_path, "UPDATE step_runs SET step_contract_sha256 = ? WHERE step_run_id = ?",
           (b2.sha256, world.b))
    world.store = open_store(world.db_path)
    # Every row now agrees with every contract; only the creation bindings do not.
    with pytest.raises(StateUntrustedError, match="contract binding"):
        world.store.get_project_run(world.project.project_run_id)
    report = world.store.recover(world.project.project_run_id)
    assert report.integrity_ok is False
    assert set(report.escalated_step_run_ids) == {world.a, world.b}
    assert world.store.inspect_project_run(world.project.project_run_id).columns["state"] == (
        "HUMAN_REQUIRED")


def test_a_step_moved_to_another_project_run_is_refused(world: World) -> None:
    other = world.store.create_project_run(project_contract_sha256=world.pc.sha256,
                                           execution_plan_sha256=world.plan.sha256)
    forge(world, "UPDATE step_runs SET project_run_id = ? WHERE step_run_id = ?",
          (other.project_run_id, world.a))
    with pytest.raises(StateUntrustedError, match="contract binding"):
        world.store.get_step_run(world.a)
    report = world.store.recover(world.project.project_run_id)
    assert report.integrity_ok is False
    assert any("not the step runs created under it" in issue for issue in report.integrity_issues)
    assert world.store.recover(other.project_run_id).escalated_step_run_ids == (world.a,)


def test_a_deleted_step_run_cannot_be_replaced_by_a_fresh_one(world: World) -> None:
    world.apply(StepEvent.ESCALATE, reason="Synthetic stop.")
    forge(world, "DELETE FROM step_runs WHERE step_run_id = ?", (world.a,))
    with pytest.raises(StateUntrustedError, match="not the step runs created under it"):
        world.store.create_step_run(project_run_id=world.project.project_run_id,
                                    step_contract_sha256=world.contract_a.sha256)
    assert [row.columns["step_run_id"] for row in world.store.inspect_step_runs(
        world.project.project_run_id)] == [world.b]
    assert world.store.recover(world.project.project_run_id).integrity_ok is False


def test_each_step_completes_under_its_own_contract_policy(db_path: Path) -> None:
    world = World(db_path, human=True, independent=True)
    try:
        drive_to(world, "ACCEPTANCE", world.a)
        with refused(RefusalCode.HUMAN_ACCEPTANCE_MISSING):
            world.store.apply_step_transition(world.a, happy_request(world, world.a))
        drive_to(world, "ACCEPTANCE", world.b)
        assert "REVIEWING" not in [r.to_state for r in world.store.transitions_for(world.b)]
        world.store.apply_step_transition(world.b, happy_request(world, world.b))
        world.apply(StepEvent.DECIDE_ACCEPTANCE, planner_decision=world.decision(
            PlannerRecommendation.RECOMMEND_STEP_ACCEPT), human_acceptance=world.human())
        steps = world.store.list_step_runs(world.project.project_run_id)
        assert [(s.step_id, s.state, s.step_contract_sha256) for s in steps] == [
            ("step-a", StepState.COMPLETE, world.contract_a.sha256),
            ("step-b", StepState.COMPLETE, world.contract_b.sha256),
        ]
        assert world.restart_and_recover().integrity_ok is True
        assert world.store.list_step_runs(world.project.project_run_id) == steps
    finally:
        world.store.close()


def test_a_dependency_is_re_proven_before_it_releases_a_dependent(world: World) -> None:
    world.to_acceptance()
    world.apply(StepEvent.DECIDE_ACCEPTANCE,
                planner_decision=world.decision(PlannerRecommendation.RECOMMEND_STEP_ACCEPT))
    # A bug writing through the store's own connection (not a supported path)
    # re-binds the completed dependency to another step's contract.
    world.store._conn.execute(
        "UPDATE step_runs SET step_contract_sha256 = ? WHERE step_run_id = ?",
        (world.contract_b.sha256, world.a))
    with pytest.raises(StateUntrustedError, match="contract binding"):
        world.store.apply_step_transition(world.b, raw_request(world, StepEvent.MARK_READY, world.b))
    assert world.raw(world.b)["state"] == "PLANNED"


# B3 — public reads hand out only proven state.


def test_a_forged_complete_step_row_is_never_returned_as_state(world: World) -> None:
    world.apply(StepEvent.MARK_READY)
    forge(world, "UPDATE step_runs SET state = 'COMPLETE', state_version = 6 "
          "WHERE step_run_id = ?", (world.a,))
    reads = (lambda: world.store.get_step_run(world.a),
             lambda: world.store.list_step_runs(world.project.project_run_id))
    for read in reads:
        with pytest.raises(StateUntrustedError, match="not explained"):
            read()
    raw = world.store.inspect_step_run(world.a)
    assert isinstance(raw, UnverifiedRunRow) and not isinstance(raw, cp.StepRun)
    assert raw.columns["state"] == "COMPLETE"

    world.store.recover(world.project.project_run_id)
    for read in reads:
        with pytest.raises(StateUntrustedError):
            read()
    assert world.raw()["state"] == "HUMAN_REQUIRED"


def test_a_forged_complete_project_row_is_never_returned_as_state(world: World) -> None:
    forge(world, "UPDATE project_runs SET state = 'COMPLETE', state_version = 1")
    for read in (lambda: world.store.get_project_run(world.project.project_run_id),
                 lambda: world.store.list_step_runs(world.project.project_run_id),
                 lambda: world.store.get_step_run(world.a),
                 lambda: world.store.get_step_run(world.b)):
        with pytest.raises(StateUntrustedError, match="not explained"):
            read()
    with pytest.raises(StateUntrustedError, match="not explained"):
        world.store.apply_step_transition(world.a, raw_request(world, StepEvent.MARK_READY))
    assert world.store.inspect_project_run(world.project.project_run_id).columns["state"] == (
        "COMPLETE")
    assert world.store.recover(world.project.project_run_id).integrity_ok is False


@pytest.mark.parametrize(
    ("column", "value"),
    [("review_verdict", "approve"), ("verification_outcome", "verified"), ("attempt", 0)],
)
def test_a_forged_fact_or_attempt_is_never_returned_or_accepted(world: World, column, value):
    world.to_acceptance("verification-failed", None)  # ACCEPTANCE, attempt 1, no verdict
    forge(world, f"UPDATE step_runs SET {column} = ? WHERE step_run_id = ?", (value, world.a))
    with pytest.raises(StateUntrustedError, match="attempt or facts"):
        world.store.get_step_run(world.a)
    accept = PlannerDecision(recommendation=PlannerRecommendation.RECOMMEND_STEP_ACCEPT,
                             rationale="Synthetic rationale.",
                             step_contract_sha256=world.contract_a.sha256, attempt=1)
    with pytest.raises(StateUntrustedError, match="attempt or facts"):
        world.store.apply_step_transition(world.a, raw_request(
            world, StepEvent.DECIDE_ACCEPTANCE, planner_decision=accept))
    assert world.store.recover(world.project.project_run_id).integrity_ok is False
    assert world.raw()["state"] == "HUMAN_REQUIRED"


# B4 — a replay is answered only after the same proof, and only as a receipt.


def test_a_step_replay_after_tampering_is_refused_before_and_after_recover(world: World) -> None:
    request = world.request(StepEvent.MARK_READY)
    world.store.apply_step_transition(world.a, request)
    forge(world, "UPDATE step_runs SET state = 'COMPLETE', state_version = 6 "
          "WHERE step_run_id = ?", (world.a,))
    with pytest.raises(StateUntrustedError, match="not explained"):
        world.store.apply_step_transition(world.a, request)
    world.store.recover(world.project.project_run_id)
    with pytest.raises(StateUntrustedError):
        world.store.apply_step_transition(world.a, request)


def test_a_project_replay_after_tampering_is_refused(world: World) -> None:
    request = ProjectTransitionRequest(request_id=new_request_id(), expected_state_version=0,
                                       event=ProjectEvent.ESCALATE, reason="Operator stop.")
    first = world.store.apply_project_transition(world.project.project_run_id, request)
    again = world.store.apply_project_transition(world.project.project_run_id, request)
    assert (again.duplicate, again.record, again.current_state) == (
        True, first.record, "HUMAN_REQUIRED")
    forge(world, "UPDATE project_runs SET state = 'ACTIVE', state_version = 0")  # undone
    with pytest.raises(StateUntrustedError, match="not explained"):
        world.store.apply_project_transition(world.project.project_run_id, request)
    assert world.store.recover(world.project.project_run_id).integrity_ok is False


def test_a_legitimate_replay_is_a_receipt_carrying_the_current_proven_state(world) -> None:
    world.apply(StepEvent.MARK_READY)
    begin = world.request(StepEvent.BEGIN_ATTEMPT)
    first = world.store.apply_step_transition(world.a, begin)
    assert (first.duplicate, first.current_state, first.current_state_version) == (
        False, "EXECUTING", 2)
    again = world.store.apply_step_transition(world.a, begin)
    assert (again.duplicate, again.record) == (True, first.record)
    assert (again.current_state, again.current_state_version) == ("EXECUTING", 2)

    world.reopen()
    with pytest.raises(RecoveryRequiredError):  # not even a receipt before recovery
        world.store.apply_step_transition(world.a, begin)
    world.store.recover(world.project.project_run_id)
    after = world.store.apply_step_transition(world.a, begin)
    assert (after.duplicate, after.record.to_state) == (True, "EXECUTING")
    assert (after.current_state, after.current_state_version) == ("RECOVERY_REQUIRED", 3)
    assert len(world.store.transitions_for(world.a)) == 3


# Pydantic models built without validation stop at the store boundary.


def test_contracts_built_without_validation_never_reach_the_store(world: World) -> None:
    other = make_project_contract(goal="Another goal.")
    loop = (PlannedStep(step_id="x", objective="y", depends_on=("x",)),)
    for record, contract in (
        (world.store.record_project_contract,
         world.pc.model_copy(update={"content": other.content})),
        (world.store.record_project_contract,
         world.pc.model_copy(update={"approval": world.pc.approval.model_copy(
             update={"approval_text": "ok"})})),
        (world.store.record_execution_plan, world.plan.model_copy(update={"steps": loop})),
        (world.store.record_step_contract,
         world.contract_a.model_copy(update={"max_attempts": 99})),
        (world.store.record_step_contract,
         world.contract_a.model_copy(update={"review_required": "no"})),
        (world.store.record_step_contract, cp.StepContract.model_construct(
            **{**world.contract_a.model_dump(), "max_attempts": 0})),
    ):
        with pytest.raises(ContractRefusedError, match="does not validate"):
            record(contract)


def test_requests_built_without_validation_are_refused(db_path: Path) -> None:
    world = World(db_path, human=True)
    try:
        world.to_acceptance()
        accept = world.decision(PlannerRecommendation.RECOMMEND_STEP_ACCEPT)
        genuine = world.request(StepEvent.DECIDE_ACCEPTANCE, planner_decision=accept,
                                human_acceptance=world.human())
        forged_human = world.human().model_copy(update={"approval_text": "sure",
                                                        "source": "model"})
        for request in (
            genuine.model_copy(update={"human_acceptance": forged_human}),
            genuine.model_copy(update={"planner_decision": accept.model_copy(
                update={"recommendation": "MARK_COMPLETE"})}),
            genuine.model_copy(update={"event": StepEvent.ESCALATE}),
            world.request(StepEvent.MARK_READY).model_copy(
                update={"event": StepEvent.DECIDE_ACCEPTANCE}),
            genuine.model_copy(update={"request_id": "not-a-request-id"}),
            genuine.model_copy(update={"expected_state_version": -1}),
            StepTransitionRequest.model_construct(
                request_id=new_request_id(), expected_state_version=genuine.expected_state_version,
                event=StepEvent.DECIDE_ACCEPTANCE, planner_decision=accept,
                human_acceptance=forged_human),
        ):
            with refused(RefusalCode.INVALID_REQUEST):
                world.store.apply_step_transition(world.a, request)
        with refused(RefusalCode.INVALID_REQUEST):
            world.store.apply_project_transition(
                world.project.project_run_id,
                ProjectTransitionRequest(request_id=new_request_id(), expected_state_version=0,
                                         event=ProjectEvent.ESCALATE, reason="Stop.")
                .model_copy(update={"reason": " "}),
            )
        assert world.step().state is StepState.ACCEPTANCE
        assert world.store.apply_step_transition(world.a, genuine).current_state == "COMPLETE"
    finally:
        world.store.close()


# --- proposals never become authority ------------------------------------------


def test_a_planner_decision_cannot_name_a_state_or_carry_reasoning(world: World) -> None:
    world.apply(StepEvent.MARK_READY)
    world.apply(StepEvent.BEGIN_ATTEMPT)
    base = world.decision(PlannerRecommendation.RECOMMEND_STEP_ACCEPT).model_dump()
    for forged in ({"next_state": "COMPLETE"}, {"to_state": "COMPLETE"},
                   {"reasoning": "hidden chain of thought"}, {"authorized": True}):
        with pytest.raises(ValidationError, match="Extra inputs"):
            PlannerDecision(**{**base, **forged})
    with pytest.raises(ValidationError):
        PlannerDecision(**{**base, "recommendation": "MARK_COMPLETE"})
    for name in ("to_state", "state", "target_state", "next_state"):
        assert name not in StepTransitionRequest.model_fields


def test_a_step_contract_proposal_cannot_set_policy() -> None:
    for forged in ({"max_attempts": 99}, {"review_required": False},
                   {"human_acceptance_required": False},
                   {"verification_authority": "pytest -q"}, {"objective": "Something else."}):
        with pytest.raises(ValidationError, match="Extra inputs"):
            make_proposal(**forged)


def test_a_planner_accept_alone_cannot_complete_a_step(world: World) -> None:
    world.apply(StepEvent.MARK_READY)
    world.apply(StepEvent.BEGIN_ATTEMPT)
    accept = world.decision(PlannerRecommendation.RECOMMEND_STEP_ACCEPT)
    with refused(RefusalCode.OUT_OF_ORDER):
        world.apply(StepEvent.DECIDE_ACCEPTANCE, planner_decision=accept)
    assert world.step().state is StepState.EXECUTING


def test_a_reviewer_approval_only_records_a_fact(world: World) -> None:
    world.apply(StepEvent.MARK_READY)
    world.apply(StepEvent.BEGIN_ATTEMPT)
    world.apply(StepEvent.IMPLEMENTATION_RETURNED, implementation=world.implementation())
    with refused(RefusalCode.OUT_OF_ORDER):
        world.apply(StepEvent.REVIEW_OBSERVED, review=world.review("approve"))
    world.apply(StepEvent.VERIFICATION_OBSERVED, verification=world.verification())
    step = world.apply(StepEvent.REVIEW_OBSERVED, review=world.review("approve"))
    assert step.state is StepState.ACCEPTANCE
    assert step.review_verdict == "approve"
    for forged in ({"commit": True}, {"approve_commit": True}, {"patch": "diff"}):
        with pytest.raises(ValidationError, match="Extra inputs"):
            ReviewProposal(**{**world.review().model_dump(), **forged})


def test_a_tester_cannot_make_its_own_test_authoritative(world: World) -> None:
    proposal = FakeTester().propose_tests(step_contract=world.contract_a, attempt=1)[0]
    assert set(TestProposal.model_fields) == {
        "step_contract_sha256", "attempt", "test_path", "description"
    }
    for forged in ({"authoritative": True}, {"authority_class": "CONTRACT_ACCEPTANCE"},
                   {"baseline_mode": "MUST_GREEN"}):
        with pytest.raises(ValidationError, match="Extra inputs"):
            TestProposal(**{**proposal.model_dump(), **forged})
    with pytest.raises(ValidationError, match="Extra inputs"):
        StepTransitionRequest(request_id=new_request_id(), expected_state_version=0,
                              event=StepEvent.MARK_READY, tests=[proposal.model_dump()])
    assert not any("test_authority" in name for name in dir(cp))


def test_implementer_claims_do_not_replace_verification(world: World) -> None:
    world.apply(StepEvent.MARK_READY)
    world.apply(StepEvent.BEGIN_ATTEMPT)
    report = world.implementation(claims=("All tests pass.", "Worktree is clean."))
    step = world.apply(StepEvent.IMPLEMENTATION_RETURNED, implementation=report)
    assert step.state is StepState.VERIFYING
    assert step.verification_outcome is None


# --- fake role ports -------------------------------------------------------------


class FakePlanner:
    def __init__(self, recommendation: PlannerRecommendation) -> None:
        self.recommendation = recommendation

    def propose_step_contract(self, *, project_contract, execution_plan, step_id):
        return make_proposal(step_id)

    def decide_step(self, *, step_contract, step_run):
        return PlannerDecision(recommendation=self.recommendation, rationale="Fake planner.",
                               step_contract_sha256=step_contract.sha256,
                               attempt=step_run.attempt)


class FakeTester:
    def propose_tests(self, *, step_contract, attempt):
        return (TestProposal(step_contract_sha256=step_contract.sha256, attempt=attempt,
                             test_path="tests/test_greeting.py", description="Greets."),)


class FakeImplementer:
    def __init__(self) -> None:
        self.calls = 0

    def implement(self, *, step_contract, attempt):
        self.calls += 1
        return ImplementationReport(step_contract_sha256=step_contract.sha256, attempt=attempt,
                                    summary="Fake change.", claims=("Done.",))


class FakeVerifier:
    def __init__(self, outcome: VerificationOutcome) -> None:
        self.outcome = outcome

    def verify(self, *, step_contract, attempt):
        return VerificationObservation(step_contract_sha256=step_contract.sha256,
                                       attempt=attempt, outcome=self.outcome,
                                       evidence_sha256=EVIDENCE)


class FakeReviewer:
    def __init__(self, verdict: ReviewVerdict) -> None:
        self.verdict = verdict

    def review(self, *, step_contract, attempt):
        return ReviewProposal(step_contract_sha256=step_contract.sha256, attempt=attempt,
                              verdict=self.verdict, evidence_sha256=EVIDENCE)


def drive_one_attempt(world: World, ports: RolePorts) -> StepState:
    """What a DL-2 inner loop will do, written out by hand with fakes: every
    port output goes through a request and the validator, never around it."""
    contract = world.contract()
    world.apply(StepEvent.MARK_READY)
    step = world.apply(StepEvent.BEGIN_ATTEMPT)
    report = ports.implementer.implement(step_contract=contract, attempt=step.attempt)
    world.apply(StepEvent.IMPLEMENTATION_RETURNED, implementation=report)
    observation = ports.verifier.verify(step_contract=contract, attempt=step.attempt)
    step = world.apply(StepEvent.VERIFICATION_OBSERVED, verification=observation)
    if step.state is StepState.REVIEWING:
        verdict = ports.reviewer.review(step_contract=contract, attempt=step.attempt)
        step = world.apply(StepEvent.REVIEW_OBSERVED, review=verdict)
    if step.state is StepState.ACCEPTANCE:
        decision = ports.planner.decide_step(step_contract=contract, step_run=step)
        step = world.apply(StepEvent.DECIDE_ACCEPTANCE, planner_decision=decision)
    return step.state


@pytest.mark.parametrize(
    ("outcome", "verdict", "recommendation", "expected"),
    [
        ("verified", "approve", PlannerRecommendation.RECOMMEND_STEP_ACCEPT, StepState.COMPLETE),
        ("verified", "changes_requested", PlannerRecommendation.RECOMMEND_STEP_ACCEPT,
         StepState.HUMAN_REQUIRED),
        ("verification-failed", "approve", PlannerRecommendation.RECOMMEND_STEP_ACCEPT,
         StepState.HUMAN_REQUIRED),
        ("verified", "approve", PlannerRecommendation.RECOMMEND_RETRY_IMPLEMENTATION,
         StepState.READY),
        ("workspace-state-untrusted", "approve", PlannerRecommendation.RECOMMEND_STEP_ACCEPT,
         StepState.RECOVERY_REQUIRED),
    ],
)
def test_fake_role_ports_reach_state_only_through_the_validator(
    world: World, outcome, verdict, recommendation, expected
) -> None:
    ports = RolePorts(planner=FakePlanner(recommendation), tester=FakeTester(),
                      implementer=FakeImplementer(), verifier=FakeVerifier(outcome),
                      reviewer=FakeReviewer(verdict))
    assert drive_one_attempt(world, ports) is expected
    proposal = ports.planner.propose_step_contract(
        project_contract=world.pc, execution_plan=world.plan, step_id="step-a")
    assert isinstance(proposal, StepContractProposal)


# --- static boundaries -------------------------------------------------------------

_PACKAGE_DIR = Path(cp.__file__).resolve().parent
_ALLOWED_IMPORTS = {
    "__future__", "collections", "contextlib", "dataclasses", "datetime", "enum", "hashlib",
    "json", "os", "pathlib", "pydantic", "re", "sqlite3", "typing", "uuid",
}


def test_the_control_plane_imports_no_executing_or_network_module() -> None:
    for source in sorted(_PACKAGE_DIR.glob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                if name.startswith("ai_dev_orchestrator."):
                    assert name.startswith("ai_dev_orchestrator.control_plane"), (source, name)
                else:
                    assert name.split(".")[0] in _ALLOWED_IMPORTS, (source.name, name)


def test_no_cli_command_reaches_the_control_plane() -> None:
    cli_source = (_PACKAGE_DIR.parent / "cli.py").read_text(encoding="utf-8")
    assert "control_plane" not in cli_source


def test_vocabulary_mirrors_match_the_shipped_verifier_and_reviewer() -> None:
    from ai_dev_orchestrator.review.models import ReviewVerdict as shipped_verdict
    from ai_dev_orchestrator.verification.verifier import VerificationResultReport

    shipped_outcome = VerificationResultReport.model_fields["outcome"].annotation
    assert typing.get_args(VerificationOutcome) == typing.get_args(shipped_outcome)
    assert typing.get_args(ReviewVerdict) == typing.get_args(shipped_verdict)
