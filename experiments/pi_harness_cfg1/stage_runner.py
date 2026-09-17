"""The one L0-L30 orchestration routine, and the only code that can ever seal.

Design Sec. 16.2 (the lifecycle), Sec. 16.3.8.3 (the terminal decision),
Sec. 16.3.8.4 (the stage-progress ledger), Sec. 16.3.10 (L0 output-namespace
preoccupation), Sec. 19.1/19.5/19.6 (admission, halt precedence, and the exact
three-way terminal transition).

**Sealing has no reachable name.** ``_record_ordinal_result`` and
``_seal_terminal_decision`` are nested inside
:func:`_run_cfg1_stage_with_injected_executor` (the offline dependency-
injection seam; :func:`run_cfg1_stage` is the sole authoritative entry point
and delegates to it with the genuine executor). They are
never assigned to a module attribute, never exported, never importable, and
never discoverable by introspecting any object a caller can obtain by holding
only a ``CFG1StageOutputAuthority`` -- the authority carries no reference to
them and gains no field here. That is a STRONGER property than "there happens
to be one call site": a single call site is a fact about how correct code
behaves, whereas no reachable name is a fact about what code holding only an
authority is CAPABLE of, regardless of intent. A single leading underscore on
an otherwise importable module function would not have provided it.

**The ledger has no callable boundary to defend at all.** A mint registry
defends a callable boundary -- an object can be presented to a function, and
the registry proves whether it is genuine. The stage-progress ledger is a plain
local variable of this routine's own call frame: nothing outside it ever holds
a reference to the ledger, or to any function that reads or writes it, so there
is no boundary for an invented ``(ordinal, status)`` pair to arrive through.

**L30 runs once per ADMITTED ORDINAL, not once per stage.** A normal ``S1``
stage reaches it up to nine times. Sealing happens only at an evaluation that
selects branch A or branch C; branch B -- the ordinary non-final-ordinal case
-- issues a token and touches neither decision registry.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

from .halt import (
    DISPOSITION_OUTPUT_NAMESPACE_PREOCCUPIED,
    DISPOSITION_STAGE_CLOSURE_EMISSION_FAILED,
    DISPOSITION_STAGE_COMPLETED,
    DISPOSITION_STAGE_DECISION_MINT_FAILED,
    DISPOSITION_STAGE_HALTED,
    DISPOSITION_STAGE_OUTPUT_AUTHORITY_HARD_STOP,
    HALT_REASON_CODES,
    ORDINAL_NOT_EXECUTED,
    _admission_conditions_hold,
    _resolve_halt_reason_code,
)
from .records import build_cfg1_run_payload
from .run_contract import Cfg1RunAdmission, Cfg1RunOutcome
from .schedule import (
    LAST_ORDINAL,
    _schedule_arm_for,
    _schedule_block_position,
    declared_ordinals,
)
from .stage_decision import (
    CFG1StageClosureDecision,
    Cfg1StageDecisionError,
    _DecisionMintRecord,
    _STAGE_DECISION_SEALED,
    _STAGE_TERMINAL_SEAL_HISTORY,
    _discard_stage_decision_state,
    _terminal_seal_recorded,
)
from .stage_output import (
    CFG1StageOutputAuthority,
    StageOutputAuthorityError,
    _retire_stage_output_authority,
    verify_stage_output_authority,
)
from .writers import (
    _run_output_path,
    emit_cfg1_run_record,
    emit_cfg1_stage_closure,
)


class Cfg1StageRunnerError(Exception):
    """The stage could not be run at all. Bounded reason code only."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"cfg1 stage runner refused: {reason_code}")
        self.reason_code = reason_code


@dataclass(frozen=True)
class Cfg1StageResult:
    """What one stage execution ended as. Console-facing, never durable evidence.

    ``disposition`` is one closed literal. Four of the six mean no confirmed
    stage-closure record exists (``halt.NO_CONFIRMED_STAGE_CLOSURE_CASES``);
    the other two -- completed and halted -- each write exactly one.
    """

    stage_id: str
    stage_execution_id: str
    disposition: str
    ordinals_attempted: tuple[int, ...]
    ordinal_status: tuple[tuple[int, str], ...]
    halted_after_ordinal: int | None
    halt_reason_code: str | None
    stage_closure_confirmed: bool
    console_codes: tuple[str, ...] = field(default_factory=tuple)


_RUN_ID_BYTES = 16

#: Independently captured, from THIS module's own file location -- never from
#: :mod:`stage_output`'s module attribute, which offline tests deliberately
#: rebind (Sec. 16.3.4's accepted test-harness seam). Both modules ship in the
#: same package directory, so in a genuine, untouched installation the two
#: values are always equal; only a test's own rebinding of
#: ``stage_output._CAPTURED_PACKAGE_DIR`` ever makes them differ. This is the
#: ground truth the offline-injection branch below checks itself against, so
#: a CALLER-SUPPLIED (non-genuine) executor cannot be used at all against the
#: genuine, installed package root (CFG1-IMPL-FU1 Finding 1).
_GENUINE_PACKAGE_DIRECTORY = str(Path(__file__).resolve().parent)


def run_cfg1_stage(authority: CFG1StageOutputAuthority, /) -> Cfg1StageResult:
    """THE sole authoritative, evidence-producing CFG1 stage entry point.

    ``authority`` is positional-only, and there is no other parameter of any
    kind. In particular there is no ``run_executor``, no ``ports``, and no
    ``_internal_probe`` -- a caller holding only a genuine, ACTIVE
    ``CFG1StageOutputAuthority`` has no supported way, through this function,
    to substitute a run executor, a hand-built ``Cfg1RunOutcome``, or a
    live-port set, and therefore no way to make this routine emit a genuine
    ``pi-harness-cfg1-run.v1`` or stage-closure artifact from anything but the
    genuine L1-L28 executor (CFG1-IMPL-FU1 Finding 1). The genuine executor is
    bound HERE, mechanically, via :func:`run_executor.
    bind_genuine_cfg1_run_executor` -- never accepted as an argument.
    """
    from .run_executor import bind_genuine_cfg1_run_executor

    genuine_executor = bind_genuine_cfg1_run_executor()
    return _run_cfg1_stage_with_injected_executor(
        authority, run_executor=genuine_executor, _internal_probe=None
    )


def _run_cfg1_stage_with_injected_executor(
    authority: CFG1StageOutputAuthority,
    /,
    *,
    run_executor,
    _internal_probe=None,
) -> Cfg1StageResult:
    """L0-L30 orchestration. Reached by ``run_cfg1_stage`` (genuine) and by the
    offline suite's own dependency-injection seam (synthetic) alike -- but the
    two are NOT equally privileged.

    ``run_executor`` is either:

    * a genuine :class:`run_executor.Cfg1GenuineRunExecutor` -- unforgeable by
      API (its own mint-registry re-check, Sec. 16.3.3's shape, applies), so
      reaching this branch proves the executor came from
      :func:`run_executor.bind_genuine_cfg1_run_executor` and nowhere else.
      This branch is unconditional: it is exactly what genuine production
      evidence requires, and the genuine, installed package root is where it
      is SUPPOSED to write; or
    * anything else -- a bare callable, a lambda, a test double. This is the
      OFFLINE dependency-injection seam, and it is refused outright unless
      :mod:`stage_output`'s ``RESULTS_ROOT`` capture has been retargeted away
      from the genuine, installed package directory. A production process's
      capture is never retargeted, so a CALLER-SUPPLIED executor mechanically
      cannot write into the genuine results namespace there, regardless of
      what ``authority`` it is given (CFG1-IMPL-FU1 Finding 1). Holding only a
      genuine authority does not let a caller construct a genuine
      ``Cfg1GenuineRunExecutor`` of its own: its ``__post_init__`` refuses any
      instance whose token this process did not itself mint.

    ``authority`` is positional-only and everything else keyword-only, so this
    routine cannot be reached with an additional positional argument. It
    declares no ``ordinal_status``, ``halted_after_ordinal`` or
    ``halt_reason_code`` parameter -- there is nowhere for an invented stage
    outcome to enter -- and it returns a :class:`Cfg1StageResult`, never a
    ``CFG1StageClosureDecision``.

    ``run_executor`` implements L1-L28 for one admitted ordinal (see
    :mod:`run_contract`). It is required: there is no default, so this routine
    is not callable while holding only an authority.

    ``_internal_probe`` is TEST-ONLY adversarial scaffolding, never a supported
    code path and never a production capability. It is invoked at fixed
    internal points with a bounded namespace; it can inject a mint-sequence
    failure by raising, and can force a malformed second reach of the sealing
    step -- which is always refused, and can never return a decision object.
    """
    from .run_executor import Cfg1GenuineRunExecutor

    if type(run_executor) is Cfg1GenuineRunExecutor:
        # CFG1-IMPL-FU2 Finding 1's test-hook boundary: a non-None probe is
        # TEST-ONLY adversarial scaffolding for the OFFLINE injection seam
        # (the `else` branch below), never a production capability of the
        # genuine branch. Nothing previously refused the combination of a
        # genuine executor with a caller-supplied probe -- both
        # `bind_genuine_cfg1_run_executor` and this routine are importable, so
        # a caller could otherwise reach the genuine branch (which the offline
        # `_CAPTURED_PACKAGE_DIR` guard below never gates) while also firing a
        # probe capable of raising mid-seal or forcing a second seal-history
        # contest against the GENUINE results namespace. Refused mechanically,
        # by type, never merely by convention or the leading underscore.
        if _internal_probe is not None:
            raise Cfg1StageRunnerError(
                "TEST_PROBE_AGAINST_GENUINE_EXECUTOR_REFUSED"
            )
        _invoke_executor = run_executor.invoke
    else:
        from . import stage_output as _stage_output_module

        if _stage_output_module._CAPTURED_PACKAGE_DIR == _GENUINE_PACKAGE_DIRECTORY:
            raise Cfg1StageRunnerError(
                "OFFLINE_EXECUTOR_INJECTION_REFUSED_IN_GENUINE_PACKAGE_ROOT"
            )
        _invoke_executor = run_executor
    # An EXACT type gate only. The provenance re-proof belongs to L0, inside
    # the guarded body, because a failing re-proof is a Sec. 16.3.7 hard stop
    # -- which must retire the authority and report one closed console code,
    # not propagate an exception past the routine that owns retirement.
    if type(authority) is not CFG1StageOutputAuthority:
        raise Cfg1StageRunnerError("NOT_A_STAGE_OUTPUT_AUTHORITY")

    stage_id = authority.stage_id
    ordinals = declared_ordinals(stage_id)
    last_ordinal = LAST_ORDINAL(stage_id)

    # --- Sec. 16.3.8.4: the runner-local stage-progress ledger -------------
    # A plain local variable of THIS call frame. Never a module global, never
    # returned, never passed to any function outside this routine's own body,
    # and never persisted -- only the VALUES read from it at the moment of
    # sealing become part of the immutable, registered decision.
    _ordinal_ledger: dict[int, str] = {}

    console_codes: list[str] = []
    current_ordinal: int | None = None

    def _fire(event: str, **context) -> None:
        """Invoke the test-only probe, if one was supplied. No-op otherwise."""
        if _internal_probe is None:
            return
        _internal_probe(
            SimpleNamespace(
                event=event,
                stage_id=stage_id,
                force_second_seal_reach=_force_second_seal_reach,
                **context,
            )
        )

    def _record_ordinal_result(run_ordinal: int, ordinal_status: str) -> None:
        """Append one ordinal's REAL L29 result. A local assignment, nothing more.

        Not a call to any separately-nameable function, and therefore not a
        capability a supported caller holding only ``authority`` could invoke
        with an invented ``(run_ordinal, ordinal_status)`` pair of its own.
        """
        _ordinal_ledger[run_ordinal] = ordinal_status

    def _seal_terminal_decision(
        *, halted_after_ordinal: int | None, halt_reason_code: str | None
    ) -> CFG1StageClosureDecision:
        """Requirement 6's five-step mint sequence, in the frozen order.

        Reads ``stage_id``/``stage_execution_id`` from the closed-over
        ``authority`` and ``ordinal_status`` from the closed-over ledger --
        never from a parameter. The only two values that DO arrive as
        arguments are the ones L30 itself just computed: the halted ordinal and
        the output of Sec. 19.5's one shared precedence function.
        """
        # Step 1 -- authority/state conditions already frozen elsewhere.
        verify_stage_output_authority(authority)
        if current_ordinal is None or current_ordinal not in _ordinal_ledger:
            raise Cfg1StageDecisionError("LEDGER_MISSING_CURRENT_ORDINAL")

        # Step 2 -- the per-authority seal-history check. This is the ONLY
        # seal-once proof: the decision registry cannot serve as one, because
        # writer step 4a clears exactly the entry such a proof would need.
        if _terminal_seal_recorded(authority.mint_nonce):
            raise Cfg1StageDecisionError("SECOND_TERMINAL_SEAL_REFUSED")

        _fire("mint:before_history")

        # Step 3 -- establish the history fact BEFORE step 4, so a failure in
        # step 4 or step 5 still leaves seal-once enforced. A stage that
        # strands itself this way never completes a terminal seal again: a
        # fail-closed state, deliberately never reopened.
        _STAGE_TERMINAL_SEAL_HISTORY.add(authority.mint_nonce)

        _fire("mint:after_history")

        ordinal_status = tuple(
            (ordinal, _ordinal_ledger.get(ordinal, ORDINAL_NOT_EXECUTED))
            for ordinal in ordinals
        )
        decision_nonce = secrets.token_hex(16)

        # Step 4 -- register authenticity.
        _STAGE_DECISION_SEALED[decision_nonce] = _DecisionMintRecord(
            authority_mint_nonce=authority.mint_nonce,
            stage_id=stage_id,
            stage_execution_id=authority.stage_execution_id,
            ordinal_status=ordinal_status,
            halted_after_ordinal=halted_after_ordinal,
            halt_reason_code=halt_reason_code,
        )

        _fire("mint:after_registration")

        # Step 5 -- construct. ``__post_init__``'s registry re-check is what
        # makes this step's success depend on step 4 having already succeeded.
        return CFG1StageClosureDecision(
            decision_nonce=decision_nonce,
            authority_mint_nonce=authority.mint_nonce,
            stage_id=stage_id,
            stage_execution_id=authority.stage_execution_id,
            ordinal_status=ordinal_status,
            halted_after_ordinal=halted_after_ordinal,
            halt_reason_code=halt_reason_code,
        )

    def _force_second_seal_reach() -> dict:
        """TEST-ONLY. Force one malformed second reach of the REAL sealing step.

        Not an operational retry path, and it grants no production capability:
        the stage runner's own code never reaches the sealing step twice for one
        authority, under any control flow. This exists solely to prove
        mechanically that a second seal is foreclosed -- and specifically that
        the INDEPENDENT seal-history fact, not decision consumability, is what
        forecloses it, including after a first decision has already been
        consumed and its own registry entry revoked.

        Returns a bounded report and **never a decision object**, under any
        outcome. ``refused_by`` is reported truthfully rather than assumed:
        after a mint-failure unwind the authority has already been retired
        (Sec. 16.3.9's frozen ordering), so step 1 refuses before step 2 can --
        a STRONGER refusal, not a weaker one, and the separately reported
        ``seal_history_present`` is what shows step 2's own fact is still set
        and would refuse independently.

        **It can only ever contest an EXISTING seal, never manufacture a first
        one.** Reached before any terminal seal -- at a branch-B L30
        evaluation, say -- the real sealing step would find no history fact and
        would legitimately proceed, poisoning the stage's one seal. So the
        no-prior-seal case returns without calling the sealing step at all.
        """
        if not _terminal_seal_recorded(authority.mint_nonce):
            return {
                "refused_by": "no_prior_seal_to_contest",
                "second_decision_registered": False,
                "seal_history_present": False,
            }
        before = len(_STAGE_DECISION_SEALED)
        refused_by = "not_refused"
        try:
            _seal_terminal_decision(halted_after_ordinal=None, halt_reason_code=None)
        except StageOutputAuthorityError:
            refused_by = "authority_reproof"
        except Cfg1StageDecisionError as exc:
            refused_by = (
                "seal_history"
                if exc.reason_code == "SECOND_TERMINAL_SEAL_REFUSED"
                else exc.reason_code
            )
        except Exception:  # noqa: BLE001 - bounded; no exception text escapes
            refused_by = "other"
        return {
            "refused_by": refused_by,
            "second_decision_registered": len(_STAGE_DECISION_SEALED) != before,
            "seal_history_present": _terminal_seal_recorded(authority.mint_nonce),
        }

    def _retire_and_report(disposition: str, code: str) -> Cfg1StageResult:
        """A hard stop: retire IMMEDIATELY, then report, then end the stage.

        Retirement precedes console reporting so that however execution
        proceeds afterwards, no code path can use that mint again. Nothing is
        written to ``results/`` -- not a run record, not a refusal record, not
        a stage-closure record -- and any pre-existing occupant is left
        completely untouched.
        """
        _retire_stage_output_authority(authority)
        console_codes.append(code)
        return Cfg1StageResult(
            stage_id=stage_id,
            stage_execution_id=authority.stage_execution_id,
            disposition=disposition,
            ordinals_attempted=tuple(sorted(_ordinal_ledger)),
            ordinal_status=tuple(
                (ordinal, _ordinal_ledger.get(ordinal, ORDINAL_NOT_EXECUTED))
                for ordinal in ordinals
            ),
            halted_after_ordinal=None,
            halt_reason_code=None,
            stage_closure_confirmed=False,
            console_codes=tuple(console_codes),
        )

    def _terminate(
        *, halted_after_ordinal: int | None, halt_reason_code: str | None
    ) -> Cfg1StageResult:
        """Branches A and C: seal, emit the closure, then retire."""
        try:
            decision = _seal_terminal_decision(
                halted_after_ordinal=halted_after_ordinal,
                halt_reason_code=halt_reason_code,
            )
        except StageOutputAuthorityError as exc:
            # The sealing step's own step-1 authority re-proof failing is a
            # PROVENANCE failure, which Sec. 16.3.7 already owns -- not a mint
            # failure. Both retire immediately and write nothing; only the
            # closed console code differs, and it should name what actually
            # failed.
            return _retire_and_report(
                DISPOSITION_STAGE_OUTPUT_AUTHORITY_HARD_STOP, exc.reason_code
            )
        except Exception:  # noqa: BLE001 - reduced HERE, Sec. 21.1; never re-raised
            # Sec. 16.3.8.3's terminal-decision mint failure disposition. No
            # second mint attempt, no admission token, no stage-closure writer
            # call, no artifact, no reclassification of any prior record, and
            # no raw exception text anywhere. The authority is retired BEFORE
            # the console report and before this routine returns.
            _retire_stage_output_authority(authority)
            console_codes.append(DISPOSITION_STAGE_DECISION_MINT_FAILED)
            _fire("mint_failed")
            return Cfg1StageResult(
                stage_id=stage_id,
                stage_execution_id=authority.stage_execution_id,
                disposition=DISPOSITION_STAGE_DECISION_MINT_FAILED,
                ordinals_attempted=tuple(sorted(_ordinal_ledger)),
                ordinal_status=tuple(
                    (ordinal, _ordinal_ledger.get(ordinal, ORDINAL_NOT_EXECUTED))
                    for ordinal in ordinals
                ),
                halted_after_ordinal=None,
                halt_reason_code=None,
                stage_closure_confirmed=False,
                console_codes=tuple(console_codes),
            )

        _fire("seal:after")

        try:
            closure = emit_cfg1_stage_closure(authority, decision=decision)
        except StageOutputAuthorityError as exc:
            return _retire_and_report(
                DISPOSITION_STAGE_OUTPUT_AUTHORITY_HARD_STOP, exc.reason_code
            )
        _fire("closure:after_write")
        _retire_stage_output_authority(authority)
        if closure.console_code is not None:
            console_codes.append(closure.console_code)
        _fire("closure:after_emit")

        if not closure.confirmed:
            disposition = DISPOSITION_STAGE_CLOSURE_EMISSION_FAILED
        elif halted_after_ordinal is None:
            disposition = DISPOSITION_STAGE_COMPLETED
        else:
            disposition = DISPOSITION_STAGE_HALTED

        return Cfg1StageResult(
            stage_id=stage_id,
            stage_execution_id=authority.stage_execution_id,
            disposition=disposition,
            ordinals_attempted=tuple(sorted(_ordinal_ledger)),
            ordinal_status=decision.ordinal_status,
            halted_after_ordinal=decision.halted_after_ordinal,
            halt_reason_code=decision.halt_reason_code,
            stage_closure_confirmed=closure.confirmed,
            console_codes=tuple(console_codes),
        )

    def _body() -> Cfg1StageResult:
        nonlocal current_ordinal
        admission_token: int | None = None

        for run_ordinal in ordinals:
            # ================= L0 ADMISSION =================
            if run_ordinal != ordinals[0]:
                if admission_token != run_ordinal:  # pragma: no cover - loop exits on halt
                    break
                admission_token = None  # single-use, names ordinal k+1 only

            try:
                verify_stage_output_authority(authority)
            except StageOutputAuthorityError as exc:
                return _retire_and_report(
                    DISPOSITION_STAGE_OUTPUT_AUTHORITY_HARD_STOP, exc.reason_code
                )

            arm_id = _schedule_arm_for(stage_id, run_ordinal)
            block, position = _schedule_block_position(stage_id, run_ordinal)

            # The path is derived by the SAME internal derivation the writer
            # will later use -- never a separately-reimplemented lookup -- and
            # is required ABSENT before this ordinal is admitted. An occupied
            # path here is Sec. 16.3.10's third hard-stop class: no run has
            # been admitted at all, so there is no ordinal for
            # `halted_after_ordinal` to name and no record to carry a code.
            expected_path = _run_output_path(authority, run_ordinal)
            if os.path.lexists(expected_path):
                return _retire_and_report(
                    DISPOSITION_OUTPUT_NAMESPACE_PREOCCUPIED,
                    DISPOSITION_OUTPUT_NAMESPACE_PREOCCUPIED,
                )

            admission = Cfg1RunAdmission(
                stage_id=stage_id,
                stage_execution_id=authority.stage_execution_id,
                run_ordinal=run_ordinal,
                arm_id=arm_id,
                block=block,
                position=position,
                run_id=secrets.token_hex(_RUN_ID_BYTES),
            )

            # ================= L1 - L28 =================
            try:
                outcome = _invoke_executor(admission)
            except Exception:  # noqa: BLE001 - reduced here; no raw text escapes
                _retire_stage_output_authority(authority)
                raise Cfg1StageRunnerError("RUN_EXECUTOR_RAISED") from None
            if type(outcome) is not Cfg1RunOutcome:
                _retire_stage_output_authority(authority)
                raise Cfg1StageRunnerError("RUN_EXECUTOR_RETURNED_FOREIGN_OUTCOME")
            console_codes.extend(outcome.console_codes)

            # ================= L29 RUN-RECORD EMISSION =================
            payload = build_cfg1_run_payload(
                stage_id=stage_id,
                stage_execution_id=authority.stage_execution_id,
                run_ordinal=run_ordinal,
                observations=outcome.observations,
            )
            # Read the already-finalized L28 bool EXACTLY, never coerced.
            # ``bool(payload[...])`` would turn a malformed ``1`` into a
            # plausible ``True`` -- precisely the Python-truthiness fail-open
            # this design refuses everywhere else. A non-bool becomes ``False``,
            # the fail-closed direction; the payload validator then refuses the
            # record on its own at step 6.
            lifecycle_all_closed = payload["lifecycle_all_closed"]
            if type(lifecycle_all_closed) is not bool:
                lifecycle_all_closed = False

            try:
                emission = emit_cfg1_run_record(
                    authority,
                    run_ordinal=run_ordinal,
                    payload=payload,
                    lifecycle_all_closed=lifecycle_all_closed,
                    safety=outcome.safety,
                )
            except StageOutputAuthorityError as exc:
                return _retire_and_report(
                    DISPOSITION_STAGE_OUTPUT_AUTHORITY_HARD_STOP, exc.reason_code
                )
            if emission.console_code is not None:
                console_codes.append(emission.console_code)

            _record_ordinal_result(run_ordinal, emission.emission_status)
            current_ordinal = run_ordinal

            # ================= L30 TERMINAL STAGE DECISION =================
            _fire("l30:enter", run_ordinal=run_ordinal)

            registries_empty = _run_scoped_registries_empty(outcome)
            halt_triggered_by_this_run = emission.self_validation_defect
            admissible = _admission_conditions_hold(
                emission_status=emission.emission_status,
                lifecycle_all_closed=lifecycle_all_closed,
                run_classification=payload["run_classification"],
                halt_triggered_by_this_run=halt_triggered_by_this_run,
                registries_empty=registries_empty,
            )

            if not admissible:
                # Branch A -- halt.
                halt_reason_code = _resolve_halt_reason_code(
                    emission_status=emission.emission_status,
                    halt_triggered_by_this_run=halt_triggered_by_this_run,
                    lifecycle_all_closed=lifecycle_all_closed,
                    run_classification=payload["run_classification"],
                    registries_empty=registries_empty,
                )
                # The SAME closed set object the stage-closure validator cites
                # -- checked here rather than asserted, so ``-O`` cannot strip
                # the one place L30 proves it never invents a seventh code.
                if halt_reason_code not in HALT_REASON_CODES:  # pragma: no cover
                    raise Cfg1StageRunnerError("HALT_REASON_CODE_OUTSIDE_CLOSED_SET")
                return _terminate(
                    halted_after_ordinal=run_ordinal, halt_reason_code=halt_reason_code
                )

            if run_ordinal != last_ordinal:
                # Branch B -- issue the single-use token and continue. No
                # decision is sealed and no stage closure is emitted.
                admission_token = run_ordinal + 1
                continue

            # Branch C -- the stage's own final declared ordinal succeeded.
            # No admission token is issued: there is no ordinal
            # LAST_ORDINAL + 1 for one to name, and inventing one would
            # misrepresent the frozen schedule. This is ordinary successful
            # completion, not a halt and not a hard stop.
            return _terminate(halted_after_ordinal=None, halt_reason_code=None)

        raise Cfg1StageRunnerError("SCHEDULE_EXHAUSTED_WITHOUT_TERMINAL_BRANCH")

    try:
        return _body()
    finally:
        # Sec. 16.3.8.3's "terminal-seal history lifetime": the fact survives
        # sealing, the entire (single) stage-closure attempt, that attempt's
        # success or failure, and authority retirement -- and is discarded only
        # once this invocation has irreversibly left every code path capable of
        # reaching the sealing step. Any orphaned decision entry goes with it.
        try:
            _fire("stage:before_return")
        except Exception:  # noqa: BLE001 - a probe defect never changes cleanup
            pass
        _discard_stage_decision_state(authority)


def _run_scoped_registries_empty(outcome: Cfg1RunOutcome) -> bool:
    """Sec. 19.1 item 4, checked against the registries themselves.

    Not a value the executor asserts about the process: the two module-level
    registries are read directly here, and the executor contributes only its
    own live-reference release fact.
    """
    from . import config_issuance, run_workspace

    return (
        run_workspace.minted_workspace_count() == 0
        and config_issuance.issued_token_count() == 0
        and outcome.live_references_released is True
    )
