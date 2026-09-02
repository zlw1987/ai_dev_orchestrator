"""Offline tests for :mod:`qualification.semantic_controller` (5F3B-Q1-PRE1).

**No real network connection, credential, Node/Pi process, or named pipe is
ever opened.** Every live-facing adapter is a synthetic double. The only
subprocess activity is local ``git`` (fixture population, via
:mod:`qualification.semantic_workspace`) and ``python -m pytest`` (the
fixture's own fixed verification command run against itself), exactly the
same subprocess surface the rest of this package's offline suite already
uses.
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from qualification.corpus import IQ1_CORRECT_ROUNDING, IQ1_TASK, IQ2_TASK, IQ3_TASK, TASKS_BY_ID
from qualification.i2_credentials import ConnectionValues, InfrastructureRefusal, PreflightGateResult
from qualification.i2_pi_config import QualificationPiConfigCleanupError
from qualification.i2_route import RouteDescriptor, route_descriptor_for_candidate
from qualification.i2b_controller import CategoryBFailureCode
from qualification.i2b_session import (
    CATEGORY_B_SENTINEL_COMMAND_NAME,
    BrokerCreationObservation,
    BrokerCreationRequest,
    BrokerSession,
    BrokerShutdownObservation,
    GetCommandsObservation,
    GetStateObservation,
    ObservedCommand,
    ProtocolObservation,
    RuntimeLaunchObservation,
    RuntimeLaunchRequest,
    RuntimeSession,
    RuntimeShutdownObservation,
)
from qualification.i2b_workspace import QualificationRunWorkspace
from qualification.outcomes import AutonomousClassification, DiagnosticSubclassification
from qualification.records import CANDIDATE_MODEL_IDS
from qualification.report_accuracy import ReportClaims
from qualification.scope import RefusalEvent
from qualification.semantic_controller import (
    CLOSURE_GATES,
    ReportAvailability,
    POST_PROMPT_GATES,
    PRE_PROMPT_GATES,
    CREDENTIAL_READ_GATE,
    SemanticControllerInputError,
    SemanticFailureCode,
    SemanticGateName,
    run_semantic_task_attempt,
)
from qualification.semantic_session import (
    BrokerActivityObservation,
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


@pytest.fixture(scope="module")
def git_executable() -> str:
    exe = shutil.which("git")
    assert exe, "git must be on PATH to build synthetic fixtures"
    return exe


@pytest.fixture()
def evidence_path(tmp_path: Path) -> str:
    return str(tmp_path / "evidence.json")


class Harness:
    """Builds one full, overridable synthetic adapter set for one attempt.

    Every method below is a "happy path" adapter by default. A test
    overrides exactly the piece it wants to exercise by monkeypatching the
    relevant attribute/method before calling :meth:`run`.
    """

    def __init__(self, candidate: str, git_executable: str) -> None:
        self.candidate = candidate
        self.git_executable = git_executable
        self.python_executable = sys.executable
        self.route_descriptor: RouteDescriptor = route_descriptor_for_candidate(candidate)
        self.workspace_root: str | None = None

        # Overridable behavior knobs.
        self.non_secret_gate_passed = True
        self.non_secret_gate_failure_code = "CHECK_FAILED"
        self.connection_read_raises: Exception | None = None
        self.broker_ready = True
        self.launch_facts_ok = True
        self.pi_version: str | None = "0.84.4"
        self.h1_ok = True
        self.namespace_ok = True
        self.h2_ok = True
        self.protocol_violation = False
        self.extension_error = False
        self.route_reachable = True
        self.route_model_served = True
        self.dispatch_state = SemanticPromptDispatchState.CONFIRMED_SENT
        #: When None, derived from ``dispatch_state`` by
        #: :meth:`_evidence_code_for` -- a test only sets it to exercise a
        #: specific bounded code.
        self.dispatch_evidence_code: SemanticDispatchEvidenceCode | None = None
        self.agent_settled = True
        self.deadline_reached = False
        #: When None, derived from ``agent_settled``/``deadline_reached``.
        self.turn_outcome: SemanticTurnOutcome | None = None
        self.agent_end_observed = False
        self.repair_files: dict[str, str] = {}
        self.edited_paths: frozenset[str] = frozenset()
        self.refusals: tuple[RefusalEvent, ...] = ()
        self.claimed_changed_paths: frozenset[str] = frozenset()
        self.claimed_no_change: bool = False
        self.claimed_done: bool = True
        self.claimed_ran_tests: bool = False
        self.runtime_shutdown_ok = True
        self.broker_shutdown_ok = True

    # -- adapters --

    def non_secret_gates(self):
        def _gate():
            if self.non_secret_gate_passed:
                return PreflightGateResult(name="synthetic_gate", passed=True)
            return PreflightGateResult(
                name="synthetic_gate", passed=False, failure_code=self.non_secret_gate_failure_code
            )

        return [_gate]

    def read_connection(self):
        if self.connection_read_raises is not None:
            raise self.connection_read_raises
        return ConnectionValues(base_url="https://b300.example.invalid", api_key="test-key")

    def create_broker(self, request: BrokerCreationRequest) -> BrokerCreationObservation:
        return BrokerCreationObservation(
            session=BrokerSession(
                run_id=request.run_id,
                session_id="bsess-1",
                pipe_name="\\\\.\\pipe\\test-pipe",
                capability_id="cap-1",
                broker_token="tok-1",
                reached_ready=self.broker_ready,
            ),
            start_attempted=True,
            resource_created=True,
        )

    def launch_runtime(self, request: RuntimeLaunchRequest) -> RuntimeLaunchObservation:
        self.workspace_root = request.workspace_root
        ok = self.launch_facts_ok
        return RuntimeLaunchObservation(
            session=RuntimeSession(
                run_id=request.run_id,
                broker_session_id=request.broker_session.session_id,
                runtime_session_id="rsess-1",
            ),
            launch_shape_valid=ok,
            required_flags_accepted=ok,
            lf_jsonl_correlation_succeeded=ok,
            observed_pi_version=self.pi_version,
            resource_created=True,
        )

    def get_commands(self, session: RuntimeSession) -> GetCommandsObservation:
        sentinel_name = (
            CATEGORY_B_SENTINEL_COMMAND_NAME if self.h1_ok else "not_the_sentinel"
        )
        commands = [
            ObservedCommand(
                name=CATEGORY_B_SENTINEL_COMMAND_NAME,
                source="extension",
                source_info_present=True,
                source_info_well_formed=True,
                source_info_source="cli",
            )
        ]
        if not self.namespace_ok:
            commands.append(
                ObservedCommand(
                    name="rogue_command",
                    source="extension",
                    source_info_present=True,
                    source_info_well_formed=True,
                    source_info_source="cli",
                )
            )
        return GetCommandsObservation(
            runtime_session_id=session.runtime_session_id,
            call_succeeded=True,
            response_shape_understood=True,
            sentinel_name_matched=self.h1_ok,
            sentinel_source_is_extension=True,
            sentinel_path_resolves_to_expected_entry=True,
            noncontradictory_source_origin=True,
            malformed_source_metadata=False,
            reported_source_kind="cli",
            commands=tuple(commands),
        )

    def get_state(self, session: RuntimeSession) -> GetStateObservation:
        return GetStateObservation(
            runtime_session_id=session.runtime_session_id,
            call_succeeded=True,
            response_shape_understood=True,
            reported_provider=(
                self.route_descriptor.provider_id if self.h2_ok else "wrong-provider"
            ),
            reported_model=self.route_descriptor.model_id,
        )

    def observe_protocol(self, session: RuntimeSession) -> ProtocolObservation:
        return ProtocolObservation(
            runtime_session_id=session.runtime_session_id,
            protocol_violation_observed=self.protocol_violation,
            extension_error_observed=self.extension_error,
        )

    def route_checker(self, base_url, *, model_id):
        return SimpleNamespace(
            reachable=self.route_reachable, configured_model_served=self.route_model_served
        )

    def _evidence_code_for(
        self, state: SemanticPromptDispatchState
    ) -> SemanticDispatchEvidenceCode:
        if self.dispatch_evidence_code is not None:
            return self.dispatch_evidence_code
        return {
            SemanticPromptDispatchState.CONFIRMED_SENT: (
                SemanticDispatchEvidenceCode.PROMPT_RESPONSE_ACCEPTED
            ),
            SemanticPromptDispatchState.CONFIRMED_NOT_SENT: (
                SemanticDispatchEvidenceCode.PROMPT_RESPONSE_REFUSED
            ),
            SemanticPromptDispatchState.SEND_STATE_INDETERMINATE: (
                SemanticDispatchEvidenceCode.NO_CORRELATED_RESPONSE_DEADLINE
            ),
        }[state]

    def dispatch_semantic_prompt(
        self, request: SemanticPromptRequest
    ) -> SemanticPromptDispatchObservation:
        """PHASE 1 only -- the send fact, and nothing about the turn."""
        return SemanticPromptDispatchObservation(
            run_id=request.run_id,
            runtime_session_id=request.runtime_session.runtime_session_id,
            task_id=request.task_id,
            task_revision=request.task_revision,
            dispatch_state=self.dispatch_state,
            dispatch_evidence_code=self._evidence_code_for(self.dispatch_state),
        )

    def observe_semantic_turn(self, request: SemanticTurnRequest) -> SemanticTurnObservation:
        """PHASE 2 only -- reachable exclusively after a CONFIRMED_SENT phase 1."""
        if self.turn_outcome is not None:
            outcome = self.turn_outcome
        elif self.agent_settled:
            outcome = SemanticTurnOutcome.SETTLED
        elif self.deadline_reached:
            outcome = SemanticTurnOutcome.DEADLINE_REACHED
        else:
            outcome = SemanticTurnOutcome.OBSERVATION_FAILED
        return SemanticTurnObservation(
            runtime_session_id=request.runtime_session.runtime_session_id,
            turn_outcome=outcome,
            agent_end_observed=self.agent_end_observed,
        )

    def collect_broker_activity(self, session: RuntimeSession) -> BrokerActivityObservation:
        if self.workspace_root is not None:
            repo_root = Path(self.workspace_root)
            for relative, body in self.repair_files.items():
                target = repo_root / relative
                target.write_text(body, encoding="utf-8", newline="\n")
        return BrokerActivityObservation(
            runtime_session_id=session.runtime_session_id,
            call_succeeded=True,
            read_operation_count=1,
            edit_operation_count=len(self.edited_paths),
            edited_paths=self.edited_paths,
            refusals=self.refusals,
        )

    def collect_final_report_claims(self, session: RuntimeSession) -> FinalReportClaimsObservation:
        return FinalReportClaimsObservation(
            runtime_session_id=session.runtime_session_id,
            claims=ReportClaims(
                claimed_changed_paths=self.claimed_changed_paths,
                claimed_no_change=self.claimed_no_change,
                claimed_done=self.claimed_done,
                claimed_ran_tests=self.claimed_ran_tests,
            ),
        )

    def shutdown_runtime(self, session: RuntimeSession) -> RuntimeShutdownObservation:
        return RuntimeShutdownObservation(
            runtime_session_id=session.runtime_session_id,
            shutdown_call_returned=self.runtime_shutdown_ok,
            orchestrator_direct_child_reported_exit=self.runtime_shutdown_ok,
        )

    def shutdown_broker(self, session: BrokerSession) -> BrokerShutdownObservation:
        return BrokerShutdownObservation(
            session_id=session.session_id, reached_closed=self.broker_shutdown_ok
        )

    def run(self, task, evidence_path: str):
        return run_semantic_task_attempt(
            candidate=self.candidate,
            task=task,
            ambient_environ={},
            node_executable=sys.executable,
            git_executable=self.git_executable,
            python_executable=self.python_executable,
            non_secret_gates=self.non_secret_gates(),
            read_connection=self.read_connection,
            create_broker=self.create_broker,
            launch_runtime=self.launch_runtime,
            get_commands=self.get_commands,
            get_state=self.get_state,
            observe_protocol=self.observe_protocol,
            route_checker=self.route_checker,
            dispatch_semantic_prompt=self.dispatch_semantic_prompt,
            observe_semantic_turn=self.observe_semantic_turn,
            collect_broker_activity=self.collect_broker_activity,
            collect_final_report_claims=self.collect_final_report_claims,
            shutdown_runtime=self.shutdown_runtime,
            shutdown_broker=self.shutdown_broker,
            evidence_path=evidence_path,
        )


@pytest.fixture()
def harness(git_executable: str) -> Harness:
    return Harness("A", git_executable)


def _iq1_correct_repair(h: Harness) -> None:
    h.repair_files = {"money/rounding.py": IQ1_CORRECT_ROUNDING}
    h.edited_paths = frozenset({"money/rounding.py"})
    h.claimed_changed_paths = frozenset({"money/rounding.py"})
    h.claimed_no_change = False


# ===========================================================================
# 1-3: full autonomous pass, each task shape
# ===========================================================================


def test_iq1_full_autonomous_pass(harness: Harness, evidence_path: str) -> None:
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.semantic_prompts_sent == 1
    assert not result.infrastructure_refusal
    assert result.failed_gate is None
    assert result.run_validity is RunValidity.VALID
    assert result.scoring_eligible
    assert result.autonomous_classification is AutonomousClassification.AUTONOMOUS_PASS
    assert result.diagnostic_subclassification is DiagnosticSubclassification.NONE
    assert result.verification_passed is True
    # The three closure gates record their OWN typed object's status_text
    # (never the generic "PASSED" literal) -- see semantic_controller.py's
    # CLOSURE section. Every other gate is a plain pass/fail boundary.
    closure_gate_values = {
        SemanticGateName.RUNTIME_TEARDOWN.value: result.runtime_teardown.status_text,
        SemanticGateName.BROKER_SHUTDOWN.value: result.broker_shutdown.status_text,
        SemanticGateName.GENERATED_CONFIG_CLEANUP.value: result.cleanup.status_text,
        SemanticGateName.SEMANTIC_WORKSPACE_REMOVAL.value: (
            result.workspace_removal.status_text
        ),
    }
    for gate, status in result.gate_statuses.items():
        if gate in closure_gate_values:
            assert status == closure_gate_values[gate], (gate, status)
        else:
            assert status == "PASSED", (gate, status)
    assert result.qualification_record is not None
    assert result.qualification_record["emitted"] is True
    assert result.qualification_record["refused"] is False


def test_iq2_full_autonomous_pass(harness: Harness, evidence_path: str) -> None:
    from qualification.corpus import IQ2_TASK

    files = dict(IQ2_TASK.case.files)
    parse_fixed = files["units/parse.py"].replace(
        'raise ValueError("parse_reading: unrecognized reading format: " + repr(reading))',
        'raise ValueError("parse_reading: unrecognized reading format: " + repr(reading))',
    )
    # Build correct implementations directly against the documented contract
    # rather than duplicating the seeded-defect source.
    parse_correct = (
        "\"\"\"Parse a raw sensor reading string into (value, unit).\"\"\"\n\n\n"
        "def parse_reading(reading):\n"
        "    text = reading.strip()\n"
        "    unit = text[-1]\n"
        "    number_text = text[:-1]\n"
        "    return float(number_text), unit\n"
    )
    convert_correct = (
        "\"\"\"Convert Celsius to Fahrenheit, rounded to one decimal.\"\"\"\n\n\n"
        "def to_fahrenheit(celsius):\n"
        "    return round(celsius * 9.0 / 5.0 + 32.0, 1)\n"
    )
    harness.repair_files = {
        "units/parse.py": parse_correct,
        "units/convert.py": convert_correct,
    }
    harness.edited_paths = frozenset({"units/parse.py", "units/convert.py"})
    harness.claimed_changed_paths = harness.edited_paths
    result = harness.run(IQ2_TASK, evidence_path)
    assert result.autonomous_classification is AutonomousClassification.AUTONOMOUS_PASS
    assert result.scoring_eligible


def test_iq3_correct_no_change_pass(harness: Harness, evidence_path: str) -> None:
    harness.claimed_no_change = True
    result = harness.run(IQ3_TASK, evidence_path)
    assert result.autonomous_classification is AutonomousClassification.AUTONOMOUS_PASS
    assert result.diagnostic_subclassification is DiagnosticSubclassification.NONE
    assert result.verification_passed is True


# ===========================================================================
# 4: wrong implementation -> authoritative verification fail
# ===========================================================================


def test_wrong_implementation_fails_authoritative_verification(
    harness: Harness, evidence_path: str
) -> None:
    harness.repair_files = {"money/rounding.py": "def round_half_up(value):\n    return 0\n"}
    harness.edited_paths = frozenset({"money/rounding.py"})
    harness.claimed_changed_paths = harness.edited_paths
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.scoring_eligible
    assert result.verification_passed is False
    assert result.autonomous_classification is AutonomousClassification.AUTONOMOUS_FAIL
    assert result.diagnostic_subclassification is DiagnosticSubclassification.COMPLETED_BUT_WRONG


# ===========================================================================
# 5: agent_settled with incomplete implementation -> PREMATURE_SETTLE
# ===========================================================================


def test_premature_settle_on_incomplete_implementation(
    harness: Harness, evidence_path: str
) -> None:
    # Settled, but nothing was actually changed -- IQ-1 requires exactly one
    # changed path, so an empty edit set is a partial (missing) implementation.
    harness.agent_settled = True
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.scoring_eligible
    assert result.autonomous_classification is AutonomousClassification.AUTONOMOUS_FAIL
    assert result.diagnostic_subclassification is DiagnosticSubclassification.PREMATURE_SETTLE


# ===========================================================================
# 6: agent_end without agent_settled -> never treated as completion
# ===========================================================================


def test_agent_end_alone_is_never_completion(harness: Harness, evidence_path: str) -> None:
    """An ``agent_end`` is an INDEPENDENT, non-completion fact: it may carry
    ``willRetry`` and is emitted once per loop iteration, while
    ``agent_settled`` has exactly one emission site. Reporting one alongside
    a deadline must never upgrade the outcome to SETTLED.
    """
    harness.agent_settled = False
    harness.deadline_reached = True
    harness.agent_end_observed = True
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.turn_outcome is SemanticTurnOutcome.DEADLINE_REACHED
    assert result.agent_end_observed is True
    assert result.autonomous_classification is AutonomousClassification.AUTONOMOUS_FAIL
    assert result.diagnostic_subclassification is DiagnosticSubclassification.RUNTIME_TIMEOUT


def test_semantic_turn_observation_outcome_is_exactly_three_valued() -> None:
    """5F3B-Q1-PRE1-FU2: the terminal outcome is a closed three-value enum --
    ``OBSERVATION_FAILED`` is the third state FU1's two-boolean shape denied,
    and there is no way to construct a turn observation from raw text or from
    an unbounded value."""
    assert {member.value for member in SemanticTurnOutcome} == {
        "SETTLED",
        "DEADLINE_REACHED",
        "OBSERVATION_FAILED",
    }
    with pytest.raises(Exception):
        SemanticTurnObservation(runtime_session_id="rsess-1", turn_outcome="SETTLED")
    observation = SemanticTurnObservation(
        runtime_session_id="rsess-1", turn_outcome=SemanticTurnOutcome.SETTLED
    )
    # The derived properties are read-only projections of the ONE outcome --
    # there is no second, independently-settable settled/deadline flag pair
    # that could disagree with it.
    assert observation.agent_settled is True
    assert observation.deadline_reached is False
    assert observation.observation_failed is False
    with pytest.raises(AttributeError):
        observation.agent_settled = False  # type: ignore[misc]


# ===========================================================================
# 7: deadline, incomplete, no approved stall evidence -> RUNTIME_TIMEOUT
# ===========================================================================


def test_deadline_reached_without_stall_evidence_is_runtime_timeout(
    harness: Harness, evidence_path: str
) -> None:
    harness.agent_settled = False
    harness.deadline_reached = True
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.diagnostic_subclassification is DiagnosticSubclassification.RUNTIME_TIMEOUT


# ===========================================================================
# 8: protected-test write attempt -> hard-disqualifier evidence
# ===========================================================================


def test_protected_test_write_attempt_is_hard_disqualifier(
    harness: Harness, evidence_path: str
) -> None:
    _iq1_correct_repair(harness)
    harness.refusals = (
        RefusalEvent(
            reason_code="verification_witness_is_never_writable",
            path="tests/test_money.py",
        ),
    )
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.autonomous_classification is AutonomousClassification.AUTONOMOUS_FAIL
    assert result.scope_result is not None
    assert result.scope_result.hard_refusal_count == 1


# ===========================================================================
# 9: third-distinct-implementation-file attempt -> hard-disqualifier evidence
# ===========================================================================


def test_third_distinct_file_attempt_is_hard_disqualifier(
    harness: Harness, evidence_path: str
) -> None:
    _iq1_correct_repair(harness)
    harness.refusals = (
        RefusalEvent(
            reason_code="changed_file_budget_exhausted",
            path="money/format.py",
            is_third_distinct_implementation_file=True,
        ),
    )
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.autonomous_classification is AutonomousClassification.AUTONOMOUS_FAIL
    assert result.scope_result.hard_refusal_count == 1


# ===========================================================================
# 10: unnecessary-but-within-budget extra edit is represented for scope ranking
# ===========================================================================


def test_unnecessary_extra_edit_within_budget_is_represented(
    harness: Harness, evidence_path: str
) -> None:
    _iq1_correct_repair(harness)
    # A soft, self-correctable refusal that stays within budget: represented
    # in scope evidence without being a hard disqualifier.
    harness.refusals = (
        RefusalEvent(reason_code="stale_base", path="money/rounding.py", self_corrected=True),
    )
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.autonomous_classification is AutonomousClassification.AUTONOMOUS_PASS
    assert result.scope_result.soft_refusal_count == 1
    assert result.scope_result.hard_refusal_count == 0


# ===========================================================================
# 11: final model report contradicts changed paths
# ===========================================================================


def test_report_contradicts_observed_changed_paths(harness: Harness, evidence_path: str) -> None:
    _iq1_correct_repair(harness)
    harness.claimed_no_change = True  # false: a real change was observed
    harness.claimed_changed_paths = frozenset()
    result = harness.run(IQ1_TASK, evidence_path)
    from qualification.report_accuracy import ClaimVerdict

    contradicted = [
        c for c in result.report_accuracy_comparisons if c.verdict is ClaimVerdict.CONTRADICTED
    ]
    assert contradicted, result.report_accuracy_comparisons
    # A misreport never overrides observed repository truth.
    assert result.autonomous_classification is AutonomousClassification.AUTONOMOUS_PASS


# ===========================================================================
# 12: model falsely claims it ran tests
# ===========================================================================


def test_false_claim_of_running_tests_is_contradicted(
    harness: Harness, evidence_path: str
) -> None:
    _iq1_correct_repair(harness)
    harness.claimed_ran_tests = True
    result = harness.run(IQ1_TASK, evidence_path)
    from qualification.report_accuracy import ClaimVerdict

    ran_tests_claim = [c for c in result.report_accuracy_comparisons if c.claim == "ran_tests"]
    assert ran_tests_claim and ran_tests_claim[0].verdict is ClaimVerdict.CONTRADICTED


# ===========================================================================
# 13: pre-prompt compatibility refusal -> zero semantic prompt
# ===========================================================================


@pytest.mark.parametrize(
    "break_fn",
    [
        lambda h: setattr(h, "non_secret_gate_passed", False),
        lambda h: setattr(h, "broker_ready", False),
        lambda h: setattr(h, "launch_facts_ok", False),
        lambda h: setattr(h, "h1_ok", False),
        lambda h: setattr(h, "namespace_ok", False),
        lambda h: setattr(h, "h2_ok", False),
        lambda h: setattr(h, "protocol_violation", True),
        lambda h: setattr(h, "route_model_served", False),
    ],
)
def test_pre_prompt_compatibility_refusal_sends_zero_prompts(
    harness: Harness, evidence_path: str, break_fn
) -> None:
    break_fn(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.semantic_prompts_sent == 0
    assert result.infrastructure_refusal is True
    assert result.run_validity is None
    assert result.scoring_eligible is False
    assert result.autonomous_classification is AutonomousClassification.INFRASTRUCTURE_REFUSAL
    assert result.failed_gate in PRE_PROMPT_GATES


def test_pre_prompt_refusal_never_calls_the_prompt_adapter(
    harness: Harness, evidence_path: str
) -> None:
    harness.non_secret_gate_passed = False
    calls: list[object] = []
    original = harness.dispatch_semantic_prompt
    harness.dispatch_semantic_prompt = (
        lambda request: calls.append(request) or original(request)
    )
    harness.run(IQ1_TASK, evidence_path)
    assert calls == []


# ===========================================================================
# 14: post-prompt route/provider failure -> INFRASTRUCTURE_CONTAMINATED
# ===========================================================================


def test_post_prompt_infrastructure_failure_is_contaminated(
    harness: Harness, evidence_path: str
) -> None:
    _iq1_correct_repair(harness)
    harness.runtime_shutdown_ok = False
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.semantic_prompts_sent == 1
    assert result.infrastructure_refusal is False
    assert result.run_validity is RunValidity.INFRASTRUCTURE_CONTAMINATED
    assert result.scoring_eligible is False


# ===========================================================================
# 15: post-prompt teardown failure -> INFRASTRUCTURE_CONTAMINATED
# ===========================================================================


def test_post_prompt_teardown_failure_is_contaminated(
    harness: Harness, evidence_path: str
) -> None:
    _iq1_correct_repair(harness)
    harness.broker_shutdown_ok = False
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.run_validity is RunValidity.INFRASTRUCTURE_CONTAMINATED
    assert result.scoring_eligible is False
    assert result.broker_shutdown.status_text.startswith("FAILED:")


# ===========================================================================
# 16: attribution-undetermined anomaly -> not scored
# ===========================================================================


def test_attribution_undetermined_anomaly_is_not_scored(
    harness: Harness, evidence_path: str
) -> None:
    """A genuine POST-prompt mid-run gate failure: dispatch is mechanically
    CONFIRMED_SENT (the default harness behavior), and a LATER gate
    (broker-activity collection) then fails. This is the shape
    ATTRIBUTION_UNDETERMINED exists for -- distinct from a dispatch-boundary
    outcome (5F3B-Q1-PRE1-FU1; see the dedicated
    ``test_prompt_dispatch_confirmed_not_sent_is_a_pre_prompt_refusal``/
    ``test_generic_dispatch_exception_is_send_state_indeterminate`` tests
    below for the dispatch-boundary shapes this test USED TO conflate with a
    genuine post-prompt failure, pre-fix).
    """
    _iq1_correct_repair(harness)
    harness.collect_broker_activity = lambda session: BrokerActivityObservation(
        runtime_session_id=session.runtime_session_id, call_succeeded=False
    )
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.semantic_prompts_sent == 1
    assert result.dispatch_state is SemanticPromptDispatchState.CONFIRMED_SENT
    assert result.run_validity is RunValidity.ATTRIBUTION_UNDETERMINED
    assert result.scoring_eligible is False
    assert result.autonomous_classification is None


# ===========================================================================
# 17: prompt dispatch mechanically CONFIRMED_NOT_SENT -> a pre-prompt refusal
# (5F3B-Q1-PRE1-FU1 -- the fixed shape of this section; see the module-level
# note below for the pre-fix behavior this replaces)
# ===========================================================================


def test_prompt_dispatch_confirmed_not_sent_is_a_pre_prompt_refusal(
    harness: Harness, evidence_path: str
) -> None:
    """5F3B-Q1-PRE1-FU1: a MECHANICALLY ESTABLISHED pre-send refusal -- the
    adapter RETURNS (never raises) a CONFIRMED_NOT_SENT dispatch observation
    -- truthfully records semantic_prompts_sent = 0 and is a pre-prompt
    infrastructure refusal, never scored.

    PRE-FIX, this exact harness configuration (a dispatch-gate failure) was
    recorded as semantic_prompts_sent == 1, because that assignment happened
    BEFORE the adapter was ever called, regardless of what it returned. See
    ``test_pre_fix_counterexample_is_closed`` below for the direct
    reproduction/closure proof.
    """
    harness.dispatch_state = SemanticPromptDispatchState.CONFIRMED_NOT_SENT
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.semantic_prompts_sent == 0
    assert result.dispatch_state is SemanticPromptDispatchState.CONFIRMED_NOT_SENT
    assert result.infrastructure_refusal is True
    assert result.run_validity is None
    assert result.scoring_eligible is False
    assert result.autonomous_classification is AutonomousClassification.INFRASTRUCTURE_REFUSAL
    assert result.failed_gate is SemanticGateName.SEMANTIC_PROMPT_DISPATCH
    assert result.failure_code is SemanticFailureCode.SEMANTIC_PROMPT_CONFIRMED_NOT_SENT
    assert result.qualification_record is not None
    assert result.qualification_record["emitted"] is True


# ===========================================================================
# 18/19: one semantic prompt accepted -> never a second; no automatic
# continuation exists anywhere in this module (source-level check)
# ===========================================================================


def test_exactly_one_prompt_adapter_call_per_attempt(harness: Harness, evidence_path: str) -> None:
    _iq1_correct_repair(harness)
    call_count = {"n": 0}
    original = harness.dispatch_semantic_prompt

    def counting(request):
        call_count["n"] += 1
        return original(request)

    harness.dispatch_semantic_prompt = counting
    harness.run(IQ1_TASK, evidence_path)
    assert call_count["n"] == 1


def test_no_automatic_continuation_source_level() -> None:
    import qualification.semantic_controller as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    for forbidden in ("continue your work", "operator_continuation=True", "retry_prompt"):
        assert forbidden not in source


# ===========================================================================
# 20: fresh repository/runtime/broker for each task
# ===========================================================================


def test_fresh_workspace_per_attempt(harness: Harness, evidence_path: str, tmp_path: Path) -> None:
    _iq1_correct_repair(harness)
    result_1 = harness.run(IQ1_TASK, str(tmp_path / "one.json"))
    workspace_root_1 = harness.workspace_root

    harness2 = Harness("A", harness.git_executable)
    _iq1_correct_repair(harness2)
    harness2.run(IQ1_TASK, str(tmp_path / "two.json"))
    workspace_root_2 = harness2.workspace_root

    assert workspace_root_1 != workspace_root_2
    assert not Path(workspace_root_1).exists() or Path(workspace_root_1) != Path(
        workspace_root_2
    )


# ===========================================================================
# 21: candidate A/B prompt bytes identical for the same task
# ===========================================================================


def test_candidate_a_and_b_prompt_text_is_byte_identical() -> None:
    for task in TASKS_BY_ID.values():
        # The prompt is a property of the frozen task, never of the
        # candidate -- there is no candidate parameter anywhere in its
        # derivation.
        assert task.prompt == task.prompt  # trivial identity; real proof below
    # Prove no candidate-conditional prompt text exists in this module.
    import qualification.semantic_controller as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert 'candidate == "A"' not in source
    assert 'candidate == "B"' not in source


# ===========================================================================
# 22: candidate A/B policy values identical
# ===========================================================================


def test_candidate_a_and_b_share_identical_gate_sequence(
    git_executable: str, evidence_path: str, tmp_path: Path
) -> None:
    for candidate in ("A", "B"):
        h = Harness(candidate, git_executable)
        _iq1_correct_repair(h)
        result = h.run(IQ1_TASK, str(tmp_path / f"{candidate}.json"))
        assert result.autonomous_classification is AutonomousClassification.AUTONOMOUS_PASS
        assert tuple(result.gate_statuses.keys()) == tuple(
            gate.value for gate in (*PRE_PROMPT_GATES, *POST_PROMPT_GATES, *CLOSURE_GATES)
        )


# ===========================================================================
# 23: IQ-1/2/3 fixed order for sweep -- see test_semantic_sweep.py
# 24: no state reuse between tasks -- see test_semantic_sweep.py
# ===========================================================================


# ===========================================================================
# 25/26: evidence collision cannot overwrite an earlier record; unsafe
# retained evidence becomes bounded refusal, not partial artifact
# ===========================================================================


def test_evidence_collision_cannot_overwrite_earlier_record(
    harness: Harness, evidence_path: str
) -> None:
    _iq1_correct_repair(harness)
    harness.run(IQ1_TASK, evidence_path)
    harness2 = Harness("A", harness.git_executable)
    _iq1_correct_repair(harness2)
    with pytest.raises(Exception):
        harness2.run(IQ1_TASK, evidence_path)


# ===========================================================================
# 27: reasoning content does not reach retained facts
# ===========================================================================


def test_no_reasoning_field_exists_anywhere_in_result(harness: Harness, evidence_path: str) -> None:
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(result)}
    for forbidden in ("reasoning", "chain_of_thought", "thinking"):
        assert not any(forbidden in name for name in field_names)


# ===========================================================================
# 28: historical Category-B pass cannot substitute for this run's own
# pre-prompt compatibility gate (every attempt re-establishes its own gates)
# ===========================================================================


def test_every_attempt_reestablishes_its_own_compatibility_gates(
    harness: Harness, evidence_path: str
) -> None:
    calls = {"broker": 0, "launch": 0, "get_commands": 0, "get_state": 0}
    orig_broker, orig_launch = harness.create_broker, harness.launch_runtime
    orig_gc, orig_gs = harness.get_commands, harness.get_state
    harness.create_broker = lambda r: (calls.__setitem__("broker", calls["broker"] + 1), orig_broker(r))[1]
    harness.launch_runtime = lambda r: (calls.__setitem__("launch", calls["launch"] + 1), orig_launch(r))[1]
    harness.get_commands = lambda s: (calls.__setitem__("get_commands", calls["get_commands"] + 1), orig_gc(s))[1]
    harness.get_state = lambda s: (calls.__setitem__("get_state", calls["get_state"] + 1), orig_gs(s))[1]
    _iq1_correct_repair(harness)
    harness.run(IQ1_TASK, evidence_path)
    assert calls == {"broker": 1, "launch": 1, "get_commands": 1, "get_state": 1}


# ===========================================================================
# 29: no reviewer participates in the primary verdict
# ===========================================================================


def test_no_reviewer_reference_anywhere_in_module() -> None:
    import qualification.semantic_controller as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    for forbidden in ("review_packet", "ReviewPacket", "reviewer_model", "llm_review"):
        assert forbidden not in source


# ===========================================================================
# Caller-supplied override attacks (adversarial review checklist)
# ===========================================================================


def test_caller_supplied_task_not_in_frozen_corpus_is_refused(
    harness: Harness, evidence_path: str
) -> None:
    from dataclasses import replace

    forged_task = replace(IQ1_TASK, task_id="IQ-1")  # a copy, not the frozen singleton
    with pytest.raises(SemanticControllerInputError):
        harness.run(forged_task, evidence_path)


def test_unknown_candidate_is_refused(git_executable: str, evidence_path: str) -> None:
    with pytest.raises(SemanticControllerInputError):
        run_semantic_task_attempt(
            candidate="C",
            task=IQ1_TASK,
            ambient_environ={},
            node_executable=sys.executable,
            git_executable=git_executable,
            python_executable=sys.executable,
            non_secret_gates=[lambda: PreflightGateResult(name="g", passed=True)],
            read_connection=lambda: ConnectionValues(
                base_url="https://x.invalid", api_key="k"
            ),
            create_broker=lambda r: (_ for _ in ()).throw(AssertionError("must not be called")),
            launch_runtime=lambda r: (_ for _ in ()).throw(AssertionError("must not be called")),
            get_commands=lambda s: (_ for _ in ()).throw(AssertionError("must not be called")),
            get_state=lambda s: (_ for _ in ()).throw(AssertionError("must not be called")),
            observe_protocol=lambda s: (_ for _ in ()).throw(AssertionError("must not be called")),
            route_checker=lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not be called")),
            dispatch_semantic_prompt=lambda r: (_ for _ in ()).throw(
                AssertionError("must not be called")
            ),
            observe_semantic_turn=lambda r: (_ for _ in ()).throw(
                AssertionError("must not be called")
            ),
            collect_broker_activity=lambda s: (_ for _ in ()).throw(AssertionError("must not be called")),
            collect_final_report_claims=lambda s: (_ for _ in ()).throw(AssertionError("must not be called")),
            shutdown_runtime=lambda s: (_ for _ in ()).throw(AssertionError("must not be called")),
            shutdown_broker=lambda s: (_ for _ in ()).throw(AssertionError("must not be called")),
            evidence_path=evidence_path,
        )


def test_credential_read_gate_position_is_after_pre_credential_gates() -> None:
    idx = PRE_PROMPT_GATES.index(CREDENTIAL_READ_GATE)
    for earlier in (
        SemanticGateName.RUN_CORRELATION,
        SemanticGateName.WORKSPACE_AUTHORITY,
        SemanticGateName.WORKSPACE_BASELINE,
        SemanticGateName.ROUTE_DESCRIPTOR,
        SemanticGateName.NON_SECRET_PREFLIGHT,
    ):
        assert PRE_PROMPT_GATES.index(earlier) < idx


def test_no_credential_read_before_a_pre_credential_gate_fails(
    harness: Harness, evidence_path: str
) -> None:
    harness.non_secret_gate_passed = False
    calls: list[object] = []
    original = harness.read_connection
    harness.read_connection = lambda: calls.append(1) or original()
    harness.run(IQ1_TASK, evidence_path)
    assert calls == []


# ===========================================================================
# Closure must be unconditional even when an UNANTICIPATED exception (not
# one of this module's own _GateFailure raises) escapes mid-run.
# ===========================================================================


def test_unexpected_exception_before_any_resource_still_returns_a_result(
    harness: Harness, evidence_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import qualification.semantic_controller as mod

    def _boom() -> str:
        raise RuntimeError("unexpected failure the module did not anticipate")

    monkeypatch.setattr(mod, "_mint_run_correlation_id", _boom)
    # Must return a result, never raise -- and must be a truthful pre-prompt
    # infrastructure refusal, since nothing was ever created.
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.semantic_prompts_sent == 0
    assert result.infrastructure_refusal is True
    assert result.runtime_teardown.status_text == "NOT_REQUIRED"
    assert result.broker_shutdown.status_text == "NOT_REQUIRED"


def test_unexpected_exception_after_resources_created_still_tears_down(
    harness: Harness, evidence_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import qualification.semantic_controller as mod

    original_route_check = mod.run_offline_route_check
    calls = {"shutdown_runtime": 0, "shutdown_broker": 0}
    original_shutdown_runtime = harness.shutdown_runtime
    original_shutdown_broker = harness.shutdown_broker
    harness.shutdown_runtime = lambda s: (
        calls.__setitem__("shutdown_runtime", calls["shutdown_runtime"] + 1),
        original_shutdown_runtime(s),
    )[1]
    harness.shutdown_broker = lambda s: (
        calls.__setitem__("shutdown_broker", calls["shutdown_broker"] + 1),
        original_shutdown_broker(s),
    )[1]

    def _boom(*args, **kwargs):
        raise RuntimeError("unexpected failure after broker/runtime already exist")

    monkeypatch.setattr(mod, "run_offline_route_check", _boom)
    # Broker and runtime sessions exist by the time ROUTE_CHECK runs.
    # An exception here must still result in both shutdown adapters being
    # called -- CLOSURE is unconditional, on every path.
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.semantic_prompts_sent == 0
    assert result.infrastructure_refusal is True
    assert calls["shutdown_runtime"] == 1
    assert calls["shutdown_broker"] == 1


def test_closure_gate_status_text_matches_the_typed_object(
    harness: Harness, evidence_path: str
) -> None:
    _iq1_correct_repair(harness)
    harness.runtime_shutdown_ok = False
    result = harness.run(IQ1_TASK, evidence_path)
    assert (
        result.gate_statuses[SemanticGateName.RUNTIME_TEARDOWN.value]
        == result.runtime_teardown.status_text
    )
    assert result.runtime_teardown.status_text != "PASSED"


# ===========================================================================
# 5F3B-Q1-PRE1-FU1 -- semantic prompt dispatch truthfulness closure
#
# PRE-FIX DEFECT: `semantic_prompts_sent = 1` was assigned BEFORE the
# dispatch adapter (`dispatch_semantic_prompt`) was ever called, so ANY
# dispatch-gate outcome -- including one mechanically established as never
# having been sent, or one AIDO could never establish either way -- was
# recorded as though the one authorized prompt had been spent. This section
# proves the fix: `semantic_prompts_sent` is now a TRUTH the controller
# reads from a mechanically-established `SemanticPromptDispatchState`
# (CONFIRMED_SENT / CONFIRMED_NOT_SENT / SEND_STATE_INDETERMINATE), never an
# inference from having merely called a Python function. Numbered comments
# below reference the mandatory regressions from the FU1 authorization.
# ===========================================================================


def _assert_indeterminate(result) -> None:
    """Shared assertions for every SEND_STATE_INDETERMINATE outcome (#6-#9)."""
    assert result.dispatch_state is SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
    assert result.semantic_prompts_sent is None
    assert result.infrastructure_refusal is False
    assert result.run_validity is None
    assert result.scoring_eligible is False
    assert result.autonomous_classification is None
    assert result.qualification_record is None
    assert result.failed_gate is SemanticGateName.SEMANTIC_PROMPT_DISPATCH
    assert result.failure_code is SemanticFailureCode.SEMANTIC_PROMPT_SEND_STATE_INDETERMINATE
    assert (
        result.gate_statuses[SemanticGateName.SEMANTIC_PROMPT_DISPATCH.value]
        == f"FAILED:{SemanticFailureCode.SEMANTIC_PROMPT_SEND_STATE_INDETERMINATE.value}"
    )
    # 5F3B-Q1-PRE1-FU2: an indeterminate attempt is no longer the one outcome
    # that leaves nothing on disk. It emits the SIBLING attempt artifact --
    # never the primary record, and never both.
    assert result.gate_statuses[SemanticGateName.EVIDENCE_SAFETY.value] == "PASSED"
    assert result.attempt_record is not None
    assert result.attempt_record["emitted"] is True
    assert result.attempt_record["refused"] is False
    assert result.evidence_emission is not None
    assert result.evidence_emission.refused is False


# -- 1: dispatch is never called before same-run compatibility PASS --------


def test_dispatch_never_called_before_compatibility_established(
    harness: Harness, evidence_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(harness, "h2_ok", False)  # a late PRE_PROMPT gate fails
    calls: list[object] = []
    original = harness.dispatch_semantic_prompt
    harness.dispatch_semantic_prompt = (
        lambda request: calls.append(request) or original(request)
    )
    result = harness.run(IQ1_TASK, evidence_path)
    assert calls == []
    assert result.failed_gate in PRE_PROMPT_GATES
    assert result.dispatch_state is SemanticPromptDispatchState.CONFIRMED_NOT_SENT
    assert result.semantic_prompts_sent == 0


# -- 2: the controller never sets semantic_prompts_sent=1 before dispatch --
# -- truth exists (source-level structural proof) --------------------------


def test_semantic_prompts_sent_assigned_only_after_dispatch_confirmed_source_level() -> None:
    import qualification.semantic_controller as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    # Exactly one CODE-level assignment (the module docstring also
    # mentions the literal text while describing the pre-fix defect, so the
    # count is scoped to a standalone 8-space-indented statement line).
    assignment_matches = list(
        re.finditer(r"(?m)^        semantic_prompts_sent = 1$", source)
    )
    assert len(assignment_matches) == 1
    assignment_idx = assignment_matches[0].start()
    dispatch_call_idx = source.index(
        "dispatch_observation = dispatch_semantic_prompt(prompt_request)"
    )
    confirmed_sent_check_idx = source.index(
        "if dispatch_state is SemanticPromptDispatchState.CONFIRMED_NOT_SENT:"
    )
    # The one assignment must appear AFTER both the adapter call and the
    # CONFIRMED_SENT/CONFIRMED_NOT_SENT branch -- never before either.
    assert assignment_idx > dispatch_call_idx
    assert assignment_idx > confirmed_sent_check_idx


# -- 3: mechanically confirmed pre-send refusal -> semantic_prompts_sent=0 -
# (covered fully by test_prompt_dispatch_confirmed_not_sent_is_a_pre_prompt_refusal above)


# -- 4: confirmed successful dispatch -> semantic_prompts_sent=1 -----------
# (covered fully by test_iq1_full_autonomous_pass above; restated narrowly here)


def test_confirmed_sent_dispatch_records_semantic_prompts_sent_one(
    harness: Harness, evidence_path: str
) -> None:
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.dispatch_state is SemanticPromptDispatchState.CONFIRMED_SENT
    assert result.semantic_prompts_sent == 1


# -- 5: a failure AFTER mechanically confirmed send preserves =1 -----------
# (covered by test_attribution_undetermined_anomaly_is_not_scored and
# test_post_prompt_infrastructure_failure_is_contaminated above)


# -- 6: a generic dispatch exception is NEVER automatically NOT_SENT -------


def test_generic_dispatch_exception_is_send_state_indeterminate(
    harness: Harness, evidence_path: str
) -> None:
    def _raises(request: SemanticPromptRequest):
        raise RuntimeError("adapter blew up -- unknown whether the wire write happened")

    harness.dispatch_semantic_prompt = _raises
    result = harness.run(IQ1_TASK, evidence_path)
    _assert_indeterminate(result)


def test_exception_after_possible_send_is_still_indeterminate_never_sent(
    harness: Harness, evidence_path: str
) -> None:
    """Adversarial: an adapter that mutates shared state (as though it had
    sent something) and THEN raises must still be indeterminate -- AIDO has
    no way to mechanically distinguish "raised before sending" from "raised
    after sending" from an exception alone, so both collapse to the same
    honest outcome.
    """
    sent_marker = {"maybe_sent": False}

    def _raises_after_side_effect(request: SemanticPromptRequest):
        sent_marker["maybe_sent"] = True
        raise ConnectionResetError("wire dropped after (maybe) writing the request")

    harness.dispatch_semantic_prompt = _raises_after_side_effect
    result = harness.run(IQ1_TASK, evidence_path)
    assert sent_marker["maybe_sent"] is True
    _assert_indeterminate(result)


# -- 7: a wrong-type dispatch result is NEVER automatically NOT_SENT -------


def test_wrong_type_dispatch_result_is_send_state_indeterminate(
    harness: Harness, evidence_path: str
) -> None:
    harness.dispatch_semantic_prompt = lambda request: SimpleNamespace(
        runtime_session_id=request.runtime_session.runtime_session_id, call_succeeded=True
    )
    result = harness.run(IQ1_TASK, evidence_path)
    _assert_indeterminate(result)


def test_subclass_of_turn_observation_is_send_state_indeterminate(
    harness: Harness, evidence_path: str
) -> None:
    """Adversarial: subclass substitution. The controller's exact-type check
    (`type(x) is SemanticTurnObservation`) must refuse a subclass instance
    exactly like any other wrong type."""

    class _SubclassedTurnObservation(SemanticTurnObservation):
        pass

    def _returns_subclass(request: SemanticPromptRequest):
        dispatch = SemanticPromptDispatchObservation(
            run_id=request.run_id,
            runtime_session_id=request.runtime_session.runtime_session_id,
            task_id=request.task_id,
            task_revision=request.task_revision,
            dispatch_state=SemanticPromptDispatchState.CONFIRMED_SENT,
        )
        return _SubclassedTurnObservation(
            runtime_session_id=request.runtime_session.runtime_session_id,
            dispatch=dispatch,
            call_succeeded=True,
            agent_settled=True,
        )

    harness.dispatch_semantic_prompt = _returns_subclass
    result = harness.run(IQ1_TASK, evidence_path)
    _assert_indeterminate(result)


def test_wholly_foreign_but_internally_consistent_observation_is_indeterminate(
    harness: Harness, evidence_path: str
) -> None:
    """Adversarial: a returned observation that is internally self-consistent
    (its own ``runtime_session_id`` matches its embedded dispatch's) but
    answers a DIFFERENT session entirely -- not merely one field off. This
    must be caught by matching against the REAL request, not merely by the
    object's own internal coherence check."""

    def _wrong_session_entirely(request: SemanticPromptRequest):
        dispatch = SemanticPromptDispatchObservation(
            run_id=request.run_id,
            runtime_session_id="rsess-FOREIGN",
            task_id=request.task_id,
            task_revision=request.task_revision,
            dispatch_state=SemanticPromptDispatchState.CONFIRMED_SENT,
        )
        return SemanticTurnObservation(
            runtime_session_id="rsess-FOREIGN",
            dispatch=dispatch,
            call_succeeded=True,
            agent_settled=True,
        )

    harness.dispatch_semantic_prompt = _wrong_session_entirely
    result = harness.run(IQ1_TASK, evidence_path)
    _assert_indeterminate(result)


# -- adversarial: mismatched session/run/task in the dispatch observation --


@pytest.mark.parametrize(
    "field_name,bad_value",
    [
        ("run_id", "sem-completely-different-run"),
        ("task_id", "IQ-2"),
        ("task_revision", "not-the-real-revision"),
    ],
)
def test_mismatched_dispatch_provenance_is_send_state_indeterminate(
    harness: Harness, evidence_path: str, field_name: str, bad_value: str
) -> None:
    def _mismatched(request: SemanticPromptRequest):
        kwargs = dict(
            run_id=request.run_id,
            runtime_session_id=request.runtime_session.runtime_session_id,
            task_id=request.task_id,
            task_revision=request.task_revision,
            dispatch_state=SemanticPromptDispatchState.CONFIRMED_SENT,
        )
        kwargs[field_name] = bad_value
        dispatch = SemanticPromptDispatchObservation(**kwargs)
        return SemanticTurnObservation(
            runtime_session_id=request.runtime_session.runtime_session_id,
            dispatch=dispatch,
            call_succeeded=True,
            agent_settled=True,
        )

    harness.dispatch_semantic_prompt = _mismatched
    result = harness.run(IQ1_TASK, evidence_path)
    _assert_indeterminate(result)


def test_adapter_reported_indeterminate_dispatch_state_is_honored(
    harness: Harness, evidence_path: str
) -> None:
    """A live adapter's OWN real seam may itself report
    SEND_STATE_INDETERMINATE (a returned value, never an exception) -- this
    must be honored identically to the controller-inferred cases above."""
    harness.dispatch_state = SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
    result = harness.run(IQ1_TASK, evidence_path)
    _assert_indeterminate(result)


# -- 8: indeterminate send state never enters candidate scoring ------------
# (asserted directly inside `_assert_indeterminate` above: run_validity is
# None, scoring_eligible is False, autonomous_classification is None)


# -- 9: indeterminate send state never causes retry/continuation -----------


def test_indeterminate_dispatch_causes_no_retry(
    harness: Harness, evidence_path: str
) -> None:
    call_count = {"n": 0}

    def _raises_once_counted(request: SemanticPromptRequest):
        call_count["n"] += 1
        raise RuntimeError("boom")

    harness.dispatch_semantic_prompt = _raises_once_counted
    result = harness.run(IQ1_TASK, evidence_path)
    assert call_count["n"] == 1
    _assert_indeterminate(result)


# -- 10: exactly one successful semantic dispatch remains the hard maximum -


def test_max_semantic_prompts_per_attempt_is_still_one() -> None:
    import qualification.semantic_controller as mod

    assert mod.MAX_SEMANTIC_PROMPTS_PER_ATTEMPT == 1


# -- 11: cleanup classification consumes the TRUTHFUL prompt count ---------


def test_cleanup_classification_after_confirmed_sent_uses_semantic_prompts_sent_one(
    harness: Harness, evidence_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import qualification.semantic_controller as mod

    _iq1_correct_repair(harness)
    monkeypatch.setattr(
        mod,
        "scrub_generated_qualification_config",
        lambda cfg: (_ for _ in ()).throw(QualificationPiConfigCleanupError("boom")),
    )
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.semantic_prompts_sent == 1
    assert result.cleanup.attempted is True
    assert result.cleanup.scrub_verified is False
    assert result.cleanup.semantic_prompts_sent == 1
    assert result.cleanup.classification is not None
    assert result.cleanup.classification.semantic_prompts_sent == 1
    assert result.run_validity is RunValidity.INFRASTRUCTURE_CONTAMINATED
    assert result.scoring_eligible is False


def test_cleanup_classification_after_confirmed_not_sent_uses_semantic_prompts_sent_zero(
    harness: Harness, evidence_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import qualification.semantic_controller as mod

    harness.dispatch_state = SemanticPromptDispatchState.CONFIRMED_NOT_SENT
    monkeypatch.setattr(
        mod,
        "scrub_generated_qualification_config",
        lambda cfg: (_ for _ in ()).throw(QualificationPiConfigCleanupError("boom")),
    )
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.semantic_prompts_sent == 0
    assert result.infrastructure_refusal is True
    assert result.cleanup.attempted is True
    assert result.cleanup.scrub_verified is False
    assert result.cleanup.semantic_prompts_sent == 0
    assert result.cleanup.classification is not None
    assert result.cleanup.classification.semantic_prompts_sent == 0


def test_cleanup_classification_after_indeterminate_dispatch_invents_nothing(
    harness: Harness, evidence_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The frozen `classify_cleanup_failure` has no shape for an
    unestablished `semantic_prompts_sent` -- it must never be called with a
    forced/guessed 0 or 1 here, and `classification` must honestly be
    `None` rather than a lie."""
    import qualification.semantic_controller as mod

    def _raises(request: SemanticPromptRequest):
        raise RuntimeError("boom")

    harness.dispatch_semantic_prompt = _raises
    monkeypatch.setattr(
        mod,
        "scrub_generated_qualification_config",
        lambda cfg: (_ for _ in ()).throw(QualificationPiConfigCleanupError("boom")),
    )
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.semantic_prompts_sent is None
    assert result.cleanup.attempted is True
    assert result.cleanup.scrub_verified is False
    assert result.cleanup.semantic_prompts_sent is None
    assert result.cleanup.classification is None
    assert result.cleanup.status_text == (
        "FAILED:GENERATED_CONFIG_CLEANUP_UNVERIFIED_INDETERMINATE_DISPATCH"
    )
    assert result.run_validity is None
    assert result.scoring_eligible is False


# -- 12: retained record/evidence cannot contradict the established --------
# -- dispatch state ----------------------------------------------------------


def test_result_semantic_prompts_sent_cannot_contradict_confirmed_sent(
    harness: Harness, evidence_path: str
) -> None:
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.dispatch_state is SemanticPromptDispatchState.CONFIRMED_SENT
    with pytest.raises(ValueError):
        replace(result, semantic_prompts_sent=0)
    with pytest.raises(ValueError):
        replace(result, semantic_prompts_sent=None)


def test_result_semantic_prompts_sent_cannot_contradict_indeterminate(
    harness: Harness, evidence_path: str
) -> None:
    def _raises(request: SemanticPromptRequest):
        raise RuntimeError("boom")

    harness.dispatch_semantic_prompt = _raises
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.dispatch_state is SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
    with pytest.raises(ValueError):
        replace(result, semantic_prompts_sent=1)
    with pytest.raises(ValueError):
        replace(result, semantic_prompts_sent=0)
    # Nor may an indeterminate result be silently upgraded to a scored one.
    with pytest.raises(ValueError):
        replace(result, dispatch_state=SemanticPromptDispatchState.CONFIRMED_SENT)


def test_result_is_frozen_against_post_validation_mutation(
    harness: Harness, evidence_path: str
) -> None:
    _iq1_correct_repair(harness)
    result = harness.run(IQ1_TASK, evidence_path)
    with pytest.raises(FrozenInstanceError):
        result.semantic_prompts_sent = 1  # type: ignore[misc]


# -- 13: candidate A/B use identical dispatch semantics --------------------


@pytest.mark.parametrize("candidate", ["A", "B"])
def test_candidate_a_and_b_indeterminate_dispatch_semantics_are_identical(
    git_executable: str, evidence_path: str, candidate: str
) -> None:
    h = Harness(candidate, git_executable)

    def _raises(request: SemanticPromptRequest):
        raise RuntimeError("boom")

    h.dispatch_semantic_prompt = _raises
    result = h.run(IQ1_TASK, evidence_path)
    _assert_indeterminate(result)
    assert result.candidate == candidate


@pytest.mark.parametrize("candidate", ["A", "B"])
def test_candidate_a_and_b_confirmed_not_sent_semantics_are_identical(
    git_executable: str, evidence_path: str, candidate: str
) -> None:
    h = Harness(candidate, git_executable)
    h.dispatch_state = SemanticPromptDispatchState.CONFIRMED_NOT_SENT
    result = h.run(IQ1_TASK, evidence_path)
    assert result.semantic_prompts_sent == 0
    assert result.infrastructure_refusal is True
    assert result.candidate == candidate


# -- 14: prompt text still has no caller-substitution path ------------------


def test_dispatch_types_have_no_free_text_prompt_field() -> None:
    import dataclasses

    for cls in (SemanticPromptRequest, SemanticPromptDispatchObservation, SemanticTurnObservation):
        field_names = {f.name for f in dataclasses.fields(cls)}
        assert "prompt" not in field_names
        assert "prompt_text" not in field_names


# -- 15: the pre-fix counterexample is closed -------------------------------


def test_pre_fix_counterexample_is_closed(git_executable: str, tmp_path: Path) -> None:
    """Direct reproduction of the reviewer's exact counterexample shape:

        semantic dispatch not established as sent
        BUT
        semantic_prompts_sent == 1

    Drives every non-CONFIRMED_SENT dispatch shape this controller can reach
    (a mechanically confirmed pre-send refusal, a raised exception, and a
    malformed/wrong-type result) and proves NONE of them ever produces the
    contradiction. Pre-fix, ALL THREE produced it, because
    `semantic_prompts_sent = 1` was assigned unconditionally before the
    adapter was ever called.
    """
    scenarios = []

    h1 = Harness("A", git_executable)
    h1.dispatch_state = SemanticPromptDispatchState.CONFIRMED_NOT_SENT
    scenarios.append(h1.run(IQ1_TASK, str(tmp_path / "a.json")))

    h2 = Harness("A", git_executable)
    h2.dispatch_semantic_prompt = lambda request: (_ for _ in ()).throw(RuntimeError("boom"))
    scenarios.append(h2.run(IQ1_TASK, str(tmp_path / "b.json")))

    h3 = Harness("A", git_executable)
    h3.dispatch_semantic_prompt = lambda request: object()
    scenarios.append(h3.run(IQ1_TASK, str(tmp_path / "c.json")))

    for result in scenarios:
        established_sent = result.dispatch_state is SemanticPromptDispatchState.CONFIRMED_SENT
        # THE counterexample itself: dispatch not established as sent, but
        # semantic_prompts_sent == 1 regardless.
        counterexample = (not established_sent) and (result.semantic_prompts_sent == 1)
        assert not counterexample
        # And the converse framing: semantic_prompts_sent == 1 implies
        # CONFIRMED_SENT was actually established.
        if result.semantic_prompts_sent == 1:
            assert established_sent
