"""5F3B-I2B -- Category-B Zero-Prompt Live-Gate Controller (OFFLINE ONLY).

**Every test here uses ONLY synthetic, injected doubles for every future
live boundary** (``launch_rpc``, ``h1_check``, ``get_commands``,
``get_state``, ``route_checker``, ``broker_ready``, ``teardown``). No test
in this module opens a socket, launches a subprocess, or reads a real
environment variable -- `qualification.i2b_controller` itself contains no
such primitive at all (proven below by a source-level regression test).

**CATEGORY-B LIVE EXECUTION IS NOT RUN BY THIS SUITE.** This suite proves
only the offline WIRING of the controller: gate ordering, the
credential-read boundary, failure attribution, teardown/cleanup discipline,
and evidence safety.
"""

from __future__ import annotations

import dataclasses
import inspect
from dataclasses import dataclass
from pathlib import Path

import pytest

import qualification.i2b_controller as i2b_controller_module
from qualification.i2_credentials import ConnectionValues, InvalidBaseUrlError, PreflightGateResult
from qualification.i2_environment import LaunchEnvironment
from qualification.i2_secret_context import build_secret_context
from qualification.i2b_controller import (
    AUTHORIZED_TOOL_NAMES,
    CategoryBControllerResult,
    CategoryBFailureCode,
    CategoryBGateName,
    CategoryBOutcome,
    GateOutcome,
    GetCommandsOutcome,
    GetStateOutcome,
    RpcLaunchOutcome,
    build_category_b_evidence,
    run_category_b_controller,
)

SYNTHETIC_BASE_URL = "https://b300-proxy.example.invalid:8443/v1"
SYNTHETIC_API_KEY = "sk-synthetic-i2b-controller-0001"

CANDIDATE_MODEL_IDS = {"A": "qwen3-coder-next", "B": "minimax-m2.7"}
PROVIDER_ID = "b300_pi_qualification"


# -- shared fixtures/helpers --------------------------------------------------


def _passing_non_secret_gates() -> list:
    return [
        lambda: PreflightGateResult(name="pi_installed_offline", passed=True),
        lambda: PreflightGateResult(name="config_generator_self_check", passed=True),
        lambda: PreflightGateResult(name="environment_forbidden_fragment_audit", passed=True),
    ]


def _connection_reader() -> ConnectionValues:
    return ConnectionValues(base_url=SYNTHETIC_BASE_URL, api_key=SYNTHETIC_API_KEY)


@dataclass(frozen=True)
class _FakeRouteModelCheck:
    reachable: bool
    configured_model_served: bool


class _Recorder:
    """Records call order for the injected live callables under test."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def record(self, name: str) -> None:
        self.calls.append(name)


def _happy_callables(recorder: _Recorder, *, model_id: str, provider_id: str = PROVIDER_ID) -> dict:
    def launch_rpc(env: LaunchEnvironment) -> RpcLaunchOutcome:
        recorder.record("launch_rpc")
        assert isinstance(env, LaunchEnvironment)
        return RpcLaunchOutcome(
            gate=GateOutcome(passed=True, failure_code=None), observed_pi_version="0.84.3"
        )

    def h1_check() -> GateOutcome:
        recorder.record("h1_check")
        return GateOutcome(passed=True, failure_code=None)

    def get_commands() -> GetCommandsOutcome:
        recorder.record("get_commands")
        return GetCommandsOutcome(
            gate=GateOutcome(passed=True, failure_code=None),
            command_names=tuple(sorted(AUTHORIZED_TOOL_NAMES)),
        )

    def get_state() -> GetStateOutcome:
        recorder.record("get_state")
        return GetStateOutcome(
            gate=GateOutcome(passed=True, failure_code=None),
            reported_provider=provider_id,
            reported_model=model_id,
        )

    def route_checker(base_url: str, *, model_id: str):
        recorder.record("route_checker")
        return _FakeRouteModelCheck(reachable=True, configured_model_served=True)

    def broker_ready() -> GateOutcome:
        recorder.record("broker_ready")
        return GateOutcome(passed=True, failure_code=None)

    def teardown() -> GateOutcome:
        recorder.record("teardown")
        return GateOutcome(passed=True, failure_code=None)

    return dict(
        launch_rpc=launch_rpc,
        h1_check=h1_check,
        get_commands=get_commands,
        get_state=get_state,
        route_checker=route_checker,
        broker_ready=broker_ready,
        teardown=teardown,
    )


def _run(
    root: Path,
    *,
    candidate: str,
    recorder: _Recorder,
    overrides: dict | None = None,
    non_secret_gates=None,
    read_connection=None,
) -> CategoryBControllerResult:
    model_id = CANDIDATE_MODEL_IDS[candidate]
    callables = _happy_callables(recorder, model_id=model_id)
    if overrides:
        callables.update(overrides)
    return run_category_b_controller(
        candidate=candidate,
        experiment_root=str(root),
        ambient_environ={"SystemRoot": r"C:\Windows", "TEMP": str(root), "TMP": str(root)},
        node_executable=str(root / "node.exe"),
        non_secret_gates=non_secret_gates if non_secret_gates is not None else _passing_non_secret_gates(),
        read_connection=read_connection if read_connection is not None else _connection_reader,
        **callables,
    )


ALL_GATE_ORDER = [
    CategoryBGateName.NON_SECRET_PREFLIGHT,
    CategoryBGateName.CONNECTION_VALUES,
    CategoryBGateName.ROUTE_DESCRIPTOR,
    CategoryBGateName.SECRET_CONTEXT,
    CategoryBGateName.PI_CONFIG_GENERATION,
    CategoryBGateName.IDENTITY_BINDING,
    CategoryBGateName.CHILD_ENVIRONMENT,
    CategoryBGateName.RPC_LAUNCH,
    CategoryBGateName.H1_EXTENSION_IDENTITY,
    CategoryBGateName.GET_COMMANDS,
    CategoryBGateName.GET_STATE,
    CategoryBGateName.H2_PROVIDER_MODEL_IDENTITY,
    CategoryBGateName.TOOL_REGISTRY,
    CategoryBGateName.ROUTE_CHECK,
    CategoryBGateName.BROKER_READY,
]


def _assert_not_reached_after(result: CategoryBControllerResult, gate: CategoryBGateName) -> None:
    index = ALL_GATE_ORDER.index(gate)
    for later_gate in ALL_GATE_ORDER[index + 1 :]:
        assert result.gate_statuses[later_gate.value] == "NOT_REACHED", (
            f"{later_gate.value} should not have been reached after {gate.value} failed"
        )


# -- candidate symmetry / full pass -------------------------------------------


@pytest.mark.parametrize("candidate", ["A", "B"])
def test_full_pass_candidate_symmetry(tmp_path: Path, candidate: str) -> None:
    root = tmp_path / candidate
    root.mkdir()
    recorder = _Recorder()
    result = _run(root, candidate=candidate, recorder=recorder)

    assert result.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED
    assert result.semantic_prompts_sent == 0
    assert result.failed_gate is None
    assert result.failure_code is None
    assert all(status == "PASSED" for status in result.gate_statuses.values())
    assert result.pi_config_created is True
    assert result.live_resource_created is True
    assert result.teardown.attempted is True
    assert result.teardown.outcome is not None and result.teardown.outcome.passed is True
    assert result.cleanup.attempted is True
    assert result.cleanup.scrub_verified is True
    assert result.evidence.retention_ready is True
    assert result.evidence.evidence is not None
    assert result.evidence.evidence["candidate"] == candidate
    assert result.evidence.evidence["model_id"] == CANDIDATE_MODEL_IDS[candidate]
    assert result.evidence.evidence["provider_id"] == PROVIDER_ID
    assert result.evidence.evidence["gateway_class"] == "b300_litellm_proxy"
    assert result.evidence.evidence["semantic_prompts_sent"] == 0
    assert result.evidence.evidence["aido_requested_max_output_tokens"] is None
    assert result.evidence.evidence["models_json_omits_max_tokens"] is True
    assert result.evidence.evidence["provider_request_count_observation_available"] is False
    assert result.evidence.evidence["wire_level_max_tokens_observation_available"] is False
    assert result.evidence.evidence["compatibility_gate_passed"] is True
    assert result.evidence.evidence["teardown_status"] == "SUCCEEDED"
    assert result.evidence.evidence["cleanup_status"] == "SUCCEEDED"

    assert recorder.calls == [
        "launch_rpc",
        "h1_check",
        "get_commands",
        "get_state",
        "route_checker",
        "broker_ready",
        "teardown",
    ]

    # the disposable config directory must be gone -- cleanup actually ran
    assert not (root / "i2_pi_config").exists()


def test_a_and_b_use_identical_controller_logic(tmp_path: Path) -> None:
    recorder_a = _Recorder()
    recorder_b = _Recorder()
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    root_a.mkdir()
    root_b.mkdir()
    result_a = _run(root_a, candidate="A", recorder=recorder_a)
    result_b = _run(root_b, candidate="B", recorder=recorder_b)

    assert recorder_a.calls == recorder_b.calls
    assert set(result_a.gate_statuses) == set(result_b.gate_statuses)
    assert list(result_a.gate_statuses.values()) == list(result_b.gate_statuses.values())
    assert result_a.outcome is result_b.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED
    # only identity differs
    assert result_a.candidate != result_b.candidate
    assert result_a.evidence.evidence["model_id"] != result_b.evidence.evidence["model_id"]


# -- credential-read ordering --------------------------------------------------


def test_credential_reader_not_called_before_non_secret_gates_pass(tmp_path: Path) -> None:
    recorder = _Recorder()
    call_count = {"n": 0}

    def counting_read_connection() -> ConnectionValues:
        call_count["n"] += 1
        return _connection_reader()

    failing_gates = [lambda: PreflightGateResult(name="pi_installed_offline", passed=False, failure_code="NOT_INSTALLED")]
    result = _run(
        tmp_path,
        candidate="A",
        recorder=recorder,
        non_secret_gates=failing_gates,
        read_connection=counting_read_connection,
    )

    assert call_count["n"] == 0
    assert result.outcome is CategoryBOutcome.INFRASTRUCTURE_REFUSAL
    assert result.failed_gate is CategoryBGateName.NON_SECRET_PREFLIGHT
    assert result.failure_code is CategoryBFailureCode.NON_SECRET_PREFLIGHT_GATE_FAILED
    assert result.semantic_prompts_sent == 0
    assert result.pi_config_created is False
    assert result.live_resource_created is False
    assert result.teardown.attempted is False
    assert result.cleanup.attempted is False
    assert recorder.calls == []
    _assert_not_reached_after(result, CategoryBGateName.NON_SECRET_PREFLIGHT)


def test_later_non_secret_gate_never_runs_after_an_earlier_one_fails(tmp_path: Path) -> None:
    calls: list[str] = []

    def gate_one():
        calls.append("one")
        return PreflightGateResult(name="one", passed=False, failure_code="NOT_INSTALLED")

    def gate_two():
        calls.append("two")  # pragma: no cover - must never run
        return PreflightGateResult(name="two", passed=True)

    recorder = _Recorder()
    result = _run(tmp_path, candidate="A", recorder=recorder, non_secret_gates=[gate_one, gate_two])
    assert calls == ["one"]
    assert result.outcome is CategoryBOutcome.INFRASTRUCTURE_REFUSAL


def test_connection_value_malformed_is_a_bounded_pre_prompt_refusal(tmp_path: Path) -> None:
    def malformed_read_connection() -> ConnectionValues:
        raise InvalidBaseUrlError("invalid B300 route URL: hostname is missing")

    recorder = _Recorder()
    result = _run(tmp_path, candidate="A", recorder=recorder, read_connection=malformed_read_connection)
    assert result.outcome is CategoryBOutcome.INFRASTRUCTURE_REFUSAL
    assert result.failed_gate is CategoryBGateName.CONNECTION_VALUES
    assert result.failure_code is CategoryBFailureCode.CONNECTION_VALUES_UNAVAILABLE
    assert recorder.calls == []


# -- individual gate refusals ---------------------------------------------------


def test_h1_mismatch_refuses(tmp_path: Path) -> None:
    recorder = _Recorder()

    def failing_h1() -> GateOutcome:
        recorder.record("h1_check")
        return GateOutcome(passed=False, failure_code=CategoryBFailureCode.H1_EXTENSION_IDENTITY_MISMATCH)

    result = _run(tmp_path, candidate="A", recorder=recorder, overrides={"h1_check": failing_h1})
    assert result.outcome is CategoryBOutcome.INFRASTRUCTURE_REFUSAL
    assert result.failed_gate is CategoryBGateName.H1_EXTENSION_IDENTITY
    assert result.failure_code is CategoryBFailureCode.H1_EXTENSION_IDENTITY_MISMATCH
    assert recorder.calls == ["launch_rpc", "h1_check", "teardown"]
    assert result.live_resource_created is True
    assert result.teardown.attempted is True
    assert result.cleanup.attempted is True
    assert result.semantic_prompts_sent == 0
    _assert_not_reached_after(result, CategoryBGateName.H1_EXTENSION_IDENTITY)


def test_get_commands_failure_refuses(tmp_path: Path) -> None:
    recorder = _Recorder()

    def failing_get_commands() -> GetCommandsOutcome:
        recorder.record("get_commands")
        return GetCommandsOutcome(
            gate=GateOutcome(passed=False, failure_code=CategoryBFailureCode.GET_COMMANDS_FAILED),
            command_names=(),
        )

    result = _run(tmp_path, candidate="A", recorder=recorder, overrides={"get_commands": failing_get_commands})
    assert result.failed_gate is CategoryBGateName.GET_COMMANDS
    assert result.failure_code is CategoryBFailureCode.GET_COMMANDS_FAILED
    assert recorder.calls == ["launch_rpc", "h1_check", "get_commands", "teardown"]
    _assert_not_reached_after(result, CategoryBGateName.GET_COMMANDS)


def test_get_commands_protocol_error_is_reported_and_refuses(tmp_path: Path) -> None:
    recorder = _Recorder()

    def protocol_error_get_commands() -> GetCommandsOutcome:
        recorder.record("get_commands")
        return GetCommandsOutcome(
            gate=GateOutcome(passed=False, failure_code=CategoryBFailureCode.PROTOCOL_OR_EXTENSION_ERROR),
            command_names=(),
        )

    result = _run(
        tmp_path, candidate="A", recorder=recorder, overrides={"get_commands": protocol_error_get_commands}
    )
    assert result.failure_code is CategoryBFailureCode.PROTOCOL_OR_EXTENSION_ERROR
    assert result.outcome is CategoryBOutcome.INFRASTRUCTURE_REFUSAL
    assert result.semantic_prompts_sent == 0


def test_get_state_failure_refuses(tmp_path: Path) -> None:
    recorder = _Recorder()

    def failing_get_state() -> GetStateOutcome:
        recorder.record("get_state")
        return GetStateOutcome(
            gate=GateOutcome(passed=False, failure_code=CategoryBFailureCode.GET_STATE_FAILED),
            reported_provider=None,
            reported_model=None,
        )

    result = _run(tmp_path, candidate="A", recorder=recorder, overrides={"get_state": failing_get_state})
    assert result.failed_gate is CategoryBGateName.GET_STATE
    assert recorder.calls == ["launch_rpc", "h1_check", "get_commands", "get_state", "teardown"]
    _assert_not_reached_after(result, CategoryBGateName.GET_STATE)


def test_h2_mismatch_refuses(tmp_path: Path) -> None:
    recorder = _Recorder()

    def wrong_identity_get_state() -> GetStateOutcome:
        recorder.record("get_state")
        return GetStateOutcome(
            gate=GateOutcome(passed=True, failure_code=None),
            reported_provider=PROVIDER_ID,
            reported_model="minimax-m2.7",  # candidate A expects qwen3-coder-next
        )

    result = _run(tmp_path, candidate="A", recorder=recorder, overrides={"get_state": wrong_identity_get_state})
    assert result.failed_gate is CategoryBGateName.H2_PROVIDER_MODEL_IDENTITY
    assert result.failure_code is CategoryBFailureCode.H2_PROVIDER_MODEL_IDENTITY_MISMATCH
    assert recorder.calls == ["launch_rpc", "h1_check", "get_commands", "get_state", "teardown"]
    _assert_not_reached_after(result, CategoryBGateName.H2_PROVIDER_MODEL_IDENTITY)


def test_wrong_tool_registry_refuses(tmp_path: Path) -> None:
    recorder = _Recorder()

    def wrong_registry_get_commands() -> GetCommandsOutcome:
        recorder.record("get_commands")
        return GetCommandsOutcome(
            gate=GateOutcome(passed=True, failure_code=None),
            command_names=("aido_read", "aido_edit", "aido_shell"),
        )

    result = _run(
        tmp_path, candidate="A", recorder=recorder, overrides={"get_commands": wrong_registry_get_commands}
    )
    assert result.failed_gate is CategoryBGateName.TOOL_REGISTRY
    assert result.failure_code is CategoryBFailureCode.TOOL_REGISTRY_MISMATCH
    assert recorder.calls == ["launch_rpc", "h1_check", "get_commands", "get_state", "teardown"]
    _assert_not_reached_after(result, CategoryBGateName.TOOL_REGISTRY)


def test_route_unavailable_refuses(tmp_path: Path) -> None:
    recorder = _Recorder()

    def unreachable_route_checker(base_url: str, *, model_id: str):
        recorder.record("route_checker")
        return _FakeRouteModelCheck(reachable=False, configured_model_served=False)

    result = _run(
        tmp_path, candidate="A", recorder=recorder, overrides={"route_checker": unreachable_route_checker}
    )
    assert result.failed_gate is CategoryBGateName.ROUTE_CHECK
    assert result.failure_code is CategoryBFailureCode.ROUTE_CHECK_FAILED
    assert recorder.calls == [
        "launch_rpc", "h1_check", "get_commands", "get_state", "route_checker", "teardown",
    ]
    _assert_not_reached_after(result, CategoryBGateName.ROUTE_CHECK)


def test_wrong_served_model_refuses(tmp_path: Path) -> None:
    recorder = _Recorder()

    def wrong_model_route_checker(base_url: str, *, model_id: str):
        recorder.record("route_checker")
        return _FakeRouteModelCheck(reachable=True, configured_model_served=False)

    result = _run(
        tmp_path, candidate="A", recorder=recorder, overrides={"route_checker": wrong_model_route_checker}
    )
    assert result.failed_gate is CategoryBGateName.ROUTE_CHECK
    assert result.failure_code is CategoryBFailureCode.ROUTE_CHECK_FAILED
    _assert_not_reached_after(result, CategoryBGateName.ROUTE_CHECK)


def test_broker_not_ready_refuses(tmp_path: Path) -> None:
    recorder = _Recorder()

    def not_ready_broker() -> GateOutcome:
        recorder.record("broker_ready")
        return GateOutcome(passed=False, failure_code=CategoryBFailureCode.BROKER_NOT_READY)

    result = _run(tmp_path, candidate="A", recorder=recorder, overrides={"broker_ready": not_ready_broker})
    assert result.outcome is CategoryBOutcome.INFRASTRUCTURE_REFUSAL
    assert result.failed_gate is CategoryBGateName.BROKER_READY
    assert result.failure_code is CategoryBFailureCode.BROKER_NOT_READY
    assert recorder.calls == [
        "launch_rpc", "h1_check", "get_commands", "get_state", "route_checker", "broker_ready", "teardown",
    ]
    assert result.live_resource_created is True
    assert result.teardown.attempted is True
    assert result.cleanup.attempted is True
    assert result.semantic_prompts_sent == 0


def test_pi_protocol_error_from_broker_ready_refuses(tmp_path: Path) -> None:
    recorder = _Recorder()

    def protocol_error_broker() -> GateOutcome:
        recorder.record("broker_ready")
        return GateOutcome(passed=False, failure_code=CategoryBFailureCode.PROTOCOL_OR_EXTENSION_ERROR)

    result = _run(
        tmp_path, candidate="A", recorder=recorder, overrides={"broker_ready": protocol_error_broker}
    )
    assert result.failure_code is CategoryBFailureCode.PROTOCOL_OR_EXTENSION_ERROR
    assert result.outcome is CategoryBOutcome.INFRASTRUCTURE_REFUSAL


# -- unexpected exceptions ------------------------------------------------------


def test_unexpected_exception_from_rpc_launch_becomes_bounded_refusal(tmp_path: Path) -> None:
    recorder = _Recorder()

    def exploding_launch_rpc(env: LaunchEnvironment) -> RpcLaunchOutcome:
        recorder.record("launch_rpc")
        raise RuntimeError("synthetic-secret-should-never-appear-sk-0001")

    result = _run(tmp_path, candidate="A", recorder=recorder, overrides={"launch_rpc": exploding_launch_rpc})
    assert result.outcome is CategoryBOutcome.INFRASTRUCTURE_REFUSAL
    assert result.failed_gate is CategoryBGateName.RPC_LAUNCH
    assert result.failure_code is CategoryBFailureCode.UNEXPECTED_EXCEPTION
    assert result.live_resource_created is True
    assert result.teardown.attempted is True
    assert result.cleanup.attempted is True
    assert result.semantic_prompts_sent == 0

    dump = repr(result) + repr(result.evidence)
    assert "synthetic-secret-should-never-appear-sk-0001" not in dump


def test_unexpected_exception_from_h1_check_becomes_bounded_refusal(tmp_path: Path) -> None:
    recorder = _Recorder()

    def exploding_h1() -> GateOutcome:
        recorder.record("h1_check")
        raise ValueError("boom")

    result = _run(tmp_path, candidate="A", recorder=recorder, overrides={"h1_check": exploding_h1})
    assert result.failed_gate is CategoryBGateName.H1_EXTENSION_IDENTITY
    assert result.failure_code is CategoryBFailureCode.UNEXPECTED_EXCEPTION
    assert recorder.calls == ["launch_rpc", "h1_check", "teardown"]


def test_unexpected_exception_from_teardown_is_bounded_and_reported(tmp_path: Path) -> None:
    recorder = _Recorder()

    def exploding_teardown() -> GateOutcome:
        recorder.record("teardown")
        raise RuntimeError("teardown-blew-up")

    result = _run(tmp_path, candidate="A", recorder=recorder, overrides={"teardown": exploding_teardown})
    assert result.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED  # gates themselves all passed
    assert result.teardown.attempted is True
    assert result.teardown.outcome is not None
    assert result.teardown.outcome.passed is False
    assert result.teardown.outcome.failure_code is CategoryBFailureCode.UNEXPECTED_EXCEPTION
    assert "teardown-blew-up" not in repr(result)


# -- zero-prompt proof ----------------------------------------------------------


@pytest.mark.parametrize(
    "override_name,override_factory",
    [
        (
            "h1_check",
            lambda: (lambda: GateOutcome(passed=False, failure_code=CategoryBFailureCode.H1_EXTENSION_IDENTITY_MISMATCH)),
        ),
        (
            "broker_ready",
            lambda: (lambda: GateOutcome(passed=False, failure_code=CategoryBFailureCode.BROKER_NOT_READY)),
        ),
    ],
)
def test_every_failure_has_zero_semantic_prompts_sent(tmp_path: Path, override_name, override_factory) -> None:
    recorder = _Recorder()
    result = _run(tmp_path, candidate="A", recorder=recorder, overrides={override_name: override_factory()})
    assert result.outcome is CategoryBOutcome.INFRASTRUCTURE_REFUSAL
    assert result.semantic_prompts_sent == 0


def test_full_pass_also_has_zero_semantic_prompts_sent(tmp_path: Path) -> None:
    recorder = _Recorder()
    result = _run(tmp_path, candidate="A", recorder=recorder)
    assert result.semantic_prompts_sent == 0


def test_observed_pi_version_is_provenance_only_never_gating(tmp_path: Path) -> None:
    """Category-B gate 2: changing the observed version alone must never
    change gate pass/fail -- only the recorded evidence provenance."""

    def make_recorder_and_result(version: str) -> tuple[_Recorder, CategoryBControllerResult]:
        recorder = _Recorder()

        def launch_rpc(env: LaunchEnvironment) -> RpcLaunchOutcome:
            recorder.record("launch_rpc")
            return RpcLaunchOutcome(gate=GateOutcome(passed=True, failure_code=None), observed_pi_version=version)

        result = _run(tmp_path / version.replace(".", "_"), candidate="A", recorder=recorder, overrides={"launch_rpc": launch_rpc})
        return recorder, result

    (root_a := tmp_path / "0_84_3").mkdir(exist_ok=True)
    (root_b := tmp_path / "9_99_9").mkdir(exist_ok=True)
    _, result_low = make_recorder_and_result("0.84.3")
    _, result_high = make_recorder_and_result("9.99.9")

    assert result_low.outcome is result_high.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED
    assert list(result_low.gate_statuses.values()) == list(result_high.gate_statuses.values())
    assert result_low.evidence.evidence["observed_pi_version"] == "0.84.3"
    assert result_high.evidence.evidence["observed_pi_version"] == "9.99.9"


# -- teardown / cleanup truthful attribution ------------------------------------


def test_teardown_not_attempted_before_live_resource_created(tmp_path: Path) -> None:
    recorder = _Recorder()

    def failing_child_environment_ambient() -> None:
        pass  # placeholder, see below

    # Force CHILD_ENVIRONMENT to fail by supplying an ambient_environ that
    # omits SystemRoot in a way the builder still succeeds with defaults --
    # instead, fail identity binding earlier by corrupting the model id
    # relationship is not directly overridable here, so we instead force a
    # PI_CONFIG_GENERATION failure (before any live resource exists) via an
    # invalid experiment_root (a file, not a directory, so mkdir fails).
    bad_root = tmp_path / "not_a_directory"
    bad_root.write_text("occupied", encoding="utf-8")
    result = _run(bad_root, candidate="A", recorder=recorder)

    assert result.failed_gate is CategoryBGateName.PI_CONFIG_GENERATION
    assert result.pi_config_created is False
    assert result.live_resource_created is False
    assert result.teardown.attempted is False
    assert result.cleanup.attempted is False
    assert recorder.calls == []


def test_cleanup_attempted_once_generated_config_exists_even_if_later_gate_fails(tmp_path: Path) -> None:
    recorder = _Recorder()

    def failing_h1() -> GateOutcome:
        recorder.record("h1_check")
        return GateOutcome(passed=False, failure_code=CategoryBFailureCode.H1_EXTENSION_IDENTITY_MISMATCH)

    result = _run(tmp_path, candidate="A", recorder=recorder, overrides={"h1_check": failing_h1})
    assert result.pi_config_created is True
    assert result.cleanup.attempted is True
    assert result.cleanup.scrub_verified is True
    assert not (tmp_path / "i2_pi_config").exists()


def test_teardown_attempted_after_live_resource_creation_even_on_failure(tmp_path: Path) -> None:
    recorder = _Recorder()

    def failing_h1() -> GateOutcome:
        recorder.record("h1_check")
        return GateOutcome(passed=False, failure_code=CategoryBFailureCode.H1_EXTENSION_IDENTITY_MISMATCH)

    result = _run(tmp_path, candidate="A", recorder=recorder, overrides={"h1_check": failing_h1})
    assert result.live_resource_created is True
    assert result.teardown.attempted is True
    assert "teardown" in recorder.calls


# -- evidence safety -------------------------------------------------------------


def test_no_candidate_classification_or_scoring_occurs(tmp_path: Path) -> None:
    recorder = _Recorder()
    result = _run(tmp_path, candidate="A", recorder=recorder)
    field_names = {f.name for f in dataclasses.fields(CategoryBControllerResult)}
    assert "run_validity" not in field_names
    assert "autonomous_classification" not in field_names
    assert "scoring_eligible" not in field_names
    assert "hard_bar" not in field_names
    assert "ranking" not in field_names
    assert result.outcome in (CategoryBOutcome.CATEGORY_B_GATE_PASSED, CategoryBOutcome.INFRASTRUCTURE_REFUSAL)


def test_unsafe_diagnostic_cannot_become_evidence(tmp_path: Path) -> None:
    """If a raw credential value ever leaked into the evidence payload, the
    scrub boundary -- not this module's own discipline -- must still refuse
    to mark it retention-ready."""
    secret_context = build_secret_context(
        base_url=SYNTHETIC_BASE_URL, api_key=SYNTHETIC_API_KEY, model_id="qwen3-coder-next"
    )
    from qualification.i2_route import route_descriptor_for_candidate

    descriptor = route_descriptor_for_candidate("A")
    result = build_category_b_evidence(
        candidate="A",
        route_descriptor=descriptor,
        # Simulate a bug where a raw credential-shaped value reached the
        # provenance field this module would normally only ever populate
        # with a plain version string.
        observed_pi_version=SYNTHETIC_API_KEY,
        outcome=CategoryBOutcome.INFRASTRUCTURE_REFUSAL,
        gate_statuses={"rpc_launch": "FAILED:RPC_LAUNCH_FAILED"},
        teardown=i2b_controller_module.TeardownStatus(attempted=False, outcome=None),
        cleanup=i2b_controller_module.CleanupStatus(attempted=False, scrub_verified=None, classification=None),
        secret_context=secret_context,
    )
    assert result.retention_ready is False
    assert result.evidence is None
    assert result.scrub["clean"] is False


def test_safe_evidence_emits_and_carries_no_forbidden_field(tmp_path: Path) -> None:
    recorder = _Recorder()
    result = _run(tmp_path, candidate="A", recorder=recorder)
    assert result.evidence.retention_ready is True
    evidence = result.evidence.evidence
    assert evidence is not None
    serialized_keys = set(evidence)
    for forbidden in ("api_key", "base_url", "endpoint_host", "broker_token", "pipe_name", "capability_id", "workspace_absolute_path"):
        assert forbidden not in serialized_keys
    import json

    dumped = json.dumps(evidence)
    assert SYNTHETIC_API_KEY not in dumped
    assert SYNTHETIC_BASE_URL not in dumped


# -- structural / source regression tests ---------------------------------------


def test_no_semantic_prompt_api_or_live_primitive_exists_in_source() -> None:
    source = inspect.getsource(i2b_controller_module)
    forbidden_tokens = (
        "IQ-1",
        "IQ-2",
        "IQ-3",
        "task_prompt",
        "send_prompt",
        "agent_start",
        "semantic_request",
        ".prompt(",
        "import subprocess",
        "import socket",
        "import httpx",
        "import requests",
    )
    for token in forbidden_tokens:
        assert token not in source, f"forbidden token {token!r} found in qualification/i2b_controller.py"


def test_no_semantic_prompt_method_exists_on_the_module() -> None:
    public_names = [name for name in dir(i2b_controller_module) if not name.startswith("_")]
    for name in public_names:
        lowered = name.lower()
        assert "prompt" not in lowered, f"unexpected prompt-shaped public name: {name}"


def test_module_does_not_import_scoring_or_classification_machinery() -> None:
    """Only actual import statements are checked -- the module's own prose
    legitimately NAMES these modules to explain what it deliberately does
    not import."""
    source = inspect.getsource(i2b_controller_module)
    import_lines = [
        line.strip()
        for line in source.splitlines()
        if line.strip().startswith("from .") or line.strip().startswith("import ")
    ]
    forbidden_modules = (".outcomes", ".hard_bar", ".ranking", ".records")
    for line in import_lines:
        for forbidden in forbidden_modules:
            assert forbidden not in line, f"unexpected import of {forbidden!r}: {line!r}"
    assert "build_qualification_record" not in source
