"""DL-4B S4 — the VERIFYING-stage execution claim adapter and M2, offline.

Every state root, inbox, exchange root and clone is a real directory under
pytest ``tmp_path``, built exactly as S3's harness builds them (synthetic Git
clone detached at its commit, S0/S1 synthetic Windows worlds, the production
``WindowsAuthorityFiles`` with synthetic owners and descriptors).

The human's two X-side steps are simulated inside the test by running the
frozen, unchanged commands in-process: ``l2-apply-approved-file-edit``
(through S3's helpers) and then ``l2-review-approved-file-edit``, whose
reviewer environment reader and network transport factory are replaced by a
literal mapping and an ``httpx.MockTransport``. The verification program is a
synthetic script under ``tmp_path``. No socket, no model, no endpoint, no
credential and no real project is involved. A claim's origin is never trusted
anyway, so forged claims are delivered the same way.

Sections: harness; the claim reader; the review handoff and evidence; M2;
claim shapes and forgeries through the store; the FD-17 protocol; tickets
and caller-supplied authority; duplicates and stale outboxes; crashes; the
tamper matrix; DL-3 → DL-2; static boundaries.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import typing
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from test_dl4b_s0_identity_boundary import A, O
from test_dl4b_s2_integration_store import SimulatedCrash, crash_at, make_proposal, snapshot, step_request
from test_dl4b_s3_write_handoff import (
    APPROVED_AT,
    ARTIFACT_NAME,
    CONFIG_NAME,
    Chain,
    FakeWaiter,
    TestFiles,
    W,
    _planned,
    approval_block,
    deliver,
    executing,
    fixed_report,
    git,
    implement,
    returned,
    rows,
    run_frozen_writer,
    s3_world,
    ticket_dirs,
    ticket_for,
    x_step,
)
from typer.testing import CliRunner

import ai_dev_orchestrator.integration as integration
from ai_dev_orchestrator import cli
from ai_dev_orchestrator.cli import app
from ai_dev_orchestrator.control_plane import (
    AidoStateRoot,
    AuthorityRefusedError,
    ProjectOuterLoop,
    RolePorts,
    StateUntrustedError,
    StepEvent,
    StepState,
    TransitionRefused,
    VerificationObservation,
    bind_role_output,
)
from ai_dev_orchestrator.control_plane.authority import EvidenceRefusedError, verification_outcome_from_evidence
from ai_dev_orchestrator.control_plane.integration_records import REVIEW_CLAIM_OUTCOMES
from ai_dev_orchestrator.control_plane.models import ReviewVerdict
from ai_dev_orchestrator.integration import claim_readers, claim_receiver, exchange
from ai_dev_orchestrator.integration import workspace_observation as wo
from ai_dev_orchestrator.integration.claim_readers import ClaimReadError
from ai_dev_orchestrator.integration.execution_claim import ExecutionClaimAdapter, mint_execution_claim_adapter
from ai_dev_orchestrator.integration.integration_session import IntegrationSession, open_integration_session_from_facts
from ai_dev_orchestrator.integration.integration_store import IntegrationStore, VerificationClaimRefusedError
from tests.test_cli_l2_apply_approved_file_edit import (
    ORIGINAL_TEXT,
    PROPOSED_TEXT,
    SECOND_TARGET,
    TARGET,
    _artifact,
    _make_repo,
    _sha,
)

WINDOWS = sys.platform == "win32"
needs_windows = pytest.mark.skipif(not WINDOWS, reason="real Windows file handles and a synthetic Windows boundary")
runner = CliRunner()

REVIEWER_MODEL = "fake-reviewer-model"
FAKE_ENV = {
    "AIDO_LITELLM_BASE_URL": "http://fake-litellm.invalid/v1",
    "AIDO_LITELLM_API_KEY": "fake-key-not-a-real-secret",
    # Required by the shared client; the project config's model still overrides it.
    "AIDO_LITELLM_DEFAULT_MODEL": "fake-env-default-model",
    "AIDO_LITELLM_TIMEOUT_SECONDS": "5",
    "AIDO_LITELLM_MAX_RETRIES": "0",
}
APPROVE_REVIEW = json.dumps({
    "verdict": "approve", "summary": "The change is small and in scope.", "findings": [],
    "residual_risks": [], "human_notes": [],
})
CHANGES_REVIEW = json.dumps({
    "verdict": "changes_requested", "summary": "Non-numeric input is not handled.",
    "findings": [{"severity": "major", "category": "correctness", "line": 2,
                  "message": "A non-numeric amount raises.", "suggested_action": "Validate the amount."}],
    "residual_risks": [], "human_notes": [],
})

PASSING = "import sys\nsys.stdout.write('3 passed\\n')\nsys.exit(0)\n"
FAILING = "import sys\nsys.stderr.write('E assert 1 == 2\\n')\nsys.exit(1)\n"
DIRTYING = "open('stray_artifact.txt', 'w').write('made by the verification')\n"
IGNORED_CACHE = "open('build.cache', 'w').write('an ignored cache')\n"

CONFIG_TEMPLATE = """\
project_id: demo_project
display_name: Demo Project
repo:
  workspace_path: {workspace}
  github_repo: demo/widgets
  default_base_branch: main
  branch_prefix: ai/demo
workspace_policy:
  deny_outside_workspace: true
  allow_symlinks: false
  max_changed_files: 20
workspace_write:
  enabled: true
  max_file_bytes: 200000
controlled_verification:
  enabled: {verify}
  executable: {executable}
  args: {args}
  timeout_seconds: 60
  max_output_bytes: 200000
controlled_review:
  enabled: {review}
  provider: "litellm"
  model: "{model}"
  endpoint:
    scheme: "http"
    host: "fake-litellm.invalid"
    port: 80
    base_path: "/v1"
allowed_paths:
  - "src/**"
  - "tests/**"
  - "docs/allowed/**"
protected_paths:
  - "src/billing/protected_*.py"
forbidden_paths:
  - ".git/**"
  - "secrets/**"
"""


# =============================================================================
# harness
# =============================================================================


class Reviewer:
    """The mocked reviewer endpoint: one canned reply, every request counted."""

    def __init__(self) -> None:
        self.content = APPROVE_REVIEW
        self.requests = 0
        self.fail = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests += 1
        if self.fail:
            raise httpx.ConnectError("simulated connection failure")
        return httpx.Response(200, json={
            "model": REVIEWER_MODEL,
            "choices": [{"message": {"role": "assistant", "content": self.content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        })


class QueueWaiter(FakeWaiter):
    """Runs one queued X-side step per sleep of A, in order."""

    def __init__(self) -> None:
        super().__init__()
        self.queue: list = []

    def sleep(self, seconds: float) -> None:
        self.sleeps += 1
        self.now += seconds
        if self.queue:
            self.queue.pop(0)()


@dataclass
class V(W):
    script: Path | None = None
    reviewer: Reviewer = field(default_factory=Reviewer)

    def body(self, text: str) -> None:
        self.script.write_text(text, encoding="utf-8")

    def other_file(self) -> Path:
        return self.repo / SECOND_TARGET


def write_config(path: Path, clone: str, script: Path, *, verify: bool = True, review: bool = True) -> bytes:
    path.write_text(CONFIG_TEMPLATE.format(
        workspace=json.dumps(clone), verify=str(verify).lower(), executable=json.dumps(sys.executable),
        args=json.dumps([str(script)]), review=str(review).lower(), model=REVIEWER_MODEL,
    ), encoding="utf-8")
    return path.read_bytes()


def make_v(tmp_path: Path, *, review: bool = True, verify: bool = True) -> V:
    for name in ("state", "inbox", "exchange", "scripts"):
        (tmp_path / name).mkdir()
    repo = _make_repo(tmp_path)
    (repo / ".gitignore").write_text("*.cache\n", encoding="utf-8")
    git(repo, "add", ".gitignore")
    git(repo, "commit", "-q", "-m", "ignore caches")
    git(repo, "checkout", "-q", "--detach")
    head = (repo / ".git" / "HEAD").read_text(encoding="ascii").strip()
    root = AidoStateRoot.create(tmp_path / "state")
    clone = os.path.realpath(repo)
    inbox, exchange_root = os.path.realpath(tmp_path / "inbox"), os.path.realpath(tmp_path / "exchange")
    script = tmp_path / "scripts" / "verify.py"
    script.write_text(PASSING, encoding="utf-8")
    v = V(tmp_path, s3_world(root.path, clone, inbox, exchange_root), _clock(), root, clone, inbox=inbox,
          exchange=exchange_root, repo=Path(clone), head=head, files=TestFiles(inbox, exchange_root),
          waiter=QueueWaiter(), script=script)
    v.config_bytes = write_config(Path(inbox) / CONFIG_NAME, clone, script, verify=verify, review=review)
    v.artifact = _artifact(approval=approval_block())
    v.put_artifact()
    return v


def _clock():
    from test_dl4b_s1_attestation_verifier import NOW, Clock

    return Clock(NOW)


@pytest.fixture
def review_env(monkeypatch):
    """The frozen review command's two injection points, at module scope, so
    the unchanged command runs as the human would run it."""
    reviewer = Reviewer()
    monkeypatch.setattr(cli, "_read_reviewer_env", lambda provider: dict(FAKE_ENV))
    monkeypatch.setattr(cli, "_build_reviewer_network_transport", lambda: httpx.MockTransport(reviewer.handler))
    return reviewer


@pytest.fixture
def v(tmp_path: Path, review_env):
    if not WINDOWS or shutil.which("git") is None:
        pytest.skip("needs Windows and git")
    harness = make_v(tmp_path)
    harness.reviewer = review_env
    harness.open()
    yield harness
    harness.close()


def run_frozen_review(handoff: Path, *flags: str) -> bytes:
    """The human's second X-side step: the existing, unchanged 5F2E command."""
    result = runner.invoke(app, [
        "l2-review-approved-file-edit",
        "--project-config", str(handoff / exchange.HANDOFF_CONFIG_NAME),
        "--approved-diff-proposal", str(handoff / exchange.HANDOFF_ARTIFACT_NAME),
        *(flags or ("--verify-approved-file-edit", "--real-reviewer")),
    ])
    return result.stdout_bytes


def written(v: V) -> tuple[Chain, object]:
    """Through S3: the approved write handed off, applied by the frozen
    writer, proven, and recorded. The step is at VERIFYING."""
    chain = executing(v)
    ticket = ticket_for(v, chain)
    x_step(v, ticket)
    v.waiter.queue.append(v.waiter.on_sleep)
    v.waiter.on_sleep = None
    returned(v, chain, ticket, implement(v, chain, ticket).output)
    assert v.store.get_step_run(chain.step.step_run_id).state is StepState.VERIFYING
    return chain, ticket


def vticket_for(v: V, chain: Chain):
    step = v.store.get_step_run(chain.step.step_run_id)
    return v.store.issue_dispatch_ticket(step.step_run_id, role="verifier", expected_state_version=step.state_version)


def review_step(v: V, ticket, *, stdout=None, extra=None, complete: bool = True, run: bool = True,
                flags: tuple[str, ...] = ()) -> None:
    """Queue the human's review step for A's next wait. ``stdout`` may be
    bytes, or a function of the frozen command's real stdout; ``extra`` runs
    after the command and before the marker (a surviving X process)."""
    handoff, outbox = ticket_dirs(v, ticket)

    def action() -> None:
        real = run_frozen_review(handoff, *flags) if run else b""
        if extra is not None:
            extra(v)
        data = stdout(real) if callable(stdout) else (real if stdout is None else stdout)
        deliver(outbox, data, complete=complete)

    v.waiter.queue.append(action)


def verify(v: V, chain: Chain, ticket):
    contract = v.store.get_step_contract(chain.contract.sha256)
    return v.session.verifier.verify(step_contract=contract, attempt=ticket.attempt, dispatch=ticket)


def observed(v: V, chain: Chain, bound, *, output: VerificationObservation | None = None):
    step = v.store.get_step_run(chain.step.step_run_id)
    payload = output if output is not None else bound.output
    return v.store.apply_step_transition(
        step.step_run_id, step_request(step, StepEvent.VERIFICATION_OBSERVED, verification=payload),
        role_output=bound if output is None else bind_role_output(_ticket_of(v, bound.ticket_id), output))


def _ticket_of(v: V, ticket_id: str):
    row = v.store._conn.execute("SELECT * FROM dispatch_tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
    return v.store._ticket_from_row(row)


def verified(v: V, **options):
    """Through S4: the review handed off, the frozen review command run, the
    claim and M2 bound, and VERIFICATION_OBSERVED recorded."""
    chain, _ = written(v)
    ticket = vticket_for(v, chain)
    review_step(v, ticket, **options)
    bound = verify(v, chain, ticket)
    observed(v, chain, bound)
    return chain, ticket, bound


def evidence(v: V) -> list[sqlite3.Row]:
    return rows(v, "verification_evidence_v2")


def verifier_rows(v: V, table: str, ticket) -> list[sqlite3.Row]:
    return v.store._conn.execute(f"SELECT * FROM {table} WHERE ticket_id = ?", (ticket.ticket_id,)).fetchall()


def claim_bytes(v: V, ticket) -> bytes:
    sha = verifier_rows(v, "execution_claims", ticket)[0]["claim_sha256"]
    return Path(v.root.path, "evidence", "claims", sha).read_bytes()


# =============================================================================
# 1. the claim reader: every frozen stdout shape, strictly
# =============================================================================


def _frozen_stdout(tmp_path: Path, review_env, body: str, *, content: str = APPROVE_REVIEW,
                   flags: tuple[str, ...] = ()) -> bytes:
    """Run the frozen review command once on a fresh synthetic clone (the
    approved change applied), outside any store."""
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    review_env.content = content
    work = tmp_path / "frozen"
    work.mkdir()
    repo = _make_repo(work)
    (repo / TARGET).write_bytes(PROPOSED_TEXT.encode("utf-8"))
    script = work / "verify.py"
    script.write_text(body, encoding="utf-8")
    inputs = work / "inputs"
    inputs.mkdir()
    write_config(inputs / exchange.HANDOFF_CONFIG_NAME, os.path.realpath(repo), script)
    (inputs / exchange.HANDOFF_ARTIFACT_NAME).write_text(json.dumps(_artifact(approval=approval_block())),
                                                         encoding="utf-8")
    return run_frozen_review(inputs, *flags)


SHAPES = {
    "exit 0 approve": (PASSING, APPROVE_REVIEW, "review-packet", "verified", "approve"),
    "exit 0 changes requested": (PASSING, CHANGES_REVIEW, "review-packet", "verified", "changes_requested"),
    "exit 2": (FAILING, APPROVE_REVIEW, "verification-failed", "verification-failed", None),
    "exit 3": (DIRTYING, APPROVE_REVIEW, "workspace-untrusted", "workspace-state-untrusted", None),
}


@pytest.mark.parametrize("name", list(SHAPES))
def test_the_reader_classifies_every_frozen_stdout_shape(tmp_path: Path, review_env, name) -> None:
    body, content, shape, outcome, verdict = SHAPES[name]
    data = _frozen_stdout(tmp_path, review_env, body, content=content)
    facts = claim_readers.read_review_claim(data)
    assert (facts.shape, facts.outcome, facts.verdict) == (shape, outcome, verdict)
    assert REVIEW_CLAIM_OUTCOMES[facts.shape] == facts.outcome
    assert (facts.path, facts.approved_by, facts.approved_at) == (TARGET, "alice", APPROVED_AT)
    assert facts.post_image_bytes == len(PROPOSED_TEXT.encode("utf-8"))
    assert review_env.requests == (1 if shape == "review-packet" else 0)
    document = json.loads(data)
    report = document["verification"] if shape == "review-packet" else document
    # The outcome agrees with DL-4A's frozen evidence reader on the same facts.
    assert verification_outcome_from_evidence(json.dumps(report).encode("utf-8")) == outcome


@pytest.mark.parametrize("name, flags, fail", [
    ("exit 1 (a refused invocation)", ("--verify-approved-file-edit",), False),
    ("exit 4 (reviewer stage failed)", (), True),
])
def test_exits_1_and_4_print_no_claim(tmp_path: Path, review_env, name, flags, fail) -> None:
    review_env.fail = fail
    data = _frozen_stdout(tmp_path, review_env, PASSING, flags=flags)
    assert data == b""
    with pytest.raises(ClaimReadError) as raised:
        claim_readers.read_review_claim(data)
    assert raised.value.category == "empty"


def _mutated(data: bytes, mutate) -> bytes:
    document = json.loads(data)
    mutate(document)
    return json.dumps(document).encode("utf-8")


def _set(path: tuple, value):
    def mutate(document):
        target = document
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
    return mutate


PACKET_FORGERIES = {
    "embedded run failed, stated verified": (_set(("verification", "execution", "passed"), False),
                                             "outcome_unsupported"),
    "embedded outcome stated failed": (lambda d: (d["verification"].update(outcome="verification-failed"),
                                                  d["verification"]["execution"].update(passed=False)),
                                       "contradictory"),
    "stated verified without passing": (_set(("verification", "outcome"), "verification-failed"),
                                        "outcome_unsupported"),
    "packet target is another path": (_set(("target", "path"), SECOND_TARGET), "contradictory"),
    "packet approver differs": (_set(("approved_by",), "mallory"), "contradictory"),
    "packet identity differs": (_set(("title",), "Another"), "contradictory"),
    "no human decision": (_set(("human_decision_required",), False), "malformed"),
    "unknown verdict": (_set(("review", "verdict"), "merge"), "malformed"),
    "extra packet field": (_set(("auto_merge",), True), "malformed"),
    "extra review field": (_set(("review", "score"), 10), "malformed"),
    "another schema": (_set(("schema_version",), "review-packet.v4"), "unexpected_shape"),
    "create change": (_set(("target", "change_type"), "create"), "malformed"),
    "post image not verified": (_set(("verification", "target", "post_image_verified_before_execution"), False),
                                "malformed"),
}


@pytest.mark.parametrize("name", list(PACKET_FORGERIES))
def test_a_forged_or_contradictory_packet_is_refused(tmp_path: Path, review_env, name) -> None:
    mutate, category = PACKET_FORGERIES[name]
    data = _mutated(_frozen_stdout(tmp_path, review_env, PASSING), mutate)
    with pytest.raises(ClaimReadError) as raised:
        claim_readers.read_review_claim(data)
    assert raised.value.category == category, raised.value


REPORT_FORGERIES = {
    "a bare verified report": (lambda d: (d.update(outcome="verified"), d["execution"].update(passed=True)),
                               "unexpected_shape"),
    "untrusted facts stated failed": (lambda d: d["workspace_postcondition"].update(head_unchanged=False),
                                      "outcome_unsupported"),
    "a missing field": (lambda d: d.pop("command"), "malformed"),
    "string passed": (_set(("execution", "passed"), "false"), "malformed"),
}


@pytest.mark.parametrize("name", list(REPORT_FORGERIES))
def test_a_forged_bare_report_is_refused(tmp_path: Path, review_env, name) -> None:
    mutate, category = REPORT_FORGERIES[name]
    data = _mutated(_frozen_stdout(tmp_path, review_env, FAILING), mutate)
    with pytest.raises(ClaimReadError) as raised:
        claim_readers.read_review_claim(data)
    assert raised.value.category == category, raised.value


@pytest.mark.parametrize("data", [
    b"\xef\xbb\xbf{}", b"[]", b'{"schema_version": "verification-result.v1", "schema_version": "x"}',
    b'{"a": NaN}', b"{} {}", "{}".encode("utf-16"), b"\xff",
])
def test_bytes_that_are_not_one_strict_json_object_are_refused(data: bytes) -> None:
    with pytest.raises(ClaimReadError):
        claim_readers.read_review_claim(data)


def test_the_review_mirror_restates_the_shipped_models() -> None:
    from ai_dev_orchestrator.review.models import ModelReviewResult
    from ai_dev_orchestrator.review.packet import (
        REVIEW_PACKET_MODE,
        REVIEW_PACKET_SCHEMA_VERSION,
        ReviewPacket,
        ReviewTargetBlock,
    )
    from ai_dev_orchestrator.verification.verifier import VerificationResultReport, VerificationTargetBlock

    assert claim_readers.REVIEW_PACKET_FIELDS == set(ReviewPacket.model_fields)
    assert all(f.is_required() for f in ReviewPacket.model_fields.values())
    assert claim_readers.REVIEW_TARGET_FIELDS == set(ReviewTargetBlock.model_fields)
    assert claim_readers.MODEL_REVIEW_FIELDS == set(ModelReviewResult.model_fields)
    assert set(claim_readers.REVIEW_VERDICTS) == set(typing.get_args(ModelReviewResult.model_fields["verdict"].annotation))
    assert set(claim_readers.REVIEW_VERDICTS) == set(typing.get_args(ReviewVerdict))
    assert claim_readers.VERIFICATION_TARGET_FIELDS == set(VerificationTargetBlock.model_fields)
    assert set(VerificationResultReport.model_fields) == claim_readers.VERIFICATION_RESULT_FIELDS
    assert (claim_readers.REVIEW_PACKET_SCHEMA_VERSION, claim_readers.REVIEW_PACKET_MODE) == (
        REVIEW_PACKET_SCHEMA_VERSION, REVIEW_PACKET_MODE)
    assert set(REVIEW_CLAIM_OUTCOMES.values()) == set(typing.get_args(
        VerificationResultReport.model_fields["outcome"].annotation))


# =============================================================================
# 2. M2, as a pure function of M1 and M2
# =============================================================================


def _obs(tree, *, head="a" * 40, git=(("HEAD", 41, "b" * 64),)) -> wo.Observation:
    return wo._manifest(head, tuple(git), tuple(sorted(tree)), "t.py")


def test_m2_classification_is_a_pure_function_of_m1_and_m2() -> None:
    post = "c" * 64
    m1 = _obs([("t.py", 3, post), ("u.py", 1, "d" * 64)])
    holds = wo.classify_verification(m1, _obs([("t.py", 3, post), ("u.py", 1, "d" * 64), ("x.cache", 1, "e" * 64)]),
                                     target_path="t.py", post_image_sha256=post)
    assert holds.holds and holds.additions == ("x.cache",) and holds.issues == ()
    cases = {
        "target changed": _obs([("t.py", 3, "f" * 64), ("u.py", 1, "d" * 64)]),
        "unrelated changed": _obs([("t.py", 3, post), ("u.py", 2, "9" * 64)]),
        "unrelated removed": _obs([("t.py", 3, post)]),
        "head changed": _obs([("t.py", 3, post), ("u.py", 1, "d" * 64)], head="1" * 40),
        ".git changed": _obs([("t.py", 3, post), ("u.py", 1, "d" * 64)], git=(("HEAD", 41, "2" * 64),)),
    }
    for name, m2 in cases.items():
        result = wo.classify_verification(m1, m2, target_path="t.py", post_image_sha256=post)
        assert not result.holds and result.issues, name
    git_only = wo._manifest("a" * 40, (("HEAD", 41, "b" * 64),), None, None)
    assert not wo.classify_verification(m1, git_only, target_path="t.py", post_image_sha256=post).holds


# =============================================================================
# 3. the review handoff and verification_evidence_v2
# =============================================================================


@needs_windows
def test_a_passing_review_claim_binds_m2_and_advances_to_reviewing(v: V) -> None:
    chain, write_ticket = written(v)
    ticket = vticket_for(v, chain)
    review_step(v, ticket)
    handoff, outbox = ticket_dirs(v, ticket)
    bound = verify(v, chain, ticket)
    # The handoff held exactly the write intent's approved artifact and config bytes.
    write_handoff, _ = ticket_dirs(v, write_ticket)
    for name in (exchange.HANDOFF_ARTIFACT_NAME, exchange.HANDOFF_CONFIG_NAME):
        assert (handoff / name).read_bytes() == (write_handoff / name).read_bytes()
    stdout = (outbox / claim_receiver.STDOUT_NAME).read_bytes()
    claim_sha = hashlib.sha256(stdout).hexdigest()
    assert bound.role == "verifier" and bound.ticket_id == ticket.ticket_id
    assert bound.output == VerificationObservation(step_contract_sha256=chain.contract.sha256, attempt=1,
                                                   outcome="verified", evidence_sha256=claim_sha)
    (row,) = evidence(v)
    intent = rows(v, "write_intents")[0]
    (claim,) = verifier_rows(v, "execution_claims", ticket)
    (m2,) = verifier_rows(v, "authority_observations", ticket)
    assert (row["ticket_id"], row["step_run_id"], row["attempt"], row["write_intent_id"], row["write_scope_sha256"],
            row["claim_sha256"], row["m2_observation_id"], row["outcome"], row["provenance"]) == (
        ticket.ticket_id, chain.step.step_run_id, 1, intent["intent_id"], v.scope.sha256, claim_sha,
        m2["observation_id"], "verified", "execution_claim")
    assert (claim["shape"], claim["provenance"], m2["kind"], m2["target_sha256"]) == (
        "review-packet", "execution_claim", "m2", _sha(PROPOSED_TEXT))
    # S5: the exact bytes are preserved, so review evidence derives from them.
    assert claim_bytes(v, ticket) == stdout
    assert v.reviewer.requests == 1
    observed(v, chain, bound)
    step = v.store.get_step_run(chain.step.step_run_id)
    assert step.state is StepState.REVIEWING
    report = v.store.recover(chain.project.project_run_id)
    assert report.integrity_ok, report.integrity_issues


@needs_windows
def test_a_claimed_failed_verification_with_m2_holding_goes_to_acceptance(v: V) -> None:
    v.body(FAILING)
    chain, ticket, bound = verified(v)
    assert bound.output.outcome == "verification-failed" and v.reviewer.requests == 0
    assert verifier_rows(v, "execution_claims", ticket)[0]["shape"] == "verification-failed"
    assert v.store.get_step_run(chain.step.step_run_id).state is StepState.ACCEPTANCE
    assert v.store.recover(chain.project.project_run_id).integrity_ok


@needs_windows
def test_a_claimed_untrusted_workspace_goes_to_recovery_required_and_lists_the_addition(v: V) -> None:
    v.body(DIRTYING)
    chain, ticket, bound = verified(v)
    assert bound.output.outcome == "workspace-state-untrusted"
    step = v.store.inspect_step_run(chain.step.step_run_id)
    assert step.columns["state"] == StepState.RECOVERY_REQUIRED.value
    m1 = v.store._stored_observation(v.store._conn.execute(
        "SELECT manifest_sha256 FROM authority_observations WHERE kind = 'm1'").fetchone()[0])
    m2 = v.store._stored_observation(verifier_rows(v, "authority_observations", ticket)[0]["manifest_sha256"])
    assert wo.classify_verification(m1, m2, target_path=TARGET, post_image_sha256=_sha(PROPOSED_TEXT)).additions == (
        "stray_artifact.txt",)


@needs_windows
def test_an_ignored_addition_is_recorded_for_the_human_and_not_refused(v: V) -> None:
    v.body(IGNORED_CACHE + PASSING)
    chain, ticket, bound = verified(v)
    assert bound.output.outcome == "verified"
    m2 = v.store._stored_observation(verifier_rows(v, "authority_observations", ticket)[0]["manifest_sha256"])
    assert "build.cache" in {path for path, _, _ in m2.tree}
    assert v.store.get_step_run(chain.step.step_run_id).state is StepState.REVIEWING


@needs_windows
def test_a_config_without_both_opt_ins_hands_off_nothing(tmp_path: Path, review_env) -> None:
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    w = make_v(tmp_path, review=False)
    w.open()
    try:
        chain, _ = written(w)
        ticket = vticket_for(w, chain)
        before = snapshot(w.store)
        with pytest.raises(AuthorityRefusedError, match="controlled_review"):
            verify(w, chain, ticket)
        assert snapshot(w.store) == before
        assert not any(d.endswith(ticket.ticket_id) for d in w.handoff_dirs())
    finally:
        w.close()


# =============================================================================
# 4. M2 decides; a claim never overrides it
# =============================================================================


def _change_target(v: V) -> None:
    v.target().write_text(ORIGINAL_TEXT, encoding="utf-8")


def _change_other(v: V) -> None:
    v.other_file().write_text("TAX_RATE = 0.99\n", encoding="utf-8")


def _remove_other(v: V) -> None:
    v.other_file().unlink()


def _git_config(v: V) -> None:
    with open(v.repo / ".git" / "config", "a", encoding="utf-8") as handle:
        handle.write("[aido]\n\tx = 1\n")


def _git_head(v: V) -> None:
    (v.repo / ".git" / "HEAD").write_bytes(b"0" * 40 + b"\n")  # still detached: M2 sees the move


def _git_ref(v: V) -> None:
    (v.repo / ".git" / "refs" / "heads" / "planted").write_text(v.head + "\n", encoding="ascii")


def _nested_repo(v: V) -> None:
    (v.repo / "vendor" / ".git").mkdir(parents=True)


def _gitmodules(v: V) -> None:
    (v.repo / ".gitmodules").write_text("[submodule]\n", encoding="utf-8")


M2_FAILURES = {
    "target changed": (_change_target, True),
    "unrelated file changed": (_change_other, True),
    "unrelated file removed": (_remove_other, True),
    ".git config changed": (_git_config, True),
    "HEAD moved": (_git_head, True),
    "ref planted": (_git_ref, True),
    "nested repository": (_nested_repo, False),
    ".gitmodules": (_gitmodules, False),
    "HEAD not detached": (lambda v: (v.repo / ".git" / "HEAD").write_bytes(b"ref: refs/heads/main\n"), False),
}


@needs_windows
@pytest.mark.parametrize("name", list(M2_FAILURES))
def test_a_verified_claim_with_a_failing_m2_never_reaches_a_trusted_state(v: V, name) -> None:
    mutate, observable = M2_FAILURES[name]
    chain, _ = written(v)
    ticket = vticket_for(v, chain)
    review_step(v, ticket, extra=mutate)
    with pytest.raises(VerificationClaimRefusedError):
        verify(v, chain, ticket)
    assert evidence(v) == []
    (claim,) = verifier_rows(v, "execution_claims", ticket)
    assert claim["shape"] == "review-packet"  # the claim says verified; M2 decides
    assert len(verifier_rows(v, "authority_observations", ticket)) == (1 if observable else 0)
    forged = VerificationObservation(step_contract_sha256=chain.contract.sha256, attempt=1, outcome="verified",
                                     evidence_sha256=claim["claim_sha256"])
    with pytest.raises(AuthorityRefusedError):
        observed(v, chain, bind_role_output(ticket, forged))
    report = v.store.recover(chain.project.project_run_id)
    assert report.integrity_ok, report.integrity_issues
    assert v.store.get_step_run(chain.step.step_run_id).state is StepState.RECOVERY_REQUIRED


# =============================================================================
# 5. claim shapes and forgeries through the store
# =============================================================================


@needs_windows
@pytest.mark.parametrize("name, stdout, run, flags", [
    ("exit 1: nothing on stdout", None, True, ("--verify-approved-file-edit",)),
    ("exit 4: reviewer failed", None, True, ()),
    ("malformed", b"{not json", False, ()),
    ("a bare verified report", "bare-verified", True, ()),
    ("a contradictory packet", "contradictory", True, ()),
    ("the write claim replayed", "write-claim", False, ()),
])
def test_an_unclassifiable_claim_records_nothing(v: V, name, stdout, run, flags) -> None:
    chain, write_ticket = written(v)
    ticket = vticket_for(v, chain)
    if name.startswith("exit 4"):
        v.reviewer.fail = True
    _, write_outbox = ticket_dirs(v, write_ticket)
    write_claim = (write_outbox / claim_receiver.STDOUT_NAME).read_bytes()
    transforms = {
        "bare-verified": lambda real: json.dumps(json.loads(real)["verification"]).encode("utf-8"),
        "contradictory": lambda real: _mutated(real, _set(("target", "path"), SECOND_TARGET)),
        "write-claim": write_claim,
    }
    review_step(v, ticket, stdout=transforms.get(stdout, stdout), run=run, flags=flags)
    before_claims = len(rows(v, "execution_claims"))
    with pytest.raises(VerificationClaimRefusedError):
        verify(v, chain, ticket)
    assert len(rows(v, "execution_claims")) == before_claims
    assert verifier_rows(v, "authority_observations", ticket) == [] and evidence(v) == []
    assert v.store.recover(chain.project.project_run_id).integrity_ok


def _forge(field_path: tuple, value):
    def transform(real: bytes) -> bytes:
        document = json.loads(real)
        _set(field_path, value)(document)
        if field_path[0] != "verification":
            _set(("verification", *field_path), value)(document)
        return json.dumps(document).encode("utf-8")
    return transform


@needs_windows
@pytest.mark.parametrize("name, transform", [
    ("another target", _forge(("target", "path"), SECOND_TARGET)),
    ("another approver", _forge(("approved_by",), "mallory")),
    ("another approval time", _forge(("approved_at",), (APPROVED_AT + timedelta(seconds=1)).isoformat())),
    ("another identity", _forge(("title",), "Another title")),
    ("another post-image size", _forge(("verification", "target", "post_image_bytes"), 1)),
])
def test_a_consistent_claim_that_does_not_bind_is_recorded_but_never_evidence(v: V, name, transform) -> None:
    chain, _ = written(v)
    ticket = vticket_for(v, chain)
    review_step(v, ticket, stdout=transform)
    with pytest.raises(VerificationClaimRefusedError, match="not bound"):
        verify(v, chain, ticket)
    assert claim_readers.read_review_claim(claim_bytes(v, ticket)).shape == "review-packet"
    assert evidence(v) == [] and len(verifier_rows(v, "authority_observations", ticket)) == 1
    assert v.store.recover(chain.project.project_run_id).integrity_ok


def genuine_packet(v: V, name: str = "elsewhere") -> bytes:
    """A valid packet for this artifact, from a throwaway clone and a passing run."""
    base = v.tmp / name
    base.mkdir()
    data = _frozen_stdout(base, v.reviewer, PASSING)
    v.reviewer.content = APPROVE_REVIEW
    return data


@needs_windows
def test_a_forged_success_claim_is_recorded_as_a_claim_and_cannot_pass_a_failing_m2(v: V) -> None:
    forged = genuine_packet(v)
    v.body(FAILING)  # the verification really fails in the clone
    chain, ticket, bound = verified(v, stdout=forged)
    # D-2′: with M2 holding, a forged "verified" is indistinguishable and is
    # recorded — labeled an execution claim, never authority.
    assert bound.output.outcome == "verified"
    assert evidence(v)[0]["provenance"] == "execution_claim"
    assert v.store.get_step_run(chain.step.step_run_id).state is StepState.REVIEWING


@needs_windows
def test_the_same_forged_success_with_a_changed_target_is_refused(v: V) -> None:
    forged = genuine_packet(v)
    chain, _ = written(v)
    ticket = vticket_for(v, chain)
    review_step(v, ticket, stdout=forged, run=False, extra=_change_target)
    with pytest.raises(VerificationClaimRefusedError, match="post-image"):
        verify(v, chain, ticket)
    assert evidence(v) == []


# =============================================================================
# 6. the FD-17 claim protocol
# =============================================================================


def _extra_entry(v: V, ticket) -> None:
    _, outbox = ticket_dirs(v, ticket)
    (outbox / "extra.txt").write_bytes(b"x")


@needs_windows
@pytest.mark.parametrize("name", ["deadline", "no marker", "extra entry", "wrong owner", "marker not empty"])
def test_every_claim_protocol_deviation_records_nothing(v: V, name) -> None:
    chain, _ = written(v)
    ticket = vticket_for(v, chain)
    _, outbox = ticket_dirs(v, ticket)
    if name == "deadline":
        pass
    elif name == "no marker":
        review_step(v, ticket, complete=False)
    elif name == "extra entry":
        review_step(v, ticket, extra=lambda w: _extra_entry(w, ticket))
    elif name == "wrong owner":
        v.files.owner[os.path.normcase(str(outbox / claim_receiver.STDOUT_NAME))] = O
        review_step(v, ticket)
    else:
        def marker(w):
            (outbox / claim_receiver.COMPLETE_NAME).write_bytes(b"x")
        review_step(v, ticket, extra=marker, complete=False)
    with pytest.raises(VerificationClaimRefusedError, match="no review claim was received"):
        verify(v, chain, ticket)
    assert verifier_rows(v, "execution_claims", ticket) == [] and evidence(v) == []
    assert verifier_rows(v, "authority_observations", ticket) == []
    assert v.store.recover(chain.project.project_run_id).integrity_ok
    assert v.store.get_step_run(chain.step.step_run_id).state is StepState.RECOVERY_REQUIRED


@needs_windows
def test_a_stale_outbox_for_the_verifier_ticket_is_never_adopted(v: V) -> None:
    chain, _ = written(v)
    ticket = vticket_for(v, chain)
    _, outbox = ticket_dirs(v, ticket)
    outbox.mkdir()
    deliver(outbox, b"{}")
    with pytest.raises(VerificationClaimRefusedError, match="pre_existing"):
        verify(v, chain, ticket)
    assert verifier_rows(v, "execution_claims", ticket) == []
    (handoff,) = verifier_rows(v, "execution_handoffs", ticket)
    assert handoff["published_at"] is None  # durable before publication, never published
    assert v.store.recover(chain.project.project_run_id).integrity_ok


@needs_windows
def test_a_claim_in_the_write_outbox_is_never_read_for_verification(v: V) -> None:
    chain, write_ticket = written(v)
    ticket = vticket_for(v, chain)
    _, write_outbox = ticket_dirs(v, write_ticket)

    def replay(w):
        (write_outbox / claim_receiver.STDOUT_NAME).write_bytes(genuine_packet(w))

    v.waiter.queue.append(lambda: replay(v))
    with pytest.raises(VerificationClaimRefusedError, match="deadline_expired"):
        verify(v, chain, ticket)
    assert verifier_rows(v, "execution_claims", ticket) == []


@needs_windows
def test_a_claim_is_never_read_after_its_ticket_left_verifying(v: V) -> None:
    chain, _ = written(v)
    ticket = vticket_for(v, chain)
    store = v.store

    _, outbox = ticket_dirs(v, ticket)

    def reduce_then_deliver():
        deliver(outbox, run_frozen_review(ticket_dirs(v, ticket)[0]))
        # Meanwhile the step leaves VERIFYING (here: a human-applied reduction).
        step = store.get_step_run(chain.step.step_run_id)
        store.apply_step_transition(step.step_run_id, step_request(
            step, StepEvent.RECOVER_INTERRUPTED, reason="operator reduced it"))

    v.waiter.queue.append(reduce_then_deliver)
    with pytest.raises(AuthorityRefusedError, match="stale|project is RECOVERY_REQUIRED"):
        verify(v, chain, ticket)
    assert not [r for r in v.files.reads if os.path.normcase(r).startswith(os.path.normcase(str(outbox)))]
    assert verifier_rows(v, "execution_claims", ticket) == [] and evidence(v) == []
    assert v.store.recover(chain.project.project_run_id).integrity_ok


# =============================================================================
# 7. tickets, recorders and caller-supplied authority
# =============================================================================


@needs_windows
def test_only_a_verifier_ticket_for_the_proven_write_is_handed_off(v: V) -> None:
    chain, write_ticket = written(v)
    contract = v.store.get_step_contract(chain.contract.sha256)
    ticket = vticket_for(v, chain)
    before = snapshot(v.store)
    with pytest.raises(AuthorityRefusedError):
        v.session.verifier.verify(step_contract=contract, attempt=1, dispatch=write_ticket)
    forged = ticket.model_copy(update={"ticket_id": "f" * 32})
    with pytest.raises(AuthorityRefusedError):
        v.session.verifier.verify(step_contract=contract, attempt=1, dispatch=forged)
    with pytest.raises(AuthorityRefusedError):
        v.session.verifier.verify(step_contract=contract, attempt=1,
                                  dispatch=ticket.model_copy(update={"state_version": ticket.state_version + 1}))
    with pytest.raises(ValueError):
        v.session.verifier.verify(step_contract=contract, attempt=2, dispatch=ticket)
    with pytest.raises(TypeError):
        v.session.verifier.verify(step_contract=contract, attempt=1, dispatch=ticket.model_dump())
    assert snapshot(v.store) == before and not any(d.endswith(ticket.ticket_id) for d in v.handoff_dirs())


@needs_windows
def test_only_the_session_minted_claim_recorder_can_hand_off_a_review(v: V) -> None:
    chain, _ = written(v)
    ticket = vticket_for(v, chain)
    before = snapshot(v.store)
    write_key = v.store._require_authority().write_key
    for key in (None, object(), write_key):
        with pytest.raises(AuthorityRefusedError, match="execution claim adapter"):
            v.store._perform_review_handoff(key, ticket)
        for phase in (v.store._claim_review_handoff, v.store._publish_review_handoff,
                      v.store._receive_review_claim):
            with pytest.raises(AuthorityRefusedError):
                phase(key, ticket)
    forged = mint_execution_claim_adapter(v.store, object())
    contract = v.store.get_step_contract(chain.contract.sha256)
    with pytest.raises(AuthorityRefusedError):
        forged.verify(step_contract=contract, attempt=1, dispatch=ticket)
    # The write recorder cannot reach the review handoff either.
    with pytest.raises(AuthorityRefusedError):
        v.session.implementer.implement(step_contract=contract, attempt=1, dispatch=ticket)
    assert snapshot(v.store) == before


def test_the_adapter_and_session_expose_no_recorder() -> None:
    with pytest.raises(TypeError):
        ExecutionClaimAdapter(object(), object())
    with pytest.raises(TypeError):
        type("Sub", (ExecutionClaimAdapter,), {})
    adapter = mint_execution_claim_adapter(object(), object())
    assert {n for n in dir(adapter) if not n.startswith("_")} == {"verify", "review"}  # S5 adds review
    with pytest.raises(AttributeError):
        adapter._recorder = None
    for copier in (lambda a: __import__("copy").copy(a), lambda a: __import__("pickle").dumps(a)):
        with pytest.raises(TypeError):
            copier(adapter)
    assert "_verifier" in IntegrationSession.__slots__


@needs_windows
def test_no_caller_supplied_observation_or_digest_passes_verifying(v: V) -> None:
    chain, _ = written(v)
    ticket = vticket_for(v, chain)
    made_up = VerificationObservation(step_contract_sha256=chain.contract.sha256, attempt=1, outcome="verified",
                                      evidence_sha256="0" * 64)
    with pytest.raises(AuthorityRefusedError, match="no verification evidence"):
        observed(v, chain, bind_role_output(ticket, made_up))
    with pytest.raises(AuthorityRefusedError):
        v.store._record_verification_evidence(object(), ticket, b"{}")
    # With genuine evidence recorded, only its exact outcome and digest pass.
    review_step(v, ticket)
    bound = verify(v, chain, ticket)
    for update in ({"outcome": "verification-failed"}, {"outcome": "workspace-state-untrusted"},
                   {"evidence_sha256": "1" * 64}):
        with pytest.raises(AuthorityRefusedError):
            observed(v, chain, bound, output=bound.output.model_copy(update=update))
    with pytest.raises((AuthorityRefusedError, ValueError)):  # a report in place of an observation
        step = v.store.get_step_run(chain.step.step_run_id)
        v.store.apply_step_transition(step.step_run_id, step_request(
            step, StepEvent.IMPLEMENTATION_RETURNED, implementation=fixed_report(chain)),
            role_output=bind_role_output(ticket, fixed_report(chain)))
    observed(v, chain, bound)
    assert v.store.get_step_run(chain.step.step_run_id).state is StepState.REVIEWING


@needs_windows
def test_review_observations_are_still_refused_s5(v: V) -> None:
    from ai_dev_orchestrator.control_plane import ReviewProposal

    chain, ticket, bound = verified(v)
    step = v.store.get_step_run(chain.step.step_run_id)
    reviewer = v.store.issue_dispatch_ticket(step.step_run_id, role="reviewer", expected_state_version=step.state_version)
    proposal = ReviewProposal(step_contract_sha256=chain.contract.sha256, attempt=1, verdict="approve",
                              evidence_sha256=bound.output.evidence_sha256)
    with pytest.raises(AuthorityRefusedError):
        v.store.apply_step_transition(step.step_run_id, step_request(step, StepEvent.REVIEW_OBSERVED, review=proposal),
                                      role_output=bind_role_output(reviewer, proposal))


# =============================================================================
# 8. duplicates, restarts, reuse of S3 evidence
# =============================================================================


@needs_windows
def test_a_verifier_dispatch_is_handed_off_once_and_never_runs_twice(v: V) -> None:
    chain, _ = written(v)
    ticket = vticket_for(v, chain)
    review_step(v, ticket)
    bound = verify(v, chain, ticket)
    dirs = v.handoff_dirs()
    requests = v.reviewer.requests
    with pytest.raises(AuthorityRefusedError, match="handed off once"):
        verify(v, chain, ticket)
    step = v.store.get_step_run(chain.step.step_run_id)
    with pytest.raises(AuthorityRefusedError):
        v.store.issue_dispatch_ticket(step.step_run_id, role="verifier", expected_state_version=step.state_version)
    assert v.handoff_dirs() == dirs and v.reviewer.requests == requests and len(evidence(v)) == 1
    observed(v, chain, bound)
    with pytest.raises(AuthorityRefusedError):
        observed(v, chain, bound)  # the dispatch answers once
    with pytest.raises(AuthorityRefusedError):
        verify(v, chain, ticket)


@needs_windows
def test_after_recovery_nothing_can_hand_off_a_review(v: V) -> None:
    chain, _ = written(v)
    ticket = vticket_for(v, chain)
    v.close()
    store = v.open()
    store.recover(chain.project.project_run_id)
    assert store.get_step_run(chain.step.step_run_id).state is StepState.RECOVERY_REQUIRED
    with pytest.raises(AuthorityRefusedError):
        verify(v, chain, ticket)
    assert not any(d.endswith(ticket.ticket_id) for d in v.handoff_dirs())


@needs_windows
def test_revoking_the_approver_after_the_write_hands_off_no_review(v: V) -> None:
    from test_dl4b_s2_integration_store import _set_alice

    chain, _ = written(v)
    ticket = vticket_for(v, chain)
    _set_alice(v, revoked=True)
    with pytest.raises((AuthorityRefusedError, StateUntrustedError)):
        verify(v, chain, ticket)
    assert not any(d.endswith(ticket.ticket_id) for d in v.handoff_dirs())
    assert verifier_rows(v, "execution_handoffs", ticket) == [] and v.reviewer.requests == 0


@needs_windows
def test_verification_evidence_binds_exactly_one_write_intent(v: V) -> None:
    chain, ticket, _ = verified(v)
    conn = v.store._conn
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO verification_evidence_v2 SELECT 'e' || substr(ticket_id, 2), step_run_id, "
                     "attempt, write_intent_id, write_scope_sha256, workspace_identity_sha256, claim_sha256, "
                     "m2_observation_id, outcome, provenance, recorded_at FROM verification_evidence_v2")
    conn.rollback()


# =============================================================================
# 9. crashes
# =============================================================================

CRASH_POINTS = [
    ("INSERT INTO execution_handoffs", False),
    ("INSERT INTO execution_handoffs", True),
    ("UPDATE execution_handoffs", False),
    ("INSERT INTO execution_claims", False),
    ("INSERT INTO authority_observations", False),
    ("INSERT INTO verification_evidence_v2", False),
    ("INSERT INTO verification_evidence_v2", True),
]


@needs_windows
@pytest.mark.parametrize("needle, after", CRASH_POINTS)
def test_a_crash_in_the_review_handoff_never_resumes_and_never_runs_twice(v: V, needle, after) -> None:
    chain, _ = written(v)
    ticket = vticket_for(v, chain)
    review_step(v, ticket)
    proxy = crash_at(v.store, needle, after=after)
    with pytest.raises(SimulatedCrash):
        verify(v, chain, ticket)
    assert not proxy.armed
    v.close()
    store = v.open()
    report = store.recover(chain.project.project_run_id)
    assert report.integrity_ok, report.integrity_issues
    assert store.get_step_run(chain.step.step_run_id).state is StepState.RECOVERY_REQUIRED
    assert evidence(v) == []
    assert len(verifier_rows(v, "execution_handoffs", ticket)) == (0 if needle.startswith("INSERT INTO execution_h")
                                                                  else 1)
    with pytest.raises(AuthorityRefusedError):
        verify(v, chain, ticket)


@needs_windows
def test_a_crash_after_the_evidence_commit_leaves_recovery_required_with_proven_evidence(v: V) -> None:
    chain, _ = written(v)
    ticket = vticket_for(v, chain)
    review_step(v, ticket)
    verify(v, chain, ticket)  # the evidence is durable; the transition never happens
    v.close()
    store = v.open()
    report = store.recover(chain.project.project_run_id)
    assert report.integrity_ok, report.integrity_issues
    assert store.get_step_run(chain.step.step_run_id).state is StepState.RECOVERY_REQUIRED
    assert len(evidence(v)) == 1


# =============================================================================
# 10. the tamper matrix: every S4 record re-proves, or the run is untrusted
# =============================================================================

NINES = "'" + "9" * 64 + "'"
S4_TAMPERS = {
    "evidence outcome": "UPDATE verification_evidence_v2 SET outcome = 'verification-failed'",
    "evidence claim digest": f"UPDATE verification_evidence_v2 SET claim_sha256 = {NINES}",
    "evidence scope": f"UPDATE verification_evidence_v2 SET write_scope_sha256 = {NINES}",
    "evidence workspace": f"UPDATE verification_evidence_v2 SET workspace_identity_sha256 = {NINES}",
    "evidence intent": "UPDATE verification_evidence_v2 SET write_intent_id = 'x'",
    "evidence m2 is m1": "UPDATE verification_evidence_v2 SET m2_observation_id = "
                         "(SELECT observation_id FROM authority_observations WHERE kind = 'm1')",
    "evidence moved to the implementer ticket": "UPDATE verification_evidence_v2 SET ticket_id = "
                                                "(SELECT ticket_id FROM write_intents)",
    "evidence attempt": "UPDATE verification_evidence_v2 SET attempt = 2",
    "evidence removed": "DELETE FROM verification_evidence_v2",
    "claim shape": "UPDATE execution_claims SET shape = 'verification-failed' WHERE shape = 'review-packet'",
    "claim digest": f"UPDATE execution_claims SET claim_sha256 = {NINES} WHERE shape = 'review-packet'",
    "claim length": "UPDATE execution_claims SET byte_length = byte_length + 1 WHERE shape = 'review-packet'",
    "claim removed": "DELETE FROM execution_claims WHERE shape = 'review-packet'",
    "m2 target": f"UPDATE authority_observations SET target_sha256 = {NINES} WHERE kind = 'm2'",
    "m2 removed": "DELETE FROM authority_observations WHERE kind = 'm2'",
    "m2 kind": "UPDATE authority_observations SET kind = 'm1' WHERE kind = 'm2'",
    "verifier handoff artifact": f"UPDATE execution_handoffs SET approved_diff_artifact_sha256 = {NINES} "
                                 "WHERE ticket_id = (SELECT ticket_id FROM verification_evidence_v2)",
    "verifier handoff unpublished": "UPDATE execution_handoffs SET handoff_directory_identity = NULL, "
                                    "outbox_directory_identity = NULL, published_at = NULL "
                                    "WHERE ticket_id = (SELECT ticket_id FROM verification_evidence_v2)",
    "verifier ticket role": "UPDATE dispatch_tickets SET role = 'reviewer' "
                            "WHERE ticket_id = (SELECT ticket_id FROM verification_evidence_v2)",
    "transition outcome": "UPDATE transitions SET verification_outcome = 'verification-failed' "
                          "WHERE event = 'verification_observed'",
    "write evidence removed": "DELETE FROM write_evidence",
    "review evidence row": "INSERT INTO review_evidence VALUES ('x', 'x', 'x', 'approve', 'execution_claim', 'x')",
}
S4_BLOB_TAMPERS = {
    "claim blob": ("claims", "SELECT claim_sha256 FROM verification_evidence_v2"),
    "m2 manifest": ("observations", "SELECT manifest_sha256 FROM authority_observations WHERE kind = 'm2'"),
}


def _replace_blob(v: V, kind: str, column_sql: str) -> None:
    conn = sqlite3.connect(v.root.store_path)
    sha = conn.execute(column_sql).fetchone()[0]
    conn.close()
    path = Path(v.root.path, "evidence", kind, sha)
    os.chmod(path, 0o666)
    path.write_bytes(path.read_bytes() + b" ")


@needs_windows
@pytest.mark.parametrize("name", list(S4_TAMPERS) + list(S4_BLOB_TAMPERS))
def test_a_tampered_s4_record_makes_the_run_untrusted(v: V, name) -> None:
    chain, _, _ = verified(v)
    v.close()
    if name in S4_BLOB_TAMPERS:
        _replace_blob(v, *S4_BLOB_TAMPERS[name])
    else:
        conn = sqlite3.connect(v.root.store_path)
        conn.execute("PRAGMA ignore_check_constraints = ON")
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute(S4_TAMPERS[name])
        conn.commit()
        conn.close()
    store = v.open()
    report = store.recover(chain.project.project_run_id)
    assert not report.integrity_ok, name
    with pytest.raises(StateUntrustedError):
        store.get_step_run(chain.step.step_run_id)


@needs_windows
def test_a_settled_but_unconsumed_verification_still_needs_its_evidence(v: V) -> None:
    chain, _ = written(v)
    ticket = vticket_for(v, chain)
    review_step(v, ticket)
    verify(v, chain, ticket)
    v.close()
    conn = sqlite3.connect(v.root.store_path)
    conn.execute("DELETE FROM verification_evidence_v2")
    conn.commit()
    conn.close()
    report = v.open().recover(chain.project.project_run_id)
    assert not report.integrity_ok
    assert any("has no evidence" in issue for issue in report.integrity_issues), report.integrity_issues


# =============================================================================
# 11. DL-3 → DL-2 enforces the same requirements
# =============================================================================


class Ports:
    def __init__(self, implementer, verifier) -> None:
        self.implementer = implementer
        self.verifier_port = verifier
        self.calls: list[str] = []

    def role_ports(self) -> RolePorts:
        return RolePorts(planner=self, tester=self, implementer=self.implementer, verifier=self.verifier_port,
                         reviewer=self)

    def propose_step_contract(self, **kwargs):
        return make_proposal()

    def propose_tests(self, **kwargs):
        return ()

    def review(self, **kwargs):
        self.calls.append("reviewer")
        raise AssertionError("a stub reviewer: S5's adapter is exercised in test_dl4b_s5_review_evidence")

    def decide_step(self, **kwargs):
        self.calls.append("planner")
        raise AssertionError("S6 does not exist")


def _x_steps(v: V) -> None:
    """Queue both human steps for A's two waits, each against the newest
    published handoff whose outbox has no marker yet."""

    def pending() -> tuple[Path, Path]:
        for name in sorted(v.handoff_dirs(), key=lambda d: os.path.getmtime(os.path.join(v.exchange, d))):
            if name.startswith("handoff-"):
                handoff, outbox = exchange.ticket_directories(v.exchange, name.split("-", 1)[1])
                if os.path.isdir(outbox) and not os.path.exists(os.path.join(outbox, claim_receiver.COMPLETE_NAME)):
                    return Path(handoff), Path(outbox)
        raise AssertionError("no pending handoff")

    def write() -> None:
        handoff, outbox = pending()
        deliver(outbox, run_frozen_writer(handoff))

    def review() -> None:
        handoff, outbox = pending()
        deliver(outbox, run_frozen_review(handoff))

    v.waiter.queue.extend([write, review])


@needs_windows
def test_the_orchestration_path_records_the_bound_verification_and_stops_at_review(v: V) -> None:
    chain = _planned(v)
    _x_steps(v)
    ports = Ports(v.session.implementer, v.session.verifier)
    ProjectOuterLoop(v.store, ports.role_ports()).run(
        project_run=v.store.get_project_run(chain.project.project_run_id),
        project_contract=chain.pc, execution_plan=chain.plan)
    events = [r.event for r in v.store.transitions_for(chain.step.step_run_id)]
    assert StepEvent.IMPLEMENTATION_RETURNED.value in events and StepEvent.VERIFICATION_OBSERVED.value in events
    assert ports.calls == ["reviewer"]
    assert len(evidence(v)) == 1 and evidence(v)[0]["outcome"] == "verified"
    assert v.store.get_step_run(chain.step.step_run_id).state is StepState.RECOVERY_REQUIRED  # stub reviewer
    assert v.reviewer.requests == 1
    dirs = v.handoff_dirs()
    again = Ports(v.session.implementer, v.session.verifier)
    ProjectOuterLoop(v.store, again.role_ports()).run(
        project_run=v.store.get_project_run(chain.project.project_run_id),
        project_contract=chain.pc, execution_plan=chain.plan)
    assert again.calls == [] and v.handoff_dirs() == dirs and v.reviewer.requests == 1


@needs_windows
def test_the_orchestration_path_with_a_forged_verifier_reaches_no_trusted_state(v: V) -> None:
    chain = _planned(v)
    _x_steps(v)
    v.waiter.queue.pop()  # no review step: only the forger answers

    class Forger:
        def verify(self, *, step_contract, attempt, dispatch=None):
            return bind_role_output(dispatch, VerificationObservation(
                step_contract_sha256=step_contract.sha256, attempt=attempt, outcome="verified",
                evidence_sha256="0" * 64))

    ports = Ports(v.session.implementer, Forger())
    ProjectOuterLoop(v.store, ports.role_ports()).run(
        project_run=v.store.get_project_run(chain.project.project_run_id),
        project_contract=chain.pc, execution_plan=chain.plan)
    events = [r.event for r in v.store.transitions_for(chain.step.step_run_id)]
    assert StepEvent.VERIFICATION_OBSERVED.value not in events
    assert v.store.get_step_run(chain.step.step_run_id).state is StepState.RECOVERY_REQUIRED
    assert ports.calls == [] and evidence(v) == []


# =============================================================================
# 12. static boundaries
# =============================================================================

_PACKAGE = Path(integration.__file__).resolve().parent


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
    return names


def test_s4_modules_have_no_execution_network_model_git_or_harness_surface() -> None:
    forbidden = {"subprocess", "socket", "httpx", "requests", "aiohttp", "urllib", "http", "asyncio",
                 "multiprocessing", "shutil", "tempfile", "winreg", "threading", "ctypes", "os"}
    harness = ("ai_dev_orchestrator.llm", "ai_dev_orchestrator.github", "ai_dev_orchestrator.review",
               "ai_dev_orchestrator.verification", "ai_dev_orchestrator.file_editing",
               "ai_dev_orchestrator.supervised_implementer", "ai_dev_orchestrator.workspace",
               "ai_dev_orchestrator.diff_proposal", "ai_dev_orchestrator.handoff", "ai_dev_orchestrator.plan",
               "ai_dev_orchestrator.cli", "ai_dev_orchestrator.config_loader")
    names_forbidden = {"Popen", "run_controlled_review", "verify_approved_file_edit", "max_tokens", "environ",
                       "getenv", "system", "unlink", "remove", "rmdir", "rename", "rmtree", "chmod"}
    for name in ("execution_claim.py", "claim_readers.py", "workspace_observation.py", "integration_store.py"):
        path = _PACKAGE / name
        imported = _imports(path)
        if name == "execution_claim.py":
            assert not {m.split(".")[0] for m in imported} & forbidden, (name, imported)
        assert not [m for m in imported if m.startswith(harness)], (name, imported)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert not names & names_forbidden, (name, names & names_forbidden)


def test_importing_the_a_side_with_s4_loads_no_harness_git_or_network_module() -> None:
    code = (
        "import sys\n"
        "import ai_dev_orchestrator.integration.integration_session\n"
        "import ai_dev_orchestrator.integration.execution_claim\n"
        "bad = [m for m in sys.modules if m.split('.')[0] in ('subprocess', 'socket', 'httpx') or m.startswith((\n"
        "  'ai_dev_orchestrator.file_editing', 'ai_dev_orchestrator.workspace', 'ai_dev_orchestrator.llm',\n"
        "  'ai_dev_orchestrator.verification', 'ai_dev_orchestrator.review', 'ai_dev_orchestrator.diff_proposal',\n"
        "  'ai_dev_orchestrator.cli'))]\n"
        "print(bad)\n"
    )
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, check=True,
                         env={**os.environ, "PYTHONPATH": str(_PACKAGE.parent.parent)}).stdout.strip()
    assert out == "[]", out


def test_no_s4_public_api_accepts_bytes_or_authority_evidence() -> None:
    import inspect

    for owner in (IntegrationStore, IntegrationSession, ExecutionClaimAdapter):
        for name, member in inspect.getmembers(owner, callable):
            if name.startswith("_"):
                continue
            for parameter in inspect.signature(member).parameters:
                lowered = parameter.lower()
                assert not any(word in lowered for word in (
                    "claim", "observation", "evidence", "stdout", "manifest", "recorder", "report", "data",
                    "digest", "bytes", "outcome")), (owner.__name__, name, parameter)


def test_the_frozen_review_command_is_unchanged_by_s4() -> None:
    """S4 reads the command's stdout; it adds no option and no injection point."""
    import inspect

    options = set(inspect.signature(cli.l2_review_approved_file_edit).parameters)
    assert options == {"project_config", "approved_diff_proposal", "verify_approved_file_edit_flag",
                       "real_reviewer", "output_format"}
    assert set(inspect.signature(cli._run_l2_review_approved_file_edit).parameters) == {
        "project_config", "approved_diff_proposal", "verify_approved_file_edit_flag", "real_reviewer",
        "read_env", "network_transport_factory"}
