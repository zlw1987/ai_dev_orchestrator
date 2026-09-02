"""Offline tests for :mod:`qualification.semantic_session` (5F3B-Q1-PRE1)."""

from __future__ import annotations

import pytest

from qualification.i2b_session import ObservationError, RuntimeSession
from qualification.report_accuracy import ReportClaims
from qualification.scope import RefusalEvent
from qualification.semantic_session import (
    DISPATCH_EVIDENCE_CODE_STATES,
    BrokerActivityObservation,
    FinalReportClaimsObservation,
    SemanticDispatchEvidenceCode,
    SemanticPromptDispatchObservation,
    SemanticPromptDispatchState,
    SemanticPromptRequest,
    SemanticTurnObservation,
    SemanticTurnOutcome,
    SemanticTurnRequest,
    require_dispatch_matches_request,
    require_turn_matches_request,
)

_DEFAULT_EVIDENCE_CODE = {
    SemanticPromptDispatchState.CONFIRMED_SENT: (
        SemanticDispatchEvidenceCode.PROMPT_RESPONSE_ACCEPTED
    ),
    SemanticPromptDispatchState.CONFIRMED_NOT_SENT: (
        SemanticDispatchEvidenceCode.PROMPT_RESPONSE_REFUSED
    ),
    SemanticPromptDispatchState.SEND_STATE_INDETERMINATE: (
        SemanticDispatchEvidenceCode.ADAPTER_RAISED
    ),
}

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
        dispatch_evidence_code=_DEFAULT_EVIDENCE_CODE[state],
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


def test_turn_outcome_is_a_closed_three_value_enum() -> None:
    """5F3B-Q1-PRE1-FU2: FU1's two-boolean shape (agent_settled XOR
    deadline_reached) could not represent a turn that became unobservable
    after the acknowledgement, so a live adapter had to fabricate a deadline
    or raise. ``OBSERVATION_FAILED`` is that third terminal state."""
    assert {member.value for member in SemanticTurnOutcome} == {
        "SETTLED",
        "DEADLINE_REACHED",
        "OBSERVATION_FAILED",
    }
    for outcome in SemanticTurnOutcome:
        observation = SemanticTurnObservation(
            runtime_session_id="rsess-1", turn_outcome=outcome
        )
        # Exactly one derived projection is true, always -- there is no way
        # to report two terminal facts, and no way to report none.
        assert (
            observation.agent_settled,
            observation.deadline_reached,
            observation.observation_failed,
        ).count(True) == 1


def test_turn_observation_refuses_raw_text_or_a_wrong_type_outcome() -> None:
    for bad in ("SETTLED", 1, True, None):
        with pytest.raises(ObservationError):
            SemanticTurnObservation(runtime_session_id="rsess-1", turn_outcome=bad)


def test_turn_observation_carries_no_dispatch_fact_at_all() -> None:
    """The structural half of invariant I-1: there is NO field on a phase-2
    observation through which a turn outcome could carry, contradict, or
    rewrite the phase-1 send fact."""
    import dataclasses

    names = {f.name for f in dataclasses.fields(SemanticTurnObservation)}
    assert names == {"runtime_session_id", "turn_outcome", "agent_end_observed"}
    assert "dispatch" not in names
    assert "call_succeeded" not in names
    assert "semantic_prompts_sent" not in names


def test_agent_end_is_an_independent_non_completion_fact() -> None:
    observation = SemanticTurnObservation(
        runtime_session_id="rsess-1",
        turn_outcome=SemanticTurnOutcome.OBSERVATION_FAILED,
        agent_end_observed=True,
    )
    assert observation.agent_end_observed is True
    assert observation.agent_settled is False
    with pytest.raises(ObservationError):
        SemanticTurnObservation(
            runtime_session_id="rsess-1",
            turn_outcome=SemanticTurnOutcome.SETTLED,
            agent_end_observed=1,  # truthiness confusion -- refused
        )


def test_turn_request_requires_a_confirmed_sent_dispatch() -> None:
    for state in (
        SemanticPromptDispatchState.CONFIRMED_NOT_SENT,
        SemanticPromptDispatchState.SEND_STATE_INDETERMINATE,
    ):
        with pytest.raises(ObservationError):
            SemanticTurnRequest(
                run_id=_RUN_ID,
                runtime_session=_SESSION,
                task_id="IQ-1",
                task_revision="IQ-1@abc",
                dispatch=_dispatch(state),
            )
    ok = SemanticTurnRequest(
        run_id=_RUN_ID,
        runtime_session=_SESSION,
        task_id="IQ-1",
        task_revision="IQ-1@abc",
        dispatch=_dispatch(),
    )
    assert ok.dispatch.dispatch_state is SemanticPromptDispatchState.CONFIRMED_SENT


def test_turn_request_refuses_a_dispatch_for_a_different_run_session_or_task() -> None:
    for kwargs in (
        {"run_id": "other-run"},
        {"runtime_session_id": "rsess-OTHER"},
        {"task_id": "IQ-2"},
        {"task_revision": "IQ-1@other"},
    ):
        with pytest.raises(ObservationError):
            SemanticTurnRequest(
                run_id=_RUN_ID,
                runtime_session=_SESSION,
                task_id="IQ-1",
                task_revision="IQ-1@abc",
                dispatch=_dispatch(**kwargs),
            )


def test_require_turn_matches_request_checks_type_and_session() -> None:
    request = SemanticTurnRequest(
        run_id=_RUN_ID,
        runtime_session=_SESSION,
        task_id="IQ-1",
        task_revision="IQ-1@abc",
        dispatch=_dispatch(),
    )
    good = SemanticTurnObservation(
        runtime_session_id="rsess-1", turn_outcome=SemanticTurnOutcome.SETTLED
    )
    assert require_turn_matches_request(good, request) is True
    foreign = SemanticTurnObservation(
        runtime_session_id="rsess-OTHER", turn_outcome=SemanticTurnOutcome.SETTLED
    )
    assert require_turn_matches_request(foreign, request) is False
    assert require_turn_matches_request(object(), request) is False

    class _Subclassed(SemanticTurnObservation):
        pass

    assert (
        require_turn_matches_request(
            _Subclassed(
                runtime_session_id="rsess-1", turn_outcome=SemanticTurnOutcome.SETTLED
            ),
            request,
        )
        is False
    )


def test_every_dispatch_state_has_at_least_one_evidence_code() -> None:
    covered = set(DISPATCH_EVIDENCE_CODE_STATES.values())
    assert covered == set(SemanticPromptDispatchState)
    # And every declared code maps somewhere -- no code without a state.
    assert set(DISPATCH_EVIDENCE_CODE_STATES) == set(SemanticDispatchEvidenceCode)


def test_dispatch_observation_refuses_a_forged_code_state_pairing() -> None:
    for code in SemanticDispatchEvidenceCode:
        established = DISPATCH_EVIDENCE_CODE_STATES[code]
        for state in SemanticPromptDispatchState:
            if state is established:
                continue
            with pytest.raises(ObservationError):
                SemanticPromptDispatchObservation(
                    run_id=_RUN_ID,
                    runtime_session_id="rsess-1",
                    task_id="IQ-1",
                    task_revision="IQ-1@abc",
                    dispatch_state=state,
                    dispatch_evidence_code=code,
                )


def test_dispatch_observation_requires_an_exact_evidence_code_type() -> None:
    for bad in ("PROMPT_RESPONSE_ACCEPTED", None, 1, True):
        with pytest.raises(ObservationError):
            SemanticPromptDispatchObservation(
                run_id=_RUN_ID,
                runtime_session_id="rsess-1",
                task_id="IQ-1",
                task_revision="IQ-1@abc",
                dispatch_state=SemanticPromptDispatchState.CONFIRMED_SENT,
                dispatch_evidence_code=bad,
            )


def test_dispatch_observation_requires_exact_dispatch_state_type() -> None:
    with pytest.raises(ObservationError):
        SemanticPromptDispatchObservation(
            run_id=_RUN_ID,
            runtime_session_id="rsess-1",
            task_id="IQ-1",
            task_revision="IQ-1@abc",
            dispatch_state="CONFIRMED_SENT",  # a str, not the enum -- refused
            dispatch_evidence_code=(
                SemanticDispatchEvidenceCode.PROMPT_RESPONSE_ACCEPTED
            ),
        )
    with pytest.raises(ObservationError):
        SemanticPromptDispatchObservation(
            run_id=_RUN_ID,
            runtime_session_id="rsess-1",
            task_id="IQ-1",
            task_revision="IQ-1@abc",
            dispatch_state=1,  # bool/truthiness confusion -- refused
            dispatch_evidence_code=(
                SemanticDispatchEvidenceCode.PROMPT_RESPONSE_ACCEPTED
            ),
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
