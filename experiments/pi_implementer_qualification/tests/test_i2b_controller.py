"""5F3B-I2B-FU1 -- Category-B Zero-Prompt Live-Gate Controller (OFFLINE ONLY).

**Every test here uses ONLY synthetic, injected doubles for every future
live boundary.** No test in this module opens a socket, launches a
subprocess, reads a real environment variable, or calls a model --
``qualification.i2b_controller`` and ``qualification.i2b_session`` contain
no such primitive at all (proven below by source-level regression tests).

**CATEGORY-B LIVE EXECUTION IS NOT RUN BY THIS SUITE.** What is proven here
is the offline controller shape: the frozen-O1 lifecycle order, run-scoped
resource authority, one-observation H1/registry and H2/state derivation,
the terminal pass rule including lifecycle closure, the full artifact
safety context, result/evidence immutability, and zero-prompt authority.
"""

from __future__ import annotations

import dataclasses
import inspect
from dataclasses import dataclass, field
from pathlib import Path

import pytest

import qualification.i2b_controller as i2b_controller_module
import qualification.i2b_session as i2b_session_module
from qualification.i2_credentials import ConnectionValues, PreflightGateResult
from qualification.i2b_controller import (
    AUTHORIZED_TOOL_NAMES,
    COMPATIBILITY_GATES,
    CategoryBControllerResult,
    CategoryBEvidence,
    CategoryBFailureCode,
    CategoryBGateName,
    CategoryBOutcome,
    CompatibilityFacts,
    build_run_safety_context,
    run_category_b_controller,
)
from qualification.i2b_session import (
    BrokerCreationRequest,
    BrokerSession,
    BrokerShutdownObservation,
    GetCommandsObservation,
    GetStateObservation,
    ObservationError,
    ObservedCommand,
    ProtocolObservation,
    RuntimeLaunchObservation,
    RuntimeLaunchRequest,
    RuntimeSession,
    RuntimeShutdownObservation,
)

SYNTHETIC_BASE_URL = "https://b300-proxy.example.invalid:8443/v1"
SYNTHETIC_API_KEY = "sk-synthetic-i2b-controller-0001"
SYNTHETIC_PIPE_NAME = r"\\.\pipe\aido-i2b-synthetic-0001"
SYNTHETIC_CAPABILITY_ID = "cap-synthetic-i2b-0001"
SYNTHETIC_BROKER_TOKEN = "brk-synthetic-i2b-token-0001"
SYNTHETIC_PI_VERSION = "0.84.3"

CANDIDATE_MODEL_IDS = {"A": "qwen3-coder-next", "B": "minimax-m2.7"}
PROVIDER_ID = "b300_pi_qualification"


# -- harness -------------------------------------------------------------------


def _passing_non_secret_gates() -> list:
    return [
        lambda: PreflightGateResult(name="pi_installed_offline", passed=True),
        lambda: PreflightGateResult(name="config_generator_self_check", passed=True),
        lambda: PreflightGateResult(name="environment_forbidden_fragment_audit", passed=True),
    ]


@dataclass(frozen=True)
class _FakeRouteModelCheck:
    reachable: bool
    configured_model_served: bool


@dataclass
class _Harness:
    """One synthetic Category-B adapter set, with per-stage knobs.

    Every adapter is a plain Python function over the I2B value objects --
    no process, no socket, no model, no environment read anywhere.
    """

    model_id: str
    api_key: str = SYNTHETIC_API_KEY
    calls: list[str] = field(default_factory=list)
    # observed run-scoped identities, captured as the adapters are driven
    broker_run_id: str | None = None
    broker: BrokerSession | None = None
    runtime: RuntimeSession | None = None
    launch_request: RuntimeLaunchRequest | None = None
    # knobs
    broker_ready: bool = True
    broker_run_id_override: str | None = None
    broker_reached_closed: bool = True
    broker_shutdown_session_id_override: str | None = None
    broker_result_override: object = None
    broker_raises: bool = False
    pi_version: str | None = SYNTHETIC_PI_VERSION
    launch_shape_valid: bool = True
    required_flags_accepted: bool = True
    lf_correlation: bool = True
    launch_returns_no_session: bool = False
    launch_cleaned_internally: bool = True
    launch_result_override: object = None
    launch_raises: bool = False
    launch_session_run_id_override: str | None = None
    launch_session_broker_id_override: str | None = None
    commands: tuple[ObservedCommand, ...] | None = None
    commands_call_succeeded: bool = True
    commands_shape_understood: bool = True
    h1_matched: bool = True
    commands_session_override: str | None = None
    commands_result_override: object = None
    state_call_succeeded: bool = True
    state_shape_understood: bool = True
    reported_provider: str | None = PROVIDER_ID
    reported_model: str | None = None
    state_session_override: str | None = None
    protocol_violation: bool = False
    extension_error: bool = False
    protocol_session_override: str | None = None
    route_reachable: bool = True
    route_model_served: bool = True
    runtime_shutdown_returned: bool = True
    runtime_child_exited: bool = True
    runtime_shutdown_session_override: str | None = None
    runtime_shutdown_raises: bool = False
    broker_shutdown_raises: bool = False

    # -- injected adapters --

    def read_connection(self) -> ConnectionValues:
        self.calls.append("read_connection")
        return ConnectionValues(base_url=SYNTHETIC_BASE_URL, api_key=self.api_key)

    def create_broker(self, request: BrokerCreationRequest) -> BrokerSession:
        self.calls.append("create_broker")
        assert isinstance(request, BrokerCreationRequest)
        self.broker_run_id = request.run_id
        if self.broker_raises:
            raise RuntimeError("synthetic broker failure")
        if self.broker_result_override is not None:
            return self.broker_result_override  # type: ignore[return-value]
        self.broker = BrokerSession(
            run_id=self.broker_run_id_override or request.run_id,
            session_id="brk-session-0001",
            pipe_name=SYNTHETIC_PIPE_NAME,
            capability_id=SYNTHETIC_CAPABILITY_ID,
            broker_token=SYNTHETIC_BROKER_TOKEN,
            reached_ready=self.broker_ready,
        )
        return self.broker

    def launch_runtime(self, request: RuntimeLaunchRequest) -> RuntimeLaunchObservation:
        self.calls.append("launch_runtime")
        assert isinstance(request, RuntimeLaunchRequest)
        self.launch_request = request
        if self.launch_raises:
            raise RuntimeError("synthetic launch failure")
        if self.launch_result_override is not None:
            return self.launch_result_override  # type: ignore[return-value]
        if self.launch_returns_no_session:
            return RuntimeLaunchObservation(
                session=None,
                launch_shape_valid=False,
                required_flags_accepted=self.required_flags_accepted,
                lf_jsonl_correlation_succeeded=False,
                observed_pi_version=self.pi_version,
                partial_resource_cleaned_internally=self.launch_cleaned_internally,
            )
        self.runtime = RuntimeSession(
            run_id=self.launch_session_run_id_override or request.run_id,
            broker_session_id=(
                self.launch_session_broker_id_override or request.broker_session.session_id
            ),
            runtime_session_id="rt-session-0001",
        )
        return RuntimeLaunchObservation(
            session=self.runtime,
            launch_shape_valid=self.launch_shape_valid,
            required_flags_accepted=self.required_flags_accepted,
            lf_jsonl_correlation_succeeded=self.lf_correlation,
            observed_pi_version=self.pi_version,
        )

    def get_commands(self, session: RuntimeSession) -> GetCommandsObservation:
        self.calls.append("get_commands")
        assert isinstance(session, RuntimeSession)
        if self.commands_result_override is not None:
            return self.commands_result_override  # type: ignore[return-value]
        commands = self.commands
        if commands is None:
            commands = tuple(
                ObservedCommand(name=name, source="extension") for name in AUTHORIZED_TOOL_NAMES
            )
        return GetCommandsObservation(
            runtime_session_id=self.commands_session_override or session.runtime_session_id,
            call_succeeded=self.commands_call_succeeded,
            response_shape_understood=self.commands_shape_understood,
            extension_identity_matched=self.h1_matched,
            commands=commands,
        )

    def get_state(self, session: RuntimeSession) -> GetStateObservation:
        self.calls.append("get_state")
        assert isinstance(session, RuntimeSession)
        return GetStateObservation(
            runtime_session_id=self.state_session_override or session.runtime_session_id,
            call_succeeded=self.state_call_succeeded,
            response_shape_understood=self.state_shape_understood,
            reported_provider=self.reported_provider,
            reported_model=(
                self.reported_model if self.reported_model is not None else self.model_id
            ),
        )

    def observe_protocol(self, session: RuntimeSession) -> ProtocolObservation:
        self.calls.append("observe_protocol")
        assert isinstance(session, RuntimeSession)
        return ProtocolObservation(
            runtime_session_id=self.protocol_session_override or session.runtime_session_id,
            protocol_violation_observed=self.protocol_violation,
            extension_error_observed=self.extension_error,
        )

    def route_checker(self, base_url: str, *, model_id: str) -> _FakeRouteModelCheck:
        self.calls.append("route_checker")
        return _FakeRouteModelCheck(
            reachable=self.route_reachable, configured_model_served=self.route_model_served
        )

    def shutdown_runtime(self, session: RuntimeSession) -> RuntimeShutdownObservation:
        self.calls.append("shutdown_runtime")
        assert isinstance(session, RuntimeSession)
        if self.runtime_shutdown_raises:
            raise RuntimeError("synthetic runtime shutdown failure")
        return RuntimeShutdownObservation(
            runtime_session_id=(
                self.runtime_shutdown_session_override or session.runtime_session_id
            ),
            shutdown_call_returned=self.runtime_shutdown_returned,
            orchestrator_direct_child_reported_exit=self.runtime_child_exited,
        )

    def shutdown_broker(self, session: BrokerSession) -> BrokerShutdownObservation:
        self.calls.append("shutdown_broker")
        assert isinstance(session, BrokerSession)
        if self.broker_shutdown_raises:
            raise RuntimeError("synthetic broker shutdown failure")
        return BrokerShutdownObservation(
            session_id=self.broker_shutdown_session_id_override or session.session_id,
            reached_closed=self.broker_reached_closed,
        )


def _run(
    root: Path,
    *,
    candidate: str = "A",
    harness: _Harness | None = None,
    non_secret_gates=None,
    read_connection=None,
) -> tuple[CategoryBControllerResult, _Harness]:
    root.mkdir(parents=True, exist_ok=True)
    workspace = root / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    harness = harness or _Harness(model_id=CANDIDATE_MODEL_IDS[candidate])
    result = run_category_b_controller(
        candidate=candidate,
        experiment_root=str(root),
        workspace_root=str(workspace),
        ambient_environ={"SystemRoot": r"C:\Windows", "TEMP": str(root), "TMP": str(root)},
        node_executable=str(root / "node.exe"),
        non_secret_gates=(
            non_secret_gates if non_secret_gates is not None else _passing_non_secret_gates()
        ),
        read_connection=read_connection if read_connection is not None else harness.read_connection,
        create_broker=harness.create_broker,
        launch_runtime=harness.launch_runtime,
        get_commands=harness.get_commands,
        get_state=harness.get_state,
        observe_protocol=harness.observe_protocol,
        route_checker=harness.route_checker,
        shutdown_runtime=harness.shutdown_runtime,
        shutdown_broker=harness.shutdown_broker,
    )
    return result, harness


def _assert_refusal(result: CategoryBControllerResult) -> None:
    assert result.outcome is CategoryBOutcome.INFRASTRUCTURE_REFUSAL
    assert result.semantic_prompts_sent == 0
    assert result.failed_gate is not None
    assert result.failure_code is not None
    assert result.compatibility_gate_passed is False


# -- the full pass, and candidate symmetry ------------------------------------


@pytest.mark.parametrize("candidate", ["A", "B"])
def test_full_pass_candidate_symmetry(tmp_path: Path, candidate: str) -> None:
    result, harness = _run(tmp_path / candidate, candidate=candidate)

    assert result.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED
    assert result.semantic_prompts_sent == 0
    assert result.failed_gate is None and result.failure_code is None
    assert result.facts.all_established is True
    assert result.compatibility_gate_passed is True

    for gate in COMPATIBILITY_GATES:
        assert result.gate_statuses[gate.value] == "PASSED", gate.value
    assert result.gate_statuses[CategoryBGateName.RUNTIME_TEARDOWN.value] == "SUCCEEDED"
    assert result.gate_statuses[CategoryBGateName.BROKER_SHUTDOWN.value] == "CLOSED"
    assert (
        result.gate_statuses[CategoryBGateName.GENERATED_CONFIG_CLEANUP.value]
        == "VERIFIED_REMOVED"
    )
    assert result.gate_statuses[CategoryBGateName.EVIDENCE_SAFETY.value] == "PASSED"

    body = result.evidence.as_dict()
    assert result.evidence.retention_ready is True
    assert body["candidate"] == candidate
    assert body["model_id"] == CANDIDATE_MODEL_IDS[candidate]
    assert body["provider_id"] == PROVIDER_ID
    assert body["gateway_class"] == "b300_litellm_proxy"
    assert body["semantic_prompts_sent"] == 0
    assert body["compatibility_gate_passed"] is True
    assert body["observed_pi_version"] == SYNTHETIC_PI_VERSION
    assert body["pi_version_is_provenance_only"] is True
    assert body["aido_requested_max_output_tokens"] is None
    assert body["models_json_omits_max_tokens"] is True
    assert all(body["compatibility_facts"].values())
    assert body["orchestrator_runtime_teardown_status"] == "SUCCEEDED"
    assert body["orchestrator_broker_shutdown_status"] == "CLOSED"
    assert body["orchestrator_generated_config_cleanup_status"] == "VERIFIED_REMOVED"

    # frozen-O1 lifecycle order, and each live adapter called exactly once
    assert harness.calls == [
        "read_connection",
        "create_broker",
        "launch_runtime",
        "get_commands",
        "get_state",
        "observe_protocol",
        "route_checker",
        "shutdown_runtime",
        "shutdown_broker",
    ]
    # the disposable config directory is really gone
    assert not (tmp_path / candidate / "i2_pi_config").exists()


def test_candidate_a_and_b_use_identical_controller_logic(tmp_path: Path) -> None:
    result_a, harness_a = _run(tmp_path / "a", candidate="A")
    result_b, harness_b = _run(tmp_path / "b", candidate="B")

    assert harness_a.calls == harness_b.calls
    assert dict(result_a.gate_statuses) == dict(result_b.gate_statuses)
    assert result_a.facts == result_b.facts
    assert result_a.outcome is result_b.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED
    assert result_a.evidence.as_dict()["model_id"] != result_b.evidence.as_dict()["model_id"]


# -- frozen O1 lifecycle: broker created and READY BEFORE the launch -----------


def test_broker_is_created_and_ready_before_the_runtime_launch(tmp_path: Path) -> None:
    result, harness = _run(tmp_path / "run")
    assert harness.calls.index("create_broker") < harness.calls.index("launch_runtime")
    assert result.gate_statuses[CategoryBGateName.BROKER_READY.value] == "PASSED"
    assert result.facts.broker_reached_required_ready_state is True


def test_launch_consumes_the_exact_broker_binding_it_needs(tmp_path: Path) -> None:
    result, harness = _run(tmp_path / "run")
    assert harness.launch_request is not None
    assert harness.launch_request.broker_session is harness.broker
    assert harness.launch_request.broker_session.pipe_name == SYNTHETIC_PIPE_NAME
    assert harness.launch_request.broker_session.capability_id == SYNTHETIC_CAPABILITY_ID
    assert harness.launch_request.broker_session.broker_token == SYNTHETIC_BROKER_TOKEN
    assert harness.launch_request.model_id == CANDIDATE_MODEL_IDS["A"]
    assert result.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED


def test_broker_not_ready_refuses_before_any_launch(tmp_path: Path) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], broker_ready=False)
    result, harness = _run(tmp_path / "run", harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.BROKER_READY
    assert result.failure_code is CategoryBFailureCode.BROKER_NOT_READY
    assert "launch_runtime" not in harness.calls
    assert result.facts.broker_reached_required_ready_state is False
    # the broker that WAS created is still closed
    assert "shutdown_broker" in harness.calls
    assert result.broker_shutdown.reached_closed is True


def test_broker_session_mismatch_refuses_before_launch_capable_continuation(
    tmp_path: Path,
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], broker_run_id_override="foreign-run-id")
    result, harness = _run(tmp_path / "run", harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.BROKER_SESSION
    assert result.failure_code is CategoryBFailureCode.BROKER_SESSION_MISMATCH
    assert "launch_runtime" not in harness.calls
    # the foreign broker is still shut down, but closure is NOT reported satisfied
    assert "shutdown_broker" in harness.calls
    assert result.broker_shutdown.closure_satisfied is False


def test_launch_request_is_unconstructible_for_a_not_ready_broker() -> None:
    broker = BrokerSession(
        run_id="run-1",
        session_id="brk-1",
        pipe_name=SYNTHETIC_PIPE_NAME,
        capability_id=SYNTHETIC_CAPABILITY_ID,
        broker_token=SYNTHETIC_BROKER_TOKEN,
        reached_ready=False,
    )
    with pytest.raises(ObservationError, match="READY"):
        RuntimeLaunchRequest(
            run_id="run-1",
            broker_session=broker,
            launch_environment=_StubLaunchEnvironment(),
            workspace_root=r"C:\synthetic\workspace",
            provider_id=PROVIDER_ID,
            model_id="qwen3-coder-next",
        )


def test_launch_request_is_unconstructible_for_a_foreign_broker() -> None:
    broker = BrokerSession(
        run_id="run-OTHER",
        session_id="brk-1",
        pipe_name=SYNTHETIC_PIPE_NAME,
        capability_id=SYNTHETIC_CAPABILITY_ID,
        broker_token=SYNTHETIC_BROKER_TOKEN,
        reached_ready=True,
    )
    with pytest.raises(ObservationError, match="different run"):
        RuntimeLaunchRequest(
            run_id="run-1",
            broker_session=broker,
            launch_environment=_StubLaunchEnvironment(),
            workspace_root=r"C:\synthetic\workspace",
            provider_id=PROVIDER_ID,
            model_id="qwen3-coder-next",
        )


class _StubLaunchEnvironment:
    """The narrowest object satisfying the launch request's env boundary."""

    def as_launch_snapshot(self) -> dict[str, str]:  # pragma: no cover - shape only
        return {}


# -- runtime/session authority binding ----------------------------------------


def test_launch_returning_a_foreign_runtime_session_is_refused(tmp_path: Path) -> None:
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"], launch_session_run_id_override="foreign-run"
    )
    result, harness = _run(tmp_path / "run", harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.RUNTIME_LAUNCH
    assert result.failure_code is CategoryBFailureCode.RUNTIME_SESSION_MISMATCH
    assert "get_commands" not in harness.calls


def test_launch_bound_to_a_foreign_broker_session_is_refused(tmp_path: Path) -> None:
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"], launch_session_broker_id_override="brk-OTHER"
    )
    result, harness = _run(tmp_path / "run", harness=harness)

    _assert_refusal(result)
    assert result.failure_code is CategoryBFailureCode.RUNTIME_SESSION_MISMATCH
    assert "get_commands" not in harness.calls


def test_get_commands_for_an_unrelated_runtime_is_refused(tmp_path: Path) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], commands_session_override="rt-OTHER")
    result, harness = _run(tmp_path / "run", harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.GET_COMMANDS
    assert result.failure_code is CategoryBFailureCode.RUNTIME_SESSION_MISMATCH
    assert "get_state" not in harness.calls


def test_get_state_for_an_unrelated_runtime_is_refused(tmp_path: Path) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], state_session_override="rt-OTHER")
    result, harness = _run(tmp_path / "run", harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.GET_STATE
    assert result.failure_code is CategoryBFailureCode.RUNTIME_SESSION_MISMATCH


def test_protocol_observation_for_an_unrelated_runtime_is_refused(tmp_path: Path) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], protocol_session_override="rt-OTHER")
    result, _ = _run(tmp_path / "run", harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.PROTOCOL_INTEGRITY
    assert result.failure_code is CategoryBFailureCode.RUNTIME_SESSION_MISMATCH


def test_teardown_of_an_unrelated_runtime_never_reports_closure(tmp_path: Path) -> None:
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"], runtime_shutdown_session_override="rt-OTHER"
    )
    result, _ = _run(tmp_path / "run", harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.RUNTIME_TEARDOWN
    assert result.failure_code is CategoryBFailureCode.RUNTIME_SESSION_MISMATCH
    assert result.runtime_teardown.closure_satisfied is False


def test_broker_shutdown_of_an_unrelated_broker_never_reports_closure(tmp_path: Path) -> None:
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"], broker_shutdown_session_id_override="brk-OTHER"
    )
    result, _ = _run(tmp_path / "run", harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.BROKER_SHUTDOWN
    assert result.broker_shutdown.closure_satisfied is False


def test_every_live_adapter_receives_the_same_runtime_session(tmp_path: Path) -> None:
    seen: list[RuntimeSession] = []
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"])
    original_get_commands = harness.get_commands
    original_get_state = harness.get_state
    original_protocol = harness.observe_protocol
    original_shutdown = harness.shutdown_runtime

    def spy_commands(session):
        seen.append(session)
        return original_get_commands(session)

    def spy_state(session):
        seen.append(session)
        return original_get_state(session)

    def spy_protocol(session):
        seen.append(session)
        return original_protocol(session)

    def spy_shutdown(session):
        seen.append(session)
        return original_shutdown(session)

    harness.get_commands = spy_commands  # type: ignore[method-assign]
    harness.get_state = spy_state  # type: ignore[method-assign]
    harness.observe_protocol = spy_protocol  # type: ignore[method-assign]
    harness.shutdown_runtime = spy_shutdown  # type: ignore[method-assign]

    result, harness = _run(tmp_path / "run", harness=harness)
    assert result.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED
    assert len(seen) == 4
    assert all(session is harness.runtime for session in seen)


# -- Pi version: observable, provenance only, and fail-closed -----------------


def test_missing_pi_version_fails_closed_even_when_everything_else_passes(
    tmp_path: Path,
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], pi_version=None)
    result, harness = _run(tmp_path / "run", harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.PI_VERSION_OBSERVED
    assert result.failure_code is CategoryBFailureCode.PI_VERSION_NOT_OBSERVED
    assert result.facts.pi_version_observed is False
    assert result.observed_pi_version is None
    # the later compatibility gates were never reached
    assert "get_commands" not in harness.calls
    # but the resources created before it were still closed
    assert result.runtime_teardown.closure_satisfied is True
    assert result.broker_shutdown.closure_satisfied is True
    assert result.cleanup.closure_satisfied is True


@pytest.mark.parametrize("bad_version", ["", "   ", "not a version", "0.84.3 (from https://x)"])
def test_blank_or_unbounded_pi_version_is_refused_at_construction(bad_version: str) -> None:
    with pytest.raises(ObservationError):
        RuntimeLaunchObservation(
            session=None,
            launch_shape_valid=False,
            required_flags_accepted=False,
            lf_jsonl_correlation_succeeded=False,
            observed_pi_version=bad_version,
            partial_resource_cleaned_internally=True,
        )


def test_pi_version_is_never_compared_against_a_pinned_value(tmp_path: Path) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], pi_version="99.0.0-rc1")
    result, _ = _run(tmp_path / "run", harness=harness)
    assert result.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED
    assert result.evidence.as_dict()["observed_pi_version"] == "99.0.0-rc1"


# -- the four independent launch facts ----------------------------------------


@pytest.mark.parametrize(
    "knob,gate,code",
    [
        (
            "launch_shape_valid",
            CategoryBGateName.RPC_LAUNCH_SHAPE,
            CategoryBFailureCode.RPC_LAUNCH_SHAPE_UNEXPECTED,
        ),
        (
            "required_flags_accepted",
            CategoryBGateName.REQUIRED_LAUNCH_FLAGS,
            CategoryBFailureCode.REQUIRED_LAUNCH_FLAGS_REJECTED,
        ),
        (
            "lf_correlation",
            CategoryBGateName.LF_JSONL_CORRELATION,
            CategoryBFailureCode.LF_JSONL_CORRELATION_FAILED,
        ),
    ],
)
def test_each_launch_fact_fails_independently(
    tmp_path: Path, knob: str, gate: CategoryBGateName, code: CategoryBFailureCode
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"])
    setattr(harness, knob, False)
    result, _ = _run(tmp_path / "run", harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is gate
    assert result.failure_code is code
    assert result.facts.all_established is False


# -- H1 and the tool registry come from ONE get_commands response -------------


def test_h1_and_tool_registry_derive_from_one_get_commands_observation(
    tmp_path: Path,
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"])
    result, harness = _run(tmp_path / "run", harness=harness)

    assert harness.calls.count("get_commands") == 1
    assert result.facts.h1_extension_identity_matched is True
    assert result.facts.authorized_tool_registry_exact is True
    assert result.gate_statuses[CategoryBGateName.H1_EXTENSION_IDENTITY.value] == "PASSED"
    assert result.gate_statuses[CategoryBGateName.TOOL_REGISTRY.value] == "PASSED"
    # the controller has NO separate H1 adapter it could correlate wrongly
    signature = inspect.signature(run_category_b_controller)
    assert "h1_check" not in signature.parameters
    assert "broker_ready" not in signature.parameters


def test_h1_failure_and_registry_failure_are_distinct_facts(tmp_path: Path) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], h1_matched=False)
    result, _ = _run(tmp_path / "run", harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.H1_EXTENSION_IDENTITY
    assert result.failure_code is CategoryBFailureCode.H1_EXTENSION_IDENTITY_MISMATCH
    assert result.facts.h1_extension_identity_matched is False
    # the registry was still evaluated from the same response, and passed
    assert result.facts.authorized_tool_registry_exact is True
    assert result.gate_statuses[CategoryBGateName.TOOL_REGISTRY.value] == "PASSED"


def test_an_unusable_get_commands_response_cannot_also_claim_h1(tmp_path: Path) -> None:
    with pytest.raises(ObservationError):
        GetCommandsObservation(
            runtime_session_id="rt-1",
            call_succeeded=False,
            response_shape_understood=False,
            extension_identity_matched=True,
            commands=(),
        )
    with pytest.raises(ObservationError):
        GetCommandsObservation(
            runtime_session_id="rt-1",
            call_succeeded=True,
            response_shape_understood=False,
            extension_identity_matched=True,
            commands=(),
        )


@pytest.mark.parametrize(
    "commands",
    [
        # a duplicated entry -- a set comparison would have collapsed this
        (
            ObservedCommand(name="aido_read", source="extension"),
            ObservedCommand(name="aido_read", source="extension"),
            ObservedCommand(name="aido_edit", source="extension"),
        ),
        # a duplicate that HIDES a missing authorized command
        (
            ObservedCommand(name="aido_read", source="extension"),
            ObservedCommand(name="aido_read", source="builtin"),
        ),
        # an extra command
        (
            ObservedCommand(name="aido_read", source="extension"),
            ObservedCommand(name="aido_edit", source="extension"),
            ObservedCommand(name="bash", source="builtin"),
        ),
        # a missing command
        (ObservedCommand(name="aido_read", source="extension"),),
        # nothing at all
        (),
    ],
)
def test_tool_registry_fails_closed_on_a_malformed_or_duplicated_list(
    tmp_path: Path, commands
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], commands=commands)
    result, _ = _run(tmp_path / "run", harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.TOOL_REGISTRY
    assert result.failure_code is CategoryBFailureCode.TOOL_REGISTRY_MISMATCH
    assert result.facts.authorized_tool_registry_exact is False


def test_an_unbounded_reported_command_list_is_refused() -> None:
    entries = tuple(
        ObservedCommand(name=f"cmd_{index}", source="builtin") for index in range(257)
    )
    with pytest.raises(ObservationError, match="bounded reported-command count"):
        GetCommandsObservation(
            runtime_session_id="rt-1",
            call_succeeded=True,
            response_shape_understood=True,
            extension_identity_matched=True,
            commands=entries,
        )


def test_duplicate_names_do_not_collapse_into_a_set() -> None:
    observation = GetCommandsObservation(
        runtime_session_id="rt-1",
        call_succeeded=True,
        response_shape_understood=True,
        extension_identity_matched=True,
        commands=(
            ObservedCommand(name="aido_read", source="extension"),
            ObservedCommand(name="aido_read", source="extension"),
        ),
    )
    assert observation.command_names_in_report_order() == ("aido_read", "aido_read")
    assert tuple(sorted(observation.command_names_in_report_order())) != AUTHORIZED_TOOL_NAMES


@pytest.mark.parametrize(
    "entry",
    [
        {"name": "aido_read", "source": "extension"},
        "aido_read",
        None,
    ],
)
def test_a_non_observed_command_entry_is_refused(entry) -> None:
    with pytest.raises(ObservationError):
        GetCommandsObservation(
            runtime_session_id="rt-1",
            call_succeeded=True,
            response_shape_understood=True,
            extension_identity_matched=True,
            commands=(entry,),
        )


@pytest.mark.parametrize(
    "name",
    ["", "  ", "aido read", r"C:\pi\commands\aido_read.js", "https://evil.example/x", "x" * 65],
)
def test_a_malformed_command_name_is_refused_at_construction(name: str) -> None:
    with pytest.raises(ObservationError):
        ObservedCommand(name=name, source="extension")


# -- H2 from ONE get_state response -------------------------------------------


def test_h2_mismatch_is_a_distinct_fact_from_get_state(tmp_path: Path) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], reported_model="some-other-model")
    result, _ = _run(tmp_path / "run", harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.H2_PROVIDER_MODEL_IDENTITY
    assert result.facts.get_state_response_shape_understood is True
    assert result.facts.h2_provider_model_identity_matched is False


def test_h2_provider_mismatch_fails_closed(tmp_path: Path) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], reported_provider="openai")
    result, _ = _run(tmp_path / "run", harness=harness)
    _assert_refusal(result)
    assert result.failure_code is CategoryBFailureCode.H2_PROVIDER_MODEL_IDENTITY_MISMATCH


def test_an_unusable_get_state_response_cannot_also_claim_an_identity() -> None:
    with pytest.raises(ObservationError):
        GetStateObservation(
            runtime_session_id="rt-1",
            call_succeeded=False,
            response_shape_understood=False,
            reported_provider=PROVIDER_ID,
            reported_model="qwen3-coder-next",
        )


def test_get_state_call_failure_is_reported_as_such(tmp_path: Path) -> None:
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"],
        state_call_succeeded=False,
        state_shape_understood=False,
        reported_provider=None,
        reported_model="",
    )
    harness.reported_model = None
    # a failed call reports no identity at all
    harness.reported_provider = None
    result, _ = _run(tmp_path / "run", harness=harness)
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.GET_STATE


# -- protocol / extension errors ----------------------------------------------


def test_a_protocol_violation_is_an_explicit_compatibility_failure(tmp_path: Path) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], protocol_violation=True)
    result, _ = _run(tmp_path / "run", harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.PROTOCOL_INTEGRITY
    assert result.failure_code is CategoryBFailureCode.PROTOCOL_VIOLATION_OBSERVED
    assert result.facts.no_protocol_violation_observed is False


def test_an_extension_error_is_an_explicit_compatibility_failure(tmp_path: Path) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], extension_error=True)
    result, _ = _run(tmp_path / "run", harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.PROTOCOL_INTEGRITY
    assert result.failure_code is CategoryBFailureCode.EXTENSION_ERROR_OBSERVED
    assert result.facts.no_extension_error_observed is False


# -- route check ---------------------------------------------------------------


@pytest.mark.parametrize(
    "reachable,served", [(False, False), (True, False)]
)
def test_route_check_failure_refuses(tmp_path: Path, reachable: bool, served: bool) -> None:
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"], route_reachable=reachable, route_model_served=served
    )
    result, _ = _run(tmp_path / "run", harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.ROUTE_CHECK
    assert result.facts.exact_candidate_model_served is False


# -- THE TERMINAL RULE: compatibility alone is never enough -------------------


def test_all_gates_pass_but_runtime_teardown_fails_is_an_infrastructure_refusal(
    tmp_path: Path,
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], runtime_child_exited=False)
    result, _ = _run(tmp_path / "run", harness=harness)

    assert result.facts.all_established is True
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.RUNTIME_TEARDOWN
    assert result.failure_code is CategoryBFailureCode.RUNTIME_TEARDOWN_FAILED
    assert result.evidence.as_dict().get("compatibility_gate_passed") is not True


def test_all_gates_pass_but_runtime_teardown_raises_is_an_infrastructure_refusal(
    tmp_path: Path,
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], runtime_shutdown_raises=True)
    result, _ = _run(tmp_path / "run", harness=harness)

    assert result.facts.all_established is True
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.RUNTIME_TEARDOWN


def test_all_gates_pass_but_broker_shutdown_incomplete_is_an_infrastructure_refusal(
    tmp_path: Path,
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], broker_reached_closed=False)
    result, _ = _run(tmp_path / "run", harness=harness)

    assert result.facts.all_established is True
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.BROKER_SHUTDOWN
    assert result.failure_code is CategoryBFailureCode.BROKER_SHUTDOWN_INCOMPLETE


def test_all_gates_pass_but_config_cleanup_fails_is_an_infrastructure_refusal(
    tmp_path: Path,
) -> None:
    """Filesystem tampering: the disposable config's authority marker is
    removed behind the controller's back, so cleanup can no longer be
    authorized and the removal is therefore never verified."""
    root = tmp_path / "run"
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"])
    original_protocol = harness.observe_protocol

    def tamper_then_observe(session):
        for marker in (root / "i2_pi_config").glob("*"):
            if marker.name not in ("settings.json", "models.json"):
                marker.unlink()
        return original_protocol(session)

    harness.observe_protocol = tamper_then_observe  # type: ignore[method-assign]
    result, _ = _run(root, harness=harness)

    assert result.facts.all_established is True
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.GENERATED_CONFIG_CLEANUP
    assert result.failure_code is CategoryBFailureCode.GENERATED_CONFIG_CLEANUP_UNVERIFIED
    assert result.cleanup.attempted is True
    assert result.cleanup.scrub_verified is False
    assert result.cleanup.classification is not None
    assert result.cleanup.classification.semantic_prompts_sent == 0


def test_evidence_scrub_refusal_prevents_a_category_b_pass(tmp_path: Path) -> None:
    """The declared API-key needle is deliberately made to collide with a
    value the evidence body legitimately carries, so the scrub gate refuses.
    A refused evidence body is never a Category-B pass, and is never
    retained in any form."""
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"], api_key=CANDIDATE_MODEL_IDS["A"]
    )
    result, _ = _run(tmp_path / "run", harness=harness)

    assert result.facts.all_established is True
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.EVIDENCE_SAFETY
    assert result.failure_code is CategoryBFailureCode.EVIDENCE_SCRUB_REFUSED
    assert result.evidence.retention_ready is False
    assert result.evidence.scrub_clean is False
    assert "api_key_value_present" in result.evidence.scrub_findings
    assert result.evidence.as_dict() == {}
    assert result.evidence.as_json() == ""


def test_a_pass_can_never_be_constructed_alongside_a_failed_closure(tmp_path: Path) -> None:
    result, _ = _run(tmp_path / "run")

    with pytest.raises(ValueError, match="teardown/cleanup"):
        CategoryBControllerResult(
            candidate="A",
            outcome=CategoryBOutcome.CATEGORY_B_GATE_PASSED,
            semantic_prompts_sent=0,
            failed_gate=None,
            failure_code=None,
            facts=CompatibilityFacts(
                **{name: True for name in CompatibilityFacts().as_dict()}
            ),
            observed_pi_version=SYNTHETIC_PI_VERSION,
            pi_config_created=True,
            broker_created=True,
            runtime_session_established=True,
            runtime_teardown=i2b_controller_module.RuntimeTeardownStatus(
                launch_attempted=True,
                closed_by_creator=False,
                authority_available=True,
                attempted=True,
                succeeded=False,
                failure_code=CategoryBFailureCode.RUNTIME_TEARDOWN_FAILED,
            ),
            broker_shutdown=result.broker_shutdown,
            cleanup=result.cleanup,
            evidence=result.evidence,
        )


def test_a_pass_requires_every_compatibility_fact(tmp_path: Path) -> None:
    result, _ = _run(tmp_path / "run")
    with pytest.raises(ValueError, match="every compatibility fact"):
        dataclasses.replace(result, facts=CompatibilityFacts())


def test_a_pass_requires_retention_ready_evidence() -> None:
    with pytest.raises(ValueError, match="retention-ready"):
        CategoryBControllerResult(
            candidate="A",
            outcome=CategoryBOutcome.CATEGORY_B_GATE_PASSED,
            semantic_prompts_sent=0,
            failed_gate=None,
            failure_code=None,
            facts=CompatibilityFacts(**{name: True for name in CompatibilityFacts().as_dict()}),
            observed_pi_version=SYNTHETIC_PI_VERSION,
            pi_config_created=False,
            broker_created=False,
            runtime_session_established=False,
            runtime_teardown=i2b_controller_module.RuntimeTeardownStatus(
                launch_attempted=False,
                closed_by_creator=False,
                authority_available=False,
                attempted=False,
                succeeded=False,
                failure_code=None,
            ),
            broker_shutdown=i2b_controller_module.BrokerShutdownStatus(
                creation_attempted=False,
                authority_available=False,
                attempted=False,
                reached_closed=False,
                failure_code=None,
            ),
            cleanup=i2b_controller_module.CleanupStatus(
                attempted=False, scrub_verified=None, classification=None
            ),
            evidence=CategoryBEvidence(
                retention_ready=False, scrub_clean=False, scrub_findings=("x",)
            ),
        )


# -- partial-resource accounting ----------------------------------------------


def test_a_failed_launch_that_cleaned_itself_strands_nothing(tmp_path: Path) -> None:
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"],
        launch_returns_no_session=True,
        launch_cleaned_internally=True,
    )
    result, harness = _run(tmp_path / "run", harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.RUNTIME_LAUNCH
    assert result.failure_code is CategoryBFailureCode.RUNTIME_LAUNCH_FAILED
    assert result.runtime_teardown.closed_by_creator is True
    assert result.runtime_teardown.attempted is False
    assert result.runtime_teardown.closure_satisfied is True
    assert "shutdown_runtime" not in harness.calls
    # the broker and the disposable config are still closed/removed
    assert result.broker_shutdown.reached_closed is True
    assert result.cleanup.scrub_verified is True


def test_a_stranding_launch_observation_is_unconstructible() -> None:
    with pytest.raises(ObservationError, match="stranded partial resource"):
        RuntimeLaunchObservation(
            session=None,
            launch_shape_valid=False,
            required_flags_accepted=True,
            lf_jsonl_correlation_succeeded=False,
            observed_pi_version=SYNTHETIC_PI_VERSION,
            partial_resource_cleaned_internally=False,
        )


def test_a_session_bearing_launch_cannot_also_claim_internal_cleanup() -> None:
    session = RuntimeSession(run_id="r", broker_session_id="b", runtime_session_id="rt")
    with pytest.raises(ObservationError, match="cleaned its partial resource"):
        RuntimeLaunchObservation(
            session=session,
            launch_shape_valid=True,
            required_flags_accepted=True,
            lf_jsonl_correlation_succeeded=True,
            observed_pi_version=SYNTHETIC_PI_VERSION,
            partial_resource_cleaned_internally=True,
        )


def test_a_launch_adapter_that_raises_leaves_teardown_authority_unavailable(
    tmp_path: Path,
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], launch_raises=True)
    result, harness = _run(tmp_path / "run", harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.RUNTIME_LAUNCH
    assert result.failure_code is CategoryBFailureCode.ADAPTER_RAISED
    assert result.runtime_teardown.launch_attempted is True
    assert result.runtime_teardown.authority_available is False
    assert result.runtime_teardown.closure_satisfied is False
    assert (
        result.runtime_teardown.failure_code
        is CategoryBFailureCode.RUNTIME_TEARDOWN_AUTHORITY_UNAVAILABLE
    )
    # the broker AIDO does hold authority over is still closed
    assert "shutdown_broker" in harness.calls
    assert result.broker_shutdown.reached_closed is True
    assert result.cleanup.scrub_verified is True


def test_a_broker_adapter_that_raises_leaves_no_launch_and_no_authority(
    tmp_path: Path,
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], broker_raises=True)
    result, harness = _run(tmp_path / "run", harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.BROKER_SESSION
    assert result.failure_code is CategoryBFailureCode.BROKER_CREATION_FAILED
    assert "launch_runtime" not in harness.calls
    assert "shutdown_broker" not in harness.calls
    assert result.broker_shutdown.authority_available is False
    assert result.broker_shutdown.closure_satisfied is False
    # the disposable config is still removed
    assert result.cleanup.scrub_verified is True


def test_teardown_and_shutdown_are_each_attempted_exactly_once(tmp_path: Path) -> None:
    result, harness = _run(tmp_path / "run")
    assert harness.calls.count("shutdown_runtime") == 1
    assert harness.calls.count("shutdown_broker") == 1
    assert result.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED


def test_teardown_order_is_runtime_then_broker(tmp_path: Path) -> None:
    _, harness = _run(tmp_path / "run")
    assert harness.calls.index("shutdown_runtime") < harness.calls.index("shutdown_broker")


# -- malformed adapter results ------------------------------------------------


@pytest.mark.parametrize("bad", [None, "ok", 1, object()])
def test_a_malformed_launch_result_fails_closed_without_crashing(tmp_path: Path, bad) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], launch_result_override=bad)
    if bad is None:
        # a None override means "use the normal path"; force it explicitly
        harness.launch_result_override = None

        def none_launch(request):
            harness.calls.append("launch_runtime")
            harness.launch_request = request
            return None

        harness.launch_runtime = none_launch  # type: ignore[method-assign]
    result, _ = _run(tmp_path / "run", harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.RUNTIME_LAUNCH
    assert result.failure_code is CategoryBFailureCode.MALFORMED_ADAPTER_RESULT


def test_a_malformed_broker_result_fails_closed(tmp_path: Path) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], broker_result_override="not-a-session")
    result, harness = _run(tmp_path / "run", harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.BROKER_SESSION
    assert result.failure_code is CategoryBFailureCode.MALFORMED_ADAPTER_RESULT
    assert "launch_runtime" not in harness.calls


def test_a_malformed_get_commands_result_fails_closed(tmp_path: Path) -> None:
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"], commands_result_override={"commands": []}
    )
    result, _ = _run(tmp_path / "run", harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.GET_COMMANDS
    assert result.failure_code is CategoryBFailureCode.MALFORMED_ADAPTER_RESULT


@pytest.mark.parametrize("value", ["true", 1, 0, None])
def test_a_non_bool_observation_flag_is_refused(value) -> None:
    with pytest.raises(ObservationError):
        ProtocolObservation(
            runtime_session_id="rt-1",
            protocol_violation_observed=value,
            extension_error_observed=False,
        )
    with pytest.raises(ObservationError):
        BrokerSession(
            run_id="r",
            session_id="b",
            pipe_name=SYNTHETIC_PIPE_NAME,
            capability_id=SYNTHETIC_CAPABILITY_ID,
            broker_token=SYNTHETIC_BROKER_TOKEN,
            reached_ready=value,
        )


def test_a_subclass_of_an_observation_type_is_refused(tmp_path: Path) -> None:
    """A subclass could re-declare a validated field as a property that
    returns a different value on each read, defeating both the exact-bool
    rule and the session-id comparisons. The adapter boundary therefore
    requires the EXACT type, not merely an instance of it."""

    class _SubclassedBrokerSession(BrokerSession):
        """Passes ``__post_init__`` and every ``isinstance`` check."""

        def alternate_session_id(self) -> str:  # pragma: no cover - shape only
            return "brk-OTHER"

    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"])
    subclassed = _SubclassedBrokerSession(
        run_id="placeholder-run",
        session_id="brk-session-0001",
        pipe_name=SYNTHETIC_PIPE_NAME,
        capability_id=SYNTHETIC_CAPABILITY_ID,
        broker_token=SYNTHETIC_BROKER_TOKEN,
        reached_ready=True,
    )
    assert isinstance(subclassed, BrokerSession)
    assert type(subclassed) is not BrokerSession

    def subclassing_create_broker(request: BrokerCreationRequest) -> BrokerSession:
        harness.calls.append("create_broker")
        return _SubclassedBrokerSession(
            run_id=request.run_id,
            session_id="brk-session-0001",
            pipe_name=SYNTHETIC_PIPE_NAME,
            capability_id=SYNTHETIC_CAPABILITY_ID,
            broker_token=SYNTHETIC_BROKER_TOKEN,
            reached_ready=True,
        )

    harness.create_broker = subclassing_create_broker  # type: ignore[method-assign]
    result, harness = _run(tmp_path / "run", harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.BROKER_SESSION
    assert result.failure_code is CategoryBFailureCode.MALFORMED_ADAPTER_RESULT
    assert "launch_runtime" not in harness.calls


def test_a_failing_launch_fact_stops_every_further_live_call(tmp_path: Path) -> None:
    """A failed compatibility fact must not be followed by more live RPC
    calls, even when the fact that failed was free to derive from an
    observation already in hand."""
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], required_flags_accepted=False)
    result, harness = _run(tmp_path / "run", harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.REQUIRED_LAUNCH_FLAGS
    assert "get_commands" not in harness.calls
    assert "get_state" not in harness.calls
    assert "observe_protocol" not in harness.calls
    assert "route_checker" not in harness.calls
    # but the facts already derivable from the launch observation are kept
    assert result.facts.pi_version_observed is True
    assert result.facts.rpc_launch_shape_valid is True
    assert result.facts.lf_jsonl_correlation_succeeded is True


def test_a_failed_h1_stops_the_next_live_call_even_though_the_registry_passed(
    tmp_path: Path,
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], h1_matched=False)
    result, harness = _run(tmp_path / "run", harness=harness)

    _assert_refusal(result)
    assert result.facts.authorized_tool_registry_exact is True
    assert "get_state" not in harness.calls
    assert "observe_protocol" not in harness.calls


def test_a_closure_gate_never_inherits_another_gates_failure_code(tmp_path: Path) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], runtime_child_exited=False)
    result, _ = _run(tmp_path / "run", harness=harness)
    statuses = result.gate_statuses
    assert statuses[CategoryBGateName.RUNTIME_TEARDOWN.value].startswith("FAILED:RUNTIME_TEARDOWN")
    assert statuses[CategoryBGateName.BROKER_SHUTDOWN.value] == "CLOSED"
    assert statuses[CategoryBGateName.GENERATED_CONFIG_CLEANUP.value] == "VERIFIED_REMOVED"


def test_command_source_is_recorded_but_is_not_part_of_the_registry_rule(
    tmp_path: Path,
) -> None:
    """I2A Sec. 15 item 6 defines the registry gate over the registered
    command SET. Extension provenance is H1's job, proven separately from
    the same response -- this slice does not invent a second source rule."""
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"],
        commands=(
            ObservedCommand(name="aido_read", source="extension"),
            ObservedCommand(name="aido_edit", source="extension"),
        ),
    )
    result, _ = _run(tmp_path / "run", harness=harness)
    assert result.facts.authorized_tool_registry_exact is True
    assert result.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED


# -- credential-read ordering (reused I2-4 wiring) ----------------------------


def test_the_connection_reader_is_never_called_before_the_non_secret_gates_pass(
    tmp_path: Path,
) -> None:
    calls = {"n": 0}

    def counting_reader() -> ConnectionValues:
        calls["n"] += 1
        return ConnectionValues(base_url=SYNTHETIC_BASE_URL, api_key=SYNTHETIC_API_KEY)

    failing_gates = [
        lambda: PreflightGateResult(name="pi_installed_offline", passed=True),
        lambda: PreflightGateResult(
            name="config_generator_self_check", passed=False, failure_code="SCHEMA_INVALID"
        ),
    ]
    result, harness = _run(
        tmp_path / "run", non_secret_gates=failing_gates, read_connection=counting_reader
    )

    assert calls["n"] == 0
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.NON_SECRET_PREFLIGHT
    assert result.failure_code is CategoryBFailureCode.NON_SECRET_PREFLIGHT_GATE_FAILED
    # no live resource of any kind was created
    assert harness.calls == []
    assert result.pi_config_created is False
    assert result.broker_created is False
    assert result.runtime_session_established is False


def test_an_unavailable_connection_value_is_a_zero_prompt_refusal(tmp_path: Path) -> None:
    from qualification.i2_credentials import ConnectionValueError

    def failing_reader() -> ConnectionValues:
        raise ConnectionValueError("AIDO_LITELLM_API_KEY is unset or blank")

    result, _ = _run(tmp_path / "run", read_connection=failing_reader)
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.CONNECTION_VALUES
    assert result.failure_code is CategoryBFailureCode.CONNECTION_VALUES_UNAVAILABLE


@pytest.mark.parametrize(
    "argument", ["candidate", "experiment_root", "workspace_root", "node_executable"]
)
def test_an_unusable_controller_argument_refuses_before_any_credential_read(
    tmp_path: Path, argument: str
) -> None:
    """Second-pass finding: a blank ``workspace_root`` ran the whole
    credential-read and config-generation sequence and only failed at broker
    creation -- reading a credential for a run that could never produce
    provably safe evidence, since the workspace needle would be empty."""
    reads = {"n": 0}

    def counting_reader() -> ConnectionValues:
        reads["n"] += 1
        return ConnectionValues(base_url=SYNTHETIC_BASE_URL, api_key=SYNTHETIC_API_KEY)

    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"])
    root = tmp_path / "run"
    root.mkdir(parents=True)
    kwargs = dict(
        candidate="A",
        experiment_root=str(root),
        workspace_root=str(root / "workspace"),
        node_executable=str(root / "node.exe"),
    )
    kwargs[argument] = "   "

    with pytest.raises(i2b_controller_module.CategoryBControllerInputError, match=argument):
        run_category_b_controller(
            ambient_environ={"SystemRoot": r"C:\Windows"},
            non_secret_gates=_passing_non_secret_gates(),
            read_connection=counting_reader,
            create_broker=harness.create_broker,
            launch_runtime=harness.launch_runtime,
            get_commands=harness.get_commands,
            get_state=harness.get_state,
            observe_protocol=harness.observe_protocol,
            route_checker=harness.route_checker,
            shutdown_runtime=harness.shutdown_runtime,
            shutdown_broker=harness.shutdown_broker,
            **kwargs,
        )
    assert reads["n"] == 0
    assert harness.calls == []


def test_a_stale_broker_session_from_a_previous_run_is_refused(tmp_path: Path) -> None:
    """A cached/leftover broker session object cannot be reused across
    invocations: the per-run correlation nonce will not match."""
    first, first_harness = _run(tmp_path / "first")
    assert first.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED
    stale = first_harness.broker
    assert stale is not None

    second = _Harness(model_id=CANDIDATE_MODEL_IDS["A"])

    def replay_stale_broker(request: BrokerCreationRequest) -> BrokerSession:
        second.calls.append("create_broker")
        second.broker = stale
        return stale

    second.create_broker = replay_stale_broker  # type: ignore[method-assign]
    result, second = _run(tmp_path / "second", harness=second)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.BROKER_SESSION
    assert result.failure_code is CategoryBFailureCode.BROKER_SESSION_MISMATCH
    assert "launch_runtime" not in second.calls


def test_the_controller_can_be_re_run_against_the_same_experiment_root(
    tmp_path: Path,
) -> None:
    """Cleanup really removed the disposable config, so a second run can
    generate its own -- no leftover blocks it and no state carries over."""
    root = tmp_path / "shared"
    first, _ = _run(root)
    assert first.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED
    assert not (root / "i2_pi_config").exists()

    second, _ = _run(root)
    assert second.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED
    assert not (root / "i2_pi_config").exists()


def test_an_unknown_candidate_is_refused_before_any_secret_context(tmp_path: Path) -> None:
    harness = _Harness(model_id="qwen3-coder-next")
    result, harness = _run(tmp_path / "run", candidate="Z", harness=harness)
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.ROUTE_DESCRIPTOR
    assert result.failure_code is CategoryBFailureCode.ROUTE_DESCRIPTOR_INVALID
    assert result.pi_config_created is False


# -- the FULL artifact safety context -----------------------------------------

_ALL_NEEDLE_CODES = {
    "endpoint_host_value_present",
    "api_key_value_present",
    "broker_token_present",
    "broker_pipe_name_present",
    "broker_capability_id_present",
    "workspace_absolute_path_present",
}


def test_the_run_safety_context_declares_every_available_sensitive_value(
    tmp_path: Path,
) -> None:
    result, _ = _run(tmp_path / "run")
    declared = set(result.evidence.as_dict()["safety_context_declared_needle_codes"])
    assert declared == _ALL_NEEDLE_CODES


def test_bearer_token_absence_is_derived_from_the_frozen_credential_mechanism() -> None:
    from qualification.i2_route import CREDENTIAL_MECHANISM, route_descriptor_for_candidate
    from qualification.i2_secret_context import build_secret_context

    descriptor = route_descriptor_for_candidate("A")
    assert descriptor.credential_mechanism == CREDENTIAL_MECHANISM == "models_json_env_interpolation"
    secret = build_secret_context(
        base_url=SYNTHETIC_BASE_URL, api_key=SYNTHETIC_API_KEY, model_id=descriptor.model_id
    )
    broker = BrokerSession(
        run_id="r",
        session_id="b",
        pipe_name=SYNTHETIC_PIPE_NAME,
        capability_id=SYNTHETIC_CAPABILITY_ID,
        broker_token=SYNTHETIC_BROKER_TOKEN,
        reached_ready=True,
    )
    safety = build_run_safety_context(
        secret_context=secret,
        broker_session=broker,
        workspace_root=r"C:\synthetic\workspace",
        route_descriptor=descriptor,
    )
    # this route mints no separate bearer value at all -- a PROVEN absence
    assert safety.bearer_token is None
    assert safety.endpoint_host == "b300-proxy.example.invalid"
    assert safety.api_key == SYNTHETIC_API_KEY
    assert safety.broker_token == SYNTHETIC_BROKER_TOKEN
    assert safety.pipe_name == SYNTHETIC_PIPE_NAME
    assert safety.capability_id == SYNTHETIC_CAPABILITY_ID
    assert safety.workspace_absolute_path == r"C:\synthetic\workspace"


def test_an_unexpected_credential_mechanism_refuses_rather_than_guessing() -> None:
    """``bearer_token=None`` is a PROVEN absence, derived from the frozen
    credential mechanism -- never an omission. A descriptor reporting any
    other mechanism refuses instead of assuming."""

    @dataclass(frozen=True)
    class _OtherMechanismDescriptor:
        credential_mechanism: str = "authorization_bearer_header"

    with pytest.raises(i2b_controller_module.CategoryBSafetyContextError):
        build_run_safety_context(
            secret_context=None,
            broker_session=None,
            workspace_root=r"C:\synthetic\workspace",
            route_descriptor=_OtherMechanismDescriptor(),  # type: ignore[arg-type]
        )


def test_an_early_failure_still_declares_the_values_it_does_have() -> None:
    safety = build_run_safety_context(
        secret_context=None,
        broker_session=None,
        workspace_root=r"C:\synthetic\workspace",
        route_descriptor=None,
    )
    codes = {code for code, _ in safety.forbidden_needles()}
    assert codes == {"workspace_absolute_path_present"}


def test_no_broker_binding_or_credential_value_reaches_the_evidence(tmp_path: Path) -> None:
    result, _ = _run(tmp_path / "run")
    body = result.evidence.as_json()
    for secret in (
        SYNTHETIC_API_KEY,
        SYNTHETIC_BROKER_TOKEN,
        SYNTHETIC_CAPABILITY_ID,
        "b300-proxy.example.invalid",
        r"\\.\pipe",
    ):
        assert secret not in body
    assert "http" not in body
    assert str(tmp_path) not in body
    # the DECLARED needle CODES are safe metadata and are deliberately present
    assert "broker_pipe_name_present" in body


def test_the_safety_context_repr_never_prints_a_value() -> None:
    safety = build_run_safety_context(
        secret_context=None,
        broker_session=BrokerSession(
            run_id="r",
            session_id="b",
            pipe_name=SYNTHETIC_PIPE_NAME,
            capability_id=SYNTHETIC_CAPABILITY_ID,
            broker_token=SYNTHETIC_BROKER_TOKEN,
            reached_ready=True,
        ),
        workspace_root=r"C:\synthetic\workspace",
        route_descriptor=None,
    )
    rendered = repr(safety)
    assert SYNTHETIC_BROKER_TOKEN not in rendered
    assert SYNTHETIC_PIPE_NAME not in rendered
    assert SYNTHETIC_CAPABILITY_ID not in rendered


def test_the_broker_session_repr_never_prints_its_binding() -> None:
    broker = BrokerSession(
        run_id="r",
        session_id="b",
        pipe_name=SYNTHETIC_PIPE_NAME,
        capability_id=SYNTHETIC_CAPABILITY_ID,
        broker_token=SYNTHETIC_BROKER_TOKEN,
        reached_ready=True,
    )
    rendered = repr(broker)
    assert SYNTHETIC_BROKER_TOKEN not in rendered
    assert SYNTHETIC_PIPE_NAME not in rendered
    assert SYNTHETIC_CAPABILITY_ID not in rendered
    assert "<bound>" in rendered


# -- result / evidence integrity ----------------------------------------------


def test_gate_statuses_cannot_be_rewritten_after_construction(tmp_path: Path) -> None:
    result, _ = _run(tmp_path / "run")
    with pytest.raises(TypeError):
        result.gate_statuses[CategoryBGateName.BROKER_READY.value] = "FAILED:anything"  # type: ignore[index]
    # a copy taken from the read-only view is independent
    snapshot = dict(result.gate_statuses)
    snapshot[CategoryBGateName.BROKER_READY.value] = "TAMPERED"
    assert result.gate_statuses[CategoryBGateName.BROKER_READY.value] == "PASSED"


def test_the_result_object_itself_is_frozen(tmp_path: Path) -> None:
    result, _ = _run(tmp_path / "run")
    for attribute, value in (
        ("outcome", CategoryBOutcome.INFRASTRUCTURE_REFUSAL),
        ("failure_code", CategoryBFailureCode.ROUTE_CHECK_FAILED),
        ("semantic_prompts_sent", 1),
    ):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(result, attribute, value)


def test_the_evidence_body_cannot_be_mutated_through_any_supported_api(
    tmp_path: Path,
) -> None:
    result, _ = _run(tmp_path / "run")
    first = result.evidence.as_dict()
    first["compatibility_gate_passed"] = False
    first["gate_statuses"][CategoryBGateName.BROKER_READY.value] = "TAMPERED"
    first["compatibility_facts"]["h1_extension_identity_matched"] = False

    second = result.evidence.as_dict()
    assert second["compatibility_gate_passed"] is True
    assert second["gate_statuses"][CategoryBGateName.BROKER_READY.value] == "PASSED"
    assert second["compatibility_facts"]["h1_extension_identity_matched"] is True
    assert first is not second


def test_the_evidence_scrub_result_is_immutable(tmp_path: Path) -> None:
    result, _ = _run(tmp_path / "run")
    assert isinstance(result.evidence.scrub_findings, tuple)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.evidence.scrub_clean = False  # type: ignore[misc]
    with pytest.raises(AttributeError):
        result.evidence.scrub_findings.append("x")  # type: ignore[attr-defined]


def test_compatibility_facts_are_immutable_and_copy_on_read(tmp_path: Path) -> None:
    result, _ = _run(tmp_path / "run")
    snapshot = result.facts.as_dict()
    snapshot["h2_provider_model_identity_matched"] = False
    assert result.facts.as_dict()["h2_provider_model_identity_matched"] is True
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.facts.pi_version_observed = False  # type: ignore[misc]


def test_a_retained_evidence_body_is_never_kept_after_a_scrub_refusal() -> None:
    with pytest.raises(ValueError, match="never retained"):
        CategoryBEvidence(
            retention_ready=False,
            scrub_clean=False,
            scrub_findings=("api_key_value_present",),
            _serialized='{"compatibility_gate_passed": true}',
        )


def test_an_evidence_scrub_result_cannot_disagree_with_itself() -> None:
    """Second-pass finding: a 'clean' scrub carrying findings (or a 'dirty'
    one carrying none) was constructible, which would let a validated
    evidence object describe a scrub outcome that never happened."""
    with pytest.raises(ValueError, match="agree exactly"):
        CategoryBEvidence(
            retention_ready=True,
            scrub_clean=True,
            scrub_findings=("api_key_value_present",),
            _serialized="{}",
        )
    with pytest.raises(ValueError, match="agree exactly"):
        CategoryBEvidence(retention_ready=False, scrub_clean=False, scrub_findings=())


def test_a_teardown_status_cannot_claim_closure_without_a_launch() -> None:
    """Second-pass finding: ``closed_by_creator`` with no launch reported
    ``closure_satisfied`` for a resource that never existed."""
    with pytest.raises(ValueError, match="no launch was attempted"):
        i2b_controller_module.RuntimeTeardownStatus(
            launch_attempted=False,
            closed_by_creator=True,
            authority_available=False,
            attempted=False,
            succeeded=False,
            failure_code=None,
        )
    with pytest.raises(ValueError, match="creator already closed"):
        i2b_controller_module.RuntimeTeardownStatus(
            launch_attempted=True,
            closed_by_creator=True,
            authority_available=True,
            attempted=True,
            succeeded=True,
            failure_code=None,
        )


def test_a_broker_status_cannot_claim_closure_without_a_creation() -> None:
    """Second-pass finding: a shutdown could be reported for a broker whose
    creation was never attempted."""
    with pytest.raises(ValueError, match="no broker creation was attempted"):
        i2b_controller_module.BrokerShutdownStatus(
            creation_attempted=False,
            authority_available=True,
            attempted=True,
            reached_closed=True,
            failure_code=None,
        )


def test_facts_reject_non_bool_values() -> None:
    with pytest.raises(ValueError, match="exactly a bool"):
        CompatibilityFacts(pi_version_observed="true")  # type: ignore[arg-type]


# -- ZERO-PROMPT AUTHORITY ----------------------------------------------------

_I2B_MODULES = (i2b_controller_module, i2b_session_module)

#: Fragments that, appearing in a NAME (an identifier, attribute, parameter,
#: function or class), would mean this slice had grown a way to carry a
#: semantic prompt. Checked against names only -- never against prose, since
#: this module's own documentation must be free to SAY the word "prompt".
_PROMPT_SHAPED_NAME_FRAGMENTS = (
    "prompt",
    "message",
    "chat",
    "completion",
    "inference",
    "agent_start",
    "instruction",
)

#: The only names allowed to contain one of the fragments above: the
#: zero-valued prompt counter itself, and the result/evidence field that
#: reports it.
_ALLOWED_PROMPT_SHAPED_NAMES = frozenset(
    {"SEMANTIC_PROMPTS_SENT", "semantic_prompts_sent"}
)

#: Modules that would give this offline slice a live I/O capability.
_FORBIDDEN_IMPORT_ROOTS = frozenset(
    {
        "subprocess",
        "socket",
        "ssl",
        "http",
        "urllib",
        "requests",
        "httpx",
        "asyncio",
        "multiprocessing",
        "threading",
        "shutil",
        "litellm",
        "openai",
    }
)

_FORBIDDEN_CODE_FRAGMENTS = ("os.environ", "getenv", "Popen", "urlopen", "open(")


def _module_source(module) -> str:
    return Path(inspect.getsourcefile(module)).read_text(encoding="utf-8")


def _module_tree(module):
    import ast

    return ast.parse(_module_source(module))


def _module_code_only(module) -> str:
    """The module's code with every docstring blanked, so prose never counts."""
    import ast

    tree = _module_tree(module)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                node.body[0].value.value = ""
    return ast.unparse(tree)


def _declared_names(module) -> set[str]:
    import ast

    names: set[str] = set()
    for node in ast.walk(_module_tree(module)):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.keyword) and node.arg:
            names.add(node.arg)
    return names


def test_no_i2b_module_has_a_prompt_shaped_name_anywhere() -> None:
    for module in _I2B_MODULES:
        for name in _declared_names(module):
            if name in _ALLOWED_PROMPT_SHAPED_NAMES:
                continue
            lowered = name.lower()
            for fragment in _PROMPT_SHAPED_NAME_FRAGMENTS:
                assert fragment not in lowered, (
                    f"{module.__name__} declares a prompt-shaped name {name!r}"
                )


def test_no_i2b_module_imports_a_live_io_primitive() -> None:
    import ast

    for module in _I2B_MODULES:
        for node in ast.walk(_module_tree(module)):
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                roots = [(node.module or "").split(".")[0]]
            else:
                continue
            for root in roots:
                assert root not in _FORBIDDEN_IMPORT_ROOTS, (
                    f"{module.__name__} imports the live-I/O module {root!r}"
                )
        code = _module_code_only(module)
        for fragment in _FORBIDDEN_CODE_FRAGMENTS:
            assert fragment not in code, f"{module.__name__} code contains {fragment!r}"


def test_the_controller_exposes_no_prompt_parameter() -> None:
    signature = inspect.signature(run_category_b_controller)
    for name in signature.parameters:
        assert "prompt" not in name.lower()
        assert "message" not in name.lower()
        assert "task" not in name.lower()


def test_semantic_prompts_sent_is_a_constant_zero(tmp_path: Path) -> None:
    assert i2b_controller_module.SEMANTIC_PROMPTS_SENT == 0
    result, _ = _run(tmp_path / "run")
    assert result.semantic_prompts_sent == 0
    assert result.evidence.as_dict()["semantic_prompts_sent"] == 0


def test_no_candidate_scoring_machinery_is_reachable() -> None:
    source = _module_code_only(i2b_controller_module)
    for token in (
        "from .outcomes",
        "from .hard_bar",
        "from .ranking",
        "AutonomousClassification",
        "AUTONOMOUS_PASS",
        "AUTONOMOUS_FAIL",
        "build_qualification_record",
    ):
        assert token not in source, f"i2b_controller references candidate scoring: {token!r}"
    assert {member.value for member in CategoryBOutcome} == {
        "CATEGORY_B_GATE_PASSED",
        "INFRASTRUCTURE_REFUSAL",
    }


@pytest.mark.parametrize(
    "harness_kwargs",
    [
        {"broker_ready": False},
        {"pi_version": None},
        {"h1_matched": False},
        {"protocol_violation": True},
        {"route_reachable": False, "route_model_served": False},
        {"runtime_child_exited": False},
        {"broker_reached_closed": False},
        {"launch_raises": True},
    ],
)
def test_every_category_b_failure_is_a_pre_prompt_infrastructure_refusal(
    tmp_path: Path, harness_kwargs: dict
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], **harness_kwargs)
    result, _ = _run(tmp_path / "run", harness=harness)
    assert result.outcome is CategoryBOutcome.INFRASTRUCTURE_REFUSAL
    assert result.semantic_prompts_sent == 0
    assert result.compatibility_gate_passed is False


# -- truthful claim scope -----------------------------------------------------


def test_the_evidence_never_claims_backend_inference_stopped(tmp_path: Path) -> None:
    result, _ = _run(tmp_path / "run")
    body = result.evidence.as_dict()
    assert body["backend_inference_lifetime_after_teardown"] == "not observed"
    assert body["descendant_process_lifetime_after_teardown"] == "not observed"
    scope = body["claim_scope"]
    assert "reports only what its own calls returned" in scope
    assert "This is NOT a claim that a descendant process was terminated" in scope
    assert "Pi/provider inference stopped" in scope
    # every mention of a stopped backend/descendant sits INSIDE the negation
    assert scope.index("NOT a claim") < scope.index("inference stopped")
    lowered = result.evidence.as_json().lower()
    for forbidden in ("sandbox", "isolated", "os-confined", "no host file"):
        assert forbidden not in lowered


def test_teardown_success_is_scoped_to_aido_s_own_direct_child(tmp_path: Path) -> None:
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"],
        runtime_shutdown_returned=True,
        runtime_child_exited=False,
    )
    result, _ = _run(tmp_path / "run", harness=harness)
    # a returned shutdown call alone is NOT closure
    assert result.runtime_teardown.attempted is True
    assert result.runtime_teardown.succeeded is False
    _assert_refusal(result)
