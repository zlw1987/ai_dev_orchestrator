"""5F3B-Q1-PRE1-FU2A -- Result / Evidence / Sweep construction integrity closure.

**No real network connection, credential, Node/Pi process, named pipe, or
model call is ever made here.** Every live-facing adapter is a synthetic
double, exactly as in ``test_semantic_controller.py``/``test_semantic_sweep.py``.

FU2 correctly closed the mutation-integrity surface (frozen dataclasses,
deep in-memory immutability, monotonic dispatch truth). Independent review
then found several SUPPORTED CONSTRUCTION / SUBSTITUTION bypasses: facts
trusted by classification, the hard bar, retained evidence, sweep
aggregation and audit could still be FORGED through the public constructors
FU2 introduced or widened, even though no already-constructed object could
be mutated. This module reproduces each bypass as a failing-before-fix
regression and proves it is refused after the fix, plus positive controls
proving genuine controller-produced objects are unaffected.

Sections mirror ``PHASE_5F3B_Q1_PRE1_FU2A`` Sec. 2's lettered bypass list:

    A   forged sweep hard bar
    B   cross-candidate task substitution
    C   illegal task prefix / order
    D   hard-bar truthiness coercion
    E   caller-authored evidence success
    F   evidence coercion (bool()/str() at an authority boundary)
    G   result identity substitution
    H   forged indeterminate attempt artifact
    I   attempt emission consumption-boundary bypass
"""

from __future__ import annotations

import inspect
import json
from dataclasses import replace
from pathlib import Path

import pytest

from qualification.corpus import IQ1_TASK, IQ2_TASK, IQ3_TASK, TASKS_BY_ID
from qualification.hard_bar import HardBarResult, QualificationState
from qualification.i2_route import route_descriptor_for_candidate
from qualification.records import CANDIDATE_MODEL_IDS
from qualification.safety import ArtifactSafetyContext
from qualification.semantic_attempt import (
    ATTEMPT_RECORD_KIND,
    ATTEMPT_RECORD_VERSION,
    AttemptRecordInvariantError,
    build_attempt_record,
    emit_attempt_or_refuse,
)
from qualification.semantic_controller import EvidenceEmission
from qualification.semantic_session import (
    SemanticDispatchEvidenceCode,
    SemanticPromptDispatchState,
)
from qualification.semantic_sweep import (
    PrimarySweepResult,
    SweepInputError,
    _task_hard_bar_facts,
)

from test_semantic_controller import Harness, _iq1_correct_repair
from test_semantic_sweep import _run_sweep


@pytest.fixture()
def evidence_path(tmp_path: Path) -> str:
    return str(tmp_path / "evidence.json")


@pytest.fixture()
def harness(git_executable: str) -> Harness:
    return Harness("A", git_executable)


def _indeterminate(h: Harness) -> None:
    h.dispatch_semantic_prompt = lambda request: (_ for _ in ()).throw(
        ConnectionResetError("wire dropped after (maybe) writing the request")
    )


# ===========================================================================
# A. FORGED SWEEP HARD BAR
# ===========================================================================


def test_sweep_refuses_a_hard_bar_that_disagrees_with_its_own_task_results(
    git_executable: str, tmp_path: Path
) -> None:
    result, _ = _run_sweep("A", git_executable, tmp_path, correct=True)
    assert result.hard_bar_result.qualification_state is QualificationState.AUTONOMOUS_QUALIFIED
    forged = HardBarResult(QualificationState.NOT_QUALIFIED, ("IQ-1:H-2",), ())
    assert forged != result.hard_bar_result
    with pytest.raises(SweepInputError):
        replace(result, hard_bar_result=forged)


def test_sweep_result_direct_construction_refuses_a_convenient_hard_bar(
    git_executable: str, tmp_path: Path
) -> None:
    result, _ = _run_sweep("A", git_executable, tmp_path, correct=True)
    with pytest.raises(SweepInputError):
        PrimarySweepResult(
            candidate=result.candidate,
            model_id=result.model_id,
            task_results=dict(result.task_results),
            confirmed_semantic_prompts_sent=result.confirmed_semantic_prompts_sent,
            semantic_dispatch_attempts=result.semantic_dispatch_attempts,
            indeterminate_dispatch_task_ids=result.indeterminate_dispatch_task_ids,
            not_attempted_task_ids=result.not_attempted_task_ids,
            hard_bar_result=HardBarResult(QualificationState.INCOMPLETE, (), ("IQ-2",)),
        )


def test_sweep_result_accepts_the_freshly_derived_hard_bar_unchanged(
    git_executable: str, tmp_path: Path
) -> None:
    """Positive control: a genuine, self-consistent rebuild still works."""
    result, _ = _run_sweep("A", git_executable, tmp_path, correct=True)
    rebuilt = PrimarySweepResult(
        candidate=result.candidate,
        model_id=result.model_id,
        task_results=dict(result.task_results),
        confirmed_semantic_prompts_sent=result.confirmed_semantic_prompts_sent,
        semantic_dispatch_attempts=result.semantic_dispatch_attempts,
        indeterminate_dispatch_task_ids=result.indeterminate_dispatch_task_ids,
        not_attempted_task_ids=result.not_attempted_task_ids,
        hard_bar_result=result.hard_bar_result,
    )
    assert rebuilt.hard_bar_result == result.hard_bar_result


# ===========================================================================
# B. CROSS-CANDIDATE TASK SUBSTITUTION
# ===========================================================================


def test_sweep_refuses_a_candidate_b_result_inside_a_candidate_a_sweep(
    git_executable: str, tmp_path: Path
) -> None:
    result_a, _ = _run_sweep("A", git_executable, tmp_path, correct=True)
    result_b, _ = _run_sweep("B", git_executable, tmp_path, correct=True)
    forged = dict(result_a.task_results)
    # Same task_id key (passes the pre-existing task_id check), foreign
    # candidate/model -- exactly the bypass independent review reproduced.
    forged["IQ-1"] = result_b.task_results["IQ-1"]
    assert forged["IQ-1"].task_id == "IQ-1"
    with pytest.raises(SweepInputError):
        PrimarySweepResult(
            candidate=result_a.candidate,
            model_id=result_a.model_id,
            task_results=forged,
            confirmed_semantic_prompts_sent=result_a.confirmed_semantic_prompts_sent,
            semantic_dispatch_attempts=result_a.semantic_dispatch_attempts,
            indeterminate_dispatch_task_ids=result_a.indeterminate_dispatch_task_ids,
            not_attempted_task_ids=result_a.not_attempted_task_ids,
            hard_bar_result=result_a.hard_bar_result,
        )


# ===========================================================================
# C. ILLEGAL TASK PREFIX / ORDER
# ===========================================================================


def _genuine_result(harness_obj: Harness, task, evidence_path: str, *, indeterminate: bool = False):
    if indeterminate:
        _indeterminate(harness_obj)
    return harness_obj.run(task, evidence_path)


def _incomplete_hard_bar(*missing_ids: str) -> HardBarResult:
    return HardBarResult(QualificationState.INCOMPLETE, (), tuple(missing_ids))


def _sweep_kwargs_for(candidate: str, task_results: dict) -> dict:
    confirmed = sum((r.semantic_prompts_sent or 0) for r in task_results.values())
    attempts = sum(1 for r in task_results.values() if r.semantic_dispatch_attempted)
    indeterminate_ids = tuple(
        tid
        for tid, r in task_results.items()
        if r.dispatch_state is SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
    )
    all_ids = ("IQ-1", "IQ-2", "IQ-3")
    not_attempted = tuple(tid for tid in all_ids if tid not in task_results)
    return dict(
        candidate=candidate,
        model_id=CANDIDATE_MODEL_IDS[candidate],
        task_results=task_results,
        confirmed_semantic_prompts_sent=confirmed,
        semantic_dispatch_attempts=attempts,
        indeterminate_dispatch_task_ids=indeterminate_ids,
        not_attempted_task_ids=not_attempted,
        hard_bar_result=_incomplete_hard_bar(*not_attempted) if not_attempted else _incomplete_hard_bar(),
    )


def test_sweep_refuses_iq2_without_iq1(git_executable: str, tmp_path: Path) -> None:
    h = Harness("A", git_executable)
    result = _genuine_result(h, IQ2_TASK, str(tmp_path / "iq2.json"))
    with pytest.raises(SweepInputError):
        PrimarySweepResult(**_sweep_kwargs_for("A", {"IQ-2": result}))


def test_sweep_refuses_iq1_plus_iq3_without_iq2(git_executable: str, tmp_path: Path) -> None:
    h1 = Harness("A", git_executable)
    r1 = _genuine_result(h1, IQ1_TASK, str(tmp_path / "iq1.json"))
    h3 = Harness("A", git_executable)
    r3 = _genuine_result(h3, IQ3_TASK, str(tmp_path / "iq3.json"))
    with pytest.raises(SweepInputError):
        PrimarySweepResult(**_sweep_kwargs_for("A", {"IQ-1": r1, "IQ-3": r3}))


def test_sweep_refuses_a_result_after_an_indeterminate_task(
    git_executable: str, tmp_path: Path
) -> None:
    h1 = Harness("A", git_executable)
    r1 = _genuine_result(h1, IQ1_TASK, str(tmp_path / "iq1.json"))
    h2 = Harness("A", git_executable)
    r2 = _genuine_result(h2, IQ2_TASK, str(tmp_path / "iq2.json"), indeterminate=True)
    h3 = Harness("A", git_executable)
    r3 = _genuine_result(h3, IQ3_TASK, str(tmp_path / "iq3.json"))
    assert r2.dispatch_state is SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
    kwargs = _sweep_kwargs_for("A", {"IQ-1": r1, "IQ-2": r2, "IQ-3": r3})
    kwargs["hard_bar_result"] = _incomplete_hard_bar()
    with pytest.raises(SweepInputError):
        PrimarySweepResult(**kwargs)


def test_sweep_accepts_an_indeterminate_task_as_the_genuine_last_attempt(
    git_executable: str, tmp_path: Path
) -> None:
    """Positive control: a genuine stopped sweep (indeterminate IS last) still works."""
    h1 = Harness("A", git_executable)
    r1 = _genuine_result(h1, IQ1_TASK, str(tmp_path / "iq1.json"))
    h2 = Harness("A", git_executable)
    r2 = _genuine_result(h2, IQ2_TASK, str(tmp_path / "iq2.json"), indeterminate=True)
    kwargs = _sweep_kwargs_for("A", {"IQ-1": r1, "IQ-2": r2})
    kwargs["hard_bar_result"] = _incomplete_hard_bar("IQ-2", "IQ-3")
    result = PrimarySweepResult(**kwargs)
    assert set(result.task_results) == {"IQ-1", "IQ-2"}


def test_sweep_result_normalizes_reordered_mapping_to_canonical_order(
    git_executable: str, tmp_path: Path
) -> None:
    """A caller's own dict insertion order is never externally observable."""
    result, _ = _run_sweep("A", git_executable, tmp_path, correct=True)
    reordered = {
        "IQ-3": result.task_results["IQ-3"],
        "IQ-1": result.task_results["IQ-1"],
        "IQ-2": result.task_results["IQ-2"],
    }
    rebuilt = PrimarySweepResult(
        candidate=result.candidate,
        model_id=result.model_id,
        task_results=reordered,
        confirmed_semantic_prompts_sent=result.confirmed_semantic_prompts_sent,
        semantic_dispatch_attempts=result.semantic_dispatch_attempts,
        indeterminate_dispatch_task_ids=result.indeterminate_dispatch_task_ids,
        not_attempted_task_ids=result.not_attempted_task_ids,
        hard_bar_result=result.hard_bar_result,
    )
    assert list(rebuilt.task_results) == ["IQ-1", "IQ-2", "IQ-3"]


# ===========================================================================
# D. HARD-BAR TRUTHINESS
# ===========================================================================


@pytest.mark.parametrize(
    "field_name",
    [
        "verification_passed",
        "expected_changed_paths_satisfied",
        "head_unchanged",
        "index_clean",
        "protected_witness_untouched",
        "no_unexpected_untracked_or_create_delete_rename",
        "broker_git_cross_check_agrees",
    ],
)
def test_result_refuses_a_truthy_non_bool_hard_bar_authority_fact(
    harness: Harness, evidence_path: str, field_name: str
) -> None:
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    assert type(getattr(result, field_name)) is bool
    with pytest.raises(ValueError):
        replace(result, **{field_name: "false"})  # truthy non-bool


def test_task_hard_bar_facts_never_calls_bool_on_authority_fields() -> None:
    source = inspect.getsource(_task_hard_bar_facts)
    assert "bool(" not in source


def test_task_hard_bar_facts_produces_exact_bool_for_a_genuine_result(
    harness: Harness, evidence_path: str
) -> None:
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    facts = _task_hard_bar_facts(result)
    assert facts is not None
    assert type(facts.verification_passed) is bool
    assert type(facts.broker_git_cross_check_agrees) is bool


# ===========================================================================
# E. CALLER-AUTHORED EVIDENCE SUCCESS
# ===========================================================================


def test_evidence_emission_public_surface_cannot_manufacture_an_incoherent_success() -> None:
    with pytest.raises(ValueError):
        EvidenceEmission(
            emitted=False,
            refused=False,
            path="x",
            scrub_checked=False,
            clean=True,
            findings=(),
        )


def test_evidence_emission_public_surface_cannot_manufacture_any_success_shape() -> None:
    """The stronger authority question: even an internally COHERENT-looking
    success shape is refused unless it was actually issued by the real
    emission-projection path.
    """
    with pytest.raises(ValueError):
        EvidenceEmission(
            emitted=True,
            refused=False,
            path="x",
            scrub_checked=True,
            clean=True,
            findings=(),
        )


def test_a_genuine_successful_emission_still_constructs(
    harness: Harness, evidence_path: str
) -> None:
    """Positive control: the real projection path is unaffected."""
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.evidence_emission is not None
    assert result.evidence_emission.refused is False
    assert result.evidence_emission.emitted is True


# ===========================================================================
# F. EVIDENCE COERCION
# ===========================================================================


def test_project_emission_is_no_longer_an_importable_module_level_helper() -> None:
    """5F3B-Q1-PRE1-FU2A-FU1: the projection logic that used to be
    ``semantic_controller._project_emission`` -- a module-level function
    that accepted an ARBITRARY caller-supplied ``Mapping`` and minted an
    H-14-bearing ``EvidenceEmission`` from it -- is now nested inside
    ``run_semantic_task_attempt`` and cannot be imported, referenced, or
    called with fabricated data from outside that one function call.
    """
    import qualification.semantic_controller as semantic_controller_module

    assert not hasattr(semantic_controller_module, "_project_emission")
    assert not hasattr(semantic_controller_module, "_EMISSION_ISSUANCE_TOKEN")
    assert not hasattr(semantic_controller_module, "_EmissionIssuance")


def test_scrub_check_returning_malformed_findings_still_refuses_end_to_end(
    harness: Harness, evidence_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The exact-type findings/bool checks the removed ``_project_emission``
    used to perform are still exercised -- through the REAL emission path
    only, never through a directly-callable helper.
    """
    import qualification.safety as safety_module

    _iq1_correct_repair(harness)
    real_scrub_check = safety_module.qualification_scrub_check

    def _malformed_findings_scrub(payload, safety):
        if payload.get("record_kind") == "artifact emission refusal":
            return real_scrub_check(payload, safety)
        # A malformed (non-str) finding element -- the same malformed shape
        # the old `_project_emission` used to defend against directly.
        return {"scrub_checked": True, "findings": [123], "clean": False}

    monkeypatch.setattr(
        safety_module, "qualification_scrub_check", _malformed_findings_scrub
    )
    with pytest.raises(ValueError):
        harness.run(IQ1_TASK, evidence_path)


def test_result_projection_cross_check_refuses_a_malformed_refused_field(
    harness: Harness, evidence_path: str
) -> None:
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    forged_record = dict(result.qualification_record)
    forged_record["refused"] = "false"  # truthy non-bool
    with pytest.raises(ValueError):
        replace(result, qualification_record=forged_record)


def test_result_projection_cross_check_refuses_a_non_str_path(
    harness: Harness, evidence_path: str
) -> None:
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    forged_record = dict(result.qualification_record)
    forged_record["path"] = 12345
    with pytest.raises(ValueError):
        replace(result, qualification_record=forged_record)


# ===========================================================================
# G. RESULT IDENTITY SUBSTITUTION
# ===========================================================================


def test_result_refuses_relabelling_a_facts_as_candidate_b(
    harness: Harness, evidence_path: str
) -> None:
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    with pytest.raises(ValueError):
        replace(result, candidate="B")  # model_id stays A's -> mismatch


def test_result_refuses_a_candidate_model_mismatch(
    harness: Harness, evidence_path: str
) -> None:
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    with pytest.raises(ValueError):
        replace(result, model_id=CANDIDATE_MODEL_IDS["B"])


def test_result_refuses_a_task_id_task_revision_mismatch(
    harness: Harness, evidence_path: str
) -> None:
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    with pytest.raises(ValueError):
        replace(result, task_id="IQ-2")  # task_revision still IQ-1's


def test_result_refuses_a_revision_that_is_not_the_frozen_corpus_revision(
    harness: Harness, evidence_path: str
) -> None:
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    tampered = result.task_revision + "-tampered"
    assert tampered != TASKS_BY_ID["IQ-1"].task_revision
    with pytest.raises(ValueError):
        replace(result, task_revision=tampered)


# ===========================================================================
# H. FORGED INDETERMINATE ATTEMPT ARTIFACT
# ===========================================================================


def _genuine_indeterminate_attempt_kwargs(git_executable: str, tmp_path: Path) -> dict:
    """Round-trip a REAL indeterminate attempt back into ``build_attempt_record``'s
    own kwarg shape, by reading the artifact it actually wrote to disk.
    """
    h = Harness("A", git_executable)
    _indeterminate(h)
    evidence_path = str(tmp_path / "genuine_indeterminate.json")
    result = h.run(IQ1_TASK, evidence_path)
    assert result.dispatch_state is SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
    payload = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
    return dict(
        candidate=payload["candidate"],
        model_id=payload["model_id"],
        task_id=payload["task_id"],
        task_revision=payload["task_revision"],
        dispatch_evidence_code=SemanticDispatchEvidenceCode(payload["dispatch_evidence_code"]),
        gate_statuses=dict(payload["gate_statuses"]),
        observed_pi_version=payload["pi_runtime"]["observed_version"],
        compatibility_facts=dict(payload["pi_runtime"]["compatibility_facts"]),
        compatibility_gate_passed=payload["pi_runtime"]["compatibility_gate_passed"],
        route_provenance=dict(payload["route_provenance"]),
        closure=json.loads(json.dumps(payload["closure"])),
    )


def test_reconstructed_genuine_indeterminate_attempt_round_trips(
    git_executable: str, tmp_path: Path
) -> None:
    """Positive control: a genuine attempt's own facts, fed straight back into
    the builder, are accepted -- the new invariant gate does not reject
    reality.
    """
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    record = build_attempt_record(**kwargs)
    assert record["record_kind"] == ATTEMPT_RECORD_KIND


def test_attempt_builder_rejects_false_compatibility_gate_for_indeterminate(
    git_executable: str, tmp_path: Path
) -> None:
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    kwargs["compatibility_gate_passed"] = False
    with pytest.raises(AttemptRecordInvariantError):
        build_attempt_record(**kwargs)


def test_attempt_builder_rejects_missing_compatibility_facts(
    git_executable: str, tmp_path: Path
) -> None:
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    kwargs["compatibility_facts"] = {}
    with pytest.raises(AttemptRecordInvariantError):
        build_attempt_record(**kwargs)


def test_attempt_builder_rejects_one_false_compatibility_fact(
    git_executable: str, tmp_path: Path
) -> None:
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    facts = dict(kwargs["compatibility_facts"])
    a_key = next(iter(facts))
    facts[a_key] = False
    kwargs["compatibility_facts"] = facts
    with pytest.raises(AttemptRecordInvariantError):
        build_attempt_record(**kwargs)


def test_attempt_builder_rejects_a_foreign_candidate_route_provenance(
    git_executable: str, tmp_path: Path
) -> None:
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    b_route = route_descriptor_for_candidate("B")
    kwargs["route_provenance"] = {
        "model_id": b_route.model_id,
        "provider_route": b_route.provider_id,
        "backend_gateway_class": b_route.backend_gateway_class,
    }
    with pytest.raises(AttemptRecordInvariantError):
        build_attempt_record(**kwargs)


def test_attempt_builder_rejects_empty_gate_statuses(
    git_executable: str, tmp_path: Path
) -> None:
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    kwargs["gate_statuses"] = {}
    with pytest.raises(AttemptRecordInvariantError):
        build_attempt_record(**kwargs)


def test_attempt_builder_rejects_a_fabricated_reachable_post_dispatch_gate(
    git_executable: str, tmp_path: Path
) -> None:
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    gate_statuses = dict(kwargs["gate_statuses"])
    assert gate_statuses["broker_activity"] == "NOT_REACHED"
    gate_statuses["broker_activity"] = "PASSED"
    kwargs["gate_statuses"] = gate_statuses
    with pytest.raises(AttemptRecordInvariantError):
        build_attempt_record(**kwargs)


def test_attempt_builder_rejects_a_pre_prompt_gate_that_never_passed(
    git_executable: str, tmp_path: Path
) -> None:
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    gate_statuses = dict(kwargs["gate_statuses"])
    gate_statuses["get_state"] = "NOT_REACHED"
    kwargs["gate_statuses"] = gate_statuses
    with pytest.raises(AttemptRecordInvariantError):
        build_attempt_record(**kwargs)


def test_attempt_builder_rejects_a_contradictory_closure_established(
    git_executable: str, tmp_path: Path
) -> None:
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    closure = dict(kwargs["closure"])
    closure["closure_established"] = not closure["closure_established"]
    kwargs["closure"] = closure
    with pytest.raises(AttemptRecordInvariantError):
        build_attempt_record(**kwargs)


def test_attempt_builder_rejects_a_classification_leak_on_cleanup_failure(
    git_executable: str, tmp_path: Path
) -> None:
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    closure = dict(kwargs["closure"])
    cleanup = dict(closure["generated_config_cleanup"])
    cleanup["classification"] = {"run_validity": "INFRASTRUCTURE_CONTAMINATED"}
    closure["generated_config_cleanup"] = cleanup
    kwargs["closure"] = closure
    with pytest.raises(AttemptRecordInvariantError):
        build_attempt_record(**kwargs)


# ===========================================================================
# I. ATTEMPT EMISSION CONSUMPTION BOUNDARY
# ===========================================================================


def test_emit_attempt_refuses_an_arbitrary_scrub_clean_dict(tmp_path: Path) -> None:
    """A scrub checks SAFETY, never semantic truth: a dict that never passed
    through ``build_attempt_record`` at all -- however scrub-clean -- must
    not be persisted.
    """
    arbitrary = {
        "experiment": "pi_implementer_qualification",
        "record_kind": ATTEMPT_RECORD_KIND,
        "record_version": ATTEMPT_RECORD_VERSION,
        "harmless_field": True,
    }
    target = tmp_path / "should_not_exist.json"
    with pytest.raises(AttemptRecordInvariantError):
        emit_attempt_or_refuse(
            arbitrary, path=str(target), safety=ArtifactSafetyContext.none_declared()
        )
    assert not target.exists()


def test_emit_attempt_refuses_a_build_attempt_record_output_tampered_afterwards(
    git_executable: str, tmp_path: Path
) -> None:
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    record = build_attempt_record(**kwargs)
    tampered = dict(record)
    tampered["pi_runtime"] = dict(tampered["pi_runtime"])
    tampered["pi_runtime"]["compatibility_gate_passed"] = False
    target = tmp_path / "tampered.json"
    with pytest.raises(AttemptRecordInvariantError):
        emit_attempt_or_refuse(
            tampered, path=str(target), safety=ArtifactSafetyContext.none_declared()
        )
    assert not target.exists()


# ===========================================================================
# POSITIVE CONTROLS -- genuine controller-produced artifacts are unaffected
# ===========================================================================


def test_full_three_task_sweeps_still_qualify_both_candidates(
    git_executable: str, tmp_path: Path
) -> None:
    result_a, _ = _run_sweep("A", git_executable, tmp_path, correct=True)
    result_b, _ = _run_sweep("B", git_executable, tmp_path, correct=True)
    assert result_a.hard_bar_result.qualification_state is QualificationState.AUTONOMOUS_QUALIFIED
    assert result_b.hard_bar_result.qualification_state is QualificationState.AUTONOMOUS_QUALIFIED


def test_indeterminate_attempt_artifact_still_writes_after_fu2a(
    git_executable: str, tmp_path: Path
) -> None:
    h = Harness("A", git_executable)
    _indeterminate(h)
    evidence_path = str(tmp_path / "still_writes.json")
    result = h.run(IQ1_TASK, evidence_path)
    assert result.attempt_record is not None
    assert Path(evidence_path).exists()


def test_scrub_refusal_fallback_still_works_after_fu2a(
    harness: Harness, evidence_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import qualification.safety as safety_module

    _iq1_correct_repair(harness)
    real_scrub_check = safety_module.qualification_scrub_check

    def _dirty_only_for_the_candidate_record(payload, safety):
        # The bounded refusal record itself must still scrub clean -- only
        # the ORIGINAL candidate payload is made to fail here.
        if payload.get("record_kind") == "artifact emission refusal":
            return real_scrub_check(payload, safety)
        return {"scrub_checked": True, "findings": ["needle_present"], "clean": False}

    monkeypatch.setattr(
        safety_module, "qualification_scrub_check", _dirty_only_for_the_candidate_record
    )
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.evidence_emission is not None
    assert result.evidence_emission.refused is True
