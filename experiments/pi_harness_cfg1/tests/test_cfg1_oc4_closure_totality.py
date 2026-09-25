"""OC-4 (Closure-Ladder Totality): the frozen Sec. 13 regression matrix.

Everything runs the GENUINE ``execute_cfg1_run`` over the doubled ports: no Node,
no Pi, no socket, no credential, no model. Each fault test asserts, at minimum,

  (i)   ``execute_cfg1_run`` RETURNED a ``Cfg1RunOutcome``;
  (ii)  the faulting step's fact(s) are at their fail-closed value;
  (iii) every later APPLICABLE step's call was made (a call recorder);
  (iv)  ``lifecycle_failure_steps`` is exactly ``compute_lifecycle_closure_v2`` of
        the observations and names the owning step;
  (v)   no hostile marker appears anywhere in the outcome, and every committed
        value is an exact plain type (I-9).

Minimum-case numbers from the design's Sec. 13 are cited in each test's docstring
or parametrization id as ``[n]``.
"""

from __future__ import annotations

import ast
import inspect
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from cfg1_doubles import (
    FakeBroker,
    FakeRepositorySnapshot,
    FakeSupervisor,
    FakeVerificationOutcome,
    build_doubled_ports,
    seam_digests_all_match,
)
from cfg1_fu1_support import make_admission

from pi_harness_cfg1 import (
    config_issuance,
    extension_issuance,
    run_executor,
    run_workspace,
    stage_runner,
)
from pi_harness_cfg1.lifecycle import compute_lifecycle_closure_v2
from pi_harness_cfg1.records import _require_valid_cfg1_run_payload_v2, build_cfg1_run_payload
from pi_harness_cfg1.run_contract import Cfg1RunOutcome
from pi_harness_cfg1.run_executor import execute_cfg1_run

MARKER = "OC4-HOSTILE-MARKER-c81e"
RAISE = object()

_PACKAGE = Path(run_executor.__file__).resolve().parent

_PLAIN_SCALARS = (bool, int, str, type(None))


# ---------------------------------------------------------------------------
# Hostile foreign objects
# ---------------------------------------------------------------------------


class Hostile:
    """Every accessor a closure region might touch executes hostile code."""

    def __getattr__(self, name):
        if name.startswith("__"):  # keep pytest / copy protocols out of the way
            raise AttributeError(name)
        raise RuntimeError(MARKER)

    def __getitem__(self, key):
        raise RuntimeError(MARKER)

    def get(self, *args, **kwargs):
        raise RuntimeError(MARKER)

    def __eq__(self, other):
        raise RuntimeError(MARKER)

    def __bool__(self):
        raise RuntimeError(MARKER)

    def __iter__(self):
        raise RuntimeError(MARKER)

    def __len__(self):
        raise RuntimeError(MARKER)

    def __int__(self):
        raise RuntimeError(MARKER)

    def __index__(self):
        raise RuntimeError(MARKER)

    __hash__ = object.__hash__

    def __repr__(self):
        return MARKER

    __str__ = __repr__


class HostileDict(dict):
    """An exact-looking mapping whose every accessor raises."""

    def get(self, *args, **kwargs):
        raise RuntimeError(MARKER)

    def __getitem__(self, key):
        raise RuntimeError(MARKER)

    def __contains__(self, key):
        raise RuntimeError(MARKER)

    def __iter__(self):
        raise RuntimeError(MARKER)

    def __repr__(self):
        return MARKER


class QuietDictSubclass(dict):
    """A dict subclass that does NOT raise: exact-type rejection alone must refuse it."""


class IntLike:
    def __int__(self):
        return 0

    def __index__(self):
        return 0

    def __eq__(self, other):
        return True

    __hash__ = object.__hash__

    def __repr__(self):
        return MARKER


class EqHostile(str):
    """A ``str`` SUBCLASS whose ``__eq__`` lies -- exact-type must refuse it first."""

    def __eq__(self, other):
        return True

    __hash__ = str.__hash__


class EqRaises:
    def __eq__(self, other):
        raise RuntimeError(MARKER)

    __hash__ = object.__hash__

    def __repr__(self):
        return MARKER


class EqReturnsForeign:
    def __eq__(self, other):
        return Hostile()

    __hash__ = object.__hash__

    def __repr__(self):
        return MARKER


# ---------------------------------------------------------------------------
# Scripted doubles that record the call sequence
# ---------------------------------------------------------------------------


class RecSupervisor(FakeSupervisor):
    """A FakeSupervisor whose closure methods are scripted and recorded."""

    def __init__(self, calls, script, *, process_mode="launch", **kwargs):
        super().__init__(**kwargs)
        self._calls = calls
        self._script = script
        self._process_mode = process_mode
        self._process = None
        self.process_reads = 0
        self._launch_count = 0

    @property
    def process(self):
        self.process_reads += 1
        mode = self._process_mode
        if mode == "launch":
            return self._process
        if mode == "object":
            return object()
        if mode == "none":
            return None
        if mode == "raise":
            raise RuntimeError(MARKER)
        if mode == "none_then_object":  # L14's own read sees None, closure's sees one
            return None if self.process_reads == 1 else object()
        if mode == "none_then_raise":
            if self.process_reads == 1:
                return None
            raise RuntimeError(MARKER)
        raise AssertionError(mode)

    @process.setter
    def process(self, value):
        self._process = value

    def launch(self):
        self._launch_count += 1
        return super().launch()

    def _scripted(self, name, default):
        self._calls.append(name)
        value = self._script.get(name, default)
        if value is RAISE:
            raise RuntimeError(MARKER)
        return value

    def shutdown(self):
        self.shutdown_calls += 1
        return self._scripted("shutdown", {"exit_status_observed": 0, "stdin_closed": True})

    def stdout_state(self):
        return self._scripted("stdout_state", {"records_ingested": 1, "eof": True})

    def stderr_snapshot(self):
        return self._scripted("stderr_snapshot", {"captured": True, "eof": True})


class RecBroker(FakeBroker):
    def __init__(self, calls, script):
        super().__init__()
        self._calls = calls
        self._script = script

    def _scripted(self, name, default):
        self._calls.append(name)
        value = self._script.get(name, default)
        if value is RAISE:
            raise RuntimeError(MARKER)
        return value

    def diagnostics_counts(self):
        return self._scripted("diagnostics_counts", dict(self.counts))

    def shutdown_for_cfg1(self):
        self.shutdown_calls += 1
        return self._scripted("shutdown_for_cfg1", dict(self.lifecycle))


class RaisingOutcome:
    """A verification outcome one of whose accessors raises."""

    def __init__(self, member, **members):
        self._member = member
        self._members = members

    def __getattr__(self, name):
        if name == self._member:
            raise RuntimeError(MARKER)
        try:
            return self._members[name]
        except KeyError:
            raise AttributeError(name) from None


def _good_outcome(**overrides):
    return replace(FakeVerificationOutcome(), **overrides)


class Run:
    """The result of one driven closure: outcome, ordered closure calls, doubles."""

    def __init__(self, outcome, calls, made, supervisor, broker):
        self.outcome = outcome
        self.obs = outcome.observations
        self.calls = calls
        self.made = made
        self.supervisor = supervisor
        self.broker = broker


def drive(
    git_executable,
    monkeypatch,
    *,
    sup=None,
    broker=None,
    process_mode="launch",
    supervisor_kwargs=None,
    scrub_config=None,
    scrub_extension=None,
    remove=None,
    discard=None,
    l27_reproof_raises=False,
    l25_reproof_raises=False,
    observe=None,
    verify=None,
    refuse_before_launch=None,
    launch_error=None,
    admission=None,
):
    """Run the genuine executor once over scripted, recording doubles.

    ``scrub_*`` / ``remove`` / ``discard``: ``None`` -> the REAL function;
    ``RAISE`` -> raise without touching the real function (registry entry
    survives); ``("returns", v)`` -> call the real function, then return ``v``;
    ``("after", None)`` -> call the real function, then raise; any other value
    is returned in place of the real function's result.
    """
    seam_digests_all_match(monkeypatch)
    calls: list[str] = []
    sup_script = dict(sup or {})
    broker_script = dict(broker or {})
    verify_count = [0]

    def _wrap(module, attr, label, mode, only_from=None):
        real = getattr(module, attr)

        def _fn(*args, **kwargs):
            if only_from is not None and inspect.currentframe().f_back.f_code.co_name != only_from:
                return real(*args, **kwargs)  # e.g. discard called from inside the real remover
            calls.append(label)
            if mode is RAISE:
                raise RuntimeError(MARKER)
            if type(mode) is tuple and mode[0] == "returns":
                real(*args, **kwargs)
                return mode[1]
            if type(mode) is tuple and mode[0] == "after":
                real(*args, **kwargs)
                raise RuntimeError(MARKER)
            if mode is not None:
                return mode
            return real(*args, **kwargs)

        monkeypatch.setattr(module, attr, _fn)

    _wrap(config_issuance, "scrub_config_issuance", "scrub_config", scrub_config)
    _wrap(extension_issuance, "scrub_extension_issuance", "scrub_extension", scrub_extension)
    _wrap(run_workspace, "remove_cfg1_run_workspace", "remove", remove)
    _wrap(
        run_workspace, "discard_cfg1_run_workspace", "discard", discard,
        only_from="_closure_l27_workspace",
    )

    real_verify = run_workspace.verify_cfg1_run_workspace

    def _verify(workspace):
        caller = inspect.currentframe().f_back.f_code.co_name
        if caller == "_closure_l27_workspace" and l27_reproof_raises:
            raise RuntimeError(MARKER)
        if caller == "_closure_l25_git_observation_1" and l25_reproof_raises:
            raise RuntimeError(MARKER)
        return real_verify(workspace)

    monkeypatch.setattr(run_workspace, "verify_cfg1_run_workspace", _verify)

    if refuse_before_launch == "reproof_false":
        monkeypatch.setattr(run_executor, "reprove_pi_identity_for_launch", lambda *a, **k: False)
    elif refuse_before_launch == "reproof_raises":

        def _boom(*a, **k):
            raise RuntimeError(MARKER)

        monkeypatch.setattr(run_executor, "reprove_pi_identity_for_launch", _boom)

    supervisor_holder: dict = {}
    broker_holder: dict = {}

    def _build_supervisor(**_kwargs):
        supervisor = RecSupervisor(
            calls,
            sup_script,
            process_mode=process_mode,
            launch_error=launch_error,
            **(supervisor_kwargs or {}),
        )
        supervisor_holder["s"] = supervisor
        return supervisor

    def _build_broker(*, capability):
        made_broker = RecBroker(calls, broker_script)
        broker_holder["b"] = made_broker
        return made_broker

    def _observe(*, workspace_root):
        calls.append("observe_repository")
        if observe is None:
            return FakeRepositorySnapshot()
        value = observe(len([c for c in calls if c == "observe_repository"]))
        if value is RAISE:
            raise RuntimeError(MARKER)
        return value

    def _run_verification(*, workspace_root, args):
        verify_count[0] += 1
        if verify_count[0] == 1:  # the L3 dispatch baseline, not a closure call
            return _good_outcome()
        calls.append("run_verification")
        if verify is None:
            return _good_outcome()
        if verify is RAISE:
            raise RuntimeError(MARKER)
        return verify

    ports, made = build_doubled_ports(
        git_executable=git_executable,
        overrides={
            "build_supervisor": _build_supervisor,
            "build_broker": _build_broker,
            "observe_repository": _observe,
            "run_verification": _run_verification,
        },
    )
    outcome = execute_cfg1_run(admission or make_admission(), ports=ports)
    return Run(outcome, calls, made, supervisor_holder.get("s"), broker_holder.get("b"))


def _plain(value, where="observations"):
    if type(value) is dict:
        for key, member in value.items():
            assert type(key) is str, where
            _plain(member, f"{where}.{key}")
    elif type(value) is list:
        for index, member in enumerate(value):
            _plain(member, f"{where}[{index}]")
    else:
        assert type(value) in _PLAIN_SCALARS, (where, type(value))


def check(run: Run) -> Run:
    """(i), (iv), (v) for every run."""
    outcome = run.outcome
    assert type(outcome) is Cfg1RunOutcome
    assert MARKER not in repr(outcome.observations)
    assert MARKER not in json.dumps(outcome.observations, default=repr)
    assert MARKER not in repr(outcome.console_codes)
    _plain(outcome.observations)
    closed, steps = compute_lifecycle_closure_v2(outcome.observations)
    assert run.obs["lifecycle_all_closed"] is closed
    assert run.obs["lifecycle_failure_steps"] == list(steps)
    return run


def payload_of(run: Run) -> dict:
    payload = build_cfg1_run_payload(
        stage_id="S1", stage_execution_id="S1-X1", run_ordinal=1, observations=run.obs
    )
    _require_valid_cfg1_run_payload_v2(payload)
    assert MARKER not in json.dumps(payload)
    return payload


def closure_calls(run: Run) -> list[str]:
    return list(run.calls)


FULL_SEQUENCE = [
    "shutdown",
    "stdout_state",
    "stderr_snapshot",
    "diagnostics_counts",
    "shutdown_for_cfg1",
    "scrub_config",
    "scrub_extension",
    "observe_repository",
    "run_verification",
    "observe_repository",
    "remove",
]


def cleanup(run: Run) -> None:
    """Best-effort disposal of a tree a deliberately-failed L27 left on disk."""
    workspace = run.made.get("workspace")
    if workspace is not None:
        shutil.rmtree(workspace.experiment_root, ignore_errors=True)


# ---------------------------------------------------------------------------
# Baseline: the ladder as shipped still runs whole, in order
# ---------------------------------------------------------------------------


def test_the_unfaulted_ladder_runs_every_step_once_in_the_frozen_order(
    git_executable, monkeypatch
):
    run = check(drive(git_executable, monkeypatch))
    assert closure_calls(run) == FULL_SEQUENCE
    assert run.obs["lifecycle_all_closed"] is True
    assert run.obs["runtime_exit_observed"] is True
    assert run.obs["runtime_transport_eof_observed"] is True
    assert run.obs["broker_state_closed"] is True
    assert run.obs["workspace_removed_verified"] is True
    assert run_workspace.minted_workspace_count() == 0


# ---------------------------------------------------------------------------
# G-L21 -- runtime teardown
# ---------------------------------------------------------------------------

_SHUTDOWN_MALFORMED = [
    pytest.param(RAISE, id="raises[1]"),
    pytest.param(None, id="None[2]"),
    pytest.param([], id="list[3]"),
    pytest.param("exit", id="str[3]"),
    pytest.param(Hostile(), id="foreign-object[3,4]"),
    pytest.param(HostileDict(), id="hostile-dict-subclass[3,4]"),
    pytest.param(QuietDictSubclass(exit_status_observed=0), id="quiet-dict-subclass[3]"),
    pytest.param({"exit_status_observed": True}, id="bool-exit[3]"),
    pytest.param({"exit_status_observed": "0"}, id="str-exit[3]"),
    pytest.param({"exit_status_observed": 0.0}, id="float-exit[3]"),
    pytest.param({"exit_status_observed": IntLike()}, id="int-like-exit[3]"),
    pytest.param({"stdin_closed": True}, id="member-missing[3]"),
    pytest.param({"exit_status_observed": None}, id="None-exit[3]"),
]


@pytest.mark.parametrize("shutdown", _SHUTDOWN_MALFORMED)
def test_l21_a_malformed_shutdown_never_yields_a_positive_exit_fact(
    git_executable, monkeypatch, shutdown
):
    run = check(drive(git_executable, monkeypatch, sup={"shutdown": shutdown}))
    assert run.obs["runtime_exit_observed"] is False
    assert "L21" in run.obs["lifecycle_failure_steps"]
    # (iii) every later applicable step was still attempted; L26 is a SEMANTIC
    # skip (`LIFECYCLE_UNPROVEN`), and L27 still removed the workspace.
    assert closure_calls(run) == [
        "shutdown",
        "stdout_state",
        "stderr_snapshot",
        "diagnostics_counts",
        "shutdown_for_cfg1",
        "scrub_config",
        "scrub_extension",
        "observe_repository",
        "remove",
    ]
    assert run.obs["verification_skip_reason"] == "LIFECYCLE_UNPROVEN"
    assert run.obs["workspace_removed_verified"] is True
    # the two reader observations are independent of the exit one
    assert run.obs["runtime_transport_eof_observed"] is True


@pytest.mark.parametrize("status", [0, 1, -1, 137])
def test_l21_an_exact_int_exit_status_including_zero_and_negative_is_observed(
    git_executable, monkeypatch, status
):
    run = check(
        drive(git_executable, monkeypatch, sup={"shutdown": {"exit_status_observed": status}})
    )
    assert run.obs["runtime_exit_observed"] is True


_EOF_MALFORMED = [
    pytest.param(RAISE, id="raises[5,7]"),
    pytest.param(None, id="None"),
    pytest.param([], id="list"),
    pytest.param(Hostile(), id="foreign-object"),
    pytest.param(HostileDict(), id="hostile-dict-subclass"),
    pytest.param(QuietDictSubclass(eof=True), id="quiet-dict-subclass"),
    pytest.param({"records_ingested": 0}, id="eof-missing[6,8]"),
    pytest.param({"eof": 1}, id="eof-1[6,8]"),
    pytest.param({"eof": "true"}, id="eof-str[6,8]"),
    pytest.param({"eof": False}, id="eof-False"),
]


@pytest.mark.parametrize("state", _EOF_MALFORMED)
def test_l21_a_malformed_stdout_state_never_proves_transport_eof(
    git_executable, monkeypatch, state
):
    run = check(drive(git_executable, monkeypatch, sup={"stdout_state": state}))
    assert run.obs["runtime_transport_eof_observed"] is False
    assert run.obs["runtime_exit_observed"] is True  # its own region, unaffected
    assert "L21" in run.obs["lifecycle_failure_steps"]
    # stderr is observed EVEN WHEN stdout failed / is not at EOF [6]
    assert "stderr_snapshot" in run.calls
    assert run.calls.index("stderr_snapshot") == run.calls.index("stdout_state") + 1
    assert "remove" in run.calls


@pytest.mark.parametrize("state", _EOF_MALFORMED)
def test_l21_a_malformed_stderr_snapshot_never_proves_transport_eof(
    git_executable, monkeypatch, state
):
    run = check(drive(git_executable, monkeypatch, sup={"stderr_snapshot": state}))
    assert run.obs["runtime_transport_eof_observed"] is False
    assert run.obs["runtime_exit_observed"] is True
    assert "L21" in run.obs["lifecycle_failure_steps"]
    assert "remove" in run.calls


def test_l21_all_three_sub_operations_fail_in_one_run_and_each_is_attempted_once(
    git_executable, monkeypatch
):
    """[8]"""
    run = check(
        drive(
            git_executable,
            monkeypatch,
            sup={"shutdown": RAISE, "stdout_state": None, "stderr_snapshot": Hostile()},
        )
    )
    assert run.calls[:3] == ["shutdown", "stdout_state", "stderr_snapshot"]
    assert run.calls.count("shutdown") == run.calls.count("stdout_state") == 1
    assert run.obs["runtime_exit_observed"] is False
    assert run.obs["runtime_transport_eof_observed"] is False
    assert "remove" in run.calls


def test_l21_raw_diagnostic_members_are_never_read(git_executable, monkeypatch):
    """Only ``exit_status_observed`` and ``eof`` are ever read."""

    reads: list[str] = []

    class Spy(dict):
        def get(self, key, *default):
            reads.append(key)
            return dict.get(self, key, *default)

        def __getitem__(self, key):
            reads.append(key)
            return dict.__getitem__(self, key)

    # exact-type rejection means a Spy is refused outright: nothing is read at all
    spy = Spy(exit_status_observed=0, text_tail=MARKER, stdin_close_error=MARKER)
    run = check(drive(git_executable, monkeypatch, sup={"shutdown": spy}))
    assert reads == []
    assert run.obs["runtime_exit_observed"] is False

    genuine_shape = {
        "exit_status_observed": 0,
        "text_tail": MARKER,
        "stdin_close_error": MARKER,
        "claim_scope": MARKER,
    }
    run = check(
        drive(
            git_executable,
            monkeypatch,
            sup={
                "shutdown": genuine_shape,
                "stdout_state": {"eof": True, "text_tail": MARKER},
                "stderr_snapshot": {"eof": True, "text_tail": MARKER},
            },
        )
    )
    assert run.obs["lifecycle_all_closed"] is True


# ---- D-3 / launch-attempt provenance [7A-7G] -------------------------------


@pytest.mark.parametrize("claim", ["object", "raise"])
@pytest.mark.parametrize("refusal", ["reproof_false", "reproof_raises"])
def test_7a_7b_7f_a_built_but_never_launched_supervisor_grants_no_cleanup_authority(
    git_executable, monkeypatch, claim, refusal
):
    """[7A] [7B] [7F]: a pre-launch ``process`` claim -- present or raising -- can
    never cause a shutdown, and the accessor is not even consulted."""
    run = check(
        drive(git_executable, monkeypatch, process_mode=claim, refuse_before_launch=refusal)
    )
    assert run.obs["refused_at_step"] == "L14"
    assert run.supervisor is not None  # it WAS built
    assert run.supervisor._launch_count == 0  # launch() was never called
    assert run.supervisor.shutdown_calls == 0
    assert "shutdown" not in run.calls
    assert run.supervisor.process_reads == 0  # not consulted at all
    assert run.obs["runtime_created"] is False
    assert run.obs["runtime_exit_observed"] is False
    # ...and the ladder still ran for what WAS created
    assert "shutdown_for_cfg1" in run.calls
    assert "remove" in run.calls


@pytest.mark.parametrize(
    "mode,l14_reads_none",
    [
        pytest.param("none_then_object", True, id="7C-present"),
        pytest.param("none_then_raise", True, id="7D-accessor-raises"),
        pytest.param("raise", False, id="7D-l14-read-itself-raises"),
    ],
)
def test_7c_7d_launch_attempted_and_raised_moves_runtime_created_false_to_true(
    git_executable, monkeypatch, mode, l14_reads_none
):
    run = check(
        drive(
            git_executable,
            monkeypatch,
            process_mode=mode,
            launch_error=RuntimeError(MARKER),
        )
    )
    assert run.supervisor._launch_count == 1
    assert run.obs["runtime_created"] is True  # False -> True, on AIDO's own attempt
    assert run.supervisor.shutdown_calls == 1  # L21 was applicable and attempted
    assert run.calls[0] == "shutdown"
    # later closure steps still proceed
    assert "shutdown_for_cfg1" in run.calls and "remove" in run.calls
    assert run.obs["verification_skip_reason"] == "PRE_DISPATCH_REFUSAL"
    # the frozen v2 validator accepts the resulting combination
    payload = payload_of(run)
    assert payload["runtime_created"] is True


def test_7e_launch_attempted_and_process_exactly_none_stays_not_created(
    git_executable, monkeypatch
):
    run = check(
        drive(
            git_executable,
            monkeypatch,
            process_mode="none",
            launch_error=RuntimeError(MARKER),
        )
    )
    assert run.supervisor._launch_count == 1
    assert run.obs["runtime_created"] is False
    assert run.supervisor.shutdown_calls == 0
    assert "shutdown" not in run.calls
    payload_of(run)


def test_7g_the_launch_attempt_fact_is_in_memory_only(git_executable, monkeypatch, tmp_path):
    run = check(drive(git_executable, monkeypatch, launch_error=RuntimeError(MARKER)))
    assert not any("launch_attempt" in key for key in run.obs)
    assert "launch_attempt" not in json.dumps(payload_of(run))
    assert "launch_attempt" not in json.dumps(list(run.outcome.console_codes))

    # nothing a caller can hand in carries it: not the ports, not the admission
    for name in run_executor.Cfg1RunPorts.__dataclass_fields__:
        assert "launch_attempt" not in name
    assert "launch_attempt" not in json.dumps(
        {name: str(value) for name, value in vars(make_admission()).items()}
    )


def test_7g_the_launch_attempt_fact_is_true_only_after_a_call_to_launch():
    state = run_executor._RunState()
    assert state.runtime_launch_attempted is False


# ---------------------------------------------------------------------------
# G-L22 -- broker diagnostic counts
# ---------------------------------------------------------------------------

_GOOD = {"read_operations": 3, "edit_operations": 2, "edited_paths": 1, "refusals": 4}

_COUNTS_MALFORMED = [
    pytest.param(RAISE, id="raises[10]"),
    pytest.param(None, id="None[11]"),
    pytest.param([1, 2, 3, 4], id="list[11]"),
    pytest.param(QuietDictSubclass(_GOOD), id="dict-subclass[11]"),
    pytest.param(HostileDict(_GOOD), id="hostile-mapping[11]"),
    pytest.param(Hostile(), id="foreign-object[11]"),
]
for _key in _GOOD:
    for _label, _bad in (
        ("bool", True),
        ("negative", -1),
        ("float", 2.0),
        ("numeric-str", "2"),
        ("int-like", IntLike()),
        ("missing", "MISSING"),
    ):
        _members = dict(_GOOD)
        if _bad == "MISSING":
            del _members[_key]
        else:
            _members[_key] = _bad
        _COUNTS_MALFORMED.append(pytest.param(_members, id=f"{_key}-{_label}-nonzero-siblings[12]"))


@pytest.mark.parametrize("counts", _COUNTS_MALFORMED)
def test_l22_any_malformed_count_makes_the_family_unavailable_with_all_zero_counts(
    git_executable, monkeypatch, counts
):
    run = check(drive(git_executable, monkeypatch, broker={"diagnostics_counts": counts}))
    assert run.obs["broker_recorded_activity_available"] is False
    for key in (
        "broker_recorded_read_operation_count",
        "broker_recorded_edit_operation_count",
        "broker_recorded_edited_path_count",
        "broker_recorded_refusal_count",
    ):
        assert run.obs[key] == 0 and type(run.obs[key]) is int
    payload_of(run)  # the run record validates (no UNAVAILABLE_..._CARRIES_COUNTS)
    # L23 (and everything after) still ran
    assert run.calls[run.calls.index("diagnostics_counts") + 1] == "shutdown_for_cfg1"
    assert "remove" in run.calls
    assert "L22" not in run.obs["lifecycle_failure_steps"]  # diagnostic, not closure


def test_l22_all_four_exact_counts_are_committed_as_available(git_executable, monkeypatch):
    run = check(drive(git_executable, monkeypatch, broker={"diagnostics_counts": dict(_GOOD)}))
    assert run.obs["broker_recorded_activity_available"] is True
    assert run.obs["broker_recorded_read_operation_count"] == 3
    assert run.obs["broker_recorded_edit_operation_count"] == 2
    assert run.obs["broker_recorded_edited_path_count"] == 1
    assert run.obs["broker_recorded_refusal_count"] == 4


# ---------------------------------------------------------------------------
# G-L23 -- broker shutdown
# ---------------------------------------------------------------------------

_GOOD_LIFECYCLE = {
    "state_reached": "CLOSED",
    "pending_operations_unreaped": 0,
    "worker_termination_observed": True,
}
_L23_FACTS = (
    "broker_state_closed",
    "broker_pending_unreaped_zero",
    "broker_worker_terminated_or_absent",
)


@pytest.mark.parametrize(
    "lifecycle",
    [
        pytest.param(RAISE, id="raises[13]"),
        pytest.param(None, id="None[14]"),
        pytest.param("CLOSED", id="str[14]"),
        pytest.param([], id="list[14]"),
        pytest.param(QuietDictSubclass(_GOOD_LIFECYCLE), id="dict-subclass[14]"),
        pytest.param(HostileDict(_GOOD_LIFECYCLE), id="hostile-mapping[14]"),
        pytest.param(Hostile(), id="foreign-object[14]"),
    ],
)
def test_l23_a_malformed_container_fails_all_three_facts(git_executable, monkeypatch, lifecycle):
    run = check(drive(git_executable, monkeypatch, broker={"shutdown_for_cfg1": lifecycle}))
    for fact in _L23_FACTS:
        assert run.obs[fact] is False
    assert "L23" in run.obs["lifecycle_failure_steps"]
    # L24-L27 ran (L26 is the semantic LIFECYCLE_UNPROVEN skip)
    assert run.calls[-4:] == ["scrub_config", "scrub_extension", "observe_repository", "remove"]
    assert run.obs["verification_skip_reason"] == "LIFECYCLE_UNPROVEN"


_MISSING = object()

_L23_MEMBER_CASES = [
    ("state_reached", "OPEN", "broker_state_closed"),
    ("state_reached", None, "broker_state_closed"),
    ("state_reached", 7, "broker_state_closed"),
    ("state_reached", EqHostile("OPEN"), "broker_state_closed"),  # str subclass, lying __eq__
    ("state_reached", EqRaises(), "broker_state_closed"),  # [15] raising __eq__
    ("state_reached", EqReturnsForeign(), "broker_state_closed"),  # [15] non-bool __eq__
    ("state_reached", _MISSING, "broker_state_closed"),
    ("pending_operations_unreaped", 1, "broker_pending_unreaped_zero"),
    ("pending_operations_unreaped", False, "broker_pending_unreaped_zero"),  # bool is not int
    ("pending_operations_unreaped", 0.0, "broker_pending_unreaped_zero"),
    ("pending_operations_unreaped", "0", "broker_pending_unreaped_zero"),
    ("pending_operations_unreaped", IntLike(), "broker_pending_unreaped_zero"),
    ("pending_operations_unreaped", _MISSING, "broker_pending_unreaped_zero"),
    ("worker_termination_observed", False, "broker_worker_terminated_or_absent"),
    ("worker_termination_observed", 1, "broker_worker_terminated_or_absent"),
    ("worker_termination_observed", "true", "broker_worker_terminated_or_absent"),
    ("worker_termination_observed", Hostile(), "broker_worker_terminated_or_absent"),
    ("worker_termination_observed", _MISSING, "broker_worker_terminated_or_absent"),  # M-4
]


@pytest.mark.parametrize(
    "member,value,failed_fact",
    [pytest.param(m, v, f, id=f"{m}-{i}[15]") for i, (m, v, f) in enumerate(_L23_MEMBER_CASES)],
)
def test_l23_each_member_is_an_independent_proof(
    git_executable, monkeypatch, member, value, failed_fact
):
    lifecycle = dict(_GOOD_LIFECYCLE)
    if value is _MISSING:
        del lifecycle[member]
    else:
        lifecycle[member] = value
    run = check(drive(git_executable, monkeypatch, broker={"shutdown_for_cfg1": lifecycle}))
    for fact in _L23_FACTS:
        assert run.obs[fact] is (fact != failed_fact), (member, fact)
    assert "L23" in run.obs["lifecycle_failure_steps"]
    # Only broker_state_closed is a member of L26's frozen five-fact eligibility
    # conjunction; the other two L23 facts fail the lifecycle but not that gate.
    if failed_fact == "broker_state_closed":
        assert run.calls[-4:] == ["scrub_config", "scrub_extension", "observe_repository", "remove"]
    else:
        assert run.calls[-6:] == [
            "scrub_config", "scrub_extension", "observe_repository",
            "run_verification", "observe_repository", "remove",
        ]


def test_l23_worker_error_text_is_never_read(git_executable, monkeypatch):
    lifecycle = dict(_GOOD_LIFECYCLE, worker_error=MARKER)
    run = check(drive(git_executable, monkeypatch, broker={"shutdown_for_cfg1": lifecycle}))
    assert run.obs["lifecycle_all_closed"] is True


# ---------------------------------------------------------------------------
# G-L24 -- scrub independence (AMEND2 preserved)
# ---------------------------------------------------------------------------

_SCRUB_FAULTS = [
    pytest.param(RAISE, id="raises"),
    pytest.param(False, id="returns-False"),
    pytest.param(None.__class__, id="returns-a-type-not-True"),
    pytest.param(1, id="returns-1-not-True"),
    pytest.param(Hostile(), id="returns-hostile"),
]


@pytest.mark.parametrize("fault", _SCRUB_FAULTS)
def test_l24_a_config_scrub_fault_never_suppresses_the_extension_scrub(
    git_executable, monkeypatch, fault
):
    """[16]"""
    run = check(drive(git_executable, monkeypatch, scrub_config=fault))
    assert run.obs["generated_config_scrub_verified"] is False
    assert run.obs["extension_binding_scrub_verified"] is True
    assert run.calls.index("scrub_extension") == run.calls.index("scrub_config") + 1
    assert "observe_repository" in run.calls and "remove" in run.calls
    assert "L24" in run.obs["lifecycle_failure_steps"]
    assert run.obs["verification_skip_reason"] == "LIFECYCLE_UNPROVEN"
    cleanup(run)


@pytest.mark.parametrize("fault", _SCRUB_FAULTS)
def test_l24_an_extension_scrub_fault_never_suppresses_l25_or_l27(
    git_executable, monkeypatch, fault
):
    """[17]"""
    run = check(drive(git_executable, monkeypatch, scrub_extension=fault))
    assert run.obs["extension_binding_scrub_verified"] is False
    assert run.obs["generated_config_scrub_verified"] is True
    assert run.calls[-2:] == ["observe_repository", "remove"]
    assert "L24" in run.obs["lifecycle_failure_steps"]
    cleanup(run)


@pytest.mark.parametrize("which", ["config", "extension"])
def test_l24_a_token_accessor_that_raises_is_an_unproven_scrub_not_an_escape(
    git_executable, monkeypatch, which
):
    """[16] [17] (E-8 / E-9): the token READ is inside the containment."""

    class TokenRaises:
        @property
        def issuance_token(self):
            raise RuntimeError(MARKER)

    seam_digests_all_match(monkeypatch)
    calls: list[str] = []
    state = run_executor._RunState()
    ports, made = build_doubled_ports(git_executable=git_executable)
    workspace, _built = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
    made["workspace"] = workspace
    state.workspace = workspace
    if which == "config":
        state.generated_config = TokenRaises()
        assert run_executor._scrub_generated_config(state) is False
        state.generated_config = Hostile()
        assert run_executor._scrub_generated_config(state) is False
    else:
        state.extension = TokenRaises()
        assert run_executor._scrub_extension_binding(state) is False
        state.extension = Hostile()
        assert run_executor._scrub_extension_binding(state) is False
    run_workspace.discard_cfg1_run_workspace(workspace)
    shutil.rmtree(workspace.experiment_root, ignore_errors=True)


def test_l24_a_hostile_token_accessor_in_the_full_ladder_leaves_every_later_step_running(
    git_executable, monkeypatch
):
    """[16] through the whole executor: hostile config object at L24."""

    class TokenRaises:
        def __init__(self, real):
            self._real = real

        @property
        def issuance_token(self):
            raise RuntimeError(MARKER)

        def __getattr__(self, name):
            return getattr(self._real, name)

    seam_digests_all_match(monkeypatch)

    original = run_executor._closure_l24_scrubs

    def _swap(state, observations):
        if state.generated_config is not None:
            state.generated_config = TokenRaises(state.generated_config)
        return original(state, observations)

    monkeypatch.setattr(run_executor, "_closure_l24_scrubs", _swap)
    run = check(drive(git_executable, monkeypatch))
    assert run.obs["generated_config_scrub_verified"] is False
    assert run.obs["extension_binding_scrub_verified"] is True
    assert "scrub_extension" in run.calls  # the extension scrub still ran
    assert run.calls[-2:] == ["observe_repository", "remove"]
    cleanup(run)


# ---------------------------------------------------------------------------
# G-L25 -- Git observation #1
# ---------------------------------------------------------------------------

_NOT_PERFORMED_1 = {
    "head_moved": False,
    "changed_tracked_paths": [],
    "untracked_path_count": 0,
    "staged_path_count": 0,
}


def test_l25_workspace_authority_verification_failure_is_a_not_performed_observation(
    git_executable, monkeypatch
):
    """[18]"""
    run = check(drive(git_executable, monkeypatch, l25_reproof_raises=True))
    assert run.obs["git_observation_1_performed"] is False
    for key, value in _NOT_PERFORMED_1.items():
        assert run.obs[key] == value
    # L26 and L27 still proceed; observation #1 never blocks closure
    assert "run_verification" in run.calls
    assert run.calls[-1] == "remove"
    assert "L25" not in run.obs["lifecycle_failure_steps"]


def test_l25_observer_raise_is_a_not_performed_observation(git_executable, monkeypatch):
    """[19]"""
    run = check(
        drive(git_executable, monkeypatch, observe=lambda n: RAISE if n == 1 else FakeRepositorySnapshot())
    )
    assert run.obs["git_observation_1_performed"] is False
    assert run.obs["git_observation_2_performed"] is True
    assert "run_verification" in run.calls and run.calls[-1] == "remove"


@pytest.mark.parametrize(
    "snapshot",
    [
        FakeRepositorySnapshot(head=None),
        FakeRepositorySnapshot(changed_tracked_paths="src/app.py"),
        FakeRepositorySnapshot(changed_tracked_paths=("src/app.py", 7)),
        FakeRepositorySnapshot(untracked_path_count=True),
        FakeRepositorySnapshot(staged_path_count=-1),
        Hostile(),
    ],
)
def test_l25_a_malformed_snapshot_takes_the_not_performed_shape(
    git_executable, monkeypatch, snapshot
):
    """[20]"""
    run = check(drive(git_executable, monkeypatch, observe=lambda n: snapshot if n == 1 else FakeRepositorySnapshot()))
    assert run.obs["git_observation_1_performed"] is False
    for key, value in _NOT_PERFORMED_1.items():
        assert run.obs[key] == value
    assert "run_verification" in run.calls and run.calls[-1] == "remove"


# ---------------------------------------------------------------------------
# G-L26 -- verification + Git observation #2
# ---------------------------------------------------------------------------

_VERIF_COUNT_KEYS = ("passed", "failed", "error")
_SENTINEL_COUNTS = {key: None for key in _VERIF_COUNT_KEYS}


def test_l26_run_verification_raising_takes_the_frozen_port_raise_shape(
    git_executable, monkeypatch
):
    """[21]"""
    run = check(drive(git_executable, monkeypatch, verify=RAISE))
    assert run.obs["verification_attempted"] is True
    assert run.obs["verification_child_reaped_or_not_started"] is False
    assert run.obs["verification_started"] is False
    assert run.obs["verification_counts"] == {"passed": 0, "failed": 0, "error": 0}
    assert "L26" in run.obs["lifecycle_failure_steps"]
    # Git observation #2 and L27 are still attempted [23]
    assert run.calls[-2:] == ["observe_repository", "remove"]
    assert run.obs["git_observation_2_performed"] is True


@pytest.mark.parametrize(
    "member",
    ["started", "completed", "timed_out", "output_limit_exceeded", "return_code", "counts", "passed"],
)
def test_l26_an_accessor_that_raises_discards_the_whole_projection(
    git_executable, monkeypatch, member
):
    """[22] [23]: no member of a partially read outcome is committed."""
    members = dict(
        started=True, completed=True, timed_out=False, output_limit_exceeded=False,
        return_code=1, passed=True, counts={"passed": 5, "failed": 5, "error": 5},
    )
    run = check(drive(git_executable, monkeypatch, verify=RaisingOutcome(member, **members)))
    assert run.obs["verification_child_reaped_or_not_started"] is False
    assert run.obs["verification_started"] is False
    assert run.obs["verification_completed"] is False
    assert run.obs["verification_return_code"] is None
    assert run.obs["verification_passed"] is False
    assert run.obs["verification_counts"] == {"passed": 0, "failed": 0, "error": 0}
    assert "L26" in run.obs["lifecycle_failure_steps"]
    assert run.calls[-2:] == ["observe_repository", "remove"]  # Git #2 + L27 [23]
    assert run.obs["git_observation_2_performed"] is True


def test_l26_a_wholly_hostile_outcome_object_is_contained(git_executable, monkeypatch):
    run = check(drive(git_executable, monkeypatch, verify=Hostile()))
    assert run.obs["verification_child_reaped_or_not_started"] is False
    assert run.calls[-2:] == ["observe_repository", "remove"]


@pytest.mark.parametrize(
    "counts",
    [
        pytest.param([1, 2, 3], id="list"),
        pytest.param(None, id="None"),
        pytest.param("counts", id="str"),
        pytest.param(QuietDictSubclass(passed=1, failed=0, error=0), id="dict-subclass"),
        pytest.param(HostileDict(passed=1, failed=0, error=0), id="hostile-dict-subclass"),
        pytest.param(Hostile(), id="raising-bool-and-get"),
    ],
)
def test_l26_a_malformed_counts_container_takes_the_sentinel_for_all_three_keys(
    git_executable, monkeypatch, counts
):
    """[22] (E-11, E-12)"""
    run = check(drive(git_executable, monkeypatch, verify=_good_outcome(counts=counts, passed=True)))
    assert run.obs["verification_counts"] == _SENTINEL_COUNTS
    assert run.obs["verification_passed"] is False  # never strengthens a pass
    assert run.calls[-2:] == ["observe_repository", "remove"]
    # the frozen Sec. 37.4.2 consequence is unchanged: the record refuses itself
    with pytest.raises(Exception):
        payload_of(run)


def test_l26_a_missing_counts_attribute_takes_the_same_sentinel(git_executable, monkeypatch):
    class NoCounts:
        started = completed = True
        timed_out = output_limit_exceeded = passed = False
        return_code = 1

    run = check(drive(git_executable, monkeypatch, verify=NoCounts()))
    assert run.obs["verification_counts"] == _SENTINEL_COUNTS


@pytest.mark.parametrize("bad", [-1, True, 1.5, "1", None, IntLike()])
def test_l26_one_malformed_count_member_takes_the_sentinel_independently(
    git_executable, monkeypatch, bad
):
    counts = {"passed": 3, "failed": bad, "error": 0}
    run = check(drive(git_executable, monkeypatch, verify=_good_outcome(counts=counts)))
    assert run.obs["verification_counts"] == {"passed": 3, "failed": None, "error": 0}


@pytest.mark.parametrize("return_code", ["0", True, False, 1.0, Hostile(), IntLike(), b"0"])
def test_l26_a_malformed_non_none_return_code_is_never_a_reaped_child(
    git_executable, monkeypatch, return_code
):
    """[22] (M-5)"""
    run = check(drive(git_executable, monkeypatch, verify=_good_outcome(return_code=return_code)))
    assert run.obs["verification_return_code"] is None
    assert run.obs["verification_child_reaped_or_not_started"] is False
    assert "L26" in run.obs["lifecycle_failure_steps"]
    assert run.calls[-2:] == ["observe_repository", "remove"]


@pytest.mark.parametrize("return_code", [0, 1, -9])
def test_l26_an_exact_int_return_code_is_a_reaped_child(git_executable, monkeypatch, return_code):
    run = check(drive(git_executable, monkeypatch, verify=_good_outcome(return_code=return_code)))
    assert run.obs["verification_return_code"] == return_code
    assert run.obs["verification_child_reaped_or_not_started"] is True
    assert "L26" not in run.obs["lifecycle_failure_steps"]


@pytest.mark.parametrize("flag", ["started", "completed", "timed_out", "output_limit_exceeded", "passed"])
@pytest.mark.parametrize("value", [1, "true", Hostile(), IntLike()])
def test_l26_a_non_bool_flag_is_false_never_truthy(git_executable, monkeypatch, flag, value):
    run = check(drive(git_executable, monkeypatch, verify=_good_outcome(**{flag: value})))
    assert run.obs[f"verification_{flag}"] is False


@pytest.mark.parametrize(
    "second",
    [
        pytest.param(RAISE, id="raises"),
        pytest.param(FakeRepositorySnapshot(changed_tracked_paths=None), id="malformed"),
        pytest.param(Hostile(), id="hostile"),
    ],
)
@pytest.mark.parametrize(
    "verify",
    [RAISE, Hostile(), _good_outcome(counts=[1]), _good_outcome(return_code="0")],
    ids=["verify-raises", "verify-hostile", "counts-list", "return-code-str"],
)
def test_l26_git_observation_2_is_attempted_after_any_verification_fault(
    git_executable, monkeypatch, verify, second
):
    """[23]: attempted after 1 and 2, and L27 after every G-L26 case."""
    run = check(
        drive(
            git_executable,
            monkeypatch,
            verify=verify,
            observe=lambda n: FakeRepositorySnapshot() if n == 1 else second,
        )
    )
    assert run.calls.count("observe_repository") == 2
    assert run.obs["git_observation_2_performed"] is False
    assert run.obs["post_verification_changed_tracked_paths"] == []
    assert run.calls[-1] == "remove"


# ---------------------------------------------------------------------------
# G-L27 -- workspace closure
# ---------------------------------------------------------------------------


def test_l27_a_reproof_that_raises_never_removes_and_discards(git_executable, monkeypatch):
    """[24]"""
    run = check(drive(git_executable, monkeypatch, l27_reproof_raises=True))
    assert run.obs["workspace_authority_reproved"] is False
    assert run.obs["workspace_removed_verified"] is False
    assert "remove" not in run.calls  # never a removal on unproven authority
    assert run.calls[-1] == "discard"
    assert "L27" in run.obs["lifecycle_failure_steps"]
    assert Path(run.made["workspace"].experiment_root).exists()  # the tree was NOT deleted
    cleanup(run)


def test_l27_a_remover_that_raises_does_not_retry_or_discard_and_the_registry_survives(
    git_executable, monkeypatch
):
    """[25]"""
    run = check(drive(git_executable, monkeypatch, remove=RAISE))
    assert run.calls.count("remove") == 1  # no retry
    assert "discard" not in run.calls  # no fallback retirement
    assert run.obs["workspace_authority_reproved"] is True
    assert run.obs["workspace_removed_verified"] is False
    assert run.obs["workspace_residual_file_count"] == 0
    assert "L27" in run.obs["lifecycle_failure_steps"]
    # the surviving entry is what makes stranded authority visible to L30
    assert run_workspace.minted_workspace_count() == 1
    assert stage_runner._run_scoped_registries_empty(run.outcome) is False
    cleanup(run)


def test_l27_a_remover_that_raises_after_filesystem_work_is_not_a_verified_removal(
    git_executable, monkeypatch
):
    run = check(drive(git_executable, monkeypatch, remove=("after", None)))
    assert run.obs["workspace_removed_verified"] is False
    assert "L27" in run.obs["lifecycle_failure_steps"]
    assert run.calls.count("remove") == 1  # no retry
    assert "discard" not in run.calls  # no fallback retirement by the executor


@pytest.mark.parametrize(
    "removal",
    [
        pytest.param(None, id="None"),
        pytest.param([], id="list"),
        pytest.param(QuietDictSubclass(removed=True, residual_file_count=0), id="dict-subclass"),
        pytest.param(HostileDict(removed=True, residual_file_count=0), id="hostile-dict-subclass"),
        pytest.param(Hostile(), id="foreign-object"),
        pytest.param({"residual_file_count": 0}, id="removed-missing"),
        pytest.param({"removed": 1, "residual_file_count": 0}, id="removed-1"),
        pytest.param({"removed": "true", "residual_file_count": 0}, id="removed-str"),
        pytest.param({"removed": True}, id="residual-missing"),
        pytest.param({"removed": True, "residual_file_count": -1}, id="residual-negative"),
        pytest.param({"removed": True, "residual_file_count": True}, id="residual-bool"),
        pytest.param({"removed": True, "residual_file_count": "0"}, id="residual-str"),
        pytest.param({"removed": True, "residual_file_count": IntLike()}, id="residual-int-like"),
    ],
)
def test_l27_a_malformed_removal_result_is_never_a_verified_removal(
    git_executable, monkeypatch, removal
):
    """[26]"""
    run = check(drive(git_executable, monkeypatch, remove=("returns", removal)))
    assert run.obs["workspace_removed_verified"] is False
    assert run.obs["workspace_residual_file_count"] == 0
    assert "L27" in run.obs["lifecycle_failure_steps"]


def test_l27_an_exact_good_removal_is_verified(git_executable, monkeypatch):
    run = check(drive(git_executable, monkeypatch))
    assert run.obs["workspace_removed_verified"] is True
    assert run.obs["workspace_residual_file_count"] == 0


def test_l27_a_discard_that_raises_is_contained_and_the_registry_survives(
    git_executable, monkeypatch
):
    """[27]"""
    run = check(drive(git_executable, monkeypatch, l27_reproof_raises=True, discard=RAISE))
    assert run.obs["workspace_authority_reproved"] is False  # no fact changes
    assert run.obs["workspace_removed_verified"] is False
    assert run.calls.count("discard") == 1  # no second attempt
    assert "remove" not in run.calls
    assert "L27" in run.obs["lifecycle_failure_steps"]
    assert run_workspace.minted_workspace_count() == 1  # not hidden
    assert stage_runner._run_scoped_registries_empty(run.outcome) is False
    cleanup(run)


def test_l27_never_touches_an_l24_fact(git_executable, monkeypatch):
    run = check(drive(git_executable, monkeypatch, scrub_config=False, scrub_extension=False))
    assert run.obs["generated_config_scrub_verified"] is False
    assert run.obs["extension_binding_scrub_verified"] is False
    assert run.calls[-1] == "remove"  # L27 ran, and upgraded neither
    cleanup(run)


# ---------------------------------------------------------------------------
# G-MULTI -- combined faults and ordering
# ---------------------------------------------------------------------------


def test_multi_l21_l23_l24_l27_fail_in_one_run(git_executable, monkeypatch):
    """[28]"""
    run = check(
        drive(
            git_executable,
            monkeypatch,
            sup={"shutdown": None, "stdout_state": RAISE},
            broker={"shutdown_for_cfg1": "CLOSED"},
            scrub_config=RAISE,
            remove=RAISE,
        )
    )
    assert run.obs["lifecycle_failure_steps"] == ["L21", "L23", "L24", "L27"]
    assert run.obs["lifecycle_all_closed"] is False
    assert run.calls == [
        "shutdown",
        "stdout_state",
        "stderr_snapshot",
        "diagnostics_counts",
        "shutdown_for_cfg1",
        "scrub_config",
        "scrub_extension",
        "observe_repository",
        "remove",
    ]
    assert run_workspace.minted_workspace_count() == 1
    cleanup(run)


def test_multi_l22_l25_and_l26_git2_fail_in_one_run(git_executable, monkeypatch):
    """[28]"""
    run = check(
        drive(
            git_executable,
            monkeypatch,
            broker={"diagnostics_counts": [1, 2]},
            observe=lambda n: RAISE,
        )
    )
    assert run.obs["broker_recorded_activity_available"] is False
    assert run.obs["git_observation_1_performed"] is False
    assert run.obs["git_observation_2_performed"] is False
    assert run.obs["verification_attempted"] is True
    assert run.calls == FULL_SEQUENCE
    assert run.obs["workspace_removed_verified"] is True


def test_multi_the_recorded_call_sequence_when_the_earliest_step_fails(
    git_executable, monkeypatch
):
    """[29]"""
    run = check(drive(git_executable, monkeypatch, sup={"shutdown": RAISE}))
    assert run.calls == [
        "shutdown",
        "stdout_state",
        "stderr_snapshot",
        "diagnostics_counts",
        "shutdown_for_cfg1",
        "scrub_config",
        "scrub_extension",
        "observe_repository",
        "remove",
    ]
    assert "run_verification" not in run.calls  # L26 absent for LIFECYCLE_UNPROVEN


def test_multi_an_l24_failure_skips_verification_but_never_the_removal(
    git_executable, monkeypatch
):
    """[30]"""
    run = check(drive(git_executable, monkeypatch, scrub_extension=RAISE))
    assert run.obs["verification_skip_reason"] == "LIFECYCLE_UNPROVEN"
    assert run.obs["verification_attempted"] is False
    assert "run_verification" not in run.calls
    assert run.calls[-1] == "remove"
    cleanup(run)


def test_multi_every_step_failing_at_once_still_returns_a_plain_outcome(
    git_executable, monkeypatch
):
    run = check(
        drive(
            git_executable,
            monkeypatch,
            sup={"shutdown": Hostile(), "stdout_state": Hostile(), "stderr_snapshot": Hostile()},
            broker={"diagnostics_counts": Hostile(), "shutdown_for_cfg1": Hostile()},
            scrub_config=Hostile(),
            scrub_extension=Hostile(),
            observe=lambda n: Hostile(),
            remove=("returns", Hostile()),
        )
    )
    assert run.calls == [
        "shutdown",
        "stdout_state",
        "stderr_snapshot",
        "diagnostics_counts",
        "shutdown_for_cfg1",
        "scrub_config",
        "scrub_extension",
        "observe_repository",
        "remove",
    ]
    assert run.obs["lifecycle_all_closed"] is False
    cleanup(run)


# ---------------------------------------------------------------------------
# G-X -- containment, plain outcome, source audits
# ---------------------------------------------------------------------------


def test_x1_a_hostile_marker_in_every_diagnostic_channel_reaches_no_sink(
    git_executable, monkeypatch, capsys
):
    """[31]"""
    run = check(
        drive(
            git_executable,
            monkeypatch,
            sup={
                "shutdown": {"exit_status_observed": 0, "text_tail": MARKER,
                             "stdin_close_error": MARKER, "claim_scope": MARKER},
                "stdout_state": {"eof": True, "text_tail": MARKER},
                "stderr_snapshot": {"eof": True, "text_tail": MARKER},
            },
            broker={"shutdown_for_cfg1": dict(_GOOD_LIFECYCLE, worker_error=MARKER),
                    "diagnostics_counts": Hostile()},
            scrub_config=RAISE,
            verify=Hostile(),
            remove=RAISE,
        )
    )
    captured = capsys.readouterr()
    assert MARKER not in captured.out and MARKER not in captured.err
    assert MARKER not in repr(run.outcome)
    cleanup(run)


def test_x2_every_committed_value_is_an_exact_plain_type_for_every_fault_class(
    git_executable, monkeypatch
):
    """[I-9] (also enforced by ``check`` in every test above)."""
    for kwargs in (
        {"sup": {"shutdown": Hostile()}},
        {"broker": {"shutdown_for_cfg1": Hostile()}},
        {"verify": Hostile()},
        {"remove": ("returns", Hostile())},
        {"broker": {"shutdown_for_cfg1": {"state_reached": EqReturnsForeign(),
                                          "pending_operations_unreaped": 0,
                                          "worker_termination_observed": True}}},
    ):
        run = check(drive(git_executable, monkeypatch, **kwargs))
        for value in run.obs.values():
            assert not isinstance(value, Hostile) and not isinstance(value, EqReturnsForeign)
        cleanup(run)


def _executor_tree() -> ast.Module:
    return ast.parse(Path(run_executor.__file__).read_text(encoding="utf-8"))


_CLOSURE_STEP_NAMES = (
    "_closure_l21_runtime_applicable",
    "_closure_l21_runtime",
    "_closure_l22_broker_counts",
    "_closure_l23_broker_shutdown",
    "_closure_l24_scrubs",
    "_scrub_generated_config",
    "_scrub_extension_binding",
    "_closure_l25_git_observation_1",
    "_closure_l26_project_verification",
    "_closure_l26_verification",
    "_closure_l27_workspace",
    "_closure_phase",
)


def _functions() -> dict[str, ast.FunctionDef]:
    return {
        node.name: node
        for node in ast.walk(_executor_tree())
        if isinstance(node, ast.FunctionDef)
    }


def test_x3_the_audited_closure_functions_exist_so_the_audits_are_not_vacuous():
    functions = _functions()
    for name in _CLOSURE_STEP_NAMES:
        assert name in functions, name


def test_x3_closure_handlers_bind_no_exception_name_and_raise_nothing():
    functions = _functions()
    handlers = 0
    for name in _CLOSURE_STEP_NAMES:
        for node in ast.walk(functions[name]):
            if isinstance(node, ast.ExceptHandler):
                handlers += 1
                assert node.name is None, (name, "binds the exception")
                assert isinstance(node.type, ast.Name) and node.type.id == "Exception", name
                for statement in ast.walk(node):
                    assert not isinstance(statement, (ast.Raise, ast.Call, ast.JoinedStr)), (
                        name, "a handler body must be constant assignments only",
                    )
    assert handlers >= 15  # non-vacuity


def test_x3_no_closure_consumption_path_uses_a_positive_default_or_foreign_truthiness():
    functions = _functions()
    for name in _CLOSURE_STEP_NAMES:
        for node in ast.walk(functions[name]):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "get" and len(node.args) >= 2:
                default = node.args[1]
                assert not (isinstance(default, ast.Constant) and default.value in (True, 1)), name
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id == "getattr" and len(node.args) == 3:
                default = node.args[2]
                assert not (isinstance(default, ast.Constant) and default.value is True), name
            if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
                for value in node.values:
                    assert not isinstance(value, ast.Dict), (name, "`or {}` on a foreign value")
            if isinstance(node, ast.Name) and node.id in ("_exact_bool",):
                pytest.fail(f"{name} routes a closure fact through a truthiness-adjacent reducer")


def test_x3_the_closure_phase_is_an_unguarded_pure_sequencer_and_is_not_laundered():
    """I-8: no ``try`` around the closure phase, or any span covering two obligations."""
    functions = _functions()
    closure_phase = functions["_closure_phase"]
    assert not any(isinstance(node, ast.Try) for node in ast.walk(closure_phase))
    called = [
        node.func.id
        for node in ast.walk(closure_phase)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert called == [
        "_closure_l21_runtime",
        "_closure_l22_broker_counts",
        "_closure_l23_broker_shutdown",
        "_closure_l24_scrubs",
        "_closure_l25_git_observation_1",
        "_closure_l26_verification",
        "_closure_l27_workspace",
    ]
    # ...and the call that enters it in execute_cfg1_run is not lexically inside a Try.
    execute = functions["execute_cfg1_run"]
    parents = {child: parent for parent in ast.walk(execute) for child in ast.iter_child_nodes(parent)}
    sites = [
        node for node in ast.walk(execute)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "_closure_phase"
    ]
    assert len(sites) == 1
    ancestor = parents[sites[0]]
    while ancestor is not execute:
        assert not isinstance(ancestor, (ast.Try, ast.ExceptHandler)), "closure is laundered"
        ancestor = parents[ancestor]
    # The steps never call one another, save the two helper relationships:
    allowed = {
        ("_closure_l21_runtime", "_closure_l21_runtime_applicable"),
        ("_closure_l26_verification", "_closure_l26_project_verification"),
    }
    for name in _CLOSURE_STEP_NAMES:
        if name == "_closure_phase":
            continue
        for node in ast.walk(functions[name]):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)                     and node.func.id.startswith("_closure_l2"):
                assert (name, node.func.id) in allowed, (name, node.func.id)


def test_x3_no_step_try_spans_two_port_obligations():
    """Every ``try`` body in a closure step contains at most one port invocation."""
    functions = _functions()
    port_attrs = {
        "shutdown", "stdout_state", "stderr_snapshot", "diagnostics_counts",
        "shutdown_for_cfg1", "run_verification", "observe_repository",
        "remove_cfg1_run_workspace", "discard_cfg1_run_workspace",
        "scrub_config_issuance", "scrub_extension_issuance",
    }
    for name in _CLOSURE_STEP_NAMES:
        for node in ast.walk(functions[name]):
            if isinstance(node, ast.Try):
                invoked = {
                    call.func.attr
                    for stmt in node.body
                    for call in ast.walk(stmt)
                    if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                    and call.func.attr in port_attrs
                }
                assert len(invoked) <= 1, (name, sorted(invoked))


def test_x3_the_only_write_of_the_launch_attempt_fact_immediately_precedes_launch():
    """[7G] source audit."""
    tree = _executor_tree()
    writes = []
    for function in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))]:
        body = getattr(function, "body", [])
        for index, statement in enumerate(body):
            targets = []
            if isinstance(statement, ast.Assign):
                targets = statement.targets
            elif isinstance(statement, ast.AnnAssign):
                targets = [statement.target]
            for target in targets:
                if (isinstance(target, ast.Attribute) and target.attr == "runtime_launch_attempted") \
                        or (isinstance(target, ast.Name) and target.id == "runtime_launch_attempted"):
                    writes.append((function.name, index, statement, body))
    # exactly two textual writes: the dataclass field default and the one executor line
    assert len(writes) == 2, [(w[0], w[1]) for w in writes]
    class_default = [w for w in writes if w[0] == "_RunState"]
    assert len(class_default) == 1
    assert isinstance(class_default[0][2].value, ast.Constant) and class_default[0][2].value.value is False
    (function_name, index, statement, body), = [w for w in writes if w[0] != "_RunState"]
    assert function_name == "_dispatch_phase"
    assert isinstance(statement.value, ast.Constant) and statement.value.value is True
    following = body[index + 1]
    assert isinstance(following, ast.Try)
    launches = [
        call for call in ast.walk(following.body[0])
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
        and call.func.attr == "launch"
    ]
    assert len(following.body) == 1 and len(launches) == 1
    # exactly one launch() call in the module, and it is that one
    all_launches = [
        call for call in ast.walk(tree)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
        and call.func.attr == "launch"
    ]
    assert len(all_launches) == 1


def test_x3_the_launch_attempt_fact_is_never_exposed_and_never_reset():
    for path in _PACKAGE.glob("*.py"):
        if path.name != "run_executor.py":
            assert "runtime_launch_attempted" not in path.read_text(encoding="utf-8"), path.name
    source = Path(run_executor.__file__).read_text(encoding="utf-8")
    assert '"runtime_launch_attempted"' not in source  # never an observation key
    tree = ast.parse(source)
    owner = {}
    for function in ast.walk(tree):
        if isinstance(function, ast.FunctionDef):
            for node in ast.walk(function):
                owner[node] = function.name
    stores, loads = [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "runtime_launch_attempted":
            (stores if isinstance(node.ctx, ast.Store) else loads).append(owner.get(node))
    assert stores == ["_dispatch_phase"]  # one write, never a reset, never elsewhere
    assert loads == ["_closure_l21_runtime_applicable"]  # one read: L21's applicability


def test_x3_the_process_read_is_reachable_only_behind_the_launch_attempt_condition():
    function = _functions()["_closure_l21_runtime_applicable"]
    statements = function.body[1:]  # after the docstring
    process_reads = [
        index for index, statement in enumerate(statements)
        if any(
            isinstance(node, ast.Constant) and node.value == "process"
            for node in ast.walk(statement)
        )
    ]
    assert len(process_reads) == 1
    guard_index = next(
        index for index, statement in enumerate(statements)
        if isinstance(statement, ast.If)
        and "runtime_launch_attempted" in ast.unparse(statement.test)
        and isinstance(statement.body[0], ast.Return)
    )
    created_index = next(
        index for index, statement in enumerate(statements)
        if isinstance(statement, ast.If) and "runtime_created" in ast.unparse(statement.test)
    )
    assert created_index < guard_index < process_reads[0]


def test_x3_a_closure_step_reads_no_process_outside_the_one_helper():
    functions = _functions()
    for name in _CLOSURE_STEP_NAMES:
        if name == "_closure_l21_runtime_applicable":
            continue
        for node in ast.walk(functions[name]):
            if isinstance(node, ast.Attribute):
                assert node.attr != "process", name
            if isinstance(node, ast.Constant):
                assert node.value != "process", name


def test_x3_the_durable_schema_did_not_grow():
    """[8] No new observation key, record version, record kind or halt code."""
    from pi_harness_cfg1 import halt, records

    keys = set(records.CFG1_RUN_OBSERVATION_KEYS_V2)
    assert set(run_executor._initial_observations()) == keys
    assert not any("launch" in key or "closure" in key or "cleanup_error" in key for key in keys)
    assert len(halt.HALT_REASON_CODES) == 6


# ---------------------------------------------------------------------------
# G-STAGE -- stage-level integration
# ---------------------------------------------------------------------------


def _stage_executor(git_executable, sup=None, **drive_options):
    """An executor for the stage runner that runs the GENUINE ``execute_cfg1_run``."""
    calls: list[str] = []
    ports, made = build_doubled_ports(
        git_executable=git_executable,
        overrides={
            "build_supervisor": lambda **_kw: RecSupervisor(calls, sup or {}),
            "build_broker": lambda *, capability: RecBroker(calls, {}),
        },
    )

    def _executor(admission):
        return execute_cfg1_run(admission, ports=ports)

    return _executor, made, calls


def test_stage_1_an_in_domain_closure_fault_ends_in_an_emitted_record_and_a_lifecycle_halt(
    git_executable, monkeypatch, make_authority
):
    """[32]"""
    seam_digests_all_match(monkeypatch)
    authority = make_authority("S1-X1")
    executor, made, calls = _stage_executor(git_executable, sup={"shutdown": None})
    result = stage_runner._run_cfg1_stage_with_injected_executor(authority, run_executor=executor)

    assert result.disposition == "STAGE_HALTED"  # never Cfg1StageRunnerError
    assert result.halt_reason_code == "LIFECYCLE_CLOSURE_UNPROVEN"
    assert result.halted_after_ordinal == 1
    assert result.stage_closure_confirmed is True  # a stage-closure record exists
    record_path = Path(authority.execution_directory, "S1_01_Q.json")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["lifecycle_all_closed"] is False
    assert "L21" in record["lifecycle_failure_steps"]
    assert record["runtime_exit_observed"] is False
    assert dict(result.ordinal_status)[1] == "RECORD_EMITTED"


def test_stage_2_a_surviving_registry_entry_is_not_admitted_past_the_ordinal(
    git_executable, monkeypatch, make_authority
):
    """[33]"""
    seam_digests_all_match(monkeypatch)
    authority = make_authority("S1-X1")
    executor, made, calls = _stage_executor(git_executable)

    def _boom(workspace):
        raise RuntimeError(MARKER)

    monkeypatch.setattr(run_workspace, "remove_cfg1_run_workspace", _boom)
    survived: list[bool] = []
    real_check = stage_runner._run_scoped_registries_empty

    def _spy(outcome):
        value = real_check(outcome)
        survived.append(value)
        return value

    monkeypatch.setattr(stage_runner, "_run_scoped_registries_empty", _spy)
    result = stage_runner._run_cfg1_stage_with_injected_executor(authority, run_executor=executor)

    assert survived == [False]  # asserted directly, not through a caller bool
    assert result.disposition == "STAGE_HALTED"
    assert result.halted_after_ordinal == 1
    assert result.halt_reason_code == "LIFECYCLE_CLOSURE_UNPROVEN"
    assert result.ordinals_attempted == (1,)  # ordinal 2 was never admitted
    assert run_workspace.minted_workspace_count() == 1
    shutil.rmtree(made["workspace"].experiment_root, ignore_errors=True)


def test_stage_3_a_base_exception_from_a_closure_port_is_not_converted_into_an_outcome(
    git_executable, monkeypatch, make_authority
):
    """Out-of-domain control: only ``Exception`` is contained."""

    class Interrupt(KeyboardInterrupt):
        pass

    seam_digests_all_match(monkeypatch)
    authority = make_authority("S1-X1")

    class InterruptingSupervisor(RecSupervisor):
        def shutdown(self):
            raise Interrupt()

    calls: list[str] = []
    ports, made = build_doubled_ports(
        git_executable=git_executable,
        overrides={
            "build_supervisor": lambda **_kw: InterruptingSupervisor(calls, {}),
            "build_broker": lambda *, capability: RecBroker(calls, {}),
        },
    )
    with pytest.raises(Interrupt):
        stage_runner._run_cfg1_stage_with_injected_executor(
            authority, run_executor=lambda admission: execute_cfg1_run(admission, ports=ports)
        )
    shutil.rmtree(made["workspace"].experiment_root, ignore_errors=True)


def test_stage_4_an_implementation_defect_outside_every_region_still_surfaces_as_raised(
    git_executable, monkeypatch, make_authority
):
    """I-8: nothing launders an out-of-domain raise into ordinary evidence."""
    seam_digests_all_match(monkeypatch)
    authority = make_authority("S1-X1")
    executor, made, calls = _stage_executor(git_executable)

    def _defect(*args, **kwargs):
        raise RuntimeError("an executor-owned sequencing defect")

    monkeypatch.setattr(run_executor, "_closure_l22_broker_counts", _defect)
    with pytest.raises(stage_runner.Cfg1StageRunnerError) as excinfo:
        stage_runner._run_cfg1_stage_with_injected_executor(authority, run_executor=executor)
    assert excinfo.value.args and "RUN_EXECUTOR_RAISED" in str(excinfo.value)
    shutil.rmtree(made["workspace"].experiment_root, ignore_errors=True)
