"""Pre-dispatch baseline capture, and the frozen turn-outcome allowlist mapping.

Design Sec. 11.1 and Sec. 16.2 L17/L19. Both pieces exist so CFG1's OBS1
evidence is projected on exactly the same basis the frozen live qualification
adapter uses -- T-5 proves the equality, over every supervisor outcome literal
plus an unknown one.

**Why the baseline is a frozen set of call ids, not a count.**
``activity.tool_calls`` is keyed by CALL ID, not a monotonic counter, so a
delta-of-count cannot correlate its entries: a key present before this dispatch
would silently persist and be miscounted as this attempt's own activity. The
frozen pre-send snapshot makes the exclusion MECHANICAL.

**Why the outcome mapping is a POSITIVE allowlist.** Exactly two literals map
to a determinate outcome. Everything else -- recognized stream terminals AND
anything unrecognized -- fails closed to ``OBSERVATION_FAILED``, never guessed
into ``SETTLED`` or ``DEADLINE_REACHED``. An unrecognized literal must never
silently become the durable, plausible-looking ``wait_ended_before_settled``
fact a negative list would have produced.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Cfg1DispatchBaseline:
    """The correlation state captured immediately before the ONE prompt write.

    Semantically equal to the frozen live adapter's ``_DispatchBaseline``, and
    carrying the two fields ``project_runtime_tool_activity`` actually reads:
    the per-event-type counts it takes deltas against, and the frozen set of
    tool-call ids it excludes.
    """

    agent_loop_event_counts: dict[str, int] = field(repr=False)
    pre_dispatch_tool_call_ids: frozenset[str] = field(repr=False)

    def __repr__(self) -> str:  # noqa: D105 - bounded; ids are never rendered
        return (
            f"{type(self).__name__}(event_types={len(self.agent_loop_event_counts)}, "
            f"pre_dispatch_tool_call_id_count={len(self.pre_dispatch_tool_call_ids)})"
        )


def _agent_loop_event_types() -> tuple[str, ...]:
    """The FROZEN adapter's own event-type set, read at capture time.

    Deliberately the live adapter's ``_AGENT_LOOP_EVENT_TYPES`` rather than
    OBS1's narrower ``_TOOL_EXECUTION_EVENT_TYPES``: the projection only reads
    the two tool-execution kinds, but capturing the same set the frozen
    ``_DispatchBaseline`` captures is what makes T-5's equality genuine rather
    than "equal on the subset we happened to need". A locally aliased import of
    a frozen module's private name follows the precedent
    ``qualification.i2b_workspace`` already established for
    ``ar2.capability._verify_root_authority``; nothing frozen is amended.
    """
    from qualification.semantic_live_adapters import _AGENT_LOOP_EVENT_TYPES

    return tuple(_AGENT_LOOP_EVENT_TYPES)


def capture_cfg1_dispatch_baseline(supervisor) -> Cfg1DispatchBaseline:
    """Capture, strictly BEFORE the one prompt write (Sec. 16.2 L17).

    Every field is taken at the SAME pre-send instant: this function itself
    runs strictly before ``send_command``, and reads the supervisor's own live
    activity object exactly once.
    """
    activity = supervisor.activity
    return Cfg1DispatchBaseline(
        agent_loop_event_counts={
            kind: activity.event_type_counts.get(kind, 0)
            for kind in _agent_loop_event_types()
        },
        pre_dispatch_tool_call_ids=frozenset(activity.tool_calls.keys()),
    )


def map_turn_wait_outcome(outcome: object):
    """The frozen POSITIVE allowlist, as one pure mapping.

    ``runtime_settled`` -> ``SETTLED``; ``runtime_deadline_expired`` ->
    ``DEADLINE_REACHED``; every other recognized literal, and every
    unrecognized value of any type, -> ``OBSERVATION_FAILED``.
    """
    from ar2.supervisor import RUNTIME_DEADLINE_EXPIRED, RUNTIME_SETTLED
    from qualification.semantic_session import SemanticTurnOutcome

    if outcome == RUNTIME_SETTLED:
        return SemanticTurnOutcome.SETTLED
    if outcome == RUNTIME_DEADLINE_EXPIRED:
        return SemanticTurnOutcome.DEADLINE_REACHED
    return SemanticTurnOutcome.OBSERVATION_FAILED


#: The supervisor wait-outcome literal -> the run record's own bounded
#: ``runtime_wait_outcome`` domain. A literal outside this table records
#: ``UNRECOGNIZED``, never a guess.
def map_runtime_wait_outcome_literal(outcome: object) -> str:
    from ar2.supervisor import (
        RUNTIME_DEADLINE_EXPIRED,
        RUNTIME_EVENT_CAP_EXCEEDED,
        RUNTIME_EXITED_EARLY,
        RUNTIME_OUTPUT_CAP_EXCEEDED,
        RUNTIME_PROTOCOL_VIOLATION,
        RUNTIME_READ_ERROR,
        RUNTIME_SETTLED,
    )

    table = {
        RUNTIME_SETTLED: "SETTLED",
        RUNTIME_DEADLINE_EXPIRED: "DEADLINE_EXPIRED",
        RUNTIME_EXITED_EARLY: "EXITED_EARLY",
        RUNTIME_PROTOCOL_VIOLATION: "PROTOCOL_VIOLATION",
        RUNTIME_OUTPUT_CAP_EXCEEDED: "OUTPUT_CAP_EXCEEDED",
        RUNTIME_EVENT_CAP_EXCEEDED: "EVENT_CAP_EXCEEDED",
        RUNTIME_READ_ERROR: "READ_ERROR",
    }
    if type(outcome) is not str:
        return "UNRECOGNIZED"
    return table.get(outcome, "UNRECOGNIZED")
