"""The value types the stage runner and a run executor exchange.

Kept in their own module, free of every live-runtime import, so the stage
runner can be exercised offline against a synthetic executor without pulling
in ``ar2.broker`` / ``ar2.supervisor`` as an import side effect (Sec. 11.3's
"pure Python, ``tmp_path``-scoped, no subprocess" discipline).

A run executor implements Sec. 16.2's L1-L28 for ONE admitted ordinal and is
**total**: it converts every failure it can encounter into an outcome carrying
bounded observation facts, exactly as Sec. 18's partial-failure table requires,
and never raises. It never decides admission, never emits an artifact, never
sees the stage-output authority, and never learns any ordinal's emission
status -- those are the stage runner's own, and keeping them there is what
makes ``ordinal_status`` a fact the runner OBSERVED rather than one it was
handed.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Cfg1RunAdmission:
    """Everything L0 hands one admitted run. No path, and no authority object.

    ``run_id`` is a fresh 128-bit nonce, minted per run and never persisted,
    never recorded, and never rendered -- it correlates in-memory ownership
    claims, and is on Sec. 21.2's forbidden-everywhere list for every sink.
    """

    stage_id: str
    stage_execution_id: str
    run_ordinal: int
    arm_id: str
    block: int
    position: int
    run_id: str = field(repr=False)

    def __repr__(self) -> str:  # noqa: D105 - run_id is never rendered
        return (
            f"{type(self).__name__}(stage_id={self.stage_id!r}, "
            f"run_ordinal={self.run_ordinal!r}, arm_id={self.arm_id!r}, "
            f"block={self.block!r}, position={self.position!r})"
        )


@dataclass(frozen=True)
class Cfg1RunOutcome:
    """One run's L28-finalized facts, as immutable plain data.

    ``observations`` carries exactly ``records.CFG1_RUN_OBSERVATION_KEYS_V2`` --
    no live object of any kind (no supervisor, activity, broker, ``RunState``,
    ``Popen``, handle, ``Path`` or authority), because the record is sealed
    only after every lifecycle outcome is known and must never hold a reference
    to something already torn down.

    ``safety`` is this run's :class:`~qualification.safety.ArtifactSafetyContext`
    -- the needles L29 scrubs against, built in memory and discarded after.
    Redaction and scrubbing are a BACKSTOP; nothing here claims a retained
    artifact is provably secret-free.

    ``live_references_released`` is the run's own contribution to Sec. 19.1
    item 4. The two process-level registries are checked by the runner itself.
    """

    observations: dict
    safety: object
    live_references_released: bool
    console_codes: tuple[str, ...] = ()
