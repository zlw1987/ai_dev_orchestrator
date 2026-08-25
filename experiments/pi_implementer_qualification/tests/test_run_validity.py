"""Run validity vs. autonomous classification -- orthogonal layers (Sec. 17.3)."""

from __future__ import annotations

import pytest

from qualification.validity import (
    RunValidity,
    ValidityResult,
    hard_bar_precondition_met,
    is_scorable,
    resolve_run_validity,
)


def test_ordinary_scored_run_is_valid_and_scoring_eligible():
    result = resolve_run_validity(infrastructure_refusal=False, semantic_prompts_sent=1)
    assert result.run_validity == RunValidity.VALID
    assert result.scoring_eligible is True


def test_infrastructure_contaminated_is_unscored_not_candidate_failure():
    result = resolve_run_validity(
        infrastructure_refusal=False,
        semantic_prompts_sent=1,
        anomaly_attribution="infrastructure",
    )
    assert result.run_validity == RunValidity.INFRASTRUCTURE_CONTAMINATED
    assert result.scoring_eligible is False


def test_attribution_undetermined_is_unscored_not_candidate_failure():
    result = resolve_run_validity(
        infrastructure_refusal=False,
        semantic_prompts_sent=1,
        anomaly_attribution="undetermined",
    )
    assert result.run_validity == RunValidity.ATTRIBUTION_UNDETERMINED
    assert result.scoring_eligible is False


def test_fixture_defect_invalidation_is_unscored():
    result = resolve_run_validity(
        infrastructure_refusal=False, semantic_prompts_sent=1, fixture_defect=True
    )
    assert result.run_validity == RunValidity.INVALIDATED_BY_FIXTURE_DEFECT
    assert result.scoring_eligible is False


def test_post_prompt_contaminated_record_preserves_prompt_count_one():
    result = resolve_run_validity(
        infrastructure_refusal=False,
        semantic_prompts_sent=1,
        anomaly_attribution="infrastructure",
    )
    # The function accepted semantic_prompts_sent == 1 without raising, and
    # scoring_eligible is False -- the attempt is preserved, only its
    # eligibility is affected.
    assert result.scoring_eligible is False


def test_pre_prompt_infrastructure_refusal_has_no_run_validity_value():
    result = resolve_run_validity(infrastructure_refusal=True, semantic_prompts_sent=0)
    assert result.run_validity is None
    assert result.scoring_eligible is False


def test_pre_prompt_refusal_requires_zero_prompts():
    with pytest.raises(ValueError):
        resolve_run_validity(infrastructure_refusal=True, semantic_prompts_sent=1)


def test_post_prompt_run_requires_exactly_one_prompt():
    with pytest.raises(ValueError):
        resolve_run_validity(infrastructure_refusal=False, semantic_prompts_sent=0)


# -- FU1 A: the two validity fields must agree --------------------------------


@pytest.mark.parametrize(
    "run_validity",
    [
        RunValidity.INFRASTRUCTURE_CONTAMINATED,
        RunValidity.ATTRIBUTION_UNDETERMINED,
        RunValidity.INVALIDATED_BY_FIXTURE_DEFECT,
        None,
    ],
)
def test_a_non_valid_result_cannot_be_constructed_as_scoring_eligible(run_validity):
    with pytest.raises(ValueError):
        ValidityResult(run_validity=run_validity, scoring_eligible=True)


def test_a_valid_result_cannot_be_constructed_as_scoring_ineligible():
    with pytest.raises(ValueError):
        ValidityResult(run_validity=RunValidity.VALID, scoring_eligible=False)


def test_is_scorable_requires_both_fields():
    assert is_scorable(ValidityResult(RunValidity.VALID, True))
    assert not is_scorable(ValidityResult(RunValidity.INFRASTRUCTURE_CONTAMINATED, False))
    assert not is_scorable(ValidityResult(RunValidity.ATTRIBUTION_UNDETERMINED, False))
    assert not is_scorable(ValidityResult(RunValidity.INVALIDATED_BY_FIXTURE_DEFECT, False))
    assert not is_scorable(ValidityResult(None, False))
    assert not is_scorable(None)


def test_hard_bar_precondition_requires_all_three_tasks_valid_and_eligible():
    valid = resolve_run_validity(infrastructure_refusal=False, semantic_prompts_sent=1)
    contaminated = resolve_run_validity(
        infrastructure_refusal=False, semantic_prompts_sent=1, anomaly_attribution="infrastructure"
    )
    required = ("IQ-1", "IQ-2", "IQ-3")

    all_valid = {"IQ-1": valid, "IQ-2": valid, "IQ-3": valid}
    assert hard_bar_precondition_met(all_valid, required)

    one_missing = {"IQ-1": valid, "IQ-2": valid}
    assert not hard_bar_precondition_met(one_missing, required)

    one_contaminated = {"IQ-1": valid, "IQ-2": contaminated, "IQ-3": valid}
    assert not hard_bar_precondition_met(one_contaminated, required)
