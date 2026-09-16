"""The ONE frozen CFG1 schedule, and the ONE derivation every consumer calls.

Design Sec. 7.3 (Stage 1) and Sec. 7.3a (Stage 2, frozen by FU7). Sec. 19.6
derives ``LAST_ORDINAL`` from this same mapping rather than pinning a second
integer constant that could drift out of agreement with the tables.

**Identity, not coincidence.** ``_schedule_arm_for`` is the one callable that
L0 admission, run-payload construction, the writers, the record validators
and the post-hoc artifact-binding verifiers all invoke -- proven by identity
of the underlying callable object (T-42 for S1, T-93 for S2), never by five
independent lookups that happen to agree today.
"""

from __future__ import annotations


class ScheduleError(Exception):
    """A stage id or run ordinal is outside the frozen schedule's domain."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"cfg1 schedule refused: {reason_code}")
        self.reason_code = reason_code


#: The closed stage domain. No third stage exists, and none may be added
#: without a design amendment.
STAGE_IDS: tuple[str, ...] = ("S1", "S2")

#: The closed arm domain across both stages (design Sec. 7.2).
ARM_IDS: tuple[str, ...] = ("Q", "R", "E", "H")

#: Arms each stage may legitimately schedule. Stage 1 never contains H; Stage
#: 2 contrasts Q against H only.
STAGE_ARMS: dict[str, tuple[str, ...]] = {
    "S1": ("Q", "R", "E"),
    "S2": ("Q", "H"),
}

#: Design Sec. 7.3 -- nine runs, three blocks of three, each arm occupying
#: each within-block position exactly once.
_S1_SCHEDULE: dict[int, str] = {
    1: "Q", 2: "R", 3: "E",
    4: "R", 5: "E", 6: "Q",
    7: "E", 8: "Q", 9: "R",
}

#: Design Sec. 7.3a (FU7) -- six runs, three blocks of two, FROZEN rather than
#: illustrative. Exact positional balance is impossible with three pairs of two
#: arms; that asymmetry is accepted, exactly as it was when this table was only
#: an example.
_S2_SCHEDULE: dict[int, str] = {
    1: "Q", 2: "H",
    3: "H", 4: "Q",
    5: "Q", 6: "H",
}

#: THE schedule mapping. ``_schedule_arm_for`` and ``LAST_ORDINAL`` both read
#: this module global at call time, so there is exactly one source of schedule
#: truth in the process (T-129's synthetic-schedule companion assertion relies
#: on that being genuinely true rather than a hard-coded pair of integers).
SCHEDULE: dict[str, dict[int, str]] = {
    "S1": _S1_SCHEDULE,
    "S2": _S2_SCHEDULE,
}

#: Within-block size per stage: three arms per block for S1, two for S2.
BLOCK_SIZE: dict[str, int] = {"S1": 3, "S2": 2}


def _require_stage_id(stage_id: object) -> str:
    """``type(stage_id) is str`` exactly, and a member of the closed domain."""
    if type(stage_id) is not str or stage_id not in SCHEDULE:
        raise ScheduleError("UNKNOWN_STAGE_ID")
    return stage_id


def _require_run_ordinal(stage_id: str, run_ordinal: object) -> int:
    """Exact ``int`` typing, then declared-range membership.

    ``bool`` is an ``int`` subclass, so ``True``/``False`` would otherwise
    silently become ordinals 1 and 0. ``type(...) is int`` refuses both, and
    refuses a ``str`` ordinal, before any schedule lookup is attempted (T-41).
    """
    if type(run_ordinal) is not int:
        raise ScheduleError("MALFORMED_RUN_ORDINAL")
    if run_ordinal not in SCHEDULE[stage_id]:
        raise ScheduleError("RUN_ORDINAL_OUT_OF_RANGE")
    return run_ordinal


def _schedule_arm_for(stage_id: object, run_ordinal: object) -> str:
    """The arm the frozen schedule assigns to ``(stage_id, run_ordinal)``.

    THE one derivation (design Sec. 16.3.8.1). There is deliberately no
    parameter through which a caller supplies an arm, anywhere in this
    package's write/emission surface.
    """
    stage = _require_stage_id(stage_id)
    ordinal = _require_run_ordinal(stage, run_ordinal)
    return SCHEDULE[stage][ordinal]


def _schedule_block_position(stage_id: object, run_ordinal: object) -> tuple[int, int]:
    """``(block, position)`` for one ordinal, from the same frozen tables.

    ``block = ((ordinal - 1) // size) + 1``; ``position = ((ordinal - 1) %
    size) + 1``, with ``size`` the stage's own block size (3 for S1, 2 for S2).
    """
    stage = _require_stage_id(stage_id)
    ordinal = _require_run_ordinal(stage, run_ordinal)
    size = BLOCK_SIZE[stage]
    return ((ordinal - 1) // size) + 1, ((ordinal - 1) % size) + 1


def LAST_ORDINAL(stage_id: object) -> int:  # noqa: N802 - design Sec. 19.6's own name
    """The stage's final declared ordinal, DERIVED from ``SCHEDULE`` itself.

    Never a second, separately-pinned integer: ``9`` and ``6`` are
    consequences of the already-frozen tables, so a schedule change cannot
    leave a duplicated literal behind disagreeing with it (T-129).
    """
    stage = _require_stage_id(stage_id)
    return max(SCHEDULE[stage])


def declared_ordinals(stage_id: object) -> tuple[int, ...]:
    """Every ordinal this stage declares, ascending. Used for ``ordinal_status``."""
    stage = _require_stage_id(stage_id)
    return tuple(sorted(SCHEDULE[stage]))
