"""Halt vocabulary, halt precedence, and the console-only stage dispositions.

Design Sec. 19.4 (the exact, closed ``HALT_REASON_CODES``) and Sec. 19.5 (the
one shared, deterministic precedence function).

**Derivation, not invention.** Every halt this design can produce is, by
construction, exactly a failure of one of Sec. 19.1's four admission
conditions -- that is what "the stage HALTS" means. So the complete set is one
code per admission condition, with item 2 split into its two independent
clauses, giving exactly six members. No seventh code, no alias, and no code
inferred from a novel failure mode may be added without a separate design
amendment.

**Console-only codes are a SEPARATE vocabulary.** Four stage-ending cases
write no confirmed stage-closure record at all, so there is no durable field
in which a code for them could truthfully live. They are reported exclusively
through the bounded console sink (Sec. 21.2) and are proven absent from
``HALT_REASON_CODES`` and from all three record schemas (T-141).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Emission-status vocabulary (Sec. 16.3.8.2 / Sec. 22.4.2)
# ---------------------------------------------------------------------------

#: A valid run record was successfully emitted (``EMISSION_CONFIRMED`` reached
#: for the primary run-record writer).
EMISSION_RECORD_EMITTED = "RECORD_EMITTED"

#: A valid REFUSAL record was successfully emitted at the run path -- whether
#: triggered by an ordinary row-11 scrub refusal (non-halting) or a row-15
#: implementation defect (halting). The halt metadata, not this status,
#: disambiguates the two.
EMISSION_EVIDENCE_REFUSED = "EVIDENCE_REFUSED"

#: The final run path collided at ``FINAL_PATH_CREATE_ATTEMPTED``. No new
#: valid run-path artifact was emitted by this run.
EMISSION_COLLISION = "EMISSION_COLLISION"

#: No successfully-confirmed run-path or refusal-path emission exists for this
#: ordinal, and the failure was NOT the path-collision case. A structurally
#: valid residue found later by the post-hoc verifier never changes this.
EMISSION_FAILED = "EMISSION_FAILED"

#: This ordinal never ran, because the stage had already halted at or before it.
ORDINAL_NOT_EXECUTED = "NOT_EXECUTED"

#: The exact per-ordinal status domain of a stage-closure record.
ORDINAL_STATUS_VALUES: frozenset[str] = frozenset(
    {
        EMISSION_RECORD_EMITTED,
        EMISSION_EVIDENCE_REFUSED,
        EMISSION_COLLISION,
        EMISSION_FAILED,
        ORDINAL_NOT_EXECUTED,
    }
)

#: The two statuses Sec. 19.1 item 3 admits on.
ADMISSIBLE_EMISSION_STATUSES: frozenset[str] = frozenset(
    {EMISSION_RECORD_EMITTED, EMISSION_EVIDENCE_REFUSED}
)


# ---------------------------------------------------------------------------
# Sec. 16.3.8.2 -- the frozen emission-phase vocabulary
# ---------------------------------------------------------------------------

#: Steps 1-9 of Sec. 16.3.8; the final path has not been touched in any way.
#: This is the ONLY phase from which a primary run-record failure may attempt
#: its one permitted refusal fallback.
PHASE_PRE_CREATE = "PRE_CREATE"

#: The exclusive-create call has been ISSUED; its outcome may be success, a
#: collision, or an ambiguous OS-level failure. Reaching this phase closes the
#: fallback window permanently, under every subsequent outcome.
PHASE_FINAL_PATH_CREATE_ATTEMPTED = "FINAL_PATH_CREATE_ATTEMPTED"

#: That call returned success: the path now exists, owned by this attempt.
PHASE_FINAL_PATH_CREATED = "FINAL_PATH_CREATED"

#: Every byte of ``artifact_bytes`` has been transferred to the open file.
PHASE_BYTES_FULLY_WRITTEN = "BYTES_FULLY_WRITTEN"

#: Flush and close both completed without error. This writer's own local write
#: sequence is done -- never a durability, fsync or storage-layer claim.
PHASE_EMISSION_CONFIRMED = "EMISSION_CONFIRMED"

EMISSION_PHASES: tuple[str, ...] = (
    PHASE_PRE_CREATE,
    PHASE_FINAL_PATH_CREATE_ATTEMPTED,
    PHASE_FINAL_PATH_CREATED,
    PHASE_BYTES_FULLY_WRITTEN,
    PHASE_EMISSION_CONFIRMED,
)


# ---------------------------------------------------------------------------
# Sec. 19.4 -- the exact, closed halt vocabulary
# ---------------------------------------------------------------------------

#: Sec. 19.1 item 2, clause 1 -- ``run_classification == REFUSED_PRE_DISPATCH``.
HALT_PRE_DISPATCH_REFUSAL = "PRE_DISPATCH_REFUSAL"

#: Sec. 19.1 item 1 -- ``lifecycle_all_closed == false``.
HALT_LIFECYCLE_CLOSURE_UNPROVEN = "LIFECYCLE_CLOSURE_UNPROVEN"

#: Sec. 19.1 item 2, clause 2 -- ``halt_triggered_by_this_run == true``: the
#: row-15 record-self-validation implementation defect.
HALT_RUN_RECORD_SELF_VALIDATION_FAILED = "RUN_RECORD_SELF_VALIDATION_FAILED"

#: Sec. 19.1 item 3, ``EMISSION_COLLISION`` -- a genuine create collision at
#: either run-path writer's own ``FINAL_PATH_CREATE_ATTEMPTED``.
HALT_RUN_RECORD_EMISSION_COLLISION = "RUN_RECORD_EMISSION_COLLISION"

#: Sec. 19.1 item 3, ``EMISSION_FAILED``. Deliberately NEUTRAL: it covers a
#: direct post-create primary failure with zero fallback attempts, a
#: ``PRE_CREATE`` primary failure whose one permitted fallback itself later
#: failed, and a refusal writer's own post-create failure -- and it asserts
#: NOTHING about which of the three occurred. (Renamed from FU7's
#: ``RUN_RECORD_REFUSAL_FALLBACK_FAILED``, which falsely claimed a fallback
#: attempt in every case it covered.)
HALT_RUN_RECORD_EMISSION_FAILED = "RUN_RECORD_EMISSION_FAILED"

#: Sec. 19.1 item 4 -- run-scoped registries or live references not empty.
HALT_RUN_SCOPED_REGISTRY_NOT_EMPTY = "RUN_SCOPED_REGISTRY_NOT_EMPTY"

#: Exactly six members. THE one object, imported by identity by both the
#: stage-closure validator and the L30 admission-decision logic -- never two
#: independently-maintained lists that happen to agree today (T-90).
HALT_REASON_CODES: frozenset[str] = frozenset(
    {
        HALT_PRE_DISPATCH_REFUSAL,
        HALT_LIFECYCLE_CLOSURE_UNPROVEN,
        HALT_RUN_RECORD_SELF_VALIDATION_FAILED,
        HALT_RUN_RECORD_EMISSION_COLLISION,
        HALT_RUN_RECORD_EMISSION_FAILED,
        HALT_RUN_SCOPED_REGISTRY_NOT_EMPTY,
    }
)


# ---------------------------------------------------------------------------
# Console-only stage dispositions -- outside every durable schema (Sec. 21.2)
# ---------------------------------------------------------------------------

#: Sec. 16.3.7 -- ``RESULTS_ROOT`` or the execution directory failed provenance.
DISPOSITION_STAGE_OUTPUT_AUTHORITY_HARD_STOP = "STAGE_OUTPUT_AUTHORITY_HARD_STOP"

#: Sec. 18 row 17 -- the stage-closure record's OWN emission failed.
DISPOSITION_STAGE_CLOSURE_EMISSION_FAILED = "STAGE_CLOSURE_EMISSION_FAILED"

#: Sec. 16.3.10 -- the schedule-derived path for the ordinal about to be
#: admitted already exists, discovered by L0's own absence check BEFORE that
#: ordinal is admitted, so no run exists for ``halted_after_ordinal`` to name.
DISPOSITION_OUTPUT_NAMESPACE_PREOCCUPIED = "OUTPUT_NAMESPACE_PREOCCUPIED"

#: Sec. 16.3.8.3 -- the terminal-decision mint sequence failed, so no genuine
#: ``CFG1StageClosureDecision`` ever existed to author a closure record.
DISPOSITION_STAGE_DECISION_MINT_FAILED = "STAGE_DECISION_MINT_FAILED"

#: Ordinary terminal dispositions that DO write a confirmed closure record.
DISPOSITION_STAGE_COMPLETED = "STAGE_COMPLETED"
DISPOSITION_STAGE_HALTED = "STAGE_HALTED"

#: The EXACT four stage-ending cases that write no confirmed stage-closure
#: record, and therefore need -- and must never be given -- a
#: ``halt_reason_code``. Cited by Sec. 19.4 and Sec. 22.4.2 alike; T-123 and
#: T-141 audit that both sections' prose still enumerate exactly these four.
NO_CONFIRMED_STAGE_CLOSURE_CASES: frozenset[str] = frozenset(
    {
        DISPOSITION_STAGE_OUTPUT_AUTHORITY_HARD_STOP,
        DISPOSITION_STAGE_CLOSURE_EMISSION_FAILED,
        DISPOSITION_OUTPUT_NAMESPACE_PREOCCUPIED,
        DISPOSITION_STAGE_DECISION_MINT_FAILED,
    }
)

#: Optional, console-only diagnostic codes distinguishing the stage-closure
#: writer's own create-attempt causes. Neither ever becomes a durable
#: ``halt_reason_code``: the artifact that would carry one was never confirmed.
CONSOLE_STAGE_CLOSURE_CREATE_COLLISION = "STAGE_CLOSURE_CREATE_COLLISION"
CONSOLE_STAGE_CLOSURE_CREATE_FAILED = "STAGE_CLOSURE_CREATE_FAILED"
CONSOLE_STAGE_CLOSURE_PRE_CREATE_FAILED = "STAGE_CLOSURE_PRE_CREATE_FAILED"
CONSOLE_STAGE_CLOSURE_WRITE_FAILED = "STAGE_CLOSURE_WRITE_FAILED"


# ---------------------------------------------------------------------------
# Sec. 19.5 -- the one shared halt-reason precedence
# ---------------------------------------------------------------------------

#: Kept beside :func:`_resolve_halt_reason_code` purely as documentation of the
#: frozen evaluation order. The function itself is the authority; this tuple is
#: never consulted by it, so the two can never disagree about behaviour.
HALT_REASON_PRECEDENCE: tuple[str, ...] = (
    HALT_RUN_RECORD_EMISSION_COLLISION,
    HALT_RUN_RECORD_EMISSION_FAILED,
    HALT_RUN_RECORD_SELF_VALIDATION_FAILED,
    HALT_LIFECYCLE_CLOSURE_UNPROVEN,
    HALT_PRE_DISPATCH_REFUSAL,
    HALT_RUN_SCOPED_REGISTRY_NOT_EMPTY,
)

#: The one classification literal Sec. 19.5 step 5 tests for. Declared here as
#: well as in :mod:`classification` would be two sources of truth, so it is
#: imported lazily inside the function instead.


def _resolve_halt_reason_code(
    *,
    emission_status: str,
    halt_triggered_by_this_run: bool,
    lifecycle_all_closed: bool,
    run_classification: str,
    registries_empty: bool,
) -> str | None:
    """The frozen six-step precedence. First match wins; ``None`` means no halt.

    Multiple Sec. 19.1 conditions can fail simultaneously for the same run, and
    a stage-closure record has exactly ONE ``halt_reason_code`` per halted
    ordinal. Without a frozen order, two implementations -- or the same
    implementation on two runs of the same failure class -- could durably
    record different codes for mechanically identical situations.

    **The ordering is a design choice, not a tie-break.** The two
    emission-outcome checks come first so that an emission failure discovered
    while trying to persist evidence of a lower-priority defect takes durable
    precedence over that defect: a reader checking ``results/`` for admissible
    evidence needs "this ordinal's evidence could not be confirmed on disk"
    foremost. The underlying defect remains available through the bounded
    console channel, never as raw text in durable evidence.

    THE one shared callable -- L30's own sealing call site invokes exactly this
    object, and the stage-closure validator cites the same ``HALT_REASON_CODES``
    set rather than reimplementing steps 3-6, which it could not do anyway: the
    four non-mechanical codes depend on facts no durable payload carries.
    """
    from .classification import CLASSIFICATION_REFUSED_PRE_DISPATCH

    if emission_status == EMISSION_COLLISION:
        return HALT_RUN_RECORD_EMISSION_COLLISION
    if emission_status == EMISSION_FAILED:
        return HALT_RUN_RECORD_EMISSION_FAILED
    if halt_triggered_by_this_run is True:
        return HALT_RUN_RECORD_SELF_VALIDATION_FAILED
    if lifecycle_all_closed is False:
        return HALT_LIFECYCLE_CLOSURE_UNPROVEN
    if run_classification == CLASSIFICATION_REFUSED_PRE_DISPATCH:
        return HALT_PRE_DISPATCH_REFUSAL
    if registries_empty is False:
        return HALT_RUN_SCOPED_REGISTRY_NOT_EMPTY
    return None


# ---------------------------------------------------------------------------
# Sec. 19.1 -- the in-memory L30 admission decision
# ---------------------------------------------------------------------------


class Cfg1AdmissionError(Exception):
    """The admission decision was asked a question it cannot yet answer."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"cfg1 admission refused: {reason_code}")
        self.reason_code = reason_code


#: The four values an L29 emission attempt can actually resolve to. An
#: admission decision may never read a value outside this set -- see below.
RESOLVED_EMISSION_STATUSES: frozenset[str] = frozenset(
    {
        EMISSION_RECORD_EMITTED,
        EMISSION_EVIDENCE_REFUSED,
        EMISSION_COLLISION,
        EMISSION_FAILED,
    }
)


def _admission_conditions_hold(
    *,
    emission_status: str,
    lifecycle_all_closed: bool,
    run_classification: str,
    halt_triggered_by_this_run: bool,
    registries_empty: bool,
) -> bool:
    """Sec. 19.1 items 1-4, as one decision. Item 5 is Sec. 19.6's, not this.

    **This cannot be called before L29 has resolved.** An unresolved or
    placeholder emission status RAISES rather than being silently treated as
    any of the four closed values -- which is what makes L28->L29->L30's
    ordering mechanical rather than merely documented (T-101).

    Item 2's two clauses are checked INDEPENDENTLY and are not redundant: a
    record-self-validation failure sets ``halt_triggered_by_this_run`` true
    REGARDLESS of whether its own permitted refusal fallback succeeded, so an
    ``EVIDENCE_REFUSED`` status alone cannot distinguish an ordinary,
    non-halting scrub refusal from an implementation-defect halt whose refusal
    artifact happened to be written. Only this bool does -- and that is exactly
    what makes "a successfully written refusal artifact does not convert an
    implementation defect into an admissible next run" a mechanical rule rather
    than a claim resting on prose.
    """
    from .classification import CLASSIFICATION_REFUSED_PRE_DISPATCH

    if type(emission_status) is not str or emission_status not in RESOLVED_EMISSION_STATUSES:
        raise Cfg1AdmissionError("EMISSION_OUTCOME_NOT_RESOLVED")
    if type(lifecycle_all_closed) is not bool:
        raise Cfg1AdmissionError("MALFORMED_LIFECYCLE_ALL_CLOSED")
    if type(halt_triggered_by_this_run) is not bool:
        raise Cfg1AdmissionError("MALFORMED_HALT_TRIGGERED_BY_THIS_RUN")
    if type(registries_empty) is not bool:
        raise Cfg1AdmissionError("MALFORMED_REGISTRIES_EMPTY")

    if lifecycle_all_closed is not True:  # item 1
        return False
    if run_classification == CLASSIFICATION_REFUSED_PRE_DISPATCH:  # item 2, clause 1
        return False
    if halt_triggered_by_this_run is not False:  # item 2, clause 2
        return False
    if emission_status not in ADMISSIBLE_EMISSION_STATUSES:  # item 3
        return False
    if registries_empty is not True:  # item 4
        return False
    return True
