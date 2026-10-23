"""DL-4A — real integration authority foundation (offline).

Every test is offline and synthetic. Each state root and target workspace is a
directory under pytest ``tmp_path``; the store is the authority store inside
that state root; contracts, plans, policies, role outputs and
``verification-result.v1`` evidence are synthetic; the role ports are in-test
fakes. No model, socket, subprocess, Pi or Node, environment variable or real
target workspace is used, and no test writes inside a target workspace.

The "human" is a test-only HMAC verifier holding a key the AIDO code under
test never sees. It stands in for the external attestation source DL-4A
cannot provide (see docs/DL4A_REAL_INTEGRATION_AUTHORITY.md §4.1); it is not
shipped.

Sections, in order: store and session boundaries; the complete
issuance-to-consumption chain; forged and stale approvals; forged
verification; role-output identity binding and cross-run reuse; policy
issuance; replay and restart; malformed inputs and post-validation mutation;
filesystem containment, partial persistence and cleanup; static boundaries;
second-review regressions.
"""

from __future__ import annotations

import ast
import hashlib
import hmac
import os
import shutil
import sqlite3
import typing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError
from review_fixtures import verification_report

import ai_dev_orchestrator.control_plane as cp
from ai_dev_orchestrator.control_plane import (
    AidoStateRoot,
    ApprovalChallenge,
    ApprovalSubjectKind,
    AuthorityRefusedError,
    BoundRoleOutput,
    ContainmentError,
    ControlPlaneStore,
    DispatchTicket,
    EvidenceRefusedError,
    ExecutionPlan,
    ExecutionPolicy,
    HumanAttestation,
    HumanStepAcceptance,
    ImplementationReport,
    PlannedStep,
    PlannerDecision,
    PlannerRecommendation,
    ProjectContract,
    ProjectContractApproval,
    ProjectContractContent,
    ProjectEvent,
    ProjectOuterLoop,
    ProjectState,
    ProjectTransitionRequest,
    RecordNotFoundError,
    RefusalCode,
    ReviewProposal,
    RolePorts,
    StateUntrustedError,
    StepContractProposal,
    StepEvent,
    StepInnerLoop,
    StepState,
    StepTransitionRequest,
    StoreError,
    TransitionRefused,
    VerificationEvidenceRecorder,
    VerificationObservation,
    assess_project_completion,
    bind_role_output,
    issue_step_contract,
    new_request_id,
    open_authority_session,
    verification_outcome_from_evidence,
)
from ai_dev_orchestrator.control_plane import containment
from ai_dev_orchestrator.control_plane.authority import (
    APPROVAL_CHALLENGE_TTL,
    VERIFICATION_RESULT_FIELDS,
    VERIFICATION_RESULT_MODE,
    VERIFICATION_RESULT_SCHEMA_VERSION,
    VERIFICATION_TRUST_FIELDS,
)
from ai_dev_orchestrator.control_plane.models import (
    REQUIRED_PROJECT_CONTRACT_APPROVAL_TEXT,
    REQUIRED_STEP_ACCEPTANCE_APPROVAL_TEXT,
    VerificationOutcome,
    canonical_json_bytes,
)
from ai_dev_orchestrator.control_plane.store import _AuthorityContext

APPROVED_AT = datetime(2026, 10, 22, 9, 0, tzinfo=timezone.utc)
INVARIANT = "No network access from the control plane."
APPROVER = "synthetic-operator"
HUMAN_KEY = b"dl4a-synthetic-human-key"
ACCEPT = PlannerRecommendation.RECOMMEND_STEP_ACCEPT
RETRY = PlannerRecommendation.RECOMMEND_RETRY_IMPLEMENTATION
REVIEW_EVIDENCE = "a" * 64


# --- the synthetic human ---------------------------------------------------------


class FakeClock:
    def __init__(self) -> None:
        self.now = APPROVED_AT
        self.fail = False

    def __call__(self) -> datetime:
        if self.fail:
            raise RuntimeError("simulated failure inside the store's transaction")
        self.now += timedelta(seconds=1)
        return self.now


def sign(key: bytes, fields: dict) -> str:
    material = canonical_json_bytes({
        "challenge_id": fields["challenge_id"],
        "subject_kind": ApprovalSubjectKind(fields["subject_kind"]).value,
        "subject_sha256": fields["subject_sha256"],
        "approver_id": fields["approver_id"],
        "attested_at": fields["attested_at"].isoformat(),
    })
    return hmac.new(key, material, hashlib.sha256).hexdigest()


class HmacHumanVerifier:
    """Test-only external trust source: confirms only proofs made with a key the
    code under test never holds, for an allowed approver."""

    def __init__(self, key: bytes = HUMAN_KEY, approvers: tuple[str, ...] = (APPROVER,)) -> None:
        self.key = key
        self.approvers = approvers
        self.calls = 0

    def verify(self, *, challenge: ApprovalChallenge, attestation: HumanAttestation) -> bool:
        self.calls += 1
        if attestation.approver_id not in self.approvers:
            return False
        if attestation.challenge_id != challenge.challenge_id:
            return False
        expected = sign(self.key, attestation.model_dump())
        return hmac.compare_digest(expected, attestation.proof)


def attest(
    challenge: ApprovalChallenge,
    *,
    approver: str = APPROVER,
    at: datetime | None = None,
    key: bytes = HUMAN_KEY,
    **overrides,
) -> HumanAttestation:
    fields = {
        "schema_version": "human-attestation.v1",
        "challenge_id": challenge.challenge_id,
        "subject_kind": challenge.subject_kind,
        "subject_sha256": challenge.subject_sha256,
        "approver_id": approver,
        "attested_at": at or challenge.issued_at,
        "approval_text": challenge.required_approval_text,
    }
    fields.update({k: v for k, v in overrides.items() if k != "proof"})
    fields["proof"] = overrides.get("proof") or sign(key, fields)
    return HumanAttestation(**fields)


# --- builders ------------------------------------------------------------------


def make_content(**overrides) -> ProjectContractContent:
    return ProjectContractContent(**{
        "schema_version": "project-contract.v1",
        "project_id": "synthetic-project",
        "goal": "Add a synthetic greeting helper.",
        "requirements": ("The helper returns a greeting.",),
        "protected_invariants": (INVARIANT,),
        "acceptance_criteria": ("A greeting test passes.",),
        **overrides,
    })


def approved_contract(content: ProjectContractContent, challenge: ApprovalChallenge,
                      *, approver: str = APPROVER, at: datetime | None = None) -> ProjectContract:
    return ProjectContract(content=content, approval=ProjectContractApproval(
        approved_by=approver,
        approved_at=at or challenge.issued_at,
        approval_text=REQUIRED_PROJECT_CONTRACT_APPROVAL_TEXT,
        source="manual",
        contract_sha256=content.sha256,
    ))


TWO_STEPS = (
    PlannedStep(step_id="step-a", objective="Write the helper."),
    PlannedStep(step_id="step-b", objective="Document it.", depends_on=("step-a",)),
)


def make_plan(pc: ProjectContract, *, version: int = 1, supersedes: str | None = None,
              steps: tuple[PlannedStep, ...] = TWO_STEPS) -> ExecutionPlan:
    return ExecutionPlan(
        schema_version="execution-plan.v1",
        project_id=pc.project_id,
        project_contract_sha256=pc.sha256,
        plan_version=version,
        supersedes_sha256=supersedes,
        steps=steps,
    )


def make_policy(review: bool = True, human: bool = False, max_attempts: int = 2) -> ExecutionPolicy:
    return ExecutionPolicy(schema_version="execution-policy.v1", review_required=review,
                           human_acceptance_required=human, max_attempts=max_attempts)


def make_proposal(step_id: str) -> StepContractProposal:
    return StepContractProposal(step_id=step_id, requirements=("Return 'hello'.",),
                                protected_invariants=(INVARIANT,))


def evidence_bytes(outcome: str = "verified", tag: str = "") -> bytes:
    """Real verification-result.v1 bytes, built through the shipped model."""
    report = verification_report(outcome=outcome, passed=outcome != "verification-failed",
                                 output_text=f"synthetic run {tag}\n")
    return report.model_dump_json().encode("utf-8")


def tamper(db_path: str, sql: str, params: tuple = ()) -> None:
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA ignore_check_constraints = ON")
    connection.execute(sql, params)
    connection.commit()
    connection.close()


def count(store: ControlPlaneStore, table: str, where: str = "1 = 1", params: tuple = ()) -> int:
    return store._conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", params).fetchone()[0]


def tree(path: Path) -> list[tuple[str, bytes | None]]:
    return sorted(
        (str(p.relative_to(path)), p.read_bytes() if p.is_file() else None)
        for p in path.rglob("*")
    )


class World:
    """One state root, one target workspace, an approved contract, an activated
    two-step plan (b depends on a) under one policy, and one project run."""

    def __init__(self, tmp_path: Path, *, review: bool = True, human: bool = False,
                 max_attempts: int = 2, verifier=None, name: str = "w") -> None:
        self.state_dir = tmp_path / f"{name}-state"
        self.workspace = tmp_path / f"{name}-workspace"
        self.state_dir.mkdir()
        self.workspace.mkdir()
        (self.workspace / "README.md").write_bytes(b"synthetic target\n")
        self.root = AidoStateRoot.create(self.state_dir)
        self.verifier = verifier or HmacHumanVerifier()
        self.clock = FakeClock()
        self.session = open_authority_session(self.root, approval_verifier=self.verifier,
                                              clock=self.clock)
        self.content = make_content()
        challenge = self.store.request_project_contract_approval(self.content)
        self.pc = approved_contract(self.content, challenge)
        self.store.record_approved_project_contract(self.pc, attest(challenge))
        self.plan = make_plan(self.pc)
        self.policy = make_policy(review, human, max_attempts)
        self.activate(self.plan, self.policy)
        self.contract_a = self.store.issue_authorized_step_contract(
            make_proposal("step-a"), execution_plan_sha256=self.plan.sha256)
        self.contract_b = self.store.issue_authorized_step_contract(
            make_proposal("step-b"), execution_plan_sha256=self.plan.sha256)
        self.project = self.new_run()

    @property
    def store(self) -> ControlPlaneStore:
        return self.session.store

    @property
    def recorder(self) -> VerificationEvidenceRecorder:
        return self.session.verification_recorder

    def activate(self, plan: ExecutionPlan, policy: ExecutionPolicy) -> str:
        challenge = self.store.request_plan_activation(
            execution_plan=plan, execution_policy=policy, target_workspace=self.workspace)
        return self.store.issue_execution_plan(plan, execution_policy=policy,
                                               target_workspace=self.workspace,
                                               attestation=attest(challenge))

    def new_run(self):
        project = self.store.create_project_run(
            project_contract_sha256=self.pc.sha256, execution_plan_sha256=self.plan.sha256)
        for contract in (self.contract_a, self.contract_b):
            self.store.create_step_run(project_run_id=project.project_run_id,
                                       step_contract_sha256=contract.sha256)
        return project

    def step(self, step_id: str, project=None):
        project = project or self.project
        return next(s for s in self.store.list_step_runs(project.project_run_id)
                    if s.step_id == step_id)

    def reopen(self, verifier=None) -> ControlPlaneStore:
        self.session.close()
        self.session = open_authority_session(self.root, approval_verifier=verifier or self.verifier,
                                              clock=self.clock)
        return self.store

    def outer(self, ports: Ports, project=None):
        return ProjectOuterLoop(self.store, ports.role_ports()).run(
            project_run=project or self.project, project_contract=self.pc,
            execution_plan=self.plan)


class Ports:
    """All five roles, bound: each answers the DispatchTicket it is given."""

    def __init__(self, world: World, *, verify=("verified",), verdicts=("approve",),
                 decide=(ACCEPT,)) -> None:
        self.world = world
        self.verify_outcomes = list(verify)
        self.verdicts = list(verdicts)
        self.decisions = list(decide)
        self.calls: list[tuple[str, DispatchTicket | None]] = []
        self.override: dict[str, typing.Callable] = {}

    @staticmethod
    def _next(queue: list):
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def role_ports(self) -> RolePorts:
        return RolePorts(planner=self, tester=self, implementer=self, verifier=self, reviewer=self)

    def propose_step_contract(self, *, project_contract, execution_plan, step_id):
        return make_proposal(step_id)

    def propose_tests(self, *, step_contract, attempt):
        return ()

    def decide_step(self, *, step_contract, step_run, dispatch=None):
        self.calls.append(("planner", dispatch))
        if "planner" in self.override:
            return self.override["planner"](step_contract, step_run.attempt, dispatch)
        return bind_role_output(dispatch, PlannerDecision(
            step_contract_sha256=step_contract.sha256, attempt=step_run.attempt,
            recommendation=self._next(self.decisions), rationale="synthetic decision"))

    def implement(self, *, step_contract, attempt, dispatch=None):
        self.calls.append(("implementer", dispatch))
        if "implementer" in self.override:
            return self.override["implementer"](step_contract, attempt, dispatch)
        return bind_role_output(dispatch, ImplementationReport(
            step_contract_sha256=step_contract.sha256, attempt=attempt, summary="Implemented."))

    def verify(self, *, step_contract, attempt, dispatch=None):
        self.calls.append(("verifier", dispatch))
        if "verifier" in self.override:
            return self.override["verifier"](step_contract, attempt, dispatch)
        receipt = self.world.recorder.record(
            dispatch, evidence_bytes(self._next(self.verify_outcomes), dispatch.ticket_id))
        return bind_role_output(dispatch, VerificationObservation(
            step_contract_sha256=step_contract.sha256, attempt=attempt,
            outcome=receipt.outcome, evidence_sha256=receipt.evidence_sha256))

    def review(self, *, step_contract, attempt, dispatch=None):
        self.calls.append(("reviewer", dispatch))
        if "reviewer" in self.override:
            return self.override["reviewer"](step_contract, attempt, dispatch)
        return bind_role_output(dispatch, ReviewProposal(
            step_contract_sha256=step_contract.sha256, attempt=attempt,
            verdict=self._next(self.verdicts), evidence_sha256=REVIEW_EVIDENCE))


class Driver:
    """Drives one project run by hand, through the store's public API only."""

    def __init__(self, world: World, project=None) -> None:
        self.world = world
        self.project = project or world.project

    @property
    def store(self) -> ControlPlaneStore:
        return self.world.store

    def step(self, step_id: str):
        return self.world.step(step_id, self.project)

    def contract(self, step_id: str):
        return self.world.contract_a if step_id == "step-a" else self.world.contract_b

    def plain(self, step_id: str, event: StepEvent, **payload):
        step = self.step(step_id)
        return self.store.apply_step_transition(step.step_run_id, StepTransitionRequest(
            request_id=new_request_id(), expected_state_version=step.state_version, event=event,
            **payload))

    def ticket(self, step_id: str, role: str) -> DispatchTicket:
        step = self.step(step_id)
        return self.store.issue_dispatch_ticket(step.step_run_id, role=role,
                                                expected_state_version=step.state_version)

    def bound(self, step_id: str, event: StepEvent, field: str, envelope: BoundRoleOutput,
              **extra):
        step = self.step(step_id)
        return self.store.apply_step_transition(
            step.step_run_id,
            StepTransitionRequest(request_id=new_request_id(),
                                  expected_state_version=step.state_version, event=event,
                                  **{field: envelope.output}, **extra.pop("payload", {})),
            role_output=envelope, **extra)

    def to_executing(self, step_id: str):
        if self.step(step_id).state is StepState.PLANNED:
            self.plain(step_id, StepEvent.MARK_READY)
        self.plain(step_id, StepEvent.BEGIN_ATTEMPT)

    def implementation(self, step_id: str, ticket: DispatchTicket | None = None) -> BoundRoleOutput:
        ticket = ticket or self.ticket(step_id, "implementer")
        return bind_role_output(ticket, ImplementationReport(
            step_contract_sha256=ticket.step_contract_sha256, attempt=ticket.attempt,
            summary="Implemented."))

    def implement(self, step_id: str):
        return self.bound(step_id, StepEvent.IMPLEMENTATION_RETURNED, "implementation",
                          self.implementation(step_id))

    def observation(self, step_id: str, outcome: str = "verified") -> BoundRoleOutput:
        ticket = self.ticket(step_id, "verifier")
        receipt = self.world.recorder.record(ticket, evidence_bytes(outcome, ticket.ticket_id))
        return bind_role_output(ticket, VerificationObservation(
            step_contract_sha256=ticket.step_contract_sha256, attempt=ticket.attempt,
            outcome=receipt.outcome, evidence_sha256=receipt.evidence_sha256))

    def verify(self, step_id: str, outcome: str = "verified"):
        return self.bound(step_id, StepEvent.VERIFICATION_OBSERVED, "verification",
                          self.observation(step_id, outcome))

    def review(self, step_id: str, verdict: str = "approve"):
        ticket = self.ticket(step_id, "reviewer")
        return self.bound(step_id, StepEvent.REVIEW_OBSERVED, "review", bind_role_output(
            ticket, ReviewProposal(step_contract_sha256=ticket.step_contract_sha256,
                                   attempt=ticket.attempt, verdict=verdict,
                                   evidence_sha256=REVIEW_EVIDENCE)))

    def decision(self, step_id: str, recommendation=ACCEPT) -> BoundRoleOutput:
        ticket = self.ticket(step_id, "planner")
        return bind_role_output(ticket, PlannerDecision(
            step_contract_sha256=ticket.step_contract_sha256, attempt=ticket.attempt,
            recommendation=recommendation, rationale="synthetic decision"))

    def to_acceptance(self, step_id: str, outcome: str = "verified"):
        self.to_executing(step_id)
        self.implement(step_id)
        self.verify(step_id, outcome)
        if self.step(step_id).state is StepState.REVIEWING:
            self.review(step_id)
        assert self.step(step_id).state is StepState.ACCEPTANCE

    def acceptance(self, step_id: str, challenge: ApprovalChallenge) -> HumanStepAcceptance:
        step = self.step(step_id)
        return HumanStepAcceptance(
            step_contract_sha256=step.step_contract_sha256, attempt=step.attempt,
            approved_by=APPROVER, approved_at=challenge.issued_at,
            approval_text=REQUIRED_STEP_ACCEPTANCE_APPROVAL_TEXT, source="manual")


def inner(world: World, ports: Ports):
    """Mark step a READY (as DL-3 would), then drive it with DL-2."""
    Driver(world).plain("step-a", StepEvent.MARK_READY)
    return StepInnerLoop(world.store, ports.role_ports()).run(
        project_run=world.project, step_run=world.step("step-a"), project_contract=world.pc,
        execution_plan=world.plan, step_contract=world.contract_a)


@pytest.fixture
def world(tmp_path: Path) -> World:
    w = World(tmp_path)
    yield w
    w.session.close()


@pytest.fixture
def human_world(tmp_path: Path) -> World:
    w = World(tmp_path, human=True, review=False)
    yield w
    w.session.close()


def refused(code: RefusalCode = RefusalCode.AUTHORITY_UNPROVEN):
    class _Matcher:
        def __enter__(self):
            self.ctx = pytest.raises(TransitionRefused)
            self.info = self.ctx.__enter__()
            return self.info

        def __exit__(self, *exc):
            result = self.ctx.__exit__(*exc)
            assert self.info.value.code is code, self.info.value
            return result

    return _Matcher()


# --- 1. store and session boundaries -----------------------------------------------


def test_an_authority_store_opens_only_through_its_state_root(world: World) -> None:
    path = world.root.store_path
    world.session.close()
    with pytest.raises(StateUntrustedError, match="DL-4A authority store"):
        ControlPlaneStore.open(path)
    world.reopen()


def test_an_authority_session_refuses_an_offline_store_file(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    root = AidoStateRoot.create(state)
    ControlPlaneStore.open(root.store_path).close()  # an offline v2 file, planted
    with pytest.raises(StateUntrustedError):
        open_authority_session(root, approval_verifier=HmacHumanVerifier())


def test_an_authority_store_refuses_another_state_roots_database(world: World,
                                                                 tmp_path: Path) -> None:
    other_dir = tmp_path / "other-state"
    other_dir.mkdir()
    other = AidoStateRoot.create(other_dir)
    world.session.close()
    shutil.copyfile(world.root.store_path, other.store_path)
    with pytest.raises(StateUntrustedError, match="different state root"):
        open_authority_session(other, approval_verifier=HmacHumanVerifier())
    world.reopen()


def test_an_authority_store_cannot_be_opened_around_the_state_root(world: World) -> None:
    with pytest.raises(StoreError):
        ControlPlaneStore._open_authority(object(), None)
    fake = _AuthorityContext(root=object(), verifier=HmacHumanVerifier(), recorder_key=object())
    with pytest.raises(StoreError):
        ControlPlaneStore._open_authority(fake, None)
    with pytest.raises(ContainmentError):
        AidoStateRoot(str(world.state_dir), "0" * 32)
    with pytest.raises(StoreError):
        open_authority_session(str(world.state_dir))  # a path is not a verified root
    with pytest.raises(StoreError):
        ControlPlaneStore._open_authority(
            _AuthorityContext(root=world.root, verifier=object(), recorder_key=object()), None)


def test_an_offline_store_has_no_authority_capability(tmp_path: Path) -> None:
    store = ControlPlaneStore.open(tmp_path / "offline.sqlite3")
    try:
        assert store.authority_mode is False
        with refused():
            store.issue_dispatch_ticket("0" * 32, role="implementer", expected_state_version=0)
        with refused():
            store.request_project_contract_approval(make_content())
        with refused():
            store.authorized_target_workspace("0" * 32)
        with refused(RefusalCode.INVALID_REQUEST):
            store.apply_step_transition("0" * 32, StepTransitionRequest(
                request_id=new_request_id(), expected_state_version=0,
                event=StepEvent.MARK_READY), role_output=object())
    finally:
        store.close()


def test_unissued_record_methods_are_refused_in_an_authority_store(world: World) -> None:
    before = count(world.store, "contracts")
    other = make_content(goal="A different goal.")
    challenge = world.store.request_project_contract_approval(other)
    with refused():
        world.store.record_project_contract(approved_contract(other, challenge))
    with refused():
        world.store.record_execution_plan(make_plan(world.pc, version=2,
                                                    supersedes=world.plan.sha256))
    hand_built = issue_step_contract(make_proposal("step-a"), project_contract=world.pc,
                                     execution_plan=world.plan, review_required=False,
                                     human_acceptance_required=False, max_attempts=5)
    with refused():
        world.store.record_step_contract(hand_built)
    assert count(world.store, "contracts") == before


def test_without_a_verifier_nothing_can_be_approved(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    session = open_authority_session(AidoStateRoot.create(state), clock=FakeClock())
    try:
        content = make_content()
        challenge = session.store.request_project_contract_approval(content)
        with refused():
            session.store.record_approved_project_contract(
                approved_contract(content, challenge), attest(challenge))
        assert count(session.store, "contracts") == 0
        assert count(session.store, "approval_challenges", "consumed_by IS NOT NULL") == 0
    finally:
        session.close()


def test_the_verification_recorder_exists_only_on_its_session(world: World) -> None:
    with pytest.raises(StoreError):
        VerificationEvidenceRecorder(world.store, object())
    driver = Driver(world)
    driver.to_executing("step-a")
    driver.implement("step-a")
    ticket = driver.ticket("step-a", "verifier")
    with refused():
        world.store._record_verification_evidence(object(), ticket, evidence_bytes())
    assert not hasattr(world.store, "verification_recorder")
    assert count(world.store, "verification_evidence") == 0


# --- 2. the complete issuance-to-consumption chain ---------------------------------


def test_the_full_chain_completes_through_the_normal_orchestration_path(world: World) -> None:
    ports = Ports(world)
    outcome = world.outer(ports)
    assert outcome.stop.value == "plan_work_complete_integration_gate_unavailable"
    assert {s.step_id: s.state for s in outcome.step_runs} == {
        "step-a": StepState.COMPLETE, "step-b": StepState.COMPLETE}
    # Every role call was dispatched under its own persisted ticket, and consumed.
    assert all(ticket is not None for _, ticket in ports.calls)
    assert len({t.ticket_id for _, t in ports.calls}) == len(ports.calls)
    assert count(world.store, "dispatch_tickets") == len(ports.calls)
    assert count(world.store, "dispatch_tickets", "consumed_request_id IS NULL") == 0
    assert count(world.store, "verification_evidence") == 2
    # The chain is re-proven from durable records alone after a restart.
    store = world.reopen()
    report = store.recover(world.project.project_run_id)
    assert report.integrity_ok and report.project_state is ProjectState.ACTIVE
    completion = assess_project_completion(store, world.project.project_run_id)
    assert completion.plan_work_complete is True
    assert completion.complete_authorized is False


def test_a_retry_binds_each_attempt_to_its_own_dispatches_and_evidence(tmp_path: Path) -> None:
    world = World(tmp_path, review=False, max_attempts=2)
    ports = Ports(world, verify=("verification-failed", "verified"), decide=(RETRY, ACCEPT))
    outcome = inner(world, ports)
    assert outcome.stop.value == "step_complete"
    rows = world.store._conn.execute(
        "SELECT attempt, outcome FROM verification_evidence ORDER BY attempt").fetchall()
    assert [tuple(r) for r in rows] == [(1, "verification-failed"), (2, "verified")]
    world.reopen()
    assert world.store.recover(world.project.project_run_id).integrity_ok
    world.session.close()


def test_a_step_version_is_dispatched_to_a_role_at_most_once_by_anyone(
        world: World, tmp_path: Path) -> None:
    driver = Driver(world)
    driver.to_executing("step-a")
    driver.ticket("step-a", "implementer")
    with refused():
        driver.ticket("step-a", "implementer")
    with refused(RefusalCode.OUT_OF_ORDER):
        driver.ticket("step-a", "verifier")
    with refused(RefusalCode.STALE_STATE_VERSION):
        world.store.issue_dispatch_ticket(driver.step("step-a").step_run_id,
                                          role="implementer", expected_state_version=0)

    # A port that re-enters to take another ticket for its own dispatch is refused.
    world2 = World(tmp_path, name="re")
    ports = Ports(world2)
    taken = []

    def greedy(contract, attempt, dispatch):
        try:
            world2.store.issue_dispatch_ticket(dispatch.step_run_id, role="implementer",
                                               expected_state_version=dispatch.state_version)
        except TransitionRefused as exc:
            taken.append(exc.code)
        return bind_role_output(dispatch, ImplementationReport(
            step_contract_sha256=contract.sha256, attempt=attempt, summary="ok"))

    ports.override["implementer"] = greedy
    world2.outer(ports)
    assert taken == [RefusalCode.AUTHORITY_UNPROVEN, RefusalCode.AUTHORITY_UNPROVEN]
    world2.session.close()


def test_human_acceptance_completes_only_through_a_verified_attestation(
        human_world: World) -> None:
    world = human_world
    driver = Driver(world)
    driver.to_acceptance("step-a")
    challenge = world.store.request_step_acceptance(driver.step("step-a").step_run_id)
    assert challenge.subject_kind is ApprovalSubjectKind.STEP_ACCEPTANCE
    applied = driver.bound("step-a", StepEvent.DECIDE_ACCEPTANCE, "planner_decision",
                           driver.decision("step-a"),
                           payload={"human_acceptance": driver.acceptance("step-a", challenge)},
                           human_attestation=attest(challenge))
    assert applied.current_state == StepState.COMPLETE.value
    assert count(world.store, "approval_challenges", "consumed_by = ?",
                 (applied.record.request_id,)) == 1
    world.reopen()
    assert world.store.recover(world.project.project_run_id).integrity_ok


def test_the_normal_orchestration_path_never_supplies_human_acceptance(
        human_world: World) -> None:
    world = human_world
    outcome = world.outer(Ports(world))
    assert world.step("step-a").state is StepState.HUMAN_REQUIRED
    assert outcome.project_run.state is ProjectState.HUMAN_REQUIRED
    assert count(world.store, "approval_challenges", "subject_kind = 'step_acceptance'") == 0


# --- 3. forged and stale approvals --------------------------------------------------


def test_a_constructed_approval_is_not_a_recorded_approval(world: World) -> None:
    content = make_content(goal="A forged goal.")
    real = world.store.request_project_contract_approval(content)
    forged_challenge = real.model_copy(update={"challenge_id": "f" * 32})
    with refused():
        world.store.record_approved_project_contract(
            approved_contract(content, real), attest(forged_challenge))
    assert count(world.store, "contracts", "sha256 = ?", (content.sha256,)) == 0


class _Raises:
    def verify(self, *, challenge, attestation):
        raise RuntimeError("attestation service unavailable")


class _Truthy:
    def __init__(self, value):
        self.value = value

    def verify(self, *, challenge, attestation):
        return self.value


@pytest.mark.parametrize("verifier", [
    HmacHumanVerifier(key=b"another key"),
    HmacHumanVerifier(approvers=("someone-else",)),
    _Raises(),
    _Truthy(1),
    _Truthy("yes"),
    _Truthy(None),
], ids=["wrong-key", "unauthorized-approver", "raises", "one", "yes", "none"])
def test_an_unconfirmed_attestation_is_refused(world: World, verifier) -> None:
    store = world.reopen(verifier=verifier)
    content = make_content(goal="Another goal.")
    challenge = store.request_project_contract_approval(content)
    with refused():
        store.record_approved_project_contract(approved_contract(content, challenge),
                                               attest(challenge))
    assert count(store, "approval_challenges", "challenge_id = ? AND consumed_by IS NULL",
                 (challenge.challenge_id,)) == 1


def test_a_proof_made_with_the_wrong_key_is_refused(world: World) -> None:
    content = make_content(goal="Another goal.")
    challenge = world.store.request_project_contract_approval(content)
    with refused():
        world.store.record_approved_project_contract(
            approved_contract(content, challenge), attest(challenge, key=b"guessed"))


def test_an_attestation_for_another_subject_is_refused(world: World) -> None:
    first, second = make_content(goal="First goal."), make_content(goal="Second goal.")
    challenge = world.store.request_project_contract_approval(first)
    with refused():
        world.store.record_approved_project_contract(approved_contract(second, challenge),
                                                     attest(challenge))
    # Re-signing the attestation for the other subject does not move the challenge.
    with refused():
        world.store.record_approved_project_contract(
            approved_contract(second, challenge),
            attest(challenge, subject_sha256=second.sha256))
    # Nor does an answer of another kind.
    with pytest.raises(ValidationError):
        attest(challenge, subject_kind=ApprovalSubjectKind.PLAN_ACTIVATION)


@pytest.mark.parametrize("field", ["approved_by", "approved_at"])
def test_the_approval_block_must_record_the_attested_approval(world: World, field) -> None:
    content = make_content(goal="Another goal.")
    challenge = world.store.request_project_contract_approval(content)
    if field == "approved_by":
        contract = approved_contract(content, challenge, approver="someone-else")
    else:
        contract = approved_contract(content, challenge,
                                     at=challenge.issued_at + timedelta(seconds=1))
    with refused():
        world.store.record_approved_project_contract(contract, attest(challenge))


def test_an_approval_is_single_use_and_a_replay_is_a_receipt(world: World) -> None:
    content = make_content(goal="Another goal.")
    challenge = world.store.request_project_contract_approval(content)
    contract, attestation = approved_contract(content, challenge), attest(challenge)
    assert world.store.record_approved_project_contract(contract, attestation) == content.sha256
    consumed = count(world.store, "approval_challenges", "consumed_by IS NOT NULL")
    # The identical approval again is a receipt; nothing new is consumed.
    assert world.store.record_approved_project_contract(contract, attestation) == content.sha256
    assert count(world.store, "approval_challenges", "consumed_by IS NOT NULL") == consumed
    # A fresh challenge cannot approve it a second time.
    again = world.store.request_project_contract_approval(content)
    with refused():
        world.store.record_approved_project_contract(approved_contract(content, again),
                                                     attest(again))


def test_an_expired_challenge_is_refused(world: World) -> None:
    content = make_content(goal="Another goal.")
    challenge = world.store.request_project_contract_approval(content)
    world.clock.now += APPROVAL_CHALLENGE_TTL
    with refused():
        world.store.record_approved_project_contract(approved_contract(content, challenge),
                                                     attest(challenge))


@pytest.mark.parametrize("offset", [timedelta(seconds=-1), timedelta(days=1)],
                         ids=["before-issue", "in-the-future"])
def test_an_attestation_dated_outside_its_window_is_refused(world: World, offset) -> None:
    content = make_content(goal="Another goal.")
    challenge = world.store.request_project_contract_approval(content)
    at = challenge.issued_at + offset
    with refused():
        world.store.record_approved_project_contract(
            approved_contract(content, challenge, at=at), attest(challenge, at=at))


def test_a_paraphrased_attestation_is_refused(world: World) -> None:
    content = make_content(goal="Another goal.")
    challenge = world.store.request_project_contract_approval(content)
    with pytest.raises(ValidationError):
        attest(challenge, approval_text="I approve this.")
    forged = attest(challenge).model_copy(update={"approval_text": "I approve this."})
    with refused():
        world.store.record_approved_project_contract(approved_contract(content, challenge),
                                                     forged)


def test_a_forged_human_step_acceptance_is_refused(human_world: World) -> None:
    world = human_world
    driver = Driver(world)
    driver.to_acceptance("step-a")
    step = driver.step("step-a")
    challenge = world.store.request_step_acceptance(step.step_run_id)
    decision = driver.decision("step-a")
    acceptance = driver.acceptance("step-a", challenge)
    # A valid HumanStepAcceptance without an attestation is not acceptance.
    with refused():
        driver.bound("step-a", StepEvent.DECIDE_ACCEPTANCE, "planner_decision", decision,
                     payload={"human_acceptance": acceptance})
    # An attestation of another kind, or for another challenge, is not either.
    project_challenge = world.store.request_project_contract_approval(make_content(goal="X y."))
    with refused():
        driver.bound("step-a", StepEvent.DECIDE_ACCEPTANCE, "planner_decision", decision,
                     payload={"human_acceptance": acceptance},
                     human_attestation=attest(project_challenge))
    with refused():
        driver.bound("step-a", StepEvent.DECIDE_ACCEPTANCE, "planner_decision", decision,
                     payload={"human_acceptance": acceptance},
                     human_attestation=attest(challenge, key=b"guessed"))
    # An attestation without a human acceptance is refused too.
    with refused():
        driver.bound("step-a", StepEvent.DECIDE_ACCEPTANCE, "planner_decision", decision,
                     human_attestation=attest(challenge))
    assert driver.step("step-a").state is StepState.ACCEPTANCE
    # Nothing was consumed: the genuine acceptance still works with the same ticket.
    applied = driver.bound("step-a", StepEvent.DECIDE_ACCEPTANCE, "planner_decision", decision,
                           payload={"human_acceptance": acceptance},
                           human_attestation=attest(challenge))
    assert applied.current_state == StepState.COMPLETE.value


def test_a_step_acceptance_goes_stale_when_the_step_moves(tmp_path: Path) -> None:
    world = World(tmp_path, human=True, review=False, max_attempts=2)
    driver = Driver(world)
    driver.to_acceptance("step-a")
    old = world.store.request_step_acceptance(driver.step("step-a").step_run_id)
    old_acceptance = driver.acceptance("step-a", old)
    driver.bound("step-a", StepEvent.DECIDE_ACCEPTANCE, "planner_decision",
                 driver.decision("step-a", RETRY))
    driver.to_acceptance("step-a")
    stale = old_acceptance.model_copy(update={"attempt": 2})
    with refused():
        driver.bound("step-a", StepEvent.DECIDE_ACCEPTANCE, "planner_decision",
                     driver.decision("step-a"), payload={"human_acceptance": stale},
                     human_attestation=attest(old))
    assert driver.step("step-a").state is StepState.ACCEPTANCE
    world.session.close()


# --- 4. forged verification ---------------------------------------------------------


def _at_verifying(world: World, project=None) -> Driver:
    driver = Driver(world, project)
    driver.to_executing("step-a")
    driver.implement("step-a")
    assert driver.step("step-a").state is StepState.VERIFYING
    return driver


def test_a_constructed_verification_observation_is_not_verification(world: World) -> None:
    driver = _at_verifying(world)
    ticket = driver.ticket("step-a", "verifier")
    forged = bind_role_output(ticket, VerificationObservation(
        step_contract_sha256=ticket.step_contract_sha256, attempt=1, outcome="verified",
        evidence_sha256=hashlib.sha256(evidence_bytes()).hexdigest()))
    with refused():
        driver.bound("step-a", StepEvent.VERIFICATION_OBSERVED, "verification", forged)
    assert driver.step("step-a").state is StepState.VERIFYING


def test_an_observation_must_state_exactly_its_recorded_evidence(world: World) -> None:
    driver = _at_verifying(world)
    ticket = driver.ticket("step-a", "verifier")
    receipt = world.recorder.record(ticket, evidence_bytes("verification-failed", "x"))
    assert receipt.outcome == "verification-failed"
    for outcome, sha in [("verified", receipt.evidence_sha256),
                         ("verification-failed", "b" * 64)]:
        forged = bind_role_output(ticket, VerificationObservation(
            step_contract_sha256=ticket.step_contract_sha256, attempt=1, outcome=outcome,
            evidence_sha256=sha))
        with refused():
            driver.bound("step-a", StepEvent.VERIFICATION_OBSERVED, "verification", forged)
    # A second recording for the same dispatch is refused: evidence is per dispatch.
    with refused():
        world.recorder.record(ticket, evidence_bytes("verified", "y"))


def _not_v1(data: bytes) -> bytes:
    return data.replace(b'"verification-result.v1"', b'"verification-result.v2"')


@pytest.mark.parametrize("make", [
    lambda: b"not json",
    lambda: b"\xff\xfe",
    lambda: b"[]",
    lambda: _not_v1(evidence_bytes()),
    lambda: evidence_bytes().replace(b'"controlled-verification"', b'"other-mode"'),
    lambda: evidence_bytes()[:-1] + b',"extra":1}',
    lambda: evidence_bytes().replace(b'"next_step":', b'"next_step_x":'),
    lambda: evidence_bytes()[:-1] + b',"outcome":"verified"}',
    lambda: evidence_bytes().replace(b'"passed":true', b'"passed":false'),
    lambda: evidence_bytes("verification-failed").replace(b'"outcome":"verification-failed"',
                                                          b'"outcome":"verified"'),
    lambda: evidence_bytes("workspace-state-untrusted").replace(
        b'"outcome":"workspace-state-untrusted"', b'"outcome":"verified"'),
    lambda: evidence_bytes().replace(b'"passed":true', b'"passed":1'),
    lambda: evidence_bytes().replace(b'"return_code":0', b'"return_code":NaN'),
    lambda: evidence_bytes().decode("utf-8"),
], ids=["text", "not-utf8", "array", "schema", "mode", "extra-field", "missing-field",
        "duplicate-key", "outcome-contradicts-run", "failed-claims-verified",
        "untrusted-claims-verified", "non-boolean-fact", "nan", "str-not-bytes"])
def test_malformed_or_self_contradicting_evidence_is_never_recorded(world: World, make) -> None:
    driver = _at_verifying(world)
    ticket = driver.ticket("step-a", "verifier")
    with refused():
        world.recorder.record(ticket, make())
    assert count(world.store, "verification_evidence") == 0
    assert os.listdir(world.root.contained_directory(("evidence", "verification"))) == []


def test_evidence_placed_in_the_state_root_by_hand_is_not_evidence(world: World) -> None:
    driver = _at_verifying(world)
    data = evidence_bytes()
    sha = hashlib.sha256(data).hexdigest()
    Path(world.root.contained_directory(("evidence", "verification")), f"{sha}.json"
         ).write_bytes(data)
    ticket = driver.ticket("step-a", "verifier")
    with refused():
        driver.bound("step-a", StepEvent.VERIFICATION_OBSERVED, "verification", bind_role_output(
            ticket, VerificationObservation(step_contract_sha256=ticket.step_contract_sha256,
                                            attempt=1, outcome="verified", evidence_sha256=sha)))


def _evidence_file(world: World) -> Path:
    (name,) = os.listdir(world.root.contained_directory(("evidence", "verification")))
    return Path(world.root.contained_directory(("evidence", "verification")), name)


def test_evidence_tampered_before_consumption_is_refused(world: World) -> None:
    driver = _at_verifying(world)
    envelope = driver.observation("step-a")
    path = _evidence_file(world)
    path.write_bytes(path.read_bytes().replace(b"synthetic run", b"synthetic RUN"))
    with refused():
        driver.bound("step-a", StepEvent.VERIFICATION_OBSERVED, "verification", envelope)


@pytest.mark.parametrize("damage", ["rewrite", "delete"])
def test_damaged_evidence_makes_a_completed_run_untrusted(world: World, damage) -> None:
    world.outer(Ports(world))
    victim = sorted(Path(world.root.contained_directory(("evidence", "verification"))).iterdir())[0]
    if damage == "rewrite":
        victim.write_bytes(victim.read_bytes().replace(b"synthetic run", b"synthetic RUN"))
    else:
        victim.unlink()
    with pytest.raises(StateUntrustedError):
        world.store.list_step_runs(world.project.project_run_id)
    store = world.reopen()
    report = store.recover(world.project.project_run_id)
    assert not report.integrity_ok
    assert report.project_state is ProjectState.HUMAN_REQUIRED


def test_a_verifier_port_cannot_choose_its_own_outcome(world: World) -> None:
    ports = Ports(world)

    def liar(contract, attempt, dispatch):
        receipt = world.recorder.record(dispatch, evidence_bytes("verification-failed", "lie"))
        return bind_role_output(dispatch, VerificationObservation(
            step_contract_sha256=contract.sha256, attempt=attempt, outcome="verified",
            evidence_sha256=receipt.evidence_sha256))

    ports.override["verifier"] = liar
    outcome = inner(world, ports)
    assert outcome.step_run.state is StepState.RECOVERY_REQUIRED
    assert outcome.cause == "result_not_recorded"
    assert outcome.refusal_code is RefusalCode.AUTHORITY_UNPROVEN


def test_the_verification_mirror_matches_the_shipped_report() -> None:
    from ai_dev_orchestrator.verification.verifier import (
        VERIFICATION_MODE,
        VERIFICATION_SCHEMA_VERSION,
        VerificationResultReport,
        VerificationWorkspacePostconditionBlock,
    )

    assert VERIFICATION_RESULT_FIELDS == set(VerificationResultReport.model_fields)
    assert set(VERIFICATION_TRUST_FIELDS) <= set(
        VerificationWorkspacePostconditionBlock.model_fields)
    assert VERIFICATION_RESULT_SCHEMA_VERSION == VERIFICATION_SCHEMA_VERSION
    assert VERIFICATION_RESULT_MODE == VERIFICATION_MODE
    shipped = VerificationResultReport.model_fields["outcome"].annotation
    assert typing.get_args(shipped) == typing.get_args(VerificationOutcome)


@pytest.mark.parametrize("outcome", typing.get_args(VerificationOutcome))
def test_shipped_reports_prove_exactly_their_own_outcome(outcome) -> None:
    data = evidence_bytes(outcome)
    assert verification_outcome_from_evidence(data) == outcome
    # The accepted contract is unchanged: the same bytes still parse as v1.
    from ai_dev_orchestrator.verification.verifier import VerificationResultReport
    assert VerificationResultReport.model_validate_json(data).outcome == outcome


# --- 5. role-output identity binding and cross-run reuse ----------------------------


def test_a_role_output_from_another_project_run_is_refused(world: World) -> None:
    second = world.new_run()
    first_driver, second_driver = Driver(world), Driver(world, second)
    for driver in (first_driver, second_driver):
        driver.to_executing("step-a")
    first_output = first_driver.implementation("step-a")
    # The frozen payload is identical for both runs; only the binding differs.
    second_ticket = second_driver.ticket("step-a", "implementer")
    assert first_output.output == second_driver.implementation(
        "step-a", second_ticket).output
    with refused():
        second_driver.bound("step-a", StepEvent.IMPLEMENTATION_RETURNED, "implementation",
                            first_output)
    # Re-labelling the first run's ticket with the second run's ids does not help.
    relabelled = first_output.model_copy(update={
        "project_run_id": second.project_run_id,
        "step_run_id": second_driver.step("step-a").step_run_id})
    with refused():
        second_driver.bound("step-a", StepEvent.IMPLEMENTATION_RETURNED, "implementation",
                            relabelled)
    assert second_driver.step("step-a").state is StepState.EXECUTING
    # Each run's own binding still works.
    second_driver.bound("step-a", StepEvent.IMPLEMENTATION_RETURNED, "implementation",
                        second_driver.implementation("step-a", second_ticket))
    first_driver.bound("step-a", StepEvent.IMPLEMENTATION_RETURNED, "implementation",
                       first_output)


def test_a_cached_role_output_cannot_answer_a_later_dispatch(tmp_path: Path) -> None:
    world = World(tmp_path, review=False, max_attempts=2)
    ports = Ports(world, verify=("verification-failed",), decide=(RETRY, ACCEPT))
    cache: list[BoundRoleOutput] = []

    def replaying(contract, attempt, dispatch):
        if not cache:
            cache.append(bind_role_output(dispatch, ImplementationReport(
                step_contract_sha256=contract.sha256, attempt=attempt, summary="first")))
        return cache[0].model_copy(update={"attempt": attempt}) if attempt > 1 else cache[0]

    ports.override["implementer"] = replaying
    outcome = inner(world, ports)
    assert outcome.step_run.state is StepState.RECOVERY_REQUIRED
    assert outcome.cause in ("role_output_misbound", "role_output_malformed")
    world.session.close()


def test_a_consumed_dispatch_cannot_answer_twice(world: World) -> None:
    driver = Driver(world)
    driver.to_executing("step-a")
    envelope = driver.implementation("step-a")
    driver.bound("step-a", StepEvent.IMPLEMENTATION_RETURNED, "implementation", envelope)
    # Same envelope, new request id, at the next version: the ticket is spent and stale.
    with refused():
        driver.bound("step-a", StepEvent.IMPLEMENTATION_RETURNED, "implementation", envelope)


def test_the_payload_must_be_the_bound_output(world: World) -> None:
    driver = Driver(world)
    driver.to_executing("step-a")
    envelope = driver.implementation("step-a")
    step = driver.step("step-a")
    other = ImplementationReport(step_contract_sha256=step.step_contract_sha256, attempt=1,
                                 summary="Something else.")
    with refused():
        world.store.apply_step_transition(step.step_run_id, StepTransitionRequest(
            request_id=new_request_id(), expected_state_version=step.state_version,
            event=StepEvent.IMPLEMENTATION_RETURNED, implementation=other),
            role_output=envelope)


def test_a_ticket_for_another_role_or_version_is_refused(world: World) -> None:
    driver = Driver(world)
    driver.to_executing("step-a")
    implementer = driver.implementation("step-a")
    driver.bound("step-a", StepEvent.IMPLEMENTATION_RETURNED, "implementation", implementer)
    verifier_ticket = driver.ticket("step-a", "verifier")
    # An implementer envelope relabelled as the verifier's role fails validation.
    with pytest.raises(ValidationError):
        bind_role_output(verifier_ticket, implementer.output)
    # A verifier envelope offered with an event that takes no role output is refused.
    receipt = world.recorder.record(verifier_ticket, evidence_bytes("verified", "r"))
    envelope = bind_role_output(verifier_ticket, VerificationObservation(
        step_contract_sha256=verifier_ticket.step_contract_sha256, attempt=1,
        outcome="verified", evidence_sha256=receipt.evidence_sha256))
    step = driver.step("step-a")
    with refused():
        world.store.apply_step_transition(step.step_run_id, StepTransitionRequest(
            request_id=new_request_id(), expected_state_version=step.state_version,
            event=StepEvent.ESCALATE, reason="no"), role_output=envelope)
    driver.bound("step-a", StepEvent.VERIFICATION_OBSERVED, "verification", envelope)
    assert driver.step("step-a").state is StepState.REVIEWING


def test_an_unbound_output_is_refused_on_both_paths(world: World) -> None:
    driver = Driver(world)
    driver.to_executing("step-a")
    step = driver.step("step-a")
    with refused():
        world.store.apply_step_transition(step.step_run_id, StepTransitionRequest(
            request_id=new_request_id(), expected_state_version=step.state_version,
            event=StepEvent.IMPLEMENTATION_RETURNED, implementation=ImplementationReport(
                step_contract_sha256=step.step_contract_sha256, attempt=1, summary="x")))
    # A DL-1/2/3-era port that returns a bare output is a malformed dispatch.
    world2 = World(Path(world.state_dir.parent), name="legacy")
    ports = Ports(world2)
    ports.override["implementer"] = lambda contract, attempt, dispatch: ImplementationReport(
        step_contract_sha256=contract.sha256, attempt=attempt, summary="bare")
    outcome = world2.outer(ports)
    assert world2.step("step-a").state is StepState.RECOVERY_REQUIRED
    assert outcome.invocations[0].inner_stop.value == "step_recovery_required"
    assert count(world2.store, "transitions", "event = 'implementation_returned'") == 0
    world2.session.close()


def test_the_dl3_role_output_binding_gap_is_closed_in_an_authority_store(world: World) -> None:
    """Counterpart of DL-3's pinned known limitation: two runs of one contract
    share (step_contract_sha256, attempt), but not a dispatch."""
    second = world.new_run()
    ports_seen: dict[str, list[str]] = {"a": [], "b": []}
    for label, project in (("a", world.project), ("b", second)):
        ports = Ports(world)
        world.outer(ports, project)
        ports_seen[label] = [t.ticket_id for _, t in ports.calls]
    assert not set(ports_seen["a"]) & set(ports_seen["b"])
    tickets = world.store._conn.execute(
        "SELECT DISTINCT project_run_id FROM dispatch_tickets").fetchall()
    assert len(tickets) == 2


# --- 6. policy issuance ---------------------------------------------------------------


def test_a_plan_is_never_recorded_without_its_own_human_activation(world: World,
                                                                     tmp_path: Path) -> None:
    successor = make_plan(world.pc, version=2, supersedes=world.plan.sha256)
    other_workspace = tmp_path / "other-workspace"
    other_workspace.mkdir()
    loose = make_policy(review=False, human=False, max_attempts=5)
    approved_for_policy = world.store.request_plan_activation(
        execution_plan=successor, execution_policy=world.policy, target_workspace=world.workspace)
    approved_for_workspace = world.store.request_plan_activation(
        execution_plan=successor, execution_policy=world.policy,
        target_workspace=other_workspace)
    contract_challenge = world.store.request_project_contract_approval(make_content(goal="Q r."))
    attempts = [
        (loose, world.workspace, attest(approved_for_policy)),          # another policy
        (world.policy, other_workspace, attest(approved_for_policy)),  # another workspace
        (world.policy, world.workspace, attest(approved_for_workspace)),
        (world.policy, world.workspace, attest(contract_challenge)),   # another kind
    ]
    for policy, workspace, attestation in attempts:
        with refused():
            world.store.issue_execution_plan(successor, execution_policy=policy,
                                             target_workspace=workspace, attestation=attestation)
    assert len(world.store.list_execution_plans(world.pc.sha256)) == 1


def test_a_plan_of_an_unapproved_contract_cannot_even_be_requested(world: World) -> None:
    content = make_content(goal="Never approved.")
    challenge = world.store.request_project_contract_approval(content)
    unapproved = approved_contract(content, challenge)  # built, never recorded
    with pytest.raises(RecordNotFoundError):
        world.store.request_plan_activation(execution_plan=make_plan(unapproved),
                                            execution_policy=world.policy,
                                            target_workspace=world.workspace)


def test_a_run_needs_an_issued_plan(world: World) -> None:
    plan = make_plan(world.pc, version=2, supersedes=world.plan.sha256)
    db = world.root.store_path
    world.session.close()
    tamper(db, "INSERT INTO contracts (sha256, kind, project_id, scope_sha256, step_id, version, "
               "body) VALUES (?, 'execution_plan', ?, ?, '', 2, ?)",
           (plan.sha256, plan.project_id, world.pc.sha256, plan.model_dump_json()))
    store = world.reopen()
    with refused():
        store.create_project_run(project_contract_sha256=world.pc.sha256,
                                 execution_plan_sha256=plan.sha256)


def test_a_caller_cannot_choose_a_step_contracts_policy(world: World) -> None:
    with pytest.raises(TypeError):
        world.store.issue_authorized_step_contract(
            make_proposal("step-a"), execution_plan_sha256=world.plan.sha256,
            max_attempts=5)  # type: ignore[call-arg]
    issued = world.store.issue_authorized_step_contract(
        make_proposal("step-a"), execution_plan_sha256=world.plan.sha256)
    assert issued == world.contract_a  # a receipt, under the approved policy
    assert (issued.review_required, issued.human_acceptance_required, issued.max_attempts) == (
        world.policy.review_required, world.policy.human_acceptance_required,
        world.policy.max_attempts)
    # A proposal that names a policy value is refused as an extra field.
    with pytest.raises(ValidationError):
        StepContractProposal(step_id="step-a", requirements=("x y",), max_attempts=5)


def test_a_hand_inserted_step_contract_cannot_start_a_step_run(world: World) -> None:
    """A contract that satisfies every DL-1 issuance rule, but with a policy the
    human never approved, is written straight into the contracts table."""
    loose = issue_step_contract(make_proposal("step-a"), project_contract=world.pc,
                                execution_plan=world.plan, review_required=False,
                                human_acceptance_required=False, max_attempts=5,
                                step_contract_version=2,
                                supersedes_sha256=world.contract_a.sha256)
    db = world.root.store_path
    world.session.close()
    tamper(db, "INSERT INTO contracts (sha256, kind, project_id, scope_sha256, step_id, version, "
               "body) VALUES (?, 'step_contract', ?, ?, 'step-a', 2, ?)",
           (loose.sha256, loose.project_id, world.plan.sha256, loose.model_dump_json()))
    store = world.reopen()
    fresh = store.create_project_run(project_contract_sha256=world.pc.sha256,
                                     execution_plan_sha256=world.plan.sha256)
    with refused():
        store.create_step_run(project_run_id=fresh.project_run_id,
                              step_contract_sha256=loose.sha256)
    assert count(store, "step_runs", "project_run_id = ?", (fresh.project_run_id,)) == 0


def _flip(column: str) -> str:
    """SQL that always changes a digest's first character (never a no-op)."""
    return f"(CASE substr({column}, 1, 1) WHEN '0' THEN '1' ELSE '0' END || substr({column}, 2))"


@pytest.mark.parametrize("sql", [
    "UPDATE plan_issuances SET policy = replace(policy, '\"max_attempts\":2', "
    "'\"max_attempts\":5')",
    "UPDATE step_contract_issuances SET policy_sha256 = " + _flip("policy_sha256"),
    "DELETE FROM step_contract_issuances",
    "UPDATE approval_challenges SET attestation_sha256 = " + _flip("attestation_sha256") + " "
    "WHERE subject_kind = 'project_contract'",
    "UPDATE approval_challenges SET consumed_by = NULL WHERE subject_kind = 'plan_activation'",
    "UPDATE plan_issuances SET target_workspace_sha256 = " + _flip("target_workspace_sha256"),
    "UPDATE dispatch_tickets SET consumed_request_id = NULL",
    "UPDATE verification_evidence SET outcome = 'verified' WHERE 0 = 1",
    "UPDATE dispatch_tickets SET state_version = state_version + 100 WHERE role = 'implementer'",
], ids=["policy", "step-policy-digest", "step-issuance-deleted", "approval-rewritten",
        "approval-unconsumed", "workspace-digest", "ticket-unconsumed", "noop-control",
        "ticket-version"])
def test_tampered_authority_records_make_the_run_untrusted(world: World, sql) -> None:
    world.outer(Ports(world))
    db = world.root.store_path
    world.session.close()
    tamper(db, sql)
    store = world.reopen()
    report = store.recover(world.project.project_run_id)
    if "0 = 1" in sql:
        assert report.integrity_ok
        return
    assert not report.integrity_ok
    assert report.project_state is ProjectState.HUMAN_REQUIRED


def test_a_successor_plan_needs_its_own_activation_and_leaves_the_run_pending(
        world: World) -> None:
    successor = make_plan(world.pc, version=2, supersedes=world.plan.sha256)
    world.activate(successor, world.policy)
    outcome = world.outer(Ports(world))
    assert outcome.stop.value == "plan_supersession_pending"
    assert outcome.project_run.state is ProjectState.ACTIVE
    assert world.step("step-a").state is StepState.PLANNED


# --- 7. replay and restart -------------------------------------------------------------


def test_an_identical_bound_request_replays_as_a_receipt(world: World) -> None:
    driver = Driver(world)
    driver.to_executing("step-a")
    envelope = driver.implementation("step-a")
    step = driver.step("step-a")
    request = StepTransitionRequest(request_id=new_request_id(),
                                    expected_state_version=step.state_version,
                                    event=StepEvent.IMPLEMENTATION_RETURNED,
                                    implementation=envelope.output)
    first = world.store.apply_step_transition(step.step_run_id, request, role_output=envelope)
    again = world.store.apply_step_transition(step.step_run_id, request, role_output=envelope)
    assert not first.duplicate and again.duplicate
    assert count(world.store, "dispatch_tickets", "consumed_request_id IS NOT NULL") == 1


def test_a_ticket_outstanding_at_a_crash_is_never_answerable(world: World) -> None:
    driver = Driver(world)
    driver.to_executing("step-a")
    envelope = driver.implementation("step-a")
    store = world.reopen()  # the session ended with the dispatch in flight
    report = store.recover(world.project.project_run_id)
    assert report.recovered_step_run_ids == (driver.step("step-a").step_run_id,)
    with pytest.raises(TransitionRefused):
        driver.bound("step-a", StepEvent.IMPLEMENTATION_RETURNED, "implementation", envelope)
    assert driver.step("step-a").state is StepState.RECOVERY_REQUIRED


def test_project_completion_and_blocked_states_stay_unresolved(world: World) -> None:
    world.outer(Ports(world))
    project = world.store.get_project_run(world.project.project_run_id)
    with refused(RefusalCode.UNSUPPORTED_IN_DL1):
        world.store.apply_project_transition(project.project_run_id, ProjectTransitionRequest(
            request_id=new_request_id(), expected_state_version=project.state_version,
            event=ProjectEvent.REQUEST_COMPLETE, reason="all steps complete"))


# --- 8. malformed inputs and post-validation mutation ----------------------------------


class _AttestationSubclass(HumanAttestation):
    pass


@pytest.mark.parametrize("make", [
    lambda a: a.model_dump(),
    lambda a: _AttestationSubclass(**a.model_dump()),
    lambda a: HumanAttestation.model_construct(**{**a.model_dump(), "approval_text": "ok"}),
    lambda a: HumanAttestation.model_construct(**{**a.model_dump(), "challenge_id": "x"}),
    lambda a: None,
], ids=["dict", "subclass", "construct-phrase", "construct-id", "none"])
def test_malformed_attestations_are_refused(world: World, make) -> None:
    content = make_content(goal="Another goal.")
    challenge = world.store.request_project_contract_approval(content)
    with refused():
        world.store.record_approved_project_contract(approved_contract(content, challenge),
                                                     make(attest(challenge)))


@pytest.mark.parametrize("make", [
    lambda e: e.model_dump(),
    lambda e: BoundRoleOutput.model_construct(**{**dict(e), "attempt": 2}),
    lambda e: BoundRoleOutput.model_construct(**{**dict(e), "ticket_id": "nope"}),
    lambda e: type("Sub", (BoundRoleOutput,), {})(**dict(e)),
], ids=["dict", "construct-attempt", "construct-ticket", "subclass"])
def test_malformed_role_output_envelopes_are_refused(world: World, make) -> None:
    driver = Driver(world)
    driver.to_executing("step-a")
    envelope = driver.implementation("step-a")
    step = driver.step("step-a")
    with refused():
        world.store.apply_step_transition(step.step_run_id, StepTransitionRequest(
            request_id=new_request_id(), expected_state_version=step.state_version,
            event=StepEvent.IMPLEMENTATION_RETURNED, implementation=envelope.output),
            role_output=make(envelope))
    assert driver.step("step-a").state is StepState.EXECUTING


def test_mutating_an_input_after_it_is_consumed_changes_nothing(world: World) -> None:
    driver = Driver(world)
    driver.to_executing("step-a")
    envelope = driver.implementation("step-a")
    driver.bound("step-a", StepEvent.IMPLEMENTATION_RETURNED, "implementation", envelope)
    object.__setattr__(envelope, "ticket_id", "0" * 32)
    object.__setattr__(envelope.output, "summary", "rewritten afterwards")
    store = world.reopen()
    assert store.recover(world.project.project_run_id).integrity_ok


def test_a_port_mutating_its_dispatch_ticket_cannot_widen_it(world: World) -> None:
    ports = Ports(world)

    def widening(contract, attempt, dispatch):
        object.__setattr__(dispatch, "role", "planner")
        object.__setattr__(dispatch, "state_version", 999)
        return BoundRoleOutput.model_construct(
            schema_version="bound-role-output.v1", ticket_id=dispatch.ticket_id,
            project_run_id=dispatch.project_run_id, step_run_id=dispatch.step_run_id,
            step_contract_sha256=contract.sha256, attempt=attempt, role="implementer",
            output=ImplementationReport(step_contract_sha256=contract.sha256, attempt=attempt,
                                        summary="ok"))

    ports.override["implementer"] = widening
    outcome = world.outer(ports)
    # DL-2 gave the port a copy, and the store re-proves its own ticket row.
    assert world.step("step-a").state in (StepState.COMPLETE,)
    assert outcome.step_runs[0].state is StepState.COMPLETE


# --- 9. filesystem containment, partial persistence and cleanup -----------------------


@pytest.mark.parametrize("case", ["relative", "dotdot", "missing", "file", "non-empty"])
def test_a_state_root_must_be_an_empty_absolute_canonical_directory(tmp_path: Path,
                                                                    case) -> None:
    (tmp_path / "dir").mkdir()
    (tmp_path / "file").write_text("x", encoding="utf-8")
    (tmp_path / "full").mkdir()
    (tmp_path / "full" / "foreign.txt").write_text("not AIDO's", encoding="utf-8")
    path = {
        "relative": "dir",
        "dotdot": str(tmp_path / "dir" / ".." / "dir"),
        "missing": str(tmp_path / "absent"),
        "file": str(tmp_path / "file"),
        "non-empty": str(tmp_path / "full"),
    }[case]
    with pytest.raises(ContainmentError):
        AidoStateRoot.create(path)
    assert (tmp_path / "full" / "foreign.txt").read_text(encoding="utf-8") == "not AIDO's"


def test_a_state_root_inside_a_git_working_tree_is_refused(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "state").mkdir()
    with pytest.raises(ContainmentError, match="Git working tree"):
        AidoStateRoot.create(repo / "state")


def test_a_state_root_holding_foreign_entries_is_not_adopted(world: World) -> None:
    foreign = world.state_dir / "foreign.txt"
    foreign.write_text("someone else's", encoding="utf-8")
    world.session.close()
    with pytest.raises(ContainmentError):
        AidoStateRoot.open(world.state_dir)
    with pytest.raises(ContainmentError):
        open_authority_session(world.root, approval_verifier=HmacHumanVerifier())
    assert foreign.read_text(encoding="utf-8") == "someone else's"
    foreign.unlink()
    world.reopen()


def test_overlapping_state_root_and_workspace_are_refused(world: World, tmp_path: Path) -> None:
    outer = tmp_path / "outer"
    (outer / "inner-state").mkdir(parents=True)
    nested_root = AidoStateRoot.create(outer / "inner-state")
    candidates = [
        (world.root, world.state_dir),                                   # the root itself
        (world.root, Path(world.root.contained_directory(("evidence",)))),  # inside it
        (nested_root, outer),                                            # around it
    ]
    if os.name == "nt":
        candidates.append((world.root, Path(str(world.state_dir).upper())))  # respelled
    for root, workspace in candidates:
        with pytest.raises(ContainmentError):
            root.authorize_target_workspace(workspace)
    with pytest.raises(ContainmentError):
        world.store.request_plan_activation(execution_plan=world.plan,
                                            execution_policy=world.policy,
                                            target_workspace=world.state_dir)


@pytest.mark.skipif(os.name != "nt", reason="junctions are a Windows reparse point")
def test_a_junction_is_refused_wherever_it_appears(world: World, tmp_path: Path) -> None:
    import _winapi

    link = tmp_path / "workspace-link"
    _winapi.CreateJunction(str(world.workspace), str(link))
    try:
        with pytest.raises(ContainmentError, match="reparse point"):
            world.root.authorize_target_workspace(link)
        with pytest.raises(ContainmentError):
            world.root.authorize_target_workspace(link)  # nothing was cached
    finally:
        os.rmdir(link)
    # The verification evidence directory swapped for a junction into the workspace.
    driver = _at_verifying(world)
    ticket = driver.ticket("step-a", "verifier")
    evidence_dir = Path(world.root.contained_directory(("evidence", "verification")))
    evidence_dir.rmdir()
    _winapi.CreateJunction(str(world.workspace), str(evidence_dir))
    try:
        with pytest.raises(ContainmentError):
            world.recorder.record(ticket, evidence_bytes("verified", "j"))
    finally:
        os.rmdir(evidence_dir)
        evidence_dir.mkdir()
    assert tree(world.workspace) == [("README.md", b"synthetic target\n")]


def test_a_replaced_target_workspace_is_refused(world: World, tmp_path: Path) -> None:
    assert world.store.authorized_target_workspace(world.project.project_run_id).path
    world.workspace.rename(tmp_path / "moved-away")
    world.workspace.mkdir()
    with pytest.raises(ContainmentError, match="no longer the directory"):
        world.store.authorized_target_workspace(world.project.project_run_id)
    with pytest.raises(ContainmentError):
        world.store.create_project_run(project_contract_sha256=world.pc.sha256,
                                       execution_plan_sha256=world.plan.sha256)


def test_the_target_workspace_is_never_written_or_cleaned(tmp_path: Path, monkeypatch) -> None:
    removed: list[str] = []
    real_unlink, real_rmdir = os.unlink, os.rmdir

    def recording_unlink(path, *args, **kwargs):
        removed.append(os.fspath(path))
        return real_unlink(path, *args, **kwargs)

    def recording_rmdir(path, *args, **kwargs):
        removed.append(os.fspath(path))
        return real_rmdir(path, *args, **kwargs)

    world = World(tmp_path)
    before = tree(world.workspace)
    monkeypatch.setattr(os, "unlink", recording_unlink)
    monkeypatch.setattr(os, "remove", recording_unlink)
    monkeypatch.setattr(os, "rmdir", recording_rmdir)
    outcome = world.outer(Ports(world))
    assert outcome.stop.value == "plan_work_complete_integration_gate_unavailable"
    monkeypatch.undo()
    world.session.close()
    assert tree(world.workspace) == before
    staging = os.path.normcase(world.root.contained_directory(("staging",)))
    assert removed and all(os.path.normcase(os.path.dirname(p)) == staging for p in removed)
    assert os.listdir(staging) == []


def test_a_failed_publish_records_nothing_and_removes_only_its_own_file(
        world: World, monkeypatch) -> None:
    driver = _at_verifying(world)
    ticket = driver.ticket("step-a", "verifier")

    def failing_link(src, dst, *args, **kwargs):
        raise OSError("simulated publish failure")

    monkeypatch.setattr(containment.os, "link", failing_link)
    with pytest.raises(OSError, match="simulated publish failure"):
        world.recorder.record(ticket, evidence_bytes("verified", "p"))
    monkeypatch.undo()
    assert os.listdir(world.root.contained_directory(("staging",))) == []
    assert os.listdir(world.root.contained_directory(("evidence", "verification"))) == []
    assert count(world.store, "verification_evidence") == 0
    # Nothing was consumed: the same dispatch can still record and be answered.
    receipt = world.recorder.record(ticket, evidence_bytes("verified", "p"))
    driver.bound("step-a", StepEvent.VERIFICATION_OBSERVED, "verification", bind_role_output(
        ticket, VerificationObservation(step_contract_sha256=ticket.step_contract_sha256,
                                        attempt=1, outcome=receipt.outcome,
                                        evidence_sha256=receipt.evidence_sha256)))


def test_a_substituted_staging_file_is_never_removed(world: World, monkeypatch) -> None:
    driver = _at_verifying(world)
    ticket = driver.ticket("step-a", "verifier")
    real_link = os.link

    def substituting_link(src, dst, *args, **kwargs):
        os.replace(src, src + ".aside")
        Path(src).write_bytes(b"someone else's file")
        raise OSError("simulated failure after substitution")

    monkeypatch.setattr(containment.os, "link", substituting_link)
    with pytest.raises(ContainmentError, match="left in place"):
        world.recorder.record(ticket, evidence_bytes("verified", "s"))
    monkeypatch.setattr(containment.os, "link", real_link)
    staged = sorted(os.listdir(world.root.contained_directory(("staging",))))
    assert len(staged) == 2
    survivor = Path(world.root.contained_directory(("staging",)), staged[0])
    assert survivor.read_bytes() == b"someone else's file"
    assert count(world.store, "verification_evidence") == 0


def test_a_database_failure_after_publishing_leaves_only_an_unreferenced_blob(
        world: World) -> None:
    driver = _at_verifying(world)
    ticket = driver.ticket("step-a", "verifier")
    data = evidence_bytes("verified", "db")
    world.clock.fail = True
    with pytest.raises(RuntimeError):
        world.recorder.record(ticket, data)
    world.clock.fail = False
    assert count(world.store, "verification_evidence") == 0
    sha = hashlib.sha256(data).hexdigest()
    assert os.listdir(world.root.contained_directory(("evidence", "verification"))) == [
        f"{sha}.json"]
    with refused():
        driver.bound("step-a", StepEvent.VERIFICATION_OBSERVED, "verification", bind_role_output(
            ticket, VerificationObservation(step_contract_sha256=ticket.step_contract_sha256,
                                            attempt=1, outcome="verified", evidence_sha256=sha)))
    # The orphan is harmless and identical bytes may be recorded properly.
    assert world.recorder.record(ticket, data).evidence_sha256 == sha


def test_a_failed_transition_consumes_no_authority(world: World) -> None:
    driver = Driver(world)
    driver.to_executing("step-a")
    envelope = driver.implementation("step-a")
    world.clock.fail = True
    with pytest.raises(RuntimeError):
        driver.bound("step-a", StepEvent.IMPLEMENTATION_RETURNED, "implementation", envelope)
    world.clock.fail = False
    assert driver.step("step-a").state is StepState.EXECUTING
    assert count(world.store, "dispatch_tickets", "consumed_request_id IS NULL") == 1
    driver.bound("step-a", StepEvent.IMPLEMENTATION_RETURNED, "implementation", envelope)
    assert driver.step("step-a").state is StepState.VERIFYING


def test_an_existing_evidence_name_is_never_overwritten(world: World) -> None:
    driver = _at_verifying(world)
    ticket = driver.ticket("step-a", "verifier")
    data = evidence_bytes("verified", "o")
    sha = hashlib.sha256(data).hexdigest()
    planted = Path(world.root.contained_directory(("evidence", "verification")), f"{sha}.json")
    planted.write_bytes(b"planted first")
    with pytest.raises(ContainmentError, match="never overwritten"):
        world.recorder.record(ticket, data)
    assert planted.read_bytes() == b"planted first"
    assert count(world.store, "verification_evidence") == 0


# --- 10. static boundaries ------------------------------------------------------------

_PACKAGE = Path(cp.__file__).resolve().parent
_DL4A_MODULES = ("authority.py", "containment.py", "authority_session.py")


def test_dl4a_modules_have_no_execution_network_or_environment_surface() -> None:
    forbidden_names = {"subprocess", "socket", "httpx", "Popen", "rmtree", "max_tokens"}
    forbidden_os = {"environ", "getenv", "putenv", "system", "popen", "startfile", "remove",
                    "removedirs", "rename", "renames", "replace", "rmdir", "chmod", "truncate"}
    for name in _DL4A_MODULES + ("store.py", "inner_loop.py"):
        tree_ = ast.parse((_PACKAGE / name).read_text(encoding="utf-8"))
        names = {n.id for n in ast.walk(tree_) if isinstance(n, ast.Name)}
        names |= {n.attr for n in ast.walk(tree_) if isinstance(n, ast.Attribute)}
        os_attrs = {
            n.attr for n in ast.walk(tree_)
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "os"
        }
        assert not names & forbidden_names, (name, names & forbidden_names)
        assert not os_attrs & forbidden_os, (name, os_attrs & forbidden_os)


def test_the_only_file_removal_is_aidos_own_staging_cleanup() -> None:
    for name in _DL4A_MODULES + ("store.py",):
        tree_ = ast.parse((_PACKAGE / name).read_text(encoding="utf-8"))
        for function in ast.walk(tree_):
            if not isinstance(function, ast.FunctionDef):
                continue
            calls = {n.attr for n in ast.walk(function) if isinstance(n, ast.Attribute)}
            if "unlink" in calls:
                assert (name, function.name) == ("containment.py", "_remove_own_staged_file")


def test_no_cli_command_reaches_dl4a() -> None:
    cli = (_PACKAGE.parent / "cli.py").read_text(encoding="utf-8")
    for term in ("authority_session", "AidoStateRoot", "control_plane.containment",
                 "control_plane", "open_authority_session"):
        assert term not in cli


def test_the_frozen_dl1_models_are_unchanged_by_dl4a() -> None:
    from ai_dev_orchestrator.control_plane import models

    assert set(VerificationObservation.model_fields) == {
        "step_contract_sha256", "attempt", "outcome", "evidence_sha256"}
    assert set(HumanStepAcceptance.model_fields) == {
        "step_contract_sha256", "attempt", "approved_by", "approved_at", "approval_text",
        "source"}
    assert models.STEP_CONTRACT_SCHEMA_VERSION == "step-contract.v1"
    assert models.PROJECT_CONTRACT_SCHEMA_VERSION == "project-contract.v1"


# --- 11. second adversarial review: regressions ---------------------------------------


def test_enforcement_lives_in_the_store_not_in_the_loop(world: World) -> None:
    """A store object that claims to be offline still refuses unbound outputs."""

    class Disguised(ControlPlaneStore):
        @property
        def authority_mode(self) -> bool:
            return False

    world.store.__class__ = Disguised
    try:
        ports = Ports(world)
        ports.override["implementer"] = lambda contract, attempt, dispatch: (
            ImplementationReport(step_contract_sha256=contract.sha256, attempt=attempt,
                                 summary="unbound"))
        outcome = inner(world, ports)
        assert outcome.step_run.state is StepState.RECOVERY_REQUIRED
        assert outcome.refusal_code is RefusalCode.AUTHORITY_UNPROVEN
        assert count(world.store, "transitions", "event = 'implementation_returned'") == 0
    finally:
        world.store.__class__ = ControlPlaneStore


def test_role_output_origin_is_bound_not_authenticated(human_world: World) -> None:
    """Pinned residual (doc §5, R-3): a caller holding the store can mint a
    planner ticket and answer it itself. Binding holds; origin is not proven.
    The human-approved policy is the backstop: COMPLETE still needs a human."""
    world = human_world
    driver = Driver(world)
    driver.to_acceptance("step-a")
    forged_planner = driver.decision("step-a", ACCEPT)  # minted by the caller, not a planner
    with refused(RefusalCode.HUMAN_ACCEPTANCE_MISSING):
        driver.bound("step-a", StepEvent.DECIDE_ACCEPTANCE, "planner_decision", forged_planner)
    assert driver.step("step-a").state is StepState.ACCEPTANCE


def test_aido_writes_nothing_outside_its_state_root(tmp_path: Path) -> None:
    world = World(tmp_path)
    outside_before = {p for p in tmp_path.rglob("*")
                      if world.state_dir not in p.parents and p != world.state_dir}
    contents_before = tree(world.workspace)
    world.outer(Ports(world))
    world.reopen()
    world.store.recover(world.project.project_run_id)
    world.session.close()
    outside_after = {p for p in tmp_path.rglob("*")
                     if world.state_dir not in p.parents and p != world.state_dir}
    assert outside_after == outside_before
    assert tree(world.workspace) == contents_before


def test_a_planner_is_never_asked_twice_for_one_version_even_after_a_crash(
        tmp_path: Path) -> None:
    """DL-2 §7 noted the Planner could be asked again at ACCEPTANCE after a
    crash. In an authority store the persisted ticket forbids it."""
    world = World(tmp_path, review=False)
    driver = Driver(world)
    driver.to_acceptance("step-a")
    driver.ticket("step-a", "planner")  # dispatched, then the process "crashed"
    store = world.reopen()
    store.recover(world.project.project_run_id)
    ports = Ports(world)
    outcome = StepInnerLoop(store, ports.role_ports()).run(
        project_run=world.project, step_run=world.step("step-a"), project_contract=world.pc,
        execution_plan=world.plan, step_contract=world.contract_a)
    assert ports.calls == []
    assert outcome.cause == "dispatch_ticket_refused"
    assert outcome.step_run.state is StepState.HUMAN_REQUIRED
    world.session.close()
