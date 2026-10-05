"""PE-2c: L1 and the stage profile ledger, L21A, item 1A at the runner.

PE-1 (``PHASE_5F3B_PI_HARNESS_PROFILE_EVOLUTION_PE1_AMENDMENT.md``) Sec. 26.3
rows C-4, C-6, C-8 (the runtime half), C-15, C-24, C-25 and C-26, plus PE-0
Sec. 14.3 counterexamples 8-11 and Sec. 14.5's B8 closure-order matrix.

Everything runs the GENUINE ``execute_cfg1_run`` / stage runner over the
doubled ports, a SYNTHETIC on-disk Pi tree and a SYNTHETIC sealed snapshot (a
genuine PE-2b load of a synthetic chain). No Node, Pi, socket, credential,
endpoint or model; the synthetic ``node.exe`` is never executed.
"""

from __future__ import annotations

import ast
import builtins
import inspect
import json
import os
import shutil
from pathlib import Path

import pytest
from cfg1_builders import happy_observations, pre_dispatch_refusal_overrides, synthetic_run_executor
from cfg1_doubles import (
    FakeSupervisor,
    approve_profiles,
    build_doubled_ports,
    build_synthetic_pi_tree,
    session_synthetic_pi_tree,
)
from cfg1_fu1_support import (
    LeafRecorder,
    fu1_ports,
    make_admission,
    make_pi_world,
    replace_directory_with_identical_copy,
)
from pe2a_support import manifest_bytes, root_manifest, synthetic_payload_files

from pi_harness_cfg1 import pi_payload, run_executor, stage_runner, writers
from pi_harness_cfg1.halt import HALT_PI_PROFILE_ATTRIBUTION_UNPROVEN
from pi_harness_cfg1.lifecycle import compute_lifecycle_closure_v2
from pi_harness_cfg1.pi_identity import (
    PI_IDENTITY_GATE_PASSED,
    PI_PROFILE_CHANGED_WITHIN_STAGE,
    PI_PROFILE_UNAPPROVED,
    pre_consumption_pi_identity_gate,
)
from pi_harness_cfg1.records import _require_valid_cfg1_run_payload_v3, build_cfg1_run_payload
from pi_harness_cfg1.run_executor import execute_cfg1_run

_PACKAGE_DIR = Path(__file__).resolve().parents[1]
_EXPOSED_NAME = "pe2c-l21a-exposure-5b1c"

_CLOSURE_STEPS = (
    ("L21", "_closure_l21_runtime"),
    ("L22", "_closure_l22_broker_counts"),
    ("L23", "_closure_l23_broker_shutdown"),
    ("L24", "_closure_l24_scrubs"),
    ("L21A", "_closure_l21a_pi_profile_reobservation"),
    ("L25", "_closure_l25_git_observation_1"),
    ("L26", "_closure_l26_verification"),
    ("L27", "_closure_l27_workspace"),
)


def _variant_files():
    files, empty_dirs = synthetic_payload_files()
    files = dict(files)
    files["dist/other.js"] = b"export const other = 3;\n"
    return files, empty_dirs


def _exposed_files():
    files, empty_dirs = synthetic_payload_files()
    files = dict(files)
    document = root_manifest()
    document["dependencies"] = dict(document["dependencies"], **{_EXPOSED_NAME: "1.0.0"})
    files["package.json"] = manifest_bytes(document)
    return files, empty_dirs


class _HookSupervisor(FakeSupervisor):
    """A FakeSupervisor whose ``shutdown`` (L21) runs a hook first, while the
    "runtime" still exists: a mutation there is a change DURING the run."""

    def __init__(self, hook=None, shutdown_result=None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._hook = hook
        self._shutdown_result = shutdown_result

    def shutdown(self):
        if self._hook is not None:
            self._hook()
        if self._shutdown_result is not None:
            self.shutdown_calls += 1
            if self._shutdown_result == "raise":
                raise RuntimeError("an injected L21 failure")
            return self._shutdown_result
        return super().shutdown()


def _record_closure_entries(monkeypatch, log: list) -> None:
    """Record each closure step's ENTRY from the executor's own function
    (before its first side effect), never from a port's claim."""
    for label, name in _CLOSURE_STEPS:
        real = getattr(run_executor, name)

        def _wrapped(*args, __real=real, __label=label, **kwargs):
            log.append(("step", __label))
            return __real(*args, **kwargs)

        monkeypatch.setattr(run_executor, name, _wrapped)


def _run(git_executable, tree, *, hook=None, shutdown_result=None, overrides=None, recorder=None, admission=None):
    recorder = recorder or LeafRecorder()
    merged = {"build_supervisor": lambda **_k: _HookSupervisor(hook, shutdown_result)}
    merged.update(overrides or {})
    ports, made = fu1_ports(git_executable, tree, leaves=recorder.leaves(), overrides=merged)
    outcome = execute_cfg1_run(admission or make_admission(), ports=ports)
    return outcome, recorder, made


def _payload(observations) -> dict:
    payload = build_cfg1_run_payload(
        stage_id="S1", stage_execution_id="S1-X1", run_ordinal=1, observations=observations
    )
    _require_valid_cfg1_run_payload_v3(json.loads(json.dumps(payload)))
    return payload


# ---------------------------------------------------------------------------
# C-4 -- L1: the stage profile, consistency, malformed admissions, cx 8
# ---------------------------------------------------------------------------


def test_c4_l1_commits_the_whole_profile_family_on_a_pass(tmp_path, monkeypatch, git_executable):
    tree = make_pi_world(tmp_path, monkeypatch)
    outcome, _recorder, _made = _run(git_executable, tree)
    observations = outcome.observations
    assert observations["pi_identity_failure_code"] is None
    assert observations["pi_payload_observation_complete"] is True
    assert observations["pi_profile_id"] == tree.profile_id
    assert observations["pi_profile_declared_package_version"] == tree.declared_package_version
    payload = _payload(observations)
    # The policy-derived head is the module-level sealed snapshot's -- here the
    # synthetic one -- never an observation and never a caller value.
    from pi_harness_cfg1 import pi_profile_policy_loader as loader

    assert payload["pi_profile_set_head_sha256"] == loader.SEALED_POLICY_SNAPSHOT.aps_head_sha256
    assert payload["pi_profile_set_head_sha256"] != loader._POLICY_DIR


def test_c4_a_different_approved_profile_on_a_later_ordinal_is_changed_within_stage(
    tmp_path, monkeypatch, git_executable
):
    variant_files, variant_dirs = _variant_files()
    tree = build_synthetic_pi_tree(str(tmp_path / "world"))
    variant = build_synthetic_pi_tree(str(tmp_path / "variant"), variant_files, variant_dirs)
    approve_profiles(monkeypatch, tree, variant)
    reads: list[str] = []

    def _read_connection():
        reads.append("read")
        return ("https://cfg1-doubles.invalid/v1", "cfg1-synthetic-key")

    # The installed payload IS the other approved profile; the stage runs
    # under ``tree``'s profile.
    admission = make_admission(2, stage_pi_profile_id=tree.profile_id)
    outcome, _recorder, _made = _run(
        git_executable, variant, overrides={"read_connection": _read_connection}, admission=admission
    )
    observations = outcome.observations
    assert observations["pi_identity_failure_code"] == PI_PROFILE_CHANGED_WITHIN_STAGE
    assert observations["pi_payload_observation_complete"] is True
    assert observations["pi_profile_id"] is None
    assert observations["pi_profile_declared_package_version"] is None
    assert observations["refused_at_step"] == "L1"
    assert observations["pre_dispatch_refusal_code"] == "OFFLINE_PREFLIGHT_FAILED"
    assert reads == []  # before any credential read
    _payload(observations)
    # The SAME installed payload passes when the constraint names it.
    same = make_admission(2, stage_pi_profile_id=variant.profile_id)
    outcome, _recorder, _made = _run(git_executable, variant, admission=same)
    assert outcome.observations["pi_profile_id"] == variant.profile_id


class _StrSubclass(str):
    pass


@pytest.mark.parametrize(
    "ordinal,value",
    [
        (1, "a" * 64),
        (2, None),
        (2, "A" * 64),
        (2, "a" * 63),
        (2, 7),
        (2, _StrSubclass("a" * 64)),
        (True, None),
    ],
)
def test_c4_a_malformed_admission_value_is_unexpected_with_p_uncommitted(
    ordinal, value, tmp_path, monkeypatch, git_executable
):
    from pi_harness_cfg1.run_contract import Cfg1RunAdmission
    from pi_harness_cfg1.schedule import _schedule_arm_for, _schedule_block_position

    tree = make_pi_world(tmp_path, monkeypatch)
    real_ordinal = 1 if ordinal is True else ordinal
    block, position = _schedule_block_position("S1", real_ordinal)
    admission = Cfg1RunAdmission(
        stage_id="S1",
        stage_execution_id="S1-X1",
        run_ordinal=ordinal,
        arm_id=_schedule_arm_for("S1", real_ordinal),
        block=block,
        position=position,
        run_id="f" * 32,
        stage_pi_profile_id=value,
    )
    recorder = LeafRecorder()
    ports, _made = fu1_ports(git_executable, tree, leaves=recorder.leaves())
    observations = execute_cfg1_run(admission, ports=ports).observations
    assert observations["pre_dispatch_refusal_code"] == "UNEXPECTED_STEP_FAILURE"
    assert observations["refused_at_step"] == "L1"
    assert observations["pi_identity_failure_code"] is None
    assert observations["pi_payload_observation_complete"] is False
    assert observations["pi_profile_id"] is None
    # P never ran: the constraint is validated BEFORE the proof.
    assert recorder.log == []


def test_c4_counterexample_8_gate_passes_then_the_payload_changes_and_l1_refuses(
    tmp_path, monkeypatch, git_executable
):
    tree = make_pi_world(tmp_path, monkeypatch)
    assert pre_consumption_pi_identity_gate({"PATH": tree.path_value}) == PI_IDENTITY_GATE_PASSED
    Path(tree.seam_path("dist/other.js")).write_bytes(b"export const other = 77;\n")
    reads: list[str] = []
    outcome, _recorder, _made = _run(
        git_executable, tree, overrides={"read_connection": lambda: reads.append("read")}
    )
    assert outcome.observations["pi_identity_failure_code"] == PI_PROFILE_UNAPPROVED
    assert reads == []


def _recording_genuine_stage(git_executable, ports, admissions, before_ordinal=None):
    def _executor(admission):
        admissions.append(admission)
        if before_ordinal is not None:
            before_ordinal(admission)
        return execute_cfg1_run(admission, ports=ports)

    return _executor


def test_c4_ordinal_1_fixes_the_stage_profile_and_every_later_admission_carries_it(
    monkeypatch, git_executable, make_authority
):
    tree = session_synthetic_pi_tree()
    approve_profiles(monkeypatch, tree)
    ports, _made = build_doubled_ports(git_executable=git_executable)
    admissions: list = []
    authority = make_authority("S1-X1")
    captured: list = []
    real_writer = stage_runner.emit_cfg1_stage_closure

    def _capture(authority_, /, *, decision):
        captured.append(decision)
        return real_writer(authority_, decision=decision)

    monkeypatch.setattr(stage_runner, "emit_cfg1_stage_closure", _capture)
    result = stage_runner._run_cfg1_stage_with_injected_executor(
        authority, run_executor=_recording_genuine_stage(git_executable, ports, admissions)
    )
    assert result.disposition == "STAGE_COMPLETED"
    assert [admission.stage_pi_profile_id for admission in admissions] == [None] + [tree.profile_id] * 8
    decision = captured[0]
    assert decision.stage_pi_profile_id == tree.profile_id
    assert decision.ordinal_pi_profile_binding == tuple((k, "STAGE_PROFILE") for k in range(1, 10))
    assert decision.pi_profile_attribution_halt is False
    closure = json.loads(Path(authority.execution_directory, "S1_stage_closure.json").read_text(encoding="utf-8"))
    assert closure["stage_pi_profile_id"] == tree.profile_id
    assert closure["stage_pi_profile_declared_package_version"] == tree.declared_package_version
    for ordinal in range(1, 10):
        record = json.loads(next(Path(authority.execution_directory).glob(f"S1_{ordinal:02d}_*.json")).read_text(encoding="utf-8"))
        assert record["pi_profile_id"] == tree.profile_id
        assert record["pi_profile_post_runtime_reobservation"] == "PROVEN_UNCHANGED"


def test_c4_a_profile_swap_between_ordinals_halts_with_changed_within_stage(
    tmp_path, monkeypatch, git_executable, make_authority
):
    """PE-1 adversarial case 15: profile swap ordinal -> ordinal."""
    variant_files, variant_dirs = _variant_files()
    tree = build_synthetic_pi_tree(str(tmp_path / "world"))
    approve_profiles(monkeypatch, tree, build_synthetic_pi_tree(str(tmp_path / "variant"), variant_files, variant_dirs))
    reads: list[int] = []

    def _read_connection():
        reads.append(1)
        return ("https://cfg1-doubles.invalid/v1", "cfg1-synthetic-key")

    ports, _made = fu1_ports(git_executable, tree, overrides={"read_connection": _read_connection})

    def _swap(admission):
        if admission.run_ordinal == 2:
            Path(tree.seam_path("dist/other.js")).write_bytes(variant_files["dist/other.js"])

    admissions: list = []
    authority = make_authority("S1-X1")
    result = stage_runner._run_cfg1_stage_with_injected_executor(
        authority, run_executor=_recording_genuine_stage(git_executable, ports, admissions, _swap)
    )
    assert result.halted_after_ordinal == 2
    assert result.halt_reason_code == "PRE_DISPATCH_REFUSAL"
    assert len(admissions) == 2
    assert reads == [1]  # only ordinal 1 ever reached L4
    second = json.loads(Path(authority.execution_directory, "S1_02_R.json").read_text(encoding="utf-8"))
    assert second["pi_identity_failure_code"] == PI_PROFILE_CHANGED_WITHIN_STAGE
    closure = json.loads(Path(authority.execution_directory, "S1_stage_closure.json").read_text(encoding="utf-8"))
    assert closure["stage_pi_profile_id"] == tree.profile_id
    assert closure["ordinal_pi_profile_binding"]["1"] == "STAGE_PROFILE"
    assert closure["ordinal_pi_profile_binding"]["2"] == "NO_PROFILE"
    assert closure["pi_profile_attribution_halt"] is False


# ---------------------------------------------------------------------------
# C-6 -- L21A: position, failure injection, applicability, each result row
# ---------------------------------------------------------------------------


def test_c6_b8_the_closure_entry_order_and_no_walk_before_l24(tmp_path, monkeypatch, git_executable):
    tree = make_pi_world(tmp_path, monkeypatch)
    recorder = LeafRecorder()
    _record_closure_entries(monkeypatch, recorder.log)
    outcome, recorder, _made = _run(git_executable, tree, recorder=recorder)
    steps = [label for kind, label in recorder.log if kind == "step"]
    assert steps == ["L21", "L22", "L23", "L24", "L21A", "L25", "L26", "L27"]
    l21_at = recorder.log.index(("step", "L21"))
    l24_at = recorder.log.index(("step", "L24"))
    l21a_at = recorder.log.index(("step", "L21A"))
    l25_at = recorder.log.index(("step", "L25"))
    # No payload-walk leaf call during the closure phase before L24's entry:
    # L21A never delays broker shutdown or the sensitive-material scrub.
    assert not [entry for entry in recorder.log[l21_at:l24_at] if entry[0] in ("digest", "enumerate")]
    # The L21A walk happens strictly between L21A's entry and L25's.
    walk = [entry for entry in recorder.log[l21a_at:l25_at] if entry[0] == "digest"]
    assert len(walk) == len(tree.files)
    assert outcome.observations["pi_profile_post_runtime_reobservation"] == "PROVEN_UNCHANGED"


@pytest.mark.parametrize(
    "failure,expected",
    [
        ("L21", "UNPROVEN"),
        ("L22", "PROVEN_UNCHANGED"),
        ("L23", "PROVEN_UNCHANGED"),
        ("L24", "PROVEN_UNCHANGED"),
    ],
)
def test_c6_a_contained_l21_to_l24_failure_never_suppresses_l21a(
    failure, expected, tmp_path, monkeypatch, git_executable
):
    from pi_harness_cfg1 import config_issuance
    from cfg1_doubles import FakeBroker

    tree = make_pi_world(tmp_path, monkeypatch)
    recorder = LeafRecorder()
    _record_closure_entries(monkeypatch, recorder.log)
    overrides = {}
    shutdown_result = None
    if failure == "L21":
        shutdown_result = "raise"
    elif failure in ("L22", "L23"):
        class _FailingBroker(FakeBroker):
            def diagnostics_counts(self):
                if failure == "L22":
                    raise RuntimeError("an injected L22 failure")
                return super().diagnostics_counts()

            def shutdown_for_cfg1(self):
                if failure == "L23":
                    raise RuntimeError("an injected L23 failure")
                return super().shutdown_for_cfg1()

        overrides["build_broker"] = lambda *, capability: _FailingBroker()
    else:
        monkeypatch.setattr(
            config_issuance,
            "scrub_config_issuance",
            lambda **_k: (_ for _ in ()).throw(RuntimeError("an injected L24 failure")),
        )
    outcome, recorder, made = _run(
        git_executable, tree, shutdown_result=shutdown_result, overrides=overrides, recorder=recorder
    )
    steps = [label for kind, label in recorder.log if kind == "step"]
    assert steps == ["L21", "L22", "L23", "L24", "L21A", "L25", "L26", "L27"]
    assert steps.count("L21A") == 1
    observations = outcome.observations
    assert observations["pi_profile_post_runtime_reobservation"] == expected
    closed, failure_steps = compute_lifecycle_closure_v2(observations)
    assert observations["lifecycle_all_closed"] is closed
    assert observations["lifecycle_failure_steps"] == list(failure_steps)
    _payload(observations)
    workspace = made.get("workspace")
    if workspace is not None:
        shutil.rmtree(workspace.experiment_root, ignore_errors=True)


@pytest.mark.parametrize("mode", ["procedure_raises", "leaf_raises_during_l21a"])
def test_c6_an_l21a_failure_is_unproven_and_never_suppresses_l25_to_l27(
    mode, tmp_path, monkeypatch, git_executable
):
    tree = make_pi_world(tmp_path, monkeypatch)
    log: list = []
    _record_closure_entries(monkeypatch, log)
    if mode == "procedure_raises":
        monkeypatch.setattr(
            run_executor,
            "reobserve_pi_profile_after_runtime",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("an injected L21A failure")),
        )
        recorder = LeafRecorder(log=log)
    else:
        def _hook(kind, path, inner_log):
            if kind == "enumerate" and ("step", "L21A") in inner_log:
                raise RuntimeError("an injected L21A leaf failure")

        recorder = LeafRecorder(hook=_hook, log=log)
    outcome, recorder, _made = _run(git_executable, tree, recorder=recorder)
    steps = [label for kind, label in log if kind == "step"]
    assert steps == ["L21", "L22", "L23", "L24", "L21A", "L25", "L26", "L27"]
    observations = outcome.observations
    assert observations["pi_profile_post_runtime_reobservation"] == "UNPROVEN"
    assert observations["lifecycle_all_closed"] is True  # L21A is not a closure predicate
    assert observations["lifecycle_failure_steps"] == []
    assert observations["verification_attempted"] is True
    assert observations["workspace_removed_verified"] is True
    assert _payload(observations)["run_classification"] == "INDETERMINATE_PI_PROFILE"


def test_c6_no_runtime_is_not_applicable_and_performs_no_walk(tmp_path, monkeypatch, git_executable):
    tree = make_pi_world(tmp_path, monkeypatch)
    recorder = LeafRecorder()
    _record_closure_entries(monkeypatch, recorder.log)
    outcome, recorder, _made = _run(
        git_executable,
        tree,
        overrides={"read_connection": lambda: (_ for _ in ()).throw(RuntimeError("no connection"))},
        recorder=recorder,
    )
    observations = outcome.observations
    assert observations["refused_at_step"] == "L4"
    assert observations["runtime_created"] is False
    assert observations["pi_profile_post_runtime_reobservation"] == "NOT_APPLICABLE"
    closure_start = recorder.log.index(("step", "L21"))
    assert not [entry for entry in recorder.log[closure_start:] if entry[0] in ("digest", "enumerate")]


class _LaunchRaisesWithProcess(FakeSupervisor):
    def launch(self):
        self.process = object()
        raise OSError("created, then failed at start-up")


class _ProcessAppearsAfterL14(FakeSupervisor):
    """L14's own read sees no process; L21's D-3 probe sees one."""

    def __init__(self):
        super().__init__()
        self._reads = 0

    @property
    def process(self):
        self._reads += 1
        return None if self._reads == 1 else object()

    @process.setter
    def process(self, value):
        pass

    def launch(self):
        raise OSError("launch failed")


@pytest.mark.parametrize("supervisor_cls", [_LaunchRaisesWithProcess, _ProcessAppearsAfterL14])
def test_c6_applicability_follows_the_d3_flip(supervisor_cls, tmp_path, monkeypatch, git_executable):
    tree = make_pi_world(tmp_path, monkeypatch)
    recorder = LeafRecorder()
    _record_closure_entries(monkeypatch, recorder.log)
    ports, _made = fu1_ports(
        git_executable, tree, leaves=recorder.leaves(), overrides={"build_supervisor": lambda **_k: supervisor_cls()}
    )
    observations = execute_cfg1_run(make_admission(), ports=ports).observations
    assert observations["refused_at_step"] == "L14"
    assert observations["runtime_created"] is True
    l21a_at = recorder.log.index(("step", "L21A"))
    assert [entry for entry in recorder.log[l21a_at:] if entry[0] == "digest"]
    # A refused-pre-dispatch run with a created process keeps its
    # classification and still records its L21A value.
    assert observations["pi_profile_post_runtime_reobservation"] == "PROVEN_UNCHANGED"
    payload = _payload(observations)
    assert payload["run_classification"] == "REFUSED_PRE_DISPATCH"


def test_c6_each_result_row(tmp_path, monkeypatch, git_executable):
    rows = {}

    # CHANGED -- a persistent payload mutation during the runtime (cx 10).
    tree = make_pi_world(tmp_path, monkeypatch, "changed")
    outcome, _r, _m = _run(
        git_executable,
        tree,
        hook=lambda: Path(tree.seam_path("dist/other.js")).write_bytes(b"export const other = 5;\n"),
    )
    rows["CHANGED/fingerprint"] = outcome.observations

    # CHANGED -- an exposure now present (exposure set of the run's profile).
    files, empty_dirs = _exposed_files()
    exposed = make_pi_world(tmp_path, monkeypatch, "exposed", files=files, empty_dirs=empty_dirs)
    outcome, _r, _m = _run(
        git_executable,
        exposed,
        hook=lambda: (Path(exposed.npm_dir) / "node_modules" / _EXPOSED_NAME).mkdir(parents=True),
    )
    rows["CHANGED/exposure"] = outcome.observations

    # UNPROVEN -- an exposure observation that cannot complete: an
    # intermediate component that is not a directory.
    unobservable = make_pi_world(tmp_path, monkeypatch, "unobservable", files=files, empty_dirs=empty_dirs)
    blocker = Path(unobservable.npm_dir) / "node_modules" / "@earendil-works" / "node_modules"
    outcome, _r, _m = _run(git_executable, unobservable, hook=lambda: blocker.write_bytes(b"not a directory"))
    rows["UNPROVEN/exposure"] = outcome.observations

    # UNPROVEN -- the direct child's exit was not proven by L21.
    tree = make_pi_world(tmp_path, monkeypatch, "no_exit")
    outcome, _r, _m = _run(git_executable, tree, shutdown_result={"stdin_closed": True})
    rows["UNPROVEN/exit"] = outcome.observations

    # UNPROVEN -- the walk could not complete (a bound now refuses it).
    tree = make_pi_world(tmp_path, monkeypatch, "incomplete")
    outcome, _r, _m = _run(
        git_executable, tree, hook=lambda: monkeypatch.setattr(pi_payload, "MAX_PAYLOAD_ENTRIES", 3)
    )
    monkeypatch.setattr(pi_payload, "MAX_PAYLOAD_ENTRIES", 250000)
    rows["UNPROVEN/walk"] = outcome.observations

    # UNPROVEN -- I_r drifted (a byte-identical copy at the same path).
    tree = make_pi_world(tmp_path, monkeypatch, "drift")
    outcome, _r, _m = _run(git_executable, tree, hook=lambda: replace_directory_with_identical_copy(tree.package_root))
    rows["UNPROVEN/root"] = outcome.observations

    # PROVEN_UNCHANGED.
    tree = make_pi_world(tmp_path, monkeypatch, "clean")
    outcome, _r, _m = _run(git_executable, tree)
    rows["PROVEN_UNCHANGED"] = outcome.observations

    for name, observations in rows.items():
        expected = name.split("/")[0]
        assert observations["pi_profile_post_runtime_reobservation"] == expected, name
        payload = _payload(observations)
        if name == "UNPROVEN/exit":
            assert payload["run_classification"] == "INDETERMINATE_LIFECYCLE"
        elif expected in ("CHANGED", "UNPROVEN"):
            assert payload["run_classification"] == "INDETERMINATE_PI_PROFILE", name
            assert observations["lifecycle_all_closed"] is True, name
        else:
            assert payload["run_classification"] == "INACTIVE"


def test_c6_counterexample_11_aba_is_undetected_the_documented_limit(tmp_path, monkeypatch, git_executable):
    tree = make_pi_world(tmp_path, monkeypatch)
    target = Path(tree.seam_path("dist/other.js"))
    original = target.read_bytes()

    def _mutate_then_restore():
        target.write_bytes(b"export const other = 'B';\n")
        target.write_bytes(original)

    outcome, _r, _m = _run(git_executable, tree, hook=_mutate_then_restore)
    # Asserted as the documented R-ABA residual, never as a guarantee.
    assert outcome.observations["pi_profile_post_runtime_reobservation"] == "PROVEN_UNCHANGED"


@pytest.mark.parametrize(
    "returned", ["NOT_APPLICABLE", None, True, 1, _StrSubclass("PROVEN_UNCHANGED"), "PROVEN_UNCHANGED ", object()]
)
def test_c6_a_malformed_procedure_value_is_unproven(returned, tmp_path, monkeypatch, git_executable):
    tree = make_pi_world(tmp_path, monkeypatch)
    calls: list[int] = []

    def _procedure(*a, **k):
        calls.append(1)
        return returned

    monkeypatch.setattr(run_executor, "reobserve_pi_profile_after_runtime", _procedure)
    outcome, _r, _m = _run(git_executable, tree)
    assert calls == [1]  # attempted exactly once; no retry
    observations = outcome.observations
    assert observations["pi_profile_post_runtime_reobservation"] == "UNPROVEN"
    assert observations["lifecycle_all_closed"] is True


# ---------------------------------------------------------------------------
# C-8 (runtime half) -- branch A on CHANGED/UNPROVEN; never C; no retry
# ---------------------------------------------------------------------------


def _observations_for(changed_at: int, value: str = "CHANGED"):
    def _for(admission):
        from pi_harness_cfg1.arms import ARM_SHAPE

        observations = happy_observations(runtime_reported_compat_shape=ARM_SHAPE[admission.arm_id])
        if admission.run_ordinal == changed_at:
            observations["pi_profile_post_runtime_reobservation"] = value
        return observations

    return _for


@pytest.mark.parametrize("value", ["CHANGED", "UNPROVEN"])
@pytest.mark.parametrize("ordinal", [1, 5, 9])
def test_c8_an_attribution_failure_halts_on_branch_a_never_c(ordinal, value, make_authority, monkeypatch):
    invoked: list[int] = []
    executor = synthetic_run_executor(observations_for=_observations_for(ordinal, value))

    def _counting(admission):
        invoked.append(admission.run_ordinal)
        return executor(admission)

    authority = make_authority("S1-X1")
    result = stage_runner._run_cfg1_stage_with_injected_executor(authority, run_executor=_counting)
    assert result.disposition == "STAGE_HALTED"
    assert result.halted_after_ordinal == ordinal
    assert result.halt_reason_code == HALT_PI_PROFILE_ATTRIBUTION_UNPROVEN
    assert invoked == list(range(1, ordinal + 1))  # no retry, no re-run, no next ordinal
    status = dict(result.ordinal_status)
    assert status[ordinal] == "RECORD_EMITTED"  # closure + evidence finished first
    assert all(status[k] == "NOT_EXECUTED" for k in range(ordinal + 1, 10))
    closure = json.loads(Path(authority.execution_directory, "S1_stage_closure.json").read_text(encoding="utf-8"))
    assert closure["pi_profile_attribution_halt"] is True
    assert closure["ordinal_pi_profile_binding"][str(ordinal)] == "STAGE_PROFILE"
    run = json.loads(next(Path(authority.execution_directory).glob(f"S1_{ordinal:02d}_*.json")).read_text(encoding="utf-8"))
    assert run["run_classification"] == "INDETERMINATE_PI_PROFILE"


def test_c8_the_attribution_flag_is_independent_of_which_code_wins(make_authority):
    """A refused-pre-dispatch run with a created process and CHANGED: the code
    is PRE_DISPATCH_REFUSAL (step 5 precedes 5A), and the independent flag
    still records the attribution failure."""

    def _for(admission):
        observations = happy_observations(
            **pre_dispatch_refusal_overrides("H1_MISMATCH", "L15"),
            runtime_reported_compat_shape="NOT_OBSERVED",
            runtime_reported_model_reasoning="NOT_OBSERVED",
            runtime_reported_thinking_level="NOT_OBSERVED",
            manipulation_check_agrees=False,
            h1_extension_identity_matched=False,
            h2_provider_model_identity_matched=False,
            pi_profile_post_runtime_reobservation="CHANGED",
        )
        return observations

    authority = make_authority("S1-X1")
    result = stage_runner._run_cfg1_stage_with_injected_executor(
        authority, run_executor=synthetic_run_executor(observations_for=_for)
    )
    assert result.halt_reason_code == "PRE_DISPATCH_REFUSAL"
    closure = json.loads(Path(authority.execution_directory, "S1_stage_closure.json").read_text(encoding="utf-8"))
    assert closure["pi_profile_attribution_halt"] is True
    assert closure["halted_after_ordinal"] == 1


@pytest.mark.parametrize(
    "runtime_created,reobservation",
    [(1, "PROVEN_UNCHANGED"), (True, _StrSubclass("PROVEN_UNCHANGED")), (None, "NOT_APPLICABLE"), (False, "PROVEN_UNCHANGED"), (True, "NOT_APPLICABLE")],
)
def test_c8_item_1a_fails_closed_on_malformed_in_memory_facts(runtime_created, reobservation, make_authority):
    """The runner's item 1A reads the in-memory facts with exact types: a
    malformed pair halts the stage even though the record then fails its own
    validator (EVIDENCE_REFUSED) -- it never admits the next ordinal."""

    def _for(admission):
        from pi_harness_cfg1.arms import ARM_SHAPE

        observations = happy_observations(runtime_reported_compat_shape=ARM_SHAPE[admission.arm_id])
        observations["runtime_created"] = runtime_created
        observations["pi_profile_post_runtime_reobservation"] = reobservation
        return observations

    authority = make_authority("S1-X1")
    result = stage_runner._run_cfg1_stage_with_injected_executor(
        authority, run_executor=synthetic_run_executor(observations_for=_for)
    )
    assert result.halted_after_ordinal == 1
    assert result.ordinals_attempted == (1,)


# ---------------------------------------------------------------------------
# C-15 / C-24 -- the closure is built from the LEDGERS, never from artifacts;
#                an EVIDENCE_REFUSED ordinal carries no profile evidence
# ---------------------------------------------------------------------------


def test_c24_an_evidence_refused_ordinal_is_no_run_evidence_and_no_artifact_is_read(
    make_authority, monkeypatch
):
    authority = make_authority("S1-X1")
    real_scrub = writers._scrub
    refused_once: list[int] = []

    def _scrub(canonical, safety):
        if canonical.get("run_ordinal") == 3 and canonical.get("record_kind") == "harness configuration diagnostic run" and not refused_once:
            refused_once.append(1)
            raise writers.Cfg1WriterError("SCRUB_NEEDLE_MATCH")  # row 11: non-halting
        return real_scrub(canonical, safety)

    monkeypatch.setattr(writers, "_scrub", _scrub)
    reads: list[str] = []
    real_open = builtins.open

    def _open(file, mode="r", *args, **kwargs):
        if "w" not in mode and "x" not in mode and "a" not in mode and str(authority.execution_directory) in str(file):
            reads.append(str(file))
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", _open)
    real_loads = json.loads
    json_reads: list[int] = []
    monkeypatch.setattr(json, "loads", lambda *a, **k: (json_reads.append(1), real_loads(*a, **k))[1])
    result = stage_runner._run_cfg1_stage_with_injected_executor(authority, run_executor=synthetic_run_executor())
    monkeypatch.undo()
    assert result.disposition == "STAGE_COMPLETED"
    assert dict(result.ordinal_status)[3] == "EVIDENCE_REFUSED"
    assert reads == []  # no run, refusal or closure artifact was ever read back
    closure = json.loads(Path(authority.execution_directory, "S1_stage_closure.json").read_text(encoding="utf-8"))
    assert closure["ordinal_pi_profile_binding"]["3"] == "NO_RUN_EVIDENCE"
    refusal = json.loads(Path(authority.execution_directory, "S1_03_E.json").read_text(encoding="utf-8"))
    assert refusal["record_version"] == "pi-harness-cfg1-refusal.v3"
    assert "pi_profile_id" not in refusal  # a refusal carries no per-run profile field


def test_c15_the_closure_ledger_sources_are_never_artifacts_statically():
    source = (_PACKAGE_DIR / "stage_runner.py").read_text(encoding="utf-8")
    for forbidden in ("json.load", "read_text", "read_bytes", "open(", "binding.verify", "glob("):
        assert forbidden not in source, forbidden


# ---------------------------------------------------------------------------
# C-25 -- capture point, no supply channel, no module-level sealer
# ---------------------------------------------------------------------------


def test_c25_ledger_facts_are_captured_before_l29_from_the_in_memory_outcome(make_authority, monkeypatch):
    """A mutation of the outcome's observations AT L29 (inside the payload
    builder) reaches the record but never the ledger, which captured first."""
    authority = make_authority("S1-X1")
    real_build = stage_runner.build_cfg1_run_payload
    admissions: list = []
    original = session_synthetic_pi_tree().profile_id

    def _build(**kwargs):
        if kwargs["run_ordinal"] == 1:
            kwargs["observations"]["pi_profile_id"] = "e" * 64
        return real_build(**kwargs)

    monkeypatch.setattr(stage_runner, "build_cfg1_run_payload", _build)
    executor = synthetic_run_executor()

    def _recording(admission):
        admissions.append(admission.stage_pi_profile_id)
        return executor(admission)

    captured: list = []
    real_writer = stage_runner.emit_cfg1_stage_closure

    def _capture(authority_, /, *, decision):
        captured.append(decision)
        return real_writer(authority_, decision=decision)

    monkeypatch.setattr(stage_runner, "emit_cfg1_stage_closure", _capture)
    stage_runner._run_cfg1_stage_with_injected_executor(authority, run_executor=_recording)
    assert admissions[1:] == [original] * 8
    assert captured[0].stage_pi_profile_id == original
    # Ordinal 1's RECORD carries the mutated value, so its binding is NO_PROFILE
    # only if the ledger had read the record -- it did not.
    assert dict(captured[0].ordinal_pi_profile_binding)[1] == "STAGE_PROFILE"


def test_c25_a_mutated_admission_never_reaches_the_ledger(make_authority):
    executor = synthetic_run_executor()

    def _mutating(admission):
        object.__setattr__(admission, "stage_pi_profile_id", "e" * 64)
        return executor(admission)

    authority = make_authority("S1-X1")
    result = stage_runner._run_cfg1_stage_with_injected_executor(authority, run_executor=_mutating)
    assert result.disposition == "STAGE_COMPLETED"
    closure = json.loads(Path(authority.execution_directory, "S1_stage_closure.json").read_text(encoding="utf-8"))
    assert closure["stage_pi_profile_id"] == session_synthetic_pi_tree().profile_id


def test_c25_a_later_ordinals_different_fact_never_moves_the_stage_profile(make_authority):
    def _for(admission):
        from pi_harness_cfg1.arms import ARM_SHAPE

        observations = happy_observations(runtime_reported_compat_shape=ARM_SHAPE[admission.arm_id])
        if admission.run_ordinal == 2:
            observations["pi_profile_id"] = "e" * 64  # a malformed double only
        return observations

    authority = make_authority("S1-X1")
    result = stage_runner._run_cfg1_stage_with_injected_executor(
        authority, run_executor=synthetic_run_executor(observations_for=_for)
    )
    # A synthetic double violated L1's constraint; the closure then fails its
    # own invariant 6 (NO_PROFILE at a non-halt ordinal) -- fail closed, never
    # a re-fixed stage profile and never a normal completion.
    assert result.stage_closure_confirmed is False
    assert result.disposition == "STAGE_CLOSURE_EMISSION_FAILED"


def test_c25_no_supply_channel_exists_in_any_public_or_writer_signature():
    from pi_harness_cfg1 import stage_decision

    assert list(inspect.signature(stage_runner.run_cfg1_stage).parameters) == ["authority"]
    assert list(inspect.signature(stage_runner._run_cfg1_stage_with_injected_executor).parameters) == [
        "authority",
        "run_executor",
        "_internal_probe",
    ]
    profile_names = {"stage_pi_profile_id", "ordinal_pi_profile_binding", "pi_profile_attribution_halt", "profile_fact", "profile_ledger"}
    for module in (stage_runner, writers, stage_decision, run_executor):
        for name, value in inspect.getmembers(module, inspect.isfunction):
            if value.__module__ != module.__name__:
                continue
            assert not set(inspect.signature(value).parameters) & profile_names, (module.__name__, name)
    assert list(inspect.signature(writers.emit_cfg1_stage_closure).parameters) == ["authority", "decision"]


def test_c25_the_profile_ledger_is_a_confined_local_and_no_module_level_sealer_exists():
    from pi_harness_cfg1 import stage_decision

    source = (_PACKAGE_DIR / "stage_runner.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    owners = []
    for function in [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]:
        for node in ast.walk(function):
            if isinstance(node, ast.Name) and node.id == "_profile_ledger":
                owners.append(function.name)
    # Only the one routine and its nested closures touch it ...
    allowed = {"_run_cfg1_stage_with_injected_executor", "_seal_terminal_decision", "_body"}
    assert set(owners) <= allowed and owners
    # ... it is assigned exactly once, never global, never returned.
    assigns = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and any(isinstance(target, ast.Name) and target.id == "_profile_ledger" for target in getattr(node, "targets", [getattr(node, "target", None)]))
    ]
    assert len(assigns) == 1
    for node in ast.walk(tree):
        if isinstance(node, ast.Global):
            assert "_profile_ledger" not in node.names
        if isinstance(node, ast.Return) and node.value is not None:
            assert "_profile_ledger" not in ast.unparse(node.value)
    for module in (stage_runner, stage_decision, writers):
        for name in dir(module):
            assert "seal_terminal" not in name, (module.__name__, name)
    assert "_profile_ledger" not in dir(stage_runner)


# ---------------------------------------------------------------------------
# C-26 -- no runtime module references or reads the candidate staging area
# ---------------------------------------------------------------------------


_RUNTIME_MODULES = (
    "pi_identity.py",
    "pi_payload.py",
    "pi_fs_leaves.py",
    "run_executor.py",
    "run_contract.py",
    "stage_runner.py",
    "stage_decision.py",
    "writers.py",
    "records.py",
    "classification.py",
    "halt.py",
    "lifecycle.py",
    "stage_output.py",
    "execution_namespace.py",
    "binding.py",
    "pi_profile_binding_verifier.py",
    "pi_profile_policy_loader.py",
)


@pytest.mark.parametrize("module_name", _RUNTIME_MODULES)
def test_c26_no_runtime_module_references_the_staging_namespace(module_name):
    source = (_PACKAGE_DIR / module_name).read_text(encoding="utf-8")
    for needle in ("pi_profile_candidates", "STAGING_DIRECTORY", "_STAGING", "pi_profile_discovery", "candidate.json"):
        assert needle not in source, (module_name, needle)
