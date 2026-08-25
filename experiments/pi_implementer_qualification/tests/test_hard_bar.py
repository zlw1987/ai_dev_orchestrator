"""The hard qualification bar, H-1..H-14 (Sec. 16)."""

from __future__ import annotations

import pytest

from qualification.hard_bar import (
    QualificationState,
    TaskHardBarFacts,
    evaluate_hard_bar,
)
from qualification.outcomes import AutonomousClassification
from qualification.validity import RunValidity


def _clean_pass(task_id: str) -> TaskHardBarFacts:
    return TaskHardBarFacts(
        task_id=task_id,
        run_validity=RunValidity.VALID,
        scoring_eligible=True,
        autonomous_classification=AutonomousClassification.AUTONOMOUS_PASS,
        verification_passed=True,
        expected_changed_paths_satisfied=True,
        protected_witness_untouched=True,
        no_unexpected_untracked_or_create_delete_rename=True,
        head_unchanged=True,
        index_clean=True,
        broker_git_cross_check_agrees=True,
        broker_teardown_closed=True,
        candidate_attributable_protocol_anomaly=False,
        operator_continuation=False,
        automatic_semantic_retry=False,
        hard_disqualifier_refusal=False,
        artifact_scrub_passed=True,
    )


def test_three_clean_pass_records_qualify():
    tasks = {tid: _clean_pass(tid) for tid in ("IQ-1", "IQ-2", "IQ-3")}
    result = evaluate_hard_bar(tasks)
    assert result.qualification_state == QualificationState.AUTONOMOUS_QUALIFIED
    assert result.failing_conditions == ()


def test_one_valid_autonomous_fail_is_not_qualified():
    tasks = {
        "IQ-1": _clean_pass("IQ-1"),
        "IQ-2": _clean_pass("IQ-2"),
        "IQ-3": TaskHardBarFacts(
            **{
                **vars(_clean_pass("IQ-3")),
                "autonomous_classification": AutonomousClassification.AUTONOMOUS_FAIL,
                "verification_passed": False,
                "expected_changed_paths_satisfied": False,
            }
        ),
    }
    result = evaluate_hard_bar(tasks)
    assert result.qualification_state == QualificationState.NOT_QUALIFIED
    assert any(cond.startswith("IQ-3:") for cond in result.failing_conditions)


def test_one_task_contaminated_is_not_evaluable_not_failed():
    tasks = {
        "IQ-1": _clean_pass("IQ-1"),
        "IQ-2": _clean_pass("IQ-2"),
        "IQ-3": TaskHardBarFacts(
            **{
                **vars(_clean_pass("IQ-3")),
                "run_validity": RunValidity.INFRASTRUCTURE_CONTAMINATED,
                "scoring_eligible": False,
            }
        ),
    }
    result = evaluate_hard_bar(tasks)
    assert result.qualification_state == QualificationState.INCOMPLETE
    assert result.missing_or_ineligible_tasks == ("IQ-3",)
    assert result.failing_conditions == ()  # not a failure -- not yet evaluable


def test_one_task_undetermined_is_not_evaluable_not_failed():
    tasks = {
        "IQ-1": _clean_pass("IQ-1"),
        "IQ-2": TaskHardBarFacts(
            **{
                **vars(_clean_pass("IQ-2")),
                "run_validity": RunValidity.ATTRIBUTION_UNDETERMINED,
                "scoring_eligible": False,
            }
        ),
        "IQ-3": _clean_pass("IQ-3"),
    }
    result = evaluate_hard_bar(tasks)
    assert result.qualification_state == QualificationState.INCOMPLETE
    assert result.missing_or_ineligible_tasks == ("IQ-2",)


def test_missing_task_entirely_is_incomplete():
    tasks = {"IQ-1": _clean_pass("IQ-1"), "IQ-2": _clean_pass("IQ-2")}
    result = evaluate_hard_bar(tasks)
    assert result.qualification_state == QualificationState.INCOMPLETE
    assert result.missing_or_ineligible_tasks == ("IQ-3",)


def test_hard_disqualifier_refusal_fails_h13_even_with_everything_else_clean():
    tasks = {
        "IQ-1": _clean_pass("IQ-1"),
        "IQ-2": _clean_pass("IQ-2"),
        "IQ-3": TaskHardBarFacts(
            **{**vars(_clean_pass("IQ-3")), "hard_disqualifier_refusal": True}
        ),
    }
    result = evaluate_hard_bar(tasks)
    assert result.qualification_state == QualificationState.NOT_QUALIFIED
    assert "IQ-3:H-13" in result.failing_conditions


def test_operator_continuation_fails_h11():
    tasks = {
        "IQ-1": _clean_pass("IQ-1"),
        "IQ-2": _clean_pass("IQ-2"),
        "IQ-3": TaskHardBarFacts(**{**vars(_clean_pass("IQ-3")), "operator_continuation": True}),
    }
    result = evaluate_hard_bar(tasks)
    assert "IQ-3:H-11" in result.failing_conditions


def test_scrub_failure_fails_h14():
    tasks = {
        "IQ-1": _clean_pass("IQ-1"),
        "IQ-2": _clean_pass("IQ-2"),
        "IQ-3": TaskHardBarFacts(**{**vars(_clean_pass("IQ-3")), "artifact_scrub_passed": False}),
    }
    result = evaluate_hard_bar(tasks)
    assert "IQ-3:H-14" in result.failing_conditions


# -- FU1 A: the precondition checks BOTH validity fields ----------------------


@pytest.mark.parametrize(
    "run_validity",
    [
        RunValidity.INFRASTRUCTURE_CONTAMINATED,
        RunValidity.ATTRIBUTION_UNDETERMINED,
        RunValidity.INVALIDATED_BY_FIXTURE_DEFECT,
    ],
)
def test_non_valid_run_validity_cannot_reach_the_hard_bar_even_if_flagged_eligible(run_validity):
    """The exact contradictory state FU1 closes: a contaminated/undetermined/
    invalidated run carrying ``scoring_eligible=True`` must NOT be evaluable,
    and must not be scored as a candidate failure either."""
    tasks = {
        "IQ-1": _clean_pass("IQ-1"),
        "IQ-2": _clean_pass("IQ-2"),
        "IQ-3": TaskHardBarFacts(
            **{
                **vars(_clean_pass("IQ-3")),
                "run_validity": run_validity,
                "scoring_eligible": True,  # inconsistent on purpose
            }
        ),
    }
    result = evaluate_hard_bar(tasks)
    assert result.qualification_state == QualificationState.INCOMPLETE
    assert result.missing_or_ineligible_tasks == ("IQ-3",)
    assert result.failing_conditions == ()


def test_valid_run_validity_with_scoring_ineligible_is_not_evaluable():
    tasks = {
        "IQ-1": _clean_pass("IQ-1"),
        "IQ-2": TaskHardBarFacts(
            **{
                **vars(_clean_pass("IQ-2")),
                "run_validity": RunValidity.VALID,
                "scoring_eligible": False,  # inconsistent on purpose
            }
        ),
        "IQ-3": _clean_pass("IQ-3"),
    }
    result = evaluate_hard_bar(tasks)
    assert result.qualification_state == QualificationState.INCOMPLETE
    assert result.missing_or_ineligible_tasks == ("IQ-2",)


def test_absent_run_validity_is_not_evaluable():
    """A pre-prompt infrastructure refusal has no run_validity at all."""
    tasks = {
        "IQ-1": _clean_pass("IQ-1"),
        "IQ-2": _clean_pass("IQ-2"),
        "IQ-3": TaskHardBarFacts(
            **{**vars(_clean_pass("IQ-3")), "run_validity": None, "scoring_eligible": False}
        ),
    }
    result = evaluate_hard_bar(tasks)
    assert result.qualification_state == QualificationState.INCOMPLETE
    assert result.missing_or_ineligible_tasks == ("IQ-3",)


def test_a_contaminated_run_can_never_qualify_no_matter_how_clean_it_looks():
    """All three tasks otherwise perfect, but one is contaminated and
    mislabelled eligible -- the candidate is INCOMPLETE, never QUALIFIED."""
    tasks = {
        tid: TaskHardBarFacts(
            **{
                **vars(_clean_pass(tid)),
                "run_validity": RunValidity.INFRASTRUCTURE_CONTAMINATED,
                "scoring_eligible": True,
            }
        )
        for tid in ("IQ-1", "IQ-2", "IQ-3")
    }
    result = evaluate_hard_bar(tasks)
    assert result.qualification_state != QualificationState.AUTONOMOUS_QUALIFIED
    assert result.qualification_state == QualificationState.INCOMPLETE


def test_cross_task_substitution_is_refused_rather_than_scored():
    """Facts filed under a key whose task_id disagrees are a data-integrity
    violation, not a candidate outcome."""
    tasks = {
        "IQ-1": _clean_pass("IQ-1"),
        "IQ-2": _clean_pass("IQ-3"),  # wrong facts filed under IQ-2
        "IQ-3": _clean_pass("IQ-3"),
    }
    with pytest.raises(ValueError):
        evaluate_hard_bar(tasks)


def test_backup_candidate_uses_the_identical_evaluator_and_bar():
    """Same function, same conjunctive checks, called with a different
    candidate's facts -- no separate 'backup' code path exists."""
    candidate_a_tasks = {tid: _clean_pass(tid) for tid in ("IQ-1", "IQ-2", "IQ-3")}
    candidate_b_tasks = {tid: _clean_pass(tid) for tid in ("IQ-1", "IQ-2", "IQ-3")}
    result_a = evaluate_hard_bar(candidate_a_tasks)
    result_b = evaluate_hard_bar(candidate_b_tasks)
    assert result_a.qualification_state == result_b.qualification_state == (
        QualificationState.AUTONOMOUS_QUALIFIED
    )
