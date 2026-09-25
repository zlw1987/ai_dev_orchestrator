"""CFG1-L16-FU2 -- L16 through the bounded runtime capability probe.

Receive-boundary rows (R-08, R-10, L-06, L-07, the real-supervisor mapping
rows, C-13, C-14) drive the REAL ``PiRpcSupervisor`` over a synthetic peer
under ``tmp_path``; no hand-built dict ever stands in for the wire. The
:class:`FakeSupervisor` with a SCRIPTED probe is used only where CFG1's own
exact-type check and refusal mapping are the subject (design Sec. 12.2).

No row launches Pi, contacts B300, reads a credential or endpoint, opens a
socket, or calls a model.
"""

from __future__ import annotations

import ast
import collections
import inspect
import json
import subprocess
import threading
import time
from pathlib import Path

import pytest

from ar2 import runtime_probe
from ar2 import supervisor as supervisor_module
from ar2.supervisor import PiRpcSupervisor, PiSupervisorError, RunBounds
from cfg1_doubles import (
    FakeExtension,
    StaticIdentityShape,
    FakeSupervisor,
    build_doubled_ports,
    probe_facts_for_arm,
    seam_digests_all_match,
)
from cfg1_fu2_support import cfg1_state_frame, cfg1_supervisor, support

from pi_harness_cfg1 import run_executor
from pi_harness_cfg1.arms import (
    ARM_COMPAT,
    ARM_SHAPE,
    RUNTIME_COMPAT_SHAPES,
    RUNTIME_MODEL_REASONING_VALUES,
    RUNTIME_THINKING_LEVELS,
)
from pi_harness_cfg1.identity import CFG1_MODEL_ID, PROVIDER_ID
from pi_harness_cfg1.records import (
    _require_valid_cfg1_run_payload_v2 as _require_valid_cfg1_run_payload,
    build_cfg1_run_payload,
)
from pi_harness_cfg1.run_contract import Cfg1RunAdmission
from pi_harness_cfg1.run_executor import (
    _PreDispatchRefusal,
    _RunState,
    execute_cfg1_run,
    observe_l16_runtime_capabilities,
)

_EXPERIMENTS = Path(__file__).resolve().parents[2]
SENTINEL = "cfg1-fu2-sentinel-51c0"
UNOBSERVED = (False, "NOT_OBSERVED", "NOT_OBSERVED", "NOT_OBSERVED")


@pytest.fixture(autouse=True)
def _seam_digests(monkeypatch):
    seam_digests_all_match(monkeypatch)


@pytest.fixture()
def admission():
    from pi_harness_cfg1.schedule import _schedule_arm_for, _schedule_block_position

    block, position = _schedule_block_position("S1", 1)
    return Cfg1RunAdmission(
        stage_id="S1",
        stage_execution_id="S1-X1",
        run_ordinal=1,
        arm_id=_schedule_arm_for("S1", 1),
        block=block,
        position=position,
        run_id="feedface" * 4,
    )


def _l16(supervisor, arm_id="Q"):
    state = _RunState(supervisor=supervisor, l14_launched_supervisor=supervisor)
    return observe_l16_runtime_capabilities(state, arm_id=arm_id)


def _l16_refusal(state, arm_id="Q"):
    with pytest.raises(_PreDispatchRefusal) as raised:
        observe_l16_runtime_capabilities(state, arm_id=arm_id)
    return raised.value.code, raised.value.step


def _real(tmp_path, name, frames, **extra):
    peer = support.make_peer(tmp_path, name, **support.respond_config(frames, **extra))
    supervisor = cfg1_supervisor(peer)
    supervisor.launch()
    return supervisor, peer


# ---------------------------------------------------------------------------
# R-10 -- the full L16 through run_executor, REAL supervisor, arm Q
# ---------------------------------------------------------------------------

_PROMPT_FRAMES = [
    '{"type":"response","id":"__ID__","command":"prompt","success":true}',
    json.dumps({"type": "message_end", "message": {"role": "assistant", "stopReason": "stop",
                                                   "content": [{"type": "text", "text": "done"}],
                                                   "reasoning_content": SENTINEL}}),
    json.dumps({"type": "agent_end"}),
    json.dumps({"type": "agent_settled"}),
]


def test_r10_the_full_l16_through_the_executor_with_the_real_supervisor(
    admission, git_executable, tmp_path
):
    assert admission.arm_id == "Q"
    peer = support.make_peer(
        tmp_path, "r10",
        **support.respond_config([cfg1_state_frame("Q")], responses={"prompt": _PROMPT_FRAMES}),
    )
    built: list = []

    def _build_supervisor(**_kwargs):
        supervisor = cfg1_supervisor(peer)
        built.append(supervisor)
        return supervisor

    ports, _made = build_doubled_ports(
        git_executable=git_executable, overrides={"build_supervisor": _build_supervisor}
    )
    try:
        outcome = execute_cfg1_run(admission, ports=ports)
    finally:
        for supervisor in built:
            support.join_readers(supervisor)
    observations = outcome.observations
    assert observations["pre_dispatch_refusal_code"] is None
    assert observations["h2_provider_model_identity_matched"] is True
    assert observations["runtime_reported_model_reasoning"] == "TRUE"
    assert observations["runtime_reported_compat_shape"] == "ABSENT"
    assert observations["runtime_reported_thinking_level"] == "medium"
    assert observations["manipulation_check_agrees"] is True
    assert observations["dispatch_state"] == "CONFIRMED_SENT"
    assert observations["runtime_exit_observed"] is True
    kinds = [command["type"] for command in peer.captured_commands()]
    assert kinds == ["get_state", "prompt"]  # the ONE get_state is the probe's
    payload = build_cfg1_run_payload(
        stage_id="S1", stage_execution_id="S1-X1", run_ordinal=1, observations=observations,
    )
    _require_valid_cfg1_run_payload(payload)
    serialized = json.dumps(payload)
    assert '"reasoning"' not in serialized and SENTINEL not in serialized
    assert support.SYNTHETIC_BASE_URL not in serialized
    assert built[0].commands_sent == ["get_state", "prompt"]


# ---------------------------------------------------------------------------
# R-08 / L-06 / L-07 -- facts come only from the run's own supervisor
# ---------------------------------------------------------------------------


def test_r08_two_real_supervisors_never_mix_their_facts(tmp_path):
    a, _peer_a = _real(tmp_path, "a", [cfg1_state_frame("Q", reasoning=False)])
    b, _peer_b = _real(tmp_path, "b", [cfg1_state_frame("Q", reasoning=True)])
    try:
        b_facts = _l16(b)
        a_facts = _l16(a)
    finally:
        support.close(a)
        support.close(b)
    assert b_facts["runtime_reported_model_reasoning"] == "TRUE"
    assert a_facts["runtime_reported_model_reasoning"] == "FALSE"
    assert a_facts["manipulation_check_agrees"] is False


def test_r35_the_l16_function_has_no_input_for_facts_or_another_supervisor():
    signature = inspect.signature(observe_l16_runtime_capabilities)
    assert list(signature.parameters) == ["state", "arm_id"]
    assert signature.parameters["arm_id"].kind is inspect.Parameter.KEYWORD_ONLY
    for name in signature.parameters:
        for fragment in ("fact", "literal", "response", "document", "verdict", "supervisor",
                         "observation", "probe", "h2", "reasoning", "compat", "thinking"):
            assert fragment not in name
    dispatch = inspect.getsource(run_executor._dispatch_phase)
    assert dispatch.count("observe_l16_runtime_capabilities(") == 1
    assert "observe_l16_runtime_capabilities(state, arm_id=admission.arm_id)" in dispatch
    assert "get_state" not in dispatch.replace("# CFG1-L16-FU2: the ONE get_state", "")
    for name in (field.name for field in run_executor.Cfg1RunPorts.__dataclass_fields__.values()):
        assert "model_identity" not in name and "get_state" not in name and "probe" not in name
    assert not hasattr(run_executor, "project_get_state")
    assert not hasattr(run_executor, "_classify_compat_object")


def test_l06_l16_refuses_any_supervisor_but_the_one_l14_launched(tmp_path):
    a = FakeSupervisor(probe_facts=probe_facts_for_arm("Q"))
    b = FakeSupervisor(probe_facts=probe_facts_for_arm("Q"))
    assert _l16_refusal(_RunState(supervisor=a, l14_launched_supervisor=b)) == (
        "RUNTIME_CORRELATION_FAILED", "L16")
    assert _l16_refusal(_RunState(supervisor=None, l14_launched_supervisor=None)) == (
        "RUNTIME_CORRELATION_FAILED", "L16")
    assert _l16_refusal(_RunState(supervisor=a, l14_launched_supervisor=None)) == (
        "RUNTIME_CORRELATION_FAILED", "L16")
    assert a.probe_calls == 0 and b.probe_calls == 0  # refused BEFORE any probe

    peer = support.make_peer(tmp_path, "never", **support.respond_config([cfg1_state_frame()]))
    never = cfg1_supervisor(peer)
    assert _l16_refusal(_RunState(supervisor=never, l14_launched_supervisor=never)) == (
        "RUNTIME_CORRELATION_FAILED", "L16")
    retired, retired_peer = _real(tmp_path, "retired", [cfg1_state_frame()])
    support.close(retired)
    assert _l16_refusal(_RunState(supervisor=retired, l14_launched_supervisor=retired)) == (
        "RUNTIME_CORRELATION_FAILED", "L16")
    assert [c for c in retired_peer.captured_commands() if c["type"] == "get_state"] == []


def test_l07_facts_retained_past_teardown_have_no_input_path(tmp_path):
    old, _ = _real(tmp_path, "old", [cfg1_state_frame(reasoning=True)])
    try:
        old_facts = _l16(old)
    finally:
        support.close(old)
    assert old_facts["runtime_reported_model_reasoning"] == "TRUE"
    new, _ = _real(tmp_path, "new", [cfg1_state_frame(reasoning=False)])
    try:
        new_facts = _l16(new)
    finally:
        support.close(new)
    assert new_facts["runtime_reported_model_reasoning"] == "FALSE"
    assert _l16_refusal(_RunState(supervisor=old, l14_launched_supervisor=old)) == (
        "RUNTIME_CORRELATION_FAILED", "L16")


# ---------------------------------------------------------------------------
# Real-supervisor mapping rows at CFG1 level (R-18, R-19, R-25, Sec. 8)
# ---------------------------------------------------------------------------


def test_r18_a_bad_correlated_command_maps_to_runtime_correlation_failed(tmp_path):
    frame = support.get_state_frame(command="get_commands")
    supervisor, _ = _real(tmp_path, "r18", [frame])
    try:
        refusal = _l16_refusal(_RunState(supervisor=supervisor, l14_launched_supervisor=supervisor))
    finally:
        support.close(supervisor)
    assert refusal == ("RUNTIME_CORRELATION_FAILED", "L16")


def test_r19_r25_unobserved_or_mismatched_identity_fails_h2_first(tmp_path):
    bounds = RunBounds(startup_deadline_seconds=1.0, shutdown_deadline_seconds=3.0,
                       direct_child_reap_grace_seconds=1.0)
    peer = support.make_peer(tmp_path, "r19", **support.respond_config(
        [support.get_state_frame(success=False)]))
    supervisor = cfg1_supervisor(peer, bounds=bounds)
    supervisor.launch()
    try:
        facts = _l16(supervisor)
    finally:
        support.close(supervisor)
    assert (facts["h2_provider_model_identity_matched"], facts["runtime_reported_model_reasoning"],
            facts["runtime_reported_compat_shape"], facts["runtime_reported_thinking_level"]) == UNOBSERVED

    frame = support.get_state_frame(support.state_data(provider="someone-else", model_id=CFG1_MODEL_ID))
    supervisor, _ = _real(tmp_path, "r25", [frame])
    try:
        facts = _l16(supervisor)
    finally:
        support.close(supervisor)
    assert facts["h2_provider_model_identity_matched"] is False
    assert facts["runtime_reported_model_reasoning"] == "TRUE"


# ---------------------------------------------------------------------------
# CFG1's exact-type check and refusal mapping (scripted-probe double)
# ---------------------------------------------------------------------------


class _StrSubclass(str):
    pass


_Facts = collections.namedtuple("_Facts", "h2 reasoning compat thinking")


@pytest.mark.parametrize(
    "scripted",
    [
        [True, "TRUE", "ABSENT", "medium"],
        (True, "TRUE", "ABSENT"),
        (True, "TRUE", "ABSENT", "medium", "extra"),
        (1, "TRUE", "ABSENT", "medium"),
        ("True", "TRUE", "ABSENT", "medium"),
        (True, "true", "ABSENT", "medium"),
        (True, _StrSubclass("TRUE"), "ABSENT", "medium"),
        (True, "TRUE", "absent", "medium"),
        (True, "TRUE", {"compat": SENTINEL}, "medium"),
        (True, "TRUE", "ABSENT", b"medium"),
        (True, "TRUE", "ABSENT", "MEDIUM"),
        (True, "TRUE", "ABSENT", SENTINEL),
        _Facts(True, "TRUE", "ABSENT", "medium"),
        None,
    ],
    ids=["list", "short", "long", "int-h2", "str-h2", "lower-reasoning", "str-subclass",
         "lower-compat", "dict-compat", "bytes-thinking", "upper-thinking", "sentinel",
         "namedtuple", "none"],
)
def test_l16_refuses_anything_but_exact_types_from_the_closed_domains(
    admission, git_executable, scripted
):
    supervisor = FakeSupervisor(probe_facts=lambda: scripted)
    if scripted is None:
        supervisor.probe_runtime_capabilities = lambda: None  # returned nothing at all
    ports, _made = build_doubled_ports(
        git_executable=git_executable, overrides={"build_supervisor": lambda **kw: supervisor}
    )
    outcome = execute_cfg1_run(admission, ports=ports)
    observations = outcome.observations
    assert observations["pre_dispatch_refusal_code"] == "RUNTIME_CORRELATION_FAILED"
    assert observations["refused_at_step"] == "L16"
    assert observations["h2_provider_model_identity_matched"] is False
    for key in ("runtime_reported_compat_shape", "runtime_reported_model_reasoning",
                "runtime_reported_thinking_level"):
        assert observations[key] == "NOT_OBSERVED"
    assert observations["prompt_writes"] == 0
    assert supervisor.commands_sent == []
    assert SENTINEL not in json.dumps(observations, default=repr)
    assert supervisor.shutdown_calls == 1


def test_l16_a_raising_probe_maps_to_runtime_correlation_failed(admission, git_executable):
    ports, made = build_doubled_ports(
        git_executable=git_executable,
        overrides={"probe_error": RuntimeError(SENTINEL)},
    )
    outcome = execute_cfg1_run(admission, ports=ports)
    assert outcome.observations["pre_dispatch_refusal_code"] == "RUNTIME_CORRELATION_FAILED"
    assert outcome.observations["refused_at_step"] == "L16"
    assert SENTINEL not in json.dumps(outcome.observations, default=repr)
    assert made["supervisor"].probe_calls == 1
    assert made["supervisor"].commands_sent == []


@pytest.mark.parametrize(
    "facts, code",
    [
        ((False, "TRUE", "ABSENT", "medium"), "H2_MISMATCH"),
        (UNOBSERVED, "H2_MISMATCH"),
        ((False, "FALSE", "BOTH_FALSE_ONLY", "off"), "H2_MISMATCH"),  # H2 first
        ((True, "FALSE", "ABSENT", "medium"), "CONFIG_SHAPE_MISMATCH"),
        ((True, "OTHER", "ABSENT", "medium"), "CONFIG_SHAPE_MISMATCH"),
        ((True, "TRUE", "OTHER", "medium"), "CONFIG_SHAPE_MISMATCH"),
        ((True, "TRUE", "ABSENT", "NOT_OBSERVED"), "CONFIG_SHAPE_MISMATCH"),
        ((True, "TRUE", "ABSENT", "medium"), None),
    ],
)
def test_l16_precedence_and_predicate_are_unchanged(admission, git_executable, facts, code):
    ports, made = build_doubled_ports(
        git_executable=git_executable, overrides={"probe_facts": facts}
    )
    outcome = execute_cfg1_run(admission, ports=ports)
    observations = outcome.observations
    assert observations["pre_dispatch_refusal_code"] == code
    if code is not None:
        assert observations["refused_at_step"] == "L16"
        assert observations["prompt_writes"] == 0
    assert observations["h2_provider_model_identity_matched"] is facts[0]
    assert observations["runtime_reported_model_reasoning"] == facts[1]
    payload = build_cfg1_run_payload(
        stage_id="S1", stage_execution_id="S1-X1", run_ordinal=1, observations=observations,
    )
    _require_valid_cfg1_run_payload(payload)


# ---------------------------------------------------------------------------
# R-36 / R-40 -- single classifier definitions; argv/expectation provenance
# ---------------------------------------------------------------------------

_PRODUCTION_TREES = (
    "pi_external_runtime_ar2",
    "pi_external_runtime_ar2_o1",
    "pi_implementer_qualification",
    "pi_harness_cfg1",
)


def _production_files():
    for tree in _PRODUCTION_TREES:
        for path in (_EXPERIMENTS / tree).rglob("*.py"):
            if {"tests", "results"} & set(path.parts):
                continue
            yield path


def test_r36_each_sec82_classifier_has_exactly_one_definition():
    definitions = collections.Counter()
    where = collections.defaultdict(set)
    for path in _production_files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                definitions[node.name] += 1
                where[node.name].add(path.relative_to(_EXPERIMENTS).as_posix())
    for name in ("classify_compat_object", "classify_compat_shape", "classify_thinking_level",
                 "classify_raw_model_reasoning", "classify_correlated_raw_record",
                 "reduce_sanitized_get_state"):
        assert definitions[name] == 1, name
        assert where[name] == {"pi_external_runtime_ar2/ar2/runtime_probe.py"}, name
    for gone in ("project_get_state", "_classify_compat_object"):
        assert definitions[gone] == 0, gone
    # The AR2 literal domains are exactly CFG1's frozen enums.
    assert runtime_probe.MODEL_REASONING_LITERALS == RUNTIME_MODEL_REASONING_VALUES
    assert runtime_probe.COMPAT_SHAPE_LITERALS == RUNTIME_COMPAT_SHAPES
    assert runtime_probe.THINKING_LEVEL_LITERALS == RUNTIME_THINKING_LEVELS
    # ...and the single classifier maps every arm's declared compat to its shape.
    for arm_id, compat in ARM_COMPAT.items():
        model = {} if compat is None else {"compat": dict(compat)}
        assert runtime_probe.classify_compat_shape({"model": model}) == ARM_SHAPE[arm_id]


def test_r40_argv_and_expectations_come_from_the_same_frozen_constants(tmp_path):
    ports = run_executor.default_cfg1_run_ports(ambient_environ={})

    class _Environment:
        @staticmethod
        def as_launch_snapshot():
            return {"SystemRoot": "C:\\Windows"}

    supervisor = ports.build_supervisor(
        identity=StaticIdentityShape(),
        extension=FakeExtension(entry_path=str(tmp_path / "index.ts"), extension_dir=str(tmp_path)),
        environment=_Environment(),
        workspace_root=str(tmp_path),
    )
    argv = list(supervisor.argv)
    provider = argv[argv.index("--provider") + 1]
    model = argv[argv.index("--model") + 1]
    assert provider == supervisor._expected_provider == PROVIDER_ID
    assert model == supervisor._expected_model == CFG1_MODEL_ID
    assert supervisor.process is None  # building launched nothing

    tree = ast.parse(Path(run_executor.__file__).read_text(encoding="utf-8"))
    (builder,) = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_build_supervisor"]
    keywords = {kw.arg: kw.value for call in ast.walk(builder) if isinstance(call, ast.Call)
                for kw in call.keywords}
    for keyword, constant in (("provider", "PROVIDER_ID"), ("model", "CFG1_MODEL_ID"),
                              ("expected_provider", "PROVIDER_ID"),
                              ("expected_model", "CFG1_MODEL_ID")):
        assert isinstance(keywords[keyword], ast.Name) and keywords[keyword].id == constant, keyword
    imports = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module == "identity"]
    imported = {alias.name for node in imports for alias in node.names}
    assert {"PROVIDER_ID", "CFG1_MODEL_ID"} <= imported


# ---------------------------------------------------------------------------
# C-13 / C-14 / C-15 -- the production ``process`` readers
# ---------------------------------------------------------------------------


class _FakeProcess:
    def __init__(self, exited):
        self.polled = 0
        self._exited = exited

    def poll(self):
        self.polled += 1
        return 0 if self._exited else None


def _p8_expression():
    """The semantic adapter's P8 gate, read from its PRODUCTION source."""
    path = _EXPERIMENTS / "pi_implementer_qualification" / "qualification" / "semantic_live_adapters.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    tests = [node.test for node in ast.walk(tree) if isinstance(node, ast.If)
             and "supervisor.process" in ast.unparse(node.test)]
    assert len(tests) == 1
    source = ast.unparse(tests[0])
    assert source == "supervisor.process is None or supervisor.process.poll() is not None"
    return compile(ast.Expression(tests[0]), str(path), "eval")


def test_c13_the_semantic_p8_gate_sees_only_the_genuine_child(tmp_path):
    p8 = _p8_expression()
    fakes = [_FakeProcess(False), _FakeProcess(True)]
    supervisor, peer = _real(tmp_path, "c13", [cfg1_state_frame()])
    try:
        for value in (None, *fakes):
            with pytest.raises(AttributeError):
                supervisor.process = value
        assert eval(p8, {"supervisor": supervisor}) is False  # genuine child runs
        supervisor.send_command({"type": "exit_now"})
        support.join_readers(supervisor)
        deadline = time.monotonic() + 5
        while supervisor.process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        for value in (None, *fakes):
            with pytest.raises(AttributeError):
                supervisor.process = value
        assert eval(p8, {"supervisor": supervisor}) is True  # genuine child exited
    finally:
        support.close(supervisor)
    assert all(fake.polled == 0 for fake in fakes)


def _partially_launched(tmp_path, monkeypatch, name):
    class _FailingStderr(supervisor_module.BoundedStreamReader):
        def start(self):
            raise RuntimeError("injected reader start failure")

    original = supervisor_module.BoundedStreamReader
    monkeypatch.setattr(supervisor_module, "BoundedStreamReader", _FailingStderr)
    peer = support.make_peer(tmp_path, name, **support.respond_config([cfg1_state_frame()]))
    supervisor = cfg1_supervisor(peer)
    with pytest.raises(RuntimeError):
        supervisor.launch()
    monkeypatch.setattr(supervisor_module, "BoundedStreamReader", original)
    return supervisor, peer


def test_c14_the_partial_launch_ownership_decision_cannot_be_forged(tmp_path, monkeypatch):
    from qualification.i2b_live_adapters import LiveCategoryBAdapters

    supervisor, peer = _partially_launched(tmp_path, monkeypatch, "c14")
    genuine = supervisor.process
    assert genuine is not None
    substitute = _FakeProcess(True)
    for value in (None, substitute):
        with pytest.raises(AttributeError):
            supervisor.process = value
    # the qualification adapter's check and its retain-and-close path
    assert (supervisor.process is None) is False
    observation = LiveCategoryBAdapters._retain_and_close_partial_runtime(
        None, supervisor=supervisor, extension_dir=""
    )
    support.join_readers(supervisor)
    assert observation.resource_created is True and observation.cleanup_attempted is True
    assert observation.direct_child_reported_exit is True
    assert genuine.poll() is not None and substitute.polled == 0
    # CFG1's L14 fact and L21 decision see the same genuine child
    assert (getattr(supervisor, "process", None) is not None) is True

    # The opposite states: Popen OSError, and the orphan path, both read None.
    failed = PiRpcSupervisor(argv=(str(tmp_path / "missing.exe"),), cwd=str(tmp_path),
                             environment={}, bounds=support.FAST_BOUNDS)
    with pytest.raises(PiSupervisorError):
        failed.launch()
    assert failed.process is None
    assert getattr(failed, "process", None) is None

    created, go = threading.Event(), threading.Event()
    children: list = []
    real_popen = subprocess.Popen

    def _held_popen(*args, **kwargs):
        child = real_popen(*args, **kwargs)
        children.append(child)
        created.set()
        go.wait(5)
        return child

    monkeypatch.setattr(supervisor_module.subprocess, "Popen", _held_popen)
    orphan_peer = support.make_peer(tmp_path, "c14_orphan", **support.respond_config([cfg1_state_frame()]))
    orphaned = cfg1_supervisor(orphan_peer)
    thread, box = support.run_in_thread(orphaned.launch)
    assert created.wait(5)
    orphaned.shutdown()
    go.set()
    thread.join(15)
    monkeypatch.setattr(supervisor_module.subprocess, "Popen", real_popen)
    assert isinstance(box.get("error"), PiSupervisorError)
    assert orphaned.process is None
    assert children[0].poll() is not None  # already torn down by the launching call


def test_c14_cfg1_l14_and_l21_see_the_genuine_partial_runtime(
    admission, git_executable, tmp_path, monkeypatch
):
    class _FailingStderr(supervisor_module.BoundedStreamReader):
        def start(self):
            raise RuntimeError("injected reader start failure")

    monkeypatch.setattr(supervisor_module, "BoundedStreamReader", _FailingStderr)
    peer = support.make_peer(tmp_path, "c14_cfg1", **support.respond_config([cfg1_state_frame()]))
    built: list = []

    def _build_supervisor(**_kwargs):
        supervisor = cfg1_supervisor(peer)
        built.append(supervisor)
        return supervisor

    ports, _made = build_doubled_ports(
        git_executable=git_executable, overrides={"build_supervisor": _build_supervisor}
    )
    try:
        outcome = execute_cfg1_run(admission, ports=ports)
    finally:
        for supervisor in built:
            support.join_readers(supervisor)
    observations = outcome.observations
    assert observations["pre_dispatch_refusal_code"] == "RUNTIME_LAUNCH_FAILED"
    assert observations["refused_at_step"] == "L14"
    assert observations["runtime_created"] is True  # L14 saw the genuine child
    assert observations["runtime_exit_observed"] is True  # L21 called shutdown()
    assert built[0].process.poll() is not None


def test_c15_the_production_process_readers_are_exactly_the_reviewed_inventory():
    reads = []
    for path in _production_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        owner = {}
        for function in ast.walk(tree):
            if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for node in ast.walk(function):
                    owner[node] = function.name
        relative = path.relative_to(_EXPERIMENTS).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "process":
                assert isinstance(node.ctx, ast.Load), (relative, "write/delete of .process")
                parent = parents[node]
                # a valid read-only use: `is None` / `is not None`, or `.poll()`
                assert (
                    isinstance(parent, ast.Compare) and isinstance(parent.ops[0], (ast.Is, ast.IsNot))
                ) or (isinstance(parent, ast.Attribute) and parent.attr == "poll"), relative
                reads.append((relative, owner.get(node), "attribute"))
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in ("getattr", "setattr", "delattr", "hasattr")
                    and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant)
                    and node.args[1].value == "process"):
                assert node.func.id == "getattr", (relative, node.func.id)
                parent = parents[node]
                assert isinstance(parent, ast.Compare) and isinstance(parent.ops[0], ast.IsNot)
                reads.append((relative, owner.get(node), "getattr"))
            if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) \
                    and node.slice.value == "process" and "__dict__" in ast.unparse(node.value):
                raise AssertionError((relative, "namespace injection of process"))
    assert sorted(reads) == sorted([
        ("pi_external_runtime_ar2_o1/o1/handshake.py", "launch_and_handshake", "attribute"),
        ("pi_implementer_qualification/qualification/i2b_live_adapters.py", "launch_runtime", "attribute"),
        ("pi_implementer_qualification/qualification/semantic_live_adapters.py", "dispatch_semantic_prompt", "attribute"),
        ("pi_implementer_qualification/qualification/semantic_live_adapters.py", "dispatch_semantic_prompt", "attribute"),
        ("pi_harness_cfg1/run_executor.py", "_dispatch_phase", "getattr"),
        ("pi_harness_cfg1/run_executor.py", "_closure_phase", "getattr"),
    ])
