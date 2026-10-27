"""DL-4B S5 — review evidence and REVIEW_OBSERVED from the S4 claim, offline.

The harness is S4's: a synthetic Git clone under pytest ``tmp_path``, S0/S1
synthetic Windows worlds, the production ``WindowsAuthorityFiles`` with
synthetic owners, and the human's two X-side steps simulated by running the
frozen, unchanged ``l2-apply-approved-file-edit`` and
``l2-review-approved-file-edit`` in-process (reviewer behind an
``httpx.MockTransport``, verification a synthetic script). The frozen review
command runs ONCE, during VERIFYING; S5 must answer the reviewer dispatch from
its stored stdout and run, wait for, observe and send nothing.

Sections: the strict review reader; the happy path per verdict; tickets and
lifecycle ordering; caller-supplied and forged authority; revocation and S4
evidence loss; duplicates; crashes; the tamper matrix; DL-3 → DL-2; static
boundaries.
"""

from __future__ import annotations

import copy
import json
import os
import sqlite3
from pathlib import Path

import pytest
from test_dl4b_s2_integration_store import SimulatedCrash, _set_alice, crash_at, snapshot, step_request
from test_dl4b_s3_write_handoff import _planned
from test_dl4b_s4_verification_claim import (
    APPROVE_REVIEW,
    CHANGES_REVIEW,
    FAILING,
    PASSING,
    Ports,
    V,
    _frozen_stdout,
    _imports,
    _set,
    _ticket_of,
    _x_steps,
    claim_bytes,
    evidence,
    observed,
    review_env,  # noqa: F401 - fixture
    review_step,
    v,  # noqa: F401 - fixture
    verified,
    verifier_rows,
    verify,
    vticket_for,
    written,
)

import ai_dev_orchestrator.integration as integration
from ai_dev_orchestrator import cli
from ai_dev_orchestrator.control_plane import (
    AuthorityRefusedError,
    ProjectOuterLoop,
    ReviewProposal,
    StateUntrustedError,
    StepEvent,
    StepState,
    TransitionRefused,
    bind_role_output,
)
from ai_dev_orchestrator.control_plane.authority import DispatchTicket
from ai_dev_orchestrator.control_plane.store import StoreError
from ai_dev_orchestrator.integration import claim_readers
from ai_dev_orchestrator.integration.claim_readers import ClaimReadError
from ai_dev_orchestrator.integration.execution_claim import ExecutionClaimAdapter, mint_execution_claim_adapter
from ai_dev_orchestrator.integration.integration_store import (
    S5_TABLES,
    UNWRITTEN_TABLES,
    IntegrationStore,
    ReviewEvidenceRefusedError,
)
from ai_dev_orchestrator.review import models as review_models

needs_windows = pytest.mark.skipif(os.name != "nt", reason="real Windows file handles and a synthetic Windows boundary")

HUMAN_REVIEW = json.dumps({
    "verdict": "needs_human_review", "summary": "The intent of the rounding change is unclear.",
    "findings": [{"severity": "minor", "category": "scope", "line": None,
                  "message": "Rounding behavior changed.", "suggested_action": "Confirm the intent."}],
    "residual_risks": ["Only one test covers this."], "human_notes": ["Ask the issue author."],
})
VERDICTS = {"approve": APPROVE_REVIEW, "changes_requested": CHANGES_REVIEW, "needs_human_review": HUMAN_REVIEW}


# =============================================================================
# harness
# =============================================================================


def rticket_for(v: V, chain):
    step = v.store.get_step_run(chain.step.step_run_id)
    return v.store.issue_dispatch_ticket(step.step_run_id, role="reviewer", expected_state_version=step.state_version)


def review(v: V, chain, ticket):
    contract = v.store.get_step_contract(chain.contract.sha256)
    return v.session.reviewer.review(step_contract=contract, attempt=ticket.attempt, dispatch=ticket)


def review_observed(v: V, chain, bound, *, output: ReviewProposal | None = None, ticket=None):
    step = v.store.get_step_run(chain.step.step_run_id)
    payload = output if output is not None else bound.output
    role_output = bound if output is None and ticket is None else bind_role_output(
        ticket if ticket is not None else _ticket_of(v, bound.ticket_id), payload)
    return v.store.apply_step_transition(
        step.step_run_id, step_request(step, StepEvent.REVIEW_OBSERVED, review=payload), role_output=role_output)


def at_reviewing(v: V, content: str = APPROVE_REVIEW, **options):
    """Through S4 with the reviewer replying ``content``: step at REVIEWING."""
    v.reviewer.content = content
    chain, vticket, vbound = verified(v, **options)
    assert v.store.get_step_run(chain.step.step_run_id).state is StepState.REVIEWING
    return chain, vticket, vbound


def reviewed(v: V, content: str = APPROVE_REVIEW):
    """Through S5: the reviewer dispatch answered and REVIEW_OBSERVED recorded."""
    chain, vticket, vbound = at_reviewing(v, content)
    rticket = rticket_for(v, chain)
    rbound = review(v, chain, rticket)
    review_observed(v, chain, rbound)
    return chain, vticket, rticket, rbound


def review_rows(v: V) -> list[sqlite3.Row]:
    return v.store._conn.execute("SELECT * FROM review_evidence").fetchall()


def claim_blobs(v: V) -> list[str]:
    return sorted(os.listdir(Path(v.root.path, "evidence", "claims")))


class NoSecondRun:
    """Every way the review command or a model could be reached again, armed to fail."""

    def __init__(self, v: V, monkeypatch) -> None:
        self.v = v
        self.requests = v.reviewer.requests
        self.sleeps = v.waiter.sleeps
        self.dirs = v.handoff_dirs()
        self.blobs = claim_blobs(v)

        def refuse(*args, **kwargs):
            raise AssertionError("S5 ran the review command or a model")

        monkeypatch.setattr(cli, "_run_l2_review_approved_file_edit", refuse)
        monkeypatch.setattr(cli, "_build_reviewer_network_transport", refuse)
        monkeypatch.setattr(cli, "_read_reviewer_env", refuse)

    def check(self) -> None:
        v = self.v
        assert v.reviewer.requests == self.requests
        assert v.waiter.sleeps == self.sleeps and v.waiter.queue == []
        assert v.handoff_dirs() == self.dirs
        assert claim_blobs(v) == self.blobs


# =============================================================================
# 1. the strict review reader
# =============================================================================


def _packet(tmp_path: Path, review_env, content: str = APPROVE_REVIEW) -> bytes:
    return _frozen_stdout(tmp_path, review_env, PASSING, content=content)


def test_the_review_mirror_restates_the_shipped_review_model() -> None:
    assert claim_readers.REVIEW_SEVERITIES == review_models.ReviewSeverity.__args__
    assert claim_readers.REVIEW_CATEGORIES == review_models.ReviewCategory.__args__
    assert claim_readers.REVIEW_VERDICTS == review_models.ReviewVerdict.__args__
    assert claim_readers.REVIEW_BLOCKING_SEVERITIES == review_models.BLOCKING_SEVERITIES
    assert set(claim_readers.REVIEW_FINDING_FIELDS) == set(review_models.ReviewFinding.model_fields)
    assert {n for n, f in review_models.ReviewFinding.model_fields.items() if f.is_required()} == set(
        claim_readers.REVIEW_FINDING_REQUIRED)
    assert set(claim_readers.MODEL_REVIEW_FIELDS) == set(review_models.ModelReviewResult.model_fields)
    for name in ("MAX_REVIEW_FINDINGS", "MAX_REVIEW_SUMMARY_CHARS", "MAX_REVIEW_MESSAGE_CHARS",
                 "MAX_REVIEW_SUGGESTED_ACTION_CHARS", "MAX_REVIEW_NOTE_CHARS", "MAX_REVIEW_NOTES"):
        assert getattr(claim_readers, name) == getattr(review_models, name), name


@pytest.mark.parametrize("verdict", list(VERDICTS))
def test_the_reader_re_derives_every_frozen_verdict(tmp_path: Path, review_env, verdict) -> None:
    data = _packet(tmp_path, review_env, VERDICTS[verdict])
    facts = claim_readers.read_review_verdict(data)
    assert facts.verdict == verdict == claim_readers.read_review_claim(data).verdict
    assert facts.claim.shape == "review-packet" and facts.claim.outcome == "verified"
    # The mirror agrees with the shipped strict parser on the genuine review.
    shipped = review_models.parse_model_review_response(json.dumps(json.loads(data)["review"]))
    assert shipped.verdict == verdict and facts.finding_count == len(shipped.findings)


def test_a_bare_verification_report_carries_no_review(tmp_path: Path, review_env) -> None:
    data = _frozen_stdout(tmp_path, review_env, FAILING)
    assert claim_readers.read_review_claim(data).shape == "verification-failed"
    with pytest.raises(ClaimReadError) as caught:
        claim_readers.read_review_verdict(data)
    assert caught.value.category == "unexpected_shape"


_BLOCKER = {"severity": "blocker", "category": "security", "line": 3, "message": "m", "suggested_action": "a"}
_MINOR = {"severity": "minor", "category": "other", "line": None, "message": "m", "suggested_action": "a"}
REVIEW_MUTATIONS = {
    "approve with a blocker": {"findings": [_BLOCKER]},
    "approve with a major": {"findings": [{**_BLOCKER, "severity": "major"}]},
    "changes requested with nothing blocking": {"verdict": "changes_requested", "findings": [_MINOR]},
    "changes requested with no finding": {"verdict": "changes_requested"},
    "blank summary": {"summary": "   "},
    "summary too long": {"summary": "x" * 4_001},
    "summary not a string": {"summary": 1},
    "unknown severity": {"findings": [{**_MINOR, "severity": "critical"}]},
    "unknown category": {"findings": [{**_MINOR, "category": "style"}]},
    "line zero": {"findings": [{**_MINOR, "line": 0}]},
    "line negative": {"findings": [{**_MINOR, "line": -1}]},
    "line a string": {"findings": [{**_MINOR, "line": "2"}]},
    "line a boolean": {"findings": [{**_MINOR, "line": True}]},
    "line a float": {"findings": [{**_MINOR, "line": 2.0}]},
    "blank message": {"findings": [{**_MINOR, "message": ""}]},
    "message too long": {"findings": [{**_MINOR, "message": "x" * 4_001}]},
    "action too long": {"findings": [{**_MINOR, "suggested_action": "x" * 2_001}]},
    "finding extra field": {"findings": [{**_MINOR, "patch": "x"}]},
    "finding missing field": {"findings": [{k: w for k, w in _MINOR.items() if k != "message"}]},
    "finding not an object": {"findings": ["x"]},
    "findings not a list": {"findings": {}},
    "too many findings": {"verdict": "needs_human_review", "findings": [_MINOR] * 21},
    "too many notes": {"human_notes": ["n"] * 21},
    "note blank": {"residual_risks": [" "]},
    "note too long": {"human_notes": ["x" * 2_001]},
    "note not a string": {"human_notes": [1]},
    "notes not a list": {"residual_risks": "x"},
    "unknown verdict": {"verdict": "reject"},
    "verdict case-folded": {"verdict": "Approve"},
}


def _with_review(data: bytes, changes: dict) -> bytes:
    document = json.loads(data)
    document["review"].update(copy.deepcopy(changes))
    return json.dumps(document).encode("utf-8")


@pytest.mark.parametrize("name", list(REVIEW_MUTATIONS))
def test_a_review_the_frozen_command_never_prints_is_refused_never_repaired(tmp_path: Path, review_env,
                                                                         name) -> None:
    data = _with_review(_packet(tmp_path, review_env), REVIEW_MUTATIONS[name])
    review = json.loads(data)["review"]
    with pytest.raises((review_models.ReviewValidationError, review_models.ReviewParseError)):
        review_models.parse_model_review_response(json.dumps(review))  # the shipped parser agrees
    with pytest.raises(ClaimReadError):
        claim_readers.read_review_verdict(data)


@pytest.mark.parametrize("changes", [
    {"findings": [{k: w for k, w in _MINOR.items() if k != "line"}]},  # line has a default
    {"verdict": "needs_human_review", "findings": [_BLOCKER] * 20},
    {"verdict": "changes_requested", "findings": [_MINOR, _BLOCKER], "human_notes": ["n"] * 20},
])
def test_every_review_the_shipped_model_accepts_is_accepted(tmp_path: Path, review_env, changes) -> None:
    data = _with_review(_packet(tmp_path, review_env), changes)
    shipped = review_models.parse_model_review_response(json.dumps(json.loads(data)["review"]))
    assert claim_readers.read_review_verdict(data).verdict == shipped.verdict


# =============================================================================
# 2. the happy path, per verdict
# =============================================================================


@needs_windows
@pytest.mark.parametrize("verdict", list(VERDICTS))
def test_the_reviewer_is_answered_from_the_s4_claim_and_reaches_acceptance(v: V, monkeypatch, verdict) -> None:
    chain, vticket, vbound = at_reviewing(v, VERDICTS[verdict])
    assert v.reviewer.requests == 1
    guard = NoSecondRun(v, monkeypatch)
    rticket = rticket_for(v, chain)
    rbound = review(v, chain, rticket)
    guard.check()
    claim_digest = verifier_rows(v, "execution_claims", vticket)[0]["claim_sha256"]
    assert claim_digest == evidence(v)[0]["claim_sha256"] == vbound.output.evidence_sha256
    assert rbound.role == "reviewer" and rbound.ticket_id == rticket.ticket_id
    assert rbound.output == ReviewProposal(step_contract_sha256=chain.contract.sha256, attempt=1, verdict=verdict,
                                           evidence_sha256=claim_digest)
    assert rbound.output.verdict == claim_readers.read_review_verdict(claim_bytes(v, vticket)).verdict
    [row] = review_rows(v)
    assert (row["ticket_id"], row["verifier_ticket_id"], row["claim_sha256"], row["verdict"], row["provenance"]) == (
        rticket.ticket_id, vticket.ticket_id, claim_digest, verdict, "execution_claim")
    review_observed(v, chain, rbound)
    guard.check()
    step = v.store.get_step_run(chain.step.step_run_id)
    # Every verdict ends at ACCEPTANCE (DL-1); the verdict is recorded, never a transition.
    assert step.state is StepState.ACCEPTANCE and step.review_verdict == verdict
    v.close()
    store = v.open()
    report = store.recover(chain.project.project_run_id)
    assert report.integrity_ok, report.integrity_issues
    assert store.get_step_run(chain.step.step_run_id).state is StepState.ACCEPTANCE


@needs_windows
def test_review_evidence_references_the_s4_blob_and_copies_nothing(v: V) -> None:
    chain, vticket, _ = at_reviewing(v)
    blobs = claim_blobs(v)
    rticket = rticket_for(v, chain)
    review(v, chain, rticket)
    assert claim_blobs(v) == blobs
    assert set(review_rows(v)[0].keys()) == {
        "ticket_id", "verifier_ticket_id", "claim_sha256", "verdict", "provenance", "recorded_at"}
    assert S5_TABLES == ("review_evidence",) and UNWRITTEN_TABLES == ()


# =============================================================================
# 3. tickets and lifecycle ordering
# =============================================================================


@needs_windows
def test_no_reviewer_dispatch_exists_before_a_verified_verification_transition(v: V) -> None:
    chain, _ = written(v)
    vticket = vticket_for(v, chain)
    review_step(v, vticket)
    vbound = verify(v, chain, vticket)  # S4 evidence recorded, VERIFICATION_OBSERVED not yet
    step = v.store.get_step_run(chain.step.step_run_id)
    with pytest.raises(TransitionRefused):
        v.store.issue_dispatch_ticket(step.step_run_id, role="reviewer", expected_state_version=step.state_version)
    forged = DispatchTicket.model_validate({**vticket.model_dump(mode="json"), "role": "reviewer",
                                            "step_state": StepState.REVIEWING.value})
    contract = v.store.get_step_contract(chain.contract.sha256)
    for ticket in (forged, vticket):
        with pytest.raises(AuthorityRefusedError):
            v.session.reviewer.review(step_contract=contract, attempt=1, dispatch=ticket)
    assert review_rows(v) == []
    observed(v, chain, vbound)
    assert v.store.get_step_run(chain.step.step_run_id).state is StepState.REVIEWING


@needs_windows
def test_a_failed_verification_never_reaches_a_reviewer(v: V) -> None:
    v.body(FAILING)
    chain, vticket, _ = verified(v)
    step = v.store.get_step_run(chain.step.step_run_id)
    assert step.state is StepState.ACCEPTANCE and step.verification_outcome == "verification-failed"
    with pytest.raises(TransitionRefused):
        v.store.issue_dispatch_ticket(step.step_run_id, role="reviewer", expected_state_version=step.state_version)
    forged = DispatchTicket.model_validate({**vticket.model_dump(mode="json"), "role": "reviewer",
                                            "step_state": StepState.REVIEWING.value,
                                            "state_version": step.state_version})
    contract = v.store.get_step_contract(chain.contract.sha256)
    with pytest.raises(AuthorityRefusedError):
        v.session.reviewer.review(step_contract=contract, attempt=1, dispatch=forged)
    assert review_rows(v) == []


@needs_windows
@pytest.mark.parametrize("change", [
    {"attempt": 2}, {"step_run_id": "c" * 32}, {"ticket_id": "f" * 32}, {"state_version": 99},
    {"project_run_id": "d" * 32}, {"role": "verifier", "step_state": StepState.VERIFYING.value},
    {"role": "implementer", "step_state": StepState.EXECUTING.value},
    {"role": "planner", "step_state": StepState.ACCEPTANCE.value}, {"step_contract_sha256": "a" * 64},
], ids=lambda change: ",".join(change))
def test_a_reviewer_ticket_for_another_step_attempt_or_role_is_refused(v: V, change) -> None:
    chain, _, _ = at_reviewing(v)
    rticket = rticket_for(v, chain)
    other = DispatchTicket.model_validate({**rticket.model_dump(mode="json"), **change})
    contract = v.store.get_step_contract(chain.contract.sha256)
    before = snapshot(v.store)
    # A ticket naming an unknown step run is refused as an unknown record (StoreError).
    with pytest.raises((AuthorityRefusedError, StoreError, ValueError)):
        v.session.reviewer.review(step_contract=contract, attempt=other.attempt, dispatch=other)
    with pytest.raises((AuthorityRefusedError, StoreError, ValueError)):
        v.store._perform_review_observation(v.store._require_authority().claim_key, other)
    assert snapshot(v.store) == before and review_rows(v) == []
    review_observed(v, chain, review(v, chain, rticket))  # the genuine ticket still answers


@needs_windows
def test_the_adapter_checks_contract_and_attempt_against_the_ticket(v: V) -> None:
    chain, _, _ = at_reviewing(v)
    rticket = rticket_for(v, chain)
    contract = v.store.get_step_contract(chain.contract.sha256)
    with pytest.raises(ValueError):
        v.session.reviewer.review(step_contract=contract, attempt=2, dispatch=rticket)
    with pytest.raises(ValueError):
        v.session.reviewer.review(step_contract=contract.model_dump(), attempt=1, dispatch=rticket)
    with pytest.raises(TypeError):
        v.session.reviewer.review(step_contract=contract, attempt=1, dispatch=rticket.model_dump())
    assert review_rows(v) == []


@needs_windows
def test_the_verifier_port_never_answers_a_reviewer_ticket(v: V) -> None:
    chain, _, _ = at_reviewing(v)
    rticket = rticket_for(v, chain)
    requests = v.reviewer.requests
    with pytest.raises(AuthorityRefusedError):
        verify(v, chain, rticket)
    assert verifier_rows(v, "execution_handoffs", rticket) == [] and v.reviewer.requests == requests


# =============================================================================
# 4. caller-supplied and forged authority
# =============================================================================


@needs_windows
def test_no_caller_supplied_proposal_verdict_or_digest_passes_reviewing(v: V) -> None:
    chain, vticket, vbound = at_reviewing(v, CHANGES_REVIEW)
    rticket = rticket_for(v, chain)
    digest = vbound.output.evidence_sha256
    right = ReviewProposal(step_contract_sha256=chain.contract.sha256, attempt=1, verdict="changes_requested",
                           evidence_sha256=digest)
    # Before the adapter recorded anything, even the exactly-right proposal is refused.
    with pytest.raises(AuthorityRefusedError, match="no review evidence"):
        review_observed(v, chain, None, output=right, ticket=rticket)
    rbound = review(v, chain, rticket)
    assert rbound.output == right
    forgeries = {
        "forged verdict approve": right.model_copy(update={"verdict": "approve"}),
        "forged verdict needs human": right.model_copy(update={"verdict": "needs_human_review"}),
        "correct verdict, another digest": right.model_copy(update={"evidence_sha256": "1" * 64}),
        "correct verdict, the M2 manifest digest": right.model_copy(update={"evidence_sha256": v.store._conn.execute(
            "SELECT manifest_sha256 FROM authority_observations WHERE kind = 'm2'").fetchone()[0]}),
    }
    for name, forged in forgeries.items():
        with pytest.raises(AuthorityRefusedError):
            review_observed(v, chain, None, output=forged, ticket=rticket)
    # The correct proposal bound to anything but its reviewer ticket.
    for other in (vticket, DispatchTicket.model_validate({**rticket.model_dump(mode="json"), "ticket_id": "e" * 32})):  # noqa: E501
        with pytest.raises((AuthorityRefusedError, ValueError)):
            review_observed(v, chain, None, output=right, ticket=other)
    with pytest.raises(AuthorityRefusedError):
        step = v.store.get_step_run(chain.step.step_run_id)
        v.store.apply_step_transition(step.step_run_id, step_request(step, StepEvent.REVIEW_OBSERVED, review=right))
    # A verification observation in place of the review.
    with pytest.raises((AuthorityRefusedError, ValueError)):
        step = v.store.get_step_run(chain.step.step_run_id)
        v.store.apply_step_transition(step.step_run_id, step_request(
            step, StepEvent.VERIFICATION_OBSERVED, verification=vbound.output),
            role_output=bind_role_output(rticket, vbound.output))
    assert v.store.get_step_run(chain.step.step_run_id).state is StepState.REVIEWING
    review_observed(v, chain, rbound)
    assert v.store.get_step_run(chain.step.step_run_id).review_verdict == "changes_requested"


@needs_windows
def test_only_the_session_minted_claim_recorder_can_record_a_review(v: V) -> None:
    chain, _, _ = at_reviewing(v)
    rticket = rticket_for(v, chain)
    before = snapshot(v.store)
    write_key = v.store._require_authority().write_key
    for key in (None, object(), write_key):
        with pytest.raises(AuthorityRefusedError, match="execution claim adapter"):
            v.store._perform_review_observation(key, rticket)
    contract = v.store.get_step_contract(chain.contract.sha256)
    with pytest.raises(AuthorityRefusedError):
        mint_execution_claim_adapter(v.store, object()).review(step_contract=contract, attempt=1, dispatch=rticket)
    with pytest.raises(AuthorityRefusedError):
        v.session.implementer.implement(step_contract=contract, attempt=1, dispatch=rticket)
    assert snapshot(v.store) == before


def test_the_adapter_exposes_verify_and_review_and_no_recorder() -> None:
    adapter = mint_execution_claim_adapter(object(), object())
    assert {n for n in dir(adapter) if not n.startswith("_")} == {"verify", "review"}
    with pytest.raises(AttributeError):
        adapter._recorder = None
    with pytest.raises(TypeError):
        ExecutionClaimAdapter(object(), object())


@needs_windows
def test_the_session_reviewer_is_its_one_execution_claim_adapter(v: V) -> None:
    assert v.session.reviewer is v.session.verifier
    assert type(v.session.reviewer) is ExecutionClaimAdapter


@needs_windows
@pytest.mark.parametrize("name", ["approve with a blocker", "changes requested with nothing blocking",
                                  "summary too long", "line a string", "finding extra field"])
def test_a_recorded_packet_whose_review_the_command_never_prints_answers_no_reviewer(v: V, name) -> None:
    """S4 binds the verification half of a packet; S5 refuses its review half
    if the frozen command could not have printed it. Nothing is recorded."""
    chain, vticket, _ = at_reviewing(v, stdout=lambda real: _with_review(real, REVIEW_MUTATIONS[name]))
    rticket = rticket_for(v, chain)
    before = snapshot(v.store)
    with pytest.raises(ReviewEvidenceRefusedError):
        review(v, chain, rticket)
    assert snapshot(v.store) == before and review_rows(v) == []
    assert v.store.recover(chain.project.project_run_id).integrity_ok


@needs_windows
def test_a_forged_but_coherent_review_is_recorded_only_as_an_execution_claim(v: V) -> None:
    """D-2′: X can print any coherent review. It reaches ACCEPTANCE labeled a
    claim, and the step still needs S6's signed human acceptance."""
    forged = {"verdict": "approve", "summary": "Looks great.", "findings": [], "residual_risks": [],
              "human_notes": []}
    v.reviewer.content = CHANGES_REVIEW  # the model really asked for changes
    chain, _, _ = at_reviewing(v, CHANGES_REVIEW, stdout=lambda real: _with_review(real, forged))
    rticket = rticket_for(v, chain)
    rbound = review(v, chain, rticket)
    assert rbound.output.verdict == "approve" and review_rows(v)[0]["provenance"] == "execution_claim"
    review_observed(v, chain, rbound)
    assert v.store.get_step_run(chain.step.step_run_id).state is StepState.ACCEPTANCE


# =============================================================================
# 5. revocation, and loss or alteration of the S4 evidence
# =============================================================================


@needs_windows
def test_revoking_the_approver_after_s4_records_no_review(v: V) -> None:
    chain, _, _ = at_reviewing(v)
    rticket = rticket_for(v, chain)
    _set_alice(v, revoked=True)
    with pytest.raises((AuthorityRefusedError, StateUntrustedError)):
        review(v, chain, rticket)
    _set_alice(v, revoked=False)
    assert review_rows(v) == []


@needs_windows
def test_revoking_the_approver_after_the_review_evidence_refuses_review_observed(v: V) -> None:
    chain, _, _ = at_reviewing(v)
    rticket = rticket_for(v, chain)
    rbound = review(v, chain, rticket)
    _set_alice(v, revoked=True)
    with pytest.raises((AuthorityRefusedError, StateUntrustedError)):
        review_observed(v, chain, rbound)
    assert not v.store.recover(chain.project.project_run_id).integrity_ok


S4_LOSS = {
    "verification evidence deleted": "DELETE FROM verification_evidence_v2",
    "verification evidence outcome": "UPDATE verification_evidence_v2 SET outcome = 'verification-failed'",
    "verification claim digest": "UPDATE verification_evidence_v2 SET claim_sha256 = '" + "9" * 64 + "'",
    "claim row deleted": "DELETE FROM execution_claims WHERE shape = 'review-packet'",
    "m2 deleted": "DELETE FROM authority_observations WHERE kind = 'm2'",
}


@needs_windows
@pytest.mark.parametrize("name", list(S4_LOSS) + ["claim blob altered", "claim blob deleted"])
def test_s4_evidence_lost_between_review_evidence_and_review_observed_is_never_consumed(v: V, name) -> None:
    chain, _, _ = at_reviewing(v)
    rticket = rticket_for(v, chain)
    rbound = review(v, chain, rticket)
    v.close()
    if name.startswith("claim blob"):
        sha = rbound.output.evidence_sha256
        path = Path(v.root.path, "evidence", "claims", sha)
        os.chmod(path, 0o666)
        path.unlink() if name.endswith("deleted") else path.write_bytes(path.read_bytes() + b" ")
    else:
        conn = sqlite3.connect(v.root.store_path)
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute(S4_LOSS[name])
        conn.commit()
        conn.close()
    store = v.open()
    with pytest.raises((AuthorityRefusedError, StateUntrustedError)):
        review_observed(v, chain, rbound)
    report = store.recover(chain.project.project_run_id)
    assert not report.integrity_ok, name


# =============================================================================
# 6. duplicates and repeated consumption
# =============================================================================


@needs_windows
def test_a_review_is_recorded_once_and_consumed_once(v: V, monkeypatch) -> None:
    chain, _, _ = at_reviewing(v)
    guard = NoSecondRun(v, monkeypatch)
    rticket = rticket_for(v, chain)
    rbound = review(v, chain, rticket)
    with pytest.raises(AuthorityRefusedError, match="reviewed once"):
        review(v, chain, rticket)
    step = v.store.get_step_run(chain.step.step_run_id)
    with pytest.raises(AuthorityRefusedError):
        v.store.issue_dispatch_ticket(step.step_run_id, role="reviewer", expected_state_version=step.state_version)
    assert len(review_rows(v)) == 1
    review_observed(v, chain, rbound)
    with pytest.raises(AuthorityRefusedError):
        review_observed(v, chain, rbound)
    with pytest.raises(AuthorityRefusedError):
        review(v, chain, rticket)
    guard.check()
    assert len(review_rows(v)) == 1


@needs_windows
def test_review_evidence_binds_exactly_one_verification(v: V) -> None:
    reviewed(v)
    conn = v.store._conn
    conn.execute("PRAGMA foreign_keys = OFF")  # isolate the UNIQUE constraint from the ticket FK
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        conn.execute("INSERT INTO review_evidence SELECT 'e' || substr(ticket_id, 2), verifier_ticket_id, "
                     "claim_sha256, verdict, provenance, recorded_at FROM review_evidence")
    conn.rollback()
    conn.execute("PRAGMA foreign_keys = ON")


# =============================================================================
# 7. crashes
# =============================================================================


@needs_windows
@pytest.mark.parametrize("after", [False, True])
def test_a_crash_while_recording_review_evidence_records_nothing_and_never_reruns(v: V, monkeypatch,
                                                                                  after) -> None:
    chain, _, _ = at_reviewing(v)
    guard = NoSecondRun(v, monkeypatch)
    rticket = rticket_for(v, chain)
    proxy = crash_at(v.store, "INSERT INTO review_evidence", after=after)
    with pytest.raises(SimulatedCrash):
        review(v, chain, rticket)
    assert not proxy.armed
    v.close()
    store = v.open()
    report = store.recover(chain.project.project_run_id)
    assert report.integrity_ok, report.integrity_issues
    assert store.get_step_run(chain.step.step_run_id).state is StepState.RECOVERY_REQUIRED
    assert review_rows(v) == [] and len(evidence(v)) == 1
    with pytest.raises(AuthorityRefusedError):
        review(v, chain, rticket)
    guard.check()


@needs_windows
def test_a_crash_after_the_review_evidence_commit_leaves_recovery_required_with_proven_evidence(
        v: V, monkeypatch) -> None:
    chain, _, _ = at_reviewing(v)
    guard = NoSecondRun(v, monkeypatch)
    rticket = rticket_for(v, chain)
    rbound = review(v, chain, rticket)  # durable; REVIEW_OBSERVED never happens
    v.close()
    store = v.open()
    report = store.recover(chain.project.project_run_id)
    assert report.integrity_ok, report.integrity_issues
    assert store.get_step_run(chain.step.step_run_id).state is StepState.RECOVERY_REQUIRED
    assert len(review_rows(v)) == 1
    with pytest.raises(AuthorityRefusedError):
        review_observed(v, chain, rbound)
    with pytest.raises(AuthorityRefusedError):
        review(v, chain, rticket)
    guard.check()


@needs_windows
def test_a_reopened_store_re_proves_every_recorded_review_transition(v: V) -> None:
    chain, _, rticket, rbound = reviewed(v, CHANGES_REVIEW)
    for _ in range(2):
        v.close()
        store = v.open()
        report = store.recover(chain.project.project_run_id)
        assert report.integrity_ok, report.integrity_issues
        assert store.get_step_run(chain.step.step_run_id).review_verdict == "changes_requested"
    assert store._review_evidence_issue(rticket.ticket_id, rbound.output) is None


# =============================================================================
# 8. the tamper matrix: every S5 record re-proves, or the run is untrusted
# =============================================================================

NINES = "'" + "9" * 64 + "'"
S5_TAMPERS = {
    "review verdict": "UPDATE review_evidence SET verdict = 'changes_requested'",
    "review claim digest": f"UPDATE review_evidence SET claim_sha256 = {NINES}",
    "review claim digest is m2": "UPDATE review_evidence SET claim_sha256 = "
                                 "(SELECT manifest_sha256 FROM authority_observations WHERE kind = 'm2')",
    "review verifier ticket": "UPDATE review_evidence SET verifier_ticket_id = (SELECT ticket_id FROM write_intents)",
    "review provenance": "UPDATE review_evidence SET provenance = 'authority_observation'",
    "review evidence removed": "DELETE FROM review_evidence",
    "review evidence moved to the verifier ticket": "UPDATE review_evidence SET ticket_id = verifier_ticket_id",
    "a second review evidence row": "INSERT INTO review_evidence SELECT 'x', 'y', claim_sha256, verdict, "
                                    "provenance, recorded_at FROM review_evidence",
    "transition verdict": "UPDATE transitions SET review_verdict = 'needs_human_review' "
                          "WHERE event = 'review_observed'",
    "reviewer ticket role": "UPDATE dispatch_tickets SET role = 'planner' "
                            "WHERE ticket_id = (SELECT ticket_id FROM review_evidence)",
    "reviewer ticket unanswered": "UPDATE dispatch_tickets SET consumed_request_id = NULL "
                                  "WHERE ticket_id = (SELECT ticket_id FROM review_evidence)",
    "reviewer ticket version": "UPDATE dispatch_tickets SET state_version = state_version + 1 "
                               "WHERE ticket_id = (SELECT ticket_id FROM review_evidence)",
    "verification evidence removed": "DELETE FROM verification_evidence_v2",
    "verification outcome": "UPDATE verification_evidence_v2 SET outcome = 'verification-failed'",
    "verification transition outcome": "UPDATE transitions SET verification_outcome = 'verification-failed' "
                                       "WHERE event = 'verification_observed'",
    "claim shape": "UPDATE execution_claims SET shape = 'verification-failed' WHERE shape = 'review-packet'",
    "m2 removed": "DELETE FROM authority_observations WHERE kind = 'm2'",
    "write evidence removed": "DELETE FROM write_evidence",
}


@needs_windows
@pytest.mark.parametrize("name", list(S5_TAMPERS) + ["claim blob"])
def test_a_tampered_s5_record_makes_the_run_untrusted(v: V, name) -> None:
    chain, _, _, rbound = reviewed(v)
    v.close()
    if name == "claim blob":
        path = Path(v.root.path, "evidence", "claims", rbound.output.evidence_sha256)
        os.chmod(path, 0o666)
        path.write_bytes(path.read_bytes() + b" ")
    else:
        conn = sqlite3.connect(v.root.store_path)
        conn.execute("PRAGMA ignore_check_constraints = ON")
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute(S5_TAMPERS[name])
        conn.commit()
        conn.close()
    store = v.open()
    report = store.recover(chain.project.project_run_id)
    assert not report.integrity_ok, name
    with pytest.raises(StateUntrustedError):
        store.get_step_run(chain.step.step_run_id)


@needs_windows
def test_a_tampered_step_run_verdict_is_detected_and_escalated(v: V) -> None:
    """R5-8: DL-1's frozen integrity escalation detects the tampered cached
    verdict and moves the run to HUMAN_REQUIRED; its escalation transition
    copies the row's facts, so S6 must take the verdict from review_evidence
    and the REVIEW_OBSERVED transition, never from ``step_runs``."""
    chain, _, rticket, _ = reviewed(v)
    v.close()
    conn = sqlite3.connect(v.root.store_path)
    conn.execute("UPDATE step_runs SET review_verdict = 'needs_human_review'")
    conn.commit()
    conn.close()
    store = v.open()
    report = store.recover(chain.project.project_run_id)
    assert not report.integrity_ok
    assert any("not explained by its log" in issue for issue in report.integrity_issues), report.integrity_issues
    assert report.escalated_step_run_ids == (chain.step.step_run_id,)
    assert store.get_step_run(chain.step.step_run_id).state is StepState.HUMAN_REQUIRED
    # The review record itself still says what the claim bytes say.
    assert store._conn.execute("SELECT verdict FROM review_evidence").fetchone()[0] == "approve"
    assert store._review_evidence_issue(rticket.ticket_id) is None


@needs_windows
def test_a_replacement_packet_under_the_same_digest_name_is_refused(v: V) -> None:
    """Content addressing: another packet can never stand in for the S4 bytes."""
    chain, _, _, rbound = reviewed(v, CHANGES_REVIEW)
    v.close()
    path = Path(v.root.path, "evidence", "claims", rbound.output.evidence_sha256)
    other = _with_review(path.read_bytes(), {"verdict": "approve", "findings": []})
    os.chmod(path, 0o666)
    path.write_bytes(other)
    report = v.open().recover(chain.project.project_run_id)
    assert not report.integrity_ok


# =============================================================================
# 9. DL-3 → DL-2
# =============================================================================


class ReviewingPorts(Ports):
    def __init__(self, implementer, verifier, reviewer) -> None:
        super().__init__(implementer, verifier)
        self.reviewer_port = reviewer

    def role_ports(self):
        ports = super().role_ports()
        return type(ports)(planner=ports.planner, tester=ports.tester, implementer=ports.implementer,
                           verifier=ports.verifier, reviewer=self.reviewer_port)


@needs_windows
def test_the_orchestration_path_records_the_review_from_the_s4_claim(v: V) -> None:
    chain = _planned(v)
    _x_steps(v)
    ports = ReviewingPorts(v.session.implementer, v.session.verifier, v.session.reviewer)
    ProjectOuterLoop(v.store, ports.role_ports()).run(
        project_run=v.store.get_project_run(chain.project.project_run_id),
        project_contract=chain.pc, execution_plan=chain.plan)
    events = [r.event for r in v.store.transitions_for(chain.step.step_run_id)]
    assert StepEvent.VERIFICATION_OBSERVED.value in events and StepEvent.REVIEW_OBSERVED.value in events
    assert v.reviewer.requests == 1 and v.waiter.queue == []  # one review-command run, one model request
    [row] = review_rows(v)
    assert row["claim_sha256"] == evidence(v)[0]["claim_sha256"] and row["verdict"] == "approve"
    assert "reviewer" not in ports.calls and ports.calls[0] == "planner"  # S6 does not exist
    step = v.store.get_step_run(chain.step.step_run_id)
    assert step.review_verdict == "approve" and step.state is not StepState.COMPLETE
    assert v.store.recover(chain.project.project_run_id).integrity_ok
    dirs, requests = v.handoff_dirs(), v.reviewer.requests
    again = ReviewingPorts(v.session.implementer, v.session.verifier, v.session.reviewer)
    ProjectOuterLoop(v.store, again.role_ports()).run(
        project_run=v.store.get_project_run(chain.project.project_run_id),
        project_contract=chain.pc, execution_plan=chain.plan)
    assert v.handoff_dirs() == dirs and v.reviewer.requests == requests and len(review_rows(v)) == 1


@needs_windows
def test_the_orchestration_path_with_a_forged_reviewer_reaches_no_trusted_state(v: V) -> None:
    chain = _planned(v)
    _x_steps(v)

    class Forger:
        def review(self, *, step_contract, attempt, dispatch=None):
            evidence_sha256 = evidence(v)[0]["claim_sha256"]  # even the right digest
            return bind_role_output(dispatch, ReviewProposal(
                step_contract_sha256=step_contract.sha256, attempt=attempt, verdict="approve",
                evidence_sha256=evidence_sha256))

    ports = ReviewingPorts(v.session.implementer, v.session.verifier, Forger())
    ProjectOuterLoop(v.store, ports.role_ports()).run(
        project_run=v.store.get_project_run(chain.project.project_run_id),
        project_contract=chain.pc, execution_plan=chain.plan)
    events = [r.event for r in v.store.transitions_for(chain.step.step_run_id)]
    assert StepEvent.VERIFICATION_OBSERVED.value in events and StepEvent.REVIEW_OBSERVED.value not in events
    assert v.store.get_step_run(chain.step.step_run_id).state is StepState.RECOVERY_REQUIRED
    assert review_rows(v) == [] and ports.calls == [] and v.reviewer.requests == 1


# =============================================================================
# 10. static boundaries
# =============================================================================

_PACKAGE = Path(integration.__file__).resolve().parent


def test_s5_code_has_no_execution_network_model_git_or_harness_surface() -> None:
    import ast

    harness = ("ai_dev_orchestrator.llm", "ai_dev_orchestrator.github", "ai_dev_orchestrator.review",
               "ai_dev_orchestrator.verification", "ai_dev_orchestrator.file_editing",
               "ai_dev_orchestrator.supervised_implementer", "ai_dev_orchestrator.workspace",
               "ai_dev_orchestrator.diff_proposal", "ai_dev_orchestrator.cli")
    for name in ("execution_claim.py", "claim_readers.py", "integration_store.py", "integration_session.py"):
        assert not [m for m in _imports(_PACKAGE / name) if m.startswith(harness)], name
    tree = ast.parse((_PACKAGE / "integration_store.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in (
                "_reviewer_chain", "_reviewer_state", "_perform_review_observation", "_review_evidence_issue"):
            called = {n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
                      for n in ast.walk(node) if isinstance(n, ast.Call)}
            # No handoff, no wait, no claim read, no observation, no publication.
            assert not called & {"publish_handoff", "await_completion", "read_claim", "observe_workspace",
                                 "_publish_blob", "_perform_review_handoff", "sleep", "_files"}, (node.name, called)


def test_no_s5_public_api_accepts_a_proposal_verdict_or_digest() -> None:
    import inspect

    for owner in (IntegrationStore, ExecutionClaimAdapter):
        for name, member in inspect.getmembers(owner, callable):
            if name.startswith("_"):
                continue
            for parameter in inspect.signature(member).parameters.values():
                lowered = parameter.name.lower()
                assert not any(word in lowered for word in (
                    "verdict", "review", "packet", "claim", "evidence", "digest", "bytes")), (name, parameter)
                assert "ReviewProposal" not in str(parameter.annotation), (name, parameter)
    assert set(inspect.signature(ExecutionClaimAdapter.review).parameters) == {
        "self", "step_contract", "attempt", "dispatch"}
