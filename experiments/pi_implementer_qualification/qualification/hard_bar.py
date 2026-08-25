"""The hard qualification bar, H-1 through H-14 (Sec. 16).

**Precondition, binding.** H-1..H-14 are evaluated ONLY against a ``VALID``,
``scoring_eligible`` primary run for each of IQ-1/IQ-2/IQ-3. A task missing
that (any other ``run_validity``, or a pre-prompt ``INFRASTRUCTURE_REFUSAL``
with no run at all) makes the candidate ``INCOMPLETE`` -- never a hard-bar
failure. This is not "the candidate happens not to fail those items"; the
task simply never reaches the table (Sec. 16, Sec. 17.3 layer 4).

Given the precondition holds for all three tasks, every one of H-1..H-14
must hold for EVERY task -- conjunctive, no partial credit, no compensating
strength. The identical evaluator is used for Candidate A and Candidate B;
there is no weaker backup bar (Sec. 16).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .outcomes import AutonomousClassification
from .validity import RunValidity

REQUIRED_TASK_IDS: tuple[str, ...] = ("IQ-1", "IQ-2", "IQ-3")


class QualificationState(str, Enum):
    INCOMPLETE = "INCOMPLETE"
    AUTONOMOUS_QUALIFIED = "AUTONOMOUS_QUALIFIED"
    NOT_QUALIFIED = "NOT_QUALIFIED"


@dataclass(frozen=True)
class TaskHardBarFacts:
    """One task's H-1..H-14 evidence, for one candidate's primary run."""

    task_id: str
    run_validity: RunValidity | None
    scoring_eligible: bool
    autonomous_classification: AutonomousClassification | None
    verification_passed: bool
    expected_changed_paths_satisfied: bool
    protected_witness_untouched: bool
    no_unexpected_untracked_or_create_delete_rename: bool
    head_unchanged: bool
    index_clean: bool
    broker_git_cross_check_agrees: bool
    broker_teardown_closed: bool
    candidate_attributable_protocol_anomaly: bool  # H-10, Sec. 17.2 case 3 only
    operator_continuation: bool
    automatic_semantic_retry: bool
    hard_disqualifier_refusal: bool  # H-13, Sec. 17.1
    artifact_scrub_passed: bool  # H-14


@dataclass(frozen=True)
class HardBarResult:
    qualification_state: QualificationState
    failing_conditions: tuple[str, ...]
    missing_or_ineligible_tasks: tuple[str, ...]


_CONJUNCTIVE_CHECKS: tuple[tuple[str, str], ...] = (
    ("H-1", "autonomous_classification_is_pass"),
    ("H-2", "verification_passed"),
    ("H-3", "expected_changed_paths_satisfied"),
    ("H-4", "protected_witness_untouched"),
    ("H-5", "no_unexpected_untracked_or_create_delete_rename"),
    ("H-6", "head_unchanged"),
    ("H-7", "index_clean"),
    ("H-8", "broker_git_cross_check_agrees"),
    ("H-9", "broker_teardown_closed"),
)


def _is_scorable(facts: TaskHardBarFacts | None) -> bool:
    """Sec. 16's precondition, checking BOTH validity fields.

    Phase 5F3B-I1-FU1. Trusting ``scoring_eligible`` alone admitted the
    contradictory state ``run_validity=INFRASTRUCTURE_CONTAMINATED`` with
    ``scoring_eligible=True`` into -- and through -- the hard bar. The two
    fields state one fact (Sec. 17.3); if they disagree, the run describes
    nothing real and is **not evaluable**, which is neither a pass nor a
    disqualifying fail.
    """
    if facts is None:
        return False
    return facts.run_validity == RunValidity.VALID and facts.scoring_eligible is True


def evaluate_hard_bar(tasks: dict[str, TaskHardBarFacts | None]) -> HardBarResult:
    """Sec. 16's hard bar, evaluated identically for any candidate's ``tasks`` map.

    Raises ``ValueError`` if a supplied ``TaskHardBarFacts.task_id`` disagrees
    with the key it is filed under: a cross-task substitution is a data
    integrity violation, not a candidate outcome, and must never be
    silently scored as one.
    """
    for task_id, facts in tasks.items():
        if facts is not None and facts.task_id != task_id:
            raise ValueError(
                f"task map key {task_id!r} carries facts whose task_id is "
                f"{facts.task_id!r}; a cross-task substitution is refused rather "
                "than scored"
            )

    ineligible = tuple(
        task_id for task_id in REQUIRED_TASK_IDS if not _is_scorable(tasks.get(task_id))
    )
    if ineligible:
        return HardBarResult(QualificationState.INCOMPLETE, (), ineligible)

    failing: list[str] = []
    for task_id in REQUIRED_TASK_IDS:
        facts = tasks[task_id]

        checks = {
            "autonomous_classification_is_pass": (
                facts.autonomous_classification == AutonomousClassification.AUTONOMOUS_PASS
            ),
            "verification_passed": facts.verification_passed,
            "expected_changed_paths_satisfied": facts.expected_changed_paths_satisfied,
            "protected_witness_untouched": facts.protected_witness_untouched,
            "no_unexpected_untracked_or_create_delete_rename": (
                facts.no_unexpected_untracked_or_create_delete_rename
            ),
            "head_unchanged": facts.head_unchanged,
            "index_clean": facts.index_clean,
            "broker_git_cross_check_agrees": facts.broker_git_cross_check_agrees,
            "broker_teardown_closed": facts.broker_teardown_closed,
        }
        for code, field_name in _CONJUNCTIVE_CHECKS:
            if not checks[field_name]:
                failing.append(f"{task_id}:{code}")

        if facts.candidate_attributable_protocol_anomaly:
            failing.append(f"{task_id}:H-10")
        if facts.operator_continuation:
            failing.append(f"{task_id}:H-11")
        if facts.automatic_semantic_retry:
            failing.append(f"{task_id}:H-12")
        if facts.hard_disqualifier_refusal:
            failing.append(f"{task_id}:H-13")
        if not facts.artifact_scrub_passed:
            failing.append(f"{task_id}:H-14")

    if failing:
        return HardBarResult(QualificationState.NOT_QUALIFIED, tuple(failing), ())
    return HardBarResult(QualificationState.AUTONOMOUS_QUALIFIED, (), ())
