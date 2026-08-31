"""5F3B-I2B-L1 -- offline adapter-contract tests for the real live adapters.

**OFFLINE ONLY.** No test in this module launches a real Node/Pi process,
opens a real Windows named pipe, opens a real socket, or reads a real
credential. The two real-I/O primitives ``qualification.i2b_live_adapters``
depends on -- ``ar2.supervisor.PiRpcSupervisor`` (a real subprocess) and
``ar2.broker.BrokerServer`` (a real named-pipe thread) -- are replaced here
with synthetic doubles that implement exactly the public surface the adapter
module calls, matching this package's own established "synthetic doubles /
injected callback" discipline. Pi's identity is a fixed synthetic
:class:`~ar2.launch.RuntimeIdentity` injected at ``LiveCategoryBAdapters``
construction, never a real ``pi --version`` subprocess probe.

What is proven here: fact derivation from a real (synthetic-transport)
launch/get_commands/get_state/protocol observation; the creator
partial-failure contract on a broker-start failure (L1 BLOCKER 1) and on a
runtime launch/correlation-probe failure (BLOCKER 2), with every cleanup
attempt guarded against its own exception (BLOCKER 3); that
``launch_runtime`` refuses any broker session it did not itself mint, field
for field (BLOCKER 4); that every RPC-reported boolean/list is projected
fail-closed rather than coerced by truthiness (BLOCKER 5); that the real
non-secret preflight producers are genuine and ordered before the credential
read (BLOCKER 6); foreign/unregistered-session refusal on every
session-consuming adapter method; that ``route_checker`` is passed to the
frozen controller's exact expected call shape unmodified; and that no
semantic-prompt capability is reachable from this module's source.
"""

from __future__ import annotations

import ast
import inspect
import io
import json
import os
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from ar2.broker import (
    STATE_CLOSED,
    STATE_CREATED,
    STATE_DRAINING,
    STATE_READY,
    STATE_TEARDOWN_INCOMPLETE,
)
from ar2.launch import LaunchIdentityError, RuntimeIdentity
from ar2.pi_config import SENTINEL_COMMAND_NAME
from ar2.pi_config import TOOL_ALLOWLIST as AR2_TOOL_ALLOWLIST
from ar2.launch import build_pi_argv
from ar2.protocol import BoundedStreamState, RecordStreamReader
from ar2.supervisor import (
    RUNTIME_DEADLINE_EXPIRED,
    RUNTIME_EVENT_CAP_EXCEEDED,
    RUNTIME_EXITED_EARLY,
    RUNTIME_LAUNCH_FAILED,
    RUNTIME_OUTPUT_CAP_EXCEEDED,
    RUNTIME_PROTOCOL_VIOLATION,
    RUNTIME_READ_ERROR,
    RUNTIME_RESPONSE_RECEIVED,
    RUNTIME_SETTLED,
    PiRpcSupervisor,
    PiSupervisorError,
)

#: 5F3B-I2B-L1-LF1. What the FROZEN ``ar2.protocol.RecordStreamReader``
#: actually assigns to ``protocol_violation`` when it observes one: a
#: message STRING, never a bool. Tests modelling an observed violation use
#: this; tests modelling "no violation" leave the double's field at ``None``.
_SYNTHETIC_VIOLATION_MESSAGE = "protocol violation: a stdout record was not strict JSON"

#: The genuine, unmodified ``build_pi_argv``, captured before any test
#: monkeypatches the adapter module's reference to it.
_real_build_pi_argv = build_pi_argv

import qualification.i2b_live_adapters as live_module
from qualification.i2_credentials import (
    InfrastructureRefusal,
    PreflightGateResult,
    resolve_connection_after_preflight,
)
from qualification.i2_environment import build_child_environment
from qualification.i2_identity import CREDENTIAL_ENV_VAR_NAME
from qualification.i2_pi_config import write_qualification_pi_config
from qualification.i2_route import route_descriptor_for_candidate
from qualification.i2_secret_context import build_secret_context
from qualification.i2b_live_adapters import (
    LiveAdapterError,
    LiveCategoryBAdapters,
    preflight_artifact_safety_scrub_self_check,
    preflight_candidate_route_generator_symmetry,
    preflight_child_environment_builder_self_check,
    preflight_config_generator_no_credential_literal_path,
    preflight_config_generator_self_check,
    preflight_environment_forbidden_fragment_audit,
    preflight_pi_installed_offline,
    preflight_planned_cli_argv_shape,
)
from qualification.i2b_controller import (
    CategoryBFailureCode,
    CategoryBGateName,
    run_category_b_controller,
)
from qualification.i2b_session import (
    BrokerCreationRequest,
    BrokerSession,
    RuntimeLaunchRequest,
    RuntimeSession,
)
from qualification.i2b_workspace import (
    QualificationRunWorkspace,
    claim_run_workspace,
    mint_qualification_run_workspace,
    remove_run_workspace,
)

SYNTHETIC_BASE_URL = "https://b300-proxy.example.invalid:8443/v1"
SYNTHETIC_API_KEY = "sk-synthetic-i2b-live-adapter-0001"


# -- workspace fixture -----------------------------------------------------


@pytest.fixture
def run_workspace():
    workspace = mint_qualification_run_workspace()
    try:
        yield workspace
    finally:
        remove_run_workspace(workspace)


@pytest.fixture
def second_run_workspace():
    workspace = mint_qualification_run_workspace()
    try:
        yield workspace
    finally:
        remove_run_workspace(workspace)


def _claimed(workspace: QualificationRunWorkspace, run_id: str) -> QualificationRunWorkspace:
    claim_run_workspace(workspace, run_id=run_id)
    return workspace


def _build_launch_request(
    workspace: QualificationRunWorkspace,
    *,
    run_id: str,
    broker_session: BrokerSession,
    candidate: str = "A",
) -> RuntimeLaunchRequest:
    """Build a ``RuntimeLaunchRequest``. The caller is responsible for
    claiming ``workspace`` for ``run_id`` exactly once, BEFORE calling this
    (claiming twice raises ``RUN_WORKSPACE_ALREADY_CLAIMED``) -- typically
    already done by minting the broker session through
    :func:`_launch_request_with_registered_broker`.
    """
    descriptor = route_descriptor_for_candidate(candidate)
    secret_context = build_secret_context(
        base_url=SYNTHETIC_BASE_URL, api_key=SYNTHETIC_API_KEY, model_id=descriptor.model_id
    )
    generated_config = write_qualification_pi_config(
        workspace.experiment_root, model_id=descriptor.model_id, base_url=SYNTHETIC_BASE_URL
    )
    launch_environment = build_child_environment(
        ambient_environ={"SystemRoot": r"C:\Windows"},
        node_executable=r"C:\synthetic\node.exe",
        generated_config=generated_config,
        secret_context=secret_context,
    )
    return RuntimeLaunchRequest(
        run_id=run_id,
        broker_session=broker_session,
        launch_environment=launch_environment,
        workspace=workspace,
        provider_id=descriptor.provider_id,
        model_id=descriptor.model_id,
    )


def _launch_request_with_registered_broker(
    adapters: LiveCategoryBAdapters,
    workspace: QualificationRunWorkspace,
    *,
    run_id: str,
    candidate: str = "A",
) -> RuntimeLaunchRequest:
    """Claim the workspace once, mint a REAL broker session through THIS
    adapter instance, and build a launch request bound to it.

    Never a standalone, unregistered ``BrokerSession`` -- BLOCKER 4
    requires ``launch_runtime`` to refuse any broker session this adapter
    instance did not itself mint, so every ordinary (non-adversarial)
    launch test must present the genuine minted session.
    """
    _claimed(workspace, run_id)
    broker_observation = adapters.create_broker(
        BrokerCreationRequest(run_id=run_id, workspace=workspace)
    )
    assert broker_observation.session is not None
    assert broker_observation.session.reached_ready is True
    return _build_launch_request(
        workspace, run_id=run_id, broker_session=broker_observation.session, candidate=candidate
    )


def _unregistered_ready_broker_session(*, run_id: str) -> BrokerSession:
    """A structurally valid, ``reached_ready=True`` ``BrokerSession`` this
    adapter instance never minted -- exactly what BLOCKER 4's refusal tests
    need."""
    return BrokerSession(
        run_id=run_id,
        session_id="brk-synthetic-0001",
        pipe_name=r"\\.\pipe\synthetic-0001",
        capability_id="cap-synthetic-0001",
        broker_token="tok-synthetic-0001",
        reached_ready=True,
    )


SYNTHETIC_IDENTITY = RuntimeIdentity(
    node_executable=r"C:\synthetic\node.exe",
    pi_cli_js=r"C:\synthetic\pi\dist\cli.js",
    pi_package_root=r"C:\synthetic\pi",
    reported_version="0.84.3",
    launch_shape="node_direct",
)


# -- synthetic transport doubles --------------------------------------------


class _FakeSupervisor:
    """Drop-in double for ``ar2.supervisor.PiRpcSupervisor``. No real process."""

    def __init__(self, *, argv, cwd, environment, bounds):
        self.argv = argv
        self.cwd = cwd
        self.environment = environment
        self.bounds = bounds
        self.launch_calls = 0
        self.launch_raises: Exception | None = None
        #: When True and ``launch_raises`` is set, ``self.process`` is
        #: assigned (mimicking a real ``subprocess.Popen`` that succeeded)
        #: BEFORE the exception is raised -- models BLOCKER 2's "launch()
        #: raised after Popen succeeded" scenario. When False, ``process``
        #: stays ``None``, modelling a pure ``Popen`` failure.
        self.launch_process_assigned_before_raise = False
        self.process: object | None = None
        self.sent: list[dict] = []
        self.send_raises: Exception | None = None
        self.responses: dict[str, tuple[str, dict | None]] = {}
        #: 5F3B-I2B-L1-LF1 ROOT CAUSE. This used to default to ``False``, a
        #: ``bool``, which is NOT the contract the real class publishes:
        #: ``ar2.protocol.RecordStreamReader.protocol_violation`` is declared
        #: ``str | None``, initialised to ``None``, and only ever assigned a
        #: violation MESSAGE string, which ``PiRpcSupervisor.stdout_state()``
        #: republishes verbatim. Because this double disagreed with the real
        #: class, the whole offline suite validated the adapter against a
        #: type the adapter would never actually see, and an adapter check
        #: that was UNSATISFIABLE against real state passed here for free.
        #: The default is now ``None`` -- "no protocol violation observed" --
        #: exactly as the real reader starts. A test modelling an observed
        #: violation assigns a MESSAGE STRING; a test modelling malformed,
        #: out-of-contract state assigns some other type (a ``bool``
        #: included, which is now itself out of contract).
        self._protocol_violation: object | None = None
        #: 5F3B-I2B-L1-LF1-FU1. The bounded startup-diagnostic surface the
        #: corrected required-flag classification consults -- modelled on the
        #: exact mapping the real ``PiRpcSupervisor.stderr_snapshot()``
        #: publishes (``captured``/``bytes_seen``/``bytes_retained``/
        #: ``cap_exceeded``/``eof``/``read_error``/``text_tail``, with
        #: ``read_error`` typed ``str | None`` exactly as
        #: ``BoundedStreamState.error`` is). The default models a clean,
        #: complete, EMPTY stderr, so no test accidentally inherits an
        #: unknown-option observation. ``stderr_text`` is the one knob most
        #: tests set; ``bytes_seen``/``bytes_retained`` follow it unless a
        #: test deliberately overrides them to model truncation.
        self.stderr_captured: object = True
        self.stderr_text: str = ""
        self.stderr_cap_exceeded: object = False
        self.stderr_eof: bool = True
        self.stderr_read_error: object = None
        self.stderr_bytes_seen_override: int | None = None
        self.stderr_bytes_retained_override: int | None = None
        self.stderr_snapshot_raises: Exception | None = None
        self.stderr_snapshot_result_override: object = None
        self.stderr_snapshot_calls = 0
        self.activity = SimpleNamespace(extension_errors=[])
        self.shutdown_calls = 0
        self.shutdown_result: dict = {"exit_status_observed": 0}
        self.shutdown_raises: Exception | None = None

    def launch(self) -> None:
        self.launch_calls += 1
        if self.launch_raises is not None:
            if self.launch_process_assigned_before_raise:
                self.process = object()
            raise self.launch_raises
        self.process = object()

    def send_command(self, command: dict) -> None:
        if self.send_raises is not None:
            raise self.send_raises
        self.sent.append(command)

    def await_response(self, command_id: str, *, timeout_seconds: float):
        return self.responses.get(command_id, (RUNTIME_DEADLINE_EXPIRED, None))

    def stderr_snapshot(self) -> dict:
        self.stderr_snapshot_calls += 1
        if self.stderr_snapshot_raises is not None:
            raise self.stderr_snapshot_raises
        if self.stderr_snapshot_result_override is not None:
            return self.stderr_snapshot_result_override  # type: ignore[return-value]
        encoded = len(self.stderr_text.encode("utf-8"))
        return {
            "captured": self.stderr_captured,
            "bytes_seen": (
                encoded
                if self.stderr_bytes_seen_override is None
                else self.stderr_bytes_seen_override
            ),
            "bytes_retained": (
                encoded
                if self.stderr_bytes_retained_override is None
                else self.stderr_bytes_retained_override
            ),
            "cap_exceeded": self.stderr_cap_exceeded,
            "eof": self.stderr_eof,
            "read_error": self.stderr_read_error,
            "text_tail": self.stderr_text,
        }

    def stdout_state(self) -> dict:
        return {
            "bytes_seen": 0,
            "records_ingested": 0,
            "byte_cap_exceeded": False,
            "event_cap_exceeded": False,
            "protocol_violation": self._protocol_violation,
            "read_error": False,
            "eof": False,
        }

    def shutdown(self) -> dict:
        self.shutdown_calls += 1
        if self.shutdown_raises is not None:
            raise self.shutdown_raises
        return dict(self.shutdown_result)


class _FakeBrokerServer:
    """Drop-in double for ``ar2.broker.BrokerServer``. No real thread/pipe.

    ``state_after_start_raise`` is kept only as NARRATIVE labelling of which
    real partial-start point a given test models -- it never drives adapter
    behaviour. The real ``BrokerServer.state`` reads ``STATE_CREATED`` for
    EVERY pre-READY failure ``start()`` can raise from (``STATE_READY`` is
    only reached deep inside the worker thread, strictly later than any
    exception ``start()`` itself can propagate), which is exactly why the
    adapter never branches on ``server.state`` at all.

    **5F3B-I2B-L1-D1 / FU3 BLOCKER 1.** The ONE fact the adapter's
    partial-start branch reads is the real class's public, monotonic
    ``pipe_resource_created``, modelled here by
    ``pipe_resource_created_after_start_raise``: the real ``start()`` sets
    it ``True`` immediately after ``create_first_instance_pipe`` returns and
    never resets it, so a pipe-creation failure leaves it ``False`` while
    every later partial-start failure point leaves it ``True``. A successful
    ``start()`` always leaves it ``True``.
    """

    def __init__(self, handler):
        self.handler = handler
        self.pipe_name = r"\\.\pipe\aido-i2b-synthetic-fake"
        self._state = STATE_CREATED
        self.start_calls = 0
        self.start_raises: Exception | None = None
        self.state_after_start_raise = STATE_CREATED
        #: What D1's monotonic public fact reads after ``start()`` raised.
        #: Defaults to True (a resource WAS created); only the
        #: pipe-creation-failure case sets it False.
        self.pipe_resource_created_after_start_raise = True
        self.pipe_resource_created = False
        self.shutdown_calls = 0
        self.shutdown_state_reached = STATE_CLOSED
        self.shutdown_raises: Exception | None = None

    @property
    def state(self) -> str:
        return self._state

    def start(self, *, ready_deadline_seconds: float = 5.0) -> None:
        self.start_calls += 1
        if self.start_raises is not None:
            self._state = self.state_after_start_raise
            self.pipe_resource_created = self.pipe_resource_created_after_start_raise
            raise self.start_raises
        self.pipe_resource_created = True
        self._state = STATE_READY

    def shutdown(self, trigger: str) -> dict:
        self.shutdown_calls += 1
        if self.shutdown_raises is not None:
            raise self.shutdown_raises
        self._state = self.shutdown_state_reached
        return {"state_reached": self.shutdown_state_reached, "shutdown_trigger": trigger}


@pytest.fixture
def patched(monkeypatch: pytest.MonkeyPatch):
    """Patch the two real-I/O classes, return handles.

    Also binds the RuntimeIdentity-authority trusted resolvers (BLOCKER 1,
    RuntimeIdentity variant) to :data:`SYNTHETIC_IDENTITY`'s own paths, so
    every ordinary (non-adversarial) ``_adapters()`` construction in this
    suite -- which always injects ``SYNTHETIC_IDENTITY`` by default --
    passes the same mechanical binding check a real live attempt would
    face, without depending on whether Node/Pi happen to be installed on
    the machine running this offline suite.
    """
    fake_supervisors: list[_FakeSupervisor] = []

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        fake_supervisors.append(s)
        return s

    fake_servers: list[_FakeBrokerServer] = []

    def _make_server(handler):
        s = _FakeBrokerServer(handler)
        fake_servers.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    monkeypatch.setattr(live_module, "BrokerServer", _make_server)
    monkeypatch.setattr(
        live_module, "_ar2_resolve_node_executable", lambda: SYNTHETIC_IDENTITY.node_executable
    )
    monkeypatch.setattr(
        live_module, "_ar2_resolve_pi_package_root", lambda: SYNTHETIC_IDENTITY.pi_package_root
    )
    return SimpleNamespace(supervisors=fake_supervisors, servers=fake_servers)


def _issued(identity: RuntimeIdentity = SYNTHETIC_IDENTITY):
    """Mint a genuine :class:`IssuedRuntimeIdentity` for one attempt.

    FU3 BLOCKER 2: ``LiveCategoryBAdapters`` no longer accepts a bare
    ``RuntimeIdentity`` -- only an issuance minted by the same trusted
    operation that runs the one real ``--version`` probe. This offline suite
    never runs that probe, so it uses the module-internal issuance function
    directly (the established test-only internal-access precedent this
    package already uses for ``i2_issuance``'s own registry). Every call
    returns a FRESH issuance, because an issuance is one-shot.
    """
    return live_module._issue_runtime_identity(identity)


def _adapters(**overrides) -> LiveCategoryBAdapters:
    kwargs = dict(
        environ_reader=lambda name: {
            "AIDO_LITELLM_BASE_URL": SYNTHETIC_BASE_URL,
            "AIDO_LITELLM_API_KEY": SYNTHETIC_API_KEY,
        }.get(name),
        runtime_identity=_issued(),
    )
    kwargs.update(overrides)
    return LiveCategoryBAdapters(**kwargs)


# -- construction --------------------------------------------------------


def test_constructor_requires_a_real_runtime_identity() -> None:
    with pytest.raises(LiveAdapterError):
        _adapters(runtime_identity="not-a-runtime-identity")


def test_constructor_rejects_none_runtime_identity() -> None:
    with pytest.raises(LiveAdapterError):
        _adapters(runtime_identity=None)


# -- read_connection ---------------------------------------------------------


def test_read_connection_uses_only_the_injected_reader(patched) -> None:
    calls = []

    def reader(name):
        calls.append(name)
        return {
            "AIDO_LITELLM_BASE_URL": SYNTHETIC_BASE_URL,
            "AIDO_LITELLM_API_KEY": SYNTHETIC_API_KEY,
        }.get(name)

    adapters = _adapters(environ_reader=reader)
    values = adapters.read_connection()
    assert values.base_url == SYNTHETIC_BASE_URL
    assert values.api_key == SYNTHETIC_API_KEY
    assert set(calls) == {"AIDO_LITELLM_BASE_URL", "AIDO_LITELLM_API_KEY"}


# -- create_broker / shutdown_broker -----------------------------------------


def test_create_broker_happy_path_reaches_ready(run_workspace, patched) -> None:
    adapters = _adapters()
    request = BrokerCreationRequest(run_id="run-0001", workspace=_claimed(run_workspace, "run-0001"))
    observation = adapters.create_broker(request)
    assert observation.session is not None
    assert observation.session.run_id == "run-0001"
    assert observation.session.reached_ready is True
    assert observation.start_attempted is True
    assert observation.resource_created is True
    assert patched.servers[0].start_calls == 1


# -- FU3 BLOCKER 1: the D1 broker partial-start fact ------------------------
#
# Every test below drives the adapter through ONE ``BrokerServer.start()``
# failure and asserts the observation is derived from D1's public, monotonic
# ``pipe_resource_created`` alone. The five mandated states are modelled
# exactly as the real class produces them:
#
#   A  pipe creation itself failed         pipe_resource_created False
#   B  pipe exists, event creation failed  pipe_resource_created True
#   C  Thread construction failed          pipe_resource_created True
#   D  Thread.start() failed               pipe_resource_created True
#   E  worker started, READY deadline      pipe_resource_created True
#
# Before FU3 the adapter reported ``resource_created=True`` and called
# ``shutdown()`` for ALL FIVE, because the pre-D1 public surface could not
# tell A apart from B-E. The pre-fix reproduction of that untruthful A is
# ``test_pre_fix_repro_state_a_would_have_claimed_a_resource_and_cleaned_it``.


def _server_factory(patched, monkeypatch, **attributes):
    """Install a ``_FakeBrokerServer`` factory carrying ``attributes``."""

    def _make_server(handler):
        server = _FakeBrokerServer(handler)
        for name, value in attributes.items():
            setattr(server, name, value)
        patched.servers.append(server)
        return server

    monkeypatch.setattr(live_module, "BrokerServer", _make_server)
    return _make_server


def _create_broker(adapters, run_workspace, run_id):
    return adapters.create_broker(
        BrokerCreationRequest(run_id=run_id, workspace=_claimed(run_workspace, run_id))
    )


def test_create_broker_state_a_pipe_creation_failed_reports_nothing_created(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D1 state A: ``create_first_instance_pipe`` raised before returning, so
    ``pipe_resource_created`` is False and no broker OS resource ever
    existed. The adapter must report the frozen "nothing created" row
    exactly, and must call ``shutdown()`` ZERO times -- a cleanup issued
    purely to keep the two branches uniform would be an untrue
    ``cleanup_attempted=True``."""
    _server_factory(
        patched,
        monkeypatch,
        start_raises=OSError("synthetic pipe creation failure"),
        pipe_resource_created_after_start_raise=False,
    )
    adapters = _adapters()
    observation = _create_broker(adapters, run_workspace, "run-0002a")

    assert observation.session is None
    assert observation.start_attempted is True
    assert observation.resource_created is False
    assert observation.cleanup_attempted is False
    assert observation.reached_closed is None
    assert observation.cleanup_verified_success is False
    assert patched.servers[0].shutdown_calls == 0


def test_pre_fix_repro_state_a_would_have_claimed_a_resource_and_cleaned_it(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The FU2 behaviour this follow-up removes, stated as an explicit
    non-regression: in state A the adapter used to report
    ``resource_created=True``/``cleanup_attempted=True`` and issue one
    ``shutdown()`` against a broker that had created nothing. Both claims
    were untrue, and neither may come back."""
    _server_factory(
        patched,
        monkeypatch,
        start_raises=OSError("synthetic pipe creation failure"),
        pipe_resource_created_after_start_raise=False,
    )
    adapters = _adapters()
    observation = _create_broker(adapters, run_workspace, "run-0002a2")

    assert observation.resource_created is not True
    assert observation.cleanup_attempted is not True
    assert patched.servers[0].shutdown_calls != 1


def test_create_broker_state_a_never_consults_server_state(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Adversarial: a server left in a state that LOOKS like a live broker
    must not change the answer -- ``pipe_resource_created`` is the only fact
    read, never ``state`` and never the exception."""
    _server_factory(
        patched,
        monkeypatch,
        start_raises=RuntimeError("synthetic failure with a misleading state"),
        state_after_start_raise=STATE_READY,
        pipe_resource_created_after_start_raise=False,
    )
    adapters = _adapters()
    observation = _create_broker(adapters, run_workspace, "run-0002a3")

    assert observation.resource_created is False
    assert observation.cleanup_attempted is False
    assert patched.servers[0].shutdown_calls == 0


def test_create_broker_state_b_pipe_exists_event_creation_failed_self_closes(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D1 state B: the pipe was created, shutdown-event creation then failed.
    Creator ownership never left ``BrokerServer``, so exactly ONE supported
    ``shutdown(TRIGGER_AIDO_TEARDOWN)`` runs, and D1's no-worker branch --
    which closes only the handles it created itself -- can genuinely reach
    ``STATE_CLOSED``. That postcondition is consumed truthfully."""
    _server_factory(
        patched,
        monkeypatch,
        start_raises=OSError("synthetic shutdown-event creation failure"),
        pipe_resource_created_after_start_raise=True,
        shutdown_state_reached=STATE_CLOSED,
    )
    adapters = _adapters()
    observation = _create_broker(adapters, run_workspace, "run-0002b")

    assert observation.session is None
    assert observation.start_attempted is True
    assert observation.resource_created is True
    assert observation.cleanup_attempted is True
    assert observation.reached_closed is True
    assert observation.cleanup_verified_success is True
    assert patched.servers[0].shutdown_calls == 1


def test_create_broker_state_b_shutdown_cannot_verify_closed_is_reported_truthfully(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same state B, but D1's own handle close did not succeed, so it
    reports ``TEARDOWN_INCOMPLETE``. Cleanup WAS attempted; the
    postcondition is honestly unverified -- never a fabricated success."""
    _server_factory(
        patched,
        monkeypatch,
        start_raises=OSError("synthetic shutdown-event creation failure"),
        pipe_resource_created_after_start_raise=True,
        shutdown_state_reached=STATE_TEARDOWN_INCOMPLETE,
    )
    adapters = _adapters()
    observation = _create_broker(adapters, run_workspace, "run-0002b2")

    assert observation.resource_created is True
    assert observation.cleanup_attempted is True
    assert observation.reached_closed is False
    assert observation.cleanup_verified_success is False
    assert patched.servers[0].shutdown_calls == 1


def test_create_broker_state_c_thread_construction_failed_self_closes(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D1 state C: ``threading.Thread(...)`` construction raised. Same
    creator-owned semantics as B."""
    _server_factory(
        patched,
        monkeypatch,
        start_raises=RuntimeError("synthetic thread construction failure"),
        pipe_resource_created_after_start_raise=True,
        shutdown_state_reached=STATE_CLOSED,
    )
    adapters = _adapters()
    observation = _create_broker(adapters, run_workspace, "run-0002c")

    assert observation.session is None
    assert observation.resource_created is True
    assert observation.cleanup_attempted is True
    assert observation.reached_closed is True
    assert patched.servers[0].shutdown_calls == 1


def test_create_broker_state_d_thread_start_failed_self_closes(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D1 state D: ``Thread.start()`` itself raised. ``self._thread`` is
    assigned but no worker ever ran, and D1's own shutdown must never join
    it. Same creator-owned semantics."""
    _server_factory(
        patched,
        monkeypatch,
        start_raises=RuntimeError("synthetic thread start failure"),
        pipe_resource_created_after_start_raise=True,
        shutdown_state_reached=STATE_CLOSED,
    )
    adapters = _adapters()
    observation = _create_broker(adapters, run_workspace, "run-0002d")

    assert observation.session is None
    assert observation.resource_created is True
    assert observation.cleanup_attempted is True
    assert observation.reached_closed is True
    assert patched.servers[0].shutdown_calls == 1


def test_create_broker_state_e_ready_deadline_failed_self_closes(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D1 state E: the worker DID start and never signalled READY. The
    worker-owned teardown ladder runs, and its result is consumed
    truthfully -- never a trusted session."""
    _server_factory(
        patched,
        monkeypatch,
        start_raises=TimeoutError("synthetic READY-deadline failure"),
        state_after_start_raise=STATE_DRAINING,  # narrative: a worker WAS running
        pipe_resource_created_after_start_raise=True,
        shutdown_state_reached=STATE_CLOSED,
    )
    adapters = _adapters()
    observation = _create_broker(adapters, run_workspace, "run-0003")

    assert observation.session is None
    assert observation.resource_created is True
    assert observation.cleanup_attempted is True
    assert observation.reached_closed is True
    assert observation.cleanup_verified_success is True
    assert patched.servers[0].shutdown_calls == 1


def test_create_broker_state_e_worker_owned_teardown_incomplete_is_not_success(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """State E where the worker did not terminate within D1's deadline:
    ``TEARDOWN_INCOMPLETE`` is not verified closure."""
    _server_factory(
        patched,
        monkeypatch,
        start_raises=TimeoutError("synthetic READY-deadline failure"),
        state_after_start_raise=STATE_DRAINING,
        pipe_resource_created_after_start_raise=True,
        shutdown_state_reached=STATE_TEARDOWN_INCOMPLETE,
    )
    adapters = _adapters()
    observation = _create_broker(adapters, run_workspace, "run-0003b")

    assert observation.cleanup_attempted is True
    assert observation.reached_closed is False
    assert observation.cleanup_verified_success is False


@pytest.mark.parametrize(
    ("label", "start_error", "state_after"),
    [
        ("B", OSError("synthetic shutdown-event creation failure"), STATE_CREATED),
        ("C", RuntimeError("synthetic thread construction failure"), STATE_CREATED),
        ("D", RuntimeError("synthetic thread start failure"), STATE_CREATED),
        ("E", TimeoutError("synthetic READY-deadline failure"), STATE_DRAINING),
    ],
)
def test_create_broker_creator_owned_shutdown_itself_raising_never_escapes(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch, label, start_error, state_after
) -> None:
    """BLOCKER 3, for every creator-owned D1 state: the ONE bounded cleanup
    attempt raising must never escape the adapter and must never mask the
    primary start failure. It is reported as an unverified postcondition."""
    _server_factory(
        patched,
        monkeypatch,
        start_raises=start_error,
        state_after_start_raise=state_after,
        pipe_resource_created_after_start_raise=True,
        shutdown_raises=RuntimeError("synthetic shutdown failure"),
    )
    adapters = _adapters()
    observation = _create_broker(adapters, run_workspace, "run-0002x" + label)

    assert observation.session is None
    assert observation.start_attempted is True
    assert observation.resource_created is True
    assert observation.cleanup_attempted is True
    assert observation.reached_closed is False
    assert observation.cleanup_verified_success is False
    assert patched.servers[0].shutdown_calls == 1


def test_create_broker_state_a_shutdown_is_never_called_so_it_can_never_raise(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """State A pairs with a raising ``shutdown()`` harmlessly, because
    ``shutdown()`` is never reached at all."""
    _server_factory(
        patched,
        monkeypatch,
        start_raises=OSError("synthetic pipe creation failure"),
        pipe_resource_created_after_start_raise=False,
        shutdown_raises=RuntimeError("synthetic shutdown failure"),
    )
    adapters = _adapters()
    observation = _create_broker(adapters, run_workspace, "run-0002a4")

    assert observation.resource_created is False
    assert observation.cleanup_attempted is False
    assert patched.servers[0].shutdown_calls == 0


@pytest.mark.parametrize("bogus", ["False", 0, None, [], object()])
def test_create_broker_non_bool_pipe_fact_fails_closed_into_cleanup(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch, bogus
) -> None:
    """A value that is not EXACTLY the ``False`` singleton is never read as
    "nothing was created" -- the frozen D1 surface cannot produce one, and
    if it somehow did, the safe direction is still to attempt the one
    bounded cleanup."""
    _server_factory(
        patched,
        monkeypatch,
        start_raises=OSError("synthetic start failure"),
        pipe_resource_created_after_start_raise=bogus,
        shutdown_state_reached=STATE_CLOSED,
    )
    adapters = _adapters()
    observation = _create_broker(adapters, run_workspace, "run-0002y")

    assert observation.resource_created is True
    assert observation.cleanup_attempted is True
    assert patched.servers[0].shutdown_calls == 1


def test_create_broker_unreadable_pipe_fact_fails_closed_into_cleanup(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unreadable fact is never "nothing was created" either."""

    class _RaisingFactServer(_FakeBrokerServer):
        @property
        def pipe_resource_created(self):
            raise RuntimeError("synthetic unreadable partial-start fact")

        @pipe_resource_created.setter
        def pipe_resource_created(self, value):
            return

    def _make_server(handler):
        server = _RaisingFactServer(handler)
        server.start_raises = OSError("synthetic start failure")
        server.shutdown_state_reached = STATE_CLOSED
        patched.servers.append(server)
        return server

    monkeypatch.setattr(live_module, "BrokerServer", _make_server)
    adapters = _adapters()
    observation = _create_broker(adapters, run_workspace, "run-0002z")

    assert observation.resource_created is True
    assert observation.cleanup_attempted is True
    assert patched.servers[0].shutdown_calls == 1


def test_create_broker_reads_only_the_public_d1_fact_in_its_failure_path() -> None:
    """Source-level: the partial-start branch names ``pipe_resource_created``
    and NEVER a private broker field or ``state``."""
    source = inspect.getsource(live_module._broker_reports_pipe_resource_created)
    partial = inspect.getsource(
        live_module.LiveCategoryBAdapters._retain_and_close_partial_broker
    )
    executable = source.split('"""')[-1] + partial.split('"""')[-1]
    assert "pipe_resource_created" in source
    for forbidden in ("_pipe_handle", "_thread", "_worker_thread_started", ".state"):
        assert forbidden not in executable


def test_shutdown_broker_refuses_a_session_it_did_not_create(run_workspace, patched) -> None:
    adapters = _adapters()
    foreign = BrokerSession(
        run_id="run-0004",
        session_id="brk-foreign-0001",
        pipe_name=r"\\.\pipe\foreign",
        capability_id="cap-foreign",
        broker_token="tok-foreign",
        reached_ready=True,
    )
    with pytest.raises(LiveAdapterError, match="not created by this adapter instance"):
        adapters.shutdown_broker(foreign)


def test_shutdown_broker_closes_the_exact_session_it_created(run_workspace, patched) -> None:
    adapters = _adapters()
    request = BrokerCreationRequest(run_id="run-0005", workspace=_claimed(run_workspace, "run-0005"))
    observation = adapters.create_broker(request)
    result = adapters.shutdown_broker(observation.session)
    assert result.session_id == observation.session.session_id
    assert result.reached_closed is True
    assert patched.servers[0].shutdown_calls == 1


# -- launch_runtime: BLOCKER 4, broker-session pinning -----------------------


def test_launch_runtime_refuses_a_broker_session_from_another_adapter_instance(
    run_workspace, second_run_workspace, patched
) -> None:
    other_adapters = _adapters()
    broker = other_adapters.create_broker(
        BrokerCreationRequest(run_id="run-4001", workspace=_claimed(second_run_workspace, "run-4001"))
    ).session

    adapters = _adapters()
    _claimed(run_workspace, "run-4001")
    request = _build_launch_request(run_workspace, run_id="run-4001", broker_session=broker)
    with pytest.raises(LiveAdapterError, match="not created by this adapter instance"):
        adapters.launch_runtime(request)


def test_launch_runtime_refuses_same_run_id_foreign_session_id(run_workspace, patched) -> None:
    adapters = _adapters()
    _claimed(run_workspace, "run-4002")
    foreign = _unregistered_ready_broker_session(run_id="run-4002")
    request = _build_launch_request(run_workspace, run_id="run-4002", broker_session=foreign)
    with pytest.raises(LiveAdapterError, match="not created by this adapter instance"):
        adapters.launch_runtime(request)


def _substituted_broker_session(genuine: BrokerSession, **overrides) -> BrokerSession:
    fields = dict(
        run_id=genuine.run_id,
        session_id=genuine.session_id,
        pipe_name=genuine.pipe_name,
        capability_id=genuine.capability_id,
        broker_token=genuine.broker_token,
        reached_ready=genuine.reached_ready,
    )
    fields.update(overrides)
    return BrokerSession(**fields)


def test_launch_runtime_refuses_substituted_pipe_name(run_workspace, patched) -> None:
    adapters = _adapters()
    _claimed(run_workspace, "run-4003")
    genuine = adapters.create_broker(
        BrokerCreationRequest(run_id="run-4003", workspace=run_workspace)
    ).session
    substituted = _substituted_broker_session(genuine, pipe_name=r"\\.\pipe\substituted")
    request = _build_launch_request(run_workspace, run_id="run-4003", broker_session=substituted)
    with pytest.raises(LiveAdapterError, match="does not match the exact authority"):
        adapters.launch_runtime(request)


def test_launch_runtime_refuses_substituted_capability_id(run_workspace, patched) -> None:
    adapters = _adapters()
    _claimed(run_workspace, "run-4004")
    genuine = adapters.create_broker(
        BrokerCreationRequest(run_id="run-4004", workspace=run_workspace)
    ).session
    substituted = _substituted_broker_session(genuine, capability_id="cap-substituted")
    request = _build_launch_request(run_workspace, run_id="run-4004", broker_session=substituted)
    with pytest.raises(LiveAdapterError, match="does not match the exact authority"):
        adapters.launch_runtime(request)


def test_launch_runtime_refuses_substituted_broker_token(run_workspace, patched) -> None:
    adapters = _adapters()
    _claimed(run_workspace, "run-4005")
    genuine = adapters.create_broker(
        BrokerCreationRequest(run_id="run-4005", workspace=run_workspace)
    ).session
    substituted = _substituted_broker_session(genuine, broker_token="tok-substituted")
    request = _build_launch_request(run_workspace, run_id="run-4005", broker_session=substituted)
    with pytest.raises(LiveAdapterError, match="does not match the exact authority"):
        adapters.launch_runtime(request)


def test_launch_runtime_reached_ready_false_is_unconstructible_at_a_lower_layer(
    run_workspace,
) -> None:
    """A ``reached_ready=False`` substitution can never even reach this
    adapter's own pinning check: the FROZEN ``RuntimeLaunchRequest.
    __post_init__`` already refuses to construct a request for a broker
    session whose ``reached_ready`` is not exactly ``True`` (frozen O1
    ordering: broker READY strictly precedes runtime launch). This test
    documents that lower-layer refusal so the absence of a
    reached_ready-substitution test against ``launch_runtime`` itself is
    not mistaken for a gap -- the L1 brief's "reached_ready disagreement"
    adversarial item is caught one layer down, before this adapter is ever
    invoked."""
    _claimed(run_workspace, "run-4006")
    not_ready = _unregistered_ready_broker_session(run_id="run-4006")
    from dataclasses import replace

    not_ready = replace(not_ready, reached_ready=False)
    with pytest.raises(Exception):  # ObservationError from RuntimeLaunchRequest
        _build_launch_request(run_workspace, run_id="run-4006", broker_session=not_ready)


def test_launch_runtime_refuses_a_second_substituted_session_id(run_workspace, patched) -> None:
    adapters = _adapters()
    _claimed(run_workspace, "run-4006b")
    genuine = adapters.create_broker(
        BrokerCreationRequest(run_id="run-4006b", workspace=run_workspace)
    ).session
    substituted = _substituted_broker_session(genuine, session_id="brk-substituted-id")
    request = _build_launch_request(run_workspace, run_id="run-4006b", broker_session=substituted)
    with pytest.raises(LiveAdapterError, match="not created by this adapter instance"):
        adapters.launch_runtime(request)


def test_launch_runtime_genuine_exact_broker_passes(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapters = _adapters()
    request = _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-4007")

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.responses["h1"] = (
            RUNTIME_RESPONSE_RECEIVED,
            _successful_get_commands_response(run_workspace),
        )
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    observation = adapters.launch_runtime(request)
    assert observation.session is not None
    assert observation.resource_created is True


# -- launch_runtime: main behaviour -------------------------------------------


def _successful_get_commands_response(workspace: QualificationRunWorkspace) -> dict:
    """The path here must match EXACTLY what ``write_disposable_extension``
    actually writes to for THIS workspace (``<experiment_root>/pi_extension/
    index.ts``) -- not the static AR2 extension SOURCE directory the files
    are copied FROM -- for H1's path check to genuinely pass."""
    extension_entry = os.path.join(workspace.experiment_root, "pi_extension", "index.ts")
    return {
        "success": True,
        "data": {
            "commands": [
                {
                    "name": SENTINEL_COMMAND_NAME,
                    "source": "extension",
                    "sourceInfo": {
                        "source": "cli",
                        "path": extension_entry,
                    },
                },
            ]
        },
    }


def test_launch_runtime_happy_path_establishes_all_four_facts(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapters = _adapters()
    request = _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-1001")

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.responses["h1"] = (RUNTIME_RESPONSE_RECEIVED, _successful_get_commands_response(run_workspace))
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    observation = adapters.launch_runtime(request)

    assert observation.session is not None
    assert observation.session.run_id == "run-1001"
    assert observation.session.broker_session_id == request.broker_session.session_id
    assert observation.launch_shape_valid is True
    assert observation.lf_jsonl_correlation_succeeded is True
    assert observation.required_flags_accepted is True
    assert observation.observed_pi_version == "0.84.3"
    assert observation.resource_created is True
    assert observation.cleanup_attempted is False
    # exactly one real get_commands frame was sent
    assert [c["type"] for c in patched.supervisors[-1].sent] == ["get_commands"]


def test_launch_runtime_never_re_resolves_identity(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L1 "SINGLE RUNTIME IDENTITY BINDING": ``launch_runtime`` must consume
    the constructor-injected ``RuntimeIdentity`` and must NEVER call
    ``resolve_pi_identity()`` again at launch time -- one Category-B
    attempt performs exactly one version probe."""
    calls: list[int] = []

    def _tracked() -> RuntimeIdentity:
        calls.append(1)
        raise LaunchIdentityError("resolve_pi_identity must never be called from launch_runtime")

    monkeypatch.setattr(live_module, "resolve_pi_identity", _tracked)
    adapters = _adapters()
    request = _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-1001b")

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.responses["h1"] = (RUNTIME_RESPONSE_RECEIVED, _successful_get_commands_response(run_workspace))
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    observation = adapters.launch_runtime(request)
    assert calls == []
    assert observation.observed_pi_version == SYNTHETIC_IDENTITY.reported_version


# -- 5F3B-I2B-L1-LF1 ----------------------------------------------------------
#
# LF1 test 4. The two tests that stood here before
# (``..._protocol_violation_denies_required_flags_accepted`` and
# ``..._malformed_protocol_violation_type_fails_closed``) asserted exactly
# the misattribution LF1 corrects: they pinned a launch-window protocol
# violation to ``required_flags_accepted is False``. They are REPLACED, not
# merely deleted -- the protocol-violation observation itself is still
# proven, at its own gate, by the ``observe_protocol`` tests below and by
# ``test_lf1_launch_window_protocol_violation_survives_to_protocol_observation``.


def test_lf1_launch_window_protocol_violation_does_not_deny_required_flags(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LF1 test 4: a protocol violation alone must NOT become an
    unknown-flag rejection.

    Frozen I2A section 15 item 3 defines ``required flags accepted`` as
    "no 'unknown flag' startup rejection". A launch-window protocol
    violation is not that fact and does not prove it; it belongs to the
    separate, later ``protocol_integrity`` gate. **No unknown-flag
    observation is present in this input**: the synthetic runtime accepted
    the exact argv, entered RPC command processing, consumed AIDO's one
    ``get_commands`` frame and returned a correlated response.
    """

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.responses["h1"] = (RUNTIME_RESPONSE_RECEIVED, _successful_get_commands_response(run_workspace))
        s._protocol_violation = _SYNTHETIC_VIOLATION_MESSAGE
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters()
    request = _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-1002")
    observation = adapters.launch_runtime(request)
    assert observation.launch_shape_valid is True
    assert observation.lf_jsonl_correlation_succeeded is True
    assert observation.required_flags_accepted is True


def test_lf1_clean_run_real_supervisor_contract_accepts_required_flags(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LF1 OBJECTIVE 1, corrected. THE LIVE REPRODUCTION.

    This is the exact synthetic shape of the first live Candidate-A attempt,
    expressed against the REAL supervisor contract
    (``protocol_violation`` is ``str | None``; ``None`` means no violation):
    ``launch_shape_valid`` True, LF correlation True, no violation, and **no
    unknown-flag observation anywhere in the input**.

    Before LF1 this produced ``required_flags_accepted=False`` -- the
    unsatisfiable ``type(None) is not bool`` check meant EVERY real launch
    reported a protocol violation. It now produces True.
    """

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.responses["h1"] = (RUNTIME_RESPONSE_RECEIVED, _successful_get_commands_response(run_workspace))
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters()
    request = _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-1002b")
    observation = adapters.launch_runtime(request)
    assert observation.launch_shape_valid is True
    assert observation.lf_jsonl_correlation_succeeded is True
    assert observation.required_flags_accepted is True
    # and the run is NOT quietly reclassified: nothing was observed to have
    # violated the protocol either.
    assert (
        adapters.observe_protocol(observation.session).protocol_violation_observed is False
    )


def test_lf1_unknown_flag_rejection_denies_required_flags_accepted(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LF1 test 2, as corrected by LF1-FU1: an unknown-CLI-flag startup
    rejection that is MECHANICALLY ESTABLISHED, not merely inferred.

    Established from the installed Pi package source, offline: an
    unrecognized option becomes an error diagnostic on STDERR and
    ``dist/main.js`` calls ``process.exit(1)`` strictly before ``runRpcMode``
    is entered, so the child terminates without ever answering an RPC
    command. The frozen supervisor's ``_wait`` reports
    ``RUNTIME_EXITED_EARLY`` for that.

    **FU1: the early exit is not the evidence -- the diagnostic is.** This
    test therefore supplies the exact stderr shape the package emits AND an
    option token actually present in AIDO's own argv, which is the only thing
    that establishes REJECTED. (The companion test
    ``test_lf1fu1_generic_early_exit_is_not_an_unknown_option_rejection``
    proves the identical outcome constant WITHOUT that diagnostic is
    INDETERMINATE instead.)

    The correct attribution is then: the Node-direct ``--mode rpc`` launch
    shape WAS valid (the process was constructed and launched), LF
    correlation did not succeed, and the required flags were REJECTED -- so
    the session IS handed over and the frozen controller can name the cause
    exactly.
    """

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.responses["h1"] = (RUNTIME_EXITED_EARLY, None)
        s.stderr_text = "Error: Unknown option: --offline\n"
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters()
    request = _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-1002c")
    observation = adapters.launch_runtime(request)
    assert observation.session is not None
    assert observation.launch_shape_valid is True
    assert observation.lf_jsonl_correlation_succeeded is False
    assert observation.required_flags_accepted is False
    assert adapters.launch_diagnostics()["run-1002c"] == {
        "argv_options": live_module.ARGV_OPTIONS_SOURCE_ESTABLISHED,
        "launch_correlation": live_module.CORRELATION_NONE_RUNTIME_EXITED_EARLY,
        "launch_window_protocol": (
            live_module.LAUNCH_WINDOW_PROTOCOL_VIOLATION_NOT_OBSERVED
        ),
        "required_launch_flags": live_module.REQUIRED_FLAGS_REJECTED_UNKNOWN_OPTION,
    }


def test_lf1_argv_options_are_all_source_established_for_the_real_argv() -> None:
    """LF1 test 3, half (a) of the proof chain: AIDO's OWN argv.

    Every option token the frozen, unmodified ``ar2.launch.build_pi_argv``
    emits is a member of the source-established option set -- each one has
    its own explicit recognizing branch in the installed Pi
    ``dist/cli/args.js`` ``parseArgs``. This is a fact about AIDO's argv
    vocabulary; it compares no version and authorizes nothing.
    """
    argv = build_pi_argv(
        SYNTHETIC_IDENTITY,
        extension_entry=r"C:\synthetic\experiment\pi_extension\index.ts",
        tool_allowlist=AR2_TOOL_ALLOWLIST,
        provider="synthetic-provider",
        model="synthetic-model",
    )
    assert live_module._argv_options_are_source_established(argv) is True
    # Every long option in the real argv is accounted for by name.
    assert {token for token in argv if token.startswith("--")} == set(
        live_module._PI_SOURCE_ESTABLISHED_LONG_OPTIONS
    )


def test_lf1_unestablished_argv_option_denies_required_flags_accepted(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LF1 test 3, fail-closed direction, as corrected by LF1-FU1: the
    runtime-behaviour half alone is NOT enough. An argv carrying an option
    whose recognition was never source-established denies ACCEPTED even when
    a correlated RPC response came back, so ``required_flags_accepted`` can
    never silently collapse into ``lf_jsonl_correlation_succeeded``.

    **FU1: denying ACCEPTED is not the same as asserting REJECTED.** A stale
    AIDO argv vocabulary says nothing about what Pi did -- and the correlated
    response in fact shows Pi rejected nothing -- so this is INDETERMINATE,
    which fails closed at the runtime-launch boundary with NO session rather
    than telling the frozen controller a rejection happened. The LF fact that
    genuinely WAS established is still reported truthfully on the partial
    observation.
    """

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(
            argv=tuple(argv) + ("--not-source-established",),
            cwd=cwd,
            environment=environment,
            bounds=bounds,
        )
        s.responses["h1"] = (RUNTIME_RESPONSE_RECEIVED, _successful_get_commands_response(run_workspace))
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    monkeypatch.setattr(
        live_module,
        "build_pi_argv",
        lambda identity, **kwargs: tuple(
            _real_build_pi_argv(identity, **kwargs)
        )
        + ("--not-source-established",),
    )
    adapters = _adapters()
    request = _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-1002d")
    observation = adapters.launch_runtime(request)
    assert observation.session is None
    assert observation.lf_jsonl_correlation_succeeded is True
    assert observation.required_flags_accepted is False
    assert observation.resource_created is True
    assert observation.cleanup_attempted is True
    assert observation.direct_child_reported_exit is True
    diagnostic = adapters.launch_diagnostics()["run-1002d"]
    assert diagnostic["argv_options"] == live_module.ARGV_OPTION_NOT_SOURCE_ESTABLISHED
    assert diagnostic["required_launch_flags"] == live_module.REQUIRED_FLAGS_INDETERMINATE


def test_lf1_argv_option_walker_fail_closed_cases() -> None:
    """The argv self-check walks AIDO's argv the way Pi's parser does, and
    fails closed on everything it does not positively recognize."""
    head = (r"C:\node.exe", r"C:\pi\dist\cli.js")
    check = live_module._argv_options_are_source_established
    # a value-taking option consumes its following token, even a dashed one
    assert check(head + ("--model", "-weird-model-id")) is True
    # a value-taking option with no value left
    assert check(head + ("--model",)) is False
    # an unexpected positional
    assert check(head + ("--offline", "a-stray-positional")) is False
    # a single-dash short option (Pi recognizes several, AIDO emits none)
    assert check(head + ("-nt",)) is False
    # a truncated argv that cannot even carry the two program paths
    assert check((r"C:\node.exe",)) is False


def test_lf1_launch_window_protocol_violation_survives_to_protocol_observation(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LF1 tests 5 and 6: independence, in the direction that matters.

    A protocol violation observed during the LAUNCH WINDOW must not
    disappear once ``required_flags_accepted`` stops consuming it. The frozen
    ``RecordStreamReader.protocol_violation`` field is monotonic and
    ``stdout_state()`` republishes it live, so the later, separate
    ``observe_protocol`` call still reports it -- which is what lets a real
    run truthfully produce ``required_launch_flags = PASSED`` alongside
    ``protocol_integrity = FAILED:PROTOCOL_VIOLATION_OBSERVED``.
    """

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.responses["h1"] = (RUNTIME_RESPONSE_RECEIVED, _successful_get_commands_response(run_workspace))
        s._protocol_violation = _SYNTHETIC_VIOLATION_MESSAGE
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters()
    request = _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-1002e")
    launch_observation = adapters.launch_runtime(request)
    assert launch_observation.required_flags_accepted is True

    protocol_observation = adapters.observe_protocol(launch_observation.session)
    assert protocol_observation.protocol_violation_observed is True
    # LF1 test 6: the two facts are now genuinely independent -- from ONE
    # real observation set, required flags PASS while protocol integrity
    # FAILS.
    assert launch_observation.required_flags_accepted is True
    assert protocol_observation.protocol_violation_observed is True
    assert adapters.launch_diagnostics()["run-1002e"] == {
        "argv_options": live_module.ARGV_OPTIONS_SOURCE_ESTABLISHED,
        "launch_correlation": live_module.CORRELATION_RESPONSE_RECEIVED,
        "launch_window_protocol": live_module.LAUNCH_WINDOW_PROTOCOL_VIOLATION_OBSERVED,
        "required_launch_flags": live_module.REQUIRED_FLAGS_ACCEPTED,
    }


def test_lf1_protocol_violation_projection_matches_the_frozen_ar2_contract() -> None:
    """LF1 test 7: malformed diagnostic state fails closed, and the ONE
    clean value is the one the frozen AR2 reader actually publishes.

    The real contract is ``str | None``. ``None`` -- and only ``None`` -- is
    "no violation". A ``bool`` is itself out of contract now, which is the
    precise inversion of the defect: the old check treated a ``bool`` as the
    only trustworthy shape and ``None`` as a violation.
    """
    project = live_module._protocol_violation_observed
    assert project({"protocol_violation": None}) is False
    assert project({"protocol_violation": _SYNTHETIC_VIOLATION_MESSAGE}) is True
    assert project({"protocol_violation": ""}) is True
    assert project({"protocol_violation": False}) is True
    assert project({"protocol_violation": True}) is True
    assert project({"protocol_violation": 0}) is True
    assert project({"protocol_violation": object()}) is True
    # a state mapping missing the key entirely is out of contract too
    assert project({}) is True


def test_lf1_every_protocol_violation_trigger_condition_is_enumerated() -> None:
    """LF1 OBJECTIVE 3: EVERY condition that can set ``protocol_violation``.

    Read from the frozen ``ar2.protocol`` source and exercised here against
    a real ``RecordStreamReader`` over an in-memory stream. There are
    exactly five, and all five live in the stdout framing/decoding path --
    none of them is a CLI-flag observation, so none of them can prove or
    disprove an unknown-flag startup rejection:

      1. a blank framed record (``RecordStreamReader._run``);
      2. an empty/whitespace-only record (``decode_record``);
      3. a record that is not valid UTF-8;
      4. a record that is not strict JSON;
      5. a record that is JSON but not an OBJECT.

    Every one of them assigns a MESSAGE STRING, never a bool -- which is the
    contract the pre-LF1 adapter projection contradicted.
    """
    from ar2.protocol import ProtocolViolation, ReasoningDropStats, decode_record

    # (2)-(5) are the decoder's own terminal conditions.
    for raw in (
        b"   ",  # whitespace only
        b"\xff\xfe not utf-8",  # invalid UTF-8
        b"{not json",  # not strict JSON
        b"[1, 2, 3]",  # JSON, but not an object
    ):
        with pytest.raises(ProtocolViolation):
            decode_record(raw)

    # (1) plus (4), end to end through the real reader on a real pipe-like
    # stream, proving the field is a STRING and that the reader stops.
    for payload, fragment in (
        (b'{"type":"a"}\n\n{"type":"b"}\n', "blank stdout record"),
        (b'{"type":"a"}\nnot-json\n', "not strict JSON"),
    ):
        reader = RecordStreamReader(
            io.BytesIO(payload),
            max_bytes=1 << 20,
            max_records=1000,
            stats=ReasoningDropStats(),
        )
        reader.start()
        reader.finished.wait(timeout=5.0)
        assert isinstance(reader.protocol_violation, str)
        assert fragment in reader.protocol_violation
        # monotonic: the reader stopped, and nothing clears the field
        assert reader.protocol_violation is not None

    # A clean stream leaves it at exactly ``None`` -- the ONE value that
    # means "no violation observed".
    clean = RecordStreamReader(
        io.BytesIO(b'{"type":"a"}\n{"type":"b"}\n'),
        max_bytes=1 << 20,
        max_records=1000,
        stats=ReasoningDropStats(),
    )
    clean.start()
    clean.finished.wait(timeout=5.0)
    assert clean.protocol_violation is None
    assert clean.record_count() == 2


def test_lf1_pi_rpc_output_shape_is_accepted_by_the_frozen_parser() -> None:
    """LF1 OBJECTIVE 3: no source-level Pi 0.84.4 RPC-shape drift.

    Pi's RPC mode writes stdout through exactly one function,
    ``dist/modes/rpc/jsonl.js`` ``serializeJsonLine``:

        ``return `${JSON.stringify(value)}\n`;``

    -- one JSON value, LF-only framing, one record per line, with that
    file's own header stating the same LF-only rule the frozen AR2 parser
    implements. Every RPC-mode emission (responses, events, extension UI
    requests) goes through it, and ``runRpcMode`` calls
    ``takeOverStdout()`` first, which redirects any OTHER
    ``process.stdout.write`` to stderr for the rest of the run.

    This models that exact shape for the record kinds AIDO's zero-prompt run
    can see and proves the frozen parser accepts all of them, including the
    U+2028/U+2029 case both sides call out explicitly.
    """
    from ar2.protocol import ReasoningDropStats, decode_record

    def serialize_json_line(value) -> bytes:
        # the Python equivalent of Pi's serializeJsonLine, ensure_ascii=False
        # so a real U+2028 byte sequence is actually emitted
        return (json.dumps(value, ensure_ascii=False) + "\n").encode("utf-8")

    emissions = [
        {"id": "h1", "type": "response", "command": "get_commands", "success": True,
         "data": {"commands": []}},
        {"id": "h2", "type": "response", "command": "get_state", "success": True,
         "data": {"model": {"provider": "p", "id": "m"}}},
        {"id": "x", "type": "response", "command": "get_state", "success": False,
         "error": "synthetic"},
        {"type": "extension_ui_request", "id": "u1"},
        # a payload string carrying the separators Node readline would split
        # on and strict JSONL must not -- the exact case both jsonl.js and
        # ar2.protocol document
        {"type": "message_end", "message": {"role": "assistant",
                                            "content": "a\u2028b\u2029c"}},
    ]
    stream = b"".join(serialize_json_line(value) for value in emissions)
    reader = RecordStreamReader(
        io.BytesIO(stream), max_bytes=1 << 20, max_records=1000, stats=ReasoningDropStats()
    )
    reader.start()
    reader.finished.wait(timeout=5.0)
    assert reader.protocol_violation is None
    assert reader.record_count() == len(emissions)
    # and each record decodes on its own too
    for value in emissions:
        assert decode_record(serialize_json_line(value).rstrip(b"\n")) == value


def test_lf1_prefix_defect_reproduction_old_projection_was_unsatisfiable() -> None:
    """LF1 OBJECTIVE 1: the PRE-FIX defect, reproduced durably.

    This evaluates the exact expression the adapter used before LF1 --

        ``type(raw) is not bool or raw is True``

    -- against the frozen AR2 contract's OWN value domain. It reports a
    protocol violation for BOTH clean state (``None``) and violated state (a
    message string), so it could never be False on a real run: the pre-fix
    ``required_flags_accepted``, which ANDed ``not`` that expression, was
    therefore False on every real launch regardless of what the runtime did.

    **No unknown-flag observation is involved anywhere in this
    reproduction.** The value domain below is exactly what
    ``RecordStreamReader.protocol_violation`` can hold; the CLI parser, the
    argv, and Pi's startup diagnostics play no part in it.
    """

    def _pre_lf1_projection(raw: object) -> bool:
        return type(raw) is not bool or raw is True

    # the two values the frozen reader can ACTUALLY publish
    assert _pre_lf1_projection(None) is True  # no violation -> reported as one
    assert _pre_lf1_projection(_SYNTHETIC_VIOLATION_MESSAGE) is True
    # so "not protocol_violation_observed" was unreachable on a real run
    assert not any(
        not _pre_lf1_projection(raw) for raw in (None, _SYNTHETIC_VIOLATION_MESSAGE)
    )
    # the corrected projection separates them, which is the whole point
    project = live_module._protocol_violation_observed
    assert project({"protocol_violation": None}) is False
    assert project({"protocol_violation": _SYNTHETIC_VIOLATION_MESSAGE}) is True


def test_lf1_required_flags_producer_reads_no_protocol_violation_bit() -> None:
    """LF1 OBJECTIVE 4 (LF1-FU1 form): source-level proof that the same bit
    no longer serves two gates.

    ``required_flags_accepted`` is now derived from ONE thing -- the declared
    three-state classification -- and neither the launch-window
    protocol-violation bit nor the launch-shape bit appears anywhere in the
    classifier's own source, so a protocol violation cannot reach the
    ``required_launch_flags`` gate by any path.
    """
    source = inspect.getsource(live_module.LiveCategoryBAdapters.launch_runtime)
    assignment = next(
        line for line in source.splitlines() if "required_flags_accepted = " in line
    )
    assert assignment.strip() == (
        "required_flags_accepted = required_flag_state == REQUIRED_FLAGS_ACCEPTED"
    )
    classifier = inspect.getsource(live_module._classify_required_flag_evidence)
    body = classifier[classifier.index('"""', classifier.index('"""') + 3) + 3 :]
    assert "argv_options_source_established" in body
    assert "lf_jsonl_correlation_succeeded" in body
    assert "protocol_violation" not in body
    assert "launch_shape_valid" not in body


def test_lf1_frozen_ar2_publishes_protocol_violation_as_str_or_none() -> None:
    """LF1 root-cause pin, read from the FROZEN AR2 source itself.

    If this ever changes, the projection above must be revisited
    deliberately rather than silently drifting back to a bool check.
    """
    reader_source = inspect.getsource(RecordStreamReader)
    assert "self.protocol_violation: str | None = None" in reader_source
    assert "self.protocol_violation = str(exc)" in reader_source
    supervisor_source = inspect.getsource(PiRpcSupervisor.stdout_state)
    assert '"protocol_violation": self._stdout.protocol_violation,' in supervisor_source


def test_lf1_recognized_await_outcomes_are_the_exact_reachable_domain() -> None:
    """LF1: ``RUNTIME_EXITED_EARLY`` is a real ``await_response`` outcome.

    Read from the frozen supervisor source: ``_wait`` -- the only body
    ``await_response`` returns from -- can return exactly these seven
    outcomes. ``RUNTIME_EXITED_EARLY`` was missing from the adapter's
    positive allowlist, which made a genuine early exit (the unknown-flag
    rejection shape) fail the EARLIER ``rpc_launch_shape`` gate instead of
    the required-flags gate.
    """
    wait_source = inspect.getsource(PiRpcSupervisor._wait)
    terminal_source = inspect.getsource(PiRpcSupervisor._terminal_stream_outcome)
    assert set(live_module._RECOGNIZED_AWAIT_RESPONSE_OUTCOMES) == {
        RUNTIME_RESPONSE_RECEIVED,
        RUNTIME_DEADLINE_EXPIRED,
        RUNTIME_EXITED_EARLY,
        RUNTIME_PROTOCOL_VIOLATION,
        RUNTIME_OUTPUT_CAP_EXCEEDED,
        RUNTIME_EVENT_CAP_EXCEEDED,
        RUNTIME_READ_ERROR,
    }
    # every one of them is named by the frozen source that produces them
    for name in ("RUNTIME_EXITED_EARLY", "RUNTIME_DEADLINE_EXPIRED", "RUNTIME_RESPONSE_RECEIVED"):
        assert name in wait_source
    for name in (
        "RUNTIME_PROTOCOL_VIOLATION",
        "RUNTIME_OUTPUT_CAP_EXCEEDED",
        "RUNTIME_EVENT_CAP_EXCEEDED",
        "RUNTIME_READ_ERROR",
    ):
        assert name in terminal_source
    # and the two outcomes ``await_response`` genuinely cannot produce stay out
    assert RUNTIME_SETTLED not in live_module._RECOGNIZED_AWAIT_RESPONSE_OUTCOMES
    assert RUNTIME_LAUNCH_FAILED not in live_module._RECOGNIZED_AWAIT_RESPONSE_OUTCOMES


def test_lf1_launch_diagnostic_values_are_declared_codes_only(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LF1 test 8: nothing raw reaches the retained diagnostic.

    Every value is a declared literal from
    ``LAUNCH_DIAGNOSTIC_CODES``. The raw supervisor outcome string, the raw
    protocol-violation MESSAGE, and every argv token (one of which is an
    absolute extension path) are all reduced away at the moment of
    observation and none of them appears anywhere in the diagnostic.
    """
    raw_outcome = "an-outcome-string-the-adapter-has-never-seen"

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.responses["h1"] = (raw_outcome, None)
        s._protocol_violation = _SYNTHETIC_VIOLATION_MESSAGE
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters()
    request = _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-1002f")
    observation = adapters.launch_runtime(request)
    # an unrecognized outcome still fails closed on the launch shape, and
    # (LF1-FU1) is INDETERMINATE for the flags, so no session crosses over
    assert observation.session is None
    assert observation.launch_shape_valid is False
    assert observation.required_flags_accepted is False

    diagnostic = adapters.launch_diagnostics()["run-1002f"]
    assert set(diagnostic) == {
        "argv_options",
        "launch_correlation",
        "launch_window_protocol",
        "required_launch_flags",
    }
    assert set(diagnostic.values()) <= live_module.LAUNCH_DIAGNOSTIC_CODES
    assert diagnostic["launch_correlation"] == live_module.CORRELATION_NONE_UNRECOGNIZED_OUTCOME

    serialized = json.dumps(adapters.launch_diagnostics())
    assert raw_outcome not in serialized
    assert _SYNTHETIC_VIOLATION_MESSAGE not in serialized
    assert "protocol violation" not in serialized
    for token in patched.supervisors[-1].argv:
        assert token not in serialized
    assert run_workspace.experiment_root not in serialized
    assert request.broker_session.pipe_name not in serialized
    assert request.broker_session.broker_token not in serialized
    assert request.broker_session.capability_id not in serialized


@pytest.mark.parametrize("version", ["0.84.3", "0.84.4", "9.99.99-unreleased"])
def test_lf1_pi_version_mismatch_alone_never_rejects(
    version, run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LF1 test 9 / OBJECTIVE 7: Pi version stays PROVENANCE ONLY.

    The first live attempt observed 0.84.4 where prior design-time source
    inspection had used 0.84.3. That difference must not, by itself, deny
    any launch fact. The version is carried on the observation and is read
    by nothing that produces a pass/fail.
    """
    identity = RuntimeIdentity(
        node_executable=SYNTHETIC_IDENTITY.node_executable,
        pi_cli_js=SYNTHETIC_IDENTITY.pi_cli_js,
        pi_package_root=SYNTHETIC_IDENTITY.pi_package_root,
        reported_version=version,
        launch_shape="node_direct",
    )

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.responses["h1"] = (
            RUNTIME_RESPONSE_RECEIVED,
            _successful_get_commands_response(run_workspace),
        )
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters(runtime_identity=_issued(identity))
    request = _launch_request_with_registered_broker(
        adapters, run_workspace, run_id="run-1002g"
    )
    observation = adapters.launch_runtime(request)
    assert observation.observed_pi_version == version
    assert observation.launch_shape_valid is True
    assert observation.lf_jsonl_correlation_succeeded is True
    assert observation.required_flags_accepted is True


def test_lf1_no_version_string_is_consulted_by_the_corrected_producer() -> None:
    """LF1 test 9, source-level: no version literal appears in the corrected
    required-flag machinery, so no exact-version authorization gate was
    introduced."""
    for function in (
        live_module._argv_options_are_source_established,
        live_module._protocol_violation_observed,
        live_module._launch_diagnostic,
    ):
        source = inspect.getsource(function)
        assert "reported_version" not in source
        assert "0.84" not in source


def test_lf1_correction_introduced_no_semantic_prompt_path() -> None:
    """LF1 test 10: the corrected module still sends only ``get_commands``
    and ``get_state``, and names no prompt anywhere."""
    source = inspect.getsource(live_module)
    assert '"type": "prompt"' not in source
    assert '"prompt"' not in source
    sent_types = sorted(
        node.value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value in {"get_commands", "get_state", "prompt"}
    )
    assert "prompt" not in sent_types


def test_launch_runtime_correlation_timeout_is_an_indeterminate_partial_launch(
    run_workspace, patched
) -> None:
    """``await_response`` timing out (never raising) is INDETERMINATE (LF1-FU1).

    Before FU1 this produced a SESSION carrying
    ``required_flags_accepted=False``, which the frozen controller read as
    REQUIRED_LAUNCH_FLAGS_REJECTED -- a cause a deadline does not establish.
    A deadline now fails closed at the runtime-launch boundary instead: the
    creator retains the runtime, closes it exactly once, reports the facts it
    genuinely observed, and hands over no session at all.
    """
    adapters = _adapters()
    request = _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-1003")
    observation = adapters.launch_runtime(request)
    assert observation.session is None
    assert observation.launch_shape_valid is True
    assert observation.lf_jsonl_correlation_succeeded is False
    assert observation.required_flags_accepted is False
    assert observation.observed_pi_version == SYNTHETIC_IDENTITY.reported_version
    assert observation.resource_created is True
    assert observation.cleanup_attempted is True
    assert observation.direct_child_reported_exit is True
    assert patched.supervisors[-1].shutdown_calls == 1
    assert (
        adapters.launch_diagnostics()["run-1003"]["required_launch_flags"]
        == live_module.REQUIRED_FLAGS_INDETERMINATE
    )


def test_launch_runtime_process_launch_failure_propagates_with_nothing_created(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``supervisor.launch()`` raising with ``supervisor.process`` still
    ``None`` means ``Popen`` itself never succeeded -- letting the
    exception propagate is correct (the frozen controller's own ``_invoke``
    reduces it to a bounded refusal with nothing to clean up)."""

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.launch_raises = PiSupervisorError(f"{RUNTIME_LAUNCH_FAILED}: synthetic")
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters()
    request = _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-1004")
    with pytest.raises(PiSupervisorError):
        adapters.launch_runtime(request)
    assert patched.supervisors[-1].process is None


def test_launch_runtime_launch_raises_after_process_assigned_retains_and_closes(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BLOCKER 2: ``PiRpcSupervisor.launch()`` assigns ``self.process``
    (via ``subprocess.Popen``) BEFORE constructing/starting its stdout/
    stderr reader threads -- only ``Popen``'s own ``OSError`` is wrapped
    locally, so a reader-setup exception can escape ``launch()`` with a
    REAL child already assigned. The adapter must distinguish this using
    ONLY the stable public ``supervisor.process`` attribute (never
    exception class/text): a real child exists here, so the creator
    retains ownership and performs exactly one bounded self-close -- never
    letting the exception propagate with nothing cleaned up."""

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.launch_raises = RuntimeError("synthetic reader-thread start failure")
        s.launch_process_assigned_before_raise = True
        s.shutdown_result = {"exit_status_observed": 1}
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters()
    request = _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-1004b")
    observation = adapters.launch_runtime(request)
    assert observation.session is None
    assert observation.resource_created is True
    assert observation.cleanup_attempted is True
    assert observation.direct_child_reported_exit is True
    assert observation.cleanup_verified_success is True
    assert patched.supervisors[-1].shutdown_calls == 1


def test_launch_runtime_launch_raises_after_process_assigned_and_cleanup_itself_raises(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BLOCKER 2 + BLOCKER 3 combined: the guarded self-close itself raising
    must never escape and must never fabricate a verified postcondition."""

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.launch_raises = RuntimeError("synthetic reader-thread start failure")
        s.launch_process_assigned_before_raise = True
        s.shutdown_raises = RuntimeError("synthetic shutdown failure")
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters()
    request = _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-1004c")
    observation = adapters.launch_runtime(request)
    assert observation.session is None
    assert observation.resource_created is True
    assert observation.cleanup_attempted is True
    assert observation.direct_child_reported_exit is False
    assert observation.cleanup_verified_success is False


def test_launch_runtime_correlation_probe_exception_retains_and_self_closes(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Adversarial items 8/9/10: a real process WAS started, but the
    correlation probe itself raised (e.g. a stdin write failure). The
    creator retains ownership, performs exactly one bounded self-close, and
    NEVER hands the controller a trusted session."""

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.send_raises = PiSupervisorError("supervisor error: stdin write failed")
        s.shutdown_result = {"exit_status_observed": 1}
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters()
    request = _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-1005")
    observation = adapters.launch_runtime(request)
    assert observation.session is None
    assert observation.resource_created is True
    assert observation.cleanup_attempted is True
    assert observation.direct_child_reported_exit is True
    assert observation.cleanup_verified_success is True
    assert patched.supervisors[-1].shutdown_calls == 1


def test_launch_runtime_correlation_probe_exception_reports_false_when_exit_unobserved(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The postcondition is the OBSERVED exit, never inferred from "shutdown
    returned without raising" (adversarial item 8)."""

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.send_raises = PiSupervisorError("supervisor error: stdin write failed")
        s.shutdown_result = {"exit_status_observed": None}
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters()
    request = _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-1006")
    observation = adapters.launch_runtime(request)
    assert observation.direct_child_reported_exit is False
    assert observation.cleanup_verified_success is False


def test_launch_runtime_correlation_probe_exception_cleanup_itself_raises(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Adversarial item D: the partial-runtime self-close itself raising
    must never escape and must never erase the primary correlation failure."""

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.send_raises = PiSupervisorError("supervisor error: stdin write failed")
        s.shutdown_raises = RuntimeError("synthetic shutdown failure")
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters()
    request = _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-1006b")
    observation = adapters.launch_runtime(request)
    assert observation.session is None
    assert observation.resource_created is True
    assert observation.cleanup_attempted is True
    assert observation.direct_child_reported_exit is False
    assert observation.cleanup_verified_success is False


# -- get_commands / get_state / observe_protocol / shutdown_runtime ----------


def test_get_commands_reprojects_the_cached_response_without_a_new_rpc_call(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.responses["h1"] = (RUNTIME_RESPONSE_RECEIVED, _successful_get_commands_response(run_workspace))
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters()
    launch_observation = adapters.launch_runtime(
        _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-2001")
    )
    sent_before = list(patched.supervisors[-1].sent)

    commands_observation = adapters.get_commands(launch_observation.session)

    assert patched.supervisors[-1].sent == sent_before  # no new frame sent
    assert commands_observation.call_succeeded is True
    assert commands_observation.response_shape_understood is True
    assert commands_observation.h1_identity_established is True
    assert commands_observation.commands[0].name == SENTINEL_COMMAND_NAME


def test_get_commands_success_field_not_exactly_bool_fails_closed(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BLOCKER 5: a ``"success": "false"`` (or any non-bool stand-in) must
    never be interpreted by Python truthiness as a protocol boolean."""

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.responses["h1"] = (RUNTIME_RESPONSE_RECEIVED, {"success": "false", "data": {}})
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters()
    launch_observation = adapters.launch_runtime(
        _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-2001b")
    )
    commands_observation = adapters.get_commands(launch_observation.session)
    assert commands_observation.call_succeeded is False
    assert commands_observation.response_shape_understood is False
    assert commands_observation.commands == ()


def test_get_commands_malformed_entry_among_valid_fails_the_whole_response_closed(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BLOCKER 5 ("GET_COMMANDS MALFORMED ENTRY"): a malformed entry mixed
    in with an otherwise-valid sentinel must never be silently filtered
    out -- it must fail the WHOLE response closed, preserving multiplicity
    rather than quietly reporting a smaller "clean" command list."""

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        valid = _successful_get_commands_response(run_workspace)
        valid["data"]["commands"].append(7)  # malformed: not an object at all
        s.responses["h1"] = (RUNTIME_RESPONSE_RECEIVED, valid)
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters()
    launch_observation = adapters.launch_runtime(
        _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-2001c")
    )
    commands_observation = adapters.get_commands(launch_observation.session)
    assert commands_observation.call_succeeded is True
    assert commands_observation.response_shape_understood is False
    assert commands_observation.commands == ()


def test_get_commands_refuses_a_foreign_session(run_workspace, patched) -> None:
    adapters = _adapters()
    foreign = RuntimeSession(
        run_id="run-x", broker_session_id="brk-x", runtime_session_id="rt-x"
    )
    with pytest.raises(LiveAdapterError, match="not created by this adapter instance"):
        adapters.get_commands(foreign)


def test_get_state_refuses_a_foreign_session(run_workspace, patched) -> None:
    adapters = _adapters()
    foreign = RuntimeSession(
        run_id="run-x", broker_session_id="brk-x", runtime_session_id="rt-x"
    )
    with pytest.raises(LiveAdapterError, match="not created by this adapter instance"):
        adapters.get_state(foreign)


def test_observe_protocol_refuses_a_foreign_session(run_workspace, patched) -> None:
    adapters = _adapters()
    foreign = RuntimeSession(
        run_id="run-x", broker_session_id="brk-x", runtime_session_id="rt-x"
    )
    with pytest.raises(LiveAdapterError, match="not created by this adapter instance"):
        adapters.observe_protocol(foreign)


def test_shutdown_runtime_refuses_a_foreign_session(run_workspace, patched) -> None:
    adapters = _adapters()
    foreign = RuntimeSession(
        run_id="run-x", broker_session_id="brk-x", runtime_session_id="rt-x"
    )
    with pytest.raises(LiveAdapterError, match="not created by this adapter instance"):
        adapters.shutdown_runtime(foreign)


def test_get_state_sends_exactly_one_fresh_real_call(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.responses["h1"] = (RUNTIME_RESPONSE_RECEIVED, _successful_get_commands_response(run_workspace))
        s.responses["h2"] = (
            RUNTIME_RESPONSE_RECEIVED,
            {
                "success": True,
                "data": {"model": {"provider": "b300_pi_qualification", "id": "qwen3-coder-next"}},
            },
        )
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters()
    launch_observation = adapters.launch_runtime(
        _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-2002")
    )
    state_observation = adapters.get_state(launch_observation.session)
    assert state_observation.call_succeeded is True
    assert state_observation.response_shape_understood is True
    assert state_observation.reported_provider == "b300_pi_qualification"
    assert state_observation.reported_model == "qwen3-coder-next"
    assert [c["type"] for c in patched.supervisors[-1].sent] == ["get_commands", "get_state"]


def test_get_state_malformed_response_reports_ununderstood_not_a_crash(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.responses["h1"] = (RUNTIME_RESPONSE_RECEIVED, _successful_get_commands_response(run_workspace))
        s.responses["h2"] = (RUNTIME_RESPONSE_RECEIVED, {"success": True, "data": "not-an-object"})
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters()
    launch_observation = adapters.launch_runtime(
        _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-2003")
    )
    state_observation = adapters.get_state(launch_observation.session)
    assert state_observation.call_succeeded is True
    assert state_observation.response_shape_understood is False
    assert state_observation.reported_provider is None
    assert state_observation.reported_model is None


def test_get_state_success_field_not_exactly_bool_fails_closed(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BLOCKER 5: ``"success": "false"`` on ``get_state`` must never be
    interpreted by truthiness."""

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.responses["h1"] = (RUNTIME_RESPONSE_RECEIVED, _successful_get_commands_response(run_workspace))
        s.responses["h2"] = (RUNTIME_RESPONSE_RECEIVED, {"success": "false", "data": {}})
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters()
    launch_observation = adapters.launch_runtime(
        _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-2003b")
    )
    state_observation = adapters.get_state(launch_observation.session)
    assert state_observation.call_succeeded is False
    assert state_observation.response_shape_understood is False


def test_get_state_deadline_expired_with_success_looking_body_is_never_usable(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BLOCKER 5 ("GET_STATE RESPONSE OUTCOME"): a contradictory pair --
    the wait outcome reporting a deadline expiry alongside a
    success-looking response body -- must NEVER produce a successful
    ``GetStateObservation``. The wait outcome gates the body."""

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.responses["h1"] = (RUNTIME_RESPONSE_RECEIVED, _successful_get_commands_response(run_workspace))
        s.responses["h2"] = (
            RUNTIME_DEADLINE_EXPIRED,
            {
                "success": True,
                "data": {"model": {"provider": "b300_pi_qualification", "id": "qwen3-coder-next"}},
            },
        )
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters()
    launch_observation = adapters.launch_runtime(
        _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-2003c")
    )
    state_observation = adapters.get_state(launch_observation.session)
    assert state_observation.call_succeeded is False
    assert state_observation.response_shape_understood is False
    assert state_observation.reported_provider is None
    assert state_observation.reported_model is None


def test_observe_protocol_reports_extension_errors_and_protocol_violation(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.responses["h1"] = (RUNTIME_RESPONSE_RECEIVED, _successful_get_commands_response(run_workspace))
        s._protocol_violation = _SYNTHETIC_VIOLATION_MESSAGE
        s.activity = SimpleNamespace(extension_errors=["synthetic_extension_error"])
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters()
    launch_observation = adapters.launch_runtime(
        _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-2004")
    )
    protocol_observation = adapters.observe_protocol(launch_observation.session)
    assert protocol_observation.protocol_violation_observed is True
    assert protocol_observation.extension_error_observed is True


def test_observe_protocol_malformed_violation_type_fails_closed(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BLOCKER 5: a ``protocol_violation`` value that is not exactly a
    ``bool`` fails closed (treated as observed) rather than being coerced."""

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.responses["h1"] = (RUNTIME_RESPONSE_RECEIVED, _successful_get_commands_response(run_workspace))
        s._protocol_violation = 0  # malformed: a falsy non-bool
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters()
    launch_observation = adapters.launch_runtime(
        _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-2004b")
    )
    protocol_observation = adapters.observe_protocol(launch_observation.session)
    assert protocol_observation.protocol_violation_observed is True


def test_observe_protocol_malformed_extension_errors_type_fails_closed(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BLOCKER 5: an ``extension_errors`` value that is not exactly a
    ``list`` fails closed (treated as an observed error)."""

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.responses["h1"] = (RUNTIME_RESPONSE_RECEIVED, _successful_get_commands_response(run_workspace))
        s.activity = SimpleNamespace(extension_errors="not-a-list")
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters()
    launch_observation = adapters.launch_runtime(
        _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-2004c")
    )
    protocol_observation = adapters.observe_protocol(launch_observation.session)
    assert protocol_observation.extension_error_observed is True


def test_shutdown_runtime_reports_the_observed_exit_not_the_call_returning(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Adversarial item 8: shutdown returning normally must not, by itself,
    be read as the child having exited."""

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.responses["h1"] = (RUNTIME_RESPONSE_RECEIVED, _successful_get_commands_response(run_workspace))
        s.shutdown_result = {"exit_status_observed": None}
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters()
    launch_observation = adapters.launch_runtime(
        _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-2005")
    )
    shutdown_observation = adapters.shutdown_runtime(launch_observation.session)
    assert shutdown_observation.shutdown_call_returned is True
    assert shutdown_observation.orchestrator_direct_child_reported_exit is False


# -- route_checker / TOOL_ALLOWLIST identity ---------------------------------


def test_route_checker_is_the_real_unmodified_ar2_function() -> None:
    from ar2.route_check import check_route_serves_model

    assert live_module.route_checker is check_route_serves_model


def test_tool_allowlist_agrees_with_ar2s_own() -> None:
    assert live_module.TOOL_ALLOWLIST == AR2_TOOL_ALLOWLIST


# -- BLOCKER 6: real non-secret preflight producers --------------------------


def test_preflight_pi_installed_offline_reports_the_real_offline_resolution() -> None:
    """This runs against the REAL AR2 resolvers (no monkeypatching) -- it
    is genuinely offline (no subprocess) either way, so it is safe to run
    unconditionally; whether Node/Pi happen to be installed on THIS test
    machine only changes which side of the bool it reports."""
    result = preflight_pi_installed_offline()
    assert isinstance(result, PreflightGateResult)
    assert result.name == "pi_installed_offline"
    if not result.passed:
        assert result.failure_code == "NOT_INSTALLED"


def test_preflight_pi_installed_offline_fails_closed_when_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise():
        raise LaunchIdentityError("launch error: synthetic node-not-found")

    monkeypatch.setattr(live_module, "_ar2_resolve_node_executable", _raise)
    result = preflight_pi_installed_offline()
    assert result.passed is False
    assert result.failure_code == "NOT_INSTALLED"


def test_preflight_config_generator_self_check_round_trips_and_cleans_up() -> None:
    import glob
    import tempfile

    before = set(glob.glob(os.path.join(tempfile.gettempdir(), "i2b-preflight-self-check-*")))
    result = preflight_config_generator_self_check()
    after = set(glob.glob(os.path.join(tempfile.gettempdir(), "i2b-preflight-self-check-*")))
    assert isinstance(result, PreflightGateResult)
    assert result.name == "config_generator_self_check"
    assert result.passed is True
    # the throwaway directory it created is removed unconditionally
    assert after == before


def test_preflight_config_generator_self_check_fails_closed_on_write_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from qualification.i2_pi_config import QualificationPiConfigError

    def _raise(*args, **kwargs):
        raise QualificationPiConfigError("config error: synthetic")

    monkeypatch.setattr(live_module, "write_qualification_pi_config", _raise)
    result = preflight_config_generator_self_check()
    assert result.passed is False
    assert result.failure_code == "VERIFICATION_FAILED"


def test_preflight_environment_forbidden_fragment_audit_happy_path() -> None:
    result = preflight_environment_forbidden_fragment_audit(
        ambient_environ={"SystemRoot": r"C:\Windows", "SOME_OTHER_VAR": "x"}
    )
    assert isinstance(result, PreflightGateResult)
    assert result.name == "environment_forbidden_fragment_audit"
    assert result.passed is True


def test_preflight_environment_forbidden_fragment_audit_fails_closed_on_unusable_ambient() -> None:
    result = preflight_environment_forbidden_fragment_audit(ambient_environ=object())
    assert result.passed is False
    assert result.failure_code == "CHECK_FAILED"


def test_preflight_environment_forbidden_fragment_audit_never_reads_a_value() -> None:
    class _ExplodingValueMapping(dict):
        def __getitem__(self, key):  # pragma: no cover - defensive
            raise AssertionError("a value was read from ambient_environ")

        def values(self):  # pragma: no cover - defensive
            raise AssertionError("a value was read from ambient_environ")

    ambient = _ExplodingValueMapping({"SystemRoot": r"C:\Windows"})
    result = preflight_environment_forbidden_fragment_audit(ambient_environ=ambient)
    assert result.passed is True


def test_preflight_environment_forbidden_fragment_audit_own_carrier_name_is_coherent() -> None:
    """A structural sanity check on the fixture itself: the real
    ``CREDENTIAL_ENV_VAR_NAME`` this audit checks is coherent, so the
    happy-path test above is not accidentally passing for the wrong
    reason."""
    from qualification.i2_environment import FORBIDDEN_NAME_FRAGMENTS, WITHHELD_PROFILE_NAMES

    assert not any(fragment in CREDENTIAL_ENV_VAR_NAME.upper() for fragment in FORBIDDEN_NAME_FRAGMENTS)
    assert CREDENTIAL_ENV_VAR_NAME not in WITHHELD_PROFILE_NAMES


def test_non_secret_gates_run_in_order_before_the_credential_reader() -> None:
    """BLOCKER 6 call-order requirement: the real live entrypoint's exact
    three-producer tuple, evaluated through the frozen
    ``resolve_connection_after_preflight`` -- every deterministic gate
    executes, IN ORDER, before ``read_connection`` is ever called."""
    calls: list[str] = []
    real_pi_installed = preflight_pi_installed_offline
    real_self_check = preflight_config_generator_self_check

    def _tracked_pi_installed():
        calls.append("pi_installed_offline")
        return real_pi_installed()

    def _tracked_self_check():
        calls.append("config_generator_self_check")
        return real_self_check()

    def _tracked_environment_audit():
        calls.append("environment_forbidden_fragment_audit")
        return preflight_environment_forbidden_fragment_audit(ambient_environ={"SystemRoot": "C:\\Windows"})

    def _read_connection() -> object:
        calls.append("read_connection")
        return object()

    result = resolve_connection_after_preflight(
        non_secret_gates=(_tracked_pi_installed, _tracked_self_check, _tracked_environment_audit),
        read_connection=_read_connection,
    )
    assert result is not None
    assert calls == [
        "pi_installed_offline",
        "config_generator_self_check",
        "environment_forbidden_fragment_audit",
        "read_connection",
    ]


def test_a_failed_preflight_gate_causes_zero_credential_reads() -> None:
    """BLOCKER 6: a failed non-secret gate must cause ZERO
    ``AIDO_LITELLM_*`` reads -- ``read_connection`` (and therefore any
    environment reader it wraps) is never invoked."""
    calls: list[str] = []

    def _failing_pi_installed():
        calls.append("pi_installed_offline")
        return PreflightGateResult(name="pi_installed_offline", passed=False, failure_code="NOT_INSTALLED")

    def _unreachable_self_check():
        calls.append("config_generator_self_check")  # pragma: no cover - must never run
        return PreflightGateResult(name="config_generator_self_check", passed=True)

    def _unreachable_environment_audit():
        calls.append("environment_forbidden_fragment_audit")  # pragma: no cover - must never run
        return PreflightGateResult(name="environment_forbidden_fragment_audit", passed=True)

    def _unreachable_read_connection() -> object:
        calls.append("read_connection")  # pragma: no cover - must never run
        return object()

    with pytest.raises(InfrastructureRefusal):
        resolve_connection_after_preflight(
            non_secret_gates=(
                _failing_pi_installed,
                _unreachable_self_check,
                _unreachable_environment_audit,
            ),
            read_connection=_unreachable_read_connection,
        )
    assert calls == ["pi_installed_offline"]


# -- zero-prompt / secret-leak source-level proofs ----------------------------


def _module_source() -> str:
    import inspect

    return inspect.getsource(live_module)


def test_no_prompt_command_type_is_ever_constructed() -> None:
    """The only RPC command types this module ever sends are get_commands and
    get_state. There is no ``"type": "prompt"`` literal anywhere."""
    source = _module_source()
    assert '"type": "prompt"' not in source
    assert "'type': 'prompt'" not in source
    tree = ast.parse(source)
    string_literals = {
        node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert "prompt" not in string_literals


def _identifiers_used_in_code() -> set[str]:
    """Every ``Name``/``Attribute`` identifier actually used in CODE -- never
    text that only appears inside a string literal (docstring, comment-like
    prose in a triple-quoted string, etc.). Parsing a docstring never
    produces a ``Name``/``Attribute`` node for a word inside it."""
    tree = ast.parse(_module_source())
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.Attribute):
            found.add(node.attr)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                found.add(alias.asname or alias.name)
    return found


def test_semantic_prompts_sent_is_never_named_in_this_module() -> None:
    assert "SEMANTIC_PROMPTS_SENT" not in _identifiers_used_in_code()


def test_no_credential_value_is_ever_interpolated_into_an_exception_message() -> None:
    """Every raised message in this module is a fixed literal string, or an
    f-string that interpolates ONLY a bounded, non-secret expression (an
    exception's own class NAME, via ``type(exc).__name__``) -- never a raw
    runtime value such as a credential, base URL, endpoint host, broker
    token, pipe name, capability id, or absolute path."""
    tree = ast.parse(_module_source())
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call)):
            continue
        for arg in node.exc.args:
            if not isinstance(arg, ast.JoinedStr):
                continue
            for piece in arg.values:
                if not isinstance(piece, ast.FormattedValue):
                    continue
                expr = piece.value
                is_exception_type_name = (
                    isinstance(expr, ast.Attribute)
                    and expr.attr == "__name__"
                    and isinstance(expr.value, ast.Call)
                    and isinstance(expr.value.func, ast.Name)
                    and expr.value.func.id == "type"
                )
                assert is_exception_type_name, (
                    "an exception message in i2b_live_adapters.py interpolates "
                    "something other than type(exc).__name__ -- every raised "
                    "message here must name no runtime value"
                )


def test_no_second_environment_reader_exists() -> None:
    """The only environment access in this module is the injected
    ``environ_reader`` this class was constructed with -- there is no real
    ``os.environ`` attribute access anywhere in the module's CODE."""
    tree = ast.parse(_module_source())
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "environ"
            and isinstance(node.value, ast.Name)
            and node.value.id == "os"
        ):
            pytest.fail("i2b_live_adapters.py accesses os.environ directly")


def test_no_direct_import_of_the_pinned_version_gate() -> None:
    """This module must never import ``ar2.launch.resolve_runtime_identity``
    (which pins an exact Pi version as an authorization gate) -- version is
    provenance only here, matching o1.pi_compat's corrected policy."""
    assert "resolve_runtime_identity" not in _identifiers_used_in_code()


# -- remaining pre-coding adversarial-analysis items -------------------------


def test_adversarial_item_4_two_brokers_never_share_state(run_workspace, second_run_workspace, patched) -> None:
    """Item 4: a broker READY observation must never belong to another
    broker. Two separate ``create_broker`` calls produce two independent
    servers/sessions with no shared state."""
    adapters = _adapters()
    r1 = adapters.create_broker(
        BrokerCreationRequest(run_id="run-A", workspace=_claimed(run_workspace, "run-A"))
    )
    r2 = adapters.create_broker(
        BrokerCreationRequest(run_id="run-B", workspace=_claimed(second_run_workspace, "run-B"))
    )
    assert r1.session.session_id != r2.session.session_id
    assert r1.session.run_id == "run-A"
    assert r2.session.run_id == "run-B"
    assert len(patched.servers) == 2
    assert patched.servers[0] is not patched.servers[1]
    # shutting down broker 1 must never touch broker 2's server
    adapters.shutdown_broker(r1.session)
    assert patched.servers[0].shutdown_calls == 1
    assert patched.servers[1].shutdown_calls == 0


def test_adversarial_item_8_broker_partial_close_reports_incomplete_truthfully(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Item 8, broker variant: the self-close call returns normally, but the
    broker's own postcondition (``STATE_CLOSED``) did NOT hold -- this must
    never be reported as verified cleanup."""

    def _make_server(handler):
        s = _FakeBrokerServer(handler)
        s.start_raises = TimeoutError("synthetic READY-deadline failure")
        s.state_after_start_raise = STATE_DRAINING
        s.shutdown_state_reached = "TEARDOWN_INCOMPLETE"
        patched.servers.append(s)
        return s

    monkeypatch.setattr(live_module, "BrokerServer", _make_server)
    adapters = _adapters()
    request = BrokerCreationRequest(run_id="run-8001", workspace=_claimed(run_workspace, "run-8001"))
    observation = adapters.create_broker(request)
    assert observation.reached_closed is False
    assert observation.cleanup_verified_success is False


def test_adversarial_item_11_malformed_get_commands_shape_does_not_crash(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Item 11: a malformed real RPC shape (``data.commands`` not a list)
    must be reported as ununderstood, never raise out of the adapter."""

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.responses["h1"] = (RUNTIME_RESPONSE_RECEIVED, {"success": True, "data": {"commands": "not-a-list"}})
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters()
    launch_observation = adapters.launch_runtime(
        _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-1101")
    )
    assert launch_observation.lf_jsonl_correlation_succeeded is True
    commands_observation = adapters.get_commands(launch_observation.session)
    assert commands_observation.call_succeeded is True
    assert commands_observation.response_shape_understood is False
    assert commands_observation.commands == ()


def test_adversarial_item_12_pi_exits_between_observations(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Item 12: Node/Pi exits between the launch correlation probe and the
    later, separate get_state call -- get_state must fail closed, not
    crash, and must not fabricate a response."""

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.responses["h1"] = (RUNTIME_RESPONSE_RECEIVED, _successful_get_commands_response(run_workspace))
        # h2 is deliberately absent from `responses`, so `await_response`
        # falls through to its own "not received" default -- simulating the
        # process having exited before a get_state response ever arrived.
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters()
    launch_observation = adapters.launch_runtime(
        _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-1201")
    )
    state_observation = adapters.get_state(launch_observation.session)
    assert state_observation.call_succeeded is False
    assert state_observation.response_shape_understood is False
    assert state_observation.reported_provider is None
    assert state_observation.reported_model is None


# -- BLOCKER 7: outer live-harness cleanup (run_i2b_live.py) -----------------


def _import_run_i2b_live():
    import run_i2b_live

    return run_i2b_live


def test_lf1_live_harness_records_only_declared_diagnostic_codes(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LF1 OBJECTIVE 6 / test 8, at the LIVE-RUN ARTIFACT level.

    ``run_i2b_live`` attaches ``adapters.launch_diagnostics()`` to the run
    summary ALONGSIDE the frozen controller's result. This proves what
    actually lands in the artifact: three declared codes per run and nothing
    else, and that the frozen evidence schema is untouched (the diagnostic
    is a sibling key of ``evidence``, never a member of it).
    """
    run_i2b_live = _import_run_i2b_live()

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.responses["h1"] = (RUNTIME_EXITED_EARLY, None)
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters()
    request = _launch_request_with_registered_broker(
        adapters, run_workspace, run_id="run-lf1-harness"
    )
    adapters.launch_runtime(request)

    diagnostics = adapters.launch_diagnostics()
    assert list(diagnostics) == ["run-lf1-harness"]
    assert set(diagnostics["run-lf1-harness"].values()) <= live_module.LAUNCH_DIAGNOSTIC_CODES

    # the harness attaches it as a SIBLING of the frozen evidence, never
    # inside it -- the frozen CategoryBEvidence schema is not reopened.
    harness_source = inspect.getsource(run_i2b_live.run_one_category_b_live_attempt)
    assert 'summary["launch_diagnostics"] = adapters.launch_diagnostics()' in harness_source
    summary_source = inspect.getsource(run_i2b_live._safe_result_summary)
    assert "launch_diagnostics" not in summary_source

    # and the frozen observation/evidence types gained no field for it
    from qualification.i2b_session import RuntimeLaunchObservation

    assert not hasattr(RuntimeLaunchObservation, "launch_diagnostic")
    assert "launch_diagnostic" not in inspect.getsource(RuntimeLaunchObservation)


def test_lf1_live_harness_diagnostic_passes_the_qualification_scrub(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LF1 test 8: the retained diagnostic carries no needle.

    Run the package's OWN artifact scrub over the serialized diagnostic,
    under a safety context declaring this run's real broker token, pipe
    name, capability id, endpoint host, API key and absolute workspace path
    as needles. The declared codes contain none of them.
    """

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.responses["h1"] = (RUNTIME_RESPONSE_RECEIVED, _successful_get_commands_response(run_workspace))
        s._protocol_violation = _SYNTHETIC_VIOLATION_MESSAGE
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters()
    request = _launch_request_with_registered_broker(
        adapters, run_workspace, run_id="run-lf1-scrub"
    )
    adapters.launch_runtime(request)

    context = live_module.ArtifactSafetyContext(
        endpoint_host="synthetic-endpoint.invalid",
        api_key=SYNTHETIC_API_KEY,
        broker_token=request.broker_session.broker_token,
        pipe_name=request.broker_session.pipe_name,
        capability_id=request.broker_session.capability_id,
        workspace_absolute_path=run_workspace.workspace_root,
    )
    check = live_module.qualification_scrub_check(adapters.launch_diagnostics(), context)
    assert check["clean"] is True
    assert check["findings"] == []


def test_outer_cleanup_both_actions_attempted_independently_on_scrub_failure(
    run_workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BLOCKER 7 / adversarial item M: an extension-scrub failure must
    never skip workspace removal."""
    run_i2b_live = _import_run_i2b_live()
    from pathlib import Path

    extension_dir = Path(run_workspace.experiment_root) / "pi_extension"
    extension_dir.mkdir(parents=True, exist_ok=True)

    def _raise(_extension_dir):
        raise RuntimeError("synthetic scrub failure")

    monkeypatch.setattr(run_i2b_live, "scrub_generated_extension_config", _raise)
    removed: list[bool] = []
    real_remove = run_i2b_live.remove_run_workspace

    def _tracked_remove(workspace):
        removed.append(True)
        return real_remove(workspace)

    monkeypatch.setattr(run_i2b_live, "remove_run_workspace", _tracked_remove)

    result = run_i2b_live._run_outer_cleanup(run_workspace)
    assert removed == [True]
    assert result["extension_scrub_attempted"] is True
    assert result["extension_scrub_verified"] is False
    assert result["workspace_removal_attempted"] is True
    assert result["workspace_removal_verified"] is True
    assert result["outer_cleanup_verified"] is False


def test_outer_cleanup_workspace_removal_failure_is_reported_not_swallowed(
    run_workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BLOCKER 7 / adversarial item N: a workspace-removal failure must be
    reported truthfully, never silently swallowed, and must not erase the
    fact that the extension scrub (if any) succeeded."""
    run_i2b_live = _import_run_i2b_live()

    def _raise(_workspace):
        raise RuntimeError("synthetic workspace removal failure")

    monkeypatch.setattr(run_i2b_live, "remove_run_workspace", _raise)
    result = run_i2b_live._run_outer_cleanup(run_workspace)
    assert result["workspace_removal_attempted"] is True
    assert result["workspace_removal_verified"] is False
    assert result["outer_cleanup_verified"] is False
    # No exception escaped, and no silent pass=True -- the caller sees the
    # truth. The real `remove_run_workspace` (this test module's own
    # import, unaffected by the monkeypatch above) still runs via the
    # `run_workspace` fixture's own teardown.


def test_outer_cleanup_verified_true_when_nothing_to_scrub_and_removal_succeeds(
    run_workspace,
) -> None:
    run_i2b_live = _import_run_i2b_live()
    result = run_i2b_live._run_outer_cleanup(run_workspace)
    assert result["extension_scrub_attempted"] is False
    assert result["extension_scrub_verified"] is True
    assert result["workspace_removal_attempted"] is True
    assert result["workspace_removal_verified"] is True
    assert result["outer_cleanup_verified"] is True



# -- L1-FU5 PRIMARY BLOCKER: the exact frozen removal return shape ----------


@pytest.mark.parametrize(
    ("removal_result", "case_id"),
    [
        ({"removed": True, "residual_file_count": 0, "verified": True}, "1-genuine-success"),
        ({"removed": False, "residual_file_count": 1, "verified": True}, "2-residual-files"),
        ({"removed": False, "residual_file_count": 0, "verified": True}, "3-not-removed-zero-residual"),
        ({"removed": True, "residual_file_count": 0, "verified": False}, "4-unverified"),
        ({"removed": "true", "residual_file_count": 0, "verified": "true"}, "5-malformed-bool-strings"),
        ({"removed": True, "verified": True}, "6-missing-residual-field"),
        ({"removed": True, "residual_file_count": 0}, "6b-missing-verified-field"),
        ({"verified": True, "residual_file_count": 0}, "6c-missing-removed-field"),
        (["removed", True, "verified", True], "7-non-dict-list"),
        ("removed", "7b-non-dict-string"),
        (None, "7c-non-dict-none"),
        ({"removed": True, "residual_file_count": True, "verified": True}, "extra-bool-residual-count"),
        ({"removed": True, "residual_file_count": 1, "verified": True}, "success-flag-but-nonzero-residual"),
    ],
)
def test_outer_cleanup_consumes_the_exact_frozen_removal_return_shape(
    run_workspace, monkeypatch: pytest.MonkeyPatch, removal_result, case_id
) -> None:
    """L1-FU5 PRIMARY BLOCKER, mandatory regressions 1-7: a NORMAL return
    from ``remove_run_workspace`` -- no exception raised -- is validated
    against the exact frozen ``ar2.fixtures.remove_disposable_tree``
    success shape. Only case 1 (and the parametrize case that reproduces it
    exactly) is accepted; every other shape -- a residual count, an
    unverified postcondition, malformed boolean-looking strings, a missing
    field, or a non-dict result entirely -- fails CLOSED. Nothing here uses
    ``bool(result)``, "no exception means success", or ``.get(...)`` default
    substitution."""
    run_i2b_live = _import_run_i2b_live()
    monkeypatch.setattr(run_i2b_live, "remove_run_workspace", lambda workspace: removal_result)
    result = run_i2b_live._run_outer_cleanup(run_workspace)
    expected = removal_result == {"removed": True, "residual_file_count": 0, "verified": True}
    assert result["workspace_removal_attempted"] is True
    assert result["workspace_removal_verified"] is expected, case_id
    assert result["outer_cleanup_verified"] is expected, case_id


def test_outer_cleanup_never_uses_truthiness_of_the_removal_return(
    run_workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Adversarial: a non-empty dict that is truthy but is not the exact
    frozen success shape must still fail closed -- guards against a
    ``bool(result)``-style regression."""
    run_i2b_live = _import_run_i2b_live()
    truthy_but_not_success = {
        "removed": False,
        "residual_file_count": 3,
        "verified": True,
        "extra_field": "still truthy",
    }
    monkeypatch.setattr(
        run_i2b_live, "remove_run_workspace", lambda workspace: truthy_but_not_success
    )
    result = run_i2b_live._run_outer_cleanup(run_workspace)
    assert bool(truthy_but_not_success) is True  # sanity: the dict itself is truthy
    assert result["workspace_removal_verified"] is False


def test_main_does_not_report_pass_when_outer_cleanup_failed(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """BLOCKER 7: a controller CATEGORY_B_GATE_PASSED result is NOT an
    accepted live PASS if the outer cleanup did not verify."""
    run_i2b_live = _import_run_i2b_live()

    def _fake_run_one_category_b_live_attempt(*, candidate: str):
        return {
            "candidate": candidate,
            "outcome": run_i2b_live.CategoryBOutcome.CATEGORY_B_GATE_PASSED.value,
            "outer_cleanup": {
                "extension_scrub_attempted": True,
                "extension_scrub_verified": False,
                "workspace_removal_attempted": True,
                "workspace_removal_verified": True,
                "outer_cleanup_verified": False,
            },
        }

    monkeypatch.setattr(
        run_i2b_live, "run_one_category_b_live_attempt", _fake_run_one_category_b_live_attempt
    )
    monkeypatch.setattr(run_i2b_live, "RESULTS_DIR", tmp_path)
    exit_code = run_i2b_live.main(["--candidate", "A", "--run-category-b-live-gate"])
    assert exit_code == 2


def test_main_reports_pass_when_outcome_passed_and_outer_cleanup_verified(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    run_i2b_live = _import_run_i2b_live()

    def _fake_run_one_category_b_live_attempt(*, candidate: str):
        return {
            "candidate": candidate,
            "outcome": run_i2b_live.CategoryBOutcome.CATEGORY_B_GATE_PASSED.value,
            "outer_cleanup": {
                "extension_scrub_attempted": False,
                "extension_scrub_verified": True,
                "workspace_removal_attempted": True,
                "workspace_removal_verified": True,
                "outer_cleanup_verified": True,
            },
        }

    monkeypatch.setattr(
        run_i2b_live, "run_one_category_b_live_attempt", _fake_run_one_category_b_live_attempt
    )
    monkeypatch.setattr(run_i2b_live, "RESULTS_DIR", tmp_path)
    exit_code = run_i2b_live.main(["--candidate", "A", "--run-category-b-live-gate"])
    assert exit_code == 0


# =============================================================================
# 5F3B-I2B-L1-FU2
# =============================================================================


# -- BLOCKER 1: executable-source authority ----------------------------------


def test_constructor_no_longer_accepts_an_extension_source_directory() -> None:
    """The supported/public constructor has NO parameter through which a
    caller can express a substitute extension source at all."""
    with pytest.raises(TypeError):
        _adapters(ar2_extension_source_dir=r"C:\arbitrary\attacker\extension")


def test_frozen_extension_source_resolves_to_the_real_ar2_extension_directory() -> None:
    import pathlib

    expected = str(
        pathlib.Path(__file__).resolve().parents[2] / "pi_external_runtime_ar2" / "extension"
    )
    assert os.path.realpath(live_module._FROZEN_AR2_EXTENSION_SOURCE_DIR) == os.path.realpath(
        expected
    )


def test_authorized_extension_source_matches_its_frozen_digest() -> None:
    """The real, on-disk AR2 extension source, hashed the same way the
    module hashes it, agrees with the frozen literal -- proving the frozen
    constant is not simply trusted uncritically."""
    observed = live_module._hash_extension_source_tree(
        live_module._FROZEN_AR2_EXTENSION_SOURCE_DIR
    )
    assert observed == live_module._FROZEN_AR2_EXTENSION_SHA256


def test_construction_refuses_when_the_frozen_extension_digest_is_tampered(
    patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A content mismatch against the frozen digest is refused BEFORE any
    broker/runtime resource is ever created -- modelling "the real source
    tree changed on disk and the reviewed digest was not updated to match"
    (the correct fail-closed direction, never a silent pass-through)."""
    monkeypatch.setattr(
        live_module, "_FROZEN_AR2_EXTENSION_SHA256", "0" * 64
    )
    with pytest.raises(LiveAdapterError, match="does not match its authorized digest"):
        _adapters()


def test_pre_fix_repro_arbitrary_extension_source_is_structurally_unreachable() -> None:
    """PRE-FIX REPRO (L1-FU2 brief): using ONLY offline doubles, prove the
    CURRENT supported API cannot express "construct with an arbitrary
    extension source directory" at all -- ``inspect.signature`` shows no
    such parameter exists, closing the exact gap the brief demonstrated
    against the pre-fix constructor."""
    parameters = inspect.signature(LiveCategoryBAdapters.__init__).parameters
    assert "ar2_extension_source_dir" not in parameters


# -- BLOCKER 1: RuntimeIdentity authority -------------------------------------


def test_construction_refuses_substituted_node_executable(patched) -> None:
    from dataclasses import replace

    substituted = replace(SYNTHETIC_IDENTITY, node_executable=r"C:\attacker\node.exe")
    with pytest.raises(LiveAdapterError, match="trusted resolver path exactly"):
        _adapters(runtime_identity=_issued(substituted))


def test_construction_refuses_substituted_pi_cli_js(patched) -> None:
    from dataclasses import replace

    substituted = replace(SYNTHETIC_IDENTITY, pi_cli_js=r"C:\attacker\pi\dist\cli.js")
    with pytest.raises(LiveAdapterError, match="trusted resolver path exactly"):
        _adapters(runtime_identity=_issued(substituted))


def test_construction_refuses_substituted_pi_package_root(patched) -> None:
    from dataclasses import replace

    substituted = replace(SYNTHETIC_IDENTITY, pi_package_root=r"C:\attacker\pi")
    with pytest.raises(LiveAdapterError, match="trusted resolver path exactly"):
        _adapters(runtime_identity=_issued(substituted))


def test_construction_refuses_a_non_node_direct_launch_shape(patched) -> None:
    from dataclasses import replace

    substituted = replace(SYNTHETIC_IDENTITY, launch_shape="something_else")
    with pytest.raises(LiveAdapterError, match="node_direct launch shape"):
        _adapters(runtime_identity=_issued(substituted))


def test_construction_refuses_an_empty_reported_version(patched) -> None:
    from dataclasses import replace

    substituted = replace(SYNTHETIC_IDENTITY, reported_version="")
    with pytest.raises(LiveAdapterError, match="non-empty observed reported_version"):
        _adapters(runtime_identity=_issued(substituted))


def test_construction_accepts_a_differing_reported_version_when_paths_match(patched) -> None:
    """``reported_version`` remains provenance only -- differing from
    whatever a real probe might report never refuses construction, as long
    as the executable paths match the trusted resolver exactly (no
    exact-version pinning is reintroduced)."""
    from dataclasses import replace

    substituted = replace(SYNTHETIC_IDENTITY, reported_version="9.9.9-different")
    adapters = _adapters(runtime_identity=_issued(substituted))
    assert adapters is not None


def test_trusted_resolution_failure_refuses_construction(
    patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If this machine's own trusted resolver cannot resolve at all, a
    RuntimeIdentity cannot be trusted either -- fails closed, never
    silently accepted."""

    def _raise():
        raise LaunchIdentityError("launch error: synthetic node-not-found")

    monkeypatch.setattr(live_module, "_ar2_resolve_node_executable", _raise)
    with pytest.raises(LiveAdapterError, match="could not resolve"):
        _adapters()


# -- BLOCKER 4: shutdown_broker exact minted authority ------------------------


def test_shutdown_broker_refuses_substituted_pipe_name(run_workspace, patched) -> None:
    adapters = _adapters()
    request = BrokerCreationRequest(run_id="run-5001", workspace=_claimed(run_workspace, "run-5001"))
    genuine = adapters.create_broker(request).session
    substituted = _substituted_broker_session(genuine, pipe_name=r"\\.\pipe\substituted-shutdown")
    with pytest.raises(LiveAdapterError, match="does not match the exact authority"):
        adapters.shutdown_broker(substituted)
    assert patched.servers[0].shutdown_calls == 0


def test_shutdown_broker_refuses_substituted_capability_id(run_workspace, patched) -> None:
    adapters = _adapters()
    request = BrokerCreationRequest(run_id="run-5002", workspace=_claimed(run_workspace, "run-5002"))
    genuine = adapters.create_broker(request).session
    substituted = _substituted_broker_session(genuine, capability_id="cap-substituted-shutdown")
    with pytest.raises(LiveAdapterError, match="does not match the exact authority"):
        adapters.shutdown_broker(substituted)
    assert patched.servers[0].shutdown_calls == 0


def test_shutdown_broker_refuses_substituted_broker_token(run_workspace, patched) -> None:
    adapters = _adapters()
    request = BrokerCreationRequest(run_id="run-5003", workspace=_claimed(run_workspace, "run-5003"))
    genuine = adapters.create_broker(request).session
    substituted = _substituted_broker_session(genuine, broker_token="tok-substituted-shutdown")
    with pytest.raises(LiveAdapterError, match="does not match the exact authority"):
        adapters.shutdown_broker(substituted)
    assert patched.servers[0].shutdown_calls == 0


def test_shutdown_broker_refuses_a_second_substituted_session_id(run_workspace, patched) -> None:
    adapters = _adapters()
    request = BrokerCreationRequest(run_id="run-5004", workspace=_claimed(run_workspace, "run-5004"))
    genuine = adapters.create_broker(request).session
    substituted = _substituted_broker_session(genuine, session_id="brk-substituted-shutdown-id")
    with pytest.raises(LiveAdapterError, match="not created by this adapter instance"):
        adapters.shutdown_broker(substituted)
    assert patched.servers[0].shutdown_calls == 0


def test_shutdown_broker_refuses_same_run_id_foreign_session_id(run_workspace, patched) -> None:
    adapters = _adapters()
    _claimed(run_workspace, "run-5005")
    foreign = _unregistered_ready_broker_session(run_id="run-5005")
    with pytest.raises(LiveAdapterError, match="not created by this adapter instance"):
        adapters.shutdown_broker(foreign)


def test_shutdown_broker_genuine_exact_minted_session_still_shuts_down(
    run_workspace, patched
) -> None:
    adapters = _adapters()
    request = BrokerCreationRequest(run_id="run-5006", workspace=_claimed(run_workspace, "run-5006"))
    observation = adapters.create_broker(request)
    result = adapters.shutdown_broker(observation.session)
    assert result.reached_closed is True
    assert patched.servers[0].shutdown_calls == 1


# -- raw supervisor outcome domain --------------------------------------------


def test_launch_runtime_unknown_supervisor_outcome_fails_closed(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An outcome string that is not a member of the recognized, positive
    ``await_response`` outcome set must never become
    ``launch_shape_valid=True`` merely because it isn't one of the two
    previously-checked known-bad constants."""

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        s.responses["h1"] = ("totally_unrecognized_outcome", None)
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    adapters = _adapters()
    request = _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-6001")
    observation = adapters.launch_runtime(request)
    assert observation.launch_shape_valid is False
    assert observation.required_flags_accepted is False


# -- BLOCKER 3: the seven I2A §14 Category-A preflight producers -------------


def test_preflight_child_environment_builder_self_check_passes() -> None:
    result = preflight_child_environment_builder_self_check()
    assert result.name == "child_environment_builder_self_check"
    assert result.passed is True


def test_preflight_child_environment_builder_self_check_fails_closed_on_builder_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(**kwargs):
        raise live_module.EnvironmentPolicyError("environment error: synthetic")

    monkeypatch.setattr(live_module, "build_child_environment", _raise)
    result = preflight_child_environment_builder_self_check()
    assert result.passed is False
    assert result.failure_code == "VERIFICATION_FAILED"


def test_preflight_candidate_route_generator_symmetry_passes() -> None:
    result = preflight_candidate_route_generator_symmetry()
    assert result.name == "candidate_route_generator_symmetry"
    assert result.passed is True


def test_preflight_candidate_route_generator_symmetry_fails_closed_on_disagreement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_write = live_module.write_qualification_pi_config
    calls = {"n": 0}

    def _tampering_write(experiment_root, *, model_id, base_url):
        generated = real_write(experiment_root, model_id=model_id, base_url=base_url)
        calls["n"] += 1
        if calls["n"] == 2:
            # Tamper candidate B's settings.json AFTER a genuine, authorized
            # write -- models a drifted generator, never a forged input.
            from pathlib import Path

            settings_path = Path(generated.settings_path)
            text = settings_path.read_text(encoding="utf-8")
            settings_path.write_text(text.replace('"quietStartup": true', '"quietStartup": false'), encoding="utf-8")
        return generated

    monkeypatch.setattr(live_module, "write_qualification_pi_config", _tampering_write)
    result = preflight_candidate_route_generator_symmetry()
    assert result.passed is False
    assert result.failure_code == "VERIFICATION_FAILED"


def test_preflight_planned_cli_argv_shape_passes() -> None:
    result = preflight_planned_cli_argv_shape()
    assert result.name == "planned_cli_argv_shape"
    assert result.passed is True


def test_preflight_planned_cli_argv_shape_fails_closed_when_argv_disagrees(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _tampered_argv(identity, *, extension_entry, tool_allowlist, provider, model):
        return ("node", "cli.js", "--api-key", "sk-should-never-appear")

    monkeypatch.setattr(live_module, "build_pi_argv", _tampered_argv)
    result = preflight_planned_cli_argv_shape()
    assert result.passed is False
    assert result.failure_code == "SCHEMA_INVALID"


def test_preflight_artifact_safety_scrub_self_check_passes() -> None:
    result = preflight_artifact_safety_scrub_self_check()
    assert result.name == "artifact_safety_scrub_self_check"
    assert result.passed is True


def test_preflight_artifact_safety_scrub_self_check_fails_closed_when_scrub_never_refuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _always_clean(payload, safety):
        return {"scrub_checked": True, "findings": [], "clean": True}

    monkeypatch.setattr(live_module, "qualification_scrub_check", _always_clean)
    result = preflight_artifact_safety_scrub_self_check()
    assert result.passed is False
    assert result.failure_code == "VERIFICATION_FAILED"


def test_preflight_config_generator_no_credential_literal_path_passes() -> None:
    result = preflight_config_generator_no_credential_literal_path()
    assert result.name == "config_generator_no_credential_literal_path"
    assert result.passed is True


def test_preflight_config_generator_no_credential_literal_path_fails_closed_on_a_credential_parameter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _hypothetical_forked_generator(experiment_root, *, model_id, base_url, api_key):
        raise AssertionError("must never be called")  # pragma: no cover

    monkeypatch.setattr(
        live_module, "write_qualification_pi_config", _hypothetical_forked_generator
    )
    result = preflight_config_generator_no_credential_literal_path()
    assert result.passed is False
    assert result.failure_code == "SCHEMA_INVALID"


def test_preflight_pi_installed_offline_reads_the_package_json_version_field(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """§14.1: the check must genuinely read ``package.json``'s ``version``
    field by plain file read -- a package root whose ``package.json`` has
    no observable version fails closed, even though every path-existence
    check passes."""
    package_root = tmp_path / "self-check-pi-package"
    dist_dir = package_root / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "cli.js").write_text("// synthetic", encoding="utf-8")
    (package_root / "package.json").write_text("{}", encoding="utf-8")  # no "version" key

    monkeypatch.setattr(live_module, "_ar2_resolve_pi_package_root", lambda: str(package_root))
    monkeypatch.setattr(
        live_module, "_ar2_resolve_node_executable", lambda: SYNTHETIC_IDENTITY.node_executable
    )
    result = preflight_pi_installed_offline()
    assert result.passed is False
    assert result.failure_code == "NOT_INSTALLED"


# -- L1-FU2 nearby: config-generator self-check issuance cleanup ------------


def test_preflight_config_generator_self_check_discards_the_issuance_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A verified cleanup must ALSO discard the process-local
    ``i2_issuance`` registry entry -- not merely delete the directory
    directly, which would leave a stale registry entry behind even though
    nothing remains on disk."""
    from qualification import i2_issuance

    real_write = live_module.write_qualification_pi_config
    captured = []

    def _capturing_write(experiment_root, *, model_id, base_url):
        generated = real_write(experiment_root, model_id=model_id, base_url=base_url)
        captured.append(generated)
        return generated

    monkeypatch.setattr(live_module, "write_qualification_pi_config", _capturing_write)
    result = preflight_config_generator_self_check()
    assert result.passed is True
    assert len(captured) == 1
    generated = captured[0]
    from pathlib import Path as _Path

    assert (
        i2_issuance._lookup_issuance(
            token=generated.authority_token, config_dir=_Path(generated.config_dir)
        )
        is None
    )


def test_preflight_config_generator_self_check_fails_when_cleanup_cannot_be_verified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cleanup that cannot be verified must FAIL this gate -- never
    silently pass."""
    from qualification.i2_cleanup import CleanupResult

    captured = _capture_generated(monkeypatch)

    def _unverified_cleanup(generated):
        return CleanupResult(existed=True, removed=False, verified_by_stat=True)

    monkeypatch.setattr(live_module, "scrub_generated_qualification_config", _unverified_cleanup)
    try:
        result = preflight_config_generator_self_check()
        assert result.passed is False
        assert result.failure_code == "VERIFICATION_FAILED"
    finally:
        # FU4: production correctly RETAINS the tree here.
        for generated in captured:
            _force_release(generated)


# -- L1-FU2: Category-A before Category-B ordering (run_i2b_live.py) --------


def test_all_category_a_gates_pass_before_the_version_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All non-secret gates run, in order, BEFORE
    ``resolve_pi_identity`` -- the one real Node/Pi subprocess this attempt
    ever launches -- and a failed gate causes ZERO calls to it."""
    run_i2b_live = _import_run_i2b_live()
    calls: list[str] = []

    def _tracked_gate_factory(name, passed):
        def _gate():
            calls.append(name)
            from qualification.i2_credentials import PreflightGateResult

            return PreflightGateResult(
                name=name, passed=passed, failure_code=None if passed else "CHECK_FAILED"
            )

        return _gate

    def _tracked_resolve_pi_identity():
        calls.append("resolve_pi_identity")
        raise AssertionError("must never be called before every gate passes")  # pragma: no cover

    monkeypatch.setattr(run_i2b_live, "resolve_pi_identity", _tracked_resolve_pi_identity)
    gates = (
        _tracked_gate_factory("gate_a", True),
        _tracked_gate_factory("gate_b", False),
        _tracked_gate_factory("gate_c", True),
    )
    with pytest.raises(InfrastructureRefusal):
        run_i2b_live._require_all_category_a_gates_pass(gates)
    assert calls == ["gate_a", "gate_b"]


def test_all_category_a_gates_passing_allows_the_version_probe_next(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_i2b_live = _import_run_i2b_live()
    calls: list[str] = []

    def _tracked_gate_factory(name):
        def _gate():
            calls.append(name)
            from qualification.i2_credentials import PreflightGateResult

            return PreflightGateResult(name=name, passed=True)

        return _gate

    gates = (_tracked_gate_factory("gate_a"), _tracked_gate_factory("gate_b"))
    run_i2b_live._require_all_category_a_gates_pass(gates)
    assert calls == ["gate_a", "gate_b"]
# -- FU3 BLOCKER 2: RuntimeIdentity ISSUANCE, not caller fabrication ---------
#
# FU2 removed PATH substitution. It did not remove caller AUTHORSHIP: a
# supported caller could build a ``RuntimeIdentity`` carrying all three
# trusted paths and an entirely fabricated ``reported_version``, and the
# adapter would later publish that fabricated string as
# ``RuntimeLaunchObservation.observed_pi_version``. Version is NOT an
# authorization gate here and never becomes one -- this is an evidence-
# provenance defect, and the fix is an issuance boundary, not a comparison.

FABRICATED_VERSION_IDENTITY = RuntimeIdentity(
    node_executable=SYNTHETIC_IDENTITY.node_executable,
    pi_cli_js=SYNTHETIC_IDENTITY.pi_cli_js,
    pi_package_root=SYNTHETIC_IDENTITY.pi_package_root,
    reported_version="99.99.99-fabricated-by-the-caller",
    launch_shape="node_direct",
)


def test_pre_fix_repro_a_fabricated_version_passes_every_fu2_check(patched) -> None:
    """The pre-fix reproduction, kept as the exact statement of what FU2
    could NOT catch: this object carries a caller-authored version and
    satisfies every FU2-era check -- it is a real ``RuntimeIdentity``, its
    ``launch_shape`` is ``node_direct``, its ``reported_version`` is
    non-empty, and all three executable paths match the trusted resolver
    exactly. FU2 would therefore have accepted it and published the
    fabricated string as evidence."""
    assert type(FABRICATED_VERSION_IDENTITY) is RuntimeIdentity
    live_module._require_runtime_identity_matches_trusted_resolution(
        FABRICATED_VERSION_IDENTITY
    )


def test_a_fabricated_runtime_identity_can_no_longer_authorize_construction(
    patched,
) -> None:
    """...and is now refused, because a bare ``RuntimeIdentity`` -- however
    well-formed -- is not an issuance."""
    with pytest.raises(LiveAdapterError, match="ISSUED by this"):
        _adapters(runtime_identity=FABRICATED_VERSION_IDENTITY)


def test_a_fabricated_runtime_identity_can_no_longer_authorize_a_live_launch(
    run_workspace, patched
) -> None:
    """The same refusal reaches the launch path: with no adapter instance
    there is no ``launch_runtime`` to call, so no fabricated version can
    reach ``RuntimeLaunchObservation.observed_pi_version``."""
    with pytest.raises(LiveAdapterError):
        _adapters(runtime_identity=FABRICATED_VERSION_IDENTITY)
    assert patched.supervisors == []
    assert patched.servers == []


def test_a_genuinely_issued_identity_is_accepted(patched) -> None:
    adapters = _adapters(runtime_identity=_issued())
    assert adapters is not None


def test_issued_runtime_identity_cannot_be_constructed_by_a_caller() -> None:
    """The constructor demands a module-private issuer key object no caller
    can name -- there is no public construction path, and no
    caller-supplied ``trusted=True`` boolean anywhere."""
    with pytest.raises(LiveAdapterError, match="minted"):
        live_module.IssuedRuntimeIdentity(object(), issuance_token="forged-token")
    with pytest.raises(LiveAdapterError, match="minted"):
        live_module.IssuedRuntimeIdentity("issuer", issuance_token="forged-token")
    with pytest.raises(LiveAdapterError, match="minted"):
        live_module.IssuedRuntimeIdentity(None, issuance_token="forged-token")


def test_an_issuance_token_not_in_this_process_registry_is_refused(patched) -> None:
    """Even holding the issuer key, a token this process never issued is
    refused -- the registry, not the object, is the authority."""
    unregistered = live_module.IssuedRuntimeIdentity(
        live_module._IDENTITY_ISSUER_KEY, issuance_token="never-issued-0001"
    )
    with pytest.raises(LiveAdapterError, match="issuance registry"):
        _adapters(runtime_identity=unregistered)
    with pytest.raises(LiveAdapterError, match="issuance registry"):
        unregistered.node_executable


def test_the_issued_object_carries_no_identity_data_of_its_own() -> None:
    """There is nothing on the object for a caller to author: it holds only
    an opaque token, and every identity fact is read back from the
    registry."""
    issued = _issued()
    assert issued.__slots__ == ("_issuance_token",)
    assert not hasattr(issued, "__dict__")
    assert issued.node_executable == SYNTHETIC_IDENTITY.node_executable


def test_the_issued_object_repr_leaks_no_token_and_no_path() -> None:
    issued = _issued()
    rendered = repr(issued) + str(issued)
    assert issued._issuance_token not in rendered
    assert SYNTHETIC_IDENTITY.node_executable not in rendered
    assert SYNTHETIC_IDENTITY.pi_package_root not in rendered


def test_an_issuance_is_one_shot_and_cannot_be_replayed_into_a_second_run(
    patched,
) -> None:
    """Adversarial item 5: one ``--version`` probe authorizes exactly ONE
    live attempt. Re-presenting the same issuance to a second adapter --
    i.e. a second run reusing the first run's probe -- is refused."""
    issued = _issued()
    first = _adapters(runtime_identity=issued)
    assert first is not None
    with pytest.raises(LiveAdapterError, match="already consumed"):
        _adapters(runtime_identity=issued)


def test_a_refused_construction_still_burns_its_issuance(patched) -> None:
    """The claim happens before any further validation, so a construction
    that is then refused can never re-present the same probe's authority."""
    from dataclasses import replace

    issued = _issued(replace(SYNTHETIC_IDENTITY, node_executable=r"C:\attacker\node.exe"))
    with pytest.raises(LiveAdapterError, match="trusted resolver path exactly"):
        _adapters(runtime_identity=issued)
    with pytest.raises(LiveAdapterError, match="already consumed"):
        _adapters(runtime_identity=issued)


def test_the_adapter_uses_the_registry_identity_not_the_presented_object(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The identity a live attempt runs on is read out of the issuance
    registry, so ``observed_pi_version`` is exactly what the issuing probe
    recorded."""
    from dataclasses import replace

    issued = _issued(replace(SYNTHETIC_IDENTITY, reported_version="0.84.3-issued"))
    adapters = _adapters(runtime_identity=issued)
    request = _launch_request_with_registered_broker(adapters, run_workspace, run_id="run-fu3-1")

    def _make_supervisor(*, argv, cwd, environment, bounds):
        supervisor = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        supervisor.responses["h1"] = (
            RUNTIME_RESPONSE_RECEIVED,
            _successful_get_commands_response(run_workspace),
        )
        patched.supervisors.append(supervisor)
        return supervisor

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)
    observation = adapters.launch_runtime(request)
    assert observation.observed_pi_version == "0.84.3-issued"
    # child-environment PATH narrowing uses that exact issued node executable
    assert issued.node_executable == SYNTHETIC_IDENTITY.node_executable
    assert observation.session is not None


def test_a_differing_real_observed_version_is_still_permitted(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No exact-version pinning is reintroduced: two genuinely issued
    identities reporting DIFFERENT real versions are both accepted."""
    from dataclasses import replace

    for version in ("0.84.3", "1.2.3", "0.90.0-rc1"):
        adapters = _adapters(
            runtime_identity=_issued(replace(SYNTHETIC_IDENTITY, reported_version=version))
        )
        assert adapters is not None


def test_reported_version_is_never_compared_to_anything() -> None:
    """Adversarial item 7, source-level: ``reported_version`` is read for
    non-emptiness and recorded, and is NEVER an operand of any comparison --
    equality, ordering or membership. Version never becomes an
    authorization gate here, and no exact-version pinning can creep back."""
    tree = ast.parse(inspect.getsource(live_module))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        operands = [node.left, *node.comparators]
        mentioned: set[str] = set()
        for operand in operands:
            for inner in ast.walk(operand):
                if isinstance(inner, ast.Attribute):
                    mentioned.add(inner.attr)
                elif isinstance(inner, ast.Name):
                    mentioned.add(inner.id)
        assert "reported_version" not in mentioned, ast.dump(node)


def test_exactly_one_version_probe_is_attributable_to_one_live_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Adversarial item 6: the probe runs exactly once, inside the trusted
    issuing operation, and issues exactly one identity. NOTHING here runs a
    real subprocess -- ``subprocess.run`` is replaced."""
    import subprocess as _subprocess

    probes: list[tuple] = []

    class _Completed:
        returncode = 0
        stdout = b"0.84.3\n"
        stderr = b""

    def _fake_run(argv, **kwargs):
        probes.append(tuple(argv))
        return _Completed()

    monkeypatch.setattr(_subprocess, "run", _fake_run)
    monkeypatch.setattr(
        live_module, "_ar2_resolve_node_executable", lambda: SYNTHETIC_IDENTITY.node_executable
    )
    monkeypatch.setattr(
        live_module, "_ar2_resolve_pi_package_root", lambda: SYNTHETIC_IDENTITY.pi_package_root
    )
    monkeypatch.setattr(live_module.os.path, "isfile", lambda path: True)

    before = len(live_module._ISSUED_RUNTIME_IDENTITIES)
    issued = live_module.resolve_pi_identity()

    assert len(probes) == 1
    assert probes[0][-1] == "--version"
    assert type(issued) is live_module.IssuedRuntimeIdentity
    assert len(live_module._ISSUED_RUNTIME_IDENTITIES) == before + 1


def test_no_second_hidden_version_probe_exists_in_this_module() -> None:
    """``subprocess`` is named in exactly ONE function -- the issuing probe
    -- so there is no second, hidden probe anywhere, at launch or
    elsewhere."""
    tree = ast.parse(inspect.getsource(live_module))
    probing = sorted(
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and "subprocess" in {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
    )
    assert probing == ["resolve_pi_identity"]


def test_resolve_pi_identity_returns_an_issuance_not_a_bare_identity() -> None:
    """Source-level: the trusted probe hands back an issuance, so no caller
    ever receives a raw ``RuntimeIdentity`` it could edit and re-present."""
    signature = inspect.signature(live_module.resolve_pi_identity)
    assert signature.return_annotation == "IssuedRuntimeIdentity"


def test_no_caller_supplied_trust_boolean_or_hash_is_accepted() -> None:
    """The issuance boundary is mechanical: no ``trusted=`` flag, no
    caller-supplied version/digest accepted as provenance proof."""
    parameters = tuple(inspect.signature(LiveCategoryBAdapters.__init__).parameters)
    assert parameters == ("self", "environ_reader", "runtime_identity", "experiment_id", "bounds")
    issue_parameters = tuple(inspect.signature(live_module._issue_runtime_identity).parameters)
    assert issue_parameters == ("identity",)


# -- FU3 BLOCKER 3: generated-config self-check cleanup ownership ------------
#
# Once ``write_qualification_pi_config`` returns a
# ``GeneratedQualificationConfig``, the OFFICIAL qualification cleanup path
# owns cleanup on EVERY later exit -- success and failure alike. A raw
# ``shutil.rmtree`` deletes files without discarding the process-local
# ``i2_issuance`` record, so it may never substitute for the discard, and a
# FAILED preflight must leave no stale issuance authority behind either.


def _issuance_live(generated) -> bool:
    """True while the process-local issuance record still exists."""
    from pathlib import Path as _Path

    from qualification import i2_issuance

    return (
        i2_issuance._lookup_issuance(
            token=generated.authority_token, config_dir=_Path(generated.config_dir)
        )
        is not None
    )


def _capture_generated(monkeypatch, *, fail_on_call: int | None = None):
    """Capture every ``GeneratedQualificationConfig`` a producer issues, and
    optionally make the Nth generation itself fail."""
    real_write = live_module.write_qualification_pi_config
    captured = []

    def _capturing_write(experiment_root, *, model_id, base_url):
        if fail_on_call is not None and len(captured) + 1 == fail_on_call:
            raise live_module.QualificationPiConfigError(
                "config error: synthetic generation failure"
            )
        generated = real_write(experiment_root, model_id=model_id, base_url=base_url)
        captured.append(generated)
        return generated

    monkeypatch.setattr(live_module, "write_qualification_pi_config", _capturing_write)
    return captured


def _count_official_cleanups(monkeypatch):
    """Count calls to the official cleanup path, per generated object."""
    real_scrub = live_module.scrub_generated_qualification_config
    calls = []

    def _counting_scrub(generated):
        calls.append(generated.authority_token)
        return real_scrub(generated)

    monkeypatch.setattr(live_module, "scrub_generated_qualification_config", _counting_scrub)
    return calls


SELF_CHECK_GENERATORS = (
    ("config_generator_self_check", preflight_config_generator_self_check, 1),
    ("child_environment_builder_self_check", preflight_child_environment_builder_self_check, 1),
    ("candidate_route_generator_symmetry", preflight_candidate_route_generator_symmetry, 2),
)


def test_every_generating_self_check_producer_is_audited() -> None:
    """The audit itself: EXACTLY these three Category-A producers call
    ``write_qualification_pi_config``. A new generating producer added later
    fails this test until it is added to
    :data:`SELF_CHECK_GENERATORS` and covered by the ownership regressions
    below."""
    def _calls_the_generator(node) -> bool:
        return any(
            isinstance(inner, ast.Call)
            and isinstance(inner.func, ast.Name)
            and inner.func.id == "write_qualification_pi_config"
            for inner in ast.walk(node)
        )

    generating = sorted(
        node.name
        for node in ast.walk(ast.parse(inspect.getsource(live_module)))
        if isinstance(node, ast.FunctionDef) and _calls_the_generator(node)
    )
    assert generating == [
        "preflight_candidate_route_generator_symmetry",
        "preflight_child_environment_builder_self_check",
        "preflight_config_generator_self_check",
    ]
    assert sorted(name for name, _, _ in SELF_CHECK_GENERATORS) == [
        "candidate_route_generator_symmetry",
        "child_environment_builder_self_check",
        "config_generator_self_check",
    ]


@pytest.mark.parametrize(("name", "producer", "expected"), SELF_CHECK_GENERATORS)
def test_success_path_leaves_no_issuance(
    name, producer, expected, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = _capture_generated(monkeypatch)
    cleanups = _count_official_cleanups(monkeypatch)
    result = producer()

    assert result.passed is True
    assert len(captured) == expected
    for generated in captured:
        assert _issuance_live(generated) is False
        assert cleanups.count(generated.authority_token) == 1


@pytest.mark.parametrize(("name", "producer", "expected"), SELF_CHECK_GENERATORS)
def test_official_cleanup_failure_fails_the_gate(
    name, producer, expected, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cleanup that cannot be VERIFIED fails the preflight -- a raw parent
    delete afterwards can never make the gate appear passed (adversarial
    item 10)."""
    from qualification.i2_cleanup import CleanupResult

    captured = _capture_generated(monkeypatch)
    monkeypatch.setattr(
        live_module,
        "scrub_generated_qualification_config",
        lambda generated: CleanupResult(existed=True, removed=False, verified_by_stat=True),
    )
    try:
        result = producer()
        assert result.passed is False
        assert result.failure_code == "VERIFICATION_FAILED"
    finally:
        # FU4: production correctly RETAINS the tree here, so this offline
        # test owns completing the authorized cleanup itself.
        for generated in captured:
            _force_release(generated)


@pytest.mark.parametrize(("name", "producer", "expected"), SELF_CHECK_GENERATORS)
def test_official_cleanup_raising_fails_the_gate_and_never_escapes(
    name, producer, expected, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = _capture_generated(monkeypatch)

    def _raising_scrub(generated):
        raise RuntimeError("synthetic cleanup failure")

    monkeypatch.setattr(live_module, "scrub_generated_qualification_config", _raising_scrub)
    try:
        result = producer()
        assert result.passed is False
        assert result.failure_code == "VERIFICATION_FAILED"
    finally:
        for generated in captured:
            _force_release(generated)


def test_config_generator_self_check_failure_after_generation_leaves_no_issuance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pre-fix defect, per producer: the post-generation failure branch
    raw-deleted the parent and left the issuance record live."""
    captured = _capture_generated(monkeypatch)
    cleanups = _count_official_cleanups(monkeypatch)

    def _failing_verify(**kwargs):
        raise live_module.QualificationPiConfigError("config error: synthetic verify failure")

    monkeypatch.setattr(live_module, "verify_generated_config_integrity", _failing_verify)
    result = preflight_config_generator_self_check()

    assert result.passed is False
    assert result.failure_code == "VERIFICATION_FAILED"
    assert len(captured) == 1
    assert _issuance_live(captured[0]) is False
    assert cleanups.count(captured[0].authority_token) == 1


def test_child_environment_builder_failure_after_generation_leaves_no_issuance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _capture_generated(monkeypatch)
    cleanups = _count_official_cleanups(monkeypatch)

    def _failing_builder(**kwargs):
        raise live_module.EnvironmentPolicyError("environment error: synthetic builder failure")

    monkeypatch.setattr(live_module, "build_child_environment", _failing_builder)
    result = preflight_child_environment_builder_self_check()

    assert result.passed is False
    assert result.failure_code == "VERIFICATION_FAILED"
    assert len(captured) == 1
    assert _issuance_live(captured[0]) is False
    assert cleanups.count(captured[0].authority_token) == 1


def test_symmetry_validation_failure_after_both_were_issued_cleans_both(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Adversarial item 9: two issued configs, validation failing after BOTH
    exist -- neither issuance may survive."""
    real_write = live_module.write_qualification_pi_config
    captured = []

    def _tampering_write(experiment_root, *, model_id, base_url):
        generated = real_write(experiment_root, model_id=model_id, base_url=base_url)
        captured.append(generated)
        if len(captured) == 2:
            from pathlib import Path as _Path

            settings_path = _Path(generated.settings_path)
            text = settings_path.read_text(encoding="utf-8")
            settings_path.write_text(
                text.replace('"quietStartup": true', '"quietStartup": false'), encoding="utf-8"
            )
        return generated

    monkeypatch.setattr(live_module, "write_qualification_pi_config", _tampering_write)
    cleanups = _count_official_cleanups(monkeypatch)
    result = preflight_candidate_route_generator_symmetry()

    assert result.passed is False
    assert len(captured) == 2
    for generated in captured:
        assert _issuance_live(generated) is False
        assert cleanups.count(generated.authority_token) == 1


def test_symmetry_second_generation_failure_still_cleans_the_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """First generation succeeded, second raised: the first issuance must
    still be discarded, and no cleanup is attempted for an object that never
    existed."""
    captured = _capture_generated(monkeypatch, fail_on_call=2)
    cleanups = _count_official_cleanups(monkeypatch)
    result = preflight_candidate_route_generator_symmetry()

    assert result.passed is False
    assert result.failure_code == "VERIFICATION_FAILED"
    assert len(captured) == 1
    assert _issuance_live(captured[0]) is False
    assert cleanups == [captured[0].authority_token]


def test_symmetry_first_generation_failure_attempts_no_cleanup_at_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generation failing BEFORE returning an object is the one case with
    nothing to clean -- no official cleanup is attempted, and no fake one is
    manufactured for uniformity."""
    captured = _capture_generated(monkeypatch, fail_on_call=1)
    cleanups = _count_official_cleanups(monkeypatch)
    result = preflight_candidate_route_generator_symmetry()

    assert result.passed is False
    assert captured == []
    assert cleanups == []


@pytest.mark.parametrize(("name", "producer", "expected"), SELF_CHECK_GENERATORS)
def test_no_double_official_cleanup(
    name, producer, expected, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = _capture_generated(monkeypatch)
    cleanups = _count_official_cleanups(monkeypatch)
    producer()
    assert len(cleanups) == len(set(cleanups)) == expected == len(captured)


def test_raw_rmtree_never_precedes_the_official_cleanup_in_any_producer() -> None:
    """Source-level ordering AND guarding: in every generating producer the
    official release runs before the throwaway parent's raw delete, and
    (FU4 BLOCKER 1) every raw delete is GUARDED by that release's own
    ``throwaway_parent_may_be_removed`` -- never unconditional."""
    for producer in (
        live_module.preflight_config_generator_self_check,
        live_module.preflight_child_environment_builder_self_check,
        live_module.preflight_candidate_route_generator_symmetry,
    ):
        source = inspect.getsource(producer)
        body = source.split('"""')[-1]
        expected = 2 if producer.__name__.endswith("symmetry") else 1
        assert body.count("shutil.rmtree") == expected
        assert body.count("_release_generated_self_check_config") == expected
        assert body.count("throwaway_parent_may_be_removed") == expected
        assert body.index("_release_generated_self_check_config") < body.index("shutil.rmtree")
        # every raw delete is the guarded body of an `if ...may_be_removed:`
        for line in body.splitlines():
            if "shutil.rmtree" not in line:
                continue
            guard = body.splitlines()[body.splitlines().index(line) - 1]
            assert "throwaway_parent_may_be_removed" in guard


def test_no_production_code_touches_the_issuance_registry_globals() -> None:
    """Production code never reaches into ``i2_issuance``'s private globals
    (prose mentions in docstrings are not code); cleanup goes through the
    official path, which owns the discard."""
    identifiers = _identifiers_used_in_code()
    assert "i2_issuance" not in identifiers
    assert "_discard_issuance" not in identifiers
    assert "_lookup_issuance" not in identifiers
    assert "_REGISTRY" not in identifiers
def test_the_whole_category_a_gate_sequence_leaves_no_issuance_behind() -> None:
    """End to end over the exact eight-gate tuple ``run_i2b_live.py`` runs
    before the version probe: after every Category-A gate has passed, the
    process-local issuance registry holds nothing new. Nothing here reads a
    credential, launches a process, or opens a pipe."""
    from qualification import i2_issuance

    run_i2b_live = _import_run_i2b_live()
    before = dict(i2_issuance._REGISTRY)

    gates = (
        preflight_pi_installed_offline,
        preflight_config_generator_self_check,
        preflight_child_environment_builder_self_check,
        preflight_candidate_route_generator_symmetry,
        preflight_planned_cli_argv_shape,
        preflight_artifact_safety_scrub_self_check,
        preflight_config_generator_no_credential_literal_path,
        lambda: preflight_environment_forbidden_fragment_audit(ambient_environ={"SystemRoot": "X"}),
    )
    run_i2b_live._require_all_category_a_gates_pass(gates)

    assert dict(i2_issuance._REGISTRY) == before


def test_a_failing_category_a_gate_also_leaves_no_issuance_behind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same fact on the FAILURE side, which is the defect FU3 closes: a
    preflight that fails after a config was generated must leave no stale
    issuance authority in this process either."""
    from qualification import i2_issuance

    before = dict(i2_issuance._REGISTRY)

    def _failing_verify(**kwargs):
        raise live_module.QualificationPiConfigError("config error: synthetic verify failure")

    monkeypatch.setattr(live_module, "verify_generated_config_integrity", _failing_verify)
    result = preflight_config_generator_self_check()

    assert result.passed is False
    assert dict(i2_issuance._REGISTRY) == before
# -- FU4 BLOCKER 1: an UNVERIFIED release must strand nothing ----------------
#
# The frozen cleanup primitive deliberately RETAINS the process-local
# issuance when it could not verify removal, precisely because the directory
# still exists and a future authorized cleanup must remain possible. FU3's
# unconditional raw ``shutil.rmtree`` of the throwaway parent therefore
# destroyed the path while leaving the issuance live -- reintroducing the
# stale-authority class one line after eliminating it. Every test below
# asserts the corrected coupling: path and issuance live or die together.


def _config_dir_exists(generated) -> bool:
    return os.path.isdir(generated.config_dir)


def _throwaway_parent(generated) -> str:
    """``write_qualification_pi_config`` creates ``<experiment_root>/
    i2_pi_config`` (``i2_pi_config.py``), so the throwaway parent these
    producers ``mkdtemp``'d is exactly the config directory's parent."""
    from pathlib import Path as _Path

    return str(_Path(generated.config_dir).parent)


def _parent_exists(generated) -> bool:
    return os.path.isdir(_throwaway_parent(generated))


def _force_release(generated) -> None:
    """Test-owned teardown for the failure-only paths where production code
    correctly leaves the tree in place: complete the authorized cleanup with
    the REAL (never monkeypatched) primitive, then remove the throwaway
    parent, so this offline suite leaves neither a temp tree nor a stale
    issuance behind."""
    import shutil as _shutil

    from qualification.i2_cleanup import scrub_generated_qualification_config as _real

    parent = _throwaway_parent(generated)
    try:
        _real(generated)
    except Exception:  # pragma: no cover - teardown must never fail a test
        pass
    _shutil.rmtree(parent, ignore_errors=True)


def _fail_after_generation_in_config_generator(monkeypatch) -> None:
    def _failing_verify(**kwargs):
        raise live_module.QualificationPiConfigError("config error: synthetic verify failure")

    monkeypatch.setattr(live_module, "verify_generated_config_integrity", _failing_verify)


def _fail_after_generation_in_child_environment(monkeypatch) -> None:
    def _failing_builder(**kwargs):
        raise live_module.EnvironmentPolicyError("environment error: synthetic builder failure")

    monkeypatch.setattr(live_module, "build_child_environment", _failing_builder)


def _fail_after_generation_in_symmetry(monkeypatch) -> None:
    """Tamper candidate B's settings.json AFTER both genuine writes, so the
    field-by-field comparison fails with both objects already issued."""
    real_write = live_module.write_qualification_pi_config
    seen = {"n": 0}

    def _tampering_write(experiment_root, *, model_id, base_url):
        generated = real_write(experiment_root, model_id=model_id, base_url=base_url)
        seen["n"] += 1
        if seen["n"] == 2:
            from pathlib import Path as _Path

            settings_path = _Path(generated.settings_path)
            text = settings_path.read_text(encoding="utf-8")
            settings_path.write_text(
                text.replace('"quietStartup": true', '"quietStartup": false'), encoding="utf-8"
            )
        return generated

    monkeypatch.setattr(live_module, "write_qualification_pi_config", _tampering_write)


GENERATING_PRODUCERS = (
    (
        "config_generator_self_check",
        preflight_config_generator_self_check,
        1,
        _fail_after_generation_in_config_generator,
    ),
    (
        "child_environment_builder_self_check",
        preflight_child_environment_builder_self_check,
        1,
        _fail_after_generation_in_child_environment,
    ),
    (
        "candidate_route_generator_symmetry",
        preflight_candidate_route_generator_symmetry,
        2,
        _fail_after_generation_in_symmetry,
    ),
)


@pytest.mark.parametrize(("name", "producer", "count", "inject"), GENERATING_PRODUCERS)
def test_release_case_a_success_removes_issuance_config_and_parent(
    name, producer, count, inject, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Case A: the official release VERIFIED, so the issuance is discarded,
    the generated tree is verified absent, and only THEN may the throwaway
    parent be raw-deleted."""
    captured = _capture_generated(monkeypatch)
    result = producer()

    assert result.passed is True
    assert len(captured) == count
    for generated in captured:
        assert _issuance_live(generated) is False
        assert _config_dir_exists(generated) is False
        assert _parent_exists(generated) is False


@pytest.mark.parametrize(("name", "producer", "count", "inject"), GENERATING_PRODUCERS)
def test_release_post_generation_failure_with_verified_cleanup_still_releases(
    name, producer, count, inject, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A post-generation VALIDATION failure whose official cleanup then
    verifies: the gate fails for the original reason, and nothing is
    stranded -- issuance discarded, config tree gone, parent removable."""
    captured = _capture_generated(monkeypatch)
    inject(monkeypatch)
    result = producer()

    assert result.passed is False
    assert result.failure_code == "VERIFICATION_FAILED"
    assert len(captured) == count
    for generated in captured:
        assert _issuance_live(generated) is False
        assert _config_dir_exists(generated) is False
        assert _parent_exists(generated) is False


@pytest.mark.parametrize(("name", "producer", "count", "inject"), GENERATING_PRODUCERS)
def test_release_case_c_unverified_cleanup_never_raw_deletes_the_retained_tree(
    name, producer, count, inject, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Case C, the FU4 defect: the official cleanup returned
    ``scrub_verified=False``, so the frozen primitive RETAINED the issuance.
    The gate fails, and the generated tree AND its throwaway parent must
    both survive -- an issuance may never be left pointing at a path this
    module deleted behind its back."""
    from qualification.i2_cleanup import CleanupResult

    captured = _capture_generated(monkeypatch)
    monkeypatch.setattr(
        live_module,
        "scrub_generated_qualification_config",
        lambda generated: CleanupResult(existed=True, removed=False, verified_by_stat=True),
    )
    result = producer()

    assert result.passed is False
    assert result.failure_code == "VERIFICATION_FAILED"
    assert len(captured) == count
    try:
        for generated in captured:
            assert _issuance_live(generated) is True
            assert _config_dir_exists(generated) is True
            assert _parent_exists(generated) is True
    finally:
        for generated in captured:
            _force_release(generated)


@pytest.mark.parametrize(("name", "producer", "count", "inject"), GENERATING_PRODUCERS)
def test_release_case_c_raising_cleanup_never_raw_deletes_beneath_the_issuance(
    name, producer, count, inject, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Case C via the primitive RAISING: identical ownership answer. The
    gate fails and nothing beneath the retained issuance is deleted."""
    captured = _capture_generated(monkeypatch)

    def _raising_scrub(generated):
        raise RuntimeError("synthetic cleanup failure")

    monkeypatch.setattr(live_module, "scrub_generated_qualification_config", _raising_scrub)
    result = producer()

    assert result.passed is False
    assert result.failure_code == "VERIFICATION_FAILED"
    assert len(captured) == count
    try:
        for generated in captured:
            assert _issuance_live(generated) is True
            assert _config_dir_exists(generated) is True
            assert _parent_exists(generated) is True
    finally:
        for generated in captured:
            _force_release(generated)


def _selective_scrub(monkeypatch, *, fail_for_model_id: str):
    """Make the official cleanup fail for exactly ONE of the two symmetry
    configs, keyed by its model id."""
    from qualification.i2_cleanup import CleanupResult
    from qualification.i2_cleanup import scrub_generated_qualification_config as _real

    def _scrub(generated):
        if generated.model_id == fail_for_model_id:
            return CleanupResult(existed=True, removed=False, verified_by_stat=True)
        return _real(generated)

    monkeypatch.setattr(live_module, "scrub_generated_qualification_config", _scrub)


@pytest.mark.parametrize("failing", ["A", "B"])
def test_symmetry_mixed_release_outcomes_are_decided_per_object(
    failing, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FU4: one aggregate cleanup bool must never decide whether BOTH
    parents are raw-deleted. The RELEASED config's issuance, tree and parent
    all go; the RETAINED config keeps all three."""
    captured = _capture_generated(monkeypatch)
    failing_model_id = live_module._CANDIDATE_MODEL_IDS[failing]
    _selective_scrub(monkeypatch, fail_for_model_id=failing_model_id)
    result = preflight_candidate_route_generator_symmetry()

    assert result.passed is False
    assert result.failure_code == "VERIFICATION_FAILED"
    assert len(captured) == 2
    retained = [g for g in captured if g.model_id == failing_model_id]
    released = [g for g in captured if g.model_id != failing_model_id]
    assert len(retained) == len(released) == 1
    try:
        assert _issuance_live(released[0]) is False
        assert _config_dir_exists(released[0]) is False
        assert _parent_exists(released[0]) is False

        assert _issuance_live(retained[0]) is True
        assert _config_dir_exists(retained[0]) is True
        assert _parent_exists(retained[0]) is True
    finally:
        _force_release(retained[0])


def test_symmetry_second_generation_failure_releases_the_first_and_strands_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FU4 case B alongside case A: the first config was issued and is
    released exactly once; the second never returned an object, so there is
    no issuance and no cleanup for it, and both parent decisions stay
    truthful."""
    captured = _capture_generated(monkeypatch, fail_on_call=2)
    cleanups = _count_official_cleanups(monkeypatch)
    result = preflight_candidate_route_generator_symmetry()

    assert result.passed is False
    assert result.failure_code == "VERIFICATION_FAILED"
    assert len(captured) == 1
    assert cleanups == [captured[0].authority_token]
    assert _issuance_live(captured[0]) is False
    assert _config_dir_exists(captured[0]) is False
    assert _parent_exists(captured[0]) is False


def test_release_record_states_are_exactly_three_and_never_overlap() -> None:
    """The release record's own decision table, stated once: only a
    generated-and-VERIFIED release lets the gate pass and the parent go, and
    "nothing generated" is a distinct history from "generated and
    released"."""
    release = live_module._GeneratedConfigRelease

    no_object = release(
        generated_object_existed=False, cleanup_attempted=False, cleanup_verified=False
    )
    verified = release(
        generated_object_existed=True, cleanup_attempted=True, cleanup_verified=True
    )
    retained = release(
        generated_object_existed=True, cleanup_attempted=True, cleanup_verified=False
    )

    assert (no_object.gate_ok, no_object.throwaway_parent_may_be_removed) == (True, True)
    assert no_object.issuance_outstanding is False
    assert (verified.gate_ok, verified.throwaway_parent_may_be_removed) == (True, True)
    assert verified.issuance_outstanding is False
    assert (retained.gate_ok, retained.throwaway_parent_may_be_removed) == (False, False)
    assert retained.issuance_outstanding is True


def test_the_release_helper_never_touches_issuance_internals_or_retries_raw() -> None:
    """Case C uses no ``i2_issuance`` discard, no registry mutation, and no
    second unreviewed raw delete."""
    body = inspect.getsource(live_module._release_generated_self_check_config).split('"""')[-1]
    for forbidden in ("i2_issuance", "_discard_issuance", "_REGISTRY", "rmtree", "unlink"):
        assert forbidden not in body


# -- FU4 BLOCKER 2: workspace ownership starts at the mint -------------------


class _FakeRunWorkspace:
    """The narrowest stand-in for a minted ``QualificationRunWorkspace``:
    only what ``_run_outer_cleanup`` reads. Never a real workspace."""

    def __init__(self, experiment_root: str) -> None:
        self.experiment_root = experiment_root
        self.workspace_root = experiment_root


def _stubbed_harness(monkeypatch, tmp_path, *, removal_raises=None, removal_returns=None):
    """Install a fully offline ``run_i2b_live`` harness: passing Category-A
    gates, an issued identity from a replaced probe, a synthetic workspace,
    and a counting ``remove_run_workspace``. No credential, no process, no
    pipe, no real workspace.

    ``removal_returns``, when given (and ``removal_raises`` is ``None``),
    is returned in place of the real removal's own return value -- this is
    how L1-FU5's mandatory regressions drive a NORMAL (non-raising) return
    that is not the frozen success shape. Absent both, the stub performs a
    real ``shutil.rmtree`` and returns the exact frozen
    ``ar2.fixtures.remove_disposable_tree`` success shape, so every
    pre-existing test in this harness that expects
    ``workspace_removal_verified is True`` keeps observing a genuinely
    valid frozen success dict rather than an untyped ``None``."""
    run_i2b_live = _import_run_i2b_live()

    for gate in (
        "preflight_pi_installed_offline",
        "preflight_config_generator_self_check",
        "preflight_child_environment_builder_self_check",
        "preflight_candidate_route_generator_symmetry",
        "preflight_planned_cli_argv_shape",
        "preflight_artifact_safety_scrub_self_check",
        "preflight_config_generator_no_credential_literal_path",
    ):
        monkeypatch.setattr(
            run_i2b_live,
            gate,
            (lambda name: lambda: PreflightGateResult(name=name, passed=True))(gate),
        )
    monkeypatch.setattr(
        run_i2b_live,
        "preflight_environment_forbidden_fragment_audit",
        lambda *, ambient_environ: PreflightGateResult(name="env_audit", passed=True),
    )

    probes: list[int] = []

    def _issue_identity():
        probes.append(1)
        return live_module._issue_runtime_identity(SYNTHETIC_IDENTITY)

    monkeypatch.setattr(run_i2b_live, "resolve_pi_identity", _issue_identity)
    monkeypatch.setattr(run_i2b_live, "resolve_git_executable", lambda *, workspace_root: None)

    workspace_dir = tmp_path / "synthetic-run-workspace"
    workspace_dir.mkdir()
    workspace = _FakeRunWorkspace(str(workspace_dir))
    monkeypatch.setattr(run_i2b_live, "mint_qualification_run_workspace", lambda: workspace)

    removals: list[object] = []

    def _remove(run_workspace):
        removals.append(run_workspace)
        if removal_raises is not None:
            raise removal_raises
        if removal_returns is not None:
            return removal_returns
        import shutil as _shutil

        _shutil.rmtree(run_workspace.experiment_root, ignore_errors=True)
        return {"removed": True, "residual_file_count": 0, "verified": True}

    monkeypatch.setattr(run_i2b_live, "remove_run_workspace", _remove)
    return SimpleNamespace(
        module=run_i2b_live, workspace=workspace, removals=removals, probes=probes
    )


def test_adapter_construction_failure_after_mint_still_cleans_the_workspace(
    patched, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """FU4 BLOCKER 2, the reproduction: a SUPPORTED fail-closed constructor
    refusal (the frozen extension source/digest check) used to strand the
    minted qualification workspace, because the constructor sat outside the
    ownership scope's ``try``. Outer cleanup now runs exactly once."""
    harness = _stubbed_harness(monkeypatch, tmp_path)
    monkeypatch.setattr(live_module, "_FROZEN_AR2_EXTENSION_SHA256", "0" * 64)

    with pytest.raises(harness.module.PreControllerRefusal) as caught:
        harness.module.run_one_category_b_live_attempt(candidate="A")

    refusal = caught.value
    assert refusal.stage == harness.module.STAGE_ADAPTER_CONSTRUCTION
    assert refusal.failure_type == "LiveAdapterError"
    assert len(harness.removals) == 1
    assert harness.removals[0] is harness.workspace


def test_adapter_construction_failure_leaves_no_workspace_when_removal_succeeds(
    patched, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    harness = _stubbed_harness(monkeypatch, tmp_path)
    monkeypatch.setattr(live_module, "_FROZEN_AR2_EXTENSION_SHA256", "0" * 64)

    with pytest.raises(harness.module.PreControllerRefusal) as caught:
        harness.module.run_one_category_b_live_attempt(candidate="A")

    assert os.path.isdir(harness.workspace.experiment_root) is False
    cleanup = caught.value.outer_cleanup
    assert cleanup["workspace_removal_attempted"] is True
    assert cleanup["workspace_removal_verified"] is True
    assert cleanup["outer_cleanup_verified"] is True


def test_adapter_construction_failure_reports_a_failed_removal_truthfully(
    patched, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """The primary constructor refusal stays primary, and the outer cleanup
    failure is reported alongside it -- never swallowed, and never allowed
    to replace the primary failure."""
    harness = _stubbed_harness(
        monkeypatch, tmp_path, removal_raises=OSError("synthetic removal failure")
    )
    monkeypatch.setattr(live_module, "_FROZEN_AR2_EXTENSION_SHA256", "0" * 64)

    with pytest.raises(harness.module.PreControllerRefusal) as caught:
        harness.module.run_one_category_b_live_attempt(candidate="A")

    refusal = caught.value
    assert refusal.failure_type == "LiveAdapterError"  # primary, unchanged
    assert refusal.stage == harness.module.STAGE_ADAPTER_CONSTRUCTION
    assert len(harness.removals) == 1
    assert refusal.outer_cleanup["workspace_removal_attempted"] is True
    assert refusal.outer_cleanup["workspace_removal_verified"] is False
    assert refusal.outer_cleanup["outer_cleanup_verified"] is False


def test_the_pre_controller_refusal_record_is_bounded_and_secret_free(
    patched, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """No exception text, runtime path, endpoint or token -- only the
    failing class NAME, the stage, the cleanup facts, and the zero-prompt
    fact. No controller result is fabricated."""
    harness = _stubbed_harness(monkeypatch, tmp_path)
    monkeypatch.setattr(live_module, "_FROZEN_AR2_EXTENSION_SHA256", "0" * 64)

    with pytest.raises(harness.module.PreControllerRefusal) as caught:
        harness.module.run_one_category_b_live_attempt(candidate="A")

    record = caught.value.as_refusal_record()
    assert record["refused"] is True
    assert record["reason"] == "LiveAdapterError"
    assert record["semantic_prompts_sent"] == 0
    assert record["controller_entered"] is False
    assert record["outer_cleanup"] is not None
    assert "outcome" not in record and "gate_statuses" not in record

    rendered = json.dumps(record)
    assert "does not match its authorized digest" not in rendered
    assert harness.workspace.experiment_root not in rendered
    assert SYNTHETIC_API_KEY not in rendered
    assert SYNTHETIC_BASE_URL not in rendered
    assert SYNTHETIC_IDENTITY.node_executable not in rendered


def test_controller_exception_after_construction_still_cleans_up_exactly_once(
    patched, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """The constructor succeeded and the controller itself raised: the
    ownership scope still runs outer cleanup exactly once. L1-FU5 nearby
    gap fix: the raw controller exception no longer propagates bare (that
    used to silently lose the cleanup truth, discarded as an unused local
    in ``finally``) -- it is reduced to a bounded
    ``PostControllerExceptionalFailure`` whose own record carries the
    cleanup facts alongside the primary failure."""
    harness = _stubbed_harness(monkeypatch, tmp_path)

    def _raising_controller(**kwargs):
        raise RuntimeError("synthetic controller failure")

    monkeypatch.setattr(harness.module, "run_category_b_controller", _raising_controller)

    with pytest.raises(harness.module.PostControllerExceptionalFailure) as caught:
        harness.module.run_one_category_b_live_attempt(candidate="A")

    assert len(harness.removals) == 1
    assert caught.value.stage == harness.module.STAGE_CONTROLLER_EXECUTION
    assert caught.value.failure_type == "RuntimeError"
    assert caught.value.outer_cleanup is not None


def test_result_processing_failure_inside_the_scope_still_cleans_up_once(
    patched, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Result processing lives INSIDE the ownership scope too, so a failure
    there cannot strand the workspace either. L1-FU5 nearby gap fix: same
    bounded reduction as the controller-exception case above, tagged with
    the result-processing stage."""
    harness = _stubbed_harness(monkeypatch, tmp_path)
    monkeypatch.setattr(
        harness.module, "run_category_b_controller", lambda **kwargs: object()
    )

    def _raising_summary(result):
        raise RuntimeError("synthetic summary failure")

    monkeypatch.setattr(harness.module, "_safe_result_summary", _raising_summary)

    with pytest.raises(harness.module.PostControllerExceptionalFailure) as caught:
        harness.module.run_one_category_b_live_attempt(candidate="A")

    assert len(harness.removals) == 1
    assert caught.value.stage == harness.module.STAGE_RESULT_PROCESSING
    assert caught.value.failure_type == "RuntimeError"
    assert caught.value.outer_cleanup is not None


# -- L1-FU5 NEARBY GAP: post-controller exceptional-path cleanup reporting --


def test_controller_exception_with_verified_cleanup_retains_both_facts(
    patched, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Mandatory regression 10: controller raises, cleanup verifies ->
    bounded primary controller failure, cleanup truth retained."""
    harness = _stubbed_harness(monkeypatch, tmp_path)

    def _raising_controller(**kwargs):
        raise RuntimeError("synthetic controller failure")

    monkeypatch.setattr(harness.module, "run_category_b_controller", _raising_controller)

    with pytest.raises(harness.module.PostControllerExceptionalFailure) as caught:
        harness.module.run_one_category_b_live_attempt(candidate="A")

    failure = caught.value
    assert failure.stage == harness.module.STAGE_CONTROLLER_EXECUTION
    assert failure.failure_type == "RuntimeError"
    assert failure.outer_cleanup["workspace_removal_verified"] is True
    assert failure.outer_cleanup["outer_cleanup_verified"] is True

    record = failure.as_refusal_record()
    assert record["controller_entered"] is True
    assert record["semantic_prompts_sent"] == 0
    assert record["outer_cleanup"]["outer_cleanup_verified"] is True


def test_controller_exception_with_a_normally_failed_removal_shows_both_facts(
    patched, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Mandatory regression 11: controller raises, and
    ``remove_run_workspace`` returns ``removed=False`` WITHOUT raising ->
    the primary controller failure is retained AND the cleanup failure is
    visible, never masked by the primary exception."""
    harness = _stubbed_harness(
        monkeypatch,
        tmp_path,
        removal_returns={"removed": False, "residual_file_count": 4, "verified": True},
    )

    def _raising_controller(**kwargs):
        raise RuntimeError("synthetic controller failure")

    monkeypatch.setattr(harness.module, "run_category_b_controller", _raising_controller)

    with pytest.raises(harness.module.PostControllerExceptionalFailure) as caught:
        harness.module.run_one_category_b_live_attempt(candidate="A")

    failure = caught.value
    assert failure.stage == harness.module.STAGE_CONTROLLER_EXECUTION
    assert failure.failure_type == "RuntimeError"
    assert failure.outer_cleanup["workspace_removal_verified"] is False
    assert failure.outer_cleanup["outer_cleanup_verified"] is False


def test_result_processing_exception_with_a_normally_failed_removal_shows_both_facts(
    patched, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Mandatory regression 12: result-summary reduction raises, and
    ``remove_run_workspace`` returns ``removed=False`` WITHOUT raising ->
    the primary result-processing failure is retained AND the cleanup
    failure is visible."""
    harness = _stubbed_harness(
        monkeypatch,
        tmp_path,
        removal_returns={"removed": False, "residual_file_count": 1, "verified": True},
    )
    monkeypatch.setattr(
        harness.module, "run_category_b_controller", lambda **kwargs: object()
    )

    def _raising_summary(result):
        raise RuntimeError("synthetic summary failure")

    monkeypatch.setattr(harness.module, "_safe_result_summary", _raising_summary)

    with pytest.raises(harness.module.PostControllerExceptionalFailure) as caught:
        harness.module.run_one_category_b_live_attempt(candidate="A")

    failure = caught.value
    assert failure.stage == harness.module.STAGE_RESULT_PROCESSING
    assert failure.failure_type == "RuntimeError"
    assert failure.outer_cleanup["workspace_removal_verified"] is False
    assert failure.outer_cleanup["outer_cleanup_verified"] is False


def test_the_post_controller_failure_record_is_bounded_and_secret_free(
    patched, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Mandatory regression 13: no exception text, no runtime path, no
    endpoint, no token -- only the failing class NAME, the stage, the
    cleanup facts, and the fixed zero-prompt invariant. No controller
    result is fabricated."""
    harness = _stubbed_harness(monkeypatch, tmp_path)

    def _raising_controller(**kwargs):
        raise RuntimeError(
            f"synthetic failure leaking {SYNTHETIC_API_KEY} and {SYNTHETIC_BASE_URL} "
            f"and workspace {harness.workspace.experiment_root}"
        )

    monkeypatch.setattr(harness.module, "run_category_b_controller", _raising_controller)

    with pytest.raises(harness.module.PostControllerExceptionalFailure) as caught:
        harness.module.run_one_category_b_live_attempt(candidate="A")

    record = caught.value.as_refusal_record()
    assert record["refused"] is True
    assert record["reason"] == "RuntimeError"
    assert record["stage"] == harness.module.STAGE_CONTROLLER_EXECUTION
    assert record["semantic_prompts_sent"] == 0
    assert record["controller_entered"] is True
    assert record["outer_cleanup"] is not None
    assert "outcome" not in record and "gate_statuses" not in record

    rendered = json.dumps(record)
    assert SYNTHETIC_API_KEY not in rendered
    assert SYNTHETIC_BASE_URL not in rendered
    assert harness.workspace.experiment_root not in rendered
    assert "synthetic failure leaking" not in rendered


def test_ordinary_controller_refusal_result_is_unaffected_by_the_fu5_guard(
    patched, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Mandatory regression 14: an ordinary (non-exceptional)
    ``CategoryBControllerResult`` refusal must still flow through
    unchanged -- the FU5 guard reduces unexpected EXCEPTIONS only, and must
    never turn an ordinary refusal result into one."""
    harness = _stubbed_harness(monkeypatch, tmp_path)
    monkeypatch.setattr(
        harness.module, "run_category_b_controller", lambda **kwargs: SimpleNamespace()
    )
    monkeypatch.setattr(
        harness.module,
        "_safe_result_summary",
        lambda result: {
            "candidate": "A",
            "outcome": "CATEGORY_B_GATE_REFUSED",
            "failed_gate": "broker_creation",
        },
    )

    summary = harness.module.run_one_category_b_live_attempt(candidate="A")

    assert summary["outcome"] == "CATEGORY_B_GATE_REFUSED"
    assert summary["outer_cleanup"]["workspace_removal_verified"] is True
    assert summary["outer_cleanup"]["outer_cleanup_verified"] is True


def test_ordinary_pass_result_with_verified_cleanup_is_unaffected_by_the_fu5_guard(
    patched, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Mandatory regression 15: an ordinary Category-B PASS with a verified
    outer cleanup is unchanged -- no exception, no
    ``PostControllerExceptionalFailure``, exactly one removal."""
    harness = _stubbed_harness(monkeypatch, tmp_path)
    monkeypatch.setattr(
        harness.module, "run_category_b_controller", lambda **kwargs: SimpleNamespace()
    )
    monkeypatch.setattr(
        harness.module,
        "_safe_result_summary",
        lambda result: {
            "candidate": "A",
            "outcome": harness.module.CategoryBOutcome.CATEGORY_B_GATE_PASSED.value,
        },
    )

    summary = harness.module.run_one_category_b_live_attempt(candidate="A")

    assert len(harness.removals) == 1
    assert summary["outcome"] == harness.module.CategoryBOutcome.CATEGORY_B_GATE_PASSED.value
    assert summary["outer_cleanup"]["workspace_removal_verified"] is True
    assert summary["outer_cleanup"]["outer_cleanup_verified"] is True


def test_main_never_exits_0_when_controller_passed_but_removal_returns_false_normally(
    patched, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Mandatory regression 9: a controller CATEGORY_B_GATE_PASSED result,
    an extension scrub that verified (nothing to scrub here), and a
    workspace removal that returns ``{"removed": False, ...}`` WITHOUT
    raising must never let ``main()`` exit 0 -- the L1-FU5 primary
    blocker's exact false-PASS scenario."""
    harness = _stubbed_harness(
        monkeypatch,
        tmp_path,
        removal_returns={"removed": False, "residual_file_count": 2, "verified": True},
    )
    monkeypatch.setattr(
        harness.module, "run_category_b_controller", lambda **kwargs: SimpleNamespace()
    )
    monkeypatch.setattr(
        harness.module,
        "_safe_result_summary",
        lambda result: {
            "candidate": "A",
            "outcome": harness.module.CategoryBOutcome.CATEGORY_B_GATE_PASSED.value,
        },
    )
    monkeypatch.setattr(harness.module, "RESULTS_DIR", tmp_path / "results")

    exit_code = harness.module.main(["--candidate", "A", "--run-category-b-live-gate"])

    assert exit_code != 0


def test_no_double_workspace_removal_on_the_success_path(
    patched, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """One mint, one removal -- on the ordinary path too."""
    harness = _stubbed_harness(monkeypatch, tmp_path)
    monkeypatch.setattr(
        harness.module,
        "run_category_b_controller",
        lambda **kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        harness.module, "_safe_result_summary", lambda result: {"outcome": "SYNTHETIC"}
    )

    summary = harness.module.run_one_category_b_live_attempt(candidate="A")

    assert len(harness.removals) == 1
    assert summary["outer_cleanup"]["workspace_removal_verified"] is True


def test_the_ownership_scope_calls_outer_cleanup_from_exactly_one_site() -> None:
    """Source-level: ``_run_outer_cleanup`` is invoked from exactly ONE
    place inside the attempt, in a ``finally``, so no path can double-remove
    and no path can skip it."""
    run_i2b_live = _import_run_i2b_live()
    source = inspect.getsource(run_i2b_live.run_one_category_b_live_attempt)
    body = source.split('"""')[-1]
    assert body.count("_run_outer_cleanup(") == 1
    tree = ast.parse(inspect.getsource(run_i2b_live))
    attempt = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "run_one_category_b_live_attempt"
    )
    in_finally = [
        call
        for handler in ast.walk(attempt)
        if isinstance(handler, ast.Try)
        for statement in handler.finalbody
        for call in ast.walk(statement)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "_run_outer_cleanup"
    ]
    assert len(in_finally) == 1


def test_the_mint_is_immediately_followed_by_the_ownership_scope() -> None:
    """Nothing that can raise may sit between the mint and the ``try`` that
    owns its cleanup -- that one-statement gap was the FU4 defect."""
    run_i2b_live = _import_run_i2b_live()
    tree = ast.parse(inspect.getsource(run_i2b_live))
    attempt = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "run_one_category_b_live_attempt"
    )
    statements = attempt.body
    mint_index = next(
        index
        for index, statement in enumerate(statements)
        if "mint_qualification_run_workspace"
        in {n.id for n in ast.walk(statement) if isinstance(n, ast.Name)}
    )
    assert isinstance(statements[mint_index + 1], ast.Try)


def test_the_adapter_constructor_is_inside_the_ownership_scope() -> None:
    """And the constructor specifically -- the statement that used to sit
    outside it."""
    run_i2b_live = _import_run_i2b_live()
    tree = ast.parse(inspect.getsource(run_i2b_live))
    attempt = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "run_one_category_b_live_attempt"
    )
    mint_index = next(
        index
        for index, statement in enumerate(attempt.body)
        if "mint_qualification_run_workspace"
        in {n.id for n in ast.walk(statement) if isinstance(n, ast.Name)}
    )
    scope = attempt.body[mint_index + 1]
    assert isinstance(scope, ast.Try)
    assert "LiveCategoryBAdapters" in {
        n.id for n in ast.walk(scope) if isinstance(n, ast.Name)
    }


def test_a_claimed_identity_stays_refused_after_a_later_constructor_refusal(
    patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FU4 hygiene check on FU3's accepted issuance: the constructor claims
    the identity BEFORE the extension-digest invariant, so a refusal there
    still burns the issuance. A claimed record is not reusable authority."""
    issued = _issued()
    monkeypatch.setattr(live_module, "_FROZEN_AR2_EXTENSION_SHA256", "0" * 64)
    with pytest.raises(LiveAdapterError, match="does not match its authorized digest"):
        _adapters(runtime_identity=issued)

    monkeypatch.undo()
    with pytest.raises(LiveAdapterError, match="already consumed"):
        _adapters(runtime_identity=issued)


# -- FU4 nearby: truthful LaunchIdentityError reporting ----------------------


def _refusal_record_for(monkeypatch, exception) -> dict:
    """Drive ``main()`` to its bounded refusal record for one exception."""
    import io as _io

    run_i2b_live = _import_run_i2b_live()

    def _raising_attempt(*, candidate: str):
        raise exception

    monkeypatch.setattr(run_i2b_live, "run_one_category_b_live_attempt", _raising_attempt)
    captured = _io.StringIO()
    monkeypatch.setattr(run_i2b_live.sys, "stdout", captured)
    code = run_i2b_live.main(["--run-category-b-live-gate"])
    assert code == 1
    return json.loads(captured.getvalue())


def test_launch_identity_refusal_no_longer_claims_nothing_was_launched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pre-fix wording claimed "nothing was launched (or the failure
    happened before any process existed)". That is FALSE for a
    ``LaunchIdentityError`` raised BECAUSE the provenance-only ``--version``
    subprocess launched, ran to completion and exited non-zero -- exactly
    what ``resolve_pi_identity`` raises there. The harness never observed
    that no process existed, so it must not claim it."""
    record = _refusal_record_for(
        monkeypatch,
        LaunchIdentityError(
            "launch error: Node-direct Pi launch exited non-zero; no fallback "
            "launch architecture is attempted"
        ),
    )
    note = record["note"]
    assert "nothing was launched" not in note
    assert "before any process existed" not in note
    assert "MAY have been attempted" in note
    assert record["semantic_prompts_sent"] == 0
    assert record["controller_entered"] is False
    assert record["reason"] == "LaunchIdentityError"


@pytest.mark.parametrize(
    "exception",
    [
        LaunchIdentityError("launch error: synthetic"),
        InfrastructureRefusal("synthetic_gate", "CHECK_FAILED"),
    ],
)
def test_every_pre_controller_refusal_record_stays_bounded_and_secret_free(
    monkeypatch: pytest.MonkeyPatch, exception
) -> None:
    record = _refusal_record_for(monkeypatch, exception)
    rendered = json.dumps(record)
    assert record["reason"] == type(exception).__name__
    assert "synthetic" not in rendered
    assert SYNTHETIC_API_KEY not in rendered
    assert SYNTHETIC_BASE_URL not in rendered
    assert record["semantic_prompts_sent"] == 0


# ===========================================================================
# 5F3B-I2B-L1-LF1-FU1 -- required-flag / LF-correlation independence closure
# ===========================================================================
#
# THE DEFECT THIS SECTION CLOSES. LF1's producer computed
#
#     required_flags_accepted = argv_options_source_established
#                               and lf_jsonl_correlation_succeeded
#
# whose positive direction is sound but whose REVERSE direction is not: no
# correlated response does NOT imply an unknown CLI flag was rejected. Because
# the frozen controller orders RPC_LAUNCH_SHAPE -> REQUIRED_LAUNCH_FLAGS ->
# LF_JSONL_CORRELATION, all six recognized non-success ``await_response``
# outcomes were attributed FIRST as REQUIRED_LAUNCH_FLAGS_REJECTED. The
# pre-fix state is reproduced below as a permanent regression, driven through
# the REAL, UNMODIFIED frozen controller.

#: The six recognized ``await_response`` outcomes that are NOT a correlated
#: response. Every one of them made the LF1 producer report
#: ``required_flags_accepted=False`` on a TRUSTED session; none of them
#: mechanically proves an unknown-option startup rejection.
_FU1_NON_SUCCESS_OUTCOMES = (
    RUNTIME_DEADLINE_EXPIRED,
    RUNTIME_PROTOCOL_VIOLATION,
    RUNTIME_OUTPUT_CAP_EXCEEDED,
    RUNTIME_EVENT_CAP_EXCEEDED,
    RUNTIME_READ_ERROR,
    RUNTIME_EXITED_EARLY,
)

#: The exact unknown-option ERROR line the installed package emits on stderr,
#: naming an option that IS present in AIDO's own argv. Test-owned data, never
#: read back out of any adapter surface.
_FU1_REAL_UNKNOWN_OPTION_LINE = "Error: Unknown option: --offline\n"

#: AIDO's genuine argv, built by the frozen, unmodified ``build_pi_argv``.
_FU1_REAL_ARGV = tuple(
    _real_build_pi_argv(
        SYNTHETIC_IDENTITY,
        extension_entry=r"C:\synthetic\experiment\pi_extension\index.ts",
        tool_allowlist=AR2_TOOL_ALLOWLIST,
        provider="synthetic-provider",
        model="synthetic-model",
    )
)


def _stderr_snapshot(text: str, **overrides) -> dict:
    """The exact mapping shape ``PiRpcSupervisor.stderr_snapshot()`` publishes."""
    encoded = len(text.encode("utf-8"))
    snapshot = {
        "captured": True,
        "bytes_seen": encoded,
        "bytes_retained": encoded,
        "cap_exceeded": False,
        "eof": True,
        "read_error": None,
        "text_tail": text,
    }
    snapshot.update(overrides)
    return snapshot


@pytest.fixture
def workspace_factory():
    """Mint as many FRESH disposable run workspaces as a test needs.

    A workspace nonce can be claimed exactly once, so any test driving more
    than one launch needs more than one workspace. Every minted workspace is
    removed afterwards, exactly as the single-workspace fixtures do.
    """
    minted = []

    def _mint():
        workspace = mint_qualification_run_workspace()
        minted.append(workspace)
        return workspace

    try:
        yield _mint
    finally:
        for workspace in minted:
            remove_run_workspace(workspace)


def _body_source(function) -> str:
    """A function's source with its own docstring removed.

    Source-level assertions about what a function READS must not be defeated
    -- or satisfied -- by prose. The docstrings here deliberately NAME the
    outcome constants they are explaining, so the checks below look at code.
    """
    source = inspect.getsource(function)
    node = ast.parse(source.lstrip()).body[0]
    literal = ast.get_docstring(node, clean=False)
    return source if literal is None else source.replace(literal, "", 1)


def _supervisor_factory(patched, monkeypatch: pytest.MonkeyPatch, configure) -> None:
    """Patch in a ``_FakeSupervisor`` factory that runs ``configure(s)``."""

    def _make_supervisor(*, argv, cwd, environment, bounds):
        s = _FakeSupervisor(argv=argv, cwd=cwd, environment=environment, bounds=bounds)
        configure(s)
        patched.supervisors.append(s)
        return s

    monkeypatch.setattr(live_module, "PiRpcSupervisor", _make_supervisor)


def _awaits(outcome, response=None):
    """A ``configure`` callable that pins the one correlation probe's outcome."""

    def _configure(s):
        s.responses["h1"] = (outcome, response)

    return _configure


def _awaits_with_stderr(outcome, stderr_text, response=None):
    def _configure(s):
        s.responses["h1"] = (outcome, response)
        s.stderr_text = stderr_text

    return _configure


def _launch_with(patched, monkeypatch, run_workspace, *, run_id, configure):
    """One real ``launch_runtime`` against a configured synthetic supervisor."""
    _supervisor_factory(patched, monkeypatch, configure)
    adapters = _adapters()
    request = _launch_request_with_registered_broker(adapters, run_workspace, run_id=run_id)
    return adapters, adapters.launch_runtime(request)


@dataclass(frozen=True)
class _FU1RouteCheck:
    reachable: bool = True
    configured_model_served: bool = True


def _drive_frozen_controller(workspace, adapters, *, candidate: str = "A"):
    """Drive the REAL, UNMODIFIED frozen controller over the REAL live
    adapters, with synthetic transport doubles underneath.

    This is what makes the attribution claims here end-to-end rather than
    adapter-local: the gate order, the first-failure choice and the failure
    code all come from ``qualification.i2b_controller``, which this phase does
    not modify. Nothing here launches a process, opens a pipe, reads a real
    credential, or calls a model.
    """
    return run_category_b_controller(
        candidate=candidate,
        run_workspace=workspace,
        ambient_environ={
            "SystemRoot": r"C:\Windows",
            "TEMP": workspace.experiment_root,
            "TMP": workspace.experiment_root,
        },
        node_executable=os.path.join(workspace.experiment_root, "node.exe"),
        non_secret_gates=[
            lambda: PreflightGateResult(name="pi_installed_offline", passed=True),
            lambda: PreflightGateResult(name="config_generator_self_check", passed=True),
            lambda: PreflightGateResult(
                name="environment_forbidden_fragment_audit", passed=True
            ),
        ],
        read_connection=adapters.read_connection,
        create_broker=adapters.create_broker,
        launch_runtime=adapters.launch_runtime,
        get_commands=adapters.get_commands,
        get_state=adapters.get_state,
        observe_protocol=adapters.observe_protocol,
        route_checker=lambda base_url, *, model_id: _FU1RouteCheck(),
        shutdown_runtime=adapters.shutdown_runtime,
        shutdown_broker=adapters.shutdown_broker,
    )


def _fu1_result_render(result) -> dict:
    """The same field set the live entry point retains, rendered JSON-safe."""
    return {
        "outcome": result.outcome.value,
        "failed_gate": result.failed_gate.value if result.failed_gate else None,
        "failure_code": result.failure_code.value if result.failure_code else None,
        "gate_statuses": dict(result.gate_statuses),
        "compatibility_facts": result.facts.as_dict(),
        "observed_pi_version": result.observed_pi_version,
        "runtime_teardown_status": result.runtime_teardown.status_text,
        "broker_shutdown_status": result.broker_shutdown.status_text,
        "cleanup_status": result.cleanup.status_text,
        "evidence_retention_ready": result.evidence.retention_ready,
        "evidence": result.evidence.as_dict() if result.evidence.retention_ready else None,
        "evidence_scrub_findings": list(result.evidence.scrub_findings),
    }


# -- the pre-fix misattribution, inverted into a permanent regression ---------


@pytest.mark.parametrize("outcome", _FU1_NON_SUCCESS_OUTCOMES)
def test_fu1_no_non_success_outcome_alone_denies_required_flags(
    outcome, run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every one of the six recognized non-success outcomes used to produce
    ``launch_shape_valid=True, lf_jsonl_correlation_succeeded=False,
    required_flags_accepted=False`` ON A TRUSTED SESSION, which the frozen
    controller reads as REQUIRED_LAUNCH_FLAGS_REJECTED. With no unknown-option
    observation none of them may do that any more: each is INDETERMINATE and
    hands over NO session, so no rejection can be named.
    """
    run_id = "run-fu1-ind-" + outcome
    adapters, observation = _launch_with(
        patched, monkeypatch, run_workspace, run_id=run_id, configure=_awaits(outcome)
    )
    # the two facts this launch genuinely established are still truthful
    assert observation.launch_shape_valid is True
    assert observation.observed_pi_version == SYNTHETIC_IDENTITY.reported_version
    assert observation.lf_jsonl_correlation_succeeded is False
    # ...and the flag fact is NOT asserted as a rejection: no session crosses
    assert observation.session is None
    assert observation.required_flags_accepted is False
    assert (
        adapters.launch_diagnostics()[run_id]["required_launch_flags"]
        == live_module.REQUIRED_FLAGS_INDETERMINATE
    )


@pytest.mark.parametrize("outcome", _FU1_NON_SUCCESS_OUTCOMES)
def test_fu1_frozen_controller_no_longer_names_a_rejection_for_any_of_the_six(
    outcome, run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same six, driven END TO END through the UNMODIFIED frozen controller.

    Pre-fix, every one of these produced
    ``failed_gate=required_launch_flags`` /
    ``failure_code=REQUIRED_LAUNCH_FLAGS_REJECTED``. Post-fix the controller
    reports the fact actually observed -- the launch produced no trustworthy
    runtime session -- and leaves REQUIRED_LAUNCH_FLAGS NOT_REACHED.
    """
    _supervisor_factory(patched, monkeypatch, _awaits(outcome))
    adapters = _adapters()
    result = _drive_frozen_controller(run_workspace, adapters)
    assert result.failed_gate is CategoryBGateName.RUNTIME_LAUNCH
    assert result.failure_code is CategoryBFailureCode.RUNTIME_LAUNCH_FAILED
    statuses = dict(result.gate_statuses)
    assert statuses[CategoryBGateName.RPC_LAUNCH_SHAPE.value] == "NOT_REACHED"
    assert statuses[CategoryBGateName.REQUIRED_LAUNCH_FLAGS.value] == "NOT_REACHED"
    assert statuses[CategoryBGateName.LF_JSONL_CORRELATION.value] == "NOT_REACHED"
    assert result.semantic_prompts_sent == 0


# -- INDEPENDENCE TEST 1: ACCEPTED + LF PASS is constructible -----------------


def test_fu1_independence_1_accepted_with_lf_pass_is_constructible(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapters, observation = _launch_with(
        patched,
        monkeypatch,
        run_workspace,
        run_id="run-fu1-acc",
        configure=_awaits(
            RUNTIME_RESPONSE_RECEIVED, _successful_get_commands_response(run_workspace)
        ),
    )
    assert observation.session is not None
    assert observation.required_flags_accepted is True
    assert observation.lf_jsonl_correlation_succeeded is True
    assert (
        adapters.launch_diagnostics()["run-fu1-acc"]["required_launch_flags"]
        == live_module.REQUIRED_FLAGS_ACCEPTED
    )


# -- INDEPENDENCE TEST 2: ACCEPTED + LF FAIL, stated exactly ------------------


def test_fu1_independence_2_accepted_requires_the_correlated_response() -> None:
    """The brief's "IF AND ONLY IF", answered honestly.

    ACCEPTED means "mechanical evidence establishes that NO unknown-option
    startup rejection occurred". The only such evidence available in this
    phase is LF1's positive proof, whose runtime half IS the correlated RPC
    response -- it is what shows ``runRpcMode`` was entered, which both
    unknown-option exits are strictly earlier than. So ACCEPTED alongside a
    FAILED LF correlation is deliberately NOT constructible: no other
    mechanically-justified proof of acceptance exists here, and inventing one
    would be exactly the fabrication FU1 exists to remove.

    That is not the defect FU1 closes. The defect was the REVERSE coupling --
    LF correlation false FORCING required flags false -- and the tests below
    prove that direction is broken in both of its outcomes.
    """
    classify = live_module._classify_required_flag_evidence
    unreadable = {"captured": False}
    for argv_ok, lf_ok in ((True, False), (False, True), (False, False)):
        assert (
            classify(
                argv=_FU1_REAL_ARGV,
                argv_options_source_established=argv_ok,
                lf_jsonl_correlation_succeeded=lf_ok,
                stderr_snapshot_reader=lambda: unreadable,
            )
            == live_module.REQUIRED_FLAGS_INDETERMINATE
        )
    assert (
        classify(
            argv=_FU1_REAL_ARGV,
            argv_options_source_established=True,
            lf_jsonl_correlation_succeeded=True,
            stderr_snapshot_reader=lambda: unreadable,
        )
        == live_module.REQUIRED_FLAGS_ACCEPTED
    )


# -- INDEPENDENCE TEST 3: protocol integrity never alters required flags ------


@pytest.mark.parametrize(
    "outcome, expected_state",
    [
        (RUNTIME_RESPONSE_RECEIVED, live_module.REQUIRED_FLAGS_ACCEPTED),
        (RUNTIME_PROTOCOL_VIOLATION, live_module.REQUIRED_FLAGS_INDETERMINATE),
    ],
)
def test_fu1_independence_3_protocol_violation_does_not_alter_required_flags(
    outcome, expected_state, run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A launch-window protocol violation changes NOTHING about the flag
    classification: with a correlated response it is still ACCEPTED, and
    without one it is INDETERMINATE for exactly the reason it would have been
    with no violation at all. The violation is a separate, later gate's fact.
    """
    run_id = "run-fu1-pv-" + outcome

    def _configure(s):
        s.responses["h1"] = (
            outcome,
            _successful_get_commands_response(run_workspace)
            if outcome == RUNTIME_RESPONSE_RECEIVED
            else None,
        )
        s._protocol_violation = _SYNTHETIC_VIOLATION_MESSAGE

    adapters, observation = _launch_with(
        patched, monkeypatch, run_workspace, run_id=run_id, configure=_configure
    )
    diagnostic = adapters.launch_diagnostics()[run_id]
    assert diagnostic["required_launch_flags"] == expected_state
    assert (
        diagnostic["launch_window_protocol"]
        == live_module.LAUNCH_WINDOW_PROTOCOL_VIOLATION_OBSERVED
    )
    assert observation.required_flags_accepted is (
        expected_state == live_module.REQUIRED_FLAGS_ACCEPTED
    )


def test_fu1_independence_3_source_level_no_protocol_bit_reaches_the_classifier() -> None:
    """Nothing in the flag-classification chain reads the protocol-violation
    projection, or the stdout state it comes from, at source level."""
    for function in (
        live_module._classify_required_flag_evidence,
        live_module._unknown_option_rejection_established,
        live_module._argv_option_tokens,
    ):
        source = inspect.getsource(function)
        assert "_protocol_violation_observed" not in source
        assert "stdout_state" not in source


# -- INDEPENDENCE TEST 4: LF-correlation failure never alters required flags --


def test_fu1_independence_4_lf_failure_alone_does_not_decide_the_flag_fact(
    run_workspace, second_run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ONE fixed correlation failure, TWO different flag classifications.

    The supervisor outcome constant is identical in both halves; only the
    bounded startup diagnostic differs. That is what "observationally
    independent" means here: the LF fact no longer determines the flag fact.
    """
    rejected_adapters, rejected = _launch_with(
        patched,
        monkeypatch,
        run_workspace,
        run_id="run-fu1-lf-a",
        configure=_awaits_with_stderr(RUNTIME_EXITED_EARLY, _FU1_REAL_UNKNOWN_OPTION_LINE),
    )
    indeterminate_adapters, indeterminate = _launch_with(
        patched,
        monkeypatch,
        second_run_workspace,
        run_id="run-fu1-lf-b",
        configure=_awaits_with_stderr(RUNTIME_EXITED_EARLY, ""),
    )

    assert rejected.lf_jsonl_correlation_succeeded is False
    assert indeterminate.lf_jsonl_correlation_succeeded is False
    assert (
        rejected_adapters.launch_diagnostics()["run-fu1-lf-a"]["required_launch_flags"]
        == live_module.REQUIRED_FLAGS_REJECTED_UNKNOWN_OPTION
    )
    assert (
        indeterminate_adapters.launch_diagnostics()["run-fu1-lf-b"]["required_launch_flags"]
        == live_module.REQUIRED_FLAGS_INDETERMINATE
    )
    assert rejected.session is not None
    assert indeterminate.session is None


# -- INDEPENDENCE TEST 5: an ESTABLISHED rejection is reported as one ---------


def test_fu1_independence_5_established_rejection_reaches_the_frozen_gate(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mechanically-established unknown-option rejection maps to
    ``required_flags_accepted=False`` on a session the frozen controller
    trusts, so REQUIRED_LAUNCH_FLAGS_REJECTED is still reachable -- and is now
    reachable ONLY from real evidence.
    """
    _supervisor_factory(
        patched,
        monkeypatch,
        _awaits_with_stderr(RUNTIME_EXITED_EARLY, _FU1_REAL_UNKNOWN_OPTION_LINE),
    )
    adapters = _adapters()
    result = _drive_frozen_controller(run_workspace, adapters)
    assert result.failed_gate is CategoryBGateName.REQUIRED_LAUNCH_FLAGS
    assert result.failure_code is CategoryBFailureCode.REQUIRED_LAUNCH_FLAGS_REJECTED
    assert result.semantic_prompts_sent == 0


@pytest.mark.parametrize(
    "message",
    [
        "Error: Unknown option: --offline",
        "Error: Unknown options: --offline, --no-approve",
        "\x1b[31mError: Unknown option: --offline\x1b[39m",
        "prelude line\r\nError: Unknown option: --offline\r\n",
    ],
)
def test_fu1_established_rejection_message_shapes(message) -> None:
    """The exact diagnostic shapes ``dist/cli/args.js`` /
    ``dist/core/agent-session-services.js`` / ``dist/main.js`` can emit --
    singular, plural, chalk-wrapped, and embedded in other output."""
    assert (
        live_module._unknown_option_rejection_established(
            argv=_FU1_REAL_ARGV, stderr_snapshot=_stderr_snapshot(message)
        )
        is True
    )


# -- INDEPENDENCE TESTS 6-9: what is NOT an unknown-option rejection ----------


@pytest.mark.parametrize("outcome", _FU1_NON_SUCCESS_OUTCOMES)
def test_fu1_independence_6_to_9_no_outcome_constant_decides_a_rejection(
    outcome, run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FU1 tests 6, 7, 8 and 9 together, at the level where they are decided.

    A generic early exit, a deadline, a protocol violation before a correlated
    response, an output cap, an event cap and a read error all classify
    identically -- INDETERMINATE -- because the classifier reads no supervisor
    outcome constant at all. ``RUNTIME_EXITED_EARLY`` in particular has no
    privileged status: an unknown-option startup rejection is ONE
    source-supported cause of it, never a proof of it.
    """
    run_id = "run-fu1-69-" + outcome
    adapters, observation = _launch_with(
        patched, monkeypatch, run_workspace, run_id=run_id, configure=_awaits(outcome)
    )
    assert (
        adapters.launch_diagnostics()[run_id]["required_launch_flags"]
        == live_module.REQUIRED_FLAGS_INDETERMINATE
    )
    assert observation.session is None


def test_fu1_independence_6_early_exit_is_not_privileged_at_source_level() -> None:
    """No supervisor outcome constant appears anywhere in the classification
    chain, so no outcome can become a proxy for flag rejection by drift."""
    outcome_names = (
        "RUNTIME_EXITED_EARLY",
        "RUNTIME_DEADLINE_EXPIRED",
        "RUNTIME_PROTOCOL_VIOLATION",
        "RUNTIME_OUTPUT_CAP_EXCEEDED",
        "RUNTIME_EVENT_CAP_EXCEEDED",
        "RUNTIME_READ_ERROR",
        "RUNTIME_RESPONSE_RECEIVED",
    )
    for function in (
        live_module._classify_required_flag_evidence,
        live_module._unknown_option_rejection_established,
        live_module._argv_option_tokens,
    ):
        source = _body_source(function)
        for name in outcome_names:
            assert name not in source


# -- the adversarial sweep on the bounded startup diagnostic ------------------


@pytest.mark.parametrize(
    "snapshot",
    [
        # a stderr READ ERROR is never proof
        _stderr_snapshot(_FU1_REAL_UNKNOWN_OPTION_LINE, read_error="OSError: synthetic"),
        # TRUNCATED by the bounded reader's own cap
        _stderr_snapshot(_FU1_REAL_UNKNOWN_OPTION_LINE, cap_exceeded=True),
        # bytes were dropped: seen != retained
        _stderr_snapshot(_FU1_REAL_UNKNOWN_OPTION_LINE, bytes_seen=999999),
        # retained more than the 4000-char tail can carry, so text_tail may be sliced
        _stderr_snapshot(_FU1_REAL_UNKNOWN_OPTION_LINE, bytes_retained=4001),
        # not captured at all
        {"captured": False},
        # captured reported by truthiness rather than exactly True
        _stderr_snapshot(_FU1_REAL_UNKNOWN_OPTION_LINE, captured=1),
        # cap_exceeded reported by truthiness rather than exactly False
        _stderr_snapshot(_FU1_REAL_UNKNOWN_OPTION_LINE, cap_exceeded=0),
        # malformed types
        _stderr_snapshot(_FU1_REAL_UNKNOWN_OPTION_LINE, text_tail=None),
        _stderr_snapshot(_FU1_REAL_UNKNOWN_OPTION_LINE, bytes_seen="12", bytes_retained="12"),
        # not a mapping at all
        "Error: Unknown option: --offline",
        None,
        # a WARNING diagnostic never reaches process.exit(1)
        _stderr_snapshot("Warning: Unknown option: --offline\n"),
        # the message shape, but not as a diagnostic line
        _stderr_snapshot("note about Error: Unknown option: --offline\n"),
        # an empty name in the list
        _stderr_snapshot("Error: Unknown options: --offline, \n"),
    ],
)
def test_fu1_bounded_diagnostic_fails_closed(snapshot) -> None:
    assert (
        live_module._unknown_option_rejection_established(
            argv=_FU1_REAL_ARGV, stderr_snapshot=snapshot
        )
        is False
    )


@pytest.mark.parametrize(
    "message",
    [
        "Error: Unknown option: --not-in-aido-argv\n",
        "Error: Unknown options: --offline, --not-in-aido-argv\n",
        "Error: Unknown option: -q\n",
    ],
)
def test_fu1_a_diagnostic_naming_an_option_not_in_aido_argv_proves_nothing(message) -> None:
    """ADVERSARIAL: the finding must be tied to an option ACTUALLY PRESENT in
    AIDO's own argv. A diagnostic naming anything else -- including one that
    also names a real AIDO option -- is ambiguous and fails closed."""
    assert (
        live_module._unknown_option_rejection_established(
            argv=_FU1_REAL_ARGV, stderr_snapshot=_stderr_snapshot(message)
        )
        is False
    )


def test_fu1_a_raising_stderr_surface_is_indeterminate_not_rejected(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _configure(s):
        s.responses["h1"] = (RUNTIME_EXITED_EARLY, None)
        s.stderr_snapshot_raises = RuntimeError("synthetic reader failure")

    adapters, observation = _launch_with(
        patched, monkeypatch, run_workspace, run_id="run-fu1-raise", configure=_configure
    )
    assert observation.session is None
    assert (
        adapters.launch_diagnostics()["run-fu1-raise"]["required_launch_flags"]
        == live_module.REQUIRED_FLAGS_INDETERMINATE
    )


def test_fu1_the_accepted_path_never_reads_stderr_at_all(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The positive proof is decided first, so an ordinary passing launch
    never touches the raw stderr surface."""
    _unused, observation = _launch_with(
        patched,
        monkeypatch,
        run_workspace,
        run_id="run-fu1-nostderr",
        configure=_awaits(
            RUNTIME_RESPONSE_RECEIVED, _successful_get_commands_response(run_workspace)
        ),
    )
    assert observation.required_flags_accepted is True
    assert patched.supervisors[-1].stderr_snapshot_calls == 0


def test_fu1_argv_option_token_walk_mirrors_pi_parseargs() -> None:
    """The token walk that ties a diagnostic to AIDO's argv follows
    ``parseArgs``' own value-consumption rules, and collects OPTION tokens
    only -- never a value, so no absolute extension path can be collected."""
    head = (r"C:\node.exe", r"C:\pi\dist\cli.js")
    tokens = live_module._argv_option_tokens
    # a source-established value-taking option consumes its value
    assert tokens(head + ("--model", "some-model")) == frozenset({"--model"})
    # a valueless option consumes nothing
    assert tokens(head + ("--offline", "--no-approve")) == frozenset(
        {"--offline", "--no-approve"}
    )
    # an UNRECOGNIZED long option consumes a following non-dash, non-@ token
    assert tokens(head + ("--bogus", "value", "--offline")) == frozenset(
        {"--bogus", "--offline"}
    )
    # ...but not one starting with - or @
    assert tokens(head + ("--bogus", "--offline")) == frozenset({"--bogus", "--offline"})
    assert tokens(head + ("--bogus", "@file")) == frozenset({"--bogus"})
    # --name=value carries its own value; the NAME is what a diagnostic prints
    assert tokens(head + ("--bogus=value",)) == frozenset({"--bogus"})
    # a single-dash token is an option token too (parseArgs' error branch)
    assert tokens(head + ("-q",)) == frozenset({"-q"})
    # the two pinned program paths are never collected
    assert tokens(head) == frozenset()
    # and a value token is never collected, even an absolute path
    assert tokens(
        head + ("--extension", r"C:\synthetic\experiment\pi_extension\index.ts")
    ) == frozenset({"--extension"})


# -- INDEPENDENCE TEST 10: creator ownership on every indeterminate path ------


@pytest.mark.parametrize("outcome", _FU1_NON_SUCCESS_OUTCOMES)
def test_fu1_independence_10_indeterminate_paths_keep_truthful_creator_ownership(
    outcome, run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An indeterminate launch retains the runtime, self-closes it EXACTLY
    once, and reports the three creator facts truthfully -- never a second
    cleanup, and never a fabricated postcondition."""
    _unused, observation = _launch_with(
        patched,
        monkeypatch,
        run_workspace,
        run_id="run-fu1-own-" + outcome,
        configure=_awaits(outcome),
    )
    assert observation.session is None
    assert observation.resource_created is True
    assert observation.cleanup_attempted is True
    assert observation.direct_child_reported_exit is True
    assert observation.cleanup_verified_success is True
    assert patched.supervisors[-1].shutdown_calls == 1


def test_fu1_indeterminate_path_reports_an_unverified_close_truthfully(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A self-close whose postcondition was not observed is reported as
    unverified, never fabricated -- and it is still exactly one attempt."""

    def _configure(s):
        s.responses["h1"] = (RUNTIME_DEADLINE_EXPIRED, None)
        s.shutdown_result = {"exit_status_observed": None}

    _unused, observation = _launch_with(
        patched,
        monkeypatch,
        run_workspace,
        run_id="run-fu1-own-unverified",
        configure=_configure,
    )
    assert observation.session is None
    assert observation.cleanup_attempted is True
    assert observation.direct_child_reported_exit is False
    assert observation.cleanup_verified_success is False
    assert patched.supervisors[-1].shutdown_calls == 1


def test_fu1_indeterminate_path_cleanup_exception_never_erases_the_failure(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BLOCKER 3 still holds on the new path: a raising self-close is reported
    as an unverified postcondition, not as an escaped exception."""

    def _configure(s):
        s.responses["h1"] = (RUNTIME_DEADLINE_EXPIRED, None)
        s.shutdown_raises = PiSupervisorError("synthetic close failure")

    _unused, observation = _launch_with(
        patched, monkeypatch, run_workspace, run_id="run-fu1-own-raise", configure=_configure
    )
    assert observation.session is None
    assert observation.cleanup_attempted is True
    assert observation.direct_child_reported_exit is False
    assert patched.supervisors[-1].shutdown_calls == 1


def test_fu1_an_indeterminate_launch_never_registers_a_runtime_record(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing is left behind that a later adapter call could pick up: no
    session was minted, so no runtime record exists to be looked up."""
    adapters, observation = _launch_with(
        patched,
        monkeypatch,
        run_workspace,
        run_id="run-fu1-noreg",
        configure=_awaits(RUNTIME_DEADLINE_EXPIRED),
    )
    assert observation.session is None
    assert adapters._runtimes == {}


def test_fu1_indeterminate_launch_still_closes_the_broker_exactly_once(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The frozen controller still resolves the broker lifecycle for an
    indeterminate launch, and the runtime teardown it never owned is reported
    as creator-retained rather than as an AIDO teardown."""
    _supervisor_factory(patched, monkeypatch, _awaits(RUNTIME_DEADLINE_EXPIRED))
    adapters = _adapters()
    result = _drive_frozen_controller(run_workspace, adapters)
    assert result.failure_code is CategoryBFailureCode.RUNTIME_LAUNCH_FAILED
    assert patched.servers[-1].shutdown_calls == 1
    assert patched.supervisors[-1].shutdown_calls == 1


# -- INDEPENDENCE TEST 11: no raw stderr escapes ------------------------------


def test_fu1_independence_11_no_raw_stderr_reaches_any_retained_surface(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The raw stderr tail is scanned transiently and dropped. It must not
    appear in the launch observation, the launch diagnostic, the frozen
    controller's result or evidence, or the serialized result JSON.
    """
    secretish = (
        "Error: Unknown option: --offline\n"
        "sk-synthetic-should-never-be-retained\n"
        "https://b300-proxy.example.invalid:8443/v1\n"
    )
    _supervisor_factory(
        patched, monkeypatch, _awaits_with_stderr(RUNTIME_EXITED_EARLY, secretish)
    )
    adapters = _adapters()
    result = _drive_frozen_controller(run_workspace, adapters)
    diagnostics = adapters.launch_diagnostics()

    rendered = json.dumps({"diagnostics": diagnostics, "result": _fu1_result_render(result)})
    for fragment in (
        "Unknown option",
        "sk-synthetic-should-never-be-retained",
        "b300-proxy.example.invalid",
        "--offline",
        "Error:",
    ):
        assert fragment not in rendered
    for diagnostic in diagnostics.values():
        assert set(diagnostic.values()) <= live_module.LAUNCH_DIAGNOSTIC_CODES
    assert repr(result.evidence).count("Unknown option") == 0


def test_fu1_no_raw_stderr_reaches_any_exception_text(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The only exception the new machinery can raise names no runtime value."""
    with pytest.raises(LiveAdapterError) as excinfo:
        live_module._launch_diagnostic(
            argv_ok=True,
            wait_outcome=RUNTIME_RESPONSE_RECEIVED,
            protocol_violation_observed=False,
            required_flags_code="Error: Unknown option: --offline",
        )
    assert "Unknown option" not in str(excinfo.value)
    assert "--offline" not in str(excinfo.value)


def test_fu1_the_diagnostic_carries_only_declared_codes(
    workspace_factory, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every produced diagnostic value, across every classification, is a
    declared literal -- and all THREE states are genuinely reachable."""
    cases = [
        (RUNTIME_RESPONSE_RECEIVED, "", live_module.REQUIRED_FLAGS_ACCEPTED),
        (
            RUNTIME_EXITED_EARLY,
            _FU1_REAL_UNKNOWN_OPTION_LINE,
            live_module.REQUIRED_FLAGS_REJECTED_UNKNOWN_OPTION,
        ),
        (RUNTIME_DEADLINE_EXPIRED, "", live_module.REQUIRED_FLAGS_INDETERMINATE),
    ]
    produced = set()
    for index, (outcome, stderr_text, expected) in enumerate(cases):
        run_id = f"run-fu1-codes-{index}"
        workspace = workspace_factory()
        adapters, _observation = _launch_with(
            patched,
            monkeypatch,
            workspace,
            run_id=run_id,
            configure=_awaits_with_stderr(
                outcome,
                stderr_text,
                _successful_get_commands_response(workspace)
                if outcome == RUNTIME_RESPONSE_RECEIVED
                else None,
            ),
        )
        diagnostic = adapters.launch_diagnostics()[run_id]
        assert diagnostic["required_launch_flags"] == expected
        assert set(diagnostic.values()) <= live_module.LAUNCH_DIAGNOSTIC_CODES
        produced.add(diagnostic["required_launch_flags"])
    # all three states are genuinely reachable
    assert produced == live_module.REQUIRED_FLAG_STATES


def test_fu1_stderr_is_read_in_exactly_one_place() -> None:
    """``stderr_snapshot`` is consulted from exactly ONE call site in this
    module, and no other function names the raw text field at all."""
    source = inspect.getsource(live_module)
    assert source.count("supervisor.stderr_snapshot()") == 1
    assert source.count("_unknown_option_rejection_established(") == 2
    assert "text_tail" in inspect.getsource(live_module._unknown_option_rejection_established)
    for other in (
        live_module.LiveCategoryBAdapters.launch_diagnostics,
        live_module.LiveCategoryBAdapters.observe_protocol,
        live_module.LiveCategoryBAdapters.get_commands,
        live_module.LiveCategoryBAdapters.get_state,
        live_module.LiveCategoryBAdapters._retain_and_close_partial_runtime,
    ):
        assert "text_tail" not in inspect.getsource(other)


# -- INDEPENDENCE TEST 12 / version policy / double conformance ---------------


def test_fu1_no_semantic_prompt_path_was_introduced() -> None:
    for function in (
        live_module._classify_required_flag_evidence,
        live_module._unknown_option_rejection_established,
        live_module._argv_option_tokens,
        live_module._launch_diagnostic,
    ):
        assert "prompt" not in inspect.getsource(function)


def test_fu1_no_version_gate_was_introduced() -> None:
    """Pi's version stays PROVENANCE ONLY: nothing in the new machinery reads
    or compares it."""
    for function in (
        live_module._classify_required_flag_evidence,
        live_module._unknown_option_rejection_established,
        live_module._argv_option_tokens,
        live_module._launch_diagnostic,
    ):
        source = inspect.getsource(function)
        assert "reported_version" not in source
        assert "0.84" not in source


def test_fu1_stderr_tail_bound_still_matches_the_frozen_ar2_source() -> None:
    """The 4000-character bound the truncation check relies on is read from the
    FROZEN ``PiRpcSupervisor.stderr_snapshot`` source itself. If AR2 ever
    changes it, this fails rather than silently accepting a sliced tail as
    complete."""
    source = inspect.getsource(PiRpcSupervisor.stderr_snapshot)
    assert f'"text_tail": text[-{live_module._STDERR_TEXT_TAIL_CHAR_LIMIT}:],' in source


def test_fu1_the_stderr_double_matches_the_real_supervisor_contract() -> None:
    """LF1's ROOT CAUSE was a synthetic double that disagreed with the real
    class, so the new double is pinned to the frozen source directly: the same
    keys, and the same declared value types -- notably ``read_error`` is
    ``str | None``, exactly ``BoundedStreamState.error``, never a bool.
    """
    source = inspect.getsource(PiRpcSupervisor.stderr_snapshot)
    double = _FakeSupervisor(argv=(), cwd="", environment={}, bounds=None).stderr_snapshot()
    expected_keys = {
        "captured",
        "bytes_seen",
        "bytes_retained",
        "cap_exceeded",
        "eof",
        "read_error",
        "text_tail",
    }
    for key in expected_keys:
        assert f'"{key}"' in source
    assert set(double) == expected_keys
    assert double["read_error"] is None
    assert type(double["captured"]) is bool
    assert type(double["cap_exceeded"]) is bool
    assert type(double["eof"]) is bool
    assert type(double["bytes_seen"]) is int
    assert type(double["bytes_retained"]) is int
    assert type(double["text_tail"]) is str
    assert "error: str | None = None" in inspect.getsource(BoundedStreamState)
