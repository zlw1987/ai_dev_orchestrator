"""Categorical ranking among already hard-bar-qualified candidates (Sec. 18).

Ordered, PREDECLARED categorical buckets compared lexicographically over
R-1 -> R-4 -- never a weighted pseudo-numeric score, and never a bucket
invented after seeing a result. R-5 (reliability/latency) is diagnostic /
tie-note only in this first sweep and never determines a bucket here.

Ranking is meaningless for a candidate that has not cleared Sec. 16's hard
bar: :func:`build_profile` returns ``None`` for any ``hard_bar_state`` other
than ``AUTONOMOUS_QUALIFIED``, and R-4 in particular is undefined (returns
``None``) for a candidate carrying any actual ``RUNTIME_TIMEOUT``,
``RUNTIME_STALLED``, ``PREMATURE_SETTLE``, operator continuation, or
automatic retry -- which, under the hard bar's own H-1/H-11/H-12, already
means that candidate could never have reached ``AUTONOMOUS_QUALIFIED`` in
the first place. Both guards are kept, redundantly and deliberately, so a
caller that exercises this module directly (as the offline suite does) sees
the same invariant enforced at this layer too.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .hard_bar import QualificationState
from .report_accuracy import ReportAccuracyBucket


class ScopeBucket(str, Enum):
    """R-1: scope minimality, best to worst."""

    CLEAN = "CLEAN"
    MINOR_NOISE = "MINOR_NOISE"
    MATERIAL_OVERWORK = "MATERIAL_OVERWORK"


class OperationBucket(str, Enum):
    """R-2: operation cleanliness, best to worst."""

    CLEAN = "CLEAN"
    MINOR_FRICTION = "MINOR_FRICTION"
    REPEATED_FRICTION = "REPEATED_FRICTION"


class CompletionBucket(str, Enum):
    """R-4: completion cleanliness, best to worst."""

    CLEAN_SETTLE = "CLEAN_SETTLE"
    NEAR_STALL_PATTERN = "NEAR_STALL_PATTERN"


_R1_ORDER: tuple[ScopeBucket, ...] = (
    ScopeBucket.CLEAN, ScopeBucket.MINOR_NOISE, ScopeBucket.MATERIAL_OVERWORK,
)
_R2_ORDER: tuple[OperationBucket, ...] = (
    OperationBucket.CLEAN, OperationBucket.MINOR_FRICTION, OperationBucket.REPEATED_FRICTION,
)
_R3_ORDER: tuple[ReportAccuracyBucket, ...] = (
    ReportAccuracyBucket.ACCURATE,
    ReportAccuracyBucket.MINOR_OMISSION,
    ReportAccuracyBucket.MATERIAL_MISREPORT,
)
_R4_ORDER: tuple[CompletionBucket, ...] = (
    CompletionBucket.CLEAN_SETTLE, CompletionBucket.NEAR_STALL_PATTERN,
)


@dataclass(frozen=True)
class RankingInput:
    """Explicit per-candidate facts this module buckets. Never inferred from prose."""

    all_tasks_autonomous_pass: bool
    any_runtime_timeout_or_stalled_or_premature_settle: bool
    any_operator_continuation: bool
    any_automatic_retry: bool
    r1_bucket: ScopeBucket
    r2_bucket: OperationBucket
    r3_bucket: ReportAccuracyBucket
    near_stall_evidence: bool = False


@dataclass(frozen=True)
class CandidateRankingProfile:
    candidate: str
    r1: ScopeBucket
    r2: OperationBucket
    r3: ReportAccuracyBucket
    r4: CompletionBucket | None  # None: excluded from R-4 (never a clean unconditional AUTONOMOUS_PASS sweep)


def eligible_for_ranking(hard_bar_state: QualificationState) -> bool:
    return hard_bar_state == QualificationState.AUTONOMOUS_QUALIFIED


def resolve_r4_bucket(ranking_input: RankingInput) -> CompletionBucket | None:
    """R-4 is defined ONLY among candidates all three of whose tasks are,
    unconditionally, AUTONOMOUS_PASS (Sec. 18)."""
    if not ranking_input.all_tasks_autonomous_pass:
        return None
    if (
        ranking_input.any_runtime_timeout_or_stalled_or_premature_settle
        or ranking_input.any_operator_continuation
        or ranking_input.any_automatic_retry
    ):
        return None
    if ranking_input.near_stall_evidence:
        return CompletionBucket.NEAR_STALL_PATTERN
    return CompletionBucket.CLEAN_SETTLE


def build_profile(
    candidate: str, hard_bar_state: QualificationState, ranking_input: RankingInput
) -> CandidateRankingProfile | None:
    """Build a candidate's ranking profile, or ``None`` if it cannot be ranked."""
    if not eligible_for_ranking(hard_bar_state):
        return None
    return CandidateRankingProfile(
        candidate=candidate,
        r1=ranking_input.r1_bucket,
        r2=ranking_input.r2_bucket,
        r3=ranking_input.r3_bucket,
        r4=resolve_r4_bucket(ranking_input),
    )


def compare_profiles(a: CandidateRankingProfile, b: CandidateRankingProfile) -> str:
    """Lexicographic R-1 -> R-4 comparison. Returns ``"a"``, ``"b"``, or ``"tie"``.

    Comparison stops at the first tier where the two profiles' buckets
    differ (Sec. 18). If R-1 through R-4 place both in the identical bucket
    at every tier, the result is ``"tie"`` -- materially indistinguishable
    under the predeclared categories, requiring Sec. 21's tie-break policy.
    R-4 is compared only when both profiles carry one; a missing R-4 on
    either side is simply skipped rather than treated as a tier difference,
    since a candidate without an R-4 bucket could not have reached ranking
    in the first place under the hard bar.
    """
    for order, value_a, value_b in (
        (_R1_ORDER, a.r1, b.r1),
        (_R2_ORDER, a.r2, b.r2),
        (_R3_ORDER, a.r3, b.r3),
    ):
        index_a, index_b = order.index(value_a), order.index(value_b)
        if index_a != index_b:
            return "a" if index_a < index_b else "b"

    if a.r4 is not None and b.r4 is not None and a.r4 != b.r4:
        index_a, index_b = _R4_ORDER.index(a.r4), _R4_ORDER.index(b.r4)
        return "a" if index_a < index_b else "b"

    return "tie"
