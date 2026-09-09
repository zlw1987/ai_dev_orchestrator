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

5F3B-LIVE1-C3 -- what this module owns, and what it deliberately does not
=========================================================================

C3 owns **POLICY MECHANICS ONLY** (LIVE1 design Sec. 9.4.8 C3-R2-1c):

    the ONE R-2 resolver and its frozen arithmetic   (Sec. 9.4.5 / 9.4.6)
    the malformed-R-2-evidence refusals              (C3-R2-4)
    R-3's NOT_EVALUABLE representation and its symmetric rule (Sec. 10.6.2a)
    the qualification-policy-revision comparison refusal       (Sec. 10A.3)
    the categorical R-1 -> R-4 comparison mechanics

**C3's in-memory profiles are NOT a durable candidate-selection authority,
and this module emits nothing durable.** That is not modesty, it is a source
fact: :class:`~qualification.semantic_sweep.PrimarySweepResult` is a PUBLIC,
CONSTRUCTIBLE frozen dataclass whose ``__post_init__`` consumes no issuance
token. It proves internal CONSISTENCY (exact entry types, candidate/model
binding, the frozen task prefix, a re-derived hard bar, an immutable copy) --
it does **not** prove that the aggregate was issued by ``run_primary_sweep``.
A caller holding three genuine, issuance-backed
:class:`~qualification.semantic_controller.SemanticTaskAttemptResult` objects
can compose a new, internally consistent aggregate. Each task's own
``scope_result`` cannot be swapped, which is enough to make the policy
mechanics here well-defined; it is not enough to make a
:class:`CandidateRankingProfile` a selection authority, and nothing in this
module says it is. Constructing a :class:`CandidateRankingProfile` directly,
rather than through :func:`build_profile`, bypasses the R-2 derivation
entirely and produces a record that is not authoritative about anything.

**M4 owns all authoritative ranking-input derivation and selection**
(C3-R2-1b / C3-R2-1c): loading the durable per-task artifacts,
schema-validating them, verifying immutable artifact identities and content
digests, verifying same candidate / task set / model / route / policy
revision, deriving the authoritative R-1, R-2, R-3-policy-state and R-4
inputs, invoking these policy mechanics, selecting a candidate, and issuing
the candidate-level decision artifact. **None of that is implemented here.**
This module reads no file, opens no path, accepts no path parameter, verifies
no digest, and writes nothing: it is pure, in-memory policy math.

Adjacent source fact, stated rather than glossed: :class:`RankingInput` still
accepts caller-authored ``r1_bucket`` and the R-4-related booleans. C3
removing the caller-authored R-2 bucket and centralizing that math is
correct, but it does **not** make the remaining tiers authoritative. Deriving
R-1 and R-4 authoritatively is M4's work, at the same boundary and by the
same rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from . import QUALIFICATION_POLICY_REVISION
from .corpus import REQUIRED_TASKS
from .hard_bar import QualificationState
from .refusal_projection import PROJECTED_REFUSAL_VOCABULARY
from .report_accuracy import ReportAccuracyBucket
from .scope import SOFT_REASON_CODES, ScopeResult
from .semantic_controller import SemanticTaskAttemptResult
from .semantic_sweep import PrimarySweepResult
from .validity import RunValidity


class RankingError(ValueError):
    """Base class for every loud, typed refusal out of the ranking boundary."""


class RankingInputError(RankingError):
    """Ranking evidence is malformed, incoherent, or forbidden by policy.

    Refused, never coerced, never clamped, never defaulted to a bucket, and
    never read through truthiness.
    """


class RankingComparabilityError(RankingError):
    """Two profiles may not be compared at all.

    Raised for a qualification-policy-revision mismatch (Sec. 10A.3 C3-PR-3)
    and for a one-sided R-3 (Sec. 10.6.2a). Both mean the two candidates were
    evaluated under different policy states, which is exactly the unfairness
    the whole pre-declaration discipline exists to prevent -- so it is a loud
    refusal, never a skipped tier, never "prefer the newer", never a warning.
    """


#: How much authority a :class:`CandidateRankingProfile` carries, stated
#: mechanically so a reader (and a test) never has to infer it from prose.
#: See this module's docstring: C3 is policy mechanics; M4 is authority.
PROFILE_AUTHORITY_SCOPE: str = (
    "in-memory qualification-policy mechanics only; NOT durable "
    "candidate-selection authority, and never an emitted artifact"
)

#: R-3's evaluability for THIS qualification-policy revision (Sec. 10.6.2).
#:
#: ``False``: the frozen corpus and harness expose **no bounded, structured,
#: machine-readable final-report claim channel**, and general NLP/prose
#: parsing is forbidden -- so no truthful :class:`ReportAccuracyBucket` can be
#: produced for either candidate. R-3 therefore ranks NEITHER candidate.
#:
#: Symmetry is structural, not conventional: while this is ``False`` every
#: profile :func:`build_profile` can produce carries ``r3=None``, so the
#: asymmetric branch of :func:`compare_profiles` is unreachable through the
#: supported construction path rather than merely unexercised. It is still
#: implemented and still tested, as defence in depth for the future revision
#: in which this becomes ``True``.
#:
#: A caller that supplies an R-3 bucket while this is ``False`` is REFUSED,
#: never silently ignored -- a silently dropped input would be the same class
#: of defect as a silent skip.
#:
#: **No member is added to**
#: :class:`~qualification.report_accuracy.ReportAccuracyBucket`. That enum is
#: the ordered output domain of the mechanical comparator
#: :func:`~qualification.report_accuracy.bucket_report_accuracy`, which is
#: unchanged; not-evaluability is a property of the ranking INPUT, never of
#: the comparator's output.
R3_EVALUABLE: bool = False

#: The three frozen primary IQ task ids, in the frozen corpus order. R-2's
#: evidence must be exactly these three, once each, in this order -- a
#: missing, extra, duplicated or reordered task set is refused.
FROZEN_PRIMARY_TASK_IDS: tuple[str, ...] = tuple(task.task_id for task in REQUIRED_TASKS)


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


# ===========================================================================
# Shared, non-coercing type guards
# ===========================================================================


def _require_exact_bool(name: str, value: object) -> None:
    """``type(value) is bool`` or refuse. Truthiness is never read.

    ``bool`` is a subclass of ``int`` and the string ``"false"`` is truthy; a
    ranking boundary that read either through ``bool(...)`` would silently
    invent a fact. This refuses instead.
    """
    if type(value) is not bool:
        raise RankingInputError(
            f"{name} must be exactly a bool -- a truthy non-bool is refused, "
            f"never coerced; got {type(value).__name__}"
        )


def _require_exact_type(name: str, value: object, expected: type) -> None:
    """Exact type, never ``isinstance``.

    ``ScopeBucket`` / ``OperationBucket`` / ``ReportAccuracyBucket`` /
    ``CompletionBucket`` are all ``str`` enums, so ``"CLEAN" ==
    ScopeBucket.CLEAN`` is ``True`` and a plain ``str`` would be found by
    ``tuple.index`` in the frozen tier orders below. A ``str`` subclass with a
    hostile ``__eq__`` is the same attack in a different shape. Exact type is
    the only check that refuses both.
    """
    if type(value) is not expected:
        raise RankingInputError(
            f"{name} must be exactly a {expected.__name__} -- a subclass or a "
            f"lookalike value is refused; got {type(value).__name__}"
        )


def _require_declared_policy_revision(name: str, value: object) -> None:
    """The value must be EXACTLY the one declared qualification-policy revision.

    Exact ``str`` type first, so a ``str`` subclass overriding ``__eq__``
    cannot satisfy the equality test that follows; then exact equality with
    the single constant :mod:`qualification` declares (Sec. 10A.3 C3-PR-1).
    A mismatch REFUSES -- it is never repaired, never normalized to the
    current revision, and never accepted as "close enough".
    """
    _require_exact_type(name, value, str)
    if value != QUALIFICATION_POLICY_REVISION:
        raise RankingInputError(
            f"{name} is not the declared qualification-policy revision "
            f"{QUALIFICATION_POLICY_REVISION!r}; a caller may not choose the "
            "revision a ranking object is evaluated under"
        )


# ===========================================================================
# R-2 -- primitive evidence, and the ONE derivation of the frozen arithmetic
# ===========================================================================


def _validate_r2_task_evidence_invariants(entry: "R2TaskEvidence") -> None:
    """The complete ``R2TaskEvidence`` invariant contract, checked against
    the entry's CURRENT field values.

    **ONE implementation, called from two places**: :meth:`R2TaskEvidence.
    __post_init__` (construction time) and :func:`resolve_r2_bucket` (the R-2
    arithmetic CONSUMPTION boundary). ``R2TaskEvidence`` is a frozen
    dataclass, but "frozen" only refuses attribute assignment through the
    normal ``self.x = ...`` path -- ``object.__setattr__`` can still mutate a
    field afterward without re-running ``__post_init__``. A construction-time
    check alone is therefore not a mechanical guarantee at the point the
    arithmetic actually consumes an entry; this function is called again,
    immediately before that consumption, against whatever the entry's CURRENT
    values are (Blocker 1, 5F3B-LIVE1-C3-FU1). Never copy this body into a
    second, independently-drifting validator.
    """
    _require_exact_type("R2TaskEvidence.task_id", entry.task_id, str)
    if entry.task_id not in FROZEN_PRIMARY_TASK_IDS:
        raise RankingInputError(
            f"R2TaskEvidence.task_id {entry.task_id!r} is not one of the frozen "
            f"primary tasks {list(FROZEN_PRIMARY_TASK_IDS)}"
        )
    # `bool` is a subclass of `int`, so `isinstance(True, int)` is True and
    # `True + True == 2`: a bool count would silently sum. Exact type only,
    # and never `int(value)`.
    if type(entry.soft_refusal_count) is not int:
        raise RankingInputError(
            "R2TaskEvidence.soft_refusal_count must be exactly an int -- a bool, "
            "a float or a numeric string is refused, never converted; got "
            f"{type(entry.soft_refusal_count).__name__}"
        )
    if entry.soft_refusal_count < 0:
        raise RankingInputError(
            "R2TaskEvidence.soft_refusal_count must be >= 0; got "
            f"{entry.soft_refusal_count}"
        )
    # A list / set / mapping would still be iterable and would still
    # produce a plausible-looking S_t, while being mutable behind this
    # frozen object's back. Exact tuple only.
    _require_exact_type(
        "R2TaskEvidence.refusal_categories", entry.refusal_categories, tuple
    )
    seen: set[str] = set()
    for index, code in enumerate(entry.refusal_categories):
        _require_exact_type(f"R2TaskEvidence.refusal_categories[{index}]", code, str)
        # C2 (5F3B-LIVE1-C2) owns the closed projected vocabulary and is
        # frozen. This module CONSUMES it; it never re-derives, renames,
        # extends or re-parses it, never reads a raw broker
        # `internal_reason`, and candidate-controlled free text can never
        # reach an R-2 category.
        if code not in PROJECTED_REFUSAL_VOCABULARY:
            raise RankingInputError(
                f"R2TaskEvidence.refusal_categories[{index}] = {code!r} is outside "
                "C2's closed projected refusal vocabulary"
            )
        if code in seen:
            raise RankingInputError(
                "R2TaskEvidence.refusal_categories must be DEDUPLICATED, exactly "
                "as scope.build_scope_result produces it; the repeated entry "
                f"{code!r} is incoherent evidence, refused rather than collapsed"
            )
        seen.add(code)
    soft_present = seen & SOFT_REASON_CODES
    if entry.soft_refusal_count > 0 and not soft_present:
        # THE OTHER HALF OF THE SAME INTERNAL IMPOSSIBILITY. Every counted
        # soft refusal is an event whose reason code is in
        # `SOFT_REASON_CODES`, and `build_scope_result` puts EVERY event's
        # code into `refusal_categories` -- so `n_t >= 1` forces
        # `|S_t| >= 1`. Sec. 9.4.6's identity `N = SUM over x in U of c(x)`
        # says the same thing: a positive N with an empty U is not a
        # value to bucket, it is incoherent evidence.
        raise RankingInputError(
            f"R2TaskEvidence for task {entry.task_id!r} is incoherent: "
            f"soft_refusal_count = {entry.soft_refusal_count} while it reports no "
            "projected soft refusal category at all; every counted soft refusal "
            "contributes its own code, so n_t >= 1 forces |S_t| >= 1"
        )
    if entry.soft_refusal_count < len(soft_present):
        # INTERNAL IMPOSSIBILITY (C3-R2-4). Every projected soft code
        # present in S_t must have occurred at least once in task t, so
        # n_t >= |S_t| always holds for genuine evidence -- and Sec.
        # 9.4.6's proof that `R <=> N > |U|` depends on it. Evidence
        # violating it is not an unknown value to normalize: it is
        # incoherent. Refused, never clamped, and never allowed to fall
        # through to a default bucket.
        raise RankingInputError(
            f"R2TaskEvidence for task {entry.task_id!r} is incoherent: "
            f"soft_refusal_count = {entry.soft_refusal_count} is fewer than the "
            f"{len(soft_present)} distinct projected soft code(s) it reports "
            f"({sorted(soft_present)}); every code present occurred at least "
            "once, so n_t >= |S_t| always holds"
        )


@dataclass(frozen=True)
class R2TaskEvidence:
    """ONE frozen primary task's primitive projected-soft-refusal evidence.

    Exactly the two fields the retained ``pi-implementer-qualification``
    record already carries for that task (LIVE1 design Sec. 9.4.6's source
    chain) and that the in-process
    :class:`~qualification.scope.ScopeResult` already holds:

    ``soft_refusal_count``
        ``n_t`` -- how many projected SOFT refusals occurred in task ``t``.
    ``refusal_categories``
        that task's DEDUPLICATED projected reason codes, exactly as
        :func:`~qualification.scope.build_scope_result` produces them. It
        carries every category, not only soft ones; ``S_t`` is the
        intersection with :data:`~qualification.scope.SOFT_REASON_CODES`.

    This is EVIDENCE, not authority. Constructing one by hand proves nothing
    about a candidate; see this module's docstring for the C3/M4 split.
    """

    task_id: str
    soft_refusal_count: int
    refusal_categories: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_r2_task_evidence_invariants(self)


def _require_frozen_task_evidence(name: str, evidence: object) -> tuple[R2TaskEvidence, ...]:
    """The evidence must be exactly the three frozen tasks, once each, in order."""
    _require_exact_type(name, evidence, tuple)
    entries: tuple[R2TaskEvidence, ...] = evidence  # type: ignore[assignment]
    for index, entry in enumerate(entries):
        _require_exact_type(f"{name}[{index}]", entry, R2TaskEvidence)
    observed_ids = tuple(entry.task_id for entry in entries)
    if observed_ids != FROZEN_PRIMARY_TASK_IDS:
        raise RankingInputError(
            f"{name} must carry exactly the three frozen primary tasks "
            f"{list(FROZEN_PRIMARY_TASK_IDS)}, once each, in that order -- a "
            "missing, extra, duplicated or reordered task set is refused; got "
            f"{list(observed_ids)}"
        )
    return entries


def resolve_r2_bucket(evidence: tuple[R2TaskEvidence, ...]) -> OperationBucket:
    """R-2's bucket, derived by AIDO. **The ONE implementation of this arithmetic.**

    Nothing else in this repository recomputes ``N``, ``U``, ``R`` or the
    bucket boundaries a second way, and no caller may supply the answer.

    The frozen definition for this qualification-policy revision (LIVE1
    design Sec. 9.4.5, proven derivable from retained evidence in Sec.
    9.4.6), over the candidate's three frozen primary tasks::

        n_t = that task's projected soft_refusal_count
        S_t = refusal_categories(t) INTERSECT scope.SOFT_REASON_CODES
        N   = n_1 + n_2 + n_3
        U   = S_1 UNION S_2 UNION S_3
        R   = (N > |U|)                 -- "some projected soft code recurs"

        CLEAN              iff N == 0
        MINOR_FRICTION     iff N in {1, 2} AND R is False
        REPEATED_FRICTION  iff R is True   OR  N >= 3

    ``N`` and ``R`` are CANDIDATE-LEVEL, not per task: the same soft code
    appearing once in each of two different IQ tasks therefore RECURS.

    **This is a policy definition, not a recovered observation of
    self-correction.** The frozen wording it replaces -- *"each visibly
    self-corrected on the candidate's very next relevant operation"* --
    requires the ordered, interleaved, path-carrying operation sequence that
    the frozen broker demonstrably does not retain. Non-recurrence is a
    STRICTLY WEAKER PROXY for self-correction, and this docstring says so in
    exactly those terms rather than implying the original criterion was
    measured. The original sequence criterion is not reintroduced.
    """
    entries = _require_frozen_task_evidence("R-2 evidence", evidence)
    # Blocker 1 (5F3B-LIVE1-C3-FU1): `_require_frozen_task_evidence` above
    # only proves the outer tuple shape, exact entry type and task-id order --
    # it does not re-check each entry's OWN invariant contract. A frozen
    # dataclass's `__post_init__` ran once, at construction; `object.
    # __setattr__` can mutate a field afterward without re-running it. This is
    # the R-2 arithmetic's actual consumption boundary, so every entry is
    # revalidated against its CURRENT values here, immediately before any
    # arithmetic reads it.
    for entry in entries:
        _validate_r2_task_evidence_invariants(entry)

    total_soft_refusals = 0
    distinct_soft_codes: set[str] = set()
    for entry in entries:
        total_soft_refusals += entry.soft_refusal_count
        distinct_soft_codes |= set(entry.refusal_categories) & SOFT_REASON_CODES

    # Sec. 9.4.6: N = SUM over x in U of c(x), and c(x) >= 1 for every x in U,
    # so N >= |U| always -- with equality exactly when no code occurs twice.
    # Each task's own `n_t >= |S_t|` guard is what makes this hold at the
    # candidate level too, so this is an internal-consistency assertion rather
    # than an input check.
    if total_soft_refusals < len(distinct_soft_codes):  # pragma: no cover - unreachable
        raise RankingInputError(
            "R-2 evidence is incoherent at candidate level: N = "
            f"{total_soft_refusals} is fewer than |U| = {len(distinct_soft_codes)}"
        )
    some_soft_code_recurs = total_soft_refusals > len(distinct_soft_codes)

    if total_soft_refusals == 0:
        # N == 0 forces |U| == 0 and therefore R False, so this arm can never
        # collide with REPEATED_FRICTION.
        return OperationBucket.CLEAN
    if total_soft_refusals in (1, 2) and not some_soft_code_recurs:
        return OperationBucket.MINOR_FRICTION
    # R is True, or N >= 3. The three arms partition every (N, R) pair.
    return OperationBucket.REPEATED_FRICTION


def _r2_evidence_for_task_result(
    task_id: str, result: SemanticTaskAttemptResult
) -> R2TaskEvidence:
    """Read ONE task attempt's own ``scope_result`` as primitive R-2 evidence.

    Every value is passed through VERBATIM. Nothing here converts a list to a
    tuple, an ``int``-like to an ``int``, or a missing fact to a default:
    :class:`R2TaskEvidence` then re-validates all of it and refuses whatever
    is malformed.
    """
    _require_exact_type(f"task_results[{task_id!r}]", result, SemanticTaskAttemptResult)
    # 5F3B-LIVE1-C3-FU2: every identity field this function (``task_id``) or
    # its caller's candidate/model consistency check (``candidate``,
    # ``model_id``) consumes off `result` must be an ordinary `str` BEFORE it
    # participates in any `==` or hashing below. Each is a `str`-typed
    # dataclass field, but a `str` subclass with a forged `__eq__`/`__hash__`
    # can still satisfy `result.task_id == task_id`, or hash/compare into the
    # candidate/model identity set the caller builds from this same result,
    # while its own underlying text is something else entirely -- Python
    # calls the RIGHT operand's override first whenever it is a subclass
    # overriding comparison, so the direction of the `==` never protects
    # against this. Exact type first defeats it regardless of direction, and
    # regardless of whether the forged text happens to already equal the
    # genuine value.
    _require_exact_type(f"task_results[{task_id!r}].task_id", result.task_id, str)
    _require_exact_type(f"task_results[{task_id!r}].candidate", result.candidate, str)
    _require_exact_type(f"task_results[{task_id!r}].model_id", result.model_id, str)
    if result.task_id != task_id:
        raise RankingInputError(
            f"task_results[{task_id!r}] carries a result for task "
            f"{result.task_id!r}; a cross-task substitution is refused"
        )
    # A candidate only reaches ranking at AUTONOMOUS_QUALIFIED, which requires
    # all three tasks VALID and scoring-eligible. Anything else carries no R-2
    # ranking evidence at all, and is refused rather than skipped or defaulted.
    _require_exact_bool(
        f"task_results[{task_id!r}].scoring_eligible", result.scoring_eligible
    )
    if result.run_validity is not RunValidity.VALID or not result.scoring_eligible:
        raise RankingInputError(
            f"task_results[{task_id!r}] is not a VALID, scoring-eligible run "
            f"(run_validity={result.run_validity!r}, "
            f"scoring_eligible={result.scoring_eligible!r}); it carries no R-2 "
            "ranking evidence"
        )
    scope_result = result.scope_result
    if scope_result is None:
        raise RankingInputError(
            f"task_results[{task_id!r}] is presented as VALID and scoring-eligible "
            "but carries no scope_result -- R-2 evidence is absent, which is "
            "refused, never read as zero soft refusals"
        )
    _require_exact_type(
        f"task_results[{task_id!r}].scope_result", scope_result, ScopeResult
    )
    return R2TaskEvidence(
        task_id=task_id,
        soft_refusal_count=scope_result.soft_refusal_count,
        refusal_categories=scope_result.refusal_categories,
    )


def r2_evidence_from_task_results(
    task_results: Mapping[str, SemanticTaskAttemptResult],
) -> tuple[R2TaskEvidence, ...]:
    """Primitive R-2 evidence read out of one candidate's three task results.

    Each :class:`~qualification.semantic_controller.SemanticTaskAttemptResult`
    is issuance-backed and one-shot, so its own ``scope_result`` cannot be
    swapped. That is what makes this reading well-defined. It is **not** an
    attestation that this SET of three results is one genuine sweep -- see
    this module's docstring, and :func:`r2_evidence_from_sweep`.
    """
    if not isinstance(task_results, Mapping):
        raise RankingInputError("task_results must be a Mapping of task id -> result")
    # ONE bounded concrete representation, taken in a SINGLE pass, before any
    # semantic check runs. `task_results` is only required to be a Mapping:
    # `__contains__`, `__iter__`, `.keys()`, `.items()` and `__getitem__` are
    # separate protocol methods a caller-supplied Mapping could implement
    # inconsistently with one another. The previous shape validated the
    # frozen task set with `__contains__` / `__iter__` and only THEN read
    # values with `__getitem__` -- two different accessor calls that a
    # hostile Mapping could answer two different ways, letting a hidden extra
    # task evade the "exactly the three frozen tasks" check even though the
    # extraction below would have seen it. Here, key discovery (`__iter__`,
    # via the `for` loop) and value extraction (`__getitem__`) happen
    # together, in the same pass, into one plain `dict`; `.keys()`,
    # `.items()` and `__contains__` on the caller's Mapping are never called
    # at all. Every check from here on -- the frozen task-set check, the
    # extraction, the task/result identity check and the candidate/model
    # consistency check -- reads ONLY this one `snapshot`, never
    # `task_results` again (Blocker 3, 5F3B-LIVE1-C3-FU1).
    # 5F3B-LIVE1-C3-FU2: every yielded `key` is gated in THIS order, before it
    # is allowed to participate in any hash or equality operation --
    # including `key in snapshot` and `key in FROZEN_PRIMARY_TASK_IDS`
    # themselves. `str` subclasses can override `__eq__`/`__hash__`, and
    # Python calls the RIGHT operand's override first whenever it is a
    # subclass overriding comparison -- so `frozen_str == key` invokes the
    # SUBCLASS's forged `__eq__`, not the frozen string's own, regardless of
    # which side of `in` the genuine value sits on. A plain equality or
    # membership check is therefore not a defence at all; only checking
    # `type(key) is str` FIRST, before any such operation runs, is. The check
    # is per-key, inside this loop, so a hostile iterator that would yield
    # unboundedly many further keys is refused at the FIRST bad one rather
    # than being drained first.
    snapshot: dict[str, SemanticTaskAttemptResult] = {}
    for key in task_results:
        _require_exact_type(f"task_results key {key!r}", key, str)
        if key not in FROZEN_PRIMARY_TASK_IDS:
            raise RankingInputError(
                "task_results must carry exactly the three frozen primary tasks "
                f"{list(FROZEN_PRIMARY_TASK_IDS)}; got an unexpected key {key!r}"
            )
        if key in snapshot:
            raise RankingInputError(
                f"task_results yielded the key {key!r} more than once from its own "
                "single iteration pass -- refused rather than silently collapsed"
            )
        snapshot[key] = task_results[key]
    missing = [task_id for task_id in FROZEN_PRIMARY_TASK_IDS if task_id not in snapshot]
    if missing:
        raise RankingInputError(
            "task_results must carry exactly the three frozen primary tasks "
            f"{list(FROZEN_PRIMARY_TASK_IDS)}; missing={missing}"
        )
    evidence = tuple(
        _r2_evidence_for_task_result(task_id, snapshot[task_id])
        for task_id in FROZEN_PRIMARY_TASK_IDS
    )
    identities = {
        (snapshot[task_id].candidate, snapshot[task_id].model_id)
        for task_id in FROZEN_PRIMARY_TASK_IDS
    }
    if len(identities) != 1:
        raise RankingInputError(
            "task_results mixes candidates/models; R-2 is a CANDIDATE-level "
            f"measure and refuses a mixed set: {sorted(identities)}"
        )
    return _require_frozen_task_evidence("R-2 evidence", evidence)


def r2_evidence_from_sweep(sweep: PrimarySweepResult) -> tuple[R2TaskEvidence, ...]:
    """Primitive R-2 evidence read out of a complete primary sweep.

    Consults **no caller primitive**: every value comes from each task
    result's own ``scope_result``.

    Read the authority statement in this module's docstring before using this
    for anything that looks like a decision. ``PrimarySweepResult`` is
    publicly constructible and attests nothing about issuance, so deriving R-2
    from it is policy math over genuine per-task facts -- never proof that the
    aggregate is one candidate's real sweep. **``semantic_sweep`` is not
    reopened, and no sweep issuance token is invented here.**
    """
    _require_exact_type("sweep", sweep, PrimarySweepResult)
    return r2_evidence_from_task_results(sweep.task_results)


# ===========================================================================
# R-3 -- NOT_EVALUABLE for this qualification-policy revision
# ===========================================================================


def _resolve_r3_bucket(supplied: object) -> ReportAccuracyBucket | None:
    """R-3's value for this revision -- ``None``, or a loud refusal.

    While :data:`R3_EVALUABLE` is ``False`` a supplied bucket is REFUSED, not
    ignored: silently discarding it would be the same class of defect as
    silently skipping a one-sided R-3 (Sec. 10.6.2a).
    """
    if supplied is None:
        return None
    _require_exact_type("r3_bucket", supplied, ReportAccuracyBucket)
    if not R3_EVALUABLE:
        raise RankingInputError(
            "R-3 is NOT_EVALUABLE for qualification-policy revision "
            f"{QUALIFICATION_POLICY_REVISION!r}: the frozen corpus and harness "
            "expose no bounded, structured, machine-readable final-report claim "
            f"channel, so the supplied bucket {supplied!r} cannot be truthful. It "
            "is refused, never silently ignored"
        )
    return supplied  # type: ignore[return-value]


# ===========================================================================
# Ranking objects
# ===========================================================================


@dataclass(frozen=True)
class RankingInput:
    """Explicit per-candidate facts this module buckets. Never inferred from prose.

    **There is deliberately no ``r2_bucket`` field.** R-2 is derived by AIDO
    from ``r2_evidence`` through the single :func:`resolve_r2_bucket`
    implementation, so there is no supported path by which a caller supplies
    ``CLEAN`` while the evidence mathematically derives ``REPEATED_FRICTION``
    (LIVE1 design Sec. 9.4.8 C3-R2-2).

    ``r1_bucket`` and the R-4-related booleans REMAIN caller-authored. That is
    stated, not hidden: C3 centralizes R-2's math; deriving R-1 and R-4
    authoritatively is M4's work.
    """

    all_tasks_autonomous_pass: bool
    any_runtime_timeout_or_stalled_or_premature_settle: bool
    any_operator_continuation: bool
    any_automatic_retry: bool
    r1_bucket: ScopeBucket
    #: Primitive per-task evidence, exactly the three frozen tasks in order.
    #: Build it with :func:`r2_evidence_from_sweep` /
    #: :func:`r2_evidence_from_task_results` where a genuine object graph
    #: exists; construct it directly only to exercise the policy math.
    r2_evidence: tuple[R2TaskEvidence, ...]
    #: ``None`` for this revision. A supplied bucket is REFUSED while
    #: :data:`R3_EVALUABLE` is ``False`` -- never ignored.
    r3_bucket: ReportAccuracyBucket | None = None
    near_stall_evidence: bool = False
    #: Carried so the ranking boundary is self-describing (Sec. 10A.3
    #: C3-PR-2), and mechanically pinned to the ONE declared constant: any
    #: other value REFUSES. A caller cannot choose the revision.
    qualification_policy_revision: str = QUALIFICATION_POLICY_REVISION

    def __post_init__(self) -> None:
        for name in (
            "all_tasks_autonomous_pass",
            "any_runtime_timeout_or_stalled_or_premature_settle",
            "any_operator_continuation",
            "any_automatic_retry",
            "near_stall_evidence",
        ):
            _require_exact_bool(f"RankingInput.{name}", getattr(self, name))
        _require_exact_type("RankingInput.r1_bucket", self.r1_bucket, ScopeBucket)
        _require_frozen_task_evidence("RankingInput.r2_evidence", self.r2_evidence)
        _resolve_r3_bucket(self.r3_bucket)
        _require_declared_policy_revision(
            "RankingInput.qualification_policy_revision",
            self.qualification_policy_revision,
        )


@dataclass(frozen=True)
class CandidateRankingProfile:
    """One candidate's categorical profile. **Not a selection authority.**

    See :data:`PROFILE_AUTHORITY_SCOPE` and this module's docstring: building
    one of these directly, rather than through :func:`build_profile`, bypasses
    the R-2 derivation and produces a record that attests nothing.

    ``__post_init__`` checks SHAPE only -- exact bucket types and an exact,
    non-blank ``str`` revision. It deliberately does NOT pin the revision
    VALUE, so a profile carrying a foreign revision remains constructible and
    :func:`compare_profiles` gets to refuse it (Sec. 10A.3 C3-PR-3) rather
    than that refusal being unreachable. The same reasoning keeps a one-sided
    ``r3`` constructible for Sec. 10.6.2a's defence-in-depth refusal.
    """

    candidate: str
    #: The qualification policy under which these buckets were produced.
    #: :func:`build_profile` stamps it from the ONE declared constant.
    qualification_policy_revision: str
    r1: ScopeBucket
    r2: OperationBucket
    #: ``None`` for every profile of this revision -- R-3 is NOT_EVALUABLE and
    #: ranks neither candidate. NOT the same thing as R-4's optionality.
    r3: ReportAccuracyBucket | None
    r4: CompletionBucket | None  # None: excluded from R-4 (never a clean unconditional AUTONOMOUS_PASS sweep)

    def __post_init__(self) -> None:
        _require_exact_type("CandidateRankingProfile.candidate", self.candidate, str)
        _require_exact_type(
            "CandidateRankingProfile.qualification_policy_revision",
            self.qualification_policy_revision,
            str,
        )
        if not self.qualification_policy_revision:
            raise RankingInputError(
                "CandidateRankingProfile.qualification_policy_revision must be non-blank"
            )
        _require_exact_type("CandidateRankingProfile.r1", self.r1, ScopeBucket)
        _require_exact_type("CandidateRankingProfile.r2", self.r2, OperationBucket)
        if self.r3 is not None:
            _require_exact_type("CandidateRankingProfile.r3", self.r3, ReportAccuracyBucket)
        if self.r4 is not None:
            _require_exact_type("CandidateRankingProfile.r4", self.r4, CompletionBucket)


def eligible_for_ranking(hard_bar_state: QualificationState) -> bool:
    return hard_bar_state == QualificationState.AUTONOMOUS_QUALIFIED


def resolve_r4_bucket(ranking_input: RankingInput) -> CompletionBucket | None:
    """R-4 is defined ONLY among candidates all three of whose tasks are,
    unconditionally, AUTONOMOUS_PASS (Sec. 18).

    **R-4's bucket semantics are unchanged by C3.** The only addition is the
    non-coercing type guard below: every branch here reads a boolean through
    ``not`` / ``or``, so a non-bool that reached this function some other way
    (a construction bypassing ``RankingInput.__post_init__``) would be read
    through truthiness and could invent a ``CLEAN_SETTLE``. The guard refuses
    instead. No well-formed input's bucket changes.
    """
    _require_exact_type("ranking_input", ranking_input, RankingInput)
    for name in (
        "all_tasks_autonomous_pass",
        "any_runtime_timeout_or_stalled_or_premature_settle",
        "any_operator_continuation",
        "any_automatic_retry",
        "near_stall_evidence",
    ):
        _require_exact_bool(f"RankingInput.{name}", getattr(ranking_input, name))
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
    """Build a candidate's ranking profile, or ``None`` if it cannot be ranked.

    R-2 is DERIVED here, once, from ``ranking_input.r2_evidence``; the profile
    is STAMPED with the single declared
    :data:`~qualification.QUALIFICATION_POLICY_REVISION` rather than with
    anything a caller passes (Sec. 10A.3 C3-PR-2); and R-3 is ``None`` for
    this revision, with a supplied bucket refused rather than dropped.
    """
    _require_exact_type("ranking_input", ranking_input, RankingInput)
    _require_exact_type("candidate", candidate, str)
    _require_exact_type("hard_bar_state", hard_bar_state, QualificationState)
    # Defence in depth: `RankingInput.__post_init__` already refused a foreign
    # revision; this refuses it again at the stamping boundary rather than
    # trusting an object that reached here some other way.
    _require_declared_policy_revision(
        "ranking_input.qualification_policy_revision",
        ranking_input.qualification_policy_revision,
    )
    if not eligible_for_ranking(hard_bar_state):
        return None
    return CandidateRankingProfile(
        candidate=candidate,
        qualification_policy_revision=QUALIFICATION_POLICY_REVISION,
        r1=ranking_input.r1_bucket,
        r2=resolve_r2_bucket(ranking_input.r2_evidence),
        r3=_resolve_r3_bucket(ranking_input.r3_bucket),
        r4=resolve_r4_bucket(ranking_input),
    )


def compare_profiles(a: CandidateRankingProfile, b: CandidateRankingProfile) -> str:
    """Lexicographic R-1 -> R-4 comparison. Returns ``"a"``, ``"b"``, or ``"tie"``.

    Comparison stops at the first tier where the two profiles' buckets
    differ (Sec. 18). If R-1 through R-4 place both in the identical bucket
    at every tier, the result is ``"tie"`` -- materially indistinguishable
    under the predeclared categories, requiring Sec. 21's tie-break policy.

    Two comparability conditions are checked BEFORE any tier is walked, so a
    short-circuit at R-1 can never hide either of them:

    ``qualification_policy_revision``
        must be identical (Sec. 10A.3 C3-PR-3). Comparing candidates
        evaluated under different policies is invalid -- never "prefer the
        newer", never "skip the affected tiers", never a warning, and never
        normalized to the current revision.

    R-3 symmetry (Sec. 10.6.2a), which is NOT R-4's optionality rule::

        a.r3 is None      AND b.r3 is None      -> SKIP R-3
        a.r3 is a bucket  AND b.r3 is a bucket  -> COMPARE in _R3_ORDER
        exactly one side is None                -> REFUSE

    R-3's absence is a GLOBAL POLICY fact for a revision; R-4's is a genuine
    PER-CANDIDATE possibility. A one-sided R-3 therefore means an asymmetric
    qualification state -- a fairness violation, not optional missing
    evidence -- and is refused rather than skipped, treated as worst, treated
    as best, or repaired with ``ACCURATE``.

    R-4 keeps its existing behaviour, unchanged by C3: it is compared only
    when both profiles carry one, and a missing R-4 on either side is simply
    skipped rather than treated as a tier difference, since a candidate
    without an R-4 bucket could not have reached ranking in the first place
    under the hard bar.
    """
    for name, profile in (("a", a), ("b", b)):
        _require_exact_type(name, profile, CandidateRankingProfile)

    # -- comparability, before any tier --
    for name, profile in (("a", a), ("b", b)):
        _require_exact_type(
            f"{name}.qualification_policy_revision",
            profile.qualification_policy_revision,
            str,
        )
    if a.qualification_policy_revision != b.qualification_policy_revision:
        raise RankingComparabilityError(
            "refusing to compare two candidates evaluated under different "
            "qualification-policy revisions "
            f"({a.qualification_policy_revision!r} vs "
            f"{b.qualification_policy_revision!r}) -- the newer is not preferred, "
            "no tier is skipped, and neither revision is normalized to the other"
        )
    if (a.r3 is None) != (b.r3 is None):
        raise RankingComparabilityError(
            "refusing to compare a one-sided R-3 "
            f"(a.r3={a.r3!r}, b.r3={b.r3!r}) -- R-3's absence is a GLOBAL policy "
            "fact for a revision, so exactly one side missing means the two "
            "candidates were evaluated under different policy states. This is "
            "never silently skipped, never treated as worst or best, and never "
            "repaired with a default bucket"
        )

    tiers: list[tuple[tuple, object, object]] = [
        (_R1_ORDER, a.r1, b.r1),
        (_R2_ORDER, a.r2, b.r2),
    ]
    if a.r3 is not None and b.r3 is not None:
        tiers.append((_R3_ORDER, a.r3, b.r3))

    for order, value_a, value_b in tiers:
        expected = type(order[0])
        _require_exact_type("profile a's tier value", value_a, expected)
        _require_exact_type("profile b's tier value", value_b, expected)
        index_a, index_b = order.index(value_a), order.index(value_b)
        if index_a != index_b:
            return "a" if index_a < index_b else "b"

    if a.r4 is not None and b.r4 is not None:
        # Blocker 2 (5F3B-LIVE1-C3-FU1): `CompletionBucket` is a `str` enum,
        # so a plain string or a `str` subclass lookalike can satisfy `!=`
        # comparisons and even `tuple.index` the same way a genuine member
        # would. Unlike the R-1/R-2/R-3 tiers above, R-4 was compared without
        # first pinning `type(value) is CompletionBucket`, which is a
        # fail-open path for a profile mutated after construction (`a.r4 =
        # object.__setattr__(profile, "r4", "CLEAN_SETTLE")`). The exact-type
        # guard runs for BOTH sides here, BEFORE the equality check -- so it
        # also catches a malformed value that happens to already equal the
        # other side, which `a.r4 != b.r4` alone would never see.
        _require_exact_type("a.r4", a.r4, CompletionBucket)
        _require_exact_type("b.r4", b.r4, CompletionBucket)
        if a.r4 != b.r4:
            index_a, index_b = _R4_ORDER.index(a.r4), _R4_ORDER.index(b.r4)
            return "a" if index_a < index_b else "b"

    return "tie"
