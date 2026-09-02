"""Offline tests for :mod:`qualification.semantic_session` (5F3B-Q1-PRE1)."""

from __future__ import annotations

import pytest

from qualification.i2b_session import ObservationError, RuntimeSession
from qualification.report_accuracy import ReportClaims
from qualification.scope import RefusalEvent
from qualification.semantic_session import (
    BrokerActivityObservation,
    FinalReportClaimsObservation,
    SemanticPromptDispatchObservation,
    SemanticPromptDispatchState,
    SemanticPromptRequest,
    SemanticTurnObservation,
    require_dispatch_matches_request,
)

_RUN_ID = "run-1"
_SESSION = RuntimeSession(run_id=_RUN_ID, broker_session_id="bsess-1", runtime_session_id="rsess-1")


def _dispatch(
    state: SemanticPromptDispatchState = SemanticPromptDispatchState.CONFIRMED_SENT,
    *,
    run_id: str = _RUN_ID,
    runtime_session_id: str = "rsess-1",
    task_id: str = "IQ-1",
    task_revision: str = "IQ-1@abc",
) -> SemanticPromptDispatchObservation:
    return SemanticPromptDispatchObservation(
        run_id=run_id,
        runtime_session_id=runtime_session_id,
        task_id=task_id,
        task_revision=task_revision,
        dispatch_state=state,
    )


def test_semantic_prompt_request_valid_by_construction() -> None:
    req = SemanticPromptRequest(
        run_id=_RUN_ID, runtime_session=_SESSION, task_id="IQ-1", task_revision="IQ-1@abc"
    )
    assert req.task_id == "IQ-1"


def test_semantic_prompt_request_refuses_foreign_runtime_session() -> None:
    other = RuntimeSession(run_id="other-run", broker_session_id="b", runtime_session_id="r")
    with pytest.raises(ObservationError):
        SemanticPromptRequest(
            run_id=_RUN_ID, runtime_session=other, task_id="IQ-1", task_revision="IQ-1@abc"
        )


def test_turn_observation_requires_exactly_one_terminal_fact() -> None:
    # Neither settled nor deadline_reached: unconstructible.
    with pytest.raises(ObservationError):
        SemanticTurnObservation(
            runtime_session_id="rsess-1", dispatch=_dispatch(), call_succeeded=True
        )
    # Both settled and deadline_reached: unconstructible (mutually exclusive).
    with pytest.raises(ObservationError):
        SemanticTurnObservation(
            runtime_session_id="rsess-1",
            dispatch=_dispatch(),
            call_succeeded=True,
            agent_settled=True,
            deadline_reached=True,
        )


def test_turn_observation_failed_call_carries_no_terminal_fact() -> None:
    with pytest.raises(ObservationError):
        SemanticTurnObservation(
            runtime_session_id="rsess-1",
            dispatch=_dispatch(SemanticPromptDispatchState.CONFIRMED_NOT_SENT),
            call_succeeded=False,
            agent_settled=True,
        )
    ok = SemanticTurnObservation(
        runtime_session_id="rsess-1",
        dispatch=_dispatch(SemanticPromptDispatchState.CONFIRMED_NOT_SENT),
        call_succeeded=False,
    )
    assert ok.call_succeeded is False


# ===========================================================================
# 5F3B-Q1-PRE1-FU1: SemanticPromptDispatchObservation / dispatch-state binding
# ===========================================================================


def test_dispatch_observation_requires_exact_dispatch_state_type() -> None:
    with pytest.raises(ObservationError):
        SemanticPromptDispatchObservation(
            run_id=_RUN_ID,
            runtime_session_id="rsess-1",
            task_id="IQ-1",
            task_revision="IQ-1@abc",
            dispatch_state="CONFIRMED_SENT",  # a str, not the enum -- refused
        )
    with pytest.raises(ObservationError):
        SemanticPromptDispatchObservation(
            run_id=_RUN_ID,
            runtime_session_id="rsess-1",
            task_id="IQ-1",
            task_revision="IQ-1@abc",
            dispatch_state=1,  # bool/truthiness confusion -- refused
        )


def test_turn_observation_requires_dispatch_bound_to_same_runtime_session() -> None:
    with pytest.raises(ObservationError):
        SemanticTurnObservation(
            runtime_session_id="rsess-1",
            dispatch=_dispatch(runtime_session_id="rsess-OTHER"),
            call_succeeded=True,
            agent_settled=True,
        )


def test_turn_observation_only_confirmed_sent_may_carry_call_succeeded() -> None:
    for state in (
        SemanticPromptDispatchState.CONFIRMED_NOT_SENT,
        SemanticPromptDispatchState.SEND_STATE_INDETERMINATE,
    ):
        with pytest.raises(ObservationError):
            SemanticTurnObservation(
                runtime_session_id="rsess-1", dispatch=_dispatch(state), call_succeeded=True
            )


def test_turn_observation_confirmed_sent_requires_call_succeeded() -> None:
    with pytest.raises(ObservationError):
        SemanticTurnObservation(
            runtime_session_id="rsess-1",
            dispatch=_dispatch(SemanticPromptDispatchState.CONFIRMED_SENT),
            call_succeeded=False,
        )


def test_require_dispatch_matches_request_checks_every_bound_field() -> None:
    request = SemanticPromptRequest(
        run_id=_RUN_ID, runtime_session=_SESSION, task_id="IQ-1", task_revision="IQ-1@abc"
    )
    assert require_dispatch_matches_request(_dispatch(), request) is True
    assert require_dispatch_matches_request(_dispatch(run_id="other-run"), request) is False
    assert (
        require_dispatch_matches_request(_dispatch(runtime_session_id="other-sess"), request)
        is False
    )
    assert require_dispatch_matches_request(_dispatch(task_id="IQ-2"), request) is False
    assert (
        require_dispatch_matches_request(_dispatch(task_revision="IQ-1@other"), request) is False
    )
    assert require_dispatch_matches_request(object(), request) is False


def test_broker_activity_observation_bounds_are_enforced() -> None:
    with pytest.raises(ObservationError):
        BrokerActivityObservation(
            runtime_session_id="rsess-1", call_succeeded=True, read_operation_count=999
        )
    with pytest.raises(ObservationError):
        BrokerActivityObservation(
            runtime_session_id="rsess-1", call_succeeded=True, edit_operation_count=999
        )


def test_broker_activity_observation_failed_call_carries_no_activity() -> None:
    with pytest.raises(ObservationError):
        BrokerActivityObservation(
            runtime_session_id="rsess-1", call_succeeded=False, read_operation_count=1
        )


def test_broker_activity_observation_refusals_are_scope_refusal_events() -> None:
    obs = BrokerActivityObservation(
        runtime_session_id="rsess-1",
        call_succeeded=True,
        refusals=(RefusalEvent(reason_code="stale_base"),),
    )
    assert type(obs.refusals[0]) is RefusalEvent


def test_final_report_claims_observation_requires_exact_report_claims_type() -> None:
    with pytest.raises(ObservationError):
        FinalReportClaimsObservation(runtime_session_id="rsess-1", claims={"claimed_done": True})
    ok = FinalReportClaimsObservation(
        runtime_session_id="rsess-1", claims=ReportClaims(claimed_done=True)
    )
    assert ok.claims.claimed_done is True
