"""The autonomous outcome classifier (Phase 5F3B-I1, design Sec. 8 / Sec. 11).

A pure policy function over explicit, externally-observed facts. It never
infers repository truth from runtime prose, and it never derives a signal
from chain-of-thought or reasoning content (Sec. 11.1) -- ``RunFacts``
simply has no field that could carry either.

**Stall-detection boundary (Sec. 11.3, binding).** This module does not, and
must not, implement its own stall detector. ``RunFacts.stall_pattern_established``
is consumed as an already-decided external fact; no repeat count, timer, or
signature-matching heuristic is encoded here. No AIDO-owned telemetry source
that can set it ``True`` exists yet, so in the current system it is never
``True`` in a live run -- the offline suite exercises both branches by
supplying the value directly (Sec. 11.3's own required test shape), which is
not the same thing as this module inventing a threshold.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AutonomousClassification(str, Enum):
    """Sec. 8's top-level, mutually exclusive outcome shapes."""

    AUTONOMOUS_PASS = "AUTONOMOUS_PASS"
    AUTONOMOUS_FAIL = "AUTONOMOUS_FAIL"
    INFRASTRUCTURE_REFUSAL = "INFRASTRUCTURE_REFUSAL"


class DiagnosticSubclassification(str, Enum):
    """Diagnostic detail on top of ``AUTONOMOUS_FAIL``. Never a peer of it.

    ``PREMATURE_SETTLE``, ``RUNTIME_TIMEOUT`` and ``RUNTIME_STALLED`` are the
    three named subclassifications Sec. 8 requires. ``COMPLETED_BUT_WRONG``
    and ``UNTRUSTED_REPOSITORY_STATE`` record the two remaining Sec. 11
    scenarios (Sec. 11.4; an observed HEAD/index/broker-cross-check anomaly)
    distinctly from ``PREMATURE_SETTLE``'s partial-implementation shape,
    without inventing a NEW top-level classification -- both are still
    plainly ``AUTONOMOUS_FAIL``.
    """

    NONE = "NONE"
    PREMATURE_SETTLE = "PREMATURE_SETTLE"
    RUNTIME_TIMEOUT = "RUNTIME_TIMEOUT"
    RUNTIME_STALLED = "RUNTIME_STALLED"
    COMPLETED_BUT_WRONG = "COMPLETED_BUT_WRONG"
    UNTRUSTED_REPOSITORY_STATE = "UNTRUSTED_REPOSITORY_STATE"


@dataclass(frozen=True)
class RunFacts:
    """Explicit facts the classifier consumes. Never chain-of-thought/prose.

    ``stall_pattern_established`` is ``None`` (absent) or ``False`` unless an
    approved, AIDO-owned telemetry source has positively established the
    Sec. 11.3 no-progress pattern from observable evidence -- see the module
    docstring. It is never derived here.
    """

    semantic_prompts_sent: int
    infrastructure_refusal: bool = False
    runtime_settled: bool = False
    runtime_deadline_reached: bool = False
    stall_pattern_established: bool | None = None
    verification_passed: bool | None = None
    expected_changed_paths_satisfied: bool | None = None
    trusted_repository_state: bool | None = None
    hard_disqualifier_present: bool = False
    operator_continuation: bool = False
    automatic_semantic_retry: bool = False


@dataclass(frozen=True)
class OutcomeClassification:
    autonomous_classification: AutonomousClassification
    diagnostic_subclassification: DiagnosticSubclassification
    reason: str


def classify_outcome(facts: RunFacts) -> OutcomeClassification:
    """Sec. 8 / Sec. 11's outcome taxonomy, evaluated from ``facts`` alone."""

    if facts.infrastructure_refusal:
        if facts.semantic_prompts_sent != 0:
            raise ValueError(
                "infrastructure_refusal is a pre-prompt gate outcome and requires "
                "semantic_prompts_sent == 0"
            )
        return OutcomeClassification(
            AutonomousClassification.INFRASTRUCTURE_REFUSAL,
            DiagnosticSubclassification.NONE,
            "a pre-prompt runtime/provider/broker/compatibility gate failed; "
            "not scored as a model outcome",
        )

    if facts.semantic_prompts_sent != 1:
        raise ValueError(
            "a scored primary run must have exactly one semantic prompt sent"
        )

    # H-11 / H-12: these disqualify the autonomous result unconditionally,
    # regardless of whatever else happened in the run.
    if facts.operator_continuation:
        return OutcomeClassification(
            AutonomousClassification.AUTONOMOUS_FAIL,
            DiagnosticSubclassification.NONE,
            "operator continuation occurred; the primary result is never rescued by it",
        )
    if facts.automatic_semantic_retry:
        return OutcomeClassification(
            AutonomousClassification.AUTONOMOUS_FAIL,
            DiagnosticSubclassification.NONE,
            "an automatic semantic retry occurred; the primary policy allows none",
        )
    # H-13: a model-attributable hard-disqualifier refusal (Sec. 17.1) is
    # disqualifying even if the run otherwise looks complete.
    if facts.hard_disqualifier_present:
        return OutcomeClassification(
            AutonomousClassification.AUTONOMOUS_FAIL,
            DiagnosticSubclassification.NONE,
            "a model-attributable hard-disqualifier refusal occurred (Sec. 17.1)",
        )

    if facts.runtime_settled:
        if (
            facts.verification_passed
            and facts.expected_changed_paths_satisfied
            and facts.trusted_repository_state
        ):
            return OutcomeClassification(
                AutonomousClassification.AUTONOMOUS_PASS,
                DiagnosticSubclassification.NONE,
                "settled; authoritative verification passed; contract satisfied; "
                "repository state trusted",
            )
        if facts.expected_changed_paths_satisfied is False:
            return OutcomeClassification(
                AutonomousClassification.AUTONOMOUS_FAIL,
                DiagnosticSubclassification.PREMATURE_SETTLE,
                "runtime settled but only a partial implementation is present (Sec. 11.2)",
            )
        if facts.verification_passed is False:
            return OutcomeClassification(
                AutonomousClassification.AUTONOMOUS_FAIL,
                DiagnosticSubclassification.COMPLETED_BUT_WRONG,
                "runtime settled with the expected files changed, but authoritative "
                "verification failed (Sec. 11.4) -- not a stall, not infrastructure",
            )
        if facts.trusted_repository_state is False:
            return OutcomeClassification(
                AutonomousClassification.AUTONOMOUS_FAIL,
                DiagnosticSubclassification.UNTRUSTED_REPOSITORY_STATE,
                "runtime settled but observed repository state is not trusted "
                "(HEAD/index/broker cross-check anomaly)",
            )
        return OutcomeClassification(
            AutonomousClassification.AUTONOMOUS_FAIL,
            DiagnosticSubclassification.PREMATURE_SETTLE,
            "runtime settled but AIDO-observed completion criteria are not fully met",
        )

    if facts.runtime_deadline_reached:
        if facts.stall_pattern_established:
            return OutcomeClassification(
                AutonomousClassification.AUTONOMOUS_FAIL,
                DiagnosticSubclassification.RUNTIME_STALLED,
                "deadline reached; the Sec. 11.3 no-progress pattern was positively "
                "established from observable evidence",
            )
        return OutcomeClassification(
            AutonomousClassification.AUTONOMOUS_FAIL,
            DiagnosticSubclassification.RUNTIME_TIMEOUT,
            "deadline reached; the Sec. 11.3 no-progress pattern was not established "
            "(Sec. 11.3a default)",
        )

    raise ValueError(
        "facts describe neither a settled run, a deadline-expired run, nor an "
        "infrastructure refusal -- this run is not yet classifiable"
    )
