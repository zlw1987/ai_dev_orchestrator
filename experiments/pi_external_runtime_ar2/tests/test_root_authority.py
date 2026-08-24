"""FU1A -- disposable-root authority ORIGINATES at creation time, closed for real.

FU-A's first version replaced a hard-coded denylist with a marker file, but the
marker was written by a function that accepted an ALREADY-EXISTING directory:

    create_disposable_root_authority(repo_root)   # repo_root already exists

That proved only "this directory was stamped, at some point, by something that
called the stamping function" -- not "this exact disposable experiment root was
created by AIDO's fixture creation path." Any caller holding a bare path string
could convert it into an authorized one retroactively.

5F3A-AR2-FU1A removes that function entirely. Authority now originates ONLY at
:func:`ar2.fixtures.create_disposable_experiment_root`, which:

1. creates a FRESH directory itself (``tempfile.mkdtemp()``), guaranteed not to
   have existed a moment before;
2. writes a fixed-schema marker there, AS PART OF THAT SAME CREATION STEP, via
   exclusive create (``O_CREAT | O_EXCL`` -- fails if one is somehow already
   there, rather than silently overwriting);
3. returns a :class:`~ar2.capability.DisposableRootAuthority` naming a
   PROSPECTIVE ``repo_root`` that does not exist yet either.

:func:`ar2.fixtures.build_case_repository` and
:func:`ar2.fixtures.build_synthetic_repository` then create EXACTLY that one
child directory. There is no path from a bare, already-existing directory to a
valid authority anywhere in this experiment any more.

Per the FU1A brief: **no real sibling project is accessed or stat'ed anywhere in
this file.** Every negative case uses a ``tmp_path``/system-temp synthetic
directory. The one denylist case exercised uses the orchestrator's own path
(this repository, not a sibling), matching the already-accepted precedent in
``test_capability_state.py``.
"""

from __future__ import annotations

import json
import os

import pytest

from ar2.capability import (
    DEFAULT_REPO_CHILD_NAME,
    ROOT_AUTHORITY_MARKER_FILENAME,
    ROOT_AUTHORITY_MARKER_SCHEMA,
    CapabilityMintError,
    DisposableRootAuthority,
    RootAuthorityError,
    approved_scratch_boundary,
    mint_capability,
)
from ar2.fixtures import (
    FixtureError,
    R1,
    build_case_repository,
    build_synthetic_repository,
    create_disposable_experiment_root,
    remove_disposable_tree,
)

from conftest import mint_for


def _write_marker(experiment_root: str, marker: dict) -> None:
    """Test-only: write a marker DIRECTLY, bypassing the sanctioned creator.

    Used only to construct adversarial ON-DISK states (a mismatched marker, a
    reparse marker) that ``create_disposable_experiment_root`` itself would
    never produce. Never used to authorize an arbitrary directory for a
    production code path -- only ``mint_capability``'s own verification is
    exercised against the result.
    """
    path = os.path.join(experiment_root, ROOT_AUTHORITY_MARKER_FILENAME)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(marker))


# -- the positive path: authority created FRESH mints successfully -------------


def test_a_freshly_created_authority_mints_successfully():
    authority = create_disposable_experiment_root(case_id="t1")
    try:
        sed = mint_capability(
            authority=authority,
            tracked_manifest=("a.py", "tests/test_a.py"),
            protected_patterns=("tests/*",),
            verification_witness_paths=("tests/test_a.py",),
        )
        assert sed.canonical_root == authority.repo_root
    finally:
        remove_disposable_tree(authority.experiment_root)


def test_1_a_builtfixture_created_by_the_sanctioned_fixture_creator_mints(
    git_executable,
):
    """Negative test #1: the ordinary R1-R4 path, end to end."""
    built = build_case_repository(R1, git_executable=git_executable)
    try:
        sed = mint_for(R1, git_executable, built)
        assert sed.canonical_root == built.repo_root
        assert "calc.py" in sed.read_eligible
    finally:
        remove_disposable_tree(built.experiment_root)


def test_the_marker_is_created_at_fresh_root_creation_time_not_afterward():
    authority = create_disposable_experiment_root(case_id="t1")
    try:
        marker_path = os.path.join(authority.experiment_root, ROOT_AUTHORITY_MARKER_FILENAME)
        assert os.path.isfile(marker_path)
        with open(marker_path, encoding="utf-8") as handle:
            on_disk = json.load(handle)
        assert on_disk == {
            "schema": ROOT_AUTHORITY_MARKER_SCHEMA,
            "experiment_id": authority.experiment_id,
            "case_id": authority.case_id,
            "repo_child_name": authority.repo_child_name,
            "nonce": authority.nonce,
        }
        # The marker lives OUTSIDE the (not-yet-existing) repo child.
        assert not os.path.exists(authority.repo_root)
    finally:
        remove_disposable_tree(authority.experiment_root)


def test_the_nonce_is_128_bits_of_hex_and_differs_per_fresh_root():
    first = create_disposable_experiment_root(case_id="t1")
    second = create_disposable_experiment_root(case_id="t1")
    try:
        assert len(first.nonce) == 32
        assert all(c in "0123456789abcdef" for c in first.nonce)
        assert first.nonce != second.nonce
        assert first.experiment_root != second.experiment_root
    finally:
        remove_disposable_tree(first.experiment_root)
        remove_disposable_tree(second.experiment_root)


# -- #2: no general API can retroactively authorize an existing directory ------


def test_2_no_normal_api_can_convert_an_existing_directory_into_an_authority(tmp_path):
    """There is no ``create_disposable_root_authority(existing_path)`` any
    more. The only creation function takes NO path argument at all."""
    import inspect

    from ar2 import fixtures as fixtures_module

    assert not hasattr(fixtures_module, "create_disposable_root_authority")
    parameters = inspect.signature(create_disposable_experiment_root).parameters
    for name, parameter in parameters.items():
        assert "path" not in name.lower()
        assert "root" not in name.lower()
        assert "dir" not in name.lower()


def test_2b_a_random_pre_existing_directory_has_no_marker_and_cannot_mint(tmp_path):
    never_authorized = tmp_path / "just_a_directory_nobody_created_via_ar2"
    never_authorized.mkdir()
    forged = DisposableRootAuthority(
        experiment_id="5F3A-AR2",
        case_id="forgery-attempt",
        experiment_root=str(tmp_path),
        repo_root=os.path.join(str(tmp_path), "just_a_directory_nobody_created_via_ar2"),
        repo_child_name="just_a_directory_nobody_created_via_ar2",
        nonce="0" * 32,
    )
    with pytest.raises(RootAuthorityError, match="no root authority marker"):
        mint_capability(authority=forged, tracked_manifest=("a.py",))


# -- #3: a valid authority for fixture A cannot mint fixture B -----------------


def test_3_a_valid_authority_for_fixture_a_cannot_mint_fixture_b():
    authority_a = create_disposable_experiment_root(case_id="a")
    authority_b = create_disposable_experiment_root(case_id="b")
    try:
        substituted = DisposableRootAuthority(
            experiment_id=authority_a.experiment_id,
            case_id=authority_a.case_id,
            experiment_root=authority_a.experiment_root,  # A's real, marked root
            repo_root=authority_b.repo_root,  # but claiming B's repo
            repo_child_name=authority_a.repo_child_name,
            nonce=authority_a.nonce,  # A's real, valid nonce
        )
        with pytest.raises(RootAuthorityError, match="expected relationship"):
            mint_capability(authority=substituted, tracked_manifest=("a.py",))
    finally:
        remove_disposable_tree(authority_a.experiment_root)
        remove_disposable_tree(authority_b.experiment_root)


# -- #4: a forged authority without a matching creation-time marker refuses ----


def test_4_a_forged_authority_with_no_matching_marker_refuses(tmp_path):
    fabricated_root = str(tmp_path)
    forged = DisposableRootAuthority(
        experiment_id="5F3A-AR2",
        case_id="t1",
        experiment_root=fabricated_root,
        repo_root=os.path.join(fabricated_root, DEFAULT_REPO_CHILD_NAME),
        repo_child_name=DEFAULT_REPO_CHILD_NAME,
        nonce="a" * 32,
    )
    # No marker was ever written at fabricated_root by the sanctioned creator.
    with pytest.raises(RootAuthorityError, match="no root authority marker"):
        mint_capability(authority=forged, tracked_manifest=("a.py",))


# -- #5/#6/#7/#8: exact marker-field agreement is required ---------------------


def test_5_experiment_id_mismatch_refuses():
    authority = create_disposable_experiment_root(case_id="t1")
    try:
        wrong = DisposableRootAuthority(
            experiment_id="5F3A-AR2-DIFFERENT",
            case_id=authority.case_id,
            experiment_root=authority.experiment_root,
            repo_root=authority.repo_root,
            repo_child_name=authority.repo_child_name,
            nonce=authority.nonce,
        )
        with pytest.raises(RootAuthorityError, match="experiment_id does not match"):
            mint_capability(authority=wrong, tracked_manifest=("a.py",))
    finally:
        remove_disposable_tree(authority.experiment_root)


def test_6_case_id_mismatch_refuses():
    authority = create_disposable_experiment_root(case_id="t1")
    try:
        wrong = DisposableRootAuthority(
            experiment_id=authority.experiment_id,
            case_id="t1-but-different",
            experiment_root=authority.experiment_root,
            repo_root=authority.repo_root,
            repo_child_name=authority.repo_child_name,
            nonce=authority.nonce,
        )
        with pytest.raises(RootAuthorityError, match="case_id does not match"):
            mint_capability(authority=wrong, tracked_manifest=("a.py",))
    finally:
        remove_disposable_tree(authority.experiment_root)


def test_7_marker_nonce_mismatch_refuses():
    authority = create_disposable_experiment_root(case_id="t1")
    try:
        wrong = DisposableRootAuthority(
            experiment_id=authority.experiment_id,
            case_id=authority.case_id,
            experiment_root=authority.experiment_root,
            repo_root=authority.repo_root,
            repo_child_name=authority.repo_child_name,
            nonce="f" * 32,  # NOT what create_disposable_experiment_root wrote
        )
        assert wrong.nonce != authority.nonce
        with pytest.raises(RootAuthorityError, match="nonce does not match"):
            mint_capability(authority=wrong, tracked_manifest=("a.py",))
    finally:
        remove_disposable_tree(authority.experiment_root)


def test_8_marker_schema_version_mismatch_refuses():
    authority = create_disposable_experiment_root(case_id="t1")
    try:
        _write_marker(
            authority.experiment_root,
            {
                "schema": "ar2-root-authority.v0-does-not-exist",
                "experiment_id": authority.experiment_id,
                "case_id": authority.case_id,
                "repo_child_name": authority.repo_child_name,
                "nonce": authority.nonce,
            },
        )
        with pytest.raises(RootAuthorityError, match="schema/version does not match"):
            mint_capability(authority=authority, tracked_manifest=("a.py",))
    finally:
        remove_disposable_tree(authority.experiment_root)


# -- #9: marker missing refuses -------------------------------------------------


def test_9_marker_missing_refuses():
    authority = create_disposable_experiment_root(case_id="t1")
    marker_path = os.path.join(authority.experiment_root, ROOT_AUTHORITY_MARKER_FILENAME)
    os.remove(marker_path)
    try:
        with pytest.raises(RootAuthorityError, match="no root authority marker"):
            mint_capability(authority=authority, tracked_manifest=("a.py",))
    finally:
        remove_disposable_tree(authority.experiment_root)


# -- #10: marker symlink/reparse refuses ----------------------------------------


def test_10_a_symlinked_marker_is_refused_not_followed():
    authority = create_disposable_experiment_root(case_id="t1")
    try:
        marker_path = os.path.join(authority.experiment_root, ROOT_AUTHORITY_MARKER_FILENAME)
        target_path = os.path.join(authority.experiment_root, "elsewhere_marker.json")
        with open(target_path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "schema": ROOT_AUTHORITY_MARKER_SCHEMA,
                    "experiment_id": authority.experiment_id,
                    "case_id": authority.case_id,
                    "repo_child_name": authority.repo_child_name,
                    "nonce": authority.nonce,
                },
                handle,
            )
        os.remove(marker_path)
        try:
            os.symlink(target_path, marker_path)
        except (OSError, NotImplementedError, AttributeError):
            pytest.skip("this host does not permit creating a symlink without elevation")
        with pytest.raises(RootAuthorityError, match="symlink or reparse point"):
            mint_capability(authority=authority, tracked_manifest=("a.py",))
    finally:
        remove_disposable_tree(authority.experiment_root)


# -- #11: repo_root must be EXACTLY the expected repository child --------------


def test_11_repo_root_not_the_expected_child_refuses():
    authority = create_disposable_experiment_root(case_id="t1")
    try:
        wrong = DisposableRootAuthority(
            experiment_id=authority.experiment_id,
            case_id=authority.case_id,
            experiment_root=authority.experiment_root,
            repo_root=os.path.join(authority.experiment_root, "not_the_repo_child_name"),
            repo_child_name=authority.repo_child_name,  # still claims "repo"
            nonce=authority.nonce,
        )
        with pytest.raises(RootAuthorityError, match="expected relationship"):
            mint_capability(authority=wrong, tracked_manifest=("a.py",))
    finally:
        remove_disposable_tree(authority.experiment_root)


def test_11b_a_repo_child_name_that_is_a_traversal_is_refused():
    """A ``repo_child_name`` containing a separator is refused on the safety
    check specifically -- constructed so ``repo_root`` is ALREADY canonical
    (no ``..`` to collapse), so this exercises the child-name check rather
    than being caught earlier by the canonical-form check."""
    authority = create_disposable_experiment_root(case_id="t1")
    try:
        unsafe_child = "sub" + os.sep + "evil"
        wrong = DisposableRootAuthority(
            experiment_id=authority.experiment_id,
            case_id=authority.case_id,
            experiment_root=authority.experiment_root,
            repo_root=os.path.join(authority.experiment_root, unsafe_child),
            repo_child_name=unsafe_child,
            nonce=authority.nonce,
        )
        assert os.path.realpath(wrong.repo_root) == wrong.repo_root
        with pytest.raises(RootAuthorityError, match="safe path segment"):
            mint_capability(authority=wrong, tracked_manifest=("a.py",))
    finally:
        remove_disposable_tree(authority.experiment_root)


# -- #12: the temp/scratch boundary is enforced even for a hand-built object ---


def test_12_a_directory_outside_the_scratch_boundary_cannot_be_minted(
    tmp_path, monkeypatch
):
    """Even a caller who manually constructs a DisposableRootAuthority object,
    with a syntactically valid shape, cannot name a root outside the approved
    temp/scratch domain.

    Wholly synthetic: no real host directory (``C:\\Users\\Public``,
    ``C:\\ProgramData``, or anything else) is read, listed, stat'ed, or
    realpath'd. ``approved_scratch_boundary()`` is monkeypatched, on the
    ``ar2.capability`` module it is called from, to a synthetic ``approved``
    directory under ``tmp_path``; the forged authority then names a sibling
    ``outside`` directory that is -- by construction, not by probing the real
    filesystem -- outside that approved boundary.
    """
    approved = tmp_path / "approved"
    outside = tmp_path / "outside"
    approved.mkdir()
    outside.mkdir()

    import ar2.capability as capability_module

    monkeypatch.setattr(
        capability_module,
        "approved_scratch_boundary",
        lambda: os.path.normcase(str(approved)),
    )

    outside_root = os.path.realpath(str(outside))
    repo_child = "ar2_fu1a_boundary_probe_repo"
    forged = DisposableRootAuthority(
        experiment_id="5F3A-AR2",
        case_id="boundary-escape-attempt",
        experiment_root=outside_root,
        repo_root=os.path.join(outside_root, repo_child),
        repo_child_name=repo_child,
        nonce="b" * 32,
    )
    with pytest.raises(RootAuthorityError, match="approved temp/scratch boundary"):
        mint_capability(authority=forged, tracked_manifest=("a.py",))


def test_12b_the_scratch_boundary_is_a_positive_check_not_a_denylist_entry():
    """Structural: the boundary check is a startswith-membership test against
    ``approved_scratch_boundary()``, not another hard-coded forbidden path."""
    import ast
    import inspect

    from ar2 import capability as capability_module

    source = inspect.getsource(capability_module._verify_root_authority)
    assert "approved_scratch_boundary" in source
    assert "startswith" in source
    tree = ast.parse(inspect.getsource(capability_module))
    boundary_fn = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "approved_scratch_boundary"
    )
    boundary_source = ast.unparse(boundary_fn)
    assert "tempfile.gettempdir" in boundary_source
    for banned in ("mis_project", "a8_oa", "bible_reading_v2", "c:\\\\dev"):
        assert banned not in boundary_source.lower()


def test_12c_a_freshly_created_root_is_always_inside_the_scratch_boundary():
    authority = create_disposable_experiment_root(case_id="t1")
    try:
        boundary = approved_scratch_boundary()
        assert os.path.normcase(authority.experiment_root).startswith(boundary + os.sep)
    finally:
        remove_disposable_tree(authority.experiment_root)


# -- #13: no test helper retroactively stamps an arbitrary existing repo_root --


def test_13_no_test_helper_has_a_normal_path_that_retroactively_stamps(tmp_path):
    """Structural: neither ``mint_for`` nor ``custom_repo`` (nor anything else
    in conftest.py) accepts a bare pre-existing path and returns a valid
    authority for it."""
    import ast
    import inspect

    import conftest as conftest_module

    source = inspect.getsource(conftest_module)
    assert "create_disposable_root_authority" not in source
    assert "def authority_for" not in source

    tree = ast.parse(source)
    mint_for_node = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "mint_for"
    )
    parameter_names = [a.arg for a in mint_for_node.args.args]
    # mint_for's third parameter is a BuiltFixture object (carrying .authority),
    # never a bare path string.
    assert parameter_names[-1] in ("built_fixture", "fixture")

    custom_repo_node = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "custom_repo"
    )
    custom_repo_source = ast.unparse(custom_repo_node)
    assert "create_disposable_experiment_root" not in custom_repo_source
    assert "build_synthetic_repository" in custom_repo_source


def test_13b_build_synthetic_repository_takes_no_pre_existing_path_argument():
    import inspect

    parameters = inspect.signature(build_synthetic_repository).parameters
    assert "repo_root" not in parameters
    assert "experiment_root" not in parameters
    assert "path" not in parameters
    assert set(parameters) == {"files", "case_id", "git_executable"}


def test_13c_build_case_repository_takes_no_pre_existing_path_argument():
    import inspect

    parameters = inspect.signature(build_case_repository).parameters
    assert "repo_root" not in parameters
    assert "experiment_root" not in parameters
    assert set(parameters) == {"case", "git_executable"}


# -- create_disposable_experiment_root's own contract ---------------------------


def test_create_disposable_experiment_root_refuses_to_stamp_the_orchestrator(
    monkeypatch,
):
    """Belt-and-braces: even the ONE sanctioned creator refuses to authorize
    the orchestrator repository, by making ``tempfile.mkdtemp`` return it --
    proving the check runs on whatever mkdtemp produces, not merely trusting
    that mkdtemp is well-behaved."""
    import ar2.fixtures as fixtures_module

    orchestrator = os.path.realpath(
        os.path.join(os.path.dirname(fixtures_module.__file__), "..", "..", "..")
    )
    monkeypatch.setattr(fixtures_module.tempfile, "mkdtemp", lambda prefix="": orchestrator)
    with pytest.raises(FixtureError, match="orchestrator repository"):
        create_disposable_experiment_root(case_id="should-never-stamp")
    # And no marker was written into the orchestrator repository as a side effect.
    assert not os.path.exists(
        os.path.join(orchestrator, ROOT_AUTHORITY_MARKER_FILENAME)
    )


def test_a_marker_collision_on_a_fresh_root_is_a_hard_invariant_violation(monkeypatch):
    """mkdtemp() guarantees a NEW directory; if a marker is somehow already
    there, the exclusive create must raise rather than silently overwrite it."""
    import ar2.fixtures as fixtures_module

    real_mkdtemp = fixtures_module.tempfile.mkdtemp
    created: list[str] = []

    def poisoned_mkdtemp(prefix=""):
        fresh = real_mkdtemp(prefix=prefix)
        created.append(fresh)
        # Simulate an impossible pre-existing marker at a "fresh" root.
        with open(
            os.path.join(fresh, ROOT_AUTHORITY_MARKER_FILENAME), "w", encoding="utf-8"
        ) as handle:
            handle.write("not a real marker")
        return fresh

    monkeypatch.setattr(fixtures_module.tempfile, "mkdtemp", poisoned_mkdtemp)
    try:
        with pytest.raises(FileExistsError):
            create_disposable_experiment_root(case_id="t1")
    finally:
        for path in created:
            remove_disposable_tree(path)


def test_build_synthetic_repository_supports_binary_content(git_executable):
    built = build_synthetic_repository(
        {"blob.bin": b"\x89PNG\x00\x01\x02binary", "ok.py": "x = 1\n"},
        case_id="binary",
        git_executable=git_executable,
    )
    try:
        on_disk = open(os.path.join(built.repo_root, "blob.bin"), "rb").read()
        assert on_disk == b"\x89PNG\x00\x01\x02binary"
    finally:
        remove_disposable_tree(built.experiment_root)
