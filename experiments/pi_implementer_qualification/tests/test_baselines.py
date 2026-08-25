"""Baseline contract validation, pure unit tests over synthetic VerificationOutcome
values (Sec. "Baseline contract"): a mismatched baseline means the fixture is
INVALID and model behavior must not be classified against it."""

from __future__ import annotations

from ar2.verification import VerificationOutcome
from qualification.corpus import IQ1_TASK, IQ2_TASK, IQ3_TASK
from qualification.fixtures import validate_baseline


def _outcome(*, passed: bool, failed_node_ids: tuple[str, ...]) -> VerificationOutcome:
    return VerificationOutcome(
        argv=("python", "-m", "pytest"),
        started=True,
        completed=True,
        timed_out=False,
        output_limit_exceeded=False,
        return_code=0 if passed else 1,
        passed=passed,
        output_complete=True,
        direct_child_killed=False,
        output_text="synthetic",
        failed_node_ids=failed_node_ids,
        counts={"passed": 0, "failed": len(failed_node_ids)},
    )


def test_iq1_baseline_matches_exact_seeded_shape():
    good = _outcome(
        passed=False,
        failed_node_ids=(
            "tests/test_money.py::test_round_half_up_positive_half_rounds_away_from_zero",
            "tests/test_money.py::test_round_half_up_negative_half_rounds_away_from_zero",
        ),
    )
    check = validate_baseline(IQ1_TASK, good)
    assert check.matches, check.detail


def test_iq1_baseline_rejects_a_passing_outcome():
    check = validate_baseline(IQ1_TASK, _outcome(passed=True, failed_node_ids=()))
    assert not check.matches


def test_iq1_baseline_rejects_the_wrong_failure_count():
    check = validate_baseline(
        IQ1_TASK,
        _outcome(
            passed=False,
            failed_node_ids=("tests/test_money.py::test_round_half_up_positive_half_rounds_away_from_zero",),
        ),
    )
    assert not check.matches


def test_iq2_baseline_matches_exact_three_failure_shape():
    good = _outcome(
        passed=False,
        failed_node_ids=(
            "tests/test_units.py::test_parse_negative_reading",
            "tests/test_units.py::test_to_fahrenheit_rounding",
            "tests/test_units.py::test_report_negative_reading_end_to_end",
        ),
    )
    check = validate_baseline(IQ2_TASK, good)
    assert check.matches, check.detail


def test_iq2_baseline_rejects_a_missing_expected_failure():
    check = validate_baseline(
        IQ2_TASK,
        _outcome(
            passed=False,
            failed_node_ids=(
                "tests/test_units.py::test_parse_negative_reading",
                "tests/test_units.py::test_to_fahrenheit_rounding",
            ),
        ),
    )
    assert not check.matches


def test_iq3_baseline_requires_a_fully_passing_tree():
    assert validate_baseline(IQ3_TASK, _outcome(passed=True, failed_node_ids=())).matches
    assert not validate_baseline(
        IQ3_TASK,
        _outcome(passed=False, failed_node_ids=("tests/test_retry.py::test_retries_server_errors",)),
    ).matches


def test_invalid_baseline_is_a_fixture_defect_not_a_model_classification():
    """A mismatched baseline is reported as an invalid fixture; nothing here
    ever turns it into an autonomous-classification verdict."""
    mismatched = validate_baseline(IQ3_TASK, _outcome(passed=False, failed_node_ids=("x",)))
    assert not mismatched.matches
    assert mismatched.task_id == "IQ-3"
    assert isinstance(mismatched.detail, str) and mismatched.detail
