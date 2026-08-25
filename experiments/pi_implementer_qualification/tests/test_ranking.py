"""Categorical ranking among already hard-bar-qualified candidates (Sec. 18)."""

from __future__ import annotations

from qualification.hard_bar import QualificationState
from qualification.ranking import (
    CompletionBucket,
    OperationBucket,
    RankingInput,
    ScopeBucket,
    build_profile,
    compare_profiles,
    resolve_r4_bucket,
)
from qualification.report_accuracy import ReportAccuracyBucket


def _clean_input(**overrides) -> RankingInput:
    base = dict(
        all_tasks_autonomous_pass=True,
        any_runtime_timeout_or_stalled_or_premature_settle=False,
        any_operator_continuation=False,
        any_automatic_retry=False,
        r1_bucket=ScopeBucket.CLEAN,
        r2_bucket=OperationBucket.CLEAN,
        r3_bucket=ReportAccuracyBucket.ACCURATE,
    )
    base.update(overrides)
    return RankingInput(**base)


def test_every_categorical_bucket_is_deterministically_constructible():
    for bucket in ScopeBucket:
        assert isinstance(bucket.value, str)
    for bucket in OperationBucket:
        assert isinstance(bucket.value, str)
    for bucket in ReportAccuracyBucket:
        assert isinstance(bucket.value, str)
    for bucket in CompletionBucket:
        assert isinstance(bucket.value, str)


def test_r1_outranks_r2_lexicographically():
    profile_a = build_profile(
        "A", QualificationState.AUTONOMOUS_QUALIFIED, _clean_input(r1_bucket=ScopeBucket.CLEAN)
    )
    profile_b = build_profile(
        "B",
        QualificationState.AUTONOMOUS_QUALIFIED,
        _clean_input(r1_bucket=ScopeBucket.MINOR_NOISE, r2_bucket=OperationBucket.REPEATED_FRICTION),
    )
    # A is better on R-1 even though B's R-2 is irrelevant once R-1 differs.
    assert compare_profiles(profile_a, profile_b) == "a"


def test_r2_decides_when_r1_ties():
    profile_a = build_profile(
        "A",
        QualificationState.AUTONOMOUS_QUALIFIED,
        _clean_input(r2_bucket=OperationBucket.CLEAN),
    )
    profile_b = build_profile(
        "B",
        QualificationState.AUTONOMOUS_QUALIFIED,
        _clean_input(r2_bucket=OperationBucket.MINOR_FRICTION),
    )
    assert compare_profiles(profile_a, profile_b) == "a"


def test_equal_r1_through_r4_is_a_tie_requiring_tie_break():
    profile_a = build_profile("A", QualificationState.AUTONOMOUS_QUALIFIED, _clean_input())
    profile_b = build_profile("B", QualificationState.AUTONOMOUS_QUALIFIED, _clean_input())
    assert compare_profiles(profile_a, profile_b) == "tie"


def test_failed_candidate_cannot_be_ranked():
    profile = build_profile("A", QualificationState.NOT_QUALIFIED, _clean_input())
    assert profile is None


def test_incomplete_candidate_cannot_be_ranked():
    profile = build_profile("A", QualificationState.INCOMPLETE, _clean_input())
    assert profile is None


def test_timeout_candidate_cannot_receive_r4_bucket():
    r4 = resolve_r4_bucket(
        _clean_input(any_runtime_timeout_or_stalled_or_premature_settle=True)
    )
    assert r4 is None


def test_stall_candidate_cannot_receive_r4_bucket():
    r4 = resolve_r4_bucket(
        _clean_input(all_tasks_autonomous_pass=False, any_runtime_timeout_or_stalled_or_premature_settle=True)
    )
    assert r4 is None


def test_premature_settle_candidate_cannot_receive_r4_bucket():
    r4 = resolve_r4_bucket(_clean_input(all_tasks_autonomous_pass=False))
    assert r4 is None


def test_operator_continuation_excludes_r4_bucket():
    r4 = resolve_r4_bucket(_clean_input(any_operator_continuation=True))
    assert r4 is None


def test_automatic_retry_excludes_r4_bucket():
    r4 = resolve_r4_bucket(_clean_input(any_automatic_retry=True))
    assert r4 is None


def test_clean_settle_bucket_for_a_fully_clean_all_pass_candidate():
    assert resolve_r4_bucket(_clean_input()) == CompletionBucket.CLEAN_SETTLE


def test_near_stall_pattern_bucket_requires_all_pass_plus_near_stall_evidence():
    r4 = resolve_r4_bucket(_clean_input(near_stall_evidence=True))
    assert r4 == CompletionBucket.NEAR_STALL_PATTERN


def test_r4_only_evaluated_among_unconditional_all_pass_candidates():
    # near_stall_evidence is irrelevant once any task is not an unconditional pass.
    r4 = resolve_r4_bucket(_clean_input(all_tasks_autonomous_pass=False, near_stall_evidence=True))
    assert r4 is None
