"""DL-3 — the offline project outer loop.

Every test is offline and synthetic. The store is a SQLite file under pytest
``tmp_path``; contracts, plans and role outputs are synthetic; the role ports
are in-test scripted fakes, keyed by step id, that record every call. No model,
no socket, no subprocess, no Pi or Node, no Git, no target workspace, and no
environment variable is used.

The suite covers, in order:

- deterministic multi-step completion and dependency-aware scheduling;
- retries within a step's own budget, and blocked steps stopping the project;
- HUMAN_REQUIRED / RECOVERY_REQUIRED never being resolved;
- project escalation during a step;
- restart, recovery and in-flight work never being re-dispatched;
- replayed scheduling and project transitions;
- caller objects that do not describe one recorded run;
- plan versions, supersession and re-planning;
- the completion gate and what it cannot prove;
- bounds under refusal and inconsistent stores;
- adversarial cases from the DL-3 self-review;
- static boundaries: no live execution path.
"""

from __future__ import annotations

import ast
import socket
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

import ai_dev_orchestrator.control_plane as cp
from ai_dev_orchestrator.control_plane import (
    AppliedTransition,
    ContractRefusedError,
    ControlPlaneStore,
    ExecutionPlan,
    ImplementationReport,
    InnerLoopStop,
    OuterLoopInputError,
    OuterLoopReentryError,
    OuterLoopStop,
    PlannedStep,
    PlannerDecision,
    PlannerRecommendation,
    ProjectCompletionAssessment,
    ProjectContract,
    ProjectContractApproval,
    ProjectContractContent,
    ProjectEvent,
    ProjectOuterLoop,
    ProjectRun,
    ProjectState,
    ProjectTransitionRequest,
    RecoveryRequiredError,
    RefusalCode,
    ReviewProposal,
    RolePorts,
    StateUntrustedError,
    StepContractProposal,
    StepEvent,
    StepRun,
    StepState,
    StepTransitionRequest,
    TransitionRefused,
    VerificationObservation,
    assess_project_completion,
    issue_step_contract,
    new_request_id,
)
from ai_dev_orchestrator.control_plane.models import REQUIRED_PROJECT_CONTRACT_APPROVAL_TEXT
from ai_dev_orchestrator.control_plane.outer_loop import outer_request_id
from ai_dev_orchestrator.control_plane.store import TransitionRecord

APPROVED_AT = datetime(2026, 10, 22, 9, 0, tzinfo=timezone.utc)
EVIDENCE = "e" * 64
INVARIANT = "No network access from the control plane."
ACCEPT = PlannerRecommendation.RECOMMEND_STEP_ACCEPT
RETRY = PlannerRecommendation.RECOMMEND_RETRY_IMPLEMENTATION
REPLAN = PlannerRecommendation.RECOMMEND_REPLAN

#: (step id, depends on). Plan order is the scheduling order.
INDEPENDENT = (("step-a", ()), ("step-b", ()), ("step-c", ()))
CHAIN = (("step-a", ()), ("step-b", ("step-a",)), ("step-c", ("step-b",)))
DIAMOND = (("step-a", ()), ("step-b", ("step-a",)), ("step-c", ()),
           ("step-d", ("step-b", "step-c")))


# --- builders ---------------------------------------------------------------


def make_project_contract(project_id: str = "synthetic-project") -> ProjectContract:
    content = ProjectContractContent(
        schema_version="project-contract.v1",
        project_id=project_id,
        goal="Add synthetic helpers.",
        requirements=("Each helper returns a greeting.",),
        protected_invariants=(INVARIANT,),
        acceptance_criteria=("Every greeting test passes together.",),
    )
    approval = ProjectContractApproval(
        approved_by="synthetic-operator",
        approved_at=APPROVED_AT,
        approval_text=REQUIRED_PROJECT_CONTRACT_APPROVAL_TEXT,
        source="manual",
        contract_sha256=content.sha256,
    )
    return ProjectContract(content=content, approval=approval)


def make_plan(pc, steps, *, version: int = 1, supersedes: str | None = None) -> ExecutionPlan:
    return ExecutionPlan(
        schema_version="execution-plan.v1",
        project_id=pc.project_id,
        project_contract_sha256=pc.sha256,
        plan_version=version,
        supersedes_sha256=supersedes,
        steps=tuple(PlannedStep(step_id=step_id, objective=f"Write {step_id}.",
                                depends_on=deps) for step_id, deps in steps),
    )


def issue(pc, plan, step_id, *, review_required=False, human=False, max_attempts=2):
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


def open_store(path: Path, store_class=ControlPlaneStore) -> ControlPlaneStore:
    return store_class.open(path, clock=FakeClock())


# --- scripted fake ports, keyed by step id ----------------------------------------


def play(scripts: dict, step_id: str, default, contract, attempt):
    """The next scripted item for ``step_id``. ``None`` or an exhausted script
    is the role's correct output; an exception is raised; a callable gets
    ``(step_contract, attempt)``; a plain string or recommendation is turned
    into a bound output by ``default``."""
    script = scripts.get(step_id, [])
    item = script.pop(0) if script else None
    if isinstance(item, BaseException):
        raise item
    if callable(item):
        return item(contract, attempt)
    return default(item)


class FakeImplementer:
    def __init__(self, world, scripts) -> None:
        self.world, self.scripts = world, scripts

    def implement(self, *, step_contract, attempt):
        self.world.log.append(("implementer", step_contract.step_id, attempt))
        return play(self.scripts, step_contract.step_id, lambda _: ImplementationReport(
            step_contract_sha256=step_contract.sha256, attempt=attempt,
            summary="Fake change.", claims=("Done and verified.",)), step_contract, attempt)


class FakeVerifier:
    def __init__(self, world, scripts) -> None:
        self.world, self.scripts = world, scripts

    def verify(self, *, step_contract, attempt):
        self.world.log.append(("verifier", step_contract.step_id, attempt))
        return play(self.scripts, step_contract.step_id, lambda outcome: VerificationObservation(
            step_contract_sha256=step_contract.sha256, attempt=attempt,
            outcome=outcome or "verified", evidence_sha256=EVIDENCE), step_contract, attempt)


class FakeReviewer:
    def __init__(self, world, scripts) -> None:
        self.world, self.scripts = world, scripts

    def review(self, *, step_contract, attempt):
        self.world.log.append(("reviewer", step_contract.step_id, attempt))
        return play(self.scripts, step_contract.step_id, lambda verdict: ReviewProposal(
            step_contract_sha256=step_contract.sha256, attempt=attempt,
            verdict=verdict or "approve", evidence_sha256=EVIDENCE), step_contract, attempt)


class FakePlanner:
    def __init__(self, world, scripts) -> None:
        self.world, self.scripts = world, scripts

    def propose_step_contract(self, *, project_contract, execution_plan, step_id):
        raise AssertionError("DL-3 never asks the Planner for a contract.")

    def decide_step(self, *, step_contract, step_run):
        self.world.log.append(("planner", step_contract.step_id, step_run.attempt))
        return play(self.scripts, step_contract.step_id, lambda rec: PlannerDecision(
            recommendation=rec or ACCEPT, rationale="Fake planner.",
            step_contract_sha256=step_contract.sha256, attempt=step_run.attempt),
            step_contract, step_run.attempt)

    def declare_project_complete(self, **_):
        raise AssertionError("DL-3 never asks the Planner whether the project is complete.")


class FakeTester:
    def propose_tests(self, *, step_contract, attempt):
        raise AssertionError("DL-3 never dispatches the Tester.")


class World:
    """One recorded project run over a configurable plan, with scripted ports
    sharing one call log."""

    def __init__(self, db_path: Path, *, steps=INDEPENDENT, policies=None, create=None,
                 implement=None, verify=None, review=None, decide=None,
                 store_class=ControlPlaneStore) -> None:
        self.db_path = db_path
        self.store_class = store_class
        self.store = open_store(db_path, store_class)
        self.pc = make_project_contract()
        self.plan = make_plan(self.pc, steps)
        self.store.record_project_contract(self.pc)
        self.store.record_execution_plan(self.plan)
        policies = policies or {}
        self.contracts = {
            step_id: issue(self.pc, self.plan, step_id, **policies.get(step_id, {}))
            for step_id, _ in steps
        }
        for contract in self.contracts.values():
            self.store.record_step_contract(contract)
        self.project = self.store.create_project_run(
            project_contract_sha256=self.pc.sha256, execution_plan_sha256=self.plan.sha256
        )
        self.runs: dict[str, StepRun] = {}
        for step_id, _ in steps:
            if create is None or step_id in create:
                self.runs[step_id] = self.store.create_step_run(
                    project_run_id=self.project.project_run_id,
                    step_contract_sha256=self.contracts[step_id].sha256,
                )
        self.log: list[tuple[str, str, int]] = []
        self.ports = self.make_ports(implement=implement, verify=verify, review=review,
                                     decide=decide)

    def make_ports(self, *, implement=None, verify=None, review=None, decide=None) -> RolePorts:
        self.planner = FakePlanner(self, dict(decide or {}))
        return RolePorts(planner=self.planner, tester=FakeTester(),
                         implementer=FakeImplementer(self, dict(implement or {})),
                         verifier=FakeVerifier(self, dict(verify or {})),
                         reviewer=FakeReviewer(self, dict(review or {})))

    def loop(self) -> ProjectOuterLoop:
        return ProjectOuterLoop(self.store, self.ports)

    def run(self, **overrides):
        arguments = {"project_run": self.project, "project_contract": self.pc,
                     "execution_plan": self.plan, **overrides}
        return self.loop().run(**arguments)

    def state(self, step_id: str) -> StepState:
        return self.store.get_step_run(self.runs[step_id].step_run_id).state

    def project_state(self) -> ProjectState:
        return self.store.get_project_run(self.project.project_run_id).state

    def implemented(self) -> list[str]:
        return [step_id for role, step_id, _ in self.log if role == "implementer"]

    def all_records(self) -> list[TransitionRecord]:
        ids = [self.project.project_run_id] + [r.step_run_id for r in self.runs.values()]
        return sorted((rec for i in ids for rec in self.store.transitions_for(i)),
                      key=lambda rec: rec.seq)

    def escalate_project(self) -> None:
        project = self.store.get_project_run(self.project.project_run_id)
        self.store.apply_project_transition(
            self.project.project_run_id,
            ProjectTransitionRequest(request_id=new_request_id(),
                                     expected_state_version=project.state_version,
                                     event=ProjectEvent.ESCALATE, reason="Synthetic stop."),
        )

    def reopen(self) -> None:
        self.store.close()
        self.store = open_store(self.db_path, self.store_class)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "aido-control-plane.sqlite3"


@pytest.fixture
def make(db_path: Path):
    worlds: list[World] = []

    def build(**options) -> World:
        world = World(db_path, **options)
        worlds.append(world)
        return world

    yield build
    for world in worlds:
        world.store.close()


class Boom(RuntimeError):
    pass


class SimulatedCrash(BaseException):
    """A process death: not an ``Exception``, so nothing catches it."""


def request_complete(world: World) -> None:
    project = world.store.get_project_run(world.project.project_run_id)
    world.store.apply_project_transition(
        world.project.project_run_id,
        ProjectTransitionRequest(request_id=new_request_id(),
                                 expected_state_version=project.state_version,
                                 event=ProjectEvent.REQUEST_COMPLETE, reason="All steps done."),
    )


# --- multi-step completion and scheduling -------------------------------------------


def test_independent_steps_complete_in_plan_order(make) -> None:
    w = make()
    outcome = w.run()
    assert w.implemented() == ["step-a", "step-b", "step-c"]
    assert outcome.stop is OuterLoopStop.PLAN_WORK_COMPLETE
    assert [s.state for s in outcome.step_runs] == [StepState.COMPLETE] * 3
    assert outcome.marked_ready == ("step-a", "step-b", "step-c")
    assert [i.step_id for i in outcome.invocations] == ["step-a", "step-b", "step-c"]
    # Every step done is not the project done.
    assert outcome.project_run.state is ProjectState.ACTIVE
    assert outcome.completion.plan_work_complete is True
    assert outcome.completion.complete_authorized is False


def test_the_schedule_is_deterministic(tmp_path: Path) -> None:
    sequences = []
    for name in ("one", "two"):
        directory = tmp_path / name
        directory.mkdir()
        w = World(directory / "store.sqlite3", steps=DIAMOND,
                  verify={"step-b": ["verification-failed"]}, decide={"step-b": [RETRY]})
        w.run()
        sequences.append(([(r.event, r.rule, r.to_state) for r in w.all_records()], w.log))
        w.store.close()
    assert sequences[0] == sequences[1]


def test_dependencies_are_scheduled_in_order(make) -> None:
    w = make(steps=DIAMOND)
    outcome = w.run()
    assert w.implemented() == ["step-a", "step-b", "step-c", "step-d"]
    assert outcome.stop is OuterLoopStop.PLAN_WORK_COMPLETE
    a, b, c, d = (w.store.transitions_for(w.runs[s].step_run_id) for s in
                  ("step-a", "step-b", "step-c", "step-d"))
    complete = {s: rec[-1].seq for s, rec in zip("abcd", (a, b, c, d))}
    ready = {s: next(r.seq for r in rec if r.event == "mark_ready")
             for s, rec in zip("abcd", (a, b, c, d))}
    assert ready["b"] > complete["a"]
    assert ready["d"] > max(complete["b"], complete["c"])


def test_a_step_never_runs_before_its_prerequisites(make) -> None:
    # step-a has no recorded step run, so step-b can never become READY; the
    # independent step-c still runs.
    w = make(steps=(("step-a", ()), ("step-b", ("step-a",)), ("step-c", ())),
             create={"step-b", "step-c"})
    outcome = w.run()
    assert w.implemented() == ["step-c"]
    assert w.state("step-b") is StepState.PLANNED
    assert outcome.stop is OuterLoopStop.NO_SCHEDULABLE_STEP
    assert outcome.completion.missing_step_ids == ("step-a",)
    assert outcome.completion.incomplete_step_ids == ("step-b",)


def test_a_step_budget_stops_before_the_next_step_is_scheduled(make) -> None:
    w = make(steps=CHAIN)
    outcome = w.run(max_steps=1)
    assert outcome.stop is OuterLoopStop.STEP_BUDGET_REACHED
    assert w.state("step-a") is StepState.COMPLETE
    assert w.state("step-b") is StepState.PLANNED
    assert w.implemented() == ["step-a"]


def test_already_completed_steps_are_not_dispatched_again(make) -> None:
    w = make()
    w.run()
    before = len(w.all_records())
    w.log.clear()
    outcome = w.run()
    assert w.log == []
    assert outcome.stop is OuterLoopStop.PLAN_WORK_COMPLETE
    assert outcome.invocations == () and outcome.marked_ready == ()
    assert len(w.all_records()) == before


# --- retries and blocked steps ----------------------------------------------------


def test_a_failed_verification_retries_within_its_own_budget(make) -> None:
    w = make(verify={"step-b": ["verification-failed"]}, decide={"step-b": [RETRY]})
    outcome = w.run()
    assert w.implemented() == ["step-a", "step-b", "step-b", "step-c"]
    assert outcome.stop is OuterLoopStop.PLAN_WORK_COMPLETE
    b = next(s for s in outcome.step_runs if s.step_id == "step-b")
    assert b.attempt == 2 and b.state is StepState.COMPLETE


def test_a_failed_step_blocks_the_project_and_no_later_step_runs(make) -> None:
    w = make(policies={"step-a": {"max_attempts": 1}},
             verify={"step-a": ["verification-failed"]}, decide={"step-a": [RETRY]})
    outcome = w.run()
    assert w.state("step-a") is StepState.FAILED
    assert w.implemented() == ["step-a"]
    assert w.state("step-b") is StepState.PLANNED
    assert outcome.stop is OuterLoopStop.STEP_BLOCKED
    assert outcome.escalation == "step_blocked"
    assert outcome.project_run.state is ProjectState.HUMAN_REQUIRED
    assert "step_blocked" in outcome.completion.blockers
    assert outcome.completion.plan_work_complete is False


@pytest.mark.parametrize("decide", [
    {"step-b": [PlannerRecommendation.HUMAN_REQUIRED]},
    {"step-b": [Boom("planner down")]},
])
def test_an_escalated_step_blocks_project_completion(make, decide) -> None:
    w = make(decide=decide)
    outcome = w.run()
    assert w.state("step-b") is StepState.HUMAN_REQUIRED
    assert w.state("step-c") is StepState.PLANNED
    assert outcome.stop is OuterLoopStop.STEP_BLOCKED
    assert outcome.project_run.state is ProjectState.HUMAN_REQUIRED
    with pytest.raises(TransitionRefused):
        request_complete(w)


def test_a_required_human_acceptance_is_never_supplied(make) -> None:
    w = make(policies={"step-a": {"human": True}})
    outcome = w.run()
    assert w.state("step-a") is StepState.HUMAN_REQUIRED
    assert outcome.stop is OuterLoopStop.STEP_BLOCKED
    assert w.implemented() == ["step-a"]


@pytest.mark.parametrize("kind", ["human", "recovery"])
def test_human_and_recovery_required_are_never_resolved(make, kind) -> None:
    if kind == "human":
        w = make(decide={"step-a": [PlannerRecommendation.HUMAN_REQUIRED]})
        expected_project = ProjectState.HUMAN_REQUIRED
    else:
        w = make(verify={"step-a": ["workspace-state-untrusted"]})
        expected_project = ProjectState.RECOVERY_REQUIRED
    first = w.run()
    assert first.project_run.state is expected_project
    before = len(w.all_records())
    w.log.clear()
    for _ in range(3):
        again = w.run()
        assert again.stop is OuterLoopStop.PROJECT_NOT_ACTIVE
        assert again.invocations == () and again.marked_ready == ()
    assert w.log == [] and len(w.all_records()) == before
    assert w.project_state() is expected_project


def test_a_recovery_required_project_is_not_further_escalated(make) -> None:
    w = make(verify={"step-a": ["workspace-state-untrusted"]})
    outcome = w.run()
    assert outcome.stop is OuterLoopStop.PROJECT_NOT_ACTIVE
    assert outcome.escalation is None
    assert outcome.project_run.state is ProjectState.RECOVERY_REQUIRED
    assert w.state("step-a") is StepState.RECOVERY_REQUIRED


# --- project escalation during a step ------------------------------------------------


def test_a_project_escalated_during_a_step_stops_all_scheduling(make) -> None:
    w = make()

    def escalate_then_report(contract, attempt):
        w.escalate_project()
        return ImplementationReport(step_contract_sha256=contract.sha256, attempt=attempt,
                                    summary="Fake.")

    w.ports = w.make_ports(implement={"step-b": [escalate_then_report]})
    outcome = w.run()
    assert w.implemented() == ["step-a", "step-b"]
    assert w.state("step-b") is StepState.RECOVERY_REQUIRED
    assert w.state("step-c") is StepState.PLANNED
    assert outcome.stop is OuterLoopStop.PROJECT_NOT_ACTIVE
    assert outcome.project_run.state is ProjectState.HUMAN_REQUIRED


def test_a_project_contract_conflict_stops_the_project(make) -> None:
    w = make(decide={"step-a": [PlannerRecommendation.PROJECT_CONTRACT_CONFLICT]})
    outcome = w.run()
    assert outcome.stop is OuterLoopStop.PROJECT_NOT_ACTIVE
    assert outcome.project_run.state is ProjectState.HUMAN_REQUIRED
    assert w.implemented() == ["step-a"]


def test_a_project_that_is_not_active_is_never_scheduled(make) -> None:
    w = make()
    w.escalate_project()
    outcome = w.run()
    assert outcome.stop is OuterLoopStop.PROJECT_NOT_ACTIVE
    assert w.log == [] and outcome.marked_ready == ()


# --- restart and recovery -----------------------------------------------------------


def test_restart_after_a_partial_project_run_preserves_progress(make) -> None:
    w = make(steps=CHAIN)
    first = w.run(max_steps=1)
    assert first.stop is OuterLoopStop.STEP_BUDGET_REACHED
    w.reopen()
    with pytest.raises(RecoveryRequiredError):
        w.run()
    report = w.store.recover(w.project.project_run_id)
    assert report.integrity_ok and report.recovered_step_run_ids == ()
    outcome = w.run()
    assert w.implemented() == ["step-a", "step-b", "step-c"]
    assert outcome.stop is OuterLoopStop.PLAN_WORK_COMPLETE
    a = next(s for s in outcome.step_runs if s.step_id == "step-a")
    assert a.attempt == 1


@pytest.mark.parametrize("role", ["implement", "verify", "review"])
def test_restart_during_in_flight_step_work_never_repeats_the_dispatch(make, role) -> None:
    w = make(policies={"step-b": {"review_required": True}},
             **{role: {"step-b": [SimulatedCrash()]}})
    with pytest.raises(SimulatedCrash):
        w.run()
    calls = list(w.log)
    w.reopen()
    report = w.store.recover(w.project.project_run_id)
    assert report.recovered_step_run_ids == (w.runs["step-b"].step_run_id,)
    outcome = w.run()
    assert w.log == calls  # nothing dispatched after the crash
    assert outcome.stop is OuterLoopStop.PROJECT_NOT_ACTIVE
    assert w.state("step-b") is StepState.RECOVERY_REQUIRED
    assert w.state("step-a") is StepState.COMPLETE
    assert w.state("step-c") is StepState.PLANNED


def test_a_crash_in_the_same_session_is_reduced_not_resumed(make) -> None:
    w = make(implement={"step-b": [SimulatedCrash()]})
    with pytest.raises(SimulatedCrash):
        w.run()
    assert w.state("step-b") is StepState.EXECUTING
    calls = list(w.log)
    outcome = w.run()
    assert w.log == calls
    assert outcome.invocations[0].step_state_before is StepState.EXECUTING
    assert outcome.invocations[0].role_dispatch_count == 0
    assert w.state("step-b") is StepState.RECOVERY_REQUIRED
    assert outcome.stop is OuterLoopStop.PROJECT_NOT_ACTIVE


def test_an_in_flight_step_behind_an_escalated_project_is_reduced_not_stranded(make) -> None:
    # Self-review finding: the first draft checked the project state first, so
    # an EXECUTING step left behind a project escalation stayed EXECUTING.
    w = make()

    def escalate_then_crash(contract, attempt):
        w.escalate_project()
        raise SimulatedCrash()

    w.ports = w.make_ports(implement={"step-b": [escalate_then_crash]})
    with pytest.raises(SimulatedCrash):
        w.run()
    assert w.state("step-b") is StepState.EXECUTING
    calls = list(w.log)
    outcome = w.run()
    assert w.log == calls
    assert w.state("step-b") is StepState.RECOVERY_REQUIRED
    assert outcome.project_run.state is ProjectState.HUMAN_REQUIRED  # never lowered
    assert outcome.stop is OuterLoopStop.PROJECT_NOT_ACTIVE


def test_an_in_flight_step_is_reduced_before_a_supersession_escalation(make) -> None:
    w = make(implement={"step-a": [SimulatedCrash()]})
    with pytest.raises(SimulatedCrash):
        w.run()
    w.store.record_execution_plan(make_plan(w.pc, INDEPENDENT, version=2,
                                            supersedes=w.plan.sha256))
    outcome = w.run()
    assert w.state("step-a") is StepState.RECOVERY_REQUIRED
    assert outcome.project_run.state is ProjectState.RECOVERY_REQUIRED
    assert outcome.completion.plan_is_latest_recorded is False
    assert w.implemented() == ["step-a"]


def test_a_reopened_store_is_not_consumed_before_recovery(make) -> None:
    w = make()
    w.reopen()
    with pytest.raises(RecoveryRequiredError):
        w.run()
    with pytest.raises(RecoveryRequiredError):
        assess_project_completion(w.store, w.project.project_run_id)
    assert w.log == []


# --- replay ---------------------------------------------------------------------------


class ReplayingStore(ControlPlaneStore):
    """Applies every DL-3 ``mark_ready`` twice, so the loop sees a receipt."""

    def apply_step_transition(self, step_run_id, request):
        applied = super().apply_step_transition(step_run_id, request)
        if request.event is StepEvent.MARK_READY:
            return super().apply_step_transition(step_run_id, request)
        return applied


def test_a_replayed_scheduling_receipt_never_runs_the_step(db_path) -> None:
    w = World(db_path, store_class=ReplayingStore)
    try:
        outcome = w.run()
        assert outcome.stop is OuterLoopStop.REPLAYED_RECEIPT
        assert w.log == [] and outcome.invocations == ()
        assert w.state("step-a") is StepState.READY
    finally:
        w.store.close()


def test_re_sending_a_recorded_dl3_request_is_a_receipt(make) -> None:
    w = make()
    w.run()
    a = w.runs["step-a"]
    request = StepTransitionRequest(request_id=outer_request_id(a.step_run_id, 0, "mark_ready"),
                                    expected_state_version=0, event=StepEvent.MARK_READY)
    applied = w.store.apply_step_transition(a.step_run_id, request)
    assert applied.duplicate and applied.current_state == "COMPLETE"


class ReplayingProjectStore(ControlPlaneStore):
    def apply_project_transition(self, project_run_id, request):
        super().apply_project_transition(project_run_id, request)
        return super().apply_project_transition(project_run_id, request)


def test_a_replayed_escalation_is_a_receipt_and_schedules_nothing(db_path) -> None:
    w = World(db_path, store_class=ReplayingProjectStore,
              decide={"step-a": [PlannerRecommendation.HUMAN_REQUIRED]})
    try:
        outcome = w.run()
        assert outcome.stop is OuterLoopStop.PROJECT_NOT_ACTIVE
        assert outcome.escalation is None
        assert w.implemented() == ["step-a"]
        escalations = [r for r in w.store.transitions_for(w.project.project_run_id)
                       if r.event == "escalate"]
        assert len(escalations) == 1
    finally:
        w.store.close()


def test_a_dl3_escalation_request_id_cannot_be_reused_for_other_content(make) -> None:
    w = make(decide={"step-a": [PlannerRecommendation.HUMAN_REQUIRED]})
    w.run()
    rid = outer_request_id(w.project.project_run_id, 0, "escalate:step_blocked")
    with pytest.raises(TransitionRefused) as caught:
        w.store.apply_project_transition(
            w.project.project_run_id,
            ProjectTransitionRequest(request_id=rid, expected_state_version=1,
                                     event=ProjectEvent.ESCALATE, reason="Different."))
    assert caught.value.code is RefusalCode.DUPLICATE_REQUEST_CONFLICT


# --- caller objects -------------------------------------------------------------------


def second_world_objects(w: World):
    other_pc = make_project_contract("other-project")
    other_plan = make_plan(other_pc, INDEPENDENT)
    w.store.record_project_contract(other_pc)
    w.store.record_execution_plan(other_plan)
    other_run = w.store.create_project_run(project_contract_sha256=other_pc.sha256,
                                           execution_plan_sha256=other_plan.sha256)
    return other_pc, other_plan, other_run


@pytest.mark.parametrize("swap", [
    "other_contract", "other_plan", "other_run_with_these_contracts", "forged_identity",
    "plan_v2", "unknown_run",
])
def test_cross_project_and_cross_plan_substitution_is_refused(make, swap) -> None:
    w = make()
    other_pc, other_plan, other_run = second_world_objects(w)
    overrides = {
        "other_contract": {"project_contract": other_pc},
        "other_plan": {"execution_plan": other_plan},
        "other_run_with_these_contracts": {"project_run": other_run},
        "forged_identity": {"project_run": w.project.model_copy(
            update={"execution_plan_sha256": other_plan.sha256})},
        "plan_v2": {"execution_plan": make_plan(w.pc, INDEPENDENT, version=2,
                                                supersedes=w.plan.sha256)},
        "unknown_run": {"project_run": w.project.model_copy(
            update={"project_run_id": "f" * 32})},
    }[swap]
    before = len(w.all_records())
    with pytest.raises((OuterLoopInputError, cp.RecordNotFoundError)):
        w.run(**overrides)
    assert w.log == [] and len(w.all_records()) == before


def test_a_step_contract_of_another_plan_cannot_join_a_run(make) -> None:
    w = make()
    plan_v2 = make_plan(w.pc, INDEPENDENT + (("step-d", ()),), version=2,
                        supersedes=w.plan.sha256)
    w.store.record_execution_plan(plan_v2)
    run_v2 = w.store.create_project_run(project_contract_sha256=w.pc.sha256,
                                        execution_plan_sha256=plan_v2.sha256)
    with pytest.raises(ContractRefusedError):
        w.store.create_step_run(project_run_id=run_v2.project_run_id,
                                step_contract_sha256=w.contracts["step-a"].sha256)


class LooseRun(ProjectRun):
    pass


@pytest.mark.parametrize("bad", ["subclass", "unvalidated", "dict", "none"])
def test_malformed_run_objects_cannot_bypass_validation(make, bad) -> None:
    w = make()
    value = {
        "subclass": LooseRun.model_validate(w.project.model_dump()),
        "unvalidated": ProjectRun.model_construct(**{**w.project.model_dump(),
                                                     "state_version": -1}),
        "dict": w.project.model_dump(),
        "none": None,
    }[bad]
    with pytest.raises(OuterLoopInputError):
        w.run(project_run=value)
    assert w.log == []


@pytest.mark.parametrize("bad", ["unvalidated_plan", "unvalidated_contract"])
def test_malformed_contract_objects_cannot_bypass_validation(make, bad) -> None:
    w = make()
    if bad == "unvalidated_plan":
        overrides = {"execution_plan": ExecutionPlan.model_construct(
            **{**dict(w.plan), "steps": ()})}
    else:
        overrides = {"project_contract": ProjectContract.model_construct(
            content=w.pc.content, approval=w.pc.approval.model_construct(
                **{**dict(w.pc.approval), "approval_text": "ok"}))}
    with pytest.raises(OuterLoopInputError):
        w.run(**overrides)


@pytest.mark.parametrize("value", [0, -1, True, "1", 1.0])
def test_a_malformed_step_budget_is_refused(make, value) -> None:
    w = make()
    with pytest.raises(OuterLoopInputError):
        w.run(max_steps=value)
    assert w.log == []


def test_a_supplied_snapshot_state_is_never_consulted(make) -> None:
    w = make()
    forged = w.project.model_copy(update={"state": ProjectState.COMPLETE, "state_version": 9})
    outcome = w.run(project_run=ProjectRun.model_validate(forged.model_dump()))
    assert outcome.stop is OuterLoopStop.PLAN_WORK_COMPLETE
    assert outcome.project_run.state is ProjectState.ACTIVE


def test_bad_constructor_arguments_are_refused(make) -> None:
    w = make()
    with pytest.raises(OuterLoopInputError):
        ProjectOuterLoop(object(), w.ports)
    with pytest.raises(OuterLoopInputError):
        ProjectOuterLoop(w.store, object())
    with pytest.raises(cp.InnerLoopInputError):
        ProjectOuterLoop(w.store, RolePorts(planner=object(), tester=FakeTester(),
                                            implementer=object(), verifier=object(),
                                            reviewer=object()))


# --- plan versions and re-planning ------------------------------------------------


def test_a_planner_replan_recommendation_installs_nothing(make) -> None:
    w = make(decide={"step-b": [REPLAN]})
    outcome = w.run()
    assert w.state("step-b") is StepState.HUMAN_REQUIRED
    assert outcome.stop is OuterLoopStop.STEP_BLOCKED
    assert outcome.replan_recommended_step_ids == ("step-b",)
    assert w.store.list_execution_plans(w.pc.sha256) == (w.plan,)
    assert outcome.project_run.execution_plan_sha256 == w.plan.sha256
    assert w.state("step-c") is StepState.PLANNED


def test_a_recorded_successor_plan_halts_the_superseded_run(make) -> None:
    w = make()
    plan_v2 = make_plan(w.pc, (("step-x", ()),), version=2, supersedes=w.plan.sha256)
    w.store.record_execution_plan(plan_v2)
    outcome = w.run()
    assert outcome.stop is OuterLoopStop.PLAN_SUPERSEDED
    assert outcome.escalation == "plan_superseded"
    assert outcome.project_run.state is ProjectState.HUMAN_REQUIRED
    assert outcome.project_run.execution_plan_sha256 == w.plan.sha256  # never substituted
    assert w.log == [] and outcome.marked_ready == ()
    assert outcome.completion.plan_is_latest_recorded is False
    assert "plan_superseded" in outcome.completion.blockers


def test_a_successor_plan_recorded_mid_run_stops_further_scheduling(make) -> None:
    w = make()

    def record_successor(contract, attempt):
        w.store.record_execution_plan(make_plan(w.pc, INDEPENDENT, version=2,
                                                supersedes=w.plan.sha256))
        return ImplementationReport(step_contract_sha256=contract.sha256, attempt=attempt,
                                    summary="Fake.")

    w.ports = w.make_ports(implement={"step-a": [record_successor]})
    outcome = w.run()
    assert w.implemented() == ["step-a"]
    assert w.state("step-a") is StepState.COMPLETE
    assert w.state("step-b") is StepState.PLANNED
    assert outcome.stop is OuterLoopStop.PLAN_SUPERSEDED


def test_a_run_on_the_current_plan_proceeds_with_its_own_steps_only(make) -> None:
    w = make()
    w.run(max_steps=1)
    plan_v2 = make_plan(w.pc, (("step-x", ()),), version=2, supersedes=w.plan.sha256)
    w.store.record_execution_plan(plan_v2)
    contract_x = issue(w.pc, plan_v2, "step-x")
    w.store.record_step_contract(contract_x)
    run_v2 = w.store.create_project_run(project_contract_sha256=w.pc.sha256,
                                        execution_plan_sha256=plan_v2.sha256)
    w.store.create_step_run(project_run_id=run_v2.project_run_id,
                            step_contract_sha256=contract_x.sha256)
    w.log.clear()
    outcome = w.loop().run(project_run=run_v2, project_contract=w.pc, execution_plan=plan_v2)
    assert w.implemented() == ["step-x"]
    assert outcome.stop is OuterLoopStop.PLAN_WORK_COMPLETE
    assert [s.step_id for s in outcome.step_runs] == ["step-x"]
    # The v1 run kept its progress and was never touched.
    assert w.state("step-a") is StepState.COMPLETE
    assert w.state("step-b") is StepState.PLANNED
    assert w.project_state() is ProjectState.ACTIVE


def test_the_recorded_plan_chain_is_re_proven(make) -> None:
    w = make()
    plan_v2 = make_plan(w.pc, INDEPENDENT, version=2, supersedes=w.plan.sha256)
    w.store.record_execution_plan(plan_v2)
    assert w.store.list_execution_plans(w.pc.sha256) == (w.plan, plan_v2)
    w.store._conn.execute("UPDATE contracts SET version = 7 WHERE sha256 = ?",
                          (plan_v2.sha256,))
    with pytest.raises(StateUntrustedError):
        w.store.list_execution_plans(w.pc.sha256)
    with pytest.raises(StateUntrustedError):
        w.run()
    assert w.log == []


def test_an_unrelated_project_contract_has_no_recorded_plans(make) -> None:
    w = make()
    assert w.store.list_execution_plans("0" * 64) == ()


# --- the completion gate ---------------------------------------------------------------


def test_the_completion_levels_are_distinct(make) -> None:
    # Every *recorded* step run complete, but the plan has an unrecorded step.
    w = make(create={"step-a", "step-c"})
    outcome = w.run()
    c = outcome.completion
    assert c.all_recorded_step_runs_complete is True
    assert c.plan_work_complete is False
    assert c.missing_step_ids == ("step-b",)
    assert c.acceptance_criteria_satisfied is False
    assert c.protected_invariants_satisfied is False
    assert c.complete_authorized is False
    assert outcome.stop is OuterLoopStop.NO_SCHEDULABLE_STEP


def test_plan_work_complete_is_not_project_complete(make) -> None:
    w = make()
    outcome = w.run()
    c = outcome.completion
    assert c.all_recorded_step_runs_complete and c.plan_work_complete
    assert c.complete_authorized is False and c.acceptance_criteria_satisfied is False
    assert c.blockers == ("acceptance_criteria_unproven", "protected_invariants_unproven",
                          "integration_gate_unavailable")
    with pytest.raises(TransitionRefused) as caught:
        request_complete(w)
    assert caught.value.code is RefusalCode.UNSUPPORTED_IN_DL1
    assert w.project_state() is ProjectState.ACTIVE


def test_a_planner_project_complete_claim_is_insufficient(make) -> None:
    # The Planner accepts every step; it has a project-complete method that the
    # loop must never call (it raises), and nothing it says completes the project.
    w = make()
    outcome = w.run()
    assert outcome.project_run.state is ProjectState.ACTIVE
    assert outcome.completion.complete_authorized is False
    with pytest.raises(AssertionError):
        w.planner.declare_project_complete()


@pytest.mark.parametrize("field", ["complete_authorized", "acceptance_criteria_satisfied",
                                   "protected_invariants_satisfied"])
def test_no_assessment_can_claim_unprovable_levels(make, field) -> None:
    w = make()
    assessment = assess_project_completion(w.store, w.project.project_run_id)
    with pytest.raises(ValidationError):
        ProjectCompletionAssessment.model_validate({**assessment.model_dump(), field: True})


def test_the_assessment_reads_only_the_store(make) -> None:
    w = make(create={"step-a"})
    w.run()
    assessment = assess_project_completion(w.store, w.project.project_run_id)
    assert assessment.plan_work_complete is False
    assert assessment.recorded_step_run_count == 1
    with pytest.raises(OuterLoopInputError):
        assess_project_completion(object(), w.project.project_run_id)


def test_a_forged_complete_row_is_untrusted_not_complete(make) -> None:
    w = make(create={"step-a", "step-b"})
    w.run()
    w.store._conn.execute(
        "UPDATE step_runs SET state = 'COMPLETE' WHERE step_run_id = ?",
        (w.runs["step-a"].step_run_id,),
    )
    w.store._conn.execute(
        "UPDATE step_runs SET state = 'FAILED' WHERE step_run_id = ?",
        (w.runs["step-b"].step_run_id,),
    )
    with pytest.raises(StateUntrustedError):
        w.run()
    with pytest.raises(StateUntrustedError):
        assess_project_completion(w.store, w.project.project_run_id)
    report = w.store.recover(w.project.project_run_id)
    assert not report.integrity_ok and report.project_state is ProjectState.HUMAN_REQUIRED


# --- bounds ---------------------------------------------------------------------------


class RefusingStore(ControlPlaneStore):
    """Refuses every request for one event."""

    refused_event = StepEvent.MARK_READY

    def apply_step_transition(self, step_run_id, request):
        if request.event is self.refused_event:
            raise TransitionRefused(RefusalCode.OUT_OF_ORDER, "synthetic refusal")
        return super().apply_step_transition(step_run_id, request)


class RefusingBeginStore(RefusingStore):
    refused_event = StepEvent.BEGIN_ATTEMPT


class LyingStore(ControlPlaneStore):
    """Claims every mark_ready succeeded without applying it."""

    def apply_step_transition(self, step_run_id, request):
        if request.event is StepEvent.MARK_READY:
            record = TransitionRecord(
                seq=0, request_id=request.request_id, request_sha256=request.request_sha256,
                subject_kind="step", subject_id=step_run_id, event="mark_ready",
                rule="dependencies_complete", from_state="PLANNED", to_state="READY",
                from_version=0, to_version=1, attempt=0, verification_outcome=None,
                review_verdict=None, recorded_at=APPROVED_AT.isoformat())
            return AppliedTransition(record=record, duplicate=False, current_state="READY",
                                     current_state_version=1)
        return super().apply_step_transition(step_run_id, request)


@pytest.mark.parametrize("store_class, stop, implemented", [
    (RefusingStore, OuterLoopStop.TRANSITION_REFUSED, []),
    (RefusingBeginStore, OuterLoopStop.STEP_NOT_SETTLED, []),
    (LyingStore, OuterLoopStop.STEP_NOT_SETTLED, []),
])
def test_the_loop_terminates_under_refusal_and_inconsistent_stores(
    db_path, store_class, stop, implemented
) -> None:
    w = World(db_path, store_class=store_class)
    try:
        outcome = w.run()
        assert outcome.stop is stop
        assert w.implemented() == implemented
        assert len(outcome.invocations) <= 1
        assert len(outcome.marked_ready) <= 1
    finally:
        w.store.close()


class RefusingRecoverStore(RefusingStore):
    refused_event = StepEvent.RECOVER_INTERRUPTED


def test_an_in_flight_step_whose_reduction_is_refused_still_terminates(db_path) -> None:
    w = World(db_path, store_class=RefusingRecoverStore,
              implement={"step-a": [SimulatedCrash()]})
    try:
        with pytest.raises(SimulatedCrash):
            w.run()
        outcome = w.run()
        assert outcome.stop is OuterLoopStop.STEP_NOT_SETTLED
        assert len(outcome.invocations) == 1
        assert outcome.invocations[0].role_dispatch_count == 0
        assert w.implemented() == ["step-a"]
        assert w.state("step-a") is StepState.EXECUTING
    finally:
        w.store.close()


def test_a_step_dl2_leaves_unsettled_is_not_invoked_twice(db_path) -> None:
    w = World(db_path, store_class=RefusingBeginStore)
    try:
        outcome = w.run()
        assert [i.inner_stop for i in outcome.invocations] == [InnerLoopStop.TRANSITION_REFUSED]
        assert w.state("step-a") is StepState.READY
        assert w.state("step-b") is StepState.PLANNED
    finally:
        w.store.close()


def test_a_long_plan_completes_within_its_bound(make) -> None:
    steps = tuple((f"step-{i:02d}", (f"step-{i - 1:02d}",) if i % 3 else ())
                  for i in range(12))
    w = make(steps=steps)
    outcome = w.run()
    assert outcome.stop is OuterLoopStop.PLAN_WORK_COMPLETE
    assert w.implemented() == [step_id for step_id, _ in steps]
    assert len(outcome.invocations) == 12


def test_the_step_budget_can_only_lower_the_bound(make) -> None:
    w = make()
    outcome = w.run(max_steps=10_000)
    assert len(outcome.invocations) == 3
    w2_outcome = w.run(max_steps=1)
    assert w2_outcome.invocations == ()


# --- adversarial: re-entry, mutation, authority confusion -----------------------------


def test_re_entering_dl3_for_the_same_project_is_refused_before_any_write(make) -> None:
    w = make()
    nested: list[BaseException] = []

    def re_enter(contract, attempt):
        before = len(w.all_records())
        try:
            w.run()
        except OuterLoopReentryError as exc:
            nested.append(exc)
        assert len(w.all_records()) == before
        return ImplementationReport(step_contract_sha256=contract.sha256, attempt=attempt,
                                    summary="Fake.")

    w.ports = w.make_ports(implement={"step-a": [re_enter]})
    outcome = w.run()
    assert len(nested) == 1
    assert w.implemented() == ["step-a", "step-b", "step-c"]
    assert outcome.stop is OuterLoopStop.PLAN_WORK_COMPLETE


def test_a_direct_inner_loop_reentry_from_a_port_cannot_double_dispatch(make) -> None:
    w = make()

    def nested_inner_loop(contract, attempt):
        step = w.store.get_step_run(w.runs["step-a"].step_run_id)
        cp.StepInnerLoop(w.store, w.ports).run(
            project_run=w.store.get_project_run(w.project.project_run_id), step_run=step,
            project_contract=w.pc, execution_plan=w.plan, step_contract=w.contracts["step-a"])
        return ImplementationReport(step_contract_sha256=contract.sha256, attempt=attempt,
                                    summary="Fake.")

    w.ports = w.make_ports(implement={"step-a": [nested_inner_loop]})
    outcome = w.run()
    assert w.implemented() == ["step-a"]
    assert w.state("step-a") is StepState.RECOVERY_REQUIRED
    assert outcome.stop is OuterLoopStop.PROJECT_NOT_ACTIVE


def test_mutating_the_callers_objects_mid_run_changes_nothing(make) -> None:
    w = make(steps=CHAIN)

    def mutate(contract, attempt):
        object.__setattr__(w.plan, "steps", w.plan.steps[:1])
        object.__setattr__(w.project, "execution_plan_version", 99)
        return ImplementationReport(step_contract_sha256=contract.sha256, attempt=attempt,
                                    summary="Fake.")

    w.ports = w.make_ports(implement={"step-a": [mutate]})
    outcome = w.run()
    assert w.implemented() == ["step-a", "step-b", "step-c"]
    assert outcome.stop is OuterLoopStop.PLAN_WORK_COMPLETE


def test_one_project_runs_steps_are_never_driven_by_another(make) -> None:
    w = make()
    run_2 = w.store.create_project_run(project_contract_sha256=w.pc.sha256,
                                       execution_plan_sha256=w.plan.sha256)
    w.store.create_step_run(project_run_id=run_2.project_run_id,
                            step_contract_sha256=w.contracts["step-a"].sha256)
    outcome = w.loop().run(project_run=run_2, project_contract=w.pc, execution_plan=w.plan)
    assert [s.step_run_id for s in outcome.step_runs] != [w.runs["step-a"].step_run_id]
    assert len(outcome.step_runs) == 1
    assert outcome.stop is OuterLoopStop.NO_SCHEDULABLE_STEP
    assert w.state("step-a") is StepState.PLANNED  # run 1 untouched


def test_known_limitation_role_outputs_do_not_name_the_project_run(make) -> None:
    # Pinned, not fixed: a role output binds (step_contract_sha256, attempt), so
    # an output produced for run 1's step-a also validates for run 2's step-a.
    w = make(create={"step-a"})
    first = w.run()
    run_2 = w.store.create_project_run(project_contract_sha256=w.pc.sha256,
                                       execution_plan_sha256=w.plan.sha256)
    step_2 = w.store.create_step_run(project_run_id=run_2.project_run_id,
                                     step_contract_sha256=w.contracts["step-a"].sha256)
    assert first.step_runs[0].step_contract_sha256 == step_2.step_contract_sha256


def test_the_outcome_is_the_stores_read(make) -> None:
    w = make()
    outcome = w.run()
    assert outcome.project_run == w.store.get_project_run(w.project.project_run_id)
    assert outcome.step_runs == w.store.list_step_runs(w.project.project_run_id)
    assert outcome.completion == assess_project_completion(w.store, w.project.project_run_id)


def test_a_role_claiming_project_completion_changes_nothing(make) -> None:
    claim = "Project complete: every acceptance criterion is satisfied."
    w = make(implement={s: [lambda c, a: ImplementationReport(
        step_contract_sha256=c.sha256, attempt=a, summary=claim, claims=(claim,))]
        for s in ("step-a", "step-b", "step-c")})
    outcome = w.run()
    assert outcome.completion.complete_authorized is False
    assert outcome.project_run.state is ProjectState.ACTIVE


# --- static boundaries: no live execution ----------------------------------------------


def test_the_outer_loop_runs_with_every_execution_path_disabled(make, monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("DL-3 must not reach a process, socket or shell.")

    import os
    for target, name in ((socket, "socket"), (socket, "create_connection"),
                         (subprocess, "Popen"), (subprocess, "run"), (os, "system"),
                         (os, "getenv")):
        monkeypatch.setattr(target, name, forbidden)
    w = make(steps=DIAMOND, verify={"step-b": ["verification-failed"]},
             decide={"step-b": [RETRY]})
    assert w.run().stop is OuterLoopStop.PLAN_WORK_COMPLETE


_OUTER_LOOP = Path(cp.__file__).resolve().parent / "outer_loop.py"
_ALLOWED = {"__future__", "enum", "hashlib", "typing", "pydantic"}


def test_the_outer_loop_imports_nothing_that_executes() -> None:
    tree = ast.parse(_OUTER_LOOP.read_text(encoding="utf-8"))
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


def test_the_outer_loop_has_no_workspace_path_or_role_surface() -> None:
    tree = ast.parse(_OUTER_LOOP.read_text(encoding="utf-8"))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    forbidden = {"open", "Path", "environ", "getenv", "system", "Popen", "socket",
                 "subprocess", "httpx", "sqlite3", "_conn", "connect",
                 # DL-3 never calls a role port: DL-2 does.
                 "implement", "verify", "review", "decide_step", "propose_step_contract",
                 "propose_tests", "planner", "implementer", "verifier", "reviewer", "tester",
                 # nor records or activates a plan, nor creates runs.
                 "record_execution_plan", "record_step_contract", "create_project_run",
                 "create_step_run", "recover", "HumanStepAcceptance"}
    assert not names & forbidden, names & forbidden


def test_the_outer_loop_never_requests_project_completion() -> None:
    source = _OUTER_LOOP.read_text(encoding="utf-8")
    assert "REQUEST_COMPLETE" not in source


def test_no_cli_command_reaches_the_outer_loop() -> None:
    cli_source = (Path(cp.__file__).resolve().parent.parent / "cli.py").read_text(
        encoding="utf-8")
    assert "outer_loop" not in cli_source and "ProjectOuterLoop" not in cli_source
