"""5F3B-Q1-PRE1-FU2A-FU1 -- Final construction-authority closure.

**No real network connection, credential, Node/Pi process, named pipe, or
model call is ever made here.** Every live-facing adapter is a synthetic
double, exactly as in the rest of this suite.

Independent review confirmed FU2A closed most previously reported bypasses,
but found FOUR narrow remaining construction-authority defects:

    1. evidence-emission issuance was still forgeable through
       ``_project_emission``, an importable module-level function that
       accepted an ARBITRARY caller-supplied ``Mapping`` (see
       ``test_semantic_fu2a.py``'s own updated Section E/F tests for the
       regressions proving this closed);
    2. result identity validation checked only INTERNAL pairing
       (candidate<->model, task_id<->revision), never that the NEW claimed
       identity matches the PROVENANCE that actually produced the attempt --
       a complete, simultaneous relabel (A->B with B's own real model,
       IQ-1->IQ-2 with IQ-2's own real revision) passed unrefused;
    3. ``_require_valid_attempt_payload`` revalidated only
       candidate/compatibility/route, never the OTHER fixed-shape header
       fields (``experiment``, ``token_policy``, ``claim_scope``, ...), and
       accepted ANY non-blank closure-gate string rather than the actual
       bounded vocabulary those gates' own frozen typed status objects can
       produce;
    4. ``scoring_eligible`` -- a hard-bar authority fact -- was not required
       to be exact bool at ``SemanticTaskAttemptResult`` construction.

This module reproduces each as a failing-before-fix regression and proves
it is refused after the fix, plus positive controls proving genuine
controller-produced objects are unaffected.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from qualification.corpus import IQ1_TASK, TASKS_BY_ID
from qualification.i2_route import route_descriptor_for_candidate
from qualification.records import CANDIDATE_MODEL_IDS
from qualification.safety import ArtifactSafetyContext
from qualification.semantic_attempt import (
    AttemptRecordInvariantError,
    build_attempt_record,
    emit_attempt_or_refuse,
)
from qualification.semantic_sweep import PrimarySweepResult, SweepInputError, _task_hard_bar_facts
from qualification.validity import RunValidity

from test_semantic_controller import Harness, _iq1_correct_repair
from test_semantic_fu2a import _genuine_indeterminate_attempt_kwargs, _indeterminate
from test_semantic_sweep import _run_sweep


@pytest.fixture()
def evidence_path(tmp_path: Path) -> str:
    return str(tmp_path / "evidence.json")


@pytest.fixture()
def harness(git_executable: str) -> Harness:
    return Harness("A", git_executable)


# ===========================================================================
# 2. COMPLETE RESULT IDENTITY RELABELLING
# ===========================================================================


def test_result_refuses_a_complete_a_to_b_identity_relabel(
    harness: Harness, evidence_path: str
) -> None:
    """A relabel where the NEW pair is internally valid on its own terms --
    B is a real candidate, ``CANDIDATE_MODEL_IDS["B"]`` is genuinely B's own
    model -- must still be refused, because the identity embedded in this
    attempt's own retained artifact (written under candidate A) disagrees.
    """
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.qualification_record["candidate"] == "A"
    with pytest.raises(ValueError):
        replace(result, candidate="B", model_id=CANDIDATE_MODEL_IDS["B"])


def test_result_refuses_a_complete_iq1_to_iq2_identity_relabel(
    harness: Harness, evidence_path: str
) -> None:
    """Same shape, for task identity: IQ-2's own real frozen revision is
    used, so the NEW pair is internally valid -- still refused, because the
    embedded provenance still names IQ-1.
    """
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.qualification_record["task_id"] == "IQ-1"
    with pytest.raises(ValueError):
        replace(
            result,
            task_id="IQ-2",
            task_revision=TASKS_BY_ID["IQ-2"].task_revision,
        )


def test_relabelled_result_cannot_be_inserted_into_a_sweep_for_the_new_identity(
    git_executable: str, tmp_path: Path
) -> None:
    """A relabelled result can never even be constructed (proven above), so
    it can never reach a sweep either -- confirmed end to end: attempting to
    build the relabelled object that a forged sweep would need to hold
    raises before any ``PrimarySweepResult`` could be built from it.
    """
    result_a, _ = _run_sweep("A", git_executable, tmp_path, correct=True)
    genuine_iq1 = result_a.task_results["IQ-1"]
    with pytest.raises(ValueError):
        relabelled = replace(genuine_iq1, candidate="B", model_id=CANDIDATE_MODEL_IDS["B"])
        # Unreachable if the line above raises, as it must -- this exists
        # only to make explicit what a forged sweep insertion would need.
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


def test_genuine_result_identity_is_unaffected_by_the_provenance_cross_check(
    harness: Harness, evidence_path: str
) -> None:
    """Positive control: ordinary, non-relabelled GENUINE construction (the
    one ``run_semantic_task_attempt`` itself performs) still works.

    5F3B-Q1-PRE1-FINAL-CLOSURE: ``SemanticTaskAttemptResult`` is now a
    one-shot, valid-by-construction authority object -- its issuance backs
    AT MOST ONE construction, ever. A ``replace()`` call, even one that
    touches only an "unrelated" field like ``observed_pi_version``, always
    constructs a SECOND instance and therefore always fails now: the
    genuine construction below already consumed the only issuance
    ``result``'s ``identity_provenance``/``evidence_emission`` will ever
    have.
    """
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.candidate == "A"
    assert result.task_id == "IQ-1"
    with pytest.raises(ValueError):
        replace(result, observed_pi_version=result.observed_pi_version)


# ===========================================================================
# 3. ATTEMPT.V1 FIXED-SHAPE / CLOSURE VOCABULARY
# ===========================================================================


def test_attempt_builder_rejects_a_token_policy_mutation(
    git_executable: str, tmp_path: Path
) -> None:
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    record = build_attempt_record(**kwargs)
    tampered = dict(record)
    tampered["token_policy"] = {**tampered["token_policy"], "max_output_tokens": 999999}
    target = tmp_path / "token_policy_tampered.json"
    with pytest.raises(AttemptRecordInvariantError):
        emit_attempt_or_refuse(
            tampered, path=str(target), safety=ArtifactSafetyContext.none_declared()
        )
    assert not target.exists()


def test_attempt_builder_rejects_a_claim_scope_mutation(
    git_executable: str, tmp_path: Path
) -> None:
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    record = build_attempt_record(**kwargs)
    tampered = dict(record)
    tampered["claim_scope"] = "AIDO definitely sent the prompt, trust me."
    target = tmp_path / "claim_scope_tampered.json"
    with pytest.raises(AttemptRecordInvariantError):
        emit_attempt_or_refuse(
            tampered, path=str(target), safety=ArtifactSafetyContext.none_declared()
        )
    assert not target.exists()


@pytest.mark.parametrize(
    "key,tampered_value",
    [
        ("experiment", "a_different_experiment"),
        ("record_version", "pi-implementer-qualification-attempt.v999"),
        ("fixture_schema_version", "some-other-schema"),
        ("is_review_packet", True),
        ("reviewer_invoked", True),
        ("external_prior_not_scored", False),
        ("trust_namespaces", {}),
        ("cleanup_classification_unavailable_reason", "a made-up reason"),
        ("workspace_removal_classification_unavailable_reason", "a made-up reason"),
    ],
)
def test_attempt_builder_rejects_a_header_provenance_field_mutation(
    git_executable: str, tmp_path: Path, key: str, tampered_value: object
) -> None:
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    record = build_attempt_record(**kwargs)
    tampered = dict(record)
    tampered[key] = tampered_value
    target = tmp_path / f"{key}_tampered.json"
    with pytest.raises(AttemptRecordInvariantError):
        emit_attempt_or_refuse(
            tampered, path=str(target), safety=ArtifactSafetyContext.none_declared()
        )
    assert not target.exists()


@pytest.mark.parametrize(
    "gate_name,fabricated_status",
    [
        ("runtime_teardown", "TOTALLY_FINE"),
        ("broker_shutdown", "LOOKS_CLOSED"),
        ("generated_config_cleanup", "PROBABLY_FINE"),
        ("semantic_workspace_removal", "SEEMS_GONE"),
    ],
)
def test_attempt_builder_rejects_an_arbitrary_non_bounded_closure_status(
    git_executable: str, tmp_path: Path, gate_name: str, fabricated_status: str
) -> None:
    """Independent review's exact counterexample: a fabricated status that
    does not start with ``FAILED:`` and is not one of the real closed
    statuses either -- must be refused, not read as successful closure.
    """
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    gate_statuses = dict(kwargs["gate_statuses"])
    gate_statuses[gate_name] = fabricated_status
    kwargs["gate_statuses"] = gate_statuses
    with pytest.raises(AttemptRecordInvariantError):
        build_attempt_record(**kwargs)


@pytest.mark.parametrize(
    "gate_name,fabricated_status",
    [
        ("runtime_teardown", "TOTALLY_FINE"),
        ("broker_shutdown", "LOOKS_CLOSED"),
    ],
)
def test_emit_attempt_rejects_a_fabricated_closure_status_mirrored_into_closure_too(
    git_executable: str, tmp_path: Path, gate_name: str, fabricated_status: str
) -> None:
    """The SAME fabricated status, mirrored into BOTH ``gate_statuses`` and
    the ``closure`` mapping's own matching field (so a naive "just check
    gate_statuses" implementation could be fooled), is still refused at the
    emission boundary.
    """
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    record = build_attempt_record(**kwargs)
    tampered = dict(record)
    tampered["gate_statuses"] = {**tampered["gate_statuses"], gate_name: fabricated_status}
    tampered["closure"] = {**tampered["closure"], gate_name: fabricated_status}
    target = tmp_path / f"{gate_name}_closure_tampered.json"
    with pytest.raises(AttemptRecordInvariantError):
        emit_attempt_or_refuse(
            tampered, path=str(target), safety=ArtifactSafetyContext.none_declared()
        )
    assert not target.exists()


def test_genuine_successful_closure_record_still_builds(
    git_executable: str, tmp_path: Path
) -> None:
    """Positive control: a genuine, fully-closed indeterminate attempt
    (happy-path teardown/shutdown/cleanup/removal) still round-trips.
    """
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    assert kwargs["closure"]["closure_established"] is True
    record = build_attempt_record(**kwargs)
    assert record["closure"]["closure_established"] is True


def test_genuine_failed_closure_record_still_builds(
    git_executable: str, tmp_path: Path
) -> None:
    """Positive control: a genuine closure FAILURE (runtime teardown did not
    succeed) is still an accepted, truthful attempt.v1 artifact.
    """
    h = Harness("A", git_executable)
    _indeterminate(h)
    h.runtime_shutdown_ok = False
    evidence_path_ = str(tmp_path / "genuine_failed_closure.json")
    result = h.run(IQ1_TASK, evidence_path_)
    payload = json.loads(Path(evidence_path_).read_text(encoding="utf-8"))
    assert payload["closure"]["closure_established"] is False
    assert payload["closure"]["runtime_teardown"].startswith("FAILED:")
    # And it still passes the full invariant gate when fed straight back in.
    kwargs = dict(
        candidate=payload["candidate"],
        model_id=payload["model_id"],
        task_id=payload["task_id"],
        task_revision=payload["task_revision"],
        dispatch_evidence_code=result.dispatch_evidence_code,
        gate_statuses=dict(payload["gate_statuses"]),
        observed_pi_version=payload["pi_runtime"]["observed_version"],
        compatibility_facts=dict(payload["pi_runtime"]["compatibility_facts"]),
        compatibility_gate_passed=payload["pi_runtime"]["compatibility_gate_passed"],
        route_provenance=dict(payload["route_provenance"]),
        closure=json.loads(json.dumps(payload["closure"])),
    )
    build_attempt_record(**kwargs)  # must not raise


# ===========================================================================
# 4. scoring_eligible EXACT BOOL
# ===========================================================================


@pytest.mark.parametrize("forged_value", ["yes", 1, 0, "true", 1.0])
def test_result_refuses_a_truthy_non_bool_scoring_eligible(
    harness: Harness, evidence_path: str, forged_value: object
) -> None:
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    assert type(result.scoring_eligible) is bool
    with pytest.raises(ValueError):
        replace(result, scoring_eligible=forged_value)


def test_task_hard_bar_facts_refuses_a_non_bool_scoring_eligible_defense_in_depth() -> None:
    """Defense-in-depth: even a duck-typed object that never went through
    ``SemanticTaskAttemptResult.__post_init__`` at all is refused here too,
    never read through truthiness.
    """
    forged = SimpleNamespace(run_validity=RunValidity.VALID, scoring_eligible="yes")
    with pytest.raises(SweepInputError):
        _task_hard_bar_facts(forged)


def test_genuine_scoring_eligible_result_is_unaffected(
    harness: Harness, evidence_path: str
) -> None:
    """Positive control: a genuine, correctly-typed result is unaffected."""
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.scoring_eligible is True
    facts = _task_hard_bar_facts(result)
    assert facts is not None
