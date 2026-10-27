"""DL-4B S6 — the human acceptance lifecycle in store.v4, offline.

The harness is S4/S5's: a synthetic Git clone under pytest ``tmp_path``, S0/S1
synthetic Windows worlds, the production ``WindowsAuthorityFiles`` with
synthetic owners, and the human's two X-side steps simulated by running the
frozen, unchanged ``l2-apply-approved-file-edit`` and
``l2-review-approved-file-edit`` in-process (reviewer behind an
``httpx.MockTransport``, verification a synthetic script). S6 adds the
boundary's ``published/`` directory, moved to a real directory, and signs the
step acceptance with S1's test-only software key.

S6 runs nothing: no model, no Git, no subprocess, no network and no
repository code. The planner is the deterministic Alpha rule.

Sections: the planner rule; the hold; restart and crashes; the acceptance
subject and bundle; signed completion; attestation failures; decline;
tampering and recovery; v2/v3 unchanged; DL-3 → DL-2 end to end; static
boundaries.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from datetime import timedelta, timezone
from pathlib import Path

import pytest
from test_control_plane_dl2 import ACCEPT, db_path, make  # noqa: F401 - DL-2's offline fixtures
from test_dl4b_s0_identity_boundary import ADMIN_FULL, OICI, RX, A, O, allow
from test_dl4b_s1_attestation_verifier import BOB
from test_dl4b_s2_integration_store import (
    SimulatedCrash,
    _put_ancestors,
    _set_alice,
    crash_at,
    make_content,
    snapshot,
    step_request,
)
from test_dl4b_s3_write_handoff import _planned
from test_dl4b_s4_verification_claim import (
    APPROVE_REVIEW,
    CHANGES_REVIEW,
    FAILING,
    V,
    _imports,
    _x_steps,
    make_v,
    review_env,  # noqa: F401 - fixture
    verified,
)
from test_dl4b_s5_review_evidence import HUMAN_REVIEW, NoSecondRun, ReviewingPorts, reviewed

import ai_dev_orchestrator.integration as integration
from ai_dev_orchestrator.control_plane import (
    AuthorityRefusedError,
    InnerLoopStop,
    OuterLoopStop,
    PlannerDecision,
    ProjectOuterLoop,
    ProjectState,
    RefusalCode,
    StateUntrustedError,
    StepEvent,
    StepInnerLoop,
    StepState,
    TransitionRefused,
    bind_role_output,
)
from ai_dev_orchestrator.control_plane.attestation_v2 import ApprovalSubjectKindV2 as K
from ai_dev_orchestrator.control_plane.integration_records import (
    ALPHA_PLANNER_RATIONALE,
    CLAIM_PROVENANCE_UNAUTHENTICATED,
    StepAcceptanceSubjectV2,
    envelope_bytes,
)
from ai_dev_orchestrator.control_plane.models import REQUIRED_STEP_ACCEPTANCE_APPROVAL_TEXT, HumanStepAcceptance
from ai_dev_orchestrator.control_plane.store import ControlPlaneStore
from ai_dev_orchestrator.integration.acceptance_bundle import (
    AIDO_OBSERVED_STATEMENT,
    EXECUTION_CLAIM_STATEMENT,
    bundle_name,
)
from ai_dev_orchestrator.integration.alpha_planner import AlphaPlannerRule, mint_alpha_planner_rule
from ai_dev_orchestrator.integration.attestation_verifier import AttestationRefusal as R
from ai_dev_orchestrator.integration.attestation_verifier import HumanAttestationRefusedError
from ai_dev_orchestrator.integration.integration_store import IntegrationStore
from ai_dev_orchestrator.integration.security_descriptor import FILE_ALL_ACCESS

WINDOWS = sys.platform == "win32"
needs_windows = pytest.mark.skipif(not WINDOWS, reason="real Windows file handles and a synthetic Windows boundary")


# =============================================================================
# harness
# =============================================================================


@pytest.fixture
def v(tmp_path: Path, review_env):
    if not WINDOWS or shutil.which("git") is None:
        pytest.skip("needs Windows and git")
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
    harness.open()
    yield harness
    harness.close()


def step_of(v: V, chain):
    return v.store.get_step_run(chain.step.step_run_id)


def pticket_for(v: V, chain):
    step = step_of(v, chain)
    return v.store.issue_dispatch_ticket(step.step_run_id, role="planner", expected_state_version=step.state_version)


def decide(v: V, chain, ticket):
    contract = v.store.get_step_contract(chain.contract.sha256)
    return v.session.planner.decide_step(step_contract=contract, step_run=step_of(v, chain), dispatch=ticket)


def decide_acceptance(v: V, chain, bound, *, decision=None):
    step = step_of(v, chain)
    return v.store.apply_step_transition(step.step_run_id, step_request(
        step, StepEvent.DECIDE_ACCEPTANCE, planner_decision=decision or bound.output), role_output=bound)


def hold(v: V, chain, bound):
    step = step_of(v, chain)
    return v.store.hold_acceptance_decision(step.step_run_id, expected_state_version=step.state_version,
                                            role_output=bound)


def held(v: V, content: str = APPROVE_REVIEW):
    """Through S6's hold: the planner rule answered, the validator refused
    exactly HUMAN_ACCEPTANCE_MISSING, and the decision held."""
    chain, _, _, _ = reviewed(v, content)
    pticket = pticket_for(v, chain)
    pbound = decide(v, chain, pticket)
    with pytest.raises(TransitionRefused) as refused:
        decide_acceptance(v, chain, pbound)
    assert refused.value.code is RefusalCode.HUMAN_ACCEPTANCE_MISSING
    record = hold(v, chain, pbound)
    return chain, pticket, pbound, record


def acceptance_for(chain, att) -> HumanStepAcceptance:
    return HumanStepAcceptance(step_contract_sha256=chain.contract.sha256, attempt=1, approved_by=att.approver_id,
                               approved_at=att.attested_at, approval_text=REQUIRED_STEP_ACCEPTANCE_APPROVAL_TEXT,
                               source="manual")


def sign(v: V, challenge, **options):
    return v.sign(challenge, **options)


def complete(v: V, chain, pbound, att, *, request=None, role_output=None, acceptance=None, decision=None):
    step = step_of(v, chain)
    request = request or step_request(step, StepEvent.DECIDE_ACCEPTANCE, planner_decision=decision or pbound.output,
                                      human_acceptance=acceptance or acceptance_for(chain, att))
    return v.store.apply_step_transition(step.step_run_id, request, role_output=role_output or pbound,
                                         human_attestation=att)


def accepted(v: V, content: str = APPROVE_REVIEW):
    chain, pticket, pbound, record = held(v, content)
    challenge = v.store.request_step_acceptance(chain.step.step_run_id)
    att = sign(v, challenge)
    applied = complete(v, chain, pbound, att)
    return chain, pticket, pbound, challenge, att, applied


def tickets(v: V, role: str) -> list[sqlite3.Row]:
    return v.store._conn.execute("SELECT * FROM dispatch_tickets WHERE role = ?", (role,)).fetchall()


def published_files(v: V) -> list[str]:
    return sorted(os.listdir(v.published))


def raw(v: V, sql: str, params: tuple = ()) -> None:
    """Rewrite the closed store directly, as an actor holding the file would."""
    v.close()
    conn = sqlite3.connect(v.root.store_path)
    conn.execute("PRAGMA ignore_check_constraints = ON")
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(sql, params)
    conn.commit()
    conn.close()


class Planner:
    """A planner port that counts its calls and answers with the Alpha rule."""

    def __init__(self, v: V) -> None:
        self.v = v
        self.calls = 0

    def decide_step(self, **kwargs):
        self.calls += 1
        return self.v.session.planner.decide_step(**kwargs)


class S6Ports(ReviewingPorts):
    def __init__(self, v: V, planner=None) -> None:
        super().__init__(v.session.implementer, v.session.verifier, v.session.reviewer)
        self.planner_port = planner or Planner(v)

    def role_ports(self):
        ports = super().role_ports()
        return type(ports)(planner=self.planner_port, tester=ports.tester, implementer=ports.implementer,
                           verifier=ports.verifier, reviewer=ports.reviewer)


def inner(v: V, chain, ports: S6Ports):
    step = step_of(v, chain)
    return StepInnerLoop(v.store, ports.role_ports()).run(
        project_run=v.store.get_project_run(chain.project.project_run_id), step_run=step,
        project_contract=chain.pc, execution_plan=chain.plan,
        step_contract=v.store.get_step_contract(chain.contract.sha256))


# =============================================================================
# 1. the deterministic planner rule
# =============================================================================


@needs_windows
def test_the_rule_recommends_acceptance_only_for_proven_verified_and_approved(v: V, monkeypatch) -> None:
    chain, _, _, _ = reviewed(v)
    guard = NoSecondRun(v, monkeypatch)
    pticket = pticket_for(v, chain)
    pbound = decide(v, chain, pticket)
    decision = pbound.output
    assert decision.recommendation.value == "RECOMMEND_STEP_ACCEPT"
    assert decision.rationale == ALPHA_PLANNER_RATIONALE["accept"]
    assert [ref.split(":")[0] for ref in decision.evidence_refs] == [
        "write-evidence", "m0", "m1", "verification-evidence", "m2", "review-evidence"]
    assert pbound.ticket_id == pticket.ticket_id and pbound.role == "planner"
    # Deterministic: asked twice, the rule answers the same bytes.
    assert envelope_bytes(decide(v, chain, pticket)) == envelope_bytes(pbound)
    guard.check()


@needs_windows
@pytest.mark.parametrize("content, ground", [(CHANGES_REVIEW, "review_not_approve"),
                                             (HUMAN_REVIEW, "review_not_approve"),
                                             (None, "verification_not_verified")],
                         ids=["changes_requested", "needs_human_review", "verification_failed"])
def test_anything_short_of_verified_and_approve_ends_at_a_human(v: V, content, ground) -> None:
    """Required cases 1 and 3: no review evidence (a claimed failed
    verification never reaches REVIEWING), or a verdict other than approve."""
    if content is None:
        v.body(FAILING)
        chain, _, _ = verified(v)
    else:
        chain, _, _, _ = reviewed(v, content)
    pbound = decide(v, chain, pticket_for(v, chain))
    assert pbound.output.recommendation.value == "HUMAN_REQUIRED"
    assert pbound.output.rationale == ALPHA_PLANNER_RATIONALE[ground]
    with pytest.raises(AuthorityRefusedError, match="applied, never held"):
        hold(v, chain, pbound)
    decide_acceptance(v, chain, pbound)  # the validator applies it; nothing is held
    step = step_of(v, chain)
    assert step.state is StepState.HUMAN_REQUIRED
    assert [row["held_envelope"] for row in tickets(v, "planner")] == [None]
    with pytest.raises(AuthorityRefusedError):
        v.store.request_step_acceptance(step.step_run_id)
    v.close()
    report = v.open().recover(chain.project.project_run_id)
    assert report.integrity_ok, report.integrity_issues


@needs_windows
@pytest.mark.parametrize("missing", ["review evidence", "verification evidence", "review claim blob"])
def test_the_rule_never_recommends_acceptance_without_s4_and_s5_evidence(v: V, missing) -> None:
    """Required case 1. The public path refuses to read an untrusted run at
    all; the rule itself, asked anyway, fails closed to HUMAN_REQUIRED."""
    chain, _, _, rbound = reviewed(v)
    step = step_of(v, chain)
    conn = v.store._conn
    conn.execute("PRAGMA foreign_keys = OFF")
    if missing == "review claim blob":
        path = Path(v.root.path, "evidence", "claims", rbound.output.evidence_sha256)
        os.chmod(path, 0o666)
        path.write_bytes(path.read_bytes() + b" ")
    else:
        conn.execute({"review evidence": "DELETE FROM review_evidence",
                      "verification evidence": "DELETE FROM verification_evidence_v2"}[missing])
    facts = v.store._alpha_facts(step.step_run_id, step.attempt, step.state_version)
    assert facts.ground == "evidence_unproven" and facts.refs == ()
    with pytest.raises(StateUntrustedError):
        pticket_for(v, chain)
    with pytest.raises(StateUntrustedError):
        v.store.held_acceptance_decision(step.step_run_id, expected_state_version=step.state_version)


@needs_windows
@pytest.mark.parametrize("where", ["step row", "step row and transition"])
def test_a_tampered_cached_verdict_never_becomes_a_favorable_decision(v: V, where) -> None:
    """Required cases 2 and 19 (S5's R5-8): the model asked for changes; the
    cached verdict is rewritten to 'approve'. The rule reads the review
    evidence, the run is untrusted, and recovery escalates it to a human."""
    chain, _, _, _ = reviewed(v, CHANGES_REVIEW)
    step = step_of(v, chain)
    raw(v, "UPDATE step_runs SET review_verdict = 'approve'")
    if where.endswith("transition"):
        raw(v, "UPDATE transitions SET review_verdict = 'approve' WHERE event = 'review_observed'")
    store = v.open()
    # The row alone: the rule reads the evidence's verdict. Row and transition:
    # the transition contradicts the evidence, so the rule fails closed.
    expected = "evidence_unproven" if where.endswith("transition") else "review_not_approve"
    assert store._alpha_facts(step.step_run_id, 1, step.state_version).ground == expected
    with pytest.raises(StateUntrustedError):
        store.get_step_run(step.step_run_id)
    report = store.recover(chain.project.project_run_id)
    assert not report.integrity_ok and report.escalated_step_run_ids == (step.step_run_id,)
    assert store.inspect_step_run(step.step_run_id).columns["state"] == StepState.HUMAN_REQUIRED.value
    for call in (lambda: pticket_for(v, chain), lambda: store.request_step_acceptance(step.step_run_id),
                 lambda: store.held_acceptance_bundle(step.step_run_id)):
        with pytest.raises((AuthorityRefusedError, StateUntrustedError, TransitionRefused)):
            call()
    assert store._conn.execute("SELECT verdict FROM review_evidence").fetchone()[0] == "changes_requested"
    assert tickets(v, "planner") == []


@needs_windows
def test_a_forged_planner_decision_is_neither_applied_nor_held(v: V) -> None:
    """Required case 2 (a forged decision): the reviewer asked for changes;
    a store holder mints an accept decision for the genuine planner ticket."""
    chain, _, _, _ = reviewed(v, CHANGES_REVIEW)
    pticket = pticket_for(v, chain)
    genuine = decide(v, chain, pticket)
    forged = bind_role_output(pticket, PlannerDecision(
        step_contract_sha256=chain.contract.sha256, attempt=1, recommendation="RECOMMEND_STEP_ACCEPT",
        rationale=ALPHA_PLANNER_RATIONALE["accept"], evidence_refs=genuine.output.evidence_refs))
    before = snapshot(v.store)
    with pytest.raises(AuthorityRefusedError, match="deterministic Alpha rule"):
        decide_acceptance(v, chain, forged)
    with pytest.raises(AuthorityRefusedError, match="deterministic Alpha rule"):
        hold(v, chain, forged)
    assert snapshot(v.store) == before
    assert step_of(v, chain).state is StepState.ACCEPTANCE


# =============================================================================
# 2. the hold
# =============================================================================


@needs_windows
def test_a_hold_stores_the_canonical_envelope_and_writes_no_transition(v: V, monkeypatch) -> None:
    chain, _, _, _ = reviewed(v)
    guard = NoSecondRun(v, monkeypatch)
    pticket = pticket_for(v, chain)
    pbound = decide(v, chain, pticket)
    step = step_of(v, chain)
    events = [r.event for r in v.store.transitions_for(step.step_run_id)]
    with pytest.raises(TransitionRefused) as refused:
        decide_acceptance(v, chain, pbound)
    assert refused.value.code is RefusalCode.HUMAN_ACCEPTANCE_MISSING
    record = hold(v, chain, pbound)
    assert (record.ticket_id, record.step_run_id, record.state_version, record.duplicate) == (
        pticket.ticket_id, step.step_run_id, step.state_version, False)
    assert record.envelope == pbound and record.envelope_sha256 == hashlib.sha256(envelope_bytes(pbound)).hexdigest()
    [row] = tickets(v, "planner")
    assert row["held_envelope"].encode("utf-8") == envelope_bytes(pbound) and row["consumed_request_id"] is None
    after = step_of(v, chain)
    assert (after.state, after.state_version) == (StepState.ACCEPTANCE, step.state_version)
    assert [r.event for r in v.store.transitions_for(step.step_run_id)] == events
    assert v.store.held_acceptance_decision(step.step_run_id, expected_state_version=step.state_version) == record
    guard.check()


@needs_windows
def test_a_repeated_hold_is_a_receipt_and_another_envelope_is_refused(v: V) -> None:
    """Required case 8."""
    chain, pticket, pbound, record = held(v)
    before = snapshot(v.store)
    again = hold(v, chain, pbound)
    assert again.duplicate and again.envelope_sha256 == record.envelope_sha256
    other = bind_role_output(pticket, pbound.output.model_copy(update={"rationale": "Accept it."}))
    with pytest.raises(AuthorityRefusedError, match="never replaced"):
        hold(v, chain, other)
    assert snapshot(v.store) == before


@needs_windows
@pytest.mark.parametrize("change", [
    {"ticket_id": "f" * 32}, {"step_run_id": "c" * 32}, {"project_run_id": "d" * 32},
    {"role": "reviewer"}, {"step_contract_sha256": "a" * 64},
], ids=lambda change: ",".join(change))
def test_an_envelope_for_another_ticket_step_or_run_is_never_held(v: V, change) -> None:
    """Required case 5."""
    chain, _, _, _ = reviewed(v)
    pticket = pticket_for(v, chain)
    pbound = decide(v, chain, pticket)
    data = {**pbound.model_dump(mode="json"), **change}
    if "step_contract_sha256" in change:
        data["output"] = {**data["output"], "step_contract_sha256": change["step_contract_sha256"]}
    from ai_dev_orchestrator.control_plane import BoundRoleOutput

    before = snapshot(v.store)
    try:
        other = BoundRoleOutput.model_validate(data)
    except ValueError:
        other = None  # the envelope type itself refuses it (a planner output answering another role)
    if other is not None:
        with pytest.raises((AuthorityRefusedError, TransitionRefused)):
            hold(v, chain, other)
    assert snapshot(v.store) == before
    hold(v, chain, pbound)


@needs_windows
def test_a_hold_at_a_stale_version_or_attempt_is_refused(v: V) -> None:
    """Required case 5 (version, attempt)."""
    chain, _, _, _ = reviewed(v)
    pticket = pticket_for(v, chain)
    pbound = decide(v, chain, pticket)
    step = step_of(v, chain)
    before = snapshot(v.store)
    for version in (step.state_version - 1, step.state_version + 1):
        with pytest.raises(AuthorityRefusedError, match="current version"):
            v.store.hold_acceptance_decision(step.step_run_id, expected_state_version=version, role_output=pbound)
    with pytest.raises(ValueError):
        bind_role_output(pticket, pbound.output.model_copy(update={"attempt": 2}))  # misbound by type
    with pytest.raises(AuthorityRefusedError):
        v.store.hold_acceptance_decision(step.step_run_id, expected_state_version=step.state_version,
                                         role_output=pbound.model_dump())
    assert snapshot(v.store) == before


@needs_windows
def test_decide_acceptance_without_a_held_decision_completes_nothing(v: V) -> None:
    """Required case 6: a signed-looking DECIDE_ACCEPTANCE before any hold."""
    chain, _, _, _ = reviewed(v)
    pticket = pticket_for(v, chain)
    pbound = decide(v, chain, pticket)
    step = step_of(v, chain)
    before = snapshot(v.store)
    with pytest.raises(AuthorityRefusedError, match="held planner decision"):
        v.store.request_step_acceptance(step.step_run_id)
    content = make_content(goal="Not an acceptance.")
    att = sign(v, v.store.request_project_contract_approval(content))
    before = snapshot(v.store)
    with pytest.raises(AuthorityRefusedError):
        complete(v, chain, pbound, att)
    with pytest.raises(AuthorityRefusedError, match="DL-4B S6"):
        v.store.apply_step_transition(step.step_run_id, step_request(
            step, StepEvent.DECIDE_ACCEPTANCE, planner_decision=pbound.output,
            human_acceptance=acceptance_for(chain, att)), role_output=pbound)
    assert snapshot(v.store) == before and step_of(v, chain).state is StepState.ACCEPTANCE


@needs_windows
def test_dl2_escalates_when_the_store_refuses_the_hold(v: V, monkeypatch) -> None:
    """§7: a refused hold ends at HUMAN_REQUIRED (DL-2's existing escalation)."""
    chain, _, _, _ = reviewed(v)

    def refuse(*args, **kwargs):
        raise AuthorityRefusedError("simulated hold refusal")

    monkeypatch.setattr(v.store, "hold_acceptance_decision", refuse)
    planner = Planner(v)
    outcome = inner(v, chain, S6Ports(v, planner))
    assert outcome.stop is InnerLoopStop.STEP_HUMAN_REQUIRED and planner.calls == 1
    assert outcome.cause == "human_acceptance_unavailable"
    assert [row["held_envelope"] for row in tickets(v, "planner")] == [None]


# =============================================================================
# 3. restart and crashes
# =============================================================================


@needs_windows
def test_a_held_decision_survives_restart_and_the_planner_is_never_asked_again(v: V) -> None:
    """Required case 9."""
    chain, _, _, record = held(v)
    planner = Planner(v)
    outcome = inner(v, chain, S6Ports(v, planner))
    assert outcome.stop is InnerLoopStop.AWAITING_HUMAN_ACCEPTANCE and outcome.dispatches == ()
    for _ in range(2):
        v.close()
        store = v.open()
        report = store.recover(chain.project.project_run_id)
        assert report.integrity_ok, report.integrity_issues
        step = store.get_step_run(chain.step.step_run_id)
        assert store.held_acceptance_decision(step.step_run_id, expected_state_version=step.state_version) == record
        outcome = inner(v, chain, S6Ports(v, planner))
        assert outcome.stop is InnerLoopStop.AWAITING_HUMAN_ACCEPTANCE
        assert outcome.cause == "awaiting_human_acceptance"
    outer = ProjectOuterLoop(v.store, S6Ports(v, planner).role_ports()).run(
        project_run=v.store.get_project_run(chain.project.project_run_id), project_contract=chain.pc,
        execution_plan=chain.plan)
    assert outer.stop is OuterLoopStop.STEP_NOT_SETTLED and outer.escalation is None
    assert planner.calls == 0 and len(tickets(v, "planner")) == 1
    assert step_of(v, chain).state is StepState.ACCEPTANCE


@needs_windows
@pytest.mark.parametrize("persisted", [False, True], ids=["before", "after"])
def test_a_crash_around_the_hold_never_asks_the_planner_again(v: V, persisted) -> None:
    """Required case 10. Before persistence nothing is held, and the planner
    ticket already exists, so the next DL-2 call escalates instead of asking
    again (no silent regeneration). After it, the hold stands."""
    chain, _, _, _ = reviewed(v)
    pbound = decide(v, chain, pticket_for(v, chain))
    if persisted:
        proxy = crash_at(v.store, "COMMIT", after=True)
    else:
        proxy = crash_at(v.store, "UPDATE dispatch_tickets SET held_envelope", after=True)
    with pytest.raises(SimulatedCrash):
        hold(v, chain, pbound)
    assert not proxy.armed
    v.close()
    store = v.open()
    report = store.recover(chain.project.project_run_id)
    assert report.integrity_ok, report.integrity_issues
    step = store.get_step_run(chain.step.step_run_id)
    assert (store.held_acceptance_decision(step.step_run_id, expected_state_version=step.state_version)
            is not None) is persisted
    planner = Planner(v)
    outcome = inner(v, chain, S6Ports(v, planner))
    assert planner.calls == 0 and len(tickets(v, "planner")) == 1
    if persisted:
        assert outcome.stop is InnerLoopStop.AWAITING_HUMAN_ACCEPTANCE
    else:
        assert outcome.stop is InnerLoopStop.STEP_HUMAN_REQUIRED
        assert outcome.cause == "dispatch_ticket_refused"


@needs_windows
def test_a_crash_while_completing_consumes_nothing_and_the_same_signature_still_completes(v: V) -> None:
    chain, _, pbound, _ = held(v)
    att = sign(v, v.store.request_step_acceptance(chain.step.step_run_id))
    proxy = crash_at(v.store, "UPDATE approval_challenges_v2 SET consumed_by")
    with pytest.raises(SimulatedCrash):
        complete(v, chain, pbound, att)
    assert not proxy.armed
    v.close()
    store = v.open()
    assert store.recover(chain.project.project_run_id).integrity_ok
    assert store.get_step_run(chain.step.step_run_id).state is StepState.ACCEPTANCE
    assert complete(v, chain, pbound, att).current_state == StepState.COMPLETE.value


# =============================================================================
# 4. the acceptance subject and the bundle
# =============================================================================

SUBJECT_FIELDS = {
    "schema_version", "kind", "project_run_id", "step_run_id", "step_contract_sha256", "attempt", "state_version",
    "verification_evidence_sha256", "write_scope_sha256", "write_evidence_sha256", "review_evidence_sha256",
    "planner_envelope_sha256", "identity_boundary_sha256", "m0_observation_sha256", "m1_observation_sha256",
    "m2_observation_sha256", "claim_provenance",
}


@needs_windows
def test_the_acceptance_subject_binds_every_reproven_record(v: V) -> None:
    chain, pticket, pbound, record = held(v)
    challenge = v.store.request_step_acceptance(chain.step.step_run_id)
    subject = v.store.held_acceptance_bundle(chain.step.step_run_id).subject
    assert set(StepAcceptanceSubjectV2.model_fields) == SUBJECT_FIELDS
    assert challenge.subject_kind is K.STEP_ACCEPTANCE
    assert challenge.subject_sha256 == subject.sha256 == record.subject_sha256
    assert challenge.required_approval_text == REQUIRED_STEP_ACCEPTANCE_APPROVAL_TEXT
    step = step_of(v, chain)
    manifests = {row["kind"]: row["manifest_sha256"] for row in v.store._conn.execute(
        "SELECT kind, manifest_sha256 FROM authority_observations")}
    assert (subject.project_run_id, subject.step_run_id, subject.step_contract_sha256, subject.attempt,
            subject.state_version) == (step.project_run_id, step.step_run_id, step.step_contract_sha256, 1,
                                       step.state_version)
    assert (subject.m0_observation_sha256, subject.m1_observation_sha256, subject.m2_observation_sha256) == (
        manifests["m0"], manifests["m1"], manifests["m2"])
    assert subject.write_scope_sha256 == v.scope.sha256
    assert subject.identity_boundary_sha256 == v.store.boundary_sha256
    assert subject.planner_envelope_sha256 == hashlib.sha256(envelope_bytes(pbound)).hexdigest()
    assert subject.claim_provenance == CLAIM_PROVENANCE_UNAUTHENTICATED
    refs = dict(ref.split(":") for ref in pbound.output.evidence_refs)
    assert (subject.write_evidence_sha256, subject.verification_evidence_sha256, subject.review_evidence_sha256) == (
        refs["write-evidence"], refs["verification-evidence"], refs["review-evidence"])
    # Every bound value moves the digest.
    for name in SUBJECT_FIELDS - {"schema_version", "kind", "claim_provenance", "attempt", "state_version"}:
        assert subject.model_copy(update={name: "1" * 64}).sha256 != subject.sha256, name
    assert subject.model_copy(update={"state_version": subject.state_version + 1}).sha256 != subject.sha256


@needs_windows
def test_the_bundle_separates_observed_facts_from_execution_claims_and_is_published(v: V) -> None:
    chain, _, pbound, record = held(v)
    bundle = v.store.held_acceptance_bundle(chain.step.step_run_id)
    content = bundle.content
    assert published_files(v) == []  # a read publishes nothing
    assert content["acceptance"]["subject"] == bundle.subject.model_dump(mode="json")
    assert content["acceptance"]["subject_sha256"] == bundle.subject.sha256 == record.subject_sha256
    observed, claims = content["aido_observed"], content["execution_claims"]
    assert observed["statement"] == AIDO_OBSERVED_STATEMENT and observed["evidence_class"] == "authority_observation"
    assert claims["statement"] == EXECUTION_CLAIM_STATEMENT and claims["evidence_class"] == "execution_claim"
    assert claims["claim_provenance"] == CLAIM_PROVENANCE_UNAUTHENTICATED
    assert (claims["review_command"]["verification_outcome"], claims["review_command"]["review_verdict"]) == (
        "verified", "approve")
    assert "verdict" not in json.dumps(observed) and "outcome" not in json.dumps(observed)
    assert set(observed["observations"]) == {"m0", "m1", "m2"}
    assert observed["approved_change"]["path"] == v.scope.path
    assert content["planner"]["held_envelope"] == pbound.model_dump(mode="json")
    assert content["step"]["step_contract_sha256"] == chain.contract.sha256
    published = v.store.publish_acceptance_bundle(chain.step.step_run_id)
    assert published.name == bundle_name(bundle.subject.sha256) and published.sha256 == bundle.sha256
    assert published_files(v) == sorted(published.names)
    assert Path(v.published, published.name).read_bytes() == bundle.document
    for blob in content["blobs"]:
        data = Path(v.published, blob["published_name"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == blob["sha256"]
        assert data == Path(v.root.path, *blob["state_root_name"].split("/")).read_bytes()
    assert v.store.publish_acceptance_bundle(chain.step.step_run_id) == published  # verified, not rewritten


@needs_windows
@pytest.mark.parametrize("how", ["bundle altered", "bundle deleted", "review claim copy altered"])
def test_a_tampered_published_bundle_completes_nothing(v: V, how) -> None:
    """Required case 14. X cannot write published/ (FD-14, re-proven by S0);
    whoever else alters it, A never completes over material it did not publish."""
    chain, _, pbound, _ = held(v)
    challenge = v.store.request_step_acceptance(chain.step.step_run_id)
    att = sign(v, challenge)
    bundle = v.store.held_acceptance_bundle(chain.step.step_run_id)
    name = bundle.name if how.startswith("bundle") else next(
        blob["published_name"] for blob in bundle.content["blobs"]
        if blob["sha256"] == bundle.content["execution_claims"]["review_command"]["claim_sha256"])
    path = Path(v.published, name)
    if how.endswith("deleted"):
        path.unlink()
    else:
        path.write_bytes(path.read_bytes().replace(b"approve", b"APPROVE"))
    before = snapshot(v.store)
    with pytest.raises(AuthorityRefusedError, match="bundle"):
        complete(v, chain, pbound, att)
    assert snapshot(v.store) == before
    if how.endswith("altered"):
        with pytest.raises(AuthorityRefusedError, match="never replaced"):
            v.store.request_step_acceptance(chain.step.step_run_id)
        assert snapshot(v.store) == before
    else:
        v.store.publish_acceptance_bundle(chain.step.step_run_id)  # republished from the store, never adopted
        assert complete(v, chain, pbound, att).current_state == StepState.COMPLETE.value


@needs_windows
def test_a_file_planted_under_the_bundle_name_gets_no_challenge(v: V) -> None:
    chain, _, _, record = held(v)
    Path(v.published, bundle_name(record.subject_sha256)).write_bytes(b'{"looks": "fine"}')
    before = snapshot(v.store)
    with pytest.raises(AuthorityRefusedError, match="never replaced"):
        v.store.request_step_acceptance(chain.step.step_run_id)
    assert snapshot(v.store) == before


# =============================================================================
# 5. signed completion
# =============================================================================


@needs_windows
def test_a_signed_acceptance_completes_the_held_step_exactly_once(v: V, monkeypatch) -> None:
    chain, pticket, pbound, _ = held(v)
    guard = NoSecondRun(v, monkeypatch)
    challenge = v.store.request_step_acceptance(chain.step.step_run_id)
    att = sign(v, challenge)
    step = step_of(v, chain)
    request = step_request(step, StepEvent.DECIDE_ACCEPTANCE, planner_decision=pbound.output,
                           human_acceptance=acceptance_for(chain, att))
    applied = complete(v, chain, pbound, att, request=request)
    assert (applied.current_state, applied.duplicate) == (StepState.COMPLETE.value, False)
    assert applied.record.rule == "acceptance_authorized"
    [row] = tickets(v, "planner")
    assert row["consumed_request_id"] == request.request_id and row["held_envelope"] is not None
    consumed = v.store._conn.execute(
        "SELECT consumed_by, attestation_sha256 FROM approval_challenges_v2 WHERE challenge_id = ?",
        (challenge.challenge_id,)).fetchone()
    assert tuple(consumed) == (f"step_acceptance:{request.request_id}", att.sha256)
    # A replay is a receipt only with exactly what it consumed.
    assert complete(v, chain, pbound, att, request=request).duplicate
    with pytest.raises(AuthorityRefusedError):
        complete(v, chain, bind_role_output(pticket, pbound.output.model_copy(update={"rationale": "x"})), att,
                 request=request)
    with pytest.raises(AuthorityRefusedError):
        v.store.apply_step_transition(step.step_run_id, request, role_output=pbound)
    project = v.store.get_project_run(chain.project.project_run_id)
    assert project.state is ProjectState.ACTIVE  # project completion stays refused (DL-1)
    guard.check()
    for _ in range(2):
        v.close()
        store = v.open()
        report = store.recover(chain.project.project_run_id)
        assert report.integrity_ok, report.integrity_issues
        assert store.get_step_run(chain.step.step_run_id).state is StepState.COMPLETE


@needs_windows
def test_an_attestation_for_another_subject_kind_or_root_completes_nothing(v: V) -> None:
    """Required case 11."""
    chain, _, pbound, _ = held(v)
    challenge = v.store.request_step_acceptance(chain.step.step_run_id)
    contract_challenge = v.store.request_project_contract_approval(make_content(goal="Another goal."))
    before = snapshot(v.store)
    other_subject = sign(v, challenge.model_copy(update={"subject_sha256": "1" * 64}))
    for att in (other_subject, sign(v, contract_challenge), sign(v, challenge, root="f" * 32)):
        with pytest.raises((AuthorityRefusedError, HumanAttestationRefusedError)):
            complete(v, chain, pbound, att)
    assert snapshot(v.store) == before
    assert complete(v, chain, pbound, sign(v, challenge)).current_state == StepState.COMPLETE.value


@needs_windows
def test_a_valid_signature_never_completes_with_another_or_stale_envelope(v: V) -> None:
    """Required case 12."""
    chain, pticket, pbound, record = held(v)
    challenge = v.store.request_step_acceptance(chain.step.step_run_id)
    att = sign(v, challenge)
    forged = pbound.output.model_copy(update={"rationale": "Accept."})
    other = bind_role_output(pticket, forged)
    subject = v.store.held_acceptance_bundle(chain.step.step_run_id).subject
    stale = subject.model_copy(update={"planner_envelope_sha256": hashlib.sha256(envelope_bytes(other)).hexdigest()})
    over_other = sign(v, challenge.model_copy(update={"subject_sha256": stale.sha256}))
    before = snapshot(v.store)
    with pytest.raises(AuthorityRefusedError, match="not the held one"):
        complete(v, chain, other, att, decision=forged)
    with pytest.raises(AuthorityRefusedError, match="not the held decision"):
        complete(v, chain, pbound, att, decision=forged)
    with pytest.raises((AuthorityRefusedError, HumanAttestationRefusedError)):
        complete(v, chain, other, over_other, decision=forged)
    with pytest.raises((AuthorityRefusedError, HumanAttestationRefusedError)):
        complete(v, chain, pbound, over_other)
    assert snapshot(v.store) == before


@needs_windows
def test_no_api_completes_a_held_step_without_the_signed_acceptance(v: V) -> None:
    """Required case 17: every supported route around the signed path."""
    from ai_dev_orchestrator.control_plane import ApprovalSubjectKind, HumanAttestation

    chain, _, pbound, _ = held(v)
    challenge = v.store.request_step_acceptance(chain.step.step_run_id)
    att = sign(v, challenge)
    step = step_of(v, chain)
    acceptance = acceptance_for(chain, att)
    signed = step_request(step, StepEvent.DECIDE_ACCEPTANCE, planner_decision=pbound.output,
                          human_acceptance=acceptance)
    v1 = HumanAttestation(
        schema_version="human-attestation.v1", challenge_id=challenge.challenge_id,
        subject_kind=ApprovalSubjectKind.STEP_ACCEPTANCE, subject_sha256=challenge.subject_sha256,
        approver_id=att.approver_id, attested_at=att.attested_at, approval_text=REQUIRED_STEP_ACCEPTANCE_APPROVAL_TEXT,
        proof="typed")
    store, base = v.store, ControlPlaneStore
    before = snapshot(store)
    for call in (
        lambda: store.apply_step_transition(step.step_run_id, signed, role_output=pbound),
        lambda: store.apply_step_transition(step.step_run_id, step_request(
            step, StepEvent.DECIDE_ACCEPTANCE, planner_decision=pbound.output), role_output=pbound),
        lambda: store.apply_step_transition(step.step_run_id, signed, role_output=None, human_attestation=att),
        lambda: store.apply_step_transition(step.step_run_id, signed, role_output=pbound, human_attestation=v1),
        lambda: base.apply_step_transition(store, step.step_run_id, signed, role_output=pbound, human_attestation=v1),
        lambda: base.apply_step_transition(store, step.step_run_id, signed, role_output=pbound, human_attestation=att),
        lambda: base.apply_step_transition(store, step.step_run_id, step_request(
            step, StepEvent.DECIDE_ACCEPTANCE, planner_decision=pbound.output), role_output=pbound),
        lambda: base.request_step_acceptance(store, step.step_run_id),
        lambda: store.apply_step_transition(step.step_run_id, step_request(
            step, StepEvent.MARK_READY), human_attestation=att),
    ):
        with pytest.raises((AuthorityRefusedError, TransitionRefused)):
            call()
        assert snapshot(store) == before
    assert step_of(v, chain).state is StepState.ACCEPTANCE
    assert complete(v, chain, pbound, att, request=signed).current_state == StepState.COMPLETE.value


# =============================================================================
# 6. attestation failures
# =============================================================================


@needs_windows
def test_an_expired_challenge_completes_nothing_and_a_fresh_one_does(v: V) -> None:
    """Required case 13 (expired)."""
    chain, _, pbound, _ = held(v)
    challenge = v.store.request_step_acceptance(chain.step.step_run_id)
    att = sign(v, challenge)
    v.clock.now = challenge.expires_at + timedelta(seconds=1)
    before = snapshot(v.store)
    with pytest.raises(HumanAttestationRefusedError) as refused:
        complete(v, chain, pbound, att)
    assert refused.value.category is R.CHALLENGE_EXPIRED
    assert snapshot(v.store) == before
    fresh = v.store.request_step_acceptance(chain.step.step_run_id)
    assert fresh.subject_sha256 == challenge.subject_sha256
    assert complete(v, chain, pbound, sign(v, fresh)).current_state == StepState.COMPLETE.value
    assert v.store.recover(chain.project.project_run_id).integrity_ok


@needs_windows
def test_mismatched_or_replayed_attestations_complete_nothing(v: V) -> None:
    """Required case 13 (mismatched, replayed)."""
    chain, _, pbound, _ = held(v)
    first = v.store.request_step_acceptance(chain.step.step_run_id)
    second = v.store.request_step_acceptance(chain.step.step_run_id)
    att = sign(v, first)
    before = snapshot(v.store)
    for bad, acceptance in (
        (sign(v, first, private=BOB), None),  # alice's name, bob's key
        (att, acceptance_for(chain, att).model_copy(update={"approved_at": att.attested_at + timedelta(seconds=1)})),
        (att, acceptance_for(chain, att).model_copy(update={"approved_by": "bob"})),
        # R6-3: the same instant in another offset is refused, so every proof can rebuild the request.
        (att, acceptance_for(chain, att).model_copy(update={
            "approved_at": att.attested_at.astimezone(timezone(timedelta(hours=-7)))})),
    ):
        with pytest.raises((AuthorityRefusedError, HumanAttestationRefusedError)):
            complete(v, chain, pbound, bad, acceptance=acceptance)
    assert snapshot(v.store) == before
    complete(v, chain, pbound, att)
    for replayed in (att, sign(v, second)):  # consumed, or for a step no longer held
        with pytest.raises((AuthorityRefusedError, HumanAttestationRefusedError)):
            complete(v, chain, pbound, replayed)
    assert v.store.recover(chain.project.project_run_id).integrity_ok


@needs_windows
def test_revocation_after_the_hold_and_before_completion_completes_nothing(v: V) -> None:
    """Required case 16."""
    chain, _, pbound, _ = held(v)
    att = sign(v, v.store.request_step_acceptance(chain.step.step_run_id))
    _set_alice(v, revoked=True)
    with pytest.raises((AuthorityRefusedError, StateUntrustedError, HumanAttestationRefusedError)):
        complete(v, chain, pbound, att)
    with pytest.raises((AuthorityRefusedError, StateUntrustedError)):
        v.store.request_step_acceptance(chain.step.step_run_id)
    report = v.store.recover(chain.project.project_run_id)
    assert not report.integrity_ok and report.project_state is ProjectState.HUMAN_REQUIRED
    assert v.store.inspect_step_run(chain.step.step_run_id).columns["state"] == StepState.HUMAN_REQUIRED.value


def _set_bob(v: V, **changes) -> None:
    entries = v.world.registry["approvers"]
    index = next(i for i, entry in enumerate(entries) if entry["approver_id"] == "bob")
    entries[index] = {**entries[index], **changes}


@needs_windows
def test_revoking_the_accepting_key_untrusts_the_completed_step(v: V) -> None:
    """FD-3: revocation is total, including re-proofs of a consumed acceptance."""
    chain, _, pbound, _ = held(v)
    challenge = v.store.request_step_acceptance(chain.step.step_run_id)
    att = sign(v, challenge, private=BOB, approver="bob")
    complete(v, chain, pbound, att)
    assert v.store.recover(chain.project.project_run_id).integrity_ok
    _set_bob(v, revoked=True)
    report = v.store.recover(chain.project.project_run_id)
    assert not report.integrity_ok and chain.step.step_run_id in report.escalated_step_run_ids
    assert any("step_acceptance" in issue for issue in report.integrity_issues), report.integrity_issues


# =============================================================================
# 7. decline
# =============================================================================


@needs_windows
def test_a_declined_hold_goes_stale_and_can_never_complete(v: V) -> None:
    """Required case 18."""
    chain, pticket, pbound, _ = held(v)
    challenge = v.store.request_step_acceptance(chain.step.step_run_id)
    att = sign(v, challenge)
    step = step_of(v, chain)
    before = snapshot(v.store)
    with pytest.raises(AuthorityRefusedError):  # an escalation carrying the held envelope
        v.store.apply_step_transition(step.step_run_id, step_request(step, StepEvent.ESCALATE, reason="No."),
                                      role_output=pbound)
    with pytest.raises(AuthorityRefusedError):  # or an attestation
        v.store.apply_step_transition(step.step_run_id, step_request(step, StepEvent.ESCALATE, reason="No."),
                                      human_attestation=att)
    assert snapshot(v.store) == before
    v.store.apply_step_transition(step.step_run_id, step_request(
        step, StepEvent.ESCALATE, reason="The human declines the held decision."))
    assert step_of(v, chain).state is StepState.HUMAN_REQUIRED
    before = snapshot(v.store)
    for call in (lambda: complete(v, chain, pbound, att),
                 lambda: v.store.request_step_acceptance(chain.step.step_run_id),
                 lambda: v.store.held_acceptance_bundle(chain.step.step_run_id)):
        with pytest.raises((AuthorityRefusedError, HumanAttestationRefusedError)):
            call()
    assert snapshot(v.store) == before
    now = step_of(v, chain)
    assert v.store.held_acceptance_decision(now.step_run_id, expected_state_version=now.state_version) is None
    [row] = tickets(v, "planner")
    assert row["held_envelope"] is not None and row["consumed_request_id"] is None
    planner = Planner(v)
    assert inner(v, chain, S6Ports(v, planner)).stop is InnerLoopStop.STEP_HUMAN_REQUIRED and planner.calls == 0
    v.close()
    report = v.open().recover(chain.project.project_run_id)
    assert report.integrity_ok, report.integrity_issues


# =============================================================================
# 8. tampering and recovery
# =============================================================================

NINES = "'" + "9" * 64 + "'"
HOLD_TAMPERS = {
    "held envelope": "UPDATE dispatch_tickets SET held_envelope = replace(held_envelope, 'deterministic', "
                     "'determined') WHERE held_envelope IS NOT NULL",
    "held digest": f"UPDATE dispatch_tickets SET held_envelope_sha256 = {NINES} WHERE held_envelope IS NOT NULL",
    "held time cleared": "UPDATE dispatch_tickets SET held_at = NULL WHERE held_envelope IS NOT NULL",
    "hold copied to the reviewer ticket": "UPDATE dispatch_tickets SET (held_envelope, held_envelope_sha256, held_at) "
                                          "= (SELECT held_envelope, held_envelope_sha256, held_at FROM dispatch_tickets "
                                          "WHERE role = 'planner') WHERE role = 'reviewer'",
    "held ticket answered by nothing": f"UPDATE dispatch_tickets SET consumed_request_id = '{'9' * 32}' "
                                       "WHERE role = 'planner'",
    "forged step acceptance challenge": "INSERT INTO approval_challenges_v2 (challenge_id, subject_kind, "
                                        f"subject_sha256, issued_at, expires_at) VALUES ('cc', 'step_acceptance', "
                                        f"{NINES}, 'a', 'b')",
    "review evidence deleted": "DELETE FROM review_evidence",
    "review verdict": "UPDATE review_evidence SET verdict = 'changes_requested'",
    "m2 target": f"UPDATE authority_observations SET target_sha256 = {NINES} WHERE kind = 'm2'",
    "m1 deleted": "DELETE FROM authority_observations WHERE kind = 'm1'",
}


@needs_windows
@pytest.mark.parametrize("name", list(HOLD_TAMPERS) + ["m0 manifest blob"])
def test_a_tampered_hold_or_its_evidence_makes_the_run_untrusted(v: V, name) -> None:
    """Required cases 4 and 15: a correct verdict with changed observations,
    deleted or altered review evidence, or any altered hold record."""
    chain, _, pbound, _ = held(v)
    att = sign(v, v.store.request_step_acceptance(chain.step.step_run_id))
    if name == "m0 manifest blob":
        sha = v.store._conn.execute("SELECT manifest_sha256 FROM authority_observations WHERE kind = 'm0'").fetchone()[0]
        v.close()
        path = Path(v.root.path, "evidence", "observations", sha)
        os.chmod(path, 0o666)
        path.write_bytes(path.read_bytes() + b" ")
    else:
        raw(v, HOLD_TAMPERS[name])
    store = v.open()
    report = store.recover(chain.project.project_run_id)
    assert not report.integrity_ok, name
    assert report.project_state is ProjectState.HUMAN_REQUIRED
    with pytest.raises((StateUntrustedError, AuthorityRefusedError, HumanAttestationRefusedError)):
        complete(v, chain, pbound, att)


COMPLETE_TAMPERS = {
    "acceptance attestation": "UPDATE approval_challenges_v2 SET attestation = replace(attestation, 'alice', "
                              "'alicf') WHERE subject_kind = 'step_acceptance'",
    "acceptance consumer": f"UPDATE approval_challenges_v2 SET consumed_by = 'step_acceptance:{'9' * 32}' "
                           "WHERE subject_kind = 'step_acceptance'",
    "acceptance subject": f"UPDATE approval_challenges_v2 SET subject_sha256 = {NINES} "
                          "WHERE subject_kind = 'step_acceptance'",
    "hold erased after completion": "UPDATE dispatch_tickets SET held_envelope = NULL, held_envelope_sha256 = NULL, "
                                    "held_at = NULL WHERE role = 'planner'",
    "decision request digest": f"UPDATE transitions SET request_sha256 = {NINES} WHERE event = 'decide_acceptance'",
}


@needs_windows
@pytest.mark.parametrize("name", list(COMPLETE_TAMPERS))
def test_a_tampered_completion_record_untrusts_the_completed_step(v: V, name) -> None:
    chain, *_ = accepted(v)
    raw(v, COMPLETE_TAMPERS[name])
    store = v.open()
    report = store.recover(chain.project.project_run_id)
    assert not report.integrity_ok, name
    assert store.inspect_step_run(chain.step.step_run_id).columns["state"] == StepState.HUMAN_REQUIRED.value


# =============================================================================
# 9. v2/v3 unchanged
# =============================================================================


def test_v2_and_v3_stores_hold_nothing_and_keep_r9(make) -> None:  # noqa: F811 - DL-2's fixture
    """Required case 20: the hold branch exists only where the store says so;
    DL-2's offline R-9 escalation is unchanged."""
    s = make(human=True, decide=[ACCEPT])
    assert s.store.holds_acceptance_decisions is False
    assert not any(hasattr(ControlPlaneStore, name) for name in (
        "hold_acceptance_decision", "held_acceptance_decision", "held_acceptance_bundle",
        "publish_acceptance_bundle"))
    outcome = s.run()
    assert outcome.stop is InnerLoopStop.STEP_HUMAN_REQUIRED
    assert (outcome.cause, outcome.refusal_code) == ("human_acceptance_unavailable",
                                                     RefusalCode.HUMAN_ACCEPTANCE_MISSING)
    assert s.events()[-2:] == ["review_observed", "escalate"]


# =============================================================================
# 10. DL-3 → DL-2 → planner → hold → restart → signed completion
# =============================================================================


@needs_windows
def test_the_orchestration_path_holds_restarts_and_completes_only_with_a_signature(v: V) -> None:
    """Required case 21."""
    chain = _planned(v)
    _x_steps(v)
    planner = Planner(v)
    outcome = ProjectOuterLoop(v.store, S6Ports(v, planner).role_ports()).run(
        project_run=v.store.get_project_run(chain.project.project_run_id), project_contract=chain.pc,
        execution_plan=chain.plan)
    assert outcome.stop is OuterLoopStop.STEP_NOT_SETTLED and outcome.escalation is None
    assert outcome.invocations[-1].inner_stop is InnerLoopStop.AWAITING_HUMAN_ACCEPTANCE
    assert planner.calls == 1 and v.reviewer.requests == 1 and v.waiter.queue == []
    assert step_of(v, chain).state is StepState.ACCEPTANCE
    v.close()
    store = v.open()
    assert store.recover(chain.project.project_run_id).integrity_ok
    again = ProjectOuterLoop(store, S6Ports(v, planner).role_ports()).run(
        project_run=store.get_project_run(chain.project.project_run_id), project_contract=chain.pc,
        execution_plan=chain.plan)
    assert again.stop is OuterLoopStop.STEP_NOT_SETTLED and planner.calls == 1
    step = store.get_step_run(chain.step.step_run_id)
    held_record = store.held_acceptance_decision(step.step_run_id, expected_state_version=step.state_version)
    store.publish_acceptance_bundle(step.step_run_id)
    att = sign(v, store.request_step_acceptance(step.step_run_id))
    complete(v, chain, held_record.envelope, att)
    final = ProjectOuterLoop(store, S6Ports(v, planner).role_ports()).run(
        project_run=store.get_project_run(chain.project.project_run_id), project_contract=chain.pc,
        execution_plan=chain.plan)
    assert final.stop is OuterLoopStop.PLAN_WORK_COMPLETE and final.project_run.state is ProjectState.ACTIVE
    assert planner.calls == 1 and v.reviewer.requests == 1
    v.close()
    report = v.open().recover(chain.project.project_run_id)
    assert report.integrity_ok, report.integrity_issues


# =============================================================================
# 11. static boundaries
# =============================================================================

_PACKAGE = Path(integration.__file__).resolve().parent
_S6_FUNCTIONS = (
    "_alpha_facts", "_proven_alpha_facts", "_alpha_planner_decision", "_planner_decision_issue", "_proven_hold",
    "_current_hold", "held_acceptance_decision", "hold_acceptance_decision", "_bundle", "held_acceptance_bundle",
    "publish_acceptance_bundle", "request_step_acceptance", "_apply_signed_acceptance",
    "_decision_transition_issue", "_s6_issues", "_authorize_decision",
)


def test_s6_code_has_no_model_git_subprocess_network_or_harness_surface() -> None:
    """Required case 22."""
    forbidden = {"subprocess", "socket", "httpx", "requests", "aiohttp", "urllib", "http", "asyncio",
                 "multiprocessing", "threading", "os", "ctypes", "shutil", "tempfile"}
    harness = ("ai_dev_orchestrator.llm", "ai_dev_orchestrator.github", "ai_dev_orchestrator.review",
               "ai_dev_orchestrator.verification", "ai_dev_orchestrator.file_editing",
               "ai_dev_orchestrator.supervised_implementer", "ai_dev_orchestrator.workspace",
               "ai_dev_orchestrator.diff_proposal", "ai_dev_orchestrator.cli", "ai_dev_orchestrator.config_loader")
    for name in ("alpha_planner.py", "acceptance_bundle.py"):
        imported = _imports(_PACKAGE / name)
        assert not {m.split(".")[0] for m in imported} & forbidden, (name, imported)
        assert not [m for m in imported if m.startswith(harness)], (name, imported)
    assert not [m for m in _imports(_PACKAGE / "integration_store.py") if m.startswith(harness)]
    tree = ast.parse((_PACKAGE / "integration_store.py").read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in _S6_FUNCTIONS:
            found.add(node.name)
            called = {n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
                      for n in ast.walk(node) if isinstance(n, ast.Call)}
            # No handoff, wait, claim read, clone observation, or role execution.
            assert not called & {"publish_handoff", "await_completion", "read_claim", "observe_workspace",
                                 "observe_git_control", "_perform_write_handoff", "_perform_review_handoff",
                                 "_perform_review_observation", "sleep", "_publish_blob"}, (node.name, called)
    assert found == set(_S6_FUNCTIONS)


def test_the_planner_port_and_session_expose_no_recorder() -> None:
    rule = mint_alpha_planner_rule(object())
    assert {n for n in dir(rule) if not n.startswith("_")} == {"decide_step"}
    with pytest.raises(AttributeError):
        rule._store = None
    with pytest.raises(TypeError):
        AlphaPlannerRule(object())
    with pytest.raises(TypeError):
        class Sub(AlphaPlannerRule):  # noqa: F841
            pass


def test_the_s6_records_are_pure_and_domain_separated() -> None:
    from ai_dev_orchestrator.control_plane import integration_records as records
    from ai_dev_orchestrator.control_plane.authority import step_acceptance_subject_sha256

    assert records.STEP_ACCEPTANCE_SUBJECT_V2_SCHEMA_VERSION == "step-acceptance-subject.v2"
    assert records.CLAIM_PROVENANCE_UNAUTHENTICATED == "execution_identity_unauthenticated"
    common = dict(project_run_id="a" * 32, step_run_id="b" * 32, step_contract_sha256="c" * 64, attempt=1,
                  state_version=5)
    subject = StepAcceptanceSubjectV2(
        schema_version="step-acceptance-subject.v2", kind="step_acceptance", **common,
        verification_evidence_sha256="d" * 64, write_scope_sha256="e" * 64, write_evidence_sha256="f" * 64,
        review_evidence_sha256="1" * 64, planner_envelope_sha256="2" * 64, identity_boundary_sha256="3" * 64,
        m0_observation_sha256="4" * 64, m1_observation_sha256="5" * 64, m2_observation_sha256="6" * 64,
        claim_provenance="execution_identity_unauthenticated")
    assert subject.sha256 != step_acceptance_subject_sha256(**common, verification_evidence_sha256="d" * 64)
    with pytest.raises(ValueError):
        StepAcceptanceSubjectV2.model_validate({**subject.model_dump(), "claim_provenance": "authority_observation"})
    assert records.evidence_record_sha256("write", {"a": 1}) != records.evidence_record_sha256("review", {"a": 1})
