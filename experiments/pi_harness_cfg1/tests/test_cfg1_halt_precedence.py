"""T-14, T-101, T-111 - T-114: admission ordering and halt-reason precedence.

A stage-closure record has exactly ONE ``halt_reason_code`` per halted ordinal,
and several Sec. 19.1 conditions can fail simultaneously for the same run.
Without a frozen precedence, two implementations -- or the same implementation
on two runs of the same failure class -- could durably record different codes
for mechanically identical situations, which is exactly the kind of
non-reproducible evidence this design exists to rule out.

Pure Python, ``tmp_path``-scoped, no live Pi/network/model/credential activity.
"""

from __future__ import annotations

import inspect
import itertools
from pathlib import Path

import pytest
from cfg1_builders import (
    happy_observations,
    pre_dispatch_refusal_overrides,
    synthetic_run_executor,
)

from pi_harness_cfg1 import halt, records, stage_runner
from pi_harness_cfg1.halt import (
    Cfg1AdmissionError,
    _admission_conditions_hold,
    _resolve_halt_reason_code,
)

#: The six precedence-ordered conditions, each as the fact tuple that makes it
#: -- and only it -- fail. "Clean" is the baseline in which nothing fails.
_CLEAN = {
    "emission_status": "RECORD_EMITTED",
    "halt_triggered_by_this_run": False,
    "lifecycle_all_closed": True,
    "run_classification": "INACTIVE",
    "registries_empty": True,
}

_CONDITIONS = (
    ("emission_collision", {"emission_status": "EMISSION_COLLISION"}, "RUN_RECORD_EMISSION_COLLISION"),
    ("emission_failed", {"emission_status": "EMISSION_FAILED"}, "RUN_RECORD_EMISSION_FAILED"),
    ("self_validation", {"halt_triggered_by_this_run": True}, "RUN_RECORD_SELF_VALIDATION_FAILED"),
    ("lifecycle", {"lifecycle_all_closed": False}, "LIFECYCLE_CLOSURE_UNPROVEN"),
    ("pre_dispatch", {"run_classification": "REFUSED_PRE_DISPATCH"}, "PRE_DISPATCH_REFUSAL"),
    ("registries", {"registries_empty": False}, "RUN_SCOPED_REGISTRY_NOT_EMPTY"),
)

#: Precedence rank: lower wins. Derived from the frozen order, not re-guessed.
_RANK = {name: index for index, (name, _facts, _code) in enumerate(_CONDITIONS)}


def _facts(*condition_names: str) -> dict:
    facts = dict(_CLEAN)
    for name in condition_names:
        overrides = next(o for n, o, _c in _CONDITIONS if n == name)
        facts.update(overrides)
    return facts


# ---------------------------------------------------------------------------
# T-111 -- a FULL pairwise sweep, not only the two named examples
# ---------------------------------------------------------------------------


def test_t111_every_co_occurring_pair_resolves_to_the_higher_precedence_code():
    pairs = list(itertools.combinations(_CONDITIONS, 2))
    assert len(pairs) == 15  # every pair of the six, not a sampled subset

    for (first_name, _f, first_code), (second_name, _s, second_code) in pairs:
        if first_name.startswith("emission") and second_name.startswith("emission"):
            # The two emission conditions are mutually exclusive by domain: one
            # ``emission_status`` field cannot hold both values at once.
            continue
        resolved = _resolve_halt_reason_code(**_facts(first_name, second_name))
        expected = (
            first_code if _RANK[first_name] < _RANK[second_name] else second_code
        )
        assert resolved == expected, (first_name, second_name)


def test_each_condition_alone_resolves_to_its_own_code():
    for name, _overrides, code in _CONDITIONS:
        assert _resolve_halt_reason_code(**_facts(name)) == code


def test_a_clean_run_resolves_to_no_halt_reason_at_all():
    assert _resolve_halt_reason_code(**_CLEAN) is None


# ---------------------------------------------------------------------------
# T-112 / T-113 -- the two overlaps the design names explicitly
# ---------------------------------------------------------------------------


def test_t112_a_row_15_defect_whose_fallback_also_failed_records_the_emission_code():
    """The emission outcome takes DURABLE precedence over the defect beneath it.

    A reader checking ``results/`` for admissible evidence needs "this
    ordinal's evidence could not be confirmed on disk" foremost; the underlying
    defect stays available through the bounded console channel.
    """
    resolved = _resolve_halt_reason_code(
        **_facts("emission_failed", "self_validation")
    )
    assert resolved == "RUN_RECORD_EMISSION_FAILED"
    assert resolved != "RUN_RECORD_SELF_VALIDATION_FAILED"


def test_t113_a_lifecycle_failure_outranks_a_non_empty_registry():
    resolved = _resolve_halt_reason_code(**_facts("lifecycle", "registries"))
    assert resolved == "LIFECYCLE_CLOSURE_UNPROVEN"
    assert resolved != "RUN_SCOPED_REGISTRY_NOT_EMPTY"


# ---------------------------------------------------------------------------
# T-114 -- exactly one precedence function, never reimplemented
# ---------------------------------------------------------------------------


def test_t114_one_shared_precedence_callable_and_no_reimplementation():
    assert stage_runner._resolve_halt_reason_code is _resolve_halt_reason_code

    # The stage-closure validator contains NO independent reconstruction of
    # steps 3-6 -- it cannot, because those four codes depend on facts no
    # durable payload carries (T-115 proves that scope directly).
    validator_source = inspect.getsource(records._require_valid_cfg1_stage_closure_payload)
    for fact in (
        "halt_triggered_by_this_run",
        "lifecycle_all_closed",
        "run_classification",
        "registries_empty",
    ):
        assert fact not in validator_source
    assert "_resolve_halt_reason_code" not in validator_source

    # And the writer contains none either.
    from pi_harness_cfg1 import writers

    assert "_resolve_halt_reason_code" not in (
        Path(writers.__file__).read_text(encoding="utf-8")
    )


def test_the_precedence_function_never_returns_a_value_outside_the_closed_set():
    for name, _overrides, _code in _CONDITIONS:
        assert _resolve_halt_reason_code(**_facts(name)) in halt.HALT_REASON_CODES


# ---------------------------------------------------------------------------
# T-101 -- L28 -> L29 -> L30 ordering, proven mechanically
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "unresolved",
    [None, "", "PENDING", "NOT_YET_RESOLVED", "NOT_EXECUTED", 0, True, object()],
    ids=lambda v: type(v).__name__ if not isinstance(v, str) else (v or "empty"),
)
def test_t101_the_admission_decision_refuses_an_unresolved_emission_status(unresolved):
    """It RAISES rather than silently treating it as any of the four values.

    ``NOT_EXECUTED`` is included deliberately: it is a legitimate member of the
    stage-closure ``ordinal_status`` domain, but it is NOT an emission outcome
    an admitted run can resolve to, so reading it here would be a category
    error, not a near-miss.
    """
    facts = dict(_CLEAN)
    facts["emission_status"] = unresolved
    with pytest.raises(Cfg1AdmissionError) as excinfo:
        _admission_conditions_hold(**facts)
    assert excinfo.value.reason_code == "EMISSION_OUTCOME_NOT_RESOLVED"


def test_t101_only_the_four_resolved_statuses_are_readable_at_all():
    assert halt.RESOLVED_EMISSION_STATUSES == frozenset(
        {"RECORD_EMITTED", "EVIDENCE_REFUSED", "EMISSION_COLLISION", "EMISSION_FAILED"}
    )
    for status in halt.RESOLVED_EMISSION_STATUSES:
        facts = dict(_CLEAN)
        facts["emission_status"] = status
        assert isinstance(_admission_conditions_hold(**facts), bool)


def test_t101_the_runner_records_l29_before_it_ever_evaluates_l30():
    source = inspect.getsource(stage_runner.run_cfg1_stage)
    emit_at = source.index("emission = emit_cfg1_run_record(")
    record_at = source.index("_record_ordinal_result(run_ordinal, emission.emission_status)")
    admission_at = source.index("admissible = _admission_conditions_hold(")
    assert emit_at < record_at < admission_at


# ---------------------------------------------------------------------------
# T-14 -- the admission rule, end to end
# ---------------------------------------------------------------------------


def _halting_executor(ordinal: int, overrides: dict):
    from pi_harness_cfg1.arms import ARM_SHAPE
    from pi_harness_cfg1.run_contract import Cfg1RunOutcome
    from qualification.safety import ArtifactSafetyContext

    def _executor(admission):
        local = {"runtime_reported_compat_shape": ARM_SHAPE[admission.arm_id]}
        if admission.run_ordinal == ordinal:
            local.update(overrides)
        return Cfg1RunOutcome(
            observations=happy_observations(**local),
            safety=ArtifactSafetyContext.none_declared(),
            live_references_released=True,
        )

    return _executor


def test_t14_a_lifecycle_failure_admits_no_later_ordinal(make_authority):
    authority = make_authority("S1-X1")
    result = stage_runner.run_cfg1_stage(
        authority,
        run_executor=_halting_executor(
            2,
            {
                "workspace_removed_verified": False,
                "lifecycle_all_closed": False,
                "lifecycle_failure_steps": ["L27"],
                "verification_attempted": False,
                "verification_skip_reason": "LIFECYCLE_UNPROVEN",
                "verification_started": False,
                "verification_completed": False,
                "verification_return_code": None,
                "verification_counts": {"passed": 0, "failed": 0, "error": 0},
                "git_observation_2_performed": False,
            },
        ),
    )
    assert result.halted_after_ordinal == 2
    assert result.halt_reason_code == "LIFECYCLE_CLOSURE_UNPROVEN"
    assert result.ordinals_attempted == (1, 2)
    assert dict(result.ordinal_status)[3] == "NOT_EXECUTED"


def test_t14_a_pre_dispatch_refusal_admits_no_later_ordinal(make_authority):
    authority = make_authority("S1-X1")
    result = stage_runner.run_cfg1_stage(
        authority,
        run_executor=_halting_executor(
            1, pre_dispatch_refusal_overrides("BROKER_NOT_READY", "L13")
        ),
    )
    assert result.halted_after_ordinal == 1
    assert result.halt_reason_code == "PRE_DISPATCH_REFUSAL"
    assert result.ordinals_attempted == (1,)


def test_t14_an_emission_collision_admits_no_later_ordinal(make_authority, monkeypatch):
    from pi_harness_cfg1 import writers

    authority = make_authority("S1-X1")
    real_open = writers._open_exclusive

    def _open(path):
        if path.endswith("S1_02_R.json"):
            raise FileExistsError(path)
        return real_open(path)

    monkeypatch.setattr(writers, "_open_exclusive", _open)
    result = stage_runner.run_cfg1_stage(
        authority, run_executor=synthetic_run_executor()
    )
    assert result.halted_after_ordinal == 2
    assert result.halt_reason_code == "RUN_RECORD_EMISSION_COLLISION"
    assert dict(result.ordinal_status)[2] == "EMISSION_COLLISION"
    assert dict(result.ordinal_status)[3] == "NOT_EXECUTED"


def test_t14_a_non_empty_run_scoped_registry_admits_no_later_ordinal(make_authority):
    """Item 4 is its own independent admission condition, checked on its own."""
    authority = make_authority("S1-X1")

    def _executor(admission):
        from pi_harness_cfg1.arms import ARM_SHAPE
        from pi_harness_cfg1.run_contract import Cfg1RunOutcome
        from qualification.safety import ArtifactSafetyContext

        return Cfg1RunOutcome(
            observations=happy_observations(
                runtime_reported_compat_shape=ARM_SHAPE[admission.arm_id]
            ),
            safety=ArtifactSafetyContext.none_declared(),
            # The run did not release its own live references.
            live_references_released=admission.run_ordinal != 2,
        )

    result = stage_runner.run_cfg1_stage(authority, run_executor=_executor)
    assert result.halted_after_ordinal == 2
    assert result.halt_reason_code == "RUN_SCOPED_REGISTRY_NOT_EMPTY"


def test_an_evidence_refusal_alone_does_not_halt_the_stage(make_authority):
    """Sec. 19.3: row 11 holds no handle and gives run k+1 nothing it consumes."""
    from pi_harness_cfg1.run_contract import Cfg1RunOutcome
    from qualification.safety import ArtifactSafetyContext

    def _executor(admission):
        from pi_harness_cfg1.arms import ARM_SHAPE

        return Cfg1RunOutcome(
            observations=happy_observations(
                runtime_reported_compat_shape=ARM_SHAPE[admission.arm_id]
            ),
            # A needle that genuinely appears in the run payload for THIS
            # ordinal only, and never in a refusal record.
            safety=(
                ArtifactSafetyContext(api_key="0.85.1")
                if admission.run_ordinal == 2
                else ArtifactSafetyContext.none_declared()
            ),
            live_references_released=True,
        )

    authority = make_authority("S1-X1")
    result = stage_runner.run_cfg1_stage(authority, run_executor=_executor)
    assert result.disposition == "STAGE_COMPLETED"
    assert result.halted_after_ordinal is None
    assert dict(result.ordinal_status)[2] == "EVIDENCE_REFUSED"
    assert dict(result.ordinal_status)[3] == "RECORD_EMITTED"
