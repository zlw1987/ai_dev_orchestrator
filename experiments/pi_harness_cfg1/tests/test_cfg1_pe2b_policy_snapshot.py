"""PE-2b: the sealed snapshot, the single genuine load site, import-time
failure, the offline evidence-reference verifier, the loader-owned head
reference view, and staging non-authority.

Acceptance rows B-10, B-11, B-15 (its loader-owned half) and B-16 of
``docs/PHASE_5F3B_PI_HARNESS_PROFILE_EVOLUTION_PE1_AMENDMENT.md`` Sec. 26.2,
plus adversarial regressions derived from the implementation. Synthetic
chains and synthetic checkouts live under ``tmp_path``; link components are
injected through doubles, never real links. Nothing here runs Pi, Node or npm
or reads a credential.
"""

from __future__ import annotations

import ast
import copy
import importlib
import inspect
import pickle
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from pe2a_support import facts_for, synthetic_payload_files
from pe2b_support import (
    SYNTHETIC_REF,
    Chain,
    PolicyWorld,
    approval,
    base_payload,
    non_seam_payload,
    retirement,
    seam_change_payload,
    two_profile_chain,
    version_bump_payload,
)
from test_cfg1_pe2b_policy_chain import LeafDouble

import pi_harness_cfg1
from ai_dev_orchestrator.workspace import canonical
from pi_harness_cfg1 import pi_profile_evidence_verifier as verifier
from pi_harness_cfg1 import pi_profile_floor
from pi_harness_cfg1 import pi_profile_policy_loader as loader
from pi_harness_cfg1.pi_profile_evidence_verifier import Cfg1EvidenceReferenceError
from pi_harness_cfg1.pi_profile_floor import (
    FLOOR_C1,
    FLOOR_C1R,
    FLOOR_C2,
    FLOOR_C3_SEAM_CHANGED,
    FLOOR_C3_SEAM_EQUAL,
    FLOOR_C5,
    ReferenceView,
    classify_floor,
)
from pi_harness_cfg1.pi_profile_policy_loader import (
    Cfg1EligibleProfileView,
    Cfg1PolicyError,
    Cfg1PolicySnapshot,
)

_PACKAGE_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _PACKAGE_DIR.parents[1]
_LOADER_SOURCE = (_PACKAGE_DIR / "pi_profile_policy_loader.py").read_text(encoding="utf-8")
_VERIFIER_SOURCE = (_PACKAGE_DIR / "pi_profile_evidence_verifier.py").read_text(encoding="utf-8")


def _load(tmp_path, chain: Chain):
    world = PolicyWorld(tmp_path)
    world.write_chain(chain)
    return world.load()


def _retired_chain():
    """A eligible (r1), S approved (r2) then retired (r3), B = A' (C2, r4)."""
    a = base_payload()
    s = seam_change_payload()
    chain = Chain()
    chain.revision(profiles=[a.profile()], approvals=[approval(a.profile_id, "C3_SEAM_CHANGED")], payloads=[a])
    chain.revision(profiles=[s.profile()], approvals=[approval(s.profile_id, "C3_SEAM_CHANGED")], payloads=[s])
    chain.revision(retirements=[retirement(s.profile_id)])
    return chain, a, s


# ---------------------------------------------------------------------------
# B-10 -- the offline evidence-reference verifier
# ---------------------------------------------------------------------------


@pytest.fixture()
def checkout(tmp_path) -> Path:
    root = tmp_path / "synthetic_checkout"
    (root / "docs" / "review").mkdir(parents=True)
    (root / "docs" / "review" / "design.md").write_bytes(b"# synthetic design\nline two\n")
    return root


def _digest(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _verify(root: Path, repo_path, sha256):
    return verifier._verify_reference_under(str(root), repo_path, sha256)


def _verify_refuses(root: Path, repo_path, sha256, code: str) -> None:
    with pytest.raises(Cfg1EvidenceReferenceError) as caught:
        _verify(root, repo_path, sha256)
    assert caught.value.reason_code == code


def test_b10_a_contained_regular_file_with_its_exact_digest_verifies(checkout):
    data = (checkout / "docs" / "review" / "design.md").read_bytes()
    assert _verify(checkout, "docs/review/design.md", _digest(data)) == verifier.EVIDENCE_REFERENCE_VERIFIED


@pytest.mark.parametrize(
    "repo_path",
    [
        "..",
        "../outside.md",
        "docs/../../outside.md",
        "docs/./review/design.md",
        "/docs/review/design.md",
        "C:/Windows/win.ini",
        "C:docs/review/design.md",
        "C:\\Windows\\win.ini",
        "//server/share/x.md",
        "\\\\server\\share\\x.md",
        "//./COM1",
        "\\\\.\\COM1",
        "\\\\?\\C:\\x.md",
        "docs\\review\\design.md",
        "docs/review/design.md:stream",
        "docs//review/design.md",
        "docs/review/design.md/",
        "",
        None,
        7,
    ],
)
def test_b10_traversal_absolute_drive_unc_and_device_forms_refuse(checkout, repo_path):
    _verify_refuses(checkout, repo_path, "ab" * 32, "EVIDENCE_REPO_PATH_GRAMMAR")


def test_b10_a_grammar_valid_but_ambiguous_component_refuses_in_the_canonical_layer(checkout):
    data = (checkout / "docs" / "review" / "design.md").read_bytes()
    _verify_refuses(checkout, "docs/review/design.md.", _digest(data), "EVIDENCE_PATH_AMBIGUOUS")


def test_b10_a_link_component_refuses(checkout, monkeypatch):
    seen: list[str] = []
    real_lstat = canonical._lstat
    real_is_link = canonical._is_symlink_or_reparse_point

    def _lstat(path, *, role):
        seen.append(str(path))
        return real_lstat(path, role=role)

    def _is_link(stat_result):
        return real_is_link(stat_result) or seen[-1].endswith("\\docs\\review")

    monkeypatch.setattr(canonical, "_lstat", _lstat)
    monkeypatch.setattr(canonical, "_is_symlink_or_reparse_point", _is_link)
    data = (checkout / "docs" / "review" / "design.md").read_bytes()
    _verify_refuses(checkout, "docs/review/design.md", _digest(data), "EVIDENCE_PATH_LINK_COMPONENT")


def test_b10_a_linked_checkout_root_refuses(checkout, monkeypatch):
    real_lstat = canonical._lstat
    seen: list[str] = []

    def _lstat(path, *, role):
        seen.append(str(path))
        return real_lstat(path, role=role)

    monkeypatch.setattr(canonical, "_lstat", _lstat)
    monkeypatch.setattr(canonical, "_is_symlink_or_reparse_point", lambda stat_result: seen[-1] == str(checkout))
    _verify_refuses(checkout, "docs/review/design.md", "ab" * 32, "EVIDENCE_PATH_LINK_COMPONENT")


def test_b10_a_non_regular_target_refuses(checkout):
    _verify_refuses(checkout, "docs/review", "ab" * 32, "EVIDENCE_NOT_A_REGULAR_FILE")


def test_b10_a_missing_target_refuses(checkout):
    _verify_refuses(checkout, "docs/review/missing.md", "ab" * 32, "EVIDENCE_PATH_MISSING_OR_INVALID")


def test_b10_a_digest_mismatch_refuses_and_nothing_is_normalized(checkout):
    target = checkout / "docs" / "review" / "design.md"
    lf = target.read_bytes()
    _verify_refuses(checkout, "docs/review/design.md", "00" * 32, "EVIDENCE_DIGEST_MISMATCH")
    target.write_bytes(lf.replace(b"\n", b"\r\n"))
    _verify_refuses(checkout, "docs/review/design.md", _digest(lf), "EVIDENCE_DIGEST_MISMATCH")


@pytest.mark.parametrize("sha256", ["AB" * 32, "ab" * 31, None, 1, "zz" * 32])
def test_b10_a_malformed_digest_refuses_before_any_filesystem_access(checkout, monkeypatch, sha256):
    monkeypatch.setattr(
        verifier, "canonicalize_existing_path_under_workspace", lambda *a, **k: pytest.fail("filesystem touched")
    )
    _verify_refuses(checkout, "docs/review/design.md", sha256, "EVIDENCE_DIGEST_MALFORMED")


def test_b10_the_public_verifier_uses_its_own_module_derived_checkout_root(checkout, monkeypatch):
    assert verifier._CHECKOUT_ROOT == str(Path(verifier.__file__).resolve().parents[2])
    assert verifier._CHECKOUT_ROOT == str(_REPO_ROOT)
    assert list(inspect.signature(verifier.verify_evidence_reference).parameters) == ["repo_path", "sha256"]
    assert list(inspect.signature(verifier.verify_evidence_references).parameters) == ["refs"]
    monkeypatch.setattr(verifier, "_CHECKOUT_ROOT", str(checkout))
    data = (checkout / "docs" / "review" / "design.md").read_bytes()
    refs = [{"repo_path": "docs/review/design.md", "sha256": _digest(data)}] * 2
    assert verifier.verify_evidence_references(refs) == 2
    with pytest.raises(Cfg1EvidenceReferenceError):
        verifier.verify_evidence_references(refs + [{"repo_path": "docs/review/design.md", "sha256": "00" * 32}])
    for bad in ("x", [{"repo_path": "a"}], [{"repo_path": "a", "sha256": "b", "x": 1}]):
        with pytest.raises(Cfg1EvidenceReferenceError) as caught:
            verifier.verify_evidence_references(bad)
        assert caught.value.reason_code == "EVIDENCE_REFS_MALFORMED"


def test_b10_the_verifier_composes_the_existing_canonical_guard_with_allow_symlinks_false(checkout, monkeypatch):
    calls: list = []
    real = verifier.canonicalize_existing_path_under_workspace

    def _recording(root, candidate, **kwargs):
        calls.append((root, candidate, kwargs))
        return real(root, candidate, **kwargs)

    monkeypatch.setattr(verifier, "canonicalize_existing_path_under_workspace", _recording)
    data = (checkout / "docs" / "review" / "design.md").read_bytes()
    _verify(checkout, "docs/review/design.md", _digest(data))
    assert calls == [(str(checkout), "docs/review/design.md", {"allow_symlinks": False})]
    assert real is canonical.canonicalize_existing_path_under_workspace


def test_b10_the_runtime_loader_never_references_the_verifier():
    for needle in (
        "pi_profile_evidence_verifier",
        "verify_evidence",
        "canonicalize_existing_path_under_workspace",
        "ai_dev_orchestrator",
        "_CHECKOUT_ROOT",
    ):
        assert needle not in _LOADER_SOURCE, needle


def test_b10_the_runtime_loader_never_calls_the_verifier_or_opens_a_reference(tmp_path, monkeypatch):
    tripped: list = []

    def _tripwire(name):
        def _call(*args, **kwargs):
            tripped.append(name)
            raise AssertionError(name)

        return _call

    for name in ("_verify_reference_under", "verify_evidence_reference", "verify_evidence_references"):
        monkeypatch.setattr(verifier, name, _tripwire(name))
    monkeypatch.setattr(canonical, "canonicalize_existing_path_under_workspace", _tripwire("canonical"))
    chain, _a, _b = two_profile_chain()
    world = PolicyWorld(tmp_path)
    world.write_chain(chain)
    double = LeafDouble()
    world.load(**double.leaves())
    assert tripped == []
    policy = str(world.dir)
    assert double.read and all(path.startswith(policy + "\\") for path in double.read)
    assert not any("docs" in path.split("\\") for path in double.read + double.enumerated)


def test_b10_importing_the_loader_does_not_import_the_verifier():
    probe = (
        "import sys\n"
        "sys.path[:0] = ['src', 'experiments']\n"
        "import pi_harness_cfg1.pi_profile_policy_loader\n"
        "print('pi_harness_cfg1.pi_profile_evidence_verifier' in sys.modules)\n"
    )
    completed = subprocess.run(  # noqa: S603 - fixed argv, shell=False, offline import probe
        [sys.executable, "-I", "-c", probe],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    assert completed.stdout.decode("ascii").strip() == "False"


# ---------------------------------------------------------------------------
# B-11 -- snapshot unforgeability, immutability, the ONE genuine load site
# ---------------------------------------------------------------------------


def test_b11_the_snapshot_and_views_are_not_constructible_outside_the_loader():
    with pytest.raises(Cfg1PolicyError):
        Cfg1PolicySnapshot(object(), aps_revision=1, aps_head_sha256="0" * 64, policy_directory="C:\\x", eligible_profiles=())
    with pytest.raises(Cfg1PolicyError):
        Cfg1EligibleProfileView(
            object(), profile_id="0" * 64, payload_fingerprint="0" * 64, resolution_exposures=(), declared_package_version="1"
        )
    with pytest.raises(Cfg1PolicyError):
        loader._HeadReferenceMaterial(object(), eligible_payloads=(), present_ineligible_profile_ids=frozenset(), seam_fingerprints=frozenset())
    with pytest.raises(Cfg1PolicyError):
        loader._PolicyLoad(object(), snapshot=None, head_reference=None, revisions=())


def test_b11_the_snapshot_is_immutable_and_cannot_be_copied_pickled_or_subclassed(tmp_path):
    chain, _a, _b = two_profile_chain()
    load = _load(tmp_path, chain)
    targets = [load, load.snapshot, load.head_reference, *load.snapshot.eligible_profiles, loader.SEALED_POLICY_SNAPSHOT]
    for target in targets:
        for name in type(target).__slots__:
            with pytest.raises(AttributeError):
                setattr(target, name, None)
            with pytest.raises(AttributeError):
                delattr(target, name)
        with pytest.raises(AttributeError):
            target.extra = 1
        with pytest.raises(TypeError):
            copy.copy(target)
        with pytest.raises(TypeError):
            copy.deepcopy(target)
        with pytest.raises(TypeError):
            pickle.dumps(target)
    for cls in (Cfg1PolicySnapshot, Cfg1EligibleProfileView, loader._HeadReferenceMaterial, loader._PolicyLoad):
        with pytest.raises(TypeError):
            type("Forged", (cls,), {"__slots__": ()})


def _immutable_graph(value, seen=None) -> None:
    seen = set() if seen is None else seen
    if id(value) in seen:
        return
    seen.add(id(value))
    kind = type(value)
    if kind in (str, int, bytes, type(None)):
        return
    if kind in (tuple, frozenset):
        for item in value:
            _immutable_graph(item, seen)
        return
    if kind in (Cfg1PolicySnapshot, Cfg1EligibleProfileView, loader._HeadReferenceMaterial, loader._PolicyLoad):
        for name in kind.__slots__:
            _immutable_graph(getattr(value, name), seen)
        return
    raise AssertionError(f"mutable or unexpected object reachable from the snapshot: {kind!r}")


def test_b11_nothing_mutable_is_reachable_from_the_sealed_load(tmp_path):
    from pe2b_support import exposed_payload

    chain, a, b = two_profile_chain()
    e = exposed_payload()
    chain.revision(profiles=[e.profile()], approvals=[approval(e.profile_id, "C3_SEAM_CHANGED")], payloads=[e])
    load = _load(tmp_path, chain)
    _immutable_graph(load)
    _immutable_graph(loader._GENUINE_POLICY_LOAD)
    assert set(Cfg1PolicySnapshot.__slots__) == {
        "policy_revision",
        "payload_contract",
        "seam_contract",
        "consumer_contract",
        "aps_revision",
        "aps_head_sha256",
        "policy_directory",
        "eligible_profile_ids",
        "eligible_profiles",
    }
    assert set(Cfg1EligibleProfileView.__slots__) == {
        "profile_id",
        "payload_fingerprint",
        "resolution_exposures",
        "declared_package_version",
    }
    views = {view.profile_id: view for view in load.snapshot.eligible_profiles}
    assert views[e.profile_id].resolution_exposures == (("@ghost", "pkg"), ("missing-dep",))
    assert load.snapshot.eligible_profile_ids == frozenset(views)


def test_b11_the_public_surface_has_no_loader_reload_setter_or_path_parameter():
    public_functions = {
        name
        for name, value in vars(loader).items()
        if not name.startswith("_") and inspect.isfunction(value) and value.__module__ == loader.__name__
    }
    assert public_functions == {"repo_path_is_valid", "head_reference_view"}
    assert list(inspect.signature(loader.head_reference_view).parameters) == []
    assert list(inspect.signature(loader.repo_path_is_valid).parameters) == ["value"]
    for forbidden in ("reload", "load", "load_policy", "set_snapshot", "replace_snapshot", "refresh"):
        assert not hasattr(loader, forbidden), forbidden


def _production_sources() -> list[Path]:
    return sorted(_PACKAGE_DIR.glob("*.py"))


def test_b11_ast_audit_exactly_one_genuine_load_site():
    sites = []
    for path in _production_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
                if name == "_load_policy_directory":
                    sites.append((path.name, node))
            if isinstance(node, ast.Name) and node.id == "_load_policy_directory" and path.name != "pi_profile_policy_loader.py":
                pytest.fail(f"{path.name} references the private loader")
    assert len(sites) == 1
    (module_name, call) = sites[0]
    assert module_name == "pi_profile_policy_loader.py"
    assert len(call.args) == 1 and not call.keywords
    assert isinstance(call.args[0], ast.Name) and call.args[0].id == "_POLICY_DIR"
    tree = ast.parse(_LOADER_SOURCE)
    owning = [
        node
        for node in tree.body
        if any(
            isinstance(sub, ast.Call) and getattr(sub.func, "id", "") == "_load_policy_directory"
            for sub in ast.walk(node)
        )
    ]
    # The one call is a MODULE-LEVEL assignment (executed once, at import),
    # never inside a function that a caller could invoke again.
    assert len(owning) == 1
    assert isinstance(owning[0], ast.AnnAssign) and owning[0].target.id == "_GENUINE_POLICY_LOAD"


def test_b11_ast_audit_the_policy_directory_derives_only_from_file():
    tree = ast.parse(_LOADER_SOURCE)
    stores: dict[str, list] = {"_POLICY_DIR": [], "_CFG1_PACKAGE_DIRECTORY": []}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in stores and isinstance(node.ctx, ast.Store):
            stores[node.id].append(node)
    assert len(stores["_POLICY_DIR"]) == 1 and len(stores["_CFG1_PACKAGE_DIRECTORY"]) == 1
    assignments = {
        node.target.id: node.value
        for node in tree.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert ast.unparse(assignments["_CFG1_PACKAGE_DIRECTORY"]) == "str(Path(__file__).resolve().parent)"
    assert ast.unparse(assignments["_POLICY_DIR"]) == "ntpath.join(_CFG1_PACKAGE_DIRECTORY, POLICY_DIRECTORY_NAME)"
    assert loader.POLICY_DIRECTORY_NAME == "pi_profile_policy"
    assert loader._POLICY_DIR == str(_PACKAGE_DIR / "pi_profile_policy")
    assert loader.SEALED_POLICY_SNAPSHOT is loader._GENUINE_POLICY_LOAD.snapshot
    assert loader.SEALED_POLICY_SNAPSHOT.policy_directory == loader._POLICY_DIR


def test_b11_the_policy_module_reads_no_environment_and_starts_no_process():
    tree = ast.parse(_LOADER_SOURCE)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        if isinstance(node, ast.ImportFrom) and node.level == 0:
            imported.add(node.module)
    assert imported <= {"__future__", "hashlib", "json", "ntpath", "re", "pathlib"}
    forbidden_names = {
        "environ",
        "getenv",
        "putenv",
        "open",
        "write",
        "mkdir",
        "makedirs",
        "unlink",
        "remove",
        "rename",
        "rmdir",
        "system",
        "Popen",
        "run",
        "chdir",
        "getcwd",
        "socket",
        "import_module",
        "exec",
        "eval",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            assert node.id not in forbidden_names, (node.id, node.lineno)
        if isinstance(node, ast.Attribute):
            assert node.attr not in forbidden_names, (node.attr, node.lineno)
    # The only filesystem access is through the two injected no-follow leaves.
    assert "pi_fs_leaves.enumerate_directory_no_follow" in _LOADER_SOURCE
    assert "pi_fs_leaves.read_payload_file_bytes" in _LOADER_SOURCE


def test_b11_a_fresh_copy_under_a_hostile_cwd_and_environment_derives_the_same_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in ("AIDO_PI_PROFILE_POLICY", "PI_PROFILE_POLICY", "POLICY_DIR", "PWD"):
        monkeypatch.setenv(name, str(tmp_path))
    spec = importlib.util.spec_from_file_location("pi_harness_cfg1._pe2b_fresh_loader_probe", loader.__file__)
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)
    assert fresh._POLICY_DIR == loader._POLICY_DIR == str(_REPO_ROOT / "experiments" / "pi_harness_cfg1" / "pi_profile_policy")
    assert fresh.SEALED_POLICY_SNAPSHOT.aps_head_sha256 == loader.SEALED_POLICY_SNAPSHOT.aps_head_sha256
    assert fresh.SEALED_POLICY_SNAPSHOT is not loader.SEALED_POLICY_SNAPSHOT


# -- import-time behaviour through a COPY of the module in a tmp package path


_PROBE = "_pe2b_import_probe_loader"


@pytest.fixture()
def probe_package(tmp_path, monkeypatch):
    """A tmp directory on ``pi_harness_cfg1.__path__`` holding a COPY of the
    loader module, so its ``__file__``-derived policy directory is synthetic
    while its relative imports resolve to the genuine PE-2a modules."""
    probe_dir = tmp_path / "probe_pkg"
    probe_dir.mkdir()
    shutil.copyfile(loader.__file__, probe_dir / (_PROBE + ".py"))
    monkeypatch.setattr(pi_harness_cfg1, "__path__", list(pi_harness_cfg1.__path__) + [str(probe_dir)])
    importlib.invalidate_caches()
    yield probe_dir
    sys.modules.pop("pi_harness_cfg1." + _PROBE, None)
    importlib.invalidate_caches()


def _import_probe():
    return importlib.import_module("pi_harness_cfg1." + _PROBE)


def test_b11_an_absent_policy_directory_makes_the_module_fail_to_import(probe_package):
    with pytest.raises(Exception) as caught:
        _import_probe()
    assert type(caught.value).__name__ == "Cfg1PolicyError"
    assert caught.value.reason_code == "POLICY_DIRECTORY_NOT_PLAIN"
    assert "pi_harness_cfg1." + _PROBE not in sys.modules
    with pytest.raises(Exception):
        _import_probe()


@pytest.mark.parametrize("damage", ["stray", "cr", "tamper", "empty_aps"])
def test_b11_a_malformed_chain_makes_the_module_fail_to_import_and_never_falls_open(probe_package, damage):
    world = PolicyWorld(probe_package)
    world.write_chain(two_profile_chain()[0])
    if damage == "stray":
        (world.aps / "notes.txt").write_bytes(b"x")
    elif damage == "cr":
        path = world.aps / "aps.r0001.json"
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    elif damage == "tamper":
        path = world.aps / "aps.r0002.json"
        path.write_bytes(path.read_bytes().replace(b"C2_MANIFEST_ONLY", b"C3_SEAM_CHANGED"))
    else:
        for path in world.aps.iterdir():
            path.unlink()
    for _attempt in range(2):
        with pytest.raises(Exception) as caught:
            _import_probe()
        assert type(caught.value).__name__ == "Cfg1PolicyError"
        assert "pi_harness_cfg1." + _PROBE not in sys.modules


def test_b11_a_valid_synthetic_chain_imports_and_a_later_revision_never_changes_the_snapshot(probe_package):
    chain, a, b = two_profile_chain()
    world = PolicyWorld(probe_package)
    world.write_chain(chain)
    module = _import_probe()
    snapshot = module.SEALED_POLICY_SNAPSHOT
    head = snapshot.aps_head_sha256
    assert snapshot.eligible_profile_ids == frozenset({a.profile_id, b.profile_id})
    assert snapshot.policy_directory == str(world.dir)
    # A later APS revision appears on disk after the sealed load.
    chain.revision(retirements=[retirement(a.profile_id)])
    world.write_chain(chain)
    assert module.SEALED_POLICY_SNAPSHOT is snapshot
    assert snapshot.aps_head_sha256 == head and snapshot.aps_revision == 2
    assert snapshot.eligible_profile_ids == frozenset({a.profile_id, b.profile_id})
    assert _import_probe() is module  # an import is not a reload
    reference = module.head_reference_view()
    assert {facts.profile_id for facts in reference.eligible} == {a.profile_id, b.profile_id}


# ---------------------------------------------------------------------------
# B-15 -- the loader-owned head reference view and the accepted classifier
# ---------------------------------------------------------------------------


def test_b15_the_reference_view_is_the_accepted_pe2a_type_and_classifier(tmp_path):
    chain, a, s = _retired_chain()
    load = _load(tmp_path, chain)
    view = loader._reference_view_from_material(load.head_reference)
    assert type(view) is ReferenceView and ReferenceView is pi_profile_floor.ReferenceView
    assert loader.classify_floor is pi_profile_floor.classify_floor is classify_floor
    assert [facts.profile_id for facts in view.eligible] == [a.profile_id]
    assert view.present_ineligible_profile_ids == frozenset({s.profile_id})


def test_b15_floors_against_a_committed_synthetic_aps(tmp_path):
    chain, a, s = _retired_chain()
    load = _load(tmp_path, chain)
    view = loader._reference_view_from_material(load.head_reference)
    files, empty_dirs = synthetic_payload_files()
    del files["dist/cli.js"]
    c5 = facts_for(files, empty_dirs)
    cases = [
        (a.facts, FLOOR_C1),
        (s.facts, FLOOR_C1R),
        (version_bump_payload().facts, FLOOR_C2),
        (non_seam_payload().facts, FLOOR_C3_SEAM_EQUAL),
        (seam_change_payload("dist/core/sdk.js").facts, FLOOR_C3_SEAM_CHANGED),
        (c5, FLOOR_C5),
    ]
    for facts, expected in cases:
        assert classify_floor(facts, view) == expected


def test_b15_every_call_rebuilds_fresh_facts_from_committed_bytes(tmp_path):
    chain, a, _s = _retired_chain()
    load = _load(tmp_path, chain)
    first = loader._reference_view_from_material(load.head_reference)
    second = loader._reference_view_from_material(load.head_reference)
    assert first is not second
    assert first.eligible[0] is not second.eligible[0]
    assert first.eligible[0].inventory is not second.eligible[0].inventory
    # Post-validation mutation of a handed-out view cannot reach the next one,
    # the snapshot, or the committed bytes.
    first.eligible[0]._parsed_root_manifests["package.json"]["version"] = "6.6.6"
    first.eligible[0].inventory._index.clear()
    third = loader._reference_view_from_material(load.head_reference)
    assert classify_floor(version_bump_payload().facts, third) == FLOOR_C2
    assert classify_floor(a.facts, third) == FLOOR_C1
    assert third.eligible[0].parsed_root_manifest("package.json")["version"] == "1.0.0"
    assert load.snapshot.eligible_profile_ids == frozenset({a.profile_id})


def test_b15_the_genuine_genesis_view_never_yields_c1_or_c2():
    view = loader.head_reference_view()
    assert view is not loader.head_reference_view()
    for payload in (base_payload(), version_bump_payload(), non_seam_payload()):
        assert classify_floor(payload.facts, view) == FLOOR_C3_SEAM_CHANGED


def test_b15_the_reference_material_holds_only_committed_bytes_and_ids(tmp_path):
    chain, a, s = _retired_chain()
    material = _load(tmp_path, chain).head_reference
    ((profile_id, fingerprint, inventory_bytes, bundle_bytes),) = material.eligible_payloads
    assert (profile_id, fingerprint) == (a.profile_id, a.fingerprint)
    assert inventory_bytes == a.inventory_bytes and bundle_bytes == a.bundle_bytes
    assert type(inventory_bytes) is bytes and type(bundle_bytes) is bytes
    with pytest.raises(Cfg1PolicyError):
        loader._reference_view_from_material("not material")


# ---------------------------------------------------------------------------
# B-16 -- the loader never references or reads <STAGING>
# ---------------------------------------------------------------------------

_STAGING_NEEDLES = (
    "pi_profile_candidates",
    "_STAGING_DIRECTORY",
    "STAGING_DIRECTORY_NAME",
    "pi_profile_discovery",
    "candidate.json",
    "aido-pi-profile-candidate",
)


@pytest.mark.parametrize("source", [_LOADER_SOURCE, _VERIFIER_SOURCE], ids=["loader", "verifier"])
def test_b16_static_audit_no_staging_reference(source):
    for needle in _STAGING_NEEDLES:
        assert needle not in source, needle


def test_b16_a_staged_candidate_never_changes_the_loaded_chain(tmp_path):
    chain, a, b = two_profile_chain()
    world = PolicyWorld(tmp_path)
    world.write_chain(chain)
    baseline = world.load()
    staging = tmp_path / "pi_profile_candidates"
    staging.mkdir()
    newcomer = version_bump_payload("7.7.7")
    (staging / (newcomer.fingerprint + ".inventory.json")).write_bytes(newcomer.inventory_bytes)
    (staging / (newcomer.fingerprint + ".manifest_bundle.json")).write_bytes(newcomer.bundle_bytes)
    (staging / (newcomer.fingerprint + ".candidate.json")).write_bytes(
        b'{"authority":"APPROVED","floor":"C1","profile_id":"' + newcomer.profile_id.encode() + b'"}\n'
    )
    forged = Chain()
    forged.records = list(chain.records)
    forged.lists = {name: list(values) for name, values in chain.lists.items()}
    forged.revision(profiles=[newcomer.profile()], approvals=[approval(newcomer.profile_id, "C3_SEAM_CHANGED")])
    (staging / "aps.r0003.json").write_bytes(forged.file_bytes()[-1])
    double = LeafDouble()
    after = world.load(**double.leaves())
    assert not any("pi_profile_candidates" in path for path in double.read + double.enumerated)
    assert after.snapshot.aps_head_sha256 == baseline.snapshot.aps_head_sha256
    assert after.snapshot.eligible_profile_ids == baseline.snapshot.eligible_profile_ids
    assert newcomer.profile_id not in after.snapshot.eligible_profile_ids
    assert after.revisions == baseline.revisions


def test_b16_the_genuine_policy_and_staging_namespaces_are_disjoint_siblings():
    staging = str(_PACKAGE_DIR / "pi_profile_candidates")
    policy = loader._POLICY_DIR
    assert Path(policy).parent == Path(staging).parent == _PACKAGE_DIR
    assert not staging.startswith(policy) and not policy.startswith(staging + "\\")


# ---------------------------------------------------------------------------
# Additional adversarial regressions derived from the implementation
# ---------------------------------------------------------------------------


def test_adv_an_uninitialised_snapshot_shell_carries_no_authority():
    shell = Cfg1PolicySnapshot.__new__(Cfg1PolicySnapshot)
    with pytest.raises(AttributeError):
        _ = shell.eligible_profile_ids
    assert shell is not loader.SEALED_POLICY_SNAPSHOT


def test_adv_a_later_revision_that_edits_history_while_appending_refuses(tmp_path):
    chain, a, b = two_profile_chain()
    import json

    from pe2b_support import rechain, with_id

    records = [json.loads(item) for item in chain.file_bytes()]
    records.append(dict(copy.deepcopy(records[-1]), revision=3))
    edited = with_id(dict(records[2]["approvals"][1], acceptance_reference="REWRITTEN"), "approval_id")
    records[2]["approvals"][1] = edited
    world = PolicyWorld(tmp_path)
    world.write_chain(chain, rechain(records))
    with pytest.raises(Cfg1PolicyError) as caught:
        world.load()
    assert caught.value.reason_code == "POLICY_APS_NOT_APPEND_ONLY"


def test_adv_an_approval_flip_between_two_revisions_cannot_create_eligibility(tmp_path):
    """A retirement cannot be "undone" by dropping it in a later revision."""
    chain, a, b = two_profile_chain()
    chain.revision(retirements=[retirement(a.profile_id)])
    import json

    from pe2b_support import rechain

    records = [json.loads(item) for item in chain.file_bytes()]
    dropped = dict(records[-1], revision=4, retirements=[])
    world = PolicyWorld(tmp_path)
    world.write_chain(chain, rechain(records + [dropped]))
    with pytest.raises(Cfg1PolicyError) as caught:
        world.load()
    assert caught.value.reason_code == "POLICY_APS_NOT_APPEND_ONLY"


def test_adv_a_loader_double_cannot_inject_a_non_bytes_or_short_read(tmp_path):
    from pi_harness_cfg1.pi_fs_leaves import PayloadFileRead

    world = PolicyWorld(tmp_path)
    world.write_chain(two_profile_chain()[0])
    path = str(world.aps / "aps.r0001.json")
    data = (world.aps / "aps.r0001.json").read_bytes()
    double = LeafDouble()
    double.read_overrides[path] = PayloadFileRead("regular_file", True, True, len(data) - 1, _digest(data[:-1]), data[:-1] + b"")
    with pytest.raises(Cfg1PolicyError):
        world.load(**double.leaves())
    double.read_overrides[path] = PayloadFileRead("regular_file", True, True, len(data), _digest(data), bytearray(data))
    with pytest.raises(Cfg1PolicyError) as caught:
        world.load(**double.leaves())
    assert caught.value.reason_code == "POLICY_LEAF_MALFORMED"


def test_adv_seam_evidence_cannot_be_retired_or_approved_as_a_profile(tmp_path):
    a = base_payload()
    from pe2b_support import seam_evidence

    evidence = seam_evidence(a.facts.seam_digests_dict())
    chain = Chain()
    chain.revision(seam_evidence=[evidence], approvals=[approval(evidence["evidence_id"], "C3_SEAM_EQUAL")])
    with pytest.raises(Cfg1PolicyError) as caught:
        _load(tmp_path / "approve", chain)
    assert caught.value.reason_code == "POLICY_APPROVAL_PROFILE_NOT_IN_REVISION"
    chain = Chain()
    chain.revision(seam_evidence=[evidence])
    chain.revision(retirements=[retirement(evidence["evidence_id"])])
    with pytest.raises(Cfg1PolicyError) as caught:
        _load(tmp_path / "retire", chain)
    assert caught.value.reason_code == "POLICY_RETIREMENT_TARGET_NOT_ELIGIBLE"


def test_adv_refusals_carry_closed_codes_and_no_record_text(tmp_path):
    a = base_payload()
    secret = "needle-7f3a-not-for-console"
    chain = Chain()
    chain.revision(profiles=[a.profile()], approvals=[approval(a.profile_id, "C2_MANIFEST_ONLY", acceptance=secret)], payloads=[a])
    with pytest.raises(Cfg1PolicyError) as caught:
        _load(tmp_path, chain)
    assert secret not in str(caught.value) and secret not in repr(caught.value.args)
    assert str(tmp_path) not in str(caught.value)
    assert SYNTHETIC_REF["repo_path"] not in str(caught.value)
