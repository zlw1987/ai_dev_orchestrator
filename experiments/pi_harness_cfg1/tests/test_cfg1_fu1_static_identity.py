"""FU1 (R6 + AMEND1): the static Pi identity proof, the gate, L1 and L14.

Tests A, D, F, G (inside P), H, I, J, L, P, S, U, V and AA-AD, AF, AG of
``PHASE_5F3B_HARNESS_CFG1_L1_BOUNDARY_FU1_DESIGN.md`` Sec. 11 as reconciled by
``..._OC3_AMEND1_DESIGN.md`` Sec. 16.

Every Pi tree here is SYNTHETIC, under ``tmp_path``, with a TEST-OWNED pin
table: its ``node.exe`` is inert bytes that nothing executes, its ``pi.cmd``
is never read, and its 20 "seam" files are synthetic. The proof runs its
GENUINE leaves over that tree. No real Node or Pi, no socket, no credential.
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
from pathlib import Path

import pytest
from cfg1_doubles import FakeSupervisor, build_synthetic_pi_tree, use_test_owned_pin_table
from cfg1_fu1_support import (
    AMBIENT_DECOYS,
    LeafRecorder,
    ProcessTripwire,
    RecordingMapping,
    file_identity,
    fu1_ports,
    install_recording_genuine_leaves,
    make_admission,
    make_pi_world,
    replace_directory_with_identical_copy,
    replace_same_bytes,
)

from pi_harness_cfg1 import (
    config_issuance,
    extension_issuance,
    pi_fs_leaves,
    pi_identity,
    run_executor,
    run_workspace,
    stage_output,
)
from pi_harness_cfg1.pi_identity import (
    PI_IDENTITY_DRIFTED_DURING_PROOF,
    PI_IDENTITY_GATE_PASSED,
    PI_RESOLUTION_FAILED,
    PI_SEAM_UNPROVEN,
    Cfg1PiIdentity,
    Cfg1PiIdentityError,
    PiProofLeaves,
    PiProofResult,
    genuine_pi_proof_leaves,
    pre_consumption_pi_identity_gate,
    prove_pi_identity,
    reprove_pi_identity_for_launch,
)
from pi_harness_cfg1.records import (
    _require_valid_cfg1_run_payload_v2,
    build_cfg1_run_payload,
)
from pi_harness_cfg1.run_executor import execute_cfg1_run

_PACKAGE_DIR = Path(__file__).resolve().parents[1]


def _record(outcome) -> dict:
    """Build the v2 record, round-trip it through JSON, and validate it ALONE."""
    payload = build_cfg1_run_payload(
        stage_id="S1",
        stage_execution_id="S1-X1",
        run_ordinal=1,
        observations=outcome.observations,
    )
    parsed = json.loads(json.dumps(payload))
    _require_valid_cfg1_run_payload_v2(parsed)
    return parsed


def _counting(overrides: dict, name: str, counter: list, *, then=None):
    def _port(*args, **kwargs):
        counter.append(name)
        if then is None:
            raise AssertionError(f"{name} must never be reached here")
        return then(*args, **kwargs)

    overrides[name] = _port


# ---------------------------------------------------------------------------
# AC -- a successful static proof, and exactly what it carries
# ---------------------------------------------------------------------------


def test_ac_a_passing_static_proof_reads_every_seam_once_and_carries_no_version(
    tmp_path, monkeypatch
):
    tree = make_pi_world(tmp_path, monkeypatch)
    recorder = LeafRecorder()
    json_calls: list[int] = []
    real_loads = json.loads
    monkeypatch.setattr(json, "loads", lambda *a, **k: (json_calls.append(1), real_loads(*a, **k))[1])

    result = prove_pi_identity({"PATH": tree.path_value}, leaves=recorder.leaves())

    assert type(result) is PiProofResult
    assert result.seam_digests_match is True
    assert result.failure_code is None
    identity = result.identity
    assert type(identity) is Cfg1PiIdentity
    # Every one of the 20 keys, including package.json, read ONCE each.
    digested = recorder.digests()
    assert sorted(digested) == sorted(tree.seam_path(key) for key in tree.pin_table)
    assert len(digested) == len(set(digested)) == 20
    assert tree.seam_path("package.json") in digested
    # No JSON parse of package.json (nor of anything) happens in P.
    assert json_calls == []
    # Exactly AMEND1 Sec. 10's five attributes, and no version-shaped name.
    assert set(Cfg1PiIdentity.__slots__) == {
        "node_executable",
        "pi_cli_js",
        "pi_package_root",
        "node_identity",
        "package_root_identity",
    }
    for name in Cfg1PiIdentity.__slots__ + PiProofResult.__slots__:
        assert "version" not in name and "reported" not in name, name
    assert not hasattr(identity, "__dict__")
    assert identity.node_executable == tree.node_exe
    assert identity.pi_package_root == tree.package_root
    assert identity.pi_cli_js == os.path.join(tree.package_root, "dist", "cli.js")
    assert identity.node_identity == file_identity(tree.node_exe)
    assert identity.package_root_identity == file_identity(tree.package_root)


def test_ac_the_identity_and_result_objects_are_p_only_and_immutable(tmp_path, monkeypatch):
    tree = make_pi_world(tmp_path, monkeypatch)
    result = prove_pi_identity({"PATH": tree.path_value}, leaves=genuine_pi_proof_leaves())
    identity = result.identity
    with pytest.raises(Cfg1PiIdentityError):
        Cfg1PiIdentity(
            object(),
            node_executable=tree.node_exe,
            pi_cli_js=identity.pi_cli_js,
            pi_package_root=tree.package_root,
            node_identity=identity.node_identity,
            package_root_identity=identity.package_root_identity,
        )
    with pytest.raises(Cfg1PiIdentityError):
        PiProofResult(object(), seam_digests_match=True, failure_code=None, identity=identity)
    with pytest.raises(Cfg1PiIdentityError):
        identity.node_executable = "C:\\elsewhere\\node.exe"
    with pytest.raises(Cfg1PiIdentityError):
        result.failure_code = None
    import copy
    import pickle

    with pytest.raises(Cfg1PiIdentityError):
        copy.copy(identity)
    with pytest.raises(Cfg1PiIdentityError):
        pickle.dumps(identity)


# ---------------------------------------------------------------------------
# L -- ONE proof, reached by the gate and by L1; leaves only
# ---------------------------------------------------------------------------


def test_l_the_gate_and_l1_reach_the_same_proof_object_and_leaf_binding():
    assert run_executor.prove_pi_identity is pi_identity.prove_pi_identity
    assert run_executor.reprove_pi_identity_for_launch is pi_identity.reprove_pi_identity_for_launch
    gate_names = pi_identity.pre_consumption_pi_identity_gate.__code__.co_names
    assert "prove_pi_identity" in gate_names and "genuine_pi_proof_leaves" in gate_names
    # The genuine executor ports bind the SAME genuine leaf effects.
    ports = run_executor.default_cfg1_run_ports(ambient_environ={})
    genuine = genuine_pi_proof_leaves()
    assert ports.pi_proof_leaves.inspect is genuine.inspect is pi_fs_leaves.inspect_no_follow
    assert ports.pi_proof_leaves.read_digest is genuine.read_digest
    assert ports.pi_proof_leaves.checkout_root == genuine.checkout_root
    assert genuine.checkout_root == str(_PACKAGE_DIR.parents[1])


def test_l_ps_leaf_surface_has_no_process_or_environment_leaf():
    # AMEND1 Sec. 16.3: asserted STRUCTURALLY.
    assert PiProofLeaves.__slots__ == ("inspect", "read_digest", "checkout_root")
    for name in PiProofLeaves.__slots__:
        for forbidden in ("run", "process", "spawn", "exec", "env", "probe", "launch"):
            assert forbidden not in name
    fields = run_executor.Cfg1RunPorts.__dataclass_fields__
    assert "resolve_runtime_identity" not in fields
    assert type(fields["pi_proof_leaves"].type) is str or fields["pi_proof_leaves"].type is PiProofLeaves
    with pytest.raises(Cfg1PiIdentityError):
        prove_pi_identity({"PATH": ""}, leaves=object())


def test_l_the_order_lives_in_p_and_gate_and_l1_walk_the_same_sequence(
    tmp_path, monkeypatch, git_executable
):
    tree = make_pi_world(tmp_path, monkeypatch)
    gate_recorder = LeafRecorder()
    install_recording_genuine_leaves(monkeypatch, gate_recorder)
    assert pre_consumption_pi_identity_gate({"PATH": tree.path_value}) == PI_IDENTITY_GATE_PASSED
    gate_sequence = list(gate_recorder.log)
    monkeypatch.undo()
    use_test_owned_pin_table(monkeypatch, tree.pin_table)

    l1_recorder = LeafRecorder()
    ports, _made = fu1_ports(
        git_executable,
        tree,
        leaves=l1_recorder.leaves(),
        overrides={"git_executable": lambda: (_ for _ in ()).throw(RuntimeError("stop at L1"))},
    )
    outcome = execute_cfg1_run(make_admission(), ports=ports)
    assert outcome.observations["refused_at_step"] == "L1"
    # L1 re-invoked every leaf, from scratch, in exactly the gate's order.
    assert l1_recorder.log == gate_sequence
    # Fixed stage order: resolution inspections, then 20 digests, then P2R
    # (root identity, then node.exe identity) and nothing after.
    kinds = [kind for kind, _ in gate_sequence]
    first_digest = kinds.index("digest")
    last_digest = len(kinds) - 1 - kinds[::-1].index("digest")
    assert kinds[first_digest : last_digest + 1].count("digest") == 20
    assert gate_sequence[-2:] == [("inspect", tree.package_root), ("inspect", tree.node_exe)]


# ---------------------------------------------------------------------------
# F -- P reads exactly one ambient name, PATH, by name
# ---------------------------------------------------------------------------


def test_f_the_gate_and_l1_read_only_path_by_name(tmp_path, monkeypatch, git_executable):
    tree = make_pi_world(tmp_path, monkeypatch)
    ambient = RecordingMapping({**AMBIENT_DECOYS, "PATH": tree.path_value})
    assert pre_consumption_pi_identity_gate(ambient) == PI_IDENTITY_GATE_PASSED
    assert ambient.lookups == ["PATH"]
    assert ambient.iterations == 0

    ambient_l1 = RecordingMapping({**AMBIENT_DECOYS, "PATH": tree.path_value})
    ports, _made = fu1_ports(
        git_executable,
        tree,
        ambient=ambient_l1,
        overrides={"git_executable": lambda: (_ for _ in ()).throw(RuntimeError("stop"))},
    )
    outcome = execute_cfg1_run(make_admission(), ports=ports)
    assert outcome.observations["refused_at_step"] == "L1"
    assert outcome.observations["pi_identity_failure_code"] is None
    assert ambient_l1.lookups == ["PATH"]
    assert ambient_l1.iterations == 0


def test_f_an_absent_or_malformed_path_is_a_resolution_refusal(tmp_path, monkeypatch):
    make_pi_world(tmp_path, monkeypatch)
    leaves = genuine_pi_proof_leaves()
    for ambient in ({}, {"PATH": 7}, {"PATH": b"C:\\x"}):
        result = prove_pi_identity(ambient, leaves=leaves)
        assert (result.failure_code, result.seam_digests_match) == (PI_RESOLUTION_FAILED, False)


# ---------------------------------------------------------------------------
# A / AB / D -- anticipated L1 refusals through the REAL executor
# ---------------------------------------------------------------------------


def _l1_refusal_case(case, tree, monkeypatch):
    """Return ``(ambient_path, leaves, overrides, expected_failure, expected_seam)``."""
    if case == "resolution":
        return tree.npm_dir, None, {}, PI_RESOLUTION_FAILED, False
    if case == "seam":
        Path(tree.seam_path("dist/cli.js")).write_bytes(b"tampered cli")
        return tree.path_value, None, {}, PI_SEAM_UNPROVEN, False
    if case == "drift":
        fired: list[int] = []

        def _hook(kind, path, log):
            if kind == "digest" and not fired:
                fired.append(1)
                replace_same_bytes(tree.node_exe)

        return tree.path_value, LeafRecorder(hook=_hook).leaves(), {}, PI_IDENTITY_DRIFTED_DURING_PROOF, True
    assert case == "git"
    return (
        tree.path_value,
        None,
        {"git_executable": lambda: (_ for _ in ()).throw(RuntimeError("no git"))},
        None,
        True,
    )


@pytest.mark.parametrize("case", ["resolution", "seam", "drift", "git"])
def test_a_and_ab_an_l1_refusal_closes_everything_and_starts_no_process(
    case, tmp_path, monkeypatch, git_executable
):
    tree = make_pi_world(tmp_path, monkeypatch)
    path_value, leaves, overrides, expected_failure, expected_seam = _l1_refusal_case(
        case, tree, monkeypatch
    )
    reached: list[str] = []
    for port in ("mint_workspace", "read_connection", "observe_route"):
        _counting(overrides, port, reached)
    ports, _made = fu1_ports(
        git_executable,
        tree,
        leaves=leaves,
        ambient={"SystemRoot": "C:\\Windows", "PATH": path_value},
        overrides=overrides,
    )
    tripwire = ProcessTripwire(monkeypatch, delegate=False)
    outcome = execute_cfg1_run(make_admission(), ports=ports)
    monkeypatch.undo()

    observations = outcome.observations
    assert tripwire.count == 0
    assert reached == []
    assert observations["refused_at_step"] == "L1"
    assert observations["pre_dispatch_refusal_code"] == "OFFLINE_PREFLIGHT_FAILED"
    assert observations["pi_identity_failure_code"] == expected_failure
    assert observations["pi_seam_digests_match"] is expected_seam
    assert observations["unexpected_failure_step"] is None
    assert observations["workspace_mint_state"] == "NOT_ATTEMPTED"
    assert observations["lifecycle_failure_steps"] == []
    assert observations["lifecycle_all_closed"] is True
    assert observations["dispatch_state"] == "NOT_ATTEMPTED"
    assert run_workspace.minted_workspace_count() == 0
    assert config_issuance.issued_token_count() == 0
    assert extension_issuance.issued_extension_token_count() == 0
    record = _record(outcome)
    assert record["record_version"] == "pi-harness-cfg1-run.v2"
    assert record["run_classification"] == "REFUSED_PRE_DISPATCH"
    assert "pi_observed_version" not in record
    assert "pi_version_probe_attempted" not in record


@pytest.mark.parametrize("case", ["resolution", "seam", "drift", "git"])
def test_a_an_l1_refusal_through_the_stage_runner_halts_pre_dispatch(
    case, tmp_path, monkeypatch, git_executable, make_authority
):
    from pi_harness_cfg1.stage_runner import _run_cfg1_stage_with_injected_executor

    tree = make_pi_world(tmp_path, monkeypatch)
    path_value, leaves, overrides, expected_failure, _seam = _l1_refusal_case(
        case, tree, monkeypatch
    )
    ports, _made = fu1_ports(
        git_executable,
        tree,
        leaves=leaves,
        ambient={"SystemRoot": "C:\\Windows", "PATH": path_value},
        overrides=overrides,
    )
    authority = make_authority("S1-X1")
    result = _run_cfg1_stage_with_injected_executor(
        authority, run_executor=lambda admission: execute_cfg1_run(admission, ports=ports)
    )
    assert result.halted_after_ordinal == 1
    assert result.halt_reason_code == "PRE_DISPATCH_REFUSAL"
    status = dict(result.ordinal_status)
    assert status[1] == "RECORD_EMITTED"
    assert all(status[ordinal] == "NOT_EXECUTED" for ordinal in range(2, 10))
    written = json.loads(
        Path(authority.execution_directory, "S1_01_Q.json").read_text(encoding="utf-8")
    )
    assert written["pi_identity_failure_code"] == expected_failure
    assert written["workspace_mint_state"] == "NOT_ATTEMPTED"
    assert written["lifecycle_failure_steps"] == []


def _make_seam_component_a_junction(tree, tmp_path):
    from conftest import make_directory_redirect

    dist = os.path.join(tree.package_root, "dist")
    real = str(tmp_path / "dist_real")
    shutil.move(dist, real)
    make_directory_redirect(Path(dist), Path(real))


@pytest.mark.parametrize(
    "perturbation",
    ["mismatch", "missing", "reparse_component", "non_regular", "oversize", "other_release"],
)
def test_d_every_seam_failure_refuses_at_l1_before_any_credential(
    perturbation, tmp_path, monkeypatch, git_executable
):
    tree = make_pi_world(tmp_path, monkeypatch)
    if perturbation == "mismatch":
        Path(tree.seam_path("dist/main.js")).write_bytes(b"one byte changed")
    elif perturbation == "missing":
        os.unlink(tree.seam_path("dist/core/sdk.js"))
    elif perturbation == "reparse_component":
        try:
            _make_seam_component_a_junction(tree, tmp_path)
        except OSError:
            pytest.skip("no directory redirect available on this platform")
    elif perturbation == "non_regular":
        target = tree.seam_path("dist/modes/rpc/jsonl.js")
        os.unlink(target)
        os.mkdir(target)
    elif perturbation == "oversize":
        monkeypatch.setattr(pi_identity, "MAX_SEAM_FILE_BYTES", 8)
    else:
        # A different Pi release's package.json -- the D1 class. Its bytes
        # differ from the reviewed ones, so this is a SEAM failure; nothing
        # reads, parses or reports a version.
        Path(tree.seam_path("package.json")).write_bytes(
            b'{"name":"@earendil-works/pi-coding-agent","version":"0.87.0"}\n'
        )
    reached: list[str] = []
    overrides: dict = {}
    for port in ("mint_workspace", "read_connection", "observe_route"):
        _counting(overrides, port, reached)
    ports, _made = fu1_ports(git_executable, tree, overrides=overrides)
    tripwire = ProcessTripwire(monkeypatch, delegate=False)
    outcome = execute_cfg1_run(make_admission(), ports=ports)
    events = tripwire.count
    monkeypatch.undo()

    observations = outcome.observations
    assert events == 0
    assert reached == []
    assert observations["pi_seam_digests_match"] is False
    assert observations["pi_identity_failure_code"] == PI_SEAM_UNPROVEN
    assert observations["pre_dispatch_refusal_code"] == "OFFLINE_PREFLIGHT_FAILED"
    record = _record(outcome)
    assert "pi_observed_version" not in record
    assert "pi_version_probe_attempted" not in record


# ---------------------------------------------------------------------------
# G (inside P) -- an unexpected raise at every P boundary
# ---------------------------------------------------------------------------


def _raise_on(kind: str, index: int):
    seen = {"inspect": 0, "digest": 0}

    def _hook(hook_kind, path, log):
        if hook_kind == kind:
            seen[kind] += 1
            if seen[kind] == index:
                raise RuntimeError("an injected P-boundary raise 4c2e")

    return _hook


def _raise_after_twentieth_digest():
    def _hook(kind, path, log):
        if kind == "inspect" and sum(1 for k, _ in log if k == "digest") == 20:
            raise RuntimeError("an injected P2R raise 4c2e")

    return _hook


@pytest.mark.parametrize(
    "boundary",
    [
        "before_p1_completes",
        "after_p1_before_p2_completes",
        "after_p2_before_p2r_completes",
        "during_result_construction",
        "during_shape_validation",
        "after_commit_git_resolution",
    ],
)
def test_g_an_unexpected_raise_inside_l1_is_unexpected_step_failure(
    boundary, tmp_path, monkeypatch, git_executable
):
    tree = make_pi_world(tmp_path, monkeypatch)
    leaves = None
    if boundary == "before_p1_completes":
        leaves = LeafRecorder(hook=_raise_on("inspect", 1)).leaves()
    elif boundary == "after_p1_before_p2_completes":
        leaves = LeafRecorder(hook=_raise_on("digest", 1)).leaves()
    elif boundary == "after_p2_before_p2r_completes":
        leaves = LeafRecorder(hook=_raise_after_twentieth_digest()).leaves()
    elif boundary == "during_result_construction":
        def _broken_identity(*_a, **_k):
            raise RuntimeError("an injected construction raise 4c2e")

        monkeypatch.setattr(pi_identity, "Cfg1PiIdentity", _broken_identity)
    elif boundary == "during_shape_validation":
        monkeypatch.setattr(
            run_executor,
            "require_pi_proof_result_shape",
            lambda result: (_ for _ in ()).throw(RuntimeError("shape 4c2e")),
        )
    else:
        monkeypatch.setattr(
            run_executor,
            "_resolve_git_for_l1",
            lambda ports: (_ for _ in ()).throw(RuntimeError("after commit 4c2e")),
        )
    ports, _made = fu1_ports(git_executable, tree, leaves=leaves)
    tripwire = ProcessTripwire(monkeypatch, delegate=False)
    outcome = execute_cfg1_run(make_admission(), ports=ports)
    events = tripwire.count
    monkeypatch.undo()
    use_test_owned_pin_table(monkeypatch, tree.pin_table)

    observations = outcome.observations
    assert events == 0
    assert observations["refused_at_step"] == "L1"
    assert observations["pre_dispatch_refusal_code"] == "UNEXPECTED_STEP_FAILURE"
    assert observations["pi_identity_failure_code"] is None
    expected_seam = boundary == "after_commit_git_resolution"
    assert observations["pi_seam_digests_match"] is expected_seam
    assert observations["unexpected_failure_step"] is None
    assert "RUN_STEP_RAISED_UNEXPECTEDLY" in outcome.console_codes
    record = _record(outcome)  # the v2 validator, on the serialized record ALONE
    assert "4c2e" not in json.dumps(record)
    assert "4c2e" not in json.dumps(list(outcome.console_codes))


# ---------------------------------------------------------------------------
# H / AA -- the pre-consumption gate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "variant", ["pass", "seam_drift", "other_release", "identity_drift", "resolution"]
)
def test_h_and_aa_the_gate_returns_one_code_consumes_nothing_and_starts_nothing(
    variant, tmp_path, monkeypatch, cfg1_package_dir
):
    tree = make_pi_world(tmp_path, monkeypatch)
    path_value = tree.path_value
    expected = PI_IDENTITY_GATE_PASSED
    if variant == "seam_drift":
        Path(tree.seam_path("dist/core/agent-session.js")).write_bytes(b"drift")
        expected = PI_SEAM_UNPROVEN
    elif variant == "other_release":
        Path(tree.seam_path("package.json")).write_bytes(b'{"version":"0.87.0"}\n')
        expected = PI_SEAM_UNPROVEN
    elif variant == "identity_drift":
        fired: list[int] = []

        def _hook(kind, path, log):
            if kind == "digest" and not fired:
                fired.append(1)
                replace_directory_with_identical_copy(tree.package_root)

        install_recording_genuine_leaves(monkeypatch, LeafRecorder(hook=_hook))
        expected = PI_IDENTITY_DRIFTED_DURING_PROOF
    elif variant == "resolution":
        path_value = tree.node_dir
        expected = PI_RESOLUTION_FAILED

    results_root = cfg1_package_dir / "results"
    minted_before = dict(stage_output._STAGE_OUTPUT_MINTED)
    ambient = RecordingMapping({**AMBIENT_DECOYS, "PATH": path_value})
    tripwire = ProcessTripwire(monkeypatch, delegate=False)
    code = pre_consumption_pi_identity_gate(ambient)
    events = tripwire.count

    assert code == expected
    assert type(code) is str
    assert events == 0
    assert ambient.lookups == ["PATH"]
    assert stage_output._STAGE_OUTPUT_MINTED == minted_before
    assert not results_root.exists()
    assert run_workspace.minted_workspace_count() == 0
    assert config_issuance.issued_token_count() == 0


def test_aa_the_gate_is_total_and_never_returns_anything_reusable(monkeypatch):
    monkeypatch.setattr(
        pi_fs_leaves,
        "inspect_no_follow",
        lambda path: (_ for _ in ()).throw(RuntimeError("leaf exploded")),
    )
    assert (
        pre_consumption_pi_identity_gate({"PATH": "C:\\Windows"})
        == "PI_IDENTITY_GATE_UNEXPECTED_FAILURE"
    )
    assert pi_identity.PI_IDENTITY_GATE_CODES == {
        "PI_IDENTITY_PROVEN",
        "PI_IDENTITY_GATE_UNEXPECTED_FAILURE",
        PI_RESOLUTION_FAILED,
        PI_SEAM_UNPROVEN,
        PI_IDENTITY_DRIFTED_DURING_PROOF,
    }
    import inspect as _inspect

    signature = _inspect.signature(pre_consumption_pi_identity_gate)
    assert list(signature.parameters) == ["ambient_environ"]
    assert signature.return_annotation in ("str", str)


_PROCESS_NAME = re.compile(r"CreateProcess|ShellExecute|WinExec")
_OS_PROCESS_ATTRS = re.compile(r"^(system|startfile|spawn\w*|exec[lv]\w*|popen|fork\w*)$")


@pytest.mark.parametrize("module_name", ["pi_identity", "pi_fs_leaves", "preflight"])
def test_aa_static_audit_p_the_gate_and_the_leaves_cannot_create_a_process(module_name):
    source = (_PACKAGE_DIR / f"{module_name}.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in ("subprocess", "multiprocessing"), alias.name
                assert alias.name != "asyncio.subprocess"
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert module.split(".")[0] not in ("subprocess", "multiprocessing"), module
            assert module != "asyncio.subprocess" and not (
                module == "asyncio" and any(a.name == "subprocess" for a in node.names)
            )
            assert not (module == "ar2.launch"), "P must not reach the AR2 launcher"
        if isinstance(node, ast.Attribute):
            assert _PROCESS_NAME.search(node.attr) is None, node.attr
            if isinstance(node.value, ast.Name) and node.value.id == "os":
                assert _OS_PROCESS_ATTRS.match(node.attr) is None, node.attr
        if isinstance(node, ast.Name):
            assert _PROCESS_NAME.search(node.id) is None, node.id
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert _PROCESS_NAME.search(node.value) is None, node.value
    if module_name == "pi_fs_leaves":
        kernel32 = {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "_K32"
        }
        assert kernel32 == {"CreateFileW", "CloseHandle", "GetFileInformationByHandleEx", "GetFileType"}


# ---------------------------------------------------------------------------
# I -- gate passes on S0, the tree drifts, L1 re-proves from scratch
# ---------------------------------------------------------------------------


def test_i_a_drift_after_the_gate_is_caught_by_l1s_own_fresh_proof(
    tmp_path, monkeypatch, git_executable
):
    tree = make_pi_world(tmp_path, monkeypatch)
    assert pre_consumption_pi_identity_gate({"PATH": tree.path_value}) == PI_IDENTITY_GATE_PASSED
    Path(tree.seam_path("dist/core/defaults.js")).write_bytes(b"drifted after the gate")

    recorder = LeafRecorder()
    ports, _made = fu1_ports(git_executable, tree, leaves=recorder.leaves())
    outcome = execute_cfg1_run(make_admission(), ports=ports)
    observations = outcome.observations
    assert observations["refused_at_step"] == "L1"
    assert observations["pi_identity_failure_code"] == PI_SEAM_UNPROVEN
    # L1 invoked its OWN leaves (the gate's observations cannot reach it).
    assert recorder.digests() and recorder.log[0][0] == "inspect"
    assert "gate" not in " ".join(run_executor.execute_cfg1_run.__code__.co_varnames)


# ---------------------------------------------------------------------------
# J -- resolution adversaries
# ---------------------------------------------------------------------------


def test_j_the_current_directory_is_never_consulted(tmp_path, monkeypatch):
    tree = make_pi_world(tmp_path, monkeypatch)
    planted = tmp_path / "cwd_plant"
    planted.mkdir()
    (planted / "node.exe").write_bytes(b"planted")
    (planted / "pi.cmd").write_bytes(b"planted")
    monkeypatch.chdir(planted)
    recorder = LeafRecorder()
    result = prove_pi_identity({"PATH": tree.npm_dir}, leaves=recorder.leaves())
    assert result.failure_code == PI_RESOLUTION_FAILED
    assert not any(str(planted) in path for _kind, path in recorder.log)


def test_j_cmd_shims_empty_and_relative_entries_are_never_selected(tmp_path, monkeypatch):
    tree = make_pi_world(tmp_path, monkeypatch)
    shim_dir = tmp_path / "shims"
    shim_dir.mkdir()
    (shim_dir / "node.cmd").write_bytes(b"@echo decoy")
    (shim_dir / "node.bat").write_bytes(b"@echo decoy")
    path_value = ";relative\\dir;C:relative;\\rooted-no-drive;" + str(shim_dir) + ";" + tree.path_value
    recorder = LeafRecorder()
    result = prove_pi_identity({"PATH": path_value}, leaves=recorder.leaves())
    assert result.failure_code is None
    assert result.identity.node_executable == tree.node_exe
    for _kind, path in recorder.log:
        assert os.path.isabs(path)
        assert not path.lower().endswith((".cmd\\node.exe", "node.cmd", "node.bat"))
        assert "relative" not in path and "rooted-no-drive" not in path


def test_j_a_later_valid_pi_root_is_never_searched_when_the_first_fails(tmp_path, monkeypatch):
    first = make_pi_world(tmp_path, monkeypatch, name="first")
    second = build_synthetic_pi_tree(str(tmp_path / "second"))
    Path(first.seam_path("dist/cli.js")).write_bytes(b"first root is broken")
    recorder = LeafRecorder()
    path_value = f"{first.node_dir};{first.npm_dir};{second.npm_dir}"
    result = prove_pi_identity({"PATH": path_value}, leaves=recorder.leaves())
    assert result.failure_code == PI_SEAM_UNPROVEN
    assert not any(str(second.base) in path for _kind, path in recorder.log)


def test_j_node_or_pi_root_inside_the_checkout_is_refused(tmp_path, monkeypatch):
    tree = make_pi_world(tmp_path, monkeypatch)
    leaves_root = LeafRecorder().leaves(checkout_root=str(tmp_path))
    assert prove_pi_identity({"PATH": tree.path_value}, leaves=leaves_root).failure_code == (
        PI_RESOLUTION_FAILED
    )
    # Only the Pi side inside the checkout: node is outside, root is inside.
    leaves_npm = LeafRecorder().leaves(checkout_root=tree.npm_dir)
    assert prove_pi_identity({"PATH": tree.path_value}, leaves=leaves_npm).failure_code == (
        PI_RESOLUTION_FAILED
    )
    # The genuine checkout is this repository; a synthetic tree is outside it.
    assert prove_pi_identity(
        {"PATH": tree.path_value}, leaves=genuine_pi_proof_leaves()
    ).failure_code is None


def _junction_or_skip(link: Path, target: Path) -> None:
    from conftest import make_directory_redirect

    try:
        make_directory_redirect(link, target)
    except OSError:
        pytest.skip("no directory redirect available on this platform")


def test_j_a_junction_path_entry_is_refused_before_realpath(tmp_path, monkeypatch):
    tree = make_pi_world(tmp_path, monkeypatch)
    link = tmp_path / "linked_nodejs"
    _junction_or_skip(link, Path(tree.node_dir))
    realpaths: list[str] = []
    real_realpath = os.path.realpath

    def _realpath(path, *a, **k):
        realpaths.append(str(path))
        return real_realpath(path, *a, **k)

    monkeypatch.setattr(os.path, "realpath", _realpath)
    result = prove_pi_identity(
        {"PATH": f"{link};{tree.npm_dir}"}, leaves=genuine_pi_proof_leaves()
    )
    assert result.failure_code == PI_RESOLUTION_FAILED
    assert not any(str(link) in path for path in realpaths)


def test_j_a_repo_local_lexical_junction_resolving_outside_is_still_refused(
    tmp_path, monkeypatch
):
    tree = make_pi_world(tmp_path, monkeypatch)
    checkout = tmp_path / "synthetic_checkout"
    checkout.mkdir()
    link = checkout / "tools_nodejs"
    _junction_or_skip(link, Path(tree.node_dir))
    leaves = LeafRecorder().leaves(checkout_root=str(checkout))
    result = prove_pi_identity({"PATH": f"{link};{tree.npm_dir}"}, leaves=leaves)
    assert result.failure_code == PI_RESOLUTION_FAILED
    # ...and a NON-reparse repo-local directory is refused on the lexical
    # form alone, even though nothing redirects.
    local = checkout / "plain_nodejs"
    local.mkdir()
    shutil.copy(tree.node_exe, local / "node.exe")
    result = prove_pi_identity({"PATH": f"{local};{tree.npm_dir}"}, leaves=leaves)
    assert result.failure_code == PI_RESOLUTION_FAILED


@pytest.mark.parametrize("shape", ["pi_cmd_directory", "pi_cmd_symlink", "node_symlink", "root_component_junction"])
def test_j_reparse_or_directory_candidates_refuse_outright(shape, tmp_path, monkeypatch):
    tree = make_pi_world(tmp_path, monkeypatch)
    if shape == "pi_cmd_directory":
        os.unlink(tree.pi_cmd)
        os.mkdir(tree.pi_cmd)
    elif shape in ("pi_cmd_symlink", "node_symlink"):
        from conftest import make_file_symlink

        target = tree.pi_cmd if shape == "pi_cmd_symlink" else tree.node_exe
        moved = target + ".real"
        os.rename(target, moved)
        try:
            make_file_symlink(Path(target), Path(moved))
        except (OSError, NotImplementedError):
            os.rename(moved, target)
            pytest.skip("file symlinks need a privilege this session lacks")
    else:
        modules = os.path.join(tree.npm_dir, "node_modules")
        real = str(tmp_path / "modules_real")
        shutil.move(modules, real)
        _junction_or_skip(Path(modules), Path(real))
    result = prove_pi_identity({"PATH": tree.path_value}, leaves=genuine_pi_proof_leaves())
    assert result.failure_code == PI_RESOLUTION_FAILED
    assert result.seam_digests_match is False


# ---------------------------------------------------------------------------
# U -- a swap between P1's capture and P2R, through BOTH the gate and L1
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("swap", ["node_exe", "package_root"])
@pytest.mark.parametrize("through", ["gate", "l1"])
def test_u_a_mid_proof_identity_swap_is_refused_by_p2r(
    swap, through, tmp_path, monkeypatch, git_executable
):
    tree = make_pi_world(tmp_path, monkeypatch)
    fired: list[int] = []

    def _hook(kind, path, log):
        if kind == "digest" and not fired:
            fired.append(1)
            if swap == "node_exe":
                replace_same_bytes(tree.node_exe)
            else:
                # Byte-identical copies of all 20 pinned files under a NEW
                # directory object at the same lexical path.
                replace_directory_with_identical_copy(tree.package_root)

    recorder = LeafRecorder(hook=_hook)
    if through == "gate":
        install_recording_genuine_leaves(monkeypatch, recorder)
        tripwire = ProcessTripwire(monkeypatch, delegate=False)
        code = pre_consumption_pi_identity_gate({"PATH": tree.path_value})
        assert code == PI_IDENTITY_DRIFTED_DURING_PROOF
        assert tripwire.count == 0
        return
    ports, _made = fu1_ports(git_executable, tree, leaves=recorder.leaves())
    tripwire = ProcessTripwire(monkeypatch, delegate=False)
    outcome = execute_cfg1_run(make_admission(), ports=ports)
    events = tripwire.count
    monkeypatch.undo()
    assert events == 0
    observations = outcome.observations
    assert observations["pi_identity_failure_code"] == PI_IDENTITY_DRIFTED_DURING_PROOF
    assert observations["pi_seam_digests_match"] is True
    assert observations["refused_at_step"] == "L1"
    _record(outcome)


# ---------------------------------------------------------------------------
# P / S / V / AD -- L14, the FIRST execution
# ---------------------------------------------------------------------------


class _LaunchRecordingSupervisor(FakeSupervisor):
    def __init__(self, log: list, **kwargs) -> None:
        super().__init__(**kwargs)
        self._log = log
        self.launch_calls = 0

    def launch(self) -> None:
        self.launch_calls += 1
        self._log.append(("launch", ""))
        super().launch()


def _l14_run(git_executable, tree, *, mutate=None, recorder=None):
    log: list = [] if recorder is None else recorder.log
    recorder = recorder or LeafRecorder(log=log)
    supervisor = _LaunchRecordingSupervisor(log)
    reads: list[str] = []

    def _build_supervisor(**_kwargs):
        # L14 step 1 (in-memory construction) runs BEFORE the re-proof, so a
        # mutation here is "after L1 passed, before L14's first execution".
        if mutate is not None:
            mutate()
        return supervisor

    def _read_connection():
        reads.append("read")
        return ("https://cfg1-doubles.invalid/v1", "cfg1-synthetic-key")

    ports, made = fu1_ports(
        git_executable,
        tree,
        leaves=recorder.leaves(),
        overrides={"build_supervisor": _build_supervisor, "read_connection": _read_connection},
    )
    outcome = execute_cfg1_run(make_admission(), ports=ports)
    return outcome, supervisor, log, reads


def test_p_the_l14_reproof_order_is_seams_then_root_then_node_then_launch(
    tmp_path, monkeypatch, git_executable
):
    tree = make_pi_world(tmp_path, monkeypatch)
    outcome, supervisor, log, _reads = _l14_run(git_executable, tree)
    assert outcome.observations["dispatch_state"] == "CONFIRMED_SENT"
    launch_at = log.index(("launch", ""))
    before = log[:launch_at]
    # Before launch(): all 20 seams (with their directory components inspected
    # no-follow), then the root, then node.exe -- and NOTHING between
    # node.exe's re-proof and launch().
    assert before[-1] == ("inspect", tree.node_exe)
    assert before[-2] == ("inspect", tree.package_root)
    digest_positions = [index for index, (kind, _) in enumerate(before) if kind == "digest"]
    l14_digests = [before[index][1] for index in digest_positions[-20:]]
    assert sorted(l14_digests) == sorted(tree.seam_path(key) for key in tree.pin_table)
    assert digest_positions[-1] < len(before) - 2
    for _kind, path in before[digest_positions[-20] : len(before) - 2]:
        assert path.startswith(tree.package_root)
    # The L14 walk is uncached: every seam was digested TWICE in the run
    # (L1's P2 and L14's (a)).
    assert sum(1 for kind, _ in before if kind == "digest") == 40
    assert supervisor.launch_calls == 1


@pytest.mark.parametrize(
    "mutation",
    ["cli_in_place", "cli_replaced", "other_seam_in_place", "node_same_bytes", "root_identical_copy"],
)
def test_s_v_and_p_a_change_after_l1_refuses_at_l14_with_no_launch(
    mutation, tmp_path, monkeypatch, git_executable
):
    tree = make_pi_world(tmp_path, monkeypatch)
    cli = tree.seam_path("dist/cli.js")

    def _mutate():
        if mutation == "cli_in_place":
            with open(cli, "r+b") as handle:  # same file record, changed bytes
                handle.write(b"X")
        elif mutation == "cli_replaced":
            os.unlink(cli)
            Path(cli).write_bytes(b"a new file in the same directory")
        elif mutation == "other_seam_in_place":
            with open(tree.seam_path("dist/core/model-runtime.js"), "r+b") as handle:
                handle.write(b"Y")
        elif mutation == "node_same_bytes":
            replace_same_bytes(tree.node_exe)
        else:
            replace_directory_with_identical_copy(tree.package_root)

    outcome, supervisor, log, reads = _l14_run(git_executable, tree, mutate=_mutate)
    observations = outcome.observations
    assert supervisor.launch_calls == 0
    assert observations["refused_at_step"] == "L14"
    assert observations["pre_dispatch_refusal_code"] == "RUNTIME_LAUNCH_FAILED"
    assert observations["runtime_created"] is False
    assert observations["pi_identity_failure_code"] is None
    assert observations["pi_seam_digests_match"] is True
    assert observations["dispatch_state"] == "NOT_ATTEMPTED"
    # Full closure of what exists: both sensitive files scrubbed by identity,
    # the broker closed, the workspace removed.
    assert observations["generated_config_scrub_verified"] is True
    assert observations["extension_binding_scrub_verified"] is True
    assert observations["broker_state_closed"] is True
    assert observations["workspace_removed_verified"] is True
    assert observations["lifecycle_all_closed"] is True
    assert reads == ["read"]
    record = _record(outcome)
    assert record["run_classification"] == "REFUSED_PRE_DISPATCH"


def test_ad_i_a_createprocess_failure_is_l14_with_no_runtime(
    tmp_path, monkeypatch, git_executable
):
    """The REAL supervisor hands the synthetic, non-image ``node.exe`` to
    ``CreateProcess`` -- which refuses it. Nothing executes."""
    tree = make_pi_world(tmp_path, monkeypatch)
    genuine = run_executor.default_cfg1_run_ports(ambient_environ={})
    reads: list[str] = []
    built: list = []

    def _build_supervisor(**kwargs):
        supervisor = genuine.build_supervisor(**kwargs)
        built.append(supervisor)
        return supervisor

    def _read_connection():
        reads.append("read")
        return ("https://cfg1-doubles.invalid/v1", "cfg1-synthetic-key")

    ports, _made = fu1_ports(
        git_executable,
        tree,
        overrides={"build_supervisor": _build_supervisor, "read_connection": _read_connection},
    )
    tripwire = ProcessTripwire(monkeypatch, delegate=True)
    outcome = execute_cfg1_run(make_admission(), ports=ports)
    events = list(tripwire.events)
    monkeypatch.undo()

    observations = outcome.observations
    assert observations["refused_at_step"] == "L14"
    assert observations["pre_dispatch_refusal_code"] == "RUNTIME_LAUNCH_FAILED"
    assert observations["runtime_created"] is False
    assert observations["route_reachable"] is True
    assert observations["broker_reached_ready"] is True
    assert observations["workspace_mint_state"] == "AUTHORITY_RETURNED"
    assert observations["generated_config_scrub_verified"] is True
    assert observations["extension_binding_scrub_verified"] is True
    assert observations["broker_state_closed"] is True
    assert observations["workspace_removed_verified"] is True
    assert observations["dispatch_state"] == "NOT_ATTEMPTED"
    assert observations["prompt_writes"] == 0
    assert reads == ["read"]
    assert built and built[0].process is None
    # AF (dynamic): exactly ONE creation attempt whose image is the resolved
    # node.exe -- at L14 -- and it was refused by the OS.
    node_attempts = [event for event in events if tree.node_exe.lower() in event[2].lower()]
    assert [event[1] for event in node_attempts].count("CreateProcess") == 1
    record = _record(outcome)
    assert record["run_classification"] == "REFUSED_PRE_DISPATCH"
    assert all("L1" not in code for code in outcome.console_codes)


def test_ad_i_and_iii_are_durably_identical_and_told_apart_only_by_calls(
    tmp_path, monkeypatch, git_executable
):
    tree = make_pi_world(tmp_path, monkeypatch)

    class _CreateProcessFails(FakeSupervisor):
        def launch(self):
            raise OSError("CreateProcess refused the image")

    ports_i, _ = fu1_ports(
        git_executable, tree, overrides={"build_supervisor": lambda **_k: _CreateProcessFails()}
    )
    outcome_i = execute_cfg1_run(make_admission(), ports=ports_i)
    outcome_iii, supervisor_iii, _log, _reads = _l14_run(
        git_executable, tree, mutate=lambda: replace_same_bytes(tree.node_exe)
    )
    assert supervisor_iii.launch_calls == 0
    assert _record(outcome_i) == _record(outcome_iii)


def test_ad_ii_a_created_process_that_never_answers_is_l15_with_a_runtime(
    tmp_path, monkeypatch, git_executable
):
    tree = make_pi_world(tmp_path, monkeypatch)
    supervisor = FakeSupervisor()
    ports, _made = fu1_ports(
        git_executable,
        tree,
        overrides={
            "build_supervisor": lambda **_k: supervisor,
            "evaluate_extension_identity": lambda **_k: (_ for _ in ()).throw(
                TimeoutError("no correlated get_commands")
            ),
        },
    )
    outcome = execute_cfg1_run(make_admission(), ports=ports)
    observations = outcome.observations
    assert observations["refused_at_step"] == "L15"
    assert observations["pre_dispatch_refusal_code"] == "RUNTIME_CORRELATION_FAILED"
    assert observations["runtime_created"] is True
    assert supervisor.shutdown_calls == 1  # L21 performed
    assert observations["runtime_exit_observed"] is True
    assert observations["dispatch_state"] == "NOT_ATTEMPTED"
    assert observations["lifecycle_all_closed"] is True
    _record(outcome)


# ---------------------------------------------------------------------------
# AF -- the probe mechanisms are unreachable
# ---------------------------------------------------------------------------


def _production_modules():
    return sorted(path for path in _PACKAGE_DIR.glob("*.py"))


def test_af_no_cfg1_module_imports_the_ar2_identity_probe_or_a_probe_environment():
    for path in _production_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "ar2.launch":
                names = {alias.name for alias in node.names}
                assert "resolve_runtime_identity" not in names, path.name
                assert names <= {"build_pi_argv"}, (path.name, names)
            if isinstance(node, ast.Attribute) and node.attr == "resolve_runtime_identity":
                raise AssertionError(f"{path.name} references resolve_runtime_identity")
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                lowered = node.name.lower()
                for retired in ("version_probe", "probe_environment", "identity_environment",
                                "probe_runner", "identity_child"):
                    assert retired not in lowered, (path.name, node.name)
            if isinstance(node, ast.Constant) and node.value == "--version":
                raise AssertionError(f"{path.name} builds a --version argv")
    assert "resolve_runtime_identity" not in run_executor.Cfg1RunPorts.__dataclass_fields__
    assert not hasattr(run_executor, "_bounded_version")


def test_af_a_full_doubled_run_creates_no_node_process_before_l14(
    tmp_path, monkeypatch, git_executable
):
    tree = make_pi_world(tmp_path, monkeypatch)
    tripwire = ProcessTripwire(monkeypatch, delegate=True)

    def _build_supervisor(**_kwargs):
        tripwire.phase = "L14"
        return FakeSupervisor()

    ports, _made = fu1_ports(git_executable, tree, overrides={"build_supervisor": _build_supervisor})
    outcome = execute_cfg1_run(make_admission(), ports=ports)
    events = list(tripwire.events)
    monkeypatch.undo()
    assert outcome.observations["dispatch_state"] == "CONFIRMED_SENT"
    for phase, _kind, command in events:
        assert tree.node_exe.lower() not in command.lower(), (phase, command)


# ---------------------------------------------------------------------------
# AG -- the frozen build_pi_argv over the CFG1 static identity object
# ---------------------------------------------------------------------------


class _RecordingIdentityShape:
    __slots__ = (
        "node_executable",
        "pi_cli_js",
        "pi_package_root",
        "node_identity",
        "package_root_identity",
        "_reads",
    )

    def __init__(self) -> None:
        object.__setattr__(self, "_reads", [])
        object.__setattr__(self, "node_executable", "C:\\syn\\node.exe")
        object.__setattr__(self, "pi_cli_js", "C:\\syn\\pi\\dist\\cli.js")
        object.__setattr__(self, "pi_package_root", "C:\\syn\\pi")
        object.__setattr__(self, "node_identity", (1, 2))
        object.__setattr__(self, "package_root_identity", (1, 3))

    def __getattribute__(self, name):
        if name != "_reads":
            object.__getattribute__(self, "_reads").append(name)
        return object.__getattribute__(self, name)


def test_ag_the_frozen_build_pi_argv_reads_exactly_two_attributes(tmp_path, monkeypatch):
    from ar2.launch import build_pi_argv

    shape = _RecordingIdentityShape()
    argv = build_pi_argv(
        shape,
        extension_entry="C:\\syn\\ext\\index.ts",
        tool_allowlist=("aido_read", "aido_edit"),
        provider="b300_pi_qualification",
        model="qwen3-coder-next",
    )
    assert argv[:2] == ("C:\\syn\\node.exe", "C:\\syn\\pi\\dist\\cli.js")
    reads = object.__getattribute__(shape, "_reads")
    # If the frozen function ever reads anything else, this fails and the
    # implementation must stop and return to design (AMEND1 Sec. 10).
    assert set(reads) == {"node_executable", "pi_cli_js"}, reads

    # ...and the GENUINE static identity object P produces works identically.
    tree = make_pi_world(tmp_path, monkeypatch)
    identity = prove_pi_identity({"PATH": tree.path_value}, leaves=genuine_pi_proof_leaves()).identity
    genuine_argv = build_pi_argv(
        identity,
        extension_entry="C:\\syn\\ext\\index.ts",
        tool_allowlist=("aido_read", "aido_edit"),
        provider="b300_pi_qualification",
        model="qwen3-coder-next",
    )
    assert genuine_argv[:2] == (tree.node_exe, identity.pi_cli_js)
    assert genuine_argv[2:] == argv[2:]


def test_ag_the_l14_reproof_rejects_anything_but_the_genuine_identity(tmp_path, monkeypatch):
    tree = make_pi_world(tmp_path, monkeypatch)
    leaves = genuine_pi_proof_leaves()
    identity = prove_pi_identity({"PATH": tree.path_value}, leaves=leaves).identity
    assert reprove_pi_identity_for_launch(identity, leaves=leaves) is True
    assert reprove_pi_identity_for_launch(_RecordingIdentityShape(), leaves=leaves) is False
    assert reprove_pi_identity_for_launch(identity, leaves=object()) is False
