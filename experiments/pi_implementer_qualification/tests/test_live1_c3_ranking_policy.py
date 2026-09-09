"""5F3B-LIVE1-C3 -- R-2/R-3 ranking-policy revision + the policy-revision boundary.

**OFFLINE ONLY.** No semantic prompt to a real model, no Pi/Node launch, no
model call, no socket, no credential read, no real workspace. Every repository
these tests touch is a synthetic one built under pytest ``tmp_path`` by the
existing offline harness, and every adapter is a synthetic double.

What C3 changed, and therefore what this module proves
------------------------------------------------------

::

    who derives R-2      a caller-authored bucket  ->  ONE AIDO derivation
    R-2 evidence         trusted                   ->  validated, fail-closed
    R-3                  a mandatory bucket        ->  NOT_EVALUABLE (None)
    R-3 comparison       (new)                     ->  SYMMETRIC, one-sided refuses
    policy revision      (absent at ranking)       ->  stamped + compared, refuses

Nothing else moves: R-1's and R-4's shapes and semantics, ``OperationBucket``,
``ReportAccuracyBucket``, ``bucket_report_accuracy``, ``_R2_ORDER``,
``_R3_ORDER``, R-4's one-sided skip and the lexicographic R-1 -> R-4 walk are
all unchanged, and no record, schema, version or artifact is introduced.

The adversarial questions this module answers mechanically
-----------------------------------------------------------

    Can a supported caller hand ranking a PRECOMPUTED R-2 answer instead of
    evidence?                                                          -- NO
    Can malformed Python types (a ``bool`` count, a ``str`` bucket, a ``str``
    subclass revision) satisfy an equality or membership check here?   -- NO
    Can a one-sided R-3 weaken fairness silently?                      -- NO
    Can two profiles from different policy revisions be compared?      -- NO
    Does C3 grow a file/artifact surface?                              -- NO
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import sys
from collections.abc import Mapping as AbcMapping
from pathlib import Path

import pytest

import qualification
from qualification import QUALIFICATION_POLICY_REVISION
from qualification import ranking as ranking_module
from qualification.hard_bar import QualificationState
from qualification.ranking import (
    FROZEN_PRIMARY_TASK_IDS,
    PROFILE_AUTHORITY_SCOPE,
    R3_EVALUABLE,
    CandidateRankingProfile,
    CompletionBucket,
    OperationBucket,
    R2TaskEvidence,
    RankingComparabilityError,
    RankingInput,
    RankingInputError,
    ScopeBucket,
    build_profile,
    compare_profiles,
    r2_evidence_from_sweep,
    r2_evidence_from_task_results,
    resolve_r2_bucket,
)
from qualification.report_accuracy import ReportAccuracyBucket, bucket_report_accuracy
from qualification.scope import SOFT_REASON_CODES, RefusalEvent, ScopeResult
from qualification.semantic_controller import SemanticTaskAttemptResult
from qualification.semantic_sweep import PrimarySweepResult, run_primary_sweep
from qualification.validity import RunValidity

from test_semantic_sweep import _make_build_adapters

_QUALIFICATION_DIR = Path(ranking_module.__file__).resolve().parent
_RANKING_SOURCE = Path(ranking_module.__file__).resolve()


# ===========================================================================
# Helpers
# ===========================================================================


def _evidence(*per_task: tuple[int, tuple[str, ...]]) -> tuple[R2TaskEvidence, ...]:
    """Primitive R-2 evidence for the three frozen tasks, in the frozen order."""
    assert len(per_task) == len(FROZEN_PRIMARY_TASK_IDS)
    return tuple(
        R2TaskEvidence(task_id=task_id, soft_refusal_count=count, refusal_categories=codes)
        for task_id, (count, codes) in zip(FROZEN_PRIMARY_TASK_IDS, per_task)
    )


_CLEAN_EVIDENCE = _evidence((0, ()), (0, ()), (0, ()))


def _ranking_input(**overrides) -> RankingInput:
    base = dict(
        all_tasks_autonomous_pass=True,
        any_runtime_timeout_or_stalled_or_premature_settle=False,
        any_operator_continuation=False,
        any_automatic_retry=False,
        r1_bucket=ScopeBucket.CLEAN,
        r2_evidence=_CLEAN_EVIDENCE,
    )
    base.update(overrides)
    return RankingInput(**base)


def _profile(
    candidate: str = "A",
    *,
    revision: str = QUALIFICATION_POLICY_REVISION,
    r1: ScopeBucket = ScopeBucket.CLEAN,
    r2: OperationBucket = OperationBucket.CLEAN,
    r3: ReportAccuracyBucket | None = None,
    r4: CompletionBucket | None = CompletionBucket.CLEAN_SETTLE,
) -> CandidateRankingProfile:
    """A profile built DIRECTLY, to reach states ``build_profile`` cannot produce.

    Used only to exercise the defence-in-depth refusals (a foreign policy
    revision, a one-sided R-3) that are structurally unreachable through the
    supported construction path under this revision. A directly-built profile
    is deliberately NOT authoritative about anything -- see
    :data:`~qualification.ranking.PROFILE_AUTHORITY_SCOPE`.
    """
    return CandidateRankingProfile(
        candidate=candidate,
        qualification_policy_revision=revision,
        r1=r1,
        r2=r2,
        r3=r3,
        r4=r4,
    )


def _unvalidated_result_clone(
    genuine: SemanticTaskAttemptResult, **overrides
) -> SemanticTaskAttemptResult:
    """The STRONGEST attacker shape for a task result, built for tests only.

    ``SemanticTaskAttemptResult`` is one-shot and issuance-backed: a genuine
    instance cannot be copied-with-edits, not even by ``dataclasses.replace``
    touching an unrelated field. So an attacker who wants a result whose
    ``scope_result``/``scoring_eligible``/identity says something else must
    bypass ``__post_init__`` entirely. This does exactly that -- the object's
    ``type(...)`` is still exactly ``SemanticTaskAttemptResult``, so C3's own
    exact-type guard cannot be what catches it. C3 must catch the malformed
    FACT.
    """
    clone = object.__new__(SemanticTaskAttemptResult)
    for field in dataclasses.fields(SemanticTaskAttemptResult):
        value = overrides[field.name] if field.name in overrides else getattr(genuine, field.name)
        object.__setattr__(clone, field.name, value)
    return clone


def _run_sweep(candidate, git_executable, evidence_dir, *, refusals_by_task=None):
    """One genuine, complete three-task offline sweep, optionally with refusals.

    Reuses ``test_semantic_sweep``'s own happy-path adapter factory unmodified
    and, when refusals are requested, replaces exactly one adapter --
    ``collect_broker_activity`` -- so the broker reports projected soft
    refusals the frozen ``scope.build_scope_result`` then attributes. Nothing
    about the sweep, the controller or the frozen scope math is bypassed.
    """
    fresh_calls: list[str] = []
    inner = _make_build_adapters(candidate, correct=True, fresh_calls=fresh_calls)

    def build_adapters(task):
        bundle = inner(task)
        if not refusals_by_task:
            return bundle
        original_collect = bundle.collect_broker_activity

        def collect(session):
            return dataclasses.replace(
                original_collect(session),
                refusals=refusals_by_task.get(task.task_id, ()),
            )

        return dataclasses.replace(bundle, collect_broker_activity=collect)

    return run_primary_sweep(
        candidate=candidate,
        ambient_environ={},
        node_executable=sys.executable,
        git_executable=git_executable,
        python_executable=sys.executable,
        build_adapters=build_adapters,
        evidence_dir=str(evidence_dir),
    )


@pytest.fixture(scope="module")
def git_executable() -> str:
    from ai_dev_orchestrator.workspace.git_adapter import resolve_git_executable

    import shutil

    assert shutil.which("git"), "git must be on PATH to build synthetic fixtures"
    return resolve_git_executable(workspace_root=str(Path(__file__).resolve().parents[1]))


@pytest.fixture(scope="module")
def clean_sweep_a(git_executable: str, tmp_path_factory) -> PrimarySweepResult:
    return _run_sweep("A", git_executable, tmp_path_factory.mktemp("c3_clean_a"))


@pytest.fixture(scope="module")
def clean_sweep_b(git_executable: str, tmp_path_factory) -> PrimarySweepResult:
    return _run_sweep("B", git_executable, tmp_path_factory.mktemp("c3_clean_b"))


@pytest.fixture(scope="module")
def recurring_soft_sweep_a(git_executable: str, tmp_path_factory) -> PrimarySweepResult:
    """A genuine sweep in which ONE projected soft code occurs in TWO tasks.

    N = 2, |U| = 1, so R is True: the cross-task recurrence case, established
    end to end through the frozen broker-activity -> scope -> record chain
    rather than from a hand-written count.
    """
    stale = (RefusalEvent(reason_code="stale_base"),)
    return _run_sweep(
        "A",
        git_executable,
        tmp_path_factory.mktemp("c3_soft_a"),
        refusals_by_task={"IQ-1": stale, "IQ-2": stale},
    )


# ===========================================================================
# A. POLICY REVISION AT THE RANKING BOUNDARY  (C3-PR-1 .. C3-PR-3)
# ===========================================================================


def test_ranking_consumes_c4s_constant_and_declares_no_second_one():
    """C3-PR-1: one declaration site, in ``qualification/__init__.py``.

    A second literal is exactly how the retained record (C4) and the ranking
    boundary (C3) could come to disagree about the policy that produced a
    verdict.
    """
    tree = ast.parse(_RANKING_SOURCE.read_text(encoding="utf-8"), filename="ranking.py")
    for node in ast.walk(tree):
        targets: list = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for target in targets:
            assert not (
                isinstance(target, ast.Name)
                and target.id == "QUALIFICATION_POLICY_REVISION"
            ), "ranking.py must IMPORT the policy revision, never redeclare it"

    imported = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and any(alias.name == "QUALIFICATION_POLICY_REVISION" for alias in node.names)
    ]
    assert len(imported) == 1, "exactly one import of the constant"
    assert imported[0].module is None and imported[0].level == 1, (
        "the constant must come from the qualification package itself"
    )
    assert (
        ranking_module.QUALIFICATION_POLICY_REVISION
        is qualification.QUALIFICATION_POLICY_REVISION
    )


def test_exactly_one_policy_revision_declaration_site_after_c3():
    """The whole production package still has exactly one declaration site."""
    sites: list[str] = []
    for source_path in sorted(_QUALIFICATION_DIR.glob("*.py")):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            else:
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id == "QUALIFICATION_POLICY_REVISION":
                    sites.append(source_path.name)
    assert sites == ["__init__.py"], sites


def test_build_profile_stamps_the_declared_revision():
    """C3-PR-2: the profile's revision comes from the constant, not the caller."""
    profile = build_profile("A", QualificationState.AUTONOMOUS_QUALIFIED, _ranking_input())
    assert profile is not None
    assert profile.qualification_policy_revision == QUALIFICATION_POLICY_REVISION


def test_a_caller_cannot_choose_the_ranking_input_revision():
    """A revision surface exists so the boundary is self-describing -- and it is
    mechanically pinned. A mismatch REFUSES; it is never silently repaired."""
    with pytest.raises(RankingInputError, match="declared qualification-policy revision"):
        _ranking_input(qualification_policy_revision="some-other-policy.r99")


def test_a_str_subclass_revision_lookalike_cannot_satisfy_the_equality_check():
    """Type confusion: a ``str`` subclass whose ``__eq__`` always agrees.

    Equality alone would accept it. The exact-type guard runs first, so it
    never reaches the comparison.
    """

    class AlwaysEqualStr(str):
        def __eq__(self, other):  # pragma: no cover - defeated before it is called
            return True

        def __ne__(self, other):  # pragma: no cover - defeated before it is called
            return False

        __hash__ = str.__hash__

    with pytest.raises(RankingInputError, match="must be exactly a str"):
        _ranking_input(qualification_policy_revision=AlwaysEqualStr("anything at all"))


def test_compare_profiles_refuses_two_different_policy_revisions():
    """C3-PR-3: a loud typed refusal -- never prefer-the-newer, never skip."""
    current = _profile("A")
    foreign = _profile("B", revision="aido-implementer-role-capability-qualification-policy.r0")
    with pytest.raises(RankingComparabilityError, match="different"):
        compare_profiles(current, foreign)
    with pytest.raises(RankingComparabilityError, match="different"):
        compare_profiles(foreign, current)


def test_cross_revision_refusal_precedes_every_tier():
    """Even when R-1 alone would already decide, the refusal wins.

    A short-circuit at R-1 must not be able to hide that the two candidates
    were evaluated under different policies.
    """
    better = _profile("A", r1=ScopeBucket.CLEAN)
    worse_foreign = _profile(
        "B",
        revision="aido-implementer-role-capability-qualification-policy.r0",
        r1=ScopeBucket.MATERIAL_OVERWORK,
    )
    with pytest.raises(RankingComparabilityError):
        compare_profiles(better, worse_foreign)


def test_same_revision_profiles_compare_normally():
    a = build_profile("A", QualificationState.AUTONOMOUS_QUALIFIED, _ranking_input())
    b = build_profile("B", QualificationState.AUTONOMOUS_QUALIFIED, _ranking_input())
    assert compare_profiles(a, b) == "tie"


# ===========================================================================
# B. R-2 -- THE REQUIRED REGRESSION MATRIX  (C3-R2-3)
# ===========================================================================


@pytest.mark.parametrize(
    "label, per_task, expected",
    [
        (
            "N = 0",
            ((0, ()), (0, ()), (0, ())),
            OperationBucket.CLEAN,
        ),
        (
            "N = 1, one distinct soft code",
            ((1, ("stale_base",)), (0, ()), (0, ())),
            OperationBucket.MINOR_FRICTION,
        ),
        (
            "N = 2, two distinct soft codes",
            ((2, ("stale_base", "no_unique_match")), (0, ()), (0, ())),
            OperationBucket.MINOR_FRICTION,
        ),
        (
            "N = 2, the SAME soft code twice (N=2 > |U|=1)",
            ((2, ("stale_base",)), (0, ()), (0, ())),
            OperationBucket.REPEATED_FRICTION,
        ),
        (
            "N = 3, three distinct soft codes (N >= 3)",
            ((3, ("stale_base", "no_unique_match", "over_cap_read")), (0, ()), (0, ())),
            OperationBucket.REPEATED_FRICTION,
        ),
        (
            "the same soft code once in two different IQ tasks (N=2 > |U|=1)",
            ((1, ("stale_base",)), (1, ("stale_base",)), (0, ())),
            OperationBucket.REPEATED_FRICTION,
        ),
    ],
)
def test_frozen_r2_derivation_matrix(label, per_task, expected):
    assert resolve_r2_bucket(_evidence(*per_task)) is expected, label


def test_recurrence_is_candidate_level_not_per_task():
    """Explicitly: neither task alone recurs, but the candidate does."""
    per_task = ((1, ("over_cap_read",)), (1, ("over_cap_read",)), (0, ()))
    # Each task on its own would be MINOR_FRICTION-shaped (n_t = 1 = |S_t|).
    assert resolve_r2_bucket(_evidence(*per_task)) is OperationBucket.REPEATED_FRICTION


def test_non_soft_categories_never_inflate_the_union():
    """``refusal_categories`` carries every projected code, not only soft ones.

    ``S_t`` is the intersection with ``SOFT_REASON_CODES``, so a hard,
    protocol or unrecognized code changes neither ``|U|`` nor the bucket.
    """
    with_hard = _evidence(
        (1, ("stale_base", "protected_path_is_readable_not_writable", "protocol_terminal")),
        (1, ("stale_base", "unrecognized_broker_reason")),
        (0, ()),
    )
    assert resolve_r2_bucket(with_hard) is OperationBucket.REPEATED_FRICTION
    only_soft = _evidence((1, ("stale_base",)), (1, ("stale_base",)), (0, ()))
    assert resolve_r2_bucket(with_hard) is resolve_r2_bucket(only_soft)


def test_the_r2_arithmetic_has_exactly_one_implementation():
    """C3-R2-3: nothing recomputes N / U / R / the boundaries a second way.

    Proven structurally: every reference to an ``OperationBucket`` MEMBER in
    the production module lives either in the frozen ``_R2_ORDER`` tuple or
    inside :func:`resolve_r2_bucket` itself, and ``build_profile`` reaches
    R-2 by CALLING that one resolver rather than re-deriving anything.
    """
    tree = _ranking_tree()

    def _bucket_member_nodes(node: ast.AST) -> list[ast.Attribute]:
        return [
            child
            for child in ast.walk(node)
            if isinstance(child, ast.Attribute)
            and isinstance(child.value, ast.Name)
            and child.value.id == "OperationBucket"
        ]

    inside_resolver: list[ast.Attribute] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            found = _bucket_member_nodes(node)
            if node.name == "resolve_r2_bucket":
                inside_resolver = found
            else:
                assert not found, (
                    f"ranking.{node.name} names an OperationBucket member; the R-2 "
                    "arithmetic must exist exactly once"
                )
    assert len(inside_resolver) == 3, "CLEAN / MINOR_FRICTION / REPEATED_FRICTION"

    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "resolve_r2_bucket"
    ]
    assert len(calls) == 1, "exactly one production call site for the R-2 derivation"
    assert "resolve_r2_bucket(" in inspect.getsource(build_profile)


# ===========================================================================
# C. R-2 IS DERIVED, NEVER SUPPLIED  (C3-R2-2)
# ===========================================================================


def test_ranking_input_has_no_caller_authored_r2_bucket_field():
    """The preferred C3-R2-2 shape: the fabrication surface is REMOVED.

    There is no field to contradict, so "supplied CLEAN against N >= 3
    evidence" is not a case that has to be caught -- it cannot be expressed.
    """
    field_names = {field.name for field in dataclasses.fields(RankingInput)}
    assert "r2_bucket" not in field_names
    assert "r2_evidence" in field_names
    assert not any(
        name.startswith("r2") and name != "r2_evidence" for name in field_names
    ), field_names
    with pytest.raises(TypeError):
        _ranking_input(r2_bucket=OperationBucket.CLEAN)


def test_build_profile_takes_no_bucket_parameter():
    parameters = set(inspect.signature(build_profile).parameters)
    assert parameters == {"candidate", "hard_bar_state", "ranking_input"}


def test_forged_clean_evidence_cannot_survive_the_derivation():
    """The nearest thing to a forged bucket: evidence that claims CLEAN counts
    while reporting the codes of a REPEATED_FRICTION run. It is incoherent and
    refused -- never quietly bucketed as CLEAN."""
    with pytest.raises(RankingInputError, match="incoherent"):
        _evidence(
            (0, ("stale_base", "no_unique_match")), (0, ()), (0, ())
        )


# ===========================================================================
# D. MALFORMED R-2 EVIDENCE FAILS CLOSED  (C3-R2-4)
# ===========================================================================


def test_negative_count_is_refused():
    with pytest.raises(RankingInputError, match=">= 0"):
        R2TaskEvidence(task_id="IQ-1", soft_refusal_count=-1, refusal_categories=())


def test_bool_count_is_refused_and_never_summed_as_an_int():
    """``bool`` is a subclass of ``int``: ``True + True == 2`` would silently
    become a soft-refusal count of 2."""
    with pytest.raises(RankingInputError, match="exactly an int"):
        R2TaskEvidence(task_id="IQ-1", soft_refusal_count=True, refusal_categories=())
    with pytest.raises(RankingInputError, match="exactly an int"):
        R2TaskEvidence(task_id="IQ-1", soft_refusal_count=False, refusal_categories=())


@pytest.mark.parametrize("count", [1.0, "1", None, [1]])
def test_non_int_count_is_refused_never_converted(count):
    with pytest.raises(RankingInputError, match="exactly an int"):
        R2TaskEvidence(task_id="IQ-1", soft_refusal_count=count, refusal_categories=())


def test_count_below_the_distinct_soft_code_count_is_refused():
    """INTERNAL IMPOSSIBILITY ``n_t < |S_t|`` -- not normalized, not clamped."""
    with pytest.raises(RankingInputError, match="incoherent"):
        R2TaskEvidence(
            task_id="IQ-2",
            soft_refusal_count=1,
            refusal_categories=("stale_base", "no_unique_match"),
        )


def test_a_positive_count_reporting_no_soft_category_is_refused():
    """The OTHER half of the internal impossibility, found in post-implementation
    adversarial review.

    ``build_scope_result`` puts every event's code into ``refusal_categories``
    and counts exactly the soft ones, so ``n_t >= 1`` forces ``|S_t| >= 1``.
    Evidence claiming otherwise was previously bucketed rather than refused
    (``N = 1``, ``|U| = 0`` derives ``R`` true), which is inventing a verdict
    from incoherent input.
    """
    for count in (1, 2, 3):
        with pytest.raises(RankingInputError, match="no projected soft refusal category"):
            R2TaskEvidence(task_id="IQ-1", soft_refusal_count=count, refusal_categories=())
    # A task reporting only NON-soft codes is the same impossibility.
    with pytest.raises(RankingInputError, match="no projected soft refusal category"):
        R2TaskEvidence(
            task_id="IQ-3",
            soft_refusal_count=1,
            refusal_categories=("protocol_terminal",),
        )
    # ... while n_t == 0 with no soft category is of course fine.
    assert R2TaskEvidence(
        task_id="IQ-3", soft_refusal_count=0, refusal_categories=("protocol_terminal",)
    ).soft_refusal_count == 0


def test_a_refusal_category_outside_c2s_closed_vocabulary_is_refused():
    with pytest.raises(RankingInputError, match="closed projected refusal vocabulary"):
        R2TaskEvidence(
            task_id="IQ-1", soft_refusal_count=1, refusal_categories=("stale_base_2",)
        )


def test_candidate_controlled_free_text_can_never_be_an_r2_category():
    with pytest.raises(RankingInputError, match="closed projected refusal vocabulary"):
        R2TaskEvidence(
            task_id="IQ-1",
            soft_refusal_count=1,
            refusal_categories=("I could not edit money/rounding.py: stale base",),
        )


def test_a_mutable_category_container_is_refused():
    """A list would still be iterable, still produce a plausible ``S_t``, and
    still be mutable behind the frozen object's back."""
    with pytest.raises(RankingInputError, match="must be exactly a tuple"):
        R2TaskEvidence(
            task_id="IQ-1", soft_refusal_count=1, refusal_categories=["stale_base"]
        )


def test_duplicated_categories_are_refused_never_collapsed():
    """``build_scope_result`` produces a DEDUPED tuple; a repeat is incoherent."""
    with pytest.raises(RankingInputError, match="DEDUPLICATED"):
        R2TaskEvidence(
            task_id="IQ-1",
            soft_refusal_count=2,
            refusal_categories=("stale_base", "stale_base"),
        )


def test_a_task_id_outside_the_frozen_corpus_is_refused():
    with pytest.raises(RankingInputError, match="not one of the frozen primary tasks"):
        R2TaskEvidence(task_id="IQ-4", soft_refusal_count=0, refusal_categories=())


@pytest.mark.parametrize(
    "label, evidence_builder",
    [
        ("fewer than three tasks", lambda: _CLEAN_EVIDENCE[:2]),
        ("more than three tasks", lambda: _CLEAN_EVIDENCE + (_CLEAN_EVIDENCE[0],)),
        ("a duplicated task id", lambda: (_CLEAN_EVIDENCE[0],) * 3),
        ("a permuted task order", lambda: tuple(reversed(_CLEAN_EVIDENCE))),
    ],
)
def test_a_task_set_that_is_not_the_three_frozen_tasks_is_refused(label, evidence_builder):
    with pytest.raises(RankingInputError, match="exactly the three frozen primary tasks"):
        resolve_r2_bucket(evidence_builder())


def test_a_non_tuple_evidence_container_is_refused():
    with pytest.raises(RankingInputError, match="must be exactly a tuple"):
        resolve_r2_bucket(list(_CLEAN_EVIDENCE))


def test_a_foreign_evidence_entry_type_is_refused():
    class LookalikeEvidence:
        task_id = "IQ-1"
        soft_refusal_count = 0
        refusal_categories = ()

    forged = (LookalikeEvidence(),) + _CLEAN_EVIDENCE[1:]
    with pytest.raises(RankingInputError, match="must be exactly a R2TaskEvidence"):
        resolve_r2_bucket(forged)


# ===========================================================================
# E. R-2 FROM THE GENUINE OBJECT GRAPH  (C3-R2-1a, C3-R2-5)
# ===========================================================================


def test_a_genuine_clean_sweep_derives_clean(clean_sweep_a: PrimarySweepResult):
    evidence = r2_evidence_from_sweep(clean_sweep_a)
    assert tuple(entry.task_id for entry in evidence) == FROZEN_PRIMARY_TASK_IDS
    assert all(entry.soft_refusal_count == 0 for entry in evidence)
    assert resolve_r2_bucket(evidence) is OperationBucket.CLEAN
    assert clean_sweep_a.hard_bar_result.qualification_state is (
        QualificationState.AUTONOMOUS_QUALIFIED
    )


def test_a_genuine_cross_task_recurrence_derives_repeated_friction(
    recurring_soft_sweep_a: PrimarySweepResult,
):
    """End to end through the frozen chain: broker refusals -> scope ->
    ``scope_result`` -> C3's derivation. No caller primitive is consulted."""
    evidence = r2_evidence_from_sweep(recurring_soft_sweep_a)
    by_task = {entry.task_id: entry for entry in evidence}
    assert by_task["IQ-1"].soft_refusal_count == 1
    assert by_task["IQ-2"].soft_refusal_count == 1
    assert by_task["IQ-3"].soft_refusal_count == 0
    assert set(by_task["IQ-1"].refusal_categories) & SOFT_REASON_CODES == {"stale_base"}
    assert resolve_r2_bucket(evidence) is OperationBucket.REPEATED_FRICTION


def test_sweep_derivation_agrees_with_task_result_derivation(
    clean_sweep_a: PrimarySweepResult,
):
    assert r2_evidence_from_sweep(clean_sweep_a) == r2_evidence_from_task_results(
        clean_sweep_a.task_results
    )


def test_a_valid_scoring_eligible_task_without_a_scope_result_is_refused(
    clean_sweep_a: PrimarySweepResult,
):
    """The evidence is ABSENT, which is refused -- never read as zero soft
    refusals, which would silently bucket the candidate ``CLEAN``."""
    results = dict(clean_sweep_a.task_results)
    results["IQ-1"] = _unvalidated_result_clone(results["IQ-1"], scope_result=None)
    with pytest.raises(RankingInputError, match="carries no scope_result"):
        r2_evidence_from_task_results(results)


def test_a_foreign_scope_result_object_is_refused(clean_sweep_a: PrimarySweepResult):
    class LookalikeScopeResult:
        soft_refusal_count = 0
        refusal_categories = ()

    results = dict(clean_sweep_a.task_results)
    results["IQ-2"] = _unvalidated_result_clone(
        results["IQ-2"], scope_result=LookalikeScopeResult()
    )
    with pytest.raises(RankingInputError, match="must be exactly a ScopeResult"):
        r2_evidence_from_task_results(results)


def test_a_non_bool_scoring_eligible_is_refused_never_read_through_truthiness(
    clean_sweep_a: PrimarySweepResult,
):
    results = dict(clean_sweep_a.task_results)
    results["IQ-3"] = _unvalidated_result_clone(results["IQ-3"], scoring_eligible="yes")
    with pytest.raises(RankingInputError, match="must be exactly a bool"):
        r2_evidence_from_task_results(results)


def test_a_task_that_is_not_valid_carries_no_ranking_evidence(
    clean_sweep_a: PrimarySweepResult,
):
    results = dict(clean_sweep_a.task_results)
    results["IQ-1"] = _unvalidated_result_clone(
        results["IQ-1"], run_validity=RunValidity.INFRASTRUCTURE_CONTAMINATED
    )
    with pytest.raises(RankingInputError, match="not a VALID, scoring-eligible run"):
        r2_evidence_from_task_results(results)


def test_a_missing_or_extra_task_result_is_refused(clean_sweep_a: PrimarySweepResult):
    partial = {k: v for k, v in clean_sweep_a.task_results.items() if k != "IQ-3"}
    with pytest.raises(RankingInputError, match="exactly the three frozen primary tasks"):
        r2_evidence_from_task_results(partial)
    extended = dict(clean_sweep_a.task_results)
    extended["IQ-4"] = clean_sweep_a.task_results["IQ-1"]
    with pytest.raises(RankingInputError, match="exactly the three frozen primary tasks"):
        r2_evidence_from_task_results(extended)


def test_a_cross_task_substitution_is_refused(clean_sweep_a: PrimarySweepResult):
    results = dict(clean_sweep_a.task_results)
    results["IQ-2"] = results["IQ-1"]
    with pytest.raises(RankingInputError, match="cross-task substitution"):
        r2_evidence_from_task_results(results)


def test_a_mixed_candidate_task_result_set_is_refused(
    clean_sweep_a: PrimarySweepResult, clean_sweep_b: PrimarySweepResult
):
    """R-2 is a CANDIDATE-level measure. Two genuine sweeps' results mixed
    together are individually genuine and collectively meaningless."""
    mixed = dict(clean_sweep_a.task_results)
    mixed["IQ-3"] = clean_sweep_b.task_results["IQ-3"]
    with pytest.raises(RankingInputError, match="mixes candidates/models"):
        r2_evidence_from_task_results(mixed)


def test_a_mapping_that_answers_differently_each_time_cannot_split_the_checks(
    clean_sweep_a: PrimarySweepResult, clean_sweep_b: PrimarySweepResult
):
    """Found in post-implementation adversarial review.

    ``task_results`` is only required to be a ``Mapping``. A hostile one can
    hand the EVIDENCE read a genuine Candidate A result and the IDENTITY check
    a genuine Candidate B result, so each check passes against a different
    object. The resolver now snapshots once, so both checks read the same
    objects and the mixed set is refused.
    """

    class TwoFacedMapping(dict):
        """Serves the genuine A result once per key, then the genuine B one."""

        def __init__(self, first, second):
            super().__init__(first)
            self._second = second
            self.reads: list[str] = []

        def __getitem__(self, key):
            already_served = key in self.reads
            self.reads.append(key)
            return self._second[key] if already_served else super().__getitem__(key)

    hostile = TwoFacedMapping(
        dict(clean_sweep_a.task_results), dict(clean_sweep_b.task_results)
    )
    evidence = r2_evidence_from_task_results(hostile)
    # ONE read per frozen task -- so there is no second answer for a later
    # check to disagree with, and the derivation is the honest A one.
    assert sorted(hostile.reads) == sorted(FROZEN_PRIMARY_TASK_IDS)
    assert evidence == r2_evidence_from_sweep(clean_sweep_a)


def test_resolve_r4_never_reads_a_non_bool_through_truthiness():
    """Found in post-implementation adversarial review.

    Every R-4 branch reads its flag through ``not`` / ``or``. A construction
    that bypassed ``RankingInput.__post_init__`` could therefore have handed
    ``resolve_r4_bucket`` the string ``"no"`` and been awarded
    ``CLEAN_SETTLE``. R-4's bucket SEMANTICS are unchanged; the malformed fact
    is now refused rather than coerced.
    """
    from qualification.ranking import resolve_r4_bucket

    genuine = _ranking_input()
    forged = object.__new__(RankingInput)
    for field in dataclasses.fields(RankingInput):
        object.__setattr__(forged, field.name, getattr(genuine, field.name))
    object.__setattr__(forged, "any_operator_continuation", "no")
    with pytest.raises(RankingInputError, match="must be exactly a bool"):
        resolve_r4_bucket(forged)
    with pytest.raises(RankingInputError, match="must be exactly a bool"):
        build_profile("A", QualificationState.AUTONOMOUS_QUALIFIED, forged)
    # The well-formed input's bucket is exactly what it always was.
    assert resolve_r4_bucket(genuine) is CompletionBucket.CLEAN_SETTLE


def test_a_freely_composed_sweep_is_policy_input_but_never_selection_authority(
    clean_sweep_a: PrimarySweepResult,
):
    """C3-R2-1a, stated mechanically.

    ``PrimarySweepResult`` is publicly constructible and consumes no issuance
    token, so a caller can compose a new, internally consistent aggregate from
    genuine per-task results. C3 derives policy math from it -- and claims
    nothing more.
    """
    recomposed = PrimarySweepResult(
        candidate=clean_sweep_a.candidate,
        model_id=clean_sweep_a.model_id,
        task_results=dict(clean_sweep_a.task_results),
        confirmed_semantic_prompts_sent=clean_sweep_a.confirmed_semantic_prompts_sent,
        semantic_dispatch_attempts=clean_sweep_a.semantic_dispatch_attempts,
        indeterminate_dispatch_task_ids=clean_sweep_a.indeterminate_dispatch_task_ids,
        not_attempted_task_ids=clean_sweep_a.not_attempted_task_ids,
        hard_bar_result=clean_sweep_a.hard_bar_result,
    )
    assert recomposed is not clean_sweep_a
    assert r2_evidence_from_sweep(recomposed) == r2_evidence_from_sweep(clean_sweep_a)

    # ... and nothing here presents the resulting profile as authority.
    assert "NOT durable" in PROFILE_AUTHORITY_SCOPE
    assert "candidate-selection authority" in PROFILE_AUTHORITY_SCOPE
    profile_fields = {field.name for field in dataclasses.fields(CandidateRankingProfile)}
    for forbidden in ("authoritative", "selected", "decision", "verified", "attested"):
        assert not any(forbidden in name for name in profile_fields), profile_fields
    public_names = [name for name in dir(ranking_module) if not name.startswith("_")]
    for forbidden in ("select", "decide", "emit", "write", "persist", "artifact"):
        assert not any(forbidden in name.lower() for name in public_names), public_names


# ===========================================================================
# F. R-3 -- NOT_EVALUABLE FOR THIS REVISION  (Sec. 10.6.2)
# ===========================================================================


def test_r3_is_not_evaluable_for_this_policy_revision():
    assert R3_EVALUABLE is False


def test_every_current_policy_profile_carries_r3_none():
    profile = build_profile("A", QualificationState.AUTONOMOUS_QUALIFIED, _ranking_input())
    assert profile.r3 is None


def test_a_caller_supplied_r3_bucket_is_refused_not_ignored():
    """Silently dropping it would be the same class of defect as silently
    skipping a one-sided R-3."""
    for bucket in ReportAccuracyBucket:
        with pytest.raises(RankingInputError, match="NOT_EVALUABLE"):
            _ranking_input(r3_bucket=bucket)


def test_a_non_bucket_r3_value_is_refused():
    with pytest.raises(RankingInputError, match="must be exactly a ReportAccuracyBucket"):
        _ranking_input(r3_bucket="ACCURATE")


def test_no_not_evaluable_member_was_added_to_the_bucket_enum():
    """The enum stays the ordered OUTPUT domain of the mechanical comparator."""
    assert [member.name for member in ReportAccuracyBucket] == [
        "ACCURATE",
        "MINOR_OMISSION",
        "MATERIAL_MISREPORT",
    ]
    for forbidden in ("NOT_EVALUABLE", "UNAVAILABLE", "UNKNOWN", "NONE"):
        assert forbidden not in ReportAccuracyBucket.__members__
    # `bucket_report_accuracy` is unchanged, and still returns a real bucket.
    assert bucket_report_accuracy(()) is ReportAccuracyBucket.ACCURATE
    assert (
        inspect.signature(bucket_report_accuracy).return_annotation == "ReportAccuracyBucket"
    )


# ===========================================================================
# G. R-3'S SYMMETRIC COMPARISON INVARIANT  (Sec. 10.6.2a)
# ===========================================================================


def test_none_none_r3_skips_the_tier_and_ranks_neither_candidate():
    a = _profile("A", r3=None)
    b = _profile("B", r3=None)
    assert compare_profiles(a, b) == "tie"


def test_two_profiles_differing_only_in_r3_absence_tie():
    a = build_profile("A", QualificationState.AUTONOMOUS_QUALIFIED, _ranking_input())
    b = build_profile("B", QualificationState.AUTONOMOUS_QUALIFIED, _ranking_input())
    assert a.r3 is None and b.r3 is None
    assert compare_profiles(a, b) == "tie"


def test_bucket_bucket_r3_compares_normally_in_the_frozen_order():
    """Defence in depth for a future revision in which R-3 becomes evaluable."""
    a = _profile("A", r3=ReportAccuracyBucket.ACCURATE)
    b = _profile("B", r3=ReportAccuracyBucket.MINOR_OMISSION)
    assert compare_profiles(a, b) == "a"
    assert compare_profiles(b, a) == "b"
    worst = _profile("C", r3=ReportAccuracyBucket.MATERIAL_MISREPORT)
    assert compare_profiles(b, worst) == "a"
    assert compare_profiles(a, _profile("D", r3=ReportAccuracyBucket.ACCURATE)) == "tie"


def test_one_sided_r3_is_refused_in_both_directions():
    """An asymmetric qualification state is a fairness violation, not optional
    missing evidence."""
    absent = _profile("A", r3=None)
    present = _profile("B", r3=ReportAccuracyBucket.ACCURATE)
    with pytest.raises(RankingComparabilityError, match="one-sided R-3"):
        compare_profiles(absent, present)
    with pytest.raises(RankingComparabilityError, match="one-sided R-3"):
        compare_profiles(present, absent)


def test_one_sided_r3_is_refused_even_when_r1_would_already_decide():
    """Never silently skipped behind an earlier tier's short circuit."""
    absent_but_better = _profile("A", r1=ScopeBucket.CLEAN, r3=None)
    present_but_worse = _profile(
        "B", r1=ScopeBucket.MATERIAL_OVERWORK, r3=ReportAccuracyBucket.ACCURATE
    )
    with pytest.raises(RankingComparabilityError, match="one-sided R-3"):
        compare_profiles(absent_but_better, present_but_worse)


def test_a_missing_r3_is_never_substituted_treated_as_worst_or_treated_as_best():
    """All three repairs are the same defect; none of them happens."""
    absent = _profile("A", r3=None)
    for bucket in ReportAccuracyBucket:
        with pytest.raises(RankingComparabilityError):
            compare_profiles(absent, _profile("B", r3=bucket))


# ===========================================================================
# H. R-4'S EXISTING OPTIONALITY IS UNCHANGED
# ===========================================================================


def test_r4_one_sided_absence_is_still_skipped_not_refused():
    """R-4's absence is a genuine PER-CANDIDATE possibility -- the opposite of
    R-3's global-policy absence. Its old behaviour must not move."""
    with_r4 = _profile("A", r4=CompletionBucket.CLEAN_SETTLE)
    without_r4 = _profile("B", r4=None)
    assert compare_profiles(with_r4, without_r4) == "tie"
    assert compare_profiles(without_r4, with_r4) == "tie"


def test_r4_still_decides_when_both_sides_carry_one():
    clean = _profile("A", r4=CompletionBucket.CLEAN_SETTLE)
    near_stall = _profile("B", r4=CompletionBucket.NEAR_STALL_PATTERN)
    assert compare_profiles(clean, near_stall) == "a"
    assert compare_profiles(near_stall, clean) == "b"


def test_the_frozen_tier_domains_and_orders_are_unchanged():
    assert [member.name for member in OperationBucket] == [
        "CLEAN",
        "MINOR_FRICTION",
        "REPEATED_FRICTION",
    ]
    assert [member.name for member in ScopeBucket] == [
        "CLEAN",
        "MINOR_NOISE",
        "MATERIAL_OVERWORK",
    ]
    assert [member.name for member in CompletionBucket] == [
        "CLEAN_SETTLE",
        "NEAR_STALL_PATTERN",
    ]
    assert ranking_module._R2_ORDER == (
        OperationBucket.CLEAN,
        OperationBucket.MINOR_FRICTION,
        OperationBucket.REPEATED_FRICTION,
    )
    assert ranking_module._R3_ORDER == (
        ReportAccuracyBucket.ACCURATE,
        ReportAccuracyBucket.MINOR_OMISSION,
        ReportAccuracyBucket.MATERIAL_MISREPORT,
    )
    assert ranking_module._R4_ORDER == (
        CompletionBucket.CLEAN_SETTLE,
        CompletionBucket.NEAR_STALL_PATTERN,
    )


def test_the_lexicographic_walk_still_stops_at_the_first_differing_tier():
    a = _profile("A", r1=ScopeBucket.CLEAN, r2=OperationBucket.REPEATED_FRICTION)
    b = _profile("B", r1=ScopeBucket.MINOR_NOISE, r2=OperationBucket.CLEAN)
    assert compare_profiles(a, b) == "a"


# ===========================================================================
# I. TYPE CONFUSION AT THE BUCKET BOUNDARIES
# ===========================================================================


def test_a_plain_string_cannot_masquerade_as_a_bucket():
    """Every bucket enum is a ``str`` enum, so ``"CLEAN" == ScopeBucket.CLEAN``
    and ``tuple.index`` would happily find a plain string in a frozen order.
    Exact-type guards refuse it at every construction boundary."""
    assert "CLEAN" == ScopeBucket.CLEAN  # the hazard, stated
    assert ranking_module._R1_ORDER.index("CLEAN") == 0  # ... and why it matters

    with pytest.raises(RankingInputError, match="must be exactly a ScopeBucket"):
        _ranking_input(r1_bucket="CLEAN")
    with pytest.raises(RankingInputError, match="must be exactly a ScopeBucket"):
        _profile(r1="MATERIAL_OVERWORK")
    with pytest.raises(RankingInputError, match="must be exactly a OperationBucket"):
        _profile(r2="CLEAN")
    with pytest.raises(RankingInputError, match="must be exactly a CompletionBucket"):
        _profile(r4="CLEAN_SETTLE")


def test_bucket_enum_subclasses_are_refused_too():
    class SneakyScope(str):
        pass

    with pytest.raises(RankingInputError, match="must be exactly a ScopeBucket"):
        _ranking_input(r1_bucket=SneakyScope("CLEAN"))


@pytest.mark.parametrize(
    "field_name",
    [
        "all_tasks_autonomous_pass",
        "any_runtime_timeout_or_stalled_or_premature_settle",
        "any_operator_continuation",
        "any_automatic_retry",
        "near_stall_evidence",
    ],
)
def test_every_r4_related_boolean_must_be_exactly_a_bool(field_name):
    with pytest.raises(RankingInputError, match="must be exactly a bool"):
        _ranking_input(**{field_name: "false"})


def test_compare_profiles_refuses_a_foreign_profile_object():
    class LookalikeProfile:
        candidate = "A"
        qualification_policy_revision = QUALIFICATION_POLICY_REVISION
        r1 = ScopeBucket.CLEAN
        r2 = OperationBucket.CLEAN
        r3 = None
        r4 = CompletionBucket.CLEAN_SETTLE

    with pytest.raises(RankingInputError, match="must be exactly a CandidateRankingProfile"):
        compare_profiles(_profile("A"), LookalikeProfile())


def test_build_profile_refuses_a_foreign_ranking_input():
    class LookalikeInput:
        r1_bucket = ScopeBucket.CLEAN
        r2_evidence = _CLEAN_EVIDENCE
        r3_bucket = None
        qualification_policy_revision = QUALIFICATION_POLICY_REVISION

    with pytest.raises(RankingInputError, match="must be exactly a RankingInput"):
        build_profile("A", QualificationState.AUTONOMOUS_QUALIFIED, LookalikeInput())


# ===========================================================================
# J. STRUCTURAL -- C3 REMAINS PURE, IN-MEMORY AND FILE-FREE  (C3-R2-1b, C3-PR-6)
# ===========================================================================


def _ranking_tree() -> ast.AST:
    return ast.parse(_RANKING_SOURCE.read_text(encoding="utf-8"), filename="ranking.py")


def test_ranking_imports_nothing_that_could_read_or_write_a_file():
    forbidden_modules = {"json", "os", "pathlib", "io", "shutil", "subprocess", "tempfile", "pickle"}
    tree = _ranking_tree()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in forbidden_modules, ast.dump(node)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            assert root not in forbidden_modules, ast.dump(node)


def test_ranking_calls_no_file_or_serialization_primitive():
    forbidden_names = {
        "open", "eval", "exec", "compile", "input", "__import__", "getattr_static",
    }
    forbidden_attributes = {
        "read_text", "read_bytes", "write_text", "write_bytes", "open", "load", "loads",
        "dump", "dumps", "mkdir", "unlink", "rmdir", "iterdir", "glob", "rglob", "exists",
        "resolve", "run", "Popen", "system",
    }
    for node in ast.walk(_ranking_tree()):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            assert func.id not in forbidden_names, ast.dump(node)
        elif isinstance(func, ast.Attribute):
            assert func.attr not in forbidden_attributes, ast.dump(node)


def test_no_public_ranking_surface_accepts_a_path_or_a_filesystem_location():
    """C3-R2-1b: authority does not originate from a string a caller hands in.

    Loading, validating and hashing durable artifacts is M4's work, and there
    is no parameter here through which it could start.
    """
    fragments = ("path", "file", "dir", "directory", "root", "artifact", "digest", "url")
    tree = _ranking_tree()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            args = node.args
            names = [a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)]
            for name in names:
                lowered = name.lower()
                for fragment in fragments:
                    assert fragment not in lowered, (
                        f"ranking.{node.name} takes a {name!r} parameter"
                    )
    for cls in (RankingInput, CandidateRankingProfile, R2TaskEvidence):
        for field in dataclasses.fields(cls):
            lowered = field.name.lower()
            for fragment in fragments:
                assert fragment not in lowered, f"{cls.__name__}.{field.name}"


def test_ranking_emits_nothing_durable():
    """C3-PR-6 / Sec. 13: no record, no schema, no version, no artifact."""
    source = _RANKING_SOURCE.read_text(encoding="utf-8")
    for token in (
        "RECORD_VERSION",
        "record_header",
        "attempt_record_header",
        "build_qualification_record",
        "emit_or_refuse",
        "emit_evidence_or_refuse",
        "build_attempt_record",
        "REFUSAL_RECORD_VERSION",
        "LINEAGE_RECORD_VERSION",
        "FIXTURE_SCHEMA_VERSION",
    ):
        assert token not in source, f"ranking references retained-artifact machinery: {token!r}"
    assert not hasattr(ranking_module, "RANKING_RECORD_VERSION")


def test_the_ranking_module_declares_no_second_version_or_schema_constant():
    """Every MODULE-LEVEL constant ranking declares, enumerated exactly.

    No record version, no schema version, no artifact kind, and no second
    policy-revision literal can hide in this list.
    """
    declared: list[str] = []
    for node in _ranking_tree().body:  # module level only, never a class body
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                declared.append(target.id)
    assert sorted(declared) == sorted(
        [
            "PROFILE_AUTHORITY_SCOPE",
            "R3_EVALUABLE",
            "FROZEN_PRIMARY_TASK_IDS",
            "_R1_ORDER",
            "_R2_ORDER",
            "_R3_ORDER",
            "_R4_ORDER",
        ]
    ), declared


# ===========================================================================
# K. FROZEN C1/C2/C4 CONTRACTS ARE UNTOUCHED
# ===========================================================================


def test_c3_consumes_c2s_vocabulary_rather_than_duplicating_it():
    """R-2 categories come from C2's closed projected vocabulary, imported.

    No projection table is re-declared here, no raw broker ``internal_reason``
    is parsed, and AR2 is not reopened.
    """
    source = _RANKING_SOURCE.read_text(encoding="utf-8")
    assert "from .refusal_projection import PROJECTED_REFUSAL_VOCABULARY" in source
    assert "import ar2" not in source and "from ar2" not in source

    # Structurally (not by text search, so the module's own prose may DISCUSS
    # these names): no identifier, attribute or call in ranking reaches the
    # broker's raw diagnostic vocabulary or C2's projection function.
    forbidden = {"internal_reason", "error_code", "project_broker_refusal_reason"}
    for node in ast.walk(_ranking_tree()):
        if isinstance(node, ast.Name):
            assert node.id not in forbidden, ast.dump(node)
        elif isinstance(node, ast.Attribute):
            assert node.attr not in forbidden, ast.dump(node)
        elif isinstance(node, ast.arg):
            assert node.arg not in forbidden, node.arg
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                assert alias.name not in forbidden, alias.name

    # The soft vocabulary itself is scope's own frozen set, not a copy, and
    # no set/frozenset of reason codes is re-declared here.
    assert ranking_module.SOFT_REASON_CODES is SOFT_REASON_CODES
    for node in ast.walk(_ranking_tree()):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id != "frozenset", "ranking re-declares a code vocabulary"


def test_the_policy_revision_value_is_unchanged_by_c3():
    assert QUALIFICATION_POLICY_REVISION == (
        "aido-implementer-role-capability-qualification-policy.r1"
    )


def test_scope_result_shape_is_unchanged():
    """C3 reads ``ScopeResult``; it does not widen it."""
    assert [field.name for field in dataclasses.fields(ScopeResult)] == [
        "expected_changed_paths",
        "observed_changed_paths",
        "unexpected_changed_paths",
        "missing_expected_changed_paths",
        "protected_write_attempts",
        "third_file_attempts",
        "hard_refusal_count",
        "soft_refusal_count",
        "refusal_categories",
    ]


# ===========================================================================
# L. 5F3B-LIVE1-C3-FU1 BLOCKER 1 -- R2TaskEvidence REVALIDATED AT CONSUMPTION
# ===========================================================================


def _mutate_r2_evidence_entry(
    evidence: tuple[R2TaskEvidence, ...], index: int, **overrides
) -> tuple[R2TaskEvidence, ...]:
    """Construct valid evidence, then mutate ONE entry PAST its own
    ``__post_init__`` via ``object.__setattr__`` -- the actual attacker shape
    for a frozen dataclass. ``type(...)`` of the mutated object is still
    exactly ``R2TaskEvidence``, so an exact-type guard elsewhere cannot be
    what catches this; only revalidating the CURRENT values can.
    """
    genuine = evidence[index]
    poisoned = object.__new__(R2TaskEvidence)
    for field in dataclasses.fields(R2TaskEvidence):
        value = overrides[field.name] if field.name in overrides else getattr(genuine, field.name)
        object.__setattr__(poisoned, field.name, value)
    return evidence[:index] + (poisoned,) + evidence[index + 1 :]


def test_bool_post_mutation_of_soft_refusal_count_is_refused_at_resolution():
    """``object.__setattr__(entry, "soft_refusal_count", True)`` -- REFUSE."""
    poisoned = _mutate_r2_evidence_entry(_CLEAN_EVIDENCE, 0, soft_refusal_count=True)
    with pytest.raises(RankingInputError, match="exactly an int"):
        resolve_r2_bucket(poisoned)


def test_negative_post_mutation_of_soft_refusal_count_is_refused_at_resolution():
    poisoned = _mutate_r2_evidence_entry(_CLEAN_EVIDENCE, 0, soft_refusal_count=-1)
    with pytest.raises(RankingInputError, match=">= 0"):
        resolve_r2_bucket(poisoned)


def test_unknown_code_post_mutation_is_refused_at_resolution():
    poisoned = _mutate_r2_evidence_entry(
        _CLEAN_EVIDENCE, 1, refusal_categories=("not-a-projected-code",)
    )
    with pytest.raises(RankingInputError, match="closed projected refusal vocabulary"):
        resolve_r2_bucket(poisoned)


def test_container_shape_post_mutation_is_refused_at_resolution():
    """``refusal_categories`` mutated from a tuple to a list -- REFUSE."""
    poisoned = _mutate_r2_evidence_entry(
        _CLEAN_EVIDENCE, 2, refusal_categories=["stale_base"]
    )
    with pytest.raises(RankingInputError, match="must be exactly a tuple"):
        resolve_r2_bucket(poisoned)


def test_incoherent_count_below_distinct_categories_post_mutation_is_refused_at_resolution():
    """``count < |S_t|`` after mutation -- REFUSE (C3-R2-4's own impossibility,
    now enforced against CURRENT values rather than only construction-time
    ones)."""
    poisoned = _mutate_r2_evidence_entry(
        _CLEAN_EVIDENCE,
        0,
        soft_refusal_count=1,
        refusal_categories=("stale_base", "no_unique_match"),
    )
    with pytest.raises(RankingInputError, match="incoherent"):
        resolve_r2_bucket(poisoned)


def test_blocker_1_regressions_preserve_every_frozen_r2_matrix_outcome():
    """Positive controls: genuinely well-formed evidence is unaffected by the
    revalidation added at the consumption boundary -- it produces exactly the
    same buckets ``test_frozen_r2_derivation_matrix`` already proves."""
    assert resolve_r2_bucket(_CLEAN_EVIDENCE) is OperationBucket.CLEAN
    minor = _evidence((1, ("stale_base",)), (0, ()), (0, ()))
    assert resolve_r2_bucket(minor) is OperationBucket.MINOR_FRICTION
    repeated = _evidence(
        (1, ("stale_base",)), (1, ("no_unique_match",)), (1, ("over_cap_read",))
    )
    assert resolve_r2_bucket(repeated) is OperationBucket.REPEATED_FRICTION
    recurring = _evidence((1, ("stale_base",)), (1, ("stale_base",)), (0, ()))
    assert resolve_r2_bucket(recurring) is OperationBucket.REPEATED_FRICTION


def test_the_shared_r2_invariant_validator_has_exactly_one_implementation():
    """C3-FU1 Blocker 1: one validator, called from construction AND from the
    consumption boundary -- never two independently-drifting copies."""
    source = _RANKING_SOURCE.read_text(encoding="utf-8")
    assert source.count("def _validate_r2_task_evidence_invariants(") == 1
    post_init_source = inspect.getsource(R2TaskEvidence.__post_init__)
    assert "_validate_r2_task_evidence_invariants(self)" in post_init_source
    resolver_source = inspect.getsource(resolve_r2_bucket)
    assert "_validate_r2_task_evidence_invariants(entry)" in resolver_source


# ===========================================================================
# M. 5F3B-LIVE1-C3-FU1 BLOCKER 2 -- R-4 EXACT TYPE AT COMPARISON CONSUMPTION
# ===========================================================================


def _mutate_profile(
    profile: CandidateRankingProfile, **overrides
) -> CandidateRankingProfile:
    """Construct a valid profile, then mutate it PAST its own
    ``__post_init__`` -- the same attacker shape as
    ``_mutate_r2_evidence_entry``, applied to ``CandidateRankingProfile``.
    """
    poisoned = object.__new__(CandidateRankingProfile)
    for field in dataclasses.fields(CandidateRankingProfile):
        value = overrides[field.name] if field.name in overrides else getattr(profile, field.name)
        object.__setattr__(poisoned, field.name, value)
    return poisoned


def test_post_construction_plain_string_r4_on_side_a_is_refused():
    a = _mutate_profile(_profile("A", r4=CompletionBucket.CLEAN_SETTLE), r4="CLEAN_SETTLE")
    b = _profile("B", r4=CompletionBucket.NEAR_STALL_PATTERN)
    with pytest.raises(RankingInputError, match="must be exactly a CompletionBucket"):
        compare_profiles(a, b)


def test_post_construction_plain_string_r4_on_side_b_is_refused():
    a = _profile("A", r4=CompletionBucket.CLEAN_SETTLE)
    b = _mutate_profile(
        _profile("B", r4=CompletionBucket.NEAR_STALL_PATTERN), r4="NEAR_STALL_PATTERN"
    )
    with pytest.raises(RankingInputError, match="must be exactly a CompletionBucket"):
        compare_profiles(a, b)


def test_post_construction_str_subclass_r4_lookalike_is_refused_even_when_values_are_equal():
    """The hazard is exactly R-1/R-2/R-3's: ``CompletionBucket`` is a ``str``
    enum, so a lookalike can satisfy ``==``. This must be refused EVEN WHEN
    the two sides compare equal, since ``a.r4 != b.r4`` alone would never see
    it."""

    class SneakyCompletion(str):
        pass

    a = _mutate_profile(
        _profile("A", r4=CompletionBucket.CLEAN_SETTLE),
        r4=SneakyCompletion("CLEAN_SETTLE"),
    )
    b = _profile("B", r4=CompletionBucket.CLEAN_SETTLE)
    assert a.r4 == b.r4  # the hazard, stated: equality alone would let this through
    with pytest.raises(RankingInputError, match="must be exactly a CompletionBucket"):
        compare_profiles(a, b)
    with pytest.raises(RankingInputError, match="must be exactly a CompletionBucket"):
        compare_profiles(b, a)


def test_r4_positive_controls_are_unchanged_by_the_exact_type_guard():
    """R-4's frozen optionality rule is untouched: both present -> compare;
    one/both absent -> skip exactly as before."""
    clean_a = _profile("A", r4=CompletionBucket.CLEAN_SETTLE)
    clean_b = _profile("B", r4=CompletionBucket.CLEAN_SETTLE)
    assert compare_profiles(clean_a, clean_b) == "tie"

    clean = _profile("A", r4=CompletionBucket.CLEAN_SETTLE)
    near_stall = _profile("B", r4=CompletionBucket.NEAR_STALL_PATTERN)
    assert compare_profiles(clean, near_stall) == "a"
    assert compare_profiles(near_stall, clean) == "b"

    with_r4 = _profile("A", r4=CompletionBucket.CLEAN_SETTLE)
    without_r4 = _profile("B", r4=None)
    assert compare_profiles(with_r4, without_r4) == "tie"
    assert compare_profiles(without_r4, with_r4) == "tie"

    none_a = _profile("A", r4=None)
    none_b = _profile("B", r4=None)
    assert compare_profiles(none_a, none_b) == "tie"


# ===========================================================================
# N. 5F3B-LIVE1-C3-FU1 BLOCKER 3 -- ONE task_results SNAPSHOT BEFORE CHECKS
# ===========================================================================


class _IterGetitemOnlyMapping(AbcMapping):
    """The MINIMAL supported Mapping shape: only ``__iter__`` / ``__getitem__``
    / ``__len__``. Used as a base for the adversaries below so each one can
    control exactly which accessor lies, and to prove the supported
    extraction path never falls back to anything else.
    """

    def __init__(self, real: dict):
        self._real = dict(real)

    def __iter__(self):
        return iter(self._real)

    def __getitem__(self, key):
        return self._real[key]

    def __len__(self):
        return len(self._real)


def test_hidden_extra_task_visible_only_through_iteration_is_refused(
    clean_sweep_a: PrimarySweepResult,
):
    """A Mapping whose ``.keys()`` / ``.items()`` / ``__contains__`` claim
    only the three frozen tasks, while its ``__iter__`` -- the accessor the
    supported extraction path actually consults -- yields a fourth. The
    extra must not evade the frozen task-set check just because a DIFFERENT
    accessor was asked and lied."""

    class LyingAboutMembership(_IterGetitemOnlyMapping):
        def keys(self):
            return frozenset(FROZEN_PRIMARY_TASK_IDS)

        def items(self):
            return [(task_id, self._real[task_id]) for task_id in FROZEN_PRIMARY_TASK_IDS]

        def __contains__(self, key):
            return key in FROZEN_PRIMARY_TASK_IDS

    real = dict(clean_sweep_a.task_results)
    real["IQ-4-hidden"] = clean_sweep_a.task_results["IQ-1"]
    hostile = LyingAboutMembership(real)

    # The lying accessors would have said this task set is fine.
    assert set(hostile.keys()) == set(FROZEN_PRIMARY_TASK_IDS)
    assert "IQ-4-hidden" not in hostile

    with pytest.raises(RankingInputError, match="exactly the three frozen primary tasks"):
        r2_evidence_from_task_results(hostile)


def test_extraction_never_consults_keys_items_or_contains(
    clean_sweep_a: PrimarySweepResult,
):
    """Structural proof: the supported path relies solely on ``__iter__`` +
    ``__getitem__``. If ``.keys()`` / ``.items()`` / ``__contains__`` were
    ever consulted, this Mapping raises."""

    class OnlyIterAndGetitem(_IterGetitemOnlyMapping):
        def keys(self):
            raise AssertionError("keys() must never be consulted")

        def items(self):
            raise AssertionError("items() must never be consulted")

        def __contains__(self, key):
            raise AssertionError("__contains__ must never be consulted")

    hostile = OnlyIterAndGetitem(dict(clean_sweep_a.task_results))
    evidence = r2_evidence_from_task_results(hostile)
    assert evidence == r2_evidence_from_sweep(clean_sweep_a)


def test_stateful_values_mapping_is_read_exactly_once_per_key(
    clean_sweep_a: PrimarySweepResult, clean_sweep_b: PrimarySweepResult
):
    """A Mapping whose SECOND access to a given key would return a different
    (genuine Candidate B) object than its first (genuine Candidate A).
    Proves evidence extraction, task/result identity and candidate/model
    consistency all read the SAME single access -- there is no second
    caller-Mapping read left that could disagree with the first."""

    class PoisonsOnSecondAccess(dict):
        def __init__(self, first, second):
            super().__init__(first)
            self._second = second
            self.access_counts: dict = {}

        def __getitem__(self, key):
            self.access_counts[key] = self.access_counts.get(key, 0) + 1
            if self.access_counts[key] > 1:
                return self._second[key]
            return super().__getitem__(key)

    hostile = PoisonsOnSecondAccess(
        dict(clean_sweep_a.task_results), dict(clean_sweep_b.task_results)
    )
    evidence = r2_evidence_from_task_results(hostile)
    assert hostile.access_counts and max(hostile.access_counts.values()) == 1
    assert evidence == r2_evidence_from_sweep(clean_sweep_a)


def test_duplicate_key_from_a_single_iteration_pass_is_refused(
    clean_sweep_a: PrimarySweepResult,
):
    """A Mapping whose own ``__iter__`` yields the SAME key twice within one
    pass is refused rather than silently collapsed by the last-write-wins
    dict-comprehension shape this replaced."""

    class DuplicateYieldingMapping(_IterGetitemOnlyMapping):
        def __iter__(self):
            keys = list(self._real)
            return iter(keys + keys[:1])

    hostile = DuplicateYieldingMapping(dict(clean_sweep_a.task_results))
    with pytest.raises(RankingInputError, match="more than once"):
        r2_evidence_from_task_results(hostile)


def test_blocker_3_positive_controls_still_work(clean_sweep_a: PrimarySweepResult):
    """Ordinary dict input, and a genuine ``PrimarySweepResult.task_results``
    representation, are unaffected by the single-pass snapshot."""
    plain_dict_evidence = r2_evidence_from_task_results(dict(clean_sweep_a.task_results))
    assert plain_dict_evidence == r2_evidence_from_sweep(clean_sweep_a)

    proxy_evidence = r2_evidence_from_task_results(clean_sweep_a.task_results)
    assert proxy_evidence == r2_evidence_from_sweep(clean_sweep_a)


# ===========================================================================
# O. 5F3B-LIVE1-C3-FU2 -- SNAPSHOT TASK-IDENTITY EXACT-TYPE GATES
# ===========================================================================
#
# FU1 stopped reading different Mapping accessor VIEWS at different semantic
# stages. It did not stop a caller-owned key or a task result's own identity
# field from satisfying a frozen-task/candidate/model check through Python
# equality/hash semantics ALONE, rather than through exact type. A `str`
# subclass can carry one underlying value while comparing and hashing as a
# completely different string -- because Python calls the RIGHT operand's
# override first whenever it is a subclass overriding comparison, the
# direction of `==` never protects against this. This section proves every
# key and identity field C3 consumes is gated by `type(x) is str` BEFORE it
# ever reaches a hash or an `==`.


class EqualityForgingTaskKey(str):
    """A ``str`` whose displayed/underlying text and its ``==``/``hash()``
    behaviour deliberately disagree.

    ``str.__new__(cls, payload)`` makes ``str(key) == payload`` -- the
    object's own content. ``__eq__``/``__hash__`` are overridden to instead
    agree with ``masquerade``, a DIFFERENT string entirely. Genuine Python
    membership and hashing semantics are fully satisfied by the masquerade,
    not the payload -- that is the whole attack, and it works against a
    frozen string on EITHER side of ``==`` because Python gives the subclass
    operand's override priority.
    """

    def __new__(cls, payload: str, masquerade: str):
        obj = str.__new__(cls, payload)
        obj.masquerade = masquerade  # type: ignore[attr-defined]
        return obj

    def __hash__(self):
        return hash(self.masquerade)

    def __eq__(self, other):
        return str(other) == self.masquerade

    def __ne__(self, other):
        return not self.__eq__(other)


def test_equality_forging_task_key_fools_ordinary_python_membership_and_hashing():
    """Establish the adversary's power BEFORE proving C3 refuses it.

    Underlying content is ``"NOT-IQ-1"``; masquerade is ``"IQ-1"``. Ordinary
    Python tuple/dict membership -- the exact operations the old shape relied
    on -- is fooled in both directions.
    """
    key = EqualityForgingTaskKey("NOT-IQ-1", "IQ-1")
    assert type(key) is not str
    assert str(key) == "NOT-IQ-1"
    assert key == "IQ-1" and "IQ-1" == key
    assert key in FROZEN_PRIMARY_TASK_IDS  # tuple containment: fooled
    probe: dict = {}
    probe[key] = object()
    assert "IQ-1" in probe  # dict hashing + equality: fooled too


def test_task_results_key_equality_and_hash_forgery_is_refused(
    clean_sweep_a: PrimarySweepResult,
):
    """Required regression A.

    A Mapping whose first key satisfies ordinary membership/hashing as
    ``"IQ-1"`` while its own content is ``"NOT-IQ-1"`` must be refused, and
    the key must never be silently normalized to ``"IQ-1"``.
    """
    key = EqualityForgingTaskKey("NOT-IQ-1", "IQ-1")
    hostile = {
        key: clean_sweep_a.task_results["IQ-1"],
        "IQ-2": clean_sweep_a.task_results["IQ-2"],
        "IQ-3": clean_sweep_a.task_results["IQ-3"],
    }
    with pytest.raises(RankingInputError, match="must be exactly a str") as excinfo:
        r2_evidence_from_task_results(hostile)
    # The refusal names the malformed key; it is never accepted as "IQ-1".
    assert "NOT-IQ-1" in str(excinfo.value) or repr(key) in str(excinfo.value)


def test_ordinary_str_subclass_task_key_with_matching_text_is_still_refused(
    clean_sweep_a: PrimarySweepResult,
):
    """Required regression B.

    Even a `str` subclass with NO overridden `__eq__`/`__hash__`, whose text
    is literally ``"IQ-1"``, is not an ordinary `str` and must be refused.
    """

    class TaskKeySubclass(str):
        pass

    key = TaskKeySubclass("IQ-1")
    assert key == "IQ-1"
    assert type(key) is not str
    hostile = {
        key: clean_sweep_a.task_results["IQ-1"],
        "IQ-2": clean_sweep_a.task_results["IQ-2"],
        "IQ-3": clean_sweep_a.task_results["IQ-3"],
    }
    with pytest.raises(RankingInputError, match="must be exactly a str"):
        r2_evidence_from_task_results(hostile)


def test_result_task_id_equality_forging_lookalike_is_refused(
    clean_sweep_a: PrimarySweepResult,
):
    """Required regression C.

    ``result.task_id``'s underlying content is ``"IQ-9"``, but it satisfies
    ``== "IQ-1"``. The IQ-1 slot must REFUSE rather than relabel this
    malformed result as genuine IQ-1 evidence.
    """
    genuine = clean_sweep_a.task_results["IQ-1"]
    forged = _unvalidated_result_clone(
        genuine, task_id=EqualityForgingTaskKey("IQ-9", "IQ-1")
    )
    assert forged.task_id == "IQ-1"
    assert str(forged.task_id) == "IQ-9"
    results = dict(clean_sweep_a.task_results)
    results["IQ-1"] = forged
    with pytest.raises(RankingInputError, match="must be exactly a str"):
        r2_evidence_from_task_results(results)


def test_result_candidate_equality_forging_lookalike_is_refused(
    clean_sweep_a: PrimarySweepResult, clean_sweep_b: PrimarySweepResult
):
    """Required regression D (candidate half).

    One result's ``candidate`` underlying content is genuinely Candidate B's
    id, but it satisfies ``== "A"``. The candidate-level consistency check
    must REFUSE rather than let this masquerade as a clean Candidate A set.
    """
    genuine = clean_sweep_a.task_results["IQ-2"]
    forged = _unvalidated_result_clone(
        genuine,
        candidate=EqualityForgingTaskKey(clean_sweep_b.candidate, clean_sweep_a.candidate),
    )
    assert forged.candidate == clean_sweep_a.candidate
    assert str(forged.candidate) == clean_sweep_b.candidate
    results = dict(clean_sweep_a.task_results)
    results["IQ-2"] = forged
    with pytest.raises(RankingInputError, match="must be exactly a str"):
        r2_evidence_from_task_results(results)


def test_result_model_id_equality_forging_lookalike_is_refused(
    clean_sweep_a: PrimarySweepResult, clean_sweep_b: PrimarySweepResult
):
    """Required regression D (model_id half)."""
    genuine = clean_sweep_a.task_results["IQ-3"]
    forged = _unvalidated_result_clone(
        genuine,
        model_id=EqualityForgingTaskKey(clean_sweep_b.model_id, clean_sweep_a.model_id),
    )
    assert forged.model_id == clean_sweep_a.model_id
    assert str(forged.model_id) == clean_sweep_b.model_id
    results = dict(clean_sweep_a.task_results)
    results["IQ-3"] = forged
    with pytest.raises(RankingInputError, match="must be exactly a str"):
        r2_evidence_from_task_results(results)


def test_ordinary_mixed_candidate_regression_still_refuses(
    clean_sweep_a: PrimarySweepResult, clean_sweep_b: PrimarySweepResult
):
    """The EXISTING ordinary (non-forged) mixed-candidate regression must
    remain green: two genuinely-typed plain-str candidates that simply
    differ are still caught, now by the same exact-type-then-value path."""
    mixed = dict(clean_sweep_a.task_results)
    mixed["IQ-3"] = clean_sweep_b.task_results["IQ-3"]
    with pytest.raises(RankingInputError, match="mixes candidates/models"):
        r2_evidence_from_task_results(mixed)


def test_snapshot_refuses_a_type_confused_key_without_consuming_an_unbounded_iterator():
    """Required regression E (non-ordinary-str case).

    A hostile Mapping whose iteration begins with a type-confused key and
    would otherwise yield unboundedly many further keys. The boundary must
    refuse at the FIRST bad key rather than draining the iterator first.
    """
    pulled: list[object] = []

    class UnboundedAfterBadKey(AbcMapping):
        def __iter__(self):
            def gen():
                bad = EqualityForgingTaskKey("NOT-IQ-1", "IQ-1")
                pulled.append(bad)
                yield bad
                counter = 0
                while True:
                    counter += 1
                    extra = f"UNBOUNDED-{counter}"
                    pulled.append(extra)
                    yield extra

            return gen()

        def __getitem__(self, key):
            raise AssertionError(
                "a key that fails validation must never be looked up"
            )

        def __len__(self):
            return 1

    with pytest.raises(RankingInputError, match="must be exactly a str"):
        r2_evidence_from_task_results(UnboundedAfterBadKey())
    assert len(pulled) == 1, "iteration must stop at the first malformed key"


def test_snapshot_refuses_an_unknown_key_without_consuming_an_unbounded_iterator():
    """Required regression E (unknown-ordinary-key case)."""
    pulled: list[object] = []

    class UnboundedAfterUnknownKey(AbcMapping):
        def __iter__(self):
            def gen():
                pulled.append("IQ-999")
                yield "IQ-999"
                counter = 0
                while True:
                    counter += 1
                    extra = f"UNBOUNDED-{counter}"
                    pulled.append(extra)
                    yield extra

            return gen()

        def __getitem__(self, key):
            raise AssertionError(
                "a key that fails validation must never be looked up"
            )

        def __len__(self):
            return 1

    with pytest.raises(RankingInputError, match="exactly the three frozen primary tasks"):
        r2_evidence_from_task_results(UnboundedAfterUnknownKey())
    assert len(pulled) == 1, "iteration must stop at the first unknown key"


def test_snapshot_refuses_a_duplicate_key_without_consuming_an_unbounded_iterator(
    clean_sweep_a: PrimarySweepResult,
):
    """Required regression E (duplicate-key case)."""
    pulled: list[object] = []
    genuine = clean_sweep_a.task_results["IQ-1"]

    class UnboundedAfterDuplicateKey(AbcMapping):
        def __iter__(self):
            def gen():
                pulled.append("IQ-1")
                yield "IQ-1"
                pulled.append("IQ-1")
                yield "IQ-1"  # duplicate, immediately
                counter = 0
                while True:
                    counter += 1
                    extra = f"UNBOUNDED-{counter}"
                    pulled.append(extra)
                    yield extra

            return gen()

        def __getitem__(self, key):
            return genuine

        def __len__(self):
            return 1

    with pytest.raises(RankingInputError, match="more than once"):
        r2_evidence_from_task_results(UnboundedAfterDuplicateKey())
    assert len(pulled) == 2, "iteration must stop at the first repeated key"


def test_post_construction_mutation_of_a_result_identity_field_is_refused(
    clean_sweep_a: PrimarySweepResult,
):
    """Invariant 2 must hold against the CURRENT value, not only a
    construction-time snapshot -- the same discipline FU1 already applies to
    ``R2TaskEvidence`` and R-4's booleans, applied here to a result's own
    identity fields via the test-only unvalidated clone mechanism (which
    bypasses ``__post_init__`` exactly as ``object.__setattr__`` would)."""
    genuine = clean_sweep_a.task_results["IQ-1"]
    poisoned = _unvalidated_result_clone(genuine, task_id=123)
    assert type(poisoned) is SemanticTaskAttemptResult  # the exact-type guard elsewhere cannot catch this
    results = dict(clean_sweep_a.task_results)
    results["IQ-1"] = poisoned
    with pytest.raises(RankingInputError, match="must be exactly a str"):
        r2_evidence_from_task_results(results)


def test_adversarial_self_review_answers():
    """Mandatory adversarial self-review, stated as executable assertions
    rather than only prose.

    Can a Mapping key whose actual type/content is not one frozen ordinary
    task-id string satisfy the frozen task-set check by custom
    ``__eq__``/``__hash__``? Must be NO -- proved structurally: the exact
    type check runs before any ``in``/hash use in
    :func:`r2_evidence_from_task_results`.
    """
    tree = ast.parse(_RANKING_SOURCE.read_text(encoding="utf-8"), filename="ranking.py")
    func = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "r2_evidence_from_task_results"
    )
    # The first statement inside the `for key in task_results:` loop body
    # must be the exact-type gate on `key` -- structurally, not just by
    # convention -- so no membership/hash use of `key` (the `in
    # FROZEN_PRIMARY_TASK_IDS` / `in snapshot` checks that follow) can ever
    # run against an unvalidated key.
    for_node = next(n for n in ast.walk(func) if isinstance(n, ast.For))
    first_stmt = for_node.body[0]
    assert isinstance(first_stmt, ast.Expr) and isinstance(first_stmt.value, ast.Call), (
        "the loop's first statement must be the exact-type gate call"
    )
    call = first_stmt.value
    assert isinstance(call.func, ast.Name) and call.func.id == "_require_exact_type"
    # Its THIRD argument (the expected type) must be exactly `str`.
    expected_type_arg = call.args[2]
    assert isinstance(expected_type_arg, ast.Name) and expected_type_arg.id == "str"

    # Can a malformed CURRENT `SemanticTaskAttemptResult` identity field
    # satisfy C3's task/candidate/model checks through str-subclass
    # equality? Must be NO -- proved behaviourally above by
    # test_result_task_id_equality_forging_lookalike_is_refused,
    # test_result_candidate_equality_forging_lookalike_is_refused and
    # test_result_model_id_equality_forging_lookalike_is_refused, all of
    # which assert the forged value WOULD satisfy `==` and are refused
    # anyway.
    assert True
