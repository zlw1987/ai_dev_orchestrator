"""PE-2c: the profile-aware canonical proof P, the gate, the shape check, L14.

PE-1 (``PHASE_5F3B_PI_HARNESS_PROFILE_EVOLUTION_PE1_AMENDMENT.md``) Sec. 26.3
rows C-1, C-2, C-3, C-5, C-12 and C-14. Every Pi tree is SYNTHETIC under
``tmp_path`` and every policy is a genuine PE-2b load of a SYNTHETIC chain
installed as the module-level sealed snapshot. Nothing runs Node or Pi, opens a
socket, reads a credential or endpoint, or touches the installed Pi.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest
from cfg1_doubles import FakeSupervisor, approve_profiles, build_synthetic_pi_tree
from cfg1_fu1_support import (
    AMBIENT_DECOYS,
    LeafRecorder,
    ProcessTripwire,
    RecordingMapping,
    fu1_ports,
    install_recording_genuine_leaves,
    make_admission,
    make_pi_world,
    replace_directory_with_identical_copy,
    replace_same_bytes,
)
from pe2a_support import manifest_bytes, root_manifest, synthetic_payload_files

from pi_harness_cfg1 import pi_identity, pi_payload
from pi_harness_cfg1 import pi_profile_policy_loader as loader
from pi_harness_cfg1.pi_identity import (
    ALLOWED_PAYLOAD_OBSERVATION_COMPLETE,
    EXPOSURE_PRESENT,
    EXPOSURE_UNOBSERVABLE,
    EXPOSURES_ABSENT,
    PI_EXTERNAL_RESOLUTION_EXPOSED,
    PI_IDENTITY_DRIFTED_DURING_PROOF,
    PI_IDENTITY_GATE_CODES,
    PI_IDENTITY_GATE_PASSED,
    PI_IDENTITY_GATE_UNEXPECTED_FAILURE,
    PI_PAYLOAD_UNPROVEN,
    PI_PROFILE_CHANGED_WITHIN_STAGE,
    PI_PROFILE_UNAPPROVED,
    PI_PROOF_FAILURE_CODES,
    PI_RESOLUTION_FAILED,
    Cfg1PiIdentity,
    Cfg1PiIdentityError,
    PiProofResult,
    genuine_pi_proof_leaves,
    observe_profile_exposures,
    pre_consumption_pi_identity_gate,
    prove_pi_identity,
    reprove_pi_identity_for_launch,
    require_pi_proof_result_shape,
)
from pi_harness_cfg1.run_executor import execute_cfg1_run

_PACKAGE_DIR = Path(__file__).resolve().parents[1]

#: A synthetic package name that exists nowhere on the machine: an exposure of
#: the "exposed" payload below (declared, not contained in the payload).
_EXPOSED_NAME = "pe2c-undeclared-exposure-7f3a"


def _exposed_files() -> tuple[dict, tuple]:
    files, empty_dirs = synthetic_payload_files()
    files = dict(files)
    document = root_manifest()
    document["dependencies"] = dict(document["dependencies"], **{_EXPOSED_NAME: "1.0.0"})
    files["package.json"] = manifest_bytes(document)
    return files, empty_dirs


def _variant_files(path: str = "dist/other.js", data: bytes = b"export const other = 3;\n"):
    files, empty_dirs = synthetic_payload_files()
    files = dict(files)
    files[path] = data
    return files, empty_dirs


def _exposure_site(tree) -> Path:
    """``<npm dir>\\node_modules\\<exposure>``: the nearest qualifying ancestor
    of the payload root (``node_modules``-named ancestors are skipped) joined
    with ``node_modules`` and the exposure's components."""
    return Path(tree.npm_dir) / "node_modules" / _EXPOSED_NAME


def _counting_overrides(reached: list[str]) -> dict:
    def _make(name):
        def _port(*args, **kwargs):
            reached.append(name)
            raise AssertionError(f"{name} must never be reached here")

        return _port

    return {name: _make(name) for name in ("mint_workspace", "read_connection", "observe_route")}


# ---------------------------------------------------------------------------
# C-1 -- P order and precedence, each of the five codes, duplicate match,
#        no manifest parser, only PATH
# ---------------------------------------------------------------------------


def test_c1_a_pass_carries_exactly_the_matched_profile_id(tmp_path, monkeypatch):
    tree = make_pi_world(tmp_path, monkeypatch)
    result = prove_pi_identity({"PATH": tree.path_value}, leaves=genuine_pi_proof_leaves())
    assert result.failure_code is None
    assert result.payload_observation_complete is True
    assert type(result.identity) is Cfg1PiIdentity
    assert result.identity.matched_profile_id == tree.profile_id
    assert PiProofResult.__slots__ == ("failure_code", "payload_observation_complete", "identity")
    assert "seam_digests_match" not in PiProofResult.__slots__
    for name in Cfg1PiIdentity.__slots__ + PiProofResult.__slots__:
        assert "version" not in name


def _reach(code: str, tmp_path, monkeypatch):
    """Drive P to exactly ``code`` and return ``(result, tree, recorder)``."""
    if code == PI_EXTERNAL_RESOLUTION_EXPOSED:
        files, empty_dirs = _exposed_files()
        tree = make_pi_world(tmp_path, monkeypatch, files=files, empty_dirs=empty_dirs)
        _exposure_site(tree).mkdir(parents=True)
    else:
        tree = make_pi_world(tmp_path, monkeypatch)
    path_value = tree.path_value
    recorder = LeafRecorder()
    if code == PI_RESOLUTION_FAILED:
        path_value = tree.npm_dir
    elif code == PI_PAYLOAD_UNPROVEN:
        monkeypatch.setattr(pi_payload, "MAX_PAYLOAD_ENTRIES", 3)
    elif code == PI_PROFILE_UNAPPROVED:
        Path(tree.seam_path("README.md")).write_bytes(b"# one changed non-seam byte\n")
    elif code == PI_IDENTITY_DRIFTED_DURING_PROOF:
        fired: list[int] = []

        def _hook(kind, path, log):
            if kind == "digest" and not fired:
                fired.append(1)
                replace_same_bytes(tree.node_exe)

        recorder = LeafRecorder(hook=_hook)
    result = prove_pi_identity({"PATH": path_value}, leaves=recorder.leaves())
    return result, tree, recorder


@pytest.mark.parametrize("code", sorted(PI_PROOF_FAILURE_CODES))
def test_c1_each_of_the_five_proof_codes_is_reachable_with_its_allowed_o(code, tmp_path, monkeypatch):
    result, _tree, _recorder = _reach(code, tmp_path, monkeypatch)
    assert result.failure_code == code
    assert result.identity is None
    assert result.payload_observation_complete is ALLOWED_PAYLOAD_OBSERVATION_COMPLETE[code]
    require_pi_proof_result_shape(result)
    assert len(PI_PROOF_FAILURE_CODES) == 5


def test_c1_precedence_membership_is_decided_before_exposure_or_drift(tmp_path, monkeypatch):
    """P2M precedes P2X and P2R: an unapproved payload is UNAPPROVED even with
    an exposure present and a node.exe swap pending -- and the exposure path is
    never even observed."""
    files, empty_dirs = _exposed_files()
    tree = make_pi_world(tmp_path, monkeypatch, files=files, empty_dirs=empty_dirs)
    _exposure_site(tree).mkdir(parents=True)
    Path(tree.seam_path("README.md")).write_bytes(b"# unapproved now\n")
    fired: list[int] = []

    def _hook(kind, path, log):
        if kind == "digest" and not fired:
            fired.append(1)
            replace_same_bytes(tree.node_exe)

    recorder = LeafRecorder(hook=_hook)
    result = prove_pi_identity({"PATH": tree.path_value}, leaves=recorder.leaves())
    assert result.failure_code == PI_PROFILE_UNAPPROVED
    assert not any(_EXPOSED_NAME in path for _kind, path in recorder.log)


def test_c1_precedence_exposure_is_decided_before_drift(tmp_path, monkeypatch):
    files, empty_dirs = _exposed_files()
    tree = make_pi_world(tmp_path, monkeypatch, files=files, empty_dirs=empty_dirs)
    _exposure_site(tree).mkdir(parents=True)
    fired: list[int] = []

    def _hook(kind, path, log):
        if kind == "digest" and not fired:
            fired.append(1)
            replace_same_bytes(tree.node_exe)

    result = prove_pi_identity({"PATH": tree.path_value}, leaves=LeafRecorder(hook=_hook).leaves())
    assert result.failure_code == PI_EXTERNAL_RESOLUTION_EXPOSED


def test_c1_resolution_failure_precedes_everything(tmp_path, monkeypatch):
    tree = make_pi_world(tmp_path, monkeypatch)
    recorder = LeafRecorder()
    result = prove_pi_identity({"PATH": tree.node_dir}, leaves=recorder.leaves())
    assert result.failure_code == PI_RESOLUTION_FAILED
    assert recorder.walk_calls() == []


def test_c1_an_unapproved_payload_under_the_genuine_committed_policy(tmp_path):
    """No synthetic policy: under the genuine committed snapshot -- whatever else it
    admits -- a payload whose profile is not in its eligible set is
    PI_PROFILE_UNAPPROVED (PE-0 F-14). Another eligible profile admits nothing else."""
    snapshot = loader.SEALED_POLICY_SNAPSHOT
    assert snapshot is loader._GENUINE_POLICY_LOAD.snapshot
    assert snapshot.policy_directory == loader._POLICY_DIR
    tree = build_synthetic_pi_tree(str(tmp_path / "unapproved_world"))
    assert tree.profile_id not in snapshot.eligible_profile_ids
    assert tree.payload_fingerprint not in {view.payload_fingerprint for view in snapshot.eligible_profiles}
    result = prove_pi_identity({"PATH": tree.path_value}, leaves=genuine_pi_proof_leaves())
    assert result.failure_code == PI_PROFILE_UNAPPROVED


def _forged_duplicate_snapshot(tree):
    """A snapshot no loader could build: two eligible views, one fingerprint."""
    view = loader.Cfg1EligibleProfileView(
        loader._SEAL_KEY,
        profile_id=tree.profile_id,
        payload_fingerprint=tree.payload_fingerprint,
        resolution_exposures=(),
        declared_package_version="1.0.0",
    )
    twin = loader.Cfg1EligibleProfileView(
        loader._SEAL_KEY,
        profile_id="f" * 64,
        payload_fingerprint=tree.payload_fingerprint,
        resolution_exposures=(),
        declared_package_version="9.9.9",
    )
    return loader.Cfg1PolicySnapshot(
        loader._SEAL_KEY,
        aps_revision=1,
        aps_head_sha256="d" * 64,
        policy_directory="C:\\synthetic",
        eligible_profiles=(view, twin),
    )


def test_c1_a_duplicate_match_raises_and_never_chooses(tmp_path, monkeypatch, git_executable):
    tree = make_pi_world(tmp_path, monkeypatch)
    monkeypatch.setattr(loader, "SEALED_POLICY_SNAPSHOT", _forged_duplicate_snapshot(tree))
    with pytest.raises(Cfg1PiIdentityError) as excinfo:
        prove_pi_identity({"PATH": tree.path_value}, leaves=genuine_pi_proof_leaves())
    assert excinfo.value.reason_code == "DUPLICATE_PROFILE_MATCH"
    # The gate reduces it to its one unexpected-failure code.
    assert pre_consumption_pi_identity_gate({"PATH": tree.path_value}) == PI_IDENTITY_GATE_UNEXPECTED_FAILURE
    # L1 records UNEXPECTED_STEP_FAILURE with NOTHING of P's family committed.
    ports, _made = fu1_ports(git_executable, tree)
    observations = execute_cfg1_run(make_admission(), ports=ports).observations
    assert observations["pre_dispatch_refusal_code"] == "UNEXPECTED_STEP_FAILURE"
    assert observations["refused_at_step"] == "L1"
    assert observations["pi_identity_failure_code"] is None
    assert observations["pi_payload_observation_complete"] is False
    assert observations["pi_profile_id"] is None


def test_c1_p_imports_no_manifest_parser_and_parses_nothing_pi_authored():
    source = (_PACKAGE_DIR / "pi_identity.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = set()
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported_modules.add((node.module or "").split(".")[-1])
            imported_names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            imported_modules.update(alias.name.split(".")[-1] for alias in node.names)
    assert not imported_modules & {"pi_manifest", "pi_profile_floor", "json", "pi_profile_discovery"}
    assert not imported_names & {"pi_manifest", "pi_profile_floor"}
    for forbidden in (
        "parse_manifest_strict",
        "validate_dependency_maps",
        "parse_package_name",
        "json.loads",
        "head_reference_view",
        "_GENUINE_POLICY_LOAD",
        "PINNED_PI_SEAM_DIGESTS",
        "PINNED_PI_VERSION",
    ):
        assert forbidden not in source, forbidden


def test_c1_p_accepts_no_snapshot_parameter_and_reads_the_module_level_snapshot():
    import inspect

    for function in (
        prove_pi_identity,
        pre_consumption_pi_identity_gate,
        reprove_pi_identity_for_launch,
        pi_identity.reobserve_pi_profile_after_runtime,
        require_pi_proof_result_shape,
    ):
        names = set(inspect.signature(function).parameters)
        assert not any("snapshot" in name or "policy" in name or "profile" in name for name in names), (
            function.__name__,
            names,
        )
    source = (_PACKAGE_DIR / "pi_identity.py").read_text(encoding="utf-8")
    assert "_policy.SEALED_POLICY_SNAPSHOT" in source


def test_c1_the_gate_and_l1_read_only_path(tmp_path, monkeypatch, git_executable):
    tree = make_pi_world(tmp_path, monkeypatch)
    ambient = RecordingMapping({**AMBIENT_DECOYS, "PATH": tree.path_value})
    assert pre_consumption_pi_identity_gate(ambient) == PI_IDENTITY_GATE_PASSED
    assert ambient.lookups == ["PATH"] and ambient.iterations == 0
    ambient_l1 = RecordingMapping({**AMBIENT_DECOYS, "PATH": tree.path_value})
    ports, _made = fu1_ports(
        git_executable,
        tree,
        ambient=ambient_l1,
        overrides={"git_executable": lambda: (_ for _ in ()).throw(RuntimeError("stop at L1"))},
    )
    execute_cfg1_run(make_admission(), ports=ports)
    assert ambient_l1.lookups == ["PATH"] and ambient_l1.iterations == 0


def test_c1_p_and_the_gate_start_no_process_and_write_nothing(tmp_path, monkeypatch, filesystem_spy):
    tree = make_pi_world(tmp_path, monkeypatch)
    tripwire = ProcessTripwire(monkeypatch, delegate=False)
    baseline = filesystem_spy.total_mutations
    assert pre_consumption_pi_identity_gate({"PATH": tree.path_value}) == PI_IDENTITY_GATE_PASSED
    prove_pi_identity({"PATH": tree.path_value}, leaves=genuine_pi_proof_leaves())
    assert tripwire.count == 0
    assert filesystem_spy.total_mutations == baseline


# ---------------------------------------------------------------------------
# C-2 -- the gate: exactly seven values, never the stage code, nothing reusable
# ---------------------------------------------------------------------------


def test_c2_the_gate_vocabulary_is_exactly_seven_and_excludes_the_stage_code():
    assert PI_IDENTITY_GATE_CODES == PI_PROOF_FAILURE_CODES | {
        PI_IDENTITY_GATE_PASSED,
        PI_IDENTITY_GATE_UNEXPECTED_FAILURE,
    }
    assert len(PI_IDENTITY_GATE_CODES) == 7
    assert PI_PROFILE_CHANGED_WITHIN_STAGE not in PI_IDENTITY_GATE_CODES


@pytest.mark.parametrize("code", sorted(PI_PROOF_FAILURE_CODES) + [PI_IDENTITY_GATE_PASSED])
def test_c2_the_gate_passes_every_proof_code_through_unchanged(code, tmp_path, monkeypatch):
    if code == PI_IDENTITY_GATE_PASSED:
        tree = make_pi_world(tmp_path, monkeypatch)
        path_value = tree.path_value
    else:
        if code == PI_EXTERNAL_RESOLUTION_EXPOSED:
            files, empty_dirs = _exposed_files()
            tree = make_pi_world(tmp_path, monkeypatch, files=files, empty_dirs=empty_dirs)
            _exposure_site(tree).mkdir(parents=True)
        else:
            tree = make_pi_world(tmp_path, monkeypatch)
        path_value = tree.path_value
        if code == PI_RESOLUTION_FAILED:
            path_value = tree.npm_dir
        elif code == PI_PAYLOAD_UNPROVEN:
            monkeypatch.setattr(pi_payload, "MAX_PAYLOAD_ENTRIES", 3)
        elif code == PI_PROFILE_UNAPPROVED:
            Path(tree.seam_path("README.md")).write_bytes(b"# changed\n")
        elif code == PI_IDENTITY_DRIFTED_DURING_PROOF:
            fired: list[int] = []

            def _hook(kind, path, log):
                if kind == "digest" and not fired:
                    fired.append(1)
                    replace_directory_with_identical_copy(tree.package_root)

            install_recording_genuine_leaves(monkeypatch, LeafRecorder(hook=_hook))
    returned = pre_consumption_pi_identity_gate({"PATH": path_value})
    assert type(returned) is str and returned == code
    assert returned in PI_IDENTITY_GATE_CODES


def test_c2_the_gate_never_returns_the_stage_code_even_from_a_forged_result(monkeypatch):
    def _forged(ambient_environ, *, leaves):
        return PiProofResult(
            pi_identity._P_ONLY,
            failure_code=PI_PROFILE_CHANGED_WITHIN_STAGE,
            payload_observation_complete=True,
            identity=None,
        )

    monkeypatch.setattr(pi_identity, "prove_pi_identity", _forged)
    assert pre_consumption_pi_identity_gate({"PATH": "C:\\x"}) == PI_IDENTITY_GATE_UNEXPECTED_FAILURE


def test_c2_the_gate_returns_nothing_reusable(tmp_path, monkeypatch):
    import inspect

    tree = make_pi_world(tmp_path, monkeypatch)
    returned = pre_consumption_pi_identity_gate({"PATH": tree.path_value})
    assert type(returned) is str
    assert tree.profile_id not in returned and tree.package_root not in returned
    signature = inspect.signature(pre_consumption_pi_identity_gate)
    assert list(signature.parameters) == ["ambient_environ"]


# ---------------------------------------------------------------------------
# C-3 -- require_pi_proof_result_shape
# ---------------------------------------------------------------------------


def _result(failure_code, complete, identity=None) -> PiProofResult:
    return PiProofResult(
        pi_identity._P_ONLY,
        failure_code=failure_code,
        payload_observation_complete=complete,
        identity=identity,
    )


class _StrSubclass(str):
    pass


@pytest.mark.parametrize(
    "failure_code",
    [
        PI_PROFILE_CHANGED_WITHIN_STAGE,
        PI_IDENTITY_GATE_PASSED,
        PI_IDENTITY_GATE_UNEXPECTED_FAILURE,
        "PI_SEAM_UNPROVEN",
        _StrSubclass(PI_PROFILE_UNAPPROVED),
        1,
        True,
    ],
)
def test_c3_stage_gate_historical_and_mistyped_codes_are_never_proof_codes(failure_code):
    for complete in (True, False):
        with pytest.raises(Cfg1PiIdentityError):
            require_pi_proof_result_shape(_result(failure_code, complete))


@pytest.mark.parametrize("code", sorted(PI_PROOF_FAILURE_CODES))
def test_c3_a_wrong_or_mistyped_observation_complete_is_refused(code):
    allowed = ALLOWED_PAYLOAD_OBSERVATION_COMPLETE[code]
    require_pi_proof_result_shape(_result(code, allowed))
    for wrong in (not allowed, int(allowed), int(not allowed), None, "true"):
        with pytest.raises(Cfg1PiIdentityError):
            require_pi_proof_result_shape(_result(code, wrong))


def test_c3_a_pass_with_a_non_eligible_id_or_a_bad_shape_is_refused(tmp_path, monkeypatch):
    tree = make_pi_world(tmp_path, monkeypatch)
    genuine = prove_pi_identity({"PATH": tree.path_value}, leaves=genuine_pi_proof_leaves())
    identity = genuine.identity
    require_pi_proof_result_shape(genuine)
    stranger = Cfg1PiIdentity(
        pi_identity._P_ONLY,
        node_executable=identity.node_executable,
        pi_cli_js=identity.pi_cli_js,
        pi_package_root=identity.pi_package_root,
        node_identity=identity.node_identity,
        package_root_identity=identity.package_root_identity,
        matched_profile_id="c" * 64,
    )
    for bad in (
        _result(None, True, stranger),  # matched id not in the sealed eligible set
        _result(None, False, identity),  # wrong O on a pass
        _result(None, 1, identity),  # int for True
        _result(None, True, None),  # pass without identity
        _result(PI_PROFILE_UNAPPROVED, True, identity),  # refusal carrying identity
    ):
        with pytest.raises(Cfg1PiIdentityError):
            require_pi_proof_result_shape(bad)
    with pytest.raises(Cfg1PiIdentityError):
        require_pi_proof_result_shape(object())
    # The same genuine identity is refused once its profile leaves the snapshot.
    approve_profiles(monkeypatch, build_synthetic_pi_tree(str(tmp_path / "other"), *_variant_files()))
    with pytest.raises(Cfg1PiIdentityError):
        require_pi_proof_result_shape(genuine)


def test_c3_a_malformed_identity_id_cannot_even_be_constructed():
    for bad in ("A" * 64, "a" * 63, 7, None, _StrSubclass("a" * 64)):
        with pytest.raises(Cfg1PiIdentityError):
            Cfg1PiIdentity(
                pi_identity._P_ONLY,
                node_executable="C:\\n.exe",
                pi_cli_js="C:\\p\\dist\\cli.js",
                pi_package_root="C:\\p",
                node_identity=(1, 2),
                package_root_identity=(1, 3),
                matched_profile_id=bad,
            )


# ---------------------------------------------------------------------------
# C-5 -- L14: re-proof of L1's EXACT profile; never a membership choice
# ---------------------------------------------------------------------------


class _LaunchRecorder(FakeSupervisor):
    def __init__(self, log: list) -> None:
        super().__init__()
        self._log = log
        self.launch_calls = 0

    def launch(self) -> None:
        self.launch_calls += 1
        self._log.append(("launch", ""))
        super().launch()


def _l14_run(git_executable, tree, mutate=None):
    recorder = LeafRecorder()
    supervisor = _LaunchRecorder(recorder.log)

    def _build_supervisor(**_kwargs):
        if mutate is not None:
            mutate()
        return supervisor

    ports, _made = fu1_ports(
        git_executable, tree, leaves=recorder.leaves(), overrides={"build_supervisor": _build_supervisor}
    )
    outcome = execute_cfg1_run(make_admission(), ports=ports)
    return outcome, supervisor, recorder


def _assert_refused_at_l14(outcome, supervisor, tree):
    observations = outcome.observations
    assert supervisor.launch_calls == 0
    assert observations["refused_at_step"] == "L14"
    assert observations["pre_dispatch_refusal_code"] == "RUNTIME_LAUNCH_FAILED"
    assert observations["runtime_created"] is False
    # Counterexample 9: L21A is NOT_APPLICABLE when no runtime was created.
    assert observations["pi_profile_post_runtime_reobservation"] == "NOT_APPLICABLE"
    assert observations["pi_profile_id"] == tree.profile_id


def test_c5_counterexample_9_a_payload_change_between_l1_and_l14_refuses(tmp_path, monkeypatch, git_executable):
    tree = make_pi_world(tmp_path, monkeypatch)

    def _mutate():
        Path(tree.seam_path("dist/other.js")).write_bytes(b"export const other = 99;\n")

    outcome, supervisor, _recorder = _l14_run(git_executable, tree, _mutate)
    _assert_refused_at_l14(outcome, supervisor, tree)


def test_c5_a_different_but_approved_profile_is_refused_at_l14(tmp_path, monkeypatch, git_executable):
    """Counterexample 16: the swap target is itself APPROVED -- and still refused,
    because L14 is equality with L1's matched profile, never re-membership."""
    variant_files, variant_dirs = _variant_files()
    tree = build_synthetic_pi_tree(str(tmp_path / "world"))
    variant = build_synthetic_pi_tree(str(tmp_path / "variant"), variant_files, variant_dirs)
    approve_profiles(monkeypatch, tree, variant)
    assert pre_consumption_pi_identity_gate({"PATH": variant.path_value}) == PI_IDENTITY_GATE_PASSED

    def _mutate():
        Path(tree.seam_path("dist/other.js")).write_bytes(variant_files["dist/other.js"])

    outcome, supervisor, _recorder = _l14_run(git_executable, tree, _mutate)
    _assert_refused_at_l14(outcome, supervisor, tree)
    # The mutated tree now IS the approved variant: P from scratch would pass.
    result = prove_pi_identity({"PATH": tree.path_value}, leaves=genuine_pi_proof_leaves())
    assert result.failure_code is None and result.identity.matched_profile_id == variant.profile_id


def test_c5_an_exposure_appearing_between_l1_and_l14_refuses(tmp_path, monkeypatch, git_executable):
    files, empty_dirs = _exposed_files()
    tree = make_pi_world(tmp_path, monkeypatch, files=files, empty_dirs=empty_dirs)
    outcome, supervisor, _recorder = _l14_run(
        git_executable, tree, lambda: _exposure_site(tree).mkdir(parents=True)
    )
    _assert_refused_at_l14(outcome, supervisor, tree)


@pytest.mark.parametrize("drift", ["root", "node"])
def test_c5_identity_drift_between_l1_and_l14_refuses(drift, tmp_path, monkeypatch, git_executable):
    tree = make_pi_world(tmp_path, monkeypatch)

    def _mutate():
        if drift == "root":
            replace_directory_with_identical_copy(tree.package_root)
        else:
            replace_same_bytes(tree.node_exe)

    outcome, supervisor, _recorder = _l14_run(git_executable, tree, _mutate)
    _assert_refused_at_l14(outcome, supervisor, tree)


def test_c5_nothing_reads_the_pi_tree_between_the_reproof_and_launch(tmp_path, monkeypatch, git_executable):
    tree = make_pi_world(tmp_path, monkeypatch)
    outcome, supervisor, recorder = _l14_run(git_executable, tree)
    assert outcome.observations["dispatch_state"] == "CONFIRMED_SENT"
    log = recorder.log
    launch_at = log.index(("launch", ""))
    assert log[launch_at - 1] == ("inspect", tree.node_exe)
    assert log[launch_at - 2] == ("inspect", tree.package_root)
    l14_walk = [entry for entry in log[:launch_at] if entry[0] in ("digest", "enumerate")]
    # Two complete walks before launch: L1's P2 and L14's re-walk.
    assert sum(1 for kind, _ in l14_walk if kind == "digest") == 2 * len(tree.files)
    assert supervisor.launch_calls == 1


def test_c5_the_l14_reproof_refuses_a_foreign_identity_or_leaves(tmp_path, monkeypatch):
    tree = make_pi_world(tmp_path, monkeypatch)
    leaves = genuine_pi_proof_leaves()
    identity = prove_pi_identity({"PATH": tree.path_value}, leaves=leaves).identity
    assert reprove_pi_identity_for_launch(identity, leaves=leaves) is True
    assert reprove_pi_identity_for_launch(object(), leaves=leaves) is False
    assert reprove_pi_identity_for_launch(identity, leaves=object()) is False
    # The profile retired from the sealed snapshot: the re-proof cannot resolve
    # L1's profile and refuses (raises -> the executor's RUNTIME_LAUNCH_FAILED).
    approve_profiles(monkeypatch, tree, retire=(tree.profile_id,))
    with pytest.raises(Cfg1PiIdentityError):
        reprove_pi_identity_for_launch(identity, leaves=leaves)


# ---------------------------------------------------------------------------
# The runtime exposure observer (P2X / L14 / L21A) agrees with PE-2a's
# ---------------------------------------------------------------------------


def test_the_runtime_exposure_observer_agrees_with_the_pe2a_observer():
    from pe2a_support import RecordingInspect

    from pi_harness_cfg1.pi_fs_leaves import (
        CLASSIFICATION_DIRECTORY,
        CLASSIFICATION_OTHER,
        CLASSIFICATION_REGULAR_FILE,
        CLASSIFICATION_REPARSE_POINT,
    )
    from pi_harness_cfg1.pi_manifest import EXPOSURES_PROVEN_ABSENT, observe_exposure_absence

    root = "C:\\w\\npm\\node_modules\\@earendil-works\\pi-coding-agent"
    near = "C:\\w\\npm\\node_modules"
    cases = {
        "absent": ({}, EXPOSURES_ABSENT),
        "present_dir": ({near + "\\x": CLASSIFICATION_DIRECTORY}, EXPOSURE_PRESENT),
        "present_file": ({near + "\\x": CLASSIFICATION_REGULAR_FILE}, EXPOSURE_PRESENT),
        "present_reparse": ({near + "\\x": CLASSIFICATION_REPARSE_POINT}, EXPOSURE_PRESENT),
        "final_other": ({near + "\\x": CLASSIFICATION_OTHER}, EXPOSURE_UNOBSERVABLE),
        "intermediate_reparse": ({near: CLASSIFICATION_REPARSE_POINT}, EXPOSURE_UNOBSERVABLE),
        "intermediate_file": ({near: CLASSIFICATION_REGULAR_FILE}, EXPOSURE_UNOBSERVABLE),
        "scoped_present": (
            {near + "\\@s": CLASSIFICATION_DIRECTORY, near + "\\@s\\y": CLASSIFICATION_DIRECTORY},
            EXPOSURE_PRESENT,
        ),
    }
    for name, (classifications, expected) in cases.items():
        classifications = dict(classifications)
        if near not in classifications:
            classifications[near] = CLASSIFICATION_DIRECTORY
        exposures = (("@s", "y"),) if name == "scoped_present" else (("x",),)
        texts = ["@s/y"] if name == "scoped_present" else ["x"]
        runtime = observe_profile_exposures(root, exposures, inspect=RecordingInspect(classifications))
        pe2a = observe_exposure_absence(root, texts, inspect=RecordingInspect(classifications)).status
        assert runtime == expected, name
        assert (runtime == EXPOSURES_ABSENT) == (pe2a == EXPOSURES_PROVEN_ABSENT), name
    raising = RecordingInspect({near: CLASSIFICATION_DIRECTORY}, raise_on={near + "\\x"})
    assert observe_profile_exposures(root, (("x",),), inspect=raising) == EXPOSURE_UNOBSERVABLE


def test_the_runtime_exposure_observer_refuses_a_malformed_policy_component():
    from pe2a_support import RecordingInspect

    root = "C:\\w\\npm\\node_modules\\@earendil-works\\pi-coding-agent"
    for bad in ((("..",),), (("a\\b",),), (("x", "y"),), (("x",), ("",)), ["x"], (("C:",),)):
        with pytest.raises(Cfg1PiIdentityError):
            observe_profile_exposures(root, bad, inspect=RecordingInspect())


# ---------------------------------------------------------------------------
# C-12 -- PE-0 Sec. 14.4 scenario 8: an undeclared sibling changes mid-run
# ---------------------------------------------------------------------------


def test_c12_an_undeclared_sibling_mutated_mid_run_leaves_p_l14_and_l21a_passing(
    tmp_path, monkeypatch, git_executable
):
    from pi_harness_cfg1.records import _require_valid_cfg1_run_payload_v3, build_cfg1_run_payload

    tree = make_pi_world(tmp_path, monkeypatch)
    sibling = Path(tree.npm_dir) / "node_modules" / "undeclared-sibling"
    sibling.mkdir(parents=True)
    (sibling / "index.js").write_bytes(b"module.exports = 1;\n")

    class _MutatingSupervisor(FakeSupervisor):
        def shutdown(self):
            (sibling / "index.js").write_bytes(b"module.exports = 2; // changed mid-run\n")
            return super().shutdown()

    ports, _made = fu1_ports(
        git_executable, tree, overrides={"build_supervisor": lambda **_k: _MutatingSupervisor()}
    )
    outcome = execute_cfg1_run(make_admission(), ports=ports)
    observations = outcome.observations
    assert observations["pi_identity_failure_code"] is None
    assert observations["dispatch_state"] == "CONFIRMED_SENT"  # L14 passed
    assert observations["pi_profile_post_runtime_reobservation"] == "PROVEN_UNCHANGED"
    payload = build_cfg1_run_payload(
        stage_id="S1", stage_execution_id="S1-X1", run_ordinal=1, observations=observations
    )
    _require_valid_cfg1_run_payload_v3(payload)
    assert payload["pi_profile_authority_scope"] == "PI_PACKAGE_PAYLOAD_AND_DECLARED_RESOLUTION_BOUNDARY"
    assert payload["pi_external_runtime_residual"] == "NOT_IDENTIFIED_BY_PROFILE"
    assert payload["run_classification"] == "INACTIVE"


# ---------------------------------------------------------------------------
# C-14 -- no credential or endpoint read on ANY profile refusal path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "code", sorted(PI_PROOF_FAILURE_CODES) + [PI_PROFILE_CHANGED_WITHIN_STAGE, "UNEXPECTED_ADMISSION"]
)
def test_c14_no_credential_port_is_called_on_any_profile_refusal(code, tmp_path, monkeypatch, git_executable):
    reached: list[str] = []
    overrides = _counting_overrides(reached)
    admission = make_admission()
    leaves = None
    if code == PI_EXTERNAL_RESOLUTION_EXPOSED:
        files, empty_dirs = _exposed_files()
        tree = make_pi_world(tmp_path, monkeypatch, files=files, empty_dirs=empty_dirs)
        _exposure_site(tree).mkdir(parents=True)
    else:
        tree = make_pi_world(tmp_path, monkeypatch)
    ambient = {"SystemRoot": "C:\\Windows", "PATH": tree.path_value}
    if code == PI_RESOLUTION_FAILED:
        ambient["PATH"] = tree.npm_dir
    elif code == PI_PAYLOAD_UNPROVEN:
        monkeypatch.setattr(pi_payload, "MAX_PAYLOAD_ENTRIES", 3)
    elif code == PI_PROFILE_UNAPPROVED:
        Path(tree.seam_path("README.md")).write_bytes(b"# changed\n")
    elif code == PI_IDENTITY_DRIFTED_DURING_PROOF:
        fired: list[int] = []

        def _hook(kind, path, log):
            if kind == "digest" and not fired:
                fired.append(1)
                replace_same_bytes(tree.node_exe)

        leaves = LeafRecorder(hook=_hook).leaves()
    elif code == PI_PROFILE_CHANGED_WITHIN_STAGE:
        admission = make_admission(2, stage_pi_profile_id="9" * 64)
    elif code == "UNEXPECTED_ADMISSION":
        admission = make_admission(2, stage_pi_profile_id="NOT-HEX")
    ports, _made = fu1_ports(git_executable, tree, leaves=leaves, ambient=ambient, overrides=overrides)
    observations = execute_cfg1_run(admission, ports=ports).observations
    assert reached == []
    assert observations["refused_at_step"] == "L1"
    if code == "UNEXPECTED_ADMISSION":
        assert observations["pre_dispatch_refusal_code"] == "UNEXPECTED_STEP_FAILURE"
        assert observations["pi_identity_failure_code"] is None
    else:
        assert observations["pi_identity_failure_code"] == code
