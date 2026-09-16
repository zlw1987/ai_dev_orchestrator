"""Run classification and the CFG1-only observation-disagreement predicates.

Design Sec. 12. Evaluated in order; FIRST MATCH WINS. The ordering is
load-bearing, not cosmetic -- row 6 deliberately precedes row 9 so that ANY
unexpected tool call routes to indeterminate even when expected ``aido_*``
calls are also present.

**Why an unexpected call proves nothing.** Only ``aido_read`` and ``aido_edit``
are offered. By source, an unregistered tool name receives an immediate
"Tool ... not found" error result inside Pi's own agent loop and never reaches
an extension or the broker at all (``agent-loop.js``), so a hallucinated call
carries no information about the intended AIDO tool path. Row 7 exists
separately because OBS1's id-collapse can misattribute a collapsed entry's
category in either direction.

This function is a PURE function of pre-emission observations. It never reads
this run's own emission outcome, which is exactly why ``run_classification``
survives in the durable run-record schema while ``halt_triggered_by_this_run``
and ``halt_reason_code`` do not (Sec. 22.2, FU8 Finding 2).
"""

from __future__ import annotations

from typing import Mapping

CLASSIFICATION_INDETERMINATE_LIFECYCLE = "INDETERMINATE_LIFECYCLE"
CLASSIFICATION_REFUSED_PRE_DISPATCH = "REFUSED_PRE_DISPATCH"
CLASSIFICATION_INDETERMINATE_DISPATCH = "INDETERMINATE_DISPATCH"
CLASSIFICATION_INDETERMINATE_RUNTIME_STREAM = "INDETERMINATE_RUNTIME_STREAM"
CLASSIFICATION_INDETERMINATE_NO_ACTIVITY_EVIDENCE = "INDETERMINATE_NO_ACTIVITY_EVIDENCE"
CLASSIFICATION_INDETERMINATE_UNEXPECTED_TOOL_ACTIVITY = (
    "INDETERMINATE_UNEXPECTED_TOOL_ACTIVITY"
)
CLASSIFICATION_INDETERMINATE_UNATTRIBUTABLE_TOOL_CALL_ID = (
    "INDETERMINATE_UNATTRIBUTABLE_TOOL_CALL_ID"
)
CLASSIFICATION_INDETERMINATE_OBSERVATION_DISAGREEMENT = (
    "INDETERMINATE_OBSERVATION_DISAGREEMENT"
)
CLASSIFICATION_ACTIVE = "ACTIVE"
CLASSIFICATION_INDETERMINATE_PROVIDER = "INDETERMINATE_PROVIDER"
CLASSIFICATION_INDETERMINATE_WAIT_ENDED = "INDETERMINATE_WAIT_ENDED"
CLASSIFICATION_INACTIVE = "INACTIVE"

#: The closed classification domain, in Sec. 12.1's own evaluation order.
RUN_CLASSIFICATIONS: tuple[str, ...] = (
    CLASSIFICATION_INDETERMINATE_LIFECYCLE,
    CLASSIFICATION_REFUSED_PRE_DISPATCH,
    CLASSIFICATION_INDETERMINATE_DISPATCH,
    CLASSIFICATION_INDETERMINATE_RUNTIME_STREAM,
    CLASSIFICATION_INDETERMINATE_NO_ACTIVITY_EVIDENCE,
    CLASSIFICATION_INDETERMINATE_UNEXPECTED_TOOL_ACTIVITY,
    CLASSIFICATION_INDETERMINATE_UNATTRIBUTABLE_TOOL_CALL_ID,
    CLASSIFICATION_INDETERMINATE_OBSERVATION_DISAGREEMENT,
    CLASSIFICATION_ACTIVE,
    CLASSIFICATION_INDETERMINATE_PROVIDER,
    CLASSIFICATION_INDETERMINATE_WAIT_ENDED,
    CLASSIFICATION_INACTIVE,
)

#: The determinate pair. Everything else is indeterminate or refused, and an
#: arm containing any of those is INDETERMINATE (Sec. 12.3).
DETERMINATE_CLASSIFICATIONS: frozenset[str] = frozenset(
    {CLASSIFICATION_ACTIVE, CLASSIFICATION_INACTIVE}
)

#: Sec. 12.1 row 4 -- stream-terminal wait outcomes.
STREAM_TERMINAL_WAIT_OUTCOMES: frozenset[str] = frozenset(
    {
        "PROTOCOL_VIOLATION",
        "OUTPUT_CAP_EXCEEDED",
        "EVENT_CAP_EXCEEDED",
        "READ_ERROR",
        "UNRECOGNIZED",
    }
)

CAPTURE_BASIS_AGENT_SETTLED = "agent_settled"
CAPTURE_BASIS_WAIT_ENDED_BEFORE_SETTLED = "wait_ended_before_settled"

#: The four CFG1-only disagreement predicate ids (Sec. 12.2). These are a CFG1
#: INTERPRETATION rule, never an OBS1 schema invariant, and they only ever
#: route to indeterminate.
DISAGREEMENT_PREDICATE_IDS: tuple[str, ...] = ("D-1", "D-2", "D-3", "D-4")


def observation_disagreement_predicates(facts: Mapping[str, object]) -> tuple[str, ...]:
    """Which Sec. 12.2 predicates hold. Evaluated only after rows 1-7 are excluded.

    At that point no unexpected or collapsed call is present and BOTH activity
    families are available, so D-1..D-3 compare only the two categories the
    broker can serve -- which is what makes them non-contradictory with row 6
    rather than merely ordered after it.

    D-1 and D-3 are suppressed for ``wait_ended_before_settled``, because
    runtime counts are then lower bounds and broker frames may legitimately
    exceed them. D-2 remains sound there: a non-error ``aido_*`` end is
    returned only after a successful ``brokerCall``, since refusal and
    unavailability both throw.
    """
    basis = facts["runtime_reported_tool_activity_capture_basis"]
    settled_basis = basis == CAPTURE_BASIS_AGENT_SETTLED

    read_calls = int(facts["runtime_reported_aido_read_call_ids"])
    edit_calls = int(facts["runtime_reported_aido_edit_call_ids"])
    read_ends = int(facts["runtime_reported_aido_read_end_observed"])
    edit_ends = int(facts["runtime_reported_aido_edit_end_observed"])
    read_errors = int(facts["runtime_reported_aido_read_error_results"])
    edit_errors = int(facts["runtime_reported_aido_edit_error_results"])

    broker_reads = int(facts["broker_recorded_read_operation_count"])
    broker_edits = int(facts["broker_recorded_edit_operation_count"])
    broker_refusals = int(facts["broker_recorded_refusal_count"])

    held: list[str] = []

    if settled_basis:
        broker_total = broker_reads + broker_edits + broker_refusals
        if broker_total > 0 and (read_calls + edit_calls) == 0:
            held.append("D-1")

    if (read_ends - read_errors) > broker_reads or (edit_ends - edit_errors) > broker_edits:
        held.append("D-2")

    if settled_basis:
        if (
            broker_reads > read_calls
            or broker_edits > edit_calls
            or (broker_reads + broker_edits + broker_refusals) > (read_calls + edit_calls)
        ):
            held.append("D-3")

    if (
        facts["git_observation_1_performed"] is True
        and facts["broker_git_cross_check_agrees"] is False
    ):
        held.append("D-4")

    return tuple(held)


def classify_cfg1_run(facts: Mapping[str, object]) -> str:
    """Sec. 12.1's twelve rows, evaluated in order. First match wins.

    ``facts`` is the run-record payload snapshot (or any mapping carrying the
    same field names). Only pre-emission observations are read; the caller's
    own emission outcome is deliberately unavailable to this function.
    """
    # 1
    if facts["lifecycle_all_closed"] is False:
        return CLASSIFICATION_INDETERMINATE_LIFECYCLE
    # 2
    if facts["pre_dispatch_refusal_code"] is not None:
        return CLASSIFICATION_REFUSED_PRE_DISPATCH
    # 3
    if facts["dispatch_state"] == "SEND_STATE_INDETERMINATE":
        return CLASSIFICATION_INDETERMINATE_DISPATCH
    # 4
    if facts["runtime_wait_outcome"] in STREAM_TERMINAL_WAIT_OUTCOMES:
        return CLASSIFICATION_INDETERMINATE_RUNTIME_STREAM
    # 5
    if (
        facts["runtime_reported_tool_activity_available"] is False
        or facts["broker_recorded_activity_available"] is False
    ):
        return CLASSIFICATION_INDETERMINATE_NO_ACTIVITY_EVIDENCE
    # 6 -- BEFORE ACTIVE, and regardless of any aido_* activity.
    if int(facts["runtime_reported_unexpected_tool_call_ids"]) > 0:
        return CLASSIFICATION_INDETERMINATE_UNEXPECTED_TOOL_ACTIVITY
    # 7
    if facts["runtime_reported_unidentified_tool_call_id_seen"] is True:
        return CLASSIFICATION_INDETERMINATE_UNATTRIBUTABLE_TOOL_CALL_ID
    # 8
    if observation_disagreement_predicates(facts):
        return CLASSIFICATION_INDETERMINATE_OBSERVATION_DISAGREEMENT

    expected_activity = int(facts["runtime_reported_aido_read_call_ids"]) + int(
        facts["runtime_reported_aido_edit_call_ids"]
    )
    # 9
    if expected_activity >= 1:
        return CLASSIFICATION_ACTIVE

    stop_counts = facts["stop_reason_counts"]
    provider_errors = int(stop_counts["error"]) + int(stop_counts["aborted"])  # type: ignore[index]
    auto_retries = int(facts["auto_retry_events"])
    # 10
    if (
        provider_errors >= 1
        or auto_retries >= 1
        or facts["stop_reasons_available"] is False
    ):
        return CLASSIFICATION_INDETERMINATE_PROVIDER
    # 11
    if (
        facts["runtime_reported_tool_activity_capture_basis"]
        == CAPTURE_BASIS_WAIT_ENDED_BEFORE_SETTLED
    ):
        return CLASSIFICATION_INDETERMINATE_WAIT_ENDED
    # 12
    return CLASSIFICATION_INACTIVE


def run_is_length_terminated(facts: Mapping[str, object]) -> bool:
    """Sec. 12.1's ``INACTIVE`` annotation. A provider-reported fact, not a cap.

    Never claims an AIDO-requested output budget was exhausted: this design
    requests no ``max_tokens`` at all, so a length stop reason names a BACKEND
    capability limit whose identity AIDO does not know and never invents.
    """
    return int(facts["stop_reason_counts"]["length"]) >= 1  # type: ignore[index]


# ---------------------------------------------------------------------------
# Sec. 12.3 -- arm and stage aggregation
# ---------------------------------------------------------------------------

ARM_ACTIVE = "ACTIVE"
ARM_INACTIVE = "INACTIVE"
ARM_MIXED = "MIXED"
ARM_INDETERMINATE = "INDETERMINATE"


def aggregate_arm(run_outcomes: tuple[tuple[str, str], ...]) -> str:
    """Aggregate one arm's three runs into ``ACTIVE``/``INACTIVE``/``MIXED``/``INDETERMINATE``.

    ``run_outcomes`` is a tuple of ``(run_classification, emission_status)``
    pairs. An arm is INDETERMINATE if ANY of its runs is indeterminate or
    refused, carries ``EVIDENCE_REFUSED`` or ``EMISSION_FAILED``, or was never
    executed because the stage halted.

    ``EMISSION_FAILED`` counts here because no successfully-confirmed,
    authoritative artifact exists for that run. A post-create write failure may
    leave non-authoritative residue on disk, but Sec. 16.3.8.2's residue policy
    means that residue is never read for classification -- so the arm is
    exactly as indeterminate as one with no artifact at all.
    """
    from .halt import (
        EMISSION_EVIDENCE_REFUSED,
        EMISSION_FAILED,
        EMISSION_COLLISION,
        ORDINAL_NOT_EXECUTED,
    )

    classifications: list[str] = []
    for classification, emission_status in run_outcomes:
        if emission_status in (
            EMISSION_EVIDENCE_REFUSED,
            EMISSION_FAILED,
            EMISSION_COLLISION,
            ORDINAL_NOT_EXECUTED,
        ):
            return ARM_INDETERMINATE
        if classification not in DETERMINATE_CLASSIFICATIONS:
            return ARM_INDETERMINATE
        classifications.append(classification)

    if not classifications:
        return ARM_INDETERMINATE
    if all(value == CLASSIFICATION_ACTIVE for value in classifications):
        return ARM_ACTIVE
    if all(value == CLASSIFICATION_INACTIVE for value in classifications):
        return ARM_INACTIVE
    return ARM_MIXED
