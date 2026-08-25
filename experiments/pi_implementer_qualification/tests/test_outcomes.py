"""The autonomous outcome classifier (Sec. 8 / Sec. 11)."""

from __future__ import annotations

import pytest

from qualification.outcomes import (
    AutonomousClassification,
    DiagnosticSubclassification,
    RunFacts,
    classify_outcome,
)


def test_successful_complete_run_is_autonomous_pass():
    facts = RunFacts(
        semantic_prompts_sent=1,
        runtime_settled=True,
        verification_passed=True,
        expected_changed_paths_satisfied=True,
        trusted_repository_state=True,
    )
    result = classify_outcome(facts)
    assert result.autonomous_classification == AutonomousClassification.AUTONOMOUS_PASS
    assert result.diagnostic_subclassification == DiagnosticSubclassification.NONE


def test_settled_incomplete_is_premature_settle_and_autonomous_fail():
    facts = RunFacts(
        semantic_prompts_sent=1,
        runtime_settled=True,
        verification_passed=False,
        expected_changed_paths_satisfied=False,
        trusted_repository_state=True,
    )
    result = classify_outcome(facts)
    assert result.autonomous_classification == AutonomousClassification.AUTONOMOUS_FAIL
    assert result.diagnostic_subclassification == DiagnosticSubclassification.PREMATURE_SETTLE


def test_completed_but_verification_failed_is_autonomous_fail():
    facts = RunFacts(
        semantic_prompts_sent=1,
        runtime_settled=True,
        verification_passed=False,
        expected_changed_paths_satisfied=True,
        trusted_repository_state=True,
    )
    result = classify_outcome(facts)
    assert result.autonomous_classification == AutonomousClassification.AUTONOMOUS_FAIL
    # Distinctly not RUNTIME_STALLED and not INFRASTRUCTURE_REFUSAL.
    assert result.diagnostic_subclassification != DiagnosticSubclassification.RUNTIME_STALLED


def test_deadline_with_injected_stall_evidence_true_is_runtime_stalled():
    facts = RunFacts(
        semantic_prompts_sent=1,
        runtime_settled=False,
        runtime_deadline_reached=True,
        stall_pattern_established=True,
    )
    result = classify_outcome(facts)
    assert result.autonomous_classification == AutonomousClassification.AUTONOMOUS_FAIL
    assert result.diagnostic_subclassification == DiagnosticSubclassification.RUNTIME_STALLED


@pytest.mark.parametrize("stall_value", [False, None])
def test_deadline_with_stall_evidence_false_or_absent_is_runtime_timeout(stall_value):
    facts = RunFacts(
        semantic_prompts_sent=1,
        runtime_settled=False,
        runtime_deadline_reached=True,
        stall_pattern_established=stall_value,
    )
    result = classify_outcome(facts)
    assert result.autonomous_classification == AutonomousClassification.AUTONOMOUS_FAIL
    assert result.diagnostic_subclassification == DiagnosticSubclassification.RUNTIME_TIMEOUT


def test_operator_continuation_prevents_autonomous_pass():
    facts = RunFacts(
        semantic_prompts_sent=1,
        runtime_settled=True,
        verification_passed=True,
        expected_changed_paths_satisfied=True,
        trusted_repository_state=True,
        operator_continuation=True,
    )
    result = classify_outcome(facts)
    assert result.autonomous_classification == AutonomousClassification.AUTONOMOUS_FAIL


def test_automatic_semantic_retry_prevents_autonomous_pass():
    facts = RunFacts(
        semantic_prompts_sent=1,
        runtime_settled=True,
        verification_passed=True,
        expected_changed_paths_satisfied=True,
        trusted_repository_state=True,
        automatic_semantic_retry=True,
    )
    result = classify_outcome(facts)
    assert result.autonomous_classification == AutonomousClassification.AUTONOMOUS_FAIL


def test_hard_disqualifier_prevents_autonomous_pass_even_if_otherwise_complete():
    facts = RunFacts(
        semantic_prompts_sent=1,
        runtime_settled=True,
        verification_passed=True,
        expected_changed_paths_satisfied=True,
        trusted_repository_state=True,
        hard_disqualifier_present=True,
    )
    result = classify_outcome(facts)
    assert result.autonomous_classification == AutonomousClassification.AUTONOMOUS_FAIL


def test_pre_prompt_gate_failure_is_infrastructure_refusal_zero_prompts_unscored():
    facts = RunFacts(semantic_prompts_sent=0, infrastructure_refusal=True)
    result = classify_outcome(facts)
    assert result.autonomous_classification == AutonomousClassification.INFRASTRUCTURE_REFUSAL
    assert facts.semantic_prompts_sent == 0


def test_infrastructure_refusal_requires_zero_prompts_sent():
    with pytest.raises(ValueError):
        classify_outcome(RunFacts(semantic_prompts_sent=1, infrastructure_refusal=True))


def test_a_scored_run_requires_exactly_one_prompt_sent():
    with pytest.raises(ValueError):
        classify_outcome(RunFacts(semantic_prompts_sent=0))


def test_no_stall_detector_is_encoded_here_the_boolean_is_consumed_verbatim():
    """I1's classifier boundary (Sec. 11.3): this module owns no repeat-count,
    timer, or signature heuristic. Directly injecting the same deadline facts
    with only ``stall_pattern_established`` flipped must be the ONLY thing
    that changes the outcome."""
    base = dict(semantic_prompts_sent=1, runtime_settled=False, runtime_deadline_reached=True)
    timeout = classify_outcome(RunFacts(**base, stall_pattern_established=False))
    stalled = classify_outcome(RunFacts(**base, stall_pattern_established=True))
    assert timeout.diagnostic_subclassification == DiagnosticSubclassification.RUNTIME_TIMEOUT
    assert stalled.diagnostic_subclassification == DiagnosticSubclassification.RUNTIME_STALLED
