"""DL-4B S2 — the integration authority store (store.v4), offline.

Every state root and clone is a real directory under pytest ``tmp_path``; the
identity boundary, the approver registry and every security fact come from
S0's and S1's synthetic Windows worlds (synthetic SIDs and descriptors), with
the boundary's ``state_root`` and ``clone`` pointed at those real directories.
Human approvals are signed by S1's **test-only** software Ed25519 keys, which
emulate an ``sk-ssh-ed25519`` authenticator. No test creates an account,
changes an ACL, runs a subprocess, opens a socket, touches a real authenticator
or writes inside a clone.

Sections: harness; schema and version separation; the session and its
boundary; re-proof at every consumption boundary; forged proofs and verifier
records; human approval (FD-5, single use); plan activation v2; revocation and
FD-4; the tamper matrix; claims, recorders and role outputs; crash and
recovery; static boundaries.
"""

from __future__ import annotations

import ast
import copy
import inspect
import ntpath
import os
import pickle
import sqlite3
import sys
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path

import pytest
from test_dl4b_s0_identity_boundary import (
    A,
    ADMIN_FULL,
    O,
    OICI,
    OWNER_RIGHTS,
    RX,
    USERS,
    X,
    World,
    allow,
)
from test_dl4b_s1_attestation_verifier import (
    ALICE,
    ALICE_NEW,
    BOB,
    NOW,
    Clock,
    RegWorld,
    attestation,
    entry,
    reg_world,
)

import ai_dev_orchestrator.integration as integration
from ai_dev_orchestrator.control_plane import (
    AidoStateRoot,
    AuthorityRefusedError,
    ControlPlaneStore,
    ExecutionPlan,
    ExecutionPolicy,
    HumanAttestation,
    ImplementationReport,
    PlannedStep,
    PlannerDecision,
    ProjectContract,
    ProjectContractApproval,
    ProjectContractContent,
    ProjectEvent,
    ProjectOuterLoop,
    ProjectState,
    ProjectTransitionRequest,
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
    TransitionRefused,
    VerificationObservation,
    bind_role_output,
    new_request_id,
    open_authority_session,
)
from ai_dev_orchestrator.control_plane import integration_records as records
from ai_dev_orchestrator.control_plane.attestation_v2 import (
    ApprovalChallengeV2,
    ApprovalSubjectKindV2 as K,
    HumanAttestationV2,
)
from ai_dev_orchestrator.control_plane.authority import APPROVAL_CHALLENGE_TTL
from ai_dev_orchestrator.control_plane.authority_session import (
    _RECORDER_TOKEN,
    VerificationEvidenceRecorder,
)
from ai_dev_orchestrator.control_plane.integration_records import (
    ALPHA_EXECUTION_POLICY,
    WriteScopeV1,
    plan_activation_subject_v2_sha256,
    write_scopes_sha256,
)
from ai_dev_orchestrator.control_plane.models import (
    REQUIRED_PROJECT_CONTRACT_APPROVAL_TEXT,
)
from ai_dev_orchestrator.control_plane.store import STORE_AUTHORITY_SCHEMA_VERSION, STORE_SCHEMA_VERSION
from ai_dev_orchestrator.integration import integration_session as session_module
from ai_dev_orchestrator.integration import integration_store as store_module
from ai_dev_orchestrator.integration.attestation_verifier import (
    AttestationRefusal as R,
    HumanAttestationRefusedError,
    RegistryHumanAttestationVerifier,
)
from ai_dev_orchestrator.integration.identity_boundary import prove_identity_boundary_from_facts
from ai_dev_orchestrator.integration.integration_session import (
    IntegrationSession,
    open_integration_session,
    open_integration_session_from_facts,
)
from ai_dev_orchestrator.integration.integration_store import (
    LATER_SLICE_TABLES,
    STORE_INTEGRATION_SCHEMA_VERSION,
    IntegrationStore,
    IsolationUnprovenError,
)
from ai_dev_orchestrator.integration.security_descriptor import (
    ADMINISTRATORS,
    FILE_ADD_FILE,
    FILE_ALL_ACCESS,
    READ_CONTROL,
)

WINDOWS = sys.platform == "win32"
needs_windows_paths = pytest.mark.skipif(
    not WINDOWS, reason="binds real tmp_path directories to a synthetic Windows identity boundary"
)

INVARIANT = "No network access from the control plane."
STEP = "step-a"
APPROVER = "alice"


class SimulatedCrash(BaseException):
    """A kill at one instruction: not an Exception, so nothing may catch it as a refusal."""


# =============================================================================
# harness
# =============================================================================


def _put_ancestors(w: World, path: str) -> None:
    """Admin-created, protected directories from the volume root down to
    ``path``'s parent, as provisioning requires (S0 §8 item 4)."""
    drive = path[:3]
    if ntpath.normcase(drive) not in w.nodes:
        w.put(drive, is_dir=True, owner=ADMINISTRATORS, protected=True, aces=[*ADMIN_FULL, allow(USERS, RX, OICI)])
    current = drive
    for part in path[3:].split("\\")[:-1]:
        current = ntpath.join(current, part)
        if ntpath.normcase(current) not in w.nodes:
            w.put(current, is_dir=True, owner=ADMINISTRATORS, protected=True,
                  aces=[*ADMIN_FULL, allow(USERS, RX, OICI)])


def bound_world(state_root: str, clone: str) -> RegWorld:
    """S1's provisioned world, with the boundary's state root and clone moved
    to two real directories, each provisioned exactly as S0's good world."""
    w = reg_world()
    for path in (state_root, clone):
        _put_ancestors(w, path)
    w.put(state_root, is_dir=True, owner=A, protected=True, aces=[allow(A, FILE_ALL_ACCESS, OICI), *ADMIN_FULL])
    w.put_child(state_root, "aido-state-root.json", is_dir=False)
    w.put_child(state_root, "control-plane.sqlite3", is_dir=False)
    from ai_dev_orchestrator.integration.security_descriptor import (
        FILE_ADD_SUBDIRECTORY,
        FILE_WRITE_ATTRIBUTES,
        FILE_WRITE_EA,
    )

    w.put(clone, is_dir=True, owner=X, protected=True, aces=[
        allow(OWNER_RIGHTS, READ_CONTROL, OICI),
        allow(X, RX | FILE_ADD_FILE | FILE_ADD_SUBDIRECTORY | FILE_WRITE_EA | FILE_WRITE_ATTRIBUTES),
        allow(X, 0x0013_01BF, 0x08 | OICI),
        allow(A, RX, OICI), allow(O, RX, OICI), *ADMIN_FULL,
    ])
    git = clone + "\\.git"
    w.put(git, is_dir=True, owner=X, protected=True, aces=[
        allow(OWNER_RIGHTS, READ_CONTROL, OICI), allow(X, RX, OICI),
        allow(A, RX, OICI), allow(O, RX, OICI), *ADMIN_FULL,
    ])
    for name in ("HEAD", "config", "index"):
        w.put_child(git, name, is_dir=False)
    w.boundary["paths"]["state_root"] = state_root
    w.boundary["paths"]["clone"] = clone
    return w


@dataclass
class Harness:
    tmp: Path
    world: RegWorld
    clock: Clock
    root: AidoStateRoot
    clone: str
    session: IntegrationSession | None = None

    @property
    def store(self) -> IntegrationStore:
        return self.session.store

    def open(self) -> IntegrationStore:
        self.session = open_integration_session_from_facts(self.root, self.world, clock=self.clock)
        return self.store

    def reopen(self) -> IntegrationStore:
        if self.session is not None:
            self.session.close()
        return self.open()

    def close(self) -> None:
        if self.session is not None:
            self.session.close()
            self.session = None

    def sign(self, challenge: ApprovalChallengeV2, *, private=ALICE, approver: str = APPROVER,
             root: str | None = None, attested_at=None, **options) -> HumanAttestationV2:
        return attestation(challenge, private=private, approver=approver,
                           attested_at=attested_at or challenge.issued_at,
                           root=root or self.root.root_id, **options)


def make_harness(tmp_path: Path) -> Harness:
    state_dir = tmp_path / "state"
    clone_dir = tmp_path / "clone"
    state_dir.mkdir()
    clone_dir.mkdir()
    (clone_dir / "greeting.py").write_text("print('hi')\n", encoding="utf-8")
    # S3: activation records A's own Git-free observation of the clone's .git
    # (detached HEAD at the scope's base_head_oid), so the clone has one.
    git_dir = clone_dir / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_bytes(("ab" * 20 + "\n").encode("ascii"))
    (git_dir / "config").write_bytes(b"[core]\n")
    (git_dir / "index").write_bytes(b"DIRC")
    root = AidoStateRoot.create(state_dir)
    clone = os.path.realpath(clone_dir)
    return Harness(tmp_path, bound_world(root.path, clone), Clock(NOW), root, clone)


@pytest.fixture
def h(tmp_path: Path):
    if not WINDOWS:
        pytest.skip("binds real tmp_path directories to a synthetic Windows identity boundary")
    harness = make_harness(tmp_path)
    harness.open()
    yield harness
    harness.close()


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


def contract_for(content: ProjectContractContent, att: HumanAttestationV2, **overrides) -> ProjectContract:
    return ProjectContract(content=content, approval=ProjectContractApproval(**{
        "approved_by": att.approver_id,
        "approved_at": att.attested_at,
        "approval_text": REQUIRED_PROJECT_CONTRACT_APPROVAL_TEXT,
        "source": "manual",
        "contract_sha256": content.sha256,
        **overrides,
    }))


ONE_STEP = (PlannedStep(step_id=STEP, objective="Write the helper."),)
TWO_STEPS = ONE_STEP + (PlannedStep(step_id="step-b", objective="Document it.", depends_on=(STEP,)),)


def make_plan(pc: ProjectContract, *, steps=ONE_STEP, version: int = 1, supersedes=None) -> ExecutionPlan:
    return ExecutionPlan(schema_version="execution-plan.v1", project_id=pc.project_id,
                         project_contract_sha256=pc.sha256, plan_version=version,
                         supersedes_sha256=supersedes, steps=steps)


def make_scope(**changes) -> WriteScopeV1:
    values = dict(schema_version="write-scope.v1", step_id=STEP, path="src/greeting.py", change_type="modify",
                  pre_image_sha256="11" * 32, base_head_oid="ab" * 20, project_config_sha256="cf" * 32)
    values.update(changes)
    return WriteScopeV1(**values)


def make_policy(review=True, human=True, attempts=1) -> ExecutionPolicy:
    return ExecutionPolicy(schema_version="execution-policy.v1", review_required=review,
                           human_acceptance_required=human, max_attempts=attempts)


def make_proposal(step_id: str = STEP) -> StepContractProposal:
    return StepContractProposal(step_id=step_id, requirements=("Return 'hello'.",),
                                protected_invariants=(INVARIANT,))


def approve_contract(h: Harness, content: ProjectContractContent | None = None) -> ProjectContract:
    content = content or make_content()
    challenge = h.store.request_project_contract_approval(content)
    att = h.sign(challenge)
    pc = contract_for(content, att)
    assert h.store.record_approved_project_contract(pc, att) == pc.sha256
    return pc


def activate(h: Harness, pc: ProjectContract, plan: ExecutionPlan | None = None, *, policy=None,
             scopes=None) -> tuple[ExecutionPlan, HumanAttestationV2]:
    plan = plan or make_plan(pc)
    policy = policy or make_policy()
    scopes = scopes if scopes is not None else (make_scope(),)
    challenge = h.store.request_plan_activation(execution_plan=plan, execution_policy=policy,
                                                write_scopes=scopes)
    att = h.sign(challenge)
    h.store.issue_execution_plan(plan, execution_policy=policy, write_scopes=scopes, attestation=att)
    return plan, att


@dataclass
class Chain:
    pc: ProjectContract
    plan: ExecutionPlan
    contract: object
    project: object
    step: object


def full_chain(h: Harness) -> Chain:
    pc = approve_contract(h)
    plan, _ = activate(h, pc)
    contract = h.store.issue_authorized_step_contract(make_proposal(), execution_plan_sha256=plan.sha256)
    project = h.store.create_project_run(project_contract_sha256=pc.sha256, execution_plan_sha256=plan.sha256)
    step = h.store.create_step_run(project_run_id=project.project_run_id, step_contract_sha256=contract.sha256)
    return Chain(pc, plan, contract, project, step)


def snapshot(store: ControlPlaneStore) -> dict[str, list[tuple]]:
    conn = store._conn
    tables = [row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {t: [tuple(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY rowid")] for t in tables}


def tamper(h: Harness, sql: str, params: tuple = ()) -> None:
    """Rewrite the closed store directly, as an actor holding the file would."""
    h.close()
    connection = sqlite3.connect(h.root.store_path)
    connection.execute("PRAGMA ignore_check_constraints = ON")
    connection.execute("PRAGMA foreign_keys = OFF")
    if sql in LATER_SLICE_TABLES:
        _fill_row(connection, sql)
    else:
        connection.execute(sql, params)
    connection.commit()
    connection.close()


def step_request(step, event: StepEvent, **payload) -> StepTransitionRequest:
    return StepTransitionRequest(request_id=new_request_id(), expected_state_version=step.state_version,
                                 event=event, **payload)


def advance_to_executing(h: Harness, chain: Chain):
    store = h.store
    step = store.get_step_run(chain.step.step_run_id)
    store.apply_step_transition(step.step_run_id, step_request(step, StepEvent.MARK_READY))
    step = store.get_step_run(step.step_run_id)
    store.apply_step_transition(step.step_run_id, step_request(step, StepEvent.BEGIN_ATTEMPT))
    return store.get_step_run(step.step_run_id)


def rename_execution_account(h: Harness) -> None:
    """A re-provisioned boundary: still valid, but a different document."""
    h.world.boundary["execution"]["account"] = "HOST\\aido-x2"
    h.world.principals[X] = replace(h.world.principals[X], account_name="HOST\\aido-x2")


def break_boundary(h: Harness) -> None:
    """X gains write on the state root: the boundary no longer holds."""
    h.world.node(h.root.path).aces.append(allow(X, FILE_ADD_FILE))


def refused_isolation(call, *args, category: str | None = None, **kwargs) -> IsolationUnprovenError:
    with pytest.raises(IsolationUnprovenError) as info:
        call(*args, **kwargs)
    assert str(info.value).startswith("authority_unproven: isolation_unproven:"), str(info.value)
    assert info.value.code is RefusalCode.AUTHORITY_UNPROVEN
    if category is not None:
        assert info.value.category == category, str(info.value)
    return info.value


def refused_attestation(category: R, call, *args, **kwargs) -> HumanAttestationRefusedError:
    with pytest.raises(HumanAttestationRefusedError) as info:
        call(*args, **kwargs)
    assert info.value.category is category, str(info.value)
    return info.value


# =============================================================================
# 1. schema and version separation
# =============================================================================


@needs_windows_paths
def test_a_new_integration_store_has_the_v4_schema_and_is_bound(h: Harness) -> None:
    conn = h.store._conn
    meta = dict(conn.execute("SELECT key, value FROM store_meta").fetchall())
    assert meta == {"schema_version": STORE_INTEGRATION_SCHEMA_VERSION, "state_root_id": h.root.root_id,
                    "authority_origin": "injected"}
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")}
    assert tables == store_module._V4_TABLES
    assert {"execution_handoffs", "execution_claims", "authority_observations", "write_intents",
            "exact_diff_approvals", "write_evidence", "verification_evidence_v2", "review_evidence",
            "write_scopes", "plan_activations", "approval_challenges_v2"} <= tables
    # No table of v3's evidence semantics exists in v4.
    assert not tables & {"verification_evidence", "plan_issuances", "approval_challenges"}
    assert h.store.authority_mode is True and h.session.is_production is False


@needs_windows_paths
def test_an_integration_store_reopens_and_keeps_its_state(h: Harness) -> None:
    chain = full_chain(h)
    before = snapshot(h.store)
    store = h.reopen()
    assert snapshot(store) == before
    report = store.recover(chain.project.project_run_id)
    assert report.integrity_ok, report.integrity_issues
    assert store.get_step_run(chain.step.step_run_id).state is StepState.PLANNED


@needs_windows_paths
def test_v2_v3_and_v4_stores_never_open_each_other(h: Harness, tmp_path: Path) -> None:
    h.close()
    # A v4 file through the v2 and v3 entry points.
    with pytest.raises(StateUntrustedError):
        ControlPlaneStore.open(h.root.store_path)
    with pytest.raises(StateUntrustedError):
        open_authority_session(h.root)
    # A v3 file through the v4 entry point.
    v3_dir = tmp_path / "v3"
    v3_dir.mkdir()
    v3_root = AidoStateRoot.create(v3_dir)
    open_authority_session(v3_root).close()
    v3_world = bound_world(v3_root.path, h.clone)
    with pytest.raises(StateUntrustedError):
        open_integration_session_from_facts(v3_root, v3_world, clock=h.clock)
    # A v2 file placed at a v4 state root's store path.
    v2_dir = tmp_path / "v2"
    v2_dir.mkdir()
    v2_root = AidoStateRoot.create(v2_dir)
    ControlPlaneStore.open(v2_root.store_path).close()
    with pytest.raises(StateUntrustedError):
        open_integration_session_from_facts(v2_root, bound_world(v2_root.path, h.clone), clock=h.clock)
    # And none of the files was changed by the refused opens.
    for path, version in ((v3_root.store_path, STORE_AUTHORITY_SCHEMA_VERSION),
                          (v2_root.store_path, STORE_SCHEMA_VERSION),
                          (h.root.store_path, STORE_INTEGRATION_SCHEMA_VERSION)):
        connection = sqlite3.connect(path)
        assert connection.execute(
            "SELECT value FROM store_meta WHERE key = 'schema_version'").fetchone()[0] == version
        connection.close()


def test_the_integration_store_has_no_other_way_to_open() -> None:
    with pytest.raises(StoreError):
        IntegrationStore.open("C:\\nowhere\\store.sqlite3")
    with pytest.raises(StoreError):
        IntegrationStore._open_authority(None, None)
    with pytest.raises(StoreError):
        IntegrationStore._open("C:\\nowhere\\store.sqlite3", None, None)


@needs_windows_paths
def test_a_store_of_another_origin_is_refused(h: Harness) -> None:
    tamper(h, "UPDATE store_meta SET value = 'windows' WHERE key = 'authority_origin'")
    with pytest.raises(StateUntrustedError, match="other kind of session"):
        h.open()


@needs_windows_paths
def test_another_state_roots_database_is_refused(h: Harness) -> None:
    tamper(h, "UPDATE store_meta SET value = ? WHERE key = 'state_root_id'", ("ff" * 16,))
    with pytest.raises(StateUntrustedError, match="different state root"):
        h.open()


@needs_windows_paths
def test_the_schema_refuses_relabelled_provenance_and_undeclared_kinds(h: Harness) -> None:
    conn = h.store._conn
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO execution_claims VALUES ('t', 'c', 1, 'review-packet', 'authority', 'now')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO authority_observations VALUES "
                     "('o', 't', 'm0', 'a', 'b', 'c', 'd', 0, 'execution_claim', 'now')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO approval_challenges_v2 (challenge_id, subject_kind, subject_sha256, "
                     "issued_at, expires_at) VALUES ('c', 'step_acceptance_v9', 's', 'a', 'b')")
    with pytest.raises(sqlite3.IntegrityError):  # consumed without its audit record
        conn.execute("INSERT INTO approval_challenges_v2 (challenge_id, subject_kind, subject_sha256, "
                     "issued_at, expires_at, consumed_by) VALUES ('c', 'project_contract', 's', 'a', 'b', 'x')")


# =============================================================================
# 2. the session and its boundary
# =============================================================================


def test_the_production_session_takes_nothing_but_the_state_root() -> None:
    signature = inspect.signature(open_integration_session)
    assert list(signature.parameters) == ["state_root"]
    source = inspect.getsource(open_integration_session)
    assert "prove=prove_identity_boundary," in source
    assert "verifier=RegistryHumanAttestationVerifier()," in source
    assert "clock=None" in source


def test_the_production_session_refuses_on_this_host_before_touching_the_state_root(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    root = AidoStateRoot.create(state)
    before = sorted(os.listdir(root.path))
    with pytest.raises(IsolationUnprovenError) as info:
        open_integration_session(root)
    assert str(info.value).startswith("authority_unproven: isolation_unproven:")
    if not WINDOWS:
        assert info.value.category == "platform_unsupported"
    assert sorted(os.listdir(root.path)) == before  # no store file was created


@needs_windows_paths
def test_a_library_session_is_never_production_and_says_so(h: Harness) -> None:
    assert h.session.is_production is False and h.store.is_production is False
    assert h.session.boundary_sha256 == h.store.boundary_sha256
    assert len(h.session.boundary_sha256) == 64


@needs_windows_paths
def test_the_session_exposes_no_recorder_and_cannot_be_altered(h: Harness) -> None:
    public = {name for name in dir(h.session) if not name.startswith("_")}
    assert public == {"state_root", "store", "implementer", "verifier", "reviewer", "boundary_sha256", "is_production", "close"}
    for name in public:
        value = getattr(h.session, name)
        assert "recorder" not in type(value).__name__.lower()
        assert not callable(getattr(value, "record", None)), name
    with pytest.raises(AttributeError):
        h.session.store = None
    with pytest.raises(AttributeError):
        h.session.recorder = object()
    with pytest.raises(TypeError):
        IntegrationSession(h.root, h.store)
    with pytest.raises(TypeError):
        class Sub(IntegrationSession):  # noqa: F841
            pass
    for clone in (copy.copy, copy.deepcopy, pickle.dumps):
        with pytest.raises(TypeError):
            clone(h.session)
    store_attributes = {name for name in dir(h.store)}
    assert not {name for name in store_attributes if "recorder" in name.lower()}


@needs_windows_paths
def test_no_session_opens_on_a_state_root_the_boundary_does_not_declare(tmp_path: Path) -> None:
    h = make_harness(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    other_root = AidoStateRoot.create(other)
    before = sorted(os.listdir(other_root.path))
    refused_isolation(open_integration_session_from_facts, other_root, h.world, clock=h.clock,
                      category="state_root_unbound")
    assert sorted(os.listdir(other_root.path)) == before


@needs_windows_paths
@pytest.mark.parametrize("mutate, category", [
    (lambda w, h: w.node(h.root.path).aces.append(allow(X, FILE_ADD_FILE)), "object_rights"),
    (lambda w, h: setattr(w.node(h.root.path), "owner", X), "object_owner"),
    (lambda w, h: w.env.append("AIDO_LITELLM_API_KEY"), "environment_unsafe"),
    (lambda w, h: setattr(w, "boundary_raw", b"{}"), "boundary_malformed"),
    (lambda w, h: w.node(h.clone + "\\.git").aces.append(allow(X, FILE_ADD_FILE)), "object_rights"),
])
def test_no_session_opens_without_the_complete_boundary_proof(tmp_path: Path, mutate, category) -> None:
    h = make_harness(tmp_path)
    mutate(h.world, h)
    before = sorted(os.listdir(h.root.path))
    refused_isolation(h.open, category=category)
    assert sorted(os.listdir(h.root.path)) == before  # the store was never created


@needs_windows_paths
def test_a_proof_with_the_other_origin_verifier_is_refused(tmp_path: Path) -> None:
    h = make_harness(tmp_path)
    with pytest.raises(IsolationUnprovenError) as info:
        IntegrationStore._open_integration(
            h.root, prove=partial(prove_identity_boundary_from_facts, h.world, clock=h.clock),
            verifier=RegistryHumanAttestationVerifier(), clock=h.clock)
    assert info.value.category == "origin_mismatch"


@needs_windows_paths
def test_the_boundary_is_pinned_for_the_whole_session(h: Harness) -> None:
    approve_contract(h)
    rename_execution_account(h)
    refused_isolation(h.store.get_project_contract, "00" * 32, category="boundary_digest_mismatch")


@needs_windows_paths
def test_after_activation_only_the_bound_boundary_opens_the_store(h: Harness) -> None:
    full_chain(h)
    h.close()
    rename_execution_account(h)
    refused_isolation(h.open, category="boundary_digest_mismatch")


# =============================================================================
# 3. re-proof at every consumption boundary
# =============================================================================

#: Every public store method, by how the boundary governs it.
REPROVED = {
    "get_project_contract", "get_execution_plan", "get_step_contract", "list_execution_plans",
    "create_project_run", "create_step_run", "get_project_run", "get_step_run", "list_step_runs",
    "apply_step_transition", "apply_project_transition", "recover", "issue_dispatch_ticket",
    "issue_authorized_step_contract", "request_project_contract_approval",
    "record_approved_project_contract", "request_plan_activation", "issue_execution_plan",
    "authorized_target_workspace",
    # DL-4B S3
    "request_exact_diff_approval", "record_exact_diff_approval",
}
REFUSED_ALWAYS = {"record_project_contract", "record_execution_plan", "record_step_contract",
                  "request_step_acceptance"}
NOT_AUTHORITY = {"close", "inspect_project_run", "inspect_step_run", "inspect_step_runs", "transitions_for",
                 "authority_mode", "boundary_sha256", "is_production"}


def test_every_public_store_method_is_classified() -> None:
    public = {name for name in dir(IntegrationStore) if not name.startswith("_") and name != "open"}
    assert public == REPROVED | REFUSED_ALWAYS | NOT_AUTHORITY


@needs_windows_paths
def test_every_consumption_boundary_reproves_and_changes_nothing_when_it_fails(h: Harness) -> None:
    chain = full_chain(h)
    step = advance_to_executing(h, chain)
    store = h.store
    content = make_content(goal="Another goal.")
    challenge = store.request_plan_activation(execution_plan=make_plan(chain.pc, version=2,
                                                                     supersedes=chain.plan.sha256),
                                              execution_policy=make_policy(), write_scopes=(make_scope(),))
    att = h.sign(challenge)
    calls = {
        "get_project_contract": lambda: store.get_project_contract(chain.pc.sha256),
        "get_execution_plan": lambda: store.get_execution_plan(chain.plan.sha256),
        "get_step_contract": lambda: store.get_step_contract(chain.contract.sha256),
        "list_execution_plans": lambda: store.list_execution_plans(chain.pc.sha256),
        "create_project_run": lambda: store.create_project_run(
            project_contract_sha256=chain.pc.sha256, execution_plan_sha256=chain.plan.sha256),
        "create_step_run": lambda: store.create_step_run(
            project_run_id=chain.project.project_run_id, step_contract_sha256=chain.contract.sha256),
        "get_project_run": lambda: store.get_project_run(chain.project.project_run_id),
        "get_step_run": lambda: store.get_step_run(step.step_run_id),
        "list_step_runs": lambda: store.list_step_runs(chain.project.project_run_id),
        "apply_step_transition": lambda: store.apply_step_transition(
            step.step_run_id, step_request(step, StepEvent.ESCALATE, reason="x")),
        "apply_project_transition": lambda: store.apply_project_transition(
            chain.project.project_run_id, ProjectTransitionRequest(
                request_id=new_request_id(), expected_state_version=0, event=ProjectEvent.ESCALATE,
                reason="x")),
        "recover": lambda: store.recover(chain.project.project_run_id),
        "issue_dispatch_ticket": lambda: store.issue_dispatch_ticket(
            step.step_run_id, role="implementer", expected_state_version=step.state_version),
        "issue_authorized_step_contract": lambda: store.issue_authorized_step_contract(
            make_proposal(), execution_plan_sha256=chain.plan.sha256),
        "request_project_contract_approval": lambda: store.request_project_contract_approval(content),
        "record_approved_project_contract": lambda: store.record_approved_project_contract(chain.pc, att),
        "request_plan_activation": lambda: store.request_plan_activation(
            execution_plan=chain.plan, execution_policy=make_policy(), write_scopes=(make_scope(),)),
        "issue_execution_plan": lambda: store.issue_execution_plan(
            make_plan(chain.pc, version=2, supersedes=chain.plan.sha256), execution_policy=make_policy(),
            write_scopes=(make_scope(),), attestation=att),
        "authorized_target_workspace": lambda: store.authorized_target_workspace(chain.project.project_run_id),
        # DL-4B S3
        "request_exact_diff_approval": lambda: store.request_exact_diff_approval(
            execution_plan_sha256=chain.plan.sha256, step_id=STEP, artifact_name="a.json",
            config_name="p.yaml"),
        "record_exact_diff_approval": lambda: store.record_exact_diff_approval(att),
    }
    assert set(calls) == REPROVED
    break_boundary(h)
    before = snapshot(store)
    for name, call in calls.items():
        error = refused_isolation(call, category="object_rights")
        assert snapshot(store) == before, name
        assert "state_root" in str(error), name
    # The boundary restored, everything works again and nothing was consumed.
    h.world.node(h.root.path).aces.pop()
    assert store.get_step_run(step.step_run_id).state is StepState.EXECUTING
    ticket = store.issue_dispatch_ticket(step.step_run_id, role="implementer",
                                         expected_state_version=step.state_version)
    assert ticket.role == "implementer"


@needs_windows_paths
def test_calling_a_base_class_method_unbound_cannot_skip_the_boundary(h: Harness) -> None:
    """Second-review finding: ``ControlPlaneStore.get_step_run(store, ...)``
    bypasses the subclass's public overrides. The hooks every base path goes
    through (``_transaction``, ``_project_integrity``, ``_load_contract``)
    re-prove on their own when no re-proven call is running."""
    chain = full_chain(h)
    step = advance_to_executing(h, chain)
    break_boundary(h)
    before = snapshot(h.store)
    base = ControlPlaneStore
    for call in (
        lambda: base.get_step_run(h.store, step.step_run_id),
        lambda: base.get_project_run(h.store, chain.project.project_run_id),
        lambda: base.list_step_runs(h.store, chain.project.project_run_id),
        lambda: base.get_project_contract(h.store, chain.pc.sha256),
        lambda: base.list_execution_plans(h.store, chain.pc.sha256),
        lambda: base.recover(h.store, chain.project.project_run_id),
        lambda: base.issue_dispatch_ticket(h.store, step.step_run_id, role="implementer",
                                           expected_state_version=step.state_version),
        lambda: base.apply_step_transition(h.store, step.step_run_id,
                                           step_request(step, StepEvent.ESCALATE, reason="x")),
        lambda: base.authorized_target_workspace(h.store, chain.project.project_run_id),
    ):
        refused_isolation(call, category="object_rights")
        assert snapshot(h.store) == before
    assert h.store._proven_depth == 0


@needs_windows_paths
def test_v3_authority_paths_called_unbound_fail_closed(h: Harness) -> None:
    """DL-4A's v1/v3 approval and evidence paths, reached by calling the base
    class unbound, find none of their tables in store.v4 and change nothing."""
    from ai_dev_orchestrator.control_plane import ApprovalChallenge, ApprovalSubjectKind

    chain = full_chain(h)
    step = advance_to_executing(h, chain)
    v1_challenge = ApprovalChallenge(
        schema_version="approval-challenge.v1", challenge_id="ab" * 16,
        subject_kind=ApprovalSubjectKind.PROJECT_CONTRACT, subject_sha256=chain.pc.content.sha256,
        issued_at=NOW, expires_at=NOW + APPROVAL_CHALLENGE_TTL,
        required_approval_text=REQUIRED_PROJECT_CONTRACT_APPROVAL_TEXT)
    v1_attestation = HumanAttestation(
        schema_version="human-attestation.v1", challenge_id=v1_challenge.challenge_id,
        subject_kind=ApprovalSubjectKind.PROJECT_CONTRACT, subject_sha256=chain.pc.content.sha256,
        approver_id=APPROVER, attested_at=NOW, approval_text=REQUIRED_PROJECT_CONTRACT_APPROVAL_TEXT,
        proof="typed")
    base = ControlPlaneStore
    before = snapshot(h.store)
    for call in (
        lambda: base.request_project_contract_approval(h.store, make_content(goal="x")),
        lambda: base.record_approved_project_contract(h.store, chain.pc, v1_attestation),
        lambda: base.request_plan_activation(h.store, execution_plan=chain.plan,
                                             execution_policy=make_policy(), target_workspace=h.clone),
        lambda: base.issue_execution_plan(h.store, chain.plan, execution_policy=make_policy(),
                                          target_workspace=h.clone, attestation=v1_attestation),
        lambda: base.request_step_acceptance(h.store, step.step_run_id),
        lambda: base.apply_step_transition(h.store, step.step_run_id, step_request(step, StepEvent.ESCALATE,
                                                                                   reason="x"),
                                           human_attestation=v1_attestation),
    ):
        with pytest.raises(Exception):
            call()
        assert snapshot(h.store) == before
    assert h.store._proven_depth == 0


@needs_windows_paths
def test_an_attestation_for_another_kind_of_subject_is_refused(h: Harness) -> None:
    pc = approve_contract(h)
    plan = make_plan(pc)
    activation = h.store.request_plan_activation(execution_plan=plan, execution_policy=make_policy(),
                                                 write_scopes=(make_scope(),))
    att = h.sign(activation)
    content = make_content(goal="Another goal.")
    before = snapshot(h.store)
    refused_attestation(R.STATEMENT_MISMATCH, h.store.record_approved_project_contract,
                        contract_for(content, att), att)
    contract_challenge = h.store.request_project_contract_approval(content)
    before = snapshot(h.store)
    att = h.sign(contract_challenge)
    refused_attestation(R.STATEMENT_MISMATCH, h.store.issue_execution_plan, plan,
                        execution_policy=make_policy(), write_scopes=(make_scope(),), attestation=att)
    assert snapshot(h.store) == before


@needs_windows_paths
def test_one_public_call_proves_the_boundary_once(h: Harness, monkeypatch) -> None:
    chain = full_chain(h)
    calls = []
    original = h.store._reprove_boundary

    def counting():
        calls.append(1)
        return original()

    monkeypatch.setattr(h.store, "_reprove_boundary", counting)
    h.store.get_step_run(chain.step.step_run_id)
    h.store.recover(chain.project.project_run_id)
    assert len(calls) == 2


@needs_windows_paths
def test_refused_methods_stay_refused(h: Harness) -> None:
    chain = full_chain(h)
    for call in (lambda: h.store.record_project_contract(chain.pc),
                 lambda: h.store.record_execution_plan(chain.plan),
                 lambda: h.store.record_step_contract(chain.contract),
                 lambda: h.store.request_step_acceptance(chain.step.step_run_id)):
        with pytest.raises(AuthorityRefusedError):
            call()


@needs_windows_paths
def test_the_state_root_is_reproven_with_the_boundary(h: Harness) -> None:
    approve_contract(h)
    (Path(h.root.path) / "planted.txt").write_text("x", encoding="utf-8")
    with pytest.raises(Exception, match="did not create"):
        h.store.request_project_contract_approval(make_content(goal="Another."))


# =============================================================================
# 4. forged proofs and verifier records
# =============================================================================


@needs_windows_paths
def test_a_previously_valid_proof_object_is_never_accepted_again(tmp_path: Path) -> None:
    h = make_harness(tmp_path)
    cached = prove_identity_boundary_from_facts(h.world, clock=h.clock)
    store = IntegrationStore._open_integration(
        h.root, prove=lambda **_: cached,
        verifier=RegistryHumanAttestationVerifier.from_facts(h.world, clock=h.clock), clock=h.clock)
    try:
        refused_isolation(store.request_project_contract_approval, make_content(), category="proof_invalid")
    finally:
        store.close()


@needs_windows_paths
@pytest.mark.parametrize("returned", [None, True, "proof", object()])
def test_a_prover_that_returns_no_proof_is_refused(tmp_path: Path, returned) -> None:
    h = make_harness(tmp_path)
    refused_isolation(
        IntegrationStore._open_integration, h.root, prove=lambda **_: returned,
        verifier=RegistryHumanAttestationVerifier.from_facts(h.world, clock=h.clock), clock=h.clock,
        category="proof_invalid")
    assert not os.path.exists(h.root.store_path)


@needs_windows_paths
def test_a_prover_that_raises_anything_refuses(tmp_path: Path) -> None:
    h = make_harness(tmp_path)

    def prove(**_):
        raise RuntimeError("secret detail")

    error = refused_isolation(
        IntegrationStore._open_integration, h.root, prove=prove,
        verifier=RegistryHumanAttestationVerifier.from_facts(h.world, clock=h.clock), clock=h.clock,
        category="security_fact_unavailable")
    assert "secret detail" not in str(error)


@needs_windows_paths
def test_a_proof_of_another_world_is_refused(h: Harness, tmp_path: Path) -> None:
    other = bound_world("C:\\AIDO\\elsewhere", h.clone)
    other.put("C:\\AIDO\\elsewhere", is_dir=True, owner=A, protected=True,
              aces=[allow(A, FILE_ALL_ACCESS, OICI), *ADMIN_FULL])
    h.store._authority = h.store._authority._replace(
        prove=lambda **k: prove_identity_boundary_from_facts(other, clock=h.clock, **{}))
    refused_isolation(h.store.get_project_contract, "00" * 32)


@needs_windows_paths
def test_a_recycled_or_foreign_verifier_record_is_refused(h: Harness, monkeypatch) -> None:
    content = make_content()
    challenge = h.store.request_project_contract_approval(content)
    att = h.sign(challenge)
    pc = contract_for(content, att)
    genuine = h.store._authority.verifier.verify_for_consumption(
        state_root_id=h.root.root_id, challenge=challenge, attestation=att)
    other = h.store.request_project_contract_approval(make_content(goal="Another."))
    other_record = h.store._authority.verifier.verify_for_consumption(
        state_root_id=h.root.root_id, challenge=other, attestation=h.sign(other))
    # A verifier handing back a record the store already accepted.
    h.store._accepted[id(genuine)] = genuine
    monkeypatch.setattr(RegistryHumanAttestationVerifier, "verify_for_consumption", lambda self, **k: genuine)
    before = snapshot(h.store)
    with pytest.raises(AuthorityRefusedError, match="never accepted again"):
        h.store.record_approved_project_contract(pc, att)
    assert snapshot(h.store) == before
    # A verifier handing back a valid record for a different challenge.
    monkeypatch.setattr(RegistryHumanAttestationVerifier, "verify_for_consumption",
                        lambda self, **k: other_record)
    before = snapshot(h.store)
    with pytest.raises(AuthorityRefusedError, match="not for this store"):
        h.store.record_approved_project_contract(pc, att)
    assert snapshot(h.store) == before
    # A verifier returning a truthy non-record.
    monkeypatch.setattr(RegistryHumanAttestationVerifier, "verify_for_consumption", lambda self, **k: True)
    with pytest.raises(AuthorityRefusedError, match="did not return"):
        h.store.record_approved_project_contract(pc, att)
    assert snapshot(h.store) == before


@needs_windows_paths
def test_a_verifier_failure_is_a_refusal_without_detail(h: Harness, monkeypatch) -> None:
    content = make_content()
    challenge = h.store.request_project_contract_approval(content)
    att = h.sign(challenge)

    def boom(self, **kwargs):
        raise RuntimeError(att.proof)

    monkeypatch.setattr(RegistryHumanAttestationVerifier, "verify_for_consumption", boom)
    before = snapshot(h.store)
    with pytest.raises(AuthorityRefusedError) as info:
        h.store.record_approved_project_contract(contract_for(content, att), att)
    assert att.proof not in str(info.value) and "SSH SIGNATURE" not in str(info.value)
    assert snapshot(h.store) == before


# =============================================================================
# 5. human approval: FD-5 ordering and single use
# =============================================================================


@needs_windows_paths
def test_the_complete_chain_records_the_audited_approvals(h: Harness) -> None:
    chain = full_chain(h)
    rows = h.store._conn.execute(
        "SELECT * FROM approval_challenges_v2 WHERE consumed_by IS NOT NULL ORDER BY consumed_by").fetchall()
    assert [row["consumed_by"] for row in rows] == [f"execution_plan:{chain.plan.sha256}",
                                                     f"project_contract:{chain.pc.sha256}"]
    for row in rows:
        assert row["facts_origin"] == "injected"
        assert row["identity_boundary_sha256"] == h.session.boundary_sha256
        assert row["key_fingerprint_sha256"].startswith("SHA256:")
        assert row["authenticator_flags"] == 0x01 and row["authenticator_counter"] == 7
        assert len(row["statement_sha256"]) == len(row["signature_sha256"]) == 64
    assert chain.contract.human_acceptance_required and chain.contract.review_required
    assert chain.contract.max_attempts == 1


@needs_windows_paths
def test_an_approval_is_single_use_and_a_replay_is_a_receipt(h: Harness) -> None:
    content = make_content()
    challenge = h.store.request_project_contract_approval(content)
    att = h.sign(challenge)
    pc = contract_for(content, att)
    assert h.store.record_approved_project_contract(pc, att) == pc.sha256
    before = snapshot(h.store)
    assert h.store.record_approved_project_contract(pc, att) == pc.sha256  # receipt
    assert snapshot(h.store) == before
    # The same consumed challenge for another contract.
    other_content = make_content(goal="Another goal.")
    forged = attestation(challenge, private=ALICE, approver=APPROVER, attested_at=challenge.issued_at,
                         root=h.root.root_id)
    with pytest.raises(AuthorityRefusedError):
        h.store.record_approved_project_contract(contract_for(other_content, forged), forged)
    # A second, fresh challenge for the approved contract.
    second = h.store.request_project_contract_approval(content)
    att2 = h.sign(second)
    with pytest.raises(AuthorityRefusedError, match="already approved"):
        h.store.record_approved_project_contract(contract_for(content, att2), att2)
    assert h.store._conn.execute(
        "SELECT COUNT(*) FROM approval_challenges_v2 WHERE consumed_by IS NOT NULL").fetchone()[0] == 1


@needs_windows_paths
def test_the_store_verifies_against_its_own_challenge_and_state_root(h: Harness) -> None:
    content = make_content()
    challenge = h.store.request_project_contract_approval(content)
    before = snapshot(h.store)
    # Signed for another state root.
    att = h.sign(challenge, root="fe" * 16)
    refused_attestation(R.SIGNATURE_INVALID, h.store.record_approved_project_contract,
                        contract_for(content, att), att)
    # Signed over a caller-built challenge AIDO never issued (another id).
    fake = ApprovalChallengeV2(**{**challenge.model_dump(), "challenge_id": "bb" * 16})
    att = h.sign(fake)
    refused_attestation(R.STATEMENT_MISMATCH, h.store.record_approved_project_contract,
                        contract_for(content, att), att)
    # Signed by an unregistered key; by the right key for another approver.
    att = h.sign(challenge, private=ALICE_NEW)
    refused_attestation(R.KEY_UNKNOWN, h.store.record_approved_project_contract, contract_for(content, att), att)
    att = h.sign(challenge, private=ALICE, approver="bob")
    refused_attestation(R.KEY_UNKNOWN, h.store.record_approved_project_contract, contract_for(content, att), att)
    # Missing presence; a typed phrase in place of a signature.
    att = h.sign(challenge, flags=0x00)
    refused_attestation(R.PRESENCE_MISSING, h.store.record_approved_project_contract,
                        contract_for(content, att), att)
    att = HumanAttestationV2(**{**h.sign(challenge).model_dump(), "proof": challenge.required_approval_text})
    refused_attestation(R.PROOF_MALFORMED, h.store.record_approved_project_contract,
                        contract_for(content, att), att)
    assert snapshot(h.store) == before


@needs_windows_paths
def test_an_expired_challenge_is_refused_by_the_store(h: Harness) -> None:
    content = make_content()
    challenge = h.store.request_project_contract_approval(content)
    att = h.sign(challenge)
    h.clock.now = challenge.expires_at
    before = snapshot(h.store)
    refused_attestation(R.CHALLENGE_EXPIRED, h.store.record_approved_project_contract,
                        contract_for(content, att), att)
    assert snapshot(h.store) == before


@needs_windows_paths
def test_a_challenge_consumed_while_it_was_being_verified_is_refused(h: Harness) -> None:
    """FD-5: the in-transaction re-check sees a consumption that happened
    after the pre-check, during the (outside-the-transaction) verification."""
    content = make_content()
    challenge = h.store.request_project_contract_approval(content)
    att = h.sign(challenge)
    pc = contract_for(content, att)
    world = h.world
    original = type(world).read_file
    state = {"armed": True}

    def read_file(self, path, limit):
        if state["armed"] and path.endswith("approver-registry.v1.json"):
            state["armed"] = False
            h.store.record_approved_project_contract(pc, att)  # a concurrent consumer wins
        return original(self, path, limit)

    world.read_file = read_file.__get__(world)
    # The nested call consumed it; the outer one must not consume it again.
    with pytest.raises(AuthorityRefusedError):
        h.store.record_approved_project_contract(pc, att)
    assert h.store._conn.execute(
        "SELECT COUNT(*) FROM approval_challenges_v2 WHERE consumed_by IS NOT NULL").fetchone()[0] == 1


@needs_windows_paths
def test_a_challenge_that_expires_during_verification_is_refused(h: Harness) -> None:
    content = make_content()
    challenge = h.store.request_project_contract_approval(content)
    att = h.sign(challenge)
    world = h.world
    original = type(world).read_file

    def read_file(self, path, limit):
        if path.endswith("approver-registry.v1.json"):
            h.clock.now = challenge.expires_at - APPROVAL_CHALLENGE_TTL / 3600  # still valid for the verifier
            result = original(self, path, limit)
            h.clock.now = challenge.expires_at  # ... and expired by the time the store re-checks
            return result
        return original(self, path, limit)

    world.read_file = read_file.__get__(world)
    before = snapshot(h.store)
    refused_attestation(R.CHALLENGE_EXPIRED, h.store.record_approved_project_contract,
                        contract_for(content, att), att)
    assert snapshot(h.store) == before


@needs_windows_paths
@pytest.mark.parametrize("bad", [
    "v1", "dict", "construct", "subclass", "none",
])
def test_malformed_attestations_are_refused(h: Harness, bad) -> None:
    content = make_content()
    challenge = h.store.request_project_contract_approval(content)
    att = h.sign(challenge)
    pc = contract_for(content, att)
    if bad == "v1":
        value = HumanAttestation(**{**att.model_dump(), "schema_version": "human-attestation.v1",
                                    "subject_kind": "project_contract"})
    elif bad == "dict":
        value = att.model_dump()
    elif bad == "construct":
        value = HumanAttestationV2.model_construct(**{**att.model_dump(), "approval_text": "I approve"})
    elif bad == "subclass":
        class Sub(HumanAttestationV2):
            pass
        value = Sub(**att.model_dump())
    else:
        value = None
    before = snapshot(h.store)
    with pytest.raises(AuthorityRefusedError):
        h.store.record_approved_project_contract(pc, value)
    assert snapshot(h.store) == before


@needs_windows_paths
def test_the_approval_block_must_be_the_signed_approval(h: Harness) -> None:
    content = make_content()
    challenge = h.store.request_project_contract_approval(content)
    att = h.sign(challenge)
    before = snapshot(h.store)
    with pytest.raises(AuthorityRefusedError, match="approval block"):
        h.store.record_approved_project_contract(contract_for(content, att, approved_by="mallory"), att)
    assert snapshot(h.store) == before


# =============================================================================
# 6. plan activation v2
# =============================================================================


@needs_windows_paths
def test_the_activation_subject_binds_scope_config_and_boundary(h: Harness) -> None:
    pc = approve_contract(h)
    plan = make_plan(pc)
    scope = make_scope()
    challenge = h.store.request_plan_activation(execution_plan=plan, execution_policy=make_policy(),
                                                write_scopes=(scope,))
    workspace = h.root.authorize_target_workspace(h.clone)
    assert challenge.subject_sha256 == plan_activation_subject_v2_sha256(
        project_contract_sha256=pc.sha256, execution_plan_sha256=plan.sha256,
        execution_policy_sha256=ALPHA_EXECUTION_POLICY.sha256, target_workspace_sha256=workspace.sha256,
        write_scopes_sha256=write_scopes_sha256((scope,)), project_config_sha256=scope.project_config_sha256,
        identity_boundary_sha256=h.session.boundary_sha256)
    att = h.sign(challenge)
    before = snapshot(h.store)
    # The same signature presented with any other bound value answers another subject.
    for changed in (make_scope(path="src/other.py"), make_scope(pre_image_sha256="22" * 32),
                    make_scope(base_head_oid="cd" * 20), make_scope(project_config_sha256="ce" * 32)):
        refused_attestation(R.STATEMENT_MISMATCH, h.store.issue_execution_plan, plan,
                            execution_policy=make_policy(), write_scopes=(changed,), attestation=att)
    assert snapshot(h.store) == before
    assert h.store.issue_execution_plan(plan, execution_policy=make_policy(), write_scopes=(scope,),
                                        attestation=att) == plan.sha256
    row = h.store._conn.execute("SELECT * FROM plan_activations").fetchone()
    assert row["identity_boundary_sha256"] == h.session.boundary_sha256
    assert row["project_config_sha256"] == scope.project_config_sha256
    assert row["write_scopes_sha256"] == write_scopes_sha256((scope,))
    assert ntpath.normcase(row["target_workspace"]) == ntpath.normcase(h.clone)


@needs_windows_paths
@pytest.mark.parametrize("policy, steps, scopes, match", [
    (make_policy(review=False), ONE_STEP, (make_scope(),), "Alpha policy"),
    (make_policy(human=False), ONE_STEP, (make_scope(),), "Alpha policy"),
    (make_policy(attempts=2), ONE_STEP, (make_scope(),), "Alpha policy"),
    (make_policy(), TWO_STEPS, (make_scope(),), "one-step plan"),
    (make_policy(), ONE_STEP, (), "exactly one write scope"),
    (make_policy(), ONE_STEP, (make_scope(), make_scope(path="src/b.py")), "exactly one write scope"),
    (make_policy(), ONE_STEP, (make_scope(step_id="step-z"),), "not for the plan's step"),
])
def test_only_the_alpha_profile_is_activated(h: Harness, policy, steps, scopes, match) -> None:
    pc = approve_contract(h)
    before = snapshot(h.store)
    with pytest.raises(AuthorityRefusedError, match=match):
        h.store.request_plan_activation(execution_plan=make_plan(pc, steps=steps), execution_policy=policy,
                                        write_scopes=scopes)
    assert snapshot(h.store) == before


@needs_windows_paths
@pytest.mark.parametrize("scopes", [[make_scope()], make_scope(), ({"step_id": STEP},)])
def test_write_scopes_must_be_a_tuple_of_exact_records(h: Harness, scopes) -> None:
    pc = approve_contract(h)
    with pytest.raises(AuthorityRefusedError):
        h.store.request_plan_activation(execution_plan=make_plan(pc), execution_policy=make_policy(),
                                        write_scopes=scopes)


@pytest.mark.parametrize("path", [
    "", "/abs.py", "C:/x.py", "a\\b.py", "a//b.py", "./a.py", "a/../b.py", ".git/config", "a/.GIT/x",
    "a/b.", "a/b ", "PROGRA~1/x.py", "con.py", "nul", "a:b", "caf\u00e9.py", "x\n.py", "a/",
])
def test_a_write_scope_names_one_file_unambiguously(path) -> None:
    with pytest.raises(ValueError):
        make_scope(path=path)


@pytest.mark.parametrize("changes", [
    {"change_type": "create"}, {"pre_image_sha256": "AB" * 32}, {"base_head_oid": "ab" * 10},
    {"project_config_sha256": "x"}, {"step_id": "Step A"}, {"schema_version": "write-scope.v2"},
    {"extra": 1},
])
def test_malformed_write_scopes_are_refused(changes) -> None:
    with pytest.raises(ValueError):
        make_scope(**changes)


@needs_windows_paths
def test_an_activation_receipt_is_only_for_the_identical_activation(h: Harness) -> None:
    pc = approve_contract(h)
    plan, att = activate(h, pc)
    before = snapshot(h.store)
    assert h.store.issue_execution_plan(plan, execution_policy=make_policy(), write_scopes=(make_scope(),),
                                        attestation=att) == plan.sha256
    assert snapshot(h.store) == before
    with pytest.raises(AuthorityRefusedError, match="already activated"):
        h.store.issue_execution_plan(plan, execution_policy=make_policy(),
                                     write_scopes=(make_scope(path="src/x.py"),), attestation=att)
    assert snapshot(h.store) == before


@needs_windows_paths
def test_an_activation_authorizes_one_project_run(h: Harness) -> None:
    chain = full_chain(h)
    before = snapshot(h.store)
    with pytest.raises(AuthorityRefusedError, match="one project run"):
        h.store.create_project_run(project_contract_sha256=chain.pc.sha256,
                                   execution_plan_sha256=chain.plan.sha256)
    assert snapshot(h.store) == before


@needs_windows_paths
def test_a_replaced_clone_is_refused(h: Harness) -> None:
    chain = full_chain(h)
    os.rename(h.clone, h.clone + "-moved")
    os.mkdir(h.clone)
    with pytest.raises(Exception, match="no longer the directory a human authorized"):
        h.store.authorized_target_workspace(chain.project.project_run_id)


@needs_windows_paths
def test_the_workspace_is_the_boundary_clone_and_never_a_callers_path(h: Harness) -> None:
    params = inspect.signature(IntegrationStore.request_plan_activation).parameters
    assert "target_workspace" not in params
    assert "target_workspace" not in inspect.signature(IntegrationStore.issue_execution_plan).parameters
    chain = full_chain(h)
    identity = h.store.authorized_target_workspace(chain.project.project_run_id)
    assert ntpath.normcase(identity.path) == ntpath.normcase(h.clone)


# =============================================================================
# 7. revocation, rotation and FD-4 re-verification
# =============================================================================


def _set_alice(h: Harness, **changes) -> None:
    entries = h.world.registry["approvers"]
    entries[0] = {**entries[0], **changes}


@needs_windows_paths
@pytest.mark.parametrize("mutate", [
    lambda h: _set_alice(h, revoked=True),
    lambda h: h.world.registry["approvers"].pop(0),
    lambda h: h.world.registry["approvers"].__setitem__(0, entry(ALICE_NEW)),
    lambda h: setattr(h.world, "registry_raw", b"not json"),
    lambda h: h.world.node("C:\\ProgramData\\AIDO\\approver-registry.v1.json").aces.append(
        allow(X, FILE_ALL_ACCESS)),
])
def test_a_revoked_rotated_or_unprotected_registry_untrusts_historical_authority(h: Harness, mutate) -> None:
    chain = full_chain(h)
    run_id = chain.project.project_run_id
    mutate(h)
    with pytest.raises(StateUntrustedError):
        h.store.get_project_run(run_id)
    with pytest.raises(StateUntrustedError):
        h.store.issue_dispatch_ticket(chain.step.step_run_id, role="implementer", expected_state_version=0)
    report = h.store.recover(run_id)
    assert not report.integrity_ok and report.project_state is ProjectState.HUMAN_REQUIRED
    issues = " ".join(report.integrity_issues)
    assert "re-proves" in issues or "re-verified" in issues
    assert ALICE.private_bytes_raw().hex() not in issues  # nothing sensitive in diagnostics


@needs_windows_paths
def test_revocation_is_total_and_persists_after_unrevoking(h: Harness) -> None:
    chain = full_chain(h)
    run_id = chain.project.project_run_id
    _set_alice(h, revoked=True)
    assert not h.store.recover(run_id).integrity_ok
    _set_alice(h, revoked=False)
    store = h.reopen()
    store.recover(run_id)
    # The escalation is recorded; HUMAN_REQUIRED has no exit.
    assert store.get_project_run(run_id).state is ProjectState.HUMAN_REQUIRED
    assert store.get_step_run(chain.step.step_run_id).state is StepState.HUMAN_REQUIRED


@needs_windows_paths
def test_a_new_challenge_cannot_be_signed_by_a_revoked_key(h: Harness) -> None:
    _set_alice(h, revoked=True)
    content = make_content()
    challenge = h.store.request_project_contract_approval(content)
    att = h.sign(challenge)
    refused_attestation(R.KEY_REVOKED, h.store.record_approved_project_contract, contract_for(content, att), att)


@needs_windows_paths
def test_another_approver_still_works_after_one_is_revoked(h: Harness) -> None:
    _set_alice(h, revoked=True)
    content = make_content()
    challenge = h.store.request_project_contract_approval(content)
    att = h.sign(challenge, private=BOB, approver="bob")
    pc = contract_for(content, att)
    assert h.store.record_approved_project_contract(pc, att) == pc.sha256


# =============================================================================
# 8. the tamper matrix
# =============================================================================

TAMPERS = {
    "attestation body": "UPDATE approval_challenges_v2 SET attestation = replace(attestation, 'alice', 'alicf') "
                        "WHERE consumed_by LIKE 'project_contract:%'",
    "attestation digest": "UPDATE approval_challenges_v2 SET attestation_sha256 = ? "
                          "WHERE consumed_by LIKE 'project_contract:%'",
    "statement audit": "UPDATE approval_challenges_v2 SET statement_sha256 = ? WHERE consumed_by LIKE 'execution%'",
    "signature audit": "UPDATE approval_challenges_v2 SET signature_sha256 = ? WHERE consumed_by LIKE 'execution%'",
    "counter audit": "UPDATE approval_challenges_v2 SET authenticator_counter = 8 WHERE consumed_by LIKE 'execution%'",
    "facts origin": "UPDATE approval_challenges_v2 SET facts_origin = 'windows' WHERE consumed_by LIKE 'project%'",
    "challenge subject": "UPDATE approval_challenges_v2 SET subject_sha256 = ? WHERE consumed_by LIKE 'execution%'",
    "consumed by": "UPDATE approval_challenges_v2 SET consumed_by = 'project_contract:' || ? "
                   "WHERE consumed_by LIKE 'project_contract:%'",
    "policy": "UPDATE plan_activations SET policy = replace(policy, '\"max_attempts\":1', '\"max_attempts\":2'), "
              "policy_sha256 = ?",
    "policy digest": "UPDATE plan_activations SET policy_sha256 = ?",
    "scope body": "UPDATE write_scopes SET body = replace(body, 'src/greeting.py', 'src/other.py')",
    "scope digest": "UPDATE write_scopes SET sha256 = ?",
    "scopes digest": "UPDATE plan_activations SET write_scopes_sha256 = ?",
    "scope deleted": "DELETE FROM write_scopes",
    "config digest": "UPDATE plan_activations SET project_config_sha256 = ?",
    "workspace": "UPDATE plan_activations SET target_workspace = target_workspace || 'x'",
    "workspace digest": "UPDATE plan_activations SET target_workspace_sha256 = ?",
    "activation challenge": "UPDATE plan_activations SET challenge_id = ?",
    "step issuance policy": "UPDATE step_contract_issuances SET policy_sha256 = ?",
    "a held ticket": "INSERT INTO dispatch_tickets SELECT 'ee' || substr(ticket_id, 3), project_run_id, "
                     "step_run_id, step_contract_sha256, attempt, 'verifier', 'verifying', 99, issued_at, NULL, "
                     "'{}', ?, issued_at FROM dispatch_tickets",
    "an answered ticket": "UPDATE dispatch_tickets SET consumed_request_id = ?",
    "an exact-diff challenge": "INSERT INTO approval_challenges_v2 (challenge_id, subject_kind, subject_sha256, "
                               "issued_at, expires_at) VALUES ('cc', 'exact_diff_approval', ?, 'a', 'b')",
    **{f"a row in {table}": table for table in LATER_SLICE_TABLES},
}


def _fill_row(connection: sqlite3.Connection, table: str) -> None:
    columns = connection.execute(f"PRAGMA table_info({table})").fetchall()
    values = [1 if column[2] == "INTEGER" else "x" for column in columns]
    for index, column in enumerate(columns):
        if column[1] == "provenance":
            values[index] = ("authority_observation" if table == "authority_observations"
                             else "execution_claim")
        elif column[1] in ("kind", "shape", "state", "outcome", "verdict"):
            values[index] = {"kind": "m0", "shape": "review-packet", "state": "completed",
                             "outcome": "verified", "verdict": "approve"}[column[1]]
    connection.execute(f"INSERT INTO {table} VALUES ({', '.join('?' for _ in columns)})", values)


@needs_windows_paths
@pytest.mark.parametrize("name", list(TAMPERS))
def test_tampered_authority_records_make_the_run_untrusted(h: Harness, name) -> None:
    chain = full_chain(h)
    step = advance_to_executing(h, chain)
    h.store.issue_dispatch_ticket(step.step_run_id, role="implementer", expected_state_version=step.state_version)
    sql = TAMPERS[name]
    tamper(h, sql, ("9" * 64,) if "?" in sql else ())
    store = h.open()
    report = store.recover(chain.project.project_run_id)
    assert not report.integrity_ok, name
    assert report.project_state is ProjectState.HUMAN_REQUIRED
    # The tampered record still does not prove, so only a diagnostic read shows the escalation.
    assert store.inspect_step_run(step.step_run_id).columns["state"] == StepState.HUMAN_REQUIRED.value
    with pytest.raises(StateUntrustedError):
        store.get_step_run(step.step_run_id)


@needs_windows_paths
def test_an_untampered_store_is_trusted(h: Harness) -> None:
    chain = full_chain(h)
    step = advance_to_executing(h, chain)
    h.store.issue_dispatch_ticket(step.step_run_id, role="implementer", expected_state_version=step.state_version)
    tamper(h, "UPDATE store_meta SET value = value")
    report = h.open().recover(chain.project.project_run_id)
    assert report.integrity_ok, report.integrity_issues
    assert report.recovered_step_run_ids == (step.step_run_id,)


@needs_windows_paths
def test_tampering_the_bound_boundary_digest_keeps_the_store_closed(h: Harness) -> None:
    full_chain(h)
    tamper(h, "UPDATE plan_activations SET identity_boundary_sha256 = ?", ("9" * 64,))
    refused_isolation(h.open, category="boundary_digest_mismatch")


# =============================================================================
# 9. claims, recorders and role outputs
# =============================================================================


@needs_windows_paths
def test_no_role_output_event_is_accepted_even_with_a_genuine_dispatch(h: Harness) -> None:
    chain = full_chain(h)
    step = advance_to_executing(h, chain)
    ticket = h.store.issue_dispatch_ticket(step.step_run_id, role="implementer",
                                           expected_state_version=step.state_version)
    output = ImplementationReport(step_contract_sha256=chain.contract.sha256, attempt=1,
                                  summary="Implemented and verified.", claims=())
    before = snapshot(h.store)
    with pytest.raises(AuthorityRefusedError, match="execution claim and authority observation"):
        h.store.apply_step_transition(step.step_run_id, step_request(
            step, StepEvent.IMPLEMENTATION_RETURNED, implementation=output),
            role_output=bind_role_output(ticket, output))
    with pytest.raises(AuthorityRefusedError):
        h.store.apply_step_transition(step.step_run_id, step_request(
            step, StepEvent.IMPLEMENTATION_RETURNED, implementation=output))
    assert snapshot(h.store) == before
    assert h.store.get_step_run(step.step_run_id).state is StepState.EXECUTING


@needs_windows_paths
@pytest.mark.parametrize("event", [StepEvent.VERIFICATION_OBSERVED, StepEvent.REVIEW_OBSERVED,
                                   StepEvent.DECIDE_ACCEPTANCE])
def test_a_caller_supplied_verification_review_or_decision_is_refused(h: Harness, event) -> None:
    chain = full_chain(h)
    step = advance_to_executing(h, chain)
    payloads = {
        StepEvent.VERIFICATION_OBSERVED: {"verification": VerificationObservation(
            step_contract_sha256=chain.contract.sha256, attempt=1, outcome="verified", evidence_sha256="a" * 64)},
        StepEvent.REVIEW_OBSERVED: {"review": ReviewProposal(
            step_contract_sha256=chain.contract.sha256, attempt=1, verdict="approve",
            evidence_sha256="a" * 64)},
        StepEvent.DECIDE_ACCEPTANCE: {"planner_decision": PlannerDecision(
            step_contract_sha256=chain.contract.sha256, attempt=1,
            recommendation="RECOMMEND_STEP_ACCEPT", rationale="forged")},
    }
    before = snapshot(h.store)
    with pytest.raises(TransitionRefused):
        h.store.apply_step_transition(step.step_run_id, step_request(step, event, **payloads[event]))
    assert snapshot(h.store) == before


@needs_windows_paths
def test_a_human_attestation_is_refused_on_every_transition(h: Harness) -> None:
    chain = full_chain(h)
    content = make_content(goal="x")
    att = h.sign(h.store.request_project_contract_approval(content))
    step = h.store.get_step_run(chain.step.step_run_id)
    before = snapshot(h.store)
    with pytest.raises(AuthorityRefusedError, match="S6"):
        h.store.apply_step_transition(step.step_run_id, step_request(step, StepEvent.MARK_READY),
                                      human_attestation=att)
    assert snapshot(h.store) == before


@needs_windows_paths
def test_dl4a_verification_recorder_cannot_record_into_an_integration_store(h: Harness) -> None:
    chain = full_chain(h)
    step = advance_to_executing(h, chain)
    ticket = h.store.issue_dispatch_ticket(step.step_run_id, role="implementer",
                                           expected_state_version=step.state_version)
    recorder = VerificationEvidenceRecorder(h.store, object(), _token=_RECORDER_TOKEN)
    before = snapshot(h.store)
    with pytest.raises(AuthorityRefusedError, match="execution claim"):
        recorder.record(ticket, b'{"schema_version": "verification-result.v1"}')
    assert snapshot(h.store) == before


def test_no_public_store_or_session_api_accepts_bytes() -> None:
    for owner in (IntegrationStore, IntegrationSession):
        for name, member in inspect.getmembers(owner, callable):
            if name.startswith("_"):
                continue
            annotations = getattr(member, "__annotations__", {}) if inspect.isfunction(member) else {}
            for parameter, annotation in annotations.items():
                assert "bytes" not in str(annotation), (owner.__name__, name, parameter)
            for parameter in inspect.signature(member).parameters:
                lowered = parameter.lower()
                assert not any(word in lowered for word in ("claim", "observation", "evidence", "stdout",
                                                            "manifest", "recorder", "report", "data")), (
                    owner.__name__, name, parameter)


@needs_windows_paths
def test_the_orchestration_path_cannot_promote_a_forged_implementation(h: Harness) -> None:
    """DL-3 → DL-2 → store: a port answering its genuine ticket with a
    self-made report reaches no more-trusted state."""
    chain = full_chain(h)

    class Ports:
        def __init__(self) -> None:
            self.calls = []

        def role_ports(self):
            return RolePorts(planner=self, tester=self, implementer=self, verifier=self, reviewer=self)

        def propose_step_contract(self, **kwargs):
            return make_proposal()

        def propose_tests(self, **kwargs):
            return ()

        def implement(self, *, step_contract, attempt, dispatch=None):
            self.calls.append("implementer")
            return bind_role_output(dispatch, ImplementationReport(
                step_contract_sha256=step_contract.sha256, attempt=attempt, summary="I wrote and verified it."))

        def verify(self, **kwargs):
            self.calls.append("verifier")
            raise AssertionError("never dispatched")

        def review(self, **kwargs):
            self.calls.append("reviewer")
            raise AssertionError("never dispatched")

        def decide_step(self, **kwargs):
            self.calls.append("planner")
            raise AssertionError("never dispatched")

    ports = Ports()
    outcome = ProjectOuterLoop(h.store, ports.role_ports()).run(
        project_run=h.store.get_project_run(chain.project.project_run_id),
        project_contract=chain.pc, execution_plan=chain.plan)
    step = h.store.get_step_run(chain.step.step_run_id)
    assert ports.calls == ["implementer"]
    assert step.state is StepState.RECOVERY_REQUIRED
    events = [record.event for record in h.store.transitions_for(step.step_run_id)]
    assert StepEvent.IMPLEMENTATION_RETURNED.value not in events
    assert h.store._conn.execute(
        "SELECT COUNT(*) FROM dispatch_tickets WHERE consumed_request_id IS NOT NULL").fetchone()[0] == 0
    assert outcome is not None
    # The inner loop directly, on a second, identical-shaped attempt: impossible (one attempt).
    with pytest.raises(TransitionRefused):
        h.store.apply_step_transition(step.step_run_id, step_request(step, StepEvent.BEGIN_ATTEMPT))


# =============================================================================
# 10. crash and recovery
# =============================================================================


class CrashingConnection:
    """Delegates to the store's connection, and crashes once at one statement,
    before it runs or (``after=True``) right after it ran."""

    def __init__(self, connection: sqlite3.Connection, needle: str, *, after: bool = False,
                 skip: int = 0) -> None:
        self._connection = connection
        self._needle = needle
        self._after = after
        self._skip = skip
        self.armed = True

    def execute(self, sql: str, params: tuple = ()):
        hit = self.armed and self._needle in sql
        if hit and self._skip:
            self._skip -= 1
            hit = False
        if hit and not self._after:
            self.armed = False
            raise SimulatedCrash(self._needle)
        result = self._connection.execute(sql, params)
        if hit:
            self.armed = False
            raise SimulatedCrash(self._needle)
        return result

    def __getattr__(self, name: str):
        return getattr(self._connection, name)


def crash_at(store: IntegrationStore, needle: str, *, after: bool = False,
             skip: int = 0) -> CrashingConnection:
    proxy = CrashingConnection(store._conn, needle, after=after, skip=skip)
    store._conn = proxy
    return proxy


@needs_windows_paths
@pytest.mark.parametrize("needle", [
    "INSERT INTO contracts", "UPDATE approval_challenges_v2 SET consumed_by", "COMMIT",
])
def test_a_crash_while_recording_a_contract_approval_records_nothing(h: Harness, needle) -> None:
    content = make_content()
    challenge = h.store.request_project_contract_approval(content)
    att = h.sign(challenge)
    pc = contract_for(content, att)
    before = snapshot(h.store)
    proxy = crash_at(h.store, needle)
    with pytest.raises(SimulatedCrash):
        h.store.record_approved_project_contract(pc, att)
    assert not proxy.armed
    h.close()  # the process died: the uncommitted transaction is gone
    store = h.open()
    assert snapshot(store) == before
    # The unconsumed challenge still answers, exactly once.
    assert store.record_approved_project_contract(pc, att) == pc.sha256
    assert store._conn.execute(
        "SELECT COUNT(*) FROM approval_challenges_v2 WHERE consumed_by IS NOT NULL").fetchone()[0] == 1


@needs_windows_paths
def test_a_crash_after_the_commit_leaves_a_receipt_not_a_second_consumption(h: Harness) -> None:
    content = make_content()
    challenge = h.store.request_project_contract_approval(content)
    att = h.sign(challenge)
    pc = contract_for(content, att)
    # The pre-check transaction commits first; crash right after the second,
    # which consumed the challenge.
    crash_at(h.store, "COMMIT", after=True, skip=1)
    with pytest.raises(SimulatedCrash):
        h.store.record_approved_project_contract(pc, att)
    store = h.reopen()
    assert store._conn.execute(
        "SELECT COUNT(*) FROM approval_challenges_v2 WHERE consumed_by IS NOT NULL").fetchone()[0] == 1
    after = snapshot(store)
    assert store.record_approved_project_contract(pc, att) == pc.sha256  # receipt
    assert snapshot(store) == after


@needs_windows_paths
@pytest.mark.parametrize("needle", [
    "INSERT INTO contracts", "INSERT INTO plan_activations", "INSERT INTO write_scopes",
    "UPDATE approval_challenges_v2 SET consumed_by",
])
def test_a_crash_while_activating_records_nothing(h: Harness, needle) -> None:
    pc = approve_contract(h)
    plan = make_plan(pc)
    challenge = h.store.request_plan_activation(execution_plan=plan, execution_policy=make_policy(),
                                                write_scopes=(make_scope(),))
    att = h.sign(challenge)
    before = snapshot(h.store)
    crash_at(h.store, needle)
    with pytest.raises(SimulatedCrash):
        h.store.issue_execution_plan(plan, execution_policy=make_policy(), write_scopes=(make_scope(),),
                                     attestation=att)
    store = h.reopen()
    assert snapshot(store) == before
    assert store.issue_execution_plan(plan, execution_policy=make_policy(), write_scopes=(make_scope(),),
                                      attestation=att) == plan.sha256


@needs_windows_paths
@pytest.mark.parametrize("needle", ["INSERT INTO transitions", "UPDATE step_runs", "INSERT INTO dispatch_tickets"])
def test_a_crash_in_the_attempt_never_resumes_and_never_dispatches_twice(h: Harness, needle) -> None:
    chain = full_chain(h)
    step = h.store.get_step_run(chain.step.step_run_id)
    h.store.apply_step_transition(step.step_run_id, step_request(step, StepEvent.MARK_READY))
    step = h.store.get_step_run(step.step_run_id)
    h.store.apply_step_transition(step.step_run_id, step_request(step, StepEvent.BEGIN_ATTEMPT))
    step = h.store.get_step_run(step.step_run_id)
    if needle == "INSERT INTO dispatch_tickets":
        h.store.issue_dispatch_ticket(step.step_run_id, role="implementer", expected_state_version=step.state_version)
    crash_at(h.store, needle)
    with pytest.raises((SimulatedCrash, TransitionRefused)):
        if needle == "INSERT INTO dispatch_tickets":
            h.store.issue_dispatch_ticket(step.step_run_id, role="implementer",
                                          expected_state_version=step.state_version)
        else:
            h.store.apply_step_transition(step.step_run_id, step_request(step, StepEvent.ESCALATE, reason="x"))
    store = h.reopen()
    report = store.recover(chain.project.project_run_id)
    assert report.integrity_ok, report.integrity_issues
    step = store.get_step_run(step.step_run_id)
    assert step.state is StepState.RECOVERY_REQUIRED
    assert store.recover(chain.project.project_run_id).recovered_step_run_ids == ()  # idempotent
    with pytest.raises(TransitionRefused):
        store.issue_dispatch_ticket(step.step_run_id, role="implementer", expected_state_version=step.state_version)
    assert store._conn.execute("SELECT COUNT(*) FROM dispatch_tickets").fetchone()[0] <= 1


@needs_windows_paths
def test_nothing_in_a_reopened_store_is_consumable_before_recover(h: Harness) -> None:
    chain = full_chain(h)
    store = h.reopen()
    with pytest.raises(RecoveryRequiredError):
        store.get_step_run(chain.step.step_run_id)


# =============================================================================
# 11. static boundaries
# =============================================================================

_PACKAGE = Path(integration.__file__).resolve().parent
_S2_MODULES = ("integration_store.py", "integration_session.py")
_S2_CONTROL_PLANE = _PACKAGE.parent / "control_plane" / "integration_records.py"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
    return names


def test_s2_modules_have_no_execution_network_model_git_or_harness_surface() -> None:
    forbidden_modules = {"subprocess", "socket", "httpx", "requests", "aiohttp", "urllib", "http", "asyncio",
                         "multiprocessing", "shutil", "tempfile", "winreg", "ctypes", "os", "threading"}
    harness_prefixes = ("ai_dev_orchestrator.llm", "ai_dev_orchestrator.github", "ai_dev_orchestrator.review",
                        "ai_dev_orchestrator.verification", "ai_dev_orchestrator.file_editing",
                        "ai_dev_orchestrator.supervised_implementer", "ai_dev_orchestrator.workspace",
                        "ai_dev_orchestrator.diff_proposal", "ai_dev_orchestrator.cli",
                        "ai_dev_orchestrator.integration.windows_security")
    forbidden_names = {"Popen", "max_tokens", "environ", "getenv", "putenv", "system", "unlink", "remove",
                       "rename", "rmtree", "write_text", "write_bytes", "chmod"}
    for path in [_PACKAGE / name for name in _S2_MODULES] + [_S2_CONTROL_PLANE]:
        imported = _imports(path)
        assert not {m.split(".")[0] for m in imported} & forbidden_modules, (path.name, imported)
        assert not [m for m in imported if m.startswith(harness_prefixes)], (path.name, imported)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert not names & forbidden_names, (path.name, names & forbidden_names)


def test_only_the_production_session_wires_production_trust_sources() -> None:
    tree = ast.parse((_PACKAGE / "integration_session.py").read_text(encoding="utf-8"))
    for function in ast.walk(tree):
        if not isinstance(function, ast.FunctionDef):
            continue
        source = ast.unparse(function)
        uses_production = "prove_identity_boundary," in source or "RegistryHumanAttestationVerifier()" in source
        assert uses_production == (function.name == "open_integration_session"), function.name
    store_source = (_PACKAGE / "integration_store.py").read_text(encoding="utf-8")
    assert "prove_identity_boundary(" not in store_source
    assert "RegistryHumanAttestationVerifier()" not in store_source
    assert "from_facts" not in store_source


def test_control_plane_and_cli_never_reach_s2() -> None:
    root = _PACKAGE.parent
    cli = (root / "cli.py").read_text(encoding="utf-8")
    for term in ("integration_store", "integration_session", "open_integration_session", "integration_records"):
        assert term not in cli
    for module in (root / "control_plane").glob("*.py"):
        assert "ai_dev_orchestrator.integration" not in module.read_text(encoding="utf-8"), module.name


def test_the_v4_records_are_pure_and_closed() -> None:
    assert records.CLAIM_SHAPES == ("write-result", "review-packet", "verification-failed", "workspace-untrusted")
    assert records.OBSERVATION_KINDS == ("m0", "m1", "m2")
    assert records.EXECUTION_CLAIM_PROVENANCE == "execution_claim"
    assert (ALPHA_EXECUTION_POLICY.review_required, ALPHA_EXECUTION_POLICY.human_acceptance_required,
            ALPHA_EXECUTION_POLICY.max_attempts) == (True, True, 1)
    assert records.is_alpha_policy(make_policy()) and not records.is_alpha_policy(make_policy(attempts=2))
    # The v2 subject is domain-separated from v1's.
    from ai_dev_orchestrator.control_plane.authority import plan_activation_subject_sha256

    common = dict(project_contract_sha256="1" * 64, execution_plan_sha256="2" * 64,
                  execution_policy_sha256="3" * 64, target_workspace_sha256="4" * 64)
    assert plan_activation_subject_sha256(**common) != plan_activation_subject_v2_sha256(
        **common, write_scopes_sha256="5" * 64, project_config_sha256="6" * 64,
        identity_boundary_sha256="7" * 64)


def test_frozen_models_and_fields_are_unchanged_by_s2() -> None:
    from ai_dev_orchestrator.control_plane import authority, models

    assert set(models.StepContract.model_fields) >= {"step_id", "review_required", "human_acceptance_required",
                                                     "max_attempts"}
    assert "write_scope" not in models.StepContract.model_fields
    assert set(authority.ApprovalSubjectKind.__members__) == {"PROJECT_CONTRACT", "PLAN_ACTIVATION",
                                                              "STEP_ACCEPTANCE"}
    assert {kind.value for kind in K} == {"project_contract", "plan_activation", "step_acceptance",
                                          "exact_diff_approval"}
