"""PE-2b B-15: discovery classifies its candidate against the COMMITTED policy.

Acceptance row B-15 of
``docs/PHASE_5F3B_PI_HARNESS_PROFILE_EVOLUTION_PE1_AMENDMENT.md`` Sec. 26.2:
with a committed synthetic APS, discovery computes the floor through the
loader-owned reference view and the accepted PE-2a classifier by identity,
never through a copy.

A synthetic committed policy is installed by rebinding the loader's
``_GENUINE_POLICY_LOAD`` global to a load of a synthetic tree under
``tmp_path`` -- test-harness memory manipulation, the same deliberate pattern
``conftest`` uses for ``_CAPTURED_PACKAGE_DIR`` and the PE-2a tests use for
the staging directory. No supported API accepts a policy, a view or a
classifier. Discovery worlds are synthetic (inert ``node.exe``, never run);
nothing here runs Pi, Node or npm or reads a credential.
"""

from __future__ import annotations

import ast
import inspect
import json
import sys
from pathlib import Path

import pytest
from pe2a_support import (
    DiscoveryWorld,
    manifest_bytes,
    root_manifest,
    staging_listing,
    synthetic_payload_files,
)
from pe2b_support import (
    Chain,
    PolicyWorld,
    approval,
    base_payload,
    genesis_like_chain,
    retirement,
)

import pi_harness_cfg1
from pi_harness_cfg1 import pi_fs_leaves, pi_profile_discovery, pi_profile_floor
from pi_harness_cfg1 import pi_profile_policy_loader as loader
from pi_harness_cfg1.pi_fs_leaves import DirectoryListing
from pi_harness_cfg1.pi_identity import genuine_pi_proof_leaves
from pi_harness_cfg1.pi_payload import genuine_payload_leaves
from pi_harness_cfg1.pi_profile_discovery import (
    DISCOVERY_CANDIDATE_STAGED,
    DISCOVERY_REFUSED_FLOOR_UNCLASSIFIABLE,
    DISCOVERY_REFUSED_POLICY_REFERENCE_UNAVAILABLE,
    Cfg1DiscoveryError,
    _discover,
    build_candidate_record,
    discover_pi_profile_candidate,
)
from pi_harness_cfg1.pi_profile_floor import (
    FLOOR_C1,
    FLOOR_C1R,
    FLOOR_C2,
    FLOOR_C3_SEAM_CHANGED,
    FLOOR_C3_SEAM_EQUAL,
    FLOOR_C5,
    FLOOR_CLASSES,
    ReferenceView,
    classify_floor,
)

_PACKAGE_DIR = Path(__file__).resolve().parents[1]
_REAL_STAGING = _PACKAGE_DIR / "pi_profile_candidates"
_SUFFIXES = (".inventory.json", ".manifest_bundle.json", ".candidate.json")


@pytest.fixture(autouse=True)
def _the_real_staging_directory_is_never_touched():
    existed = _REAL_STAGING.exists()
    yield
    assert _REAL_STAGING.exists() is existed
    assert not existed


@pytest.fixture()
def staging(tmp_path, monkeypatch) -> Path:
    package = tmp_path / "synthetic_cfg1_package"
    package.mkdir()
    target = package / "pi_profile_candidates"
    monkeypatch.setattr(pi_profile_discovery, "_STAGING_DIRECTORY", str(target))
    return target


def _run(world: DiscoveryWorld):
    return _discover(
        {"PATH": world.path_value},
        proof_leaves=genuine_pi_proof_leaves(),
        payload_leaves=genuine_payload_leaves(),
        read_manifest=pi_fs_leaves.read_payload_file_bytes,
    )


def _world(tmp_path, name: str, **changes: bytes) -> DiscoveryWorld:
    files, empty_dirs = synthetic_payload_files()
    files.update(changes)
    return DiscoveryWorld(tmp_path / name, files, empty_dirs)


def _install_policy(tmp_path, monkeypatch, chain: Chain) -> object:
    world = PolicyWorld(tmp_path / "committed_policy")
    world.write_chain(chain)
    load = world.load()
    monkeypatch.setattr(loader, "_GENUINE_POLICY_LOAD", load)
    return load


def _candidate(staging: Path, outcome) -> dict:
    return json.loads((staging / (outcome.payload_fingerprint + ".candidate.json")).read_bytes())


def _console_floor(outcome) -> str:
    (line,) = [line for line in outcome.console_lines if line.startswith("  floor ")]
    return line[len("  floor ") :]


def _a_eligible_chain() -> Chain:
    a = base_payload()
    chain = Chain()
    chain.revision(profiles=[a.profile()], approvals=[approval(a.profile_id, "C3_SEAM_CHANGED")], payloads=[a])
    return chain


def _a_retired_chain() -> Chain:
    chain = _a_eligible_chain()
    chain.revision(retirements=[retirement(base_payload().profile_id)])
    return chain


_VARIANTS = {
    "exact": {},
    "version_bump": {"package.json": manifest_bytes(root_manifest(version="1.0.1"))},
    "non_seam_change": {"dist/cli/setup.js": b"export const setup = 99;\n"},
    "seam_change": {"dist/main.js": b"synthetic pe2b discovery seam change\n"},
    "c5_wrong_name": {"package.json": manifest_bytes(root_manifest(name="not-pi"))},
}

_MATRIX = [
    ("eligible", "exact", FLOOR_C1),
    ("retired", "exact", FLOOR_C1R),
    ("eligible", "version_bump", FLOOR_C2),
    ("eligible", "non_seam_change", FLOOR_C3_SEAM_EQUAL),
    ("eligible", "seam_change", FLOOR_C3_SEAM_CHANGED),
    ("eligible", "c5_wrong_name", FLOOR_C5),
    ("retired", "version_bump", FLOOR_C3_SEAM_CHANGED),
    ("zero_eligible_with_seam_evidence", "exact", FLOOR_C3_SEAM_EQUAL),
    ("zero_eligible_with_seam_evidence", "seam_change", FLOOR_C3_SEAM_CHANGED),
    ("zero_eligible_with_seam_evidence", "c5_wrong_name", FLOOR_C5),
]


def _chain_for(state: str) -> Chain:
    return {
        "eligible": _a_eligible_chain,
        "retired": _a_retired_chain,
        "zero_eligible_with_seam_evidence": genesis_like_chain,
    }[state]()


# ---------------------------------------------------------------------------
# The matrix: candidate floor == accepted classifier over the committed view
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("state, variant, expected", _MATRIX)
def test_b15_discovery_floor_matrix_against_a_committed_synthetic_aps(
    tmp_path, monkeypatch, staging, state, variant, expected
):
    load = _install_policy(tmp_path, monkeypatch, _chain_for(state))
    world = _world(tmp_path, "world", **_VARIANTS[variant])
    outcome = _run(world)
    assert outcome.code == DISCOVERY_CANDIDATE_STAGED
    candidate = _candidate(staging, outcome)
    assert candidate["floor"] == expected
    assert _console_floor(outcome) == candidate["floor"]
    assert candidate["authority"] == "NON_AUTHORITY_CANDIDATE"
    assert ("  authority NON_AUTHORITY_CANDIDATE") in outcome.console_lines
    # The floor equals an INDEPENDENT application of the accepted classifier
    # to independently recomputed facts and a fresh committed view.
    from pe2a_support import facts_for

    files, empty_dirs = synthetic_payload_files()
    files.update(_VARIANTS[variant])
    facts = facts_for(files, empty_dirs)
    assert facts.payload_fingerprint == outcome.payload_fingerprint
    assert classify_floor(facts, loader._reference_view_from_material(load.head_reference)) == expected
    # Classification never changes the staging boundary or its contents.
    names = [outcome.payload_fingerprint + suffix for suffix in _SUFFIXES]
    assert outcome.staged_files == tuple(names)
    assert staging_listing(staging) == sorted(names)
    # The policy tree was not written to.
    assert sorted(p.name for p in (tmp_path / "committed_policy" / "pi_profile_policy").iterdir())[0] == "aps"


def test_b15_the_genuine_genesis_head_classifies_and_never_falls_back(tmp_path, staging):
    """No rebinding: the real committed genesis r0001 (zero eligible)."""
    assert loader.SEALED_POLICY_SNAPSHOT.eligible_profile_ids == frozenset()
    outcome = _run(_world(tmp_path, "world"))
    candidate = _candidate(staging, outcome)
    assert candidate["floor"] == FLOOR_C3_SEAM_CHANGED == _console_floor(outcome)
    assert "NOT_COMPUTED" not in json.dumps(candidate) and "NOT_COMPUTED" not in "\n".join(outcome.console_lines)


def test_b15_the_public_entry_point_uses_the_committed_view(tmp_path, monkeypatch, staging):
    _install_policy(tmp_path, monkeypatch, _a_eligible_chain())
    world = _world(tmp_path, "world")
    outcome = discover_pi_profile_candidate({"PATH": world.path_value})
    assert _candidate(staging, outcome)["floor"] == FLOOR_C1


# ---------------------------------------------------------------------------
# Identity and the zero-argument loader surface
# ---------------------------------------------------------------------------


def test_b15_discovery_uses_the_accepted_classifier_by_identity():
    assert pi_profile_discovery.classify_floor is pi_profile_floor.classify_floor
    assert pi_profile_discovery.ReferenceView is pi_profile_floor.ReferenceView
    assert pi_profile_discovery.FLOOR_CLASSES is pi_profile_floor.FLOOR_CLASSES
    source = (_PACKAGE_DIR / "pi_profile_discovery.py").read_text(encoding="utf-8")
    defined = {node.name for node in ast.walk(ast.parse(source)) if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    for name in ("classify_floor", "c2_relation", "ReferenceView", "head_reference_view", "_reference_view_from_material"):
        assert name not in defined, name


def test_b15_the_view_comes_from_the_zero_argument_loader_surface_once(tmp_path, monkeypatch, staging):
    _install_policy(tmp_path, monkeypatch, _a_eligible_chain())
    calls: list = []
    real_view = loader.head_reference_view
    real_classify = pi_profile_discovery.classify_floor

    def _view(*args, **kwargs):
        calls.append(("view", args, kwargs))
        view = real_view()
        calls.append(("returned", view))
        return view

    def _classify(facts, reference):
        calls.append(("classify", reference))
        return real_classify(facts, reference)

    monkeypatch.setattr(loader, "head_reference_view", _view)
    monkeypatch.setattr(pi_profile_discovery, "classify_floor", _classify)
    outcome = _run(_world(tmp_path, "world"))
    assert outcome.code == DISCOVERY_CANDIDATE_STAGED
    assert calls[0] == ("view", (), {})
    assert calls[2][0] == "classify" and calls[2][1] is calls[1][1]
    assert len(calls) == 3
    assert list(inspect.signature(real_view).parameters) == []


def test_b15_no_caller_can_inject_a_view_classifier_policy_path_snapshot_or_head():
    surfaces = {
        discover_pi_profile_candidate: ["ambient_environ"],
        pi_profile_discovery.main: ["argv"],
        _discover: ["ambient_environ", "proof_leaves", "payload_leaves", "read_manifest"],
        pi_profile_discovery._classify_against_committed_policy: ["facts"],
    }
    for function, expected in surfaces.items():
        assert list(inspect.signature(function).parameters) == expected, function.__name__
    for name in ("reference", "view", "classifier", "classify", "policy", "snapshot", "aps_head", "head"):
        for function in surfaces:
            with pytest.raises(TypeError):
                function(**{name: object()})


@pytest.mark.parametrize(
    "argv",
    [["--policy", "C:\\x"], ["--aps-head", "0" * 64], ["--floor", "C1"], ["--reference-view", "x"]],
)
def test_b15_no_cli_option_can_select_policy_or_floor(argv, monkeypatch, staging):
    called = []
    monkeypatch.setattr(pi_profile_discovery, "discover_pi_profile_candidate", lambda env: called.append(env))
    assert pi_profile_discovery.main(argv) == 2
    assert called == [] and not staging.exists()


def test_b15_environment_and_cwd_cannot_select_a_policy(tmp_path, monkeypatch, staging):
    hostile = PolicyWorld(tmp_path / "hostile")
    hostile.write_chain(_a_eligible_chain())
    monkeypatch.chdir(tmp_path / "hostile")
    for name in ("AIDO_PI_PROFILE_POLICY", "PI_PROFILE_POLICY", "POLICY_DIR", "AIDO_APS_HEAD_SHA256"):
        monkeypatch.setenv(name, str(hostile.dir))
    world = _world(tmp_path, "world")
    monkeypatch.setenv("PATH", world.path_value)
    assert pi_profile_discovery.main([]) == 0
    # The genuine committed genesis decided, not the hostile tree (which would say C1).
    assert _candidate(staging, type("O", (), {"payload_fingerprint": base_payload().fingerprint})())["floor"] == (
        FLOOR_C3_SEAM_CHANGED
    )


# ---------------------------------------------------------------------------
# Fail closed: never NOT_COMPUTED, never a default view
# ---------------------------------------------------------------------------


def _assert_refused_without_staging(outcome, code, staging, needle=None):
    assert outcome.code == code
    assert outcome.staged_files == ()
    assert not staging.exists()
    text = "\n".join(outcome.console_lines)
    assert "NOT_COMPUTED" not in text and "floor" not in text
    assert ":\\" not in text
    if needle is not None:
        assert needle not in text


def test_b15_a_raising_reference_view_refuses(tmp_path, monkeypatch, staging):
    def _raise():
        raise loader.Cfg1PolicyError("NEEDLE_9c1d_POLICY_TEXT")

    monkeypatch.setattr(loader, "head_reference_view", _raise)
    outcome = _run(_world(tmp_path, "world"))
    _assert_refused_without_staging(outcome, DISCOVERY_REFUSED_POLICY_REFERENCE_UNAVAILABLE, staging, "9c1d")


class _SubclassedView(ReferenceView):
    pass


@pytest.mark.parametrize(
    "returned",
    [None, "C1", {}, (), object(), "subclass"],
)
def test_b15_a_malformed_reference_view_refuses(tmp_path, monkeypatch, staging, returned):
    if returned == "subclass":
        returned = _SubclassedView(eligible=(), present_ineligible_profile_ids=(), seam_fingerprints=())
    monkeypatch.setattr(loader, "head_reference_view", lambda: returned)
    outcome = _run(_world(tmp_path, "world"))
    _assert_refused_without_staging(outcome, DISCOVERY_REFUSED_POLICY_REFERENCE_UNAVAILABLE, staging)


def test_b15_a_malformed_committed_policy_state_refuses(tmp_path, monkeypatch, staging):
    monkeypatch.setattr(loader, "_GENUINE_POLICY_LOAD", object())
    outcome = _run(_world(tmp_path, "world"))
    _assert_refused_without_staging(outcome, DISCOVERY_REFUSED_POLICY_REFERENCE_UNAVAILABLE, staging)


def test_b15_corrupted_committed_reference_bytes_refuse(tmp_path, monkeypatch, staging):
    load = _install_policy(tmp_path, monkeypatch, _a_eligible_chain())
    material = load.head_reference
    ((profile_id, fingerprint, inventory_bytes, bundle_bytes),) = material.eligible_payloads
    corrupt = loader._HeadReferenceMaterial(
        loader._SEAL_KEY,
        eligible_payloads=((profile_id, fingerprint, inventory_bytes.replace(b"\n", b"\r\n"), bundle_bytes),),
        present_ineligible_profile_ids=material.present_ineligible_profile_ids,
        seam_fingerprints=material.seam_fingerprints,
    )
    forged = loader._PolicyLoad(loader._SEAL_KEY, snapshot=load.snapshot, head_reference=corrupt, revisions=load.revisions)
    monkeypatch.setattr(loader, "_GENUINE_POLICY_LOAD", forged)
    outcome = _run(_world(tmp_path, "world"))
    _assert_refused_without_staging(outcome, DISCOVERY_REFUSED_POLICY_REFERENCE_UNAVAILABLE, staging)


def test_b15_an_unimportable_loader_refuses(tmp_path, monkeypatch, staging):
    """A loader that cannot be imported at all (``None`` in sys.modules)."""
    monkeypatch.delattr(pi_harness_cfg1, "pi_profile_policy_loader")
    monkeypatch.setitem(sys.modules, "pi_harness_cfg1.pi_profile_policy_loader", None)
    outcome = _run(_world(tmp_path, "world"))
    _assert_refused_without_staging(outcome, DISCOVERY_REFUSED_POLICY_REFERENCE_UNAVAILABLE, staging)


def test_b15_a_genuine_policy_that_refuses_at_import_makes_discovery_refuse(tmp_path, monkeypatch, staging):
    """A REAL fresh import of the loader whose genuine policy directory is
    observed as a reparse point: the import raises, discovery refuses."""
    real_enumerate = pi_fs_leaves.enumerate_directory_no_follow
    policy_dir = loader._POLICY_DIR

    def _enumerate(path, max_entries):
        if path == policy_dir:
            return DirectoryListing("reparse_point", False, False, None)
        return real_enumerate(path, max_entries)

    monkeypatch.setattr(pi_fs_leaves, "enumerate_directory_no_follow", _enumerate)
    monkeypatch.delattr(pi_harness_cfg1, "pi_profile_policy_loader")
    monkeypatch.delitem(sys.modules, "pi_harness_cfg1.pi_profile_policy_loader")
    outcome = _run(_world(tmp_path, "world"))
    _assert_refused_without_staging(outcome, DISCOVERY_REFUSED_POLICY_REFERENCE_UNAVAILABLE, staging)
    assert "pi_harness_cfg1.pi_profile_policy_loader" not in sys.modules
    # Never falls open on a second attempt either.
    again = _run(_world(tmp_path, "world2"))
    assert again.code == DISCOVERY_REFUSED_POLICY_REFERENCE_UNAVAILABLE


def test_b15_a_raising_classifier_refuses(tmp_path, monkeypatch, staging):
    def _raise(facts, reference):
        raise pi_profile_floor.Cfg1FloorError("NEEDLE_44ab")

    monkeypatch.setattr(pi_profile_discovery, "classify_floor", _raise)
    outcome = _run(_world(tmp_path, "world"))
    _assert_refused_without_staging(outcome, DISCOVERY_REFUSED_FLOOR_UNCLASSIFIABLE, staging, "44ab")


@pytest.mark.parametrize("returned", ["NOT_COMPUTED", "C4", "c1", "", None, 1, FLOOR_C1.encode()])
def test_b15_an_out_of_vocabulary_floor_refuses(tmp_path, monkeypatch, staging, returned):
    monkeypatch.setattr(pi_profile_discovery, "classify_floor", lambda facts, reference: returned)
    outcome = _run(_world(tmp_path, "world"))
    _assert_refused_without_staging(outcome, DISCOVERY_REFUSED_FLOOR_UNCLASSIFIABLE, staging)


def test_b15_the_candidate_builder_refuses_a_missing_or_foreign_floor():
    from pe2a_support import facts_for

    facts = facts_for(*synthetic_payload_files())
    with pytest.raises(TypeError):
        build_candidate_record(facts, None)
    for bad in ("NOT_COMPUTED", "C4", None, "APPROVED"):
        with pytest.raises(Cfg1DiscoveryError) as caught:
            build_candidate_record(facts, None, floor=bad)
        assert caught.value.reason_code == "MALFORMED_FLOOR"
    for floor in FLOOR_CLASSES:
        record = build_candidate_record(facts, None, floor=floor)
        assert record["floor"] == floor and record["authority"] == "NON_AUTHORITY_CANDIDATE"


# ---------------------------------------------------------------------------
# Non-authority: staging is never an input, and the floor grants nothing
# ---------------------------------------------------------------------------


def test_b15_forged_staging_candidates_never_influence_the_floor(tmp_path, monkeypatch, staging):
    _install_policy(tmp_path, monkeypatch, genesis_like_chain())
    staging.mkdir()
    other = "ab" * 32
    (staging / (other + ".candidate.json")).write_bytes(
        b'{"authority":"APPROVED","floor":"C1","aps_head_sha256":"' + b"0" * 64 + b'"}\n'
    )
    forged_head = Chain()
    a = base_payload()
    forged_head.revision(profiles=[a.profile()], approvals=[approval(a.profile_id, "C3_SEAM_CHANGED")])
    (staging / "aps.r0001.json").write_bytes(forged_head.file_bytes()[0])
    outcome = _run(_world(tmp_path, "world"))
    assert outcome.code == DISCOVERY_CANDIDATE_STAGED
    assert _candidate(staging, outcome)["floor"] == FLOOR_C3_SEAM_EQUAL  # genesis-like, never C1


@pytest.mark.parametrize("floor", sorted(FLOOR_CLASSES))
def test_b15_the_floor_value_never_changes_the_staging_boundary(tmp_path, monkeypatch, staging, floor):
    monkeypatch.setattr(pi_profile_discovery, "classify_floor", lambda facts, reference: floor)
    outcome = _run(_world(tmp_path, "world"))
    assert outcome.code == DISCOVERY_CANDIDATE_STAGED
    names = [outcome.payload_fingerprint + suffix for suffix in _SUFFIXES]
    assert outcome.staged_files == tuple(names) and staging_listing(staging) == sorted(names)
    candidate = _candidate(staging, outcome)
    assert candidate["floor"] == floor == _console_floor(outcome)
    assert candidate["authority"] == "NON_AUTHORITY_CANDIDATE"
    assert candidate["record_kind"] == "aido-pi-profile-candidate.v1"
    assert candidate["discovery"] == {"discovery_tool_revision": "PE-2b"}


def test_b15_a_c1_floor_grants_no_eligibility_and_writes_no_policy(tmp_path, monkeypatch, staging):
    load = _install_policy(tmp_path, monkeypatch, _a_eligible_chain())
    policy_dir = tmp_path / "committed_policy" / "pi_profile_policy"
    before = sorted((p.relative_to(policy_dir).as_posix(), p.read_bytes()) for p in policy_dir.rglob("*") if p.is_file())
    snapshot = load.snapshot
    newcomer = _world(tmp_path, "world", **_VARIANTS["version_bump"])
    outcome = _run(newcomer)
    assert _candidate(staging, outcome)["floor"] == FLOOR_C2
    assert loader._GENUINE_POLICY_LOAD.snapshot is snapshot
    assert outcome.payload_fingerprint not in {view.payload_fingerprint for view in snapshot.eligible_profiles}
    after = sorted((p.relative_to(policy_dir).as_posix(), p.read_bytes()) for p in policy_dir.rglob("*") if p.is_file())
    assert after == before
    genuine = _PACKAGE_DIR / "pi_profile_policy"
    assert sorted(p.relative_to(genuine).as_posix() for p in genuine.rglob("*")) == ["aps", "aps/aps.r0001.json"]


def test_b15_the_policy_loader_is_wired_exactly_where_pe1_places_it():
    """At PE-2b no runtime module referenced the loader. PE-2c (PE-1 Sec. 11.4,
    Sec. 20.3, Sec. 21) then wires it in EXACTLY these places: P / gate / L1 /
    L14 / L21A read the module-level ``SEALED_POLICY_SNAPSHOT`` (``pi_identity``);
    the v3 record builders cite its frozen literals (``records``); and the
    read-only post-hoc binding verifier reads the private load summary. Only
    discovery ever reads ``head_reference_view`` (B-15), and no runtime module
    reads the private load object."""
    users = set()
    for path in sorted(_PACKAGE_DIR.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if any(
            needle in source
            for needle in ("pi_profile_policy_loader", "head_reference_view", "SEALED_POLICY_SNAPSHOT")
        ):
            users.add(path.name)
    assert users == {
        "pi_profile_discovery.py",
        "pi_profile_evidence_verifier.py",
        "pi_profile_policy_loader.py",
        "pi_identity.py",
        "records.py",
        "pi_profile_binding_verifier.py",
    }
    for name in sorted(users - {"pi_profile_policy_loader.py", "pi_profile_discovery.py"}):
        source = (_PACKAGE_DIR / name).read_text(encoding="utf-8")
        assert "head_reference_view" not in source, name
    for name in ("pi_identity.py", "records.py"):
        source = (_PACKAGE_DIR / name).read_text(encoding="utf-8")
        assert "_GENUINE_POLICY_LOAD" not in source and "_load_policy_directory" not in source, name
    verifier_source = (_PACKAGE_DIR / "pi_profile_evidence_verifier.py").read_text(encoding="utf-8")
    assert "head_reference_view" not in verifier_source and "SEALED_POLICY_SNAPSHOT" not in verifier_source
