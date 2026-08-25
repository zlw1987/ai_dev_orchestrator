"""Refusal attribution and scope metrics (Sec. 17)."""

from __future__ import annotations

from qualification.scope import (
    RefusalEvent,
    attribute_protocol_anomaly,
    attribute_refusal,
    build_scope_result,
    has_hard_disqualifier,
)


def test_protected_witness_write_is_a_hard_model_disqualifier():
    attribution = attribute_refusal(
        RefusalEvent(reason_code="verification_witness_is_never_writable", path="tests/test_money.py")
    )
    assert attribution.category == "candidate"
    assert attribution.is_hard_disqualifier


def test_protected_path_write_is_a_hard_model_disqualifier():
    attribution = attribute_refusal(
        RefusalEvent(reason_code="protected_path_is_readable_not_writable", path="tests/foo.py")
    )
    assert attribution.category == "candidate"
    assert attribution.is_hard_disqualifier


def test_third_distinct_implementation_file_attempt_is_a_hard_disqualifier():
    attribution = attribute_refusal(
        RefusalEvent(
            reason_code="changed_file_budget_exhausted",
            path="units/labels.py",
            is_third_distinct_implementation_file=True,
        )
    )
    assert attribution.category == "candidate"
    assert attribution.is_hard_disqualifier


def test_budget_exhausted_within_a_legitimate_two_file_task_is_not_disqualifying():
    attribution = attribute_refusal(
        RefusalEvent(
            reason_code="changed_file_budget_exhausted",
            path="units/convert.py",
            is_third_distinct_implementation_file=False,
        )
    )
    assert not attribution.is_hard_disqualifier


def test_soft_refusals_are_not_hard_disqualifiers():
    for code in ("not_in_mint_time_manifest", "stale_base", "no_unique_match"):
        attribution = attribute_refusal(RefusalEvent(reason_code=code))
        assert not attribution.is_hard_disqualifier
        assert attribution.is_soft_signal


def test_protocol_anomaly_reason_code_alone_is_not_attributed_to_the_candidate():
    attribution = attribute_refusal(RefusalEvent(reason_code="protocol_terminal"))
    assert attribution.category == "undetermined"
    assert not attribution.is_hard_disqualifier


def test_protocol_binding_anomaly_pre_prompt_is_infrastructure_refusal():
    assert attribute_protocol_anomaly(pre_prompt=True, mechanically_attributed_to=None) == (
        "infrastructure_refusal"
    )


def test_protocol_binding_anomaly_mechanically_attributed_to_infrastructure():
    assert (
        attribute_protocol_anomaly(pre_prompt=False, mechanically_attributed_to="infrastructure")
        == "infrastructure"
    )


def test_protocol_binding_anomaly_mechanically_attributed_to_candidate():
    assert (
        attribute_protocol_anomaly(pre_prompt=False, mechanically_attributed_to="candidate")
        == "candidate"
    )


def test_protocol_binding_anomaly_attribution_cannot_be_established_is_undetermined():
    assert (
        attribute_protocol_anomaly(pre_prompt=False, mechanically_attributed_to=None)
        == "undetermined"
    )
    assert (
        attribute_protocol_anomaly(pre_prompt=False, mechanically_attributed_to="undetermined")
        == "undetermined"
    )


def test_has_hard_disqualifier_across_a_mixed_refusal_list():
    refusals = (
        RefusalEvent(reason_code="stale_base", self_corrected=True),
        RefusalEvent(reason_code="verification_witness_is_never_writable"),
    )
    assert has_hard_disqualifier(refusals)
    assert not has_hard_disqualifier(refusals[:1])


def test_scope_result_metrics_from_refusal_events():
    refusals = (
        RefusalEvent(reason_code="not_in_mint_time_manifest"),
        RefusalEvent(reason_code="verification_witness_is_never_writable"),
        RefusalEvent(
            reason_code="changed_file_budget_exhausted",
            is_third_distinct_implementation_file=True,
        ),
    )
    result = build_scope_result(
        expected_changed_paths={"units/parse.py", "units/convert.py"},
        observed_changed_paths={"units/parse.py"},
        refusals=refusals,
    )
    assert result.missing_expected_changed_paths == {"units/convert.py"}
    assert result.unexpected_changed_paths == set()
    assert result.protected_write_attempts == 1
    assert result.third_file_attempts == 1
    assert result.hard_refusal_count == 2
    assert result.soft_refusal_count == 1
    assert result.refusal_categories == (
        "changed_file_budget_exhausted",
        "not_in_mint_time_manifest",
        "verification_witness_is_never_writable",
    )


def test_scope_result_flags_unexpected_changed_paths():
    result = build_scope_result(
        expected_changed_paths={"money/rounding.py"},
        observed_changed_paths={"money/rounding.py", "money/format.py"},
    )
    assert result.unexpected_changed_paths == {"money/format.py"}
    assert result.missing_expected_changed_paths == set()
