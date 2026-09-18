"""CFG1-L16-FU2 -- child-resource ownership and the read-only ``process`` (C-rows).

Oracle, per design Sec. 11.3c: (1) a process-like SUBSTITUTE's call log, which
must stay empty; (2) the genuine peer's stdin capture and observed exit; (3) an
identity log, recorded by test-side wrappers on the GENUINE child's own methods,
of the object every consumption acted on.

Rows marked *white-box* deliberately rebind a PRIVATE attribute, in tests only,
to show that the Sec. 5.6.2 verification fails closed for a smuggled binding.
That is a defense-in-depth demonstration, not a claim about the supported API.
C-13, C-14 and C-15 read the qualification and CFG1 trees and live in the CFG1
suite.
"""

from __future__ import annotations

import ast
import inspect
import subprocess
import textwrap
import threading
import time
from pathlib import Path

import pytest

from ar2 import supervisor as supervisor_module
from ar2.supervisor import (
    CHILD_BINDING_UNVERIFIED,
    LAUNCH_REFUSED,
    PiRpcSupervisor,
    PiSupervisorError,
    RunBounds,
)

from probe_support import (
    FAST_BOUNDS,
    Recorder,
    close,
    frame,
    get_state_frame,
    join_readers,
    make_peer,
    make_supervisor,
    reap_raw_child,
    respond_config,
    run_in_thread,
)

GOOD = get_state_frame()
FACTS = (True, "TRUE", "ABSENT", "medium")
GET_COMMANDS = [frame({"type": "response", "id": "__ID__", "command": "get_commands",
                       "success": True, "data": {"commands": []}})]


def _peer(tmp_path, name="peer", **extra):
    responses = dict(extra.pop("responses", {}))
    responses.setdefault("get_commands", GET_COMMANDS)
    return make_peer(tmp_path, name, **respond_config([GOOD], responses=responses, **extra))


def _instrument_child(child, identity_log, pre_hook=None, fake_terminate=False):
    """Wrap the GENUINE child's own methods (test-only) to log what each consumption hit."""
    for name in ("poll", "wait", "terminate", "kill"):
        real = getattr(child, name)

        def _wrapper(*args, _real=real, _name=name, **kwargs):
            identity_log.append((_name, child))
            if pre_hook is not None:
                pre_hook(_name)
            if _name == "terminate" and fake_terminate:
                return None  # test-only: survive terminate so the kill rung is reached
            return _real(*args, **kwargs)

        setattr(child, name, _wrapper)


def _instrument_writes(monkeypatch, write_log, pre_hook=None):
    real = supervisor_module._write_frame

    def _write(stream, payload):
        write_log.append(stream)
        if pre_hook is not None:
            pre_hook("write")
        return real(stream, payload)

    monkeypatch.setattr(supervisor_module, "_write_frame", _write)
    return real


def _attempt_substitution(supervisor, substitute, expected):
    """Every attempt on ``process`` must REFUSE and leave the observation unchanged."""
    with pytest.raises(AttributeError):
        supervisor.process = substitute
    with pytest.raises(AttributeError):
        del supervisor.process
    with pytest.raises(AttributeError):
        setattr(supervisor, "process", None)
    with pytest.raises(AttributeError):
        object.__setattr__(supervisor, "process", substitute)
    assert supervisor.process is expected


def _commands(peer, kind):
    return [command for command in peer.captured_commands() if command.get("type") == kind]


def test_c01_substitution_after_launch_is_refused_and_nothing_is_retargeted(tmp_path, monkeypatch):
    substitute_log: list = []
    substitute = Recorder(substitute_log)
    peer = _peer(tmp_path)
    supervisor = make_supervisor(peer)
    supervisor.launch()
    genuine = supervisor.process
    binding = supervisor._runtime_child
    identity: list = []
    writes: list = []
    _instrument_child(genuine, identity)
    _instrument_writes(monkeypatch, writes)
    try:
        _attempt_substitution(supervisor, substitute, genuine)
        supervisor.orphan_termination = substitute  # a public diagnostic; inert
        supervisor.send_command({"id": "c01", "type": "get_commands"})
        outcome, response = supervisor.await_response("c01", timeout_seconds=4)
        assert response is not None
        facts = supervisor.probe_runtime_capabilities()
        record = supervisor.shutdown()
    finally:
        join_readers(supervisor)
    assert facts == FACTS
    assert substitute_log == []
    assert identity and all(target is genuine for _name, target in identity)
    assert {name for name, _t in identity} >= {"poll", "wait"}
    assert writes and all(stream is binding.stdin for stream in writes)
    assert len(_commands(peer, "get_commands")) == 1 and len(_commands(peer, "get_state")) == 1
    assert record["exit_status_observed"] is not None
    assert genuine.poll() is not None and peer.saw_eof()
    assert supervisor.process is genuine


def test_c02_boundary_sweep_every_action_lands_on_the_genuine_child(tmp_path, monkeypatch):
    substitute_log: list = []
    substitute = Recorder(substitute_log)
    peer = _peer(tmp_path, mode="ignore_eof", max_lifetime=30)
    bounds = RunBounds(startup_deadline_seconds=4.0, shutdown_deadline_seconds=1.0,
                       direct_child_reap_grace_seconds=0.5)
    supervisor = make_supervisor(peer, bounds=bounds)
    _attempt_substitution(supervisor, substitute, None)  # before launch
    supervisor.launch()
    genuine = supervisor.process
    boundaries: list = []

    def _sweep(boundary):
        boundaries.append(boundary)
        _attempt_substitution(supervisor, substitute, genuine)

    identity: list = []
    writes: list = []
    _instrument_child(genuine, identity, pre_hook=_sweep, fake_terminate=True)
    _instrument_writes(monkeypatch, writes, pre_hook=_sweep)
    real_settled = supervisor._probe_write_settled

    def _before_stdin_close(timeout):
        _sweep("before_stdin_close")
        return real_settled(timeout)

    supervisor._probe_write_settled = _before_stdin_close
    try:
        _sweep("before_probe_commit")
        facts = supervisor.probe_runtime_capabilities()
        record = supervisor.shutdown()
    finally:
        join_readers(supervisor)
        reap_raw_child(genuine)
    assert facts == FACTS
    assert {"write", "poll", "before_stdin_close", "wait", "terminate", "kill"} <= set(boundaries)
    assert record["direct_child_kill_sent"] is True
    assert record["rung_reached"] == "exited_after_kill"
    assert substitute_log == []
    assert all(target is genuine for _name, target in identity)
    assert all(stream is supervisor._runtime_child.stdin for stream in writes)


def test_c03_retirement_then_substitution_retargets_nothing(tmp_path, monkeypatch):
    substitute_log: list = []
    substitute = Recorder(substitute_log)
    peer = _peer(tmp_path)
    supervisor = make_supervisor(peer)
    supervisor.launch()
    genuine = supervisor.process
    identity: list = []
    _instrument_child(genuine, identity)
    supervisor._retire()  # test-only: retirement WITHOUT the ladder
    with pytest.raises(PiSupervisorError):
        supervisor.probe_runtime_capabilities()
    _attempt_substitution(supervisor, substitute, genuine)
    record = supervisor.shutdown()
    join_readers(supervisor)
    assert _commands(peer, "get_state") == []  # zero probe bytes
    assert record["exit_status_observed"] is not None
    assert genuine.poll() is not None
    assert substitute_log == []
    assert all(target is genuine for _name, target in identity)
    assert supervisor.process is genuine


def test_c03_substitution_during_an_in_flight_probe_write_retargets_nothing(tmp_path, monkeypatch):
    substitute_log: list = []
    substitute = Recorder(substitute_log)
    peer = _peer(tmp_path)
    supervisor = make_supervisor(peer)
    supervisor.launch()
    genuine = supervisor.process
    at_write, release = threading.Event(), threading.Event()
    real_write = supervisor_module._write_frame

    def _held(stream, payload):
        at_write.set()
        release.wait(5)
        return real_write(stream, payload)

    monkeypatch.setattr(supervisor_module, "_write_frame", _held)
    probe_thread, probe_box = run_in_thread(supervisor.probe_runtime_capabilities)
    try:
        assert at_write.wait(5)
        shut_thread, shut_box = run_in_thread(supervisor.shutdown)
        time.sleep(0.3)
        _attempt_substitution(supervisor, substitute, genuine)
        release.set()
        probe_thread.join(10)
        shut_thread.join(10)
    finally:
        release.set()
        join_readers(supervisor)
    assert substitute_log == []
    assert shut_box["result"]["exit_status_observed"] is not None
    assert len(_commands(peer, "get_state")) == 1 and peer.saw_eof()
    assert isinstance(probe_box["error"], PiSupervisorError)


def test_c04_rebinding_the_exposed_childs_pipes_is_inert(tmp_path):
    recorder_log: list = []
    peer = _peer(tmp_path)
    supervisor = make_supervisor(peer)
    supervisor.launch()
    genuine = supervisor.process
    originals = (genuine.stdin, genuine.stdout, genuine.stderr)
    genuine.stdin = Recorder(recorder_log, "stdin")
    genuine.stdout = Recorder(recorder_log, "stdout")
    genuine.stderr = Recorder(recorder_log, "stderr")
    try:
        supervisor.send_command({"id": "c04", "type": "get_commands"})
        assert supervisor.await_response("c04", timeout_seconds=4)[1] is not None
        facts = supervisor.probe_runtime_capabilities()
        record = supervisor.shutdown()
    finally:
        genuine.stdin, genuine.stdout, genuine.stderr = originals
        join_readers(supervisor)
    assert facts == FACTS
    assert recorder_log == []
    assert len(_commands(peer, "get_commands")) == 1 and len(_commands(peer, "get_state")) == 1
    assert peer.saw_eof()  # the CAPTURED stdin was closed
    assert record["stdin_closed"] is True


def _orphan_run(tmp_path, monkeypatch, name, *, before_teardown=None):
    """Launch racing retirement so L3 orphans the child. Returns (supervisor, peer, child)."""
    created, go = threading.Event(), threading.Event()
    children: list = []
    real_popen = subprocess.Popen

    def _popen(*args, **kwargs):
        child = real_popen(*args, **kwargs)
        children.append(child)
        created.set()
        go.wait(5)
        return child

    monkeypatch.setattr(supervisor_module.subprocess, "Popen", _popen)
    peer = _peer(tmp_path, name)
    supervisor = make_supervisor(peer)
    if before_teardown is not None:
        real_teardown = supervisor._teardown_orphan

        def _held_teardown(orphan, created_child):
            before_teardown(supervisor, created_child)
            return real_teardown(orphan, created_child)

        supervisor._teardown_orphan = _held_teardown
    thread, box = run_in_thread(supervisor.launch)
    assert created.wait(5)
    supervisor.shutdown()
    go.set()
    thread.join(20)
    monkeypatch.setattr(supervisor_module.subprocess, "Popen", real_popen)
    assert isinstance(box.get("error"), PiSupervisorError)
    assert str(box["error"]) == LAUNCH_REFUSED
    return supervisor, peer, children[0]


def test_c05_the_orphan_surface_cannot_be_substituted(tmp_path, monkeypatch):
    substitute_log: list = []
    substitute = Recorder(substitute_log)
    identity: list = []
    observed_process: list = []

    def _before_teardown(supervisor, child):
        _instrument_child(child, identity)
        observed_process.append(supervisor.process)
        _attempt_substitution(supervisor, substitute, None)
        supervisor.orphan_termination = substitute  # public diagnostic; inert
        supervisor.termination = substitute

    supervisor, peer, child = _orphan_run(tmp_path, monkeypatch, "c05", before_teardown=_before_teardown)
    assert observed_process == [None]
    assert supervisor.process is None
    assert substitute_log == []
    assert identity and all(target is child for _name, target in identity)
    assert child.poll() is not None and peer.saw_eof()
    assert supervisor.orphan_termination["exit_status_observed"] is not None


def test_c06_i_a_smuggled_orphan_binding_makes_every_runtime_consumption_fail_closed(
    tmp_path, monkeypatch
):
    donor, _donor_peer, donor_child = _orphan_run(tmp_path, monkeypatch, "c06_donor")
    peer = _peer(tmp_path, "c06_victim")
    supervisor = make_supervisor(peer)
    supervisor.launch()
    genuine = supervisor.process
    identity: list = []
    _instrument_child(genuine, identity)
    _instrument_child(donor_child, identity)
    writes: list = []
    real_write = _instrument_writes(monkeypatch, writes)
    supervisor._orphan_child = donor._orphan_child  # WHITE-BOX smuggling
    try:
        for action in (
            lambda: supervisor.send_command({"id": "x", "type": "get_commands"}),
            lambda: supervisor.probe_runtime_capabilities(),
            lambda: supervisor.await_response("x", timeout_seconds=1),
            lambda: supervisor.shutdown(),
        ):
            with pytest.raises(PiSupervisorError) as raised:
                action()
            assert str(raised.value) in (CHILD_BINDING_UNVERIFIED, "supervisor error: runtime capability probe refused")
        assert writes == [] and identity == []
        assert peer.captured_commands() == []
        assert supervisor._lifecycle == "RETIRED"  # retirement still happened first
    finally:
        monkeypatch.setattr(supervisor_module, "_write_frame", real_write)
        supervisor._orphan_child = None
        close(supervisor)


def test_c06_ii_a_runtime_binding_in_the_orphan_slot_fails_teardown_closed(tmp_path, monkeypatch):
    other_peer = _peer(tmp_path, "c06ii_other")
    other = make_supervisor(other_peer)
    other.launch()
    identity: list = []

    def _smuggle(supervisor, child):
        _instrument_child(child, identity)
        _instrument_child(other.process, identity)
        supervisor._orphan_child = other._runtime_child  # WHITE-BOX smuggling

    try:
        supervisor, peer, child = _orphan_run(tmp_path, monkeypatch, "c06ii", before_teardown=_smuggle)
        assert identity == []  # no action on either child
        assert supervisor.orphan_termination["verification_failed"] is True
        assert child.poll() is None  # left running, loudly, never retargeted
        assert other.process.poll() is None
    finally:
        reap_raw_child(child)
        close(other)

    for cls_member in (PiRpcSupervisor.__init__, PiRpcSupervisor.launch):
        for parameter in inspect.signature(cls_member).parameters:
            for fragment in ("child", "pipe", "binding", "process", "stdin", "popen"):
                assert fragment not in parameter.lower()
    for name, member in inspect.getmembers(PiRpcSupervisor, predicate=inspect.isfunction):
        if name.startswith("_"):
            continue
        for parameter in inspect.signature(member).parameters:
            for fragment in ("child", "pipe", "binding", "process", "stdin", "popen"):
                assert fragment not in parameter.lower(), (name, parameter)


def test_c07_a_cross_supervisor_binding_fails_the_owner_check(tmp_path, monkeypatch):
    peer_a, peer_b = _peer(tmp_path, "a"), _peer(tmp_path, "b")
    a, b = make_supervisor(peer_a), make_supervisor(peer_b)
    a.launch()
    b.launch()
    own_binding = a._runtime_child
    identity: list = []
    _instrument_child(a.process, identity)
    _instrument_child(b.process, identity)
    with pytest.raises(AttributeError):
        a.process = b.process  # supported API: refused
    assert a.process is own_binding.child
    a._runtime_child = b._runtime_child  # WHITE-BOX smuggling
    try:
        for action in (
            lambda: a.send_command({"id": "x", "type": "get_commands"}),
            lambda: a.probe_runtime_capabilities(),
            lambda: a.await_response("x", timeout_seconds=1),
            lambda: a.shutdown(),
        ):
            with pytest.raises(PiSupervisorError):
                action()
        assert identity == []
        assert peer_a.captured_commands() == [] and peer_b.captured_commands() == []
    finally:
        a._runtime_child = own_binding
        close(a)
        close(b)


def test_c08_mutating_compatibility_fields_changes_no_target(tmp_path, monkeypatch):
    peer = _peer(tmp_path)
    supervisor = make_supervisor(peer)
    supervisor.launch()
    trusted = supervisor._runtime_child
    supervisor.commands_sent = ["forged"]
    supervisor.stdin_write_error = "forged"
    supervisor.termination = {"forged": True}
    supervisor.orphan_termination = {"forged": True}
    with pytest.raises(AttributeError):
        supervisor.process = None
    identity: list = []
    writes: list = []
    _instrument_child(trusted.child, identity)
    _instrument_writes(monkeypatch, writes)
    try:
        supervisor.send_command({"id": "c08", "type": "get_commands"})
        assert supervisor.await_response("c08", timeout_seconds=4)[1] is not None
        assert supervisor.probe_runtime_capabilities() == FACTS
        supervisor.shutdown()
    finally:
        join_readers(supervisor)
    assert supervisor._runtime_child is trusted
    assert all(target is trusted.child for _name, target in identity)
    assert writes and all(stream is trusted.stdin for stream in writes)
    assert trusted.child.poll() is not None


def test_c10_retirement_invalidates_operation_authority_but_never_retargets(tmp_path):
    peer = _peer(tmp_path)
    supervisor = make_supervisor(peer)
    supervisor.launch()
    binding = supervisor._runtime_child
    parts = (binding.child, binding.stdin, binding.stdout, binding.stderr, binding.role, binding.owner)
    identity: list = []
    _instrument_child(binding.child, identity)
    supervisor._retire()
    with pytest.raises(PiSupervisorError):
        supervisor.probe_runtime_capabilities()
    assert supervisor._runtime_child is binding
    assert all(a is b for a, b in zip(parts, (binding.child, binding.stdin, binding.stdout,
                                             binding.stderr, binding.role, binding.owner)))
    record = supervisor.shutdown()
    join_readers(supervisor)
    assert _commands(peer, "get_state") == []
    assert record["exit_status_observed"] is not None
    assert identity and all(target is binding.child for _name, target in identity)


# ---------------------------------------------------------------------------
# C-11 -- source / AST checks on ar2/supervisor.py
# ---------------------------------------------------------------------------


def _supervisor_tree():
    return ast.parse(Path(supervisor_module.__file__).read_text(encoding="utf-8"))


def _enclosing_functions(tree):
    parents = {}
    for function in ast.walk(tree):
        if isinstance(function, ast.FunctionDef):
            for node in ast.walk(function):
                parents.setdefault(node, function.name)
    return parents


def _is_binding_member(node, member):
    return (isinstance(node, ast.Attribute) and node.attr == member
            and isinstance(node.value, ast.Name) and node.value.id == "binding")


def test_c11_every_consumption_takes_its_target_from_the_ownership_binding():
    tree = _supervisor_tree()
    owner = _enclosing_functions(tree)
    popen_calls = []
    for node in ast.walk(tree):
        # no read of a ``process`` attribute anywhere in the module
        if isinstance(node, ast.Attribute) and node.attr == "process":
            raise AssertionError(f"a read of .process in {owner.get(node)}")
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        attr, receiver = node.func.attr, node.func.value
        if attr == "Popen":
            popen_calls.append(owner.get(node))
        if attr in ("poll", "terminate", "kill"):
            assert _is_binding_member(receiver, "child"), (attr, owner.get(node))
        if attr == "wait":
            allowed = _is_binding_member(receiver, "child") or (
                isinstance(receiver, ast.Attribute) and receiver.attr == "finished")
            assert allowed, owner.get(node)
        if attr in ("write", "flush"):
            assert owner.get(node) == "_write_frame"
        if attr == "close":
            assert _is_binding_member(receiver, "stdin") or (
                isinstance(receiver, ast.Name) and receiver.id == "pipe"), owner.get(node)
    assert popen_calls == ["launch"]  # exactly one child-creation site
    # the write routine's stream argument always comes from the binding
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_write_frame":
            first = node.args[0]
            assert _is_binding_member(first, "stdin") or (
                isinstance(first, ast.Name) and first.id == "target"), owner.get(node)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in (
                "RecordStreamReader", "BoundedStreamReader"):
            expected = "stdout" if node.func.id == "RecordStreamReader" else "stderr"
            assert _is_binding_member(node.args[0], expected)
    source = inspect.getsource(PiRpcSupervisor.probe_runtime_capabilities)
    assert "target = binding.stdin" in source


def test_c11_only_l3_and_the_unwinding_bind_write_the_bindings():
    tree = _supervisor_tree()
    writers: dict[str, set] = {"_runtime_child": set(), "_orphan_child": set()}
    for function in ast.walk(tree):
        if not isinstance(function, ast.FunctionDef):
            continue
        for node in ast.walk(function):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Attribute) and target.attr in writers:
                        writers[target.attr].add((function.name, ast.unparse(node.value)))
    runtime_values = {value for name, value in writers["_runtime_child"] if name != "__init__"}
    orphan_values = {value for name, value in writers["_orphan_child"] if name != "__init__"}
    assert {name for name, _ in writers["_runtime_child"]} == {"__init__", "_bind_install_or_orphan"}
    assert {name for name, _ in writers["_orphan_child"]} == {
        "__init__", "_bind_install_or_orphan", "_unwind_failed_launch"}
    assert runtime_values == {"_capture_child(child, role=_ROLE_RUNTIME, owner=self)"}
    assert orphan_values == {"_capture_child(child, role=_ROLE_ORPHAN, owner=self)"}
    assert ("__init__", "None") in writers["_runtime_child"]
    assert ("__init__", "None") in writers["_orphan_child"]


# ---------------------------------------------------------------------------
# C-12 -- the ``process`` contract, state by state
# ---------------------------------------------------------------------------


class _FakeProcess:
    def __init__(self, exited: bool) -> None:
        self.polled = 0
        self._exited = exited

    def poll(self):
        self.polled += 1
        return 0 if self._exited else None


def _assert_process_contract(supervisor, expected, foreign_popen):
    for value in (None, _FakeProcess(False), _FakeProcess(True), foreign_popen):
        with pytest.raises(AttributeError):
            supervisor.process = value
        assert supervisor.process is expected
    with pytest.raises(AttributeError):
        del supervisor.process
    supervisor.__dict__["process"] = _FakeProcess(False)  # WHITE-BOX namespace injection
    try:
        assert supervisor.process is expected  # a data descriptor is never shadowed
    finally:
        del supervisor.__dict__["process"]
    assert supervisor.process is expected


def test_c12_process_is_determined_solely_by_the_runtime_child_binding(tmp_path, monkeypatch):
    foreign_peer = _peer(tmp_path, "foreign")
    foreign = make_supervisor(foreign_peer)
    foreign.launch()
    foreign_popen = foreign.process
    cleanup = [foreign]
    try:
        # never launched
        fresh = make_supervisor(_peer(tmp_path, "fresh"))
        _assert_process_contract(fresh, None, foreign_popen)

        # retired before its first launch; a refused launch leaves it None
        retired_first = make_supervisor(_peer(tmp_path, "retired_first"))
        retired_first.shutdown()
        with pytest.raises(PiSupervisorError):
            retired_first.launch()
        _assert_process_contract(retired_first, None, foreign_popen)

        # after an L2 OSError
        failed = PiRpcSupervisor(argv=(str(tmp_path / "missing.exe"),), cwd=str(tmp_path),
                                 environment={}, bounds=FAST_BOUNDS)
        with pytest.raises(PiSupervisorError):
            failed.launch()
        _assert_process_contract(failed, None, foreign_popen)

        # installed; a repeated launch leaves it; after shutdown it is still the child
        installed = make_supervisor(_peer(tmp_path, "installed"))
        installed.launch()
        cleanup.append(installed)
        genuine = installed.process
        assert genuine is installed._runtime_child.child
        _assert_process_contract(installed, genuine, foreign_popen)
        with pytest.raises(PiSupervisorError):
            installed.launch()
        _assert_process_contract(installed, genuine, foreign_popen)
        close(installed)
        _assert_process_contract(installed, genuine, foreign_popen)
        with pytest.raises(PiSupervisorError):
            installed.launch()
        _assert_process_contract(installed, genuine, foreign_popen)

        # partial install failure
        class _FailingStderr(supervisor_module.BoundedStreamReader):
            def start(self):
                raise RuntimeError("injected")

        monkeypatch.setattr(supervisor_module, "BoundedStreamReader", _FailingStderr)
        partial = make_supervisor(_peer(tmp_path, "partial"))
        with pytest.raises(RuntimeError):
            partial.launch()
        monkeypatch.undo()
        cleanup.append(partial)
        partial_child = partial.process
        assert partial_child is not None and partial_child is partial._runtime_child.child
        _assert_process_contract(partial, partial_child, foreign_popen)
        with pytest.raises(PiSupervisorError):
            partial.launch()
        _assert_process_contract(partial, partial_child, foreign_popen)
    finally:
        for supervisor in cleanup:
            close(supervisor)

    # the orphan path, and mid-launch before L3
    held_process: list = []

    def _observe(supervisor, child):
        held_process.append(supervisor.process)

    orphaned, _peer_o, orphan_child = _orphan_run(tmp_path, monkeypatch, "c12_orphan",
                                                  before_teardown=_observe)
    assert held_process == [None]
    _assert_process_contract(orphaned, None, foreign_popen)
    with pytest.raises(PiSupervisorError):
        orphaned.launch()
    _assert_process_contract(orphaned, None, foreign_popen)

    # introspection: a property with no setter, no deleter, and no alias
    descriptor = vars(PiRpcSupervisor)["process"]
    assert isinstance(descriptor, property)
    assert descriptor.fset is None and descriptor.fdel is None
    assert [name for name, value in vars(PiRpcSupervisor).items() if isinstance(value, property)] == ["process"]
    getter = ast.parse(textwrap.dedent(inspect.getsource(descriptor.fget)))
    assert "_runtime_child" in ast.unparse(getter)
    init_source = inspect.getsource(PiRpcSupervisor.__init__)
    assert "self.process" not in init_source
    probe = make_supervisor(_peer(tmp_path, "vars"))
    probe.launch()
    try:
        assert not [name for name, value in vars(probe).items() if value is probe.process]
    finally:
        close(probe)
