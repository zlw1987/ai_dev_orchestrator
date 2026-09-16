"""T-135 - T-141: the terminal-decision mint failure's frozen disposition.

Three failure points exist between requirement 6's steps 2 and 5, and all three
receive the SAME, uniform disposition: ``STAGE_DECISION_MINT_FAILED``, console
only, no second mint attempt ever, no admission token, no stage-closure writer
call, no artifact, no reclassification of any prior record, the stage-output
authority retired before the console report, and no raw exception text
anywhere.

**Operational retry versus test injection, stated exactly (FU14).** In all
three sub-cases the STAGE RUNNER ITSELF performs zero second mint/seal
attempts -- that is the operational claim, and it is proven by counting the
runner's own reaches of the sealing step. Separately, in sub-cases (a) and (b)
only, the HARNESS forces exactly one malformed second reach while the runner
invocation is still alive. That forced reach is an adversarial injection, not
a retry path, and it grants no production capability. Sub-case (c) performs no
such forced reach at all: a history entry that was never created cannot be the
target of a second-seal-refusal proof.

Pure Python, ``tmp_path``-scoped, no live Pi/network/model/credential activity.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cfg1_builders import synthetic_run_executor

from pi_harness_cfg1 import stage_runner
from pi_harness_cfg1.stage_decision import (
    _STAGE_DECISION_SEALED,
    _STAGE_TERMINAL_SEAL_HISTORY,
)
from pi_harness_cfg1.stage_output import (
    StageOutputAuthorityError,
    verify_stage_output_authority,
)


class _DistinctiveMintFailure(RuntimeError):
    """A type this design's own code never raises, carrying a unique message."""


#: Deliberately identifying, so T-140 can prove it reaches NO sink at all.
_DISTINCTIVE_MESSAGE = "CFG1-MINT-FAILURE-NEEDLE-8f2c41ab"

#: The three failure points, and the probe event that sits at each one.
_FAILURE_POINTS = {
    # (c) strictly between steps 2 and 3 -- BEFORE the history fact exists.
    "before_history": "mint:before_history",
    # (a) strictly between steps 3 and 4 -- history set, decision unregistered.
    "after_history": "mint:after_history",
    # (b) strictly between steps 4 and 5 -- registered, never constructed.
    "after_registration": "mint:after_registration",
}


class _MintFailureHarness:
    """Drives one stage to a mint failure and records everything observable."""

    def __init__(self, authority, failure_point: str, *, force_second_reach: bool):
        self.authority = authority
        self.event = _FAILURE_POINTS[failure_point]
        self.force_second_reach = force_second_reach
        self.sealing_step_reaches = 0
        self.during_unwind: dict | None = None
        self.history_during_unwind: bool | None = None
        self.decision_entries_during_unwind: int | None = None
        self.history_at_return: bool | None = None
        self.forced_reach_report: dict | None = None

    def probe(self, context):
        if context.event == "mint:before_history":
            self.sealing_step_reaches += 1
        if context.event == self.event:
            raise _DistinctiveMintFailure(_DISTINCTIVE_MESSAGE)
        if context.event == "mint_failed":
            self.history_during_unwind = (
                self.authority.mint_nonce in _STAGE_TERMINAL_SEAL_HISTORY
            )
            self.decision_entries_during_unwind = len(_STAGE_DECISION_SEALED)
            if self.force_second_reach:
                self.forced_reach_report = context.force_second_seal_reach()
        if context.event == "stage:before_return":
            self.history_at_return = (
                self.authority.mint_nonce in _STAGE_TERMINAL_SEAL_HISTORY
            )


def _drive(authority, failure_point, *, force_second_reach, closure_spy):
    harness = _MintFailureHarness(
        authority, failure_point, force_second_reach=force_second_reach
    )
    result = stage_runner._run_cfg1_stage_with_injected_executor(
        authority,
        run_executor=synthetic_run_executor(),
        _internal_probe=harness.probe,
    )
    assert closure_spy == []  # zero stage-closure writer calls, in every case
    return result, harness


@pytest.fixture()
def closure_spy(monkeypatch):
    """Counts every call to the stage-closure writer, from anywhere."""
    calls: list = []
    monkeypatch.setattr(
        stage_runner,
        "emit_cfg1_stage_closure",
        lambda authority, /, *, decision: calls.append(decision),
    )
    return calls


def _assert_common_mint_failure_shape(authority, result):
    """Every property the frozen disposition requires, in all three sub-cases."""
    # 7/8: exactly one bounded console report, and the stage ends.
    assert result.disposition == "STAGE_DECISION_MINT_FAILED"
    assert result.console_codes == ("STAGE_DECISION_MINT_FAILED",)
    # 2: no admission token is issued -- no ordinal beyond the last attempted.
    assert result.halted_after_ordinal is None
    assert result.halt_reason_code is None
    # 4: no stage-closure artifact of any kind was written.
    assert not Path(authority.execution_directory, "S1_stage_closure.json").exists()
    assert result.stage_closure_confirmed is False
    # 6: the authority is retired.
    with pytest.raises(StageOutputAuthorityError) as excinfo:
        verify_stage_output_authority(authority)
    assert excinfo.value.reason_code == "UNKNOWN_MINT_NONCE"
    # 5: every already-confirmed run record remains untouched.
    from pi_harness_cfg1.binding import verify_cfg1_run_artifact_binding

    for ordinal, arm in enumerate(["Q", "R", "E", "R", "E", "Q", "E", "Q", "R"], start=1):
        path = Path(authority.execution_directory, f"S1_{ordinal:02d}_{arm}.json")
        assert verify_cfg1_run_artifact_binding(str(path)) is True


# ---------------------------------------------------------------------------
# T-137 -- failure BEFORE seal-history establishment (T-135 sub-case (c))
# ---------------------------------------------------------------------------


def test_t137_and_t135c_a_failure_before_history_strands_nothing_and_retries_nothing(
    make_authority, closure_spy
):
    authority = make_authority("S1-X1")
    result, harness = _drive(
        authority, "before_history", force_second_reach=False, closure_spy=closure_spy
    )

    _assert_common_mint_failure_shape(authority, result)
    # (1) BOTH registries are left with zero entries for that authority. The
    # absence of stranded state is a fact this design PROVES -- never a licence
    # it grants to attempt the mint sequence again.
    assert harness.history_during_unwind is False
    assert harness.decision_entries_during_unwind == 0
    assert authority.mint_nonce not in _STAGE_TERMINAL_SEAL_HISTORY
    assert _STAGE_DECISION_SEALED == {}
    # (4) The runner reached the sealing step exactly ONCE.
    assert harness.sealing_step_reaches == 1
    # And the harness itself forced no synthetic second attempt of any kind:
    # a history entry that was never created cannot be the target of a
    # second-seal-refusal proof.
    assert harness.forced_reach_report is None


# ---------------------------------------------------------------------------
# T-138 -- failure AFTER history, BEFORE registration (T-135 sub-case (a))
# ---------------------------------------------------------------------------


def test_t138_and_t135a_history_is_retained_for_exactly_the_frozen_lifetime(
    make_authority, closure_spy
):
    authority = make_authority("S1-X1")
    result, harness = _drive(
        authority, "after_history", force_second_reach=True, closure_spy=closure_spy
    )

    _assert_common_mint_failure_shape(authority, result)
    assert harness.sealing_step_reaches == 1  # zero runner-owned retries

    # (1)/(2) present through immediate retirement AND through the bounded
    # console report...
    assert harness.history_during_unwind is True
    # ...and no decision was ever registered in this sub-case.
    assert harness.decision_entries_during_unwind == 0
    # (3) present for the remainder of the runner's own invocation -- never
    # claimed to persist for "the remainder of the test process".
    assert harness.history_at_return is True
    # (4) absent after that same invocation returns.
    assert authority.mint_nonce not in _STAGE_TERMINAL_SEAL_HISTORY

    # The harness-forced second reach is refused, with no second registration.
    assert harness.forced_reach_report is not None
    assert harness.forced_reach_report["second_decision_registered"] is False
    assert harness.forced_reach_report["seal_history_present"] is True


# ---------------------------------------------------------------------------
# T-139 -- failure AFTER registration, BEFORE construction (T-135 sub-case (b))
# ---------------------------------------------------------------------------


def test_t139_and_t135b_an_orphaned_decision_entry_authenticates_nothing(
    make_authority, closure_spy
):
    authority = make_authority("S1-X1")
    result, harness = _drive(
        authority, "after_registration", force_second_reach=True, closure_spy=closure_spy
    )

    _assert_common_mint_failure_shape(authority, result)
    assert harness.sealing_step_reaches == 1

    # GROUP (I) -- while the invocation is still active.
    # (1) the history entry is present.
    assert harness.history_during_unwind is True
    # (3) an ORPHANED decision entry exists: registered at step 4, but no
    # object was ever returned to any caller, because step 5 never completed.
    assert harness.decision_entries_during_unwind == 1
    # (2) the harness-forced second reach is refused, with no second
    # registration -- an adversarial injection, never an operational retry.
    assert harness.forced_reach_report is not None
    assert harness.forced_reach_report["second_decision_registered"] is False
    assert harness.forced_reach_report["seal_history_present"] is True

    # GROUP (II) -- strictly after the invocation exits. This group never
    # re-asserts group (I)'s forced-reach refusal: no sealing-capable lexical
    # path exists at this point for any backstop to guard.
    # (4) the orphan decision entry is gone -- bounded cleanup, not indefinite.
    assert _STAGE_DECISION_SEALED == {}
    # (5) and so is the seal-history entry.
    assert authority.mint_nonce not in _STAGE_TERMINAL_SEAL_HISTORY


def test_t139_no_code_path_can_construct_a_decision_for_the_orphaned_entry(
    make_authority, closure_spy
):
    """The orphan authenticates nothing, because its nonce escaped nowhere.

    ``__post_init__`` requires the exact, freshly-generated ``decision_nonce``,
    and no caller ever obtained it: the object that would have carried it was
    never constructed.
    """
    from pi_harness_cfg1.stage_decision import (
        CFG1StageClosureDecision,
        Cfg1StageDecisionError,
    )

    captured: dict = {}

    class _Harness(_MintFailureHarness):
        def probe(self, context):
            if context.event == "mint_failed":
                captured.update(dict(_STAGE_DECISION_SEALED))
            super().probe(context)

    authority = make_authority("S1-X1")
    harness = _Harness(authority, "after_registration", force_second_reach=False)
    stage_runner._run_cfg1_stage_with_injected_executor(
        authority, run_executor=synthetic_run_executor(), _internal_probe=harness.probe
    )

    assert len(captured) == 1
    orphan_nonce, record = next(iter(captured.items()))
    # Even KNOWING the nonce (which no caller ever does), the entry is gone by
    # the time anything outside the runner could use it.
    assert orphan_nonce not in _STAGE_DECISION_SEALED
    with pytest.raises(Cfg1StageDecisionError) as excinfo:
        CFG1StageClosureDecision(
            decision_nonce=orphan_nonce,
            authority_mint_nonce=record.authority_mint_nonce,
            stage_id=record.stage_id,
            stage_execution_id=record.stage_execution_id,
            ordinal_status=record.ordinal_status,
            halted_after_ordinal=record.halted_after_ordinal,
            halt_reason_code=record.halt_reason_code,
        )
    assert excinfo.value.reason_code == "UNKNOWN_DECISION_NONCE"


# ---------------------------------------------------------------------------
# T-140 -- raw exception text reaches NO sink, for any of the three points
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("failure_point", sorted(_FAILURE_POINTS))
def test_t140_no_raw_exception_text_type_or_traceback_reaches_any_sink(
    failure_point, make_authority, closure_spy, capsys
):
    authority = make_authority("S1-X1")
    result, _harness = _drive(
        authority, failure_point, force_second_reach=False, closure_spy=closure_spy
    )

    console = json.dumps(list(result.console_codes)) + capsys.readouterr().out
    written = "".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(Path(authority.execution_directory).rglob("*"))
        if path.is_file()
    )

    for sink in (console, written):
        # (1) the distinctive message and type appear in NEITHER sink.
        assert _DISTINCTIVE_MESSAGE not in sink
        assert "_DistinctiveMintFailure" not in sink
        # (3) no traceback, repr, or str(exc) output of any kind.
        assert "Traceback" not in sink
        assert "RuntimeError" not in sink
    # (2) the only code observable for this failure is the closed literal.
    assert result.console_codes == ("STAGE_DECISION_MINT_FAILED",)


# ---------------------------------------------------------------------------
# T-136's ordinary-completion half (the mint-failure half is T-138/T-139)
# ---------------------------------------------------------------------------


def test_t136_the_history_fact_is_absent_only_after_an_ordinary_run_returns(
    make_authority,
):
    seen: list[bool] = []

    # The probe namespace deliberately exposes no registry accessor of its own,
    # so a direct module read is the honest way to inspect an internal fact.
    def _probe(context):
        if context.event == "stage:before_return":
            seen.append(authority.mint_nonce in _STAGE_TERMINAL_SEAL_HISTORY)

    authority = make_authority("S1-X1")
    result = stage_runner._run_cfg1_stage_with_injected_executor(
        authority, run_executor=synthetic_run_executor(), _internal_probe=_probe
    )
    assert result.disposition == "STAGE_COMPLETED"
    assert seen == [True]
    assert authority.mint_nonce not in _STAGE_TERMINAL_SEAL_HISTORY
