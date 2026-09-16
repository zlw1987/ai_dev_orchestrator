"""The entire CFG1 public write/emission surface. Three functions, no paths.

Design Sec. 16.3.8 (the ten-step writer sequence), Sec. 16.3.8.1 (the one
emission-bytes pipeline and the exact ``65536`` bound), Sec. 16.3.8.2
(non-recursive fallback, the emission-phase model, and the post-create residue
policy), and Sec. 16.3.8.3 steps 8-10 (shared verbatim by the stage-closure
writer).

**No path crosses this boundary, in either direction.** A helper-returned bare
path is never an authority token: once returned it is an ordinary string,
indistinguishable from a hand-built one. So there is no public path-returning
helper at all -- a writer takes an authority, a schedule ordinal and a
payload, re-proves the authority as literally its first action, and derives
its own output path internally afterwards. ``arm_id`` is likewise derived from
the ordinal through the one shared schedule function, never accepted.

**The fallback window closes at the create CALL, not at a collision.** Step 10
is four distinct sub-actions -- create, write, flush, close -- and the create
can succeed and only afterwards have the write, flush or close fail, leaving
zero bytes, partial JSON, or complete bytes whose durability was never
established. A refusal fallback at that same path could then overwrite,
collide, or leave two artifacts of undefined relative trustworthiness. So the
moment ``FINAL_PATH_CREATE_ATTEMPTED`` is reached, no fallback is ever
attempted, under any subsequent outcome.

**Residue is never touched.** No overwrite, no truncate, no rename, no unlink
by pathname, ever -- and a structurally valid residue never retroactively
converts a failed live emission into a successful one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from . import MAX_CFG1_ARTIFACT_BYTES
from .halt import (
    EMISSION_COLLISION,
    EMISSION_EVIDENCE_REFUSED,
    EMISSION_FAILED,
    EMISSION_RECORD_EMITTED,
    PHASE_BYTES_FULLY_WRITTEN,
    PHASE_EMISSION_CONFIRMED,
    PHASE_FINAL_PATH_CREATE_ATTEMPTED,
    PHASE_FINAL_PATH_CREATED,
    PHASE_PRE_CREATE,
    CONSOLE_STAGE_CLOSURE_CREATE_COLLISION,
    CONSOLE_STAGE_CLOSURE_CREATE_FAILED,
    CONSOLE_STAGE_CLOSURE_PRE_CREATE_FAILED,
    CONSOLE_STAGE_CLOSURE_WRITE_FAILED,
)
from .records import (
    FINDING_AUTHORITY_BINDING,
    FINDING_RECORD_INVARIANT,
    FINDING_SCHEMA_VIOLATION,
    FINDING_SCRUB_NEEDLE_MATCH,
    FINDING_SIZE_BOUND_EXCEEDED,
    Cfg1RecordValidationError,
    _require_valid_cfg1_refusal_payload,
    _require_valid_cfg1_run_payload,
    _require_valid_cfg1_stage_closure_payload,
    _run_record_filename,
    _stage_closure_record_filename,
    build_cfg1_refusal_payload,
)
from .schedule import ScheduleError, _schedule_arm_for, declared_ordinals
from .stage_output import (
    CFG1StageOutputAuthority,
    verify_stage_output_authority,
)


class Cfg1WriterError(Exception):
    """A writer refused at an input gate. Bounded reason code only."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"cfg1 writer refused: {reason_code}")
        self.reason_code = reason_code


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Cfg1EmissionResult:
    """One run-scoped emission attempt's own observed outcome.

    ``emission_status`` is what the writer ITSELF observed at emission time,
    which is authoritative for classification even when a later, independent
    read of leftover bytes happens to succeed.
    """

    emission_status: str
    phase_reached: str
    self_validation_defect: bool
    fallback_attempted: bool
    console_code: str | None = None


@dataclass(frozen=True)
class Cfg1StageClosureEmissionResult:
    """The stage-closure writer's own live outcome. No fallback exists for it."""

    confirmed: bool
    phase_reached: str
    console_code: str | None = None


# ---------------------------------------------------------------------------
# The single emission-bytes pipeline (Sec. 16.3.8.1)
# ---------------------------------------------------------------------------


def _serialize_artifact(canonical: dict) -> bytes:
    """Serialize the canonical snapshot EXACTLY ONCE.

    Whatever bytes this returns are the bytes that get size-checked AND the
    bytes that get written -- never two separate serializations expected to
    agree. "Expected to agree" is exactly the assumption this pipeline closes:
    key ordering or escaping could diverge between two calls for reasons as
    mundane as a dict-ordering change elsewhere in the process, and a writer
    that reserialized could then write bytes the passed size check never
    actually measured.
    """
    return (
        json.dumps(canonical, indent=2, ensure_ascii=True, sort_keys=True) + "\n"
    ).encode("utf-8")


# -- filesystem seams. Named, module-level, and called through the module
# -- namespace so an offline regression can spy on or fail any one of the four
# -- sub-actions of step 10 independently (Sec. 16.3.8.2's phase model).


def _open_exclusive(path: str):
    """``O_CREAT | O_EXCL``. A ``FileExistsError`` IS the collision proof."""
    return open(path, "xb")  # noqa: SIM115 - the caller owns the handle's lifetime


def _write_all(handle, data: bytes) -> None:
    handle.write(data)


def _flush_handle(handle) -> None:
    handle.flush()


def _close_handle(handle) -> None:
    handle.close()


def _release_handle_quietly(handle) -> None:
    """Release an OS handle after a failed write. Never touches the bytes.

    Calls the underlying object's own ``close`` directly rather than the
    :func:`_close_handle` seam, so a regression that injected a close failure
    still gets its failure -- and the process still stops leaking a descriptor.
    This performs no truncate, no rename and no unlink: the residue is left
    exactly as the failed write left it.
    """
    try:
        handle.close()
    except Exception:  # noqa: BLE001 - best effort; never masks the real failure
        pass


def _build_refusal_payload(**kwargs) -> dict:
    """Seam over the refusal-payload builder, so construction can be exercised."""
    return build_cfg1_refusal_payload(**kwargs)


# ---------------------------------------------------------------------------
# Shared internal helpers
# ---------------------------------------------------------------------------


def _require_run_ordinal(authority: CFG1StageOutputAuthority, run_ordinal: object) -> int:
    """Step 2's ordinal gate. Exact ``int``; ``bool`` explicitly rejected."""
    if type(run_ordinal) is not int:
        raise Cfg1WriterError("MALFORMED_RUN_ORDINAL")
    if run_ordinal not in declared_ordinals(authority.stage_id):
        raise Cfg1WriterError("RUN_ORDINAL_OUT_OF_RANGE")
    return run_ordinal


def _run_output_path(authority: CFG1StageOutputAuthority, run_ordinal: int) -> str:
    """Step 9, internal only. Derives the arm itself; accepts no ``arm_id``.

    Never exposed as a return value a caller can capture and pass elsewhere:
    the only callers are this module's own writers and L0's absence check,
    both of which already hold the authority this path descends from.
    """
    arm_id = _schedule_arm_for(authority.stage_id, run_ordinal)
    filename = _run_record_filename(authority.stage_id, run_ordinal, arm_id)
    return str(_join(authority.execution_directory, filename))


def _stage_closure_output_path(authority: CFG1StageOutputAuthority) -> str:
    filename = _stage_closure_record_filename(authority.stage_id)
    return str(_join(authority.execution_directory, filename))


def _join(directory: str, filename: str):
    from pathlib import Path

    return Path(directory) / filename


def _canonicalize(payload: object) -> dict:
    """Step 4. ONE walk, inside a bounded except; no exception text retained.

    This is the FIRST point at which any field of the caller's payload is read
    at all -- steps 1-3 touch nothing but the authority, the ordinal, and the
    payload's exact type.
    """
    try:
        canonical = json.loads(json.dumps(payload))
    except Exception as exc:  # noqa: BLE001 - reduced at the catch point, Sec. 21.1
        raise Cfg1WriterError("PAYLOAD_NOT_CANONICALIZABLE") from exc
    if type(canonical) is not dict:
        raise Cfg1WriterError("PAYLOAD_NOT_CANONICALIZABLE")
    return canonical


def _scrub(canonical: dict, safety) -> None:
    """Step 8's scrub. A BACKSTOP, never a guarantee of secret-freedom."""
    from qualification.safety import qualification_scrub_check

    check = qualification_scrub_check(canonical, safety)
    if not check["clean"]:
        raise Cfg1WriterError("SCRUB_NEEDLE_MATCH")


def _size_check(artifact_bytes: bytes) -> None:
    """Step 8's bound -- the identical constant the verifier's read applies."""
    if len(artifact_bytes) > MAX_CFG1_ARTIFACT_BYTES:
        raise Cfg1WriterError("ARTIFACT_SIZE_BOUND_EXCEEDED")


@dataclass(frozen=True)
class _WriteOutcome:
    phase: str
    collided: bool
    failed: bool


def _write_artifact(path: str, artifact_bytes: bytes) -> _WriteOutcome:
    """Step 10's four sub-actions, each phase recorded as it is actually reached.

    Fail closed on ambiguity: only an unambiguous, platform-defined
    "path already existed" signal counts as a collision. Every other exception
    from the create call is treated identically to a write failure -- the path
    is NEVER inferred to be absent merely because the error was not
    ``FileExistsError``.
    """
    phase = PHASE_FINAL_PATH_CREATE_ATTEMPTED
    try:
        handle = _open_exclusive(path)
    except FileExistsError:
        return _WriteOutcome(phase=phase, collided=True, failed=True)
    except Exception:  # noqa: BLE001 - ambiguous create state, never "absent"
        return _WriteOutcome(phase=phase, collided=False, failed=True)

    phase = PHASE_FINAL_PATH_CREATED
    try:
        _write_all(handle, artifact_bytes)
        phase = PHASE_BYTES_FULLY_WRITTEN
        _flush_handle(handle)
        _close_handle(handle)
    except Exception:  # noqa: BLE001 - residue policy below; never repaired
        _release_handle_quietly(handle)
        return _WriteOutcome(phase=phase, collided=False, failed=True)

    return _WriteOutcome(phase=PHASE_EMISSION_CONFIRMED, collided=False, failed=False)


def _classify_pre_create_failure(error: Exception) -> tuple[tuple[str, ...], int, bool]:
    """Map one bounded ``PRE_CREATE`` failure to findings and the halt bool.

    Returns ``(finding_categories, finding_count, self_validation_defect)``.

    Only an ordinary scrub-needle hit leaves ``self_validation_defect`` false
    (Sec. 18 row 11, the one non-halting emission refusal). Every other
    pre-create failure is an implementation defect (row 15), and Sec. 19.1
    item 2's second clause makes that a halt REGARDLESS of whether the
    ensuing refusal artifact is written successfully -- a successfully written
    refusal does not convert a defect into an admissible next run.
    """
    if isinstance(error, Cfg1RecordValidationError):
        return (
            tuple(sorted({error.category, FINDING_RECORD_INVARIANT})),
            2,
            True,
        )
    reason = getattr(error, "reason_code", "")
    if reason == "SCRUB_NEEDLE_MATCH":
        return ((FINDING_SCRUB_NEEDLE_MATCH,), 1, False)
    if reason == "ARTIFACT_SIZE_BOUND_EXCEEDED":
        return ((FINDING_SIZE_BOUND_EXCEEDED,), 1, True)
    if reason == "AUTHORITY_BINDING_MISMATCH":
        return ((FINDING_AUTHORITY_BINDING,), 1, True)
    return (
        tuple(sorted({FINDING_SCHEMA_VIOLATION, FINDING_RECORD_INVARIANT})),
        2,
        True,
    )


# ---------------------------------------------------------------------------
# emit_cfg1_run_record -- the primary run-scoped writer
# ---------------------------------------------------------------------------


def emit_cfg1_run_record(
    authority: CFG1StageOutputAuthority,
    /,
    *,
    run_ordinal: int,
    payload: dict,
    lifecycle_all_closed: bool,
    safety,
) -> Cfg1EmissionResult:
    """Sec. 16.3.8's ten-step sequence, no step skipped or reordered.

    ``authority`` is positional-only and everything else keyword-only, so any
    additional positional argument -- a path-shaped one in particular -- raises
    ``TypeError`` from Python's own argument binding, before a single line of
    this function runs (T-39).

    ``safety`` is the run's :class:`~qualification.safety.ArtifactSafetyContext`
    -- a bundle of values to be SEARCHED FOR and refused, never a destination.
    It is not a path parameter in the sense T-21/T-38 forbid, and it grants no
    write authority of any kind.
    """
    # Step 1 -- unconditional, before touching run_ordinal or payload at all.
    # A failure here is a Sec. 16.3.7 HARD STOP, not an emission failure: the
    # very location a refusal record would need is what failed provenance, so
    # this propagates rather than attempting any fallback.
    verify_stage_output_authority(authority)

    # Step 2 -- schedule identity from TRUSTED arguments only.
    ordinal = _require_run_ordinal(authority, run_ordinal)
    arm_id = _schedule_arm_for(authority.stage_id, ordinal)

    # Step 3 -- exact type gate, with ZERO payload-field reads having occurred.
    if type(payload) is not dict:
        raise Cfg1WriterError("PAYLOAD_NOT_A_DICT")
    if type(lifecycle_all_closed) is not bool:
        raise Cfg1WriterError("MALFORMED_LIFECYCLE_ALL_CLOSED")

    try:
        canonical = _canonicalize(payload)  # step 4 -- the ONE walk
        # Step 5 -- `payload` is never read again from this line on.
        _require_valid_cfg1_run_payload(canonical)  # step 6
        _bind_run_identity(canonical, authority, ordinal, arm_id)  # step 7
        _scrub(canonical, safety)  # step 8a
        artifact_bytes = _serialize_artifact(canonical)  # step 8b -- ONCE
        _size_check(artifact_bytes)  # step 8c
    except (Cfg1WriterError, Cfg1RecordValidationError, ScheduleError) as exc:
        categories, count, defect = _classify_pre_create_failure(exc)
        return _attempt_refusal_fallback(
            authority,
            run_ordinal=ordinal,
            finding_categories=categories,
            finding_count=count,
            lifecycle_all_closed=lifecycle_all_closed,
            safety=safety,
            self_validation_defect=defect,
        )

    path = _run_output_path(authority, ordinal)  # step 9
    outcome = _write_artifact(path, artifact_bytes)  # step 10
    if not outcome.failed:
        return Cfg1EmissionResult(
            emission_status=EMISSION_RECORD_EMITTED,
            phase_reached=PHASE_EMISSION_CONFIRMED,
            self_validation_defect=False,
            fallback_attempted=False,
        )
    # FINAL_PATH_CREATE_ATTEMPTED was reached: NO fallback, under any outcome.
    return Cfg1EmissionResult(
        emission_status=EMISSION_COLLISION if outcome.collided else EMISSION_FAILED,
        phase_reached=outcome.phase,
        self_validation_defect=False,
        fallback_attempted=False,
        console_code="RUN_RECORD_CREATE_COLLIDED"
        if outcome.collided
        else "RUN_RECORD_WRITE_FAILED",
    )


def _bind_run_identity(
    canonical: dict, authority: CFG1StageOutputAuthority, ordinal: int, arm_id: str
) -> None:
    """Step 7 -- bind the canonical snapshot to THIS writer's own identity.

    Every equality compares against the writer's own authority, ordinal and
    derived arm -- never against another field of the same payload. A canonical
    payload can agree with itself perfectly while belonging to a different
    stage execution entirely, which is exactly what this step refuses.
    """
    expected_filename = _run_record_filename(authority.stage_id, ordinal, arm_id)
    if (
        canonical.get("stage_id") != authority.stage_id
        or canonical.get("stage_execution_id") != authority.stage_execution_id
        or canonical.get("run_ordinal") != ordinal
        or type(canonical.get("run_ordinal")) is not int
        or canonical.get("arm_id") != arm_id
        or canonical.get("record_filename") != expected_filename
    ):
        raise Cfg1WriterError("AUTHORITY_BINDING_MISMATCH")


def _attempt_refusal_fallback(
    authority: CFG1StageOutputAuthority,
    *,
    run_ordinal: int,
    finding_categories: tuple[str, ...],
    finding_count: int,
    lifecycle_all_closed: bool,
    safety,
    self_validation_defect: bool,
) -> Cfg1EmissionResult:
    """The ONE permitted refusal fallback, for a ``PRE_CREATE`` primary failure.

    The refusal artifact is built FRESHLY from authority identity, the
    schedule-derived ordinal and arm, the bounded finding categories, and the
    already-finalized lifecycle bool -- never from arbitrary fields of the
    rejected payload. No recursion exists: this is called at most once, and
    :func:`emit_cfg1_refusal_record` never calls itself or this function.
    """
    try:
        refusal_payload = _build_refusal_payload(
            stage_id=authority.stage_id,
            stage_execution_id=authority.stage_execution_id,
            run_ordinal=run_ordinal,
            finding_count=finding_count,
            finding_categories=finding_categories,
            lifecycle_all_closed=lifecycle_all_closed,
        )
    except Exception:  # noqa: BLE001 - bounded; no exception text retained
        return Cfg1EmissionResult(
            emission_status=EMISSION_FAILED,
            phase_reached=PHASE_PRE_CREATE,
            self_validation_defect=self_validation_defect,
            fallback_attempted=True,
            console_code="REFUSAL_RECORD_CONSTRUCTION_FAILED",
        )

    result = emit_cfg1_refusal_record(
        authority,
        run_ordinal=run_ordinal,
        refusal_payload=refusal_payload,
        safety=safety,
    )
    return Cfg1EmissionResult(
        emission_status=result.emission_status,
        phase_reached=result.phase_reached,
        self_validation_defect=self_validation_defect,
        fallback_attempted=True,
        console_code=result.console_code,
    )


# ---------------------------------------------------------------------------
# emit_cfg1_refusal_record -- never recursive, at any phase, for any cause
# ---------------------------------------------------------------------------


def emit_cfg1_refusal_record(
    authority: CFG1StageOutputAuthority,
    /,
    *,
    run_ordinal: int,
    refusal_payload: dict,
    safety,
) -> Cfg1EmissionResult:
    """Emit one bounded refusal artifact at the schedule-derived RUN path.

    **This writer never emits another refusal record for its own failure** --
    regardless of whether that failure was ``PRE_CREATE``, a create collision,
    a non-collision create error, or a post-create write/flush/close failure.
    It returns one bounded emission-failure result and nothing else.

    Its own create collision is classified IDENTICALLY to the primary writer's
    (``EMISSION_COLLISION``): the distinction this design draws is never
    "primary writer versus refusal writer", always "collision versus every
    other failure mode", applied to whichever writer's own create call failed.
    """
    verify_stage_output_authority(authority)
    ordinal = _require_run_ordinal(authority, run_ordinal)
    arm_id = _schedule_arm_for(authority.stage_id, ordinal)

    if type(refusal_payload) is not dict:
        raise Cfg1WriterError("PAYLOAD_NOT_A_DICT")

    try:
        canonical = _canonicalize(refusal_payload)
        _require_valid_cfg1_refusal_payload(canonical)
        _bind_refusal_identity(canonical, authority, ordinal, arm_id)
        _scrub(canonical, safety)
        artifact_bytes = _serialize_artifact(canonical)
        _size_check(artifact_bytes)
    except (Cfg1WriterError, Cfg1RecordValidationError, ScheduleError) as exc:
        return Cfg1EmissionResult(
            emission_status=EMISSION_FAILED,
            phase_reached=PHASE_PRE_CREATE,
            self_validation_defect=False,
            fallback_attempted=False,
            console_code=f"REFUSAL_RECORD_PRE_CREATE_FAILED:{getattr(exc, 'reason_code', 'UNKNOWN')}",
        )

    path = _run_output_path(authority, ordinal)
    outcome = _write_artifact(path, artifact_bytes)
    if not outcome.failed:
        return Cfg1EmissionResult(
            emission_status=EMISSION_EVIDENCE_REFUSED,
            phase_reached=PHASE_EMISSION_CONFIRMED,
            self_validation_defect=False,
            fallback_attempted=False,
        )
    return Cfg1EmissionResult(
        emission_status=EMISSION_COLLISION if outcome.collided else EMISSION_FAILED,
        phase_reached=outcome.phase,
        self_validation_defect=False,
        fallback_attempted=False,
        console_code="REFUSAL_RECORD_CREATE_COLLIDED"
        if outcome.collided
        else "REFUSAL_RECORD_WRITE_FAILED",
    )


def _bind_refusal_identity(
    canonical: dict, authority: CFG1StageOutputAuthority, ordinal: int, arm_id: str
) -> None:
    """A refusal record cannot claim a different stage execution than its writer."""
    expected_filename = _run_record_filename(authority.stage_id, ordinal, arm_id)
    if (
        canonical.get("stage_id") != authority.stage_id
        or canonical.get("stage_execution_id") != authority.stage_execution_id
        or canonical.get("run_ordinal") != ordinal
        or type(canonical.get("run_ordinal")) is not int
        or canonical.get("arm_id") != arm_id
        or canonical.get("record_filename") != expected_filename
    ):
        raise Cfg1WriterError("AUTHORITY_BINDING_MISMATCH")


# ---------------------------------------------------------------------------
# emit_cfg1_stage_closure -- decision-backed, never payload-backed
# ---------------------------------------------------------------------------


def emit_cfg1_stage_closure(
    authority: CFG1StageOutputAuthority, /, *, decision
) -> Cfg1StageClosureEmissionResult:
    """Sec. 16.3.8.3's adapted sequence; Sec. 16.3.8 steps 8-10 unchanged.

    Its ONLY parameters are ``authority`` and ``decision``. There is
    deliberately no ``payload``, no ``ordinal_status``, no
    ``halted_after_ordinal``, no ``halt_reason_code``, no ``record_filename``,
    no ``stage_id`` and no ``stage_execution_id`` -- internal self-consistency
    of a caller-supplied payload is not provenance that the payload equals the
    decision L30 actually reached.

    The scrub runs against an explicit "nothing to declare" safety context: a
    stage-closure record carries only closed literals, schedule-sized ordinal
    statuses and a closed halt code, so there is no run-scoped endpoint,
    credential, pipe name or workspace path for it to contain. Saying so
    explicitly is the point of the named constructor -- a caller who forgot a
    context would otherwise get the same silent success.

    **No fallback of any kind exists here.** Every one of the six failure
    causes resolves identically: live result FAILED, console-only bounded
    report, no replacement name, no refusal record, authority retired by the
    caller, any residue left completely untouched.
    """
    from qualification.safety import ArtifactSafetyContext

    from .stage_decision import (
        CFG1StageClosureDecision,
        Cfg1StageDecisionError,
        _revoke_decision_consumability,
        _verify_sealed_decision,
    )

    # Step 1 -- identical to Sec. 16.3.8 step 1, before touching `decision`.
    verify_stage_output_authority(authority)

    # Step 2 -- exact type, zero field reads on anything else.
    if type(decision) is not CFG1StageClosureDecision:
        raise Cfg1WriterError("NOT_A_STAGE_CLOSURE_DECISION")

    # Steps 3 and 4 -- authenticity re-proof and the authority-rebinding gate.
    _verify_sealed_decision(decision, authority)

    # Step 4a -- revoke this decision's own consumability entry, unconditionally,
    # BEFORE any payload is built and regardless of how steps 5-10 resolve.
    # This touches the decision registry ONLY; the per-authority seal-history
    # fact is a separate registry this step has no authority over.
    _revoke_decision_consumability(decision)

    try:
        # Step 5 -- built internally from `authority` and the immutable,
        # already-re-verified `decision`. Nothing untrusted was ever accepted,
        # so there is no analogue of steps 3-4's canonicalization here.
        canonical = {
            "experiment": _stage_closure_header()[0],
            "record_version": _stage_closure_header()[1],
            "record_kind": _stage_closure_header()[2],
            "stage_id": authority.stage_id,
            "stage_execution_id": authority.stage_execution_id,
            "record_filename": _stage_closure_record_filename(authority.stage_id),
            "ordinal_status": {
                str(ordinal): status for ordinal, status in decision.ordinal_status
            },
            "halted_after_ordinal": decision.halted_after_ordinal,
            "halt_reason_code": decision.halt_reason_code,
        }
        # Step 6 -- the same dispatched validator, unchanged, for the same
        # reason every writer runs one: a final, independent structural check.
        _require_valid_cfg1_stage_closure_payload(canonical)
        # Step 7 holds by construction (canonical was built FROM authority);
        # re-asserted defensively, exactly as every other writer does.
        if (
            canonical["stage_id"] != authority.stage_id
            or canonical["stage_execution_id"] != authority.stage_execution_id
            or canonical["record_filename"]
            != _stage_closure_record_filename(authority.stage_id)
        ):
            raise Cfg1WriterError("AUTHORITY_BINDING_MISMATCH")
        _scrub(canonical, ArtifactSafetyContext.none_declared())  # step 8a
        artifact_bytes = _serialize_artifact(canonical)  # step 8b -- ONCE
        _size_check(artifact_bytes)  # step 8c
    except (Cfg1WriterError, Cfg1RecordValidationError, Cfg1StageDecisionError):
        return Cfg1StageClosureEmissionResult(
            confirmed=False,
            phase_reached=PHASE_PRE_CREATE,
            console_code=CONSOLE_STAGE_CLOSURE_PRE_CREATE_FAILED,
        )

    path = _stage_closure_output_path(authority)  # step 9
    outcome = _write_artifact(path, artifact_bytes)  # step 10
    if not outcome.failed:
        return Cfg1StageClosureEmissionResult(
            confirmed=True, phase_reached=PHASE_EMISSION_CONFIRMED
        )
    if outcome.collided:
        console_code = CONSOLE_STAGE_CLOSURE_CREATE_COLLISION
    elif outcome.phase == PHASE_FINAL_PATH_CREATE_ATTEMPTED:
        console_code = CONSOLE_STAGE_CLOSURE_CREATE_FAILED
    else:
        console_code = CONSOLE_STAGE_CLOSURE_WRITE_FAILED
    return Cfg1StageClosureEmissionResult(
        confirmed=False, phase_reached=outcome.phase, console_code=console_code
    )


def _stage_closure_header() -> tuple[str, str, str]:
    from . import (
        PACKAGE_ID,
        STAGE_CLOSURE_RECORD_KIND,
        STAGE_CLOSURE_RECORD_VERSION,
    )

    return PACKAGE_ID, STAGE_CLOSURE_RECORD_VERSION, STAGE_CLOSURE_RECORD_KIND


__all__ = [
    "Cfg1EmissionResult",
    "Cfg1StageClosureEmissionResult",
    "Cfg1WriterError",
    "emit_cfg1_run_record",
    "emit_cfg1_refusal_record",
    "emit_cfg1_stage_closure",
]
