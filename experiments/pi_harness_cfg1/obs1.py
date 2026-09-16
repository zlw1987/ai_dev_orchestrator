"""CFG1's OBS1 consumption -- imported and called, never copied or subclassed.

Design Sec. 11.1, under the reviewer's frozen F2 decision (Sec. 0.1). CFG1
does **not** emit the ``pi-implementer-qualification-activity.v1`` companion
artifact: that companion is qualification-corpus-bound by construction, and
CFG1 is an independent diagnostic lineage with no qualification authority.

What CFG1 does instead is import and call, UNMODIFIED,
``project_runtime_tool_activity`` and ``RuntimeToolActivitySnapshot``, thereby
preserving their per-dispatch correlation, capture-basis semantics, bounded
tool vocabulary, exact int/bool rules, cross-field invariants, and exclusion of
raw arguments, results and reasoning. ``AttemptIdentity``, the corpus,
``VALID_TASK_IDS``, the OBS1 record kinds and the OBS1 schema/version are not
amended, not imported for authority, and not touched.

A projection failure is BOUNDED: availability goes false, one closed reason
code is recorded, every count is zeroed, and no exception text is retained.
"""

from __future__ import annotations

#: The exactly-zeroed shape an unavailable activity family must carry, so an
#: unavailable observation can never be mistaken for an observed absence of
#: activity. Sec. 22.3's own unavailable branch checks precisely this.
_UNAVAILABLE_COUNTS: dict[str, int] = {
    "runtime_reported_tool_execution_start_events": 0,
    "runtime_reported_tool_execution_end_events": 0,
    "runtime_reported_distinct_tool_call_ids": 0,
    "runtime_reported_aido_read_call_ids": 0,
    "runtime_reported_aido_read_end_observed": 0,
    "runtime_reported_aido_read_error_results": 0,
    "runtime_reported_aido_edit_call_ids": 0,
    "runtime_reported_aido_edit_end_observed": 0,
    "runtime_reported_aido_edit_error_results": 0,
    "runtime_reported_unexpected_tool_call_ids": 0,
    "runtime_reported_unexpected_tool_end_observed": 0,
    "runtime_reported_unexpected_tool_error_results": 0,
}


def unavailable_activity_fields(reason_code: str) -> dict[str, object]:
    """The bounded "no usable activity observation" field set.

    ``reason_code`` is one of the two closed literals -- ``PROJECTION_REFUSED``
    (the frozen projection itself refused) or ``INTERNAL_ERROR`` (anything
    else). No exception text, repr or traceback accompanies either.
    """
    fields: dict[str, object] = {
        "runtime_reported_tool_activity_available": False,
        "runtime_reported_tool_activity_capture_basis": None,
        "runtime_reported_unidentified_tool_call_id_seen": False,
        "activity_unavailable_reason": reason_code,
    }
    fields.update(_UNAVAILABLE_COUNTS)
    return fields


def project_cfg1_runtime_activity(
    *, activity: object, baseline: object, turn_outcome: object
) -> dict[str, object]:
    """Call the FROZEN projection, then flatten its snapshot into record fields.

    The projection and the snapshot type are imported here, at call time, from
    the frozen module -- never re-implemented, never subclassed, and never
    shadowed by a CFG1 symbol of the same name (T-6).
    """
    from qualification.runtime_activity import (
        ActivityRecordInvariantError,
        project_runtime_tool_activity,
    )

    try:
        snapshot = project_runtime_tool_activity(
            activity, baseline, turn_outcome=turn_outcome
        )
    except ActivityRecordInvariantError:
        return unavailable_activity_fields("PROJECTION_REFUSED")
    except Exception:  # noqa: BLE001 - bounded; no exception text retained
        return unavailable_activity_fields("INTERNAL_ERROR")

    return {
        "runtime_reported_tool_activity_available": True,
        "runtime_reported_tool_activity_capture_basis": snapshot.capture_basis,
        "runtime_reported_tool_execution_start_events": snapshot.tool_execution_start_events,
        "runtime_reported_tool_execution_end_events": snapshot.tool_execution_end_events,
        "runtime_reported_distinct_tool_call_ids": snapshot.distinct_tool_call_ids,
        "runtime_reported_unidentified_tool_call_id_seen": snapshot.unidentified_tool_call_id_seen,
        "runtime_reported_aido_read_call_ids": snapshot.aido_read_call_ids,
        "runtime_reported_aido_read_end_observed": snapshot.aido_read_end_observed,
        "runtime_reported_aido_read_error_results": snapshot.aido_read_error_results,
        "runtime_reported_aido_edit_call_ids": snapshot.aido_edit_call_ids,
        "runtime_reported_aido_edit_end_observed": snapshot.aido_edit_end_observed,
        "runtime_reported_aido_edit_error_results": snapshot.aido_edit_error_results,
        "runtime_reported_unexpected_tool_call_ids": snapshot.unexpected_tool_call_ids,
        "runtime_reported_unexpected_tool_end_observed": snapshot.unexpected_tool_end_observed,
        "runtime_reported_unexpected_tool_error_results": snapshot.unexpected_tool_error_results,
        "activity_unavailable_reason": None,
    }
