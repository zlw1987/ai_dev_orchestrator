"""Run validity, kept strictly separate from autonomous classification (Sec. 17.3).

Design's five-layer model, restated here so this module's precondition is
explicit:

    1. artifact safety / emission validity   (records.py, H-14)
    2. run validity / attribution            (THIS MODULE)
    3. autonomous model classification       (outcomes.py, Sec. 8)
    4. hard-bar candidate qualification      (hard_bar.py, Sec. 16)
    5. ranking among qualified candidates    (ranking.py, Sec. 18)

``run_validity`` answers "is this run's evidence eligible to be scored at
all?" -- a question orthogonal to "what did the model do?" (layer 3) or "is
the candidate safe/correct?" (layer 4). Conflating the two produced the
internally contradictory earlier draft this section corrects (Sec. 17.3).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RunValidity(str, Enum):
    VALID = "VALID"
    INFRASTRUCTURE_CONTAMINATED = "INFRASTRUCTURE_CONTAMINATED"
    ATTRIBUTION_UNDETERMINED = "ATTRIBUTION_UNDETERMINED"
    INVALIDATED_BY_FIXTURE_DEFECT = "INVALIDATED_BY_FIXTURE_DEFECT"


@dataclass(frozen=True)
class ValidityResult:
    """``run_validity`` is ``None`` only for a pre-prompt infrastructure refusal,
    which is an earlier gate outcome and needs no run-validity value at all
    (Sec. 17.3). ``scoring_eligible`` is always present and is ``True`` if
    and only if ``run_validity == VALID``.

    That "if and only if" is enforced at construction (Phase 5F3B-I1-FU1):
    the two fields exist to state one fact for two different downstream
    consumers, so a :class:`ValidityResult` whose fields disagree describes
    nothing real and is refused rather than allowed to propagate into the
    hard bar.
    """

    run_validity: RunValidity | None
    scoring_eligible: bool

    def __post_init__(self) -> None:
        expected = self.run_validity == RunValidity.VALID
        if self.scoring_eligible is not expected:
            raise ValueError(
                "scoring_eligible must be true if and only if run_validity == VALID; got "
                f"run_validity={self.run_validity!r} with "
                f"scoring_eligible={self.scoring_eligible!r}"
            )


def resolve_run_validity(
    *,
    infrastructure_refusal: bool,
    semantic_prompts_sent: int,
    anomaly_attribution: str | None = None,
    fixture_defect: bool = False,
) -> ValidityResult:
    """Resolve ``run_validity``/``scoring_eligible`` from attribution facts.

    ``anomaly_attribution`` is one of ``"candidate"``, ``"infrastructure"``,
    ``"undetermined"``, or ``None`` (no anomaly at all) -- see
    :mod:`qualification.scope` Sec. 17.2's attribution ordering, which is
    what should have produced this value before it reaches here. This
    function does not itself decide attribution; it only turns an already-
    decided attribution into the corresponding ``run_validity``.
    """
    if infrastructure_refusal:
        if semantic_prompts_sent != 0:
            raise ValueError(
                "a pre-prompt infrastructure_refusal requires semantic_prompts_sent == 0"
            )
        return ValidityResult(run_validity=None, scoring_eligible=False)

    if semantic_prompts_sent != 1:
        raise ValueError(
            "a post-prompt run must truthfully report semantic_prompts_sent == 1, "
            "even when contaminated or attribution-undetermined"
        )

    if fixture_defect:
        return ValidityResult(RunValidity.INVALIDATED_BY_FIXTURE_DEFECT, False)

    if anomaly_attribution == "infrastructure":
        return ValidityResult(RunValidity.INFRASTRUCTURE_CONTAMINATED, False)
    if anomaly_attribution == "undetermined":
        return ValidityResult(RunValidity.ATTRIBUTION_UNDETERMINED, False)
    if anomaly_attribution not in (None, "candidate"):
        raise ValueError(f"unrecognized anomaly_attribution: {anomaly_attribution!r}")

    # No anomaly, or an anomaly mechanically attributed to the candidate
    # itself (Sec. 17.2 case 3): the run is ordinarily scorable.
    return ValidityResult(RunValidity.VALID, True)


def is_scorable(result: ValidityResult | None) -> bool:
    """Whether one task's run may enter hard-bar/ranking evaluation.

    Checks BOTH validity fields rather than trusting ``scoring_eligible``
    alone (Phase 5F3B-I1-FU1). :class:`ValidityResult` already refuses an
    inconsistent pair at construction, so this dual check is defense in
    depth -- but the hard bar is the one place where trusting a single
    field would silently admit a contaminated run, so it checks both here
    too rather than relying on a guarantee made somewhere else.
    """
    if result is None:
        return False
    return result.run_validity == RunValidity.VALID and result.scoring_eligible is True


def hard_bar_precondition_met(
    results: dict[str, ValidityResult], required_task_ids: tuple[str, ...]
) -> bool:
    """§16's precondition: one VALID, scoring-eligible primary result per task."""
    return all(is_scorable(results.get(task_id)) for task_id in required_task_ids)
