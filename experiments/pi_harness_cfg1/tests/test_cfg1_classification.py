"""Sec. 12 in full: the twelve rows, the four predicates, and the aggregation.

The row ORDER is load-bearing, not cosmetic. Row 6 deliberately precedes row 9,
so ANY unexpected tool call routes to indeterminate even when expected
``aido_*`` calls are also present -- because an unregistered name never reaches
an extension or the broker at all, and so proves nothing about the intended
AIDO tool path.

Pure Python, no live Pi/network/model/credential activity.
"""

from __future__ import annotations

import pytest
from cfg1_builders import (
    active_observation_overrides,
    happy_observations,
    pre_dispatch_refusal_overrides,
    run_payload,
    unavailable_activity_overrides,
)

from pi_harness_cfg1.classification import (
    ARM_ACTIVE,
    ARM_INACTIVE,
    ARM_INDETERMINATE,
    ARM_MIXED,
    RUN_CLASSIFICATIONS,
    aggregate_arm,
    classify_cfg1_run,
    observation_disagreement_predicates,
    run_is_length_terminated,
)


def _facts(**overrides):
    return happy_observations(**overrides)


# ---------------------------------------------------------------------------
# Sec. 12.1 -- the twelve rows, in order, first match wins
# ---------------------------------------------------------------------------


def test_the_closed_classification_domain_is_exactly_the_twelve_rows():
    assert len(RUN_CLASSIFICATIONS) == 12
    assert len(set(RUN_CLASSIFICATIONS)) == 12
    assert RUN_CLASSIFICATIONS[0] == "INDETERMINATE_LIFECYCLE"
    assert RUN_CLASSIFICATIONS[-1] == "INACTIVE"


def test_row_1_a_lifecycle_failure_outranks_everything_else():
    facts = _facts(
        lifecycle_all_closed=False,
        workspace_removed_verified=False,
        lifecycle_failure_steps=["L27"],
        **pre_dispatch_refusal_overrides("BROKER_NOT_READY", "L13"),
    )
    assert classify_cfg1_run(facts) == "INDETERMINATE_LIFECYCLE"


def test_row_2_a_pre_dispatch_refusal_outranks_dispatch_state():
    facts = _facts(**pre_dispatch_refusal_overrides("ROUTE_UNAVAILABLE", "L7"))
    assert classify_cfg1_run(facts) == "REFUSED_PRE_DISPATCH"


def test_row_3_an_indeterminate_dispatch():
    facts = _facts(
        dispatch_state="SEND_STATE_INDETERMINATE",
        runtime_wait_outcome="DEADLINE_EXPIRED",
        **unavailable_activity_overrides(),
    )
    assert classify_cfg1_run(facts) == "INDETERMINATE_DISPATCH"


@pytest.mark.parametrize(
    "outcome",
    [
        "PROTOCOL_VIOLATION",
        "OUTPUT_CAP_EXCEEDED",
        "EVENT_CAP_EXCEEDED",
        "READ_ERROR",
        "UNRECOGNIZED",
    ],
)
def test_row_4_every_stream_terminal_outcome(outcome):
    facts = _facts(runtime_wait_outcome=outcome, **unavailable_activity_overrides())
    assert classify_cfg1_run(facts) == "INDETERMINATE_RUNTIME_STREAM"


def test_row_5_either_activity_family_being_unavailable():
    assert (
        classify_cfg1_run(_facts(**unavailable_activity_overrides()))
        == "INDETERMINATE_NO_ACTIVITY_EVIDENCE"
    )
    assert (
        classify_cfg1_run(
            _facts(
                broker_recorded_activity_available=False,
                broker_recorded_read_operation_count=0,
            )
        )
        == "INDETERMINATE_NO_ACTIVITY_EVIDENCE"
    )


def test_row_6_an_unexpected_call_outranks_active_even_alongside_expected_calls():
    """The ordering that matters most in Sec. 12.

    A hallucinated call gets an immediate "Tool ... not found" result inside
    Pi's own agent loop and never reaches an extension or the broker, so it
    carries no information about the intended AIDO tool path. A run carrying
    one is indeterminate REGARDLESS of how much genuine activity it also has.
    """
    overrides = active_observation_overrides()
    overrides.update(
        {
            "runtime_reported_unexpected_tool_call_ids": 1,
            "runtime_reported_distinct_tool_call_ids": 2,
            "runtime_reported_tool_execution_start_events": 2,
            "runtime_reported_tool_execution_end_events": 2,
        }
    )
    facts = _facts(**overrides)
    # There IS genuine expected activity...
    assert facts["runtime_reported_aido_read_call_ids"] == 1
    # ...and the run is still indeterminate, not ACTIVE.
    assert classify_cfg1_run(facts) == "INDETERMINATE_UNEXPECTED_TOOL_ACTIVITY"


def test_row_7_a_collapsed_unattributable_call_id():
    overrides = active_observation_overrides()
    overrides["runtime_reported_unidentified_tool_call_id_seen"] = True
    assert (
        classify_cfg1_run(_facts(**overrides))
        == "INDETERMINATE_UNATTRIBUTABLE_TOOL_CALL_ID"
    )


def test_row_9_active_requires_at_least_one_expected_call():
    assert classify_cfg1_run(_facts(**active_observation_overrides())) == "ACTIVE"


@pytest.mark.parametrize(
    "overrides",
    [
        {"stop_reason_counts": {"stop": 0, "length": 0, "toolUse": 0, "error": 1,
                                "aborted": 0, "other": 0}},
        {"stop_reason_counts": {"stop": 0, "length": 0, "toolUse": 0, "error": 0,
                                "aborted": 1, "other": 0}},
        {"auto_retry_events": 1},
        {"stop_reasons_available": False},
    ],
    ids=["error", "aborted", "auto_retry", "stop_reasons_unavailable"],
)
def test_row_10_a_provider_level_anomaly_is_never_read_as_zero_tool_use(overrides):
    assert classify_cfg1_run(_facts(**overrides)) == "INDETERMINATE_PROVIDER"


def test_row_11_a_wait_that_ended_before_settled_is_never_inactive():
    facts = _facts(
        runtime_reported_tool_activity_capture_basis="wait_ended_before_settled",
        runtime_wait_outcome="DEADLINE_EXPIRED",
    )
    assert classify_cfg1_run(facts) == "INDETERMINATE_WAIT_ENDED"


def test_row_12_inactive_is_the_only_determinate_absence():
    assert classify_cfg1_run(_facts()) == "INACTIVE"


def test_inactive_carries_the_length_terminated_annotation():
    """A provider-reported fact, NEVER an AIDO-requested budget claim.

    This design requests no ``max_tokens`` at all, so a length stop reason
    names a BACKEND capability limit whose identity AIDO does not know and
    never invents.
    """
    assert run_is_length_terminated(_facts()) is False
    facts = _facts(
        stop_reason_counts={"stop": 0, "length": 1, "toolUse": 0, "error": 0,
                            "aborted": 0, "other": 0}
    )
    assert run_is_length_terminated(facts) is True
    assert classify_cfg1_run(facts) == "INACTIVE"


# ---------------------------------------------------------------------------
# Sec. 12.2 -- the four disagreement predicates, and their basis requirements
# ---------------------------------------------------------------------------


def test_d1_broker_activity_without_any_runtime_call_is_a_disagreement():
    """Only THIS run's extension holds the binding and connects to its pipe."""
    facts = _facts(broker_recorded_read_operation_count=1)
    assert "D-1" in observation_disagreement_predicates(facts)
    assert classify_cfg1_run(facts) == "INDETERMINATE_OBSERVATION_DISAGREEMENT"


def test_d2_more_non_error_ends_than_broker_operations_is_a_disagreement():
    """A non-error ``aido_*`` end is returned only after a successful brokerCall.

    Refusal and unavailability both THROW, so an end without a matching broker
    operation cannot have happened.
    """
    overrides = active_observation_overrides()
    overrides["broker_recorded_read_operation_count"] = 0
    facts = _facts(**overrides)
    assert "D-2" in observation_disagreement_predicates(facts)


def test_d3_more_broker_frames_than_runtime_calls_is_a_disagreement():
    overrides = active_observation_overrides()
    overrides["broker_recorded_read_operation_count"] = 2
    facts = _facts(**overrides)
    assert "D-3" in observation_disagreement_predicates(facts)


def test_d1_and_d3_are_suppressed_for_a_wait_that_ended_before_settled():
    """Runtime counts are LOWER BOUNDS there, so broker frames may exceed them.

    D-2 remains sound regardless: a successful end still requires a prior
    accepted operation.
    """
    facts = _facts(
        runtime_reported_tool_activity_capture_basis="wait_ended_before_settled",
        runtime_wait_outcome="DEADLINE_EXPIRED",
        broker_recorded_read_operation_count=2,
    )
    held = observation_disagreement_predicates(facts)
    assert "D-1" not in held
    assert "D-3" not in held

    overrides = active_observation_overrides()
    overrides.update(
        {
            "runtime_reported_tool_activity_capture_basis": "wait_ended_before_settled",
            "runtime_wait_outcome": "DEADLINE_EXPIRED",
            "broker_recorded_read_operation_count": 0,
        }
    )
    assert "D-2" in observation_disagreement_predicates(_facts(**overrides))


def test_d4_a_broker_git_cross_check_failure_is_a_disagreement():
    facts = _facts(broker_git_cross_check_agrees=False)
    assert "D-4" in observation_disagreement_predicates(facts)
    # ...and only when Git observation #1 actually happened.
    facts = _facts(
        broker_git_cross_check_agrees=False, git_observation_1_performed=False
    )
    assert "D-4" not in observation_disagreement_predicates(facts)


def test_no_run_can_be_both_unexpected_tool_activity_and_a_disagreement():
    """Sec. 12.2's non-contradiction proof, as a behavioural check.

    Rows 6-7 exclude every case in which runtime category counts could be
    misattributed, and the D predicates never cite unexpected counts -- so the
    first match always wins cleanly.
    """
    overrides = active_observation_overrides()
    overrides.update(
        {
            "runtime_reported_unexpected_tool_call_ids": 1,
            "runtime_reported_distinct_tool_call_ids": 2,
            "runtime_reported_tool_execution_start_events": 2,
            "runtime_reported_tool_execution_end_events": 2,
            "broker_recorded_read_operation_count": 9,  # would trip D-3
        }
    )
    facts = _facts(**overrides)
    assert classify_cfg1_run(facts) == "INDETERMINATE_UNEXPECTED_TOOL_ACTIVITY"


def test_the_payload_validator_accepts_every_classification_it_recomputes():
    """Each row, assembled as a real payload and revalidated end to end."""
    from pi_harness_cfg1.records import _require_valid_cfg1_run_payload

    for overrides, expected in (
        ({}, "INACTIVE"),
        (active_observation_overrides(), "ACTIVE"),
        (unavailable_activity_overrides(), "INDETERMINATE_NO_ACTIVITY_EVIDENCE"),
        (
            pre_dispatch_refusal_overrides("ROUTE_UNAVAILABLE", "L7"),
            "REFUSED_PRE_DISPATCH",
        ),
        ({"broker_recorded_read_operation_count": 1},
         "INDETERMINATE_OBSERVATION_DISAGREEMENT"),
    ):
        payload = run_payload(**overrides)
        _require_valid_cfg1_run_payload(payload)
        assert payload["run_classification"] == expected


# ---------------------------------------------------------------------------
# Sec. 12.3 -- arm aggregation
# ---------------------------------------------------------------------------


def test_an_arm_is_active_or_inactive_only_when_its_three_runs_are_unanimous():
    assert aggregate_arm((("ACTIVE", "RECORD_EMITTED"),) * 3) == ARM_ACTIVE
    assert aggregate_arm((("INACTIVE", "RECORD_EMITTED"),) * 3) == ARM_INACTIVE


def test_three_determinate_but_non_unanimous_runs_are_mixed():
    outcomes = (
        ("ACTIVE", "RECORD_EMITTED"),
        ("INACTIVE", "RECORD_EMITTED"),
        ("ACTIVE", "RECORD_EMITTED"),
    )
    assert aggregate_arm(outcomes) == ARM_MIXED


@pytest.mark.parametrize(
    "bad_run",
    [
        ("INDETERMINATE_PROVIDER", "RECORD_EMITTED"),
        ("REFUSED_PRE_DISPATCH", "RECORD_EMITTED"),
        ("INACTIVE", "EVIDENCE_REFUSED"),
        ("INACTIVE", "EMISSION_FAILED"),
        ("INACTIVE", "EMISSION_COLLISION"),
        ("INACTIVE", "NOT_EXECUTED"),
    ],
    ids=lambda pair: f"{pair[0]}|{pair[1]}",
)
def test_any_indeterminate_refused_failed_or_unexecuted_run_makes_the_arm_indeterminate(
    bad_run,
):
    """``EMISSION_FAILED`` counts because no CONFIRMED artifact exists.

    A post-create write failure may leave non-authoritative residue on disk,
    but Sec. 16.3.8.2's residue policy means that residue is never read for
    classification -- so the arm is exactly as indeterminate as one with no
    artifact at all.
    """
    outcomes = (("ACTIVE", "RECORD_EMITTED"), bad_run, ("ACTIVE", "RECORD_EMITTED"))
    assert aggregate_arm(outcomes) == ARM_INDETERMINATE


def test_an_empty_arm_is_indeterminate_never_vacuously_unanimous():
    assert aggregate_arm(()) == ARM_INDETERMINATE
