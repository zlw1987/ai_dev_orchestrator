"""DL-4B S7 — the non-model Alpha driver and the operator helper, offline.

The harness is S4–S6's: a synthetic Git clone under pytest ``tmp_path``, S0/S1
synthetic Windows worlds, the production ``WindowsAuthorityFiles`` with
synthetic owners, the boundary's ``published/`` directory, and the reviewer
behind an ``httpx.MockTransport``. Every driver invocation runs over a FRESH
integration session (a new process, as far as the store can tell), so nothing
the driver remembered can decide anything.

The human's X-side steps are simulated exactly as S3–S5 simulate them: the
frozen, unchanged ``l2-apply-approved-file-edit`` and
``l2-review-approved-file-edit`` run in-process while A waits, with stdout
written to the outbox. A guard wraps both frozen command bodies and fails if
either runs anywhere but inside that simulated X step, so the driver is shown
never to execute them. O's statements are prepared with the operator helper and
signed with S1's test-only software key.

Sections: harness; the complete chain; restart at every durable boundary;
stage discipline and caller inputs; approvals; execution failures; acceptance,
decline and completion; persisted state decides; the operator helper; the
production entry points; static boundaries.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from test_dl4b_s0_identity_boundary import ADMIN_FULL, OICI, RX, A, O, allow
from test_dl4b_s1_attestation_verifier import ALICE, BOB, armor, fingerprint, sign, sk_blob, statement_bytes
from test_dl4b_s2_integration_store import (
    ONE_STEP,
    SimulatedCrash,
    _put_ancestors,
    _set_alice,
    make_content,
    make_policy,
    make_proposal,
    rename_execution_account,
    snapshot,
)
from test_dl4b_s3_write_handoff import (
    APPROVED_AT,
    ARTIFACT_NAME,
    CONFIG_NAME,
    OTHER_TEXT,
    _key,
    deliver,
    run_frozen_writer,
)
from test_dl4b_s4_verification_claim import (
    CHANGES_REVIEW,
    PASSING,
    V,
    _frozen_stdout,
    _imports,
    make_v,
    review_env,  # noqa: F401 - fixture
    run_frozen_review,
    write_config,
)

from tests.test_cli_l2_apply_approved_file_edit import PROPOSED_TEXT, _sha

import ai_dev_orchestrator.integration as integration
from ai_dev_orchestrator import cli
from ai_dev_orchestrator.control_plane.attestation_v2 import ApprovalSubjectKindV2 as K
from ai_dev_orchestrator.integration import alpha_driver, alpha_operator, claim_receiver, exchange
from ai_dev_orchestrator.integration.alpha_driver import (
    ATTESTATION_NAMES,
    DEFINITION_NAME,
    AlphaDriver,
    AlphaStage,
    DriverOutcome,
    DriverReport,
    parse_definition,
)
from ai_dev_orchestrator.integration.security_descriptor import FILE_ALL_ACCESS

WINDOWS = sys.platform == "win32"
needs_windows = pytest.mark.skipif(not WINDOWS, reason="real Windows file handles and a synthetic Windows boundary")
MISSING = object()


# =============================================================================
# harness
# =============================================================================


class XGuard:
    """Wraps both frozen command bodies. Either may run only while the
    simulated human X step is active; anything else is the driver (or A)
    executing X-side work, and fails the test."""

    def __init__(self, monkeypatch) -> None:
        self.active = False
        self.calls: list[str] = []
        for name in ("_run_l2_apply_approved_file_edit", "_run_l2_review_approved_file_edit"):
            original = getattr(cli, name)

            def wrapped(*args, _original=original, _name=name, **kwargs):
                assert self.active, f"{_name} ran outside the human's X step"
                self.calls.append(_name)
                return _original(*args, **kwargs)

            monkeypatch.setattr(cli, name, wrapped)


def definition_document(h: V, **changes) -> dict:
    document = {
        "schema_version": "alpha-definition.v1",
        "project_contract": make_content().model_dump(mode="json"),
        "step": ONE_STEP[0].model_dump(mode="json"),
        "execution_policy": make_policy().model_dump(mode="json"),
        "write_scope": h.scope.model_dump(mode="json"),
        "step_contract_proposal": make_proposal().model_dump(mode="json"),
        "approved_diff_name": ARTIFACT_NAME,
        "project_config_name": CONFIG_NAME,
    }
    document.update(changes)
    return document


def put_definition(h: V, document: dict | None = None) -> None:
    h.put_inbox(DEFINITION_NAME, json.dumps(document or definition_document(h)).encode("utf-8"))


def make_d(tmp_path: Path, review_env, monkeypatch) -> V:
    harness = make_v(tmp_path)
    harness.reviewer = review_env
    published = tmp_path / "published"
    published.mkdir()
    path = os.path.realpath(published)
    _put_ancestors(harness.world, path)
    harness.world.put(path, is_dir=True, owner=A, protected=True,
                      aces=[allow(A, FILE_ALL_ACCESS, OICI), *ADMIN_FULL, allow(O, RX, OICI)])
    harness.world.boundary["paths"]["published"] = path
    harness.files.published = path
    harness.published = path
    harness.guard = XGuard(monkeypatch)
    harness.announced = []
    harness.trace = []
    put_definition(harness)
    harness.open()
    return harness


@pytest.fixture
def d(tmp_path: Path, review_env, monkeypatch):
    if not WINDOWS or shutil.which("git") is None:
        pytest.skip("needs Windows and git")
    harness = make_d(tmp_path, review_env, monkeypatch)
    yield harness
    harness.close()


def invoke(h: V, verb: str) -> DriverReport:
    """One A invocation: a fresh session (a new process), a new driver."""
    h.close()
    h.open()
    report = AlphaDriver(h.session, announce=h.announced.append).invoke(verb)
    h.trace.append((verb, report.outcome.value, report.stage.value))
    return report


def o_sign(h: V, report: DriverReport, *, attested_at=None, private=ALICE, approver: str = "alice",
           name: str | None = None) -> bytes:
    """O's steps: read the published report, prepare the statement with the
    helper, sign it (S1's test-only key), and place the attestation."""
    presented = report.to_json().encode("utf-8")
    at = attested_at or report.challenge.issued_at
    message = alpha_operator.statement_bytes(presented, approver_id=approver,
                                             key_fingerprint_sha256=fingerprint(sk_blob(private)), attested_at=at)
    data = alpha_operator.attestation_bytes(presented, approver_id=approver, attested_at=at,
                                            signature=armor(sign(private, message)))
    h.put_inbox(name or report.attestation_inbox_name, data)
    return data


def approve(h: V, **sign_options) -> DriverReport:
    request = invoke(h, "request-approval")
    assert request.outcome is DriverOutcome.APPROVAL_REQUIRED and request.challenge is not None, request.to_json()
    if request.challenge.subject_kind is K.EXACT_DIFF_APPROVAL:
        sign_options.setdefault("attested_at", APPROVED_AT)
        h.clock.now = max(h.clock.now, APPROVED_AT + timedelta(minutes=1))
    o_sign(h, request, **sign_options)
    return invoke(h, "record-approval")


def approved(h: V) -> DriverReport:
    """Contract, activation and exact-diff approvals, each through the driver."""
    assert invoke(h, "status").stage is AlphaStage.CONTRACT_APPROVAL
    assert approve(h).stage is AlphaStage.PLAN_ACTIVATION
    assert approve(h).stage is AlphaStage.EXACT_DIFF_APPROVAL
    report = approve(h)
    assert report.stage is AlphaStage.ATTEMPT and report.outcome is DriverOutcome.READY_TO_RUN, report.to_json()
    return report


def pending(h: V) -> tuple[Path, Path]:
    for name in sorted(h.handoff_dirs(), key=lambda n: os.path.getmtime(os.path.join(h.exchange, n))):
        if name.startswith("handoff-"):
            handoff, outbox = exchange.ticket_directories(h.exchange, name.split("-", 1)[1])
            if os.path.isdir(outbox) and not os.path.exists(os.path.join(outbox, claim_receiver.COMPLETE_NAME)):
                return Path(handoff), Path(outbox)
    raise AssertionError("no pending handoff")


def x_step(h: V, command, *, stdout=None, extra=None, complete: bool = True, run: bool = True) -> None:
    """Queue the human's X-side step for A's next wait. It must be the step
    the driver announced last, against the handoff A just published."""

    def action() -> None:
        handoff, outbox = pending(h)
        announced = h.announced[-1]
        assert (announced["handoff_directory"], announced["outbox_directory"]) == (str(handoff), str(outbox))
        h.guard.active = True
        try:
            real = command(handoff) if run else b""
            data = stdout(h) if callable(stdout) else stdout
        finally:
            h.guard.active = False
        if extra is not None:
            extra(h, handoff, outbox)
        if data is MISSING:
            deliver(outbox, None, complete=complete)
        else:
            deliver(outbox, real if data is None else data, complete=complete)

    h.waiter.queue.append(action)


def x_steps(h: V, *, write: dict | None = None, review: dict | None = None) -> None:
    x_step(h, run_frozen_writer, **(write or {}))
    x_step(h, run_frozen_review, **(review or {}))


def held(h: V) -> DriverReport:
    approved(h)
    x_steps(h)
    report = invoke(h, "run")
    assert report.outcome is DriverOutcome.AWAITING_HUMAN_ACCEPTANCE, report.to_json()
    assert h.waiter.queue == []
    return report


def accept(h: V, **sign_options) -> DriverReport:
    request = invoke(h, "request-approval")
    assert request.challenge.subject_kind is K.STEP_ACCEPTANCE, request.to_json()
    o_sign(h, request, **sign_options)
    return invoke(h, "record-approval")


def rows(h: V, table: str, where: str = "", params: tuple = ()) -> list[sqlite3.Row]:
    return h.store._conn.execute(f"SELECT * FROM {table} {where}", params).fetchall()


def tickets(h: V, role: str) -> list[sqlite3.Row]:
    return rows(h, "dispatch_tickets", "WHERE role = ?", (role,))


def frozen(h: V) -> tuple:
    """Everything the authority plane and the exchange hold, for unchanged-ness."""
    return (snapshot(h.store), tuple(h.handoff_dirs()), tuple(sorted(os.listdir(h.published))),
            h.reviewer.requests, tuple(h.guard.calls))


def refused(report: DriverReport, category: str | None = None) -> None:
    assert report.outcome is DriverOutcome.REFUSED, report.to_json()
    if category is not None:
        assert report.refusal["category"] == category, report.refusal


# =============================================================================
# 1. the complete chain
# =============================================================================


@needs_windows
def test_the_complete_offline_alpha_reaches_complete_only_through_every_human_step(d: V) -> None:
    """Contract approval → plan activation → exact-diff approval → bounded
    write → verification → review → durable hold → restart → signed
    acceptance → COMPLETE, each invocation in a fresh session."""
    approved(d)
    assert d.guard.calls == [] and d.reviewer.requests == 0  # nothing ran before the attempt
    x_steps(d)
    run = invoke(d, "run")
    assert run.outcome is DriverOutcome.AWAITING_HUMAN_ACCEPTANCE and run.stage is AlphaStage.ACCEPTANCE
    assert run.dl3_stop == "step_not_settled" and run.held["recommendation"] == "RECOMMEND_STEP_ACCEPT"
    # The driver announced exactly the two frozen X commands, unchanged, and ran neither.
    assert [a["action"] for a in run.announced_x_actions] == ["run_frozen_write_command", "run_frozen_review_command"]
    write, review = run.announced_x_actions
    assert write["argv"][1:2] == ["l2-apply-approved-file-edit"] and write["argv"][-2:] == [
        "--apply-approved-plan", "--write-approved-file"]
    assert review["argv"][1:2] == ["l2-review-approved-file-edit"] and review["argv"][-2:] == [
        "--verify-approved-file-edit", "--real-reviewer"]
    assert all(a["actor"] == "X" and a["cmd_exe_lines"][1].startswith("type nul > ") for a in run.announced_x_actions)
    assert d.guard.calls == ["_run_l2_apply_approved_file_edit", "_run_l2_review_approved_file_edit"]
    assert d.reviewer.requests == 1 and len(tickets(d, "planner")) == 1
    # Restart: the hold survives and nothing is re-planned or re-run.
    for _ in range(2):
        status = invoke(d, "status")
        assert status.outcome is DriverOutcome.AWAITING_HUMAN_ACCEPTANCE and status.held == run.held
    request = invoke(d, "request-approval")
    subject = request.subject
    assert subject["bundle_name"] in os.listdir(d.published)
    assert subject["step_acceptance_subject_sha256"] == request.challenge.subject_sha256 == run.held["subject_sha256"]
    assert subject["subject_sha256_matches_published_bundle"] == request.challenge.subject_sha256
    assert "subject_sha256_recomputed_by_driver" not in subject  # the v2 subject is the store's, confirmed
    bundle = json.loads(Path(d.published, subject["bundle_name"]).read_bytes())
    assert {"aido_observed", "execution_claims"} <= set(bundle)
    o_sign(d, request)
    done = invoke(d, "record-approval")
    assert done.outcome is DriverOutcome.COMPLETE and done.stage is AlphaStage.COMPLETE, done.to_json()
    assert done.run["step_state"] == "COMPLETE" and done.run["project_state"] == "ACTIVE"
    final = invoke(d, "status")
    assert final.outcome is DriverOutcome.COMPLETE and final.recovery["integrity_ok"]
    assert d.guard.calls == ["_run_l2_apply_approved_file_edit", "_run_l2_review_approved_file_edit"]
    assert d.reviewer.requests == 1 and len(tickets(d, "planner")) == 1
    assert hashlib.sha256(d.target().read_bytes()).hexdigest() == _sha(PROPOSED_TEXT)  # the one approved write
    print("\nS7 offline Alpha trace:")
    for verb, outcome, stage in d.trace:
        print(f"  {verb:<20} {outcome:<27} {stage}")


# =============================================================================
# 2. restart at every durable boundary
# =============================================================================


class CrashAfterCommit:
    """Delegates to the store's connection; once a statement matching
    ``match`` ran, the process dies right after the next COMMIT: the boundary
    is durable and nothing after it happened."""

    def __init__(self, connection, match) -> None:
        self._connection = connection
        self._match = match
        self.armed = False
        self.fired = False

    def execute(self, sql: str, params: tuple = ()):
        result = self._connection.execute(sql, params)
        if not self.fired:
            if sql == "ROLLBACK":
                self.armed = False
            elif sql == "COMMIT" and self.armed:
                self.fired = True
                raise SimulatedCrash("after a durable boundary")
            elif self._match(sql, params):
                self.armed = True
        return result

    def __getattr__(self, name: str):
        return getattr(self._connection, name)


def _state(value: str):
    return lambda sql, params: sql.startswith("UPDATE step_runs SET state") and params[0] == value


def _ticket(role: str):
    return lambda sql, params: sql.startswith("INSERT INTO dispatch_tickets") and role in params


BOUNDARIES = {
    # name: (match, stage after restart, what continuing reaches)
    "step contract issued": (lambda s, p: "INSERT INTO step_contract_issuances" in s, AlphaStage.ATTEMPT, "held"),
    "project run created": (lambda s, p: s.startswith("INSERT INTO project_runs"), AlphaStage.ATTEMPT, "held"),
    "step run created": (lambda s, p: s.startswith("INSERT INTO step_runs"), AlphaStage.ATTEMPT, "held"),
    "marked ready": (_state("READY"), AlphaStage.ATTEMPT, "held"),
    "attempt begun": (_state("EXECUTING"), AlphaStage.RECOVERY_REQUIRED, None),
    "implementer ticket": (_ticket("implementer"), AlphaStage.RECOVERY_REQUIRED, None),
    "write intent": (lambda s, p: s.startswith("INSERT INTO write_intents"), AlphaStage.RECOVERY_REQUIRED, None),
    "implementation returned": (_state("VERIFYING"), AlphaStage.RECOVERY_REQUIRED, None),
    "verifier ticket": (_ticket("verifier"), AlphaStage.RECOVERY_REQUIRED, None),
    "verification observed": (_state("REVIEWING"), AlphaStage.RECOVERY_REQUIRED, None),
    "review observed": (_state("ACCEPTANCE"), AlphaStage.DECISION, "held"),
    "planner ticket": (_ticket("planner"), AlphaStage.DECISION, "human"),
    "hold persisted": (lambda s, p: s.startswith("UPDATE dispatch_tickets SET held_envelope"),
                       AlphaStage.ACCEPTANCE, "already_held"),
}


@needs_windows
@pytest.mark.parametrize("name", list(BOUNDARIES))
def test_a_restart_at_every_durable_boundary_resumes_only_what_the_store_allows(d: V, name) -> None:
    match, stage, then = BOUNDARIES[name]
    approved(d)
    x_steps(d)
    d.close()
    d.open()
    proxy = CrashAfterCommit(d.store._conn, match)
    d.store._conn = proxy
    with pytest.raises(SimulatedCrash):
        AlphaDriver(d.session, announce=d.announced.append).run()
    assert proxy.fired
    d.waiter.queue.clear()  # the human's console died with A, or never started
    calls, requests = list(d.guard.calls), d.reviewer.requests
    status = invoke(d, "status")
    assert status.stage is stage, status.to_json()
    dirs = d.handoff_dirs()
    if then is None:
        # Interrupted in flight: reduced, never resumed, never re-dispatched.
        assert status.outcome is DriverOutcome.RECOVERY_REQUIRED
        for verb in ("run", "record-approval"):
            refused(invoke(d, verb))
        assert d.handoff_dirs() == dirs and d.guard.calls == calls and d.reviewer.requests == requests
        return
    if then == "already_held":
        assert status.outcome is DriverOutcome.AWAITING_HUMAN_ACCEPTANCE
        refused(invoke(d, "run"), "not_runnable")
    else:
        if stage is AlphaStage.ATTEMPT:
            x_steps(d)
        again = invoke(d, "run")
        if then == "human":  # a planner ticket without a hold is never asked again
            assert again.outcome is DriverOutcome.HUMAN_REQUIRED, again.to_json()
        else:
            assert again.outcome is DriverOutcome.AWAITING_HUMAN_ACCEPTANCE, again.to_json()
    assert len(tickets(d, "planner")) == 1
    assert d.guard.calls == ["_run_l2_apply_approved_file_edit", "_run_l2_review_approved_file_edit"]
    assert d.reviewer.requests == 1


@needs_windows
@pytest.mark.parametrize("kind", ["contract", "activation", "diff"])
def test_a_restart_while_recording_an_approval_records_it_once(d: V, kind) -> None:
    """A crash right after an approval's commit: the next invocation sees it
    recorded, never asks for it again, and a replayed record is refused."""
    stages = {"contract": 0, "activation": 1, "diff": 2}
    for _ in range(stages[kind]):
        approve(d)
    request = invoke(d, "request-approval")
    if request.challenge.subject_kind is K.EXACT_DIFF_APPROVAL:
        d.clock.now = APPROVED_AT + timedelta(minutes=1)
        o_sign(d, request, attested_at=APPROVED_AT)
    else:
        o_sign(d, request)
    d.close()
    d.open()
    proxy = CrashAfterCommit(d.store._conn, lambda s, p: s.startswith("UPDATE approval_challenges_v2 SET consumed_by"))
    d.store._conn = proxy
    with pytest.raises(SimulatedCrash):
        AlphaDriver(d.session).record_approval()
    status = invoke(d, "status")
    after = [AlphaStage.PLAN_ACTIVATION, AlphaStage.EXACT_DIFF_APPROVAL, AlphaStage.ATTEMPT][stages[kind]]
    assert status.stage is after
    consumed = rows(d, "approval_challenges_v2", "WHERE consumed_by IS NOT NULL")
    assert len(consumed) == stages[kind] + 1


# =============================================================================
# 3. stage discipline and caller inputs
# =============================================================================


@needs_windows
def test_no_verb_skips_a_stage_and_a_refused_verb_changes_nothing(d: V) -> None:
    # Every attestation a later stage needs is already in the inbox: none is read early.
    for kind, name in ATTESTATION_NAMES.items():
        d.put_inbox(name, b'{"not": "for this stage"}')
    before = frozen(d)
    for verb in ("run", "decline-acceptance"):
        refused(invoke(d, verb))
    refused(invoke(d, "record-approval"), "attestation_invalid")
    assert frozen(d) == before
    assert approve(d).stage is AlphaStage.PLAN_ACTIVATION
    before = frozen(d)
    for verb in ("run", "decline-acceptance"):
        refused(invoke(d, verb))
    assert frozen(d) == before
    approve(d)
    approve(d)
    before = frozen(d)
    for verb in ("request-approval", "record-approval", "decline-acceptance"):
        refused(invoke(d, verb), None)
    assert frozen(d) == before


@needs_windows
def test_run_without_the_exact_diff_approval_begins_no_attempt(d: V) -> None:
    approve(d)
    approve(d)
    before = frozen(d)
    report = invoke(d, "run")
    refused(report, "not_runnable")
    assert report.stage is AlphaStage.EXACT_DIFF_APPROVAL and frozen(d) == before
    assert rows(d, "project_runs") == [] and rows(d, "dispatch_tickets") == []


@needs_windows
@pytest.mark.parametrize("change", [
    {"project_contract": make_content(goal="Another project's goal.").model_dump(mode="json")},
    {"step_contract_proposal": {**make_proposal().model_dump(mode="json"), "requirements": ["Return 'bye'."]}},
], ids=["another contract", "another step contract"])
def test_a_definition_that_does_not_describe_the_recorded_alpha_refuses_everything(d: V, change) -> None:
    """Cross-project and cross-attempt confusion: the state root records one
    Alpha; a definition that is not it reaches nothing."""
    approved(d)
    if "step_contract_proposal" in change:
        x_steps(d)
        assert invoke(d, "run").outcome is DriverOutcome.AWAITING_HUMAN_ACCEPTANCE
    put_definition(d, definition_document(d, **change))
    before = frozen(d)
    for verb in alpha_driver.VERBS:
        refused(invoke(d, verb), "foreign_record")
    assert frozen(d) == before


@needs_windows
@pytest.mark.parametrize("data, category", [
    (None, "definition_unreadable"),
    (b'{"schema_version": "alpha-definition.v1", "schema_version": "alpha-definition.v1"}', "definition_invalid"),
    (b"[]", "definition_invalid"),
    (b"\xff\xfe{}", "definition_invalid"),
    ("extra", "definition_invalid"),
    ("v2", "definition_invalid"),
    ("other step", "definition_invalid"),
    ("reserved name", "definition_invalid"),
    ("policy", "definition_invalid"),
], ids=["missing", "duplicate key", "array", "bom", "extra field", "version", "step mismatch", "reserved name",
        "truthy policy"])
def test_a_malformed_definition_is_refused_before_anything_is_read(d: V, data, category) -> None:
    path = Path(d.inbox, DEFINITION_NAME)
    if data is None:
        path.unlink()
    elif type(data) is bytes:
        path.write_bytes(data)
    else:
        document = definition_document(d)
        if data == "extra":
            document["note"] = "x"
        elif data == "v2":
            document["schema_version"] = "alpha-definition.v2"
        elif data == "other step":
            document["step"] = {**document["step"], "step_id": "step-b"}
        elif data == "reserved name":
            document["approved_diff_name"] = ATTESTATION_NAMES[K.STEP_ACCEPTANCE]
        else:
            document["execution_policy"] = {**document["execution_policy"], "max_attempts": "1"}
        put_definition(d, document)
    before = frozen(d)
    for verb in alpha_driver.VERBS:
        refused(invoke(d, verb), category)
    assert frozen(d) == before


def test_the_driver_takes_a_session_and_verbs_nothing_else() -> None:
    for bad in (None, object(), "session"):
        with pytest.raises(TypeError):
            AlphaDriver(bad)
    with pytest.raises(TypeError):
        AlphaDriver.__init__(object.__new__(AlphaDriver), None)
    public = {n for n in dir(AlphaDriver) if not n.startswith("_")}
    assert public == {"status", "request_approval", "record_approval", "run", "decline_acceptance", "invoke"}
    import inspect

    for name in public - {"invoke"}:
        assert list(inspect.signature(getattr(AlphaDriver, name)).parameters) == ["self"], name
    assert list(inspect.signature(AlphaDriver.__init__).parameters) == ["self", "session", "announce"]


@needs_windows
@pytest.mark.parametrize("verb", ["RUN", "run ", "", None, 1, True, b"run", "complete"])
def test_an_unknown_verb_is_refused_without_touching_the_store(d: V, verb) -> None:
    before = frozen(d)
    with pytest.raises(ValueError):
        AlphaDriver(d.session).invoke(verb)
    assert frozen(d) == before


# =============================================================================
# 4. approvals
# =============================================================================


@needs_windows
def test_each_challenge_is_presented_with_a_subject_the_driver_rederived(d: V) -> None:
    contract = invoke(d, "request-approval")
    assert contract.subject["project_contract_sha256"] == contract.challenge.subject_sha256
    template = contract.statement_template
    assert template["state_root_id"] == d.root.root_id and template["challenge_id"] == contract.challenge.challenge_id
    assert (template["approver_id"], template["key_fingerprint_sha256"], template["attested_at"]) == (None,) * 3
    assert contract.attestation_inbox_name == ATTESTATION_NAMES[K.PROJECT_CONTRACT]
    o_sign(d, contract)
    invoke(d, "record-approval")
    activation = invoke(d, "request-approval")
    assert activation.subject["subject_sha256_recomputed_by_driver"] == activation.challenge.subject_sha256
    assert activation.subject["identity_boundary_sha256"] == d.session.boundary_sha256
    assert activation.subject["write_scope"] == d.scope.model_dump(mode="json")
    o_sign(d, activation)
    invoke(d, "record-approval")
    diff = invoke(d, "request-approval")
    inbox_artifact = Path(d.inbox, ARTIFACT_NAME).read_bytes()
    assert diff.subject["approved_diff_artifact_sha256"] == hashlib.sha256(inbox_artifact).hexdigest()
    assert diff.subject["subject_sha256_recomputed_by_driver"] == diff.challenge.subject_sha256


@needs_windows
def test_an_inbox_changed_after_the_diff_challenge_is_not_presented_for_signing(d: V) -> None:
    approve(d)
    approve(d)
    d.close()
    d.open()
    real = d.store.request_exact_diff_approval

    def then_change(**kwargs):
        challenge = real(**kwargs)
        d.put_artifact({**d.artifact, "note": "changed after the store read it"})
        return challenge

    d.store.request_exact_diff_approval = then_change  # an O-side edit racing A's two reads
    report = AlphaDriver(d.session).request_approval()
    refused(report, "subject_unconfirmed")
    assert report.challenge is None and report.statement_template is None


@needs_windows
def test_a_stale_challenge_records_nothing_and_a_fresh_one_does(d: V) -> None:
    request = invoke(d, "request-approval")
    o_sign(d, request)
    d.clock.now += timedelta(minutes=61)
    before = frozen(d)
    report = invoke(d, "record-approval")
    refused(report, "HumanAttestationRefusedError:challenge_expired")
    assert frozen(d) == before and report.stage is AlphaStage.CONTRACT_APPROVAL
    assert approve(d).stage is AlphaStage.PLAN_ACTIVATION


@needs_windows
@pytest.mark.parametrize("problem", ["missing", "garbage", "other kind", "unregistered key", "other approver",
                                     "replayed"])
def test_a_missing_or_invalid_approval_records_nothing(d: V, problem) -> None:
    request = invoke(d, "request-approval")
    name = ATTESTATION_NAMES[K.PROJECT_CONTRACT]
    if problem == "garbage":
        d.put_inbox(name, b"{")
    elif problem == "other kind":
        d.put_inbox(name, json.dumps({**json.loads(o_sign(d, request)), "subject_kind": "plan_activation"}).encode())
    elif problem == "unregistered key":
        o_sign(d, request, private=BOB)
    elif problem == "other approver":
        o_sign(d, request, approver="bob")
    elif problem == "replayed":
        o_sign(d, request)
        invoke(d, "record-approval")
        approve(d)  # the activation: a recorded contract attestation can never be consumed again
        activation_request = invoke(d, "request-approval")
        assert activation_request.challenge.subject_kind is K.EXACT_DIFF_APPROVAL
        d.put_inbox(ATTESTATION_NAMES[K.EXACT_DIFF_APPROVAL], Path(d.inbox, name).read_bytes())
    before = frozen(d)
    report = invoke(d, "record-approval")
    refused(report)
    assert frozen(d) == before


@needs_windows
def test_a_revoked_approval_stops_the_alpha_before_any_attempt(d: V) -> None:
    approved(d)
    _set_alice(d, revoked=True)
    before = frozen(d)
    for verb in alpha_driver.VERBS:
        report = invoke(d, verb)
        refused(report, "StateUntrustedError")
    assert frozen(d) == before and rows(d, "project_runs") == []


@needs_windows
def test_a_changed_identity_boundary_opens_no_session_and_consumes_nothing(d: V) -> None:
    approved(d)
    d.close()
    rename_execution_account(d)
    from ai_dev_orchestrator.integration.integration_store import IsolationUnprovenError

    with pytest.raises(IsolationUnprovenError):
        d.open()


@needs_windows
def test_a_config_for_another_workspace_gets_no_exact_diff_challenge(d: V, tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    d.config_bytes = write_config(Path(d.inbox) / CONFIG_NAME, os.path.realpath(elsewhere), d.script)
    put_definition(d)  # the scope binds this config, which names another workspace
    approve(d)
    approve(d)
    before = frozen(d)
    report = invoke(d, "request-approval")
    refused(report, "AuthorityRefusedError")
    assert "workspace" in report.refusal["detail"] and report.challenge is None
    assert frozen(d) == before


# =============================================================================
# 5. execution failures
# =============================================================================


def _wrong_owner(h: V, handoff: Path, outbox: Path) -> None:
    h.files.owner[_key(str(outbox / claim_receiver.STDOUT_NAME))] = O


def _other_text(h: V, handoff: Path, outbox: Path) -> None:
    h.target().write_bytes(OTHER_TEXT.encode("utf-8"))


def _target_reverted(h: V, handoff: Path, outbox: Path) -> None:
    h.target().write_bytes(Path(h.tmp, "original_target").read_bytes())


def _previous_claim(h: V) -> bytes:
    """The write ticket's claim, copied byte for byte into the review outbox."""
    return Path(h.announced[0]["outbox_directory"], claim_receiver.STDOUT_NAME).read_bytes()


def _forged_packet(h: V) -> bytes:
    base = h.tmp / "elsewhere"
    base.mkdir()
    return _frozen_stdout(base, h.reviewer, PASSING)


FAILURES = {
    "claim written by another identity": {"write": {"extra": _wrong_owner}},
    "write differs from the exact diff": {"write": {"extra": _other_text}},
    "no write claim": {"write": {"stdout": MISSING}},
    "no completion marker": {"write": {"complete": False}},
    "unparseable verification claim": {"review": {"stdout": b'{"schema_version": "nothing"}'}},
    "empty verification claim": {"review": {"run": False, "stdout": b""}},
    "a previous ticket's claim reused": {"review": {"run": False, "stdout": _previous_claim}},
    "m2 mismatch": {"review": {"extra": _target_reverted}},
}


@needs_windows
@pytest.mark.parametrize("name", list(FAILURES))
def test_a_failed_or_indeterminate_execution_ends_in_recovery_and_never_runs_again(d: V, name) -> None:
    approved(d)
    Path(d.tmp, "original_target").write_bytes(d.target().read_bytes())
    spec = FAILURES[name]
    x_step(d, run_frozen_writer, **spec.get("write", {}))
    if "review" in spec:
        x_step(d, run_frozen_review, **spec["review"])
    report = invoke(d, "run")
    assert report.outcome is DriverOutcome.RECOVERY_REQUIRED and report.stage is AlphaStage.RECOVERY_REQUIRED, \
        report.to_json()
    d.waiter.queue.clear()
    before = frozen(d)
    for verb in ("status", "run", "request-approval"):
        again = invoke(d, verb)
        assert again.stage is AlphaStage.RECOVERY_REQUIRED
        if verb != "status":
            refused(again)
    assert frozen(d) == before
    assert tickets(d, "planner") == []
    assert rows(d, "approval_challenges_v2", "WHERE subject_kind = 'step_acceptance'") == []


@needs_windows
def test_a_forged_review_packet_is_only_a_labeled_claim_and_completes_nothing_by_itself(d: V) -> None:
    """D-2': X can always print a genuine-shaped `approve` packet (here, one
    produced against a throwaway copy). With M2 holding, A cannot tell it from
    a real one, so it reaches the hold, but only as an execution claim the
    human sees labeled, and nothing completes without the human's signature."""
    approved(d)
    x_step(d, run_frozen_writer)
    x_step(d, run_frozen_review, run=False, stdout=_forged_packet)
    report = invoke(d, "run")
    assert report.outcome is DriverOutcome.AWAITING_HUMAN_ACCEPTANCE, report.to_json()
    request = invoke(d, "request-approval")
    bundle = json.loads(Path(d.published, request.subject["bundle_name"]).read_bytes())
    claims = bundle["execution_claims"]
    assert claims["claim_provenance"] == "execution_identity_unauthenticated"
    assert claims["review_command"]["review_verdict"] == "approve" and "repository code" in claims["statement"]
    before = frozen(d)
    for verb in ("run", "record-approval"):  # no signature placed: nothing completes
        refused(invoke(d, verb))
    assert frozen(d) == before
    declined = invoke(d, "decline-acceptance")
    assert declined.outcome is DriverOutcome.HUMAN_REQUIRED


@needs_windows
def test_a_review_verdict_other_than_approve_ends_at_a_human_with_nothing_to_sign(d: V) -> None:
    d.reviewer.content = CHANGES_REVIEW
    approved(d)
    x_steps(d)
    report = invoke(d, "run")
    assert report.outcome is DriverOutcome.HUMAN_REQUIRED and report.run["step_state"] == "HUMAN_REQUIRED"
    before = frozen(d)
    for verb in ("request-approval", "record-approval", "run", "decline-acceptance"):
        refused(invoke(d, verb))
    assert frozen(d) == before


@needs_windows
def test_a_claimed_failed_verification_ends_at_a_human(d: V) -> None:
    approved(d)
    from test_dl4b_s4_verification_claim import FAILING

    d.body(FAILING)
    x_steps(d)
    report = invoke(d, "run")
    assert report.outcome is DriverOutcome.HUMAN_REQUIRED and report.held is None, report.to_json()


# =============================================================================
# 6. acceptance, decline and completion
# =============================================================================


@needs_windows
def test_repeated_runs_never_dispatch_again(d: V) -> None:
    held(d)
    before = frozen(d)
    for _ in range(2):
        refused(invoke(d, "run"), "not_runnable")
    assert frozen(d) == before
    assert len(tickets(d, "implementer")) == len(tickets(d, "verifier")) == len(tickets(d, "reviewer")) == 1


@needs_windows
@pytest.mark.parametrize("problem", ["missing", "unregistered key", "an earlier approval's attestation",
                                     "attested in AIDO's future", "expired"])
def test_a_missing_or_invalid_acceptance_completes_nothing(d: V, problem) -> None:
    held(d)
    request = invoke(d, "request-approval")
    name = ATTESTATION_NAMES[K.STEP_ACCEPTANCE]
    if problem == "unregistered key":
        o_sign(d, request, private=BOB)
    elif problem == "an earlier approval's attestation":
        d.put_inbox(name, Path(d.inbox, ATTESTATION_NAMES[K.EXACT_DIFF_APPROVAL]).read_bytes())
    elif problem == "attested in AIDO's future":
        o_sign(d, request, attested_at=request.challenge.issued_at + timedelta(minutes=1))
        d.clock.now = request.challenge.issued_at  # signed "in the future" of AIDO's clock
    elif problem == "expired":
        o_sign(d, request)
        d.clock.now += timedelta(minutes=61)
    before = frozen(d)
    report = invoke(d, "record-approval")
    refused(report)
    assert report.stage is AlphaStage.ACCEPTANCE and frozen(d) == before
    if problem != "missing":
        Path(d.inbox, name).unlink()
    d.clock.now = max(d.clock.now, request.challenge.issued_at)
    assert accept(d).outcome is DriverOutcome.COMPLETE


@needs_windows
def test_the_human_declines_without_signing_and_nothing_can_complete_afterwards(d: V) -> None:
    held(d)
    request = invoke(d, "request-approval")
    o_sign(d, request)  # even a valid signature already in the inbox
    declined = invoke(d, "decline-acceptance")
    assert declined.outcome is DriverOutcome.HUMAN_REQUIRED and declined.run["step_state"] == "HUMAN_REQUIRED"
    assert declined.dl3_stop is None and declined.run["project_state"] == "ACTIVE"  # DL-3 blocks it on its next run
    before = frozen(d)
    for verb in ("record-approval", "request-approval", "run", "decline-acceptance"):
        refused(invoke(d, verb))
    assert frozen(d) == before
    assert rows(d, "step_runs")[0]["state"] == "HUMAN_REQUIRED"


@needs_windows
def test_a_signed_completion_is_applied_exactly_once(d: V) -> None:
    held(d)
    assert accept(d).outcome is DriverOutcome.COMPLETE
    transitions = rows(d, "transitions")
    before = frozen(d)
    for verb in ("record-approval", "request-approval", "decline-acceptance", "run"):
        report = invoke(d, verb)
        assert report.stage is AlphaStage.COMPLETE
        refused(report)
    assert frozen(d) == before and rows(d, "transitions") == transitions


@needs_windows
def test_a_crash_while_completing_completes_on_the_next_invocation_with_the_same_signature(d: V) -> None:
    held(d)
    request = invoke(d, "request-approval")
    o_sign(d, request)
    d.close()
    d.open()
    from test_dl4b_s2_integration_store import crash_at

    proxy = crash_at(d.store, "UPDATE approval_challenges_v2 SET consumed_by")
    with pytest.raises(SimulatedCrash):
        AlphaDriver(d.session).record_approval()
    assert not proxy.armed
    assert invoke(d, "status").stage is AlphaStage.ACCEPTANCE
    assert invoke(d, "record-approval").outcome is DriverOutcome.COMPLETE


# =============================================================================
# 7. the persisted state, not the driver, decides
# =============================================================================


@needs_windows
def test_the_driver_follows_state_it_did_not_create_and_remembers_nothing(d: V) -> None:
    held(d)
    driver = AlphaDriver(d.session)
    assert driver.status().stage is AlphaStage.ACCEPTANCE
    # The same driver instance, and the human's decline recorded through the
    # store API directly (not through the driver): the driver follows the store.
    from test_dl4b_s2_integration_store import step_request

    from ai_dev_orchestrator.control_plane import StepEvent

    step = d.store.get_step_run(rows(d, "step_runs")[0]["step_run_id"])
    d.store.apply_step_transition(step.step_run_id, step_request(step, StepEvent.ESCALATE, reason="Declined."))
    assert driver.status().stage is AlphaStage.HUMAN_REQUIRED
    refused(driver.record_approval())
    refused(driver.request_approval())


@needs_windows
def test_a_tampered_hold_is_untrusted_and_never_presented(d: V) -> None:
    held(d)
    d.close()
    conn = sqlite3.connect(d.root.store_path)
    conn.execute("UPDATE dispatch_tickets SET held_envelope = replace(held_envelope, 'deterministic', 'determined') "
                 "WHERE held_envelope IS NOT NULL")
    conn.commit()
    conn.close()
    d.open()
    report = invoke(d, "status")
    assert report.outcome is DriverOutcome.HUMAN_REQUIRED and report.stage is AlphaStage.UNTRUSTED
    assert not report.recovery["integrity_ok"]
    for verb in ("request-approval", "record-approval", "run"):
        refused(invoke(d, verb))
    assert rows(d, "approval_challenges_v2", "WHERE subject_kind = 'step_acceptance'") == []


@needs_windows
def test_a_second_project_run_can_be_neither_created_nor_adopted(d: V) -> None:
    """R7-1: store.v4 authorizes one project run per activation, so no
    supported call creates a second, and a second run row written into the
    file makes the store's own inventory proof refuse (before the driver's
    one-run backstop is even reached)."""
    from ai_dev_orchestrator.control_plane import AuthorityRefusedError

    approved(d)
    x_steps(d)
    invoke(d, "run")
    [row] = rows(d, "project_runs")
    before = frozen(d)
    with pytest.raises(AuthorityRefusedError):
        d.store.create_project_run(project_contract_sha256=row["project_contract_sha256"],
                                   execution_plan_sha256=row["execution_plan_sha256"])
    assert frozen(d) == before
    d.close()
    conn = sqlite3.connect(d.root.store_path)
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("INSERT INTO project_runs SELECT ?, project_id, project_contract_sha256, execution_plan_sha256, "
                 "execution_plan_version, state, state_version FROM project_runs", ("f" * 32,))
    conn.commit()
    conn.close()
    d.open()
    before = frozen(d)
    for verb in alpha_driver.VERBS:
        report = invoke(d, verb)
        refused(report, "StateUntrustedError")
        assert "more than one" in report.refusal["detail"]
    assert frozen(d) == before


# =============================================================================
# 8. the operator helper
# =============================================================================


@needs_windows
def test_the_operator_statement_is_exactly_the_statement_s1_verifies(d: V) -> None:
    request = invoke(d, "request-approval")
    presented = request.to_json().encode("utf-8")
    at = request.challenge.issued_at
    ours = alpha_operator.statement_bytes(presented, approver_id="alice",
                                          key_fingerprint_sha256=fingerprint(sk_blob(ALICE)), attested_at=at)
    assert ours == statement_bytes(private=ALICE, ch=request.challenge, attested_at=at, root=d.root.root_id)
    for at_bad in (request.challenge.issued_at - timedelta(seconds=1), request.challenge.expires_at):
        with pytest.raises(alpha_operator.OperatorInputError):
            alpha_operator.statement_bytes(presented, approver_id="alice",
                                           key_fingerprint_sha256=fingerprint(sk_blob(ALICE)), attested_at=at_bad)
    status = invoke(d, "status").to_json().encode("utf-8")
    for bad in (status, b"", b"[]", presented + b"{}", presented.replace(b'"request-approval"', b'"status"')):
        with pytest.raises(alpha_operator.OperatorInputError):
            alpha_operator.presented_challenge(bad)


def test_the_operator_cli_writes_only_stdout(tmp_path: Path, capsysbinary) -> None:
    report = tmp_path / "report.json"
    report.write_bytes(b"{}")
    assert alpha_operator.main(["statement", "--report", str(report), "--approver-id", "alice",
                                "--attested-at", "2026-10-27T18:00:00Z", "--key-fingerprint", "SHA256:x"]) == 1
    captured = capsysbinary.readouterr()
    assert captured.out == b"" and b"refused:" in captured.err
    assert sorted(os.listdir(tmp_path)) == ["report.json"]


# =============================================================================
# 9. the production entry points
# =============================================================================


def test_the_production_entry_point_refuses_without_an_isolated_interpreter(tmp_path: Path, capsys) -> None:
    assert not alpha_driver._isolated()  # pytest itself is not -I
    assert alpha_driver.main(["--state-root", str(tmp_path), "status"]) == 1
    document = json.loads(capsys.readouterr().out)
    assert document["outcome"] == "REFUSED" and document["refusal"]["category"] == "interpreter_not_isolated"
    assert os.listdir(tmp_path) == []


@pytest.mark.skipif(not WINDOWS, reason="the production boundary is Windows-only")
def test_the_production_entry_point_refuses_on_this_unprovisioned_host(tmp_path: Path) -> None:
    from ai_dev_orchestrator.control_plane import AidoStateRoot

    (tmp_path / "state").mkdir()
    root = AidoStateRoot.create(tmp_path / "state")
    before = sorted(os.listdir(root.path))
    result = subprocess.run([sys.executable, "-I", "-m", "ai_dev_orchestrator.integration.alpha_driver",
                             "--state-root", root.path, "status"], capture_output=True, text=True,
                            env={**os.environ, "PYTHONPATH": str(Path(integration.__file__).resolve().parents[2])})
    assert result.returncode == 1, result.stderr
    document = json.loads(result.stdout)
    assert document["outcome"] == "REFUSED" and "isolation_unproven" in document["refusal"]["detail"]
    assert sorted(os.listdir(root.path)) == before


# =============================================================================
# 10. static boundaries
# =============================================================================

_PACKAGE = Path(integration.__file__).resolve().parent
_FORBIDDEN_MODULES = {"subprocess", "socket", "httpx", "requests", "aiohttp", "urllib", "http", "asyncio",
                      "multiprocessing", "threading", "os", "ctypes", "shutil", "tempfile", "winreg", "_winapi"}
_HARNESS = ("ai_dev_orchestrator.llm", "ai_dev_orchestrator.github", "ai_dev_orchestrator.review",
            "ai_dev_orchestrator.verification", "ai_dev_orchestrator.file_editing",
            "ai_dev_orchestrator.supervised_implementer", "ai_dev_orchestrator.workspace",
            "ai_dev_orchestrator.diff_proposal", "ai_dev_orchestrator.patch_proposal", "ai_dev_orchestrator.plan",
            "ai_dev_orchestrator.handoff", "ai_dev_orchestrator.cli", "ai_dev_orchestrator.config_loader",
            "ai_dev_orchestrator.config", "ai_dev_orchestrator.redaction")


def test_the_driver_and_the_helper_import_no_model_harness_git_subprocess_or_network() -> None:
    for name in ("alpha_driver.py", "alpha_operator.py"):
        imported = _imports(_PACKAGE / name)
        assert not {m.split(".")[0] for m in imported} & _FORBIDDEN_MODULES, (name, imported)
        assert not [m for m in imported if m.startswith(_HARNESS)], (name, imported)
    operator = _imports(_PACKAGE / "alpha_operator.py")
    assert not [m for m in operator if m.startswith("ai_dev_orchestrator.integration")], operator
    source = (_PACKAGE / "alpha_driver.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = [n.func for n in ast.walk(tree) if isinstance(n, ast.Call)]
    methods = {f.attr for f in calls if isinstance(f, ast.Attribute)}
    functions = {f.id for f in calls if isinstance(f, ast.Name)}
    # No recorder phase, no handoff, wait, claim read or observation of its own,
    # no hold of its own, no file access, no sleep, no harness function.
    assert not methods & {"_perform_write_handoff", "_perform_review_handoff", "_perform_review_observation",
                          "publish_handoff", "await_completion", "read_claim", "observe_workspace",
                          "observe_git_control", "hold_acceptance_decision", "_publish_blob", "_read_inbox",
                          "write_bytes", "write_text", "read_bytes", "sleep", "Popen", "run_controlled_review",
                          "apply_approved_file_edit", "execute"}, methods
    assert not functions & {"open", "exec", "eval", "__import__", "compile"}, functions
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not names & {"Popen", "system", "popen", "startfile", "spawnv", "execv", "remove", "unlink", "rename",
                        "rmdir", "mkdir", "makedirs", "chmod", "putenv", "unsetenv", "kill", "rmtree",
                        "write_text", "write_bytes", "max_tokens", "_conn", "_authority", "_last_proof"}, names
    # Every private attribute the driver touches is its own: never the store's,
    # the session's, a port's or a record's (no raw connection, no capability).
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr.startswith("_") and not node.attr.startswith("__"):
            assert isinstance(node.value, ast.Name) and node.value.id == "self", ast.unparse(node)


def test_the_driver_loads_nothing_that_executes_when_imported() -> None:
    code = (
        "import sys\n"
        "import ai_dev_orchestrator.integration.alpha_driver, ai_dev_orchestrator.integration.alpha_operator\n"
        "bad = [m for m in sys.modules if m.split('.')[0] in ('subprocess', 'socket', 'httpx') or m.startswith((\n"
        "  'ai_dev_orchestrator.file_editing', 'ai_dev_orchestrator.workspace', 'ai_dev_orchestrator.llm',\n"
        "  'ai_dev_orchestrator.verification', 'ai_dev_orchestrator.review', 'ai_dev_orchestrator.diff_proposal',\n"
        "  'ai_dev_orchestrator.cli', 'ai_dev_orchestrator.supervised_implementer'))]\n"
        "print(bad)\n"
    )
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, check=True,
                         env={**os.environ, "PYTHONPATH": str(_PACKAGE.parent.parent)}).stdout.strip()
    assert out == "[]", out


def test_no_model_call_surface_and_no_cli_command_reaches_the_driver() -> None:
    cli_source = (_PACKAGE.parent / "cli.py").read_text(encoding="utf-8")
    assert "alpha_driver" not in cli_source and "alpha_operator" not in cli_source
    for name in ("alpha_driver.py", "alpha_operator.py"):
        source = (_PACKAGE / name).read_text(encoding="utf-8")
        for word in ("AIDO_LITELLM", "AIDO_VLLM", "GITHUB_TOKEN", "max_tokens", r"\benviron\b", r"\bgetenv\b"):
            assert not re.search(word, source), (name, word)


def test_the_report_and_definition_are_presentation_only() -> None:
    import inspect

    from ai_dev_orchestrator.integration.integration_store import IntegrationStore

    for name, method in inspect.getmembers(IntegrationStore, inspect.isfunction):
        if name.startswith("_"):
            continue
        hints = " ".join(str(p.annotation) for p in inspect.signature(method).parameters.values())
        assert "DriverReport" not in hints and "AlphaDefinition" not in hints, name
    with pytest.raises(ValueError):
        parse_definition("{}")

