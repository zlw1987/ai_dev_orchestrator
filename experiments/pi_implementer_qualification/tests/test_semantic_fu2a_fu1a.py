"""5F3B-Q1-PRE1-FU2A-FU1A -- Final authority-issuance closure.

**No real network connection, credential, Node/Pi process, named pipe, or
model call is ever made here.** Every live-facing adapter is a synthetic
double, exactly as in the rest of this suite.

Independent review accepted FU2A-FU1 except for THREE remaining
construction-authority bypasses:

    1. ``EvidenceEmission``'s success check (``self._issuance is not None``)
       was satisfiable by ANY non-``None`` object -- e.g.
       ``EvidenceEmission(..., refused=False, ..., _issuance=object())`` --
       not one specific, unobtainable value;
    2. the identity-provenance cross-check (FU2A-FU1) compared
       ``self.candidate``/etc. against a plain string embedded in
       ``qualification_record``/``attempt_record`` -- both ordinary
       caller-editable copies, so replacing BOTH together (top-level fields
       AND the embedded projection) consistently passed unrefused;
    3. ``_require_valid_attempt_payload`` accepted any unknown top-level or
       ``pi_runtime`` field (scrub-clean, so it rode along unexamined), and
       accepted ANY ``CategoryBFailureCode`` on ``runtime_teardown``/
       ``broker_shutdown`` rather than only the codes each resource kind's
       own frozen typed status object can actually produce.

This module reproduces each as a failing-before-fix regression and proves
it is refused after the fix, plus positive controls proving genuine
controller-produced objects are unaffected.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from qualification.corpus import IQ1_TASK, TASKS_BY_ID
from qualification.hard_bar import QualificationState
from qualification.records import CANDIDATE_MODEL_IDS
from qualification.safety import ArtifactSafetyContext
from qualification.semantic_attempt import (
    AttemptRecordInvariantError,
    build_attempt_record,
    emit_attempt_or_refuse,
)
from qualification.semantic_controller import EvidenceEmission

from test_semantic_controller import Harness, _iq1_correct_repair
from test_semantic_fu2a import _genuine_indeterminate_attempt_kwargs
from test_semantic_sweep import _run_sweep


@pytest.fixture()
def evidence_path(tmp_path: Path) -> str:
    return str(tmp_path / "evidence.json")


@pytest.fixture()
def harness(git_executable: str) -> Harness:
    return Harness("A", git_executable)


# ===========================================================================
# 1. EVIDENCEEMISSION SUCCESS IS STILL PUBLICLY FORGEABLE
# ===========================================================================


def test_evidence_emission_object_issuance_cannot_make_success() -> None:
    """The independent review's exact counterexample: passing an arbitrary
    ``object()`` (or any other value) as issuance can no longer even be
    ATTEMPTED -- there is no ``_issuance`` field left at all, and the public
    constructor refuses ``refused=False`` unconditionally.
    """
    with pytest.raises(TypeError):
        # No `_issuance` parameter exists any more.
        EvidenceEmission(
            emitted=True,
            refused=False,
            path="x",
            scrub_checked=True,
            clean=True,
            findings=(),
            _issuance=object(),  # type: ignore[call-arg]
        )
    with pytest.raises(ValueError):
        EvidenceEmission(
            emitted=True, refused=False, path="x", scrub_checked=True, clean=True, findings=()
        )


def test_evidence_emission_success_is_unconstructible_for_any_argument_combination() -> None:
    """No combination of the six public fields can ever produce a
    ``refused=False`` instance through the public constructor.
    """
    for emitted, scrub_checked, clean, findings in (
        (True, True, True, ()),
        (False, False, True, ()),
        (True, True, True, ("finding",)),
    ):
        with pytest.raises(ValueError):
            EvidenceEmission(
                emitted=emitted,
                refused=False,
                path="x",
                scrub_checked=scrub_checked,
                clean=clean,
                findings=findings,
            )


def test_scrub_refused_result_cannot_be_upgraded_to_h14_success(
    harness: Harness, evidence_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stronger end-to-end bypass: a genuine scrub-refused result,
    combined with a forged ``qualification_record``/``attempt_record``
    (``refused=False``) AND a caller-built "successful" ``EvidenceEmission``,
    must not be able to turn H-14 from failure to pass. It cannot even get
    off the ground: the caller-built successful ``EvidenceEmission`` is
    itself unconstructible.
    """
    import qualification.safety as safety_module

    _iq1_correct_repair(harness)
    real_scrub_check = safety_module.qualification_scrub_check

    def _dirty_scrub(payload, safety):
        if payload.get("record_kind") == "artifact emission refusal":
            return real_scrub_check(payload, safety)
        return {"scrub_checked": True, "findings": ["needle_present"], "clean": False}

    monkeypatch.setattr(safety_module, "qualification_scrub_check", _dirty_scrub)
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.evidence_emission.refused is True  # genuine scrub refusal

    forged_projection = dict(result.qualification_record)
    forged_projection["refused"] = False
    forged_projection["path"] = result.evidence_emission.path

    with pytest.raises(ValueError):
        forged_emission = EvidenceEmission(
            emitted=True,
            refused=False,
            path=result.evidence_emission.path,
            scrub_checked=True,
            clean=True,
            findings=(),
        )
        # Unreachable if the line above raises, as it must.
        replace(
            result,
            qualification_record=forged_projection,
            evidence_emission=forged_emission,
        )


def test_real_successful_primary_emission_still_yields_h14_success(
    harness: Harness, evidence_path: str
) -> None:
    """Positive control."""
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.evidence_emission is not None
    assert result.evidence_emission.refused is False
    assert result.evidence_emission.emitted is True


def test_real_successful_attempt_emission_still_yields_its_genuine_projection(
    git_executable: str, tmp_path: Path
) -> None:
    """Positive control."""
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    record = build_attempt_record(**kwargs)
    emission = emit_attempt_or_refuse(
        record, path=str(tmp_path / "genuine.json"), safety=ArtifactSafetyContext.none_declared()
    )
    assert emission["refused"] is False
    assert emission["emitted"] is True


def test_real_scrub_refusal_still_yields_h14_failure(
    harness: Harness, evidence_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Positive control."""
    import qualification.safety as safety_module

    _iq1_correct_repair(harness)
    real_scrub_check = safety_module.qualification_scrub_check

    def _dirty_scrub(payload, safety):
        if payload.get("record_kind") == "artifact emission refusal":
            return real_scrub_check(payload, safety)
        return {"scrub_checked": True, "findings": ["needle_present"], "clean": False}

    monkeypatch.setattr(safety_module, "qualification_scrub_check", _dirty_scrub)
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.evidence_emission.refused is True


# ===========================================================================
# 2. RESULT IDENTITY PROVENANCE IS STILL CALLER-AUTHORABLE
# ===========================================================================


def test_complete_a_to_b_relabel_of_result_and_projection_together_refused(
    harness: Harness, evidence_path: str
) -> None:
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    forged_projection = dict(result.qualification_record)
    forged_projection["candidate"] = "B"
    forged_projection["model_id"] = CANDIDATE_MODEL_IDS["B"]
    with pytest.raises(ValueError):
        replace(
            result,
            candidate="B",
            model_id=CANDIDATE_MODEL_IDS["B"],
            qualification_record=forged_projection,
        )


def test_complete_iq1_to_iq2_relabel_of_result_and_projection_together_refused(
    harness: Harness, evidence_path: str
) -> None:
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    forged_projection = dict(result.qualification_record)
    forged_projection["task_id"] = "IQ-2"
    forged_projection["task_revision"] = TASKS_BY_ID["IQ-2"].task_revision
    with pytest.raises(ValueError):
        replace(
            result,
            task_id="IQ-2",
            task_revision=TASKS_BY_ID["IQ-2"].task_revision,
            qualification_record=forged_projection,
        )


def test_relabelled_object_cannot_enter_the_new_candidate_task_sweep(
    git_executable: str, tmp_path: Path
) -> None:
    from qualification.semantic_sweep import PrimarySweepResult

    result_a, _ = _run_sweep("A", git_executable, tmp_path, correct=True)
    genuine_iq1 = result_a.task_results["IQ-1"]
    forged_projection = dict(genuine_iq1.qualification_record)
    forged_projection["candidate"] = "B"
    forged_projection["model_id"] = CANDIDATE_MODEL_IDS["B"]
    with pytest.raises(ValueError):
        relabelled = replace(
            genuine_iq1,
            candidate="B",
            model_id=CANDIDATE_MODEL_IDS["B"],
            qualification_record=forged_projection,
        )
        # Unreachable if the line above raises, as it must.
        PrimarySweepResult(
            candidate="B",
            model_id=CANDIDATE_MODEL_IDS["B"],
            task_results={"IQ-1": relabelled},
            confirmed_semantic_prompts_sent=relabelled.semantic_prompts_sent or 0,
            semantic_dispatch_attempts=1,
            indeterminate_dispatch_task_ids=(),
            not_attempted_task_ids=("IQ-2", "IQ-3"),
            hard_bar_result=result_a.hard_bar_result,
        )


def test_genuine_construction_identity_provenance_is_correct(
    harness: Harness, evidence_path: str
) -> None:
    """Positive control: identity_provenance is genuinely minted for this
    attempt's own candidate.

    5F3B-Q1-PRE1-FINAL-CLOSURE: this test previously proved a plain
    ``replace()`` of an unrelated field (``observed_pi_version``) still
    worked. It no longer does, and must not: ``SemanticTaskAttemptResult``
    is now a one-shot, valid-by-construction authority object, and the
    genuine construction below already consumed the only issuance this
    result's bundle will ever have.
    """
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.candidate == "A"
    assert result.identity_provenance.candidate == "A"
    with pytest.raises(ValueError):
        replace(result, observed_pi_version=result.observed_pi_version)


def test_full_sweeps_still_qualify_after_fu2a_fu1a(
    git_executable: str, tmp_path: Path
) -> None:
    """Positive control: nothing about genuine sweep construction changed."""
    result_a, _ = _run_sweep("A", git_executable, tmp_path, correct=True)
    assert result_a.hard_bar_result.qualification_state is QualificationState.AUTONOMOUS_QUALIFIED


# ===========================================================================
# 3. ATTEMPT.V1 CLOSED SHAPE + EXACT RESOURCE FAILURE DOMAINS
# ===========================================================================


def test_attempt_builder_rejects_an_extra_top_level_semantic_field(
    git_executable: str, tmp_path: Path
) -> None:
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    record = build_attempt_record(**kwargs)
    tampered = dict(record)
    tampered["semantic_prompt_definitely_sent"] = True
    target = tmp_path / "extra_top_level.json"
    with pytest.raises(AttemptRecordInvariantError):
        emit_attempt_or_refuse(
            tampered, path=str(target), safety=ArtifactSafetyContext.none_declared()
        )
    assert not target.exists()


def test_attempt_builder_rejects_an_extra_provider_request_count_field(
    git_executable: str, tmp_path: Path
) -> None:
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    record = build_attempt_record(**kwargs)
    tampered = dict(record)
    tampered["provider_request_count"] = 1
    target = tmp_path / "extra_provider_count.json"
    with pytest.raises(AttemptRecordInvariantError):
        emit_attempt_or_refuse(
            tampered, path=str(target), safety=ArtifactSafetyContext.none_declared()
        )
    assert not target.exists()


def test_attempt_builder_rejects_an_extra_pi_runtime_field(
    git_executable: str, tmp_path: Path
) -> None:
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    record = build_attempt_record(**kwargs)
    tampered = dict(record)
    tampered["pi_runtime"] = {**tampered["pi_runtime"], "active_tool_registry": []}
    target = tmp_path / "extra_pi_runtime.json"
    with pytest.raises(AttemptRecordInvariantError):
        emit_attempt_or_refuse(
            tampered, path=str(target), safety=ArtifactSafetyContext.none_declared()
        )
    assert not target.exists()


@pytest.mark.parametrize("gate_name", ["runtime_teardown", "broker_shutdown"])
def test_attempt_builder_rejects_route_check_failed_on_closure_gates(
    git_executable: str, tmp_path: Path, gate_name: str
) -> None:
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    gate_statuses = dict(kwargs["gate_statuses"])
    gate_statuses[gate_name] = "FAILED:ROUTE_CHECK_FAILED"
    kwargs["gate_statuses"] = gate_statuses
    closure = dict(kwargs["closure"])
    closure[gate_name] = "FAILED:ROUTE_CHECK_FAILED"
    closure["closure_established"] = False
    kwargs["closure"] = closure
    with pytest.raises(AttemptRecordInvariantError):
        build_attempt_record(**kwargs)


def test_attempt_builder_rejects_runtime_carrying_a_broker_only_failure_code(
    git_executable: str, tmp_path: Path
) -> None:
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    gate_statuses = dict(kwargs["gate_statuses"])
    gate_statuses["runtime_teardown"] = "FAILED:BROKER_SHUTDOWN_INCOMPLETE"
    kwargs["gate_statuses"] = gate_statuses
    closure = dict(kwargs["closure"])
    closure["runtime_teardown"] = "FAILED:BROKER_SHUTDOWN_INCOMPLETE"
    closure["closure_established"] = False
    kwargs["closure"] = closure
    with pytest.raises(AttemptRecordInvariantError):
        build_attempt_record(**kwargs)


def test_attempt_builder_rejects_broker_carrying_a_runtime_only_failure_code(
    git_executable: str, tmp_path: Path
) -> None:
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    gate_statuses = dict(kwargs["gate_statuses"])
    gate_statuses["broker_shutdown"] = "FAILED:RUNTIME_TEARDOWN_FAILED"
    kwargs["gate_statuses"] = gate_statuses
    closure = dict(kwargs["closure"])
    closure["broker_shutdown"] = "FAILED:RUNTIME_TEARDOWN_FAILED"
    closure["closure_established"] = False
    kwargs["closure"] = closure
    with pytest.raises(AttemptRecordInvariantError):
        build_attempt_record(**kwargs)


def test_genuine_successful_attempt_record_still_builds_after_fu2a_fu1a(
    git_executable: str, tmp_path: Path
) -> None:
    """Positive control: an ordinary genuine indeterminate attempt (closed
    shape, real resource-domain codes) still round-trips.
    """
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    record = build_attempt_record(**kwargs)
    assert set(record) == {
        "experiment", "record_version", "fixture_schema_version", "record_kind",
        "is_review_packet", "reviewer_invoked", "external_prior_not_scored",
        "trust_namespaces", "candidate", "model_id", "task_id", "task_revision",
        "semantic_dispatch_state", "dispatch_evidence_code",
        "semantic_prompts_sent_established", "attempt_consumed",
        "qualification_record_emitted", "scoring_eligible", "run_validity",
        "autonomous_classification", "diagnostic_subclassification",
        "hard_bar_evaluable", "operator_continuation", "automatic_semantic_retry",
        "pi_runtime", "route_provenance", "gate_statuses", "closure",
        "cleanup_classification_unavailable_reason",
        "workspace_removal_classification_unavailable_reason", "token_policy",
        "claim_scope",
    }


def test_genuine_failed_closure_attempt_record_still_builds_after_fu2a_fu1a(
    git_executable: str, tmp_path: Path
) -> None:
    """Positive control: a genuine closure FAILURE (real resource-domain
    code) is still an accepted, truthful attempt.v1 artifact.
    """
    import json

    h = Harness("A", git_executable)
    h.dispatch_semantic_prompt = lambda request: (_ for _ in ()).throw(
        ConnectionResetError("wire dropped after (maybe) writing the request")
    )
    h.runtime_shutdown_ok = False
    evidence_path_ = str(tmp_path / "genuine_failed.json")
    h.run(IQ1_TASK, evidence_path_)
    payload = json.loads(Path(evidence_path_).read_text(encoding="utf-8"))
    assert payload["closure"]["runtime_teardown"] == "FAILED:RUNTIME_TEARDOWN_FAILED"
    assert payload["closure"]["closure_established"] is False
