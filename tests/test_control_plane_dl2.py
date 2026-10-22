"""DL-2 — the offline single-Step inner loop.

Every test is offline and synthetic. The store is a SQLite file under pytest
``tmp_path``; contracts, plans and role outputs are synthetic; the role ports
are in-test scripted fakes that record every call. No model, no socket, no
subprocess, no Pi or Node, no Git, no target workspace, and no environment
variable is used.

The suite covers, in order:

- complete paths, with and without required review;
- bounded retry and attempt-budget exhaustion;
- reviewer and Planner outcomes that do not support acceptance, and a required
  human acceptance that DL-2 has no source for;
- project escalation during the loop;
- role failures: exceptions and malformed, stale or mis-bound outputs;
- interruption, controller re-instantiation, store reopen and recovery;
- replayed receipts never causing a dispatch;
- caller objects that do not describe one recorded step;
- adversarial cases from the DL-2 self-review;
- static boundaries: no live execution path.
"""

from __future__ import annotations

import ast
import socket
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import ai_dev_orchestrator.control_plane as cp
from ai_dev_orchestrator.control_plane import (
    ControlPlaneStore,
    ExecutionPlan,
    ImplementationReport,
    InnerLoopInputError,
    InnerLoopStop,
    PlannedStep,
    PlannerDecision,
    PlannerRecommendation,
    ProjectContract,
    ProjectContractApproval,
    ProjectContractContent,
    ProjectEvent,
    ProjectState,
    ProjectTransitionRequest,
    RecoveryRequiredError,
    RefusalCode,
    ReviewProposal,
    RolePorts,
    StepContract,
    StepContractProposal,
    StepEvent,
    StepInnerLoop,
    StepRun,
    StepState,
    StepTransitionRequest,
    VerificationObservation,
    issue_step_contract,
    new_request_id,
)
from ai_dev_orchestrator.control_plane.inner_loop import step_request_id
from ai_dev_orchestrator.control_plane.models import REQUIRED_PROJECT_CONTRACT_APPROVAL_TEXT

APPROVED_AT = datetime(2026, 10, 22, 9, 0, tzinfo=timezone.utc)
EVIDENCE = "e" * 64
INVARIANT = "No network access from the control plane."
ACCEPT = PlannerRecommendation.RECOMMEND_STEP_ACCEPT
RETRY = PlannerRecommendation.RECOMMEND_RETRY_IMPLEMENTATION


# --- builders ---------------------------------------------------------------


def make_project_contract(project_id: str = "synthetic-project") -> ProjectContract:
    content = ProjectContractContent(
        schema_version="project-contract.v1",
        project_id=project_id,
        goal="Add a synthetic greeting helper.",
        requirements=("The helper returns a greeting.",),
        protected_invariants=(INVARIANT,),
        acceptance_criteria=("A greeting test passes.",),
    )
    approval = ProjectContractApproval(
        approved_by="synthetic-operator",
        approved_at=APPROVED_AT,
        approval_text=REQUIRED_PROJECT_CONTRACT_APPROVAL_TEXT,
        source="manual",
        contract_sha256=content.sha256,
    )
    return ProjectContract(content=content, approval=approval)


def make_plan(pc: ProjectContract, *, version: int = 1, supersedes: str | None = None):
    return ExecutionPlan(
        schema_version="execution-plan.v1",
        project_id=pc.project_id,
        project_contract_sha256=pc.sha256,
        plan_version=version,
        supersedes_sha256=supersedes,
        steps=(
            PlannedStep(step_id="step-a", objective="Write the helper."),
            PlannedStep(step_id="step-b", objective="Write a second helper."),
        ),
    )


def issue(pc, plan, step_id="step-a", *, review_required=True, human=False, max_attempts=2):
    return issue_step_contract(
        StepContractProposal(step_id=step_id, requirements=("Return 'hello'.",),
                             protected_invariants=(INVARIANT,)),
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


# --- scripted fake ports ------------------------------------------------------


def play(script: list, default, step_contract, attempt):
    """Run the next scripted behaviour. ``None`` or an exhausted script is the
    role's correct output; an exception instance is raised; a callable gets
    ``(step_contract, attempt)``; anything else is returned as is."""
    item = script.pop(0) if script else None
    if item is None:
        return default()
    if isinstance(item, BaseException):
        raise item
    if callable(item):
        return item(step_contract, attempt)
    return item


class FakeImplementer:
    def __init__(self, log: list, script=()) -> None:
        self.log, self.script = log, list(script)

    def implement(self, *, step_contract, attempt):
        self.log.append(("implementer", attempt))
        return play(self.script, lambda: ImplementationReport(
            step_contract_sha256=step_contract.sha256, attempt=attempt,
            summary="Fake change.", claims=("Done.",)), step_contract, attempt)


class FakeVerifier:
    """Script items that are outcome strings produce a bound observation."""

    def __init__(self, log: list, script=()) -> None:
        self.log, self.script = log, list(script)

    def verify(self, *, step_contract, attempt):
        self.log.append(("verifier", attempt))
        if self.script and isinstance(self.script[0], str):
            outcome = self.script.pop(0)
            return VerificationObservation(step_contract_sha256=step_contract.sha256,
                                           attempt=attempt, outcome=outcome,
                                           evidence_sha256=EVIDENCE)
        return play(self.script, lambda: VerificationObservation(
            step_contract_sha256=step_contract.sha256, attempt=attempt, outcome="verified",
            evidence_sha256=EVIDENCE), step_contract, attempt)


class FakeReviewer:
    """Script items that are verdict strings produce a bound proposal."""

    def __init__(self, log: list, script=()) -> None:
        self.log, self.script = log, list(script)

    def review(self, *, step_contract, attempt):
        self.log.append(("reviewer", attempt))
        if self.script and isinstance(self.script[0], str):
            verdict = self.script.pop(0)
            return ReviewProposal(step_contract_sha256=step_contract.sha256, attempt=attempt,
                                  verdict=verdict, evidence_sha256=EVIDENCE)
        return play(self.script, lambda: ReviewProposal(
            step_contract_sha256=step_contract.sha256, attempt=attempt, verdict="approve",
            evidence_sha256=EVIDENCE), step_contract, attempt)


class FakePlanner:
    """Script items that are recommendations produce a bound decision."""

    def __init__(self, log: list, script=()) -> None:
        self.log, self.script = log, list(script)
        self.seen: list[StepRun] = []

    def propose_step_contract(self, *, project_contract, execution_plan, step_id):
        raise AssertionError("DL-2 never asks the Planner for a contract.")

    def decide_step(self, *, step_contract, step_run):
        self.log.append(("planner", step_run.attempt))
        self.seen.append(step_run)
        if self.script and isinstance(self.script[0], PlannerRecommendation):
            recommendation = self.script.pop(0)
            return PlannerDecision(recommendation=recommendation, rationale="Fake planner.",
                                   step_contract_sha256=step_contract.sha256,
                                   attempt=step_run.attempt)
        return play(self.script, lambda: PlannerDecision(
            recommendation=ACCEPT, rationale="Fake planner.",
            step_contract_sha256=step_contract.sha256, attempt=step_run.attempt),
            step_contract, step_run.attempt)


class FakeTester:
    def propose_tests(self, *, step_contract, attempt):
        raise AssertionError("DL-2 never dispatches the Tester.")


class Scenario:
    """One recorded project run whose step-a is READY under a configurable
    contract, plus scripted ports sharing one call log."""

    def __init__(self, db_path: Path, *, review_required=True, human=False, max_attempts=2,
                 implement=(), verify=(), review=(), decide=(), ready=True):
        self.db_path = db_path
        self.store = open_store(db_path)
        self.pc = make_project_contract()
        self.plan = make_plan(self.pc)
        self.contract = issue(self.pc, self.plan, review_required=review_required, human=human,
                              max_attempts=max_attempts)
        self.contract_b = issue(self.pc, self.plan, "step-b", review_required=False)
        for record, item in ((self.store.record_project_contract, self.pc),
                             (self.store.record_execution_plan, self.plan),
                             (self.store.record_step_contract, self.contract),
                             (self.store.record_step_contract, self.contract_b)):
            record(item)
        self.project = self.store.create_project_run(
            project_contract_sha256=self.pc.sha256, execution_plan_sha256=self.plan.sha256
        )
        self.step = self.store.create_step_run(
            project_run_id=self.project.project_run_id, step_contract_sha256=self.contract.sha256
        )
        self.step_b = self.store.create_step_run(
            project_run_id=self.project.project_run_id,
            step_contract_sha256=self.contract_b.sha256,
        )
        if ready:
            self.apply(StepEvent.MARK_READY)
        self.log: list[tuple[str, int]] = []
        self.ports = self.make_ports(implement=implement, verify=verify, review=review,
                                     decide=decide)

    def make_ports(self, *, implement=(), verify=(), review=(), decide=()) -> RolePorts:
        self.implementer = FakeImplementer(self.log, implement)
        self.verifier = FakeVerifier(self.log, verify)
        self.reviewer = FakeReviewer(self.log, review)
        self.planner = FakePlanner(self.log, decide)
        return RolePorts(planner=self.planner, tester=FakeTester(),
                         implementer=self.implementer, verifier=self.verifier,
                         reviewer=self.reviewer)

    def run(self, **overrides):
        loop = StepInnerLoop(self.store, overrides.pop("ports", self.ports))
        arguments = {
            "project_run": self.project, "step_run": self.step, "project_contract": self.pc,
            "execution_plan": self.plan, "step_contract": self.contract, **overrides,
        }
        return loop.run(**arguments)

    def current(self) -> StepRun:
        return self.store.get_step_run(self.step.step_run_id)

    def project_state(self) -> ProjectState:
        return self.store.get_project_run(self.project.project_run_id).state

    def apply(self, event: StepEvent, **payload):
        request = StepTransitionRequest(
            request_id=new_request_id(),
            expected_state_version=self.current().state_version,
            event=event,
            **payload,
        )
        return self.store.apply_step_transition(self.step.step_run_id, request)

    def escalate_project(self) -> None:
        project = self.store.get_project_run(self.project.project_run_id)
        self.store.apply_project_transition(
            self.project.project_run_id,
            ProjectTransitionRequest(request_id=new_request_id(),
                                     expected_state_version=project.state_version,
                                     event=ProjectEvent.ESCALATE, reason="Synthetic escalation."),
        )

    def events(self) -> list[str]:
        return [record.event for record in self.store.transitions_for(self.step.step_run_id)]

    def roles(self) -> list[str]:
        return [role for role, _ in self.log]

    def reopen(self) -> None:
        self.store.close()
        self.store = open_store(self.db_path)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "aido-control-plane.sqlite3"


@pytest.fixture
def make(db_path: Path):
    scenarios: list[Scenario] = []

    def build(**options) -> Scenario:
        scenario = Scenario(db_path, **options)
        scenarios.append(scenario)
        return scenario

    yield build
    for scenario in scenarios:
        scenario.store.close()


# --- 1-2: complete paths ----------------------------------------------------------


def test_a_step_completes_with_verification_and_required_review(make) -> None:
    s = make(review_required=True)
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_COMPLETE
    assert outcome.step_run == s.current()
    assert outcome.step_run.state is StepState.COMPLETE
    assert outcome.step_run.verification_outcome == "verified"
    assert outcome.step_run.review_verdict == "approve"
    assert outcome.project_run.state is ProjectState.ACTIVE
    assert s.log == [("implementer", 1), ("verifier", 1), ("reviewer", 1), ("planner", 1)]
    assert [d.result for d in outcome.dispatches] == ["valid"] * 4
    assert s.events() == ["mark_ready", "begin_attempt", "implementation_returned",
                          "verification_observed", "review_observed", "decide_acceptance"]
    assert outcome.cause is None and outcome.refusal_code is None


def test_a_step_completes_without_review_when_its_contract_permits(make) -> None:
    s = make(review_required=False)
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_COMPLETE
    assert "reviewer" not in s.roles()
    assert outcome.step_run.review_verdict is None
    assert "review_observed" not in s.events()


def test_the_planner_sees_the_authoritative_step_and_ports_get_the_stored_contract(make):
    s = make()
    s.run()
    (seen,) = s.planner.seen
    assert seen.state is StepState.ACCEPTANCE
    assert seen.verification_outcome == "verified" and seen.review_verdict == "approve"
    assert seen.step_contract_sha256 == s.contract.sha256


# --- 3-4: retry and budget ----------------------------------------------------------


def test_a_failed_verification_is_retried_and_then_succeeds(make) -> None:
    s = make(max_attempts=2, verify=["verification-failed", "verified"], decide=[RETRY, ACCEPT])
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_COMPLETE
    assert outcome.step_run.attempt == 2
    # The failed attempt skips review (the validator routes it to acceptance).
    assert s.log == [("implementer", 1), ("verifier", 1), ("planner", 1),
                     ("implementer", 2), ("verifier", 2), ("reviewer", 2), ("planner", 2)]


def test_the_attempt_budget_is_never_exceeded(make) -> None:
    s = make(max_attempts=2, verify=["verification-failed"] * 5, decide=[RETRY] * 5)
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_FAILED
    assert s.roles().count("implementer") == 2
    assert s.store.transitions_for(s.step.step_run_id)[-1].rule == "attempt_budget_exhausted"


@pytest.mark.parametrize("max_attempts", [1, 3, 5])
def test_a_planner_that_always_retries_is_bounded_by_the_contract(make, max_attempts) -> None:
    s = make(max_attempts=max_attempts, review_required=False, decide=[RETRY] * 10)
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_FAILED
    assert s.roles().count("implementer") == max_attempts
    assert outcome.step_run.attempt == max_attempts


def test_a_project_escalated_by_the_planner_leaves_the_step_at_acceptance(make) -> None:
    def escalate_then_retry(contract, attempt):
        s.escalate_project()
        return PlannerDecision(recommendation=RETRY, rationale="Retry.",
                               step_contract_sha256=contract.sha256, attempt=attempt)

    s = make(verify=["verification-failed"], decide=[escalate_then_retry])
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.PROJECT_NOT_ACTIVE
    assert outcome.step_run.state is StepState.ACCEPTANCE
    assert outcome.refusal_code is RefusalCode.PROJECT_NOT_ACTIVE
    assert s.roles().count("implementer") == 1


# --- 5-7: reviewer, planner and human acceptance ---------------------------------------


@pytest.mark.parametrize("verdict", ["changes_requested", "needs_human_review"])
def test_a_review_that_does_not_approve_cannot_be_accepted(make, verdict) -> None:
    s = make(review=[verdict], decide=[ACCEPT])
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_HUMAN_REQUIRED
    assert outcome.step_run.review_verdict == verdict
    assert s.store.transitions_for(s.step.step_run_id)[-1].rule == (
        "accept_recommended_without_review_approval")


def test_changes_requested_can_lead_to_an_authorized_retry(make) -> None:
    s = make(review=["changes_requested", "approve"], decide=[RETRY, ACCEPT])
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_COMPLETE
    assert outcome.step_run.attempt == 2
    assert s.roles().count("reviewer") == 2


def test_an_accept_recommendation_against_failed_verification_escalates(make) -> None:
    s = make(verify=["verification-failed"], decide=[ACCEPT])
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_HUMAN_REQUIRED
    assert outcome.step_run.verification_outcome == "verification-failed"
    assert "reviewer" not in s.roles()
    assert s.store.transitions_for(s.step.step_run_id)[-1].rule == (
        "accept_recommended_without_verified_outcome")


@pytest.mark.parametrize("recommendation", [
    PlannerRecommendation.RECOMMEND_RETRY_TEST, PlannerRecommendation.RECOMMEND_REPLAN,
    PlannerRecommendation.PLAN_CONFLICT, PlannerRecommendation.HUMAN_REQUIRED,
])
def test_recommendations_dl2_cannot_act_on_end_at_a_human(make, recommendation) -> None:
    s = make(decide=[recommendation])
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_HUMAN_REQUIRED
    assert outcome.project_run.state is ProjectState.ACTIVE


def test_a_project_contract_conflict_escalates_the_project(make) -> None:
    s = make(decide=[PlannerRecommendation.PROJECT_CONTRACT_CONFLICT])
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_HUMAN_REQUIRED
    assert outcome.project_run.state is ProjectState.HUMAN_REQUIRED


def test_a_required_human_acceptance_is_never_fabricated(make) -> None:
    s = make(human=True, decide=[ACCEPT])
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_HUMAN_REQUIRED
    assert outcome.cause == "human_acceptance_unavailable"
    assert outcome.refusal_code is RefusalCode.HUMAN_ACCEPTANCE_MISSING
    assert s.roles().count("planner") == 1
    # The refused decision was never recorded; the escalation was.
    assert s.events()[-2:] == ["review_observed", "escalate"]
    assert "decide_acceptance" not in s.events()


def test_a_human_acceptance_step_may_still_retry_without_a_human(make) -> None:
    s = make(human=True, verify=["verification-failed", "verification-failed"],
             decide=[RETRY, RETRY])
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_FAILED
    assert outcome.cause is None


# --- 8: project escalation -------------------------------------------------------------


def test_a_non_active_project_is_not_advanced(make) -> None:
    s = make()
    s.escalate_project()
    before = s.events()
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.PROJECT_NOT_ACTIVE
    assert outcome.step_run.state is StepState.READY
    assert s.log == [] and s.events() == before


def test_a_project_escalated_while_the_implementer_runs_stops_the_step(make) -> None:
    def escalate_then_report(contract, attempt):
        s.escalate_project()
        return ImplementationReport(step_contract_sha256=contract.sha256, attempt=attempt,
                                    summary="Fake change.")

    s = make(implement=[escalate_then_report])
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_RECOVERY_REQUIRED
    assert outcome.cause == "result_not_recorded" and outcome.cause_role == "implementer"
    assert outcome.refusal_code is RefusalCode.PROJECT_NOT_ACTIVE
    # Severity never drops: the project stays HUMAN_REQUIRED.
    assert outcome.project_run.state is ProjectState.HUMAN_REQUIRED
    assert s.roles() == ["implementer"]


def test_an_untrusted_workspace_stops_the_step_and_the_project(make) -> None:
    s = make(verify=["workspace-state-untrusted"])
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_RECOVERY_REQUIRED
    assert outcome.project_run.state is ProjectState.RECOVERY_REQUIRED
    assert s.roles() == ["implementer", "verifier"]


# --- 9: exceptions from each port -------------------------------------------------------


class Boom(RuntimeError):
    pass


@pytest.mark.parametrize(("role", "expected_roles"), [
    ("implement", ["implementer"]),
    ("verify", ["implementer", "verifier"]),
    ("review", ["implementer", "verifier", "reviewer"]),
])
def test_an_in_flight_role_that_raises_requires_recovery(make, role, expected_roles) -> None:
    s = make(**{role: [Boom("synthetic failure")]})
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_RECOVERY_REQUIRED
    assert outcome.cause == "role_raised"
    assert outcome.dispatches[-1].result == "raised"
    assert outcome.project_run.state is ProjectState.RECOVERY_REQUIRED
    assert s.roles() == expected_roles
    assert s.events()[-1] == "recover_interrupted"


def test_a_planner_that_raises_escalates_without_a_decision(make) -> None:
    s = make(decide=[Boom("synthetic failure")])
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_HUMAN_REQUIRED
    assert outcome.cause == "role_raised" and outcome.cause_role == "planner"
    assert "decide_acceptance" not in s.events()
    assert s.roles().count("planner") == 1


class SimulatedCrash(BaseException):
    """The process dying mid-call: never caught by the loop."""


@pytest.mark.parametrize(("role", "stuck"), [
    ("implement", StepState.EXECUTING),
    ("verify", StepState.VERIFYING),
    ("review", StepState.REVIEWING),
])
def test_a_crash_leaves_the_persisted_intent_and_restart_never_reruns_it(
    make, role, stuck
) -> None:
    s = make(**{role: [SimulatedCrash()]})
    with pytest.raises(SimulatedCrash):
        s.run()
    assert s.store.inspect_step_run(s.step.step_run_id).columns["state"] == stuck.value
    calls_before = list(s.log)

    s.reopen()
    with pytest.raises(RecoveryRequiredError):
        s.run(ports=s.make_ports())
    report = s.store.recover(s.project.project_run_id)
    assert report.recovered_step_run_ids == (s.step.step_run_id,)

    log: list = []
    s.log = log
    outcome = s.run(ports=s.make_ports())
    assert outcome.stop is InnerLoopStop.STEP_RECOVERY_REQUIRED
    assert outcome.dispatches == () and log == []
    assert outcome.project_run.state is ProjectState.RECOVERY_REQUIRED
    assert len(calls_before) >= 1


# --- 10: restart and re-instantiation -----------------------------------------------------


def drive_to(s: Scenario, state: StepState) -> None:
    """Persist a step at ``state`` by hand, as an interrupted earlier call would."""
    contract, step = s.contract, s.current()
    s.apply(StepEvent.BEGIN_ATTEMPT)
    if state is StepState.EXECUTING:
        return
    bound = {"step_contract_sha256": contract.sha256, "attempt": step.attempt + 1}
    s.apply(StepEvent.IMPLEMENTATION_RETURNED,
            implementation=ImplementationReport(summary="Earlier change.", **bound))
    if state is StepState.VERIFYING:
        return
    s.apply(StepEvent.VERIFICATION_OBSERVED,
            verification=VerificationObservation(outcome="verified", evidence_sha256=EVIDENCE,
                                                 **bound))
    if state is StepState.REVIEWING:
        return
    s.apply(StepEvent.REVIEW_OBSERVED,
            review=ReviewProposal(verdict="approve", evidence_sha256=EVIDENCE, **bound))


IN_FLIGHT = [StepState.EXECUTING, StepState.VERIFYING, StepState.REVIEWING]


@pytest.mark.parametrize("state", IN_FLIGHT)
def test_a_reopened_store_must_be_recovered_and_in_flight_work_is_not_resumed(make, state):
    s = make()
    drive_to(s, state)
    s.reopen()
    with pytest.raises(RecoveryRequiredError):
        s.run()
    assert s.log == []
    s.store.recover(s.project.project_run_id)
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_RECOVERY_REQUIRED
    assert s.log == [] and outcome.dispatches == ()


@pytest.mark.parametrize("state", IN_FLIGHT)
def test_a_new_controller_in_the_same_session_never_resumes_in_flight_work(make, state):
    s = make()
    drive_to(s, state)
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_RECOVERY_REQUIRED
    assert outcome.cause == "in_flight_not_dispatched_here"
    assert outcome.project_run.state is ProjectState.RECOVERY_REQUIRED
    assert s.log == []
    assert s.events()[-1] == "recover_interrupted"


def test_a_step_at_acceptance_resumes_after_reopen_without_rerunning_work(make) -> None:
    s = make()
    drive_to(s, StepState.ACCEPTANCE)
    s.reopen()
    s.store.recover(s.project.project_run_id)
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_COMPLETE
    assert s.log == [("planner", 1)]


def test_a_ready_step_after_a_recorded_retry_resumes_on_the_next_attempt(make) -> None:
    s = make(max_attempts=2, review_required=False)
    drive_to(s, StepState.VERIFYING)
    bound = {"step_contract_sha256": s.contract.sha256, "attempt": 1}
    s.apply(StepEvent.VERIFICATION_OBSERVED,
            verification=VerificationObservation(outcome="verification-failed",
                                                 evidence_sha256=EVIDENCE, **bound))
    s.apply(StepEvent.DECIDE_ACCEPTANCE,
            planner_decision=PlannerDecision(recommendation=RETRY, rationale="Retry.", **bound))
    assert s.current().state is StepState.READY
    s.reopen()
    s.store.recover(s.project.project_run_id)
    outcome = s.run(ports=s.make_ports(verify=["verification-failed"], decide=[RETRY]))
    # Only one attempt was left: the budget is persisted, not per controller.
    assert outcome.stop is InnerLoopStop.STEP_FAILED
    assert s.roles().count("implementer") == 1
    assert outcome.step_run.attempt == 2


def test_a_terminal_step_is_never_redispatched(make) -> None:
    s = make()
    assert s.run().stop is InnerLoopStop.STEP_COMPLETE
    s.log.clear()
    for _ in range(2):
        again = s.run()
        assert again.stop is InnerLoopStop.STEP_COMPLETE and again.dispatches == ()
    s.reopen()
    s.store.recover(s.project.project_run_id)
    assert s.run().dispatches == ()
    assert s.log == []


def test_a_planned_step_is_not_scheduled_by_the_inner_loop(make) -> None:
    s = make(ready=False)
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_NOT_READY
    assert s.events() == [] and s.log == []


# --- 11: replay -------------------------------------------------------------------------


class ReplayingStore(ControlPlaneStore):
    """Applies the chosen event twice, so the loop gets the second answer: the
    receipt of a request that an earlier, interrupted call already committed."""

    replay_event: StepEvent | None = None

    def apply_step_transition(self, step_run_id, request):
        if request.event is self.replay_event:
            super().apply_step_transition(step_run_id, request)
        return super().apply_step_transition(step_run_id, request)


@pytest.mark.parametrize(("event", "expected_roles"), [
    (StepEvent.BEGIN_ATTEMPT, []),
    (StepEvent.IMPLEMENTATION_RETURNED, ["implementer"]),
    (StepEvent.VERIFICATION_OBSERVED, ["implementer", "verifier"]),
])
def test_a_replayed_receipt_never_dispatches_a_role(make, db_path, event, expected_roles):
    s = make()
    s.store.close()
    s.store = ReplayingStore.open(db_path, clock=FakeClock())
    s.store.recover(s.project.project_run_id)
    s.store.replay_event = event
    outcome = s.run()
    assert outcome.cause == "replayed_receipt"
    assert s.roles() == expected_roles
    assert outcome.stop is InnerLoopStop.STEP_RECOVERY_REQUIRED


def test_a_replayed_decision_does_not_start_another_attempt(make, db_path) -> None:
    s = make(verify=["verification-failed"], decide=[RETRY])
    s.store.close()
    s.store = ReplayingStore.open(db_path, clock=FakeClock())
    s.store.recover(s.project.project_run_id)
    s.store.replay_event = StepEvent.DECIDE_ACCEPTANCE
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.REPLAYED_RECEIPT
    assert outcome.step_run.state is StepState.READY
    assert s.roles().count("implementer") == 1


def test_re_sending_a_recorded_request_is_a_receipt_and_dispatches_nothing(make) -> None:
    s = make()
    s.run()
    begin = s.store.transitions_for(s.step.step_run_id)[1]
    request = StepTransitionRequest(
        request_id=step_request_id(s.step.step_run_id, begin.from_version,
                                   StepEvent.BEGIN_ATTEMPT),
        expected_state_version=begin.from_version,
        event=StepEvent.BEGIN_ATTEMPT,
    )
    applied = s.store.apply_step_transition(s.step.step_run_id, request)
    assert applied.duplicate and applied.record.to_state == "EXECUTING"
    assert applied.current_state == "COMPLETE"
    s.log.clear()
    assert s.run().dispatches == () and s.log == []


def test_a_role_that_pre_records_its_own_result_gets_no_further_dispatch(make) -> None:
    def record_then_report(contract, attempt):
        report = ImplementationReport(step_contract_sha256=contract.sha256, attempt=attempt,
                                      summary="Fake change.", claims=("Done.",))
        step = s.current()
        s.store.apply_step_transition(s.step.step_run_id, StepTransitionRequest(
            request_id=step_request_id(step.step_run_id, step.state_version,
                                       StepEvent.IMPLEMENTATION_RETURNED),
            expected_state_version=step.state_version,
            event=StepEvent.IMPLEMENTATION_RETURNED,
            implementation=report,
        ))
        return report

    s = make(implement=[record_then_report])
    outcome = s.run()
    assert outcome.cause == "replayed_receipt"
    assert s.roles() == ["implementer"]
    assert outcome.stop is InnerLoopStop.STEP_RECOVERY_REQUIRED


# --- 12: caller objects ------------------------------------------------------------------


def second_project(s: Scenario):
    """Another project run in the same store with the same contract and plan."""
    other = s.store.create_project_run(project_contract_sha256=s.pc.sha256,
                                       execution_plan_sha256=s.plan.sha256)
    step = s.store.create_step_run(project_run_id=other.project_run_id,
                                   step_contract_sha256=s.contract.sha256)
    return other, step


def other_plan(s: Scenario):
    plan2 = make_plan(s.pc, version=2, supersedes=s.plan.sha256)
    s.store.record_execution_plan(plan2)
    return plan2


@pytest.mark.parametrize("swap", [
    "step_contract_of_another_step", "project_run_of_another_run", "step_run_of_another_run",
    "another_plan_version", "another_project_contract", "forged_project_identity",
    "forged_step_identity",
])
def test_objects_that_do_not_belong_together_are_refused(make, swap) -> None:
    s = make()
    if swap == "step_contract_of_another_step":
        overrides = {"step_contract": s.contract_b}
    elif swap == "project_run_of_another_run":
        overrides = {"project_run": second_project(s)[0]}
    elif swap == "step_run_of_another_run":
        overrides = {"step_run": second_project(s)[1]}
    elif swap == "another_plan_version":
        overrides = {"execution_plan": other_plan(s)}
    elif swap == "another_project_contract":
        overrides = {"project_contract": make_project_contract("other-project")}
    elif swap == "forged_project_identity":
        overrides = {"project_run": s.project.model_copy(
            update={"execution_plan_sha256": "f" * 64})}
    else:
        overrides = {"step_run": s.step.model_copy(update={"step_id": "step-b"})}
    before = s.events()
    with pytest.raises(InnerLoopInputError):
        s.run(**overrides)
    assert s.log == [] and s.events() == before


def test_a_supplied_snapshot_state_is_never_consulted(make) -> None:
    s = make()
    forged = s.step.model_copy(update={"state": StepState.COMPLETE, "attempt": 5,
                                       "verification_outcome": "verified"})
    outcome = s.run(step_run=forged)
    assert outcome.stop is InnerLoopStop.STEP_COMPLETE
    assert outcome.step_run.attempt == 1
    assert s.roles() == ["implementer", "verifier", "reviewer", "planner"]


class LooseContract(StepContract):
    pass


@pytest.mark.parametrize("bad", ["subclass", "unvalidated_policy", "not_a_model"])
def test_a_contract_that_is_not_exactly_a_validated_step_contract_is_refused(make, bad):
    s = make(review_required=True)
    if bad == "subclass":
        contract = LooseContract.model_validate(s.contract.model_dump())
    elif bad == "unvalidated_policy":
        contract = StepContract.model_construct(
            **{**s.contract.model_dump(), "review_required": 0})
    else:
        contract = s.contract.model_dump()
    with pytest.raises(InnerLoopInputError):
        s.run(step_contract=contract)
    assert s.log == []


def test_a_weaker_policy_copy_of_the_contract_is_refused(make) -> None:
    s = make(review_required=True, max_attempts=2)
    weaker = s.contract.model_copy(update={"review_required": False, "max_attempts": 5})
    with pytest.raises(InnerLoopInputError):
        s.run(step_contract=weaker)
    assert s.log == []


def test_ports_missing_a_role_method_are_refused_before_anything_runs(make) -> None:
    s = make()

    class NoVerify:
        pass

    ports = RolePorts(planner=s.planner, tester=FakeTester(), implementer=s.implementer,
                      verifier=NoVerify(), reviewer=s.reviewer)
    with pytest.raises(InnerLoopInputError):
        StepInnerLoop(s.store, ports)
    with pytest.raises(InnerLoopInputError):
        StepInnerLoop(object(), s.ports)
    assert s.events() == ["mark_ready"]


# --- 13: malformed role outputs ------------------------------------------------------------


def misbound_attempt(model, **fields):
    return lambda contract, attempt: model(step_contract_sha256=contract.sha256,
                                           attempt=attempt + 1, **fields)


def misbound_contract(model, **fields):
    return lambda contract, attempt: model(step_contract_sha256="0" * 64, attempt=attempt,
                                           **fields)


def unvalidated(model, **fields):
    return lambda contract, attempt: model.model_construct(
        step_contract_sha256=contract.sha256, attempt=attempt, **fields)


class SubReport(ImplementationReport):
    pass


class SubObservation(VerificationObservation):
    pass


REPORT = {"summary": "Fake change."}
OBSERVED = {"outcome": "verified", "evidence_sha256": EVIDENCE}
REVIEWED = {"verdict": "approve", "evidence_sha256": EVIDENCE}
DECIDED = {"recommendation": ACCEPT, "rationale": "Accept."}

@pytest.mark.parametrize(("role", "item", "result"), [
    ("implement", lambda c, a: None, "malformed"),
    ("implement", lambda c, a: {"summary": "dict"}, "malformed"),
    ("implement", lambda c, a: VerificationObservation(
        step_contract_sha256=c.sha256, attempt=a, **OBSERVED), "malformed"),
    ("implement", lambda c, a: SubReport(step_contract_sha256=c.sha256, attempt=a, **REPORT),
     "malformed"),
    ("implement", unvalidated(ImplementationReport, summary="   "), "malformed"),
    ("implement", misbound_attempt(ImplementationReport, **REPORT), "misbound"),
    ("implement", misbound_contract(ImplementationReport, **REPORT), "misbound"),
    ("verify", unvalidated(VerificationObservation, outcome="passed",
                           evidence_sha256=EVIDENCE), "malformed"),
    ("verify", unvalidated(VerificationObservation, outcome=True,
                           evidence_sha256=EVIDENCE), "malformed"),
    ("verify", lambda c, a: SubObservation(step_contract_sha256=c.sha256, attempt=a,
                                           **OBSERVED), "malformed"),
    ("verify", lambda c, a: VerificationObservation.model_construct(
        step_contract_sha256=c.sha256, attempt=str(a), **OBSERVED), "malformed"),
    ("verify", misbound_attempt(VerificationObservation, **OBSERVED), "misbound"),
    ("review", unvalidated(ReviewProposal, verdict="lgtm", evidence_sha256=EVIDENCE),
     "malformed"),
    ("review", lambda c, a: ImplementationReport(step_contract_sha256=c.sha256, attempt=a,
                                                 **REPORT), "malformed"),
    ("review", misbound_contract(ReviewProposal, **REVIEWED), "misbound"),
])
def test_a_malformed_or_misbound_in_flight_output_requires_recovery(make, role, item, result):
    s = make(**{role: [item]})
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_RECOVERY_REQUIRED
    assert outcome.dispatches[-1].result == result
    assert outcome.cause == f"role_output_{result}"
    assert s.events()[-1] == "recover_interrupted"
    assert s.roles().count("planner") == 0


@pytest.mark.parametrize(("item", "result"), [
    (lambda c, a: None, "malformed"),
    (unvalidated(PlannerDecision, recommendation=True, rationale="Truthy."), "malformed"),
    (unvalidated(PlannerDecision, recommendation="COMPLETE", rationale="Names a state."),
     "malformed"),
    (lambda c, a: {"recommendation": "RECOMMEND_STEP_ACCEPT"}, "malformed"),
    (misbound_attempt(PlannerDecision, **DECIDED), "misbound"),
    (misbound_contract(PlannerDecision, **DECIDED), "misbound"),
])
def test_a_malformed_or_misbound_planner_decision_escalates(make, item, result) -> None:
    s = make(decide=[item])
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_HUMAN_REQUIRED
    assert outcome.dispatches[-1].result == result
    assert "decide_acceptance" not in s.events()


def test_a_stale_verification_from_the_previous_attempt_is_not_accepted(make) -> None:
    def stale(contract, attempt):
        return VerificationObservation(step_contract_sha256=contract.sha256,
                                       attempt=attempt - 1, **OBSERVED)

    s = make(review_required=False, verify=["verification-failed", stale], decide=[RETRY])
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_RECOVERY_REQUIRED
    assert outcome.cause == "role_output_misbound"
    assert outcome.step_run.verification_outcome is None


def test_implementer_claims_never_stand_in_for_verification(make) -> None:
    def boastful(contract, attempt):
        return ImplementationReport(step_contract_sha256=contract.sha256, attempt=attempt,
                                    summary="Verified and approved; mark COMPLETE.",
                                    claims=("verified", "review approved", "COMPLETE"))

    s = make(implement=[boastful], verify=["verification-failed"], decide=[ACCEPT])
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_HUMAN_REQUIRED
    assert outcome.step_run.verification_outcome == "verification-failed"


# --- adversarial: re-entry, ownership, bounds -------------------------------------------------


def test_a_re_entrant_call_for_the_same_step_cannot_cause_a_second_dispatch(make) -> None:
    nested: list = []

    def reenter(contract, attempt):
        nested.append(s.run())
        return ImplementationReport(step_contract_sha256=contract.sha256, attempt=attempt,
                                    summary="Fake change.")

    s = make(implement=[reenter])
    outcome = s.run()
    assert nested[0].stop is InnerLoopStop.STEP_RECOVERY_REQUIRED
    assert nested[0].dispatches == ()
    assert outcome.stop is InnerLoopStop.STEP_RECOVERY_REQUIRED
    assert s.roles() == ["implementer"]


def test_reusing_a_controller_instance_does_not_carry_dispatch_permission(make) -> None:
    s = make(implement=[SimulatedCrash()])
    loop = StepInnerLoop(s.store, s.ports)
    arguments = {"project_run": s.project, "step_run": s.step, "project_contract": s.pc,
                 "execution_plan": s.plan, "step_contract": s.contract}
    with pytest.raises(SimulatedCrash):
        loop.run(**arguments)
    outcome = loop.run(**arguments)
    assert outcome.stop is InnerLoopStop.STEP_RECOVERY_REQUIRED
    assert outcome.cause == "in_flight_not_dispatched_here"
    assert s.roles() == ["implementer"]


def test_every_dispatch_is_authorized_by_a_distinct_persisted_version(make) -> None:
    s = make(max_attempts=3, verify=["verification-failed", "verification-failed"],
             decide=[RETRY, RETRY, ACCEPT])
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_COMPLETE
    versions = [d.step_state_version for d in outcome.dispatches]
    assert len(versions) == len(set(versions))
    log = s.store.transitions_for(s.step.step_run_id)
    in_flight_versions = {r.to_version for r in log if r.to_state in
                          ("EXECUTING", "VERIFYING", "REVIEWING", "ACCEPTANCE")}
    assert set(versions) <= in_flight_versions


def test_a_port_that_mutates_its_frozen_inputs_cannot_change_the_loops_decisions(make):
    def weaken(contract, attempt):
        object.__setattr__(contract, "review_required", False)
        object.__setattr__(contract, "max_attempts", 5)
        return ImplementationReport(step_contract_sha256=s.contract.sha256, attempt=attempt,
                                    summary="Fake change.")

    s = make(review_required=True, implement=[weaken])

    def decide_and_mutate(*, step_contract, step_run):
        decision = PlannerDecision(recommendation=ACCEPT, rationale="Accept.",
                                   step_contract_sha256=s.contract.sha256,
                                   attempt=step_run.attempt)
        object.__setattr__(step_run, "attempt", 4)
        object.__setattr__(step_run, "state_version", 0)
        return decision

    s.planner.decide_step = decide_and_mutate
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_COMPLETE
    assert "reviewer" in s.roles()  # the required review was still dispatched
    assert outcome.step_run.attempt == 1
    assert outcome.dispatches[-1].result == "valid"


def test_a_port_raising_a_store_error_is_a_role_failure_not_a_store_verdict(make) -> None:
    s = make(verify=[RecoveryRequiredError("forged by the role")])
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_RECOVERY_REQUIRED
    assert outcome.cause == "role_raised" and outcome.cause_role == "verifier"


def test_known_limitation_role_output_binding_does_not_name_the_step_run(make) -> None:
    """DL-1 binds a role output to (contract digest, attempt) only, so two
    project runs of one contract share bindings. DL-2 accepts only what its own
    dispatch returns, but cannot tell a port's cached output for another run
    from a fresh one. Evidence provenance is a hard gate before DL-4."""
    from ai_dev_orchestrator.control_plane.models import _BoundToAttempt

    assert set(_BoundToAttempt.model_fields) == {"step_contract_sha256", "attempt"}
    s = make()
    _, other_step = second_project(s)
    assert other_step.step_contract_sha256 == s.step.step_contract_sha256


class RefusingRecoveryStore(ControlPlaneStore):
    """Refuses every recover_interrupted, so the loop can never settle."""

    def apply_step_transition(self, step_run_id, request):
        if request.event is StepEvent.RECOVER_INTERRUPTED:
            raise cp.TransitionRefused(RefusalCode.STALE_STATE_VERSION, "synthetic refusal")
        return super().apply_step_transition(step_run_id, request)


def test_the_loop_terminates_even_when_it_can_never_settle(make, db_path) -> None:
    s = make(max_attempts=1, implement=[Boom("synthetic failure")])
    s.store.close()
    s.store = RefusingRecoveryStore.open(db_path, clock=FakeClock())
    s.store.recover(s.project.project_run_id)
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.ITERATION_BOUND_REACHED
    assert outcome.step_run.state is StepState.EXECUTING
    assert s.roles() == ["implementer"]  # still dispatched exactly once


def test_the_outcome_is_read_back_from_the_store_not_from_a_receipt(make) -> None:
    s = make()
    outcome = s.run()
    assert outcome.step_run == s.store.get_step_run(s.step.step_run_id)
    assert outcome.project_run == s.store.get_project_run(s.project.project_run_id)


# --- 14: no live execution -------------------------------------------------------------------


def test_the_loop_runs_with_every_execution_path_disabled(make, monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("DL-2 must not reach a process, socket or shell.")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    import os
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(os, "getenv", forbidden)
    s = make(verify=["verification-failed", "verified"], decide=[RETRY, ACCEPT])
    assert s.run().stop is InnerLoopStop.STEP_COMPLETE


_INNER_LOOP = Path(cp.__file__).resolve().parent / "inner_loop.py"
_ALLOWED = {"__future__", "enum", "hashlib", "typing", "pydantic"}


def test_the_inner_loop_imports_nothing_that_executes() -> None:
    tree = ast.parse(_INNER_LOOP.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        for name in names:
            if name.startswith("ai_dev_orchestrator."):
                assert name.startswith("ai_dev_orchestrator.control_plane."), name
            else:
                assert name.split(".")[0] in _ALLOWED, name


def test_the_inner_loop_has_no_workspace_or_path_surface() -> None:
    tree = ast.parse(_INNER_LOOP.read_text(encoding="utf-8"))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    forbidden = {"open", "Path", "environ", "getenv", "system", "Popen", "socket",
                 "subprocess", "httpx", "sqlite3", "_conn", "connect"}
    assert not names & forbidden, names & forbidden


def test_no_cli_command_reaches_the_inner_loop() -> None:
    cli_source = (Path(cp.__file__).resolve().parent.parent / "cli.py").read_text(
        encoding="utf-8")
    assert "inner_loop" not in cli_source and "StepInnerLoop" not in cli_source
