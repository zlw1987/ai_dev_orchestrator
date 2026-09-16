"""The sealed terminal stage decision -- CFG1-owned, non-forgeable, L30-only.

Design Sec. 16.3.8.3. This module holds the TYPE and the two registries. It
deliberately holds NO sealing function: stage-decision issuance is not part of
the public, authority-parameterized API surface at all, and there is no
module-level, importable, or otherwise externally-reachable name through which
any caller -- however privileged -- can request a sealed decision carrying
facts of its own choosing.

**Why removing the sealer was the only fix.** FU9 made the stage-closure writer
refuse caller-selected closure facts, then moved the same defect one layer
upstream to ``seal_cfg1_stage_decision(authority, *, ordinal_status, ...)``.
Any importer holding a genuine ACTIVE authority could call that with an
internally self-consistent tuple describing a stage that never happened, and
get back a genuine, registry-backed object the writer would accept -- because
a mint registry proves WHO issued an object, never that the FACTS inside it
came from the real L30 state. Stronger argument validation could not close
that: the defect is that the facts arrive as arguments at all. So the sealing
sequence exists only as code lexically owned by the one stage-runner routine
that executes L0-L30, reading its inputs from that routine's own local
stage-progress ledger.

**Two independent one-shot properties, two disjoint registries.**

``_STAGE_DECISION_SEALED``
    Decision AUTHENTICITY and one-shot CONSUMABILITY. Revoked at the start of
    a decision's one permitted consumption. Answers "is this specific object
    genuine and still consumable" -- never "has this authority already sealed".

``_STAGE_TERMINAL_SEAL_HISTORY``
    A per-AUTHORITY seal-history fact, established once on the first terminal
    seal, and never removed by decision consumption, by that consumption's
    write succeeding or failing, or by authority retirement. This is what makes
    seal-once true: proving it from the decision registry alone was
    self-defeating, since consumption clears exactly the evidence the proof
    needed (FU12).
"""

from __future__ import annotations

from dataclasses import dataclass, field


class Cfg1StageDecisionError(Exception):
    """A stage decision could not be proven genuine. Bounded reason code only."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"cfg1 stage decision refused: {reason_code}")
        self.reason_code = reason_code


@dataclass(frozen=True)
class _DecisionMintRecord:
    """Every bound field, recorded at seal time and re-compared at consumption."""

    authority_mint_nonce: str = field(repr=False)
    stage_id: str
    stage_execution_id: str
    ordinal_status: tuple[tuple[int, str], ...]
    halted_after_ordinal: int | None
    halt_reason_code: str | None

    def __repr__(self) -> str:  # noqa: D105 - the authority nonce is never rendered
        return f"{type(self).__name__}(<bound>)"


#: decision_nonce -> record. Process-local, in-memory only, never persisted,
#: never CFG1 evidence. Revoked at consumption (writer step 4a).
_STAGE_DECISION_SEALED: dict[str, _DecisionMintRecord] = {}

#: authority.mint_nonce -> present. Process-local, in-memory only. Established
#: once, at the FIRST terminal seal, BEFORE the decision itself is registered,
#: so a failure between the two still leaves seal-once enforced. Removed only
#: by the stage runner's own bounded cleanup, after it has irreversibly left
#: every code path capable of reaching the sealing step.
_STAGE_TERMINAL_SEAL_HISTORY: set[str] = set()

_DECISION_NONCE_BYTES = 16


@dataclass(frozen=True)
class CFG1StageClosureDecision:
    """The one terminal stage decision -- SUCCESS or HALTED, never halt-only.

    Represents BOTH terminal outcomes (Sec. 19.6 branches C and A). A
    successful stage has ``halted_after_ordinal is None`` and
    ``halt_reason_code is None``; a halted one carries both.

    Valid by construction: ``__post_init__`` refuses any instance whose
    ``decision_nonce`` is unregistered, and any instance whose bound fields
    disagree with what was registered under it. ``frozen=True`` prevents
    mutation; the registry re-check prevents CONSTRUCTION -- and a later
    ``object.__setattr__`` bypass is caught at the next re-proof, never
    trusted from a cached prior check.

    ``ordinal_status`` is an immutable tuple of ``(ordinal, status)`` pairs
    sorted by ordinal. The durable JSON object's decimal-string keys are that
    same data in JSON's own required key form -- rendered by the writer, never
    stored twice.
    """

    decision_nonce: str = field(repr=False)
    authority_mint_nonce: str = field(repr=False)
    stage_id: str
    stage_execution_id: str
    ordinal_status: tuple[tuple[int, str], ...]
    halted_after_ordinal: int | None
    halt_reason_code: str | None

    def __post_init__(self) -> None:
        if type(self.decision_nonce) is not str or not self.decision_nonce:
            raise Cfg1StageDecisionError("UNKNOWN_DECISION_NONCE")
        record = _STAGE_DECISION_SEALED.get(self.decision_nonce)
        if record is None:
            raise Cfg1StageDecisionError("UNKNOWN_DECISION_NONCE")
        if _bound_fields(self) != _bound_fields(record):
            raise Cfg1StageDecisionError("DECISION_FIELD_MISMATCH")

    def __repr__(self) -> str:  # noqa: D105 - nonces are never rendered
        return (
            f"{type(self).__name__}(stage_id={self.stage_id!r}, "
            f"stage_execution_id={self.stage_execution_id!r}, "
            f"halted_after_ordinal={self.halted_after_ordinal!r}, "
            f"halt_reason_code={self.halt_reason_code!r})"
        )


def _bound_fields(value) -> tuple:
    """The exact tuple both the object and its registry record must agree on."""
    return (
        value.authority_mint_nonce,
        value.stage_id,
        value.stage_execution_id,
        value.ordinal_status,
        value.halted_after_ordinal,
        value.halt_reason_code,
    )


def _verify_sealed_decision(decision: CFG1StageClosureDecision, authority) -> None:
    """Writer steps 3 and 4 -- re-proven FRESH, every call.

    Step 3 re-looks-up the authenticity record and re-compares every bound
    field, so a genuine object mutated through a ``frozen=True`` bypass is
    caught here rather than trusted from its construction-time check.

    Step 4 is the authority-rebinding gate: a genuine decision sealed under one
    stage execution can never be presented alongside a different authority,
    even one that is itself genuine and ACTIVE.
    """
    record = _STAGE_DECISION_SEALED.get(decision.decision_nonce)
    if record is None:
        raise Cfg1StageDecisionError("UNKNOWN_DECISION_NONCE")
    if _bound_fields(decision) != _bound_fields(record):
        raise Cfg1StageDecisionError("DECISION_FIELD_MISMATCH")
    if decision.authority_mint_nonce != authority.mint_nonce:
        raise Cfg1StageDecisionError("DECISION_AUTHORITY_MISMATCH")


def _revoke_decision_consumability(decision: CFG1StageClosureDecision) -> None:
    """Writer step 4a -- remove the CONSUMABILITY entry, and only that.

    Never merely marked, never revertible: a second consumption of the same
    genuine object fails with the identical ``UNKNOWN_DECISION_NONCE`` a
    never-sealed decision produces, so it does not merely become useless -- it
    becomes mechanically indistinguishable from one that was never sealed.

    This touches ``_STAGE_DECISION_SEALED`` ONLY. It has no authority over
    ``_STAGE_TERMINAL_SEAL_HISTORY``, whose entry was established once at seal
    time and answers an entirely different question.
    """
    _STAGE_DECISION_SEALED.pop(decision.decision_nonce, None)


def _terminal_seal_recorded(authority_mint_nonce: str) -> bool:
    """Has this authority already reached the terminal sealing step? (step 2)"""
    return authority_mint_nonce in _STAGE_TERMINAL_SEAL_HISTORY


def _discard_stage_decision_state(authority) -> None:
    """Bounded in-memory cleanup, run ONLY as the stage runner returns.

    Removes this authority's seal-history fact and any ORPHANED decision
    registry entry (one registered at step 4 whose ``__post_init__`` then
    failed, so no object was ever returned to any caller and no code path can
    reconstruct the exact freshly-generated nonce it would need).

    **Takes the ownership HANDLE, never a bare nonce string.** Cleanup that
    accepted an identifier would clear a seal-history fact for anything whose
    name happened to look right -- and that fact is the one backstop refusing a
    second terminal seal. A wrong type is a silent no-op rather than a raise,
    because this runs on the stage runner's own exit path where raising would
    mask whatever it is unwinding from.

    Deliberately called from that exit path and nowhere else: while a
    sealing-capable frame still exists, the seal-history fact must survive.
    """
    from .stage_output import CFG1StageOutputAuthority

    if type(authority) is not CFG1StageOutputAuthority:
        return
    _STAGE_TERMINAL_SEAL_HISTORY.discard(authority.mint_nonce)
    for nonce, record in list(_STAGE_DECISION_SEALED.items()):
        if record.authority_mint_nonce == authority.mint_nonce:
            _STAGE_DECISION_SEALED.pop(nonce, None)
