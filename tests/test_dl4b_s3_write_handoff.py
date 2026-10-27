"""DL-4B S3 — exact-diff approval and the write handoff, offline.

Every state root, inbox, exchange root and clone is a real directory under
pytest ``tmp_path``. The clone is a **synthetic Git repository** (the 5F2C test
fixtures), detached at its one commit. The identity boundary, the approver
registry and every security fact come from S0's and S1's synthetic Windows
worlds; the files A reads are the real files, read through the production
:class:`WindowsAuthorityFiles` (so write-sharing denial, link counts, reparse
flags and final paths are real), with **synthetic owners and descriptors**
substituted, as S0's tests substitute synthetic security facts.

The human's X-side step is simulated inside the test by running the frozen,
unchanged ``l2-apply-approved-file-edit`` command (Typer's runner, in-process)
against the handoff directory A published, writing its stdout to the outbox
and then the completion marker. That is legitimate because a claim's origin
is never trusted anyway. No test creates an account, needs elevation, changes
an ACL outside ``tmp_path``, opens a socket, calls a model, or touches a real
project. Signatures come from S1's test-only software keys.

Sections: harness; exact-diff approval; the write handoff; M0; M1 and the
effect; the FD-17 claim protocol; caller-supplied authority; duplicate,
concurrent and restarted attempts; crashes; the tamper matrix; DL-3 → DL-2;
production primitives; static boundaries.
"""

from __future__ import annotations

import ast
import hashlib
import json
import ntpath
import os
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field, replace
from datetime import timedelta
from pathlib import Path

import pytest
from test_dl4b_s0_identity_boundary import (
    ADMIN_FULL,
    CREATOR_OWNER,
    IO,
    OI,
    OICI,
    RX,
    A,
    O,
    X,
    allow,
)
from test_dl4b_s1_attestation_verifier import ALICE, BOB, NOW, Clock
from test_dl4b_s2_integration_store import (
    STEP,
    Harness,
    SimulatedCrash,
    _put_ancestors,
    _set_alice,
    approve_contract,
    bound_world,
    crash_at,
    make_plan,
    make_policy,
    make_proposal,
    snapshot,
    step_request,
)
from typer.testing import CliRunner

import ai_dev_orchestrator.integration as integration
from ai_dev_orchestrator.cli import app
from ai_dev_orchestrator.control_plane import (
    AuthorityRefusedError,
    ImplementationReport,
    ProjectOuterLoop,
    RolePorts,
    StateUntrustedError,
    StepEvent,
    StepState,
    TransitionRefused,
    bind_role_output,
)
from ai_dev_orchestrator.control_plane.attestation_v2 import ApprovalSubjectKindV2 as K
from ai_dev_orchestrator.control_plane.store import StoreLockedError
from ai_dev_orchestrator.control_plane.integration_records import (
    WRITE_HANDOFF_REPORT_SUMMARY,
    WriteScopeV1,
    exact_diff_approval_subject_v1_sha256,
    plan_activation_subject_v2_sha256,
)
from ai_dev_orchestrator.integration import claim_readers, claim_receiver, exchange
from ai_dev_orchestrator.integration import integration_store as store_module
from ai_dev_orchestrator.integration import workspace_observation as wo
from ai_dev_orchestrator.integration.attestation_verifier import HumanAttestationRefusedError
from ai_dev_orchestrator.integration.authority_files import WindowsAuthorityFiles
from ai_dev_orchestrator.integration.integration_session import IntegrationSession, open_integration_session_from_facts
from ai_dev_orchestrator.integration.integration_store import IntegrationStore, WriteHandoffRefusedError
from ai_dev_orchestrator.integration.security_descriptor import (
    FILE_ADD_FILE,
    FILE_ALL_ACCESS,
    FILE_DELETE_CHILD,
    WRITE_DAC,
    WRITE_OWNER,
    DELETE,
    ObjectKind,
    Principal,
    build_security_descriptor,
    parse_security_descriptor,
    upper_bound_rights,
)
from ai_dev_orchestrator.integration.write_handoff import WriteHandoffAdapter, mint_write_handoff_adapter
from tests.test_cli_l2_apply_approved_file_edit import (
    ORIGINAL_TEXT,
    PROPOSED_TEXT,
    TARGET,
    _artifact,
    _change,
    _make_repo,
    _sha,
    _write_config,
)

WINDOWS = sys.platform == "win32"
needs_windows = pytest.mark.skipif(not WINDOWS, reason="real Windows file handles and a synthetic Windows boundary")
needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
runner = CliRunner()

APPROVED_AT = NOW + timedelta(minutes=1)
ARTIFACT_NAME = "approved.json"
CONFIG_NAME = "project.yaml"
OTHER_TEXT = ORIGINAL_TEXT.replace("sum(items)", "sum(items) + 1")


# =============================================================================
# harness
# =============================================================================


def s3_world(state_root: str, clone: str, inbox: str, exchange_root: str):
    """S2's world, with the boundary's inbox and exchange root also moved to
    real directories, each provisioned as S0's good world provisions them."""
    w = bound_world(state_root, clone)
    for path in (inbox, exchange_root):
        _put_ancestors(w, path)
    w.put(inbox, is_dir=True, owner=A, protected=True, aces=[
        allow(A, FILE_ALL_ACCESS, OICI), *ADMIN_FULL, allow(O, RX | FILE_ADD_FILE),
        allow(CREATOR_OWNER, FILE_ALL_ACCESS, IO | OI),
    ])
    w.put(exchange_root, is_dir=True, owner=A, protected=True,
          aces=[allow(A, FILE_ALL_ACCESS, OICI), *ADMIN_FULL, allow(X, RX), allow(O, RX)])
    w.boundary["paths"]["inbox"] = inbox
    w.boundary["paths"]["exchange_root"] = exchange_root
    return w


def _key(path: str) -> str:
    return ntpath.normcase(path)


class TestFiles:
    """Real file access with synthetic owners and descriptors.

    Reads go through the production :class:`WindowsAuthorityFiles`. Each
    returned descriptor is replaced: a directory A created reports exactly the
    descriptor A asked for; an inbox file is O's; a file in an outbox is X's;
    a handoff file is A's; anything in the clone is X's. Tests override owners
    or descriptors per path, and hook reads to model TOCTOU.
    """

    __test__ = False

    def __init__(self, inbox: str, exchange_root: str) -> None:
        self.real = WindowsAuthorityFiles()
        self.inbox = inbox
        self.exchange = exchange_root
        self.created: dict[str, bytes] = {}
        self.owner: dict[str, str] = {}
        self.descriptor: dict[str, bytes] = {}
        self.reads: list[str] = []
        self.before_read: dict[str, object] = {}
        self.fail_create: set[str] = set()
        #: DL-4B S6: the boundary's published/ directory, whose files A creates.
        self.published: str | None = None

    def _owner(self, path: str) -> str:
        if _key(path) in self.owner:
            return self.owner[_key(path)]
        parent = ntpath.basename(ntpath.dirname(path))
        if _key(ntpath.dirname(path)) == _key(self.inbox):
            return O
        if parent.startswith("outbox-"):
            return X
        if _key(path).startswith(_key(self.exchange)):
            return A
        if self.published is not None and _key(ntpath.dirname(path)) == _key(self.published):
            return A
        return X

    def _facts(self, path: str, facts):
        if facts is None:
            return None
        key = _key(path)
        if key in self.descriptor:
            sd = self.descriptor[key]
        elif key in self.created:
            sd = self.created[key]
        else:
            owner = self._owner(path)
            sd = build_security_descriptor(owner, [allow(owner, FILE_ALL_ACCESS)], protected=False)
        return replace(facts, security_descriptor=sd)

    def read_file(self, path, limit):
        self.reads.append(path)
        hook = self.before_read.pop(ntpath.basename(path), None)
        if hook is not None:
            hook()
        result = self.real.read_file(path, limit)
        return None if result is None else (self._facts(path, result[0]), result[1])

    def object_facts(self, path):
        return self._facts(path, self.real.object_facts(path))

    def list_directory(self, path):
        return self.real.list_directory(path)

    def file_identity(self, path):
        return self.real.file_identity(path)

    def create_directory(self, path, security_descriptor):
        if ntpath.basename(path).split("-")[0] in self.fail_create:
            raise OSError("simulated creation failure")
        os.mkdir(path)
        self.created[_key(path)] = security_descriptor

    def create_file(self, path, content):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0))
        try:
            os.write(fd, content)
            os.fsync(fd)
        finally:
            os.close(fd)


class FakeWaiter:
    """A monotonic clock that advances only when A sleeps. ``on_sleep`` runs
    once, at A's first sleep: that is where the human's X-side step happens."""

    def __init__(self) -> None:
        self.now = 1_000.0
        self.sleeps = 0
        self.on_sleep = None

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps += 1
        self.now += seconds
        action, self.on_sleep = self.on_sleep, None
        if action is not None:
            action()


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


@dataclass
class W(Harness):
    inbox: str = ""
    exchange: str = ""
    repo: Path | None = None
    head: str = ""
    files: TestFiles | None = None
    waiter: FakeWaiter = field(default_factory=FakeWaiter)
    config_bytes: bytes = b""
    artifact: dict | None = None

    def open(self) -> IntegrationStore:
        self.session = open_integration_session_from_facts(
            self.root, self.world, clock=self.clock, files=self.files, waiter=self.waiter)
        return self.store

    @property
    def scope(self) -> WriteScopeV1:
        return WriteScopeV1(schema_version="write-scope.v1", step_id=STEP, path=TARGET, change_type="modify",
                            pre_image_sha256=_sha(ORIGINAL_TEXT), base_head_oid=self.head,
                            project_config_sha256=hashlib.sha256(self.config_bytes).hexdigest())

    def put_inbox(self, name: str, data: bytes) -> None:
        Path(self.inbox, name).write_bytes(data)

    def put_artifact(self, artifact: dict | None = None, name: str = ARTIFACT_NAME) -> bytes:
        data = json.dumps(artifact if artifact is not None else self.artifact).encode("utf-8")
        self.put_inbox(name, data)
        return data

    def target(self) -> Path:
        return self.repo / TARGET

    def handoff_dirs(self) -> list[str]:
        return sorted(os.listdir(self.exchange))


def approval_block(**changes) -> dict:
    block = {"approved_by": "alice", "approved_at": APPROVED_AT.isoformat(),
             "approval_text": "I approve this diff proposal for workspace file editing", "source": "manual"}
    block.update(changes)
    return block


def make_w(tmp_path: Path) -> W:
    for name in ("state", "inbox", "exchange"):
        (tmp_path / name).mkdir()
    repo = _make_repo(tmp_path)
    git(repo, "checkout", "-q", "--detach")
    head = (repo / ".git" / "HEAD").read_text(encoding="ascii").strip()
    from ai_dev_orchestrator.control_plane import AidoStateRoot

    root = AidoStateRoot.create(tmp_path / "state")
    clone = os.path.realpath(repo)
    inbox, exchange_root = os.path.realpath(tmp_path / "inbox"), os.path.realpath(tmp_path / "exchange")
    world = s3_world(root.path, clone, inbox, exchange_root)
    w = W(tmp_path, world, Clock(NOW), root, clone, inbox=inbox, exchange=exchange_root, repo=Path(clone),
          head=head, files=TestFiles(inbox, exchange_root))
    config = _write_config(Path(inbox), clone, name=CONFIG_NAME)
    w.config_bytes = config.read_bytes()
    w.artifact = _artifact(approval=approval_block())
    w.put_artifact()
    return w


@pytest.fixture
def w(tmp_path: Path):
    if not WINDOWS or shutil.which("git") is None:
        pytest.skip("needs Windows and git")
    harness = make_w(tmp_path)
    harness.open()
    yield harness
    harness.close()


@dataclass
class Chain:
    pc: object
    plan: object
    contract: object = None
    project: object = None
    step: object = None
    approval_id: str | None = None


def activate_scope(w: W, pc, scope: WriteScopeV1 | None = None):
    plan = make_plan(pc)
    policy = make_policy()
    challenge = w.store.request_plan_activation(execution_plan=plan, execution_policy=policy,
                                                write_scopes=(scope or w.scope,))
    w.store.issue_execution_plan(plan, execution_policy=policy, write_scopes=(scope or w.scope,),
                                 attestation=w.sign(challenge))
    return plan


def request_diff(w: W, plan, *, artifact_name: str = ARTIFACT_NAME, config_name: str = CONFIG_NAME):
    return w.store.request_exact_diff_approval(execution_plan_sha256=plan.sha256, step_id=STEP,
                                               artifact_name=artifact_name, config_name=config_name)


def sign_diff(w: W, challenge, **options):
    w.clock.now = max(w.clock.now, APPROVED_AT + timedelta(minutes=1))
    return w.sign(challenge, attested_at=APPROVED_AT, **options)


def approved(w: W) -> Chain:
    """Contract, activation and a recorded exact-diff approval."""
    pc = approve_contract(w)
    plan = activate_scope(w, pc)
    challenge = request_diff(w, plan)
    approval_id = w.store.record_exact_diff_approval(sign_diff(w, challenge))
    return Chain(pc, plan, approval_id=approval_id)


def executing(w: W, chain: Chain | None = None) -> Chain:
    chain = chain or approved(w)
    store = w.store
    chain.contract = store.issue_authorized_step_contract(make_proposal(), execution_plan_sha256=chain.plan.sha256)
    chain.project = store.create_project_run(project_contract_sha256=chain.pc.sha256,
                                             execution_plan_sha256=chain.plan.sha256)
    step = store.create_step_run(project_run_id=chain.project.project_run_id,
                                 step_contract_sha256=chain.contract.sha256)
    store.apply_step_transition(step.step_run_id, step_request(step, StepEvent.MARK_READY))
    step = store.get_step_run(step.step_run_id)
    store.apply_step_transition(step.step_run_id, step_request(step, StepEvent.BEGIN_ATTEMPT))
    chain.step = store.get_step_run(step.step_run_id)
    return chain


def ticket_for(w: W, chain: Chain):
    step = w.store.get_step_run(chain.step.step_run_id)
    return w.store.issue_dispatch_ticket(step.step_run_id, role="implementer", expected_state_version=step.state_version)


def ticket_dirs(w: W, ticket) -> tuple[Path, Path]:
    handoff, outbox = exchange.ticket_directories(w.exchange, ticket.ticket_id)
    return Path(handoff), Path(outbox)


def run_frozen_writer(handoff: Path) -> bytes:
    """The human's X-side step: the existing, unchanged 5F2C command."""
    result = runner.invoke(app, [
        "l2-apply-approved-file-edit",
        "--project-config", str(handoff / exchange.HANDOFF_CONFIG_NAME),
        "--approved-diff-proposal", str(handoff / exchange.HANDOFF_ARTIFACT_NAME),
        "--apply-approved-plan", "--write-approved-file",
    ])
    return result.stdout_bytes


def deliver(outbox: Path, stdout: bytes | None, *, complete: bool = True) -> None:
    if stdout is not None:
        (outbox / claim_receiver.STDOUT_NAME).write_bytes(stdout)
    if complete:
        (outbox / claim_receiver.COMPLETE_NAME).write_bytes(b"")


def x_step(w: W, ticket, *, write: bool = True, stdout=None, complete: bool = True, extra=None):
    """Schedule the human's X-side step for A's first wait. ``stdout`` may be
    bytes, or a function of the frozen command's real stdout."""
    handoff, outbox = ticket_dirs(w, ticket)

    def action() -> None:
        real = run_frozen_writer(handoff) if write else b""
        if extra is not None:
            extra(w, handoff, outbox)
        data = stdout(real) if callable(stdout) else (real if stdout is None else stdout)
        deliver(outbox, data, complete=complete)

    w.waiter.on_sleep = action


def genuine_write_report(w: W) -> bytes:
    """A valid-shaped workspace-write-result.v1 for this artifact, produced by
    the frozen writer in a throwaway copy of the repository."""
    scratch = w.tmp / "scratch"
    scratch.mkdir(exist_ok=True)
    copy_repo = _make_repo(scratch)
    git(copy_repo, "checkout", "-q", "--detach")
    inputs = scratch / "inputs"
    inputs.mkdir(exist_ok=True)
    config = _write_config(inputs, os.path.realpath(copy_repo))
    artifact = inputs / "approved.json"
    artifact.write_text(json.dumps(w.artifact), encoding="utf-8")
    result = runner.invoke(app, ["l2-apply-approved-file-edit", "--project-config", str(config),
                                 "--approved-diff-proposal", str(artifact), "--apply-approved-plan",
                                 "--write-approved-file"])
    assert result.exit_code == 0, result.stderr
    return result.stdout_bytes


def implement(w: W, chain: Chain, ticket):
    contract = w.store.get_step_contract(chain.contract.sha256)
    return w.session.implementer.implement(step_contract=contract, attempt=ticket.attempt, dispatch=ticket)


def rows(w: W, table: str) -> list[sqlite3.Row]:
    return w.store._conn.execute(f"SELECT * FROM {table}").fetchall()


def intent_state(w: W) -> str | None:
    found = rows(w, "write_intents")
    return found[0]["state"] if found else None


def returned(w: W, chain: Chain, ticket, report: ImplementationReport):
    step = w.store.get_step_run(chain.step.step_run_id)
    return w.store.apply_step_transition(
        step.step_run_id, step_request(step, StepEvent.IMPLEMENTATION_RETURNED, implementation=report),
        role_output=bind_role_output(ticket, report))


def fixed_report(chain: Chain) -> ImplementationReport:
    return ImplementationReport(step_contract_sha256=chain.contract.sha256, attempt=1,
                                summary=WRITE_HANDOFF_REPORT_SUMMARY, claims=())


# =============================================================================
# 1. exact-diff approval (H6)
# =============================================================================


@needs_windows
def test_an_exact_diff_approval_binds_the_stored_artifact_bytes_and_the_activated_scope(w: W) -> None:
    pc = approve_contract(w)
    plan = activate_scope(w, pc)
    challenge = request_diff(w, plan)
    assert challenge.subject_kind is K.EXACT_DIFF_APPROVAL
    assert challenge.required_approval_text == "I approve this diff proposal for workspace file editing"
    artifact = (Path(w.inbox) / ARTIFACT_NAME).read_bytes()
    activation = w.store._load_activation(plan.sha256)
    expected = exact_diff_approval_subject_v1_sha256(
        plan_activation_subject_sha256=plan_activation_subject_v2_sha256(
            project_contract_sha256=pc.sha256, execution_plan_sha256=plan.sha256,
            execution_policy_sha256=make_policy().sha256,
            target_workspace_sha256=activation.target_workspace_sha256,
            write_scopes_sha256=activation.write_scopes_sha256,
            project_config_sha256=w.scope.project_config_sha256,
            identity_boundary_sha256=w.session.boundary_sha256),
        execution_plan_sha256=plan.sha256, step_id=STEP, write_scope_sha256=w.scope.sha256,
        approved_diff_artifact_sha256=hashlib.sha256(artifact).hexdigest())
    assert challenge.subject_sha256 == expected
    # The bytes are now A's own, write-once, by digest.
    stored = Path(w.root.path, "evidence", "approved-diff", hashlib.sha256(artifact).hexdigest())
    assert stored.read_bytes() == artifact
    approval_id = w.store.record_exact_diff_approval(sign_diff(w, challenge))
    row = rows(w, "exact_diff_approvals")[0]
    assert (row["approval_id"], row["step_id"], row["write_scope_sha256"], row["consumed_by_ticket_id"]) == (
        approval_id, STEP, w.scope.sha256, None)
    report = w.store.recover(w.store.create_project_run(
        project_contract_sha256=pc.sha256, execution_plan_sha256=plan.sha256).project_run_id)
    assert report.integrity_ok, report.integrity_issues


@needs_windows
def test_changing_the_artifact_in_the_inbox_after_the_request_changes_nothing(w: W) -> None:
    pc = approve_contract(w)
    plan = activate_scope(w, pc)
    challenge = request_diff(w, plan)
    w.put_artifact(_artifact(approval=approval_block(), title="Another"))  # the inbox file is never read again
    w.store.record_exact_diff_approval(sign_diff(w, challenge))
    assert rows(w, "exact_diff_approvals")[0]["approved_diff_artifact_sha256"] == hashlib.sha256(
        json.dumps(w.artifact).encode()).hexdigest()


def _two_changes():
    return _artifact(approval=approval_block(), changes=[_change(), _change(path="src/billing/tax.py",
                                                                            original="TAX_RATE = 0.2\n",
                                                                            proposed="TAX_RATE = 0.3\n")])


ARTIFACT_REFUSALS = {
    "another path": lambda w: _artifact(approval=approval_block(), changes=[_change(
        path="src/billing/tax.py", original="TAX_RATE = 0.2\n", proposed="TAX_RATE = 0.3\n")]),
    "another pre-image": lambda w: _artifact(approval=approval_block(), changes=[_change(original=OTHER_TEXT)]),
    "two changes": lambda w: _two_changes(),
    "no change": lambda w: _artifact(approval=approval_block(), changes=[]),
    "create": lambda w: _artifact(approval=approval_block(), changes=[_change(change_type="create")]),
    "paraphrased phrase": lambda w: _artifact(approval=approval_block(approval_text="I approve this diff")),
    "model source": lambda w: _artifact(approval=approval_block(source="model")),
    "identity mismatch": lambda w: _artifact(approval=approval_block(), title="Another title"),
    "extra field": lambda w: {**w.artifact, "auto_apply": True},
    "files edited": lambda w: {**w.artifact, "diff_proposal": {**w.artifact["diff_proposal"], "files_edited": True}},
}


@needs_windows
@pytest.mark.parametrize("name", list(ARTIFACT_REFUSALS))
def test_an_artifact_outside_the_scope_or_the_5f2c_contract_is_refused(w: W, name) -> None:
    pc = approve_contract(w)
    plan = activate_scope(w, pc)
    w.put_artifact(ARTIFACT_REFUSALS[name](w), name="bad.json")
    before = snapshot(w.store)
    with pytest.raises(AuthorityRefusedError):
        request_diff(w, plan, artifact_name="bad.json")
    assert snapshot(w.store) == before


@needs_windows
@pytest.mark.parametrize("data", [
    b"\xef\xbb\xbf{}", b'{"a": 1, "a": 2}', b"[]", b"{" + b" " * 10, b'{"x": NaN}', b"",
])
def test_an_artifact_that_is_not_one_strict_json_object_is_refused(w: W, data) -> None:
    pc = approve_contract(w)
    plan = activate_scope(w, pc)
    w.put_inbox("bad.json", data)
    with pytest.raises(AuthorityRefusedError):
        request_diff(w, plan, artifact_name="bad.json")


CONFIG_REFUSALS = {
    "workspace write disabled": dict(write_enabled=False),
    "another project": dict(project_id="other_project"),
    "another repo": dict(github_repo="other/repo"),
}


@needs_windows
@pytest.mark.parametrize("name", list(CONFIG_REFUSALS) + ["another workspace", "not the scope's config"])
def test_a_config_that_is_not_the_scope_s_or_the_clone_s_is_refused(w: W, name) -> None:
    if name == "another workspace":
        other = w.tmp / "elsewhere"
        other.mkdir()
        data = _write_config(w.tmp, os.path.realpath(other), name="other.yaml").read_bytes()
    elif name == "not the scope's config":
        data = w.config_bytes + b"# a comment changes the digest\n"
    else:
        data = _write_config(w.tmp, w.clone, name="other.yaml", **CONFIG_REFUSALS[name]).read_bytes()
    pc = approve_contract(w)
    if name in CONFIG_REFUSALS or name == "another workspace":
        w.config_bytes = data  # the scope binds this config's digest; A still refuses its content
    plan = activate_scope(w, pc)
    w.put_inbox("other.yaml", data)
    before = snapshot(w.store)
    with pytest.raises(AuthorityRefusedError):
        request_diff(w, plan, config_name="other.yaml")
    assert snapshot(w.store) == before


@needs_windows
@pytest.mark.parametrize("problem", ["missing", "owned by X", "owned by A", "hard link", "directory",
                                     "oversize", "traversal", "reserved", "trailing dot"])
def test_inbox_files_must_be_single_link_regular_files_the_operator_placed(w: W, problem, monkeypatch) -> None:
    pc = approve_contract(w)
    plan = activate_scope(w, pc)
    name = ARTIFACT_NAME
    path = Path(w.inbox, ARTIFACT_NAME)
    if problem == "missing":
        name = "absent.json"
    elif problem == "owned by X":
        w.files.owner[_key(str(path))] = X
    elif problem == "owned by A":
        w.files.owner[_key(str(path))] = A
    elif problem == "hard link":
        os.link(path, w.tmp / "second-link.json")
    elif problem == "directory":
        name = "folder"
        Path(w.inbox, name).mkdir()
    elif problem == "oversize":
        monkeypatch.setattr(claim_readers, "MAX_APPROVED_DIFF_BYTES", 100)
    else:
        name = {"traversal": "..\\approved.json", "reserved": "CON.json", "trailing dot": "approved.json."}[problem]
    before = snapshot(w.store)
    with pytest.raises(AuthorityRefusedError):
        request_diff(w, plan, artifact_name=name)
    assert snapshot(w.store) == before


@needs_windows
@pytest.mark.parametrize("change", [dict(approved_by="bob"), dict(approved_at=(APPROVED_AT + timedelta(seconds=1)).isoformat())])
def test_the_artifact_approval_block_must_be_the_attested_approver_and_time(w: W, change) -> None:
    w.artifact = _artifact(approval=approval_block(**change))
    w.put_artifact()
    pc = approve_contract(w)
    plan = activate_scope(w, pc)
    challenge = request_diff(w, plan)
    before = snapshot(w.store)
    with pytest.raises(AuthorityRefusedError, match="approval block"):
        w.store.record_exact_diff_approval(sign_diff(w, challenge))
    assert snapshot(w.store) == before


@needs_windows
def test_an_exact_diff_approval_is_single_use_per_step_and_a_replay_is_a_receipt(w: W) -> None:
    pc = approve_contract(w)
    plan = activate_scope(w, pc)
    challenge = request_diff(w, plan)
    att = sign_diff(w, challenge)
    approval_id = w.store.record_exact_diff_approval(att)
    assert w.store.record_exact_diff_approval(att) == approval_id  # receipt
    with pytest.raises(AuthorityRefusedError, match="one exact-diff approval"):
        request_diff(w, plan)
    assert len(rows(w, "exact_diff_approvals")) == 1


@needs_windows
def test_two_open_challenges_for_one_step_record_only_one_approval(w: W) -> None:
    pc = approve_contract(w)
    plan = activate_scope(w, pc)
    first, second = request_diff(w, plan), request_diff(w, plan)
    w.store.record_exact_diff_approval(sign_diff(w, first))
    before = snapshot(w.store)
    with pytest.raises(AuthorityRefusedError, match="one exact-diff approval"):
        w.store.record_exact_diff_approval(sign_diff(w, second))
    assert snapshot(w.store) == before


@needs_windows
def test_a_forged_or_misdirected_signature_is_not_an_exact_diff_approval(w: W) -> None:
    pc = approve_contract(w)
    plan = activate_scope(w, pc)
    challenge = request_diff(w, plan)
    before = snapshot(w.store)
    with pytest.raises(HumanAttestationRefusedError):  # a key the registry does not hold for alice
        w.store.record_exact_diff_approval(sign_diff(w, challenge, private=BOB))
    contract_challenge = w.store.request_project_contract_approval(pc.content.model_copy(update={"goal": "x"}))
    with pytest.raises(HumanAttestationRefusedError):  # an approval of another kind of subject
        w.store.record_exact_diff_approval(w.sign(contract_challenge))
    with pytest.raises(AuthorityRefusedError):  # a model built without validation is never authority
        w.store.record_exact_diff_approval(type(sign_diff(w, challenge)).model_construct())
    assert rows(w, "exact_diff_approvals") == []
    del before


@needs_windows
def test_an_exact_diff_challenge_for_another_state_root_does_not_record(w: W) -> None:
    pc = approve_contract(w)
    plan = activate_scope(w, pc)
    challenge = request_diff(w, plan)
    with pytest.raises(HumanAttestationRefusedError):
        w.store.record_exact_diff_approval(sign_diff(w, challenge, root="ee" * 16))


# =============================================================================
# 2. the write handoff
# =============================================================================


@needs_windows
def test_one_approved_write_is_handed_off_observed_and_returned(w: W) -> None:
    chain = executing(w)
    ticket = ticket_for(w, chain)
    x_step(w, ticket)
    report = implement(w, chain, ticket)
    assert report.output == fixed_report(chain)
    assert w.target().read_text(encoding="utf-8") == PROPOSED_TEXT
    # Durable records: M0, M1, the claim receipt, the completed intent, the evidence.
    assert intent_state(w) == "completed"
    kinds = sorted(row["kind"] for row in rows(w, "authority_observations"))
    assert kinds == ["m0", "m1"]
    claim = rows(w, "execution_claims")[0]
    assert (claim["shape"], claim["provenance"]) == ("write-result", "execution_claim")
    assert rows(w, "exact_diff_approvals")[0]["consumed_by_ticket_id"] == ticket.ticket_id
    assert len(rows(w, "write_evidence")) == 1
    # Exactly one handoff and one outbox, each with exactly the DACL A set.
    handoff, outbox = ticket_dirs(w, ticket)
    assert w.handoff_dirs() == sorted([handoff.name, outbox.name])
    assert sorted(os.listdir(handoff)) == sorted([exchange.HANDOFF_ARTIFACT_NAME, exchange.HANDOFF_CONFIG_NAME])
    assert (handoff / exchange.HANDOFF_CONFIG_NAME).read_bytes() == w.config_bytes
    for path, acl in ((handoff, exchange.handoff_dacl(A, X)), (outbox, exchange.outbox_dacl(A, X, O))):
        sd = parse_security_descriptor(w.files.created[_key(str(path))])
        assert sd.owner == A and sd.protected and sd.dacl == acl
    applied = returned(w, chain, ticket, report.output)
    assert applied.current_state == StepState.VERIFYING.value
    # A fresh session re-proves the whole chain.
    w.reopen()
    rep = w.store.recover(chain.project.project_run_id)
    assert rep.integrity_ok, rep.integrity_issues
    assert w.store.get_step_run(chain.step.step_run_id).state is StepState.RECOVERY_REQUIRED


@needs_windows
def test_the_dacls_bound_what_x_can_do_to_a_s_directories() -> None:
    principal = Principal(role="execution", sid=X, allow_sids=frozenset({X, "S-1-1-0", "S-1-5-11", "S-1-5-32-545"}),
                          deny_sids=frozenset({X, "S-1-1-0"}))
    handoff = parse_security_descriptor(build_security_descriptor(A, exchange.handoff_dacl(A, X), protected=True))
    outbox = parse_security_descriptor(build_security_descriptor(A, exchange.outbox_dacl(A, X, O), protected=True))
    forbidden = WRITE_DAC | WRITE_OWNER | DELETE | FILE_DELETE_CHILD
    assert upper_bound_rights(handoff, principal, ObjectKind.DIRECTORY) & (forbidden | FILE_ADD_FILE) == 0
    assert upper_bound_rights(outbox, principal, ObjectKind.DIRECTORY) & forbidden == 0
    assert upper_bound_rights(outbox, principal, ObjectKind.DIRECTORY) & FILE_ADD_FILE
    authority = Principal(role="authority", sid=A, allow_sids=frozenset({A, "S-1-1-0"}), deny_sids=frozenset({A}))
    assert upper_bound_rights(outbox, authority, ObjectKind.DIRECTORY) & (FILE_ADD_FILE | WRITE_DAC) == 0


@needs_windows
def test_no_handoff_is_visible_before_the_intent_is_durable(w: W, monkeypatch) -> None:
    chain = executing(w)
    ticket = ticket_for(w, chain)
    seen = []
    original = exchange.publish_handoff

    def publish(*args, **kwargs):
        # At the moment of publication no transaction is open: the intent and
        # the spent approval are committed (the store holds its file exclusively).
        conn = w.store._conn
        assert not conn.in_transaction
        seen.append(([tuple(r) for r in conn.execute("SELECT state FROM write_intents")],
                     [tuple(r) for r in conn.execute("SELECT consumed_by_ticket_id FROM exact_diff_approvals")]))
        assert w.handoff_dirs() == []
        return original(*args, **kwargs)

    monkeypatch.setattr(exchange, "publish_handoff", publish)
    x_step(w, ticket)
    implement(w, chain, ticket)
    assert seen == [([("pending",)], [(ticket.ticket_id,)])]


# =============================================================================
# 3. M0 refuses an unexpected pre-image, HEAD or Git control state
# =============================================================================


def _m0_target(w: W) -> None:
    w.target().write_text(OTHER_TEXT, encoding="utf-8")


def _m0_head(w: W) -> None:
    (w.repo / ".git" / "HEAD").write_text("0" * 40 + "\n", encoding="ascii")


def _m0_symbolic(w: W) -> None:
    (w.repo / ".git" / "HEAD").write_text("ref: refs/heads/master\n", encoding="ascii")


def _m0_config(w: W) -> None:
    with open(w.repo / ".git" / "config", "a", encoding="utf-8") as handle:
        handle.write("[aido]\n\tdrift = 1\n")


def _m0_hook(w: W) -> None:
    (w.repo / ".git" / "hooks" / "post-checkout").write_text("#!/bin/sh\n", encoding="utf-8")


def _m0_gitmodules(w: W) -> None:
    (w.repo / ".gitmodules").write_text("[submodule]\n", encoding="utf-8")


def _m0_modules(w: W) -> None:
    (w.repo / ".git" / "modules").mkdir()


def _m0_hard_link(w: W) -> None:
    os.link(w.repo / "src" / "billing" / "tax.py", w.tmp / "tax-link.py")


def _m0_junction(w: W) -> None:
    import _winapi

    _winapi.CreateJunction(str(w.tmp / "inbox"), str(w.repo / "linked"))


def _m0_nested(w: W) -> None:
    (w.repo / "vendor" / ".git").mkdir(parents=True)


M0_REFUSALS = {
    "target is not the pre-image": (_m0_target, "pre-image"),
    "HEAD moved": (_m0_head, "HEAD"),
    "symbolic HEAD": (_m0_symbolic, "head_not_detached"),
    ".git config drift": (_m0_config, "activation-time"),
    ".git hook planted": (_m0_hook, "activation-time"),
    ".gitmodules": (_m0_gitmodules, "submodules_present"),
    ".git/modules": (_m0_modules, "submodules_present"),
    "hard-linked file": (_m0_hard_link, "hard_link"),
    "junction in the tree": (_m0_junction, "reparse_point"),
    "nested repository": (_m0_nested, "nested_repository"),
}


@needs_windows
@pytest.mark.parametrize("name", list(M0_REFUSALS))
def test_m0_refuses_and_nothing_is_spent_or_published(w: W, name) -> None:
    chain = executing(w)
    ticket = ticket_for(w, chain)
    mutate, match = M0_REFUSALS[name]
    mutate(w)
    before = snapshot(w.store)
    with pytest.raises(AuthorityRefusedError, match=match):
        implement(w, chain, ticket)
    assert snapshot(w.store) == before
    assert rows(w, "exact_diff_approvals")[0]["consumed_by_ticket_id"] is None
    assert w.handoff_dirs() == []


@needs_windows
def test_m0_refuses_an_over_cap_tree(w: W, monkeypatch) -> None:
    chain = executing(w)
    ticket = ticket_for(w, chain)
    monkeypatch.setattr(wo, "MAX_TREE_ENTRIES", 2)
    with pytest.raises(AuthorityRefusedError, match="over_cap"):
        implement(w, chain, ticket)
    assert w.handoff_dirs() == [] and intent_state(w) is None


@needs_windows
def test_activation_refuses_a_head_other_than_the_scope_base(w: W) -> None:
    pc = approve_contract(w)
    with pytest.raises(AuthorityRefusedError, match="base_head_oid"):
        activate_scope(w, pc, w.scope.model_copy(update={"base_head_oid": "1" * 40}))
    _m0_symbolic(w)
    with pytest.raises(AuthorityRefusedError, match="head_not_detached"):
        activate_scope(w, pc)
    assert rows(w, "plan_activations") == [] and rows(w, "activation_observations") == []


# =============================================================================
# 4. M1 decides the effect, independently of the claim
# =============================================================================


def _extra_file(w, handoff, outbox):
    (w.repo / "src" / "billing" / "extra.py").write_text("x = 1\n", encoding="utf-8")


def _git_drift(w, handoff, outbox):
    _m0_config(w)


@needs_windows
@pytest.mark.parametrize("case, expected", [
    ("success claim, nothing written", "refused"),
    ("success claim, another file also changed", "indeterminate"),
    ("success claim, wrong bytes written", "indeterminate"),
    ("written, claim names another approver", "indeterminate"),
    ("written, claim is not a write result", "indeterminate"),
    ("written, .git changed too", "indeterminate"),
    ("written, no claim before the deadline", "indeterminate"),
    ("nothing written, no claim", "refused"),
])
def test_m1_decides_what_happened_and_a_claim_never_overrides_it(w: W, case, expected) -> None:
    chain = executing(w)
    genuine = genuine_write_report(w)
    ticket = ticket_for(w, chain)
    if case == "success claim, nothing written":
        x_step(w, ticket, write=False, stdout=genuine)
    elif case == "success claim, another file also changed":
        x_step(w, ticket, extra=_extra_file)
    elif case == "success claim, wrong bytes written":
        x_step(w, ticket, write=False, stdout=genuine,
               extra=lambda w, h, o: w.target().write_text(OTHER_TEXT, encoding="utf-8"))
    elif case == "written, claim names another approver":
        x_step(w, ticket, stdout=lambda real: real.replace(b'"approved_by": "alice"', b'"approved_by": "mallory"'))
    elif case == "written, claim is not a write result":
        x_step(w, ticket, stdout=b'{"schema_version": "verification-result.v1"}')
    elif case == "written, .git changed too":
        x_step(w, ticket, extra=_git_drift)
    elif case == "written, no claim before the deadline":
        x_step(w, ticket, complete=False)
    else:
        x_step(w, ticket, write=False, stdout=None, complete=False)
    with pytest.raises(WriteHandoffRefusedError, match=expected):
        implement(w, chain, ticket)
    assert intent_state(w) == expected
    assert rows(w, "write_evidence") == []
    # The approval is spent: no second write is ever handed off.
    assert rows(w, "exact_diff_approvals")[0]["consumed_by_ticket_id"] == ticket.ticket_id
    with pytest.raises(AuthorityRefusedError):
        returned(w, chain, ticket, fixed_report(chain))
    rep = w.store.recover(chain.project.project_run_id)
    assert rep.integrity_ok, rep.integrity_issues


@needs_windows
def test_m1_classification_is_a_pure_function_of_two_observations() -> None:
    def obs(tree, head="a" * 40, git="g" * 64):
        return wo.Observation(head_oid=head, git_control=(), git_control_sha256=git, tree=tuple(tree),
                              target_path="t", target_sha256=None, target_size=None, manifest=b"", manifest_sha256="")
    pre, post = "1" * 64, "2" * 64
    base = [("t", 1, pre), ("u", 1, "3" * 64)]
    approved_tree = [("t", 1, post), ("u", 1, "3" * 64)]
    kw = dict(target_path="t", pre_image_sha256=pre, post_image_sha256=post)
    assert wo.classify_write(obs(base), obs(approved_tree), **kw) == "as_approved"
    assert wo.classify_write(obs(base), obs(base), **kw) == "no_change"
    assert wo.classify_write(obs(base), obs(approved_tree + [("v", 1, "4" * 64)]), **kw) == "indeterminate"
    assert wo.classify_write(obs(base), obs([("t", 1, post)]), **kw) == "indeterminate"  # u removed
    assert wo.classify_write(obs(base), obs([("t", 1, "5" * 64), ("u", 1, "3" * 64)]), **kw) == "indeterminate"
    assert wo.classify_write(obs(base), obs(approved_tree, head="b" * 40), **kw) == "indeterminate"
    assert wo.classify_write(obs(base), obs(approved_tree, git="h" * 64), **kw) == "indeterminate"
    assert wo.classify_write(obs(base), obs(base, git="h" * 64), **kw) == "indeterminate"


# =============================================================================
# 5. every FD-17 protocol deviation fails closed
# =============================================================================


def _hold_open_for_writing(w: W, outbox: Path):
    handle = open(outbox / claim_receiver.STDOUT_NAME, "ab")  # noqa: SIM115 - held across A's read
    w.tmp_handles = getattr(w, "tmp_handles", []) + [handle]


CLAIM_DEVIATIONS = {
    "extra entry": (lambda w, h, o: (o / "notes.txt").write_bytes(b"x"), "unexpected_entry"),
    "missing stdout": (lambda w, h, o: None, "missing_entry"),
    "marker not empty": (None, "marker_not_empty"),
    "empty stdout": (None, "empty"),
    "stdout is a directory": (None, "not_regular_file"),
    "stdout is a junction": (None, "reparse_point"),
    "stdout hard-linked": (None, "hard_link"),
    "stdout owned by the operator": (None, "wrong_owner"),
    "stdout owned by A": (None, "wrong_owner"),
    "marker owned by the operator": (None, "wrong_owner"),
    "sharing violation": (None, "sharing_violation"),
    "oversize": (None, "oversize"),
    "deadline": (None, "deadline_expired"),
}


@needs_windows
@pytest.mark.parametrize("name", list(CLAIM_DEVIATIONS))
def test_every_claim_protocol_deviation_records_no_claim(w: W, name, monkeypatch) -> None:
    chain = executing(w)
    ticket = ticket_for(w, chain)
    handoff, outbox = ticket_dirs(w, ticket)
    stdout_path, marker_path = outbox / claim_receiver.STDOUT_NAME, outbox / claim_receiver.COMPLETE_NAME

    def action() -> None:
        real = run_frozen_writer(handoff)
        if name == "missing stdout":
            deliver(outbox, None)
            return
        if name == "stdout is a directory":
            stdout_path.mkdir()
            deliver(outbox, None)
            return
        if name == "stdout is a junction":
            import _winapi

            _winapi.CreateJunction(str(w.tmp / "inbox"), str(stdout_path))
            deliver(outbox, None)
            return
        deliver(outbox, b"" if name == "empty stdout" else real, complete=name != "deadline")
        if name == "extra entry":
            (outbox / "notes.txt").write_bytes(b"x")
        elif name == "marker not empty":
            marker_path.write_bytes(b"done")
        elif name == "stdout hard-linked":
            os.link(stdout_path, w.tmp / "copy.json")
        elif name == "stdout owned by the operator":
            w.files.owner[_key(str(stdout_path))] = O
        elif name == "stdout owned by A":
            w.files.owner[_key(str(stdout_path))] = A
        elif name == "marker owned by the operator":
            w.files.owner[_key(str(marker_path))] = O
        elif name == "sharing violation":
            _hold_open_for_writing(w, outbox)

    if name == "oversize":
        monkeypatch.setattr(claim_readers, "MAX_WRITE_CLAIM_BYTES", 64)
    w.waiter.on_sleep = action
    try:
        with pytest.raises(WriteHandoffRefusedError, match=CLAIM_DEVIATIONS[name][1]):
            implement(w, chain, ticket)
    finally:
        for handle in getattr(w, "tmp_handles", []):
            handle.close()
    assert rows(w, "execution_claims") == []
    assert intent_state(w) == "indeterminate"  # the write happened; the claim protocol failed
    assert rows(w, "write_evidence") == []


@needs_windows
def test_the_deadline_is_a_code_constant_and_only_the_listing_is_read_while_waiting(w: W) -> None:
    assert claim_receiver.CLAIM_WAIT_SECONDS == 2 * 60 * 60
    chain = executing(w)
    ticket = ticket_for(w, chain)
    _, outbox = ticket_dirs(w, ticket)
    with pytest.raises(WriteHandoffRefusedError, match="deadline_expired"):
        implement(w, chain, ticket)
    assert w.waiter.now - 1_000.0 >= claim_receiver.CLAIM_WAIT_SECONDS
    assert not [p for p in w.files.reads if _key(p).startswith(_key(str(outbox)))]
    assert intent_state(w) == "refused"


@needs_windows
def test_a_claim_is_never_read_after_its_ticket_left_executing(w: W) -> None:
    chain = executing(w)
    ticket = ticket_for(w, chain)
    handoff, outbox = ticket_dirs(w, ticket)

    def action() -> None:
        deliver(outbox, run_frozen_writer(handoff))
        # Meanwhile the step leaves EXECUTING (here: a human-applied reduction).
        step = w.store.get_step_run(chain.step.step_run_id)
        w.store.apply_step_transition(step.step_run_id, step_request(
            step, StepEvent.RECOVER_INTERRUPTED, reason="operator reduced it"))

    w.waiter.on_sleep = action
    with pytest.raises(AuthorityRefusedError, match="stale|project is RECOVERY_REQUIRED"):
        implement(w, chain, ticket)
    assert not [p for p in w.files.reads if _key(p).startswith(_key(str(outbox)))]
    assert rows(w, "execution_claims") == []
    assert intent_state(w) == "pending"  # never settled by a step that is no longer in flight
    rep = w.store.recover(chain.project.project_run_id)
    assert rep.integrity_ok, rep.integrity_issues


@needs_windows
@pytest.mark.parametrize("which", ["handoff", "outbox"])
def test_a_pre_existing_per_ticket_directory_is_never_adopted(w: W, which) -> None:
    chain = executing(w)
    ticket = ticket_for(w, chain)
    handoff, outbox = ticket_dirs(w, ticket)
    (handoff if which == "handoff" else outbox).mkdir()
    with pytest.raises(WriteHandoffRefusedError, match="pre_existing"):
        implement(w, chain, ticket)
    assert intent_state(w) in ("refused", "indeterminate")
    assert rows(w, "execution_claims") == []
    assert w.target().read_text(encoding="utf-8") == ORIGINAL_TEXT


@needs_windows
@pytest.mark.parametrize("what", ["outbox dacl", "outbox owner", "handoff dacl"])
def test_a_directory_without_exactly_the_dacl_a_set_is_refused(w: W, what, monkeypatch) -> None:
    chain = executing(w)
    ticket = ticket_for(w, chain)
    handoff, outbox = ticket_dirs(w, ticket)
    original = w.files.create_directory

    def create(path, sd):
        original(path, sd)
        if ("outbox" in what and path == str(outbox)) or ("handoff" in what and path == str(handoff)):
            owner = X if "owner" in what else A
            acl = list(parse_security_descriptor(sd).dacl) + ([] if "owner" in what else [allow(X, WRITE_DAC)])
            w.files.created[_key(path)] = build_security_descriptor(owner, acl, protected=True)

    monkeypatch.setattr(w.files, "create_directory", create)
    with pytest.raises(WriteHandoffRefusedError, match="dacl_mismatch|substituted"):
        implement(w, chain, ticket)
    assert rows(w, "execution_claims") == []


@needs_windows
def test_an_outbox_replaced_while_a_waited_is_refused(w: W) -> None:
    chain = executing(w)
    ticket = ticket_for(w, chain)
    handoff, outbox = ticket_dirs(w, ticket)

    def action() -> None:
        deliver(outbox, run_frozen_writer(handoff))
        os.rename(outbox, w.tmp / "moved-outbox")  # only A or an administrator could, in production
        outbox.mkdir()
        deliver(outbox, (w.tmp / "moved-outbox" / claim_receiver.STDOUT_NAME).read_bytes())

    w.waiter.on_sleep = action
    with pytest.raises(WriteHandoffRefusedError, match="substituted|dacl_mismatch"):
        implement(w, chain, ticket)
    assert rows(w, "execution_claims") == []


# =============================================================================
# 6. caller-supplied claims, observations and reports establish nothing
# =============================================================================


@needs_windows
def test_only_the_session_minted_recorder_can_hand_off_a_write(w: W) -> None:
    chain = executing(w)
    ticket = ticket_for(w, chain)
    before = snapshot(w.store)
    for key in (None, object()):
        with pytest.raises(AuthorityRefusedError, match="write handoff adapter"):
            w.store._perform_write_handoff(key, ticket)
        # No phase is reachable around the gated entry either.
        for phase in (w.store._claim_write_intent, w.store._publish_write_handoff, w.store._receive_write_claim):
            with pytest.raises(AuthorityRefusedError, match="write handoff adapter"):
                phase(key, ticket)
    forged = mint_write_handoff_adapter(w.store, object())
    with pytest.raises(AuthorityRefusedError, match="write handoff adapter"):
        forged.implement(step_contract=w.store.get_step_contract(chain.contract.sha256), attempt=1,
                         dispatch=ticket)
    with pytest.raises(TypeError):
        WriteHandoffAdapter(w.store, object())
    assert snapshot(w.store) == before and w.handoff_dirs() == []


@needs_windows
def test_the_session_and_adapter_expose_no_recorder() -> None:
    public = {name for name in dir(WriteHandoffAdapter) if not name.startswith("_")}
    assert public == {"implement"}
    assert "_recorder" in WriteHandoffAdapter.__slots__
    assert not hasattr(IntegrationSession, "recorder")


@needs_windows
def test_a_report_without_proven_write_evidence_never_returns(w: W) -> None:
    chain = executing(w)
    ticket = ticket_for(w, chain)
    before = snapshot(w.store)
    for report in (fixed_report(chain), ImplementationReport(step_contract_sha256=chain.contract.sha256, attempt=1,
                                                             summary="I wrote it.", claims=("tests pass",))):
        with pytest.raises(AuthorityRefusedError, match="execution claim and authority observation"):
            returned(w, chain, ticket, report)
    assert snapshot(w.store) == before


@needs_windows
def test_with_proven_evidence_only_the_fixed_report_returns(w: W) -> None:
    chain = executing(w)
    ticket = ticket_for(w, chain)
    x_step(w, ticket)
    implement(w, chain, ticket)
    other = ImplementationReport(step_contract_sha256=chain.contract.sha256, attempt=1, summary="Done, verified.")
    with pytest.raises(AuthorityRefusedError, match="fixed write-handoff report"):
        returned(w, chain, ticket, other)
    assert returned(w, chain, ticket, fixed_report(chain)).current_state == StepState.VERIFYING.value


@needs_windows
def test_the_adapter_refuses_a_contract_or_attempt_other_than_the_ticket_s(w: W) -> None:
    chain = executing(w)
    ticket = ticket_for(w, chain)
    contract = w.store.get_step_contract(chain.contract.sha256)
    with pytest.raises(ValueError):
        w.session.implementer.implement(step_contract=contract, attempt=2, dispatch=ticket)
    with pytest.raises(TypeError):
        w.session.implementer.implement(step_contract=contract, attempt=1, dispatch=ticket.model_dump())
    assert w.handoff_dirs() == [] and intent_state(w) is None


@needs_windows
def test_a_non_implementer_or_stale_ticket_hands_off_nothing(w: W) -> None:
    chain = executing(w)
    ticket = ticket_for(w, chain)
    stale = ticket.model_copy(update={"state_version": ticket.state_version + 1})
    with pytest.raises(AuthorityRefusedError):
        w.store._perform_write_handoff(w.session.implementer._recorder._key, stale)
    assert w.handoff_dirs() == [] and intent_state(w) is None


# =============================================================================
# 7. duplicate, concurrent and restarted attempts
# =============================================================================


@needs_windows
def test_a_second_handoff_for_the_same_ticket_is_refused(w: W) -> None:
    chain = executing(w)
    ticket = ticket_for(w, chain)
    x_step(w, ticket)
    implement(w, chain, ticket)
    dirs = w.handoff_dirs()
    with pytest.raises(AuthorityRefusedError, match="already"):
        implement(w, chain, ticket)
    assert w.handoff_dirs() == dirs


@needs_windows
def test_a_second_session_cannot_claim_the_spent_approval_concurrently(w: W) -> None:
    chain = executing(w)
    ticket = ticket_for(w, chain)
    handoff, outbox = ticket_dirs(w, ticket)
    outcomes = []

    def second_session() -> None:
        try:
            open_integration_session_from_facts(w.root, w.world, clock=w.clock, files=w.files,
                                                waiter=FakeWaiter()).close()
            outcomes.append("opened")
        except StoreLockedError:
            outcomes.append("locked")

    def action() -> None:
        second_session()  # while A waits for the human, nothing else can hold the store
        deliver(outbox, run_frozen_writer(handoff))

    second_session()
    w.waiter.on_sleep = action
    implement(w, chain, ticket)
    assert outcomes == ["locked", "locked"] and intent_state(w) == "completed"
    assert w.handoff_dirs() == sorted([handoff.name, outbox.name])
    # And a session that does get the store must recover() first, which reduces the step.
    w.reopen()
    with pytest.raises(StateUntrustedError):
        w.store._perform_write_handoff(w.session.implementer._recorder._key, ticket)


@needs_windows
def test_racing_intent_claims_spend_the_approval_once(w: W) -> None:
    """A second claim lands while the first is taking M0: the first's write
    transaction re-checks everything and refuses, so the approval is spent
    once and only one handoff can ever be published."""
    chain = executing(w)
    ticket = ticket_for(w, chain)
    raced = []

    def race() -> None:
        raced.append(w.store._claim_write_intent(w.session.implementer._recorder._key, ticket).manifest_sha256)

    w.files.before_read["tax.py"] = race
    with pytest.raises(AuthorityRefusedError, match="already has a write intent|already spent"):
        implement(w, chain, ticket)
    assert len(raced) == 1
    assert len(rows(w, "write_intents")) == 1
    assert rows(w, "exact_diff_approvals")[0]["consumed_by_ticket_id"] == ticket.ticket_id
    assert w.handoff_dirs() == []


@needs_windows
def test_after_recovery_nothing_can_hand_off_or_dispatch_again(w: W) -> None:
    chain = executing(w)
    ticket = ticket_for(w, chain)
    x_step(w, ticket, write=False, complete=False)
    with pytest.raises(WriteHandoffRefusedError):
        implement(w, chain, ticket)
    w.reopen()
    w.store.recover(chain.project.project_run_id)
    step = w.store.get_step_run(chain.step.step_run_id)
    assert step.state is StepState.RECOVERY_REQUIRED
    with pytest.raises(AuthorityRefusedError):
        implement(w, chain, ticket)
    with pytest.raises(TransitionRefused):
        w.store.issue_dispatch_ticket(step.step_run_id, role="implementer", expected_state_version=step.state_version)
    with pytest.raises(TransitionRefused):
        w.store.apply_step_transition(step.step_run_id, step_request(step, StepEvent.BEGIN_ATTEMPT))
    assert len([d for d in w.handoff_dirs() if d.startswith("handoff-")]) == 1


# =============================================================================
# 8. crash at every durable point: no retry, no second write
# =============================================================================

CRASH_POINTS = [
    ("INSERT INTO authority_observations", 0, False),   # M0 row
    ("INSERT INTO write_intents", 0, False),
    ("UPDATE exact_diff_approvals", 0, False),
    ("INSERT INTO execution_handoffs", 0, False),
    ("INSERT INTO execution_handoffs", 0, True),         # the intent transaction's last statement
    ("UPDATE execution_handoffs", 0, False),            # publication record
    ("INSERT INTO authority_observations", 1, False),   # M1 row
    ("INSERT INTO execution_claims", 0, False),
    ("UPDATE write_intents", 0, False),
    ("INSERT INTO write_evidence", 0, False),
    ("INSERT INTO write_evidence", 0, True),
]


@needs_windows
@pytest.mark.parametrize("needle, skip, after", CRASH_POINTS)
def test_a_crash_in_the_write_handoff_never_resumes_and_never_writes_twice(w: W, needle, skip, after) -> None:
    chain = executing(w)
    ticket = ticket_for(w, chain)
    x_step(w, ticket)
    proxy = crash_at(w.store, needle, after=after, skip=skip)
    with pytest.raises(SimulatedCrash):
        implement(w, chain, ticket)
    assert not proxy.armed
    w.close()
    store = w.open()
    rep = store.recover(chain.project.project_run_id)
    assert rep.integrity_ok, rep.integrity_issues
    assert store.get_step_run(chain.step.step_run_id).state is StepState.RECOVERY_REQUIRED
    intents = rows(w, "write_intents")
    spent = rows(w, "exact_diff_approvals")[0]["consumed_by_ticket_id"]
    assert (spent is None) == (not intents)  # the approval is spent iff the intent is durable
    assert len([d for d in w.handoff_dirs() if d.startswith("handoff-")]) <= 1
    with pytest.raises(AuthorityRefusedError):
        implement(w, chain, ticket)
    assert w.target().read_text(encoding="utf-8") in (ORIGINAL_TEXT, PROPOSED_TEXT)


@needs_windows
@pytest.mark.parametrize("where", ["handoff directory", "handoff file", "outbox directory", "waiting", "claim read"])
def test_a_crash_around_publication_or_reception_leaves_recovery_required(w: W, where, monkeypatch) -> None:
    chain = executing(w)
    ticket = ticket_for(w, chain)
    x_step(w, ticket)

    def crash(*args, **kwargs):
        raise SimulatedCrash(where)

    if where == "handoff directory":
        original = w.files.create_directory
        monkeypatch.setattr(w.files, "create_directory",
                            lambda path, sd: crash() if "handoff-" in path else original(path, sd))
    elif where == "handoff file":
        monkeypatch.setattr(w.files, "create_file", crash)
    elif where == "outbox directory":
        original = w.files.create_directory
        monkeypatch.setattr(w.files, "create_directory",
                            lambda path, sd: crash() if "outbox-" in path else original(path, sd))
    elif where == "waiting":
        w.waiter.on_sleep = crash
    else:
        w.files.before_read[claim_receiver.STDOUT_NAME] = crash
    with pytest.raises(SimulatedCrash):
        implement(w, chain, ticket)
    w.reopen()
    rep = w.store.recover(chain.project.project_run_id)
    assert rep.integrity_ok, rep.integrity_issues
    assert w.store.get_step_run(chain.step.step_run_id).state is StepState.RECOVERY_REQUIRED
    assert intent_state(w) == "pending"
    with pytest.raises(AuthorityRefusedError):
        implement(w, chain, ticket)
    assert len([d for d in w.handoff_dirs() if d.startswith("handoff-")]) <= 1


@needs_windows
@pytest.mark.parametrize("needle", ["INSERT INTO transitions", "UPDATE dispatch_tickets", "COMMIT"])
def test_a_crash_while_recording_the_implementation_returns_nothing(w: W, needle) -> None:
    chain = executing(w)
    ticket = ticket_for(w, chain)
    x_step(w, ticket)
    report = implement(w, chain, ticket)
    crash_at(w.store, needle)
    with pytest.raises(SimulatedCrash):
        returned(w, chain, ticket, report.output)
    w.reopen()
    rep = w.store.recover(chain.project.project_run_id)
    assert rep.integrity_ok, rep.integrity_issues
    assert w.store.get_step_run(chain.step.step_run_id).state is StepState.RECOVERY_REQUIRED
    assert StepEvent.IMPLEMENTATION_RETURNED.value not in [
        r.event for r in w.store.transitions_for(chain.step.step_run_id)]


# =============================================================================
# 9. the tamper matrix: every S3 record re-proves, or the run is untrusted
# =============================================================================

def _replace_blob(w: W, kind: str, column_sql: str) -> None:
    conn = sqlite3.connect(w.root.store_path)
    sha = conn.execute(column_sql).fetchone()[0]
    conn.close()
    path = Path(w.root.path, "evidence", kind, sha)
    os.chmod(path, 0o666)
    path.write_bytes(path.read_bytes() + b" ")


S3_TAMPERS = {
    "intent state": "UPDATE write_intents SET state = 'refused'",
    "intent artifact": "UPDATE write_intents SET approved_diff_artifact_sha256 = '" + "9" * 64 + "'",
    "approval unspent": "UPDATE exact_diff_approvals SET consumed_by_ticket_id = NULL",
    "approval artifact": "UPDATE exact_diff_approvals SET approved_diff_artifact_sha256 = '" + "9" * 64 + "'",
    "approval attestation": "UPDATE approval_challenges_v2 SET attestation = replace(attestation, 'alice', 'alicf') "
                            "WHERE consumed_by LIKE 'exact_diff:%'",
    "request config": "UPDATE exact_diff_requests SET project_config_sha256 = '" + "9" * 64 + "'",
    "m0 target": "UPDATE authority_observations SET target_sha256 = '" + "9" * 64 + "' WHERE kind = 'm0'",
    "m1 swapped for m0": "UPDATE write_evidence SET m1_observation_id = m0_observation_id",
    "m1 removed": "DELETE FROM authority_observations WHERE kind = 'm1'",
    "an m2 observation": "INSERT INTO authority_observations SELECT 'ff' || substr(observation_id, 3), ticket_id, "
                         "'m2', target_sha256, head_oid, git_control_sha256, manifest_sha256, entry_count, "
                         "provenance, observed_at FROM authority_observations WHERE kind = 'm1'",
    "claim shape": "UPDATE execution_claims SET shape = 'review-packet'",
    "claim digest": "UPDATE execution_claims SET claim_sha256 = '" + "9" * 64 + "'",
    "claim removed": "DELETE FROM execution_claims",
    "handoff unpublished": "UPDATE execution_handoffs SET handoff_directory_identity = NULL, "
                           "outbox_directory_identity = NULL, published_at = NULL",
    "evidence removed": "DELETE FROM write_evidence",
    "activation git digest": "UPDATE activation_observations SET git_control_sha256 = '" + "9" * 64 + "'",
    "activation observation removed": "DELETE FROM activation_observations",
    "verification evidence row": "INSERT INTO verification_evidence_v2 VALUES ('x', 'x', 1, 'x', 'x', 'x', 'x', 'x', "
                                 "'verified', 'execution_claim', 'x')",
    "ticket answered twice": "UPDATE dispatch_tickets SET role = 'verifier'",
}
BLOB_TAMPERS = {
    "artifact blob": ("approved-diff", "SELECT approved_diff_artifact_sha256 FROM exact_diff_approvals"),
    "config blob": ("config", "SELECT project_config_sha256 FROM exact_diff_requests"),
    "claim blob": ("claims", "SELECT claim_sha256 FROM execution_claims"),
    "m1 manifest": ("observations", "SELECT manifest_sha256 FROM authority_observations WHERE kind = 'm1'"),
}


@needs_windows
@pytest.mark.parametrize("name", list(S3_TAMPERS) + list(BLOB_TAMPERS))
def test_a_tampered_s3_record_makes_the_run_untrusted(w: W, name) -> None:
    chain = executing(w)
    ticket = ticket_for(w, chain)
    x_step(w, ticket)
    returned(w, chain, ticket, implement(w, chain, ticket).output)
    w.close()
    if name in BLOB_TAMPERS:
        _replace_blob(w, *BLOB_TAMPERS[name])
    else:
        conn = sqlite3.connect(w.root.store_path)
        conn.execute("PRAGMA ignore_check_constraints = ON")
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute(S3_TAMPERS[name])
        conn.commit()
        conn.close()
    store = w.open()
    report = store.recover(chain.project.project_run_id)
    assert not report.integrity_ok, name
    with pytest.raises(StateUntrustedError):
        store.get_step_run(chain.step.step_run_id)


@needs_windows
def test_revoking_the_approver_untrusts_the_write_and_refuses_a_pending_intent(w: W) -> None:
    chain = executing(w)
    ticket = ticket_for(w, chain)
    _set_alice(w, revoked=True)
    with pytest.raises((AuthorityRefusedError, StateUntrustedError)):
        implement(w, chain, ticket)
    assert w.handoff_dirs() == [] and intent_state(w) is None
    report = w.store.recover(chain.project.project_run_id)  # revocation untrusts the recorded approval
    assert not report.integrity_ok
    _set_alice(w, revoked=False)  # the escalation persists
    assert w.store.inspect_step_run(chain.step.step_run_id).columns["state"] == StepState.HUMAN_REQUIRED.value


# =============================================================================
# 10. DL-3 → DL-2 enforces the same requirements
# =============================================================================


class Ports:
    def __init__(self, implementer) -> None:
        self.implementer = implementer
        self.calls: list[str] = []

    def role_ports(self) -> RolePorts:
        return RolePorts(planner=self, tester=self, implementer=self.implementer, verifier=self, reviewer=self)

    def propose_step_contract(self, **kwargs):
        return make_proposal()

    def propose_tests(self, **kwargs):
        return ()

    def verify(self, **kwargs):
        self.calls.append("verifier")
        raise AssertionError("S4 does not exist: the verifier has no adapter")

    def review(self, **kwargs):
        self.calls.append("reviewer")
        raise AssertionError("never dispatched")

    def decide_step(self, **kwargs):
        self.calls.append("planner")
        raise AssertionError("never dispatched")


def _outer(w: W, chain: Chain, implementer):
    ports = Ports(implementer)
    outcome = ProjectOuterLoop(w.store, ports.role_ports()).run(
        project_run=w.store.get_project_run(chain.project.project_run_id),
        project_contract=chain.pc, execution_plan=chain.plan)
    return ports, outcome


def _planned(w: W) -> Chain:
    chain = approved(w)
    chain.contract = w.store.issue_authorized_step_contract(make_proposal(), execution_plan_sha256=chain.plan.sha256)
    chain.project = w.store.create_project_run(project_contract_sha256=chain.pc.sha256,
                                               execution_plan_sha256=chain.plan.sha256)
    chain.step = w.store.create_step_run(project_run_id=chain.project.project_run_id,
                                         step_contract_sha256=chain.contract.sha256)
    return chain


@needs_windows
def test_the_orchestration_path_records_the_proven_write_and_stops_at_verification(w: W) -> None:
    chain = _planned(w)

    def action() -> None:
        handoffs = [d for d in w.handoff_dirs() if d.startswith("handoff-")]
        ticket_id = handoffs[0].split("-", 1)[1]
        handoff, outbox = exchange.ticket_directories(w.exchange, ticket_id)
        deliver(Path(outbox), run_frozen_writer(Path(handoff)))

    w.waiter.on_sleep = action
    ports, _ = _outer(w, chain, w.session.implementer)
    step = w.store.get_step_run(chain.step.step_run_id)
    events = [r.event for r in w.store.transitions_for(step.step_run_id)]
    assert StepEvent.IMPLEMENTATION_RETURNED.value in events
    assert ports.calls == ["verifier"]
    assert step.state is StepState.RECOVERY_REQUIRED  # S4 does not exist yet
    assert intent_state(w) == "completed"
    assert w.target().read_text(encoding="utf-8") == PROPOSED_TEXT
    # A second DL-3 call dispatches nothing and hands off nothing.
    dirs = w.handoff_dirs()
    again, _ = _outer(w, chain, w.session.implementer)
    assert again.calls == [] and w.handoff_dirs() == dirs


@needs_windows
def test_the_orchestration_path_enforces_m0_like_the_direct_path(w: W) -> None:
    chain = _planned(w)
    _m0_target(w)
    ports, _ = _outer(w, chain, w.session.implementer)
    step = w.store.get_step_run(chain.step.step_run_id)
    assert step.state is StepState.RECOVERY_REQUIRED and ports.calls == []
    assert w.handoff_dirs() == [] and intent_state(w) is None
    assert rows(w, "exact_diff_approvals")[0]["consumed_by_ticket_id"] is None


@needs_windows
def test_the_orchestration_path_reduces_an_unproven_write_to_recovery_required(w: W) -> None:
    chain = _planned(w)
    ports, _ = _outer(w, chain, w.session.implementer)  # nobody answers: the deadline passes
    step = w.store.get_step_run(chain.step.step_run_id)
    assert step.state is StepState.RECOVERY_REQUIRED
    assert StepEvent.IMPLEMENTATION_RETURNED.value not in [r.event for r in w.store.transitions_for(step.step_run_id)]
    assert ports.calls == [] and intent_state(w) == "refused"


@needs_windows
def test_the_orchestration_path_with_a_forged_implementer_reaches_no_trusted_state(w: W) -> None:
    chain = _planned(w)

    class Forger:
        def implement(self, *, step_contract, attempt, dispatch=None):
            return bind_role_output(dispatch, ImplementationReport(
                step_contract_sha256=step_contract.sha256, attempt=attempt, summary=WRITE_HANDOFF_REPORT_SUMMARY))

    ports, _ = _outer(w, chain, Forger())
    step = w.store.get_step_run(chain.step.step_run_id)
    assert step.state is StepState.RECOVERY_REQUIRED and ports.calls == []
    assert w.handoff_dirs() == [] and rows(w, "exact_diff_approvals")[0]["consumed_by_ticket_id"] is None


# =============================================================================
# 11. production primitives on this host
# =============================================================================


def _current_user_sid() -> str:
    from ai_dev_orchestrator.integration.windows_security import WindowsSecurityFacts

    return WindowsSecurityFacts().current_token().user_sid


@needs_windows
def test_the_production_files_create_directories_with_exactly_the_requested_dacl(tmp_path: Path) -> None:
    files = WindowsAuthorityFiles()
    me = _current_user_sid()
    for name, acl in (("handoff", exchange.handoff_dacl(me, X)), ("outbox", exchange.outbox_dacl(me, X, O))):
        path = str(tmp_path / name)
        files.create_directory(path, build_security_descriptor(me, acl, protected=True))
        facts = files.object_facts(path)
        sd = parse_security_descriptor(facts.security_descriptor)
        assert sd.owner == me and sd.protected and sd.dacl == acl, name
        assert exchange.verify_directory(files, path, me, acl, name)
        with pytest.raises(FileExistsError):
            files.create_directory(path, build_security_descriptor(me, acl, protected=True))


@needs_windows
def test_the_production_read_denies_write_sharing_and_creation_is_exclusive(tmp_path: Path) -> None:
    files = WindowsAuthorityFiles()
    path = str(tmp_path / "stdout.json")
    files.create_file(path, b"{}")
    with pytest.raises(FileExistsError):
        files.create_file(path, b"{}")
    facts, data = files.read_file(path, 10)
    assert data == b"{}" and facts.link_count == 1 and not facts.is_reparse_point
    with open(path, "ab"):
        with pytest.raises(OSError, match="32"):
            files.read_file(path, 10)


# =============================================================================
# 12. static boundaries
# =============================================================================

_PACKAGE = Path(integration.__file__).resolve().parent
_S3 = ("authority_files.py", "claim_readers.py", "claim_receiver.py", "exchange.py", "state_blobs.py",
       "workspace_observation.py", "write_handoff.py")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
    return names


def test_s3_modules_have_no_execution_network_model_git_or_harness_surface() -> None:
    forbidden = {"subprocess", "socket", "httpx", "requests", "aiohttp", "urllib", "http", "asyncio",
                 "multiprocessing", "shutil", "tempfile", "winreg", "threading"}
    harness = ("ai_dev_orchestrator.llm", "ai_dev_orchestrator.github", "ai_dev_orchestrator.review",
               "ai_dev_orchestrator.verification", "ai_dev_orchestrator.file_editing",
               "ai_dev_orchestrator.supervised_implementer", "ai_dev_orchestrator.workspace",
               "ai_dev_orchestrator.diff_proposal", "ai_dev_orchestrator.handoff", "ai_dev_orchestrator.plan",
               "ai_dev_orchestrator.cli", "ai_dev_orchestrator.config_loader")
    names_forbidden = {"Popen", "max_tokens", "environ", "getenv", "putenv", "system", "unlink", "remove", "rmdir",
                       "rename", "replace_file", "rmtree", "chmod", "SetSecurityInfo", "SetFileSecurityW",
                       "SetNamedSecurityInfoW", "DeleteFileW", "MoveFileW", "MoveFileExW", "ReplaceFileW",
                       "CreateProcessW", "ShellExecuteW"}
    for name in _S3 + ("integration_store.py", "integration_session.py"):
        path = _PACKAGE / name
        imported = _imports(path)
        assert not {m.split(".")[0] for m in imported} & forbidden, (name, imported)
        assert not [m for m in imported if m.startswith(harness)], (name, imported)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert not names & names_forbidden, (name, names & names_forbidden)
    # ctypes only where the two creating calls live; os only where A touches files.
    for name in _S3:
        imported = {m.split(".")[0] for m in _imports(_PACKAGE / name)}
        assert ("ctypes" in imported) == (name == "authority_files.py"), name
        assert ("os" in imported) <= (name in ("authority_files.py", "state_blobs.py")), name


def test_importing_the_a_side_loads_no_harness_git_or_network_module() -> None:
    code = (
        "import sys\n"
        "import ai_dev_orchestrator.integration.integration_session\n"
        "bad = [m for m in sys.modules if m.split('.')[0] in ('subprocess', 'socket', 'httpx') or m.startswith((\n"
        "  'ai_dev_orchestrator.file_editing', 'ai_dev_orchestrator.workspace', 'ai_dev_orchestrator.llm',\n"
        "  'ai_dev_orchestrator.verification', 'ai_dev_orchestrator.review', 'ai_dev_orchestrator.diff_proposal'))]\n"
        "print(bad)\n"
    )
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, check=True,
                         env={**os.environ, "PYTHONPATH": str(_PACKAGE.parent.parent)}).stdout.strip()
    assert out == "[]", out


def test_the_mirror_readers_restate_the_shipped_models() -> None:
    from ai_dev_orchestrator.diff_proposal.models import DiffProposalArtifact, DiffProposalFileChange
    from ai_dev_orchestrator.file_editing.models import (
        REQUIRED_DIFF_EDIT_APPROVAL_TEXT,
        ApprovedDiffProposalArtifact,
        DiffEditApproval,
    )
    from ai_dev_orchestrator.file_editing.writer import (
        WORKSPACE_WRITE_MODE,
        WORKSPACE_WRITE_SCHEMA_VERSION,
        WorkspaceWriteReport,
        WorkspaceWriteTarget,
    )
    from ai_dev_orchestrator.handoff.models import ApprovedL1PlanArtifact

    assert claim_readers.APPROVED_DIFF_FIELDS == set(ApprovedDiffProposalArtifact.model_fields)
    assert all(f.is_required() for f in ApprovedDiffProposalArtifact.model_fields.values())
    assert claim_readers.DIFF_EDIT_APPROVAL_FIELDS == set(DiffEditApproval.model_fields)
    assert claim_readers.DIFF_PROPOSAL_FIELDS == set(DiffProposalArtifact.model_fields)
    assert claim_readers.DIFF_PROPOSAL_REQUIRED == {k for k, f in DiffProposalArtifact.model_fields.items()
                                                    if f.is_required()}
    assert claim_readers.DIFF_CHANGE_FIELDS == set(DiffProposalFileChange.model_fields)
    assert claim_readers.DIFF_CHANGE_REQUIRED == {k for k, f in DiffProposalFileChange.model_fields.items()
                                                  if f.is_required()}
    assert claim_readers.APPROVED_PLAN_FIELDS == set(ApprovedL1PlanArtifact.model_fields)
    assert claim_readers.WRITE_RESULT_FIELDS == set(WorkspaceWriteReport.model_fields)
    assert all(f.is_required() for f in WorkspaceWriteReport.model_fields.values())
    assert claim_readers.WRITE_TARGET_FIELDS == set(WorkspaceWriteTarget.model_fields)
    assert (claim_readers.WRITE_RESULT_SCHEMA_VERSION, claim_readers.WRITE_RESULT_MODE) == (
        WORKSPACE_WRITE_SCHEMA_VERSION, WORKSPACE_WRITE_MODE)
    assert REQUIRED_DIFF_EDIT_APPROVAL_TEXT == "I approve this diff proposal for workspace file editing"
    from ai_dev_orchestrator.plan.models import L1Plan

    assert L1Plan.model_fields["automation_level"].default == "L1"
    assert L1Plan.model_fields["requires_human_approval"].default is True


def test_the_mirror_reader_agrees_with_the_frozen_parser_on_the_fixture() -> None:
    from ai_dev_orchestrator.file_editing.models import parse_approved_diff_proposal_artifact

    artifact = _artifact(approval=approval_block())
    data = json.dumps(artifact).encode("utf-8")
    shipped = parse_approved_diff_proposal_artifact(data.decode("utf-8"))
    mirrored = claim_readers.read_approved_diff(data)
    change = shipped.diff_proposal.changes[0]
    assert (mirrored.path, mirrored.pre_image_sha256, mirrored.post_image_sha256) == (
        change.path, change.pre_image_sha256, change.post_image_sha256)
    assert (mirrored.approved_by, mirrored.approved_at) == (shipped.approval.approved_by, shipped.approval.approved_at)
    assert mirrored.post_image_sha256 == _sha(PROPOSED_TEXT)


def test_no_s3_public_api_accepts_bytes_or_authority_evidence() -> None:
    import inspect

    for owner in (IntegrationStore, IntegrationSession, WriteHandoffAdapter):
        for name, member in inspect.getmembers(owner, callable):
            if name.startswith("_"):
                continue
            for parameter in inspect.signature(member).parameters:
                lowered = parameter.lower()
                assert not any(word in lowered for word in (
                    "claim", "observation", "evidence", "stdout", "manifest", "recorder", "report", "data",
                    "digest", "sha256_of", "bytes")), (owner.__name__, name, parameter)
