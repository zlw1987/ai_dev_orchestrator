"""5F3B-Q1-PRE1-FU2 -- design-conformance regressions.

**No real network connection, credential, Node/Pi process, named pipe, or
model call is ever made here.** Every live-facing adapter is a synthetic
double, and the only subprocess activity is local ``git`` (fixture
population) and ``python -m pytest`` (the fixture's own fixed verification
command, run against itself) -- exactly the surface the rest of this
package's offline suite already uses.

Each section names the frozen contract it closes, from
``docs/PHASE_5F3B_Q1_PRE1_DESIGN_FU1_SEMANTIC_DISPATCH_AUTHORITY.md``:

    Sec. 2      two-phase semantic dispatch / turn observation
    Sec. 3      indeterminate-attempt evidence contract
    Sec. 3.J    sweep stop policy (see test_semantic_sweep.py)
    Sec. 4      distinct count ownership (see test_semantic_sweep.py)
    Sec. 9.1    semantic workspace ownership / verified removal
    Sec. 9.2    full artifact safety context
    Sec. 9.3    optional / untrusted final assistant report
    Sec. 9.4    deep result / sweep immutability
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

from qualification import ATTEMPT_RECORD_VERSION, REFUSAL_RECORD_VERSION
from qualification.corpus import IQ1_CORRECT_ROUNDING, IQ1_TASK
from qualification.hard_bar import QualificationState
from qualification.i2_route import CREDENTIAL_MECHANISM, route_descriptor_for_candidate
from qualification.i2b_session import BrokerSession
from qualification.i2b_workspace import (
    mint_qualification_run_workspace,
    remove_run_workspace,
)
from qualification.outcomes import AutonomousClassification, DiagnosticSubclassification
from qualification.records import RECORD_VERSION
from qualification.report_accuracy import ClaimVerdict, ReportClaims
from qualification.safety import ArtifactSafetyContext
from qualification.semantic_attempt import (
    ATTEMPT_RECORD_KIND,
    CLASSIFICATION_UNAVAILABLE_REASON,
    INDETERMINATE_EVIDENCE_CODES,
    AttemptRecordInvariantError,
    build_attempt_record,
)
from qualification.semantic_controller import (
    CLOSURE_GATES,
    GATING_POST_PROMPT_GATES,
    NON_GATING_POST_PROMPT_GATES,
    POST_PROMPT_GATES,
    PRE_PROMPT_GATES,
    EvidenceEmission,
    ReportAvailability,
    SemanticFailureCode,
    SemanticGateName,
    SemanticSafetyContextError,
    SemanticWorkspaceRemovalStatus,
    build_run_safety_context,
    freeze_mapping,
    workspace_removal_succeeded,
)
from qualification.semantic_session import (
    DISPATCH_EVIDENCE_CODE_STATES,
    FinalReportClaimsObservation,
    SemanticDispatchEvidenceCode,
    SemanticPromptDispatchObservation,
    SemanticPromptDispatchState,
    SemanticPromptRequest,
    SemanticTurnObservation,
    SemanticTurnOutcome,
    SemanticTurnRequest,
)
from qualification.validity import RunValidity

from test_semantic_controller import Harness, _iq1_correct_repair


@pytest.fixture(scope="module")
def git_executable() -> str:
    """AIDO's OWN accepted Git resolution (5F3B-LIVE1-C1-P12a).

    The semantic attempt's fixture-population checkpoint requires EXACT
    STRING EQUALITY with ``resolve_git_executable``'s return value, so this
    fixture must BE that value -- never another spelling of the same target.
    """
    from ai_dev_orchestrator.workspace.git_adapter import resolve_git_executable

    exe = shutil.which("git")
    assert exe, "git must be on PATH to build synthetic fixtures"
    return resolve_git_executable(workspace_root=str(Path(__file__).resolve().parents[1]))


@pytest.fixture()
def evidence_path(tmp_path: Path) -> str:
    return str(tmp_path / "evidence.json")


@pytest.fixture()
def harness(git_executable: str) -> Harness:
    return Harness("A", git_executable)


def _instrumented(h: Harness) -> list[str]:
    """Record the exact adapter-call sequence across BOTH phases."""
    calls: list[str] = []
    dispatch, observe = h.dispatch_semantic_prompt, h.observe_semantic_turn

    def _dispatch(request):
        calls.append("dispatch")
        return dispatch(request)

    def _observe(request):
        calls.append("observe")
        return observe(request)

    h.dispatch_semantic_prompt = _dispatch
    h.observe_semantic_turn = _observe
    return calls


# ===========================================================================
# A. TWO-PHASE SEMANTIC DISPATCH (Sec. 2)
# ===========================================================================


# -- 1: dispatch ACK and turn completion are SEPARATE adapter calls --------


def test_dispatch_and_turn_observation_are_two_distinct_adapter_calls(
    harness: Harness, evidence_path: str
) -> None:
    _iq1_correct_repair(harness)
    calls = _instrumented(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    # Two calls, in order -- never one whole-turn call, and never the turn
    # call first.
    assert calls == ["dispatch", "observe"]
    assert result.dispatch_state is SemanticPromptDispatchState.CONFIRMED_SENT
    assert result.turn_outcome is SemanticTurnOutcome.SETTLED


def test_controller_signature_has_both_phases_and_no_whole_turn_adapter() -> None:
    import inspect

    import qualification.semantic_controller as mod

    parameters = inspect.signature(mod.run_semantic_task_attempt).parameters
    assert "dispatch_semantic_prompt" in parameters
    assert "observe_semantic_turn" in parameters
    assert "send_semantic_prompt" not in parameters
    source = Path(mod.__file__).read_text(encoding="utf-8")
    # Exactly one call site each. A second dispatch call site anywhere would
    # be a second semantic prompt.
    assert source.count("dispatch_semantic_prompt(prompt_request)") == 1
    assert source.count("observe_semantic_turn(turn_request)") == 1


# -- 2: phase 2 is NEVER called without CONFIRMED_SENT ---------------------


@pytest.mark.parametrize(
    "configure",
    [
        pytest.param(
            lambda h: setattr(
                h, "dispatch_state", SemanticPromptDispatchState.CONFIRMED_NOT_SENT
            ),
            id="confirmed_not_sent",
        ),
        pytest.param(
            lambda h: setattr(
                h, "dispatch_state", SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
            ),
            id="indeterminate",
        ),
        pytest.param(
            lambda h: setattr(
                h,
                "dispatch_semantic_prompt",
                lambda request: (_ for _ in ()).throw(RuntimeError("boom")),
            ),
            id="dispatch_raised",
        ),
        pytest.param(
            lambda h: setattr(h, "dispatch_semantic_prompt", lambda request: object()),
            id="dispatch_wrong_type",
        ),
        pytest.param(lambda h: setattr(h, "h2_ok", False), id="pre_prompt_gate_failed"),
    ],
)
def test_phase_two_is_never_entered_without_confirmed_sent(
    harness: Harness, evidence_path: str, configure
) -> None:
    observed: list[object] = []
    original = harness.observe_semantic_turn
    harness.observe_semantic_turn = lambda request: (
        observed.append(request) or original(request)
    )
    configure(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    assert observed == []
    assert result.turn_outcome is None
    assert result.dispatch_state is not SemanticPromptDispatchState.CONFIRMED_SENT


def test_turn_request_cannot_be_constructed_from_a_non_confirmed_dispatch() -> None:
    """The structural half of the same rule: even a caller that bypassed the
    controller could not build the phase-2 input."""
    from qualification.i2b_session import RuntimeSession

    session = RuntimeSession(
        run_id="sem-1", broker_session_id="bsess-1", runtime_session_id="rsess-1"
    )
    for state, code in (
        (
            SemanticPromptDispatchState.CONFIRMED_NOT_SENT,
            SemanticDispatchEvidenceCode.PROMPT_RESPONSE_REFUSED,
        ),
        (
            SemanticPromptDispatchState.SEND_STATE_INDETERMINATE,
            SemanticDispatchEvidenceCode.ADAPTER_RAISED,
        ),
    ):
        dispatch = SemanticPromptDispatchObservation(
            run_id="sem-1",
            runtime_session_id="rsess-1",
            task_id="IQ-1",
            task_revision="IQ-1@r1",
            dispatch_state=state,
            dispatch_evidence_code=code,
        )
        with pytest.raises(Exception):
            SemanticTurnRequest(
                run_id="sem-1",
                runtime_session=session,
                task_id="IQ-1",
                task_revision="IQ-1@r1",
                dispatch=dispatch,
            )


# -- 3/4: a phase-2 failure NEVER erases CONFIRMED_SENT --------------------


@pytest.mark.parametrize(
    "configure,expected_end",
    [
        pytest.param(
            lambda h: setattr(
                h,
                "observe_semantic_turn",
                lambda request: (_ for _ in ()).throw(RuntimeError("phase 2 blew up")),
            ),
            False,
            id="phase2_adapter_raised",
        ),
        pytest.param(
            lambda h: setattr(h, "observe_semantic_turn", lambda request: object()),
            False,
            id="phase2_wrong_type",
        ),
        pytest.param(
            lambda h: setattr(
                h, "turn_outcome", SemanticTurnOutcome.OBSERVATION_FAILED
            ),
            False,
            id="phase2_protocol_or_read_failure",
        ),
        pytest.param(
            lambda h: setattr(
                h,
                "observe_semantic_turn",
                lambda request: SemanticTurnObservation(
                    runtime_session_id="rsess-FOREIGN",
                    turn_outcome=SemanticTurnOutcome.SETTLED,
                ),
            ),
            False,
            id="phase2_foreign_session",
        ),
    ],
)
def test_phase_two_failure_preserves_semantic_prompts_sent_one(
    harness: Harness, evidence_path: str, configure, expected_end: bool
) -> None:
    """Invariant I-1. Under FU1 these shapes had to either fabricate a
    deadline or raise -- and raising erased the already-established
    CONFIRMED_SENT into SEND_STATE_INDETERMINATE, converting a KNOWN SPENT
    prompt into an UNKNOWN one."""
    _iq1_correct_repair(harness)
    configure(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.dispatch_state is SemanticPromptDispatchState.CONFIRMED_SENT
    assert result.semantic_prompts_sent == 1
    assert result.turn_outcome is SemanticTurnOutcome.OBSERVATION_FAILED
    assert result.agent_end_observed is expected_end
    assert result.failed_gate is SemanticGateName.TURN_COMPLETION
    assert result.failure_code is SemanticFailureCode.TURN_OBSERVATION_FAILED
    # An observation failure is never reported as a deadline, and never as a
    # settle.
    assert result.turn_outcome is not SemanticTurnOutcome.DEADLINE_REACHED
    assert result.diagnostic_subclassification is not DiagnosticSubclassification.RUNTIME_TIMEOUT
    # A primary record still exists -- the prompt WAS spent, and that fact is
    # retained immutably rather than lost.
    assert result.qualification_record is not None
    assert result.attempt_record is None


# -- 5: a deadline is a MODEL outcome, never contamination -----------------


def test_confirmed_sent_then_deadline_is_runtime_timeout_not_contamination(
    harness: Harness, evidence_path: str
) -> None:
    harness.agent_settled = False
    harness.deadline_reached = True
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.semantic_prompts_sent == 1
    assert result.turn_outcome is SemanticTurnOutcome.DEADLINE_REACHED
    assert result.run_validity is RunValidity.VALID
    assert result.scoring_eligible is True
    assert result.autonomous_classification is AutonomousClassification.AUTONOMOUS_FAIL
    assert result.diagnostic_subclassification is DiagnosticSubclassification.RUNTIME_TIMEOUT
    assert result.failed_gate is None


# -- 6: agent_end alone never becomes SETTLED ------------------------------


def test_agent_end_observed_alone_never_upgrades_to_settled(
    harness: Harness, evidence_path: str
) -> None:
    harness.agent_settled = False
    harness.turn_outcome = SemanticTurnOutcome.OBSERVATION_FAILED
    harness.agent_end_observed = True
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.agent_end_observed is True
    assert result.turn_outcome is SemanticTurnOutcome.OBSERVATION_FAILED
    assert result.autonomous_classification is None


# -- 7: a local write/flush success with NO acknowledgement -----------------


def test_write_flush_success_without_acknowledgement_is_indeterminate(
    harness: Harness, evidence_path: str
) -> None:
    """Sec. 1.7: a successful ``send_command`` proves only local transport
    issuance -- not that Pi was alive to read it, framed a line, parsed it,
    reached the prompt case, or ran preflight. A live adapter reports that as
    SEND_STATE_INDETERMINATE with a bounded code, and the controller must
    honor it rather than reading a successful Python call as a send."""
    harness.dispatch_state = SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
    harness.dispatch_evidence_code = (
        SemanticDispatchEvidenceCode.WRITE_FAILED_TRANSMISSION_UNKNOWN
    )
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.dispatch_state is SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
    assert result.semantic_prompts_sent is None
    assert (
        result.dispatch_evidence_code
        is SemanticDispatchEvidenceCode.WRITE_FAILED_TRANSMISSION_UNKNOWN
    )


# -- 8: a correlated prompt refusal is CONFIRMED_NOT_SENT ------------------


def test_prompt_response_refused_is_confirmed_not_sent(
    harness: Harness, evidence_path: str
) -> None:
    """Sec. 1.5: ``success: false`` can only come from the ``catch`` in
    ``AgentSession.prompt``, whose scope ends before ``_runAgentPrompt`` --
    nothing was handed to the agent loop and no provider request was made.
    A proven zero, so the attempt is NOT consumed."""
    harness.dispatch_state = SemanticPromptDispatchState.CONFIRMED_NOT_SENT
    harness.dispatch_evidence_code = SemanticDispatchEvidenceCode.PROMPT_RESPONSE_REFUSED
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.semantic_prompts_sent == 0
    assert result.infrastructure_refusal is True
    assert (
        result.dispatch_evidence_code
        is SemanticDispatchEvidenceCode.PROMPT_RESPONSE_REFUSED
    )
    assert result.qualification_record is not None
    assert result.attempt_record is None


# -- 9: a malformed or foreign dispatch observation ------------------------


@pytest.mark.parametrize(
    "make_adapter",
    [
        pytest.param(lambda: (lambda request: object()), id="wrong_type"),
        pytest.param(
            lambda: (
                lambda request: SimpleNamespace(
                    run_id=request.run_id,
                    dispatch_state=SemanticPromptDispatchState.CONFIRMED_SENT,
                )
            ),
            id="duck_typed_impostor",
        ),
        pytest.param(
            lambda: (
                lambda request: SemanticPromptDispatchObservation(
                    run_id=request.run_id,
                    runtime_session_id="rsess-FOREIGN",
                    task_id=request.task_id,
                    task_revision=request.task_revision,
                    dispatch_state=SemanticPromptDispatchState.CONFIRMED_SENT,
                    dispatch_evidence_code=(
                        SemanticDispatchEvidenceCode.PROMPT_RESPONSE_ACCEPTED
                    ),
                )
            ),
            id="foreign_session",
        ),
    ],
)
def test_malformed_or_foreign_dispatch_observation_is_indeterminate(
    harness: Harness, evidence_path: str, make_adapter
) -> None:
    harness.dispatch_semantic_prompt = make_adapter()
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.dispatch_state is SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
    assert result.semantic_prompts_sent is None
    assert (
        result.dispatch_evidence_code
        is SemanticDispatchEvidenceCode.OBSERVATION_MALFORMED_OR_FOREIGN
    )


def test_dispatch_observation_subclass_substitution_is_refused(
    harness: Harness, evidence_path: str
) -> None:
    class _Subclassed(SemanticPromptDispatchObservation):
        pass

    harness.dispatch_semantic_prompt = lambda request: _Subclassed(
        run_id=request.run_id,
        runtime_session_id=request.runtime_session.runtime_session_id,
        task_id=request.task_id,
        task_revision=request.task_revision,
        dispatch_state=SemanticPromptDispatchState.CONFIRMED_SENT,
        dispatch_evidence_code=SemanticDispatchEvidenceCode.PROMPT_RESPONSE_ACCEPTED,
    )
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.dispatch_state is SemanticPromptDispatchState.SEND_STATE_INDETERMINATE


def test_evidence_code_cannot_be_attached_to_a_state_it_does_not_establish() -> None:
    """The bounded vocabulary is not decorative: each code maps to exactly
    one state, and a forged pairing is refused at construction."""
    with pytest.raises(Exception):
        SemanticPromptDispatchObservation(
            run_id="sem-1",
            runtime_session_id="rsess-1",
            task_id="IQ-1",
            task_revision="IQ-1@r1",
            # An indeterminate code cannot claim CONFIRMED_SENT.
            dispatch_state=SemanticPromptDispatchState.CONFIRMED_SENT,
            dispatch_evidence_code=SemanticDispatchEvidenceCode.ADAPTER_RAISED,
        )
    with pytest.raises(Exception):
        SemanticPromptDispatchObservation(
            run_id="sem-1",
            runtime_session_id="rsess-1",
            task_id="IQ-1",
            task_revision="IQ-1@r1",
            dispatch_state=SemanticPromptDispatchState.CONFIRMED_SENT,
            dispatch_evidence_code="PROMPT_RESPONSE_ACCEPTED",  # raw text
        )


def test_dispatch_evidence_code_mapping_is_read_only() -> None:
    assert isinstance(DISPATCH_EVIDENCE_CODE_STATES, MappingProxyType)
    with pytest.raises(TypeError):
        DISPATCH_EVIDENCE_CODE_STATES[  # type: ignore[index]
            SemanticDispatchEvidenceCode.ADAPTER_RAISED
        ] = SemanticPromptDispatchState.CONFIRMED_SENT


# -- 10: no SECOND dispatch after ANY of the three states ------------------


@pytest.mark.parametrize(
    "state",
    [
        SemanticPromptDispatchState.CONFIRMED_SENT,
        SemanticPromptDispatchState.CONFIRMED_NOT_SENT,
        SemanticPromptDispatchState.SEND_STATE_INDETERMINATE,
    ],
)
def test_exactly_one_dispatch_for_every_dispatch_state(
    harness: Harness, evidence_path: str, state
) -> None:
    _iq1_correct_repair(harness)
    harness.dispatch_state = state
    calls = _instrumented(harness)
    harness.run(IQ1_TASK, evidence_path)
    assert calls.count("dispatch") == 1
    assert calls.count("observe") == (
        1 if state is SemanticPromptDispatchState.CONFIRMED_SENT else 0
    )


# ===========================================================================
# B. THE INDETERMINATE ATTEMPT ARTIFACT (Sec. 3)
# ===========================================================================


def _indeterminate(h: Harness) -> None:
    h.dispatch_semantic_prompt = lambda request: (_ for _ in ()).throw(
        ConnectionResetError("wire dropped after (maybe) writing the request")
    )


# -- 11/14: exactly ONE artifact, and it is the attempt artifact -----------


def test_indeterminate_attempt_writes_exactly_one_attempt_artifact(
    harness: Harness, tmp_path: Path
) -> None:
    evidence_path = str(tmp_path / "evidence.json")
    _indeterminate(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    written = sorted(entry.name for entry in tmp_path.iterdir() if entry.is_file())
    assert written == ["evidence.json"]
    payload = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
    assert payload["record_version"] == ATTEMPT_RECORD_VERSION
    assert payload["record_kind"] == ATTEMPT_RECORD_KIND
    # NEVER also a primary record for the same attempt.
    assert payload["record_version"] != RECORD_VERSION
    assert result.qualification_record is None
    assert result.attempt_record is not None


# -- 12: the gap is an ABSENT KEY, at every depth --------------------------


def test_attempt_artifact_omits_semantic_prompts_sent_entirely(
    harness: Harness, evidence_path: str
) -> None:
    _indeterminate(harness)
    harness.run(IQ1_TASK, evidence_path)
    raw = Path(evidence_path).read_text(encoding="utf-8")
    payload = json.loads(raw)

    def _has_key(value, key):
        if isinstance(value, dict):
            return key in value or any(_has_key(v, key) for v in value.values())
        if isinstance(value, list):
            return any(_has_key(v, key) for v in value)
        return False

    assert not _has_key(payload, "semantic_prompts_sent")
    assert payload["semantic_prompts_sent_established"] is False
    # Never a sentinel doing double duty.
    assert '"semantic_prompts_sent"' not in raw
    # Sec. 3.G: the attempt IS consumed -- an indeterminate send is not a
    # PROVEN zero, and treating it as one would risk exposing the candidate
    # to the same frozen task twice with the first exposure unrecorded.
    assert payload["attempt_consumed"] is True
    assert payload["automatic_semantic_retry"] is False
    assert payload["scoring_eligible"] is False
    assert payload["run_validity"] is None
    assert payload["hard_bar_evaluable"] is False
    assert payload["qualification_record_emitted"] is False
    assert (
        payload["cleanup_classification_unavailable_reason"]
        == CLASSIFICATION_UNAVAILABLE_REASON
    )
    assert (
        payload["workspace_removal_classification_unavailable_reason"]
        == CLASSIFICATION_UNAVAILABLE_REASON
    )
    assert "AIDO" in payload["claim_scope"]


def test_attempt_record_builder_refuses_a_determinate_evidence_code() -> None:
    assert INDETERMINATE_EVIDENCE_CODES == frozenset(
        code
        for code, state in DISPATCH_EVIDENCE_CODE_STATES.items()
        if state is SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
    )
    with pytest.raises(AttemptRecordInvariantError):
        build_attempt_record(
            candidate="A",
            model_id="qwen3-coder-next",
            task_id="IQ-1",
            task_revision="IQ-1@r1",
            dispatch_evidence_code=(
                SemanticDispatchEvidenceCode.PROMPT_RESPONSE_ACCEPTED
            ),
            gate_statuses={},
            observed_pi_version=None,
            compatibility_facts={},
            compatibility_gate_passed=False,
            route_provenance={},
            closure={},
        )


def test_attempt_record_builder_refuses_a_smuggled_prompt_count() -> None:
    with pytest.raises(AttemptRecordInvariantError):
        build_attempt_record(
            candidate="A",
            model_id="qwen3-coder-next",
            task_id="IQ-1",
            task_revision="IQ-1@r1",
            dispatch_evidence_code=SemanticDispatchEvidenceCode.ADAPTER_RAISED,
            gate_statuses={},
            observed_pi_version=None,
            compatibility_facts={},
            compatibility_gate_passed=False,
            route_provenance={},
            # Nested, one level down -- the recursive check must still catch it.
            closure={"generated_config_cleanup": {"semantic_prompts_sent": 0}},
        )


def test_attempt_record_builder_refuses_a_mismatched_candidate_model_pairing() -> None:
    with pytest.raises(AttemptRecordInvariantError):
        build_attempt_record(
            candidate="A",
            model_id="minimax-m2.7",  # B's model
            task_id="IQ-1",
            task_revision="IQ-1@r1",
            dispatch_evidence_code=SemanticDispatchEvidenceCode.ADAPTER_RAISED,
            gate_statuses={},
            observed_pi_version=None,
            compatibility_facts={},
            compatibility_gate_passed=False,
            route_provenance={},
            closure={},
        )


# -- 13/35: a scrub refusal produces ONLY the bounded refusal fallback -----


def test_attempt_artifact_scrub_refusal_emits_only_the_bounded_refusal(
    harness: Harness, evidence_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sec. 3.C: the artifact-emission-refusal RECORD is not reused as the
    MEANING of an indeterminate attempt -- but it IS the correct fallback if
    the attempt artifact itself fails the scrub. And Sec. 9.2.3: the ONE
    complete safety context protects the attempt artifact exactly as it
    protects a primary record, so a workspace needle catches it here.
    """
    import qualification.semantic_controller as mod

    original = mod.build_attempt_record
    captured: dict[str, str] = {}

    def _leaky(**kwargs):
        payload = original(**kwargs)
        # 5F3B-Q1-PRE1-FU2A-FU1A: the payload's top-level (and pi_runtime)
        # key set is now CLOSED, so an extra, unknown key is refused by that
        # earlier, stronger check before it could ever reach the scrub this
        # test means to exercise. Leak the needle into an EXISTING,
        # unconstrained str field instead (`pi_runtime.observed_version` is
        # never checked against a fixed value) -- the scrub is still what
        # catches it.
        payload["pi_runtime"] = {
            **payload["pi_runtime"],
            "observed_version": captured["workspace"],
        }
        return payload

    original_remove = mod.remove_run_workspace

    def _capture_then_remove(workspace):
        captured["workspace"] = workspace.experiment_root
        return original_remove(workspace)

    monkeypatch.setattr(mod, "remove_run_workspace", _capture_then_remove)
    monkeypatch.setattr(mod, "build_attempt_record", _leaky)
    _indeterminate(harness)
    result = harness.run(IQ1_TASK, evidence_path)

    payload = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
    assert payload["record_version"] == REFUSAL_RECORD_VERSION
    assert payload["refused_record_kind"] == ATTEMPT_RECORD_KIND
    assert payload["outcome"] == "artifact_emission_refused"
    assert payload["candidate_artifact_not_emitted"] is True
    assert "workspace_absolute_path_present" in payload["finding_categories"]
    # The unsafe payload itself never reached disk.
    assert captured["workspace"] not in json.dumps(payload)
    assert result.evidence_emission is not None
    assert result.evidence_emission.refused is True
    assert (
        result.gate_statuses[SemanticGateName.EVIDENCE_SAFETY.value]
        == "FAILED:EVIDENCE_SCRUB_REFUSED"
    )


# ===========================================================================
# C. SEMANTIC WORKSPACE OWNERSHIP AND VERIFIED REMOVAL (Sec. 9.1)
# ===========================================================================


# -- 24/25: the STRICT acceptance predicate --------------------------------


@pytest.mark.parametrize(
    "result,expected",
    [
        pytest.param(
            {"removed": True, "residual_file_count": 0, "verified": True}, True, id="the_one_success"
        ),
        pytest.param(
            {"removed": False, "residual_file_count": 3, "verified": True},
            False,
            id="residual_files_with_verified_true",
        ),
        pytest.param(
            {"removed": True, "residual_file_count": 3, "verified": True},
            False,
            id="nonzero_residual_is_never_partial_success",
        ),
        pytest.param(
            {"removed": True, "residual_file_count": False, "verified": True},
            False,
            id="bool_is_not_an_int_substitute",
        ),
        pytest.param(
            {"removed": True, "residual_file_count": 0, "verified": "true"},
            False,
            id="truthy_string_is_refused",
        ),
        pytest.param(
            {"removed": "true", "residual_file_count": 0, "verified": True},
            False,
            id="truthy_removed_is_refused",
        ),
        pytest.param({"removed": True, "verified": True}, False, id="missing_key"),
        pytest.param(None, False, id="non_dict"),
        pytest.param(SimpleNamespace(removed=True), False, id="duck_typed_object"),
    ],
)
def test_workspace_removal_predicate_fails_closed(result, expected: bool) -> None:
    assert workspace_removal_succeeded(result) is expected


# -- 20/21/22/23: removal is attempted EXACTLY ONCE on every terminal path --


@pytest.mark.parametrize(
    "configure,expect_removal",
    [
        pytest.param(lambda h: None, True, id="confirmed_sent_success"),
        pytest.param(_indeterminate, True, id="indeterminate_dispatch"),
        pytest.param(
            lambda h: setattr(
                h, "dispatch_state", SemanticPromptDispatchState.CONFIRMED_NOT_SENT
            ),
            True,
            id="confirmed_not_sent",
        ),
        pytest.param(lambda h: setattr(h, "h2_ok", False), True, id="pre_prompt_gate_failed"),
        pytest.param(lambda h: setattr(h, "broker_ready", False), True, id="broker_never_ready"),
        pytest.param(
            lambda h: setattr(h, "turn_outcome", SemanticTurnOutcome.OBSERVATION_FAILED),
            True,
            id="phase2_observation_failed",
        ),
        pytest.param(
            lambda h: setattr(h, "runtime_shutdown_ok", False), True, id="teardown_failed"
        ),
    ],
)
def test_workspace_removal_is_attempted_exactly_once_on_every_terminal_path(
    harness: Harness, evidence_path: str, monkeypatch: pytest.MonkeyPatch, configure, expect_removal
) -> None:
    """Sec. 9.1.2: the attempt OWNS its workspace from the instant mint
    returns, and this attempt -- and no other code -- is responsible for
    removing it. Before FU2 the controller never called removal at all, so
    every attempt left its disposable Git fixture tree on disk indefinitely.
    """
    import qualification.semantic_controller as mod

    original = mod.remove_run_workspace
    roots: list[str] = []

    def _counting(workspace):
        roots.append(workspace.experiment_root)
        return original(workspace)

    monkeypatch.setattr(mod, "remove_run_workspace", _counting)
    _iq1_correct_repair(harness)
    configure(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    assert len(roots) == (1 if expect_removal else 0)
    assert result.workspace_removal.attempted is expect_removal
    assert result.workspace_removal.verified is expect_removal
    assert not Path(roots[0]).exists()
    assert (
        result.gate_statuses[SemanticGateName.SEMANTIC_WORKSPACE_REMOVAL.value]
        == "VERIFIED_REMOVED"
    )


def test_no_workspace_means_no_removal_attempt_and_satisfied_closure(
    harness: Harness, evidence_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import qualification.semantic_controller as mod

    calls: list[object] = []
    monkeypatch.setattr(
        mod, "remove_run_workspace", lambda ws: calls.append(ws) or {"removed": True}
    )
    monkeypatch.setattr(
        mod,
        "_mint_run_correlation_id",
        lambda: (_ for _ in ()).throw(RuntimeError("no run id, so no workspace")),
    )
    result = harness.run(IQ1_TASK, evidence_path)
    assert calls == []
    assert result.workspace_removal.attempted is False
    assert result.workspace_removal.closure_satisfied is True
    assert (
        result.gate_statuses[SemanticGateName.SEMANTIC_WORKSPACE_REMOVAL.value]
        == "NOT_REQUIRED"
    )


# -- 26: a raised removal is reported, never swallowed ---------------------


def test_removal_exception_records_attempted_true_verified_false(
    harness: Harness, evidence_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import qualification.semantic_controller as mod

    real_roots: list = []
    original = mod.remove_run_workspace

    def _raising(workspace):
        real_roots.append(workspace)
        raise OSError("the tree could not be removed")

    monkeypatch.setattr(mod, "remove_run_workspace", _raising)
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.workspace_removal.attempted is True
    assert result.workspace_removal.verified is False
    # And it never skipped the evidence construction that follows it.
    assert result.qualification_record is not None
    # Clean up the tree the injected double refused to remove.
    for workspace in real_roots:
        original(workspace)


# -- 27: an unverified removal after sent=1 is INFRASTRUCTURE_CONTAMINATED --


@pytest.mark.parametrize(
    "removal_result",
    [
        {"removed": False, "residual_file_count": 2, "verified": True},
        {"removed": True, "residual_file_count": 2, "verified": True},
        {"removed": True, "residual_file_count": False, "verified": True},
        "not-a-dict",
    ],
)
def test_unverified_removal_after_confirmed_sent_is_unscorable_but_keeps_sent_one(
    harness: Harness, evidence_path: str, monkeypatch: pytest.MonkeyPatch, removal_result
) -> None:
    import qualification.semantic_controller as mod

    original = mod.remove_run_workspace
    kept: list = []

    def _unverified(workspace):
        kept.append(workspace)
        return removal_result

    monkeypatch.setattr(mod, "remove_run_workspace", _unverified)
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    # Sec. 9.1.6: no workspace-removal failure may move the send fact.
    assert result.dispatch_state is SemanticPromptDispatchState.CONFIRMED_SENT
    assert result.semantic_prompts_sent == 1
    assert result.workspace_removal.verified is False
    assert result.workspace_removal.closure_satisfied is False
    assert result.run_validity is RunValidity.INFRASTRUCTURE_CONTAMINATED
    assert result.scoring_eligible is False
    assert result.workspace_removal.status_text == (
        "FAILED:SEMANTIC_WORKSPACE_REMOVAL_UNVERIFIED"
    )
    for workspace in kept:
        original(workspace)


# -- 28: under an indeterminate dispatch, nothing is fabricated ------------


def test_unverified_removal_under_indeterminate_dispatch_stays_indeterminate(
    harness: Harness, evidence_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import qualification.semantic_controller as mod

    original = mod.remove_run_workspace
    kept: list = []

    def _unverified(workspace):
        kept.append(workspace)
        return {"removed": False, "residual_file_count": 1, "verified": True}

    monkeypatch.setattr(mod, "remove_run_workspace", _unverified)
    _indeterminate(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.dispatch_state is SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
    assert result.semantic_prompts_sent is None
    assert result.workspace_removal.semantic_prompts_sent is None
    assert (
        result.workspace_removal.classification_unavailable_reason
        == CLASSIFICATION_UNAVAILABLE_REASON
    )
    assert result.workspace_removal.status_text == (
        "FAILED:SEMANTIC_WORKSPACE_REMOVAL_UNVERIFIED_INDETERMINATE_DISPATCH"
    )
    assert result.run_validity is None
    payload = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
    removal = payload["closure"]["semantic_workspace_removal"]
    assert removal["attempted"] is True
    assert removal["verified"] is False
    for workspace in kept:
        original(workspace)


def test_workspace_removal_status_refuses_a_fabricated_classification_gap() -> None:
    with pytest.raises(ValueError):
        SemanticWorkspaceRemovalStatus(
            attempted=True,
            verified=False,
            facts=None,
            semantic_prompts_sent=None,
            classification_unavailable_reason=None,
        )
    with pytest.raises(ValueError):
        SemanticWorkspaceRemovalStatus(
            attempted=False,
            verified=True,
            facts=None,
            semantic_prompts_sent=1,
            classification_unavailable_reason=None,
        )


# -- 29: evidence is never built or emitted before removal truth is known --


def test_evidence_is_emitted_only_after_workspace_removal_truth_is_known(
    harness: Harness, evidence_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import qualification.semantic_controller as mod

    order: list[str] = []
    original_remove = mod.remove_run_workspace
    original_emit = mod.emit_or_refuse

    def _remove(workspace):
        order.append("remove")
        return original_remove(workspace)

    def _emit(record, **kwargs):
        order.append("emit")
        return original_emit(record, **kwargs)

    monkeypatch.setattr(mod, "remove_run_workspace", _remove)
    monkeypatch.setattr(mod, "emit_or_refuse", _emit)
    _iq1_correct_repair(harness)
    harness.run(IQ1_TASK, evidence_path)
    assert order == ["remove", "emit"]


def test_frozen_closure_order_is_declared_and_executed(harness: Harness) -> None:
    import qualification.semantic_controller as mod

    assert CLOSURE_GATES == (
        SemanticGateName.RUNTIME_TEARDOWN,
        SemanticGateName.BROKER_SHUTDOWN,
        SemanticGateName.GENERATED_CONFIG_CLEANUP,
        SemanticGateName.SEMANTIC_WORKSPACE_REMOVAL,
        SemanticGateName.EVIDENCE_SAFETY,
    )
    source = Path(mod.__file__).read_text(encoding="utf-8")
    teardown = source.index("runtime_teardown = _close_runtime(")
    shutdown = source.index("broker_shutdown = _close_broker(")
    config = source.index("cleanup = _attempt_cleanup(")
    removal = source.index("workspace_removal = _remove_semantic_workspace(")
    safety = source.index("safety_context = build_run_safety_context(")
    emission = source.index("emission = emit_or_refuse(")
    assert teardown < shutdown < config < removal < safety < emission


# ===========================================================================
# D. FULL ARTIFACT SAFETY CONTEXT (Sec. 9.2)
# ===========================================================================


@pytest.fixture()
def minted_workspace():
    workspace = mint_qualification_run_workspace()
    try:
        yield workspace
    finally:
        try:
            remove_run_workspace(workspace)
        except Exception:  # pragma: no cover - best-effort fixture teardown
            pass


def _broker_session() -> BrokerSession:
    return BrokerSession(
        run_id="sem-abc",
        session_id="bsess-1",
        pipe_name="\\\\.\\pipe\\aido-test-pipe",
        capability_id="cap-xyz",
        broker_token="tok-secret",
        reached_ready=True,
    )


# -- 30: a workspace with NO secret context still declares its needle ------


def test_workspace_needle_is_declared_without_a_secret_context(minted_workspace) -> None:
    """The pre-FU2 early return on ``secret_context is None`` could drop a
    REAL, already-minted workspace needle -- WORKSPACE_AUTHORITY runs
    strictly BEFORE SECRET_CONTEXT, so this was reachable, not theoretical."""
    safety = build_run_safety_context(
        secret_context=None,
        broker_session=None,
        run_workspace=minted_workspace,
        route_descriptor=None,
    )
    assert safety.workspace_absolute_path == minted_workspace.experiment_root
    codes = {code for code, _ in safety.forbidden_needles()}
    assert "workspace_absolute_path_present" in codes


# -- 31: a broker with NO secret context still declares its needles --------


def test_broker_needles_are_declared_without_a_secret_context() -> None:
    session = _broker_session()
    safety = build_run_safety_context(
        secret_context=None,
        broker_session=session,
        run_workspace=None,
        route_descriptor=None,
    )
    assert safety.broker_token == session.broker_token
    assert safety.pipe_name == session.pipe_name
    assert safety.capability_id == session.capability_id
    codes = {code for code, _ in safety.forbidden_needles()}
    assert {
        "broker_token_present",
        "broker_pipe_name_present",
        "broker_capability_id_present",
    } <= codes


# -- 32: a secret context declares the endpoint/key ------------------------


def test_secret_context_declares_endpoint_and_key(minted_workspace) -> None:
    from qualification.i2_secret_context import build_secret_context

    secret_context = build_secret_context(
        base_url="https://b300.example.invalid/v1",
        api_key="synthetic-test-key",
        model_id=route_descriptor_for_candidate("A").model_id,
    )
    session = _broker_session()
    safety = build_run_safety_context(
        secret_context=secret_context,
        broker_session=session,
        run_workspace=minted_workspace,
        route_descriptor=route_descriptor_for_candidate("A"),
    )
    codes = {code for code, _ in safety.forbidden_needles()}
    assert {
        "endpoint_host_value_present",
        "api_key_value_present",
        "broker_token_present",
        "broker_pipe_name_present",
        "broker_capability_id_present",
        "workspace_absolute_path_present",
    } <= codes
    # bearer_token is a DERIVED absence for this route's frozen mechanism,
    # never an unproven default.
    assert safety.bearer_token is None


# -- 33: an unexpected credential mechanism REFUSES ------------------------


def test_unexpected_credential_mechanism_refuses_safety_context_construction() -> None:
    descriptor = route_descriptor_for_candidate("A")
    assert descriptor.credential_mechanism == CREDENTIAL_MECHANISM
    # Forge one -- `RouteDescriptor.__post_init__` refuses any other
    # mechanism at construction, so this is the only way to reach the branch,
    # and the point of the contract is that it stays REFUSED rather than
    # silently defaulting `bearer_token` the day a second mechanism is added.
    object.__setattr__(descriptor, "credential_mechanism", "some_future_bearer_flow")
    try:
        with pytest.raises(SemanticSafetyContextError):
            build_run_safety_context(
                secret_context=None,
                broker_session=None,
                run_workspace=None,
                route_descriptor=descriptor,
            )
    finally:
        object.__setattr__(descriptor, "credential_mechanism", CREDENTIAL_MECHANISM)


def test_impostor_route_descriptor_refuses_safety_context_construction() -> None:
    with pytest.raises(SemanticSafetyContextError):
        build_run_safety_context(
            secret_context=None,
            broker_session=None,
            run_workspace=None,
            route_descriptor=SimpleNamespace(
                credential_mechanism=CREDENTIAL_MECHANISM
            ),
        )


# -- 34: none_declared ONLY for a genuine all-absent state -----------------


def test_none_declared_only_for_a_genuinely_all_absent_state(minted_workspace) -> None:
    empty = build_run_safety_context(
        secret_context=None, broker_session=None, run_workspace=None, route_descriptor=None
    )
    assert empty == ArtifactSafetyContext.none_declared()
    assert empty.forbidden_needles() == ()
    for kwargs in (
        {"run_workspace": minted_workspace},
        {"broker_session": _broker_session()},
    ):
        base = {
            "secret_context": None,
            "broker_session": None,
            "run_workspace": None,
            "route_descriptor": None,
        }
        base.update(kwargs)
        safety = build_run_safety_context(**base)
        assert safety != ArtifactSafetyContext.none_declared()
        assert safety.forbidden_needles() != ()


# -- 35: ONE safety context protects every retained shape ------------------


def test_one_safety_context_serves_every_retained_artifact_shape() -> None:
    import qualification.semantic_controller as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    # Exactly one construction per attempt, and every emission uses it.
    assert source.count("safety_context = build_run_safety_context(") == 1
    assert source.count("safety=safety_context") == 2
    assert "emit_attempt_or_refuse(\n            attempt_payload, path=evidence_path, safety=safety_context\n        )" in source
    assert "emit_or_refuse(record, path=evidence_path, safety=safety_context)" in source


def test_unprovable_safety_context_writes_nothing_at_all(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail closed: an artifact is never scrubbed against a context AIDO
    could not prove complete."""
    import qualification.semantic_controller as mod

    evidence_path = str(tmp_path / "evidence.json")
    monkeypatch.setattr(
        mod,
        "build_run_safety_context",
        lambda **kwargs: (_ for _ in ()).throw(
            SemanticSafetyContextError("UNEXPECTED_CREDENTIAL_MECHANISM")
        ),
    )
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    assert not Path(evidence_path).exists()
    assert result.qualification_record is None
    assert result.attempt_record is None
    assert result.evidence_emission is None
    assert (
        result.gate_statuses[SemanticGateName.EVIDENCE_SAFETY.value]
        == "FAILED:SAFETY_CONTEXT_UNPROVABLE"
    )
    # The workspace was still removed -- removal precedes evidence entirely.
    assert result.workspace_removal.verified is True


# ===========================================================================
# E. THE FINAL ASSISTANT REPORT IS OPTIONAL AND UNTRUSTED (Sec. 9.3)
# ===========================================================================


def test_final_report_claims_is_declared_non_gating() -> None:
    assert NON_GATING_POST_PROMPT_GATES == (SemanticGateName.FINAL_REPORT_CLAIMS,)
    assert SemanticGateName.FINAL_REPORT_CLAIMS not in GATING_POST_PROMPT_GATES
    assert set(GATING_POST_PROMPT_GATES) | set(NON_GATING_POST_PROMPT_GATES) == set(
        POST_PROMPT_GATES
    )


# -- 36/37/38: a missing, malformed or foreign report changes NOTHING ------


@pytest.mark.parametrize(
    "configure,expected_availability",
    [
        pytest.param(
            lambda h: setattr(
                h,
                "collect_final_report_claims",
                lambda session: (_ for _ in ()).throw(RuntimeError("no final message")),
            ),
            ReportAvailability.UNAVAILABLE,
            id="collection_raised",
        ),
        pytest.param(
            lambda h: setattr(h, "collect_final_report_claims", lambda session: object()),
            ReportAvailability.UNAVAILABLE,
            id="wrong_type",
        ),
        pytest.param(
            lambda h: setattr(
                h,
                "collect_final_report_claims",
                lambda session: FinalReportClaimsObservation(
                    runtime_session_id="rsess-FOREIGN",
                    claims=ReportClaims(claimed_done=True),
                ),
            ),
            ReportAvailability.MALFORMED,
            id="foreign_session",
        ),
    ],
)
def test_unusable_final_report_never_disturbs_authoritative_truth(
    harness: Harness, evidence_path: str, configure, expected_availability
) -> None:
    """Sec. 9.3.1: before FU2 every one of these routed through the shared
    ``_GateFailure`` path and made an otherwise-successful, fully-verified,
    fully-closed run ATTRIBUTION_UNDETERMINED and unscorable."""
    _iq1_correct_repair(harness)
    configure(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.report_availability is expected_availability
    assert result.failed_gate is None
    assert result.run_validity is RunValidity.VALID
    assert result.run_validity is not RunValidity.ATTRIBUTION_UNDETERMINED
    assert result.scoring_eligible is True
    assert result.autonomous_classification is AutonomousClassification.AUTONOMOUS_PASS
    assert result.diagnostic_subclassification is DiagnosticSubclassification.NONE
    # Layers 1-4 -- the authoritative ones -- are untouched.
    assert result.verification_passed is True
    assert result.expected_changed_paths_satisfied is True
    assert result.head_unchanged is True
    assert result.index_clean is True
    assert result.protected_witness_untouched is True
    assert result.no_unexpected_untracked_or_create_delete_rename is True
    assert result.broker_git_cross_check_agrees is True
    # Report accuracy alone becomes not-evaluable, purely descriptively.
    assert result.report_accuracy_comparisons == ()
    payload = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
    assert payload["report_accuracy"] == {
        "attempted": True,
        "available": False,
        "reason": expected_availability.value,
    }
    assert result.gate_statuses[SemanticGateName.FINAL_REPORT_CLAIMS.value] == (
        f"NOT_EVALUABLE:{expected_availability.value}"
    )


def test_unusable_final_report_still_qualifies_a_correct_candidate(
    git_executable: str, tmp_path: Path
) -> None:
    """The end-to-end consequence: an unusable self-report must not be able
    to cost a candidate its hard-bar verdict."""
    from qualification.hard_bar import evaluate_hard_bar
    from qualification.semantic_sweep import _task_hard_bar_facts

    h = Harness("A", git_executable)
    _iq1_correct_repair(h)
    h.collect_final_report_claims = lambda session: (_ for _ in ()).throw(
        RuntimeError("no final message")
    )
    result = h.run(IQ1_TASK, str(tmp_path / "iq1.json"))
    facts = _task_hard_bar_facts(result)
    assert facts is not None
    assert facts.artifact_scrub_passed is True
    verdict = evaluate_hard_bar({"IQ-1": facts, "IQ-2": None, "IQ-3": None})
    assert "IQ-1" not in verdict.missing_or_ineligible_tasks


# -- 39: a CONTRADICTORY report is a report-accuracy finding only ----------


def test_contradictory_report_is_a_report_accuracy_finding_only(
    harness: Harness, evidence_path: str
) -> None:
    _iq1_correct_repair(harness)
    harness.claimed_changed_paths = frozenset({"money/format.py"})  # never touched
    harness.claimed_ran_tests = True  # never true for this harness
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.report_availability is ReportAvailability.AVAILABLE
    assert result.run_validity is RunValidity.VALID
    assert result.scoring_eligible is True
    assert result.failed_gate is None
    verdicts = {c.claim: c.verdict for c in result.report_accuracy_comparisons}
    assert verdicts["changed_paths"] is ClaimVerdict.CONTRADICTED
    payload = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
    assert payload["report_accuracy"]["available"] is True


# -- 40: a report failure causes NO retry ----------------------------------


def test_bad_final_report_triggers_no_semantic_retry(
    harness: Harness, evidence_path: str
) -> None:
    _iq1_correct_repair(harness)
    calls = _instrumented(harness)
    report_calls = {"n": 0}

    def _failing(session):
        report_calls["n"] += 1
        raise RuntimeError("no final message")

    harness.collect_final_report_claims = _failing
    harness.run(IQ1_TASK, evidence_path)
    assert calls == ["dispatch", "observe"]
    assert report_calls["n"] == 1


# ===========================================================================
# F. DEEP IMMUTABILITY (Sec. 9.4)
# ===========================================================================


# -- 41: gate statuses cannot be mutated after validation ------------------


def test_gate_statuses_cannot_be_mutated(harness: Harness, evidence_path: str) -> None:
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    assert isinstance(result.gate_statuses, MappingProxyType)
    with pytest.raises(TypeError):
        result.gate_statuses[SemanticGateName.RUNTIME_TEARDOWN.value] = "PASSED"  # type: ignore[index]
    with pytest.raises(TypeError):
        del result.gate_statuses[SemanticGateName.RUNTIME_TEARDOWN.value]  # type: ignore[misc]
    with pytest.raises(AttributeError):
        result.gate_statuses.clear()  # type: ignore[attr-defined]


# -- 42/46: COPY BEFORE WRAPPING ------------------------------------------


def test_mutating_a_replace_input_cannot_construct_a_second_result(
    harness: Harness, evidence_path: str
) -> None:
    """This test previously proved ``freeze_mapping`` copies a caller-held
    ``gate_statuses`` dict before wrapping it, via
    ``replace(result, gate_statuses=caller_dict)``. That COPY-BEFORE-
    WRAPPING property is still true and is still directly, thoroughly
    exercised -- independent of ``SemanticTaskAttemptResult`` entirely -- by
    :func:`test_freeze_mapping_copies_before_wrapping` immediately below.

    5F3B-Q1-PRE1-FINAL-CLOSURE: ``SemanticTaskAttemptResult`` is now a
    one-shot, valid-by-construction authority object -- its issuance backs
    AT MOST ONE construction, ever. So `replace(result, gate_statuses=...)`,
    even with a byte-for-byte COPY of ``result``'s own genuine
    ``gate_statuses``, always constructs a SECOND instance now, and must
    always fail: the genuine construction below already consumed the only
    issuance this result's bundle will ever have.
    """
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    caller_dict = dict(result.gate_statuses)
    with pytest.raises(ValueError):
        replace(result, gate_statuses=caller_dict)


def test_freeze_mapping_copies_before_wrapping() -> None:
    backing = {"a": ["x"], "b": {"c": {"d"}}}
    frozen = freeze_mapping(backing)
    backing["a"].append("y")
    backing["new"] = "value"
    assert frozen["a"] == ("x",)
    assert "new" not in frozen
    assert isinstance(frozen["b"], MappingProxyType)
    assert frozen["b"]["c"] == frozenset({"d"})
    with pytest.raises(TypeError):
        frozen["b"]["c"] = "z"  # type: ignore[index]


# -- 43: the record projections are recursively immutable ------------------


def test_qualification_record_projection_is_recursively_immutable(
    harness: Harness, evidence_path: str
) -> None:
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    projection = result.qualification_record
    assert isinstance(projection, MappingProxyType)
    with pytest.raises(TypeError):
        projection["refused"] = True  # type: ignore[index]
    scrub = projection["scrub"]
    assert isinstance(scrub, MappingProxyType)
    with pytest.raises(TypeError):
        scrub["clean"] = False  # type: ignore[index]
    # The nested findings list is a tuple, not a mutable list.
    assert isinstance(scrub["findings"], tuple)
    with pytest.raises(AttributeError):
        scrub["findings"].append("forged")  # type: ignore[attr-defined]


def test_attempt_record_projection_is_recursively_immutable(
    harness: Harness, evidence_path: str
) -> None:
    _indeterminate(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    projection = result.attempt_record
    assert isinstance(projection, MappingProxyType)
    with pytest.raises(TypeError):
        projection["refused"] = True  # type: ignore[index]
    assert isinstance(projection["scrub"]["findings"], tuple)


def test_evidence_emission_is_a_frozen_typed_projection(
    harness: Harness, evidence_path: str
) -> None:
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    emission = result.evidence_emission
    assert type(emission) is EvidenceEmission
    with pytest.raises(Exception):
        emission.refused = True  # type: ignore[misc]
    assert isinstance(emission.findings, tuple)
    # An internally contradictory emission cannot even be constructed.
    with pytest.raises(ValueError):
        EvidenceEmission(
            emitted=True,
            refused=True,
            path="x",
            scrub_checked=True,
            clean=True,
            findings=(),
        )


def test_result_cannot_carry_an_emission_that_disagrees_with_its_projection(
    harness: Harness, evidence_path: str
) -> None:
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    forged = replace(result.evidence_emission, refused=True, clean=False)
    with pytest.raises(ValueError):
        replace(result, evidence_emission=forged)
    with pytest.raises(ValueError):
        replace(result, evidence_emission=None)


# -- 44/45: the sweep's task results cannot drift from the hard bar --------


def test_sweep_task_results_cannot_be_replaced_added_or_removed(
    git_executable: str, tmp_path: Path
) -> None:
    from test_semantic_sweep import _run_sweep

    result, _ = _run_sweep("A", git_executable, tmp_path, correct=True)
    assert isinstance(result.task_results, MappingProxyType)
    victim = result.task_results["IQ-1"]
    with pytest.raises(TypeError):
        result.task_results["IQ-2"] = victim  # type: ignore[index]
    with pytest.raises(TypeError):
        del result.task_results["IQ-1"]  # type: ignore[misc]
    with pytest.raises(TypeError):
        result.task_results["IQ-4T"] = victim  # type: ignore[index]
    # And the hard-bar verdict cannot drift from what a reader can inspect.
    assert result.hard_bar_result.qualification_state is (
        QualificationState.AUTONOMOUS_QUALIFIED
    )
    assert set(result.task_results) == {"IQ-1", "IQ-2", "IQ-3"}


def test_sweep_result_copies_its_task_results_before_wrapping(
    git_executable: str, tmp_path: Path
) -> None:
    from qualification.semantic_sweep import PrimarySweepResult
    from test_semantic_sweep import _run_sweep

    result, _ = _run_sweep("A", git_executable, tmp_path, correct=True)
    caller_dict = dict(result.task_results)
    rebuilt = PrimarySweepResult(
        candidate=result.candidate,
        model_id=result.model_id,
        task_results=caller_dict,
        confirmed_semantic_prompts_sent=result.confirmed_semantic_prompts_sent,
        semantic_dispatch_attempts=result.semantic_dispatch_attempts,
        indeterminate_dispatch_task_ids=result.indeterminate_dispatch_task_ids,
        not_attempted_task_ids=result.not_attempted_task_ids,
        hard_bar_result=result.hard_bar_result,
    )
    caller_dict.clear()
    caller_dict["FORGED"] = None
    assert set(rebuilt.task_results) == {"IQ-1", "IQ-2", "IQ-3"}
    assert "FORGED" not in rebuilt.task_results


def test_sweep_result_refuses_a_cross_task_substitution(
    git_executable: str, tmp_path: Path
) -> None:
    from qualification.semantic_sweep import PrimarySweepResult, SweepInputError
    from test_semantic_sweep import _run_sweep

    result, _ = _run_sweep("A", git_executable, tmp_path, correct=True)
    forged = dict(result.task_results)
    forged["IQ-2"] = forged["IQ-1"]
    with pytest.raises(SweepInputError):
        PrimarySweepResult(
            candidate=result.candidate,
            model_id=result.model_id,
            task_results=forged,
            confirmed_semantic_prompts_sent=result.confirmed_semantic_prompts_sent,
            semantic_dispatch_attempts=result.semantic_dispatch_attempts,
            indeterminate_dispatch_task_ids=result.indeterminate_dispatch_task_ids,
            not_attempted_task_ids=result.not_attempted_task_ids,
            hard_bar_result=result.hard_bar_result,
        )


# ===========================================================================
# G. CANDIDATE A/B FAIRNESS AND POLICY SYMMETRY
# ===========================================================================


# -- 47: byte/policy-identical dispatch semantics for the same task --------


def test_candidate_a_and_b_dispatch_semantics_are_identical(
    git_executable: str, tmp_path: Path
) -> None:
    observed: dict[str, dict[str, object]] = {}
    for candidate in ("A", "B"):
        h = Harness(candidate, git_executable)
        _iq1_correct_repair(h)
        calls = _instrumented(h)
        result = h.run(IQ1_TASK, str(tmp_path / f"{candidate}.json"))
        observed[candidate] = {
            "calls": tuple(calls),
            "gates": tuple(result.gate_statuses.keys()),
            "statuses": tuple(result.gate_statuses.values()),
            "dispatch_state": result.dispatch_state,
            "evidence_code": result.dispatch_evidence_code,
            "dispatch_attempted": result.semantic_dispatch_attempted,
            "turn_outcome": result.turn_outcome,
            "prompts_sent": result.semantic_prompts_sent,
            "report_availability": result.report_availability,
            "removal": result.workspace_removal.status_text,
            "prompt": IQ1_TASK.prompt,
            "classification": result.autonomous_classification,
        }
    assert observed["A"] == observed["B"]


@pytest.mark.parametrize(
    "configure",
    [
        pytest.param(_indeterminate, id="indeterminate"),
        pytest.param(
            lambda h: setattr(
                h, "dispatch_state", SemanticPromptDispatchState.CONFIRMED_NOT_SENT
            ),
            id="confirmed_not_sent",
        ),
        pytest.param(
            lambda h: setattr(h, "turn_outcome", SemanticTurnOutcome.OBSERVATION_FAILED),
            id="observation_failed",
        ),
    ],
)
def test_candidate_a_and_b_failure_semantics_are_identical(
    git_executable: str, tmp_path: Path, configure
) -> None:
    observed: dict[str, tuple] = {}
    for candidate in ("A", "B"):
        h = Harness(candidate, git_executable)
        _iq1_correct_repair(h)
        configure(h)
        result = h.run(IQ1_TASK, str(tmp_path / f"{candidate}.json"))
        observed[candidate] = (
            result.dispatch_state,
            result.dispatch_evidence_code,
            result.semantic_prompts_sent,
            result.turn_outcome,
            result.failed_gate,
            result.failure_code,
            result.run_validity,
            result.scoring_eligible,
            result.qualification_record is None,
            result.attempt_record is None,
            tuple(result.gate_statuses.items()),
        )
    assert observed["A"] == observed["B"]


# -- 48: no candidate-specific branch outside the frozen pairing -----------


def test_no_candidate_conditional_branch_in_the_semantic_modules() -> None:
    import qualification.semantic_attempt as attempt_mod
    import qualification.semantic_controller as controller_mod
    import qualification.semantic_session as session_mod
    import qualification.semantic_sweep as sweep_mod

    for module in (controller_mod, sweep_mod, session_mod, attempt_mod):
        source = Path(module.__file__).read_text(encoding="utf-8")
        for forbidden in (
            'candidate == "A"',
            'candidate == "B"',
            "candidate is 'A'",
            'candidate != "A"',
            "qwen3-coder-next",
            "minimax",
        ):
            assert forbidden not in source, (module.__name__, forbidden)
        # The ONLY candidate -> model authority is the frozen mapping.
        if "CANDIDATE_MODEL_IDS" in source:
            assert "CANDIDATE_MODEL_IDS[candidate]" in source or "in CANDIDATE_MODEL_IDS" in source


def test_preserved_semantic_authority_constants() -> None:
    """Nothing FU2 touched may weaken the already-accepted authority set."""
    import qualification.semantic_controller as mod
    from qualification.records import TOKEN_POLICY
    from qualification.semantic_sweep import MAX_SEMANTIC_PROMPTS_PER_CANDIDATE

    assert mod.MAX_SEMANTIC_PROMPTS_PER_ATTEMPT == 1
    assert MAX_SEMANTIC_PROMPTS_PER_CANDIDATE == 3
    assert TOKEN_POLICY["aido_requested_max_output_tokens"] is None
    source = Path(mod.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "continue your work",
        "operator_continuation=True",
        "retry_prompt",
        "automatic_semantic_retry=True",
        # Reasoning-bearing content has no CODE-level seam here: no field,
        # no key, no attribute access. (The word appears only in prose that
        # explains a reused rationale, which is why this is a token check
        # rather than a substring check.)
        '"reasoning"',
        "reasoning=",
        ".reasoning",
        "chain_of_thought",
        "thinking=",
    ):
        assert forbidden not in source
    # And structurally: no field on any FU2-touched value object could hold
    # it even if a live adapter tried.
    import dataclasses

    import qualification.semantic_session as session_mod

    for cls in (
        mod.SemanticTaskAttemptResult,
        mod.SemanticWorkspaceRemovalStatus,
        mod.EvidenceEmission,
        session_mod.SemanticPromptDispatchObservation,
        session_mod.SemanticTurnObservation,
        session_mod.SemanticTurnRequest,
    ):
        names = {f.name for f in dataclasses.fields(cls)}
        for forbidden in ("reasoning", "chain_of_thought", "thinking"):
            assert not any(forbidden in name for name in names), (cls, forbidden)
        # And no free-text prompt seam a caller could substitute through
        # (`semantic_prompts_sent` is a COUNT, not prompt content).
        assert names.isdisjoint({"prompt", "prompt_text", "message"}), cls
    # The pre-prompt compatibility prefix is unchanged and still precedes
    # every post-prompt gate.
    assert PRE_PROMPT_GATES[-1] is SemanticGateName.ROUTE_CHECK
    assert POST_PROMPT_GATES[0] is SemanticGateName.SEMANTIC_PROMPT_DISPATCH
    assert POST_PROMPT_GATES[1] is SemanticGateName.TURN_COMPLETION


def test_a_report_that_was_never_collected_is_not_an_unavailable_report(
    harness: Harness, evidence_path: str
) -> None:
    """"AIDO never asked" is a different fact from "AIDO asked and got
    nothing usable", and a pre-prompt refusal must not be recorded as the
    second."""
    harness.dispatch_state = SemanticPromptDispatchState.CONFIRMED_NOT_SENT
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.report_availability is None
    assert result.gate_statuses[SemanticGateName.FINAL_REPORT_CLAIMS.value] == "NOT_REACHED"
    payload = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
    assert payload["report_accuracy"] == {"attempted": False}


def test_no_bounded_failure_code_exists_for_the_final_report_gate() -> None:
    """The seam through which report collection could be re-wired into
    ``failed_gate`` -> ``attribute_protocol_anomaly`` ->
    ATTRIBUTION_UNDETERMINED is deliberately gone, not merely unused."""
    assert not any(
        "FINAL_REPORT" in member.name for member in SemanticFailureCode
    ), [m.name for m in SemanticFailureCode if "FINAL_REPORT" in m.name]


def test_report_comparisons_must_be_an_immutable_tuple_of_claim_comparisons(
    harness: Harness, evidence_path: str
) -> None:
    """Adversarial: mutable-alias injection through the one post-prompt
    field that carries a sequence."""
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    assert isinstance(result.report_accuracy_comparisons, tuple)
    with pytest.raises(ValueError):
        replace(result, report_accuracy_comparisons=list(result.report_accuracy_comparisons))
    with pytest.raises(ValueError):
        replace(result, report_accuracy_comparisons=(SimpleNamespace(claim="x"),))
    # And comparisons cannot coexist with a not-evaluable report.
    with pytest.raises(ValueError):
        replace(result, report_availability=ReportAvailability.MALFORMED)


def test_result_refuses_a_turn_outcome_without_a_confirmed_sent_dispatch(
    harness: Harness, evidence_path: str
) -> None:
    _indeterminate(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.turn_outcome is None
    with pytest.raises(ValueError):
        replace(result, turn_outcome=SemanticTurnOutcome.SETTLED)
    with pytest.raises(ValueError):
        replace(result, agent_end_observed=True)
    # Nor may an indeterminate result be silently upgraded into a scored one
    # or given a primary record.
    with pytest.raises(ValueError):
        replace(result, dispatch_state=SemanticPromptDispatchState.CONFIRMED_SENT)
    with pytest.raises(ValueError):
        replace(result, scoring_eligible=True)


def test_result_refuses_a_dispatch_state_that_its_evidence_code_denies(
    harness: Harness, evidence_path: str
) -> None:
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.dispatch_state is SemanticPromptDispatchState.CONFIRMED_SENT
    with pytest.raises(ValueError):
        replace(
            result,
            dispatch_evidence_code=SemanticDispatchEvidenceCode.ADAPTER_RAISED,
        )
    with pytest.raises(ValueError):
        replace(result, semantic_dispatch_attempted=False)
