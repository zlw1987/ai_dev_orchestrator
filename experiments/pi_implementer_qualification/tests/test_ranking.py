"""Categorical ranking among already hard-bar-qualified candidates (Sec. 18).

The R-2 derivation, the R-3 ``NOT_EVALUABLE`` policy, the malformed-evidence
refusals and the qualification-policy-revision boundary that 5F3B-LIVE1-C3
added are proven in ``test_live1_c3_ranking_policy.py``. This module keeps the
original Sec. 18 mechanics -- tier order, R-4's optionality, hard-bar
eligibility -- exercised against the post-C3 shapes.
"""

from __future__ import annotations

from qualification.hard_bar import QualificationState
from qualification.ranking import (
    FROZEN_PRIMARY_TASK_IDS,
    CompletionBucket,
    OperationBucket,
    R2TaskEvidence,
    RankingInput,
    ScopeBucket,
    build_profile,
    compare_profiles,
    resolve_r4_bucket,
)
from qualification.report_accuracy import ReportAccuracyBucket


def _evidence(*per_task: tuple[int, tuple[str, ...]]) -> tuple[R2TaskEvidence, ...]:
    """Primitive R-2 evidence for the three frozen tasks, in the frozen order."""
    assert len(per_task) == len(FROZEN_PRIMARY_TASK_IDS)
    return tuple(
        R2TaskEvidence(task_id=task_id, soft_refusal_count=count, refusal_categories=codes)
        for task_id, (count, codes) in zip(FROZEN_PRIMARY_TASK_IDS, per_task)
    )


#: No soft refusal anywhere -- N = 0, so R-2 derives CLEAN.
_CLEAN_R2_EVIDENCE = _evidence((0, ()), (0, ()), (0, ()))
#: N = 1, one distinct soft code -- derives MINOR_FRICTION.
_MINOR_R2_EVIDENCE = _evidence((1, ("stale_base",)), (0, ()), (0, ()))
#: N = 3, three distinct soft codes -- derives REPEATED_FRICTION (N >= 3).
_REPEATED_R2_EVIDENCE = _evidence(
    (1, ("stale_base",)), (1, ("no_unique_match",)), (1, ("over_cap_read",))
)


def _clean_input(**overrides) -> RankingInput:
    base = dict(
        all_tasks_autonomous_pass=True,
        any_runtime_timeout_or_stalled_or_premature_settle=False,
        any_operator_continuation=False,
        any_automatic_retry=False,
        r1_bucket=ScopeBucket.CLEAN,
        r2_evidence=_CLEAN_R2_EVIDENCE,
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
        _clean_input(
            r1_bucket=ScopeBucket.MINOR_NOISE, r2_evidence=_REPEATED_R2_EVIDENCE
        ),
    )
    # A is better on R-1 even though B's R-2 is irrelevant once R-1 differs.
    assert compare_profiles(profile_a, profile_b) == "a"


def test_r2_decides_when_r1_ties():
    profile_a = build_profile(
        "A",
        QualificationState.AUTONOMOUS_QUALIFIED,
        _clean_input(r2_evidence=_CLEAN_R2_EVIDENCE),
    )
    profile_b = build_profile(
        "B",
        QualificationState.AUTONOMOUS_QUALIFIED,
        _clean_input(r2_evidence=_MINOR_R2_EVIDENCE),
    )
    assert profile_a.r2 is OperationBucket.CLEAN
    assert profile_b.r2 is OperationBucket.MINOR_FRICTION
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
