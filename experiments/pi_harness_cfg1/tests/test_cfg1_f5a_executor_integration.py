"""F5-A executor integration (F5A-INT) -- OFFLINE regressions.

What these tests are, stated exactly. They drive the GENUINE
``execute_cfg1_run`` over the doubled ports: a SYNTHETIC on-disk Pi tree
approved by a SYNTHETIC sealed snapshot (a genuine PE-2b load), a REAL minted
``CFG1-T1`` workspace under the system temporary directory, and the GENUINE
provisioning adapter creating a real run-private copy with handle-relative
creates inside that workspace. The supervisor is a ``FakeSupervisor``: nothing
here launches Node or Pi, opens a socket, reads a credential or contacts a
model. The only test-local authority seam is the synthetic profile's LDT row
(``pe2c_support.install_synthetic_ldt_rows``).

What they are NOT. They are not Windows authority qualification and do not
touch A2-3: no reparse point is created, no directory is converted, and no
conversion races a create. Refusals reached through monkeypatched seams are
named in each test; they show the integration's own branches refuse and keep
truthful lifecycle evidence, not that a real native anomaly occurs.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import os
import sys
from pathlib import Path

import pytest
from cfg1_doubles import FakeSupervisor, build_synthetic_pi_tree
from cfg1_fu1_support import ProcessTripwire, fu1_ports, make_admission, make_pi_world
from pe2c_support import install_synthetic_policy

from pi_harness_cfg1 import lifecycle, pi_identity, records, run_executor, run_workspace, stage_runner
from pi_harness_cfg1 import pi_runtime_provision as rp
from pi_harness_cfg1.pi_identity import Cfg1PiIdentity, genuine_pi_proof_leaves, prove_pi_identity
from pi_harness_cfg1.records import _require_valid_cfg1_run_payload_v3, build_cfg1_run_payload
from pi_harness_cfg1.run_executor import default_cfg1_run_ports, execute_cfg1_run

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="Win32/NTFS semantics; a skip is not a pass"
)



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _capturing_port(captured: list):
    """The genuine offline adapter, recording what it returned."""

    def _port(*, workspace, source):
        provision = rp.admit_runtime_provision_for_source(workspace=workspace, source=source)
        captured.append(provision)
        return provision

    return _port


def _supervisor_recorder(seen: list):
    def _build(*, identity, extension, environment, workspace_root):
        seen.append(identity)
        return FakeSupervisor()

    return _build


def _run(git_executable, tree, *, overrides=None, admission=None):
    ports, made = fu1_ports(git_executable, tree, overrides=overrides)
    outcome = execute_cfg1_run(admission or make_admission(), ports=ports)
    return outcome, made


def _payload(observations) -> dict:
    payload = build_cfg1_run_payload(
        stage_id="S1", stage_execution_id="S1-X1", run_ordinal=1, observations=observations
    )
    _require_valid_cfg1_run_payload_v3(json.loads(json.dumps(payload)))
    return payload


def _assert_l3r_refusal(outcome, code="RUNTIME_PROVISIONING_FAILED", classification="REFUSED_PRE_DISPATCH"):
    observations = outcome.observations
    assert observations["refused_at_step"] == "L3R"
    assert observations["pre_dispatch_refusal_code"] == code
    assert observations["runtime_created"] is False
    assert observations["pi_profile_post_runtime_reobservation"] == "NOT_APPLICABLE"
    assert observations["route_reachable"] is False  # L7 never ran
    assert observations["broker_resource_created"] is False
    payload = _payload(observations)
    assert payload["run_classification"] == classification
    return payload


def _package_root(workspace) -> str:
    return workspace.experiment_root + "\\" + rp.RUNTIME_DIR_NAME + "\\" + rp.PACKAGE_DIR_NAME


def _remove_residue(workspace) -> None:
    """Test teardown only: the frozen no-follow remover over a root this test
    minted, for residue a deliberately leaked handle kept L27 from removing."""
    from ar2.fixtures import remove_disposable_tree

    if Path(workspace.experiment_root).exists():
        remove_disposable_tree(workspace.experiment_root)
    run_workspace.discard_cfg1_run_workspace(workspace)


def _all_ledger_states(provision) -> list[str]:
    return [
        entry.state
        for handles in (provision._construction, provision._final_pins)
        if handles is not None
        for entry in handles._entries
    ]


# ---------------------------------------------------------------------------
# 1. Authorized binding through L3R; S dropped; L bound to the provision
# ---------------------------------------------------------------------------


def test_l3r_binds_workspace_profile_and_inventory_and_launch_consumes_only_l(
    tmp_path, monkeypatch, git_executable
):
    tree = make_pi_world(tmp_path, monkeypatch)
    captured: list = []
    seen: list = []
    environment_nodes: list = []
    l21a_inputs: list = []
    from pi_harness_cfg1.environment import build_cfg1_child_environment

    def _environment(**kwargs):
        environment_nodes.append(kwargs["node_executable"])
        return build_cfg1_child_environment(**kwargs)

    real_reobserve = run_executor.reobserve_pi_profile_after_runtime

    def _reobserve(identity, **kwargs):
        l21a_inputs.append(identity)
        return real_reobserve(identity, **kwargs)

    monkeypatch.setattr(run_executor, "reobserve_pi_profile_after_runtime", _reobserve)
    outcome, made = _run(
        git_executable,
        tree,
        overrides={
            "provision_runtime": _capturing_port(captured),
            "build_supervisor": _supervisor_recorder(seen),
            "build_environment": _environment,
        },
    )
    observations = outcome.observations
    assert observations["refused_at_step"] is None, observations["pre_dispatch_refusal_code"]
    assert observations["runtime_created"] is True
    assert observations["pi_profile_post_runtime_reobservation"] == "PROVEN_UNCHANGED"
    assert observations["workspace_removed_verified"] is True
    assert outcome.live_references_released is True
    assert _payload(observations)["run_classification"] == "INACTIVE"

    (provision,) = captured
    workspace = made["workspace"]
    (launch,) = seen
    assert type(launch) is Cfg1PiIdentity
    assert launch is provision.launch_identity
    assert launch.pi_package_root == _package_root(workspace)
    assert launch.pi_cli_js == _package_root(workspace) + "\\dist\\cli.js"
    assert launch.matched_profile_id == tree.profile_id
    assert launch.node_executable == tree.node_exe
    # S (the ambient synthetic tree) is only a byte source: never a launch root.
    assert launch.pi_package_root != tree.package_root
    assert environment_nodes == [tree.node_exe]
    assert l21a_inputs == [launch]
    # Released exactly once at L27 entry; every handle proven closed.
    assert provision._released is True
    assert provision.final_pins_held == 0
    assert set(_all_ledger_states(provision)) == {rp.HANDLE_CLOSED}
    assert len(provision._final_pins._entries) == 4


def test_after_l3r_no_reference_to_s_remains_in_executor_state(tmp_path, monkeypatch, git_executable):
    tree = make_pi_world(tmp_path, monkeypatch)
    states: list = []
    real = run_executor._l3r_provision_runtime

    def _spy(admission, *, ports, state):
        source = state.pi_identity
        real(admission, ports=ports, state=state)
        states.append((source, state))

    monkeypatch.setattr(run_executor, "_l3r_provision_runtime", _spy)
    outcome, _made = _run(git_executable, tree)
    assert outcome.observations["refused_at_step"] is None
    ((source, state),) = states
    assert type(source) is Cfg1PiIdentity and source.pi_package_root == tree.package_root
    assert state.pi_identity is state.runtime_provision.launch_identity
    assert state.pi_identity is not source
    # No field of the executor's run state still refers to S.
    for field in dataclasses.fields(state):
        assert getattr(state, field.name) is not source, field.name


# ---------------------------------------------------------------------------
# 2. Cross-run / cross-profile / cross-source objects are never adopted
# ---------------------------------------------------------------------------


def test_a_provision_for_another_workspace_is_refused_and_never_adopted(
    tmp_path, monkeypatch, git_executable
):
    tree = make_pi_world(tmp_path, monkeypatch)
    foreign_workspace, _built = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
    foreign: list = []
    try:

        def _port(*, workspace, source):
            provision = rp.admit_runtime_provision_for_source(workspace=foreign_workspace, source=source)
            foreign.append(provision)
            return provision

        outcome, made = _run(git_executable, tree, overrides={"provision_runtime": _port})
        _assert_l3r_refusal(outcome)
        (provision,) = foreign
        # Never adopted: never run, never released by this run, nothing created.
        assert provision.state == rp.STATE_ADMITTED
        assert provision._released is False
        assert not Path(foreign_workspace.experiment_root, rp.RUNTIME_DIR_NAME).exists()
        assert outcome.live_references_released is True
        assert outcome.observations["workspace_removed_verified"] is True
    finally:
        run_workspace.remove_cfg1_run_workspace(foreign_workspace)


def test_a_provision_for_another_approved_profile_is_refused(tmp_path, monkeypatch, git_executable):
    tree = build_synthetic_pi_tree(str(tmp_path / "a"))
    files = dict(tree.files)
    files["dist/other.js"] = b"export const other = 99;\n"
    other = build_synthetic_pi_tree(str(tmp_path / "b"), files, tree.empty_dirs)
    install_synthetic_policy(monkeypatch, tree.payload, other.payload)
    proven = prove_pi_identity(
        {"PATH": other.path_value}, leaves=genuine_pi_proof_leaves()
    ).identity
    assert proven.matched_profile_id == other.profile_id

    def _port(*, workspace, source):
        return rp.admit_runtime_provision_for_source(workspace=workspace, source=proven)

    outcome, _made = _run(git_executable, tree, overrides={"provision_runtime": _port})
    _assert_l3r_refusal(outcome)


def test_a_provision_from_another_byte_source_of_the_same_profile_is_refused(
    tmp_path, monkeypatch, git_executable
):
    tree = make_pi_world(tmp_path, monkeypatch)
    twin = build_synthetic_pi_tree(str(tmp_path / "twin"), tree.files, tree.empty_dirs)
    assert twin.profile_id == tree.profile_id
    twin_identity = prove_pi_identity({"PATH": twin.path_value}, leaves=genuine_pi_proof_leaves()).identity

    def _port(*, workspace, source):
        return rp.admit_runtime_provision_for_source(workspace=workspace, source=twin_identity)

    outcome, _made = _run(git_executable, tree, overrides={"provision_runtime": _port})
    _assert_l3r_refusal(outcome)


@pytest.mark.parametrize("kind", ["none", "object", "string", "uninitialised", "already_run", "released"])
def test_malformed_or_contradictory_port_returns_are_refused_and_never_adopted(
    kind, tmp_path, monkeypatch, git_executable
):
    tree = make_pi_world(tmp_path, monkeypatch)
    extra_workspaces = []

    def _port(*, workspace, source):
        if kind == "none":
            return None
        if kind == "object":
            return object()
        if kind == "string":
            return workspace.experiment_root
        if kind == "uninitialised":
            return object.__new__(rp.RuntimeProvision)
        provision = rp.admit_runtime_provision_for_source(workspace=workspace, source=source)
        if kind == "released":
            rp.release_at_l27_entry(provision)
        if kind == "already_run":
            rp.run_runtime_provision(provision)
            extra_workspaces.append(provision)
        return provision

    outcome, made = _run(git_executable, tree, overrides={"provision_runtime": _port})
    # A port that ran its provision itself still holds that provision's final
    # pins; the executor never adopted it, so L27's removal is blocked and the
    # lifecycle is reported indeterminate -- truthfully, never repaired.
    _assert_l3r_refusal(
        outcome,
        classification="INDETERMINATE_LIFECYCLE" if kind == "already_run" else "REFUSED_PRE_DISPATCH",
    )
    # Never adopted, so not executor-owned: the release fact is vacuous.
    assert outcome.live_references_released is True
    for provision in extra_workspaces:
        # The port ran it itself; the executor never adopted it, so it never
        # released it either -- the test (standing in for that port) must.
        assert provision.final_pins_held == 4 and provision._released is False
        rp.release_at_l27_entry(provision)
        _remove_residue(made["workspace"])


def test_a_workspace_not_claimed_by_this_run_refuses_before_the_port(tmp_path, monkeypatch, git_executable):
    tree = make_pi_world(tmp_path, monkeypatch)
    calls: list = []

    def _claimed(workspace, *, run_id):
        # Only L3R's own check is falsified; L8's runs later and never here.
        return False

    monkeypatch.setattr(run_workspace, "workspace_is_claimed_by", _claimed)
    outcome, _made = _run(
        git_executable, tree, overrides={"provision_runtime": lambda **k: calls.append(k)}
    )
    _assert_l3r_refusal(outcome)
    assert calls == []


# ---------------------------------------------------------------------------
# 3. L3R refusal before any downstream authority; nothing minted on failure
# ---------------------------------------------------------------------------


def test_an_l3r_refusal_reaches_no_credential_route_capability_or_launch(
    tmp_path, monkeypatch, git_executable
):
    tree = make_pi_world(tmp_path, monkeypatch)
    touched: list = []

    def _refusing_port(*, workspace, source):
        raise rp.Cfg1RuntimeProvisionError("SOURCE_NOT_APPROVED_PAYLOAD")

    outcome, _made = _run(
        git_executable,
        tree,
        overrides={
            "provision_runtime": _refusing_port,
            "read_connection": lambda: touched.append("L4") or ("x", "y"),
            "mint_capability": lambda **k: touched.append("L8"),
            "build_supervisor": lambda **k: touched.append("L14"),
        },
    )
    _assert_l3r_refusal(outcome)
    assert touched == []
    assert outcome.live_references_released is True
    assert outcome.observations["workspace_removed_verified"] is True
    assert "F5A_LIVE_PROVISIONING_NOT_QUALIFIED" not in outcome.console_codes


def test_an_unexpected_raise_in_the_port_is_unexpected_step_failure_at_l3r(
    tmp_path, monkeypatch, git_executable
):
    tree = make_pi_world(tmp_path, monkeypatch)

    def _raising(*, workspace, source):
        raise RuntimeError("an injected port failure")

    outcome, _made = _run(git_executable, tree, overrides={"provision_runtime": _raising})
    _assert_l3r_refusal(outcome, code="UNEXPECTED_STEP_FAILURE")
    assert "RUN_STEP_RAISED_UNEXPECTEDLY" in outcome.console_codes


def test_a_provisioning_failure_mints_no_launch_identity(tmp_path, monkeypatch, git_executable):
    """The source drifts after L1 (an extra file): the run's own source walk no
    longer equals the profile, so L3R refuses with nothing written and no L."""
    tree = make_pi_world(tmp_path, monkeypatch)
    captured: list = []

    def _port(*, workspace, source):
        provision = _capturing_port(captured)(workspace=workspace, source=source)
        Path(tree.package_root, "dist", "planted.js").write_bytes(b"planted\n")
        return provision

    seen: list = []
    outcome, made = _run(
        git_executable,
        tree,
        overrides={"provision_runtime": _port, "build_supervisor": _supervisor_recorder(seen)},
    )
    _assert_l3r_refusal(outcome)
    (provision,) = captured
    assert provision.state == rp.STATE_REFUSED
    assert provision.refusal_reason == "SOURCE_NOT_APPROVED_PAYLOAD"
    assert provision.launch_identity is None
    assert seen == []
    assert outcome.live_references_released is True


@pytest.mark.parametrize("injected", ["bind_returns_none", "bind_raises"])
def test_a_copy_validation_failure_after_the_final_pins_mints_no_l_and_releases_them(
    injected, tmp_path, monkeypatch, git_executable
):
    """Injected seam: the executor's independent re-observation of the copy
    (``bind_run_provisioned_launch_identity``) fails AFTER the four final pins
    are held. No L is recorded, and L27 entry still releases every pin."""
    tree = make_pi_world(tmp_path, monkeypatch)
    captured: list = []

    def _bind(*args, **kwargs):
        assert captured[0].final_pins_held == 4
        if injected == "bind_raises":
            raise RuntimeError("an injected bind failure")
        return None

    monkeypatch.setattr(run_executor, "bind_run_provisioned_launch_identity", _bind)
    outcome, _made = _run(git_executable, tree, overrides={"provision_runtime": _capturing_port(captured)})
    _assert_l3r_refusal(
        outcome, code="RUNTIME_PROVISIONING_FAILED" if injected == "bind_returns_none" else "UNEXPECTED_STEP_FAILURE"
    )
    (provision,) = captured
    assert provision.state == rp.STATE_PROVEN
    assert provision.launch_identity is None
    assert provision._released is True and provision.final_pins_held == 0
    assert outcome.live_references_released is True
    assert outcome.observations["workspace_removed_verified"] is True


def test_an_exposure_present_above_the_copy_is_refused_by_the_launch_identity_binder(
    tmp_path, monkeypatch, git_executable
):
    """Injected seam (post-pin item 2): the binder's exposure observation over
    ``C`` reports a present exposure; no L is minted."""
    tree = make_pi_world(tmp_path, monkeypatch)
    captured: list = []
    real = pi_identity.observe_profile_exposures

    def _observe(payload_root, exposures, *, inspect):
        if payload_root.endswith("\\" + rp.RUNTIME_DIR_NAME + "\\" + rp.PACKAGE_DIR_NAME):
            return pi_identity.EXPOSURE_PRESENT
        return real(payload_root, exposures, inspect=inspect)

    monkeypatch.setattr(pi_identity, "observe_profile_exposures", _observe)
    outcome, _made = _run(git_executable, tree, overrides={"provision_runtime": _capturing_port(captured)})
    _assert_l3r_refusal(outcome)
    assert captured[0].launch_identity is None


# ---------------------------------------------------------------------------
# 4. The launch-identity binder (pi_identity) -- read-only, independent
# ---------------------------------------------------------------------------


def _proven_source(tree):
    return prove_pi_identity({"PATH": tree.path_value}, leaves=genuine_pi_proof_leaves()).identity


def test_the_binder_refuses_malformed_or_unproven_copies(tmp_path, monkeypatch):
    tree = make_pi_world(tmp_path, monkeypatch)
    source = _proven_source(tree)
    copy_root = tmp_path / "copy" / "pi-coding-agent"
    copy_root.parent.mkdir()
    import shutil

    shutil.copytree(tree.package_root, copy_root)
    stat = os.stat(copy_root)
    identity = (stat.st_dev, stat.st_ino)
    leaves = genuine_pi_proof_leaves()
    bind = pi_identity.bind_run_provisioned_launch_identity

    good = bind(source, package_root=str(copy_root), package_root_identity=identity, leaves=leaves)
    assert type(good) is Cfg1PiIdentity and good.pi_package_root == str(copy_root)
    assert good.node_identity == source.node_identity and good.matched_profile_id == source.matched_profile_id

    assert bind(object(), package_root=str(copy_root), package_root_identity=identity, leaves=leaves) is None
    assert bind(source, package_root="relative\\x", package_root_identity=identity, leaves=leaves) is None
    assert bind(source, package_root=str(copy_root), package_root_identity=(1,), leaves=leaves) is None
    assert bind(source, package_root=str(copy_root), package_root_identity=(identity[0], identity[1] + 1), leaves=leaves) is None
    assert bind(source, package_root=source.pi_package_root, package_root_identity=source.package_root_identity, leaves=leaves) is None
    (copy_root / "dist" / "other.js").write_bytes(b"changed\n")
    assert bind(source, package_root=str(copy_root), package_root_identity=identity, leaves=leaves) is None


def test_the_binder_imports_no_writer_and_performs_no_write():
    tree = ast.parse(Path(pi_identity.__file__).read_text(encoding="utf-8"))
    imported = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    for module in ("pi_runtime_provision", "run_workspace", "win_config_authority", "config_issuance",
                   "extension_issuance", "writers", "subprocess", "shutil"):
        assert not any(name and module in name for name in imported), (module, imported)
    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "bind_run_provisioned_launch_identity"
    )
    called = {
        (call.func.attr if isinstance(call.func, ast.Attribute) else getattr(call.func, "id", ""))
        for call in ast.walk(function)
        if isinstance(call, ast.Call)
    }
    assert not called & {"open", "write_bytes", "write_text", "mkdir", "unlink", "rename", "CreateFileW"}
    # Exactly two Cfg1PiIdentity construction sites: P, and this binder.
    constructors = [
        holder.name
        for holder in tree.body
        if isinstance(holder, ast.FunctionDef)
        for call in ast.walk(holder)
        if isinstance(call, ast.Call) and getattr(call.func, "id", "") == "Cfg1PiIdentity"
    ]
    assert sorted(constructors) == ["bind_run_provisioned_launch_identity", "prove_pi_identity"]


# ---------------------------------------------------------------------------
# 5. L14 precondition
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mutation", ["rt_gains_a_child", "run_root_node_modules", "identity_swapped", "pin_closed"])
def test_the_l14_precondition_refuses_with_no_supervisor_and_no_launch(
    mutation, tmp_path, monkeypatch, git_executable
):
    tree = make_pi_world(tmp_path, monkeypatch)
    captured: list = []
    built: list = []
    from pi_harness_cfg1.environment import build_cfg1_child_environment

    def _environment(**kwargs):
        provision = captured[0]
        workspace = kwargs["workspace"]
        if mutation == "rt_gains_a_child":
            Path(workspace.experiment_root, rp.RUNTIME_DIR_NAME, "agent").mkdir()
        elif mutation == "run_root_node_modules":
            Path(workspace.experiment_root, "node_modules").mkdir()
        elif mutation == "identity_swapped":
            other = pi_identity.bind_run_provisioned_launch_identity(
                _proven_source(tree),
                package_root=provision.package_root,
                package_root_identity=provision.package_root_identity,
                leaves=genuine_pi_proof_leaves(),
            )
            assert other is not None and other is not provision.launch_identity
            object.__setattr__(provision, "_launch_identity", other)
        elif mutation == "pin_closed":
            pins = provision._final_pins
            pins.close(pins._entries[1])
        return build_cfg1_child_environment(**kwargs)

    outcome, _made = _run(
        git_executable,
        tree,
        overrides={
            "provision_runtime": _capturing_port(captured),
            "build_environment": _environment,
            "build_supervisor": lambda **k: built.append(k) or FakeSupervisor(),
        },
    )
    observations = outcome.observations
    assert observations["refused_at_step"] == "L14"
    assert observations["pre_dispatch_refusal_code"] == "RUNTIME_LAUNCH_FAILED"
    assert observations["runtime_created"] is False
    assert built == []
    assert captured[0]._released is True
    assert outcome.live_references_released is True
    _payload(observations)


def test_the_l14_precondition_unit_rules(tmp_path, monkeypatch, git_executable):
    tree = make_pi_world(tmp_path, monkeypatch)
    source = _proven_source(tree)
    workspace, _built = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
    other_workspace, _b = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
    provision = rp.admit_runtime_provision_for_source(workspace=workspace, source=source)
    try:
        # Not yet run / not bound: refused.
        assert rp.reprove_provision_for_launch(provision, workspace=workspace, launch=None) is False
        rp.run_runtime_provision(provision)
        assert rp.reprove_provision_for_launch(provision, workspace=workspace, launch=None) is False
        launch = pi_identity.bind_run_provisioned_launch_identity(
            source,
            package_root=provision.package_root,
            package_root_identity=provision.package_root_identity,
            leaves=genuine_pi_proof_leaves(),
        )
        # A launch identity naming another root is never recorded.
        with pytest.raises(rp.Cfg1RuntimeProvisionError):
            rp.record_launch_identity(provision, source)
        rp.record_launch_identity(provision, launch)
        with pytest.raises(rp.Cfg1RuntimeProvisionError):
            rp.record_launch_identity(provision, launch)  # exactly once
        assert rp.reprove_provision_for_launch(provision, workspace=workspace, launch=launch) is True
        assert rp.reprove_provision_for_launch(provision, workspace=other_workspace, launch=launch) is False
        assert rp.reprove_provision_for_launch(provision, workspace=workspace, launch=source) is False
        assert rp.reprove_provision_for_launch(object(), workspace=workspace, launch=launch) is False
        row = rp.LAUNCH_DERIVATION_TABLE.pop(tree.profile_id)
        try:
            assert rp.reprove_provision_for_launch(provision, workspace=workspace, launch=launch) is False
        finally:
            rp.LAUNCH_DERIVATION_TABLE[tree.profile_id] = row
        assert rp.reprove_provision_for_launch(provision, workspace=workspace, launch=launch) is True
    finally:
        rp.release_at_l27_entry(provision)
        assert rp.provision_live_references_proven_released(provision) is True
        assert rp.reprove_provision_for_launch(provision, workspace=workspace, launch=None) is False
        run_workspace.remove_cfg1_run_workspace(workspace)
        run_workspace.remove_cfg1_run_workspace(other_workspace)


# ---------------------------------------------------------------------------
# 6. The offline/live barrier
# ---------------------------------------------------------------------------


def test_the_default_binding_refuses_provisioning_before_any_io(filesystem_spy):
    ports = default_cfg1_run_ports(ambient_environ={"PATH": ""})
    assert ports.provision_runtime is rp.live_runtime_provisioning_not_qualified
    before = (filesystem_spy.total_mutations, len(filesystem_spy.lstat_calls))
    with pytest.raises(rp.Cfg1RuntimeProvisionError) as refused:
        ports.provision_runtime(workspace=None, source=None)
    assert refused.value.reason_code == rp.LIVE_PROVISIONING_NOT_QUALIFIED
    assert (filesystem_spy.total_mutations, len(filesystem_spy.lstat_calls)) == before


def test_the_genuine_executor_binding_halts_at_l3r_before_credentials_or_any_process(
    tmp_path, monkeypatch, git_executable
):
    """The default ports, with only offline-safe members replaced (Git
    resolution, the synthetic Pi tree's PATH, the L3 verification and
    repository observation). ``provision_runtime`` stays the DEFAULT."""
    from cfg1_doubles import FakeRepositorySnapshot, FakeVerificationOutcome

    tree = make_pi_world(tmp_path, monkeypatch)
    touched: list = []
    defaults = default_cfg1_run_ports(ambient_environ={"SystemRoot": "C:\\Windows", "PATH": tree.path_value})
    ports = dataclasses.replace(
        defaults,
        git_executable=lambda: git_executable,
        run_verification=lambda *, workspace_root, args: FakeVerificationOutcome(),
        observe_repository=lambda *, workspace_root: FakeRepositorySnapshot(),
        read_connection=lambda: touched.append("L4") or ("x", "y"),
    )
    tripwire = ProcessTripwire(monkeypatch, delegate=True)
    outcome = execute_cfg1_run(make_admission(), ports=ports)
    _assert_l3r_refusal(outcome)
    assert "F5A_LIVE_PROVISIONING_NOT_QUALIFIED" in outcome.console_codes
    assert touched == []
    # Only the frozen L2 fixture's own Git children may exist; never Node/Pi.
    assert all("node" not in event[2].lower() for event in tripwire.events)
    assert outcome.live_references_released is True


def _pi_supervisor_tripwire(monkeypatch) -> list:
    import ar2.supervisor

    constructed: list = []

    class _Tripwire:
        def __init__(self, *args, **kwargs):
            constructed.append(kwargs)
            raise AssertionError("a real PiRpcSupervisor must never be constructed here")

    monkeypatch.setattr(ar2.supervisor, "PiRpcSupervisor", _Tripwire)
    return constructed


def test_the_genuine_supervisor_builder_refuses_every_genuine_cfg1_identity(tmp_path, monkeypatch):
    tree = make_pi_world(tmp_path, monkeypatch)
    constructed = _pi_supervisor_tripwire(monkeypatch)
    ports = default_cfg1_run_ports(ambient_environ={"PATH": tree.path_value})
    with pytest.raises(RuntimeError):
        ports.build_supervisor(
            identity=_proven_source(tree), extension=object(), environment=object(), workspace_root="C:\\x"
        )
    assert constructed == []


def test_composing_the_offline_provisioner_with_the_genuine_builder_never_launches(
    tmp_path, monkeypatch, git_executable
):
    """A supported caller composing the genuine offline provisioner with the
    GENUINE supervisor builder reaches L14 and is refused there: no real
    supervisor is constructed, ``launch()`` is never called, no process."""
    tree = make_pi_world(tmp_path, monkeypatch)
    constructed = _pi_supervisor_tripwire(monkeypatch)
    genuine_builder = default_cfg1_run_ports(ambient_environ={"PATH": tree.path_value}).build_supervisor
    tripwire = ProcessTripwire(monkeypatch, delegate=True)
    outcome, _made = _run(git_executable, tree, overrides={"build_supervisor": genuine_builder})
    observations = outcome.observations
    assert observations["refused_at_step"] == "L14"
    assert observations["pre_dispatch_refusal_code"] == "RUNTIME_LAUNCH_FAILED"
    assert observations["runtime_created"] is False
    assert constructed == []
    assert all("node" not in event[2].lower() for event in tripwire.events)
    assert outcome.live_references_released is True


def test_static_audit_of_the_barrier():
    """AST facts: the default binding names the refusing port; that port is an
    unconditional refusal; the genuine builder refuses a genuine identity
    before anything else; ``PiRpcSupervisor`` and ``build_pi_argv`` are used
    only inside it; ``launch()`` is called once, after the L14 precondition;
    and no environment value is read by the provisioner."""
    executor_source = Path(run_executor.__file__).read_text(encoding="utf-8")
    tree = ast.parse(executor_source)
    defaults = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "default_cfg1_run_ports")
    keywords = {
        kw.arg: kw.value
        for call in ast.walk(defaults)
        if isinstance(call, ast.Call) and getattr(call.func, "id", "") == "Cfg1RunPorts"
        for kw in call.keywords
    }
    bound = keywords["provision_runtime"]
    assert isinstance(bound, ast.Attribute) and bound.attr == "live_runtime_provisioning_not_qualified"
    builder = next(n for n in ast.walk(defaults) if isinstance(n, ast.FunctionDef) and n.name == "_build_supervisor")
    first = builder.body[0]
    assert isinstance(first, ast.If) and isinstance(first.body[0], ast.Raise)
    assert "Cfg1PiIdentity" in ast.unparse(first.test)
    users = {
        holder.name
        for holder in ast.walk(tree)
        if isinstance(holder, ast.FunctionDef)
        for node in ast.walk(holder)
        if isinstance(node, ast.Name) and node.id in ("PiRpcSupervisor", "build_pi_argv")
    }
    assert users <= {"default_cfg1_run_ports", "_build_supervisor"}
    launches = [
        call for call in ast.walk(tree)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr == "launch"
    ]
    assert len(launches) == 1
    dispatch = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_dispatch_phase")
    dispatch_source = ast.unparse(dispatch)
    assert dispatch_source.index("_l14_runtime_provision_precondition") < dispatch_source.index(".launch()")
    assert dispatch_source.index("_l3r_provision_runtime") < dispatch_source.index("read_connection")

    provisioner = ast.parse(Path(rp.__file__).read_text(encoding="utf-8"))
    refusing = next(
        n for n in provisioner.body
        if isinstance(n, ast.FunctionDef) and n.name == "live_runtime_provisioning_not_qualified"
    )
    body = [statement for statement in refusing.body if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Constant)]
    assert len(body) == 1 and ast.unparse(body[0]) == "_refuse(LIVE_PROVISIONING_NOT_QUALIFIED)"
    names = {node.id for node in ast.walk(provisioner) if isinstance(node, ast.Name)} | {
        node.attr for node in ast.walk(provisioner) if isinstance(node, ast.Attribute)
    }
    assert not names & {"environ", "getenv", "putenv"}


# ---------------------------------------------------------------------------
# 7. Final-pin release across exits; 8. close failure is lifecycle-significant
# ---------------------------------------------------------------------------


def test_final_pins_are_released_after_a_later_pre_dispatch_refusal(tmp_path, monkeypatch, git_executable):
    from cfg1_doubles import FakeRouteObservation

    tree = make_pi_world(tmp_path, monkeypatch)
    captured: list = []
    outcome, _made = _run(
        git_executable,
        tree,
        overrides={
            "provision_runtime": _capturing_port(captured),
            "observe_route": lambda **k: FakeRouteObservation(reachable=False),
        },
    )
    assert outcome.observations["refused_at_step"] == "L7"
    assert captured[0]._released is True and captured[0].final_pins_held == 0
    assert outcome.live_references_released is True
    assert outcome.observations["workspace_removed_verified"] is True


def test_an_unexpected_failure_inside_the_provision_latches_unproven_release(
    tmp_path, monkeypatch, git_executable
):
    """Injected seam: post-pin validation raises a non-refusal AFTER the final
    pins are held. The pins are still released at L27 entry, but an unexpected
    interruption can never prove that no handle went untracked (candidate
    Sec. 4 F-3), so the derived fact is ``False`` and L30 would halt."""
    tree = make_pi_world(tmp_path, monkeypatch)
    captured: list = []

    def _boom(provision, held):
        raise RuntimeError("an injected unexpected failure")

    monkeypatch.setattr(rp, "_post_pin_validation", _boom)
    outcome, _made = _run(git_executable, tree, overrides={"provision_runtime": _capturing_port(captured)})
    _assert_l3r_refusal(outcome, code="UNEXPECTED_STEP_FAILURE")
    (provision,) = captured
    assert provision.state == rp.STATE_FAILED_UNEXPECTED
    assert provision._released is True and provision.final_pins_held == 0
    assert outcome.live_references_released is False
    assert stage_runner._run_scoped_registries_empty(outcome) is False


def _fail_closes(monkeypatch, *, kind: str, genuine: bool) -> list:
    """Make every close of ``kind`` report failure. ``genuine=False`` closes the
    handle for real first (only the REPORT fails); ``genuine=True`` leaves it
    open, recorded in the returned list for the test to close afterwards."""
    leaked: list = []
    real_close = rp._close_raw_handle
    real_ledger_close = rp._HandleLedger.close

    def _close(self, entry):
        if entry.kind != kind or entry.state != rp.HANDLE_OPEN:
            return real_ledger_close(self, entry)
        if genuine:
            leaked.append(entry.raw)
        else:
            real_close(entry.raw)
        entry.state = rp.HANDLE_CLOSE_FAILED
        self._open -= 1
        return False

    monkeypatch.setattr(rp._HandleLedger, "close", _close)
    return leaked


@pytest.mark.parametrize("genuine", [False, True])
def test_a_final_pin_close_failure_latches_false_whatever_l27_removal_does(
    genuine, tmp_path, monkeypatch, git_executable
):
    tree = make_pi_world(tmp_path, monkeypatch)
    captured: list = []
    leaked = _fail_closes(monkeypatch, kind=rp._KIND_FINAL_PIN, genuine=genuine)
    outcome, made = _run(git_executable, tree, overrides={"provision_runtime": _capturing_port(captured)})
    try:
        observations = outcome.observations
        assert observations["refused_at_step"] is None
        assert outcome.live_references_released is False
        assert rp.HANDLE_CLOSE_FAILED in _all_ledger_states(captured[0])
        if genuine:
            # The leaked pins keep L27's removal from completing: lifecycle degraded.
            assert observations["workspace_removed_verified"] is False
            assert "L27" in observations["lifecycle_failure_steps"]
            assert _payload(observations)["run_classification"] == "INDETERMINATE_LIFECYCLE"
        else:
            # Removal succeeded; the latch is NOT repaired by it.
            assert observations["workspace_removed_verified"] is True
            assert run_workspace.minted_workspace_count() == 0
            assert stage_runner._run_scoped_registries_empty(outcome) is False
    finally:
        for raw in leaked:
            rp._close_raw_handle(raw)
        if genuine:
            _remove_residue(made["workspace"])


def test_a_construction_close_failure_refuses_l3r_and_latches_false(tmp_path, monkeypatch, git_executable):
    tree = make_pi_world(tmp_path, monkeypatch)
    captured: list = []
    _fail_closes(monkeypatch, kind=rp._KIND_FILE, genuine=False)
    outcome, _made = _run(git_executable, tree, overrides={"provision_runtime": _capturing_port(captured)})
    _assert_l3r_refusal(outcome)
    assert captured[0].refusal_reason == "CONSTRUCTION_HANDLE_NOT_CLOSED"
    assert outcome.live_references_released is False


def test_the_derived_fact_ignores_dropped_references_and_registries(tmp_path, monkeypatch, git_executable):
    """A CLOSE_FAILED entry stays unproven however the Python object is
    treated: the ledger entry, not the object, decides."""
    tree = make_pi_world(tmp_path, monkeypatch)
    captured: list = []
    _fail_closes(monkeypatch, kind=rp._KIND_FINAL_PIN, genuine=False)
    outcome, _made = _run(git_executable, tree, overrides={"provision_runtime": _capturing_port(captured)})
    provision = captured.pop()
    assert outcome.live_references_released is False
    assert rp.provision_live_references_proven_released(provision) is False
    with pytest.raises(rp.Cfg1RuntimeProvisionError):
        rp.release_at_l27_entry(provision)  # exactly once; never retried
    assert rp.provision_live_references_proven_released(provision) is False


def test_the_derived_fact_is_vacuously_true_when_provisioning_was_never_attempted(
    tmp_path, monkeypatch, git_executable
):
    tree = make_pi_world(tmp_path, monkeypatch)
    calls: list = []
    outcome, _made = _run(
        git_executable,
        tree,
        overrides={
            "run_verification": lambda **k: (_ for _ in ()).throw(RuntimeError("L3 refuses")),
            "provision_runtime": lambda **k: calls.append(k),
        },
    )
    assert outcome.observations["refused_at_step"] == "L3"
    assert calls == []
    assert outcome.live_references_released is True


def test_the_executor_no_longer_returns_a_constant_release_fact():
    tree = ast.parse(Path(run_executor.__file__).read_text(encoding="utf-8"))
    for call in ast.walk(tree):
        if isinstance(call, ast.Call) and getattr(call.func, "id", "") == "Cfg1RunOutcome":
            value = next(kw.value for kw in call.keywords if kw.arg == "live_references_released")
            assert not isinstance(value, ast.Constant)


# ---------------------------------------------------------------------------
# 9. Versioned records: v3-only extension, v1/v2 unchanged
# ---------------------------------------------------------------------------


def test_v1_v2_vocabulary_objects_are_unchanged_and_v3_extends_them_only():
    assert lifecycle.REFUSAL_STEPS == frozenset(f"L{i}" for i in range(1, 19))
    assert "L3R" not in lifecycle.REFUSAL_STEPS
    assert lifecycle.REFUSAL_STEPS_V3 == lifecycle.REFUSAL_STEPS | {"L3R"}
    assert records.REFUSAL_STEPS is lifecycle.REFUSAL_STEPS
    assert "RUNTIME_PROVISIONING_FAILED" not in records.PRE_DISPATCH_REFUSAL_CODES
    assert "RUNTIME_PROVISIONING_FAILED" not in records.PRE_DISPATCH_REFUSAL_CODES_V2
    assert "L3R" not in records.REFUSAL_CODES_BY_STEP
    assert records.PRE_DISPATCH_REFUSAL_CODES_V3 == records.PRE_DISPATCH_REFUSAL_CODES_V2 | {
        "RUNTIME_PROVISIONING_FAILED"
    }
    assert records.REFUSAL_CODES_BY_STEP_V3["L3R"] == {"RUNTIME_PROVISIONING_FAILED", "UNEXPECTED_STEP_FAILURE"}
    for step, codes in records.REFUSAL_CODES_BY_STEP.items():
        assert records.REFUSAL_CODES_BY_STEP_V3[step] is codes
    # Only the v3 run validator reads the v3 objects.
    source = Path(records.__file__).read_text(encoding="utf-8")
    module = ast.parse(source)
    readers = {
        holder.name
        for holder in module.body
        if isinstance(holder, ast.FunctionDef)
        for node in ast.walk(holder)
        if isinstance(node, ast.Name)
        and node.id in ("REFUSAL_STEPS_V3", "PRE_DISPATCH_REFUSAL_CODES_V3", "REFUSAL_CODES_BY_STEP_V3")
    }
    assert readers == {"_require_valid_cfg1_run_payload_v3"}


def test_r3_s15_accepts_the_l3r_domain_and_refuses_everything_else(tmp_path, monkeypatch, git_executable):
    tree = make_pi_world(tmp_path, monkeypatch)

    def _refusing(**_k):
        raise rp.Cfg1RuntimeProvisionError("SOURCE_NOT_APPROVED_PAYLOAD")

    outcome, _made = _run(git_executable, tree, overrides={"provision_runtime": _refusing})
    payload = _assert_l3r_refusal(outcome)

    def _check(**changes):
        candidate = json.loads(json.dumps(payload))
        candidate.update(changes)
        _require_valid_cfg1_run_payload_v3(candidate)

    _check(pre_dispatch_refusal_code="UNEXPECTED_STEP_FAILURE")
    for code in ("WORKSPACE_BASELINE_FAILED", "RUNTIME_LAUNCH_FAILED", "CREDENTIAL_BOUNDARY_FAILED"):
        with pytest.raises(records.Cfg1RecordValidationError):
            _check(pre_dispatch_refusal_code=code)
    with pytest.raises(records.Cfg1RecordValidationError):
        _check(refused_at_step="L4")  # RUNTIME_PROVISIONING_FAILED outside L3R
    with pytest.raises(records.Cfg1RecordValidationError):
        _check(refused_at_step="L3r")
    # R3-S15's RC half, isolated: the rule itself refuses RC true at L3R.
    with pytest.raises(records.Cfg1RecordValidationError) as refused:
        _check(runtime_created=True, pi_profile_post_runtime_reobservation="UNPROVEN")
    assert refused.value.reason_code in ("L3R_REFUSAL_OUTSIDE_R3_S15",)


@pytest.mark.parametrize(
    ("code", "step"), [("RUNTIME_PROVISIONING_FAILED", "L3R"), ("UNEXPECTED_STEP_FAILURE", "L3R"),
                       ("RUNTIME_PROVISIONING_FAILED", "L3")]
)
def test_the_v2_validator_refuses_the_l3r_vocabulary(code, step):
    from cfg1_builders import happy_observations_v2, pre_dispatch_refusal_overrides, v2_run_payload

    payload = v2_run_payload(observations=happy_observations_v2(**pre_dispatch_refusal_overrides(code, step)))
    with pytest.raises(records.Cfg1RecordValidationError) as refused:
        records._require_valid_cfg1_run_payload_v2(json.loads(json.dumps(payload)))
    assert refused.value.category == records.FINDING_SCHEMA_VIOLATION


# ---------------------------------------------------------------------------
# 10. Evidence under partial failure carries no path, byte or raw text
# ---------------------------------------------------------------------------


def test_refusal_evidence_carries_no_path_and_no_foreign_bytes(tmp_path, monkeypatch, git_executable):
    """The source is redirected to foreign bytes carrying a SECRET marker after
    the run's own source observation (injected through the copy-read leaf).
    Nothing of it reaches the run root, the observations or the console."""
    from pi_harness_cfg1 import pi_fs_leaves

    tree = make_pi_world(tmp_path, monkeypatch)
    secret = b"SECRET-f5a-int-7c1e"
    real_read = pi_fs_leaves.read_payload_file_bytes

    def _read(path, size):
        if path.endswith("\\dist\\other.js"):
            Path(path).write_bytes(secret + b"x" * 8)
        return real_read(path, size)

    monkeypatch.setattr(pi_fs_leaves, "read_payload_file_bytes", _read)
    captured: list = []
    roots: list = []

    def _port(*, workspace, source):
        roots.append(workspace.experiment_root)
        return _capturing_port(captured)(workspace=workspace, source=source)

    persisted: list = []
    real_release = run_executor._closure_l27_release_runtime_provision

    def _scan_then_release(state):
        root = Path(roots[0])
        persisted.extend(
            str(path) for path in root.rglob("*") if path.is_file() and secret in path.read_bytes()
        )
        return real_release(state)

    monkeypatch.setattr(run_executor, "_closure_l27_release_runtime_provision", _scan_then_release)
    outcome, _made = _run(git_executable, tree, overrides={"provision_runtime": _port})
    _assert_l3r_refusal(outcome)
    assert captured[0].refusal_reason == "SOURCE_BYTES_NOT_APPROVED"
    assert persisted == []
    assert Path(roots[0], rp.RUNTIME_DIR_NAME).exists() is False  # removed by L27 with R
    rendered = json.dumps(outcome.observations) + json.dumps(list(outcome.console_codes))
    for needle in (roots[0], tree.package_root, secret.decode()):
        assert needle not in rendered
    assert outcome.observations["workspace_removed_verified"] is True
