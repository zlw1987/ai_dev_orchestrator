"""PE-2a: static discovery and its fixed, non-authority staging write boundary.

Acceptance rows A-15 .. A-19 of
``docs/PHASE_5F3B_PI_HARNESS_PROFILE_EVOLUTION_PE1_AMENDMENT.md`` Sec. 26.1
(Sec. 9.10, R1 B12), plus end-to-end adversarial regressions.

Every discovery here runs over a SYNTHETIC world under pytest ``tmp_path``:
an inert ``node.exe`` that nothing executes, a never-read ``pi.cmd`` and a
synthetic payload. ``PATH`` is the test's own value; the installed Pi is never
on it. The staging directory is retargeted to ``tmp_path`` by rebinding the
module global -- test-harness memory manipulation, the same deliberate
pattern ``conftest`` uses for ``_CAPTURED_PACKAGE_DIR`` -- while separate tests
prove the PRODUCTION derivation from ``__file__``. Reparse points are doubles.
"""

from __future__ import annotations

import ast
import builtins
import importlib.util
import inspect as _inspect
import json
import os
import re
import shutil
from pathlib import Path

import pytest
from cfg1_fu1_support import AMBIENT_DECOYS, ProcessTripwire, RecordingMapping
from pe2a_support import (
    DiscoveryWorld,
    manifest_bytes,
    root_manifest,
    staging_listing,
    synthetic_payload_files,
)

from pi_harness_cfg1 import pi_fs_leaves, pi_manifest, pi_profile_discovery
from pi_harness_cfg1.pi_fs_leaves import NoFollowObservation
from pi_harness_cfg1.pi_identity import PiProofLeaves, genuine_pi_proof_leaves
from pi_harness_cfg1.pi_manifest import bundle_from_record, compute_profile_id
from pi_harness_cfg1.pi_payload import (
    PayloadLeaves,
    canonical_json_bytes,
    genuine_payload_leaves,
    inventory_from_record,
)
from pi_harness_cfg1.pi_profile_discovery import (
    DISCOVERY_CANDIDATE_STAGED,
    DISCOVERY_REFUSED_ARGUMENTS,
    DISCOVERY_REFUSED_ARTIFACT_BOUND_EXCEEDED,
    DISCOVERY_REFUSED_IDENTITY_DRIFTED,
    DISCOVERY_REFUSED_MANIFEST_CAPTURE_UNBOUND,
    DISCOVERY_REFUSED_PAYLOAD_CHANGED_BETWEEN_WALKS,
    DISCOVERY_REFUSED_PAYLOAD_UNPROVEN,
    DISCOVERY_REFUSED_PI_RESOLUTION_FAILED,
    DISCOVERY_REFUSED_STAGING_TARGET_OCCUPIED,
    DISCOVERY_REFUSED_STAGING_TOPOLOGY,
    DISCOVERY_STAGING_WRITE_FAILED_RESIDUE_LEFT,
    STAGING_FILENAME_GRAMMAR,
    Cfg1DiscoveryError,
    _discover,
    discover_pi_profile_candidate,
)

_TESTS_DIR = Path(__file__).resolve().parent
_PACKAGE_DIR = _TESTS_DIR.parent
_REPO_ROOT = _PACKAGE_DIR.parents[1]
_REAL_STAGING = _PACKAGE_DIR / "pi_profile_candidates"
_SUFFIXES = (".inventory.json", ".manifest_bundle.json", ".candidate.json")


@pytest.fixture(autouse=True)
def _the_real_staging_directory_is_never_touched():
    """PE-2a tests must leave NO real candidate artifact in the repository."""
    existed = _REAL_STAGING.exists()
    yield
    assert _REAL_STAGING.exists() is existed, "a PE-2a test touched the REAL staging directory"
    assert not existed, "a real pi_profile_candidates directory exists in the checkout"


@pytest.fixture()
def staging(tmp_path, monkeypatch) -> Path:
    package = tmp_path / "synthetic_cfg1_package"
    package.mkdir()
    target = package / "pi_profile_candidates"
    monkeypatch.setattr(pi_profile_discovery, "_STAGING_DIRECTORY", str(target))
    return target


@pytest.fixture()
def world(tmp_path) -> DiscoveryWorld:
    return DiscoveryWorld(tmp_path / "world")


def _run(world: DiscoveryWorld, **overrides):
    leaves = dict(
        proof_leaves=genuine_pi_proof_leaves(),
        payload_leaves=genuine_payload_leaves(),
        read_manifest=pi_fs_leaves.read_payload_file_bytes,
    )
    leaves.update(overrides)
    return _discover({"PATH": world.path_value}, **leaves)


def _proof_leaves_with(inspect) -> PiProofLeaves:
    genuine = genuine_pi_proof_leaves()
    return PiProofLeaves(inspect=inspect, read_digest=genuine.read_digest, checkout_root=genuine.checkout_root)


def _inspect_overriding(overrides: dict[str, str]):
    def _inspect(path):
        if path in overrides:
            classification = overrides[path]
            identity = (7, 7) if classification in ("directory", "regular_file") else None
            return NoFollowObservation(classification, identity)
        return pi_fs_leaves.inspect_no_follow(path)

    return _inspect


# ---------------------------------------------------------------------------
# Positive end-to-end
# ---------------------------------------------------------------------------


def test_discovery_stages_exactly_three_canonical_non_authority_artifacts(world, staging):
    outcome = _run(world)
    assert outcome.code == DISCOVERY_CANDIDATE_STAGED
    fingerprint = outcome.payload_fingerprint
    names = [fingerprint + suffix for suffix in _SUFFIXES]
    assert outcome.staged_files == tuple(names)  # candidate LAST
    assert staging_listing(staging) == sorted(names)
    for name in names:
        assert STAGING_FILENAME_GRAMMAR.fullmatch(name)
        data = (staging / name).read_bytes()
        assert data.endswith(b"\n") and not data.endswith(b"\n\n") and b"\r" not in data
        assert canonical_json_bytes(json.loads(data)) + b"\n" == data

    inventory = inventory_from_record(json.loads((staging / names[0]).read_bytes()))
    assert inventory.payload_fingerprint == fingerprint
    bundle = bundle_from_record(json.loads((staging / names[1]).read_bytes()), inventory)
    assert bundle.payload_fingerprint == fingerprint
    candidate = json.loads((staging / names[2]).read_bytes())
    assert candidate["authority"] == "NON_AUTHORITY_CANDIDATE"
    assert candidate["floor"] == "NOT_COMPUTED"
    assert candidate["approvability"] == {"status": "APPROVABILITY_FLOOR_MET", "reason": None, "manifest_path": None}
    assert candidate["payload_fingerprint"] == fingerprint
    assert candidate["profile_id"] == compute_profile_id(fingerprint, [])
    assert candidate["resolution_exposures"] == []
    assert candidate["exposure_absence_observation"] == "EXPOSURES_PROVEN_ABSENT"
    assert candidate["pi_profile_authority_scope"] == "PI_PACKAGE_PAYLOAD_AND_DECLARED_RESOLUTION_BOUNDARY"
    assert candidate["pi_external_runtime_residual"] == "NOT_IDENTIFIED_BY_PROFILE"
    assert candidate["declared"]["package_name"] == "@earendil-works/pi-coding-agent"
    assert "aido_commit" not in json.dumps(candidate)  # no Git was run


def test_discovery_console_carries_no_absolute_path(world, staging):
    outcome = _run(world)
    text = "\n".join(outcome.console_lines)
    assert outcome.console_lines[0] == "PI_PROFILE_DISCOVERY DISCOVERY_CANDIDATE_STAGED"
    assert str(world.base) not in text and str(staging) not in text
    assert ":\\" not in text


def test_discovery_stages_a_c5_candidate_with_its_reason(tmp_path, staging):
    files, empty_dirs = synthetic_payload_files()
    files["package.json"] = manifest_bytes(root_manifest(name="not-pi"))
    world = DiscoveryWorld(tmp_path / "world", files, empty_dirs)
    outcome = _run(world)
    assert outcome.code == DISCOVERY_CANDIDATE_STAGED
    candidate = json.loads((staging / (outcome.payload_fingerprint + ".candidate.json")).read_bytes())
    assert candidate["approvability"]["status"] == "C5_UNDER_HPP1"
    assert candidate["approvability"]["reason"] == "DECLARED_PACKAGE_NAME_MISMATCH"
    assert candidate["floor"] == "NOT_COMPUTED"


# ---------------------------------------------------------------------------
# A-15 -- double walk, no process, only PATH, floor NOT_COMPUTED
# ---------------------------------------------------------------------------


def test_a15_walks_that_differ_between_passes_refuse_and_write_nothing(world, staging):
    genuine = genuine_payload_leaves()
    root = world.payload_root_str
    seen = {"root": 0}

    def _enumerate(path, budget):
        if path == root:
            seen["root"] += 1
            if seen["root"] == 2:
                (world.payload_root / "dist" / "other.js").write_bytes(b"changed between walks")
        return genuine.enumerate_directory(path, budget)

    outcome = _run(world, payload_leaves=PayloadLeaves(enumerate_directory=_enumerate, read_file=genuine.read_file))
    assert outcome.code == DISCOVERY_REFUSED_PAYLOAD_CHANGED_BETWEEN_WALKS
    assert outcome.staged_files == ()
    assert not staging.exists()


def test_a15_an_incomplete_walk_refuses_and_writes_nothing(world, staging):
    genuine = genuine_payload_leaves()
    target = str(world.payload_root / "README.md")

    def _read(path, cap):
        if path == target:
            return pi_fs_leaves.PayloadFileRead("other", False, False, None, None, None)
        return genuine.read_file(path, cap)

    outcome = _run(world, payload_leaves=PayloadLeaves(enumerate_directory=genuine.enumerate_directory, read_file=_read))
    assert outcome.code == DISCOVERY_REFUSED_PAYLOAD_UNPROVEN
    assert outcome.payload_fingerprint is None
    assert "  PAYLOAD_ENTRY_UNOBSERVABLE" in outcome.console_lines
    assert not staging.exists()


def test_a15_a_manifest_changed_after_the_walks_refuses(world, staging):
    target = str(world.payload_root / "package.json")

    def _read_manifest(path, cap):
        if path == target:
            (world.payload_root / "package.json").write_bytes(manifest_bytes(root_manifest(version="6.6.6")))
        return pi_fs_leaves.read_payload_file_bytes(path, cap)

    outcome = _run(world, read_manifest=_read_manifest)
    assert outcome.code == DISCOVERY_REFUSED_MANIFEST_CAPTURE_UNBOUND
    assert not staging.exists()


def test_a15_identity_drift_before_staging_refuses(world, staging):
    from cfg1_fu1_support import replace_directory_with_identical_copy

    fired = []

    def _read_manifest(path, cap):
        if not fired:
            fired.append(1)
            replace_directory_with_identical_copy(world.payload_root_str)
        return pi_fs_leaves.read_payload_file_bytes(path, cap)

    outcome = _run(world, read_manifest=_read_manifest)
    assert outcome.code == DISCOVERY_REFUSED_IDENTITY_DRIFTED
    assert not staging.exists()


def test_a15_discovery_creates_no_process(world, staging, monkeypatch):
    tripwire = ProcessTripwire(monkeypatch, delegate=False)
    outcome = discover_pi_profile_candidate({"PATH": world.path_value})
    assert outcome.code == DISCOVERY_CANDIDATE_STAGED
    assert tripwire.events == []


def test_a15_discovery_reads_only_path_from_the_ambient_mapping(world, staging):
    ambient = RecordingMapping({**AMBIENT_DECOYS, "PATH": world.path_value})
    outcome = discover_pi_profile_candidate(ambient)
    assert outcome.code == DISCOVERY_CANDIDATE_STAGED
    assert ambient.lookups == ["PATH"]
    assert ambient.iterations == 0
    everything = "\n".join(outcome.console_lines) + "".join(
        (staging / name).read_text(encoding="ascii") for name in outcome.staged_files
    )
    for decoy in AMBIENT_DECOYS.values():
        assert decoy not in everything


def test_a15_no_path_refuses_as_resolution_failure(staging):
    outcome = discover_pi_profile_candidate(RecordingMapping({**AMBIENT_DECOYS}))
    assert outcome.code == DISCOVERY_REFUSED_PI_RESOLUTION_FAILED
    assert not staging.exists()


def test_a15_the_installed_pi_is_not_reachable_from_a_test_path(world):
    assert "AppData\\Roaming\\npm" not in world.path_value


_PROCESS_NAME = re.compile(r"CreateProcess|ShellExecute|WinExec")
_OS_PROCESS_ATTRS = re.compile(r"^(system|startfile|spawn\w*|exec[lv]\w*|popen|fork\w*)$")
_PE2A_MODULES = ("pi_payload", "pi_manifest", "pi_profile_floor", "pi_profile_discovery", "pi_fs_leaves")


@pytest.mark.parametrize("module_name", _PE2A_MODULES)
def test_a15_static_audit_no_process_node_network_or_policy_surface(module_name):
    source = (_PACKAGE_DIR / f"{module_name}.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_roots = {
        "subprocess",
        "multiprocessing",
        "socket",
        "http",
        "urllib",
        "requests",
        "httpx",
        "ar2",
        "qualification",
        "ai_dev_orchestrator",
        "asyncio",
        "ctypes" if module_name != "pi_fs_leaves" else "-",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in forbidden_roots, alias.name
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in forbidden_roots, node.module
            if node.level:
                assert node.module not in ("run_executor", "stage_runner", "writers", "records"), node.module
        if isinstance(node, ast.Attribute):
            assert _PROCESS_NAME.search(node.attr) is None, node.attr
            if isinstance(node.value, ast.Name) and node.value.id == "os":
                assert _OS_PROCESS_ATTRS.match(node.attr) is None, node.attr
                assert node.attr not in ("getenv", "getcwd", "chdir", "putenv"), node.attr
        if isinstance(node, ast.Name):
            assert _PROCESS_NAME.search(node.id) is None, node.id
    # No string literal other than a docstring (which explain the negative)
    # carries a version-probe flag.
    docstrings = {
        id(body[0].value)
        for body in (
            getattr(n, "body", None)
            for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef))
        )
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            assert "--version" not in node.value, node.lineno
            assert _PROCESS_NAME.search(node.value) is None, node.lineno


def test_a15_static_audit_only_main_touches_the_process_environment():
    tree = ast.parse((_PACKAGE_DIR / "pi_profile_discovery.py").read_text(encoding="utf-8"))
    users = set()
    for function in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)):
        for node in ast.walk(function):
            if isinstance(node, ast.Attribute) and node.attr == "environ":
                users.add(function.name)
    assert users == {"main"}
    for module_name in ("pi_payload", "pi_manifest", "pi_profile_floor", "pi_fs_leaves"):
        assert "environ" not in (_PACKAGE_DIR / f"{module_name}.py").read_text(encoding="utf-8")


def test_a15_the_floor_is_not_computed_and_no_policy_is_loaded():
    source = (_PACKAGE_DIR / "pi_profile_discovery.py").read_text(encoding="utf-8")
    for name in ("classify_floor", "ReferenceView", "pi_profile_policy", "c2_relation", "compute_pmd_deltas"):
        assert name not in source, name
    assert "FLOOR_NOT_COMPUTED" in source


# ---------------------------------------------------------------------------
# A-16 -- no arbitrary output selection
# ---------------------------------------------------------------------------


_OUTPUT_PARAMETER = re.compile(r"(out|output|dir|directory|dest|destination|target|staging|file|filename|path)", re.I)


def test_a16_the_entry_points_have_no_output_parameter():
    assert list(_inspect.signature(discover_pi_profile_candidate).parameters) == ["ambient_environ"]
    assert list(_inspect.signature(pi_profile_discovery.main).parameters) == ["argv"]
    assert list(_inspect.signature(_discover).parameters) == [
        "ambient_environ",
        "proof_leaves",
        "payload_leaves",
        "read_manifest",
    ]
    assert list(_inspect.signature(pi_profile_discovery._stage_candidate_artifacts).parameters) == [
        "payload_fingerprint",
        "artifacts",
        "inspect",
    ]
    for function in (discover_pi_profile_candidate, pi_profile_discovery.main, _discover):
        for name in _inspect.signature(function).parameters:
            assert _OUTPUT_PARAMETER.search(name) is None or name == "argv", name


def test_a16_the_staging_location_is_read_only_from_the_module_global():
    tree = ast.parse((_PACKAGE_DIR / "pi_profile_discovery.py").read_text(encoding="utf-8"))
    loads = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id == "_STAGING_DIRECTORY" and isinstance(node.ctx, ast.Load)
    ]
    stores = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id == "_STAGING_DIRECTORY" and isinstance(node.ctx, ast.Store)
    ]
    assert len(stores) == 1 and len(loads) == 1
    staging_function = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_stage_candidate_artifacts"
    )
    assert any(node is loads[0] for node in ast.walk(staging_function))
    # ``_staging_targets`` and the creates are reached only from there.
    for helper in ("_staging_targets", "_create_exclusive", "_make_staging_directory"):
        callers = {
            function.name
            for function in ast.walk(tree)
            if isinstance(function, ast.FunctionDef)
            for node in ast.walk(function)
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == helper
        }
        assert callers == {"_stage_candidate_artifacts"}, (helper, callers)


@pytest.mark.parametrize(
    "argv",
    [
        ["--output", "C:\\elsewhere"],
        ["--out-dir=..\\..\\x"],
        ["\\\\server\\share\\x"],
        ["C:\\dev\\ai_dev_orchestrator\\experiments\\pi_harness_cfg1\\pi_profile_policy"],
        ["results"],
        ["-o", "x"],
    ],
)
def test_a16_any_argument_refuses_before_discovery(argv, staging, monkeypatch, capsys):
    called = []
    monkeypatch.setattr(pi_profile_discovery, "discover_pi_profile_candidate", lambda env: called.append(env))
    assert pi_profile_discovery.main(argv) == 2
    assert called == []
    assert capsys.readouterr().out.strip() == "PI_PROFILE_DISCOVERY " + DISCOVERY_REFUSED_ARGUMENTS
    assert not staging.exists()


def test_a16_environment_and_cwd_cannot_redirect_output(world, staging, tmp_path, monkeypatch, capsys):
    hostile_cwd = tmp_path / "hostile_cwd"
    hostile_cwd.mkdir()
    monkeypatch.chdir(hostile_cwd)
    monkeypatch.setenv("PATH", world.path_value)
    for name in ("PI_PROFILE_CANDIDATES", "AIDO_STAGING_DIR", "OUTPUT_DIR", "TMP", "TEMP", "USERPROFILE"):
        monkeypatch.setenv(name, str(tmp_path / "hostile_env"))
    assert pi_profile_discovery.main([]) == 0
    assert list(hostile_cwd.iterdir()) == []
    assert not (tmp_path / "hostile_env").exists()
    assert len(staging_listing(staging)) == 3
    assert "DISCOVERY_CANDIDATE_STAGED" in capsys.readouterr().out


def test_a16_a_recording_filesystem_double_sees_no_write_outside_staging(world, staging, monkeypatch):
    mutations: list[str] = []
    real_open = builtins.open
    real_mkdir = os.mkdir

    def _open(file, mode="r", *args, **kwargs):
        if any(flag in mode for flag in ("w", "a", "+", "x")):
            mutations.append(str(file))
        return real_open(file, mode, *args, **kwargs)

    def _mkdir(path, *args, **kwargs):
        mutations.append(str(path))
        return real_mkdir(path, *args, **kwargs)

    def _refuse(name):
        def _call(*args, **kwargs):
            mutations.append(f"{name}:{args!r}")
            raise AssertionError(f"discovery called {name}")

        return _call

    monkeypatch.setattr(builtins, "open", _open)
    monkeypatch.setattr(os, "mkdir", _mkdir)
    for name in ("makedirs", "rename", "replace", "remove", "unlink", "rmdir", "truncate", "open"):
        monkeypatch.setattr(os, name, _refuse(f"os.{name}"))
    for name in ("rmtree", "move", "copyfile", "copy", "copy2"):
        monkeypatch.setattr(shutil, name, _refuse(f"shutil.{name}"))
    outcome = _run(world)
    monkeypatch.undo()
    assert outcome.code == DISCOVERY_CANDIDATE_STAGED
    staging_text = str(staging)
    assert mutations[0] == staging_text  # the one mkdir
    assert len(mutations) == 4
    for path in mutations:
        assert path == staging_text or os.path.dirname(path) == staging_text, path


def test_a16_the_production_staging_derivation_is_fixed_by_file_location(tmp_path, monkeypatch):
    """Load a FRESH copy of the module under a hostile CWD and environment;
    its staging location is still exactly <ROOT>\\experiments\\pi_harness_cfg1\\pi_profile_candidates."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PI_PROFILE_CANDIDATES", str(tmp_path))
    spec = importlib.util.spec_from_file_location(
        "pi_harness_cfg1._pe2a_fresh_discovery_probe", pi_profile_discovery.__file__
    )
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)
    expected = str(_REPO_ROOT / "experiments" / "pi_harness_cfg1" / "pi_profile_candidates")
    assert fresh._STAGING_DIRECTORY == expected
    assert fresh._CFG1_PACKAGE_DIRECTORY == str(Path(pi_profile_discovery.__file__).resolve().parent)
    policy = str(_REPO_ROOT / "experiments" / "pi_harness_cfg1" / "pi_profile_policy")
    results = str(_REPO_ROOT / "experiments" / "pi_harness_cfg1" / "results")
    for other in (policy, results):
        assert not expected.startswith(other) and not other.startswith(expected)


# ---------------------------------------------------------------------------
# A-17 -- staging topology and the exact filename grammar
# ---------------------------------------------------------------------------


def test_a17_a_missing_staging_directory_is_created_by_exactly_one_exclusive_mkdir(world, staging, monkeypatch):
    calls = []
    real_mkdir = os.mkdir

    def _mkdir(path, *args, **kwargs):
        calls.append((str(path), args, kwargs))
        return real_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(os, "mkdir", _mkdir)
    assert _run(world).code == DISCOVERY_CANDIDATE_STAGED
    assert calls == [(str(staging), (), {})]
    # A second discovery of a DIFFERENT payload reuses the plain directory.
    calls.clear()
    (world.payload_root / "dist" / "other.js").write_bytes(b"second payload")
    assert _run(world).code == DISCOVERY_CANDIDATE_STAGED
    assert calls == []
    assert len(staging_listing(staging)) == 6


def test_a17_a_missing_parent_refuses_with_nothing_written(world, staging, monkeypatch):
    monkeypatch.setattr(
        pi_profile_discovery, "_STAGING_DIRECTORY", str(staging.parent / "absent_parent" / "pi_profile_candidates")
    )
    outcome = _run(world)
    assert outcome.code == DISCOVERY_REFUSED_STAGING_TOPOLOGY
    assert not (staging.parent / "absent_parent").exists()


@pytest.mark.parametrize("classification", ["reparse_point", "other", "regular_file"])
def test_a17_staging_as_junction_symlink_file_or_other_refuses(world, staging, classification):
    inspect = _inspect_overriding({str(staging): classification})
    outcome = _run(world, proof_leaves=_proof_leaves_with(inspect))
    assert outcome.code == DISCOVERY_REFUSED_STAGING_TOPOLOGY
    assert not staging.exists()


def test_a17_a_real_file_at_the_staging_path_refuses(world, staging):
    staging.write_bytes(b"occupant")
    outcome = _run(world)
    assert outcome.code == DISCOVERY_REFUSED_STAGING_TOPOLOGY
    assert staging.read_bytes() == b"occupant"


@pytest.mark.parametrize("classification", ["reparse_point", "other", "regular_file", "missing"])
def test_a17_a_parent_that_is_not_a_plain_directory_refuses(world, staging, classification):
    inspect = _inspect_overriding({str(staging.parent): classification})
    outcome = _run(world, proof_leaves=_proof_leaves_with(inspect))
    assert outcome.code == DISCOVERY_REFUSED_STAGING_TOPOLOGY
    assert not staging.exists()


def test_a17_a_staging_directory_that_turns_into_a_reparse_point_after_mkdir_refuses(world, staging):
    state = {"made": False}
    real = pi_fs_leaves.inspect_no_follow

    def _inspect(path):
        if path == str(staging) and staging.exists():
            return NoFollowObservation("reparse_point", None)
        return real(path)

    outcome = _run(world, proof_leaves=_proof_leaves_with(_inspect))
    assert outcome.code == DISCOVERY_REFUSED_STAGING_TOPOLOGY
    assert staging_listing(staging) == []
    del state


@pytest.mark.parametrize(
    "name, ok",
    [
        ("a" * 64 + ".candidate.json", True),
        ("0123456789abcdef" * 4 + ".inventory.json", True),
        ("f" * 64 + ".manifest_bundle.json", True),
        ("A" * 64 + ".candidate.json", False),
        ("a" * 63 + ".candidate.json", False),
        ("a" * 65 + ".candidate.json", False),
        ("a" * 64 + ".candidate.JSON", False),
        ("a" * 64 + ".profile.json", False),
        ("a" * 64 + ".candidate.json\n", False),
        ("..\\" + "a" * 64 + ".candidate.json", False),
        ("a" * 64 + ".candidate.json:stream", False),
    ],
)
def test_a17_the_exact_filename_grammar(name, ok):
    assert (STAGING_FILENAME_GRAMMAR.fullmatch(name) is not None) is ok
    assert STAGING_FILENAME_GRAMMAR.pattern == r"^[0-9a-f]{64}\.(candidate|inventory|manifest_bundle)\.json$"


class _StrSub(str):
    pass


@pytest.mark.parametrize(
    "fingerprint",
    ["A" * 64, "a" * 63, "..", "a" * 32 + "\\" + "a" * 31, "C:" + "a" * 62, _StrSub("a" * 64), None, 1],
)
def test_a17_names_are_formed_only_from_a_validated_fingerprint(fingerprint, staging):
    with pytest.raises(Cfg1DiscoveryError):
        pi_profile_discovery._staging_targets(fingerprint, str(staging))


def test_a17_every_target_is_structurally_contained(staging):
    targets = pi_profile_discovery._staging_targets("b" * 64, str(staging))
    assert [name for name, _ in targets] == ["b" * 64 + suffix for suffix in _SUFFIXES]
    for name, path in targets:
        assert os.path.dirname(path) == str(staging) and os.path.basename(path) == name


# ---------------------------------------------------------------------------
# A-18 -- exclusive create, residue, no cleanup
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("suffix", _SUFFIXES)
@pytest.mark.parametrize("occupant", ["file", "directory", "reparse_point"])
def test_a18_any_pre_existing_target_refuses_before_any_create(world, staging, monkeypatch, suffix, occupant):
    first = _run(world)
    fingerprint = first.payload_fingerprint
    for name in first.staged_files:
        (staging / name).unlink()
    target = staging / (fingerprint + suffix)
    overrides = {}
    if occupant == "file":
        target.write_bytes(b"pre-existing occupant")
    elif occupant == "directory":
        target.mkdir()
    else:
        overrides[str(target)] = "reparse_point"
    creates = []
    monkeypatch.setattr(pi_profile_discovery, "_create_exclusive", lambda path, data: creates.append(path))
    outcome = _run(world, proof_leaves=_proof_leaves_with(_inspect_overriding(overrides)))
    assert outcome.code == DISCOVERY_REFUSED_STAGING_TARGET_OCCUPIED
    assert creates == []
    if occupant == "file":
        assert target.read_bytes() == b"pre-existing occupant"
    if occupant == "directory":
        assert target.is_dir() and list(target.iterdir()) == []


@pytest.mark.parametrize("fail_at", [2, 3])
def test_a18_a_mid_sequence_failure_leaves_residue_and_deletes_nothing(world, staging, monkeypatch, fail_at):
    real_create = pi_profile_discovery._create_exclusive
    count = {"n": 0}

    def _create(path, data):
        count["n"] += 1
        if count["n"] == fail_at:
            raise OSError("injected write failure")
        return real_create(path, data)

    monkeypatch.setattr(pi_profile_discovery, "_create_exclusive", _create)
    outcome = _run(world)
    assert outcome.code == DISCOVERY_STAGING_WRITE_FAILED_RESIDUE_LEFT
    fingerprint = outcome.payload_fingerprint
    expected_residue = [fingerprint + suffix for suffix in _SUFFIXES[: fail_at - 1]]
    assert list(outcome.staged_files) == expected_residue
    assert staging_listing(staging) == sorted(expected_residue)
    assert not (staging / (fingerprint + ".candidate.json")).exists()
    residue = {name: (staging / name).read_bytes() for name in expected_residue}

    # A repeat discovery of the same fingerprint refuses at the precheck and
    # leaves the residue byte-identical.
    monkeypatch.setattr(pi_profile_discovery, "_create_exclusive", real_create)
    again = _run(world)
    assert again.code == DISCOVERY_REFUSED_STAGING_TARGET_OCCUPIED
    assert {name: (staging / name).read_bytes() for name in expected_residue} == residue


def test_a18_a_collision_at_create_time_is_refused_and_the_occupant_kept(world, staging, monkeypatch):
    """Raced occupant planted after the precheck: ``xb`` refuses it."""
    real_create = pi_profile_discovery._create_exclusive

    def _create(path, data):
        if path.endswith(".manifest_bundle.json"):
            Path(path).write_bytes(b"raced occupant")
        return real_create(path, data)

    monkeypatch.setattr(pi_profile_discovery, "_create_exclusive", _create)
    outcome = _run(world)
    assert outcome.code == DISCOVERY_STAGING_WRITE_FAILED_RESIDUE_LEFT
    bundle = staging / (outcome.payload_fingerprint + ".manifest_bundle.json")
    assert bundle.read_bytes() == b"raced occupant"
    assert len(outcome.staged_files) == 1


def test_a18_an_artifact_over_its_bound_is_c5_and_nothing_is_written(world, staging, monkeypatch):
    monkeypatch.setattr(pi_manifest, "MAX_MANIFEST_BYTES", 10)
    outcome = _run(world)
    assert outcome.code == DISCOVERY_REFUSED_ARTIFACT_BOUND_EXCEEDED
    assert "  approvability C5_UNDER_HPP1" in outcome.console_lines
    assert not staging.exists()


def test_a18_static_audit_the_writer_has_exactly_one_mkdir_and_one_exclusive_open():
    tree = ast.parse((_PACKAGE_DIR / "pi_profile_discovery.py").read_text(encoding="utf-8"))
    destructive = {"unlink", "remove", "rmdir", "rmtree", "rename", "replace", "truncate", "makedirs", "move"}
    mkdirs, opens = [], []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        assert name not in destructive, (name, node.lineno)
        if name == "mkdir":
            mkdirs.append(node)
        if name == "open":
            opens.append(node)
    assert len(mkdirs) == 1 and not mkdirs[0].keywords and len(mkdirs[0].args) == 1
    assert len(opens) == 1
    assert isinstance(opens[0].func, ast.Name) and opens[0].args[1].value == "xb"
    assert "tempfile" not in ast.unparse(tree) and "shutil" not in ast.unparse(tree)


def test_a18_an_unexpected_failure_writes_nothing_and_escapes_no_text(world, staging, monkeypatch):
    def _explode(*args, **kwargs):
        raise RuntimeError("a distinctive needle 5c1e")

    monkeypatch.setattr(pi_profile_discovery, "compute_profile_facts", _explode)
    outcome = _run(world)
    assert outcome.code == "DISCOVERY_REFUSED_UNEXPECTED_FAILURE"
    assert "5c1e" not in "\n".join(outcome.console_lines)
    assert not staging.exists()


# ---------------------------------------------------------------------------
# A-19 -- non-authority (PE-2a share)
# ---------------------------------------------------------------------------


def test_a19_only_the_discovery_writer_references_the_staging_namespace():
    for source_path in sorted(_PACKAGE_DIR.glob("*.py")):
        source = source_path.read_text(encoding="utf-8")
        for needle in ("pi_profile_candidates", "_STAGING_DIRECTORY", "STAGING_DIRECTORY_NAME", "pi_profile_discovery"):
            if needle in source:
                assert source_path.name == "pi_profile_discovery.py", (source_path.name, needle)


def test_a19_no_pe2a_module_reads_a_staged_artifact_back():
    tree = ast.parse((_PACKAGE_DIR / "pi_profile_discovery.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            assert name not in ("read_bytes", "read_text", "load", "loads", "listdir", "scandir", "iterdir", "glob")
    for module_name in ("pi_payload", "pi_manifest", "pi_profile_floor"):
        source = (_PACKAGE_DIR / f"{module_name}.py").read_text(encoding="utf-8")
        assert "candidate.json" not in source and "aido-pi-profile-candidate" not in source


def test_a19_a_staged_candidate_never_changes_any_pe2a_computation(world, staging):
    first = _run(world)
    second_world_outcome = _run(world)  # same payload again
    assert second_world_outcome.code == DISCOVERY_REFUSED_STAGING_TARGET_OCCUPIED
    assert second_world_outcome.payload_fingerprint == first.payload_fingerprint
    # Tampering the staged candidate does not feed back into anything.
    candidate = staging / (first.payload_fingerprint + ".candidate.json")
    os.chmod(candidate, 0o666)
    candidate.write_bytes(b'{"authority":"APPROVED","floor":"C1"}\n')
    third = _run(world)
    assert third.payload_fingerprint == first.payload_fingerprint
    assert third.code == DISCOVERY_REFUSED_STAGING_TARGET_OCCUPIED


# ---------------------------------------------------------------------------
# Adversarial: exposures, raw keys in console, nested reparse via discovery
# ---------------------------------------------------------------------------


def test_discovery_with_an_uncontained_dependency_observes_upward_absence(tmp_path, staging):
    files, empty_dirs = synthetic_payload_files()
    files = dict(files)
    files["package.json"] = manifest_bytes(root_manifest(peerDependencies={"@ext/peer": "1"}))
    world = DiscoveryWorld(tmp_path / "world", files, empty_dirs)
    base = str(world.base)
    observed = []
    real = pi_fs_leaves.inspect_no_follow

    def _inspect(path):
        if "\\node_modules\\@ext" in path or path.endswith("\\node_modules") and not path.startswith(base):
            observed.append(path)
            if not path.startswith(base):
                return NoFollowObservation("missing", None)
        return real(path)

    outcome = _run(world, proof_leaves=_proof_leaves_with(_inspect))
    assert outcome.code == DISCOVERY_CANDIDATE_STAGED
    candidate = json.loads((staging / (outcome.payload_fingerprint + ".candidate.json")).read_bytes())
    assert candidate["resolution_exposures"] == ["@ext/peer"]
    assert candidate["exposure_absence_observation"] == "EXPOSURES_PROVEN_ABSENT"
    assert candidate["profile_id"] == compute_profile_id(outcome.payload_fingerprint, ["@ext/peer"])

    # Plant the exposure in an ancestor node_modules: now present.
    planted = world.npm_dir / "node_modules" / "@ext" / "peer"
    planted.mkdir(parents=True)
    (world.payload_root / "dist" / "other.js").write_bytes(b"new payload so the target is free")
    outcome = _run(world, proof_leaves=_proof_leaves_with(_inspect))
    candidate = json.loads((staging / (outcome.payload_fingerprint + ".candidate.json")).read_bytes())
    assert candidate["exposure_absence_observation"] == "EXPOSURE_PRESENT_OR_UNOBSERVABLE"
    assert candidate["exposure_present_or_unobservable"] == "@ext/peer"


@pytest.mark.parametrize("key", ["../needle-x", "@scope/../needle-x", "C:\\needle-x", "needle-X", "\\\\needle\\share"])
def test_discovery_never_renders_a_refused_raw_key_and_observes_no_key_path(tmp_path, staging, key):
    files, empty_dirs = synthetic_payload_files()
    files = dict(files)
    files["package.json"] = manifest_bytes(root_manifest(optionalDependencies={key: "1"}))
    world = DiscoveryWorld(tmp_path / "world", files, empty_dirs)
    seen = []
    real = pi_fs_leaves.inspect_no_follow

    def _inspect(path):
        seen.append(path)
        return real(path)

    outcome = _run(world, proof_leaves=_proof_leaves_with(_inspect))
    assert outcome.code == DISCOVERY_CANDIDATE_STAGED
    assert not any("needle" in path.lower() for path in seen)
    text = "\n".join(outcome.console_lines)
    assert "needle" not in text.lower()
    assert "  c5_reason PACKAGE_NAME_OUTSIDE_HPP1_GRAMMAR" in outcome.console_lines
    assert "  c5_manifest_path package.json" in outcome.console_lines
    candidate = (staging / (outcome.payload_fingerprint + ".candidate.json")).read_bytes()
    assert b"needle" not in candidate.lower()
    assert json.loads(candidate)["profile_id"] is None


def test_discovery_refuses_a_nested_reparse_point_with_nothing_written(world, staging):
    genuine = genuine_payload_leaves()
    nested = str(world.payload_root / "node_modules" / "left-pad" / "node_modules")

    def _enumerate(path, budget):
        listing = genuine.enumerate_directory(path, budget)
        if path == os.path.dirname(nested) and listing.entries is not None:
            entries = tuple((n, "reparse" if n == "node_modules" else k) for n, k in listing.entries)
            return pi_fs_leaves.DirectoryListing("directory", True, False, entries)
        return listing

    outcome = _run(world, payload_leaves=PayloadLeaves(enumerate_directory=_enumerate, read_file=genuine.read_file))
    assert outcome.code == DISCOVERY_REFUSED_PAYLOAD_UNPROVEN
    assert "  PAYLOAD_REPARSE_POINT" in outcome.console_lines
    assert not staging.exists()


def test_discovery_does_not_alter_the_canonical_proof(world, staging, monkeypatch):
    """Discovery reuses P1's functions; P itself is untouched and still refuses
    a synthetic tree whose seams do not match the historical pin table."""
    from pi_harness_cfg1.pi_identity import PI_SEAM_UNPROVEN, prove_pi_identity

    _run(world)
    result = prove_pi_identity({"PATH": world.path_value}, leaves=genuine_pi_proof_leaves())
    assert result.failure_code == PI_SEAM_UNPROVEN


# ---------------------------------------------------------------------------
# Post-implementation self-review regressions
# ---------------------------------------------------------------------------


def test_review_console_lines_are_ascii_even_for_a_non_ascii_payload_path(tmp_path, staging):
    """A grammar-valid path with a bidi override must not reach the console raw."""
    files, empty_dirs = synthetic_payload_files()
    files = dict(files)
    spoof = "dist/\u202eevil/node_modules/x/package.json"
    files[spoof] = b"[]"  # a package root whose manifest is not an object -> C5
    world = DiscoveryWorld(tmp_path / "world", files, empty_dirs)
    outcome = _run(world)
    assert outcome.code == DISCOVERY_CANDIDATE_STAGED
    for line in outcome.console_lines:
        assert line.isascii(), line
    assert "  c5_manifest_path dist/\\u202eevil/node_modules/x/package.json" in outcome.console_lines
    assert "\u202e" not in "\n".join(outcome.console_lines)
