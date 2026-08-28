"""5F3B-I2B-FU2 -- Category-B Zero-Prompt Live-Gate Controller (OFFLINE ONLY).

**Every test here uses ONLY synthetic, injected doubles for every future live
boundary.** No test in this module opens a socket, launches a subprocess,
reads a real environment variable, reads a real credential, or calls a model.
Every workspace is a FRESH disposable root minted by
``qualification.i2b_workspace.mint_qualification_run_workspace`` (which is
``ar2.fixtures.create_disposable_experiment_root`` underneath, i.e. a
``tempfile.mkdtemp()`` under the approved scratch boundary) and removed
afterwards -- never a real project, never a sibling, never ``tmp_path``
promoted into authority.

**CATEGORY-B LIVE EXECUTION IS NOT RUN BY THIS SUITE.** What is proven here
is the offline controller shape: the frozen-O1 lifecycle order, the corrected
pre-credential ordering, synthetic workspace authority, one-observation
H1/namespace and H2/state derivation, the creator partial-failure contract,
foreign-session refusal, the terminal pass rule including lifecycle closure,
the full artifact safety context, result/evidence immutability, and
zero-prompt authority.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import pytest

from ar2.capability import ROOT_AUTHORITY_MARKER_FILENAME
from ar2.handshakes import evaluate_extension_identity
from ar2.pi_config import EXPECTED_EXTENSION_SOURCE_KIND, SENTINEL_COMMAND_NAME

import qualification.i2b_controller as i2b_controller_module
import qualification.i2b_session as i2b_session_module
import qualification.i2b_workspace as i2b_workspace_module
from qualification.i2_credentials import ConnectionValues, PreflightGateResult
from qualification.i2b_controller import (
    COMPATIBILITY_GATES,
    CREDENTIAL_READ_GATE,
    PRE_CREDENTIAL_GATES,
    TOOL_REGISTRY_CLAIM_SCOPE,
    CategoryBControllerInputError,
    CategoryBControllerResult,
    CategoryBEvidence,
    CategoryBFailureCode,
    CategoryBGateName,
    CategoryBOutcome,
    CompatibilityFacts,
    CleanupStatus,
    ResourceClosureState,
    RuntimeTeardownStatus,
    BrokerShutdownStatus,
    build_run_safety_context,
    run_category_b_controller,
)
from qualification.safety import ArtifactSafetyContext
from qualification.i2b_session import (
    CATEGORY_B_SENTINEL_COMMAND_NAME,
    CLI_EXTENSION_ORIGIN_KIND,
    EXTENSION_COMMAND_SOURCE,
    H1_COMPONENT_FIELDS,
    INLINE_EXTENSION_ORIGIN_KIND,
    BrokerCreationObservation,
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
    h1_components_from_frozen_evaluation,
    observed_command_from_reported_entry,
)
from qualification.i2b_workspace import (
    QualificationRunWorkspace,
    WorkspaceAuthorityError,
    claim_run_workspace,
    mint_qualification_run_workspace,
    remove_run_workspace,
    verify_run_workspace,
)

SYNTHETIC_BASE_URL = "https://b300-proxy.example.invalid:8443/v1"
SYNTHETIC_API_KEY = "sk-synthetic-i2b-controller-0001"
SYNTHETIC_PIPE_NAME = r"\\.\pipe\aido-i2b-synthetic-0001"
SYNTHETIC_CAPABILITY_ID = "cap-synthetic-i2b-0001"
SYNTHETIC_BROKER_TOKEN = "brk-synthetic-i2b-token-0001"
SYNTHETIC_PI_VERSION = "0.84.3"
SYNTHETIC_EXTENSION_ENTRY = os.path.join(os.path.dirname(__file__), "index.ts")

CANDIDATE_MODEL_IDS = {"A": "qwen3-coder-next", "B": "minimax-m2.7"}
PROVIDER_ID = "b300_pi_qualification"

#: The GENUINE observed Pi shape (design FU3 E19-E22): AIDO's sentinel is
#: top-level ``"extension"`` with ``sourceInfo.source == "cli"``; Pi's own
#: inline ``llama`` is top-level ``"extension"`` with
#: ``sourceInfo.source == "inline"``. BOTH carry the same top-level source,
#: which is exactly why the top level cannot be the discriminator.
GENUINE_SENTINEL_COMMAND = ObservedCommand(
    name=SENTINEL_COMMAND_NAME,
    source=EXTENSION_COMMAND_SOURCE,
    source_info_present=True,
    source_info_well_formed=True,
    source_info_source=CLI_EXTENSION_ORIGIN_KIND,
)
GENUINE_LLAMA_COMMAND = ObservedCommand(
    name="llama",
    source=EXTENSION_COMMAND_SOURCE,
    source_info_present=True,
    source_info_well_formed=True,
    source_info_source=INLINE_EXTENSION_ORIGIN_KIND,
)
GENUINE_COMMANDS = (GENUINE_SENTINEL_COMMAND, GENUINE_LLAMA_COMMAND)

#: The five H1 components in their "everything the frozen rule requires held"
#: state. ``malformed_source_metadata`` is the one that must be FALSE.
PASSING_H1_COMPONENTS = {
    "sentinel_name_matched": True,
    "sentinel_source_is_extension": True,
    "sentinel_path_resolves_to_expected_entry": True,
    "noncontradictory_source_origin": True,
    "malformed_source_metadata": False,
}


# -- workspace fixture ---------------------------------------------------------


@pytest.fixture
def run_workspace() -> Iterator[QualificationRunWorkspace]:
    """One FRESH minted disposable run workspace, removed afterwards."""
    workspace = mint_qualification_run_workspace()
    try:
        yield workspace
    finally:
        try:
            remove_run_workspace(workspace)
        except WorkspaceAuthorityError:  # pragma: no cover - defensive
            pass


@pytest.fixture
def second_run_workspace() -> Iterator[QualificationRunWorkspace]:
    workspace = mint_qualification_run_workspace()
    try:
        yield workspace
    finally:
        try:
            remove_run_workspace(workspace)
        except WorkspaceAuthorityError:  # pragma: no cover - defensive
            pass


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

    Every adapter is a plain Python function over the I2B value objects -- no
    process, no socket, no model, no environment read anywhere. Every call is
    recorded, so a test can assert not only what a refusal REPORTED but also
    which live adapters were never invoked at all.
    """

    model_id: str
    api_key: str = SYNTHETIC_API_KEY
    calls: list[str] = field(default_factory=list)
    # observed run-scoped identities, captured as the adapters are driven
    broker_run_id: str | None = None
    broker: BrokerSession | None = None
    runtime: RuntimeSession | None = None
    creation_request: BrokerCreationRequest | None = None
    launch_request: RuntimeLaunchRequest | None = None
    # broker knobs
    broker_ready: bool = True
    broker_run_id_override: str | None = None
    broker_reached_closed: bool = True
    broker_shutdown_session_id_override: str | None = None
    broker_result_override: object = None
    broker_returns_no_session: bool = False
    broker_start_attempted: bool = True
    broker_resource_created: bool = False
    broker_cleanup_attempted: bool = False
    broker_reached_closed_on_partial: bool | None = None
    broker_raises: bool = False
    # launch knobs
    pi_version: str | None = SYNTHETIC_PI_VERSION
    launch_shape_valid: bool = True
    required_flags_accepted: bool = True
    lf_correlation: bool = True
    launch_returns_no_session: bool = False
    launch_resource_created: bool = False
    launch_cleanup_attempted: bool = False
    launch_direct_child_reported_exit: bool | None = None
    launch_result_override: object = None
    launch_raises: bool = False
    launch_session_run_id_override: str | None = None
    launch_session_broker_id_override: str | None = None
    # get_commands knobs
    commands: tuple[ObservedCommand, ...] | None = None
    commands_call_succeeded: bool = True
    commands_shape_understood: bool = True
    h1_components: dict | None = None
    commands_session_override: str | None = None
    commands_result_override: object = None
    sentinel_command_name: str = SENTINEL_COMMAND_NAME
    # get_state knobs
    state_call_succeeded: bool = True
    state_shape_understood: bool = True
    reported_provider: str | None = PROVIDER_ID
    reported_model: str | None = None
    state_session_override: str | None = None
    # protocol / route knobs
    protocol_violation: bool = False
    extension_error: bool = False
    protocol_session_override: str | None = None
    route_reachable: bool = True
    route_model_served: bool = True
    # shutdown knobs
    runtime_shutdown_returned: bool = True
    runtime_child_exited: bool = True
    runtime_shutdown_session_override: str | None = None
    runtime_shutdown_raises: bool = False
    broker_shutdown_raises: bool = False

    # -- injected adapters --

    def read_connection(self) -> ConnectionValues:
        self.calls.append("read_connection")
        return ConnectionValues(base_url=SYNTHETIC_BASE_URL, api_key=self.api_key)

    def create_broker(self, request: BrokerCreationRequest) -> BrokerCreationObservation:
        self.calls.append("create_broker")
        assert isinstance(request, BrokerCreationRequest)
        self.creation_request = request
        self.broker_run_id = request.run_id
        if self.broker_raises:
            raise RuntimeError("synthetic broker failure")
        if self.broker_result_override is not None:
            return self.broker_result_override  # type: ignore[return-value]
        if self.broker_returns_no_session:
            return BrokerCreationObservation(
                session=None,
                start_attempted=self.broker_start_attempted,
                resource_created=self.broker_resource_created,
                cleanup_attempted=self.broker_cleanup_attempted,
                reached_closed=self.broker_reached_closed_on_partial,
            )
        self.broker = BrokerSession(
            run_id=self.broker_run_id_override or request.run_id,
            session_id="brk-session-0001",
            pipe_name=SYNTHETIC_PIPE_NAME,
            capability_id=SYNTHETIC_CAPABILITY_ID,
            broker_token=SYNTHETIC_BROKER_TOKEN,
            reached_ready=self.broker_ready,
        )
        return BrokerCreationObservation(
            session=self.broker, start_attempted=True, resource_created=True
        )

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
                launch_shape_valid=self.launch_shape_valid,
                required_flags_accepted=self.required_flags_accepted,
                lf_jsonl_correlation_succeeded=self.lf_correlation,
                observed_pi_version=self.pi_version,
                resource_created=self.launch_resource_created,
                cleanup_attempted=self.launch_cleanup_attempted,
                direct_child_reported_exit=self.launch_direct_child_reported_exit,
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
            resource_created=True,
        )

    def get_commands(self, session: RuntimeSession) -> GetCommandsObservation:
        self.calls.append("get_commands")
        assert isinstance(session, RuntimeSession)
        if self.commands_result_override is not None:
            return self.commands_result_override  # type: ignore[return-value]
        commands = GENUINE_COMMANDS if self.commands is None else self.commands
        components = dict(PASSING_H1_COMPONENTS)
        if self.h1_components is not None:
            components.update(self.h1_components)
        return GetCommandsObservation(
            runtime_session_id=self.commands_session_override or session.runtime_session_id,
            call_succeeded=self.commands_call_succeeded,
            response_shape_understood=self.commands_shape_understood,
            sentinel_command_name=self.sentinel_command_name,
            commands=commands,
            reported_source_kind=CLI_EXTENSION_ORIGIN_KIND,
            **components,
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

    def count(self, name: str) -> int:
        return self.calls.count(name)


def _run(
    workspace: QualificationRunWorkspace,
    *,
    candidate: str = "A",
    harness: _Harness | None = None,
    non_secret_gates=None,
    read_connection=None,
) -> tuple[CategoryBControllerResult, _Harness]:
    harness = harness or _Harness(model_id=CANDIDATE_MODEL_IDS[candidate])
    result = run_category_b_controller(
        candidate=candidate,
        run_workspace=workspace,
        ambient_environ={
            "SystemRoot": r"C:\Windows",
            "TEMP": workspace.experiment_root,
            "TMP": workspace.experiment_root,
        },
        node_executable=os.path.join(workspace.experiment_root, "node.exe"),
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


class _CountingReader:
    """A ``read_connection`` double that COUNTS its invocations."""

    def __init__(self, *, api_key: str = SYNTHETIC_API_KEY) -> None:
        self.calls = 0
        self._api_key = api_key

    def __call__(self) -> ConnectionValues:
        self.calls += 1
        return ConnectionValues(base_url=SYNTHETIC_BASE_URL, api_key=self._api_key)


# -- the full pass, and candidate symmetry ------------------------------------


@pytest.mark.parametrize("candidate", ["A", "B"])
def test_full_pass_candidate_symmetry(
    run_workspace: QualificationRunWorkspace, candidate: str
) -> None:
    result, harness = _run(run_workspace, candidate=candidate)

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
    assert not Path(run_workspace.experiment_root, "i2_pi_config").exists()


def test_candidate_a_and_b_use_identical_controller_logic(
    run_workspace: QualificationRunWorkspace, second_run_workspace: QualificationRunWorkspace
) -> None:
    result_a, harness_a = _run(run_workspace, candidate="A")
    result_b, harness_b = _run(second_run_workspace, candidate="B")

    assert harness_a.calls == harness_b.calls
    assert dict(result_a.gate_statuses) == dict(result_b.gate_statuses)
    assert result_a.facts == result_b.facts
    assert result_a.outcome is result_b.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED
    assert result_a.evidence.as_dict()["model_id"] != result_b.evidence.as_dict()["model_id"]


# -- CORRECTED OBSERVABILITY: get_commands enumerates SLASH COMMANDS ----------


def test_the_genuine_observed_pi_shape_passes_the_namespace_gate(
    run_workspace: QualificationRunWorkspace,
) -> None:
    """The MANDATORY E19-shape regression case (design FU3 Sec. 5.3).

    Sentinel with ``sourceInfo.source == "cli"`` plus Pi's own inline
    ``llama`` with ``sourceInfo.source == "inline"`` -- both reporting the
    SAME top-level ``source == "extension"``, exactly as three real captured
    live runs against Pi 0.84.2 and 0.84.3 reported. The corrected gate must
    be satisfiable against this shape, not merely against a synthetic double.
    """
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], commands=GENUINE_COMMANDS)
    result, _ = _run(run_workspace, harness=harness)

    assert {c.source for c in GENUINE_COMMANDS} == {EXTENSION_COMMAND_SOURCE}
    assert result.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED
    assert result.facts.no_unexpected_extension_command_observed is True
    assert (
        result.gate_statuses[CategoryBGateName.EXTENSION_COMMAND_NAMESPACE.value] == "PASSED"
    )


def test_the_old_tool_registry_gate_is_gone_everywhere() -> None:
    """The superseded ``aido_read``/``aido_edit`` command-set gate must not exist."""
    assert not hasattr(i2b_controller_module, "AUTHORIZED_TOOL_NAMES")
    assert not hasattr(CategoryBGateName, "TOOL_REGISTRY")
    assert not hasattr(CategoryBFailureCode, "TOOL_REGISTRY_MISMATCH")
    assert "authorized_tool_registry_exact" not in {
        spec.name for spec in dataclasses.fields(CompatibilityFacts)
    }
    # In the module's CODE (docstrings blanked, so prose that merely explains
    # the supersession does not count), the two tool names may appear only
    # inside the mandated claim-scope constant that says they are NOT what
    # get_commands proves.
    code = _module_code_only(i2b_controller_module)
    for line in code.splitlines():
        if "aido_read" in line or "aido_edit" in line:
            assert any(part in line for part in TOOL_REGISTRY_CLAIM_SCOPE), line


def test_a_second_cli_sourced_extension_command_fails_closed(
    run_workspace: QualificationRunWorkspace,
) -> None:
    intruder = ObservedCommand(
        name="not_our_extension",
        source=EXTENSION_COMMAND_SOURCE,
        source_info_present=True,
        source_info_well_formed=True,
        source_info_source=CLI_EXTENSION_ORIGIN_KIND,
    )
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"], commands=GENUINE_COMMANDS + (intruder,)
    )
    result, harness = _run(run_workspace, harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.EXTENSION_COMMAND_NAMESPACE
    assert result.failure_code is CategoryBFailureCode.UNEXPECTED_CLI_EXTENSION_COMMAND
    assert result.facts.no_unexpected_extension_command_observed is False
    # H1 still passed -- they are two DISTINCT facts from one response
    assert result.facts.h1_extension_identity_matched is True
    assert "get_state" not in harness.calls


def test_a_duplicated_sentinel_cli_entry_does_not_collapse(
    run_workspace: QualificationRunWorkspace,
) -> None:
    """Multiplicity is load-bearing: two identical CLI entries are still two."""
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"],
        commands=(GENUINE_SENTINEL_COMMAND, GENUINE_SENTINEL_COMMAND, GENUINE_LLAMA_COMMAND),
    )
    result, _ = _run(run_workspace, harness=harness)

    _assert_refusal(result)
    assert result.failure_code is CategoryBFailureCode.UNEXPECTED_CLI_EXTENSION_COMMAND


def test_many_inline_pi_owned_commands_are_tolerated(
    run_workspace: QualificationRunWorkspace,
) -> None:
    """Pi's own catalog is not this gate's business -- an upgrade must not break it."""
    extra_inline = tuple(
        ObservedCommand(
            name=f"pi_builtin_{index}",
            source=EXTENSION_COMMAND_SOURCE,
            source_info_present=True,
            source_info_well_formed=True,
            source_info_source=INLINE_EXTENSION_ORIGIN_KIND,
        )
        for index in range(12)
    )
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"], commands=GENUINE_COMMANDS + extra_inline
    )
    result, _ = _run(run_workspace, harness=harness)
    assert result.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED


def test_a_non_extension_sourced_command_is_ignored_by_the_gate(
    run_workspace: QualificationRunWorkspace,
) -> None:
    builtin = ObservedCommand(name="help", source="builtin")
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], commands=GENUINE_COMMANDS + (builtin,))
    result, _ = _run(run_workspace, harness=harness)
    assert result.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED


@pytest.mark.parametrize(
    "bad_entry_kwargs",
    [
        # sourceInfo entirely absent
        {"source_info_present": False, "source_info_well_formed": False},
        # sourceInfo present but not an object
        {"source_info_present": True, "source_info_well_formed": False},
        # sourceInfo well formed, but carries no origin at all
        {"source_info_present": True, "source_info_well_formed": True},
        # sourceInfo well formed with an origin that is neither cli nor inline
        {
            "source_info_present": True,
            "source_info_well_formed": True,
            "source_info_source": "workspace",
        },
    ],
)
def test_unrecognized_extension_command_provenance_fails_closed(
    run_workspace: QualificationRunWorkspace, bad_entry_kwargs: dict
) -> None:
    stranger = ObservedCommand(
        name="mystery", source=EXTENSION_COMMAND_SOURCE, **bad_entry_kwargs
    )
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"], commands=GENUINE_COMMANDS + (stranger,)
    )
    result, _ = _run(run_workspace, harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.EXTENSION_COMMAND_NAMESPACE
    assert result.failure_code is CategoryBFailureCode.EXTENSION_COMMAND_PROVENANCE_UNKNOWN


def test_a_sentinel_with_unrecognized_provenance_fails_closed(
    run_workspace: QualificationRunWorkspace,
) -> None:
    """Even AIDO's OWN sentinel is refused when its provenance is unreadable."""
    broken_sentinel = ObservedCommand(
        name=SENTINEL_COMMAND_NAME,
        source=EXTENSION_COMMAND_SOURCE,
        source_info_present=True,
        source_info_well_formed=False,
    )
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"], commands=(broken_sentinel, GENUINE_LLAMA_COMMAND)
    )
    result, _ = _run(run_workspace, harness=harness)

    _assert_refusal(result)
    assert result.failure_code is CategoryBFailureCode.EXTENSION_COMMAND_PROVENANCE_UNKNOWN


def test_the_one_cli_entry_must_be_the_sentinel(
    run_workspace: QualificationRunWorkspace,
) -> None:
    """A single CLI entry that is not the sentinel is not AIDO's extension."""
    impostor = ObservedCommand(
        name="someone_elses_command",
        source=EXTENSION_COMMAND_SOURCE,
        source_info_present=True,
        source_info_well_formed=True,
        source_info_source=CLI_EXTENSION_ORIGIN_KIND,
    )
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"], commands=(impostor, GENUINE_LLAMA_COMMAND)
    )
    result, _ = _run(run_workspace, harness=harness)

    _assert_refusal(result)
    assert result.failure_code is CategoryBFailureCode.UNEXPECTED_CLI_EXTENSION_COMMAND


def test_the_cli_entry_must_be_the_h1_validated_sentinel(
    run_workspace: QualificationRunWorkspace,
) -> None:
    """A sentinel-named CLI entry whose H1 failed cannot satisfy the namespace gate."""
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"],
        h1_components={"sentinel_path_resolves_to_expected_entry": False},
    )
    result, _ = _run(run_workspace, harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.H1_EXTENSION_IDENTITY
    assert result.facts.h1_extension_identity_matched is False
    assert result.facts.no_unexpected_extension_command_observed is False
    assert (
        result.gate_statuses[CategoryBGateName.EXTENSION_COMMAND_NAMESPACE.value]
        == f"FAILED:{CategoryBFailureCode.UNEXPECTED_CLI_EXTENSION_COMMAND.value}"
    )


def test_the_sentinel_name_is_aidos_own_bytes_not_an_adapter_nomination(
    run_workspace: QualificationRunWorkspace,
) -> None:
    """Found in post-implementation self-review, and closed.

    ``sentinel_command_name`` arrives on the observation. Left unpinned, an
    adapter could nominate Pi's OWN ``llama`` as "the sentinel", mark it
    ``"cli"``, and have both H1 and the namespace partition evaluated against
    that nomination -- a fabricated identity dressed as an observation. AIDO
    now declares the name itself and refuses any other.
    """
    assert CATEGORY_B_SENTINEL_COMMAND_NAME == SENTINEL_COMMAND_NAME
    with pytest.raises(ObservationError):
        GetCommandsObservation(
            runtime_session_id="rt-1",
            call_succeeded=True,
            response_shape_understood=True,
            sentinel_command_name="llama",
            commands=GENUINE_COMMANDS,
            **PASSING_H1_COMPONENTS,
        )
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], sentinel_command_name="llama")
    result, _ = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.GET_COMMANDS
    assert result.failure_code is CategoryBFailureCode.ADAPTER_RAISED


def test_h1_components_that_disagree_with_the_reported_list_fail_closed(
    run_workspace: QualificationRunWorkspace,
) -> None:
    """H1 claiming a sentinel the command list does not contain is refused.

    The two facts come from ONE response, so they cannot honestly disagree.
    When they do, the namespace partition has no CLI entry to match and the
    gate fails closed rather than inheriting H1's word for it.
    """
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], commands=(GENUINE_LLAMA_COMMAND,))
    result, _ = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.facts.h1_extension_identity_matched is True
    assert result.failed_gate is CategoryBGateName.EXTENSION_COMMAND_NAMESPACE
    assert result.failure_code is CategoryBFailureCode.UNEXPECTED_CLI_EXTENSION_COMMAND


def test_no_command_entry_at_all_fails_the_namespace_gate(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"],
        commands=(),
        h1_components={
            "sentinel_name_matched": False,
            "sentinel_source_is_extension": False,
            "sentinel_path_resolves_to_expected_entry": False,
        },
    )
    result, _ = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.H1_EXTENSION_IDENTITY


def test_an_unbounded_reported_command_list_is_refused() -> None:
    entries = tuple(
        ObservedCommand(name=f"c{index}", source="builtin") for index in range(257)
    )
    with pytest.raises(ObservationError):
        GetCommandsObservation(
            runtime_session_id="rt-1",
            call_succeeded=True,
            response_shape_understood=True,
            sentinel_command_name=SENTINEL_COMMAND_NAME,
            commands=entries,
            **PASSING_H1_COMPONENTS,
        )


@pytest.mark.parametrize("name", ["", "a" * 65, "has space", "C:\\path\\index.ts", "a;b"])
def test_a_malformed_command_name_is_refused_at_construction(name: str) -> None:
    with pytest.raises(ObservationError):
        ObservedCommand(name=name, source=EXTENSION_COMMAND_SOURCE)


@pytest.mark.parametrize("entry", [None, "aido_read", 7, ("aido_read", "extension")])
def test_a_non_observed_command_entry_is_refused(entry) -> None:
    with pytest.raises(ObservationError):
        GetCommandsObservation(
            runtime_session_id="rt-1",
            call_succeeded=True,
            response_shape_understood=True,
            sentinel_command_name=SENTINEL_COMMAND_NAME,
            commands=(entry,),
            **PASSING_H1_COMPONENTS,
        )


def test_observed_command_provenance_flags_cannot_contradict_each_other() -> None:
    with pytest.raises(ObservationError):
        ObservedCommand(
            name="x",
            source=EXTENSION_COMMAND_SOURCE,
            source_info_present=False,
            source_info_well_formed=True,
        )
    with pytest.raises(ObservationError):
        ObservedCommand(
            name="x",
            source=EXTENSION_COMMAND_SOURCE,
            source_info_present=True,
            source_info_well_formed=False,
            source_info_source=CLI_EXTENSION_ORIGIN_KIND,
        )


@pytest.mark.parametrize("value", [None, "", "false", 0, 1, object()])
def test_observed_command_provenance_flags_reject_non_bool(value) -> None:
    with pytest.raises(ObservationError):
        ObservedCommand(
            name="x", source=EXTENSION_COMMAND_SOURCE, source_info_present=value
        )


# -- the raw-entry projection a future live adapter must use ------------------


def test_the_raw_entry_projection_reproduces_the_genuine_shape() -> None:
    sentinel = observed_command_from_reported_entry(
        {
            "name": SENTINEL_COMMAND_NAME,
            "source": "extension",
            "sourceInfo": {"path": SYNTHETIC_EXTENSION_ENTRY, "source": "cli"},
        }
    )
    llama = observed_command_from_reported_entry(
        {
            "name": "llama",
            "source": "extension",
            "sourceInfo": {"path": "<inline:llama.cpp>", "source": "inline"},
        }
    )
    assert sentinel == GENUINE_SENTINEL_COMMAND
    assert llama == GENUINE_LLAMA_COMMAND
    # the reported paths -- an AIDO absolute path and Pi's inline marker --
    # are inputs, never retained fields
    for command in (sentinel, llama):
        assert SYNTHETIC_EXTENSION_ENTRY not in repr(command)
        assert "llama.cpp" not in repr(command)


@pytest.mark.parametrize(
    "entry, expect_present, expect_well_formed, expect_origin",
    [
        ({"name": "a", "source": "extension"}, False, False, None),
        ({"name": "a", "source": "extension", "sourceInfo": None}, False, False, None),
        ({"name": "a", "source": "extension", "sourceInfo": "cli"}, True, False, None),
        ({"name": "a", "source": "extension", "sourceInfo": ["cli"]}, True, False, None),
        ({"name": "a", "source": "extension", "sourceInfo": {}}, True, True, None),
        (
            {"name": "a", "source": "extension", "sourceInfo": {"source": 7}},
            True,
            False,
            None,
        ),
        (
            {"name": "a", "source": "extension", "sourceInfo": {"source": "C:\\x\\y"}},
            True,
            False,
            None,
        ),
        (
            {"name": "a", "source": "extension", "sourceInfo": {"source": "inline"}},
            True,
            True,
            "inline",
        ),
    ],
)
def test_the_raw_entry_projection_bounds_every_malformed_source_info(
    entry, expect_present, expect_well_formed, expect_origin
) -> None:
    command = observed_command_from_reported_entry(entry)
    assert command.source_info_present is expect_present
    assert command.source_info_well_formed is expect_well_formed
    assert command.source_info_source == expect_origin
    if expect_origin not in (CLI_EXTENSION_ORIGIN_KIND, INLINE_EXTENSION_ORIGIN_KIND):
        assert not command.provenance_is_cli and not command.provenance_is_inline


@pytest.mark.parametrize("entry", [None, "aido", 7, ["name"]])
def test_the_raw_entry_projection_refuses_a_non_object_entry(entry) -> None:
    with pytest.raises(ObservationError):
        observed_command_from_reported_entry(entry)


# -- H1: components, AIDO-derived verdict, differential conformance -----------


def test_h1_is_never_a_single_adapter_supplied_verdict() -> None:
    """No field on the observation can, alone, authorize H1."""
    assert not hasattr(GetCommandsObservation, "extension_identity_matched")
    for missing in H1_COMPONENT_FIELDS:
        components = dict(PASSING_H1_COMPONENTS)
        components[missing] = not components[missing]
        observation = GetCommandsObservation(
            runtime_session_id="rt-1",
            call_succeeded=True,
            response_shape_understood=True,
            sentinel_command_name=SENTINEL_COMMAND_NAME,
            commands=GENUINE_COMMANDS,
            **components,
        )
        assert observation.h1_identity_established is False, missing


def _h1_corpus() -> list[tuple[str, list]]:
    """The adversarial corpus design FU3 Sec. 6.3(c) requires, at minimum."""
    entry = SYNTHETIC_EXTENSION_ENTRY
    other = os.path.join(os.path.dirname(__file__), "somewhere_else.ts")
    return [
        ("sentinel absent", []),
        (
            "sentinel present, source is not extension",
            [{"name": SENTINEL_COMMAND_NAME, "source": "builtin",
              "sourceInfo": {"path": entry, "source": "cli"}}],
        ),
        (
            "correct name and source, non-matching path",
            [{"name": SENTINEL_COMMAND_NAME, "source": "extension",
              "sourceInfo": {"path": other, "source": "cli"}}],
        ),
        (
            "sourceInfo present but not an object",
            [{"name": SENTINEL_COMMAND_NAME, "source": "extension", "sourceInfo": "cli"}],
        ),
        (
            "sourceInfo.path present but not a string",
            [{"name": SENTINEL_COMMAND_NAME, "source": "extension",
              "sourceInfo": {"path": 7, "source": "cli"}}],
        ),
        (
            "flat path present but not a string",
            [{"name": SENTINEL_COMMAND_NAME, "source": "extension", "path": 7}],
        ),
        (
            "neither path field usable",
            [{"name": SENTINEL_COMMAND_NAME, "source": "extension", "sourceInfo": {}}],
        ),
        (
            "flat path only, matching (AR1's documented fallback)",
            [{"name": SENTINEL_COMMAND_NAME, "source": "extension", "path": entry}],
        ),
        (
            "contradicting sourceInfo.source",
            [{"name": SENTINEL_COMMAND_NAME, "source": "extension",
              "sourceInfo": {"path": entry, "source": "inline"}}],
        ),
        (
            "the genuine match",
            [{"name": SENTINEL_COMMAND_NAME, "source": "extension",
              "sourceInfo": {"path": entry, "source": "cli"}}],
        ),
        (
            "AR1's observed real-world shape: sentinel + Pi's inline llama",
            [
                {"name": SENTINEL_COMMAND_NAME, "source": "extension",
                 "sourceInfo": {"path": entry, "source": "cli", "scope": "temporary"}},
                {"name": "llama", "source": "extension",
                 "sourceInfo": {"path": "<inline:llama.cpp>", "source": "inline"}},
            ],
        ),
        (
            "two sentinel-named extension entries, one with a wrong path",
            [
                {"name": SENTINEL_COMMAND_NAME, "source": "extension",
                 "sourceInfo": {"path": other, "source": "cli"}},
                {"name": SENTINEL_COMMAND_NAME, "source": "extension",
                 "sourceInfo": {"path": entry, "source": "cli"}},
            ],
        ),
        (
            "sentinel-named entry that is not a dict at all",
            ["not-an-object", {"name": SENTINEL_COMMAND_NAME, "source": "extension",
                               "sourceInfo": {"path": entry, "source": "cli"}}],
        ),
        (
            "an unbounded reported origin kind",
            [{"name": SENTINEL_COMMAND_NAME, "source": "extension",
              "sourceInfo": {"path": entry, "source": "a" * 64}}],
        ),
        (
            "a non-string reported origin kind",
            [{"name": SENTINEL_COMMAND_NAME, "source": "extension",
              "sourceInfo": {"path": entry, "source": 7}}],
        ),
        (
            "a reported origin kind that is an object",
            [{"name": SENTINEL_COMMAND_NAME, "source": "extension",
              "sourceInfo": {"path": entry, "source": {"kind": "cli"}}}],
        ),
    ]


def test_h1_projection_is_differentially_conformant_with_the_frozen_evaluator() -> None:
    """The adapter's projection must AGREE with the frozen rule on every row.

    Design FU3 Sec. 6.3(c). The frozen
    ``ar2.handshakes.evaluate_extension_identity`` is called UNMODIFIED; the
    projection maps its dict field-for-field; and AIDO's own conjunction over
    the projected components must equal the frozen ``passed`` exactly.

    A row whose reported origin kind is not a bounded token is REFUSED by the
    projection rather than retained -- and the frozen evaluator computes
    ``passed=False`` for every such row, so refusing can never turn a frozen
    pass into a projection failure.
    """
    checked = 0
    for label, commands in _h1_corpus():
        frozen = evaluate_extension_identity(
            list(commands), extension_entry=SYNTHETIC_EXTENSION_ENTRY
        )
        try:
            projected = h1_components_from_frozen_evaluation(frozen)
            observation = GetCommandsObservation(
                runtime_session_id="rt-1",
                call_succeeded=True,
                response_shape_understood=True,
                commands=(),
                **projected,
            )
        except ObservationError:
            assert frozen["passed"] is False, label
            continue

        assert observation.sentinel_name_matched is frozen["sentinel_name_matched"], label
        assert (
            observation.sentinel_source_is_extension is frozen["extension_source_matched"]
        ), label
        assert (
            observation.sentinel_path_resolves_to_expected_entry
            is frozen["extension_path_matched"]
        ), label
        assert (
            observation.noncontradictory_source_origin
            is frozen["noncontradictory_source_origin"]
        ), label
        assert (
            observation.malformed_source_metadata is frozen["malformed_source_metadata"]
        ), label
        assert observation.h1_identity_established is frozen["passed"], label
        assert observation.expected_source_kind == frozen["expected_source_kind"]
        checked += 1
    assert checked >= 12


def test_the_projection_never_carries_the_frozen_evaluators_free_text() -> None:
    frozen = evaluate_extension_identity([], extension_entry=SYNTHETIC_EXTENSION_ENTRY)
    assert frozen["failure_reasons"], "the corpus row must actually produce reasons"
    projected = h1_components_from_frozen_evaluation(frozen)
    assert "failure_reasons" not in projected
    assert "passed" not in projected
    assert "proves" not in projected and "does_not_prove" not in projected


def test_the_projection_refuses_an_incomplete_frozen_evaluation() -> None:
    frozen = evaluate_extension_identity([], extension_entry=SYNTHETIC_EXTENSION_ENTRY)
    del frozen["extension_path_matched"]
    with pytest.raises(ObservationError):
        h1_components_from_frozen_evaluation(frozen)
    with pytest.raises(ObservationError):
        h1_components_from_frozen_evaluation("not a mapping")


def test_h1_is_only_evaluated_against_the_cli_origin_kind() -> None:
    assert EXPECTED_EXTENSION_SOURCE_KIND == CLI_EXTENSION_ORIGIN_KIND
    with pytest.raises(ObservationError):
        GetCommandsObservation(
            runtime_session_id="rt-1",
            call_succeeded=True,
            response_shape_understood=True,
            sentinel_command_name=SENTINEL_COMMAND_NAME,
            expected_source_kind="inline",
            **PASSING_H1_COMPONENTS,
        )


def test_an_unusable_get_commands_response_cannot_also_claim_h1() -> None:
    with pytest.raises(ObservationError):
        GetCommandsObservation(
            runtime_session_id="rt-1",
            call_succeeded=False,
            response_shape_understood=False,
            sentinel_command_name=SENTINEL_COMMAND_NAME,
            **PASSING_H1_COMPONENTS,
        )
    with pytest.raises(ObservationError):
        GetCommandsObservation(
            runtime_session_id="rt-1",
            call_succeeded=True,
            response_shape_understood=False,
            sentinel_command_name=SENTINEL_COMMAND_NAME,
            **PASSING_H1_COMPONENTS,
        )
    with pytest.raises(ObservationError):
        GetCommandsObservation(
            runtime_session_id="rt-1",
            call_succeeded=False,
            response_shape_understood=True,
            sentinel_command_name=SENTINEL_COMMAND_NAME,
        )
    with pytest.raises(ObservationError):
        GetCommandsObservation(
            runtime_session_id="rt-1",
            call_succeeded=False,
            response_shape_understood=False,
            sentinel_command_name=SENTINEL_COMMAND_NAME,
            commands=GENUINE_COMMANDS,
        )


def test_h1_and_the_namespace_gate_derive_from_one_get_commands_observation(
    run_workspace: QualificationRunWorkspace,
) -> None:
    result, harness = _run(run_workspace)
    assert harness.count("get_commands") == 1
    assert result.facts.h1_extension_identity_matched is True
    assert result.facts.no_unexpected_extension_command_observed is True
    assert result.facts.get_commands_response_shape_understood is True


def test_get_commands_call_failure_stops_before_h1(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"],
        commands_call_succeeded=False,
        commands_shape_understood=False,
        commands=(),
        h1_components={
            "sentinel_name_matched": False,
            "sentinel_source_is_extension": False,
            "sentinel_path_resolves_to_expected_entry": False,
        },
    )
    harness.commands_result_override = GetCommandsObservation(
        runtime_session_id="rt-session-0001",
        call_succeeded=False,
        response_shape_understood=False,
        sentinel_command_name=SENTINEL_COMMAND_NAME,
    )
    result, harness = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.failure_code is CategoryBFailureCode.GET_COMMANDS_FAILED
    assert result.facts.h1_extension_identity_matched is False


# -- PRE-CREDENTIAL ORDERING (design FU3 Sec. 7) ------------------------------


def test_the_credential_read_gate_comes_after_every_pre_credential_gate() -> None:
    """A source-level assertion, not merely a behavioural one."""
    order = {gate: index for index, gate in enumerate(COMPATIBILITY_GATES)}
    for gate in PRE_CREDENTIAL_GATES:
        assert order[gate] < order[CREDENTIAL_READ_GATE], gate.value
    assert PRE_CREDENTIAL_GATES == (
        CategoryBGateName.RUN_CORRELATION,
        CategoryBGateName.WORKSPACE_AUTHORITY,
        CategoryBGateName.ROUTE_DESCRIPTOR,
        CategoryBGateName.NON_SECRET_PREFLIGHT,
    )
    assert CREDENTIAL_READ_GATE is CategoryBGateName.CONNECTION_VALUES
    # ...and the enum's own declaration order agrees with the gate tuple
    assert [gate for gate in CategoryBGateName][: len(COMPATIBILITY_GATES)] == list(
        COMPATIBILITY_GATES
    )


def test_an_unknown_candidate_causes_zero_credential_reads(
    run_workspace: QualificationRunWorkspace,
) -> None:
    reader = _CountingReader()
    harness = _Harness(model_id="unused")
    result, harness = _run(
        run_workspace, candidate="typo", harness=harness, read_connection=reader
    )

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.ROUTE_DESCRIPTOR
    assert result.failure_code is CategoryBFailureCode.ROUTE_DESCRIPTOR_INVALID
    assert reader.calls == 0
    assert harness.calls == []
    assert result.gate_statuses[CategoryBGateName.CONNECTION_VALUES.value] == "NOT_REACHED"


def test_an_unverifiable_workspace_causes_zero_credential_reads(
    run_workspace: QualificationRunWorkspace,
) -> None:
    reader = _CountingReader()
    # Tamper: remove the marker the frozen AR2 verification re-reads.
    os.remove(os.path.join(run_workspace.experiment_root, ROOT_AUTHORITY_MARKER_FILENAME))
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"])
    result, harness = _run(run_workspace, harness=harness, read_connection=reader)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.WORKSPACE_AUTHORITY
    assert result.failure_code is CategoryBFailureCode.WORKSPACE_AUTHORITY_UNVERIFIED
    assert reader.calls == 0
    assert harness.calls == []
    assert result.gate_statuses[CategoryBGateName.ROUTE_DESCRIPTOR.value] == "NOT_REACHED"


def test_a_workspace_already_claimed_by_another_run_causes_zero_credential_reads(
    run_workspace: QualificationRunWorkspace,
) -> None:
    claim_run_workspace(run_workspace, run_id="some-other-run")
    reader = _CountingReader()
    result, harness = _run(run_workspace, read_connection=reader)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.WORKSPACE_AUTHORITY
    assert reader.calls == 0
    assert harness.calls == []


def test_cross_run_reuse_of_one_workspace_is_refused(
    run_workspace: QualificationRunWorkspace,
) -> None:
    first, _ = _run(run_workspace)
    assert first.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED

    reader = _CountingReader()
    second, harness = _run(run_workspace, read_connection=reader)
    _assert_refusal(second)
    assert second.failed_gate is CategoryBGateName.WORKSPACE_AUTHORITY
    assert reader.calls == 0
    assert harness.calls == []


def test_a_correlation_id_failure_is_a_bounded_zero_credential_refusal(
    run_workspace: QualificationRunWorkspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom() -> str:
        raise OSError("synthetic entropy exhaustion")

    monkeypatch.setattr(i2b_controller_module, "_mint_run_correlation_id", _boom)
    reader = _CountingReader()
    result, harness = _run(run_workspace, read_connection=reader)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.RUN_CORRELATION
    assert result.failure_code is CategoryBFailureCode.RUN_CORRELATION_UNAVAILABLE
    assert reader.calls == 0
    assert harness.calls == []
    assert result.semantic_prompts_sent == 0
    assert result.pi_config_created is False
    assert result.broker_created is False
    assert result.runtime_session_established is False
    assert result.runtime_teardown.status_text == "NOT_REQUIRED"
    assert result.broker_shutdown.status_text == "NOT_REQUIRED"
    assert result.cleanup.status_text == "NOT_REQUIRED"
    # the raw exception text is nowhere in the retained evidence or the result
    assert "entropy" not in result.evidence.as_json()
    assert "entropy" not in repr(result)


def test_a_failing_non_secret_gate_still_causes_zero_credential_reads(
    run_workspace: QualificationRunWorkspace,
) -> None:
    reader = _CountingReader()
    gates = [
        lambda: PreflightGateResult(name="pi_installed_offline", passed=True),
        lambda: PreflightGateResult(
            name="config_generator_self_check",
            passed=False,
            failure_code="CONFIG_GENERATOR_SELF_CHECK_FAILED",
        ),
    ]
    result, harness = _run(run_workspace, non_secret_gates=gates, read_connection=reader)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.NON_SECRET_PREFLIGHT
    assert reader.calls == 0
    assert harness.calls == []


def test_the_connection_reader_is_called_exactly_once_on_the_pass_path(
    run_workspace: QualificationRunWorkspace,
) -> None:
    reader = _CountingReader()
    result, _ = _run(run_workspace, read_connection=reader)
    assert result.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED
    assert reader.calls == 1


def test_an_unavailable_connection_value_is_a_zero_prompt_refusal(
    run_workspace: QualificationRunWorkspace,
) -> None:
    def _blank_reader() -> ConnectionValues:
        return ConnectionValues(base_url="", api_key="")

    result, harness = _run(run_workspace, read_connection=_blank_reader)
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.CONNECTION_VALUES
    assert result.failure_code is CategoryBFailureCode.CONNECTION_VALUES_UNAVAILABLE
    assert result.gate_statuses[CategoryBGateName.NON_SECRET_PREFLIGHT.value] == "PASSED"
    assert "create_broker" not in harness.calls


# -- SYNTHETIC WORKSPACE AUTHORITY (design FU3 Sec. 8) ------------------------


def test_the_controller_has_no_path_parameter_at_all() -> None:
    parameters = set(inspect.signature(run_category_b_controller).parameters)
    assert "workspace_root" not in parameters
    assert "experiment_root" not in parameters
    for name in parameters:
        assert "path" not in name.lower()
        assert not name.lower().endswith("_root") or name == "run_workspace"


def test_no_function_converts_an_existing_path_into_workspace_authority() -> None:
    """The whole property: authority originates at CREATION, never from a string."""
    for name, value in vars(i2b_workspace_module).items():
        if name.startswith("_") or not inspect.isfunction(value):
            continue
        if value.__module__ != i2b_workspace_module.__name__:
            continue
        for parameter in inspect.signature(value).parameters.values():
            assert "path" not in parameter.name.lower(), (name, parameter.name)
            assert "root" not in parameter.name.lower(), (name, parameter.name)
            assert "dir" not in parameter.name.lower(), (name, parameter.name)
    # ...and the one minting function takes NO argument that could steer it
    assert inspect.signature(mint_qualification_run_workspace).parameters == {}


def test_a_workspace_object_cannot_be_forged_for_an_arbitrary_directory(
    run_workspace: QualificationRunWorkspace, tmp_path: Path
) -> None:
    with pytest.raises(WorkspaceAuthorityError):
        QualificationRunWorkspace(
            run_workspace_nonce="deadbeef",
            experiment_root=str(tmp_path),
            workspace_root=str(tmp_path / "repo"),
        )
    # a REGISTERED nonce cannot be re-pointed at another directory either
    with pytest.raises(WorkspaceAuthorityError):
        QualificationRunWorkspace(
            run_workspace_nonce=run_workspace.run_workspace_nonce,
            experiment_root=str(tmp_path),
            workspace_root=str(tmp_path / "repo"),
        )


def test_a_substituted_workspace_object_is_refused_by_the_controller(
    run_workspace: QualificationRunWorkspace, tmp_path: Path
) -> None:
    @dataclass(frozen=True)
    class _LookAlike:
        run_workspace_nonce: str = "look-alike"
        experiment_root: str = str(tmp_path)
        workspace_root: str = str(tmp_path)

    with pytest.raises(CategoryBControllerInputError):
        _run(_LookAlike())  # type: ignore[arg-type]
    assert not (tmp_path / "i2_pi_config").exists()


def test_a_subclass_of_the_workspace_type_is_refused_everywhere(
    run_workspace: QualificationRunWorkspace,
) -> None:
    """Found in post-implementation self-review: EXACT type, never isinstance.

    A subclass could override ``workspace_root`` with a property returning a
    different value on each read -- passing verification and then naming
    something else at the consumption boundary.
    """

    class _Sneaky(QualificationRunWorkspace):
        pass

    sneaky = _Sneaky(
        run_workspace_nonce=run_workspace.run_workspace_nonce,
        experiment_root=run_workspace.experiment_root,
        workspace_root=run_workspace.workspace_root,
    )
    with pytest.raises(WorkspaceAuthorityError):
        verify_run_workspace(sneaky)
    with pytest.raises(CategoryBControllerInputError):
        _run(sneaky)  # type: ignore[arg-type]
    claim_run_workspace(run_workspace, run_id="run-1")
    with pytest.raises(ObservationError):
        BrokerCreationRequest(run_id="run-1", workspace=sneaky)


def test_discarding_a_workspace_cannot_resurrect_or_relaunder_authority(
    run_workspace: QualificationRunWorkspace,
) -> None:
    """The public discard removes the MINT record, not merely the claim."""
    claim_run_workspace(run_workspace, run_id="run-1")
    i2b_workspace_module.discard_run_workspace(run_workspace)
    with pytest.raises(WorkspaceAuthorityError):
        verify_run_workspace(run_workspace)
    with pytest.raises(WorkspaceAuthorityError):
        claim_run_workspace(run_workspace, run_id="run-2")
    with pytest.raises(WorkspaceAuthorityError):
        QualificationRunWorkspace(
            run_workspace_nonce=run_workspace.run_workspace_nonce,
            experiment_root=run_workspace.experiment_root,
            workspace_root=run_workspace.workspace_root,
        )
    # ...and the controller itself refuses it at WORKSPACE_AUTHORITY, before
    # the route descriptor and long before any credential read.
    reader = _CountingReader()
    result, harness = _run(run_workspace, read_connection=reader)
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.WORKSPACE_AUTHORITY
    assert reader.calls == 0
    assert harness.calls == []


def test_the_minted_workspace_lives_under_the_approved_scratch_boundary(
    run_workspace: QualificationRunWorkspace,
) -> None:
    from ar2.capability import approved_scratch_boundary, diagnostic_forbidden_root_reason

    boundary = approved_scratch_boundary()
    assert os.path.normcase(run_workspace.experiment_root).startswith(boundary + os.sep)
    assert diagnostic_forbidden_root_reason(run_workspace.experiment_root) is None
    assert diagnostic_forbidden_root_reason(run_workspace.workspace_root) is None
    assert os.path.isdir(run_workspace.workspace_root)


def test_workspace_relocation_after_validation_fails_closed(
    run_workspace: QualificationRunWorkspace,
) -> None:
    verify_run_workspace(run_workspace)
    os.rename(
        run_workspace.workspace_root, run_workspace.workspace_root + "_moved"
    )
    try:
        with pytest.raises(WorkspaceAuthorityError):
            verify_run_workspace(run_workspace)
    finally:
        os.rename(run_workspace.workspace_root + "_moved", run_workspace.workspace_root)


def test_workspace_marker_tampering_after_validation_fails_closed(
    run_workspace: QualificationRunWorkspace,
) -> None:
    verify_run_workspace(run_workspace)
    marker = os.path.join(run_workspace.experiment_root, ROOT_AUTHORITY_MARKER_FILENAME)
    original = Path(marker).read_text(encoding="utf-8")
    tampered = json.loads(original)
    tampered["nonce"] = "0" * 32
    Path(marker).write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(WorkspaceAuthorityError):
        verify_run_workspace(run_workspace)
    Path(marker).write_text(original, encoding="utf-8")
    assert verify_run_workspace(run_workspace) == run_workspace.workspace_root


def test_tampering_between_the_gate_and_the_config_write_fails_closed(
    run_workspace: QualificationRunWorkspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The consumption boundary re-verifies -- it never trusts the earlier gate."""
    marker = os.path.join(run_workspace.experiment_root, ROOT_AUTHORITY_MARKER_FILENAME)
    original = Path(marker).read_text(encoding="utf-8")
    real_claim = i2b_workspace_module.claim_run_workspace

    def _claim_then_tamper(workspace, *, run_id):
        real_claim(workspace, run_id=run_id)
        os.remove(marker)

    monkeypatch.setattr(i2b_controller_module, "claim_run_workspace", _claim_then_tamper)
    try:
        result, harness = _run(run_workspace)
    finally:
        Path(marker).write_text(original, encoding="utf-8")

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.PI_CONFIG_GENERATION
    assert result.failure_code is CategoryBFailureCode.WORKSPACE_AUTHORITY_UNVERIFIED
    assert result.pi_config_created is False
    assert "create_broker" not in harness.calls


def test_the_run_workspace_binds_config_broker_and_launch_to_one_identity(
    run_workspace: QualificationRunWorkspace,
) -> None:
    result, harness = _run(run_workspace)
    assert result.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED
    assert harness.creation_request is not None and harness.launch_request is not None
    assert harness.creation_request.workspace is run_workspace
    assert harness.launch_request.workspace is run_workspace
    assert harness.creation_request.workspace_root == run_workspace.workspace_root
    assert harness.launch_request.workspace_root == run_workspace.workspace_root


def test_a_request_for_an_unclaimed_or_foreign_workspace_is_unconstructible(
    run_workspace: QualificationRunWorkspace, second_run_workspace: QualificationRunWorkspace
) -> None:
    with pytest.raises(ObservationError):
        BrokerCreationRequest(run_id="run-a", workspace=run_workspace)
    claim_run_workspace(run_workspace, run_id="run-a")
    BrokerCreationRequest(run_id="run-a", workspace=run_workspace)
    with pytest.raises(ObservationError):
        BrokerCreationRequest(run_id="run-b", workspace=run_workspace)
    with pytest.raises(ObservationError):
        BrokerCreationRequest(run_id="run-a", workspace=second_run_workspace)
    with pytest.raises(ObservationError):
        BrokerCreationRequest(run_id="run-a", workspace=run_workspace.workspace_root)


def test_a_workspace_request_repr_never_prints_a_path(
    run_workspace: QualificationRunWorkspace,
) -> None:
    claim_run_workspace(run_workspace, run_id="run-a")
    request = BrokerCreationRequest(run_id="run-a", workspace=run_workspace)
    for rendered in (repr(request), str(request), repr(run_workspace), str(run_workspace)):
        assert run_workspace.experiment_root not in rendered
        assert run_workspace.workspace_root not in rendered


# -- frozen O1 lifecycle: broker created and READY BEFORE the launch ----------


def test_broker_is_created_and_ready_before_the_runtime_launch(
    run_workspace: QualificationRunWorkspace,
) -> None:
    result, harness = _run(run_workspace)
    assert harness.calls.index("create_broker") < harness.calls.index("launch_runtime")
    assert result.gate_statuses[CategoryBGateName.BROKER_READY.value] == "PASSED"
    assert result.facts.broker_reached_required_ready_state is True


def test_launch_consumes_the_exact_broker_binding_it_needs(
    run_workspace: QualificationRunWorkspace,
) -> None:
    result, harness = _run(run_workspace)
    assert harness.launch_request is not None
    assert harness.launch_request.broker_session is harness.broker
    assert harness.launch_request.broker_session.pipe_name == SYNTHETIC_PIPE_NAME
    assert harness.launch_request.broker_session.capability_id == SYNTHETIC_CAPABILITY_ID
    assert harness.launch_request.broker_session.broker_token == SYNTHETIC_BROKER_TOKEN
    assert harness.launch_request.model_id == CANDIDATE_MODEL_IDS["A"]
    assert result.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED


def test_broker_not_ready_refuses_before_any_launch(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], broker_ready=False)
    result, harness = _run(run_workspace, harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.BROKER_READY
    assert result.failure_code is CategoryBFailureCode.BROKER_NOT_READY
    assert "launch_runtime" not in harness.calls
    assert result.facts.broker_reached_required_ready_state is False
    # the broker that WAS created, and IS this run's own, is still closed
    assert harness.count("shutdown_broker") == 1
    assert result.broker_shutdown.reached_closed is True


def test_launch_request_is_unconstructible_for_a_not_ready_broker(
    run_workspace: QualificationRunWorkspace,
) -> None:
    claim_run_workspace(run_workspace, run_id="run-1")
    broker = BrokerSession(
        run_id="run-1",
        session_id="brk-1",
        pipe_name=SYNTHETIC_PIPE_NAME,
        capability_id=SYNTHETIC_CAPABILITY_ID,
        broker_token=SYNTHETIC_BROKER_TOKEN,
        reached_ready=False,
    )
    with pytest.raises(ObservationError):
        RuntimeLaunchRequest(
            run_id="run-1",
            broker_session=broker,
            launch_environment=_StubLaunchEnvironment(),
            workspace=run_workspace,
            provider_id=PROVIDER_ID,
            model_id=CANDIDATE_MODEL_IDS["A"],
        )


def test_launch_request_is_unconstructible_for_a_foreign_broker(
    run_workspace: QualificationRunWorkspace,
) -> None:
    claim_run_workspace(run_workspace, run_id="run-1")
    broker = BrokerSession(
        run_id="another-run",
        session_id="brk-1",
        pipe_name=SYNTHETIC_PIPE_NAME,
        capability_id=SYNTHETIC_CAPABILITY_ID,
        broker_token=SYNTHETIC_BROKER_TOKEN,
        reached_ready=True,
    )
    with pytest.raises(ObservationError):
        RuntimeLaunchRequest(
            run_id="run-1",
            broker_session=broker,
            launch_environment=_StubLaunchEnvironment(),
            workspace=run_workspace,
            provider_id=PROVIDER_ID,
            model_id=CANDIDATE_MODEL_IDS["A"],
        )


class _StubLaunchEnvironment:
    def as_launch_snapshot(self) -> dict:
        return {}


# -- POSSESSION IS NOT AUTHORITY (design FU3 Sec. 9.4) ------------------------


def test_a_foreign_broker_session_is_never_passed_to_shutdown_broker(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], broker_run_id_override="foreign-run-id")
    result, harness = _run(run_workspace, harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.BROKER_SESSION
    assert result.failure_code is CategoryBFailureCode.BROKER_SESSION_MISMATCH
    assert harness.count("shutdown_broker") == 0
    assert harness.count("launch_runtime") == 0
    assert result.broker_shutdown.state is ResourceClosureState.SHUTDOWN_REFUSED_FOREIGN_SESSION
    assert result.broker_shutdown.attempted is False
    assert result.broker_shutdown.authority_available is False
    assert result.broker_shutdown.closure_satisfied is False
    assert result.gate_statuses[CategoryBGateName.BROKER_SHUTDOWN.value] == (
        f"FAILED:{CategoryBFailureCode.BROKER_SHUTDOWN_REFUSED_FOREIGN_SESSION.value}"
    )


def test_a_foreign_runtime_run_id_is_never_passed_to_shutdown_runtime(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"], launch_session_run_id_override="foreign-run-id"
    )
    result, harness = _run(run_workspace, harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.RUNTIME_LAUNCH
    assert result.failure_code is CategoryBFailureCode.RUNTIME_SESSION_MISMATCH
    assert harness.count("shutdown_runtime") == 0
    assert result.runtime_teardown.state is ResourceClosureState.SHUTDOWN_REFUSED_FOREIGN_SESSION
    assert result.runtime_teardown.attempted is False
    assert result.runtime_teardown.authority_available is False
    assert result.runtime_teardown.closure_satisfied is False
    assert result.gate_statuses[CategoryBGateName.RUNTIME_TEARDOWN.value] == (
        f"FAILED:{CategoryBFailureCode.RUNTIME_SHUTDOWN_REFUSED_FOREIGN_SESSION.value}"
    )
    # ...and the run's OWN broker is still closed normally
    assert harness.count("shutdown_broker") == 1


def test_a_same_run_wrong_broker_runtime_session_is_never_torn_down(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"], launch_session_broker_id_override="brk-somewhere-else"
    )
    result, harness = _run(run_workspace, harness=harness)

    _assert_refusal(result)
    assert result.failure_code is CategoryBFailureCode.RUNTIME_SESSION_MISMATCH
    assert harness.count("shutdown_runtime") == 0
    assert result.runtime_teardown.state is ResourceClosureState.SHUTDOWN_REFUSED_FOREIGN_SESSION


def test_the_positive_control_still_tears_down_exactly_once(
    run_workspace: QualificationRunWorkspace,
) -> None:
    """The refusal must be specific to the foreign case, not a regression."""
    result, harness = _run(run_workspace)
    assert result.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED
    assert harness.count("shutdown_runtime") == 1
    assert harness.count("shutdown_broker") == 1
    assert result.runtime_teardown.state is ResourceClosureState.CLOSED_BY_ORCHESTRATOR
    assert result.broker_shutdown.state is ResourceClosureState.CLOSED_BY_ORCHESTRATOR
    assert result.runtime_teardown.attempted is True
    assert result.broker_shutdown.attempted is True
    assert harness.calls.index("shutdown_runtime") < harness.calls.index("shutdown_broker")


# -- CREATOR PARTIAL-FAILURE LIFECYCLE (design FU3 Sec. 9.3) ------------------


def test_runtime_state_1_nothing_created(run_workspace: QualificationRunWorkspace) -> None:
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"],
        launch_returns_no_session=True,
        launch_shape_valid=False,
        launch_resource_created=False,
    )
    result, harness = _run(run_workspace, harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.RUNTIME_LAUNCH
    assert harness.count("shutdown_runtime") == 0
    assert result.runtime_teardown.state is ResourceClosureState.NOT_REQUIRED
    assert result.runtime_teardown.closure_satisfied is True
    assert result.gate_statuses[CategoryBGateName.RUNTIME_TEARDOWN.value] == "NOT_REQUIRED"


def test_runtime_state_2_stranded_no_cleanup_attempt(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"],
        launch_returns_no_session=True,
        launch_shape_valid=False,
        launch_resource_created=True,
        launch_cleanup_attempted=False,
    )
    result, harness = _run(run_workspace, harness=harness)

    _assert_refusal(result)
    assert harness.count("shutdown_runtime") == 0
    status = result.runtime_teardown
    assert status.state is ResourceClosureState.PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT
    assert status.closure_satisfied is False
    assert status.attempted is False
    assert status.authority_available is False
    assert result.gate_statuses[CategoryBGateName.RUNTIME_TEARDOWN.value] == (
        "FAILED:PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT"
    )
    # ...and the truthful facts survive on the observation itself
    observation = RuntimeLaunchObservation(
        session=None,
        launch_shape_valid=False,
        required_flags_accepted=True,
        lf_jsonl_correlation_succeeded=False,
        observed_pi_version=SYNTHETIC_PI_VERSION,
        resource_created=True,
        cleanup_attempted=False,
    )
    assert observation.resource_created is True
    assert observation.cleanup_attempted is False
    assert observation.direct_child_reported_exit is None
    assert observation.cleanup_verified_success is False


def test_runtime_state_3_cleanup_attempted_and_verified(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"],
        launch_returns_no_session=True,
        launch_shape_valid=False,
        launch_resource_created=True,
        launch_cleanup_attempted=True,
        launch_direct_child_reported_exit=True,
    )
    result, harness = _run(run_workspace, harness=harness)

    _assert_refusal(result)
    assert harness.count("shutdown_runtime") == 0
    status = result.runtime_teardown
    assert status.state is ResourceClosureState.CLOSED_BY_CREATOR_VERIFIED
    assert status.closure_satisfied is True
    assert status.attempted is False  # the CREATOR closed it, not the controller
    assert result.gate_statuses[CategoryBGateName.RUNTIME_TEARDOWN.value] == (
        "CLOSED_BY_CREATOR_VERIFIED"
    )
    # a satisfied closure never becomes a pass on its own
    assert result.outcome is CategoryBOutcome.INFRASTRUCTURE_REFUSAL


def test_runtime_state_4_cleanup_attempted_but_unverified(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"],
        launch_returns_no_session=True,
        launch_shape_valid=False,
        launch_resource_created=True,
        launch_cleanup_attempted=True,
        launch_direct_child_reported_exit=False,
    )
    result, harness = _run(run_workspace, harness=harness)

    _assert_refusal(result)
    assert harness.count("shutdown_runtime") == 0
    status = result.runtime_teardown
    assert status.state is ResourceClosureState.CLOSED_BY_CREATOR_UNVERIFIED
    assert status.closure_satisfied is False
    assert result.gate_statuses[CategoryBGateName.RUNTIME_TEARDOWN.value] == (
        "FAILED:CLOSED_BY_CREATOR_UNVERIFIED"
    )


@pytest.mark.parametrize(
    "created, attempted, postcondition, expected_state",
    [
        (False, False, None, ResourceClosureState.NOT_REQUIRED),
        (
            True,
            False,
            None,
            ResourceClosureState.PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT,
        ),
        (True, True, True, ResourceClosureState.CLOSED_BY_CREATOR_VERIFIED),
        (True, True, False, ResourceClosureState.CLOSED_BY_CREATOR_UNVERIFIED),
    ],
)
def test_broker_creator_partial_states(
    run_workspace: QualificationRunWorkspace,
    created: bool,
    attempted: bool,
    postcondition: bool | None,
    expected_state: ResourceClosureState,
) -> None:
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"],
        broker_returns_no_session=True,
        broker_start_attempted=created,
        broker_resource_created=created,
        broker_cleanup_attempted=attempted,
        broker_reached_closed_on_partial=postcondition,
    )
    result, harness = _run(run_workspace, harness=harness)

    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.BROKER_SESSION
    assert harness.count("shutdown_broker") == 0
    assert harness.count("launch_runtime") == 0
    assert result.broker_shutdown.state is expected_state
    assert result.broker_shutdown.attempted is False
    assert result.broker_shutdown.closure_satisfied is (
        expected_state
        in (
            ResourceClosureState.NOT_REQUIRED,
            ResourceClosureState.CLOSED_BY_CREATOR_VERIFIED,
        )
    )


def test_state_teardown_incomplete_is_not_verified_closure() -> None:
    """``STATE_TEARDOWN_INCOMPLETE`` (``reached_closed=False``) never verifies."""
    incomplete = BrokerCreationObservation(
        session=None,
        start_attempted=True,
        resource_created=True,
        cleanup_attempted=True,
        reached_closed=False,
    )
    closed = BrokerCreationObservation(
        session=None,
        start_attempted=True,
        resource_created=True,
        cleanup_attempted=True,
        reached_closed=True,
    )
    assert incomplete.cleanup_verified_success is False
    assert closed.cleanup_verified_success is True


def test_a_direct_child_that_did_not_report_exit_never_verifies() -> None:
    not_exited = RuntimeLaunchObservation(
        session=None,
        launch_shape_valid=False,
        required_flags_accepted=False,
        lf_jsonl_correlation_succeeded=False,
        observed_pi_version=None,
        resource_created=True,
        cleanup_attempted=True,
        direct_child_reported_exit=False,
    )
    exited = dataclasses.replace(not_exited, direct_child_reported_exit=True)
    assert not_exited.cleanup_verified_success is False
    assert exited.cleanup_verified_success is True


def test_the_creator_can_never_supply_the_generic_cleanup_verdict() -> None:
    """FU3C: no constructor argument, field, alias or mapping path exists."""
    for observation_type in (RuntimeLaunchObservation, BrokerCreationObservation):
        names = {spec.name for spec in dataclasses.fields(observation_type)}
        assert "cleanup_verified_success" not in names
        assert not any("verified_success" in name for name in names)
        assert isinstance(
            inspect.getattr_static(observation_type, "cleanup_verified_success"), property
        )
    with pytest.raises(TypeError):
        RuntimeLaunchObservation(  # type: ignore[call-arg]
            session=None,
            launch_shape_valid=False,
            required_flags_accepted=False,
            lf_jsonl_correlation_succeeded=False,
            observed_pi_version=None,
            resource_created=True,
            cleanup_attempted=True,
            direct_child_reported_exit=False,
            cleanup_verified_success=True,
        )
    with pytest.raises(TypeError):
        BrokerCreationObservation(  # type: ignore[call-arg]
            session=None,
            start_attempted=True,
            resource_created=True,
            cleanup_attempted=True,
            reached_closed=False,
            cleanup_verified_success=True,
        )


def test_no_partial_handle_or_partial_close_callable_exists_anywhere() -> None:
    parameters = set(inspect.signature(run_category_b_controller).parameters)
    for name in parameters:
        assert "partial" not in name.lower()
    for module in (i2b_controller_module, i2b_session_module):
        exported = set(vars(module))
        assert not any("PartialRuntimeHandle" == name for name in exported)
        assert not any("PartialBrokerHandle" == name for name in exported)
        assert not any(name.startswith("close_partial") for name in exported)
    assert not hasattr(i2b_session_module, "partial_resource_cleaned_internally")
    assert "partial_resource_cleaned_internally" not in {
        spec.name for spec in dataclasses.fields(RuntimeLaunchObservation)
    }


# -- malformed cleanup-observation typing (design FU3 Sec. 9.3.3) -------------


@pytest.mark.parametrize("bad", ["", "false", 0, 1, object(), [], 1.0])
def test_a_non_bool_cleanup_postcondition_is_refused(bad) -> None:
    """``None`` is covered separately by the attempted=True/None rule below."""
    with pytest.raises(ObservationError):
        RuntimeLaunchObservation(
            session=None,
            launch_shape_valid=False,
            required_flags_accepted=False,
            lf_jsonl_correlation_succeeded=False,
            observed_pi_version=None,
            resource_created=True,
            cleanup_attempted=True,
            direct_child_reported_exit=bad,
        )
    with pytest.raises(ObservationError):
        BrokerCreationObservation(
            session=None,
            start_attempted=True,
            resource_created=True,
            cleanup_attempted=True,
            reached_closed=bad,
        )


def test_attempted_true_with_a_none_postcondition_is_refused() -> None:
    with pytest.raises(ObservationError):
        RuntimeLaunchObservation(
            session=None,
            launch_shape_valid=False,
            required_flags_accepted=False,
            lf_jsonl_correlation_succeeded=False,
            observed_pi_version=None,
            resource_created=True,
            cleanup_attempted=True,
            direct_child_reported_exit=None,
        )
    with pytest.raises(ObservationError):
        BrokerCreationObservation(
            session=None,
            start_attempted=True,
            resource_created=True,
            cleanup_attempted=True,
            reached_closed=None,
        )


@pytest.mark.parametrize("postcondition", [True, False])
def test_attempted_false_with_a_non_none_postcondition_is_refused(postcondition: bool) -> None:
    with pytest.raises(ObservationError):
        RuntimeLaunchObservation(
            session=None,
            launch_shape_valid=False,
            required_flags_accepted=False,
            lf_jsonl_correlation_succeeded=False,
            observed_pi_version=None,
            resource_created=True,
            cleanup_attempted=False,
            direct_child_reported_exit=postcondition,
        )
    with pytest.raises(ObservationError):
        BrokerCreationObservation(
            session=None,
            start_attempted=True,
            resource_created=True,
            cleanup_attempted=False,
            reached_closed=postcondition,
        )


def test_cleanup_cannot_have_been_attempted_for_a_resource_never_created() -> None:
    with pytest.raises(ObservationError):
        RuntimeLaunchObservation(
            session=None,
            launch_shape_valid=False,
            required_flags_accepted=False,
            lf_jsonl_correlation_succeeded=False,
            observed_pi_version=None,
            resource_created=False,
            cleanup_attempted=True,
            direct_child_reported_exit=True,
        )
    with pytest.raises(ObservationError):
        BrokerCreationObservation(
            session=None,
            start_attempted=False,
            resource_created=False,
            cleanup_attempted=True,
            reached_closed=True,
        )


def test_a_returned_session_cannot_also_claim_a_creator_self_close(
    run_workspace: QualificationRunWorkspace,
) -> None:
    claim_run_workspace(run_workspace, run_id="run-1")
    session = RuntimeSession(
        run_id="run-1", broker_session_id="brk-1", runtime_session_id="rt-1"
    )
    with pytest.raises(ObservationError):
        RuntimeLaunchObservation(
            session=session,
            launch_shape_valid=True,
            required_flags_accepted=True,
            lf_jsonl_correlation_succeeded=True,
            observed_pi_version=SYNTHETIC_PI_VERSION,
            resource_created=True,
            cleanup_attempted=True,
            direct_child_reported_exit=True,
        )
    with pytest.raises(ObservationError):
        RuntimeLaunchObservation(
            session=session,
            launch_shape_valid=True,
            required_flags_accepted=True,
            lf_jsonl_correlation_succeeded=True,
            observed_pi_version=SYNTHETIC_PI_VERSION,
            resource_created=False,
        )
    broker = BrokerSession(
        run_id="run-1",
        session_id="brk-1",
        pipe_name=SYNTHETIC_PIPE_NAME,
        capability_id=SYNTHETIC_CAPABILITY_ID,
        broker_token=SYNTHETIC_BROKER_TOKEN,
        reached_ready=True,
    )
    with pytest.raises(ObservationError):
        BrokerCreationObservation(
            session=broker, start_attempted=True, resource_created=True, cleanup_attempted=True,
            reached_closed=True,
        )
    with pytest.raises(ObservationError):
        BrokerCreationObservation(
            session=broker, start_attempted=False, resource_created=True
        )


def test_a_creation_facts_and_cleanup_facts_stay_orthogonal() -> None:
    """The launch's own four facts are never masked by the cleanup outcome."""
    observation = RuntimeLaunchObservation(
        session=None,
        launch_shape_valid=True,
        required_flags_accepted=True,
        lf_jsonl_correlation_succeeded=False,
        observed_pi_version=SYNTHETIC_PI_VERSION,
        resource_created=True,
        cleanup_attempted=True,
        direct_child_reported_exit=False,
    )
    assert observation.launch_shape_valid is True
    assert observation.required_flags_accepted is True
    assert observation.lf_jsonl_correlation_succeeded is False
    assert observation.pi_version_observed is True
    assert observation.cleanup_verified_success is False


def test_an_adapter_that_raises_leaves_authority_unavailable(
    run_workspace: QualificationRunWorkspace, second_run_workspace: QualificationRunWorkspace
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], launch_raises=True)
    result, harness = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.RUNTIME_LAUNCH
    assert result.failure_code is CategoryBFailureCode.ADAPTER_RAISED
    assert harness.count("shutdown_runtime") == 0
    assert result.runtime_teardown.state is ResourceClosureState.SHUTDOWN_AUTHORITY_UNAVAILABLE
    assert result.runtime_teardown.closure_satisfied is False

    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], broker_raises=True)
    result, harness = _run(second_run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.BROKER_SESSION
    assert result.failure_code is CategoryBFailureCode.BROKER_CREATION_FAILED
    assert harness.count("shutdown_broker") == 0
    assert harness.count("launch_runtime") == 0
    assert result.broker_shutdown.state is ResourceClosureState.SHUTDOWN_AUTHORITY_UNAVAILABLE
    assert result.runtime_teardown.state is ResourceClosureState.NOT_REQUIRED


# -- runtime/session authority binding ----------------------------------------


def test_get_commands_for_an_unrelated_runtime_is_refused(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], commands_session_override="rt-other")
    result, harness = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.GET_COMMANDS
    assert result.failure_code is CategoryBFailureCode.RUNTIME_SESSION_MISMATCH
    assert "get_state" not in harness.calls


def test_get_state_for_an_unrelated_runtime_is_refused(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], state_session_override="rt-other")
    result, harness = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.GET_STATE
    assert result.failure_code is CategoryBFailureCode.RUNTIME_SESSION_MISMATCH


def test_protocol_observation_for_an_unrelated_runtime_is_refused(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], protocol_session_override="rt-other")
    result, _ = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.PROTOCOL_INTEGRITY
    assert result.failure_code is CategoryBFailureCode.RUNTIME_SESSION_MISMATCH


def test_a_shutdown_observation_for_an_unrelated_runtime_never_reports_closure(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"], runtime_shutdown_session_override="rt-other"
    )
    result, harness = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert harness.count("shutdown_runtime") == 1
    assert result.runtime_teardown.closure_satisfied is False
    assert result.runtime_teardown.failure_code is CategoryBFailureCode.RUNTIME_SESSION_MISMATCH


def test_a_shutdown_observation_for_an_unrelated_broker_never_reports_closure(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"], broker_shutdown_session_id_override="brk-other"
    )
    result, harness = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert harness.count("shutdown_broker") == 1
    assert result.broker_shutdown.closure_satisfied is False
    assert result.broker_shutdown.failure_code is CategoryBFailureCode.BROKER_SESSION_MISMATCH


def test_every_live_adapter_receives_the_same_runtime_session(
    run_workspace: QualificationRunWorkspace,
) -> None:
    seen: list[RuntimeSession] = []
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"])
    original_get_commands = harness.get_commands
    original_get_state = harness.get_state
    original_observe = harness.observe_protocol
    original_shutdown = harness.shutdown_runtime

    def _record(fn):
        def _wrapped(session):
            seen.append(session)
            return fn(session)

        return _wrapped

    harness.get_commands = _record(original_get_commands)  # type: ignore[method-assign]
    harness.get_state = _record(original_get_state)  # type: ignore[method-assign]
    harness.observe_protocol = _record(original_observe)  # type: ignore[method-assign]
    harness.shutdown_runtime = _record(original_shutdown)  # type: ignore[method-assign]

    result, harness = _run(run_workspace, harness=harness)
    assert result.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED
    assert len(seen) == 4
    assert all(session is seen[0] for session in seen)


# -- Pi version: observable, provenance only, and fail-closed -----------------


def test_missing_pi_version_fails_closed_even_when_everything_else_passes(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], pi_version=None)
    result, harness = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.PI_VERSION_OBSERVED
    assert result.failure_code is CategoryBFailureCode.PI_VERSION_NOT_OBSERVED
    assert result.observed_pi_version is None
    assert "get_commands" not in harness.calls


@pytest.mark.parametrize("bad_version", ["", " ", "v0.84.3", "0." + "9" * 40, "0.84.3; rm"])
def test_blank_or_unbounded_pi_version_is_refused_at_construction(bad_version: str) -> None:
    with pytest.raises(ObservationError):
        RuntimeLaunchObservation(
            session=None,
            launch_shape_valid=False,
            required_flags_accepted=False,
            lf_jsonl_correlation_succeeded=False,
            observed_pi_version=bad_version,
            resource_created=False,
        )


def test_pi_version_is_never_compared_against_a_pinned_value(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], pi_version="99.99.99")
    result, _ = _run(run_workspace, harness=harness)
    assert result.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED
    assert result.evidence.as_dict()["observed_pi_version"] == "99.99.99"
    assert result.evidence.as_dict()["pi_version_is_provenance_only"] is True


# -- the four independent launch facts ----------------------------------------


@pytest.mark.parametrize(
    "knob, gate, code",
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
    run_workspace: QualificationRunWorkspace, knob: str, gate, code
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], **{knob: False})
    result, harness = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.failed_gate is gate
    assert result.failure_code is code
    assert "get_commands" not in harness.calls


# -- H2 from ONE get_state response -------------------------------------------


def test_h2_mismatch_is_a_distinct_fact_from_get_state(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], reported_model="some-other-model")
    result, _ = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.H2_PROVIDER_MODEL_IDENTITY
    assert result.facts.get_state_response_shape_understood is True
    assert result.facts.h2_provider_model_identity_matched is False


def test_h2_provider_mismatch_fails_closed(run_workspace: QualificationRunWorkspace) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], reported_provider="openai")
    result, _ = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.failure_code is CategoryBFailureCode.H2_PROVIDER_MODEL_IDENTITY_MISMATCH


def test_an_unusable_get_state_response_cannot_also_claim_an_identity() -> None:
    with pytest.raises(ObservationError):
        GetStateObservation(
            runtime_session_id="rt-1",
            call_succeeded=False,
            response_shape_understood=True,
            reported_provider=PROVIDER_ID,
        )
    with pytest.raises(ObservationError):
        GetStateObservation(
            runtime_session_id="rt-1",
            call_succeeded=True,
            response_shape_understood=False,
            reported_model="x",
        )


def test_get_state_call_failure_is_reported_as_such(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"],
        state_call_succeeded=False,
        state_shape_understood=False,
        reported_provider=None,
        reported_model="",
    )
    harness.reported_model = None

    def _failed_state(session: RuntimeSession) -> GetStateObservation:
        harness.calls.append("get_state")
        return GetStateObservation(
            runtime_session_id=session.runtime_session_id,
            call_succeeded=False,
            response_shape_understood=False,
        )

    harness.get_state = _failed_state  # type: ignore[method-assign]
    result, _ = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.failure_code is CategoryBFailureCode.GET_STATE_FAILED


# -- protocol / extension errors ----------------------------------------------


def test_a_protocol_violation_is_an_explicit_compatibility_failure(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], protocol_violation=True)
    result, harness = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.failure_code is CategoryBFailureCode.PROTOCOL_VIOLATION_OBSERVED
    assert result.facts.no_protocol_violation_observed is False
    assert "route_checker" not in harness.calls


def test_an_extension_error_is_an_explicit_compatibility_failure(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], extension_error=True)
    result, _ = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.failure_code is CategoryBFailureCode.EXTENSION_ERROR_OBSERVED
    assert result.facts.no_extension_error_observed is False


# -- route check ---------------------------------------------------------------


@pytest.mark.parametrize("reachable, served", [(False, False), (True, False)])
def test_route_check_failure_refuses(
    run_workspace: QualificationRunWorkspace, reachable: bool, served: bool
) -> None:
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"], route_reachable=reachable, route_model_served=served
    )
    result, _ = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.ROUTE_CHECK
    assert result.facts.exact_candidate_model_served is False


# -- THE TERMINAL RULE: compatibility alone is never enough -------------------


def test_all_gates_pass_but_runtime_teardown_fails_is_an_infrastructure_refusal(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], runtime_child_exited=False)
    result, _ = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.facts.all_established is True
    assert result.failed_gate is CategoryBGateName.RUNTIME_TEARDOWN
    assert result.failure_code is CategoryBFailureCode.RUNTIME_TEARDOWN_FAILED
    assert result.evidence.as_dict()["compatibility_gate_passed"] is False


def test_all_gates_pass_but_runtime_teardown_raises_is_an_infrastructure_refusal(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], runtime_shutdown_raises=True)
    result, _ = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.RUNTIME_TEARDOWN
    assert result.runtime_teardown.attempted is True
    assert result.runtime_teardown.succeeded is False


def test_all_gates_pass_but_broker_shutdown_incomplete_is_an_infrastructure_refusal(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], broker_reached_closed=False)
    result, _ = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.facts.all_established is True
    assert result.failed_gate is CategoryBGateName.BROKER_SHUTDOWN
    assert result.failure_code is CategoryBFailureCode.BROKER_SHUTDOWN_INCOMPLETE


def test_all_gates_pass_but_config_cleanup_fails_is_an_infrastructure_refusal(
    run_workspace: QualificationRunWorkspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _unverified(_config):
        raise RuntimeError("synthetic cleanup failure")

    monkeypatch.setattr(
        i2b_controller_module, "scrub_generated_qualification_config", _unverified
    )
    result, _ = _run(run_workspace)
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.GENERATED_CONFIG_CLEANUP
    assert result.cleanup.closure_satisfied is False
    assert result.evidence.as_dict()["compatibility_gate_passed"] is False
    # clean up the directory the failed scrub left behind
    import shutil

    shutil.rmtree(Path(run_workspace.experiment_root, "i2_pi_config"), ignore_errors=True)


def test_evidence_scrub_refusal_prevents_a_category_b_pass(
    run_workspace: QualificationRunWorkspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _dirty(_payload, _safety):
        return {"scrub_checked": True, "findings": ["synthetic_finding"], "clean": False}

    monkeypatch.setattr(i2b_controller_module, "qualification_scrub_check", _dirty)
    result, _ = _run(run_workspace)
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.EVIDENCE_SAFETY
    assert result.failure_code is CategoryBFailureCode.EVIDENCE_SCRUB_REFUSED
    assert result.evidence.retention_ready is False
    assert result.evidence.as_dict() == {}
    assert result.evidence.as_json() == ""


def test_a_safety_context_that_cannot_be_proven_prevents_a_pass(
    run_workspace: QualificationRunWorkspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _refuse(**_kwargs):
        raise i2b_controller_module.CategoryBSafetyContextError("SYNTHETIC")

    monkeypatch.setattr(i2b_controller_module, "build_run_safety_context", _refuse)
    result, _ = _run(run_workspace)
    _assert_refusal(result)
    assert result.failure_code is CategoryBFailureCode.SAFETY_CONTEXT_UNPROVABLE
    assert result.evidence.scrub_findings == ("safety_context_unprovable",)


def test_no_teardown_fact_is_computed_after_the_terminal_decision(
    run_workspace: QualificationRunWorkspace,
) -> None:
    """Every closure fact is an INPUT to the pass decision, never an epilogue."""
    result, harness = _run(run_workspace)
    assert result.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED
    # the evidence body -- built before the outcome is chosen -- already
    # carries the resolved closure statuses
    body = result.evidence.as_dict()
    assert body["orchestrator_runtime_teardown_status"] == result.runtime_teardown.status_text
    assert body["orchestrator_broker_shutdown_status"] == result.broker_shutdown.status_text
    assert (
        body["orchestrator_generated_config_cleanup_status"] == result.cleanup.status_text
    )
    assert body["gate_statuses"][CategoryBGateName.RUNTIME_TEARDOWN.value] == "SUCCEEDED"
    assert body["gate_statuses"][CategoryBGateName.BROKER_SHUTDOWN.value] == "CLOSED"
    # ...and no adapter was called after the shutdowns
    assert harness.calls[-2:] == ["shutdown_runtime", "shutdown_broker"]


def test_a_pass_can_never_be_constructed_alongside_a_failed_closure(
    run_workspace: QualificationRunWorkspace,
) -> None:
    result, _ = _run(run_workspace)
    with pytest.raises(ValueError):
        dataclasses.replace(
            result,
            runtime_teardown=RuntimeTeardownStatus(
                state=ResourceClosureState.SHUTDOWN_FAILED,
                failure_code=CategoryBFailureCode.RUNTIME_TEARDOWN_FAILED,
            ),
        )
    with pytest.raises(ValueError):
        dataclasses.replace(
            result,
            broker_shutdown=BrokerShutdownStatus(
                state=ResourceClosureState.SHUTDOWN_REFUSED_FOREIGN_SESSION,
                failure_code=CategoryBFailureCode.BROKER_SHUTDOWN_REFUSED_FOREIGN_SESSION,
            ),
        )


def test_a_pass_requires_every_compatibility_fact(
    run_workspace: QualificationRunWorkspace,
) -> None:
    result, _ = _run(run_workspace)
    with pytest.raises(ValueError):
        dataclasses.replace(result, facts=CompatibilityFacts())


def test_a_closure_status_cannot_contradict_itself() -> None:
    with pytest.raises(ValueError):
        RuntimeTeardownStatus(state=ResourceClosureState.NOT_REQUIRED,
                              failure_code=CategoryBFailureCode.RUNTIME_TEARDOWN_FAILED)
    with pytest.raises(ValueError):
        RuntimeTeardownStatus(state=ResourceClosureState.SHUTDOWN_FAILED)
    with pytest.raises(ValueError):
        BrokerShutdownStatus(state=ResourceClosureState.CLOSED_BY_ORCHESTRATOR,
                             failure_code=CategoryBFailureCode.BROKER_SHUTDOWN_INCOMPLETE)
    with pytest.raises(ValueError):
        BrokerShutdownStatus(state="CLOSED")  # type: ignore[arg-type]


def test_every_unsatisfied_closure_state_reports_no_orchestrator_attempt() -> None:
    """FU2C: each state now requires ITS OWN valid failure_code (a bare
    ``RUNTIME_TEARDOWN_FAILED`` on every state -- including
    ``SHUTDOWN_REFUSED_FOREIGN_SESSION``, ``SHUTDOWN_AUTHORITY_UNAVAILABLE``
    and both creator-retained states -- is no longer accepted; see
    ``RuntimeTeardownStatus._ALLOWED_FAILURE_CODES_BY_STATE``)."""
    codes_by_state = {
        ResourceClosureState.SHUTDOWN_REFUSED_FOREIGN_SESSION: (
            CategoryBFailureCode.RUNTIME_SHUTDOWN_REFUSED_FOREIGN_SESSION
        ),
        ResourceClosureState.SHUTDOWN_AUTHORITY_UNAVAILABLE: (
            CategoryBFailureCode.RUNTIME_TEARDOWN_AUTHORITY_UNAVAILABLE
        ),
        ResourceClosureState.CLOSED_BY_CREATOR_UNVERIFIED: (
            CategoryBFailureCode.CLOSED_BY_CREATOR_UNVERIFIED
        ),
        ResourceClosureState.PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT: (
            CategoryBFailureCode.PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT
        ),
    }
    for state, code in codes_by_state.items():
        status = RuntimeTeardownStatus(state=state, failure_code=code)
        assert status.attempted is False
        assert status.authority_available is False
        assert status.closure_satisfied is False


# -- malformed adapter results ------------------------------------------------


@pytest.mark.parametrize("bad", [None, "ok", 42, {"session": None}])
def test_a_malformed_launch_result_fails_closed_without_crashing(
    run_workspace: QualificationRunWorkspace, bad
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"])
    harness.launch_result_override = bad if bad is not None else "not-an-observation"
    result, harness = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.RUNTIME_LAUNCH
    assert result.failure_code is CategoryBFailureCode.MALFORMED_ADAPTER_RESULT
    assert harness.count("shutdown_runtime") == 0


def test_a_malformed_broker_result_fails_closed(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"])
    harness.broker_result_override = "not-a-broker-creation-observation"
    result, harness = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.BROKER_SESSION
    assert result.failure_code is CategoryBFailureCode.MALFORMED_ADAPTER_RESULT
    assert harness.count("shutdown_broker") == 0


def test_a_bare_broker_session_is_no_longer_an_accepted_creation_result(
    run_workspace: QualificationRunWorkspace,
) -> None:
    """I2B-FU1's ``create_broker -> BrokerSession`` shape must fail closed now."""
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"])
    harness.broker_result_override = BrokerSession(
        run_id="whatever",
        session_id="brk-1",
        pipe_name=SYNTHETIC_PIPE_NAME,
        capability_id=SYNTHETIC_CAPABILITY_ID,
        broker_token=SYNTHETIC_BROKER_TOKEN,
        reached_ready=True,
    )
    result, harness = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.failure_code is CategoryBFailureCode.MALFORMED_ADAPTER_RESULT
    assert harness.count("shutdown_broker") == 0


def test_a_malformed_get_commands_result_fails_closed(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"])
    harness.commands_result_override = {"commands": []}
    result, _ = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.GET_COMMANDS
    assert result.failure_code is CategoryBFailureCode.MALFORMED_ADAPTER_RESULT


@pytest.mark.parametrize("value", [None, "", "false", 0, 1, object()])
def test_a_non_bool_observation_flag_is_refused(value) -> None:
    with pytest.raises(ObservationError):
        ProtocolObservation(
            runtime_session_id="rt-1",
            protocol_violation_observed=value,
            extension_error_observed=False,
        )
    with pytest.raises(ObservationError):
        RuntimeShutdownObservation(
            runtime_session_id="rt-1",
            shutdown_call_returned=value,
            orchestrator_direct_child_reported_exit=False,
        )
    with pytest.raises(ObservationError):
        BrokerShutdownObservation(session_id="brk-1", reached_closed=value)


def test_a_subclass_of_an_observation_type_is_refused(
    run_workspace: QualificationRunWorkspace,
) -> None:
    class _SneakyLaunch(RuntimeLaunchObservation):
        pass

    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"])
    harness.launch_result_override = _SneakyLaunch(
        session=None,
        launch_shape_valid=False,
        required_flags_accepted=False,
        lf_jsonl_correlation_succeeded=False,
        observed_pi_version=SYNTHETIC_PI_VERSION,
        resource_created=False,
    )
    result, _ = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.failure_code is CategoryBFailureCode.MALFORMED_ADAPTER_RESULT


def test_a_subclass_of_the_broker_creation_observation_is_refused(
    run_workspace: QualificationRunWorkspace,
) -> None:
    class _SneakyBroker(BrokerCreationObservation):
        pass

    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"])
    harness.broker_result_override = _SneakyBroker(
        session=None, start_attempted=True, resource_created=False
    )
    result, harness = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.failure_code is CategoryBFailureCode.MALFORMED_ADAPTER_RESULT
    assert harness.count("shutdown_broker") == 0


def test_a_subclass_of_a_session_type_is_refused_inside_an_observation(
    run_workspace: QualificationRunWorkspace,
) -> None:
    """A session subclass could re-derive its ids on every read."""

    class _SneakySession(RuntimeSession):
        pass

    class _SneakyBrokerSession(BrokerSession):
        pass

    with pytest.raises(ObservationError):
        RuntimeLaunchObservation(
            session=_SneakySession(
                run_id="run-1", broker_session_id="brk-1", runtime_session_id="rt-1"
            ),
            launch_shape_valid=True,
            required_flags_accepted=True,
            lf_jsonl_correlation_succeeded=True,
            observed_pi_version=SYNTHETIC_PI_VERSION,
            resource_created=True,
        )
    with pytest.raises(ObservationError):
        BrokerCreationObservation(
            session=_SneakyBrokerSession(
                run_id="run-1",
                session_id="brk-1",
                pipe_name=SYNTHETIC_PIPE_NAME,
                capability_id=SYNTHETIC_CAPABILITY_ID,
                broker_token=SYNTHETIC_BROKER_TOKEN,
                reached_ready=True,
            ),
            start_attempted=True,
            resource_created=True,
        )


def test_a_failing_launch_fact_stops_every_further_live_call(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], required_flags_accepted=False)
    result, harness = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    for never in ("get_commands", "get_state", "observe_protocol", "route_checker"):
        assert never not in harness.calls
    # closure still runs for the resources that DO exist
    assert harness.count("shutdown_runtime") == 1
    assert harness.count("shutdown_broker") == 1


def test_a_failed_h1_stops_the_next_live_call(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"], h1_components={"malformed_source_metadata": True}
    )
    result, harness = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.H1_EXTENSION_IDENTITY
    assert "get_state" not in harness.calls


def test_a_closure_gate_never_inherits_another_gates_failure_code(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"], runtime_child_exited=False, broker_reached_closed=False
    )
    result, _ = _run(run_workspace, harness=harness)
    statuses = result.gate_statuses
    assert statuses[CategoryBGateName.RUNTIME_TEARDOWN.value] == (
        f"FAILED:{CategoryBFailureCode.RUNTIME_TEARDOWN_FAILED.value}"
    )
    assert statuses[CategoryBGateName.BROKER_SHUTDOWN.value] == (
        f"FAILED:{CategoryBFailureCode.BROKER_SHUTDOWN_INCOMPLETE.value}"
    )


# -- controller argument refusal ----------------------------------------------


@pytest.mark.parametrize("bad", ["", "   ", None, 7])
def test_an_unusable_controller_argument_refuses_before_any_credential_read(
    run_workspace: QualificationRunWorkspace, bad
) -> None:
    reader = _CountingReader()
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"])
    with pytest.raises(CategoryBControllerInputError):
        run_category_b_controller(
            candidate=bad,
            run_workspace=run_workspace,
            ambient_environ={},
            node_executable="node.exe",
            non_secret_gates=_passing_non_secret_gates(),
            read_connection=reader,
            create_broker=harness.create_broker,
            launch_runtime=harness.launch_runtime,
            get_commands=harness.get_commands,
            get_state=harness.get_state,
            observe_protocol=harness.observe_protocol,
            route_checker=harness.route_checker,
            shutdown_runtime=harness.shutdown_runtime,
            shutdown_broker=harness.shutdown_broker,
        )
    assert reader.calls == 0
    assert harness.calls == []


# -- the FULL artifact safety context -----------------------------------------


def test_the_run_safety_context_declares_every_available_sensitive_value(
    run_workspace: QualificationRunWorkspace,
) -> None:
    result, harness = _run(run_workspace)
    assert result.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED
    declared = set(result.evidence.as_dict()["safety_context_declared_needle_codes"])
    assert declared == {
        "endpoint_host_value_present",
        "api_key_value_present",
        "broker_token_present",
        "broker_pipe_name_present",
        "broker_capability_id_present",
        "workspace_absolute_path_present",
    }


def test_the_workspace_needle_covers_the_workspace_root_and_the_config_dir(
    run_workspace: QualificationRunWorkspace,
) -> None:
    """One declared needle must refuse ANY of the run's three absolute paths."""
    from qualification.safety import qualification_scrub_check

    claim_run_workspace(run_workspace, run_id="run-1")
    safety = build_run_safety_context(
        secret_context=None,
        broker_session=None,
        run_workspace=run_workspace,
        route_descriptor=None,
    )
    assert safety.workspace_absolute_path == run_workspace.experiment_root
    for leaked in (
        run_workspace.experiment_root,
        run_workspace.workspace_root,
        os.path.join(run_workspace.experiment_root, "i2_pi_config"),
    ):
        check = qualification_scrub_check({"note": leaked}, safety)
        assert check["clean"] is False, leaked
        assert "workspace_absolute_path_present" in check["findings"]


def test_bearer_token_absence_is_derived_from_the_frozen_credential_mechanism(
    run_workspace: QualificationRunWorkspace,
) -> None:
    from qualification.i2_route import route_descriptor_for_candidate
    from qualification.i2_secret_context import build_secret_context

    descriptor = route_descriptor_for_candidate("A")
    secret_context = build_secret_context(
        base_url=SYNTHETIC_BASE_URL, api_key=SYNTHETIC_API_KEY, model_id=descriptor.model_id
    )
    safety = build_run_safety_context(
        secret_context=secret_context,
        broker_session=None,
        run_workspace=run_workspace,
        route_descriptor=descriptor,
    )
    assert safety.bearer_token is None
    assert safety.api_key == SYNTHETIC_API_KEY
    assert safety.endpoint_host is not None


def test_an_unexpected_credential_mechanism_refuses_rather_than_guessing(
    run_workspace: QualificationRunWorkspace,
) -> None:
    from qualification.i2_route import route_descriptor_for_candidate

    descriptor = route_descriptor_for_candidate("A")
    forged = dataclasses.replace(descriptor)
    object.__setattr__(forged, "credential_mechanism", "authorization_bearer_header")
    with pytest.raises(i2b_controller_module.CategoryBSafetyContextError):
        build_run_safety_context(
            secret_context=None,
            broker_session=None,
            run_workspace=run_workspace,
            route_descriptor=forged,
        )


def test_an_early_failure_still_declares_the_values_it_does_have(
    run_workspace: QualificationRunWorkspace,
) -> None:
    safety = build_run_safety_context(
        secret_context=None, broker_session=None, run_workspace=run_workspace,
        route_descriptor=None,
    )
    assert safety.workspace_absolute_path == run_workspace.experiment_root
    assert [code for code, _ in safety.forbidden_needles()] == [
        "workspace_absolute_path_present"
    ]


def test_no_broker_binding_or_credential_value_reaches_the_evidence(
    run_workspace: QualificationRunWorkspace,
) -> None:
    result, _ = _run(run_workspace)
    serialized = result.evidence.as_json()
    assert serialized
    for secret in (
        SYNTHETIC_API_KEY,
        SYNTHETIC_BROKER_TOKEN,
        SYNTHETIC_CAPABILITY_ID,
        SYNTHETIC_PIPE_NAME,
        "b300-proxy.example.invalid",
        run_workspace.experiment_root,
        run_workspace.workspace_root,
    ):
        assert secret not in serialized
        assert json.dumps(secret)[1:-1] not in serialized


def test_the_broker_session_repr_never_prints_its_binding() -> None:
    session = BrokerSession(
        run_id="run-1",
        session_id="brk-1",
        pipe_name=SYNTHETIC_PIPE_NAME,
        capability_id=SYNTHETIC_CAPABILITY_ID,
        broker_token=SYNTHETIC_BROKER_TOKEN,
        reached_ready=True,
    )
    for rendered in (repr(session), str(session)):
        assert SYNTHETIC_PIPE_NAME not in rendered
        assert SYNTHETIC_CAPABILITY_ID not in rendered
        assert SYNTHETIC_BROKER_TOKEN not in rendered


# -- result / evidence integrity ----------------------------------------------


def test_gate_statuses_cannot_be_rewritten_after_construction(
    run_workspace: QualificationRunWorkspace,
) -> None:
    result, _ = _run(run_workspace)
    with pytest.raises(TypeError):
        result.gate_statuses[CategoryBGateName.BROKER_READY.value] = "FAILED:whatever"
    copied = dict(result.gate_statuses)
    copied[CategoryBGateName.BROKER_READY.value] = "FAILED:whatever"
    assert result.gate_statuses[CategoryBGateName.BROKER_READY.value] == "PASSED"


def test_the_result_object_itself_is_frozen(
    run_workspace: QualificationRunWorkspace,
) -> None:
    result, _ = _run(run_workspace)
    for attribute, value in (
        ("outcome", CategoryBOutcome.INFRASTRUCTURE_REFUSAL),
        ("semantic_prompts_sent", 1),
        ("candidate", "Z"),
    ):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(result, attribute, value)


def test_the_evidence_body_cannot_be_mutated_through_any_supported_api(
    run_workspace: QualificationRunWorkspace,
) -> None:
    result, _ = _run(run_workspace)
    body = result.evidence.as_dict()
    body["compatibility_gate_passed"] = False
    body["gate_statuses"]["broker_ready"] = "FAILED:tampered"
    body["compatibility_facts"]["h1_extension_identity_matched"] = False
    fresh = result.evidence.as_dict()
    assert fresh["compatibility_gate_passed"] is True
    assert fresh["gate_statuses"]["broker_ready"] == "PASSED"
    assert fresh["compatibility_facts"]["h1_extension_identity_matched"] is True
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.evidence.retention_ready = False  # type: ignore[misc]


def test_the_evidence_scrub_result_is_immutable(
    run_workspace: QualificationRunWorkspace,
) -> None:
    result, _ = _run(run_workspace)
    assert isinstance(result.evidence.scrub_findings, tuple)
    with pytest.raises(AttributeError):
        result.evidence.scrub_findings.append("x")  # type: ignore[attr-defined]


def test_compatibility_facts_are_immutable_and_copy_on_read(
    run_workspace: QualificationRunWorkspace,
) -> None:
    result, _ = _run(run_workspace)
    snapshot = result.facts.as_dict()
    snapshot["h1_extension_identity_matched"] = False
    assert result.facts.as_dict()["h1_extension_identity_matched"] is True
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.facts.h1_extension_identity_matched = False  # type: ignore[misc]


def test_the_public_evidence_constructor_cannot_assert_any_field_at_all() -> None:
    """FU2A blocker 3: retention_ready/scrub_clean/the body were caller-supplied.

    ``CategoryBEvidence(retention_ready=True, scrub_clean=True, scrub_findings=(),
    _serialized='{"api_key": "raw-secret"}')`` used to construct successfully --
    nothing proved the body had ever actually been scrub-checked. Every field is
    now ``init=False``; the public constructor takes NO arguments at all and
    always yields the safe, inert default. This is the concrete counterexample
    from the follow-up brief, proven refused (as a TypeError, since the keyword
    no longer exists on the constructor at all -- a stronger proof than a
    ValueError would be).
    """
    with pytest.raises(TypeError):
        CategoryBEvidence(  # type: ignore[call-arg]
            retention_ready=True,
            scrub_clean=True,
            scrub_findings=(),
            _serialized='{"api_key": "raw-secret"}',
        )
    with pytest.raises(TypeError):
        CategoryBEvidence(retention_ready=False)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        CategoryBEvidence(scrub_findings=("x",))  # type: ignore[call-arg]

    default = CategoryBEvidence()
    assert default.retention_ready is False
    assert default.scrub_clean is False
    assert default.as_dict() == {}
    assert default.as_json() == ""


def test_retention_ready_true_is_only_reachable_by_actually_scrubbing_the_payload() -> None:
    """The classmethod DERIVES the verdict from a real scrub call -- never trusts one."""
    safety = ArtifactSafetyContext(api_key="sk-should-be-caught")
    unsafe = CategoryBEvidence._build_from_payload({"note": "sk-should-be-caught"}, safety)
    assert unsafe.retention_ready is False
    assert unsafe.scrub_clean is False
    assert unsafe.scrub_findings
    assert unsafe.as_dict() == {}
    assert unsafe.as_json() == ""
    assert "sk-should-be-caught" not in repr(unsafe)

    clean = CategoryBEvidence._build_from_payload({"note": "nothing sensitive"}, safety)
    assert clean.retention_ready is True
    assert clean.scrub_clean is True
    assert clean.as_dict() == {"note": "nothing sensitive"}


def test_a_malformed_scrub_check_result_is_refused_never_coerced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A malformed frozen-check return shape must not silently become a pass."""

    def _truthy_non_bool_clean(_payload, _safety):
        return {"scrub_checked": True, "findings": [], "clean": "yes"}  # non-bool, truthy

    monkeypatch.setattr(i2b_controller_module, "qualification_scrub_check", _truthy_non_bool_clean)
    # "yes" is truthy, so bare Python truthiness would incorrectly treat this
    # as clean; the classmethod requires `type(clean) is bool` exactly and
    # refuses outright rather than guessing.
    with pytest.raises(ValueError):
        CategoryBEvidence._build_from_payload({"x": 1}, ArtifactSafetyContext.none_declared())

    def _non_list_findings(_payload, _safety):
        return {"scrub_checked": True, "findings": "none", "clean": True}

    monkeypatch.setattr(i2b_controller_module, "qualification_scrub_check", _non_list_findings)
    with pytest.raises(ValueError):
        CategoryBEvidence._build_from_payload({"x": 1}, ArtifactSafetyContext.none_declared())

    def _not_a_dict(_payload, _safety):
        return ["clean"]

    monkeypatch.setattr(i2b_controller_module, "qualification_scrub_check", _not_a_dict)
    with pytest.raises(ValueError):
        CategoryBEvidence._build_from_payload({"x": 1}, ArtifactSafetyContext.none_declared())


def test_refused_requires_at_least_one_bounded_finding_code() -> None:
    with pytest.raises(ValueError):
        CategoryBEvidence._refused(())
    with pytest.raises(ValueError):
        CategoryBEvidence._refused(("",))
    refused = CategoryBEvidence._refused(("safety_context_unprovable",))
    assert refused.retention_ready is False
    assert refused.as_dict() == {}


def test_a_subclass_of_categorybevidence_cannot_override_retention_ready() -> None:
    """Found in post-implementation self-review.

    ``init=False`` fields with a plain default never go through
    ``object.__setattr__`` in the generated ``__init__`` at all -- so a
    subclass overriding ``retention_ready`` as a read-only property could
    construct via the bare, no-argument ``cls()`` with no ``AttributeError``,
    and immediately report ``retention_ready is True`` with nothing ever
    scrub-checked. Closed by refusing subclassing outright: ``__post_init__``
    now requires ``type(self) is CategoryBEvidence`` exactly.
    """

    class _Sneaky(CategoryBEvidence):
        @property
        def retention_ready(self):  # type: ignore[override]
            return True

    with pytest.raises(ValueError):
        _Sneaky()


def test_facts_reject_non_bool_values() -> None:
    with pytest.raises(ValueError):
        CompatibilityFacts(pi_version_observed="yes")  # type: ignore[arg-type]


# -- FU2A: CleanupStatus truthiness fail-open (blocker 1) ---------------------


def test_cleanup_status_scrub_verified_string_false_is_refused() -> None:
    """The exact counterexample from the follow-up brief.

    ``CleanupStatus(attempted=True, scrub_verified="false", classification=None)``
    used to construct successfully and report ``closure_satisfied is True`` /
    ``status_text == "VERIFIED_REMOVED"`` -- Python truthiness treats a
    non-empty string as truthy. Proven refused before it can appear in any
    result.
    """
    with pytest.raises(ObservationError):
        CleanupStatus(attempted=True, scrub_verified="false", classification=None)


@pytest.mark.parametrize("bad", [1, 0, "true", "", object(), 1.0, [], {}])
def test_cleanup_status_rejects_every_non_bool_scrub_verified(bad) -> None:
    """``None`` is covered separately by the attempted=True/None requirement below."""
    with pytest.raises(ObservationError):
        CleanupStatus(attempted=True, scrub_verified=bad, classification=None)


def test_cleanup_status_attempted_true_requires_a_scrub_verified_value() -> None:
    with pytest.raises(ValueError):
        CleanupStatus(attempted=True, scrub_verified=None, classification=None)


def test_the_frozen_cleanup_helpers_own_return_is_consumed_fail_closed(
    run_workspace: QualificationRunWorkspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``_attempt_cleanup`` must never ``bool(...)`` the frozen helper's result."""

    @dataclass(frozen=True)
    class _FakeCleanupResult:
        scrub_verified: object

    def _truthy_non_bool(_config):
        return _FakeCleanupResult(scrub_verified="not-actually-verified")

    monkeypatch.setattr(i2b_controller_module, "scrub_generated_qualification_config", _truthy_non_bool)
    result, _ = _run(run_workspace)
    _assert_refusal(result)
    assert result.cleanup.attempted is True
    assert result.cleanup.scrub_verified is False
    assert result.cleanup.closure_satisfied is False
    assert result.gate_statuses[CategoryBGateName.GENERATED_CONFIG_CLEANUP.value] != "VERIFIED_REMOVED"
    import shutil

    shutil.rmtree(Path(run_workspace.experiment_root, "i2_pi_config"), ignore_errors=True)


# -- FU2A: CategoryBControllerResult was not valid-by-construction (blocker 2) --


def _passing_facts(**overrides) -> CompatibilityFacts:
    kwargs = dict(
        pi_version_observed=True,
        rpc_launch_shape_valid=True,
        required_launch_flags_accepted=True,
        lf_jsonl_correlation_succeeded=True,
        get_commands_response_shape_understood=True,
        h1_extension_identity_matched=True,
        no_unexpected_extension_command_observed=True,
        get_state_response_shape_understood=True,
        h2_provider_model_identity_matched=True,
        no_protocol_violation_observed=True,
        no_extension_error_observed=True,
        exact_candidate_model_served=True,
        broker_reached_required_ready_state=True,
    )
    kwargs.update(overrides)
    return CompatibilityFacts(**kwargs)


def _passing_gate_status_pairs() -> tuple:
    """FU2B: EVERY gate ``PASSED`` is itself invalid -- the three lifecycle
    CLOSURE gates never report ``PASSED`` in a real run (they report their
    OWN resource-kind text: ``SUCCEEDED``/``CLOSED``/``VERIFIED_REMOVED``).
    This is the exact class of defect this phase closes; the helper must not
    reproduce it.
    """
    pairs = {gate.value: "PASSED" for gate in CategoryBGateName}
    pairs[CategoryBGateName.RUNTIME_TEARDOWN.value] = "SUCCEEDED"
    pairs[CategoryBGateName.BROKER_SHUTDOWN.value] = "CLOSED"
    pairs[CategoryBGateName.GENERATED_CONFIG_CLEANUP.value] = "VERIFIED_REMOVED"
    return tuple(sorted(pairs.items()))


def _canonical_evidence_payload(
    *,
    candidate: str,
    gate_status_pairs: tuple,
    facts: CompatibilityFacts,
    observed_pi_version,
    compatibility_gate_passed: bool,
    runtime_teardown_status_text: str,
    broker_shutdown_status_text: str,
    cleanup_status_text: str,
) -> dict:
    """The exact subset of fields evidence-binding requires -- see
    ``_require_evidence_describes_this_result`` in the controller.
    """
    try:
        gate_statuses = {
            name: status
            for name, status in gate_status_pairs
            if name != CategoryBGateName.EVIDENCE_SAFETY.value
        }
    except (TypeError, ValueError):
        # A test deliberately feeding a MALFORMED `_gate_status_pairs` shape
        # (e.g. a 3-tuple entry) to prove the real constructor's own shape
        # check refuses it -- this helper must not itself crash first and
        # mask that. The payload's exact content is irrelevant once the real
        # constructor's shape check fires, which it always will for the same
        # malformed input.
        gate_statuses = {}
    return {
        "candidate": candidate,
        "semantic_prompts_sent": 0,
        "compatibility_gate_passed": compatibility_gate_passed,
        "compatibility_facts": facts.as_dict(),
        "observed_pi_version": observed_pi_version,
        "gate_statuses": gate_statuses,
        "orchestrator_runtime_teardown_status": runtime_teardown_status_text,
        "orchestrator_broker_shutdown_status": broker_shutdown_status_text,
        "orchestrator_generated_config_cleanup_status": cleanup_status_text,
    }


def _build_result(**overrides):
    """A GENUINELY SELF-CONSISTENT, valid ``CATEGORY_B_GATE_PASSED`` result by
    default (FU2B). Every default value agrees with every other: the typed
    closure objects are all ``CLOSED_BY_ORCHESTRATOR``/verified, the gate
    statuses match those typed objects exactly, and the evidence body is
    scrub-built from a payload that actually describes this same result.

    This matters because ``CategoryBControllerResult`` is now valid by
    construction: a caller that leaves a CONTRADICTORY default in place (the
    pre-FU2B version of this helper had
    ``pi_config_created=True`` alongside ``cleanup.attempted=False``, and
    ``runtime_teardown``/``broker_shutdown`` left at ``NOT_REQUIRED`` while
    claiming ``broker_created``/``runtime_session_established`` were
    ``True``) means every test overriding a DIFFERENT field is actually
    exercising the FIRST cross-field check the constructor happens to run,
    not the specific one the test names -- exactly the isolation failure this
    phase's own brief warned about. Every override below replaces exactly
    one thing; every OTHER default stays mutually consistent.
    """
    candidate = overrides.get("candidate", "A")
    facts = overrides.pop("facts", _passing_facts())
    observed_pi_version = overrides.pop("observed_pi_version", "0.84.3")
    outcome = overrides.get("outcome", CategoryBOutcome.CATEGORY_B_GATE_PASSED)
    runtime_teardown = overrides.pop(
        "runtime_teardown", RuntimeTeardownStatus(state=ResourceClosureState.CLOSED_BY_ORCHESTRATOR)
    )
    broker_shutdown = overrides.pop(
        "broker_shutdown", BrokerShutdownStatus(state=ResourceClosureState.CLOSED_BY_ORCHESTRATOR)
    )
    cleanup = overrides.pop(
        "cleanup", CleanupStatus(attempted=True, scrub_verified=True, classification=None)
    )
    gate_status_pairs = overrides.pop("_gate_status_pairs", _passing_gate_status_pairs())
    if "evidence" in overrides:
        evidence = overrides.pop("evidence")
    else:
        payload = _canonical_evidence_payload(
            candidate=candidate,
            gate_status_pairs=gate_status_pairs,
            facts=facts,
            observed_pi_version=observed_pi_version,
            compatibility_gate_passed=(outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED),
            # A test deliberately overriding one of these three with a
            # duck-typed/foreign object (to prove the RESULT's own exact-type
            # check refuses it) may not expose `.status_text` at all; the
            # helper must not crash before the real constructor gets a
            # chance to raise ITS OWN error for that.
            runtime_teardown_status_text=getattr(runtime_teardown, "status_text", "<n/a>"),
            broker_shutdown_status_text=getattr(broker_shutdown, "status_text", "<n/a>"),
            cleanup_status_text=getattr(cleanup, "status_text", "<n/a>"),
        )
        evidence = CategoryBEvidence._build_from_payload(payload, ArtifactSafetyContext.none_declared())
    kwargs = dict(
        candidate=candidate,
        outcome=outcome,
        semantic_prompts_sent=0,
        failed_gate=None,
        failure_code=None,
        facts=facts,
        observed_pi_version=observed_pi_version,
        pi_config_created=True,
        broker_created=True,
        runtime_session_established=True,
        runtime_teardown=runtime_teardown,
        broker_shutdown=broker_shutdown,
        cleanup=cleanup,
        evidence=evidence,
        _gate_status_pairs=gate_status_pairs,
    )
    kwargs.update(overrides)
    return CategoryBControllerResult(**kwargs)


def test_a_bare_object_exposing_closure_satisfied_cannot_authorize_a_pass() -> None:
    """The exact counterexample from the follow-up brief: an unrelated object
    exposing ``closure_satisfied = True`` as a bare class attribute, with NO
    relationship to this module's types."""

    class _FakeClosure:
        closure_satisfied = True

    with pytest.raises(ValueError):
        _build_result(runtime_teardown=_FakeClosure())
    with pytest.raises(ValueError):
        _build_result(broker_shutdown=_FakeClosure())
    with pytest.raises(ValueError):
        _build_result(cleanup=_FakeClosure())


def test_a_subclass_overriding_closure_satisfied_cannot_authorize_a_pass() -> None:
    """The overridden property forces ``closure_satisfied`` unconditionally
    True; the ALREADY-ACCEPTED base ``__post_init__`` then requires
    ``failure_code is None`` to construct at all (since it too reads the
    overridden property) -- so the state/failure_code pairing that would
    normally be genuinely unsatisfied (a real ``SHUTDOWN_FAILED``) must be
    constructed WITHOUT a failure_code to exist as an object in the first
    place. That alone does not make it safe: ``status_text`` (not
    overridden) still reports ``FAILED:...`` for that same instance, proving
    the object is internally incoherent, and the exact-type check at the
    result boundary is what actually refuses it regardless.
    """

    class _FakeTeardown(RuntimeTeardownStatus):
        @property
        def closure_satisfied(self):  # type: ignore[override]
            return True

    class _FakeBroker(BrokerShutdownStatus):
        @property
        def closure_satisfied(self):  # type: ignore[override]
            return True

    bad_rt = _FakeTeardown(state=ResourceClosureState.SHUTDOWN_FAILED, failure_code=None)
    assert bad_rt.closure_satisfied is True  # the override genuinely lies
    assert bad_rt.status_text.startswith("FAILED:")  # ...and contradicts itself
    with pytest.raises(ValueError):
        _build_result(runtime_teardown=bad_rt)

    bad_bs = _FakeBroker(state=ResourceClosureState.SHUTDOWN_FAILED, failure_code=None)
    assert bad_bs.closure_satisfied is True
    assert bad_bs.status_text.startswith("FAILED:")
    with pytest.raises(ValueError):
        _build_result(broker_shutdown=bad_bs)


def test_a_subclass_of_cleanup_status_overriding_closure_satisfied_is_refused() -> None:
    class _FakeCleanup(CleanupStatus):
        @property
        def closure_satisfied(self):  # type: ignore[override]
            return True

    classification = i2b_controller_module.classify_cleanup_failure(semantic_prompts_sent=0)
    fake = _FakeCleanup(attempted=True, scrub_verified=False, classification=classification)
    assert fake.closure_satisfied is True  # the override genuinely lies
    assert fake.status_text.startswith("FAILED:")  # ...and contradicts itself
    with pytest.raises(ValueError):
        _build_result(cleanup=fake)


def test_a_subclass_of_compatibility_facts_overriding_all_established_is_refused() -> None:
    class _FakeFacts(CompatibilityFacts):
        @property
        def all_established(self):  # type: ignore[override]
            return True

    fake = _FakeFacts()  # every field defaults to False
    assert fake.all_established is True  # the override genuinely lies
    with pytest.raises(ValueError):
        _build_result(facts=fake)


def test_evidence_subclassing_is_refused_outright_even_via_the_classmethods() -> None:
    """Even a subclass that changes NOTHING is refused, the moment ``cls()``
    runs inside either classmethod -- before any scrub check is even
    attempted."""

    class _FakeEvidence(CategoryBEvidence):
        pass

    with pytest.raises(ValueError):
        _FakeEvidence._build_from_payload({"ok": True}, ArtifactSafetyContext.none_declared())
    with pytest.raises(ValueError):
        _FakeEvidence._refused(("x",))


def test_a_duck_typed_object_cannot_stand_in_for_evidence_at_the_result_boundary() -> None:
    """An unrelated object, no relation to CategoryBEvidence at all, claiming
    ``retention_ready = True`` as a bare class attribute."""

    class _FakeEvidence:
        retention_ready = True
        scrub_clean = True
        scrub_findings = ()

        def as_dict(self):
            return {}

        def as_json(self):
            return ""

    with pytest.raises(ValueError):
        _build_result(evidence=_FakeEvidence())


@pytest.mark.parametrize(
    "field_name, bad_value",
    [
        ("candidate", ""),
        ("candidate", "   "),
        ("candidate", 7),
        ("semantic_prompts_sent", False),  # bool(False) == 0, but is NOT exactly int
        ("semantic_prompts_sent", 0.0),
        ("outcome", "CATEGORY_B_GATE_PASSED"),
        ("pi_config_created", 1),
        ("pi_config_created", "true"),
        ("broker_created", None),
        ("runtime_session_established", 0),
        ("observed_pi_version", 7),
    ],
)
def test_result_scalar_fields_are_checked_by_exact_type(field_name, bad_value) -> None:
    with pytest.raises(ValueError):
        _build_result(**{field_name: bad_value})


def test_result_enum_fields_are_checked_by_exact_type() -> None:
    with pytest.raises(ValueError):
        _build_result(
            outcome=CategoryBOutcome.INFRASTRUCTURE_REFUSAL,
            failed_gate="broker_ready",  # a raw str, not a CategoryBGateName
            failure_code=CategoryBFailureCode.BROKER_NOT_READY,
        )
    with pytest.raises(ValueError):
        _build_result(
            outcome=CategoryBOutcome.INFRASTRUCTURE_REFUSAL,
            failed_gate=CategoryBGateName.BROKER_READY,
            failure_code="BROKER_NOT_READY",  # a raw str, not a CategoryBFailureCode
        )


def test_the_false_semantic_prompts_sent_counterexample_is_refused() -> None:
    """``False == 0`` in Python -- confirm the exact-int check catches it."""
    assert False == 0  # documents the Python behavior this guards against
    with pytest.raises(ValueError):
        _build_result(semantic_prompts_sent=False)


# -- FU2A: _gate_status_pairs contradicting a terminal PASS (blocker 2, item 10) --


def test_a_failed_or_not_reached_gate_status_cannot_coexist_with_a_pass() -> None:
    for bad_status in ("NOT_REACHED", f"FAILED:{CategoryBFailureCode.ROUTE_CHECK_FAILED.value}"):
        pairs = dict(_passing_gate_status_pairs())
        pairs[CategoryBGateName.ROUTE_CHECK.value] = bad_status
        with pytest.raises(ValueError):
            _build_result(_gate_status_pairs=tuple(sorted(pairs.items())))


def test_gate_status_pairs_must_name_every_declared_gate_exactly_once() -> None:
    # missing gate
    pairs = dict(_passing_gate_status_pairs())
    del pairs[CategoryBGateName.ROUTE_CHECK.value]
    with pytest.raises(ValueError):
        _build_result(_gate_status_pairs=tuple(sorted(pairs.items())))
    # duplicated gate name
    dup = _passing_gate_status_pairs() + ((CategoryBGateName.ROUTE_CHECK.value, "PASSED"),)
    with pytest.raises(ValueError):
        _build_result(_gate_status_pairs=dup)
    # unknown gate name
    pairs = dict(_passing_gate_status_pairs())
    pairs["not_a_real_gate"] = "PASSED"
    with pytest.raises(ValueError):
        _build_result(_gate_status_pairs=tuple(sorted(pairs.items())))


def test_gate_status_pairs_rejects_an_unrecognized_status_text() -> None:
    pairs = dict(_passing_gate_status_pairs())
    pairs[CategoryBGateName.ROUTE_CHECK.value] = "TOTALLY_FINE_TRUST_ME"
    with pytest.raises(ValueError):
        _build_result(_gate_status_pairs=tuple(sorted(pairs.items())))


def test_gate_status_pairs_shape_is_checked_structurally() -> None:
    with pytest.raises(ValueError):
        _build_result(_gate_status_pairs=[(g.value, "PASSED") for g in CategoryBGateName])  # a list, not a tuple
    with pytest.raises(ValueError):
        bad = tuple(
            (g.value, "PASSED", "extra") if g is CategoryBGateName.ROUTE_CHECK else (g.value, "PASSED")
            for g in CategoryBGateName
        )
        _build_result(_gate_status_pairs=bad)  # type: ignore[arg-type]


def test_a_refusal_result_still_validates_its_gate_status_pairs() -> None:
    """Validation is not conditional on the outcome being a PASS."""
    pairs = dict(_passing_gate_status_pairs())
    pairs["not_a_real_gate"] = "PASSED"
    with pytest.raises(ValueError):
        _build_result(
            outcome=CategoryBOutcome.INFRASTRUCTURE_REFUSAL,
            failed_gate=CategoryBGateName.ROUTE_CHECK,
            failure_code=CategoryBFailureCode.ROUTE_CHECK_FAILED,
            _gate_status_pairs=tuple(sorted(pairs.items())),
        )


def test_the_full_pipeline_result_actually_satisfies_the_hardened_invariants(
    run_workspace: QualificationRunWorkspace,
) -> None:
    """A real, end-to-end controller PASS must still construct cleanly."""
    result, _ = _run(run_workspace)
    assert result.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED
    assert type(result.facts) is CompatibilityFacts
    assert type(result.evidence) is CategoryBEvidence
    assert type(result.runtime_teardown) is RuntimeTeardownStatus
    assert type(result.broker_shutdown) is BrokerShutdownStatus
    assert type(result.cleanup) is CleanupStatus



# =============================================================================
# FU2B -- terminal cross-field + per-gate status + evidence-binding closure
# =============================================================================
#
# FU2A hardened individual TYPES (exact-type checks, no bare truthiness) but
# left CategoryBControllerResult semantically incoherent: a result could
# claim `pi_config_created=True` alongside `cleanup.attempted=False`, or
# `runtime_session_established=True` alongside `runtime_teardown.state=
# NOT_REQUIRED`, or accept ANY known-good status string on ANY gate
# (`route_check = "NOT_REQUIRED"`, a text only a closure gate ever produces),
# or accept a retention-ready CategoryBEvidence built from a payload with no
# relationship to the result consuming it. All were REPRODUCED against the
# actual pre-fix code (the OLD `_build_result` default itself WAS exactly
# this contradictory shape) before any fix was written.


def _valid_pass_evidence_for(
    *, candidate="A", facts=None, observed_pi_version="0.84.3", gate_status_pairs=None,
    runtime_teardown=None, broker_shutdown=None, cleanup=None,
):
    """Build a retention-ready CategoryBEvidence that genuinely DESCRIBES the
    given (or default-valid) result fields -- for tests that need to swap
    exactly ONE field on top of an otherwise-consistent shape.
    """
    facts = facts if facts is not None else _passing_facts()
    gate_status_pairs = gate_status_pairs if gate_status_pairs is not None else _passing_gate_status_pairs()
    runtime_teardown = runtime_teardown or RuntimeTeardownStatus(state=ResourceClosureState.CLOSED_BY_ORCHESTRATOR)
    broker_shutdown = broker_shutdown or BrokerShutdownStatus(state=ResourceClosureState.CLOSED_BY_ORCHESTRATOR)
    cleanup = cleanup or CleanupStatus(attempted=True, scrub_verified=True, classification=None)
    payload = _canonical_evidence_payload(
        candidate=candidate,
        gate_status_pairs=gate_status_pairs,
        facts=facts,
        observed_pi_version=observed_pi_version,
        compatibility_gate_passed=True,
        runtime_teardown_status_text=runtime_teardown.status_text,
        broker_shutdown_status_text=broker_shutdown.status_text,
        cleanup_status_text=cleanup.status_text,
    )
    return CategoryBEvidence._build_from_payload(payload, ArtifactSafetyContext.none_declared())


# -- mandatory pre-coding counterexamples, each isolated to ONE field --------


def test_counterexample_1_pi_config_created_true_cleanup_not_attempted() -> None:
    with pytest.raises(ValueError, match="pi_config_created must equal cleanup.attempted"):
        _build_result(cleanup=CleanupStatus(attempted=False, scrub_verified=None, classification=None))


def test_counterexample_2_runtime_session_established_true_teardown_not_required() -> None:
    with pytest.raises(ValueError, match="disagrees with the typed closure object"):
        _build_result(runtime_teardown=RuntimeTeardownStatus(state=ResourceClosureState.NOT_REQUIRED))


def test_counterexample_3_broker_created_true_broker_shutdown_not_required() -> None:
    with pytest.raises(ValueError, match="disagrees with the typed closure object"):
        _build_result(broker_shutdown=BrokerShutdownStatus(state=ResourceClosureState.NOT_REQUIRED))


def test_counterexample_4_typed_not_required_but_gate_status_says_passed() -> None:
    pairs = dict(_passing_gate_status_pairs())
    pairs[CategoryBGateName.RUNTIME_TEARDOWN.value] = "PASSED"
    with pytest.raises(ValueError, match="disagrees with the typed closure object"):
        _build_result(
            runtime_teardown=RuntimeTeardownStatus(state=ResourceClosureState.NOT_REQUIRED),
            _gate_status_pairs=tuple(sorted(pairs.items())),
        )


def test_counterexample_5_route_check_gate_status_not_required() -> None:
    pairs = dict(_passing_gate_status_pairs())
    pairs[CategoryBGateName.ROUTE_CHECK.value] = "NOT_REQUIRED"
    # Refused -- now caught by the facts-vs-gate cross-check before even
    # reaching the per-gate PASS-required text check; both independently
    # forbid it, and either refusal proves the bypass is closed.
    with pytest.raises(ValueError):
        _build_result(_gate_status_pairs=tuple(sorted(pairs.items())))


def test_counterexample_6_pass_using_unrelated_scrubbed_evidence_payload() -> None:
    evidence = CategoryBEvidence._build_from_payload({"ok": True}, ArtifactSafetyContext.none_declared())
    with pytest.raises(ValueError, match="does not describe this result's own"):
        _build_result(evidence=evidence)


def test_counterexample_7_candidate_not_a_frozen_candidate() -> None:
    with pytest.raises(ValueError, match="frozen candidates"):
        _build_result(candidate="not-a-frozen-candidate")


def test_counterexample_8_pi_version_observed_true_but_observed_pi_version_none() -> None:
    with pytest.raises(ValueError, match="facts.pi_version_observed must equal"):
        _build_result(observed_pi_version=None)


def test_counterexample_9_hostile_finding_object_never_stringified() -> None:
    class _Hostile:
        def __str__(self):  # pragma: no cover - must never be called
            raise AssertionError("str() was called on the hostile finding object")

        def __repr__(self):  # pragma: no cover - must never be called
            raise AssertionError("repr() was called on the hostile finding object")

    def _hostile_scrub(_payload, _safety):
        return {"scrub_checked": True, "findings": [_Hostile()], "clean": False}

    original = i2b_controller_module.qualification_scrub_check
    i2b_controller_module.qualification_scrub_check = _hostile_scrub
    try:
        with pytest.raises(ValueError, match="unrecognized finding entry"):
            CategoryBEvidence._build_from_payload({"x": 1}, ArtifactSafetyContext.none_declared())
    finally:
        i2b_controller_module.qualification_scrub_check = original


def test_counterexample_10_failed_gate_disagrees_with_its_own_gate_status() -> None:
    pairs = dict(_passing_gate_status_pairs())
    pairs[CategoryBGateName.BROKER_READY.value] = "PASSED"  # says PASSED...
    with pytest.raises(ValueError, match="disagrees with gate_statuses"):
        _build_result(
            outcome=CategoryBOutcome.INFRASTRUCTURE_REFUSAL,
            failed_gate=CategoryBGateName.BROKER_READY,  # ...but this claims it FAILED
            failure_code=CategoryBFailureCode.BROKER_NOT_READY,
            _gate_status_pairs=tuple(sorted(pairs.items())),
        )


# -- PASS requires the actual successful Category-B shape --------------------


def test_pass_requires_pi_config_created_broker_created_runtime_session_established() -> None:
    # FU2D: the PASS-shape "all be True" rule is now DEFENCE IN DEPTH rather
    # than the first line of defence, and deliberately so (the same stance
    # FU2B already documented for the redundant `observed_pi_version is not
    # None` PASS-only check). On a terminal PASS every compatibility gate
    # must read exactly PASSED, and FU2D binds each existence boolean to its
    # own gate -- so a PASS claiming `broker_created=False` now contradicts
    # `gate_statuses['broker_session'] == 'PASSED'` and is refused by the
    # stricter, more specific existence rule before the PASS-shape rule is
    # reached. Both refusals are correct; the contradiction is what matters.
    with pytest.raises(ValueError, match="all be True|returned a session"):
        _build_result(broker_created=False)
    with pytest.raises(ValueError, match="all be True|returned a session"):
        _build_result(runtime_session_established=False)
    # pi_config_created must be flipped together with cleanup.attempted (the
    # already-enforced cross-field invariant binding the two) AND with
    # PI_CONFIG_GENERATION's own gate status (FU2D: the controller assigns
    # `generated_config` exactly on that gate's success path, so all three
    # move together). Flipping the gate makes every LATER compatibility gate
    # unreachable, which is why this variant asserts on the trace rule --
    # the "all be True" PASS-shape rule is already proven by the two
    # single-field cases above.
    pairs = dict(_passing_gate_status_pairs())
    pairs[CategoryBGateName.GENERATED_CONFIG_CLEANUP.value] = "NOT_REQUIRED"
    pairs[CategoryBGateName.PI_CONFIG_GENERATION.value] = (
        f"FAILED:{CategoryBFailureCode.PI_CONFIG_GENERATION_FAILED.value}"
    )
    with pytest.raises(ValueError, match="not a trace the controller could have produced"):
        _build_result(
            pi_config_created=False,
            cleanup=CleanupStatus(attempted=False, scrub_verified=None, classification=None),
            _gate_status_pairs=tuple(sorted(pairs.items())),
        )


def test_pass_requires_cleanup_attempted_and_verified() -> None:
    # attempted=False (paired with pi_config_created=False, to keep the
    # cross-field invariant satisfied and isolate THIS check specifically)
    with pytest.raises(ValueError):
        _build_result(
            pi_config_created=False,
            cleanup=CleanupStatus(attempted=False, scrub_verified=None, classification=None),
        )


def test_pass_requires_runtime_teardown_and_broker_shutdown_closed_by_orchestrator() -> None:
    for state in (
        ResourceClosureState.CLOSED_BY_CREATOR_VERIFIED,
        ResourceClosureState.SHUTDOWN_REFUSED_FOREIGN_SESSION,
    ):
        failure_code = (
            None
            if state is ResourceClosureState.CLOSED_BY_CREATOR_VERIFIED
            else CategoryBFailureCode.RUNTIME_SHUTDOWN_REFUSED_FOREIGN_SESSION
        )
        rt = RuntimeTeardownStatus(state=state, failure_code=failure_code)
        pairs = dict(_passing_gate_status_pairs())
        pairs[CategoryBGateName.RUNTIME_TEARDOWN.value] = rt.status_text
        # FU2C: a FAILED (not merely non-CLOSED_BY_ORCHESTRATOR) runtime_teardown
        # status trips the "a PASS may have no FAILED gate" check.
        # FU2D: and both states here now ALSO contradict the resource-existence
        # rules -- CLOSED_BY_CREATOR_VERIFIED is reachable only when NO session
        # object was returned (while RUNTIME_LAUNCH reads PASSED, so one was),
        # and SHUTDOWN_REFUSED_FOREIGN_SESSION only when that gate recorded a
        # session MISMATCH. Every one of these is a correct refusal of the same
        # underlying contradiction.
        with pytest.raises(
            ValueError,
            match="CLOSED_BY_ORCHESTRATOR|must have no FAILED gate|is not reachable when "
            "gate_statuses",
        ):
            _build_result(runtime_teardown=rt, _gate_status_pairs=tuple(sorted(pairs.items())))


def test_pass_requires_an_observed_pi_version() -> None:
    # Isolate from the universal cross-field check by ALSO flipping the fact,
    # to prove there is a SEPARATE, explicit PASS-only check for this too
    # (redundant with facts.all_established, by design, per the brief).
    with pytest.raises(ValueError):
        _build_result(observed_pi_version=None, facts=_passing_facts(pi_version_observed=False))


def test_the_valid_pass_baseline_is_genuinely_minimal_and_necessary() -> None:
    """Positive control: the default _build_result() PASS is not accidentally
    over-constrained -- it constructs, and EVERY field matters (already
    proven individually above)."""
    result = _build_result()
    assert result.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED


# -- per-gate status validation: a gate cannot borrow another gate's text ----


def test_a_closure_only_status_text_is_refused_on_a_compatibility_gate() -> None:
    """``"CLOSED"``/``"SUCCEEDED"``/``"VERIFIED_REMOVED"`` are texts only the
    THREE typed closure gates ever produce. On any compatibility gate they
    are unrecognized -- and, on a PASS, additionally not exactly ``"PASSED"``.
    """
    for borrowed_text in ("CLOSED", "SUCCEEDED", "VERIFIED_REMOVED"):
        pairs = dict(_passing_gate_status_pairs())
        pairs[CategoryBGateName.H1_EXTENSION_IDENTITY.value] = borrowed_text
        with pytest.raises(ValueError):
            _build_result(_gate_status_pairs=tuple(sorted(pairs.items())))


def test_a_failure_code_valid_on_one_gate_is_refused_on_another(
    run_workspace: QualificationRunWorkspace,
) -> None:
    """``BROKER_NOT_READY`` is BROKER_READY's own code; H1's gate never emits it."""
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], h1_components={"malformed_source_metadata": True})
    result, _ = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.H1_EXTENSION_IDENTITY

    pairs = dict(result.gate_statuses)
    pairs[CategoryBGateName.H1_EXTENSION_IDENTITY.value] = (
        f"FAILED:{CategoryBFailureCode.BROKER_NOT_READY.value}"
    )
    payload = _canonical_evidence_payload(
        candidate=result.candidate, gate_status_pairs=tuple(sorted(pairs.items())),
        facts=result.facts, observed_pi_version=result.observed_pi_version,
        compatibility_gate_passed=False,
        runtime_teardown_status_text=result.runtime_teardown.status_text,
        broker_shutdown_status_text=result.broker_shutdown.status_text,
        cleanup_status_text=result.cleanup.status_text,
    )
    evidence = CategoryBEvidence._build_from_payload(payload, ArtifactSafetyContext.none_declared())
    with pytest.raises(ValueError, match="is not a status this gate's own producer can emit"):
        CategoryBControllerResult(
            candidate=result.candidate, outcome=CategoryBOutcome.INFRASTRUCTURE_REFUSAL,
            semantic_prompts_sent=0,
            failed_gate=CategoryBGateName.H1_EXTENSION_IDENTITY,
            failure_code=CategoryBFailureCode.BROKER_NOT_READY,
            facts=result.facts, observed_pi_version=result.observed_pi_version,
            pi_config_created=result.pi_config_created, broker_created=result.broker_created,
            runtime_session_established=result.runtime_session_established,
            runtime_teardown=result.runtime_teardown, broker_shutdown=result.broker_shutdown,
            cleanup=result.cleanup, evidence=evidence,
            _gate_status_pairs=tuple(sorted(pairs.items())),
        )


def test_every_compatibility_gate_has_its_own_declared_allowed_codes() -> None:
    """The table is exhaustive and matches COMPATIBILITY_GATES exactly."""
    table = i2b_controller_module._COMPATIBILITY_GATE_ALLOWED_FAILURE_CODE_VALUES
    assert set(table) == {gate.value for gate in COMPATIBILITY_GATES}
    for gate in COMPATIBILITY_GATES:
        assert table[gate.value], f"{gate.value} has no allowed failure codes at all"


def test_evidence_safety_gate_is_bound_to_retention_ready() -> None:
    result, _ = None, None
    pairs = dict(_passing_gate_status_pairs())
    pairs[CategoryBGateName.EVIDENCE_SAFETY.value] = f"FAILED:{CategoryBFailureCode.EVIDENCE_SCRUB_REFUSED.value}"
    with pytest.raises(ValueError, match="retention_ready is True"):
        _build_result(_gate_status_pairs=tuple(sorted(pairs.items())))


# -- evidence binding: every covered key individually mismatched -------------


@pytest.mark.parametrize(
    "mutate",
    [
        lambda body: body.__setitem__("candidate", "B"),
        lambda body: body.__setitem__("semantic_prompts_sent", 1),
        lambda body: body.__setitem__("compatibility_gate_passed", False),
        lambda body: body["compatibility_facts"].__setitem__("h1_extension_identity_matched", False),
        lambda body: body.__setitem__("observed_pi_version", "9.9.9"),
        lambda body: body["gate_statuses"].__setitem__(CategoryBGateName.ROUTE_CHECK.value, "NOT_REACHED"),
        lambda body: body.__setitem__("orchestrator_runtime_teardown_status", "SOMETHING_ELSE"),
        lambda body: body.__setitem__("orchestrator_broker_shutdown_status", "SOMETHING_ELSE"),
        lambda body: body.__setitem__("orchestrator_generated_config_cleanup_status", "SOMETHING_ELSE"),
    ],
)
def test_evidence_binding_catches_every_covered_key_individually(mutate) -> None:
    facts = _passing_facts()
    pairs = _passing_gate_status_pairs()
    runtime_teardown = RuntimeTeardownStatus(state=ResourceClosureState.CLOSED_BY_ORCHESTRATOR)
    broker_shutdown = BrokerShutdownStatus(state=ResourceClosureState.CLOSED_BY_ORCHESTRATOR)
    cleanup = CleanupStatus(attempted=True, scrub_verified=True, classification=None)
    payload = _canonical_evidence_payload(
        candidate="A", gate_status_pairs=pairs, facts=facts, observed_pi_version="0.84.3",
        compatibility_gate_passed=True, runtime_teardown_status_text=runtime_teardown.status_text,
        broker_shutdown_status_text=broker_shutdown.status_text, cleanup_status_text=cleanup.status_text,
    )
    mutate(payload)
    evidence = CategoryBEvidence._build_from_payload(payload, ArtifactSafetyContext.none_declared())
    with pytest.raises(ValueError, match="does not describe this result's own"):
        _build_result(
            facts=facts, _gate_status_pairs=pairs, runtime_teardown=runtime_teardown,
            broker_shutdown=broker_shutdown, cleanup=cleanup, evidence=evidence,
        )


def test_evidence_binding_applies_to_refusals_too_not_only_pass() -> None:
    """A retention-ready evidence body must describe a REFUSAL result too.

    **FU2D corrected this test's own premise.** Its previous comment claimed
    "NOTHING was created before BROKER_READY failed", and it hand-set
    `pi_config_created=False` / `cleanup.attempted=False` /
    `broker_shutdown=NOT_REQUIRED` accordingly. That is false for this
    controller's lifecycle: the generated Pi config and the broker session
    are both created BEFORE `BROKER_READY` is ever checked (the frozen-O1
    order mints and readies the broker before Pi is launched). The trace is
    now derived, so the resources that genuinely exist at that point are
    reported as existing, and this test isolates the EVIDENCE-BINDING check
    on a shape the controller could actually produce.
    """
    unrelated_evidence = CategoryBEvidence._build_from_payload(
        {"unrelated": True}, ArtifactSafetyContext.none_declared()
    )
    with pytest.raises(ValueError, match="does not describe this result's own"):
        _reachable_refusal(
            failed={CategoryBGateName.BROKER_READY: CategoryBFailureCode.BROKER_NOT_READY},
            failed_gate=CategoryBGateName.BROKER_READY,
            failure_code=CategoryBFailureCode.BROKER_NOT_READY,
            evidence=unrelated_evidence,
        )


def test_fu2d_a_broker_ready_failure_reports_the_resources_that_already_exist() -> None:
    """The positive half of the correction above, asserted directly: at a
    BROKER_READY failure the generated config and the broker session both
    already exist, so a truthful result says so."""
    result = _reachable_refusal(
        failed={CategoryBGateName.BROKER_READY: CategoryBFailureCode.BROKER_NOT_READY},
        failed_gate=CategoryBGateName.BROKER_READY,
        failure_code=CategoryBFailureCode.BROKER_NOT_READY,
    )
    assert result.pi_config_created is True
    assert result.cleanup.attempted is True
    assert result.broker_created is True
    assert result.broker_shutdown.state is ResourceClosureState.CLOSED_BY_ORCHESTRATOR
    # ...and the runtime was never launched, so nothing is owed for it
    assert result.runtime_session_established is False
    assert result.runtime_teardown.state is ResourceClosureState.NOT_REQUIRED


# -- malformed / bounded finding codes ----------------------------------------


@pytest.mark.parametrize("bad_finding", [7, 3.5, None, ("tuple",), ["list"], {"dict": 1}, b"bytes"])
def test_non_string_finding_entries_are_refused_never_stringified(
    bad_finding, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _bad_scrub(_payload, _safety):
        return {"scrub_checked": True, "findings": [bad_finding], "clean": False}

    monkeypatch.setattr(i2b_controller_module, "qualification_scrub_check", _bad_scrub)
    with pytest.raises(ValueError, match="unrecognized finding entry"):
        CategoryBEvidence._build_from_payload({"x": 1}, ArtifactSafetyContext.none_declared())


@pytest.mark.parametrize(
    "bad_code",
    ["", "UPPERCASE_CODE", "has space", "has-dash", "1starts_with_digit", "trailing.dot.", "a" * 65],
)
def test_out_of_pattern_finding_codes_are_refused(bad_code, monkeypatch: pytest.MonkeyPatch) -> None:
    def _bad_scrub(_payload, _safety):
        return {"scrub_checked": True, "findings": [bad_code], "clean": False}

    monkeypatch.setattr(i2b_controller_module, "qualification_scrub_check", _bad_scrub)
    with pytest.raises(ValueError, match="unrecognized finding entry"):
        CategoryBEvidence._build_from_payload({"x": 1}, ArtifactSafetyContext.none_declared())


def test_refused_also_enforces_the_bounded_finding_code_pattern() -> None:
    with pytest.raises(ValueError):
        CategoryBEvidence._refused(("NOT-LOWERCASE",))
    with pytest.raises(ValueError):
        CategoryBEvidence._refused((7,))  # type: ignore[arg-type]
    # the genuine literal this module actually uses still works
    refused = CategoryBEvidence._refused(("safety_context_unprovable",))
    assert refused.retention_ready is False


def test_real_finding_codes_all_satisfy_the_bounded_pattern() -> None:
    """The pattern must accept every code this package's frozen scrub layer
    actually produces -- not merely reject malformed ones."""
    real_codes = (
        "http_url_scheme_present", "https_url_scheme_present",
        "authorization_header_text_present", "bearer_token_marker_present",
        "named_pipe_endpoint_prefix_present", "reasoning_content_present",
        "record_not_ascii_representable", "ipv4_literal_present",
        "endpoint_host_value_present", "api_key_value_present",
        "bearer_token_present", "broker_token_present",
        "broker_pipe_name_present", "broker_capability_id_present",
        "workspace_absolute_path_present", "safety_context_unprovable",
        "evidence_not_yet_built",
    )
    for code in real_codes:
        assert i2b_controller_module._FINDING_CODE_PATTERN.fullmatch(code), code


# -- nearby value-object coherence sweep: annotation-only trust ---------------


@pytest.mark.parametrize("bad", ["RUNTIME_TEARDOWN_FAILED", 7, object(), ["x"]])
def test_resource_closure_status_failure_code_is_exact_type_checked(bad) -> None:
    """Found in post-implementation self-review: a raw value used to
    construct successfully and only blow up LATER, with an unrelated
    AttributeError, inside `.status_text`."""
    with pytest.raises(ValueError):
        RuntimeTeardownStatus(state=ResourceClosureState.SHUTDOWN_FAILED, failure_code=bad)
    with pytest.raises(ValueError):
        BrokerShutdownStatus(state=ResourceClosureState.SHUTDOWN_FAILED, failure_code=bad)


@pytest.mark.parametrize("bad", ["not-a-classification", 7, object(), ["x"]])
def test_cleanup_status_classification_is_exact_type_checked(bad) -> None:
    with pytest.raises(ValueError):
        CleanupStatus(attempted=True, scrub_verified=False, classification=bad)


def test_cleanup_status_text_agrees_with_what_fail_actually_records(
    run_workspace: QualificationRunWorkspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression for a REAL production bug found via the new equality
    binding: ``CleanupStatus.status_text`` used to embed
    ``classification.autonomous_classification.value`` (an
    ``AutonomousClassification`` member) while the controller's own
    ``_fail()`` always overwrites ``gate_statuses['generated_config_cleanup']``
    with ``CategoryBFailureCode.GENERATED_CONFIG_CLEANUP_UNVERIFIED`` --  two
    DIFFERENT strings for the SAME gate, in the SAME evidence body, under two
    different keys. Reproduced end to end through the real controller.
    """

    def _unverified(_config):
        raise RuntimeError("synthetic cleanup failure")

    monkeypatch.setattr(i2b_controller_module, "scrub_generated_qualification_config", _unverified)
    result, _ = _run(run_workspace)
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.GENERATED_CONFIG_CLEANUP
    assert result.cleanup.status_text == (
        f"FAILED:{CategoryBFailureCode.GENERATED_CONFIG_CLEANUP_UNVERIFIED.value}"
    )
    assert (
        result.gate_statuses[CategoryBGateName.GENERATED_CONFIG_CLEANUP.value]
        == result.cleanup.status_text
    )
    assert (
        result.evidence.as_dict()["orchestrator_generated_config_cleanup_status"]
        == result.cleanup.status_text
    )
    import shutil

    shutil.rmtree(Path(run_workspace.experiment_root, "i2_pi_config"), ignore_errors=True)


def test_cleanup_status_classification_is_a_real_diagnostic_still_carried() -> None:
    """The fix removed `classification` from `status_text`'s SOURCE, not
    from the object -- it remains a real, validated, retained fact."""
    classification = i2b_controller_module.classify_cleanup_failure(semantic_prompts_sent=0)
    status = CleanupStatus(attempted=True, scrub_verified=False, classification=classification)
    assert status.classification is classification
    assert status.status_text == f"FAILED:{CategoryBFailureCode.GENERATED_CONFIG_CLEANUP_UNVERIFIED.value}"


# -- post-implementation adversarial review -----------------------------------


def test_dataclasses_replace_cannot_break_a_genuine_passing_result() -> None:
    """A genuine PASS, mutated field-by-field via dataclasses.replace, must
    be refused for EVERY field this phase newly binds."""
    valid = _build_result()
    assert valid.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED

    with pytest.raises(ValueError):
        dataclasses.replace(valid, pi_config_created=False)
    with pytest.raises(ValueError):
        dataclasses.replace(
            valid, runtime_teardown=RuntimeTeardownStatus(state=ResourceClosureState.NOT_REQUIRED)
        )
    with pytest.raises(ValueError):
        dataclasses.replace(valid, candidate="not-a-frozen-candidate")
    with pytest.raises(ValueError):
        dataclasses.replace(valid, observed_pi_version=None)
    with pytest.raises(ValueError):
        dataclasses.replace(
            valid,
            evidence=CategoryBEvidence._build_from_payload(
                {"unrelated": True}, ArtifactSafetyContext.none_declared()
            ),
        )
    bad_pairs = dict(valid.gate_statuses)
    bad_pairs[CategoryBGateName.ROUTE_CHECK.value] = "NOT_REACHED"
    with pytest.raises(ValueError):
        dataclasses.replace(valid, _gate_status_pairs=tuple(sorted(bad_pairs.items())))


def _minimal_refusal_facts(**overrides) -> CompatibilityFacts:
    """All facts False by default -- a bare, "nothing established" refusal shape."""
    kwargs = dict(
        pi_version_observed=False, rpc_launch_shape_valid=False, required_launch_flags_accepted=False,
        lf_jsonl_correlation_succeeded=False, get_commands_response_shape_understood=False,
        h1_extension_identity_matched=False, no_unexpected_extension_command_observed=False,
        get_state_response_shape_understood=False, h2_provider_model_identity_matched=False,
        no_protocol_violation_observed=False, no_extension_error_observed=False,
        exact_candidate_model_served=False, broker_reached_required_ready_state=False,
    )
    kwargs.update(overrides)
    return CompatibilityFacts(**kwargs)


#: FU2D: the two gate statuses that mean a full session object was returned.
_BROKER_SESSION_RETURNED = frozenset(
    {"PASSED", f"FAILED:{CategoryBFailureCode.BROKER_SESSION_MISMATCH.value}"}
)
_RUNTIME_SESSION_RETURNED = frozenset(
    {"PASSED", f"FAILED:{CategoryBFailureCode.RUNTIME_SESSION_MISMATCH.value}"}
)


def _reachable_compatibility_pairs(failed: dict | None = None) -> dict:
    """FU2D: a genuinely REACHABLE compatibility-gate trace.

    Replaces the old `_all_not_reached_pairs`, whose premise -- "every gate
    NOT_REACHED except the ones a test happens to name" -- was itself an
    impossible-trace generator: it produced traces like
    `WORKSPACE_AUTHORITY=NOT_REACHED` alongside `ROUTE_DESCRIPTOR=FAILED`, or
    a single launch-fact gate reporting a verdict while its three siblings
    (which the controller's own loop always sets together) stayed
    NOT_REACHED. Tests built on it were therefore not isolating the invariant
    they named at all -- the new trace validator would have caught them
    first.

    Walks the compatibility gates in order applying the SAME prerequisite
    rules the controller declares (`_GATE_PREREQUISITES`, imported rather
    than re-declared, so this helper can never drift from the source):
    a gate named in `failed` gets its code, a gate whose prerequisites all
    passed gets `PASSED`, and everything else gets `NOT_REACHED`.

    Both intentional observation-group behaviours fall out for free: naming
    ONE launch-fact gate as failed leaves its three siblings `PASSED` (all
    four are reached together), and naming `H1_EXTENSION_IDENTITY` failed
    leaves `EXTENSION_COMMAND_NAMESPACE` reached too.
    """
    failed = failed or {}
    pairs: dict = {}
    for gate in COMPATIBILITY_GATES:
        if gate in failed:
            pairs[gate.value] = f"FAILED:{failed[gate].value}"
            continue
        prerequisites = i2b_controller_module._GATE_PREREQUISITES[gate]
        pairs[gate.value] = (
            "PASSED"
            if all(pairs[p.value] == "PASSED" for p in prerequisites)
            else "NOT_REACHED"
        )
    return pairs


def _closure_objects_for_trace(pairs: dict) -> tuple:
    """FU2D: the closure objects and existence booleans a controller run with
    THIS compatibility trace would actually have produced.

    Derived exactly as the controller does:
    `pi_config_created = generated_config is not None` (i.e. that gate
    passed); `broker_created`/`runtime_session_established` = whether a full
    session object was returned; and each closure state follows from whether
    a session existed and whether it was this run's own.
    """
    pi_config_created = pairs[CategoryBGateName.PI_CONFIG_GENERATION.value] == "PASSED"
    broker_status = pairs[CategoryBGateName.BROKER_SESSION.value]
    launch_status = pairs[CategoryBGateName.RUNTIME_LAUNCH.value]
    broker_created = broker_status in _BROKER_SESSION_RETURNED
    runtime_established = launch_status in _RUNTIME_SESSION_RETURNED

    if not runtime_established:
        runtime_teardown = RuntimeTeardownStatus(state=ResourceClosureState.NOT_REQUIRED)
    elif launch_status == "PASSED":
        runtime_teardown = RuntimeTeardownStatus(
            state=ResourceClosureState.CLOSED_BY_ORCHESTRATOR
        )
    else:
        runtime_teardown = RuntimeTeardownStatus(
            state=ResourceClosureState.SHUTDOWN_REFUSED_FOREIGN_SESSION,
            failure_code=CategoryBFailureCode.RUNTIME_SHUTDOWN_REFUSED_FOREIGN_SESSION,
        )

    if not broker_created:
        broker_shutdown = BrokerShutdownStatus(state=ResourceClosureState.NOT_REQUIRED)
    elif broker_status == "PASSED":
        broker_shutdown = BrokerShutdownStatus(
            state=ResourceClosureState.CLOSED_BY_ORCHESTRATOR
        )
    else:
        broker_shutdown = BrokerShutdownStatus(
            state=ResourceClosureState.SHUTDOWN_REFUSED_FOREIGN_SESSION,
            failure_code=CategoryBFailureCode.BROKER_SHUTDOWN_REFUSED_FOREIGN_SESSION,
        )

    cleanup = (
        CleanupStatus(attempted=True, scrub_verified=True, classification=None)
        if pi_config_created
        else CleanupStatus(attempted=False, scrub_verified=None, classification=None)
    )
    return (
        pi_config_created,
        broker_created,
        runtime_established,
        runtime_teardown,
        broker_shutdown,
        cleanup,
    )


def _facts_for_trace(pairs: dict, **overrides) -> CompatibilityFacts:
    """The `CompatibilityFacts` a run with THIS trace would have recorded:
    each single-mapped fact equals its own gate's PASSED-ness (defaulting to
    False for a gate never reached), the two PROTOCOL_INTEGRITY facts follow
    that gate. Overrides let a test express the accepted launch-fact
    asymmetry (observed True while the gate itself was never reached), or
    deliberately LIE about one fact to prove the fact-vs-gate check.
    """
    values = {
        name: pairs[gate.value] == "PASSED"
        for name, gate in i2b_controller_module._SINGLE_FACT_TO_GATE.items()
    }
    protocol_passed = pairs[CategoryBGateName.PROTOCOL_INTEGRITY.value] == "PASSED"
    values["no_protocol_violation_observed"] = protocol_passed
    values["no_extension_error_observed"] = protocol_passed
    values.update(overrides)
    return CompatibilityFacts(**values)


_UNSET = object()


def _reachable_refusal(
    *,
    failed: dict,
    failed_gate: CategoryBGateName,
    failure_code: CategoryBFailureCode,
    fact_overrides: dict | None = None,
    observed_pi_version=_UNSET,
    evidence=None,
    **overrides,
):
    """FU2D: a fully self-consistent, genuinely REACHABLE refusal result.

    Every field not explicitly overridden is DERIVED from the trace, so a
    test overriding exactly one thing is isolating exactly that one thing.
    """
    pairs = _reachable_compatibility_pairs(failed)
    (
        pi_config_created,
        broker_created,
        runtime_established,
        runtime_teardown,
        broker_shutdown,
        cleanup,
    ) = _closure_objects_for_trace(pairs)
    runtime_teardown = overrides.pop("runtime_teardown", runtime_teardown)
    broker_shutdown = overrides.pop("broker_shutdown", broker_shutdown)
    cleanup = overrides.pop("cleanup", cleanup)
    full = dict(pairs)
    full[CategoryBGateName.RUNTIME_TEARDOWN.value] = runtime_teardown.status_text
    full[CategoryBGateName.BROKER_SHUTDOWN.value] = broker_shutdown.status_text
    full[CategoryBGateName.GENERATED_CONFIG_CLEANUP.value] = cleanup.status_text
    evidence = (
        evidence
        if evidence is not None
        else CategoryBEvidence._refused(
            i2b_controller_module._SAFETY_CONTEXT_UNPROVABLE_REFUSAL
        )
    )
    # FU2F: EVIDENCE_SAFETY is bound to evidence's ACTUAL construction origin,
    # not merely retention_ready -- derive it the same way the real
    # controller does, so a test supplying a genuine BUILT-but-dirty body (not
    # just the default REFUSED one) does not trip that binding instead of the
    # check it is exercising.
    if evidence.retention_ready:
        _evidence_safety_status = "PASSED"
    elif evidence._origin == i2b_controller_module._EVIDENCE_ORIGIN_BUILT:
        _evidence_safety_status = f"FAILED:{CategoryBFailureCode.EVIDENCE_SCRUB_REFUSED.value}"
    else:
        _evidence_safety_status = f"FAILED:{CategoryBFailureCode.SAFETY_CONTEXT_UNPROVABLE.value}"
    full[CategoryBGateName.EVIDENCE_SAFETY.value] = _evidence_safety_status
    full.update(overrides.pop("_gate_status_overrides", {}))
    facts = _facts_for_trace(pairs, **(fact_overrides or {}))
    if observed_pi_version is _UNSET:
        # Derived, not guessed: the universal cross-field invariant requires
        # `facts.pi_version_observed == (observed_pi_version is not None)`,
        # so a helper that hard-coded either one would make every caller
        # trip THAT check instead of the one it is actually testing.
        observed_pi_version = "0.84.3" if facts.pi_version_observed else None
    kwargs = dict(
        candidate="A",
        outcome=CategoryBOutcome.INFRASTRUCTURE_REFUSAL,
        semantic_prompts_sent=0,
        failed_gate=failed_gate,
        failure_code=failure_code,
        facts=facts,
        observed_pi_version=observed_pi_version,
        pi_config_created=pi_config_created,
        broker_created=broker_created,
        runtime_session_established=runtime_established,
        runtime_teardown=runtime_teardown,
        broker_shutdown=broker_shutdown,
        cleanup=cleanup,
        evidence=evidence,
        _gate_status_pairs=tuple(sorted(full.items())),
    )
    kwargs.update(overrides)
    return CategoryBControllerResult(**kwargs)


def test_a_fact_claiming_true_while_its_own_gate_is_failed_is_refused() -> None:
    """The exact bypass found in post-implementation self-review: a
    hand-built REFUSAL claiming `facts.h1_extension_identity_matched=True`
    while `gate_statuses['h1_extension_identity']` reads `FAILED:...` -- two
    individually-typed, individually-valid objects that disagree about the
    SAME underlying fact.
    """
    # FU2D: built on a genuinely REACHABLE trace now -- H1 and the namespace
    # gate both fail from ONE successful get_commands, and every resource
    # fact is derived from that trace rather than hand-set to an impossible
    # combination. Only the ONE fact under test lies.
    with pytest.raises(ValueError, match="disagrees with gate_statuses"):
        _reachable_refusal(
            failed={
                CategoryBGateName.H1_EXTENSION_IDENTITY: CategoryBFailureCode.H1_EXTENSION_IDENTITY_MISMATCH,
                CategoryBGateName.EXTENSION_COMMAND_NAMESPACE: CategoryBFailureCode.UNEXPECTED_CLI_EXTENSION_COMMAND,
            },
            failed_gate=CategoryBGateName.H1_EXTENSION_IDENTITY,
            failure_code=CategoryBFailureCode.H1_EXTENSION_IDENTITY_MISMATCH,
            fact_overrides={"h1_extension_identity_matched": True},  # LIES: gate says FAILED
            observed_pi_version="0.84.3",
        )


def test_every_single_mapped_fact_is_checked_against_its_own_gate() -> None:
    """Sweep all eleven single-mapped facts: each, claimed True while its
    OWN gate reads FAILED, is refused independently.

    FU2D: each sweep entry now sits on a genuinely reachable trace whose
    first failure IS that gate, so the fact-vs-gate check is what fires --
    previously every entry rode on an unreachable all-NOT_REACHED trace.
    """
    table = i2b_controller_module._SINGLE_FACT_TO_GATE
    assert len(table) == 11
    for fact_name, gate in table.items():
        # Use the gate's OWN first allowed code, so the per-gate-vocabulary
        # check does not mask THIS check.
        allowed = next(
            iter(i2b_controller_module._COMPATIBILITY_GATE_ALLOWED_FAILURE_CODE_VALUES[gate.value])
        )
        code = CategoryBFailureCode(allowed)
        # `observed_pi_version` is DERIVED by the helper from the resulting
        # facts, so the separate universal cross-field check binding the two
        # cannot fire first and mask THIS check.
        with pytest.raises(ValueError, match="disagrees with gate_statuses"):
            _reachable_refusal(
                failed={gate: code},
                failed_gate=gate,
                failure_code=code,
                fact_overrides={fact_name: True},
            ), fact_name


def test_protocol_integrity_conjunction_is_checked() -> None:
    # no_protocol_violation_observed=True alone (extension_error is the one
    # that actually failed) must NOT be enough to claim the gate passed.
    with pytest.raises(ValueError, match="protocol_integrity"):
        _reachable_refusal(
            failed={
                CategoryBGateName.PROTOCOL_INTEGRITY: CategoryBFailureCode.EXTENSION_ERROR_OBSERVED
            },
            failed_gate=CategoryBGateName.PROTOCOL_INTEGRITY,
            failure_code=CategoryBFailureCode.EXTENSION_ERROR_OBSERVED,
            fact_overrides={
                "no_protocol_violation_observed": True,
                "no_extension_error_observed": True,
            },
            observed_pi_version="0.84.3",
        )


def test_the_launch_facts_may_legitimately_be_true_while_not_reached() -> None:
    """The ONE honest exception: the four launch facts are recorded from the
    launch observation BEFORE the controller knows whether RUNTIME_LAUNCH
    itself will pass (a session mismatch can still fail RUNTIME_LAUNCH after
    a fact already reads True). This positive control proves the guard does
    not over-refuse this genuinely legitimate, already-accepted state.
    """
    # FU2D CORRECTION. The shape this test previously asserted as a valid
    # "positive control" was itself UNREACHABLE, and was the brief's own
    # primary counterexample: it claimed `pi_config_created=False` while
    # PI_CONFIG_GENERATION read PASSED (the controller assigns
    # `generated_config` exactly there), `cleanup` NOT_REQUIRED alongside
    # that, and `runtime_session_established=False` alongside a
    # RUNTIME_SESSION_MISMATCH refusal -- but that refusal happens only
    # AFTER `launch_observation.session` was returned and assigned, so a
    # runtime session provably DID exist. Refusing to shut a foreign session
    # down is not the same fact as no session having been returned.
    #
    # The genuine, reachable shape of this exception is below, and the
    # accepted asymmetry it exists to protect is untouched: the four launch
    # FACTS read True while their own GATES stay NOT_REACHED.
    result = _reachable_refusal(
        failed={CategoryBGateName.RUNTIME_LAUNCH: CategoryBFailureCode.RUNTIME_SESSION_MISMATCH},
        failed_gate=CategoryBGateName.RUNTIME_LAUNCH,
        failure_code=CategoryBFailureCode.RUNTIME_SESSION_MISMATCH,
        fact_overrides={
            "pi_version_observed": True,
            "rpc_launch_shape_valid": True,
            "required_launch_flags_accepted": True,
            "lf_jsonl_correlation_succeeded": True,
        },
        observed_pi_version="0.84.3",
    )
    assert result.outcome is CategoryBOutcome.INFRASTRUCTURE_REFUSAL
    # the four launch-fact GATES were genuinely never reached...
    for gate in (
        CategoryBGateName.PI_VERSION_OBSERVED, CategoryBGateName.RPC_LAUNCH_SHAPE,
        CategoryBGateName.REQUIRED_LAUNCH_FLAGS, CategoryBGateName.LF_JSONL_CORRELATION,
    ):
        assert result.gate_statuses[gate.value] == "NOT_REACHED"
    # ...while their FACTS, derived from the observation already in hand, are True
    assert result.facts.pi_version_observed is True
    assert result.facts.lf_jsonl_correlation_succeeded is True
    # and the resource trace is the reachable one: a session WAS returned,
    # the config WAS generated, so cleanup was attempted.
    assert result.runtime_session_established is True
    assert result.runtime_teardown.state is ResourceClosureState.SHUTDOWN_REFUSED_FOREIGN_SESSION
    assert result.pi_config_created is True
    assert result.cleanup.attempted is True


def test_the_launch_facts_are_still_checked_once_their_gate_is_reached() -> None:
    """The exception is narrow: once RUNTIME_LAUNCH passes and the four
    launch-fact gates ARE evaluated, disagreement is refused exactly like
    every other fact.
    """
    with pytest.raises(ValueError, match="disagrees with gate_statuses"):
        _reachable_refusal(
            failed={
                CategoryBGateName.PI_VERSION_OBSERVED: CategoryBFailureCode.PI_VERSION_NOT_OBSERVED
            },
            failed_gate=CategoryBGateName.PI_VERSION_OBSERVED,
            failure_code=CategoryBFailureCode.PI_VERSION_NOT_OBSERVED,
            # LIES: the gate says FAILED, and it genuinely WAS reached
            fact_overrides={"pi_version_observed": True},
            # a real, non-None version, so this isolates the fact-vs-gate
            # check from the separate observed_pi_version cross-check
            observed_pi_version="0.84.3",
        )


@pytest.mark.parametrize(
    "harness_kwargs, failed_gate",
    [
        ({"broker_ready": False}, CategoryBGateName.BROKER_READY),
        ({"pi_version": None}, CategoryBGateName.PI_VERSION_OBSERVED),
        ({"protocol_violation": True}, CategoryBGateName.PROTOCOL_INTEGRITY),
        ({"route_reachable": False, "route_model_served": False}, CategoryBGateName.ROUTE_CHECK),
    ],
)
def test_every_real_refusal_path_satisfies_the_new_binding_invariants(
    run_workspace: QualificationRunWorkspace, harness_kwargs: dict, failed_gate: CategoryBGateName
) -> None:
    """The strongest end-to-end proof: real controller refusals at DIFFERENT
    gates all construct cleanly under the new cross-field/gate-status/
    evidence-binding invariants -- not merely synthetic ones.
    """
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], **harness_kwargs)
    result, _ = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.failed_gate is failed_gate
    # the binding checks already ran inside __post_init__ (construction
    # succeeded); re-assert the headline agreement explicitly too
    assert result.pi_config_created == result.cleanup.attempted
    assert result.facts.pi_version_observed == (result.observed_pi_version is not None)
    assert (
        result.gate_statuses[CategoryBGateName.RUNTIME_TEARDOWN.value]
        == result.runtime_teardown.status_text
    )
    assert (
        result.gate_statuses[CategoryBGateName.BROKER_SHUTDOWN.value]
        == result.broker_shutdown.status_text
    )
    assert (
        result.gate_statuses[CategoryBGateName.GENERATED_CONFIG_CLEANUP.value]
        == result.cleanup.status_text
    )


def test_a_and_b_both_still_pass_under_every_new_invariant(
    run_workspace: QualificationRunWorkspace, second_run_workspace: QualificationRunWorkspace
) -> None:
    """Positive control: candidate A and B both still pass end to end under
    every new cross-field/gate-status/evidence-binding invariant."""
    result_a, _ = _run(run_workspace, candidate="A")
    result_b, _ = _run(second_run_workspace, candidate="B")
    assert result_a.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED
    assert result_b.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED

def test_a_workspace_object_is_frozen(run_workspace: QualificationRunWorkspace) -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        run_workspace.workspace_root = "C:\\dev\\mis_project"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        run_workspace.run_workspace_nonce = "other"  # type: ignore[misc]


# -- ZERO-PROMPT AUTHORITY ----------------------------------------------------

_I2B_MODULES = (i2b_controller_module, i2b_session_module, i2b_workspace_module)

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
_ALLOWED_PROMPT_SHAPED_NAMES = frozenset({"SEMANTIC_PROMPTS_SENT", "semantic_prompts_sent"})

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

#: ``i2b_workspace`` is the ONE module allowed to touch the filesystem, and
#: only to create/verify one disposable directory tree. It still may not
#: import a network/process primitive, and still may not read an environment
#: variable -- but ``os.path``/``os.mkdir`` are exactly its job.
_FILESYSTEM_MODULES = frozenset({i2b_workspace_module.__name__})
_FILESYSTEM_ALLOWED_FRAGMENTS = frozenset()


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
        allowed = (
            _FILESYSTEM_ALLOWED_FRAGMENTS if module.__name__ in _FILESYSTEM_MODULES else frozenset()
        )
        for fragment in _FORBIDDEN_CODE_FRAGMENTS:
            if fragment in allowed:
                continue
            assert fragment not in code, f"{module.__name__} code contains {fragment!r}"


def test_the_controller_exposes_no_prompt_parameter() -> None:
    signature = inspect.signature(run_category_b_controller)
    for name in signature.parameters:
        assert "prompt" not in name.lower()
        assert "message" not in name.lower()
        assert "task" not in name.lower()


def test_semantic_prompts_sent_is_a_constant_zero(
    run_workspace: QualificationRunWorkspace,
) -> None:
    assert i2b_controller_module.SEMANTIC_PROMPTS_SENT == 0
    result, _ = _run(run_workspace)
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
        {"h1_components": {"sentinel_name_matched": False}},
        {"protocol_violation": True},
        {"route_reachable": False, "route_model_served": False},
        {"runtime_child_exited": False},
        {"broker_reached_closed": False},
        {"launch_raises": True},
    ],
)
def test_every_category_b_failure_is_a_pre_prompt_infrastructure_refusal(
    run_workspace: QualificationRunWorkspace, harness_kwargs: dict
) -> None:
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], **harness_kwargs)
    result, _ = _run(run_workspace, harness=harness)
    assert result.outcome is CategoryBOutcome.INFRASTRUCTURE_REFUSAL
    assert result.semantic_prompts_sent == 0
    assert result.compatibility_gate_passed is False


# -- truthful claim scope -----------------------------------------------------


def test_the_evidence_never_claims_backend_inference_stopped(
    run_workspace: QualificationRunWorkspace,
) -> None:
    result, _ = _run(run_workspace)
    body = result.evidence.as_dict()
    assert body["backend_inference_lifetime_after_teardown"] == "not observed"
    assert body["descendant_process_lifetime_after_teardown"] == "not observed"
    scope = body["claim_scope"]
    assert "NOT a claim that a descendant process was terminated" in scope
    for forbidden in (
        "descendant process was terminated",
        "inference stopped",
        "GPU work stopped",
    ):
        assert f"the {forbidden}" not in scope


def test_the_evidence_records_the_tool_registry_non_observation(
    run_workspace: QualificationRunWorkspace,
) -> None:
    result, _ = _run(run_workspace)
    body = result.evidence.as_dict()
    assert body["active_tool_registry_observation_available"] is False
    assert body["provider_request_count_observation_available"] is False
    assert body["wire_level_max_tokens_observation_available"] is False
    assert body["tool_registry_claim_scope"] == list(TOOL_REGISTRY_CLAIM_SCOPE)
    joined = "\n".join(body["tool_registry_claim_scope"])
    assert "configured registry allowlist" in joined
    assert "extension identity" in joined
    assert "NOT established" in joined
    assert "runtime registry contained only those two" in joined
    assert "NOT an observation of the active tool registry" in body["claim_scope"]


def test_teardown_success_is_scoped_to_aidos_own_direct_child(
    run_workspace: QualificationRunWorkspace,
) -> None:
    harness = _Harness(
        model_id=CANDIDATE_MODEL_IDS["A"], runtime_shutdown_returned=True, runtime_child_exited=False
    )
    result, _ = _run(run_workspace, harness=harness)
    assert result.runtime_teardown.succeeded is False
    assert result.runtime_teardown.closure_satisfied is False


# =============================================================================
# FU2C -- resource/state failure-code domains + first-failure attribution +
#         cleanup-classification coherence
# =============================================================================
#
# Independent review found three residual gaps FU2B's structural checks left
# open, each REPRODUCED against the pre-fix code before any change was made:
#
# 1. `_ResourceClosureStatus` validated `failure_code` by TYPE only (ANY
#    `CategoryBFailureCode` accepted on ANY state, on EITHER resource kind).
#    `RuntimeTeardownStatus(state=SHUTDOWN_FAILED,
#    failure_code=BROKER_SHUTDOWN_INCOMPLETE)` and a foreign-session state
#    carrying the generic teardown-failed code instead of its own
#    foreign-session-specific code both constructed successfully -- the
#    closure gate then trusted that typed object's own `status_text` as
#    internally-consistent but FALSE evidence.
# 2. `failed_gate`/`failure_code` were checked for agreement with THEIR OWN
#    gate's recorded text, but nothing verified `failed_gate` was the FIRST
#    failed gate in the controller's own evaluation order -- a hand-built
#    result could nominate a LATER genuinely-failed gate while an EARLIER one
#    was also independently FAILED in `gate_statuses`.
# 3. `CleanupStatus` checked `classification`'s TYPE
#    (`CleanupFailureClassification`) but not its FIELDS -- an
#    internally-impossible instance (e.g. `semantic_prompts_sent=1` alongside
#    the pre-prompt classification, a shape `classify_cleanup_failure` itself
#    never returns) constructed and was accepted.


# -- Blocker 1: resource/state failure-code domains ---------------------------


def test_fu2c_counterexample_1_runtime_shutdown_failed_carrying_broker_code() -> None:
    """Pre-coding check 1: a runtime SHUTDOWN_FAILED must never carry a
    BROKER-only code."""
    with pytest.raises(ValueError, match="not valid for state"):
        RuntimeTeardownStatus(
            state=ResourceClosureState.SHUTDOWN_FAILED,
            failure_code=CategoryBFailureCode.BROKER_SHUTDOWN_INCOMPLETE,
        )


def test_fu2c_counterexample_2_runtime_foreign_session_carrying_generic_code() -> None:
    """Pre-coding check 2: a runtime foreign-session refusal must carry ITS
    OWN specific code, never the generic ``RUNTIME_TEARDOWN_FAILED`` that
    ``SHUTDOWN_FAILED`` uses."""
    with pytest.raises(ValueError, match="not valid for state"):
        RuntimeTeardownStatus(
            state=ResourceClosureState.SHUTDOWN_REFUSED_FOREIGN_SESSION,
            failure_code=CategoryBFailureCode.RUNTIME_TEARDOWN_FAILED,
        )


def test_fu2c_counterexample_3_broker_shutdown_failed_carrying_runtime_code() -> None:
    """Pre-coding check 3: a broker SHUTDOWN_FAILED must never carry a
    RUNTIME-only code."""
    with pytest.raises(ValueError, match="not valid for state"):
        BrokerShutdownStatus(
            state=ResourceClosureState.SHUTDOWN_FAILED,
            failure_code=CategoryBFailureCode.RUNTIME_TEARDOWN_FAILED,
        )


@pytest.mark.parametrize(
    "status_cls, unrelated_code",
    [
        (RuntimeTeardownStatus, CategoryBFailureCode.BROKER_SHUTDOWN_AUTHORITY_UNAVAILABLE),
        (BrokerShutdownStatus, CategoryBFailureCode.RUNTIME_TEARDOWN_AUTHORITY_UNAVAILABLE),
    ],
)
def test_fu2c_counterexample_4_creator_unverified_carrying_unrelated_resource_code(
    status_cls, unrelated_code
) -> None:
    """Pre-coding check 4: ``CLOSED_BY_CREATOR_UNVERIFIED`` must carry ONLY
    its own shared code, never an unrelated resource-specific one (here: the
    OTHER resource kind's authority-unavailable code)."""
    with pytest.raises(ValueError, match="not valid for state"):
        status_cls(
            state=ResourceClosureState.CLOSED_BY_CREATOR_UNVERIFIED,
            failure_code=unrelated_code,
        )


@pytest.mark.parametrize("status_cls", [RuntimeTeardownStatus, BrokerShutdownStatus])
def test_fu2c_every_state_failure_code_pairing_is_exhaustively_swept(status_cls) -> None:
    """For EVERY unsatisfied state this resource kind can reach, and EVERY
    declared ``CategoryBFailureCode``: the ALLOWED codes construct cleanly,
    and every OTHER code is refused. The strongest available proof that the
    table is EXACT, not merely 'big enough'."""
    table = status_cls._ALLOWED_FAILURE_CODES_BY_STATE
    assert table, f"{status_cls.__name__} declares no allowed-code table at all"
    for state, allowed in table.items():
        assert allowed, f"{status_cls.__name__}/{state} has no allowed failure codes at all"
        for code in CategoryBFailureCode:
            if code in allowed:
                status = status_cls(state=state, failure_code=code)
                assert status.failure_code is code
                assert status.closure_satisfied is False
            else:
                with pytest.raises(ValueError, match="not valid for state"):
                    status_cls(state=state, failure_code=code)


def test_fu2c_a_code_valid_for_runtime_is_not_automatically_valid_for_broker() -> None:
    """The two tables are DISTINCT, not one shared vocabulary re-used by
    name: ``RUNTIME_TEARDOWN_AUTHORITY_UNAVAILABLE`` is valid only on the
    runtime ``SHUTDOWN_AUTHORITY_UNAVAILABLE`` state and refused on the
    broker's, and symmetrically for the broker's own code."""
    RuntimeTeardownStatus(
        state=ResourceClosureState.SHUTDOWN_AUTHORITY_UNAVAILABLE,
        failure_code=CategoryBFailureCode.RUNTIME_TEARDOWN_AUTHORITY_UNAVAILABLE,
    )
    with pytest.raises(ValueError, match="not valid for state"):
        BrokerShutdownStatus(
            state=ResourceClosureState.SHUTDOWN_AUTHORITY_UNAVAILABLE,
            failure_code=CategoryBFailureCode.RUNTIME_TEARDOWN_AUTHORITY_UNAVAILABLE,
        )
    BrokerShutdownStatus(
        state=ResourceClosureState.SHUTDOWN_AUTHORITY_UNAVAILABLE,
        failure_code=CategoryBFailureCode.BROKER_SHUTDOWN_AUTHORITY_UNAVAILABLE,
    )
    with pytest.raises(ValueError, match="not valid for state"):
        RuntimeTeardownStatus(
            state=ResourceClosureState.SHUTDOWN_AUTHORITY_UNAVAILABLE,
            failure_code=CategoryBFailureCode.BROKER_SHUTDOWN_AUTHORITY_UNAVAILABLE,
        )


def test_fu2c_the_shared_creator_retained_codes_really_are_shared() -> None:
    """``CLOSED_BY_CREATOR_UNVERIFIED``/
    ``PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT`` genuinely ARE the same
    two codes on both resource kinds (mirroring
    ``_RUNTIME_CLOSURE_FAILURE_CODES is _BROKER_CLOSURE_FAILURE_CODES`` in
    the source) -- a deliberate, documented exception, never a gap."""
    for state, code in (
        (
            ResourceClosureState.CLOSED_BY_CREATOR_UNVERIFIED,
            CategoryBFailureCode.CLOSED_BY_CREATOR_UNVERIFIED,
        ),
        (
            ResourceClosureState.PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT,
            CategoryBFailureCode.PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT,
        ),
    ):
        RuntimeTeardownStatus(state=state, failure_code=code)
        BrokerShutdownStatus(state=state, failure_code=code)


def test_fu2c_resource_closure_tables_cover_every_unsatisfied_state() -> None:
    unsatisfied = {
        member
        for member in ResourceClosureState
        if member
        not in (
            ResourceClosureState.NOT_REQUIRED,
            ResourceClosureState.CLOSED_BY_ORCHESTRATOR,
            ResourceClosureState.CLOSED_BY_CREATOR_VERIFIED,
        )
    }
    assert set(RuntimeTeardownStatus._ALLOWED_FAILURE_CODES_BY_STATE) == unsatisfied
    assert set(BrokerShutdownStatus._ALLOWED_FAILURE_CODES_BY_STATE) == unsatisfied


def test_fu2c_real_controller_creator_retained_broker_state_still_constructs(
    run_workspace: QualificationRunWorkspace,
) -> None:
    """Positive control (pre-coding check 10): a genuine end-to-end
    creator-retained-ownership refusal -- the broker's creation adapter
    reports a resource it retained ownership of, attempted its own bounded
    close, and could not verify -- still constructs cleanly under the new
    per-state/per-resource code domain, and the shutdown adapter is never
    called (possession is not authority)."""
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"])
    harness.broker_returns_no_session = True
    harness.broker_resource_created = True
    harness.broker_cleanup_attempted = True
    harness.broker_reached_closed_on_partial = False
    result, harness = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.broker_shutdown.state is ResourceClosureState.CLOSED_BY_CREATOR_UNVERIFIED
    assert result.broker_shutdown.failure_code is CategoryBFailureCode.CLOSED_BY_CREATOR_UNVERIFIED
    assert harness.count("shutdown_broker") == 0


# -- Blocker 2: failed_gate must be the FIRST failure -------------------------


def test_fu2c_counterexample_5_earlier_compat_failure_later_closure_failure_wrong_failed_gate() -> None:
    """Pre-coding checks 5/6: ``ROUTE_CHECK`` (compatibility, earlier) AND
    ``RUNTIME_TEARDOWN`` (closure, later) both FAILED -- and RUNTIME_TEARDOWN's
    OWN recorded status genuinely agrees with the nominated failure_code --
    but failed_gate points to the LATER RUNTIME_TEARDOWN. Refused; the first
    failure is ROUTE_CHECK.
    """
    pairs = dict(_passing_gate_status_pairs())
    pairs[CategoryBGateName.ROUTE_CHECK.value] = f"FAILED:{CategoryBFailureCode.ROUTE_CHECK_FAILED.value}"
    rt = RuntimeTeardownStatus(
        state=ResourceClosureState.SHUTDOWN_FAILED,
        failure_code=CategoryBFailureCode.RUNTIME_TEARDOWN_FAILED,
    )
    pairs[CategoryBGateName.RUNTIME_TEARDOWN.value] = rt.status_text
    pairs[CategoryBGateName.EVIDENCE_SAFETY.value] = (
        f"FAILED:{CategoryBFailureCode.SAFETY_CONTEXT_UNPROVABLE.value}"
    )
    facts = _passing_facts(exact_candidate_model_served=False)
    evidence = CategoryBEvidence._refused(("safety_context_unprovable",))
    with pytest.raises(ValueError, match="failed_gate must be the FIRST failed gate"):
        CategoryBControllerResult(
            candidate="A", outcome=CategoryBOutcome.INFRASTRUCTURE_REFUSAL, semantic_prompts_sent=0,
            failed_gate=CategoryBGateName.RUNTIME_TEARDOWN,  # WRONG: ROUTE_CHECK failed FIRST
            failure_code=CategoryBFailureCode.RUNTIME_TEARDOWN_FAILED,
            facts=facts, observed_pi_version="0.84.3",
            pi_config_created=True, broker_created=True, runtime_session_established=True,
            runtime_teardown=rt,
            broker_shutdown=BrokerShutdownStatus(state=ResourceClosureState.CLOSED_BY_ORCHESTRATOR),
            cleanup=CleanupStatus(attempted=True, scrub_verified=True, classification=None),
            evidence=evidence, _gate_status_pairs=tuple(sorted(pairs.items())),
        )


def test_fu2c_counterexample_6_h1_and_namespace_both_failed_wrong_failed_gate_is_later() -> None:
    """Pre-coding checks 5/6, variant: ``H1_EXTENSION_IDENTITY`` and
    ``EXTENSION_COMMAND_NAMESPACE`` both FAILED from the same
    ``get_commands`` observation, but failed_gate points to the LATER
    namespace gate. Refused; H1 failed FIRST.
    """
    # FU2D: rebuilt on a genuinely reachable trace. Nothing lies about a
    # FACT or about a resource here -- only `failed_gate` itself is wrong.
    with pytest.raises(ValueError, match="failed_gate must be the FIRST failed gate"):
        _reachable_refusal(
            failed={
                CategoryBGateName.H1_EXTENSION_IDENTITY: CategoryBFailureCode.H1_EXTENSION_IDENTITY_MISMATCH,
                CategoryBGateName.EXTENSION_COMMAND_NAMESPACE: CategoryBFailureCode.UNEXPECTED_CLI_EXTENSION_COMMAND,
            },
            failed_gate=CategoryBGateName.EXTENSION_COMMAND_NAMESPACE,  # WRONG: H1 failed FIRST
            failure_code=CategoryBFailureCode.UNEXPECTED_CLI_EXTENSION_COMMAND,
            observed_pi_version="0.84.3",
        )


def test_fu2c_evidence_safety_alone_failing_may_be_failed_gate() -> None:
    """Pre-coding check 4 (from the brief's own list): when every other gate
    passed/closed and only EVIDENCE_SAFETY fails, failed_gate=EVIDENCE_SAFETY
    is accepted -- it is genuinely the (only, hence first) failed gate.

    FU2F CORRECTION: this test previously paired `EVIDENCE_SCRUB_REFUSED`
    with `CategoryBEvidence._refused(("safety_context_unprovable",))` -- the
    real controller's SAFETY_CONTEXT_UNPROVABLE evidence shape, not a shape
    `EVIDENCE_SCRUB_REFUSED` can ever accompany (that code is only ever
    emitted for a `_build_from_payload` body that is not retention-ready).
    This is that phase's own reproduced counterexample. The evidence object
    below is now a GENUINE scrub refusal -- built via the same real,
    unmodified `_build_from_payload` -> `qualification_scrub_check` path
    `test_retention_ready_true_is_only_reachable_by_actually_scrubbing_the_
    payload` already uses, with an actual API key both declared to the
    safety context and present in the payload -- never a monkeypatch, and
    never the safety-context-unprovable shape.
    """
    pairs = dict(_passing_gate_status_pairs())
    pairs[CategoryBGateName.EVIDENCE_SAFETY.value] = (
        f"FAILED:{CategoryBFailureCode.EVIDENCE_SCRUB_REFUSED.value}"
    )
    facts = _passing_facts()
    safety = ArtifactSafetyContext(api_key="sk-should-be-caught")
    evidence = CategoryBEvidence._build_from_payload({"note": "sk-should-be-caught"}, safety)
    assert evidence.retention_ready is False
    assert evidence._origin == i2b_controller_module._EVIDENCE_ORIGIN_BUILT
    result = CategoryBControllerResult(
        candidate="A", outcome=CategoryBOutcome.INFRASTRUCTURE_REFUSAL, semantic_prompts_sent=0,
        failed_gate=CategoryBGateName.EVIDENCE_SAFETY,
        failure_code=CategoryBFailureCode.EVIDENCE_SCRUB_REFUSED,
        facts=facts, observed_pi_version="0.84.3",
        pi_config_created=True, broker_created=True, runtime_session_established=True,
        runtime_teardown=RuntimeTeardownStatus(state=ResourceClosureState.CLOSED_BY_ORCHESTRATOR),
        broker_shutdown=BrokerShutdownStatus(state=ResourceClosureState.CLOSED_BY_ORCHESTRATOR),
        cleanup=CleanupStatus(attempted=True, scrub_verified=True, classification=None),
        evidence=evidence, _gate_status_pairs=tuple(sorted(pairs.items())),
    )
    assert result.failed_gate is CategoryBGateName.EVIDENCE_SAFETY


def test_fu2c_real_pipeline_earlier_compat_failure_stays_failed_gate_despite_later_cleanup_failure(
    run_workspace: QualificationRunWorkspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pre-coding check 3 / genuine end-to-end reproduction: a real
    PROTOCOL_INTEGRITY (compatibility) failure, combined with a real
    generated-config cleanup failure (closure, always resolved regardless of
    where compatibility stopped) -- the FIRST, EARLIER compatibility failure
    remains failed_gate.
    """

    def _always_raises(_config):
        raise RuntimeError("synthetic cleanup failure")

    monkeypatch.setattr(i2b_controller_module, "scrub_generated_qualification_config", _always_raises)
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], protocol_violation=True)
    result, _ = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.PROTOCOL_INTEGRITY
    assert result.gate_statuses[CategoryBGateName.GENERATED_CONFIG_CLEANUP.value].startswith("FAILED:")

    import shutil

    shutil.rmtree(Path(run_workspace.experiment_root, "i2_pi_config"), ignore_errors=True)


@pytest.mark.parametrize(
    "harness_kwargs",
    [
        {"broker_ready": False},
        {"pi_version": None},
        {"h1_components": {"malformed_source_metadata": True}},  # real H1+namespace double failure
        {"protocol_violation": True},
        {"route_reachable": False, "route_model_served": False},
        {"runtime_child_exited": False},  # closure-only failure, everything else passes
        {"broker_reached_closed": False},  # closure-only failure, everything else passes
    ],
)
def test_fu2c_real_refusals_failed_gate_is_always_the_first_failed_gate_in_declared_order(
    run_workspace: QualificationRunWorkspace, harness_kwargs: dict
) -> None:
    """Pre-coding check 5 (genuine controller refusals remain constructible),
    stated as a GENERAL property over many real refusal shapes -- including
    ones where two gates fail from one observation, and ones where every
    compatibility gate passes and only a closure gate fails."""
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], **harness_kwargs)
    result, _ = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    first_failed = next(
        gate
        for gate in CategoryBGateName
        if result.gate_statuses[gate.value].startswith("FAILED:")
    )
    assert result.failed_gate is first_failed


def test_fu2c_a_genuine_pass_still_constructs_with_no_failed_gate_check_active() -> None:
    """Positive control: the ordinary valid PASS baseline is unaffected by
    the new 'no FAILED gate on a PASS' check."""
    result = _build_result()
    assert result.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED
    assert result.failed_gate is None


# -- Blocker 3: CleanupFailureClassification internal coherence --------------


def _reference_cleanup_classification():
    """The ONE shape Category-B can ever produce -- read straight off the
    frozen, reused ``classify_cleanup_failure`` rather than hand-declared."""
    return i2b_controller_module.classify_cleanup_failure(semantic_prompts_sent=0)


def test_fu2c_pre_coding_check_7_wrong_semantic_prompts_sent_is_refused() -> None:
    bad = dataclasses.replace(_reference_cleanup_classification(), semantic_prompts_sent=1)
    with pytest.raises(ValueError, match="semantic_prompts_sent"):
        CleanupStatus(attempted=True, scrub_verified=False, classification=bad)


def test_fu2c_pre_coding_check_8_scoring_eligible_true_is_refused() -> None:
    bad = dataclasses.replace(_reference_cleanup_classification(), scoring_eligible=True)
    with pytest.raises(ValueError, match="scoring_eligible"):
        CleanupStatus(attempted=True, scrub_verified=False, classification=bad)


def test_fu2c_pre_coding_check_9_wrong_autonomous_classification_is_refused() -> None:
    bad = dataclasses.replace(_reference_cleanup_classification(), autonomous_classification=None)
    with pytest.raises(ValueError, match="autonomous_classification"):
        CleanupStatus(attempted=True, scrub_verified=False, classification=bad)


def test_fu2c_cleanup_classification_run_validity_set_is_refused() -> None:
    """The four-field shape's remaining field: a pre-prompt refusal must
    carry no ``run_validity`` at all."""
    post_prompt = i2b_controller_module.classify_cleanup_failure(semantic_prompts_sent=1)
    bad = dataclasses.replace(
        _reference_cleanup_classification(), run_validity=post_prompt.run_validity
    )
    with pytest.raises(ValueError, match="run_validity"):
        CleanupStatus(attempted=True, scrub_verified=False, classification=bad)


def test_fu2c_cleanup_classification_semantic_prompts_sent_false_is_refused() -> None:
    """``False == 0`` in Python -- confirm the exact-int check catches it
    here too, not merely the (already-covered) result-level field."""
    assert False == 0  # documents the Python behavior this guards against
    bad = dataclasses.replace(_reference_cleanup_classification(), semantic_prompts_sent=False)
    with pytest.raises(ValueError):
        CleanupStatus(attempted=True, scrub_verified=False, classification=bad)


@pytest.mark.parametrize("bad_scoring_eligible", [1, 0, "false", None])
def test_fu2c_cleanup_classification_scoring_eligible_non_bool_is_refused(
    bad_scoring_eligible,
) -> None:
    bad = dataclasses.replace(
        _reference_cleanup_classification(), scoring_eligible=bad_scoring_eligible
    )
    with pytest.raises(ValueError, match="scoring_eligible"):
        CleanupStatus(attempted=True, scrub_verified=False, classification=bad)


def test_fu2c_pre_coding_check_10_genuine_cleanup_classification_still_constructs() -> None:
    """Positive control: the actual reachable Category-B shape is accepted,
    and the object is retained unchanged as a real diagnostic."""
    good = _reference_cleanup_classification()
    status = CleanupStatus(attempted=True, scrub_verified=False, classification=good)
    assert status.classification is good


def test_fu2c_real_pipeline_cleanup_failure_still_constructs_under_the_new_check(
    run_workspace: QualificationRunWorkspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Positive control, end-to-end: a genuine controller-driven cleanup
    failure still produces an accepted ``CleanupStatus.classification``."""

    def _unverified(_config):
        raise RuntimeError("synthetic cleanup failure")

    monkeypatch.setattr(i2b_controller_module, "scrub_generated_qualification_config", _unverified)
    result, _ = _run(run_workspace)
    _assert_refusal(result)
    assert result.cleanup.classification is not None
    assert result.cleanup.classification == _reference_cleanup_classification()

    import shutil

    shutil.rmtree(Path(run_workspace.experiment_root, "i2_pi_config"), ignore_errors=True)


def test_fu2c_no_i2b_module_names_autonomous_classification() -> None:
    """This module's own residual proof: the fix reuses
    ``classify_cleanup_failure``'s own return value for comparison rather
    than importing/naming ``AutonomousClassification`` inside
    ``i2b_controller`` -- ``test_no_candidate_scoring_machinery_is_reachable``
    already forbids that token in this module's code; this test pins down
    WHY the FU2C fix does not need to violate it.
    """
    source = _module_code_only(i2b_controller_module)
    assert "AutonomousClassification" not in source
    assert "from .outcomes" not in source


# =============================================================================
# FU2D -- refusal-trace + resource-existence coherence closure
# =============================================================================
#
# FU2C closed WHICH failure code a gate/resource may carry and WHICH gate may
# be nominated as `failed_gate`. Independent review found the remaining gap
# was one layer up: individually-valid resource and gate objects could still
# describe an EXECUTION TRACE the real controller could never have produced.
# The suite's own `test_the_launch_facts_may_legitimately_be_true_while_not_
# reached` "positive control" WAS such a trace -- PI_CONFIG_GENERATION PASSED
# alongside `pi_config_created=False`/cleanup NOT_REQUIRED, and a
# RUNTIME_SESSION_MISMATCH refusal (which happens only AFTER a session was
# returned) alongside `runtime_session_established=False`.
#
# All 13 negative counterexamples below reproduced against the pre-fix code.


# -- resource existence: the generated Pi config -----------------------------


def test_fu2d_counterexample_2_pi_config_created_false_while_its_gate_passed() -> None:
    pairs = dict(_passing_gate_status_pairs())
    with pytest.raises(ValueError, match="pi_config_created .* must equal"):
        _build_result(
            outcome=CategoryBOutcome.INFRASTRUCTURE_REFUSAL,
            failed_gate=CategoryBGateName.EVIDENCE_SAFETY,
            failure_code=CategoryBFailureCode.EVIDENCE_SCRUB_REFUSED,
            pi_config_created=False,
            cleanup=CleanupStatus(attempted=False, scrub_verified=None, classification=None),
            evidence=CategoryBEvidence._refused(("safety_context_unprovable",)),
            _gate_status_pairs=tuple(
                sorted(
                    {
                        **pairs,
                        CategoryBGateName.GENERATED_CONFIG_CLEANUP.value: "NOT_REQUIRED",
                        CategoryBGateName.EVIDENCE_SAFETY.value: (
                            f"FAILED:{CategoryBFailureCode.EVIDENCE_SCRUB_REFUSED.value}"
                        ),
                    }.items()
                )
            ),
        )


def test_fu2d_counterexample_3_pi_config_created_true_while_its_gate_not_reached() -> None:
    with pytest.raises(ValueError, match="pi_config_created .* must equal"):
        _reachable_refusal(
            failed={
                CategoryBGateName.WORKSPACE_AUTHORITY: CategoryBFailureCode.WORKSPACE_AUTHORITY_UNVERIFIED
            },
            failed_gate=CategoryBGateName.WORKSPACE_AUTHORITY,
            failure_code=CategoryBFailureCode.WORKSPACE_AUTHORITY_UNVERIFIED,
            pi_config_created=True,
            cleanup=CleanupStatus(attempted=True, scrub_verified=True, classification=None),
        )


def test_fu2d_a_config_generation_pass_can_never_coexist_with_not_required_cleanup() -> None:
    """The composite the brief names explicitly: PI_CONFIG_GENERATION PASSED
    plus a NOT_REQUIRED generated-config cleanup is unreachable, because
    `pi_config_created` binds to BOTH (to the gate by FU2D, and to
    `cleanup.attempted` by FU2B)."""
    pairs = dict(_passing_gate_status_pairs())
    pairs[CategoryBGateName.GENERATED_CONFIG_CLEANUP.value] = "NOT_REQUIRED"
    with pytest.raises(ValueError):
        _build_result(
            cleanup=CleanupStatus(attempted=False, scrub_verified=None, classification=None),
            _gate_status_pairs=tuple(sorted(pairs.items())),
        )


# -- resource existence: runtime and broker sessions -------------------------


def _pass_pairs_with_closure(gate: CategoryBGateName, status) -> tuple:
    """The PASS baseline trace with ONE closure gate's recorded text swapped
    to match a substituted typed object -- so the FU2B typed-object equality
    binding (which would otherwise fire first) cannot mask the FU2D
    resource-existence check under test."""
    pairs = dict(_passing_gate_status_pairs())
    pairs[gate.value] = status.status_text
    return tuple(sorted(pairs.items()))


@pytest.mark.parametrize(
    "n, state, code",
    [
        (4, ResourceClosureState.CLOSED_BY_ORCHESTRATOR, None),
        (
            5,
            ResourceClosureState.SHUTDOWN_REFUSED_FOREIGN_SESSION,
            CategoryBFailureCode.RUNTIME_SHUTDOWN_REFUSED_FOREIGN_SESSION,
        ),
    ],
)
def test_fu2d_counterexamples_4_5_no_runtime_session_but_a_session_bearing_closure(
    n, state, code
) -> None:
    """A session-bearing closure state is unreachable when no session object
    was ever returned."""
    status = RuntimeTeardownStatus(state=state, failure_code=code)
    with pytest.raises(ValueError, match="returned a session|is not reachable when gate_statuses"):
        _build_result(
            runtime_session_established=False,
            runtime_teardown=status,
            _gate_status_pairs=_pass_pairs_with_closure(
                CategoryBGateName.RUNTIME_TEARDOWN, status
            ),
        )


def test_fu2d_counterexample_6_runtime_session_exists_but_authority_unavailable() -> None:
    """`SHUTDOWN_AUTHORITY_UNAVAILABLE` is returned from a branch ABOVE the
    session check -- unreachable once a session was returned."""
    status = RuntimeTeardownStatus(
        state=ResourceClosureState.SHUTDOWN_AUTHORITY_UNAVAILABLE,
        failure_code=CategoryBFailureCode.RUNTIME_TEARDOWN_AUTHORITY_UNAVAILABLE,
    )
    with pytest.raises(ValueError, match="is not reachable when gate_statuses"):
        _build_result(
            runtime_teardown=status,
            _gate_status_pairs=_pass_pairs_with_closure(
                CategoryBGateName.RUNTIME_TEARDOWN, status
            ),
        )


@pytest.mark.parametrize(
    "n, state, code",
    [
        (7, ResourceClosureState.CLOSED_BY_ORCHESTRATOR, None),
        (
            8,
            ResourceClosureState.SHUTDOWN_REFUSED_FOREIGN_SESSION,
            CategoryBFailureCode.BROKER_SHUTDOWN_REFUSED_FOREIGN_SESSION,
        ),
    ],
)
def test_fu2d_counterexamples_7_8_no_broker_session_but_a_session_bearing_closure(
    n, state, code
) -> None:
    status = BrokerShutdownStatus(state=state, failure_code=code)
    with pytest.raises(ValueError, match="returned a session|is not reachable when gate_statuses"):
        _build_result(
            broker_created=False,
            broker_shutdown=status,
            _gate_status_pairs=_pass_pairs_with_closure(
                CategoryBGateName.BROKER_SHUTDOWN, status
            ),
        )


def test_fu2d_counterexample_9_broker_session_exists_but_authority_unavailable() -> None:
    status = BrokerShutdownStatus(
        state=ResourceClosureState.SHUTDOWN_AUTHORITY_UNAVAILABLE,
        failure_code=CategoryBFailureCode.BROKER_SHUTDOWN_AUTHORITY_UNAVAILABLE,
    )
    with pytest.raises(ValueError, match="is not reachable when gate_statuses"):
        _build_result(
            broker_shutdown=status,
            _gate_status_pairs=_pass_pairs_with_closure(
                CategoryBGateName.BROKER_SHUTDOWN, status
            ),
        )


def test_fu2d_a_foreign_session_is_still_a_returned_session() -> None:
    """The distinction the brief insists on: refusing to act on a session is
    NOT the same fact as no session having been returned. A foreign runtime
    session yields `runtime_session_established=True`."""
    result = _reachable_refusal(
        failed={CategoryBGateName.RUNTIME_LAUNCH: CategoryBFailureCode.RUNTIME_SESSION_MISMATCH},
        failed_gate=CategoryBGateName.RUNTIME_LAUNCH,
        failure_code=CategoryBFailureCode.RUNTIME_SESSION_MISMATCH,
    )
    assert result.runtime_session_established is True
    assert result.runtime_teardown.state is ResourceClosureState.SHUTDOWN_REFUSED_FOREIGN_SESSION
    assert result.runtime_teardown.closure_satisfied is False


def test_fu2d_a_creator_retained_partial_resource_is_not_a_returned_session(
    run_workspace: QualificationRunWorkspace,
) -> None:
    """The OTHER half of the same distinction, end to end through the real
    controller: a broker whose creator kept ownership (``resource_created=True``
    but ``session=None``) means a physical resource may exist while
    `broker_created` is correctly False -- no `BrokerSession` ever crossed
    the boundary. The two facts must never be collapsed into one boolean."""
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"])
    harness.broker_returns_no_session = True
    harness.broker_resource_created = True
    harness.broker_cleanup_attempted = True
    harness.broker_reached_closed_on_partial = False
    result, harness = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.broker_created is False  # no session object crossed the boundary
    assert result.broker_shutdown.state is ResourceClosureState.CLOSED_BY_CREATOR_UNVERIFIED
    assert harness.count("shutdown_broker") == 0


def test_fu2d_session_authority_is_bound_in_both_directions() -> None:
    """A returned session is refused as foreign EXACTLY when its own gate
    recorded a session mismatch, and acted on EXACTLY when that gate PASSED."""
    # gate PASSED but closure claims the session was foreign
    foreign = RuntimeTeardownStatus(
        state=ResourceClosureState.SHUTDOWN_REFUSED_FOREIGN_SESSION,
        failure_code=CategoryBFailureCode.RUNTIME_SHUTDOWN_REFUSED_FOREIGN_SESSION,
    )
    with pytest.raises(ValueError, match="is not reachable when gate_statuses"):
        _build_result(
            outcome=CategoryBOutcome.INFRASTRUCTURE_REFUSAL,
            failed_gate=CategoryBGateName.RUNTIME_TEARDOWN,
            failure_code=CategoryBFailureCode.RUNTIME_SHUTDOWN_REFUSED_FOREIGN_SESSION,
            runtime_teardown=foreign,
            evidence=CategoryBEvidence._refused(("safety_context_unprovable",)),
            _gate_status_pairs=tuple(
                sorted(
                    {
                        **dict(_pass_pairs_with_closure(
                            CategoryBGateName.RUNTIME_TEARDOWN, foreign
                        )),
                        CategoryBGateName.EVIDENCE_SAFETY.value: (
                            f"FAILED:{CategoryBFailureCode.SAFETY_CONTEXT_UNPROVABLE.value}"
                        ),
                    }.items()
                )
            ),
        )
    # gate recorded a mismatch but closure claims AIDO acted on it
    with pytest.raises(ValueError, match="is not reachable when gate_statuses"):
        _reachable_refusal(
            failed={CategoryBGateName.RUNTIME_LAUNCH: CategoryBFailureCode.RUNTIME_SESSION_MISMATCH},
            failed_gate=CategoryBGateName.RUNTIME_LAUNCH,
            failure_code=CategoryBFailureCode.RUNTIME_SESSION_MISMATCH,
            runtime_teardown=RuntimeTeardownStatus(
                state=ResourceClosureState.CLOSED_BY_ORCHESTRATOR
            ),
        )


# -- gate-trace reachability --------------------------------------------------


def test_fu2d_counterexample_10_a_gate_reached_without_its_prerequisite() -> None:
    pairs = {g.value: "NOT_REACHED" for g in CategoryBGateName}
    pairs[CategoryBGateName.RUN_CORRELATION.value] = "PASSED"
    pairs[CategoryBGateName.ROUTE_DESCRIPTOR.value] = (
        f"FAILED:{CategoryBFailureCode.ROUTE_DESCRIPTOR_INVALID.value}"
    )
    for gate in (
        CategoryBGateName.RUNTIME_TEARDOWN,
        CategoryBGateName.BROKER_SHUTDOWN,
        CategoryBGateName.GENERATED_CONFIG_CLEANUP,
    ):
        pairs[gate.value] = "NOT_REQUIRED"
    pairs[CategoryBGateName.EVIDENCE_SAFETY.value] = (
        f"FAILED:{CategoryBFailureCode.SAFETY_CONTEXT_UNPROVABLE.value}"
    )
    with pytest.raises(ValueError, match="not a trace the controller could have produced"):
        CategoryBControllerResult(
            candidate="A", outcome=CategoryBOutcome.INFRASTRUCTURE_REFUSAL, semantic_prompts_sent=0,
            failed_gate=CategoryBGateName.ROUTE_DESCRIPTOR,
            failure_code=CategoryBFailureCode.ROUTE_DESCRIPTOR_INVALID,
            facts=_minimal_refusal_facts(), observed_pi_version=None,
            pi_config_created=False, broker_created=False, runtime_session_established=False,
            runtime_teardown=RuntimeTeardownStatus(state=ResourceClosureState.NOT_REQUIRED),
            broker_shutdown=BrokerShutdownStatus(state=ResourceClosureState.NOT_REQUIRED),
            cleanup=CleanupStatus(attempted=False, scrub_verified=None, classification=None),
            evidence=CategoryBEvidence._refused(("safety_context_unprovable",)),
            _gate_status_pairs=tuple(sorted(pairs.items())),
        )


def test_fu2d_counterexample_11_an_early_failure_with_a_later_gate_passed() -> None:
    with pytest.raises(ValueError, match="not a trace the controller could have produced"):
        _reachable_refusal(
            failed={
                CategoryBGateName.WORKSPACE_AUTHORITY: CategoryBFailureCode.WORKSPACE_AUTHORITY_UNVERIFIED
            },
            failed_gate=CategoryBGateName.WORKSPACE_AUTHORITY,
            failure_code=CategoryBFailureCode.WORKSPACE_AUTHORITY_UNVERIFIED,
            _gate_status_overrides={CategoryBGateName.ROUTE_CHECK.value: "PASSED"},
            fact_overrides={"exact_candidate_model_served": True},
        )


def test_fu2d_counterexample_12_h1_reports_a_verdict_after_get_commands_failed() -> None:
    for later in (
        CategoryBGateName.H1_EXTENSION_IDENTITY,
        CategoryBGateName.EXTENSION_COMMAND_NAMESPACE,
    ):
        with pytest.raises(ValueError, match="not a trace the controller could have produced"):
            _reachable_refusal(
                failed={CategoryBGateName.GET_COMMANDS: CategoryBFailureCode.GET_COMMANDS_FAILED},
                failed_gate=CategoryBGateName.GET_COMMANDS,
                failure_code=CategoryBFailureCode.GET_COMMANDS_FAILED,
                _gate_status_overrides={later.value: "PASSED"},
            )


def test_fu2d_counterexample_13_a_launch_fact_gate_reports_a_verdict_after_launch_failed() -> None:
    for gate in (
        CategoryBGateName.PI_VERSION_OBSERVED, CategoryBGateName.RPC_LAUNCH_SHAPE,
        CategoryBGateName.REQUIRED_LAUNCH_FLAGS, CategoryBGateName.LF_JSONL_CORRELATION,
    ):
        with pytest.raises(ValueError, match="not a trace the controller could have produced"):
            _reachable_refusal(
                failed={
                    CategoryBGateName.RUNTIME_LAUNCH: CategoryBFailureCode.RUNTIME_SESSION_MISMATCH
                },
                failed_gate=CategoryBGateName.RUNTIME_LAUNCH,
                failure_code=CategoryBFailureCode.RUNTIME_SESSION_MISMATCH,
                _gate_status_overrides={gate.value: "PASSED"},
            )


def test_fu2d_a_reached_prerequisite_makes_not_reached_impossible_too() -> None:
    """The OTHER direction of the biconditional: the controller's launch-fact
    loop sets all four gates together, so three NOT_REACHED beside one
    verdict never happened either."""
    with pytest.raises(ValueError, match="not a trace the controller could have produced"):
        _reachable_refusal(
            failed={
                CategoryBGateName.PI_VERSION_OBSERVED: CategoryBFailureCode.PI_VERSION_NOT_OBSERVED
            },
            failed_gate=CategoryBGateName.PI_VERSION_OBSERVED,
            failure_code=CategoryBFailureCode.PI_VERSION_NOT_OBSERVED,
            _gate_status_overrides={
                CategoryBGateName.RPC_LAUNCH_SHAPE.value: "NOT_REACHED",
                CategoryBGateName.REQUIRED_LAUNCH_FLAGS.value: "NOT_REACHED",
                CategoryBGateName.LF_JSONL_CORRELATION.value: "NOT_REACHED",
            },
        )


def test_fu2d_run_correlation_may_never_be_not_reached() -> None:
    """The one gate with an empty prerequisite: the controller always
    attempts it, so NOT_REACHED is not a state it can report."""
    with pytest.raises(ValueError, match="not a trace the controller could have produced"):
        _reachable_refusal(
            failed={
                CategoryBGateName.RUN_CORRELATION: CategoryBFailureCode.RUN_CORRELATION_UNAVAILABLE
            },
            failed_gate=CategoryBGateName.RUN_CORRELATION,
            failure_code=CategoryBFailureCode.RUN_CORRELATION_UNAVAILABLE,
            _gate_status_overrides={CategoryBGateName.RUN_CORRELATION.value: "NOT_REACHED"},
        )


def test_fu2d_the_prerequisite_table_matches_the_controllers_own_stage_order() -> None:
    """Structural: the table names exactly the compatibility gates, and every
    prerequisite is strictly earlier (also asserted at import time)."""
    table = i2b_controller_module._GATE_PREREQUISITES
    assert set(table) == set(COMPATIBILITY_GATES)
    for gate, prerequisites in table.items():
        for prerequisite in prerequisites:
            assert COMPATIBILITY_GATES.index(prerequisite) < COMPATIBILITY_GATES.index(gate)
    # the two intentional multi-fact observation groups share one prerequisite
    assert (
        table[CategoryBGateName.H1_EXTENSION_IDENTITY]
        == table[CategoryBGateName.EXTENSION_COMMAND_NAMESPACE]
        == (CategoryBGateName.GET_COMMANDS,)
    )
    for gate in (
        CategoryBGateName.PI_VERSION_OBSERVED, CategoryBGateName.RPC_LAUNCH_SHAPE,
        CategoryBGateName.REQUIRED_LAUNCH_FLAGS, CategoryBGateName.LF_JSONL_CORRELATION,
    ):
        assert table[gate] == (CategoryBGateName.RUNTIME_LAUNCH,)


# -- positive controls: the two intentional observation groups ---------------


def test_fu2d_counterexample_14_h1_and_namespace_may_both_fail_from_one_observation() -> None:
    """POSITIVE CONTROL: both facts come from ONE successful get_commands
    response, so both gates are reached and either or both may fail."""
    result = _reachable_refusal(
        failed={
            CategoryBGateName.H1_EXTENSION_IDENTITY: CategoryBFailureCode.H1_EXTENSION_IDENTITY_MISMATCH,
            CategoryBGateName.EXTENSION_COMMAND_NAMESPACE: CategoryBFailureCode.UNEXPECTED_CLI_EXTENSION_COMMAND,
        },
        failed_gate=CategoryBGateName.H1_EXTENSION_IDENTITY,
        failure_code=CategoryBFailureCode.H1_EXTENSION_IDENTITY_MISMATCH,
    )
    assert result.gate_statuses[CategoryBGateName.GET_COMMANDS.value] == "PASSED"
    for gate in (
        CategoryBGateName.H1_EXTENSION_IDENTITY,
        CategoryBGateName.EXTENSION_COMMAND_NAMESPACE,
    ):
        assert result.gate_statuses[gate.value].startswith("FAILED:")


def test_fu2d_one_launch_fact_may_fail_while_its_three_siblings_pass() -> None:
    """POSITIVE CONTROL: the four launch-fact gates are reached together and
    fail independently."""
    result = _reachable_refusal(
        failed={
            CategoryBGateName.REQUIRED_LAUNCH_FLAGS: CategoryBFailureCode.REQUIRED_LAUNCH_FLAGS_REJECTED
        },
        failed_gate=CategoryBGateName.REQUIRED_LAUNCH_FLAGS,
        failure_code=CategoryBFailureCode.REQUIRED_LAUNCH_FLAGS_REJECTED,
    )
    assert result.gate_statuses[CategoryBGateName.PI_VERSION_OBSERVED.value] == "PASSED"
    assert result.gate_statuses[CategoryBGateName.RPC_LAUNCH_SHAPE.value] == "PASSED"
    assert result.gate_statuses[CategoryBGateName.LF_JSONL_CORRELATION.value] == "PASSED"
    assert result.gate_statuses[CategoryBGateName.GET_COMMANDS.value] == "NOT_REACHED"


# -- the strongest proof: every REAL controller trace is accepted ------------


@pytest.mark.parametrize(
    "harness_kwargs",
    [
        {},  # the full pass
        {"broker_ready": False},
        {"broker_raises": True},
        {"broker_result_override": "not-an-observation"},
        {"broker_run_id_override": "some-other-run"},
        {"launch_raises": True},
        {"launch_returns_no_session": True},
        {"launch_session_run_id_override": "some-other-run"},
        {"launch_session_broker_id_override": "some-other-broker"},
        {"pi_version": None},
        {"launch_shape_valid": False},
        {"required_flags_accepted": False},
        {"lf_correlation": False},
        {"commands_call_succeeded": False},
        {"commands_shape_understood": False},
        {"commands_session_override": "rt-other"},
        {"h1_components": {"malformed_source_metadata": True}},
        {"state_call_succeeded": False},
        {"state_shape_understood": False},
        {"reported_provider": "someone-else"},
        {"protocol_violation": True},
        {"extension_error": True},
        {"route_reachable": False, "route_model_served": False},
        {"runtime_child_exited": False},
        {"broker_reached_closed": False},
        {"runtime_shutdown_raises": True},
        {"broker_shutdown_raises": True},
        {"runtime_shutdown_session_override": "rt-other"},
        {"broker_shutdown_session_id_override": "brk-other"},
    ],
)
def test_fu2d_every_real_controller_trace_is_accepted_by_the_new_validators(
    run_workspace: QualificationRunWorkspace, harness_kwargs: dict
) -> None:
    """The decisive check that the new rules are DERIVED from the source and
    not merely plausible: 29 distinct real controller runs -- every creation,
    observation, identity and teardown failure mode the harness can drive,
    plus the full pass -- must each construct their result cleanly.

    A rule that over-refuses shows up here immediately; a rule read correctly
    off the source cannot.
    """
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], **harness_kwargs)
    result, _ = _run(run_workspace, harness=harness)
    # construction already ran every FU2D validator; re-assert the headline
    # existence bindings explicitly too.
    assert result.pi_config_created == (
        result.gate_statuses[CategoryBGateName.PI_CONFIG_GENERATION.value] == "PASSED"
    )
    assert result.pi_config_created == result.cleanup.attempted
    assert result.runtime_session_established == (
        result.runtime_teardown.state in i2b_controller_module._SESSION_BEARING_CLOSURE_STATES
    )
    assert result.broker_created == (
        result.broker_shutdown.state in i2b_controller_module._SESSION_BEARING_CLOSURE_STATES
    )


def test_fu2d_second_review_bypass_creator_states_need_the_adapter_to_have_been_called() -> None:
    """Regression for the ONE additional bypass this phase's own second
    adversarial review found (not on the mandatory list).

    Binding the closure state only to "was a session returned" left the
    creator-retained and authority-unavailable RUNTIME states constructible
    on a trace where ``BROKER_SESSION`` failed -- i.e. where the launch
    adapter was never called at all, so `launch_attempted` is False and
    ``NOT_REQUIRED`` is the only state `_close_runtime` can return. Found by
    an exhaustive (closure state x existence boolean) sweep over three
    reachable traces.
    """
    for state, code in (
        (
            ResourceClosureState.SHUTDOWN_AUTHORITY_UNAVAILABLE,
            CategoryBFailureCode.RUNTIME_TEARDOWN_AUTHORITY_UNAVAILABLE,
        ),
        (
            ResourceClosureState.CLOSED_BY_CREATOR_UNVERIFIED,
            CategoryBFailureCode.CLOSED_BY_CREATOR_UNVERIFIED,
        ),
        (ResourceClosureState.CLOSED_BY_CREATOR_VERIFIED, None),
        (
            ResourceClosureState.PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT,
            CategoryBFailureCode.PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT,
        ),
    ):
        with pytest.raises(ValueError, match="is not reachable when gate_statuses"):
            _reachable_refusal(
                failed={
                    CategoryBGateName.BROKER_SESSION: CategoryBFailureCode.BROKER_SESSION_MISMATCH
                },
                failed_gate=CategoryBGateName.BROKER_SESSION,
                failure_code=CategoryBFailureCode.BROKER_SESSION_MISMATCH,
                runtime_teardown=RuntimeTeardownStatus(state=state, failure_code=code),
            )


def test_fu2d_not_required_is_reachable_from_a_launch_that_created_nothing() -> None:
    """The other side of that same map, and the over-refusal the
    real-controller sweep caught in an earlier draft:
    `_creator_retained_ownership_state` returns NOT_REQUIRED whenever the
    creator reports `resource_created=False`, so a RUNTIME_LAUNCH_FAILED
    trace legitimately admits FOUR states, not three."""
    reachable = i2b_controller_module._RUNTIME_LAUNCH_STATUS_TO_CLOSURE_STATES[
        f"FAILED:{CategoryBFailureCode.RUNTIME_LAUNCH_FAILED.value}"
    ]
    assert ResourceClosureState.NOT_REQUIRED in reachable
    assert len(reachable) == 4
    result = _reachable_refusal(
        failed={CategoryBGateName.RUNTIME_LAUNCH: CategoryBFailureCode.RUNTIME_LAUNCH_FAILED},
        failed_gate=CategoryBGateName.RUNTIME_LAUNCH,
        failure_code=CategoryBFailureCode.RUNTIME_LAUNCH_FAILED,
        runtime_teardown=RuntimeTeardownStatus(state=ResourceClosureState.NOT_REQUIRED),
    )
    assert result.runtime_session_established is False


def test_fu2d_status_to_closure_state_maps_cover_their_whole_vocabulary() -> None:
    """Structural: each map's keys are exactly NOT_REACHED, PASSED and one
    entry per failure code that gate's own producer can emit -- so a code
    added to one table without the other cannot fall through unconstrained
    (also asserted at import time)."""
    for gate, mapping in (
        (
            CategoryBGateName.RUNTIME_LAUNCH,
            i2b_controller_module._RUNTIME_LAUNCH_STATUS_TO_CLOSURE_STATES,
        ),
        (
            CategoryBGateName.BROKER_SESSION,
            i2b_controller_module._BROKER_SESSION_STATUS_TO_CLOSURE_STATES,
        ),
    ):
        expected = {"NOT_REACHED", "PASSED"} | {
            f"FAILED:{code}"
            for code in i2b_controller_module._COMPATIBILITY_GATE_ALLOWED_FAILURE_CODE_VALUES[
                gate.value
            ]
        }
        assert set(mapping) == expected
        for states in mapping.values():
            assert states, "every status must name at least one reachable closure state"


def test_fu2d_a_genuine_pass_still_constructs(
    run_workspace: QualificationRunWorkspace,
) -> None:
    result, _ = _run(run_workspace)
    assert result.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED
    assert result.pi_config_created is True
    assert result.broker_created is True
    assert result.runtime_session_established is True


def test_fu2d_dataclasses_replace_on_a_real_refusal_cannot_break_the_trace(
    run_workspace: QualificationRunWorkspace,
) -> None:
    """Second-adversarial-review sweep: mutate a GENUINE controller refusal
    field by field; every FU2D-bound field must refuse."""
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], broker_ready=False)
    result, _ = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    with pytest.raises(ValueError):
        dataclasses.replace(result, pi_config_created=False)
    with pytest.raises(ValueError):
        dataclasses.replace(result, broker_created=False)
    with pytest.raises(ValueError):
        dataclasses.replace(result, runtime_session_established=True)
    with pytest.raises(ValueError):
        dataclasses.replace(
            result,
            broker_shutdown=BrokerShutdownStatus(state=ResourceClosureState.NOT_REQUIRED),
        )


# -- 5F3B-I2B-FU2E: NOT_REACHED does not mean every fact may float -----------
#
# FU2D's fact-vs-gate binding skipped the check ENTIRELY whenever a fact's own
# gate read NOT_REACHED -- correct for the four LAUNCH facts (the one honest,
# already-accepted asymmetry), but far too broad for the other seven
# single-mapped facts, whose own gate and whose own observation are always set
# together, unconditionally, in the SAME block. The mandatory counterexamples
# below reproduce the exact bypass this phase closes: each constructs cleanly
# under the pre-FU2E validator (confirmed via a scratch reconstruction of the
# pre-fix module during this phase's own diagnostic pass) and must now be
# refused.


@pytest.mark.parametrize(
    "fact_name, failed_gate, failure_code",
    [
        (
            "get_commands_response_shape_understood",
            CategoryBGateName.RUN_CORRELATION,
            CategoryBFailureCode.RUN_CORRELATION_UNAVAILABLE,
        ),
        (
            "h1_extension_identity_matched",
            CategoryBGateName.RUN_CORRELATION,
            CategoryBFailureCode.RUN_CORRELATION_UNAVAILABLE,
        ),
        (
            "no_unexpected_extension_command_observed",
            CategoryBGateName.RUN_CORRELATION,
            CategoryBFailureCode.RUN_CORRELATION_UNAVAILABLE,
        ),
        (
            "exact_candidate_model_served",
            CategoryBGateName.RUN_CORRELATION,
            CategoryBFailureCode.RUN_CORRELATION_UNAVAILABLE,
        ),
        (
            "broker_reached_required_ready_state",
            CategoryBGateName.BROKER_SESSION,
            CategoryBFailureCode.BROKER_CREATION_FAILED,
        ),
        (
            "get_state_response_shape_understood",
            CategoryBGateName.GET_COMMANDS,
            CategoryBFailureCode.GET_COMMANDS_FAILED,
        ),
        (
            "h2_provider_model_identity_matched",
            CategoryBGateName.GET_COMMANDS,
            CategoryBFailureCode.GET_COMMANDS_FAILED,
        ),
    ],
)
def test_fu2e_blocker1_a_non_launch_fact_may_not_float_true_while_never_reached(
    fact_name: str, failed_gate: CategoryBGateName, failure_code: CategoryBFailureCode
) -> None:
    """Mandatory counterexamples 1-5: a non-launch fact claiming True while
    its OWN producing gate was NEVER REACHED (an EARLY prefix failure leaves
    it NOT_REACHED, never merely unchecked) must be refused -- exactly like a
    fact disagreeing with a gate that DID run already was.
    """
    own_gate = i2b_controller_module._SINGLE_FACT_TO_GATE[fact_name]
    with pytest.raises(ValueError, match="NOT_REACHED"):
        _reachable_refusal(
            failed={failed_gate: failure_code},
            failed_gate=failed_gate,
            failure_code=failure_code,
            fact_overrides={fact_name: True},
        )
    del own_gate  # documents which gate this fact is bound to; not asserted directly


def test_fu2e_blocker1_every_non_launch_single_mapped_fact_is_swept() -> None:
    """Structural: the sweep above names every one of the seven non-launch
    single-mapped facts at least once -- never a partial, hand-picked subset
    that happens to pass."""
    covered = {
        "get_commands_response_shape_understood",
        "h1_extension_identity_matched",
        "no_unexpected_extension_command_observed",
        "exact_candidate_model_served",
        "broker_reached_required_ready_state",
        "get_state_response_shape_understood",
        "h2_provider_model_identity_matched",
    }
    assert covered == set(i2b_controller_module._SINGLE_FACT_TO_GATE) - i2b_controller_module._LAUNCH_FACT_NAMES


@pytest.mark.parametrize(
    "failed_gate, failure_code, runtime_teardown_override",
    [
        (
            CategoryBGateName.BROKER_READY,
            CategoryBFailureCode.BROKER_NOT_READY,
            None,
        ),
        (
            CategoryBGateName.RUNTIME_LAUNCH,
            CategoryBFailureCode.RUNTIME_LAUNCH_REQUEST_UNCONSTRUCTIBLE,
            None,
        ),
        (
            CategoryBGateName.RUNTIME_LAUNCH,
            CategoryBFailureCode.ADAPTER_RAISED,
            RuntimeTeardownStatus(
                state=ResourceClosureState.SHUTDOWN_AUTHORITY_UNAVAILABLE,
                failure_code=CategoryBFailureCode.RUNTIME_TEARDOWN_AUTHORITY_UNAVAILABLE,
            ),
        ),
        (
            CategoryBGateName.RUNTIME_LAUNCH,
            CategoryBFailureCode.MALFORMED_ADAPTER_RESULT,
            RuntimeTeardownStatus(
                state=ResourceClosureState.SHUTDOWN_AUTHORITY_UNAVAILABLE,
                failure_code=CategoryBFailureCode.RUNTIME_TEARDOWN_AUTHORITY_UNAVAILABLE,
            ),
        ),
    ],
)
def test_fu2e_blocker2_launch_facts_may_not_float_true_without_a_valid_observation(
    failed_gate: CategoryBGateName,
    failure_code: CategoryBFailureCode,
    runtime_teardown_override: RuntimeTeardownStatus | None,
) -> None:
    """Mandatory counterexamples 4/7/8/9 (RUNTIME_LAUNCH's own NOT_REACHED
    case is covered by the BROKER_READY-failure trace, since RUNTIME_LAUNCH's
    sole prerequisite is BROKER_READY): none of these four RUNTIME_LAUNCH
    statuses ever reaches the `fact_values[...] = launch_observation....`
    assignment, so a launch fact claiming True on any of them is refused.

    ADAPTER_RAISED/MALFORMED_ADAPTER_RESULT need an explicit
    `SHUTDOWN_AUTHORITY_UNAVAILABLE` runtime_teardown override -- the DEFAULT
    trace-derived teardown (`NOT_REQUIRED`, correct for the other two codes)
    is not itself reachable for these two per FU2D's own
    `_RUNTIME_LAUNCH_STATUS_TO_CLOSURE_STATES` map, and that EARLIER check
    would otherwise mask the one this test isolates.
    """
    kwargs: dict = {}
    if runtime_teardown_override is not None:
        kwargs["runtime_teardown"] = runtime_teardown_override
    with pytest.raises(ValueError, match="no valid RuntimeLaunchObservation was ever obtained"):
        _reachable_refusal(
            failed={failed_gate: failure_code},
            failed_gate=failed_gate,
            failure_code=failure_code,
            fact_overrides={
                "pi_version_observed": True,
                "rpc_launch_shape_valid": True,
                "required_launch_flags_accepted": True,
                "lf_jsonl_correlation_succeeded": True,
            },
            **kwargs,
        )


def test_fu2e_blocker2_positive_control_runtime_launch_failed_with_valid_no_session_observation() -> None:
    """Mandatory counterexample 10 (POSITIVE): a valid RuntimeLaunchObservation
    with ``session=None`` (RUNTIME_LAUNCH_FAILED) still independently carries
    the four launch facts -- the real controller records `fact_values[...]`
    immediately after `_invoke` returns a non-None observation, strictly
    BEFORE it learns whether a session was returned at all. This is the
    corresponding positive control to
    `test_the_launch_facts_may_legitimately_be_true_while_not_reached`
    (RUNTIME_SESSION_MISMATCH), required so blocker 2's exception is proven
    on BOTH of its two reachable statuses, not just one.
    """
    result = _reachable_refusal(
        failed={CategoryBGateName.RUNTIME_LAUNCH: CategoryBFailureCode.RUNTIME_LAUNCH_FAILED},
        failed_gate=CategoryBGateName.RUNTIME_LAUNCH,
        failure_code=CategoryBFailureCode.RUNTIME_LAUNCH_FAILED,
        fact_overrides={
            "pi_version_observed": True,
            "rpc_launch_shape_valid": True,
            "required_launch_flags_accepted": True,
            "lf_jsonl_correlation_succeeded": True,
        },
        observed_pi_version="0.84.3",
    )
    assert result.outcome is CategoryBOutcome.INFRASTRUCTURE_REFUSAL
    for gate in (
        CategoryBGateName.PI_VERSION_OBSERVED, CategoryBGateName.RPC_LAUNCH_SHAPE,
        CategoryBGateName.REQUIRED_LAUNCH_FLAGS, CategoryBGateName.LF_JSONL_CORRELATION,
    ):
        assert result.gate_statuses[gate.value] == "NOT_REACHED"
    assert result.facts.pi_version_observed is True
    assert result.facts.lf_jsonl_correlation_succeeded is True
    # the OTHER accepted distinction: a valid observation with session=None
    # never crosses the runtime-session-established boundary, unlike a
    # foreign session (RUNTIME_SESSION_MISMATCH) that DID cross it.
    assert result.runtime_session_established is False
    assert result.runtime_teardown.state is ResourceClosureState.NOT_REQUIRED


# -- 5F3B-I2B-FU2E blocker 3: PROTOCOL_INTEGRITY failure-code/fact mapping ---


def test_fu2e_blocker3_not_reached_pins_both_protocol_facts_false() -> None:
    """Mandatory counterexample 6: PROTOCOL_INTEGRITY NOT_REACHED (an earlier
    GET_STATE failure) with either protocol fact True must be refused."""
    for fact_name in ("no_protocol_violation_observed", "no_extension_error_observed"):
        with pytest.raises(ValueError, match="no valid ProtocolObservation was ever consumed"):
            _reachable_refusal(
                failed={CategoryBGateName.GET_STATE: CategoryBFailureCode.GET_STATE_FAILED},
                failed_gate=CategoryBGateName.GET_STATE,
                failure_code=CategoryBFailureCode.GET_STATE_FAILED,
                fact_overrides={fact_name: True},
            )


def test_fu2e_blocker3_session_mismatch_pins_both_protocol_facts_false() -> None:
    """The other pre-observation PROTOCOL_INTEGRITY failure: a session-id
    mismatch happens BEFORE the `else` branch that populates either fact, so
    both must remain False even though the gate itself is FAILED, not
    NOT_REACHED."""
    with pytest.raises(ValueError, match="no valid ProtocolObservation was ever consumed"):
        _reachable_refusal(
            failed={
                CategoryBGateName.PROTOCOL_INTEGRITY: CategoryBFailureCode.RUNTIME_SESSION_MISMATCH
            },
            failed_gate=CategoryBGateName.PROTOCOL_INTEGRITY,
            failure_code=CategoryBFailureCode.RUNTIME_SESSION_MISMATCH,
            fact_overrides={"no_protocol_violation_observed": True},
        )


def test_fu2e_blocker3_counterexample_12_protocol_violation_pins_only_its_own_fact() -> None:
    """Mandatory counterexample 12: claiming
    `no_protocol_violation_observed=True` alongside
    FAILED:PROTOCOL_VIOLATION_OBSERVED must be refused -- the real controller
    only ever reaches that failure code when the raw observation's
    `protocol_violation_observed` was True, i.e. the fact is always False on
    that branch. (The pair used here -- no_pv=True, no_ee=False -- is the
    brief's own example of what the real controller would instead classify as
    EXTENSION_ERROR_OBSERVED.)
    """
    with pytest.raises(
        ValueError, match="FAILED:PROTOCOL_VIOLATION_OBSERVED, so facts.no_protocol_violation_observed must be False"
    ):
        _reachable_refusal(
            failed={
                CategoryBGateName.PROTOCOL_INTEGRITY: CategoryBFailureCode.PROTOCOL_VIOLATION_OBSERVED
            },
            failed_gate=CategoryBGateName.PROTOCOL_INTEGRITY,
            failure_code=CategoryBFailureCode.PROTOCOL_VIOLATION_OBSERVED,
            fact_overrides={
                "no_protocol_violation_observed": True,
                "no_extension_error_observed": False,
            },
        )


def test_fu2e_blocker3_protocol_violation_precedence_leaves_the_other_fact_free() -> None:
    """POSITIVE CONTROL: protocol violation has precedence when BOTH were
    observed, so FAILED:PROTOCOL_VIOLATION_OBSERVED with
    no_extension_error_observed=False (an extension error was ALSO present,
    just not the one reported) must still construct."""
    result = _reachable_refusal(
        failed={
            CategoryBGateName.PROTOCOL_INTEGRITY: CategoryBFailureCode.PROTOCOL_VIOLATION_OBSERVED
        },
        failed_gate=CategoryBGateName.PROTOCOL_INTEGRITY,
        failure_code=CategoryBFailureCode.PROTOCOL_VIOLATION_OBSERVED,
        fact_overrides={
            "no_protocol_violation_observed": False,
            "no_extension_error_observed": False,
        },
    )
    assert result.facts.no_protocol_violation_observed is False
    assert result.facts.no_extension_error_observed is False


def test_fu2e_blocker3_counterexample_13_extension_error_pins_both_facts_exactly() -> None:
    """Mandatory counterexample 13: FAILED:EXTENSION_ERROR_OBSERVED is only
    ever reached (the real controller's `elif`) when
    `protocol_violation_observed=False` and `extension_error_observed=True`,
    i.e. no_protocol_violation_observed=True and no_extension_error_observed
    =False, always. Any other pair is refused."""
    with pytest.raises(
        ValueError,
        match="FAILED:EXTENSION_ERROR_OBSERVED, so facts.no_protocol_violation_observed must be True",
    ):
        _reachable_refusal(
            failed={
                CategoryBGateName.PROTOCOL_INTEGRITY: CategoryBFailureCode.EXTENSION_ERROR_OBSERVED
            },
            failed_gate=CategoryBGateName.PROTOCOL_INTEGRITY,
            failure_code=CategoryBFailureCode.EXTENSION_ERROR_OBSERVED,
            fact_overrides={
                "no_protocol_violation_observed": False,
                "no_extension_error_observed": True,
            },
        )


def test_fu2e_blocker3_passed_still_requires_both_facts_true() -> None:
    """POSITIVE/NEGATIVE pairing for the PASSED branch: still requires the
    conjunction (unchanged from FU2D), now reached via the exact-match branch
    rather than the old bare conjunction-vs-passed comparison."""
    with pytest.raises(ValueError, match="protocol_integrity"):
        _reachable_refusal(
            failed={
                CategoryBGateName.ROUTE_CHECK: CategoryBFailureCode.ROUTE_CHECK_FAILED
            },
            failed_gate=CategoryBGateName.ROUTE_CHECK,
            failure_code=CategoryBFailureCode.ROUTE_CHECK_FAILED,
            fact_overrides={
                "no_protocol_violation_observed": True,
                "no_extension_error_observed": False,
            },
        )


# -- 5F3B-I2B-FU2E: terminal evidence state closure ---------------------------


def test_fu2e_counterexample_14_a_terminal_result_may_not_carry_the_not_yet_built_sentinel() -> None:
    """Mandatory counterexample 14: `CategoryBEvidence()`'s bare, no-argument
    constructor produces a safe INTERMEDIATE placeholder
    (`scrub_findings == ("evidence_not_yet_built",)`) that is legitimate to
    construct in isolation but is never a shape `run_category_b_controller`
    itself returns (every real path calls `_refused` or
    `_build_from_payload`). A terminal `CategoryBControllerResult` carrying it
    must be refused.
    """
    bare_evidence = CategoryBEvidence()
    assert bare_evidence.scrub_findings == ("evidence_not_yet_built",)
    assert bare_evidence.retention_ready is False
    with pytest.raises(ValueError, match="evidence_not_yet_built"):
        _reachable_refusal(
            failed={
                CategoryBGateName.RUN_CORRELATION: CategoryBFailureCode.RUN_CORRELATION_UNAVAILABLE
            },
            failed_gate=CategoryBGateName.RUN_CORRELATION,
            failure_code=CategoryBFailureCode.RUN_CORRELATION_UNAVAILABLE,
            evidence=bare_evidence,
        )


def test_fu2e_a_real_refusal_still_carries_a_real_evidence_body_never_the_sentinel(
    run_workspace: QualificationRunWorkspace,
) -> None:
    """End-to-end: a genuine controller refusal's evidence is always built via
    `_refused` with a real finding code, never the bare sentinel."""
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], broker_ready=False)
    result, _ = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    assert result.evidence.scrub_findings != ("evidence_not_yet_built",)


def test_fu2e_second_adversarial_sweep_dataclasses_replace_cannot_reintroduce_the_sentinel(
    run_workspace: QualificationRunWorkspace,
) -> None:
    """Second-adversarial-review-style sweep: mutating a genuine PASS's
    evidence to the bare sentinel via `dataclasses.replace` must be refused,
    exactly like every other FU2D/FU2E-bound field already is."""
    result, _ = _run(run_workspace)
    assert result.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED
    with pytest.raises(ValueError):
        dataclasses.replace(result, evidence=CategoryBEvidence())


# -- 5F3B-I2B-FU2E: every REAL controller refusal trace still constructs -----


@pytest.mark.parametrize(
    "harness_kwargs",
    [
        {"broker_ready": False},
        {"launch_returns_no_session": True},
        {"launch_session_run_id_override": "some-other-run"},
        {"protocol_violation": True},
        {"extension_error": True},
        {"pi_version": None},
    ],
)
def test_fu2e_real_controller_refusal_traces_are_not_over_refused(
    run_workspace: QualificationRunWorkspace, harness_kwargs: dict
) -> None:
    """The decisive proof that FU2E's tighter rules do not over-refuse a
    GENUINE controller run: every real refusal mode the four launch facts and
    the two protocol facts can be involved in must still construct cleanly.
    """
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], **harness_kwargs)
    result, _ = _run(run_workspace, harness=harness)
    _assert_refusal(result)


# =============================================================================
# 5F3B-I2B-FU2F -- evidence-safety failure attribution closure
# =============================================================================
#
# FU2E closed the gate-vs-fact binding, but a narrower gap survived: the
# CURRENT test suite still accepted
# `gate_statuses['evidence_safety'] = FAILED:EVIDENCE_SCRUB_REFUSED` paired
# with `evidence = CategoryBEvidence._refused(("safety_context_unprovable",))`
# -- a trace `run_category_b_controller` can never produce, since that
# `_refused` shape is EXCLUSIVELY the safety-context-unprovable branch's own
# output and the controller's two `_fail(EVIDENCE_SAFETY, ...)` call sites
# each correspond to a DIFFERENT, mutually exclusive evidence-construction
# path. `CategoryBEvidence` now stamps its own construction origin
# (`_origin`: "refused" via `_refused`, "built" via `_build_from_payload`,
# "unbuilt" for the untouched bare-constructor default), and
# `CategoryBControllerResult` binds `EVIDENCE_SAFETY`'s failure code to that
# origin directly, mirroring how the three lifecycle-closure gates are already
# bound to their own typed objects' `status_text`.


def _genuine_safety_context_unprovable_evidence() -> CategoryBEvidence:
    """The REAL shape `run_category_b_controller`'s only `_refused(...)` call
    site ever produces -- never a monkeypatch, never a hand-picked finding
    code."""
    return CategoryBEvidence._refused(
        i2b_controller_module._SAFETY_CONTEXT_UNPROVABLE_REFUSAL
    )


def _genuine_scrub_refusal_evidence() -> CategoryBEvidence:
    """A REAL, non-retention-ready `_build_from_payload` evidence body -- the
    same real, unmodified `qualification_scrub_check` path
    `test_retention_ready_true_is_only_reachable_by_actually_scrubbing_the_
    payload` already uses to prove a genuine dirty verdict, never a
    monkeypatch and never the safety-context-unprovable shape."""
    safety = ArtifactSafetyContext(api_key="sk-should-be-caught")
    evidence = CategoryBEvidence._build_from_payload({"note": "sk-should-be-caught"}, safety)
    assert evidence.retention_ready is False
    assert evidence._origin == i2b_controller_module._EVIDENCE_ORIGIN_BUILT
    return evidence


def _evidence_safety_result(
    *, evidence: CategoryBEvidence, evidence_safety_status: str
) -> CategoryBControllerResult:
    """Every OTHER gate PASSED/closed; only `EVIDENCE_SAFETY` (and, when
    non-PASSED, `failed_gate`/`failure_code`) varies -- isolates exactly the
    evidence-origin/failure-code binding this phase adds, the same pattern
    `test_fu2c_evidence_safety_alone_failing_may_be_failed_gate` already
    uses.
    """
    pairs = dict(_passing_gate_status_pairs())
    pairs[CategoryBGateName.EVIDENCE_SAFETY.value] = evidence_safety_status
    passed = evidence_safety_status == "PASSED"
    failure_code = (
        None
        if passed
        else CategoryBFailureCode(evidence_safety_status[len("FAILED:"):])
    )
    return CategoryBControllerResult(
        candidate="A",
        outcome=(
            CategoryBOutcome.CATEGORY_B_GATE_PASSED
            if passed
            else CategoryBOutcome.INFRASTRUCTURE_REFUSAL
        ),
        semantic_prompts_sent=0,
        failed_gate=None if passed else CategoryBGateName.EVIDENCE_SAFETY,
        failure_code=failure_code,
        facts=_passing_facts(),
        observed_pi_version="0.84.3",
        pi_config_created=True,
        broker_created=True,
        runtime_session_established=True,
        runtime_teardown=RuntimeTeardownStatus(state=ResourceClosureState.CLOSED_BY_ORCHESTRATOR),
        broker_shutdown=BrokerShutdownStatus(state=ResourceClosureState.CLOSED_BY_ORCHESTRATOR),
        cleanup=CleanupStatus(attempted=True, scrub_verified=True, classification=None),
        evidence=evidence,
        _gate_status_pairs=tuple(sorted(pairs.items())),
    )


def test_fu2f_current_counterexample_evidence_scrub_refused_plus_safety_context_unprovable_evidence_is_refused() -> None:
    """The CURRENT REPRODUCED COUNTEREXAMPLE from the brief, closed directly:
    `EVIDENCE_SCRUB_REFUSED` paired with the real safety-context-unprovable
    `_refused(...)` shape is not a trace the controller can produce."""
    with pytest.raises(ValueError, match="CategoryBEvidence._refused"):
        _evidence_safety_result(
            evidence=_genuine_safety_context_unprovable_evidence(),
            evidence_safety_status=f"FAILED:{CategoryBFailureCode.EVIDENCE_SCRUB_REFUSED.value}",
        )


def test_fu2f_mandatory_counterexample_2_safety_context_unprovable_plus_real_scrub_refusal_is_refused() -> None:
    """Mandatory counterexample 2: the SYMMETRIC bypass the brief asked to
    determine the reachability of -- `SAFETY_CONTEXT_UNPROVABLE` paired with
    a REAL dirty `_build_from_payload` body. This one was NOT explicitly
    named as "the current counterexample" but the old bare
    `evidence.retention_ready`-only check accepted it too (confirmed against
    the pre-fix predicate during this phase's own diagnostic pass); it is now
    refused on the same footing as counterexample 1.
    """
    with pytest.raises(ValueError, match="CategoryBEvidence._build_from_payload"):
        _evidence_safety_result(
            evidence=_genuine_scrub_refusal_evidence(),
            evidence_safety_status=f"FAILED:{CategoryBFailureCode.SAFETY_CONTEXT_UNPROVABLE.value}",
        )


def test_fu2f_mandatory_counterexample_3_evidence_scrub_refused_plus_bare_evidence_remains_refused() -> None:
    """Mandatory counterexample 3: `EVIDENCE_SCRUB_REFUSED` paired with the
    bare, never-built `CategoryBEvidence()` placeholder remains refused --
    not by THIS phase's new origin binding (which deliberately leaves the
    "unbuilt" origin unconstrained at that specific checkpoint), but by
    FU2E's own, UNCHANGED terminal `evidence_not_yet_built` sentinel check,
    exactly as FU2E left it.
    """
    with pytest.raises(ValueError, match="evidence_not_yet_built"):
        _evidence_safety_result(
            evidence=CategoryBEvidence(),
            evidence_safety_status=f"FAILED:{CategoryBFailureCode.EVIDENCE_SCRUB_REFUSED.value}",
        )


def test_fu2f_mandatory_counterexample_4_real_safety_context_unprovable_path_still_constructs(
    run_workspace: QualificationRunWorkspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mandatory counterexample 4: the REAL controller's safety-context-
    unprovable path, end to end, still constructs -- and now also carries the
    correct construction origin."""

    def _refuse(**_kwargs):
        raise i2b_controller_module.CategoryBSafetyContextError("SYNTHETIC")

    monkeypatch.setattr(i2b_controller_module, "build_run_safety_context", _refuse)
    result, _ = _run(run_workspace)
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.EVIDENCE_SAFETY
    assert result.failure_code is CategoryBFailureCode.SAFETY_CONTEXT_UNPROVABLE
    assert result.evidence._origin == i2b_controller_module._EVIDENCE_ORIGIN_REFUSED
    assert result.evidence.scrub_findings == i2b_controller_module._SAFETY_CONTEXT_UNPROVABLE_REFUSAL


def test_fu2f_mandatory_counterexample_5_real_scrub_refusal_path_still_constructs(
    run_workspace: QualificationRunWorkspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mandatory counterexample 5: force the REAL qualification scrub result
    dirty via a safe synthetic double (not a real secret, not a real
    endpoint) and verify the real controller's scrub-refusal path, end to
    end, still constructs -- and now also carries the correct construction
    origin."""

    def _dirty(_payload, _safety):
        return {"scrub_checked": True, "findings": ["synthetic_finding"], "clean": False}

    monkeypatch.setattr(i2b_controller_module, "qualification_scrub_check", _dirty)
    result, _ = _run(run_workspace)
    _assert_refusal(result)
    assert result.failed_gate is CategoryBGateName.EVIDENCE_SAFETY
    assert result.failure_code is CategoryBFailureCode.EVIDENCE_SCRUB_REFUSED
    assert result.evidence._origin == i2b_controller_module._EVIDENCE_ORIGIN_BUILT
    assert result.evidence.retention_ready is False


# -- MALFORMED_ADAPTER_RESULT: provably unreachable, and now refused if hand-built --


def test_fu2f_malformed_adapter_result_is_no_longer_an_accepted_evidence_safety_code() -> None:
    """The defensive `_fail(EVIDENCE_SAFETY, MALFORMED_ADAPTER_RESULT)` call
    site (guarding `outcome is INFRASTRUCTURE_REFUSAL and failed_gate is
    None`) is PROVABLY UNREACHABLE: EVIDENCE_SAFETY is unconditionally
    resolved to PASSED or one of the two real codes on every path before
    that guard runs, and `provisional_pass=False` always traces back, through
    `_GATE_PREREQUISITES`, to an earlier genuine `_fail` call (RUN_CORRELATION
    is never NOT_REACHED). `MALFORMED_ADAPTER_RESULT` is therefore no longer
    part of EVIDENCE_SAFETY's accepted terminal vocabulary at all -- neither
    evidence origin may claim it, so if the dead defensive line ever fires
    due to a future regression, result construction itself raises loudly.
    """
    for evidence in (
        _genuine_safety_context_unprovable_evidence(),
        _genuine_scrub_refusal_evidence(),
    ):
        with pytest.raises(ValueError):
            _evidence_safety_result(
                evidence=evidence,
                evidence_safety_status=f"FAILED:{CategoryBFailureCode.MALFORMED_ADAPTER_RESULT.value}",
            )


def test_fu2f_malformed_adapter_result_remains_valid_for_other_gates() -> None:
    """Scope check: `MALFORMED_ADAPTER_RESULT` is removed ONLY from
    EVIDENCE_SAFETY's vocabulary -- it remains a real, reachable code for
    RUNTIME_LAUNCH/BROKER_SESSION/GET_COMMANDS/GET_STATE/PROTOCOL_INTEGRITY,
    exactly as FU2B established. This phase does not touch those."""
    for gate in (
        CategoryBGateName.RUNTIME_LAUNCH,
        CategoryBGateName.BROKER_SESSION,
        CategoryBGateName.GET_COMMANDS,
        CategoryBGateName.GET_STATE,
        CategoryBGateName.PROTOCOL_INTEGRITY,
    ):
        assert (
            CategoryBFailureCode.MALFORMED_ADAPTER_RESULT.value
            in i2b_controller_module._COMPATIBILITY_GATE_ALLOWED_FAILURE_CODE_VALUES[gate.value]
        )


# -- second adversarial review: exhaustive cross-swap sweep -------------------


def test_fu2f_second_adversarial_review_cross_swap_sweep() -> None:
    """Cross-swap EVERY individually-valid NON-retention-ready evidence-
    construction shape against EVERY reachable EVIDENCE_SAFETY status text.
    No pair `run_category_b_controller` cannot produce may construct; every
    pair it CAN produce must.

    The retention-ready (``PASSED``) shape is deliberately swept elsewhere
    (`test_fu2d_a_genuine_pass_still_constructs`,
    `test_fu2f_mandatory_counterexample_4/5_...`) rather than hand-built here
    -- a genuinely retention-ready evidence body must also describe THIS
    exact result's own candidate/facts/gate-statuses
    (`_require_evidence_describes_this_result`, unchanged and unrelated to
    this phase), so a hand-built PASSED case here would trip THAT binding
    instead of the one under test.
    """
    refused = _genuine_safety_context_unprovable_evidence()
    built_dirty = _genuine_scrub_refusal_evidence()
    bare = CategoryBEvidence()

    statuses = (
        "PASSED",
        f"FAILED:{CategoryBFailureCode.SAFETY_CONTEXT_UNPROVABLE.value}",
        f"FAILED:{CategoryBFailureCode.EVIDENCE_SCRUB_REFUSED.value}",
        f"FAILED:{CategoryBFailureCode.MALFORMED_ADAPTER_RESULT.value}",
    )
    # (evidence, status) -> whether this is the ONE reachable pairing for it
    reachable = {
        (id(refused), f"FAILED:{CategoryBFailureCode.SAFETY_CONTEXT_UNPROVABLE.value}"),
        (id(built_dirty), f"FAILED:{CategoryBFailureCode.EVIDENCE_SCRUB_REFUSED.value}"),
    }
    for evidence in (refused, built_dirty, bare):
        for status in statuses:
            should_construct = (id(evidence), status) in reachable
            if evidence is bare:
                # every pairing with the bare/unbuilt placeholder is refused,
                # by FU2E's own unchanged sentinel check -- never reachable.
                should_construct = False
            if should_construct:
                result = _evidence_safety_result(
                    evidence=evidence, evidence_safety_status=status
                )
                assert result.evidence is evidence
            else:
                with pytest.raises(ValueError):
                    _evidence_safety_result(evidence=evidence, evidence_safety_status=status)


def test_fu2f_dataclasses_replace_cannot_swap_in_the_wrong_evidence_origin(
    run_workspace: QualificationRunWorkspace,
) -> None:
    """Second-adversarial-review sweep, end to end: mutate a GENUINE
    controller refusal's evidence to the OTHER origin's shape via
    `dataclasses.replace`; both directions are refused."""
    harness = _Harness(model_id=CANDIDATE_MODEL_IDS["A"], broker_ready=False)
    result, _ = _run(run_workspace, harness=harness)
    _assert_refusal(result)
    with pytest.raises(ValueError):
        dataclasses.replace(
            result, evidence=_genuine_safety_context_unprovable_evidence()
        )
    with pytest.raises(ValueError):
        dataclasses.replace(result, evidence=_genuine_scrub_refusal_evidence())


def test_fu2f_dataclasses_replace_cannot_swap_evidence_into_a_genuine_pass(
    second_run_workspace: QualificationRunWorkspace,
) -> None:
    """The same property, on the OTHER genuine shape: a real PASS's
    retention-ready evidence cannot be replaced with either non-retention-
    ready origin via `dataclasses.replace`."""
    passing, _ = _run(second_run_workspace)
    assert passing.outcome is CategoryBOutcome.CATEGORY_B_GATE_PASSED
    with pytest.raises(ValueError):
        dataclasses.replace(passing, evidence=_genuine_scrub_refusal_evidence())
    with pytest.raises(ValueError):
        dataclasses.replace(
            passing, evidence=_genuine_safety_context_unprovable_evidence()
        )


def test_fu2f_evidence_origin_is_not_a_finding_code_taxonomy() -> None:
    """Structural: `_origin` names exactly three construction paths, never a
    scrub finding code -- it must never satisfy the bounded finding-code
    pattern this module's OTHER, genuinely-scrub-derived codes use, so a
    future reader cannot mistake it for a fourth entry in that vocabulary."""
    assert i2b_controller_module._EVIDENCE_ORIGINS == {"unbuilt", "refused", "built"}
    for origin in i2b_controller_module._EVIDENCE_ORIGINS:
        assert origin not in (
            "safety_context_unprovable",
            "evidence_not_yet_built",
        )
